# -*- coding: utf-8 -*-
"""Danisma: bir ajanin bir ajana sordugu soruyu TESLIM EDEN parca.

Bugune kadarki SESSIZ hata buydu: `soru_sor` aracinin varsayilan alicisi
"lider"di ve lider bir AJANDIR. Yani bir ajan lidere soru sordugunda,
soru kimseye ulasmiyordu -- insanin "senden bekleniyor" kuyruguna dusup
orada duruyordu. Ofis, liderin cevaplamasi gereken soruyu sessizce
insana havale ediyordu. Hata vermiyordu; sadece yanlis kisi bekliyordu.

Bu, projenin karsi kuruldugu hata sinifinin ta kendisi: **sistem saglikli
gorunurken yanlis calisiyor.**

## Ajan ajana danisma -- kural

Kullanici sordu: *"bir ajan digerine is fikir soru danisabilecek mi?"*
Cevap: **evet, ama yalnizca SORU olarak; asla talimat olarak.**

Gerekce olcume dayanir: MAST'in ikinci en buyuk hata kumesi ajanlar arasi
uyumsuzluk (%36,9) ve serbest ajan sohbeti tam olarak o hatanin yasadigi
yer -- iki ajan kendi aralarinda karar verir, kimse gormez, ucuncusu
baska varsayimla calisir. Bu yuzden:

* **Danisan yazamaz, danisilan da yazamaz** (`yazabilir=False`). Danisma
  bilgi alisverisidir, yetki devri degil. Danisilan yazabilseydi ayni
  anda iki ajan yaziyor olurdu (Yasa 1) ve o yazma HICBIR KILIDIN altinda
  olmazdi -- kilit makinesi bunu hic gormezdi.

* **Danisma bir YAPRAKTIR: danisilanin arac kutusu yoktur.** MCP
  verilmez, yani danisilan ajan kendi de soru soramaz. Sayacla
  sinirlamadik, YAPIYLA sinirladik: A->B->C->A halkasi kurulamaz cunku
  B'nin sorma yetenegi yoktur. Sayac, unutuldugunda sessizce buyur;
  olmayan bir yetenek unutulmaz.

* **Is acamaz.** Gorev acmak yalnizca liderdedir (zaten kodda). Danisma
  bilgi verir, is dagitmaz.

* **Temiz oturum** (Yasa 4). Danisilan, soranin transkriptini almaz --
  taze bir goz olmasinin butun degeri bu. Aldigi sey: kim soruyor, hangi
  is icin, soru ne, ve ofisin gecerli bilgileri.

* **"Bilmiyorum" gecerli bir cevaptir ve INSANA YUKSELIR.** Cevap
  zorlanirsa cevap URETILIR. Danisilan bilmiyorsa soru olmez, insana
  yonlendirilir -- sessizce kaybolmasi, en bastaki hatanin aynisi olurdu.

* **Kilit alinmaz, gorev durumu degismez.** Danisma kisa ve salt okunur;
  ne danisanin ne danisilanin isi yer degistirir.
"""

from __future__ import annotations

from . import kullanim, roller
from .guncelleme import model_coz as _model_coz
from .motor import motor_ac, MotorHatasi
from .postane import NOT_KURALI, gorev_notlari
from .tahta import TahtaHatasi

#: Danisilanin cevabinin ustunde durulacak uzunluk. Danisma kisa bir
#: bilgi alisverisidir; uzayan sey cevap degil, isin kendisidir -- o da
#: bir GOREV olarak acilmalidir, danisma olarak degil.
CEVAP_SINIRI = 3000

#: Danisilan bunu yazarsa bilmedigi anlasilir ve soru insana yukselir.
BILMIYORUM = "BILMIYORUM"


class DanismaHatasi(RuntimeError):
    pass


