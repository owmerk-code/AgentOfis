# -*- coding: utf-8 -*-
"""Ofisin KULLANICIYA ait calisma durumunun TEK koku: `~/.agentofis`.

Kasa, kota hafizasi, baglayici ve motor saglik defterleri, codex evi,
kabin profili, yedekler, golge depolar -- hepsi proje kokunun DISINDA
durur (ajanlarin `Bash(cat *)` izni proje kokunde gecer) ve hepsi bu
kokun altindadir.

## Neden tek kok

OLCULDU (27.09.2026): `duman_gorsel.py`'nin bir bolumu kota hatasini
taklit ediyordu ama kota defteri ancak sonraki bir bolumde gecici
dosyaya yonlendiriliyordu. Her test kosusu kullanicinin GERCEK
`~/.agentofis/kota.json`ina "Gemini kotasi doldu" yaziyordu ve lider
bir sonraki triyajda bu yanlis bilgiyle karar veriyordu. Yol on ayri
sabitte kopyaydi; her sinama kendi sabitini ayri ayri yonlendirmek
zorundaydi ve biri unutulunca gercek hafiza kirleniyordu -- bu projede
alti kez odenen "iki kopyadan biri unutulur" deseni.

Artik kok TEK yerde: `OFIS_EV` ortam degiskeni verilmisse o, yoksa
`~/.agentofis`. Sinamalarin ilk ice aktardigi `testler/_temizlik.py`
onu gecici bir klasore cevirir; boylece hicbir sinama -- unutsa bile --
gercek hafizaya YAZAMAZ.

Kok ICE AKTARMA aninda okunur (modul sabitleri onu kullanir). Ortam
degiskeni sonradan degistirilirse zaten olusmus sabitler degismez; bu
bilincli: calisan bir ofisin kokunun sessizce kaymasi, hayalet
veritabani dersinin yeni bir kapisi olurdu.
"""

from __future__ import annotations

import os
from pathlib import Path


def ofis_evi() -> Path:
    """Etkin kok. `OFIS_EV` bos degilse o, yoksa `~/.agentofis` (mutlak)."""
    ozel = (os.environ.get("OFIS_EV") or "").strip()
    kok = Path(ozel) if ozel else Path.home() / ".agentofis"
    return kok.expanduser().resolve()


#: Ice aktarma anindaki kok. Modul sabitleri bunu kullanir.
OFIS_EVI = ofis_evi()


def gercek_ev_mi() -> bool:
    """Kok kullanicinin gercek `~/.agentofis`i mi (sinama DEGIL mi)."""
    return OFIS_EVI == (Path.home() / ".agentofis").expanduser().resolve()
