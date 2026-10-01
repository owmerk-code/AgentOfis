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


#: OFISIN TEK EVI (01.10.2026, kullanici karari): kodun yaninda,
#: `Masaustu\AgentOfis\ev`. *"agent sistemimizin altyapisi, klasorleri,
#: kodlar, ajanlar, hafiza ... hepsi tek bir yerde olacak, arka planda"*;
#: patronun projeleri masaustunde KENDI klasorlerinde. Ev GitHub'a ve ZIP
#: yedegine GIRMEZ (kasa, oturumlar, cerezler, golge depolar).
#: `OFIS_YENI_EV` YALNIZ sinama icin: bekcinin sinamasi gercek eve yazmasin.
YENI_EV = Path((os.environ.get("OFIS_YENI_EV") or "").strip()
               or Path(__file__).resolve().parent.parent / "ev")
#: Tasima yapilana kadar ofis ESKI evinde calisir: kod degisikligi tek
#: basina calisan ofisi bos bir eve tasimaz (hafiza kaybolmaz).
ESKI_EV = Path.home() / ".agentofis"


#: PROJE ICINDEKI OFIS IZI (01.10.2026, ayrim asama 2): patronun projesinde
#: ofise ait TEK sey gizli `.ofis/` klasorudur (`.git` gibi). Sohbet ekleri
#: ve ajanlarin yardimci betikleri orada; ofisin olcumu onu atlar.
PROJE_GIZLI = ".ofis"
EK_KLASORU = PROJE_GIZLI + "/ekler"
KARALAMA = PROJE_GIZLI + "/karalama"


#: OFISIN KENDI KODU (repo koku). Proje koku bunun ICINDE olamaz.
OFIS_KODU = Path(__file__).resolve().parent.parent
#: Patronun projeleri masaustunde KENDI klasorlerinde (01.10.2026 karari).
MASAUSTU = Path.home() / "Desktop"


def proje_klasor_adi(ad: str) -> str:
    """Proje adindan masaustu klasor adi: Windows'ta yasak isaretler atilir."""
    import re as _re
    temiz = _re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", str(ad or "")).strip(" .-")
    return temiz[:80] or "Proje"


def varsayilan_proje_koku(ad: str) -> Path:
    return MASAUSTU / proje_klasor_adi(ad)


def ofis_icinde_mi(yol) -> bool:
    """Yol ofisin KENDI yerinde mi (kodu, yeni ya da eski evi).

    Proje koku orada olursa ajan ofisin kodunu, kurallarini (CLAUDE.md --
    01.10.2026 OLCULDU: ajan anayasanin ilk satirini aynen okudu),
    hafizasini gorur; isler karisir. Kural yapi: boyle kok ACILMAZ.
    """
    try:
        p = Path(yol).expanduser().resolve()
    except (OSError, ValueError):
        return False
    for ev in (OFIS_KODU, YENI_EV, ESKI_EV):
        try:
            e = Path(ev).expanduser().resolve()
        except (OSError, ValueError):
            continue
        if p == e or e in p.parents:
            return True
    return False


def varsayilan_ev() -> Path:
    """Yeni ev VARSA o; yoksa eski ev varsa o; ikisi de yoksa yeni ev."""
    if YENI_EV.is_dir():
        return YENI_EV
    if ESKI_EV.is_dir():
        return ESKI_EV
    return YENI_EV


def ofis_evi() -> Path:
    """Etkin kok. `OFIS_EV` bos degilse o, yoksa `varsayilan_ev()` (mutlak)."""
    ozel = (os.environ.get("OFIS_EV") or "").strip()
    kok = Path(ozel) if ozel else varsayilan_ev()
    return kok.expanduser().resolve()


#: Ice aktarma anindaki kok. Modul sabitleri bunu kullanir.
OFIS_EVI = ofis_evi()


def gercek_ev_mi() -> bool:
    """Kok kullanicinin GERCEK evi mi (yeni ya da eski; sinama DEGIL mi)."""
    return OFIS_EVI in (YENI_EV.expanduser().resolve(), ESKI_EV.expanduser().resolve())
