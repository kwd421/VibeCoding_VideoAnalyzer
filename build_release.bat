@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Checking virtual environment...
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv\Scripts\python.exe not found.
  exit /b 1
)

if not exist ".venv\Scripts\pyinstaller.exe" (
  echo ERROR: .venv\Scripts\pyinstaller.exe not found.
  exit /b 1
)

echo [2/4] Cleaning old build output...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/4] Building release with PyInstaller...
.\.venv\Scripts\pyinstaller.exe VibeAnalyzer.spec --clean --noconfirm
if errorlevel 1 (
  echo ERROR: PyInstaller build failed.
  exit /b 1
)

echo [4/4] Done.
echo Output: %CD%\dist\VibeAnalyzer_Alpha
endlocal
