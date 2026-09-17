@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo        TAN VIDEO CUTTER - INSTALAR
echo ========================================
echo.
where python >nul 2>nul
if errorlevel 1 (
  echo Python no esta instalado o no esta en PATH.
  echo Instala Python 3.11 o 3.12 desde https://www.python.org/downloads/windows/
  echo IMPORTANTE: marca Add python.exe to PATH durante la instalacion.
  pause
  exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo.
  echo FFmpeg no fue encontrado.
  where winget >nul 2>nul
  if errorlevel 1 (
    echo Instala FFmpeg manualmente y agregalo al PATH.
    echo Puedes usar: https://www.gyan.dev/ffmpeg/builds/
    pause
    exit /b 1
  ) else (
    echo Instalando FFmpeg con winget...
    winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
    echo.
    echo FFmpeg fue solicitado. Si acaba de instalarse, cierra esta ventana,
    echo abre una nueva y ejecuta nuevamente install_windows.bat.
  )
)

if not exist .venv (
  echo Creando entorno virtual...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo Hubo un error instalando dependencias.
  pause
  exit /b 1
)
echo.
echo ========================================
echo Instalacion terminada.
echo Ahora haz doble clic en EJECUTAR.bat
echo ========================================
pause
