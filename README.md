# Next.js Documentation PDF Generator

Automated PDF generation of Next.js documentation with clean extraction and full styling preservation.

## ✨ Features

- 🎨 **Complete Next.js Styling** - All CSS preserved (colors, fonts, code blocks, shadows)
- 📄 **Full-Width Layout** - Content spans entire page for better readability
- 🖼️ **Lazy-Loaded Images** - Waits for all images to fully load
- 🚫 **Clean Output** - Removes navigation, breadcrumbs, "Copy page" buttons, feedback sections
- 📦 **Smart Page Breaks** - Code blocks and cards never split across pages
- 🎯 **No Orphaned Headings** - Headings always stay with their content
- ⚡ **Fast Generation** - ~3-8 seconds per page
- 🔗 **Next Steps Cards** - Preserved with full styling and grid layout

## 🚀 Quick Start

### Local Generation

1. **Install dependencies:**
   ```bash
   pip install requests beautifulsoup4 playwright PyPDF2
   python -m playwright install chromium
   ```

2. **Generate PDFs:**
   ```bash
   # Test with 2 pages per section (default)
   python generate_docs_clean.py

   # Generate all documentation pages
   $env:LIMIT=0; python generate_docs_clean.py
   ```

3. **Output:**
   - Individual PDFs: `pdfs/` folder
   - Merged archive: `NextJS_Docs_Archive.pdf`

### GitHub Actions

1. Go to **Actions** tab in your repository
2. Select **"Next.js Docs PDF (Clean Extraction)"** workflow
3. Click **"Run workflow"**
4. Set `limit` parameter:
   - `0` = All pages
   - `2` = 2 pages per section (testing)
   - Any number = Custom limit
5. Download artifacts when complete

## 🔧 How It Works

### Clean Extraction Process

1. **Fetch Links** - Scrapes Next.js docs for App Router and Pages Router links
2. **Desktop Viewport** - Renders pages at 2560x1440 for optimal layout
3. **Lazy Loading** - Scrolls through page to trigger image loading
4. **Wait for Assets** - Ensures all images load before PDF generation
5. **Remove UI Elements** - Strips breadcrumbs, navigation, copy buttons
6. **Extract Content** - Pulls article HTML and all CSS stylesheets
7. **Rebuild Page** - Creates clean HTML with Next.js styling
8. **Generate PDF** - Renders to PDF with smart page breaks
9. **Merge PDFs** - Combines all pages into single archive

### Smart Features

- **Page Break Prevention:**
  - Code blocks stay intact
  - Card grids don't split
  - Headings never orphaned
  
- **Element Removal:**
  - Breadcrumbs (Next.js Docs > App Router > ...)
  - "Copy page" button
  - "Was this helpful?" feedback
  - Navigation sidebars
  - Header and footer

- **Preserved Elements:**
  - Next Steps cards with grid layout
  - Code syntax highlighting
  - All images and fonts
  - Complete styling

## 📁 Project Structure

```
Next.js-Docs/
├── generate_docs_clean.py          # Main PDF generation script
├── .github/workflows/
│   └── generate-docs-clean.yml     # GitHub Actions workflow
├── pdfs/                            # Individual page PDFs (Git LFS)
├── NextJS_Docs_Archive.pdf         # Merged PDF archive
└── README.md                        # This file
```

## ⚙️ Configuration

### Environment Variables

- **`LIMIT`** - Number of pages per section
  - Default: `2` (local testing)
  - `0` = All pages
  - Any number = Custom limit

### Viewport Settings

- Width: `2560px`
- Height: `1440px`
- Ensures desktop layout rendering

### PDF Settings

- Format: `A4`
- Margins: `1cm` (all sides)
- Background: `Enabled`

## 🎯 Output Quality

### What You Get

✅ Professional PDF with:
- Full Next.js documentation styling
- Syntax-highlighted code blocks
- Properly formatted cards and grids
- All images loaded and displayed
- Clean, readable layout
- No UI clutter

### What's Removed

❌ Unwanted elements:
- Navigation sidebars
- Breadcrumb trails
- Copy page buttons
- Feedback widgets
- Header/footer chrome

## 📊 Performance

- **Speed:** 3-8 seconds per page
- **Quality:** Full CSS preservation
- **Reliability:** Automatic retry on failures
- **Size:** ~900KB for 4 pages (test), varies for full docs

## 🤝 Contributing

This is a personal documentation archiver. Feel free to fork and adapt for your needs!

## 📝 License

This tool is for personal documentation archiving. Next.js documentation belongs to Vercel.
