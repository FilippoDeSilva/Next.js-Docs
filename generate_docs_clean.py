import asyncio
import os
import time
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import requests
from PyPDF2 import PdfMerger

BASE_URL = "https://nextjs.org/docs"
HEADERS = {"User-Agent": "Mozilla/5.0"}
LIMIT = int(os.getenv("LIMIT", "2"))
THEME = os.getenv("THEME", "dark").lower()  # 'dark' or 'light'

def log(msg):
    print(msg, flush=True)

def get_links():
    """Fetch all documentation links"""
    resp = requests.get(BASE_URL, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    
    app_links = []
    pages_links = []
    
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/docs/app") and href not in app_links:
            app_links.append(BASE_URL.replace("/docs", "") + href)
        elif href.startswith("/docs/pages") and href not in pages_links:
            pages_links.append(BASE_URL.replace("/docs", "") + href)
    
    if LIMIT > 0:
        app_links = app_links[:LIMIT]
        pages_links = pages_links[:LIMIT]
    
    log(f"📄 Found {len(app_links)} App and {len(pages_links)} Pages docs (limit={LIMIT})")
    return {"AppRouter": app_links, "PagesRouter": pages_links}

def sanitize_filename(text):
    return "".join(c for c in text if c.isalnum() or c in (" ", "_", "-", ".")).strip().replace(" ", "_")

async def render_group(group, links):
    """Render documentation with clean HTML extraction"""
    os.makedirs("pdfs", exist_ok=True)
    pdf_paths = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={'width': 2560, 'height': 1440},
            color_scheme='dark',  # Force dark mode preference
            forced_colors='none'
        )
        
        # Emulate dark mode media query
        await context.add_init_script("""
            Object.defineProperty(window, 'matchMedia', {
                writable: true,
                value: (query) => ({
                    matches: query === '(prefers-color-scheme: dark)',
                    media: query,
                    onchange: null,
                    addListener: () => {},
                    removeListener: () => {},
                    addEventListener: () => {},
                    removeEventListener: () => {},
                    dispatchEvent: () => {},
                }),
            });
        """)
        
        for idx, url in enumerate(links, start=1):
            log(f"\n🌐 ({idx}/{len(links)}) Navigating to: {url}")
            page = await context.new_page()
            
            try:
                start = time.time()
                await page.goto(url, wait_until="load", timeout=25000)
                
                # Toggle theme based on preference
                if THEME == 'dark':
                    try:
                        await page.wait_for_selector('[data-theme-switcher]', timeout=3000)
                        await page.evaluate("""() => {
                            const switcher = document.querySelector('[data-theme-switcher="true"]');
                            if (switcher) switcher.click();
                        }""")
                        await page.wait_for_timeout(1000)
                        log("🌙 Dark mode enabled")
                    except:
                        log("⚠️ Dark mode toggle not found")
                else:
                    log("☀️ Light mode (default)")
                
                # Scroll to trigger lazy loading
                await page.evaluate("""async () => {
                    const scrollStep = 300;
                    const scrollDelay = 100;
                    const totalHeight = document.body.scrollHeight;
                    
                    for (let i = 0; i < totalHeight; i += scrollStep) {
                        window.scrollTo(0, i);
                        await new Promise(r => setTimeout(r, scrollDelay));
                    }
                    window.scrollTo(0, 0); // Scroll back to top
                }""")
                
                # Wait for all images to load
                await page.evaluate("""async () => {
                    const images = Array.from(document.images);
                    await Promise.all(
                        images.map(img => {
                            if (img.complete) return Promise.resolve();
                            return new Promise((resolve) => {
                                img.onload = resolve;
                                img.onerror = resolve;
                                // Timeout after 3 seconds per image
                                setTimeout(resolve, 3000);
                            });
                        })
                    );
                }""")
                
                # Wait for network to be idle
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except:
                    pass  # Continue even if timeout
                
                # Remove unwanted elements before extraction (but keep code blocks and cards)
                await page.evaluate("""() => {
                    // Remove "Was this helpful?" section
                    document.querySelectorAll('[data-feedback-inline]').forEach(el => el.remove());
                    
                    // Remove breadcrumbs and "Copy page" button by exact structure
                    document.querySelectorAll('.not-prose.flex.flex-col').forEach(el => {
                        // Check if it has breadcrumb structure (flex-wrap with links)
                        const hasBreadcrumbs = el.querySelector('.flex.flex-wrap.items-center');
                        // Check if it has Copy page button
                        const hasCopyButton = el.textContent.includes('Copy page');
                        
                        if (hasBreadcrumbs || hasCopyButton) {
                            el.remove();
                        }
                    });
                    
                    // Backup: Remove any div with "Copy page" button
                    document.querySelectorAll('button').forEach(btn => {
                        if (btn.textContent.includes('Copy page')) {
                            // Remove parent container
                            let parent = btn.parentElement;
                            while (parent && !parent.classList.contains('not-prose')) {
                                parent = parent.parentElement;
                            }
                            if (parent) parent.remove();
                        }
                    });
                    
                    // Remove only the specific "Was this helpful" feedback widget
                    document.querySelectorAll('*').forEach(el => {
                        const text = el.textContent || '';
                        // Skip pre, code elements, and links
                        if (el.tagName === 'PRE' || el.tagName === 'CODE' || el.tagName === 'A') return;
                        // Only remove if it's specifically the feedback text
                        if (text.trim() === 'Was this helpful?' || (text.includes('Was this helpful') && text.length < 50)) {
                            el.remove();
                        }
                    });
                }""")
                
                # Extract the main content HTML and fetch all stylesheets
                theme_mode = THEME  # Pass theme to JavaScript
                js_code = f"""async () => {{
                    // Find the main article content
                    const article = document.querySelector('article') || document.querySelector('main');
                    if (!article) return {{html: '', css: '', links: []}};
                    
                    // Remove theme-specific images based on current theme
                    const theme = '{theme_mode}';
                    if (theme === 'dark') {{
                        // Remove light mode images (they have dark-theme:hidden class)
                        article.querySelectorAll('img.dark-theme\\\\:hidden').forEach(img => {{
                            img.remove();
                        }});
                        
                        // Show dark mode images (remove hidden class)
                        article.querySelectorAll('img.hidden.dark-theme\\\\:block').forEach(img => {{
                            img.classList.remove('hidden');
                        }});
                    }} else {{
                        // Remove dark mode images (they have dark-theme:block class)
                        article.querySelectorAll('img.dark-theme\\\\:block').forEach(img => {{
                            img.remove();
                        }});
                        
                        // Show light mode images (remove dark-theme:hidden if any)
                        article.querySelectorAll('img.dark-theme\\\\:hidden').forEach(img => {{
                            img.classList.remove('dark-theme:hidden');
                        }});
                    }}
                    
                    // Get all inline styles
                    let allCSS = '';
                    document.querySelectorAll('style').forEach(style => {{
                        allCSS += style.textContent + '\\n';
                    }});
                    
                    // Get all external stylesheet URLs
                    const styleLinks = [];
                    document.querySelectorAll('link[rel="stylesheet"]').forEach(link => {{
                        if (link.href) {{
                            styleLinks.push(link.href);
                        }}
                    }});
                    
                    // Fetch external stylesheets
                    for (const url of styleLinks) {{
                        try {{
                            const response = await fetch(url);
                            const css = await response.text();
                            allCSS += css + '\\n';
                        }} catch (e) {{
                            console.log('Failed to fetch:', url);
                        }}
                    }}
                    
                    return {{
                        html: article.innerHTML,
                        css: allCSS,
                        links: styleLinks
                    }};
                }}"""
                extracted_data = await page.evaluate(js_code)
                
                content_html = extracted_data['html']
                nextjs_css = extracted_data['css']
                
                title = await page.title()
                log(f"📝 Title: {title} | ⏱️ {round(time.time() - start, 2)}s")
                
                # Create a clean HTML page with Next.js styling + full-width layout
                theme_class = 'class="dark" data-theme="dark"' if THEME == 'dark' else ''
                page_bg = '#000' if THEME == 'dark' else '#fff'
                
                clean_html = f"""
                <!DOCTYPE html>
                <html {theme_class}>
                <head>
                    <meta charset="UTF-8">
                    <title>{title}</title>
                    <style>
                        /* Next.js original styles */
                        {nextjs_css}
                    </style>
                    <style>
                        /* PDF paper with theme-based background */
                        @page {{
                            background-color: {page_bg};
                            margin: 2cm 3cm;
                        }}
                        
                        /* Full-width layout */
                        body {{
                            padding: 0 !important;
                            max-width: 100% !important;
                            margin: 0 !important;
                        }}
                        
                        /* Ensure content uses full width */
                        article, main, div {{
                            max-width: 100% !important;
                        }}
                        
                        /* Hide any remaining navigation elements */
                        nav, aside, header, footer {{
                            display: none !important;
                        }}
                        
                        /* Prevent page breaks inside cards and code blocks */
                        .grid > a,
                        .grid > div,
                        pre,
                        pre code,
                        div:has(pre),
                        figure:has(pre),
                        [class*="card"] {{
                            page-break-inside: avoid !important;
                            break-inside: avoid !important;
                            -webkit-column-break-inside: avoid !important;
                        }}
                        
                        /* Keep grid containers together */
                        .grid {{
                            page-break-inside: avoid !important;
                            break-inside: avoid !important;
                        }}
                        
                        /* Prevent orphaned code blocks */
                        pre {{
                            page-break-before: auto !important;
                            page-break-after: auto !important;
                            orphans: 3 !important;
                            widows: 3 !important;
                        }}
                        
                        /* Prevent orphaned headings - keep with following content */
                        h1, h2, h3, h4, h5, h6 {{
                            page-break-after: avoid !important;
                            break-after: avoid !important;
                            orphans: 3 !important;
                            widows: 3 !important;
                        }}
                        
                        /* Keep headings with at least some following content */
                        h1, h2, h3 {{
                            page-break-inside: avoid !important;
                            break-inside: avoid !important;
                        }}
                        
                        /* Hide breadcrumbs and copy button specifically */
                        .not-prose:has(a[href*="docs"]):not(:has(.grid)),
                        button:has-text("Copy page"),
                        div:has(button[aria-label*="Copy"]) {{
                            display: none !important;
                        }}
                    </style>
                </head>
                <body>
                    {content_html}
                </body>
                </html>
                """
                
                # Set the clean HTML content
                await page.set_content(clean_html, wait_until="load")
                
                # Generate PDF
                safe_title = sanitize_filename(title) or f"{group}_{idx:02d}"
                filename = f"pdfs/{group}_{idx:02d}_{safe_title}.pdf"
                await page.pdf(
                    path=filename,
                    format="A4",
                    print_background=True,
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                    prefer_css_page_size=True
                )
                log(f"📦 Saved PDF: {filename}")
                pdf_paths.append(filename)
                
            except Exception as e:
                log(f"❌ Failed to render {url}: {e}")
            finally:
                await page.close()
        
        await browser.close()
    
    return pdf_paths

async def main():
    groups = get_links()
    all_pdfs = []
    
    for group_name, group_links in groups.items():
        pdfs = await render_group(group_name, group_links)
        all_pdfs.extend(pdfs)
    
    if not all_pdfs:
        log("⚠️ No PDFs generated — exiting.")
        return
    
    # Merge all PDFs
    log(f"\n🧩 Merging {len(all_pdfs)} PDFs into: NextJS_Docs_Archive.pdf")
    merger = PdfMerger()
    for pdf_path in all_pdfs:
        log(f"➕ Adding: {pdf_path}")
        merger.append(pdf_path)
    
    merger.write("NextJS_Docs_Archive.pdf")
    merger.close()
    log("🎉 Final PDF ready: NextJS_Docs_Archive.pdf")

if __name__ == "__main__":
    asyncio.run(main())
