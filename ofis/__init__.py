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


def _gercek_defter_mi(db) -> bool:
    """Patronun GERCEK defteri mi (sinama/ornek degil)."""
    from .db import VARSAYILAN_YOL
    try:
        return Path(db.yol).resolve() == Path(VARSAYILAN_YOL).resolve()
    except (OSError, ValueError):
        return False


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
        from .yollar import ofis_icinde_mi, varsayilan_proje_koku
        if kok_klasor:
            kok_klasor = str(Path(kok_klasor).expanduser().resolve())
            # AYRIM (01.10.2026): proje koku ofisin kendi yerinde OLAMAZ.
            if ofis_icinde_mi(kok_klasor):
                raise ValueError(
                    f"Proje klasoru ofisin kendi yerinde olamaz: {kok_klasor}. "
                    "Ajanlar ofisin kodunu ve kurallarini gorur, isler karisir. "
                    "Projeyi masaustunde kendi klasorunde ac.")
        elif _gercek_defter_mi(db):
            # Patronun gercek ofisinde yeni proje MASAUSTUNDE acilir.
            kok_klasor = str(varsayilan_proje_koku(ad))
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

    def kok_klasoru(self, kanat_id: str = None) -> str:
        """Ajanlarin ORTAK calisma koku (karar 18.09.2026).

        TAKIM KLASORU (06.10.2026, patron: "her takim ayri"): takimin kendi
        koku varsa o (`tahta.kanat_koku`, TEK yer); yoksa projenin koku.

        TEK YER: kabuk ve panel ikisi de bunu cagirir. Kural once yalniz
        kabukta yasiyordu (`_kok_klasor`); panele ikinci bir kopya
        yazilsaydi biri digerinden kayar ve iki yuzey ayni ajani farkli
        klasore alirdi. Kok tanimsizsa defterin yanindaki `calisma/`.
        """
        from .tahta import kanat_koku
        tk = kanat_koku(self.db, kanat_id)
        if tk:
            return tk
        with self.db.baglanti() as conn:
            row = conn.execute("SELECT kok_klasor FROM proje WHERE id = ?",
                               (self.proje_id,)).fetchone()
        kok = ((row["kok_klasor"] if row else "") or "").strip()
        if kok:
            return kok
        # Gercek defterde koksuz proje ofisin icine (veri/calisma) DUSMEZ.
        if _gercek_defter_mi(self.db):
            from .yollar import varsayilan_proje_koku
            with self.db.baglanti() as conn:
                r = conn.execute("SELECT ad FROM proje WHERE id = ?", (self.proje_id,)).fetchone()
            return str(varsayilan_proje_koku((r["ad"] if r else "") or "Proje"))
        return str(Path(self.db.yol).parent / "calisma")

    def isin_koku(self, gorev_or_id) -> str:
        """Bir isin calisma koku (`kok_klasoru` kurallariyla, isin TAKIMINA
        gore). `tahta.gorev_koku`tan farki: koksuz projede bos degil, ajanlarin
        gercekten calistigi yedek kok doner."""
        g = gorev_or_id
        if not isinstance(g, dict):
            with self.db.baglanti() as c:
                r = c.execute("SELECT kanat_id FROM gorev WHERE id = ?", (g,)).fetchone()
            g = dict(r) if r else {}
        return self.kok_klasoru(g.get("kanat_id") or None)

    def kokler(self) -> list:
        """Projenin ve takimlarinin butun kokleri (ek / belge ararken)."""
        out = [self.kok_klasoru()]
        with self.db.baglanti() as conn:
            for r in conn.execute("SELECT klasor FROM kanat WHERE proje_id = ? AND klasor != ''",
                                  (self.proje_id,)):
                if r["klasor"] not in out:
                    out.append(r["klasor"])
        return out

    def yeni_takim_koku(self, ad: str) -> str:
        """Yeni takimin VARSAYILAN klasoru: gercek ofiste `Masaustu\\<ad>`;
        sinama/ornek defterde projenin kokunun icinde (gercek masaustune
        dokunulmaz)."""
        from .yollar import ofis_icinde_mi, proje_klasor_adi, MASAUSTU
        ata = MASAUSTU if _gercek_defter_mi(self.db) else Path(self.kok_klasoru())
        temel = proje_klasor_adi(ad or "Takim")
        # BASKASININ KOKU OLAMAZ: takim adi projenin ya da baska bir takimin
        # klasoruyle (ya da ofisin kendi yeriyle) ayni dusebilir -- iki is
        # ayni dosyalari habersiz paylasirdi. Bos ilk ad secilir.
        with self.db.baglanti() as conn:
            dolu = {str(Path(r[0]).resolve()).lower() for r in conn.execute(
                "SELECT kok_klasor FROM proje WHERE kok_klasor != '' "
                "UNION SELECT klasor FROM kanat WHERE klasor != ''")}
        for i in range(1, 100):
            aday = ata / (temel if i == 1 else f"{temel}-{i}")
            if str(aday.resolve()).lower() not in dolu and not ofis_icinde_mi(aday):
                return str(aday)
        raise ValueError("Takim icin bos klasor adi bulunamadi.")

    def takim_klasoru_ayarla(self, kanat_id: str, yol: str) -> dict:
        """Takimin kokunu ayarlar; takimin ajanlari o koke tasinir.

        Acik isi olan takimda DEGISMEZ (calisan isin kilitleri ve kanitlari
        eski koke gore). Kok ofisin icinde olamaz (`ofis_icinde_mi`).
        Bos yol = projenin koku (takim kendi klasorunu birakir).
        """
        from .yollar import ofis_icinde_mi
        yol = (yol or "").strip()
        if yol:
            p = Path(yol).expanduser()
            if not p.is_absolute():
                raise ValueError("Takim klasoru MUTLAK yol olmali.")
            if ofis_icinde_mi(p):
                raise ValueError("Takim klasoru ofisin kendi yerinde olamaz.")
        from .tahta import _kok_anahtari
        eski = _kok_anahtari(self.kok_klasoru(kanat_id))
        with self.db.baglanti() as conn:
            acik = conn.execute(
                "SELECT no FROM gorev WHERE proje_id = ? AND kanat_id = ? AND silindi = 0 "
                "AND durum IN ('calisiyor', 'inceleme')", (self.proje_id, kanat_id)).fetchall()
        if acik:
            raise ValueError("Takimin calisan isi var (" + ", ".join(f"#{r[0]}" for r in acik)
                             + "); is bitince klasor degistirilir.")
        # Klasor ANCAK kapilar gectikten sonra acilir (reddedilen istek
        # diskte iz birakmaz).
        if yol:
            p.mkdir(parents=True, exist_ok=True)
            yol = str(p.resolve())
        with self.db.baglanti() as conn:
            conn.execute("UPDATE kanat SET klasor = ? WHERE id = ? AND proje_id = ?",
                         (yol, kanat_id, self.proje_id))
            yeni = self.kok_klasoru(kanat_id)
            # Yalniz takimin kokunde calisanlar tasinir; KENDI klasoru olan
            # (yalitilmis) ajanin klasoruna dokunulmaz.
            for r in conn.execute("SELECT ad, klasor FROM ajan WHERE proje_id = ? AND kanat_id = ?",
                                  (self.proje_id, kanat_id)).fetchall():
                if _kok_anahtari(r["klasor"]) == eski:
                    conn.execute("UPDATE ajan SET klasor = ? WHERE proje_id = ? AND ad = ?",
                                 (yeni, self.proje_id, r["ad"]))
        self.db.olay_yaz(self.proje_id, "takim_klasoru", f"{kanat_id}: {yeni}", ajan_ad="insan")
        return {"kanat_id": kanat_id, "klasor": yeni}

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
