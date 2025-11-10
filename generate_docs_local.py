import asyncio
from playwright.async_api import async_playwright
import requests, os, time
from bs4 import BeautifulSoup
from PyPDF2 import PdfMerger

BASE_URL = "https://nextjs.org/docs"
HEADERS = {"User-Agent": "Mozilla/5.0"}
LIMIT = int(os.getenv("LIMIT", "2"))  # Default to 2 pages for testing, set LIMIT=0 for all

def log(msg):
    print(msg, flush=True)

def get_links():
    log("🔍 Fetching documentation links...")
    html = requests.get(BASE_URL, headers=HEADERS, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")

    app_links, pages_links = [], []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("/docs/"):
            continue
        full = f"https://nextjs.org{href}"
        if "/docs/app/" in href and full not in app_links:
            app_links.append(full)
        elif "/docs/pages/" in href and full not in pages_links:
            pages_links.append(full)

    if LIMIT > 0:
        app_links = app_links[:LIMIT]
        pages_links = pages_links[:LIMIT]

    log(f"📄 Found {len(app_links)} App and {len(pages_links)} Pages docs (limit={LIMIT})")
    return app_links, pages_links

async def wait_for_images(page, timeout_sec=10):
    async def images_ready():
        return await page.evaluate("""() => {
            const imgs = Array.from(document.images);
            return imgs.length === 0 || imgs.every(img => img.complete && img.naturalHeight !== 0);
        }""")
    start = time.time()
    while time.time() - start < timeout_sec:
        if await images_ready():
            return True
        await asyncio.sleep(0.5)
    return False

async def wait_for_fonts(page, timeout_sec=10):
    try:
        await asyncio.wait_for(page.evaluate("document.fonts.ready.then(() => true)"), timeout=timeout_sec)
        return True
    except asyncio.TimeoutError:
        return False

async def trigger_lazy_loading(page, max_steps=20):
    # Smoothly scroll to bottom to trigger lazy-loaded content
    await page.evaluate("""async (steps) => {
        const total = steps;
        for (let i = 0; i < total; i++) {
            window.scrollBy(0, Math.floor(window.innerHeight * 0.8));
            await new Promise(r => setTimeout(r, 200));
        }
        window.scrollTo(0, document.body.scrollHeight);
    }""", max_steps)

def sanitize_filename(text):
    return "".join(c for c in text if c.isalnum() or c in (" ", "_", "-", ".")).strip().replace(" ", "_")

async def render_group(group, links):
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
                await trigger_lazy_loading(page)

                # Wait for images and fonts with bounded timeouts
                imgs_ok = await wait_for_images(page, timeout_sec=12)
                fonts_ok = await wait_for_fonts(page, timeout_sec=8)
                title = await page.title()
                log(f"📝 Title: {title} | 🖼️ Images: {'ready' if imgs_ok else 'timeout'} | 🔤 Fonts: {'ready' if fonts_ok else 'timeout'} | ⏱️ {round(time.time() - start, 2)}s")

                # Remove unwanted site chrome using exact Next.js selectors
                await page.evaluate("""() => {
                    // Remove header (exact class from Next.js docs)
                    const header = document.querySelector('header.bg-background-100');
                    if (header) header.remove();
                    
                    // Remove sidebar navigation (exact structure from Next.js docs)
                    const sidebar = document.querySelector('nav.styled-scrollbar');
                    if (sidebar && sidebar.parentElement) {
                        sidebar.parentElement.remove();
                    }
                    
                    // Remove breadcrumb navigation and "Copy page" button (not-prose class)
                    document.querySelectorAll('.not-prose').forEach(el => el.remove());
                    
                    // Remove "Using App Router" and "Latest Version" selector boxes
                    document.querySelectorAll('button[role="combobox"]').forEach(el => {
                        if (el.parentElement && el.parentElement.classList.contains('pb-px')) {
                            el.parentElement.remove();
                        } else {
                            el.remove();
                        }
                    });
                    
                    // Remove pagination footer (nav with aria-label="pagination")
                    document.querySelectorAll('nav[aria-label="pagination"]').forEach(el => el.remove());
                    
                    // Remove "Was this helpful?" feedback section
                    document.querySelectorAll('[data-feedback-inline]').forEach(el => el.remove());
                    
                    // Remove all nav elements outside main content
                    document.querySelectorAll('nav').forEach(nav => {
                        if (!nav.closest('main')) nav.remove();
                    });
                    
                    // Remove footer
                    document.querySelectorAll('footer').forEach(el => el.remove());
                    
                    // Remove aside elements (sidebar boxes)
                    document.querySelectorAll('aside').forEach(el => el.remove());
                }""")
                
                # Apply print-optimized CSS for full-width content
                await page.add_style_tag(content="""
                    /* Hide navigation elements */
                    header, nav, aside, footer, 
                    button[role="combobox"],
                    [data-feedback-inline],
                    nav[aria-label="pagination"],
                    .not-prose {
                        display: none !important;
                    }
                    
                    /* Print-optimized: Force content to use available width */
                    @media print {
                        body, html {
                            margin: 0 !important;
                            padding: 1.5rem !important;
                        }
                        
                        main, article {
                            max-width: 100% !important;
                            width: 100% !important;
                            margin: 0 !important;
                        }
                    }
                    
                    /* Also apply for screen (PDF generation) */
                    body {
                        margin: 0 !important;
                        padding: 1.5rem !important;
                    }
                    
                    main, article {
                        max-width: 100% !important;
                        width: 100% !important;
                        margin: 0 !important;
                    }
                """)

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

def merge_pdfs(paths, output):
    log(f"\n🧩 Merging {len(paths)} PDFs into: {output}")
    merger = PdfMerger()
    for path in paths:
        log(f"➕ Adding: {path}")
        merger.append(path)
    merger.write(output)
    merger.close()
    log(f"🎉 Final PDF ready: {output}")

async def main():
    app_links, pages_links = get_links()
    app_pdfs = await render_group("AppRouter", app_links)
    pages_pdfs = await render_group("PagesRouter", pages_links)
    all_pdfs = app_pdfs + pages_pdfs
    if not all_pdfs:
        log("⚠️ No PDFs generated — exiting.")
        return
    merge_pdfs(all_pdfs, "NextJS_Docs_Archive.pdf")

if __name__ == "__main__":
    asyncio.run(main())
