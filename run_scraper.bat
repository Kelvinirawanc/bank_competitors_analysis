@echo off
setlocal EnableExtensions
cd /d %~dp0

color 0A

echo ============================================================
echo BANK COMPETITORS TRACKER
echo GOOGLE PLAY REVIEW COLLECTION
echo ============================================================
echo.

echo [1/3] Checking Python...
where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found in PATH.
    echo Install Python 3.10+ and enable Add Python to PATH.
    pause
    exit /b 1
)
python --version

echo.
echo [2/3] Installing/updating dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Collecting maximum public written reviews...
echo This can take a long time because the scraper uses multiple pagination passes.
echo It will NOT use sample/demo review data.
echo.
python scraper\scrape_reviews.py --max-reviews-per-stream 0 --google-languages id,en --google-sorts NEWEST,RATING,HELPFUL
if errorlevel 1 (
    echo.
    echo SCRAPER FAILED.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo SCRAPER COMPLETE
echo ============================================================
echo.
echo Open the dashboard with open_dashboard.bat
pause
