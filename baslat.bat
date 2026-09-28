@echo off
REM AgentOfis - tek tik acilis.
REM Panel YALNIZCA 127.0.0.1'e baglanir. Telefondan erisim icin
REM Tailscale adresini (100.x) acikca vermek gerekir; butun arayuzlere
REM acilmak (0.0.0.0) kodda reddedilir.
chcp 65001 >nul
cd /d "%~dp0"

echo AgentOfis baslatiliyor...

python -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
  echo   Panel bagimliliklari kuruluyor ^(fastapi, uvicorn^)...
  python -m pip install --quiet fastapi uvicorn || goto :hata
)

REM Devral (gercek terminal) icin. Kurulamazsa panel yine acilir;
REM yalniz "Devral" dugmesi sebebini soyler.
python -c "import winpty" 2>nul
if errorlevel 1 (
  echo   Terminal bileseni kuruluyor ^(pywinpty^)...
  python -m pip install --quiet pywinpty
)

if not exist "veri\ofis.sqlite3" (
  echo   Ilk acilis: ornek ofis kuruluyor...
  python veri\ornek_ofis.py --db veri\ofis.sqlite3 || goto :hata
)

start "" http://127.0.0.1:8900
python -m ofis.panel --db veri\ofis.sqlite3 --kapi 8900
goto :son

:hata
echo.
echo HATA: baslatilamadi. Yukaridaki mesaja bak.
pause

:son
