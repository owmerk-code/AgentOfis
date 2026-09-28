# -*- coding: utf-8 -*-
"""AgentOfis — kendi ajan ekibin.

Katmanlar:
    db      : sema ve baglanti (mimarinin kendisi)
    kadro   : ajanlar, roller, siciller
    tahta   : gorevler, DAG, yazma kilidi, kanit kapisi
    bellek  : cift-zamanli olgular, karar gunlugu, uyanis ozeti
    brifing : dort katmanli baglam uretimi
    koltuk  : gorevi alan, brifingi ureten, motoru kosturan halka
    lider   : fan-out kapisi, dagitim, kanita karsi inceleme
    postane : ajanlar arasi soru-cevap, insan onayi
    danisma : ajana sorulan soruyu TESLIM eden parca (yaprak, salt okunur)
    orkestra: hedeften kapanisa halkayi donduren parca
    sohbet  : liderin ON KAPISI -- insanin tek muhatabi
    saglik  : ofis kendi tikandigini fark etsin (teshis + care)
    motor   : fise takilan motor adaptorleri (claude, codex, opencode, api)
"""

from __future__ import annotations

import uuid
from pathlib import Path

from .db import Veritabani, simdi
from .kadro import Kadro, KadroHatasi
from .tahta import Tahta, TahtaHatasi, KilitCakismasi, RevizyonCakismasi
from .bellek import Bellek, BellekHatasi
from .brifing import Brifing
from .koltuk import Koltuk, KoltukHatasi
from .lider import Lider, LiderHatasi
from .postane import Postane, PostaneHatasi
from .danisma import Danisma, DanismaHatasi
from .orkestra import Orkestra, OrkestraHatasi
from .ekip import Ekip, EkipHatasi
from .sohbet import Sohbet, SohbetHatasi
from .saglik import Saglik

__all__ = [
    "Ekip", "EkipHatasi",
    "Veritabani", "Kadro", "Tahta", "Bellek", "Brifing", "Koltuk", "Lider", "Postane", "Danisma", "Orkestra", "Sohbet", "Saglik", "Ofis",
    "KadroHatasi", "TahtaHatasi", "KilitCakismasi", "RevizyonCakismasi",
    "BellekHatasi", "KoltukHatasi", "LiderHatasi", "PostaneHatasi", "DanismaHatasi", "OrkestraHatasi", "SohbetHatasi",
]


class Ofis:
    """Bir projenin tum katmanlarini tek yerden acar."""

    def __init__(self, db, proje_id: str) -> None:
        self.db = db
        self.proje_id = proje_id
        self.kadro = Kadro(db, proje_id)
        self.tahta = Tahta(db, proje_id)
        self.bellek = Bellek(db, proje_id)
        self.brifing = Brifing(db, proje_id, self.kadro, self.tahta, self.bellek)
        self.koltuk = Koltuk(self)
        self.lider = Lider(self)
        self.postane = Postane(self)
        # Tahta, DURDURULMUS ajanin kilidini dusurmemeli. Bilgi postanede
        # (soru/onay bekleyenler) ama tahta ondan once kuruluyor; islevle
        # baglamak katman sirasini bozmadan bilgiyi ulastirir.
        self.tahta.duraklatilmis_kaynak = self._duraklatilmis_ajanlar
        self.danisma = Danisma(self)
        self.orkestra = Orkestra(self)
        self.ekip = Ekip(self)
        self.sohbet = Sohbet(self)
        self.saglik = Saglik(self)

    @property
    def plan(self) -> dict:
        """Ofisin abonelik plani. Sorgudur, saklanan kopya degil."""
        from . import plan as _plan
        return _plan.oku(self.db, self.proje_id)

    def _duraklatilmis_ajanlar(self) -> list:
        """Sistemin KENDISININ durdurdugu ajanlar -- olmus degiller.

        Kilit kirasi olen ajana karsi var. Soru sorup cevap bekleyen ajan
        nabiz atmaz, ama bu ONUN kusuru degil: ona "SIMDI DUR" denmistir.
        Kirayi ona uygulamak, dogru davranani cezalandirmaktir.
        """
        adlar = set()
        for m in self.postane.bekleyen_sorular():
            adlar.add(m["gonderen"])
        for o in self.postane.bekleyen_onaylar():
            adlar.add(o["isteyen"])
        # DEVRAL: insan ajanin isinde calisirken kilit ajan adina durur ve
        # nabiz atan tur yoktur. Kirayi dusurmek, insanin calistigi
        # dosyalari baska bir ise acmak olurdu (Yasa 1).
        from . import devral as _devral
        for d in _devral.devralinanlar(self.db, self.proje_id):
            if d.get("ajan"):
                adlar.add(d["ajan"])
        return sorted(adlar)

    @classmethod
    def proje_ac(cls, db, ad: str, *, amac: str = "", basari_olcutu: str = "",
                 kapsam_disi: str = "", kisitlar: str = "", sozluk: str = "",
                 kok_klasor: str = "") -> "Ofis":
        # Kok klasor de MUTLAK saklanir -- ayni goreli yol tuzagi
        # (bkz. db.py ve kadro.ise_al). Proje kaydi baska bir klasorden
        # okundugunda ayni yere isaret etmeli.
        if kok_klasor:
            kok_klasor = str(Path(kok_klasor).expanduser().resolve())
        proje_id = uuid.uuid4().hex
        an = simdi()
        with db.baglanti() as conn:
            var = conn.execute("SELECT id FROM proje WHERE ad = ?", (ad,)).fetchone()
            if var:
                return cls(db, var["id"])
            conn.execute(
                "INSERT INTO proje (id, ad, amac, basari_olcutu, kapsam_disi, kisitlar, "
                "sozluk, kok_klasor, durum, revizyon, olusturuldu, guncellendi) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'acik', 1, ?, ?)",
                (proje_id, ad, amac, basari_olcutu, kapsam_disi, kisitlar, sozluk,
                 kok_klasor, an, an),
            )
        db.olay_yaz(proje_id, "proje_acildi", ad)
        return cls(db, proje_id)

    def kok_klasoru(self) -> str:
        """Ajanlarin ORTAK calisma koku (karar 18.09.2026).

        TEK YER: kabuk ve panel ikisi de bunu cagirir. Kural once yalniz
        kabukta yasiyordu (`_kok_klasor`); panele ikinci bir kopya
        yazilsaydi biri digerinden kayar ve iki yuzey ayni ajani farkli
        klasore alirdi. Kok tanimsizsa defterin yanindaki `calisma/`.
        """
        with self.db.baglanti() as conn:
            row = conn.execute("SELECT kok_klasor FROM proje WHERE id = ?",
                               (self.proje_id,)).fetchone()
        kok = ((row["kok_klasor"] if row else "") or "").strip()
        return kok or str(Path(self.db.yol).parent / "calisma")

    def kanat_ac(self, ad: str, onek: str, renk: str = "#E0785A") -> str:
        kanat_id = uuid.uuid4().hex
        with self.db.baglanti() as conn:
            var = conn.execute(
                "SELECT id FROM kanat WHERE proje_id = ? AND ad = ?",
                (self.proje_id, ad),
            ).fetchone()
            if var:
                return var["id"]
            conn.execute(
                "INSERT INTO kanat (id, proje_id, ad, onek, renk, olusturuldu) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (kanat_id, self.proje_id, ad, onek, renk, simdi()),
            )
        return kanat_id
