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

REM Ilk acilis: GERCEK ofis (08.10.2026: ornek/sahte ofis kurulmaz).
REM Masaustu\Ofisim + GENEL takimi + lider (Claude Opus); gerisini patron
REM panelden kurar (Organizasyon > Yeni ajan / takim sablonu).
if not exist "veri\ofis.sqlite3" (
  echo   Ilk acilis: ofis kuruluyor ^(Masaustu\Ofisim^)...
  python -m ofis.kabuk --db veri\ofis.sqlite3 kur --ad Ofisim --kanat GENEL --klasor "%USERPROFILE%\Desktop\Ofisim" --amac "Gunluk islerin buyuk kismini ajan ekibiyle yurutmek" --olcut "Verilen hedef kanitla kapaniyor" || goto :hata
  python -m ofis.kabuk --db veri\ofis.sqlite3 --proje Ofisim ise-al arda lider --lider --motor claude --model opus || goto :hata
)

start "" http://127.0.0.1:8900
python -m ofis.panel --db veri\ofis.sqlite3 --kapi 8900
goto :son

:hata
echo.
echo HATA: baslatilamadi. Yukaridaki mesaja bak.
pause

:son
