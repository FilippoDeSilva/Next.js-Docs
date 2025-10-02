#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Starting downloads..."

# Use working directory instead of root
BASE_DIR="$(pwd)/docs_downloads"
CANARY_DIR="$BASE_DIR/canary"
STABLE_DIR="$BASE_DIR/stable"

mkdir -p "$CANARY_DIR" "$STABLE_DIR"

download_docs() {
  local url=$1
  local out_dir=$2
  local label=$3

  echo "⬇️ Downloading Next.js docs ($label) from $url ..."
  httrack "$url" -O "$out_dir" "+*.nextjs.org/*" -v -%v -c -N "%h/%p/%n.%t" || true

  echo "📂 Copying docs into repo folder..."
  if [ -d "$out_dir" ]; then
    mkdir -p "docs/$label"
    cp -r "$out_dir"/* "docs/$label" || echo "⚠️ Nothing copied for $label"
  else
    echo "⚠️ No directory created for $label"
  fi

  echo "📄 Generating PDF..."
  html_files=$(find "docs/$label" -name "*.html" || true)
  if [ -n "$html_files" ]; then
    wkhtmltopdf $html_files "docs/${label}_docs.pdf" || echo "⚠️ PDF generation failed for $label"
  else
    echo "⚠️ No HTML files found for $label, skipping PDF."
  fi

  echo "✅ Finished $label docs"
}

download_docs "https://nextjs.org/docs/canary" "$CANARY_DIR" "canary"
download_docs "https://nextjs.org/docs" "$STABLE_DIR" "stable"