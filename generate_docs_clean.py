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
            viewport={'width': 2560, 'height': 1440}
        )
        
        for idx, url in enumerate(links, start=1):
            log(f"\n🌐 ({idx}/{len(links)}) Navigating to: {url}")
            page = await context.new_page()
            
            try:
                start = time.time()
                await page.goto(url, wait_until="load", timeout=25000)
                
                # Wait for images to load (with timeout)
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except:
                    pass  # Continue even if timeout
                
                # Remove unwanted elements before extraction
                await page.evaluate("""() => {
                    // Remove "Was this helpful?" section
                    document.querySelectorAll('[data-feedback-inline]').forEach(el => el.remove());
                    
                    // Remove breadcrumbs and "Copy page" button (not-prose class)
                    document.querySelectorAll('.not-prose').forEach(el => el.remove());
                    
                    // Remove any elements containing "Was this helpful"
                    document.querySelectorAll('*').forEach(el => {
                        if (el.textContent && el.textContent.includes('Was this helpful')) {
                            el.remove();
                        }
                    });
                }""")
                
                # Extract the main content HTML and fetch all stylesheets
                extracted_data = await page.evaluate("""async () => {
                    // Find the main article content
                    const article = document.querySelector('article') || document.querySelector('main');
                    if (!article) return {html: '', css: '', links: []};
                    
                    // Get all inline styles
                    let allCSS = '';
                    document.querySelectorAll('style').forEach(style => {
                        allCSS += style.textContent + '\\n';
                    });
                    
                    // Get all external stylesheet URLs
                    const styleLinks = [];
                    document.querySelectorAll('link[rel="stylesheet"]').forEach(link => {
                        if (link.href) {
                            styleLinks.push(link.href);
                        }
                    });
                    
                    // Fetch external stylesheets
                    for (const url of styleLinks) {
                        try {
                            const response = await fetch(url);
                            const css = await response.text();
                            allCSS += css + '\\n';
                        } catch (e) {
                            console.log('Failed to fetch:', url);
                        }
                    }
                    
                    return {
                        html: article.innerHTML,
                        css: allCSS,
                        links: styleLinks
                    };
                }""")
                
                content_html = extracted_data['html']
                nextjs_css = extracted_data['css']
                
                title = await page.title()
                log(f"📝 Title: {title} | ⏱️ {round(time.time() - start, 2)}s")
                
                # Create a clean HTML page with Next.js styling + full-width layout
                clean_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>{title}</title>
                    <style>
                        /* Next.js original styles */
                        {nextjs_css}
                    </style>
                    <style>
                        /* Override for full-width layout */
                        body {{
                            padding: 2rem !important;
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
                    margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"}
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
