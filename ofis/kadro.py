# -*- coding: utf-8 -*-
"""Kadro: ajanlarin ise alinmasi, rolleri ve sicilleri.

Degismezler:

* **Ad geri donmez.** Basarisiz bir ajan bile adini tuketir (bkz. db.py).
* **Kafa yazamaz.** `tur='kafa'` olan ajan dosya yazan bir gorev alamaz;
  yalnizca dusunup metin uretir. Bu maliyet degil SORUMLULUK kuralidir:
  ucuz model kendi sinirini taniyamaz (Cognition'in olcumu), o yuzden
  yargi gerektiren ve dosyaya dokunan isler ona verilmez.
* **Lider tektir.** Bir kanatta tek lider olur; iki lider ayni isi iki kez
  dagitir ve kimse fark etmez.
"""

from __future__ import annotations

import json
import re
import uuid

from pathlib import Path

from . import roller
from .klasor import klasor_dogrula
from .db import simdi

AD_DESENI = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: Motor listesi BURADA TUTULMAZ, kayit defterine sorulur.
#: Iki ayri liste tutuldugunda kacinilmaz olan sey oldu: defterde kayitli
#: bir motor kadroda "bilinmiyor" sayildi. Tek kaynak olmali -- adaptor
#: eklemek tek dosya yazip tek satir kaydetmek demek (motor/__init__.py).
def motorlar() -> tuple:
    from .motor import kayitli_motorlar
    return kayitli_motorlar()


TURLER = ("eller", "kafa")
EFORLAR = ("dusuk", "normal", "yuksek", "cok_yuksek")

FAZ_KURULUYOR = "kuruluyor"
FAZ_AKTIF = "aktif"
FAZ_BASARISIZ = "basarisiz"

#: Ontanimli meslekler. Liste kapali degildir -- yeni meslek eklemek icin
#: kod degistirmek gerekmez, ad yeter.
MESLEKLER = (
    "lider", "backend", "arayuz", "tasarim", "test", "arastirma",
    "metin", "reklam", "sosyal", "magaza", "analiz",
)


class KadroHatasi(RuntimeError):
    pass


def _ad_dogrula(ad: str) -> str:
    ad = (ad or "").strip().lower()
    if not AD_DESENI.match(ad):
        raise KadroHatasi(
            f"Gecersiz ajan adi: {ad!r}. Kucuk harf ve tire kullan (ornek: demir, veri-analisti). "
            "Ad hem adres hem kimliktir; serbest metin olursa mesajlar kaybolur."
        )
    if len(ad) > 64:
        raise KadroHatasi("Ajan adi 64 karakteri asamaz.")
    return ad


