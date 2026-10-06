# -*- coding: utf-8 -*-
"""ONIZLEME (06.10.2026, Asama 4 / K14, E75).

Yayindan ONCE bakilacak yer: ajan bir siteyi yayina almak icin onay
istediginde patron kartta "Onizlemeyi ac" der ve isin klasorundeki siteyi
kendi bilgisayarinda gorur.

Neden ayri kucuk sunucu (panelin altindan degil): derlenen siteler
(Vite, Next export...) dosyalarini KOK-MUTLAK yolla ister (`/assets/x.js`).
Panelin `/onizleme/...` altindan sunulsa bu yollar panele gider ve sayfa
bos gorunur -- yanlis gosteren onizleme. Her site klasoru kendi
`127.0.0.1:<port>` kokunde sunulur; yalniz bu bilgisayar erisir (telefon
ve ag DISARIDA), nokta ile baslayan yol (`.ofis`, `.git`, `.env`) verilmez.

Giris sayfasi OLCULUR, tahmin edilmez: `index.html` once kokte, sonra
yaygin derleme klasorlerinde aranir; yoksa "onizlenecek sayfa yok" denir.
"""

from __future__ import annotations

import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ADAYLAR = ("index.html", "dist/index.html", "build/index.html", "out/index.html",
           "public/index.html", "_site/index.html", "site/index.html", "docs/index.html")
AZAMI_SUNUCU = 8

_KILIT = threading.Lock()
_SUNUCULAR: dict = {}          # klasor (kucuk harf) -> (sunucu, port)


def giris(kok) -> str:
    """Kokte onizlenecek giris sayfasi (kok-goreli) ya da ''."""
    if not kok:
        return ""
    k = Path(kok)
    for a in ADAYLAR:
        try:
            if (k / a).is_file():
                return a
        except OSError:
            continue
    return ""


class _Isleyici(SimpleHTTPRequestHandler):
    """Nokta ile baslayan yol parcasi verilmez; gunluk ekrana yazilmaz."""

    def send_head(self):
        yol = self.path.split("?", 1)[0].split("#", 1)[0]
        if any(p.startswith(".") for p in yol.split("/") if p):
            self.send_error(404, "Gizli yol onizlenmez")
            return None
        return super().send_head()

    def log_message(self, *a):      # noqa: D401 -- sessiz (panel konsolu dolmasin)
        pass


def ac(kok) -> dict:
    """Giris sayfasinin klasorunu yerel sunucuda acar. Doner: {url, klasor, giris}.

    Ayni klasor icin sunucu YENIDEN kullanilir. Sayfa yoksa ValueError.
    """
    g = giris(kok)
    if not g:
        raise ValueError("Bu isin klasorunde onizlenecek sayfa yok (index.html; "
                         "dist/, build/, out/, public/ de arandi).")
    klasor = (Path(kok) / g).parent.resolve()
    anahtar = str(klasor).lower()
    with _KILIT:
        var = _SUNUCULAR.get(anahtar)
        if var is None:
            if len(_SUNUCULAR) >= AZAMI_SUNUCU:
                eski_anahtar = next(iter(_SUNUCULAR))
                eski, _ = _SUNUCULAR.pop(eski_anahtar)
                try:
                    eski.shutdown()
                    eski.server_close()
                except OSError:
                    pass
            isleyici = functools.partial(_Isleyici, directory=str(klasor))
            sunucu = ThreadingHTTPServer(("127.0.0.1", 0), isleyici)
            sunucu.daemon_threads = True
            threading.Thread(target=sunucu.serve_forever, name="onizleme",
                             daemon=True).start()
            var = (sunucu, sunucu.server_address[1])
            _SUNUCULAR[anahtar] = var
    return {"url": f"http://127.0.0.1:{var[1]}/", "klasor": str(klasor), "giris": g}


def kapat_hepsi() -> None:
    with _KILIT:
        for s, _ in _SUNUCULAR.values():
            try:
                s.shutdown()
                s.server_close()
            except OSError:
                pass
        _SUNUCULAR.clear()
