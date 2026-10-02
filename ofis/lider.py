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

#: Patrona giden metinde liderin kendi arac durumu anlatilmaz (01.10,
#: gercek set G07: 'komut calistirma aracim kapaliydi, calisiyor
#: gorunuyor'). Rapor turu ve inceleme taslagi AYNI kurali kullanir.
ARAC_SUSKUNLUGU = ("Kendi araclarindan, neyi calistiramadigindan SOZ ETME (bu tur bilerek aracsiz; dogrulama kanitta ve ofisin olcumunde). 'gorunuyor' deme: kanit ne diyorsa onu soyle.")

#: `PATRONA:` blogu: satirdan baslar, bir sonraki hukum satirina ya da
#: kod citine kadar surer.
#: `Not:` / `Inceleme notu:` ile baslayan satir da biter (01.10, patronun
#: ofis kopyasi): kural 7 "kapatirken kisaca not dus" diyor; lider notu
#: PATRONA'nin ALTINA yazdi ve patrona "karalama/yazi_bas.py, georgia.ttf,
#: cekirdek sayisi 5 degil 6" gibi inceleme ayrintisi gitti.
_PATRONA = re.compile(r"^[ \t]*PATRONA:[ \t]*(.*?)(?=^[ \t]*(?:KARAR|DERS|BILGI|Not|NOT|[İI]nceleme notu):|^```|\Z)",
                      re.M | re.S)


def patrona_ayikla(hukum: str) -> str:
    """Incelemenin `PATRONA:` metni (yoksa bos). Bicim satirlari ayiklanir."""
    m = _PATRONA.search(hukum or "")
    if not m:
        return ""
    metin = m.group(1).strip()
    return metin[:1500]

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


#: Web OZET araci (WebFetch, web aramasi) ham icerik degil OZET verir;
#: dogrudan olcumu curutemez. Inceleme ve danisma ayni sozu kullanir.
OZET_ARACI_KURALI = (
    "WEB OZETI OLCUM DEGILDIR: WebFetch / web aramasi sayfayi kucuk bir "
    "modelle OZETLER, yanilabilir ya da eski bilgi verebilir. Ajanin "
    "tarayicida ya da `curl` ile DOGRUDAN olctugu sayfa icerigini bu ozetle "
    "CURUTME. Celiski gorursen ham icerige kendin bak (`curl -s <adres>`); "
    "bakamiyorsan yalniz ozet yuzunden GERI GONDERME, suphe notu dus.")


