# -*- coding: utf-8 -*-
"""GECE KOSUSU -- gercek seti iki motorda sirayla kosturur, sabaha ozet birakir.

    python testler/gece_kos.py            # Windows Gorev Zamanlayicisi bunu cagirir
    python testler/gece_kos.py --kur      # zamanlanmis gorevi kurar (her gun 03:30)
    python testler/gece_kos.py --kaldir   # zamanlanmis gorevi kaldirir

Kullanici (30.09.2026): *"gece otomatik olur, saatleri belirlersin,
bilgisayari acik birakirim."* Neden 03:30: patron uyurken kota bos; sabah
ise baslamadan once bitmis olur (iki motor ~1-1,5 saat, olculecek).

Iki kural:
* Patronun GERCEK ofisinde o an bir is kosuyorsa bekler (en fazla 2 saat),
  sonra yine de kosmaz -- patronun isiyle kota icin yarismaz; atladigini
  ozete yazar.
* Motorlar SIRAYLA kosar (paralel degil): gecenin olcumu, iki hesabin ayni
  anda yuklendigi bir durumu olcmemeli.

Ozet: `testler/rapor/gece-<tarih>.md` (iki motorun satirlari + rapor yollari).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import subprocess
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
RAPOR = KOK / "testler" / "rapor"
GOREV_ADI = "AgentOfis Gece Seti"
SAAT = "03:30"
BEKLEME_SN = 2 * 3600


def _gercek_ofiste_is_kosuyor() -> bool:
    """Patronun defterinde 'calisiyor' durumunda is var mi (salt okunur)."""
    import sqlite3
    db = KOK / "veri" / "ofis.sqlite3"
    if not db.exists():
        return False
    try:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
        return bool(c.execute("SELECT 1 FROM gorev WHERE durum='calisiyor' LIMIT 1").fetchone())
    except sqlite3.Error:
        return False


def kos() -> int:
    RAPOR.mkdir(exist_ok=True)
    tarih = _dt.datetime.now().strftime("%Y%m%d")
    ozet = [f"# Gece seti — {_dt.datetime.now():%d.%m.%Y %H:%M}", ""]
    bas = time.time()
    while _gercek_ofiste_is_kosuyor() and time.time() - bas < BEKLEME_SN:
        time.sleep(300)
    if _gercek_ofiste_is_kosuyor():
        ozet.append("ATLANDI: gercek ofiste 2 saat boyunca is kostu; kotayla yarisilmadi.")
        (RAPOR / f"gece-{tarih}.md").write_text("\n".join(ozet) + "\n", encoding="utf-8")
        return 0
    for motor in ("claude", "codex"):
        t0 = time.time()
        r = subprocess.run([sys.executable, str(KOK / "testler" / "gercek_set.py"),
                            "--motor", motor, "--sakla"], cwd=KOK, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=4 * 3600)
        satirlar = [s for s in (r.stdout or "").splitlines() if s.strip()]
        ozet += [f"## {motor} ({(time.time() - t0) / 60:.0f} dk)", ""]
        ozet += [f"    {s}" for s in satirlar[-14:]] or ["    (cikti yok)"]
        if r.returncode not in (0, 1):
            ozet.append(f"    HATA (kod {r.returncode}): {(r.stderr or '')[-400:]}")
        ozet.append("")
    (RAPOR / f"gece-{tarih}.md").write_text("\n".join(ozet) + "\n", encoding="utf-8")
    return 0


def kur() -> int:
    """Windows Gorev Zamanlayicisi: her gun SAAT'te, oturum aciksa (ConPTY
    terminalleri kullanicinin oturumunda kosar)."""
    komut = f'"{sys.executable}" "{Path(__file__).resolve()}"'
    r = subprocess.run(["schtasks", "/Create", "/TN", GOREV_ADI, "/TR", komut,
                        "/SC", "DAILY", "/ST", SAAT, "/F"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    print((r.stdout or r.stderr).strip())
    return r.returncode


def kaldir() -> int:
    r = subprocess.run(["schtasks", "/Delete", "/TN", GOREV_ADI, "/F"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    print((r.stdout or r.stderr).strip())
    return r.returncode


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kur", action="store_true")
    ap.add_argument("--kaldir", action="store_true")
    a = ap.parse_args()
    sys.exit(kur() if a.kur else kaldir() if a.kaldir else kos())
