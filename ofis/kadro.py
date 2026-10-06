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


def kapi_modeli_mi(model) -> str:
    """Kapi modeli (fable/astra) adi ya da bos. Patron karari (05.10.2026):
    ajana ELLE atanabilir ("genelde tercih etmiyorum"); otomatik hicbir
    yolda (kademe) yer almaz. Atama uyari olarak kayda gecer."""
    m = (model or "").lower()
    return next((k for k in roller.KAPI_MODELLERI if k in m), "")


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
        self._kapi_uyarisi(ad, model)
        return self.ajan(ad)

    def _kapi_uyarisi(self, ad: str, model) -> None:
        if kapi_modeli_mi(model):
            self.db.olay_yaz(self.proje_id, "uyari",
                             f"{ad} KAPI modeliyle ({model}) calisacak: her tur pahali, "
                             "limiti hizli bitirir (patronun elle secimi).", ajan_ad="insan")

    def katalogdan_al(self, ad: str, meslek: str, *, motor: str = "",
                      model: str = "", **kw) -> dict:
        """Ise alma -- motor ve model MESLEK KATALOGUNDAN (05.10.2026).

        Panel, sablon ve liderin onerisi buradan gecer; `ise_al`in kendi
        varsayilani ("claude") eski cagiranlar icin oldugu gibi kalir.
        Acikca verilen motor/model her zaman kazanir. Katalogun motoru
        kurulu degilse yedek motor secilir ve bu olaya YAZILIR.
        """
        from .motor import musait_motorlar
        try:
            rol_ad = roller.coz(meslek)
        except roller.RolHatasi as exc:
            raise KadroHatasi(str(exc)) from exc
        k_motor, k_model, not_ = roller.meslek_motoru(
            rol_ad, self.db, self.proje_id, musait_motorlar())
        if not motor:
            motor = k_motor
            if not model:
                model = k_model
        elif not model and motor == k_motor:
            model = k_model
        a = self.ise_al(ad, rol_ad, motor=motor, model=model, **kw)
        if not_:
            self.db.olay_yaz(self.proje_id, "uyari", f"{a['ad']}: {not_}", ajan_ad=a["ad"])
        return a

    # -- organizasyon: tasi, cikar, lider ----------------------------------

    def _acik_isleri(self, ad: str) -> list:
        with self.db.baglanti() as conn:
            return [f"#{r['no']}" for r in conn.execute(
                "SELECT no FROM gorev WHERE proje_id = ? AND sahip = ? "
                "AND durum NOT IN ('bitti', 'iptal') ORDER BY no",
                (self.proje_id, ad)).fetchall()]

    def tasi(self, ad: str, kanat_id: str) -> dict:
        """Ajani baska takima tasir; hafizasi, dersleri ve oturumu onunla gider.

        Acik isi varsa REDDEDILIR: is eski takimin lideriyle incelenir, ajan
        yari yolda takim degistirirse kimin inceleyecegi belirsizlesir.
        Lider tasinmaz -- once takimina baska bir lider secilir.
        """
        a = self.ajan(ad)
        if a.get("arsiv"):
            raise KadroHatasi(f"{ad} arsivde; once geri al.")
        with self.db.baglanti() as conn:
            if not conn.execute("SELECT 1 FROM kanat WHERE proje_id = ? AND id = ?",
                                (self.proje_id, kanat_id)).fetchone():
                raise KadroHatasi("Hedef takim yok.")
        if a["kanat_id"] == kanat_id:
            return a
        if a["lider_mi"]:
            raise KadroHatasi(f"{ad} takiminin LIDERI. Once o takima baska bir "
                              "lider sec, sonra tasi -- lidersiz takim is dagitamaz.")
        acik = self._acik_isleri(ad)
        if acik:
            raise KadroHatasi(f"{ad}'in acik isleri var ({', '.join(acik)}). Isler "
                              "bitsin ya da iptal edilsin, sonra tasi.")
        # TAKIM KLASORU (06.10.2026): eski takiminin kokunde calisan ajan
        # yeni takiminin kokune gecer; KENDI klasoru olan (yalitilmis) ajanin
        # klasoruna dokunulmaz.
        from .tahta import kanat_koku, _kok_anahtari
        with self.db.baglanti() as conn:
            pr = conn.execute("SELECT kok_klasor FROM proje WHERE id = ?", (self.proje_id,)).fetchone()
        proje_kok = (pr["kok_klasor"] if pr else "") or ""
        eski_kok = kanat_koku(self.db, a["kanat_id"]) or proje_kok
        yeni_kok = a["klasor"]
        if eski_kok and _kok_anahtari(a["klasor"]) == _kok_anahtari(eski_kok):
            yeni_kok = kanat_koku(self.db, kanat_id) or proje_kok or a["klasor"]
        with self.db.baglanti() as conn:
            conn.execute("UPDATE ajan SET kanat_id = ?, klasor = ?, revizyon = revizyon + 1, "
                         "guncellendi = ? WHERE proje_id = ? AND ad = ?",
                         (kanat_id, yeni_kok, simdi(), self.proje_id, ad))
        self.db.olay_yaz(self.proje_id, "ajan_tasindi", f"{ad} baska takima tasindi",
                         ajan_ad="insan")
        return self.ajan(ad)

    def cikar(self, ad: str) -> dict:
        """Ajani takimdan cikarir: ARSIVE gider, silinmez (ad geri donmez,
        sicili ve gecmis isleri okunur kalir). Acik isi olan ve takiminda
        baska ajan varken LIDER olan ajan cikarilamaz."""
        a = self.ajan(ad)
        if a.get("arsiv"):
            return a
        acik = self._acik_isleri(ad)
        if acik:
            raise KadroHatasi(f"{ad}'in acik isleri var ({', '.join(acik)}). Isler "
                              "bitsin ya da iptal edilsin, sonra cikar.")
        if a["lider_mi"]:
            with self.db.baglanti() as conn:
                diger = conn.execute(
                    "SELECT COUNT(*) AS n FROM ajan WHERE proje_id = ? AND kanat_id IS ? "
                    "AND ad != ? AND arsiv = 0", (self.proje_id, a["kanat_id"], ad)
                ).fetchone()["n"]
            if diger:
                raise KadroHatasi(f"{ad} takiminin LIDERI ve takimda {diger} ajan "
                                  "daha var. Once baska bir lider sec.")
        with self.db.baglanti() as conn:
            conn.execute("UPDATE ajan SET arsiv = 1, lider_mi = 0, kanat_id = NULL, "
                         "revizyon = revizyon + 1, guncellendi = ? "
                         "WHERE proje_id = ? AND ad = ?", (simdi(), self.proje_id, ad))
        self.db.olay_yaz(self.proje_id, "ajan_cikarildi",
                         f"{ad} ({a['meslek']}) takimdan cikarildi -- arsivde, ad geri donmez",
                         ajan_ad="insan")
        return self.ajan(ad)

    def lider_yap(self, ad: str) -> dict:
        """Ajani KENDI takiminin lideri yapar; eski lider ekip uyesi olur.
        Takimda tek lider kurali korunur (ayni islemde biri iner, biri cikar)."""
        a = self.ajan(ad)
        if a.get("arsiv"):
            raise KadroHatasi(f"{ad} arsivde.")
        if a["tur"] != "eller":
            raise KadroHatasi("Lider 'eller' olmali: gorev acar, tahtaya yazar, kanit inceler.")
        if a["lider_mi"]:
            return a
        with self.db.baglanti() as conn:
            conn.execute("UPDATE ajan SET lider_mi = 0, guncellendi = ? WHERE proje_id = ? "
                         "AND kanat_id IS ? AND lider_mi = 1",
                         (simdi(), self.proje_id, a["kanat_id"]))
            conn.execute("UPDATE ajan SET lider_mi = 1, revizyon = revizyon + 1, "
                         "guncellendi = ? WHERE proje_id = ? AND ad = ?",
                         (simdi(), self.proje_id, ad))
        self.db.olay_yaz(self.proje_id, "lider_degisti", f"{ad} takiminin lideri oldu",
                         ajan_ad="insan")
        return self.ajan(ad)

    def karakter_yaz(self, ad: str, karakter: str) -> dict:
        karakter = (karakter or "").strip()
        if karakter and not re.fullmatch(r"\d{1,2}:\d{1,2}:\d{1,2}", karakter):
            raise KadroHatasi("Karakter 'sac:ten:kumas' bicimi olmali (orn. 2:1:0).")
        self.ajan(ad)
        with self.db.baglanti() as conn:
            conn.execute("UPDATE ajan SET karakter = ?, guncellendi = ? "
                         "WHERE proje_id = ? AND ad = ?",
                         (karakter, simdi(), self.proje_id, ad))
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
        if model is not None and model != mevcut["model"]:
            self._kapi_uyarisi(ad, model)
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

    def liste(self, kanat_id: str = None, *, arsivli: bool = False) -> list:
        """Kadro. ARSIVDEKILER varsayilan olarak YOK: cikarilan ajan is
        almaz, lidere gosterilmez, sohbette adreslenmez. Ad kontrolu gibi
        "butun adlar" gereken yer `arsivli=True` verir."""
        arsiv = "" if arsivli else " AND arsiv = 0"
        with self.db.baglanti() as conn:
            if kanat_id:
                rows = conn.execute(
                    "SELECT * FROM ajan WHERE proje_id = ? AND kanat_id = ?" + arsiv
                    + " ORDER BY lider_mi DESC, ad",
                    (self.proje_id, kanat_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM ajan WHERE proje_id = ?" + arsiv
                    + " ORDER BY lider_mi DESC, ad",
                    (self.proje_id,),
                ).fetchall()
        return [dict(r) for r in rows]

    def lider(self, kanat_id: str = None) -> dict:
        with self.db.baglanti() as conn:
            row = conn.execute(
                "SELECT * FROM ajan WHERE proje_id = ? AND kanat_id IS ? AND lider_mi = 1 "
                "AND arsiv = 0",
                (self.proje_id, kanat_id),
            ).fetchone()
        if not row:
            raise KadroHatasi("Bu kanadin lideri yok. Once lider ise al.")
        return dict(row)

    def gorevin_lideri(self, gorev: dict) -> dict:
        """Bir isin lideri -- TEK KURAL (inceleme, ajanin lidere sorusu).

        OLCULDU (01.10.2026): `lider(gorev["kanat_id"])` takimi yazili
        OLMAYAN eski iste `kanat_id IS NULL` olan bir lider ariyordu; patronun
        ofisinde demir'in takimi ANA, yani o 9 eski isten biri incelemeye
        gelse inceleme "lideri yok" hatasiyla butun halkayi dusururdu.
        Sira: isin takimi -> sahibinin takimi -> ofiste TEK lider varsa o.
        """
        if gorev.get("kanat_id"):
            return self.lider(gorev["kanat_id"])
        if gorev.get("sahip"):
            try:
                return self.lider(self.ajan(gorev["sahip"])["kanat_id"])
            except KadroHatasi:
                pass
        liderler = [a for a in self.liste() if a["lider_mi"]]
        if len(liderler) == 1:
            return liderler[0]
        raise KadroHatasi(f"#{gorev.get('no')} isin takimi ve sahibi yok, ofiste "
                          f"{len(liderler)} lider var: kimin inceleyecegi belirsiz. "
                          "Isi bir takima ata.")

    # -- sicil (ders) ------------------------------------------------------

    def ders_yaz(self, ajan_ad: str, ders: str, gorev_id: str = None) -> dict:
        """Ayni ders ikinci kez gelirse tekrar sayaci artar, yeni satir acilmaz.

        Tekrar sayisi onemlidir: lider "bunu sana ucuncu kez soyluyorum"
        diyebilmeli ve brifingde o satir one cikmali.
        """
        ders = (ders or "").strip()
        if not ders:
            raise KadroHatasi("Bos ders yazilamaz.")
        # HAFIZA KAPISI (bellek.koruma_kapisi ile ayni kural): ders her
        # brifinge girer. Reddedilen ders incelemeyi DUSURMEZ (isin
        # hukmu ayri), yalniz yazilmaz ve patrona gosterilir.
        from .riskli import koruma_asma
        bulunan = koruma_asma(ders)
        if bulunan:
            self.db.olay_yaz(
                self.proje_id, "hafiza_reddi",
                f"{ajan_ad} icin ders yazilmak istendi; ofis DURDURDU (korumayi "
                f"asmayi anlatiyor: '{bulunan}'). Yazi: {' '.join(ders.split())[:300]}",
                ajan_ad=ajan_ad, gorev_id=gorev_id)
            return {"id": None, "ders": ders, "tekrar": 0, "reddedildi": True}
        an = simdi()
        with self.db.baglanti() as conn:
            row = conn.execute(
                "SELECT id, tekrar, kaldirildi FROM ders WHERE proje_id = ? AND ajan_ad = ? AND ders = ?",
                (self.proje_id, ajan_ad, ders),
            ).fetchone()
            if row and row["kaldirildi"]:
                # Patron bu dersi YANLIS dedi: lider yeniden yazsa da geri gelmez.
                return {"id": row["id"], "ders": ders, "tekrar": 0, "reddedildi": True,
                        "sebep": "patron yanlis dedi"}
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
        from .riskli import hata_gomme
        _hg = hata_gomme(ders)
        if _hg:
            self.db.olay_yaz(self.proje_id, "hata_suphesi",
                             f"{ajan_ad} icin bir DOLANMA YOLU ders olarak yazildi -- altinda "
                             f"duzeltilecek bir hata olabilir ('{_hg}'): {' '.join(ders.split())[:300]}",
                             ajan_ad=ajan_ad, gorev_id=gorev_id)
        # TEKRAR SAYISI OLAYA YAZILIR. Olculdu (21.09): sayac defterde dogru
        # artiyordu ama olay govdesi her seferinde AYNI cumleydi -- panel
        # ayni satiri iki kez basiyor, anlamli sinyal ("bu ajan ayni hatayi
        # yapmaya devam ediyor") ekrandan kayboluyordu.
        ek = f"  [{tekrar}. kez]" if tekrar > 1 else ""
        self.db.olay_yaz(self.proje_id, "ders", f"{ajan_ad}: {ders}{ek}",
                         ajan_ad=ajan_ad)
        return {"id": ders_id, "ders": ders, "tekrar": tekrar}

    def ders_yanlis(self, ders_id: str, sebep: str) -> dict:
        """Patron dersi YANLIS diye kaldirir: brifinge girmez, geri gelmez."""
        sebep = " ".join((sebep or "").split())
        if not sebep:
            raise KadroHatasi("Sebep zorunlu: bu ders neden yanlis?")
        with self.db.baglanti() as conn:
            r = conn.execute("SELECT ajan_ad, ders FROM ders WHERE id = ? AND proje_id = ?",
                             (ders_id, self.proje_id)).fetchone()
            if not r:
                raise KadroHatasi("Boyle bir ders yok.")
            conn.execute("UPDATE ders SET kaldirildi = ? WHERE id = ?", (sebep[:400], ders_id))
        self.db.olay_yaz(self.proje_id, "ders_yanlis",
                         f"{r['ajan_ad']}: '{r['ders'][:200]}' YANLIS diye kaldirildi -- {sebep[:200]}",
                         ajan_ad="insan")
        return {"ajan": r["ajan_ad"], "ders": r["ders"]}

    def dersler(self, ajan_ad: str) -> list:
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT ders, tekrar FROM ders WHERE proje_id = ? AND ajan_ad = ? AND kaldirildi = '' "
                "ORDER BY tekrar DESC, guncellendi DESC, rowid DESC",
                (self.proje_id, ajan_ad),
            ).fetchall()
        return [dict(r) for r in rows]