def kisalt(metin: str, sinir: int) -> str:
    """Lidere giden metni kisaltir ve kisalttigini SOYLER.

    02.10.2026 OLCULDU: inceleme patrona giden mesaji 160 harfte SESSIZCE
    kesiyordu; lider "mesaj yarida kesilmis" deyip TAM mesaji geri
    gonderdi. Sessiz kesme, kanitta ve notta da ayni yanilgiyi dogurur."""
    metin = metin or ""
    if len(metin) <= sinir:
        return metin
    return metin[:sinir] + f" [... OFIS KISALTTI: tamami {len(metin)} harf]"


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
        # PATRONUN KENDI SOZU incelemede de (01.10.2026). Olculdu (gercek set
        # G07, claude): patron "yilan oyunu yap" dedi; plani yazan lider
        # olcute "oyun SURERKEN cekilmis ekran goruntusu" ekledi; basliksiz
        # tarayicida yilan hemen oldugu icin her goruntu "Oyun Bitti" cikti,
        # kod dogru oldugu halde is 5 kez geri gonderildi (825 sn).
        with self.db.baglanti() as _c:
            _ps = _c.execute("SELECT govde FROM olay WHERE proje_id = ? AND gorev_id = ? AND "
                             "tur = 'patron_sozu' ORDER BY rowid DESC LIMIT 1",
                             (self.proje_id, g["id"])).fetchone()
        if _ps and (_ps["govde"] or "").strip():
            satirlar += ["", f"**Patronun KENDI sozu:** \"{kisalt(_ps['govde'].strip(), 600)}\"",
                         "Olcutun, patronun ISTEMEDIGI bir kanit bicimini (orn. oyun "
                         "surerken ekran goruntusu, video) sart kosan kismi RET SEBEBI "
                         "DEGILDIR: is patronun istedigini yapiyorsa kapat, eksik "
                         "bicimi nota yaz."]
        # KARDES KOLLAR (01.10.2026). Olculdu (gercek set G08, codex): hedef
        # iki kola bolundu (sehirler / renkler); inceleyen sehirler kolunu
        # "ust hedef renkler.md'yi de istiyor" diye GERI GONDERDI, ajan
        # yanlis yonlenip dosyayi bozdu. Ust hedef ORTAK; her kol yalniz
        # kendi olcutuyle yargilanir.
        with self.db.baglanti() as _c:
            kardesler = _c.execute(
                "SELECT no, baslik, sahip, durum FROM gorev WHERE proje_id = ? AND "
                "ana_hedef = ? AND id != ? AND silindi = 0 ORDER BY no",
                (self.proje_id, g["ana_hedef"], g["id"])).fetchall()
        if kardesler:
            satirlar += ["", "**Bu is BOLUNMUS bir hedefin BIR KOLUDUR.** Ust hedefin "
                             "geri kalani BASKA kollarda:"]
            satirlar += [f"- #{k['no']} {k['baslik']} ({k['sahip'] or 'sahipsiz'}, {k['durum']})"
                         for k in kardesler[:8]]
            satirlar += ["YALNIZ bu kolun KABUL OLCUTUNU degerlendir; kardes kolun "
                         "isini bu koldan ISTEME, bu yuzden geri gonderme."]
        # PATRONUN NOTLARI isin tanimina EKTIR ve incelemeye girer. Girmeseydi
        # lider, patronun "dur, sunu degistir" dedigi isi "olcutten sapti"
        # diye geri gonderirdi. ULASMAYAN not ayrica soylenir: ajan onu hic
        # gormediyse ona uymamasi bir kusur degil, bir TESLIM eksigidir.
        notlar = gorev_notlari(self.db, self.proje_id, g["id"])
        if notlar:
            satirlar += ["", f"**Patronun bu ise notlari** ({NOT_KURALI}):"]
            for n in notlar:
                satirlar.append(
                    f"- {kisalt(n['govde'], 400)}"
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
                    satirlar.append(f"  ```\n  {kisalt(k['icerik'], 1500)}\n  ```")
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
        # PATRONA GONDERILENLER -- ofisin kaydi, ajanin sozu degil.
        # OLCULDU (30.09.2026, gercek set G01, codex): ajan ekran goruntusunu
        # `sohbete_yaz` ile gondermisti; lider "sohbete gonderildigine dair
        # kanit yok" deyip isi GERI GONDERDI, ajan goruntuyu ikinci kez
        # yolladi. Lider, olcutu karsilayan olguyu goremiyordu.
        try:
            with self.db.baglanti() as _c:
                _giden = [r["govde"] for r in _c.execute(
                    "SELECT govde FROM olay WHERE proje_id = ? AND gorev_id = ? "
                    "AND tur = 'ajan_sohbet' ORDER BY rowid", (self.proje_id, g["id"]))]
        except sqlite3.Error:
            _giden = None
        if _giden:
            from .ekler import ayikla as _ayikla
            satirlar += ["", "### Patronun sohbetine GONDERILENLER (ofisin kaydi)", ""]
            for _m in _giden[:6]:
                _metin, _yollar = _ayikla(_m)
                # KESME GORUNUR (02.10.2026 OLCULDU): mesaj 160 harfte sessizce
                # kesiliyordu; lider "mesaj '2) G' ile yarida kesilmis" deyip
                # TAM mesaji geri gonderdi. Ofis kisaltirsa bunu SOYLER.
                satirlar.append(f"- \"{kisalt(_metin, 1500)}\""
                                + (f" · ekler: {', '.join(_yollar)}" if _yollar else ""))
        satirlar += ["", "_Not: `.ofis/ekler/` klasoru her iste serbesttir; patrona "
                         "gosterilecek dosyanin oraya yazilmasi ihlal DEGILDIR. "
                         "`.ofis/karalama/` (yardimci betikler) da serbesttir, olculmez._"]
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
            # 30.09.2026, gercek set: dort gereksiz ret. Codex lideri pytest'i
            # salt okunur incelemede calistiramadi (gecici klasor yazilamiyor)
            # ve isi bu yuzden geri gonderdi; claude lideri "Cay" yerine
            # "Çay", "© 2024" yili ve bir harf hatasi icin geri gonderdi.
            # Her ret bir tur daha, bir mesaj daha ve patronun beklemesi.
            "6. SEN SALT OKUNURSUN: bir komut yazma gerektirdigi icin (pytest",
            "   gecici klasoru vb.) senin incelemende calismazsa bu AJANIN",
            "   hatasi DEGILDIR; ajanin kanitini ve ofisin disk olcumunu tart,",
            "   yalniz bu yuzden GERI GONDERME. Komutun senin tarafinda",
            "   CALISAMAMASI (izin / gecici klasor / 'No usable temporary",
            "   directory' hatasi) ajanin kanitiyla CELISKI DEGILDIR (madde 4",
            "   burada uygulanmaz); celiski ancak komut CALISIP FARKLI sonuc",
            "   verirse vardir.",
            # 02.10.2026 OLCULDU (sinama paneli, example.org): ajan tarayicida
            # ve curl ile "h1 yok" olctu (DOGRU); lider WebFetch ozetiyle "h1
            # var" deyip isi GERI GONDERDI ve ajanin sorusuna da ayni yanlisla
            # cevap verdi -- bir tur bosa gitti.
            "6b. " + OZET_ARACI_KURALI,
            "7. ANLAMI DEGISTIRMEYEN fark ret sebebi DEGILDIR: Turkce harf",
            "   (Cay/Çay), buyuk-kucuk harf, siralama, uslup, telif yili,",
            "   kucuk yazim hatasi. Olcut karsilaniyorsa KAPAT; istersen",
            "   kapatirken KARAR satirinin USTUNE kisaca not dus (not patrona",
            "   gitmez). Geri gondermek yalniz olcut",
            "   karsilanmiyorsa ya da bir sey BOZULDUYSA.",
            # 30.09 olculdu (G01, claude): goruntu ekler/'de hazirdi, ajan
            # sohbete gondermeyi unuttu, lider isi geri gonderdi. Raporda
            # ofis gitmemis dosyayi listeler, lider `[ek]` ile ekler.
            "8. Patrona gidecek dosya `.ofis/ekler/` altinda HAZIRSA, sirf ajan",
            "   `sohbete_yaz` cagirmadi diye GERI GONDERME: kapat; ofis",
            "   raporda gitmemis dosyayi sana gosterir, sen eklersin.",
            # 01.10 olculdu (G06, claude): "dosyanin kendisi olcutu
            # karsiliyor ama kanit iki maddeyi kapsamiyor" -> geri gonderdi.
            "9. Olcutu dosyayi / ciktiyi KENDIN okuyup dogruladiysan, sirf",
            "   ajanin kaniti eksik anlatti diye GERI GONDERME: kapat ve",
            "   neyi kendin gordugunu gerekceye yaz. Senin bagimsiz okuman,",
            "   ajanin anlatisindan GUCLU bir kanittir.",
            "",
            "### Hukmunu TAM OLARAK su bicimde yaz",
            "",
            "Kapatiyorsan:",
            "```",
            "KARAR: kapat",
            "PATRONA: <patrona gidecek 1-4 cumle: ne yapildi, SONUC ne",
            "(istenen sayi/fiyat/cevap burada), dosya varsa adi>",
            "```",
            "`PATRONA:` metni patrona DOGRUDAN gider: baslik, KANIT/DURUM satiri,",
            "ic konusma YAZMA; ilk cumle sonuc olsun. Is numarasi anlatma.",
            ARAC_SUSKUNLUGU,
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

        lider = (self.ofis.kadro.gorevin_lideri(gorev) if not lider_ad
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
                              ajan_ad=lider["ad"], butce_usd=butce_usd,
                              lider=True)
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
        # HUKUM SATIRI UNUTULDUYSA BIR KEZ SORULUR (01.10.2026). Olculdu
        # (gercek set G16): lider incelemeyi yazdi, sonuna `KARAR:` satirini
        # koymadi; is "inceleme sonucsuz" ile asili kaldi. Yeniden tam
        # inceleme pahali; liderin KENDI metni ona gosterilir, yalniz hukum
        # istenir (kisa, aracsiz tur). Yine yoksa eski yol: belirsiz.
        if hukum.strip() and not KARAR_DESENI.search(hukum):
            metin = ("Az once asagidaki incelemeyi yazdin ama HUKUM SATIRI YOK:\n\n---\n"
                     + hukum[-3000:] + "\n---\n\nYalnizca hukmunu yaz, baska hicbir sey yazma:\n"
                     "`KARAR: kapat` ve altinda `PATRONA: <1-4 cumle sonuc>`\n"
                     "ya da `KARAR: geri -- <ne eksik, somut>`")
            try:
                _b2, _ek2, parcalar2 = limitte_devret(
                    basamaklar, kostur,
                    devir=lambda eski, yeni: lider_devri(
                        self.ofis, lider, eski, yeni, gorev_id=gorev["id"]))
                ek_hukum = "".join(parcalar2)
                if KARAR_DESENI.search(ek_hukum):
                    hukum = hukum + "\n" + ek_hukum
                    self.db.olay_yaz(self.proje_id, "uyari",
                                     f"#{no} liderin hukum satiri eksikti; ayrica soruldu.",
                                     ajan_ad=lider["ad"], gorev_id=gorev["id"])
            except (ZincirBitti, MotorHatasi):
                pass
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
            # PATRONA TASLAGI (30.09.2026). Olculdu (gercek set, codex G01,
            # 120 sn): isin kendisi 25 sn, liderin ayri RAPOR turu 21 sn.
            # Kapatan inceleme sonucu zaten okumustur; patrona gidecek
            # metni ayni turda yazar, tek isli planda ayri rapor turu atlanir
            # (`sohbet._rapor`). Taslak yoksa eski yol aynen isler.
            taslak = patrona_ayikla(hukum)
            if taslak:
                self.db.olay_yaz(self.proje_id, "rapor_taslak", taslak,
                                 ajan_ad=lider_ad, gorev_id=guncel["id"])
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
