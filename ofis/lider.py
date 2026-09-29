# -*- coding: utf-8 -*-
"""Lider: fan-out kapisi, dagitim ve kanita karsi inceleme.

Liderin uc isi var ve ucu de birer KAPIDIR -- kolaylik degil:

1. **Fan-out kapisi.** Bolmek varsayilan degildir. Anthropic'in olcumu:
   coklu ajan ~15x jeton yakar ve yalnizca genislik-oncelikli iste kazanir;
   performans varyansinin %80'ini jeton kullanimi acikliyor. Lider bolse
   de bolmese de GEREKCESINI karar gunlugune yazar. Gerekce zorunlu
   olmasaydi bolmek "daha hizli olur herhalde" sanisiyla varsayilana
   donusurdu -- rakipte bildirilen hata da bunun tersiydi: lider hic
   dagitmiyor, isi kendi iginde kosuyordu. Iki uc da kayittan anlasilir.

2. **Ayrik alan kapisi.** Kollar PLANLAMA aninda cakisirsa reddedilir.
   Cakismayi `sahiplen` de yakalar ama orada is coktan dagitilmis,
   brifingler uretilmis olur. Erken ret ucuzdur.

3. **Inceleme kapisi -- ve burasi en onemlisi.** Lider incelemeye ISCININ
   TRANSKRIPTIYLE girmez. Cognition'in olcumu ("context rot"): inceleyen
   ajan onceki baglami bilmediginde daha iyi buluyor. Transkripti okuyan
   inceleyici, iscinin gerekcelerini de devralir ve ayni kor noktayi
   paylasir -- "mantikli anlatiyor" diye kanitsiz onaylar.

   Bu yuzden lider TEMIZ OTURUMDA acilir ve yalnizca sunu gorur:
       ust hedef  ·  kabul olcutu  ·  KANITLAR  ·  degisen dosyalar
   Ne konusuldugunu degil, NE URETILDIGINI degerlendirir.

   Lider ayrica YAZAMAZ (`yazabilir=False`): inceleyici duzeltmeye
   baslarsa inceleme biter, is devralinmis olur -- ve kimse o duzeltmeyi
   incelemez.

Karar sessizce "kapat"a dusmez: lider acik bir hukum yazmadiysa is
incelemede BEKLER. Belirsizligi onaya cevirmek, kanit kapisini arka
kapidan acmaktir.
"""

from __future__ import annotations

import json
import re
import sqlite3

from . import butce, degisim, kullanim, plan, roller, tarayici, tavan
from .motor import motor_ac, MotorHatasi
from .postane import NOT_KURALI, gorev_notlari
from .zincir import LIDER_ZINCIRI, basamaklari_kur, limitte_devret, lider_devri, tur_butcesi, ZincirBitti
from .tahta import TahtaHatasi, yol_normalle, yollar_cakisir

#: Liderin hukmu. Baska bir sey yazarsa hukum YOK sayilir -- is beklemede
#: kalir. "Herhalde kapat demek istedi" diye yorumlamak, kapiyi kaldirmaktir.
KARAR_DESENI = re.compile(r"^\s*KARAR\s*:\s*(kapat|geri)\b[ \t:-]*(.*)$",
                          re.IGNORECASE | re.MULTILINE)

