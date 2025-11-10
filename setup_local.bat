@echo off
echo Installing Python dependencies...
pip install requests beautifulsoup4 playwright PyPDF2

echo.
echo Installing Playwright browsers...
python -m playwright install chromium

echo.
echo Setup complete! You can now run: python generate_docs_local.py
echo.
echo To generate ALL pages, run: 
echo   $env:LIMIT=0; python generate_docs_local.py
echo.
echo To generate 5 pages per section, run: 
echo   $env:LIMIT=5; python generate_docs_local.py
pause
