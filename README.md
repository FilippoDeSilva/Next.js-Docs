# Next.js Documentation PDF Generator

Automated PDF generation of Next.js documentation with clean extraction and full styling preservation.

## Features

- ✅ **Clean Extraction** - Extracts article content and preserves all Next.js styling
- ✅ **Full-Width Layout** - Content spans the entire page for better readability
- ✅ **Complete Styling** - Includes all CSS (colors, fonts, code blocks, etc.)
- ✅ **Fast Generation** - ~2-6 seconds per page
- ✅ **Image Loading** - Waits for all images to load before PDF generation
- ✅ **Clean Output** - Removes navigation, breadcrumbs, "Copy page" buttons, and feedback sections

## Usage

### Local Generation

1. **Setup environment:**
   ```bash
   pip install requests beautifulsoup4 playwright PyPDF2
   python -m playwright install chromium
   ```

2. **Generate PDFs:**
   ```bash
   # Generate 2 pages per section (for testing)
   python generate_docs_clean.py

   # Generate all pages
   $env:LIMIT=0; python generate_docs_clean.py
   ```

3. **Output:**
   - Individual PDFs in `pdfs/` folder
   - Merged PDF: `NextJS_Docs_Archive.pdf`

### GitHub Actions

Run the workflow manually:
1. Go to **Actions** tab
2. Select **"Next.js Docs PDF (Clean Extraction)"**
3. Click **"Run workflow"**
4. Set limit (0 for all pages, or specific number for testing)
5. Download artifacts when complete

## How It Works

1. **Fetches documentation links** from Next.js docs site
2. **Navigates to each page** with desktop viewport (2560x1440)
3. **Waits for images** to load (networkidle state)
4. **Removes unwanted elements** (breadcrumbs, navigation, feedback sections)
5. **Extracts article HTML** and all CSS stylesheets
6. **Creates clean HTML** with Next.js styling + full-width layout
7. **Generates PDF** with proper formatting
8. **Merges all PDFs** into single archive

## Files

- `generate_docs_clean.py` - Main PDF generation script (recommended)
- `generate_docs_local.py` - Legacy script with DOM manipulation
- `.github/workflows/generate-docs-clean.yml` - GitHub Actions workflow
- `setup_local.bat` - Windows setup script

## Environment Variables

- `LIMIT` - Number of pages per section (default: 2 for local, 0 for GitHub Actions)
  - `0` = Generate all pages
  - `2` = Generate 2 pages per section (App Router + Pages Router)
  - Any number = Limit pages for testing
