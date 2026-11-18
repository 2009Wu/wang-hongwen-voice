@echo off
setlocal
chcp 65001 >nul
set "STUDIO_UI_PY=%~dp0.runtime\ui\Scripts\python.exe"
if not exist "%STUDIO_UI_PY%" (
  echo Open the Studio once to finish setup before changing analytics preferences.
  pause
  exit /b 1
)
if "%~1"=="" (
  echo [E] Enable anonymous usage statistics
  echo [D] Disable anonymous usage statistics
  choice /c ED /n
  if errorlevel 2 (
    "%STUDIO_UI_PY%" "%~dp0configure_analytics.py" --disable
  ) else (
    "%STUDIO_UI_PY%" "%~dp0configure_analytics.py"
  )
  pause
) else (
  "%STUDIO_UI_PY%" "%~dp0configure_analytics.py" %*
)