class Kadro:
    def __init__(self, db, proje_id: str) -> None:
        self.db = db
        self.proje_id = proje_id

    # -- ise alma ----------------------------------------------------------

    def ise_al(self, ad: str, meslek: str, *, motor: str = "claude",
               model: str = "", tur: str = "", efor: str = "normal",
               klasor: str = "", kanat_id: str = None,
               lider_mi: bool = False) -> dict:
        """Ajan ise alir. ROL, bos birakilan alanlari DOLDURUR.

        `meslek` artik serbest metin degil, `ofis/roller.py`'deki
        kutuphaneden bir addir. Sebep olculdu: serbest metinken `bilge`
        (arastirma) ve `deniz` (icerik) `tur='kafa'` ise alindi ve
        ikisi de -- isi DOSYA URETMEK olmasina ragmen -- dosya
        yazamaz halde kaldi. Kimse fark etmedi, cunku "arastirma"
        yalnizca bir kelimeydi.

        **Etiket yanlis kurulursa fark edilmez; tanim yanlis kurulursa
        kurulmaz.**

        Doldurma yalnizca BOS alanlara yapilir: acikca verilen deger
        her zaman kazanir. Rol bir varsayilandir, bir dayatma degil --
        kullanicinin sectigi modeli sessizce iptal etmek, ayni sinifin
        baska bir hatasi olurdu (bkz. zincir.py: "zincir ajanin KENDI
        motorundan baslar").
        """
        ad = _ad_dogrula(ad)
        if motor not in motorlar():
            raise KadroHatasi(
                f"Bilinmeyen motor: {motor}. Secenekler: {', '.join(motorlar())}")

        # ROL KAPISI: bilinmeyen rol reddedilir ve gecerli adlar sayilir.
        # Yanlis yazilmis bir rol adi sessiz bir olum sebebidir.
        # RolHatasi KadroHatasi'na cevrilir (mesaj -- gecerli adlar --
        # korunur). Olculdu (23.09.2026): cevrilmiyordu, kabuk yalniz
        # KadroHatasi yakaladigi icin yanlis yazilmis bir rol `ise-al`i
        # ham bir yigin iziyle olduruyordu; panel 500 donuyordu.
        try:
            meslek = roller.coz(meslek)
        except roller.RolHatasi as exc:
            raise KadroHatasi(str(exc)) from exc
        tanim = roller.ROLLER[meslek]

        # Rolun DOLDURDUKLARI -- yalnizca bos alanlar.
        if not tur:
            tur = tanim.tur
        if not model:
            model = roller.model_sec(
                motor, tanim.kademe,
                roller.kademe_haritasi(self.db, self.proje_id))

        if tur not in TURLER:
            raise KadroHatasi(f"Tur 'eller' ya da 'kafa' olmali, {tur!r} degil.")
        # Klasor MUTLAK saklanir. Ajan turu AYRI BIR SURECTE ve BASKA bir
        # calisma klasorunde kosar; goreli bir yol orada baska bir yere
        # cozulur. Ayni sinifin en agir ornegi veritabani yolunda yasandi:
        # MCP sunucusu ajanin klasorunde kosup `calisma/veri/ofis.sqlite3`
        # diye BOMBOS bir veritabani yaratti, ajan ofisin yanlis resmini
        # gordu ve hicbir yerde hata gorunmedi (bkz. db.py).
        #
        # Yolu KAYDEDERKEN cozmek, KULLANIRKEN cozmekten guvenlidir:
        # kullanim ani, kaydin yapildigi klasorde olmayabilir.
        if klasor:
            klasor = str(Path(klasor).expanduser().resolve())
        if efor not in EFORLAR:
            raise KadroHatasi(f"Efor {EFORLAR} icinden olmali.")
        if lider_mi and tur != "eller":
            raise KadroHatasi(
                "Lider 'eller' olmali: gorev acar, tahtaya yazar, kanit inceler."
            )

        with self.db.baglanti() as conn:
            var = conn.execute(
                "SELECT ad FROM ajan WHERE proje_id = ? AND ad = ?",
                (self.proje_id, ad),
            ).fetchone()
            if var:
                raise KadroHatasi(
                    f"{ad!r} adi zaten kullanilmis. Ad geri donmez -- gecmis okunabilir "
                    "kalsin diye. Baska bir ad sec."
                )
            if lider_mi:
                mevcut = conn.execute(
                    "SELECT ad FROM ajan WHERE proje_id = ? AND kanat_id IS ? AND lider_mi = 1",
                    (self.proje_id, kanat_id),
                ).fetchone()
                if mevcut:
                    raise KadroHatasi(
                        f"Bu kanadin lideri zaten var: {mevcut['ad']}. "
                        "Iki lider ayni isi iki kez dagitir."
                    )

            ajan_id = uuid.uuid4().hex
            an = simdi()
            conn.execute(
                "INSERT INTO ajan (id, proje_id, kanat_id, ad, meslek, lider_mi, motor, "
                "model, efor, tur, klasor, oturum_id, faz, revizyon, olusturuldu, guncellendi) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, 1, ?, ?)",
                (ajan_id, self.proje_id, kanat_id, ad, meslek, 1 if lider_mi else 0,
                 motor, model, efor, tur, klasor, FAZ_KURULUYOR, an, an),
            )
        self.db.olay_yaz(self.proje_id, "ise_alindi",
                         f"{ad} ({meslek}) ise alindi -- {motor}", ajan_ad=ad)
        return self.ajan(ad)

    def faz_ayarla(self, ad: str, faz: str) -> dict:
        if faz not in (FAZ_KURULUYOR, FAZ_AKTIF, FAZ_BASARISIZ):
            raise KadroHatasi(f"Bilinmeyen faz: {faz}")
        mevcut = self.ajan(ad)
        if mevcut["faz"] in (FAZ_AKTIF, FAZ_BASARISIZ) and faz != mevcut["faz"]:
            raise KadroHatasi(
                f"{ad} zaten {mevcut['faz']} -- faz makinesi tek yonludur. "
                "Calisma anindaki mesgul/bos durumu AYRI turetilir."
            )
        with self.db.baglanti() as conn:
            conn.execute(
                "UPDATE ajan SET faz = ?, revizyon = revizyon + 1, guncellendi = ? "
                "WHERE proje_id = ? AND ad = ?",
                (faz, simdi(), self.proje_id, ad),
            )
        return self.ajan(ad)

    def oturum_kaydet(self, ad: str, oturum_id: str) -> None:
        """Motorun oturum kimligini sakla -- kimlik burada yasar.

        Bu deger sayesinde makine kapanip acildiginda ajan kaldigi yerden
        devam eder. Kaybedilirse ajan hafizasini yitirir.
        """
        with self.db.baglanti() as conn:
            conn.execute(
                "UPDATE ajan SET oturum_id = ?, guncellendi = ? WHERE proje_id = ? AND ad = ?",
                (oturum_id, simdi(), self.proje_id, ad),
            )

    def motor_ayarla(self, ad: str, *, motor: str = None, model: str = None,
                     efor: str = None, meslek: str = None,
                     klasor: str = None) -> dict:
        """Motor FISE TAKILIDIR: calisirken degistirilebilir.

        Yeni motor bir sonraki gorevde gecerli olur; suren oturum basladigi
        motorla kalir -- yarida motor degistirmek baglami koparir.

        `meslek` (rol) de degistirilebilir ama bu DAHA BUYUK bir
        degisiklik: rol turu, araclari, kanit beklentisini ve olcutunu
        birlikte tasir. Rol degisince `tur` de rolun gerektirdigine
        cekilir -- yoksa `kafa` bir ajan `arastirma` rolu alir ve yine
        dosya yazamaz; duzeltmek istedigimiz hatanin ta kendisi olurdu.

        Ne degismez: AD ve SICIL. Ajan bir kimliktir; ders sayaci ancak
        ayni ajanda birikirse anlam tasir.
        """
        mevcut = self.ajan(ad)
        motor = motor or mevcut["motor"]
        if motor not in motorlar():
            raise KadroHatasi(f"Bilinmeyen motor: {motor}")
        # EFOR DA DOGRULANIR. `ise_al` dogruluyordu, bu yontem dogrulamiyordu
        # (olculdu, 23.09.2026): bozuk bir efor deftere yazilir ve motor onu
        # tur aninda ya reddeder ya sessizce varsayilana dusururdu. Ayni kural
        # iki kapidan birinde eksikse, o kapi kuralin olmadigi yerdir.
        if efor is not None and efor not in EFORLAR:
            raise KadroHatasi(f"Efor {EFORLAR} icinden olmali.")

        yeni_meslek = mevcut["meslek"]
        yeni_tur = mevcut["tur"]
        if meslek is not None:
            try:
                yeni_meslek = roller.coz(meslek)
            except roller.RolHatasi as exc:
                raise KadroHatasi(str(exc)) from exc
            yeni_tur = roller.ROLLER[yeni_meslek].tur
            if mevcut["lider_mi"] and yeni_tur != "eller":
                raise KadroHatasi(
                    "Lider 'eller' olmali: gorev acar, tahtaya yazar.")

        # KLASOR DEGISTIRMEK BIR YETKI DEGISIKLIGIDIR, ayar degil.
        #
        # Ajanin klasoru `--restricted` sinirini belirler: disari
        # cikamaz. Genisletmek, o ajanin BUTUN gelecek islerinde acik
        # kalan bir kapi demektir -- gorevin `ek_klasorler` alaninin
        # aksine, is bitince kapanmaz.
        #
        # Bu yuzden ayni kapidan gecer (`klasor.py`): mutlaklastirilir,
        # var oldugu OLCULUR, surucu koku ve sistem klasoru reddedilir.
        # Ve SESSIZ OLMAZ -- kayda gecer.
        yeni_klasor = mevcut["klasor"]
        if klasor is not None:
            yeni_klasor = str(klasor_dogrula(klasor))

        with self.db.baglanti() as conn:
            conn.execute(
                "UPDATE ajan SET motor = ?, model = ?, efor = ?, meslek = ?, "
                "tur = ?, klasor = ?, revizyon = revizyon + 1, "
                "guncellendi = ? WHERE proje_id = ? AND ad = ?",
                (motor,
                 mevcut["model"] if model is None else model,
                 mevcut["efor"] if efor is None else efor,
                 yeni_meslek, yeni_tur, yeni_klasor,
                 simdi(), self.proje_id, ad),
            )
        if klasor is not None and yeni_klasor != mevcut["klasor"]:
            self.db.olay_yaz(
                self.proje_id, "klasor_acildi",
                f"{ad} klasoru degisti: {mevcut['klasor']} -> {yeni_klasor}",
                ajan_ad=ad)
        return self.ajan(ad)

    # -- okuma -------------------------------------------------------------

    def ajan(self, ad: str) -> dict:
        with self.db.baglanti() as conn:
            row = conn.execute(
                "SELECT * FROM ajan WHERE proje_id = ? AND ad = ?",
                (self.proje_id, ad),
            ).fetchone()
        if not row:
            raise KadroHatasi(f"Ajan bulunamadi: {ad}")
        return dict(row)

    def liste(self, kanat_id: str = None) -> list:
        with self.db.baglanti() as conn:
            if kanat_id:
                rows = conn.execute(
                    "SELECT * FROM ajan WHERE proje_id = ? AND kanat_id = ? "
                    "ORDER BY lider_mi DESC, ad",
                    (self.proje_id, kanat_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM ajan WHERE proje_id = ? ORDER BY lider_mi DESC, ad",
                    (self.proje_id,),
                ).fetchall()
        return [dict(r) for r in rows]

    def lider(self, kanat_id: str = None) -> dict:
        with self.db.baglanti() as conn:
            row = conn.execute(
                "SELECT * FROM ajan WHERE proje_id = ? AND kanat_id IS ? AND lider_mi = 1",
                (self.proje_id, kanat_id),
            ).fetchone()
        if not row:
            raise KadroHatasi("Bu kanadin lideri yok. Once lider ise al.")
        return dict(row)

    # -- sicil (ders) ------------------------------------------------------

    def ders_yaz(self, ajan_ad: str, ders: str, gorev_id: str = None) -> dict:
        """Ayni ders ikinci kez gelirse tekrar sayaci artar, yeni satir acilmaz.

        Tekrar sayisi onemlidir: lider "bunu sana ucuncu kez soyluyorum"
        diyebilmeli ve brifingde o satir one cikmali.
        """
        ders = (ders or "").strip()
        if not ders:
            raise KadroHatasi("Bos ders yazilamaz.")
        an = simdi()
        with self.db.baglanti() as conn:
            row = conn.execute(
                "SELECT id, tekrar FROM ders WHERE proje_id = ? AND ajan_ad = ? AND ders = ?",
                (self.proje_id, ajan_ad, ders),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE ders SET tekrar = tekrar + 1, guncellendi = ? WHERE id = ?",
                    (an, row["id"]),
                )
                ders_id = row["id"]
                tekrar = int(row["tekrar"]) + 1
            else:
                tekrar = 1
                ders_id = uuid.uuid4().hex
                conn.execute(
                    "INSERT INTO ders (id, proje_id, ajan_ad, ders, sebep_gorev_id, "
                    "tekrar, olusturuldu, guncellendi) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                    (ders_id, self.proje_id, ajan_ad, ders, gorev_id, an, an),
                )
        # TEKRAR SAYISI OLAYA YAZILIR. Olculdu (21.09): sayac defterde dogru
        # artiyordu ama olay govdesi her seferinde AYNI cumleydi -- panel
        # ayni satiri iki kez basiyor, anlamli sinyal ("bu ajan ayni hatayi
        # yapmaya devam ediyor") ekrandan kayboluyordu.
        ek = f"  [{tekrar}. kez]" if tekrar > 1 else ""
        self.db.olay_yaz(self.proje_id, "ders", f"{ajan_ad}: {ders}{ek}",
                         ajan_ad=ajan_ad)
        return {"id": ders_id, "ders": ders, "tekrar": tekrar}

    def dersler(self, ajan_ad: str) -> list:
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT ders, tekrar FROM ders WHERE proje_id = ? AND ajan_ad = ? "
                "ORDER BY tekrar DESC, guncellendi DESC, rowid DESC",
                (self.proje_id, ajan_ad),
            ).fetchall()
        return [dict(r) for r in rows]
