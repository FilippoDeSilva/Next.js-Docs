#!/usr/bin/env bash
set -e

# Output directories
OUTPUT_DIR="nextjs-docs-tmp"
REPO_DOCS_DIR="nextjs-docs"
PDF_DIR="pdf-docs"

# HTTrack settings
HTTRACK_CONN=5
THREADS=2

# Versions to download
VERSIONS=("stable" "canary")

mkdir -p "$OUTPUT_DIR" "$REPO_DOCS_DIR" "$PDF_DIR"

download_version() {
  version="$1"
  
  if [ "$version" == "canary" ]; then
    URL="https://nextjs.org/docs/canary"
  else
    URL="https://nextjs.org/docs"
  fi

  OUT_DIR="$OUTPUT_DIR/$version"
  REPO_DIR="$REPO_DOCS_DIR/$version"
  PDF_FILE="$PDF_DIR/NextjsDocs-$version.pdf"

  mkdir -p "$OUT_DIR" "$REPO_DIR"

  echo "⬇️ Downloading Next.js docs ($version) from $URL ..."
  LOG_FILE="$OUT_DIR/httrack.log"
  
  # Run HTTrack
  httrack "$URL" -O "$OUT_DIR" "+*.nextjs.org/*" -v --clean -c$HTTRACK_CONN -N "%h/%p/%n.%t" | tee "$LOG_FILE"

  echo "📂 Copying docs into repo folder..."
  rm -rf "$REPO_DIR"/*
  cp -r "$OUT_DIR"/* "$REPO_DIR"

  echo "📄 Generating PDF..."
  HTML_FILES=$(find "$OUT_DIR" -name "*.html" | sort)
  if [ ! -z "$HTML_FILES" ]; then
    wkhtmltopdf --enable-local-file-access $HTML_FILES "$PDF_FILE"
    echo "✅ PDF generated: $PDF_FILE"
  else
    echo "⚠️ No HTML files found for $version, skipping PDF."
  fi

  echo "✅ Finished $version docs"
}

export -f download_version

# Parallel download
echo "🚀 Starting downloads..."
parallel -j $THREADS download_version ::: "${VERSIONS[@]}"