# -*- coding: utf-8 -*-
"""CANLI GOSTERI -- patronun GERCEK ofisinin kopyasinda, patronun izledigi
sinama paneli (06.10.2026, Asama 5: Flow ile uctan uca video).

    python testler/canli_gosteri.py            # kopya kur + panel 8911

Patron http://127.0.0.1:8911 adresinden HER SEYI canli izler: sohbete dusen
mesaj, liderin plani, ajan panolari, gomulu tarayicida Flow, onay kartlari
(krediyi PATRON kendisi onaylar), sohbete dusen video.

Dokunulmayanlar: gercek defter (`veri/ofis.sqlite3`) ve gercek proje klasoru
(`Masaustu\\Ofisim`) -- ikisi de gecici klasore KOPYALANIR (`ofis_kopyasi`).
Bilincli kullanilanlar (patron onayi, 06.10): ofisin GERCEK evi (motor
girisleri) ve kabinin GERCEK profili (Flow girisi). Patronun kendi paneli bu
sirada KAPALI olmali (ayni profil iki Chrome'da acilamaz).
Kopyada patronun sirasi, zamanli isleri ve bekleyen onaylari KAPATILIR:
gosteride patronun gercek isleri kendiliginden kosmasin.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "testler"))
for _a in (sys.stdout, sys.stderr):
    try:
        _a.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from ofis_kopyasi import kopya_kur, PROJE  # noqa: E402  (OFIS_KABIN_KAPI=9399 kurar)

KAPI = 8911


def main() -> int:
    ana, db_yol, calisma = kopya_kur()
    c = sqlite3.connect(db_yol)
    for sorgu in ("UPDATE kuyruk SET durum = 'iptal' WHERE durum IN ('bekliyor', 'kosuyor')",
                  "UPDATE zamanli SET etkin = 0, sonraki = NULL",
                  "UPDATE onay SET durum = 'reddedildi', cevap_notu = 'kopya: gosteri' "
                  "WHERE durum = 'bekliyor'",
                  "UPDATE mesaj SET cevap = 'kopya: gosteri', cevaplandi = datetime('now') "
                  "WHERE alici = 'insan' AND cevaplandi IS NULL"):
        try:
            c.execute(sorgu)
        except sqlite3.Error as exc:
            print(f"(atlandi: {exc})")
    c.commit()
    c.close()
    print(f"KOPYA: {ana}")
    print(f"PROJE KLASORU (kopya): {calisma}")
    print(f"PANEL: http://127.0.0.1:{KAPI}", flush=True)
    from ofis.panel import kos
    kos("127.0.0.1", KAPI, str(db_yol), PROJE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
