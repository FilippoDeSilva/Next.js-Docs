#!/usr/bin/env bash
set -e

# --- CONFIG ---
OUTPUT_DIR="${OUTPUT_DIR:-nextjs-docs-tmp}"
REPO_DIR="${REPO_DOCS_DIR:-nextjs-docs}"
PDF_DIR="${PDF_DIR:-pdf-docs}"
HTTRACK_CONN="${HTTRACK_CONN:-5}"
THREADS="${THREADS:-2}"
VERSIONS=("stable" "canary")
GH_PAT="${GH_PAT:?Missing GH_PAT env variable}"
PR_BRANCH="${PR_BRANCH:-update-docs}"

mkdir -p "$OUTPUT_DIR" "$REPO_DIR" "$PDF_DIR"

download_version() {
    version="$1"
    URL="https://nextjs.org/docs"
    [ "$version" == "canary" ] && URL="https://nextjs.org/docs/canary"

    OUT_DIR="$OUTPUT_DIR/$version"
    HASH_FILE="$OUTPUT_DIR/${version}_hash.txt"
    PDF_FILE="$PDF_DIR/NextjsDocs-$version.pdf"

    mkdir -p "$OUT_DIR"

    OLD_HASH=""
    [ -f "$HASH_FILE" ] && OLD_HASH=$(cat "$HASH_FILE")
    NEW_HASH=$(curl -s "$URL/sitemap.xml" | md5sum | cut -d ' ' -f1)

    if [ "$OLD_HASH" == "$NEW_HASH" ]; then
        echo "✅ No changes for $version, skipping download."
        return
    fi

    echo "⬇️ Downloading docs for $version from $URL ..."
    LOG_FILE="$OUT_DIR/httrack_$version.log"

    httrack "$URL" -O "$OUT_DIR" "+*.nextjs.org/*" -v --clean -c$HTTRACK_CONN -N "%h/%p/%n.%t" | tee "$LOG_FILE"

    echo "📂 Copying docs into repo folder..."
    rm -rf "$REPO_DIR/$version"
    mkdir -p "$REPO_DIR/$version"
    cp -r "$OUT_DIR"/* "$REPO_DIR/$version"

    echo "$NEW_HASH" > "$HASH_FILE"

    echo "📄 Generating PDF..."
    HTML_FILES=$(find "$OUT_DIR" -name "*.html" | sort)
    if [ ! -z "$HTML_FILES" ]; then
        wkhtmltopdf --enable-local-file-access $HTML_FILES "$PDF_FILE"
        echo "✅ PDF generated: $PDF_FILE"
    else
        echo "⚠️ No HTML files found for $version, skipping PDF."
    fi
}

# --- DOWNLOAD ALL VERSIONS ---
for version in "${VERSIONS[@]}"; do
    download_version "$version"
done

# --- PUSH CHANGES ---
git config --global user.name "GitHub Actions"
git config --global user.email "actions@github.com"
git fetch origin main
git checkout -B "$PR_BRANCH" origin/main
git add "$REPO_DIR" "$PDF_DIR"
git commit -m "Update Next.js Docs: $(date +'%Y-%m-%d')" || echo "No changes"

# Use PAT for authenticated push
git remote set-url origin https://$GH_PAT@github.com/FilippoDeSilva/Next.js-Docs.git
git push -u origin "$PR_BRANCH" --force