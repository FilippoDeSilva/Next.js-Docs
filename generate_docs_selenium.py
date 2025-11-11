import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import requests
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT
from PyPDF2 import PdfMerger
import base64
from io import BytesIO

BASE_URL = "https://nextjs.org/docs"
HEADERS = {"User-Agent": "Mozilla/5.0"}
LIMIT = int(os.getenv("LIMIT", "2"))
THEME = os.getenv("THEME", "dark").lower()

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

def render_group(group, links):
    """Render documentation using Selenium + direct PDF generation"""
    os.makedirs("pdfs", exist_ok=True)
    pdf_paths = []
    
    theme_icon = "🌙" if THEME == 'dark' else "☀️"
    log(f"\n{theme_icon} Theme preference: {THEME.upper()}")
    
    # Setup Chrome with headless mode and theme preferences
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=2560,1440")
    chrome_options.add_argument("--hide-scrollbars")
    
    # Force dark mode preference at browser level
    if THEME == 'dark':
        chrome_options.add_argument("--force-dark-mode")
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.prefers_color_scheme": 1  # 1 = dark, 2 = light
        })
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        for idx, url in enumerate(links, start=1):
            log(f"\n🌐 ({idx}/{len(links)}) Navigating to: {url}")
            start = time.time()
            
            driver.get(url)
            time.sleep(3)  # Wait for page load
            
            # Toggle theme based on preference
            if THEME == 'dark':
                try:
                    # Wait for the specific theme switcher button
                    theme_btn = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'button[data-theme-switcher="true"][aria-label*="dark theme"]'))
                    )
                    
                    # Check if already in dark mode
                    is_dark = driver.execute_script("""
                        return document.documentElement.classList.contains('dark') || 
                               document.documentElement.getAttribute('data-theme') === 'dark';
                    """)
                    
                    if not is_dark:
                        # Click to enable dark mode
                        driver.execute_script("arguments[0].click();", theme_btn)
                        time.sleep(3)  # Wait for theme to apply and images to swap
                        
                        # Verify dark mode is now applied
                        is_dark = driver.execute_script("""
                            return document.documentElement.classList.contains('dark') || 
                                   document.documentElement.getAttribute('data-theme') === 'dark';
                        """)
                        
                        if is_dark:
                            log("🌙 Dark mode enabled and verified")
                        else:
                            log("⚠️ Dark mode not applied after click")
                    else:
                        log("🌙 Dark mode already active")
                        
                except Exception as e:
                    log(f"⚠️ Dark mode toggle error: {e}")
            else:
                log("☀️ Light mode (default)")
            
            # Scroll to load all lazy images (including theme-specific ones)
            driver.execute_script("""
                const scrollStep = 300;
                const scrollDelay = 100;
                const totalHeight = document.body.scrollHeight;
                
                async function scrollPage() {
                    for (let i = 0; i < totalHeight; i += scrollStep) {
                        window.scrollTo(0, i);
                        await new Promise(r => setTimeout(r, scrollDelay));
                    }
                    window.scrollTo(0, 0);
                }
                scrollPage();
            """)
            time.sleep(3)
            
            # Wait for all images to load (including theme-specific ones)
            driver.execute_script("""
                const images = Array.from(document.images);
                Promise.all(
                    images.map(img => {
                        if (img.complete) return Promise.resolve();
                        return new Promise((resolve) => {
                            img.onload = resolve;
                            img.onerror = resolve;
                            setTimeout(resolve, 5000);
                        });
                    })
                );
            """)
            time.sleep(2)
            
            # Force load ALL images by scrolling them into view and triggering load
            driver.execute_script("""
                return new Promise(async (resolve) => {
                    const article = document.querySelector('article') || document.querySelector('main');
                    if (!article) {
                        resolve();
                        return;
                    }
                    
                    const images = Array.from(article.querySelectorAll('img'));
                    console.log('Total images found:', images.length);
                    
                    if (images.length === 0) {
                        resolve();
                        return;
                    }
                    
                    // Force each image to load by scrolling into view and setting src from srcset
                    for (const img of images) {
                        // Scroll image into view to trigger lazy loading
                        img.scrollIntoView({ behavior: 'instant', block: 'center' });
                        
                        // If image has srcset but no proper src, set it
                        if (img.srcset && (!img.src || img.src.includes('data:image'))) {
                            const srcsetParts = img.srcset.split(',')[0].trim().split(' ');
                            if (srcsetParts[0]) {
                                img.src = srcsetParts[0];
                            }
                        }
                        
                        // Wait a bit for lazy loading to trigger
                        await new Promise(r => setTimeout(r, 100));
                    }
                    
                    // Now wait for all images to actually load
                    const loadPromises = images.map(img => {
                        return new Promise((imgResolve) => {
                            if (img.complete && img.naturalWidth > 0) {
                                console.log('Image already loaded:', img.alt);
                                imgResolve();
                            } else {
                                console.log('Waiting for image:', img.alt, img.src);
                                img.onload = () => {
                                    console.log('Image loaded:', img.alt);
                                    imgResolve();
                                };
                                img.onerror = () => {
                                    console.log('Image error:', img.alt);
                                    imgResolve();
                                };
                                // Timeout per image
                                setTimeout(imgResolve, 5000);
                            }
                        });
                    });
                    
                    await Promise.all(loadPromises);
                    console.log('All images loaded');
                    resolve();
                });
            """)
            time.sleep(2)
            
            # Extract content and ALL CSS + convert images to base64
            extracted_data = driver.execute_script("""
                async function extractContent() {
                    // Find the main article content
                    const article = document.querySelector('article') || document.querySelector('main');
                    if (!article) return {html: '', css: '', links: []};
                    
                    // Remove unwanted elements from article
                    article.querySelectorAll('[data-feedback-inline]').forEach(el => el.remove());
                    article.querySelectorAll('.not-prose').forEach(el => {
                        if (el.textContent.includes('Copy page')) {
                            el.remove();
                        }
                    });
                    
                    // Remove theme-specific images based on current theme (BEFORE base64 conversion)
                    const theme = '""" + THEME + """';
                    if (theme === 'dark') {
                        // Dark mode: Remove light images, show dark images
                        article.querySelectorAll('img').forEach(img => {
                            // Remove light mode images (have "dark-theme:hidden" in class)
                            if (img.className.includes('dark-theme:hidden')) {
                                img.remove();
                            }
                            // Show dark mode images (remove "hidden" class)
                            else if (img.className.includes('dark-theme:block')) {
                                img.classList.remove('hidden');
                                img.style.display = 'block';
                            }
                        });
                    } else {
                        // Light mode: Remove dark images, keep light images
                        article.querySelectorAll('img').forEach(img => {
                            // Remove dark mode images (have "dark-theme:block" in class)
                            if (img.className.includes('dark-theme:block')) {
                                img.remove();
                            }
                            // Ensure light mode images are visible (remove any hiding classes)
                            else if (img.className.includes('dark-theme:hidden')) {
                                img.classList.remove('dark-theme:hidden');
                                img.style.display = 'block';
                            }
                        });
                    }
                    
                    // Remove image placeholders/skeletons (they show as gray boxes)
                    article.querySelectorAll('span[data-placeholder], div[data-placeholder]').forEach(el => el.remove());
                    article.querySelectorAll('span[style*="background"], div[style*="background"]').forEach(el => {
                        // Remove elements that look like skeleton loaders (gray backgrounds)
                        const style = el.getAttribute('style') || '';
                        if (style.includes('background') && !el.querySelector('img') && el.textContent.trim() === '') {
                            el.remove();
                        }
                    });
                    
                    // Convert remaining images to base64 data URLs and remove placeholders
                    const imagePromises = Array.from(article.querySelectorAll('img')).map(async (img) => {
                        // Make sure image src is absolute URL
                        if (img.src && !img.src.startsWith('data:') && !img.src.startsWith('http')) {
                            img.src = new URL(img.src, window.location.origin).href;
                        }
                        
                        if (!img.src || img.src.startsWith('data:')) {
                            return;
                        }
                        
                        try {
                            const response = await fetch(img.src);
                            const blob = await response.blob();
                            const reader = new FileReader();
                            
                            return new Promise((resolve) => {
                                reader.onloadend = () => {
                                    img.src = reader.result;
                                    img.removeAttribute('srcset');
                                    
                                    // Remove placeholder siblings (they're usually span or div next to img)
                                    const parent = img.parentElement;
                                    if (parent) {
                                        // Remove all sibling spans/divs that look like placeholders
                                        Array.from(parent.children).forEach(child => {
                                            if (child !== img && (child.tagName === 'SPAN' || child.tagName === 'DIV')) {
                                                const style = child.getAttribute('style') || '';
                                                const className = child.className || '';
                                                // Remove if it has background styling or placeholder-like classes
                                                if (style.includes('background') || className.includes('placeholder') || 
                                                    className.includes('skeleton') || child.textContent.trim() === '') {
                                                    child.remove();
                                                }
                                            }
                                        });
                                    }
                                    
                                    resolve();
                                };
                                reader.onerror = () => resolve();
                                reader.readAsDataURL(blob);
                            });
                        } catch (e) {
                            console.log('Failed to convert image:', img.src);
                        }
                    });
                    
                    await Promise.all(imagePromises);
                    
                    // Final cleanup: remove any remaining empty spans/divs that might be placeholders
                    article.querySelectorAll('span, div').forEach(el => {
                        if (el.children.length === 0 && el.textContent.trim() === '') {
                            const style = el.getAttribute('style') || '';
                            if (style.includes('background') || style.includes('width') && style.includes('height')) {
                                el.remove();
                            }
                        }
                    });
                    
                    // Get all inline styles
                    let allCSS = '';
                    document.querySelectorAll('style').forEach(style => {
                        allCSS += style.textContent + '\\n';
                    });
                    
                    // Get all external stylesheets
                    const styleLinks = Array.from(document.querySelectorAll('link[rel="stylesheet"]'))
                        .map(link => link.href)
                        .filter(href => href);
                    
                    return {
                        html: article.innerHTML,
                        css: allCSS,
                        links: styleLinks
                    };
                }
                
                return extractContent();
            """)
            
            content_html = extracted_data['html']
            nextjs_css = extracted_data['css']
            title = driver.title
            
            # Fetch external stylesheets
            for css_url in extracted_data['links']:
                try:
                    import requests
                    response = requests.get(css_url, timeout=5)
                    nextjs_css += response.text + '\n'
                except:
                    pass
            
            log(f"📝 Title: {title} | ⏱️ {round(time.time() - start, 2)}s")
            
            # Create clean HTML with Next.js styling (exactly like Playwright version)
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
                    /* PDF formatting */
                    @page {{
                        background-color: {page_bg};
                        margin: 2cm 3cm;
                    }}
                    
                    body {{
                        padding: 0 !important;
                        max-width: 100% !important;
                        margin: 0 !important;
                    }}
                    
                    article, main, div {{
                        max-width: 100% !important;
                    }}
                    
                    nav, aside, header, footer {{
                        display: none !important;
                    }}
                    
                    /* Prevent page breaks inside code blocks - move to next page if needed */
                    pre, pre code, figure:has(pre), div:has(pre) {{
                        page-break-inside: avoid !important;
                        break-inside: avoid !important;
                        page-break-before: auto !important;
                    }}
                    
                    /* Keep grid items together */
                    .grid > a, .grid > div {{
                        page-break-inside: avoid !important;
                        break-inside: avoid !important;
                    }}
                    
                    /* Keep headings with following content */
                    h1, h2, h3, h4, h5, h6 {{
                        page-break-after: avoid !important;
                        break-after: avoid !important;
                        orphans: 4 !important;
                        widows: 4 !important;
                    }}
                    
                    /* Prevent orphaned callouts and blockquotes */
                    blockquote, aside, div[class*="callout"], div[class*="note"], 
                    div[class*="warning"], div[class*="info"], div[role="note"] {{
                        page-break-inside: avoid !important;
                        break-inside: avoid !important;
                        page-break-after: avoid !important;
                        orphans: 4 !important;
                        widows: 4 !important;
                    }}
                    
                    /* Keep paragraphs from being orphaned */
                    p {{
                        orphans: 4 !important;
                        widows: 4 !important;
                    }}
                    
                    /* Keep list items together */
                    li {{
                        page-break-inside: avoid !important;
                        orphans: 3 !important;
                        widows: 3 !important;
                    }}
                    
                    /* Ensure images render properly without placeholders */
                    img {{
                        max-width: 100% !important;
                        height: auto !important;
                        display: block !important;
                    }}
                    
                    /* Hide any skeleton loaders or placeholders */
                    [data-placeholder], span[style*="background"]:empty {{
                        display: none !important;
                    }}
                </style>
            </head>
            <body>
                {content_html}
            </body>
            </html>
            """
            
            # Load the clean HTML
            driver.execute_script("document.open(); document.write(arguments[0]); document.close();", clean_html)
            time.sleep(2)  # Wait for styles to apply
            
            # Generate PDF directly using Selenium's print_page
            safe_title = sanitize_filename(title) or f"{group}_{idx:02d}"
            filename = f"pdfs/{group}_{idx:02d}_{safe_title}.pdf"
            
            # Use Selenium's PDF generation (CSS @page handles margins)
            print_options = {
                'paperWidth': 8.27,  # A4 width in inches
                'paperHeight': 11.69,  # A4 height in inches
                'marginTop': 0,  # CSS @page handles margins
                'marginBottom': 0,
                'marginLeft': 0,
                'marginRight': 0,
                'printBackground': True,
                'preferCSSPageSize': True,
                'displayHeaderFooter': False,
                'scale': 1.0,
            }
            
            pdf_data = driver.execute_cdp_cmd('Page.printToPDF', print_options)
            
            # Save PDF
            with open(filename, 'wb') as f:
                f.write(base64.b64decode(pdf_data['data']))
            
            log(f"📦 Saved PDF: {filename}")
            pdf_paths.append(filename)
            
    finally:
        driver.quit()
    
    return pdf_paths

def main():
    groups = get_links()
    all_pdfs = []
    
    for group_name, group_links in groups.items():
        pdfs = render_group(group_name, group_links)
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
    main()