#: Lider isterse ajana kalici bir ders yazdirir. HER redde otomatik ders
#: yazilmaz: tek seferlik bir eksik, sicili doldurur ve tekrar sayacini
#: anlamsizlastirir. Sayacin degeri, yalnizca GERCEK deseni saymasindadir.
DERS_DESENI = re.compile(r"^\s*DERS\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)

#: Liderin incelemede cikardigi KALICI BILGI: `BILGI: konu -> icerik`.
#:
#: OLCULDU (24.09.2026): iki gercek haiku turunda isci, brifingde ZORUNLU
#: yazan talimata ragmen `bilgi_yaz`i HIC cagirmadi (ayar.txt'den portu
#: okudu, rapora yazdi, hafizaya yazmadi). Hafizayi yalniz iscinin iyi
#: niyetine birakmak onu bos birakmaktir. Inceleme dogal yer: lider daha
#: guclu bir model, isi KANITLA birlikte temiz baglamda okuyor ve DERS
#: satirini zaten ayni bicimde yaziyor.
BILGI_DESENI = re.compile(r"^\s*BILGI\s*:\s*(.+?)\s*->\s*(.+)$",
                          re.IGNORECASE | re.MULTILINE)

#: Bir incelemeden en fazla kac bilgi yazilir -- hafiza bir cop kutusu
#: degil; lider her seyi yazmaya kalkarsa brifing gurultuyle dolar.
AZAMI_INCELEME_BILGI = 5


#: Kacinci retten sonra inceleme KAPI MODELINE yukselir. 2 secildi:
#: birinci ret siradan (isci eksik birakmistir), ikincisi bir DESENDIR
#: -- ya isci anlamiyor ya olcut belirsiz. Ikisi de daha iyi bir goz
#: ister. 1 olsaydi her siradan ret pahaliya kosardi; 3 olsaydi iki tur
#: daha bosa giderdi.
YUKSELTME_ESIGI = 2


class LiderHatasi(RuntimeError):
    pass


class Lider:
    def __init__(self, ofis, *, motor_fabrikasi=motor_ac) -> None:
        self.ofis = ofis
        self.db = ofis.db
        self.proje_id = ofis.proje_id
        self.motor_fabrikasi = motor_fabrikasi

    # -- 1. fan-out kapisi -------------------------------------------------

    def dagitim_karari(self, hedef: str, *, bol: bool, gerekce: str,
                       lider_ad: str, kol_sayisi: int = 1) -> dict:
        """Bolme karari ve GEREKCESI karar gunlugune yazilir.

        Kapinin kendisi budur: karar serbest, kayit zorunlu. Alti ay sonra
        "bunu neden bolmustuk" sorusunun cevabi burada durur.
        """
        gerekce = (gerekce or "").strip()
        if not gerekce:
            raise LiderHatasi(
                "Dagitim gerekcesi zorunlu. Bolmek ~15 kat jeton yakar ve "
                "yalnizca genislik-oncelikli iste kazanir; bolmemek de bir "
                "karardir. Ikisi de gerekcesiyle yazilir."
            )
        karar = (f"'{hedef}' {kol_sayisi} kola bolundu." if bol
                 else f"'{hedef}' bolunmedi, tek ajanda kosacak.")
        return self.ofis.bellek.karar_yaz(
            karar, gerekce, lider_ad, tur="dagitim",
        )

    # -- 2. ayrik alan kapisi ----------------------------------------------

    def kollari_dogrula(self, kollar) -> None:
        """Kollarin yazma alanlari BIRBIRIYLE cakisiyor mu.

        Planlama aninda bakilir. `sahiplen` de yakalar ama orada is
        dagitilmis, brifingler uretilmis olur -- ve lider hatayi ancak
        ikinci ajan calismaya BASLAYAMADIGINDA gorur.
        """
        temiz = []
        for kol in kollar:
            alanlar = [yol_normalle(y) for y in (kol.get("yazma_alani") or [])]
            temiz.append((kol.get("baslik", "?"), [a for a in alanlar if a]))

        for i, (ad_i, alan_i) in enumerate(temiz):
            for ad_j, alan_j in temiz[i + 1:]:
                for a in alan_i:
                    for b in alan_j:
                        if yollar_cakisir(a, b):
                            raise LiderHatasi(
                                f"Kollar ayrik degil: '{ad_i}' ({a}) ile "
                                f"'{ad_j}' ({b}) ayni dosyalara yaziyor. "
                                "Iki ajan ayni anda yazarsa cakisan kararlar "
                                "cikar. Ya alanlari ayir ya tek kolda birlestir."
                            )

    def dagit(self, hedef: str, kollar, *, gerekce: str, lider_ad: str,
              kanat_id: str = None, ek_klasorler=None,
              tarayici_alani=None, tarayici_yazma: bool = True,
              baglayicilar=None, tarayici_kabin: bool = False) -> list:
        """Hedefi kollara bol, gorevleri ac. Kapilar once, is sonra.

        `kollar` ogeleri: baslik, neden, kabul_olcutu, yazma_alani,
        govde (istege bagli), sahip (istege bagli), bagli_oldugu (no listesi).

        `ek_klasorler` HER kola ayni sekilde tasinir ve lider onu
        SECMEZ. Ofis disi bir klasoru acmak bir yetki genislemesidir;
        yetki insandan gelir, dagitim liderden. Lider secseydi, kendi
        actigi bir kapinin gerekcesini yine kendisi yazardi.
        """
        if not kollar:
            raise LiderHatasi("Bos dagitim yapilamaz.")
        bol = len(kollar) > 1
        self.kollari_dogrula(kollar)
        self.dagitim_karari(hedef, bol=bol, gerekce=gerekce,
                            lider_ad=lider_ad, kol_sayisi=len(kollar))

        # PAYLASILAN KABIN yalniz INSANIN ISARET ETTIGI kaynaklara.
        # Lider bir kola kendi sectigi baska bir site yazabilir; kabin o
        # kola da verilseydi patronun oturumu insanin hic isaret etmedigi
        # bir siteye acilirdi. Yetki insandan gelir, dagitim liderden.
        insan_web = set(tarayici.kaynaklari_dogrula(tarayici_alani or []))

        def _kol_web(kol) -> list:
            # Modelin yazdigi listede bos satir olabilir; bos kaynak
            # `gorev_ac`ta istisna atar ve plan kapisindan gecmis bir isi
            # acilirken oldururdu.
            kendi = [str(w).strip() for w in (kol.get("tarayici_alani") or [])
                     if str(w).strip()]
            return kendi or list(tarayici_alani or [])

        def _kabin_mi(kol) -> bool:
            if not (tarayici_kabin and insan_web):
                return False
            kol_web = set(tarayici.kaynaklari_dogrula(_kol_web(kol)))
            return bool(kol_web) and kol_web <= insan_web

        acilan = []
        for kol in kollar:
            acilan.append(self.ofis.tahta.gorev_ac(
                kol["baslik"],
                neden=kol.get("neden", ""),
                ana_hedef=hedef,          # ust hedef HER kola tasinir
                kabul_olcutu=kol.get("kabul_olcutu", ""),
                govde=kol.get("govde", ""),
                yazma_alani=kol.get("yazma_alani") or [],
                sahip=kol.get("sahip", ""),
                bagli_oldugu=kol.get("bagli_oldugu") or [],
                kanat_id=kanat_id,
                acan=lider_ad,
                ek_klasorler=ek_klasorler,
                tarayici_alani=_kol_web(kol),
                # YAZMA YETKISI PLANDAN GELMEZ, INSANDAN GELIR.
                # `tarayici_alani` kolun kendisinden gelebiliyor (lider
                # hangi siteye bakilacagini secebilir) ama YAZMA oyle
                # degil: lider kendi actigi bir kapinin gerekcesini yine
                # kendisi yazardi -- kanit kapisinin kendi isini
                # onaylamasi gibi. Klasor ve kadro kurallarinin aynisi:
                # *yetki insandan gelir, dagitim liderden.*
                tarayici_yazma=bool(tarayici_yazma),
                tarayici_kabin=_kabin_mi(kol),
                # Lider baglayici SECMEZ; insanin verdigini isler.
                # Yetki insandan gelir, dagitim liderden.
                baglayicilar=baglayicilar or [],
                zorluk=kol.get("zorluk", ""),
                zorluk_gerekce=kol.get("zorluk_gerekce", ""),
            ))
        return acilan

    # -- 3. inceleme kapisi ------------------------------------------------

    def bekleyen_incelemeler(self) -> list:
        return self.ofis.tahta.liste(durum="inceleme")

    def _isin_yeri(self, gorev: dict) -> str:
        """Isin URETILDIGI klasor. Inceleme orada kosar.

        OLCULDU -- ve pahali bir hataydi: inceleme once liderin KENDI
        klasorunde kosuyordu; isci klasoru yalnizca `--add-dir` ile
        erisilebilir yapilmisti. Lider `Glob` calistirdi, calisma dizini
        bos oldugu icin hicbir sey bulamadi ve isi "dosyalar ortada yok,
        kanit dogrulanamiyor" diyerek REDDETTI. Dosyalar duruyordu; isci
        isini dogru yapmisti. Dahasi lider, iscinin siciline "kanit
        uydurma" dersi yazdi -- yanlis bir ders, kalici bir kayit ve
        tekrar ederse sayaci da siser.

        Ders: inceleyiciye "bak" demek yetmez, NEREYE bakacagi verilir.
        Eksik baglam, kotu niyet gibi gorunur.
        """
        isci_ad = gorev["sahip"]
        if isci_ad:
            isci = self.ofis.kadro.ajan(isci_ad)
            if isci["klasor"]:
                return isci["klasor"]
        return ""

    def inceleme_metni(self, no: int) -> str:
        """Liderin gorecegi TEK sey. Transkript YOK, tartisma YOK.

        Burada olmayan sey bilincli olarak yoktur: iscinin ne dedigi, hangi
        yolu denedigi, neyi zor buldugu. Inceleyici bunlari bilirse iscinin
        cercevesini devralir. Degerlendirilecek olan anlati degil URUNDUR.
        """
        g = self.ofis.tahta.gorev(no)
        kanitlar = self.ofis.tahta.kanitlar(no)

        satirlar = [
            "## INCELEME",
            "",
            "Bir isi inceliyorsun. Isi YAPAN ajanin anlatisini gormuyorsun --",
            "bilerek. Degerlendirecegin sey anlati degil, URETILEN SEY.",
            "",
            f"### #{g['no']} — {g['baslik']}",
            "",
            f"**Bagli oldugu ust hedef:** {g['ana_hedef']}",
            "",
            f"**Bu is nicin acildi:** {g['neden']}",
            "",
            f"**KABUL OLCUTU:** {g['kabul_olcutu']}",
            "",
            f"**Yazma alani:** {', '.join(g['yazma_alani']) or '—'}",
        ]
        if g["govde"]:
            satirlar += ["", "**Gorev tarifi:**", "", g["govde"]]
        # PATRONUN NOTLARI isin tanimina EKTIR ve incelemeye girer. Girmeseydi
        # lider, patronun "dur, sunu degistir" dedigi isi "olcutten sapti"
        # diye geri gonderirdi. ULASMAYAN not ayrica soylenir: ajan onu hic
        # gormediyse ona uymamasi bir kusur degil, bir TESLIM eksigidir.
        notlar = gorev_notlari(self.db, self.proje_id, g["id"])
        if notlar:
            satirlar += ["", f"**Patronun bu ise notlari** ({NOT_KURALI}):"]
            for n in notlar:
                satirlar.append(
                    f"- {n['govde'][:400]}"
                    + ("" if n["okundu"] else
                       "  _(ajana ULASMADI -- is bu nota gore yapilmadiysa "
                       "GERI GONDER, not bir sonraki turda gider)_"))
        # KUNYE ve KURALLAR incelemeye de girer: kabul olcutunu karsilayan
        # ama KAPSAM DISI olan ya da bir ofis kuralini cignenen is
        # kapatilmamali -- ve inceleyen bunu bilmiyorsa kapatir.
        kunye = self.ofis.brifing.kunye_ozeti()
        if kunye:
            satirlar += ["", kunye,
                         "",
                         "Is kabul olcutunu karsilasa bile KAPSAM DISI bir "
                         "sey yapmissa ya da bir OFIS KURALINI cignemisse "
                         "KAPATMA; hangisi oldugunu soyleyerek geri gonder."]

        yer = self._isin_yeri(g)
        if yer:
            satirlar += [
                "",
                "### Isin bulundugu yer",
                "",
                f"Calisma dizinin ZATEN burasi: `{yer}`",
                "Kanitlari dogrulamak icin dosyalari buradan oku.",
                "Bir dosyayi bulamiyorsan once `ls` ile bak -- yolu yanlis",
                "aramak, isin yapilmadigi anlamina gelmez.",
            ]

        satirlar += ["", "### Sunulan kanitlar", ""]
        if kanitlar:
            for k in kanitlar:
                satirlar.append(f"- **[{k['tur']}]** {k['baslik']}")
                if k["icerik"]:
                    satirlar.append(f"  ```\n  {k['icerik'][:1500]}\n  ```")
        else:
            satirlar.append("- (kanit yok)")

        # OFISIN KENDI OLCUMU -- ajanin sozu degil.
        #
        # Bu blok olmadan kapi kordu. Gercek ofiste 16 `diff` KANITI
        # vardi ve hepsi ajanin anlatisiydi ("ONCEKI / COZUM / satir
        # 68-73"): bir dosyanin degistigini degil, ajanin degistirdigini
        # SOYLEDIGINI kanitliyordu. Simdi liderin elinde anlatiyla
        # karsilastirabilecegi bagimsiz bir olcum var.
        #
        # *Kapi, kendisine verilen olcutten iyi olamaz* -- ama elindeki
        # olcuden de iyi olamaz.
        # GENIS BIR `except` OLMAZ. Yazarken once `except Exception`
        # koymustum -- yani tam kendi kuralimi cignedim: genis bir
        # except, sessizce yok sayilan ayarin en kolay kurulma bicimi.
        # Daraltildi ve okunamama hali GORUNUR: olcemedigimize "iyi"
        # demeyiz, "bilinmiyor" deriz (`saglik.py` kurali).
        olculen, olcum_hatasi = [], ""
        try:
            olculen = degisim.oku(self.db, self.proje_id,
                                  gorev_id=g["id"], limit=40)
        except sqlite3.Error as exc:
            olcum_hatasi = str(exc)
        if olcum_hatasi:
            satirlar += [
                "",
                "### Diskte olculen degisiklik: SONUC BILINMIYOR",
                "",
                f"Olcum defteri okunamadi ({olcum_hatasi}). Bu 'degisiklik",
                "yok' DEMEK DEGILDIR -- dosyalari kendin oku.",
            ]
        if olculen:
            o = degisim.ozet(olculen)
            satirlar += [
                "",
                "### Diskte OLCULEN degisiklik (ofisin olcumu, ajanin sozu DEGIL)",
                "",
                f"{o['dosya']} dosya · +{o['eklenen']}/-{o['silinen']} satir",
                "",
            ]
            for k in olculen[:25]:
                isaret = []
                if k["beyan_disi"]:
                    isaret.append("**BEYAN DISI**")
                if k.get("atif_belirsiz"):
                    isaret.append("(atif belirsiz: paralel tur)")
                if k["olculemedi"]:
                    isaret.append(f"({k['olculemedi']})")
                satirlar.append(
                    f"- `{k['yol']}` {k['hal']} +{k['eklenen']}/-{k['silinen']}"
                    + ((" " + " ".join(isaret)) if isaret else ""))
            if o["beyan_disi"]:
                satirlar += [
                    "",
                    "**DIKKAT:** yukarida BEYAN DISI isaretli dosyalar, isin",
                    "yazma alaninin DISINDA. Yazma kilidi bir BEYANDIR ve bu",
                    "olcum beyanin gercekle uyusmadigini gosteriyor. Bunu",
                    "hukmunde ANMADAN gecme: ya isin gercekten oraya dokunmasi",
                    "gerekiyordu (o zaman yazma alani yanlis beyan edilmis) ya",
                    "da dokunmamaliydi (o zaman baska bir isi bozmus olabilir).",
                ]
            if o.get("atif_belirsiz"):
                satirlar += [
                    "",
                    "_Paralel tur kostugu icin bazi satirlarda 'kim yazdi'",
                    "OLCULEMEDI; beyan denetimi o satirlarda yapilmadi._",
                ]
        # Olcum YOKSA sessiz kalinir -- "hicbir sey degismedi" DEMEZ.
        # Kod yazmayan bir is (arastirma, inceleme) zaten dosya
        # degistirmez; ona "degisiklik yok" demek, olcmedigimiz bir seye
        # hukum vermek olurdu.

        satirlar += [
            "",
            "### Nasil inceleyeceksin",
            "",
            "1. Kanitlari **kabul olcutune** karsi tart. Olcutu karsiliyor mu?",
            "2. Sonucu alt gorevin kendi mantigina gore degil, **ust hedefe**",
            "   gore degerlendir. Is kusursuz olup hedefi iskalayabilir.",
            "3. Dosyalari okuyabilirsin ama **DUZELTEMEZSIN**. Duzeltmeye",
            "   baslarsan inceleme biter, isi devralmis olursun -- ve o",
            "   duzeltmeyi kimse incelemez.",
            "4. **Kanitlar BIRBIRIYLE tutarli mi?** Iki kanit ayni soruya",
            "   FARKLI cevap veriyorsa (iki ayri sayi, iki ayri dosya adi)",
            "   bu basli basina bir bulgudur. Hangisinin gecerli oldugunu",
            "   SOYLE ve neden oldugunu yaz; secemiyorsan GERI GONDER.",
            "   Celisen kanit kanit degildir -- hangisine dayanacagini",
            "   bilmeyen bir defter, kayit tutmuyor demektir.",
            "5. Kanit yetersizse ya da olcutu karsilamiyorsa GERI GONDER.",
            "   'Anlatisi mantikli' kanit degildir.",
            "",
            "### Hukmunu TAM OLARAK su bicimde yaz",
            "",
            "Kapatiyorsan:",
            "```",
            "KARAR: kapat",
            "```",
            "Geri gonderiyorsan (gerekce zorunlu -- ajan neyi duzeltecegini bilmeli):",
            "```",
            "KARAR: geri -- <ne eksik, somut olarak>",
            "```",
            "Ajanin tekrarlayan bir hatasi varsa ayrica:",
            "```",
            "DERS: <ajanin bir daha yapmamasi gereken sey>",
            "```",
            "KAPATIYORSAN ve bu is projeye dair KALICI bir deger ortaya",
            "cikardiysa (port, surum, adres, fiyat, hesap adi, klasor yolu) --",
            "baska bir ajanin da bilmesi gereken -- her biri icin bir satir",
            f"(en fazla {AZAMI_INCELEME_BILGI}); yalniz KANITLA dogruladigini yaz:",
            "```",
            "BILGI: <kisa konu> -> <deger (nereden)>",
            "```",
            "Asagidaki HAFIZA bolumunde zaten dogru duran bir bilgiyi TEKRAR",
            "YAZMA. Ayni seyi duzeltiyorsan listedeki konu adini AYNEN kullan:",
            "baska bir adla yazmak ayni olguyu iki konuya boler.",
            "",
            "_Hukum satirini yazmazsan is incelemede bekler; bu bir onay degildir._",
        ]
        satirlar += self._hafiza_blogu(no)
        return "\n".join(satirlar)

    #: Inceleme istemine konu adi olarak girecek en fazla bilgi.
    HAFIZA_KONU_AZAMI = 40

    def _hafiza_blogu(self, no: int) -> list:
        """Liderin BILGI yazmadan once gormesi gereken hafiza.

        OLCULDU (24.09.2026, gercek haiku turu): isci `servis portu`
        yazdi, lider ayni degeri `Servis port numarasi` diye yazdi --
        AYNI OLGU IKI KONUYA bolundu. Harf normallestirmesi farkli kelime
        secimini yakalayamaz; yakalamanin yolu yazanin ne oldugunu GORMESI.
        Gormeden yazmak tahmindir (klasor duzeninde odenen ders).
        """
        olgular = self.ofis.bellek.gecerli_olgular()
        if not olgular:
            return []
        bu_is = [o for o in olgular
                 if str(o.get("kaynak") or "").endswith(f"#{no}")]
        satirlar = ["", "### HAFIZA (BILGI yazmadan once bak)", ""]
        if bu_is:
            satirlar.append("Bu iste ZATEN yazilanlar (dogruysa tekrar yazma):")
            satirlar += [f"- {o['konu']}: {o['icerik']}" for o in bu_is]
            satirlar.append("")
        # Once BU ISE ilgili konular, sonra gerisi: alfabetik ilk 40,
        # hafiza buyuyunce tam ihtiyac duyulan adi disarida birakirdi
        # (sinama bunu yakaladi).
        g = self.ofis.tahta.gorev(no)
        metin = " ".join(str(g.get(a) or "") for a in
                         ("baslik", "govde", "neden", "ana_hedef",
                          "kabul_olcutu"))
        ilgili = [o["konu"] for o in
                  self.ofis.bellek.ilgili_olgular(metin)["secilen"]]
        adlar = list(dict.fromkeys(
            ilgili + [o["konu"] for o in olgular]))[:self.HAFIZA_KONU_AZAMI]
        satirlar.append("Hafizadaki konu adlari: " + ", ".join(adlar)
                        + (f" (+{len(olgular) - len(adlar)} daha)"
                           if len(olgular) > len(adlar) else ""))
        return satirlar

    def incele(self, no: int, *, lider_ad: str = "", butce_usd: float = None,
               zaman_asimi: float = None) -> dict:
        """Lideri TEMIZ oturumda acip hukum aldirir ve hukmu uygular.

        Oturum kimligi bilerek verilmez. Liderin baska islerden birikmis
        baglami, incelemeye tasinmamalidir -- Yasa 4. Her inceleme kendi
        temiz kafasiyla yapilir.
        """
        gorev = self.ofis.tahta.gorev(no)
        if gorev["durum"] != "inceleme":
            raise LiderHatasi(
                f"#{no} incelemede degil, '{gorev['durum']}'. "
                "Inceleme yalnizca isci isi teslim ettikten sonra yapilir."
            )
        if not self.ofis.tahta.kanitlar(no):
            raise LiderHatasi(
                f"#{no} kanitsiz. Kanitsiz is incelenmez de kapanmaz da."
            )

        lider = (self.ofis.kadro.lider(gorev["kanat_id"]) if not lider_ad
                 else self.ofis.kadro.ajan(lider_ad))
        # YAPAN INCELEYEMEZ. Lider birlestirme isini kendi ustlenebilir --
        # ama o isi kendi inceleyemez: kanit kapisi kendi isini onaylamis
        # olurdu ve Yasa 4 (temiz baglam) coker; birlestiren ajan butun
        # parcalarin baglamini tasir, o cerceveyi devralmis olarak bakar.
        # Inceleme o zaman INSANA duser.
        if gorev["sahip"] and gorev["sahip"] == lider["ad"]:
            raise LiderHatasi(
                f"#{no} isini {lider['ad']} yapti; yapan inceleyemez. "
                "Bu isi insan incelemeli ya da baska bir lider bakmali."
            )
        isci_ad = gorev["sahip"]
        isci = self.ofis.kadro.ajan(isci_ad) if isci_ad else None

        # KAPI MODELINE YUKSELTME -- is ikinci kez geri dondugunde.
        #
        # Nobet zincirinin TERSI: orada limit gelince daha ucuza inilir,
        # burada is takildiginda daha guclusune cikilir. Ayni ucuz
        # modeli ucuncu kez kosturmak jeton yakar ve ayni hukmu uretir.
        #
        # UC KURAL, ucu de olculmus bir sebebe dayaniyor:
        #
        # 1. TAVAN ZORUNLU. Kapi modeli (fable) pahali; kullanicinin
        #    olcumu *"tek promptta 5 saatlik limiti bitiriyordu."*
        #    Tavan verilmediyse rolun alt sinirina duseriz -- tavansiz
        #    kosmayiz.
        # 2. TAVAN UYGULANAMIYORSA YUKSELTME YAPILMAZ. `codex` tur
        #    basina tavan uygulayamiyor (`butce_destegi=False`), yani
        #    `astra` otomatik hicbir yola baglanamaz. Para kontrolleri
        #    KAPALI KALARAK basarisiz olur.
        # 3. SESSIZ OLMAZ. Yukseltme gorunur bir olaydir; "bu inceleme
        #    neden pahaliya kosmus" sorusu sonradan cevaplanabilmeli.
        model = lider["model"]
        ret_sayisi = self.ofis.tahta.ret_sayisi(no)
        if ret_sayisi >= YUKSELTME_ESIGI:
            p = plan.oku(self.db, self.proje_id)
            kapi = roller.kapi_modeli(
                lider["motor"], tavansiz_izinli=p["tavansiz_kapi_izinli"])
            # HAFTALIK TAVAN: tur basina tavan tek bir turun kacmasini
            # onler; haftalik tavan COK SAYIDA MAKUL turun toplamda
            # limiti bitirmesini onler. Kullanicinin yasadigi ikincisi.
            hafta = butce.kapi_acik_mi(self.db, self.proje_id)
            if kapi and not hafta["acik"]:
                # Is DURMAZ -- pahali basamak kapanir, inceleme liderin
                # kendi modeliyle kosar. Zincirdeki ayni ayrim: kaynak
                # tukenince is olmez.
                self.db.olay_yaz(
                    self.proje_id, "uyari",
                    f"#{no} yukseltme ATLANDI -- {hafta['sebep']}",
                    ajan_ad=lider["ad"], gorev_id=gorev["id"])
                kapi = None
            if kapi:
                # TUR SINIRI iceride bir kacak frenidir (27.09.2026): haftalik
                # pay saglayicinin kendi yuzdesiyle korunuyor (`butce.py`).
                # Ad `kapi_siniri`: `tavan` bu dosyada MODULDUR (kacak freni).
                kapi_siniri = butce_usd or hafta["tur_siniri"]
                if kapi_siniri:
                    model = kapi["model"]
                    butce_usd = kapi_siniri
                    self.db.olay_yaz(
                        self.proje_id, "yukseltme",
                        f"#{no} {ret_sayisi}. kez geri dondu -> inceleme "
                        f"{lider['motor']}/{model} ile, tavan ${kapi_siniri:.2f}",
                        ajan_ad=lider["ad"], gorev_id=gorev["id"])
            else:
                # Atlanan yukseltme de GORUNUR olmali: gorunmeyen bosluk,
                # "neden hala ayni hukum geliyor" sorusunu cevapsiz birakir.
                self.db.olay_yaz(
                    self.proje_id, "uyari",
                    f"#{no} {ret_sayisi}. kez geri dondu ama "
                    f"'{lider['motor']}' motorunda tavan uygulanabilir bir "
                    "kapi modeli yok -- yukseltme YAPILMADI.",
                    ajan_ad=lider["ad"], gorev_id=gorev["id"])

        metin = self.inceleme_metni(no)
        # Inceleme ISIN URETILDIGI yerde kosar (bkz. `_isin_yeri`): lider
        # kendi bos klasorunde arayip "yok" demesin.
        inceleme_klasoru = self._isin_yeri(gorev) or lider["klasor"]
        # NOBET ZINCIRI -- inceleme de liderin isidir ve limitte DURMAMALI.
        # Kapi modeline yukseltildiyse (fable ayri bir cepten yer) once
        # liderin KENDI modeli denenir: fable'in cebi dolmus olabilir ama
        # hesabin genel penceresi dolmamis olabilir.
        zincir = (((lider["motor"], lider["model"]),) if model != lider["model"]
                  else ()) + LIDER_ZINCIRI
        basamaklar, uyarilar = basamaklari_kur(
            self.db, self.proje_id, dict(lider, model=model),
            fabrika=self.motor_fabrikasi, zincir=zincir, butce_usd=butce_usd,
            kademe_haritasi=roller.kademe_haritasi(self.db, self.proje_id),
            rol="lider")
        for u in uyarilar:
            self.db.olay_yaz(self.proje_id, "uyari", u, ajan_ad=lider["ad"],
                             gorev_id=gorev["id"])

        def kostur(b):
            from .motor.tui import kipe_gore
            # Inceleme de gercek terminalde olabilir -- TEMIZ oturum, salt
            # okunur. Tavan gereken tur (fable hakemi) ARKADA kalir.
            motor = kipe_gore(self.db, self.proje_id,
                              self.motor_fabrikasi(b["motor"]),
                              ajan_ad=lider["ad"], butce_usd=butce_usd)
            parcalar, ek = [], {}
            fren = tavan.KacakFreni()
            for olay in motor.tur_kos(
                metin,
                klasor=inceleme_klasoru,
                oturum_id="",                 # TEMIZ oturum -- Yasa 4
                model=b["model"],             # kapi modeline yukseltilmis olabilir
                # Efor tavani insanindir -- lider turu da uyar.
                efor=roller.tur_eforu(self.db, self.proje_id, lider["efor"]),
                yazabilir=False,              # inceleyici duzeltmez
                # Liderin kendi klasoru + ISIN ofis disi klasorleri.
                # Ikincisi olmazsa inceleyici, iscinin YAZDIGI dosyalari
                # goremez ve kaniti "dogrulanamiyor" diye reddeder --
                # bu hatayi bir kez yasadik ve isciye haksiz ders yazildi.
                ek_klasorler=tuple(
                    ([lider["klasor"]] if lider["klasor"] else [])
                    + list(gorev.get("ek_klasorler") or [])),
                # Dolar tavanini yalniz UYGULAYABILEN motor alir; codex
                # tavan gelince turu hic baslatmadan reddeder.
                butce_usd=tur_butcesi(b, motor, butce_usd),
                zaman_asimi=zaman_asimi,
                ek_ortam=b.get("ortam") or None,
            ):
                kesildi = tavan.lider_freni(
                    self.db, self.proje_id, fren, olay, ajan_ad=lider["ad"],
                    gorev_id=gorev["id"], motor=b["motor"],
                    hesap=b.get("hesap") or "", yol="inceleme")
                if kesildi:
                    return kesildi, []
                if olay.tur == "metin":
                    parcalar.append(olay.govde)
                elif olay.tur == "bitti":
                    ek = dict(olay.ek or {})
                    # INCELEME DE OLCULUR. Hic yazilmiyordu -- ve hakem
                    # (fable) tam bu turda kosuyor, yani haftalik kapi
                    # butcesi en pahali harcamayi GORMUYORDU. Gorevle
                    # etiketlenir: incelemenin jetonu o isin maliyetidir.
                    kullanim.tur_ozeti_yaz(
                        self.db, self.proje_id, ek, ajan_ad=lider["ad"],
                        gorev_id=gorev["id"], motor=b["motor"],
                        hesap=b.get("hesap") or "", yol="inceleme")
            return ek, parcalar

        try:
            _b, ek, parcalar = limitte_devret(
                basamaklar, kostur,
                devir=lambda eski, yeni: lider_devri(
                    self.ofis, lider, eski, yeni, gorev_id=gorev["id"]))
        except ZincirBitti as exc:
            return self._belirsiz(no, f"Inceleme kosulamadi: {exc}")
        except MotorHatasi as exc:
            return self._belirsiz(no, f"Inceleme motoru baslamadi: {exc}")
        if not ek.get("basarili") and not parcalar:
            return self._belirsiz(
                no, "Inceleme turu basarisiz oldu, hukum alinamadi.")

        hukum = "".join(parcalar)
        return self._hukmu_uygula(no, hukum, lider["ad"], isci_ad)

    # -- ic isleyis --------------------------------------------------------

    def _hukmu_uygula(self, no: int, hukum: str, lider_ad: str,
                      isci_ad: str) -> dict:
        eslesme = KARAR_DESENI.search(hukum or "")
        if not eslesme:
            # Liderin NE yazdigi kayda duser: hukumsuz kalan inceleme
            # sebebi gorulmeden duzeltilemez (28.09: gorulemedigi icin
            # codex'in mesaj birlestirme hatasi ayri bir kosu istedi).
            ozet = " ".join((hukum or "").split())[-400:] or "(bos)"
            return self._belirsiz(
                no, "Lider acik bir hukum yazmadi (KARAR satiri yok). "
                    f"Yazdiginin sonu: {ozet}")

        yon = eslesme.group(1).lower()
        gerekce = (eslesme.group(2) or "").strip()

        ders = DERS_DESENI.search(hukum or "")
        if ders and isci_ad:
            self.ofis.kadro.ders_yaz(isci_ad, ders.group(1).strip(), None)

        guncel = self.ofis.tahta.gorev(no)
        if yon == "kapat":
            # Kanit kapisi tahtada; lider onu atlatamaz, yalnizca tetikler.
            self.ofis.tahta.kapat(guncel["no"], guncel["revizyon"],
                                  kapatan=lider_ad)
            self.ofis.bellek.karar_yaz(
                f"#{no} kapatildi.",
                gerekce or "Kanitlar kabul olcutunu karsiliyor.",
                lider_ad, tur="genel", gorev_id=guncel["id"],
            )
            yazilan, reddedilen = self._bilgileri_yaz(no, hukum, lider_ad)
            return {"hukum": "kapat", "gerekce": gerekce, "gorev_no": no,
                    "ders": bool(ders), "bilgi": yazilan,
                    "bilgi_ret": reddedilen}

        if not gerekce:
            return self._belirsiz(
                no, "Geri gonderme gerekcesiz yazildi; ajan neyi "
                    "duzeltecegini bilemez.")
        self.ofis.tahta.geri_gonder(guncel["no"], guncel["revizyon"],
                                    gerekce=gerekce, gonderen=lider_ad)
        return {"hukum": "geri", "gerekce": gerekce, "gorev_no": no,
                "ders": bool(ders)}

    def _bilgileri_yaz(self, no: int, hukum: str, lider_ad: str) -> tuple:
        """`BILGI:` satirlarini hafizaya yazar -- YALNIZ is kapanirken.

        Geri gonderilen isin "bilgisi" dogrulanmamistir: kanit kapisindan
        gecmeyen bir isten cikan degeri butun ofise yaymak, yanlisi
        kaliciya cevirmek olurdu. Kapanan isin bilgisi kanitla desteklidir.

        Insanin yazdigi bilgiyi LIDER de devremez (`bellek.bilgi_ekle`);
        reddedilen yazma SESSIZ kalmaz, olay olur ve donuste soylenir.
        """
        from .bellek import BellekHatasi
        yazilan, reddedilen = [], []
        for m in list(BILGI_DESENI.finditer(hukum or ""))[:AZAMI_INCELEME_BILGI]:
            konu, icerik = m.group(1).strip(" `*"), m.group(2).strip(" `*")
            try:
                r = self.ofis.bellek.bilgi_ekle(konu, icerik, yazan=lider_ad,
                                                gorev_no=no)
                if r["durum"] != "ayni":
                    yazilan.append(r["konu"])
            except BellekHatasi as exc:
                reddedilen.append(konu)
                self.ofis.db.olay_yaz(
                    self.ofis.proje_id, "uyari",
                    f"#{no} incelemesinden bilgi yazilamadi: {exc}",
                    ajan_ad=lider_ad)
        return yazilan, reddedilen

    def _belirsiz(self, no: int, sebep: str) -> dict:
        """Hukum yoksa is INCELEMEDE BEKLER.

        Varsayilan olarak kapatmak, kanit kapisini arka kapidan acmak
        olurdu: bir sey ters gittiginde sistem "onayladi" der ve kimse
        onaylamamistir.
        """
        self.db.olay_yaz(self.proje_id, "uyari",
                         f"#{no} inceleme sonucsuz: {sebep}")
        return {"hukum": "belirsiz", "gerekce": sebep, "gorev_no": no,
                "ders": False}
