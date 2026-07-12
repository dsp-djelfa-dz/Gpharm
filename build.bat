@echo off
echo ==============================================
echo Installing PyInstaller and dependencies
echo ==============================================
pip install pyinstaller

echo.
echo ==============================================
echo Building the standalone application (.exe)
echo ==============================================
pyinstaller --noconfirm --onefile --add-data "templates;templates/" --add-data "static;static/" --name "PharmacyRoster" "app.py"

echo.
echo ==============================================
echo Build Complete!
echo You can find your generic standalone application:
echo dist\PharmacyRoster.exe
echo ==============================================
pause
