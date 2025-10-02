#!/bin/bash
set -e

OUTPUT_DIR="nextjs-docs-tmp"
PDF_DIR="pdf-docs"
HTTRACK_CONN="${HTTRACK_CONN:-5}"

VERSIONS=("canary" "stable")

echo "🚀 Starting downloads..."

mkdir -p "$OUTPUT_DIR"
mkdir -p "$PDF_DIR"

for VERSION in "${VERSIONS[@]}"; do
  if [ "$VERSION" == "stable" ]; then
    URL="https://nextjs.org/docs"
  else
    URL="https://nextjs.org/docs/$VERSION"
  fi

  TARGET_DIR="$OUTPUT_DIR/$VERSION"
  LOG_FILE="$TARGET_DIR/httrack.log"

  echo "⬇️ Downloading Next.js docs ($VERSION) from $URL ..."
  mkdir -p "$TARGET_DIR"

  httrack "$URL" \
    -O "$TARGET_DIR" \
    "+*.nextjs.org/*" \
    -c"$HTTRACK_CONN" \
    -v \
    -N "%h%p/%n.%t" \
    --disable-security-limits \
    2>&1 | tee "$LOG_FILE"

  echo "📄 Generating PDF for $VERSION..."
  HTML_FILE=$(find "$TARGET_DIR" -name "index.html" | head -n 1)
  if [ -n "$HTML_FILE" ]; then
    wkhtmltopdf "$HTML_FILE" "$PDF_DIR/$VERSION-docs.pdf" || echo "⚠️ Failed to generate PDF for $VERSION"
  else
    echo "⚠️ No HTML found for $VERSION, skipping PDF"
  fi

  echo "✅ Finished $VERSION docs"
done