class Danisma:
    def __init__(self, ofis, *, motor_fabrikasi=motor_ac) -> None:
        self.ofis = ofis
        self.db = ofis.db
        self.proje_id = ofis.proje_id
        self.motor_fabrikasi = motor_fabrikasi

    # -- metin -------------------------------------------------------------

    #: Takim sohbetinden danisilana gosterilen son oge sayisi ve harf siniri.
    TAKIM_OZETI_ADET = 8
    TAKIM_OZETI_HARF = 400

    def _takim_ozeti(self, mesaj: dict) -> list:
        """Patronun `@ajan` sorusunda TAKIM SOHBETININ son satirlari.

        OLCULDU (29.09.2026, gercek haiku): patron `@ege is:` ile iki slogan
        yazdirdi, sonra `@cem hangi slogani daha iyi buldun?` dedi. Cem
        "hangi sloganlari gormuyorum" dedi -- dogru davrandi (uydurmadi)
        ama takim sohbetinde soru, odada az once konusulana dayanir.
        Yasa 4'un "temiz goz"u AJANIN KENDI transkriptine karsidir; bu,
        patronla ayni odanin ortak konusmasi. Ajanlar ARASI danismada
        verilmez: orada taze goz bilincli.

        Kisa ve sinirli: her oge kesilir, sayi sinirli -- her soruda odenir.
        """
        from .takim import akis
        try:
            kanat = self.ofis.kadro.ajan(mesaj["alici"])["kanat_id"]
        except Exception:
            kanat = None
        ogeler = [x for x in akis(self.ofis, kanat_id=kanat, adet=40)
                  if x.get("id") != mesaj.get("id")][-self.TAKIM_OZETI_ADET:]
        if not ogeler:
            return []
        satirlar = ["", "## TAKIM SOHBETINDE SON KONUSULANLAR",
                    "(patron bunlari goruyor; sorusu bunlara dayanabilir)", ""]
        for x in ogeler:
            kimden = "patron" if x["kimden"] == "insan" else x["kimden"]
            kime = (" -> " + ("patron" if x["kime"] == "insan" else x["kime"])
                    if x["kime"] else "")
            no = f" #{x['gorev_no']}" if x.get("gorev_no") else ""
            metin = " ".join((x["metin"] or "").split())[:self.TAKIM_OZETI_HARF]
            satirlar.append(f"- {kimden}{kime} [{x['tur']}{no}]: {metin}")
        return satirlar

    def soru_metni(self, mesaj: dict) -> str:
        """Danisilanin gorecegi metin. Transkript YOK, taze goz var."""
        soran = mesaj["gonderen"]
        satirlar = [
            "# SANA BIR SORU SORULDU",
            "",
            ("**Patron (insan)** sana DOGRUDAN soruyor -- ofisin sahibi, "
             "karar onun." if soran == "insan" else f"**{soran}** sana daniyor."),
        ]

        try:
            soran_ajan = self.ofis.kadro.ajan(soran)
            satirlar.append(f"Meslegi: {soran_ajan['meslek']}.")
        except Exception:
            pass

        if mesaj.get("gorev_no"):
            try:
                g = self.ofis.tahta.gorev(mesaj["gorev_no"])
                satirlar += [
                    "",
                    f"Uzerinde calistigi is: **#{g['no']} {g['baslik']}**",
                    f"- neden: {g['neden']}",
                    f"- ana hedef: {g['ana_hedef']}",
                    f"- kabul olcutu: {g['kabul_olcutu']}",
                    f"- yazma alani: {', '.join(g['yazma_alani']) or 'yok'}",
                ]
                # PATRONUN NOTLARI danismaya da girer. OLCULDU (27.09, D14
                # codex): ajan notla is metninin celistigini sordu, danisma
                # notu gormedigi icin "kullanma" dedi, ayni liderin
                # incelemesi notu gorup isi geri gonderdi. Akil veren ile
                # hukum veren AYNI resme bakmali.
                notlar = gorev_notlari(self.db, self.proje_id, g["id"])
                if notlar:
                    satirlar += ["", f"Patronun bu ise notlari ({NOT_KURALI}):"]
                    satirlar += [f"- {n['govde'][:400]}" for n in notlar]
            except TahtaHatasi:
                # Gorev silinmis olabilir: soru yine cevaplanir. DAR tutuldu:
                # genis `except` notlarin okunamamasini da yutardi.
                pass

        if soran == "insan":
            satirlar += self._takim_ozeti(mesaj)

        satirlar += ["", "## SORUSU", "", mesaj["govde"], ""]

        with self.db.baglanti() as conn:
            proje = conn.execute("SELECT * FROM proje WHERE id = ?",
                                 (self.proje_id,)).fetchone()
        if proje is not None:
            satirlar += ["---", "", "## PROJE", "",
                         f"- amac: {proje['amac']}",
                         f"- basari olcutu: {proje['basari_olcutu']}"]
            if proje["kisitlar"]:
                satirlar.append(f"- kisitlar: {proje['kisitlar']}")
            if proje["kapsam_disi"]:
                satirlar.append(f"- kapsam disi: {proje['kapsam_disi']}")
            # Kurallar danisilana da girer: kurala aykiri bir akil vermek,
            # kuralin ise bosuna konmus olmasi demek.
            satirlar += self.ofis.brifing.kural_satirlari()

        olgular = self.ofis.bellek.ilgili_olgular(mesaj["govde"])["secilen"]
        if olgular:
            satirlar += ["", "## BILINENLER", ""]
            for o in olgular:
                satirlar.append(f"- {o['konu']}: {o['icerik']}")

        satirlar += [
            "",
            "---",
            "",
            "## NE YAPACAKSIN",
            "",
            "Soruyu **kendi uzmanligindan** cevapla. Kisa ve net yaz.",
            "",
            "Sinirlarin -- bunlar kasitli:",
            "",
            "- **Dosya YAZAMAZSIN.** Bu bir danisma, is degil. Isi soran",
            "  yapacak; sen ona ne yapmasi gerektigini soyleyeceksin.",
            "- **Is acamazsin, gorev veremezsin.** Sen akil verirsin.",
            "- **Baskasina soru soramazsin.** Bu turda arac kutun yok.",
            "",
            f"**Bilmiyorsan tek basina `{BILMIYORUM}` yaz** ve sebebini",
            "ekle. Soru olmez, insana yukselir. UYDURMA: yanlis bir cevap,",
            "cevapsizliktan pahalidir -- soran ona guvenip yoluna devam eder.",
        ]
        return "\n".join(satirlar)

    # -- calistirma --------------------------------------------------------

    def cevapla(self, mesaj: dict, *, butce_usd=None, zaman_asimi=None) -> dict:
        """Danisilani kosturur, cevabi TAHTAYA gecirir.

        Doner: `{"durum": "cevaplandi"|"yukseldi", "cevap", "ajan"}`.
        """
        alici = mesaj["alici"]
        try:
            ajan = self.ofis.kadro.ajan(alici)
        except Exception as exc:
            return self._yukselt(mesaj, f"'{alici}' diye bir ajan yok: {exc}")

        if ajan["faz"] == "basarisiz":
            return self._yukselt(
                mesaj, f"'{alici}' basarisiz fazda, cevap veremez.")

        metin = self.soru_metni(mesaj)
        try:
            ham = self._kostur(ajan, metin, butce_usd, zaman_asimi)
        except (MotorHatasi, DanismaHatasi) as exc:
            # Cevap alinamadi. SESSIZCE BIRAKILMAZ -- soru insana yukselir.
            # En bastaki hata zaten "soru kimseye ulasmiyordu"ydu.
            return self._yukselt(mesaj, f"'{alici}' cevap veremedi: {exc}")

        cevap = (ham or "").strip()[:CEVAP_SINIRI]
        if not cevap:
            return self._yukselt(mesaj, f"'{alici}' bos cevap dondurdu.")
        if cevap.upper().startswith(BILMIYORUM):
            return self._yukselt(mesaj, f"'{alici}' bilmiyor: {cevap}")

        self.ofis.postane.cevapla(mesaj["id"], cevap, cevaplayan=alici)
        self.db.olay_yaz(self.proje_id, "danisma",
                         f"{alici} -> {mesaj['gonderen']}: {cevap[:200]}",
                         ajan_ad=alici, gorev_id=mesaj.get("gorev_id"))
        return {"durum": "cevaplandi", "cevap": cevap, "ajan": alici}

    def insana_cevapla(self, mesaj: dict, *, butce_usd=None,
                       zaman_asimi=None) -> dict:
        """Insanin DOGRUDAN bir ajana sordugu soru -- panelin "ajana sor"u.

        `cevapla`dan tek farki: YUKSELTME YOK. Ajanlar arasinda cevapsiz
        soru insana yukselir; ama burada soran ZATEN insan -- yukseltmek
        insanin kendi sorusunu kendi kuyruguna dusururdu. Cevap alinamazsa
        SEBEBI cevap olarak yazilir: cevapsizlik yine gorunur olur.

        Sinirlar ayni ve YAPIYLA: yazamaz, is acamaz, arac kutusu yok.
        Ajana sormak bilgi alisverisidir, emir degil -- is vermek hala
        yalnizca liderin yetkisi.
        """
        alici = mesaj["alici"]
        try:
            ajan = self.ofis.kadro.ajan(alici)
        except Exception as exc:
            cevap = f"(cevap alinamadi: '{alici}' diye bir ajan yok -- {exc})"
        else:
            try:
                cevap = (self._kostur(ajan, self.soru_metni(mesaj), butce_usd,
                                      zaman_asimi) or "").strip()[:CEVAP_SINIRI]
                if not cevap:
                    cevap = "(cevap alinamadi: ajan bos cevap dondurdu)"
            except (MotorHatasi, DanismaHatasi) as exc:
                cevap = f"(cevap alinamadi: {exc})"
        self.ofis.postane.cevapla(mesaj["id"], cevap, cevaplayan=alici)
        return {"cevap": cevap, "ajan": alici}

    def bekleyenleri_cevapla(self, *, butce_usd=None, zaman_asimi=None) -> list:
        """Ajana yonelmis butun bekleyen sorulari teslim eder."""
        sonuclar = []
        for m in self.ofis.postane.ajana_bekleyenler():
            try:
                sonuclar.append(self.cevapla(m, butce_usd=butce_usd,
                                             zaman_asimi=zaman_asimi))
            except Exception as exc:          # tek soru butun turu dusurmesin
                sonuclar.append(self._yukselt(m, f"Danisma dustu: {exc}"))
        return sonuclar

    # -- ic isleyis --------------------------------------------------------

    def _yukselt(self, mesaj: dict, sebep: str) -> dict:
        self.ofis.postane.insana_yonlendir(mesaj["id"], sebep)
        return {"durum": "yukseldi", "cevap": "", "ajan": mesaj["alici"],
                "sebep": sebep}

    def _kostur(self, ajan: dict, metin: str, butce_usd, zaman_asimi) -> str:
        """Danisilani TEMIZ oturumda, YAZMA YETKISI VERMEDEN kosturur.

        `mcp_yapilandirma` verilmez: danisilanin arac kutusu yoktur, yani
        kendi de soru soramaz. Danisma zinciri yapiyla kesilir.
        """
        motor = self.motor_fabrikasi(ajan["motor"])
        parcalar = []
        try:
            for olay in motor.tur_kos(
                metin, klasor=ajan["klasor"], oturum_id="",
                # Takma ad ofisin sabitledigi kimlige cevrilir (zincirle ayni).
                model=_model_coz(self.db, self.proje_id, ajan["motor"], ajan["model"]),
                efor=roller.tur_eforu(self.db, self.proje_id, ajan["efor"]),
                yazabilir=False,
                butce_usd=(butce_usd
                           if getattr(motor, "butce_destegi", False) else None),
                zaman_asimi=zaman_asimi,
            ):
                if olay.tur == "metin":
                    parcalar.append(olay.govde)
                elif olay.tur == "bitti":
                    # Danisma da bir motor turudur ve OLCULUR -- hic
                    # yazilmiyordu; ofisin harcamasi bu yolu gormuyordu.
                    kullanim.tur_ozeti_yaz(
                        self.db, self.proje_id, olay.ek, ajan_ad=ajan["ad"],
                        motor=ajan["motor"], yol="danisma")
                    if not olay.ek.get("basarili") and not parcalar:
                        raise DanismaHatasi("danisma turu basarisiz oldu")
        except MotorHatasi as exc:
            raise DanismaHatasi(f"motor baslamadi: {exc}") from exc
        return "".join(parcalar)
