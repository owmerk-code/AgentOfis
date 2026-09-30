# -*- coding: utf-8 -*-
"""Orkestra: halkayi insan mudahalesi olmadan donduren parca.

Bugune kadar butun kapilar vardi ama KIMSE KAPIDAN GECMIYORDU: gorevi
insan aciyordu, kollari insan yaziyordu, isciyi insan kosturuyordu,
incelemeyi insan tetikliyordu. "Fan-out karari liderde" yazmistik ama
lideri karar vermeye iten hicbir sey yoktu. Eksik olan buydu:

    insan bir HEDEF yazar
        -> lider boler mi bolmez mi KARAR VERIR (gerekcesiyle)
        -> isciler ayrik alanlarda PARALEL kosar
        -> kanit uretir
        -> lider kanita karsi inceler
        -> kapatir ya da gerekceyle geri gonderir

Kararlar ve sebepleri:

* **Lider plani JSON verir, serbest metin degil.** Serbest metni ayristirmak
  modelin o gunku uslubuna bagimli olur -- kanit metin koprusunde tam bunu
  yasadik (bkz. mcp_sunucu.py). Bicim zorunlu olunca ya gelir ya gelmez;
  ikisi de kayittir.

* **Kapilar plani REDDEDER ve lidere SEBEBINI soyler.** Bir kez daha
  denenir. Sessizce duzeltmek, liderin yanlis ogrenmesi demektir: bir
  dahaki sefere de ayni hatayi yapar ve kimse fark etmez. Ret ogretir.

* **Paralellik kilide birakilir, ama GERCEKTEN paralel kosulur.**
  Orkestra "su ikisi paralel kossun" diye karar VERMEZ -- cakisan alan
  zaten `sahiplen` tarafindan reddedilir (Yasa 1), kural tek yerde kalir.
  Ama isler AYNI ANDA baslatilir.

  OLCULDU: once bloke calisiyordu. Uc ayrik is, her biri ~0.55 sn,
  toplam 1.64 sn surdu -- yani duvar saati islerin TOPLAMI'ydi, en
  uzunu degil. Kilit makinesi hic gercek cekisme gormemisti; "ayrik
  alan paralel calisiyor" dedigimiz sey yalnizca kilidin VERILEBILIR
  olmasiydi.

  Paralellik acilirken kapaliyken gorunmeyen sorunlar da acilir:

  1. **Ayni ajana iki is.** `_bosta_mi` veritabanini okur; iki iplik
     ayni bos ajani secebilir. Cozum: ATAMA once tek iplikte yapilir ve
     ajan bellekte REZERVE edilir, sonra kosulur. Onceden rezerve
     etmeseydik, ayni ajan iki isi ayni anda uzerine alirdi.
  2. **Ortak klasorde derleme cakismasi.** Yazma kilidi BEYAN EDILEN
     yollari korur; `dist/`, `node_modules/.cache`, `__pycache__` gibi
     uretilen ciktilar beyan edilmezse iki is ayni anda uzerine yazar.
     Cozum kodda degil PLANDA: lider, isin CALISTIRDIGI komutun
     dokundugu yerleri de yazma alanina yazar (bkz. plan_metni).
  3. **Bir kol duserse otekiler devam etmeli.** Her isin istisnasi
     kendi icinde toplanir; biri patlayinca digerleri iptal olmaz.
  4. **Butce N KAT hizli yanar.** Tur basina tavan aynidir ama ayni
     anda N tur kosar. Ozet bunu bildirir.
  5. **SQLite cekismesi.** `Veritabani` butun baglantilari tek kilitle
     sirali tutar (db.py) ve WAL acik; okuma yazani bloklamaz.

* **Bekleyen is ILERLEME SAYILMAZ.** Soru sormus ya da onay bekleyen ajan
  durdurulmustur, basarisiz degil. Dongu onu atlar ve insana bildirir.
  Kendi kendine cevap uydurup devam etseydi, `soru_sor` aracinin butun
  anlami giderdi.

* **Dongu ILERLEME YOKSA DURUR.** Ilerlemeyen bir donguyu dondurmeye devam
  etmek jeton yakar ve panelde "calisiyor" gorunur -- en pahali yanilgi.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

from . import baglayici, izin as izin_mod, kullanim, roller, sartname, tarayici, tavan
from .klasor import klasorleri_dogrula, metinler
from .koltuk import Koltuk, durdurma_istendi
from .danisma import Danisma
from .lider import Lider, LiderHatasi
from .motor import motor_ac, MotorHatasi
from .zincir import LIDER_ZINCIRI, basamaklari_kur, limitte_devret, lider_devri, tur_butcesi, ZincirBitti
from .tahta import KilitCakismasi, TahtaHatasi

#: Liderin plani. Kod blogu icinde ya da duz JSON kabul edilir.
JSON_BLOK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

#: Bir turda en fazla kac kol. Daha fazlasi bolme degil dagilmadir:
#: coklu ajan ~15x jeton yakar ve yalnizca genislik-oncelikli iste kazanir.
AZAMI_KOL = 6


class OrkestraHatasi(RuntimeError):
    pass


def _json_ayikla(metin: str):
    """Liderin cevabindan plani cikarir. Bulamazsa None -- uydurmaz."""
    eslesme = JSON_BLOK.search(metin or "")
    ham = eslesme.group(1) if eslesme else None
    if ham is None:
        bas = (metin or "").find("{")
        son = (metin or "").rfind("}")
        if bas == -1 or son <= bas:
            return None
        ham = metin[bas:son + 1]
    try:
        return json.loads(ham)
    except json.JSONDecodeError:
        return None


#: "Ajanlar kabinde" anahtari (ayar). Varsayilan KAPALI: kabinde insanin
#: oturumlari yasar; ajani oraya sokmak insanin bilerek verdigi bir yetki.
KABIN_IZLE_ANAHTARI = "kabin_izle"

#: Izleme kabini hangi ise verilsin: tarayici kullanacagi en belli olana.
#: Tahmin degil ONCELIK: eslesen yoksa kabin ilk ise verilir (kullanmazsa
#: zarar yok, bir sonraki turda baska ise gecer).
_TARAYICI_IPUCU = ("http", "site", "sayfa", "tarayici", "tarayıcı", "web",
                   "oyun", "tikla", "tıkla", "ekran", "form", "kabin", "url")


def kabin_izle_acik_mi(db, proje_id) -> bool:
    return (db.ayar_oku(proje_id, KABIN_IZLE_ANAHTARI, "kapali") or "") == "acik"


def _tarayici_puani(g: dict) -> int:
    metin = " ".join(str(g.get(k) or "") for k in
                     ("baslik", "ana_hedef", "neden", "govde")).lower()
    return sum(1 for i in _TARAYICI_IPUCU if i in metin)


def _kabin_ucnoktasi() -> str:
    """Kabin aciksa CDP ucnoktasi, degilse bos. OLCER, varsaymaz."""
    from . import kabin as _kab, tarayici as _tar
    return _tar.cdp_adresi() if _kab.acik_mi() else ""


class Orkestra:
    def __init__(self, ofis, *, motor_fabrikasi=motor_ac, zincir=None) -> None:
        self.ofis = ofis
        self.db = ofis.db
        self.proje_id = ofis.proje_id
        self.motor_fabrikasi = motor_fabrikasi
        # Koltuk ve lider KENDI fabrikamizla kurulur. `ofis.koltuk`i
        # kullansaydik motor secimi sessizce yok sayilirdi: orkestraya
        # verilen fabrika hicbir yere ulasmaz, her sey varsayilan motorla
        # kosardi. Sessizce yok sayilan ayar, ayar degildir.
        self.koltuk = Koltuk(ofis, motor_fabrikasi=motor_fabrikasi,
                             zincir=zincir)
        self.lider = Lider(ofis, motor_fabrikasi=motor_fabrikasi)
        self.danisma = Danisma(ofis, motor_fabrikasi=motor_fabrikasi)
        # Kabin ACIK mi, aciksa ucnoktasi. Degistirilebilir bir alan:
        # sinama gercek 9222'ye bakmasin (kullanicinin kabini acik olsa
        # sinamanin sonucu degisirdi).
        self.kabin_ucnoktasi = _kabin_ucnoktasi

    # -- 1. hedeften plana ---------------------------------------------------

    def plan_metni(self, hedef: str, kanat_id: str, hata: str = "",
                   *, ek_klasorler=None, atanan: str = "",
                   patron_sozu: str = "") -> str:
        """Lidere verilen planlama istegi.

        Kadro ISIMLERIYLE verilir: lider kimin ne yaptigini bilmeden
        atama yapamaz. Ayrica her ajanin turu (eller/kafa) yazar --
        kafa ajana dosya yazan is verilemez ve lider bunu bilmelidir.

        Ofis disi klasor acildiysa lider bunu GORMELI: gormeden plan
        yaparsa isi yanlis yere yazdirir. Ayni sebeple lidere gercek
        klasor duzeni de gosteriliyor (`_klasor_duzeni`) -- gormeden
        yol yazmak tahmindir ve ilk iste tam bu yuzden var olmayan bir
        klasor yazilmisti.
        """
        kadro = [a for a in self.ofis.kadro.liste()
                 if a["kanat_id"] == kanat_id and not a["lider_mi"]]
        satirlar = [
            "## HEDEF",
            "",
            hedef,
        ]
        if patron_sozu:
            # Izin YALNIZ patronun kendi sozunden cikar; lider onu
            # gormeden alinti yapamaz (hedef liderin yeniden yazimi
            # olabilir).
            satirlar += ["", "## PATRONUN KENDI SOZU (izin alintisi buradan, kelimesi kelimesine)",
                         "", patron_sozu]
        satirlar += [
            "",
        ]
        # KUNYE: bolen kisi "yapma" denen seyi bilmeli (bkz.
        # brifing.kunye_ozeti -- olculdu, lider hic gormuyordu).
        kunye = self.ofis.brifing.kunye_ozeti()
        if kunye:
            satirlar += [kunye, ""]
        if atanan:
            # TAKIM SOHBETI: patron isi `@ad is: ...` ile DOGRUDAN bir
            # ajana verdi. Kime -- patronun karari; nasil (olcut, yazma
            # alani, bolme) -- liderin. Kapi `_plani_dogrula`da.
            satirlar += [
                "## PATRON ISI KIME VERECEGINI SECTI",
                "",
                f"Patron bu isi dogrudan **{atanan}**'a verdi. BUTUN "
                f"kollarin `sahip` alani `{atanan}` OLMALI (birlestirme "
                "kolu dahil). Kabul olcutunu, yazma alanini ve bolup "
                "bolmemeyi SEN belirlersin; kimin yapacagini degil.",
                "",
            ]
        satirlar += ["## KADRON", ""]
        for a in kadro:
            yetki = ("dosya YAZAMAZ, yalnizca dusunur ve metin uretir"
                     if a["tur"] == "kafa" else "dosya yazar, komut kosturur")
            dersler = self.ofis.kadro.dersler(a["ad"])
            satir = f"- **{a['ad']}** ({a['meslek']}) — {yetki}"
            if dersler:
                satir += f" · gecmis notu: {dersler[0]['ders']}"
            satirlar.append(satir)
            # ROLUN OLCUT SABLONU LIDERE GOSTERILIR.
            #
            # Olculdu (21.09.2026): `olcut_sablonu` alani MAST %41,8
            # (belirtim hatasi) yuzunden eklenmisti -- Gemini adaptoru
            # kabul olcutunu TAM karsilayip yine de kurulamaz cikmisti.
            # Ama alan yalnizca ISCININ brifingine giriyordu; olcutu
            # YAZAN lider onu hic gormuyordu.
            #
            # Yani rolun en pahali alani, karari veren yere ulasmiyordu.
            # "Kapi, kendisine verilen olcutten iyi olamaz" -- o olcutu
            # yazan kisiye sablonu vermemek, kapiyi kor birakmakti.
            try:
                r = roller.rol(a["meslek"])
            except roller.RolHatasi:
                # YALNIZCA "bu meslek kutuphanede yok" hali yutulur --
                # eski bir kayit plani durdurmasin. Genis bir `except`
                # koysaydik bir ice aktarma hatasi da yutulur ve ozellik
                # SESSIZCE calismazdi (bu projenin 1 numarali hatasi).
                r = None
            if r is not None:
                if r.olcut_sablonu:
                    satirlar.append(
                        f"    bu rolde 'bitti' genellikle: {r.olcut_sablonu}")
                if r.kanit_turleri:
                    satirlar.append(
                        f"    uretebilecegi kanit: {', '.join(r.kanit_turleri)}")

        # BAGLAYICI ENVANTERI LIDERE GOSTERILIR.
        # Klasorde ayni dersi bir kez odedik: lider dosya duzenini
        # GORMEDEN yol yazmis ve var olmayan bir klasor uydurmustu.
        # Gormeden karar vermek tahmindir -- baglayicida da oyle.
        satirlar += ["", baglayici.lider_blogu()]

        # AJANLARIN NE YAPABILDIGI LIDERE SOYLENIR.
        #
        # OLCULDU (24.09.2026, gercek ofis, is #30): patron "semuparfum.com
        # sitemizi musteri gozuyle analiz et" dedi. Lider gorev metnine
        # "yalniz tarayiciyi kullan" yazdi ama isci tarayici ALMADI (alan
        # bostu, o zaman bos alan "tarayici yok" demekti). Uc kez "bende
        # tarayici yok" diye soruldu, patron "kullan" dedi, hicbir sey
        # degismedi. Artik tarayici her iste SERBEST; lider bunu bilmezse
        # yapilabilir bir isi "ajanin araci yok" diye insana havale eder.
        satirlar += [
            "",
            "## AJANLARININ ELINDEKILER",
            "",
            "Ajanlar terminaldeki Claude Code / Codex gibi calisir: web'de "
            "arar, sayfa okur, TARAYICIYI serbestce kullanir (her siteye "
            "gider, tiklar, form doldurur, sepet/odeme adimlarina bakar) ve "
            "komut kosturur. Yalniz riskli EYLEM (geri alinamaz / disari "
            "cikar / para) patrona sorulur. Bir isi 'ajanin araci yok' diye "
            "insana havale etme.",
            "",
            # 30.09 olculdu: "tarayiciyi ac ve youtube'a gir" -> lider
            # "varsayilan tarayiciyi ac" yazdi, ajan patronun Chrome'unu
            # acip masaustunu surdu.
            "Patron 'tarayiciyi ac', 'siteye gir' derse bu OFISIN "
            "tarayicisidir (panelde gorunen kabin ya da ajanin kendi "
            "tarayicisi). Hedefe 'varsayilan tarayici', 'Chrome'u ac' ya "
            "da 'masaustu ekran goruntusu' YAZMA; kanit sayfanin "
            "`browser_take_screenshot` goruntusudur.",
            "",
            # 30.09 olculdu (#36, "sitemizi ac, ekran goruntusu at"): olcut
            # "yeni sekmede acildi" ve "git status" istedi; kabin yeni sekmeyi
            # yasakliyor, git bu isle ilgisiz. Is iki kez geri gonderildi,
            # sohbete bes uzun mesaj dustu.
            "KABUL OLCUTU ISLE ORANTILI olsun: patronun istedigi sonucun "
            "kendisini olc (ornek: 'sayfanin ekran goruntusu sohbette'). "
            "Istenmeyen ara adim (yeni sekme, git durumu, dosya zamani) "
            "SART YAZMA. Paylasilan kabinde yeni sekme ACILMAZ; olcute "
            "sekme sarti yazma.",
            "",
            "`ekler/` klasoru HER ISTE SERBESTTIR (yazma alani gerekmez): patrona gosterilecek dosya oraya kaydedilir -- sayfa goruntusu icin `browser_take_screenshot` araci `filename: \"ekler/<ad>.png\"` ile -- ve `sohbete_yaz(ekler=[...])` ile gonderilir. Oradaki dosyayi SILME. Patrona dosya/goruntu gidecek iste 'dosya "
            "yazma' deme; `ekler/` yazma alanina girmez.",
            "",
            "`tarayici_alani` alanini NORMALDE YAZMA. Yalniz bir isi BILEREK "
            "birkac siteyle SINIRLAMAK istersen doldur; doldurursan ajan "
            "listede olmayan her site icin patrona sormak zorunda kalir.",
            "",
            "## TARAYICI VERILEN ISLERDE ONAY",
            "",
            "Tarayicisi olan bir isi alan ajan SERBESTCE gezer, arar, "
            "okur, TIKLAR ve form doldurur. Ofis yalnizca su uc sarttan "
            "birini tasiyan eylemi durdurup patrona sorar: **geri "
            "alinamaz** · **disariya cikar** · **para**.",
            "",
            "Bunun plandaki karsiligi: kabul olcutunu yazarken onay "
            "beklenecek bir adim varsa ONU AYRI bir adim yap. Ajan onay "
            "beklerken DURUR ve tur biter -- bu bir basarisizlik "
            "DEGILDIR, cevap gelince kaldigi yerden devam eder.",
        ]

        duzen = self._klasor_duzeni()
        if duzen:
            satirlar += [
                "",
                "## CALISMA KLASORU",
                "",
                "Ajanlar bu klasorde calisir. `yazma_alani` alanina",
                "BURADAKI GERCEK YOLLARI yaz -- uydurma, gordugunu yaz.",
                "",
                "```",
                duzen,
                "```",
            ]

        ekler = metinler(klasorleri_dogrula(ek_klasorler))
        if ekler:
            # Lider klasorun VARLIGINI bilmezse oraya gore plan yapamaz;
            # yazma alanini calisma kokune gore yazar ve isci yanlis
            # yere yazar. Mutlak yol veriliyor -- goreli yol baska bir
            # surecte baska bir yere cozulur (hayalet veritabani dersi).
            satirlar += [
                "",
                "## OFIS DISI KLASOR (patron acti)",
                "",
                "Patron su klasoru BU IS icin acti. Ajanlar buraya",
                "erisebilir; yollar MUTLAKTIR, oldugu gibi kullan:",
                "",
                "```",
            ] + ekler + [
                "```",
                "",
                "Is buradaysa `yazma_alani` alanina bu MUTLAK yolu yaz,",
                "calisma kokune gore goreli bir yol degil.",
                "Ne oldugunu bilmiyorsan TAHMIN ETME -- once baktir.",
            ]

        satirlar += [
            "",
            "## KARARIN",
            "",
            "Bu hedefi **bolecek misin, bolmeyecek misin?**",
            "",
            "Bolmek varsayilan DEGILDIR. Coklu ajan yaklasik 15 KAT jeton",
            "yakar ve yalnizca is gercekten bagimsiz kollara ayriliyorsa",
            "kazandirir. Kollar birbirini bekliyorsa ya da ayni dosyalara",
            "dokunuyorsa BOLME -- tek ajanda kostur.",
            "",
            "**Iki gorev ayni dosyalara yazamaz.** Yazma alanlarini ayrik",
            "bolmek zorundasin; cakisirsa plan reddedilir.",
            "",
            "**Yazma alanina URETILEN ciktilari da yaz.** Isler AYNI ANDA",
            "kosar. Bir is `npm run build` ya da derleme kosturuyorsa",
            "`dist/`, `public/` gibi uretilen klasorler de onun yazma",
            "alanidir. Beyan edilmeyen cikti kilitlenmez ve iki is ayni",
            "dosyanin uzerine ayni anda yazar -- kimse fark etmez.",
            "",
            "**Bolersen BIRLESTIRME kolu ekle.** Parcalar kendiliginden bir",
            "butun olmaz: birinin oturup parcalari birlestirmesi, uctan uca",
            "calistirmasi ve kanitlamasi gerekir. Bu kol otekileri BEKLER",
            "(`bekler` alani) ve kendi kabul olcutu uctan uca olmalidir.",
            "Tek kol aciyorsan birlestirmeye gerek yok.",
            "",
            "## CIKTI BICIMI",
            "",
            "Yalnizca su JSON'u ver, baska hicbir sey yazma:",
            "",
            "```json",
            "{",
            '  "bol": true,',
            '  "gerekce": "NEDEN boldun ya da bolmedin -- zorunlu",',
            '  "kollar": [',
            "    {",
            '      "baslik": "kisa is adi",',
            '      "sahip": "kadrodan bir ajan adi",',
            '      "neden": "bu is NICIN var",',
            '      "kabul_olcutu": "bittigini KANITLAYAN sey",',
            '      "govde": "ajana tarif",',
            '      "yazma_alani": ["klasor/yol"],',
            '      "zorluk": "kolay | orta | zor | cok_zor",',
            '      "zorluk_gerekce": "zor/cok_zor ise NEDEN -- zorunlu",',
            '      "bekler": []',
            "    }",
            "  ]" + (',' if patron_sozu else ''),
        ] + (['  "izinler": []'] if patron_sozu else []) + [
            "}",
            "```",
            "",
            "**ZORLUK her kola ayri yazilir.** Gerekli guc ISIN",
            "ozelligidir, kisinin degil -- ayni ajan kolay bir isi ucuz",
            "modelde, zor bir isi guclu modelde kosar.",
            "",
            "- `kolay` : kapali uclu, olcutu net, tek adim. Dosya sayma,",
            "  bicim duzeltme, bilinen bir deseni uygulama.",
            "- `orta`  : varsayilan. Cogu is buradadir.",
            "- `zor`   : gercekten YARGI gerektiren is -- belirsiz tasarim,",
            "  birden cok dosyayi etkileyen degisiklik, ince hata avi.",
            "- `cok_zor`: EN GUCLU model + en yuksek efor. SEYREK: mimari",
            "  karar, guvenlik, `zor`da iki kez basarisiz olmus is. Limiti",
            "  en hizli yiyen seviye budur.",
            "",
            "**`zor` ve `cok_zor` GEREKCE ISTER.** Guclu model pahalidir; her",
            "kola `zor` yazmak faturayi sessizce buyutur ve plan reddedilir.",
            "",
            "Kurallar:",
            "- `gerekce` bos olamaz; bolmemek de bir karardir ve gerekce ister.",
            "- Her kolda `neden` ve `kabul_olcutu` zorunlu. Kabul olcutu",
            "  olculebilir olmali: 'iyi olsun' degil, 'testler gecsin'.",
            "- Olcutu yazarken o ajanin ROLUNUN sablonunu TEMEL AL (yukarida",
            "  her ajanin altinda yaziyor) ve BU ISE gore somutlastir. Sablonu",
            "  gormezden gelip genel bir olcut yazmak, kapiyi kor birakir:",
            "  kanit kapisi kendisine verilen olcutten daha iyi olamaz.",
            f"- En fazla {AZAMI_KOL} kol.",
            "- Dosya yazmayan is icin `yazma_alani` bos dizi olmali.",
            "- `tarayici_alani` (istege bagli, cogu iste YAZMA): isi bilerek",
            "  birkac siteyle SINIRLAMAK icin adres listesi.",
            "- Dosya yazan isi YAZAMAZ olan ajana verme.",
            "- `bekler`: bu kolun beklemesi gereken kollarin SIRA NUMARASI",
            "  (0'dan baslar). Yalnizca KENDINDEN ONCEKI kollari bekleyebilir.",
            "- Birlestirme kolunu KENDINE de verebilirsin (`sahip` bos birak).",
            "  Ama o zaman inceleme insana duser: YAPAN INCELEYEMEZ.",
        ]
        if patron_sozu:
            satirlar += ["", izin_mod.plan_blogu()]
        if hata:
            satirlar += [
                "",
                "## ONCEKI PLANIN REDDEDILDI",
                "",
                hata,
                "",
                "Duzeltip yeniden ver.",
            ]
        return "\n".join(satirlar)

    def _klasor_duzeni(self, derinlik: int = 2) -> str:
        """Calisma klasorunun kisa agaci.

        OLCULDU -- ve is durdu: lider yazma alanini `calisma/demir` yazdi,
        yani BASKA BIR AJANIN klasorunu. Dosya sistemini hic gormemisti.
        Isci celiskiyi fark edip sordu (dogru davranis) ama bir tur bosa
        gitti. Gormeden yol yazmak, tahmin etmektir; lidere GORDUGU seyi
        veriyoruz.
        """
        from pathlib import Path as _P
        with self.db.baglanti() as conn:
            row = conn.execute("SELECT kok_klasor FROM proje WHERE id = ?",
                               (self.proje_id,)).fetchone()
        kok = _P((row["kok_klasor"] or "").strip()) if row else None
        if not kok or not kok.is_dir():
            return ""
        satirlar = []
        def gez(yol, seviye, onek=""):
            if seviye > derinlik or len(satirlar) > 60:
                return
            try:
                ogeler = sorted(yol.iterdir(), key=lambda x: (x.is_file(), x.name))
            except OSError:
                return
            for o in ogeler:
                if o.name.startswith((".", "__")):
                    continue
                satirlar.append(f"{onek}{o.name}{'/' if o.is_dir() else ''}")
                if o.is_dir():
                    gez(o, seviye + 1, onek + "  ")
        # KOKUN ADI YOLA GIRMEZ. Olculdu (26.09.2026, deneme D11): baslik
        # `calisma/  (calisma koku)` diye yaziliyordu ve lider yollari
        # `calisma/sayilar.py` diye yazdi -- iki denemede de. Yollar KOKUN
        # ICINDEN baslar; baslik bunu SOYLER, ogeler `./` ile gosterilir.
        satirlar.append(f"(kok: {kok.name} -- yollar BURADAN baslar; "
                        f"'{kok.name}/' yola YAZILMAZ)")
        gez(kok, 1, "  ./")
        if len(satirlar) == 1:
            satirlar.append("  (kok bos -- yeni dosyalar dogrudan ad ile: "
                            "'ornek.py')")
        return chr(10).join(satirlar[:60])

    def _plani_dogrula(self, plan, kanat_id: str, ek_klasorler=None,
                       atanan: str = "", patron_sozu: str = "",
                       son_sans: bool = False) -> str:
        """Plani kapilardan gecirir. Sorun varsa ANLATAN metin doner."""
        if not isinstance(plan, dict):
            return "Plan JSON olarak okunamadi."
        if not str(plan.get("gerekce") or "").strip():
            return ("`gerekce` bos. Bolmek de bolmemek de gerekce ister -- "
                    "alti ay sonra 'bunu neden boyle yapmistik' sorusunun "
                    "cevabi o satirdir.")
        # IZINLER patronun SOZUNE karsi dogrulanir (alinti + olumsuzluk
        # + sinif). Gecersiz izin plani reddeder: ret ogretir -- ama SON
        # DENEMEDE plani dusurmez (01.10.2026, gercek set G14: gecersiz tek
        # bir izin butun isi "Plan alinamadi" ile oldurdu). Son denemede izin
        # ATILIR, kayda gecer; bedeli o adimin patrona sorulmasidir.
        _, izin_hatasi = izin_mod.plan_izinleri(plan.get("izinler"),
                                                patron_sozu)
        if izin_hatasi and son_sans:
            self.db.olay_yaz(self.proje_id, "uyari",
                             f"Planin izinleri ATILDI (son deneme): {izin_hatasi}")
            plan["izinler"] = []
        elif izin_hatasi:
            return izin_hatasi
        kollar = plan.get("kollar")
        if not isinstance(kollar, list) or not kollar:
            return "`kollar` bos. En az bir kol gerekli."
        if len(kollar) > AZAMI_KOL:
            return f"{len(kollar)} kol cok. En fazla {AZAMI_KOL} olmali."

        adlar = {a["ad"]: a for a in self.ofis.kadro.liste()}
        for kol in kollar:
            if not isinstance(kol, dict):
                return "Her kol bir JSON nesnesi olmali."
            for alan in ("baslik", "neden", "kabul_olcutu"):
                if not str(kol.get(alan) or "").strip():
                    return (f"Bir kolda `{alan}` bos. Belirtim eksikligi "
                            "olculmus en buyuk hata kumesidir (%41,8): gorev "
                            "nicin var oldugunu tasimazsa ajan isi kusursuz "
                            "yapip hedefi iskalar.")
            sahip = str(kol.get("sahip") or "").strip()
            if atanan and sahip != atanan:
                # Patronun secimi SESSIZCE degistirilemez: lider baska
                # birini daha uygun buluyorsa bunu patrona soyler, planla
                # ustune yazmaz. (Bos sahip = lider yapar; o da degil.)
                return (f"Patron bu isi {atanan}'a verdi; bir kolun sahibi "
                        f"'{sahip or 'bos (lider)'}'. Butun kollar "
                        f"`\"sahip\": \"{atanan}\"` olmali.")
            if sahip:
                ajan = adlar.get(sahip)
                if ajan is None:
                    return (f"'{sahip}' diye bir ajan yok. Kadrodan bir ad sec.")
                if ajan["lider_mi"]:
                    return (f"'{sahip}' lider. Lider inceler, isi isci yapar.")
                alan = [y for y in (kol.get("yazma_alani") or []) if str(y).strip()]
                if ajan["tur"] == "kafa" and alan:
                    return (f"'{sahip}' YAZAMAZ ama ona dosya yazan bir is "
                            f"verdin ({', '.join(alan)}). Bu isi 'eller' bir "
                            "ajana ver ya da yazma alanini bosalt.")
        for sira, kol in enumerate(kollar):
            bekler = kol.get("bekler") or []
            if not isinstance(bekler, list):
                return "`bekler` bir sayi listesi olmali."
            for b in bekler:
                if not isinstance(b, int) or b < 0 or b >= len(kollar):
                    return f"`bekler` icinde gecersiz sira numarasi: {b!r}"
                if b >= sira:
                    return (f"{sira}. kol kendinden SONRAKI bir kolu ({b}) "
                            "bekleyemez. Dongu olur ve hicbir is asla "
                            "hazir olmaz.")
        try:
            self.lider.kollari_dogrula(kollar)
        except LiderHatasi as exc:
            return str(exc)

        # YAZMA ALANI KAPISI PLANDA DA KOSAR.
        #
        # Olculmus hata (21.09.2026): kapi yalniz `tahta.gorev_ac`ta
        # vardi, yani plan kapilarindan SONRA -- ve oradan atilan
        # istisna "ret ogretir" dongusunun DISINDA kaliyordu. Sonuc:
        # `kabuk konus` bir Python traceback'iyle coktu, lider sebebi
        # hic ogrenmedi, patron ham yigin izi gordu.
        #
        # Ofisin kendi kurali bunu zaten yaziyordu: *"Ayrik alan kapisi
        # PLANLAMADA. `sahiplen` de yakalar ama orada is dagitilmis,
        # brifingler uretilmistir. Erken ret ucuz."* Ayni cumle bu kapi
        # icin de gecerli; yeni bir kapi yazarken onu dongue baglamayi
        # unutmak, kapinin ogretme gucunu kaybettiriyor.
        #
        # `gorev_ac`taki kapi KALIYOR: iki bagimsiz kapi, biri
        # kaldirilsa oteki tutar (`Ekip.reddet` / `bellek.karar_yaz`
        # ikilisinde olculen desen).
        for kol in kollar:
            # TARAYICI ALANI da planda dogrulanir: bozuk bir adres
            # `gorev_ac`ta patlasaydi ret ogretme dongusunun DISINDA
            # kalirdi (yazma alani kapisinda bir kez odendi).
            web = kol.get("tarayici_alani") or []
            if not isinstance(web, list):
                return ("`tarayici_alani` bir adres LISTESI olmali "
                        "(ornek: [\"https://alan.adi\"]).")
            try:
                tarayici.kaynaklari_dogrula(
                    [str(w) for w in web if str(w).strip()])
            except tarayici.TarayiciHatasi as exc:
                return f"`tarayici_alani` gecersiz: {exc}"
            alan = [str(y).strip() for y in (kol.get("yazma_alani") or [])
                    if str(y).strip()]
            if not alan:
                continue
            try:
                self.ofis.tahta._alanlari_dogrula(alan, ek_klasorler)
            except TahtaHatasi as exc:
                return str(exc)
        return ""

    def hedef_ver(self, hedef: str, *, lider_ad: str = "", kanat_id: str = None,
                  butce_usd: float = None, zaman_asimi: float = None,
                  deneme: int = 2, ek_klasorler=None,
                  tarayici_alani=None, tarayici_yazma: bool = True,
                  baglayicilar=None, tarayici_kabin: bool = False,
                  sartname_denetimi: bool = False, atanan: str = "",
                  patron_sozu: str = "") -> dict:
        """Lideri TEMIZ oturumda acar, bolme kararini ALDIRIR, gorevleri acar.

        Oturum kimligi verilmez: her planlama kendi temiz kafasiyla yapilir
        (Yasa 4). Liderin onceki islerden birikmis baglami plana tasinmaz.
        """
        hedef = (hedef or "").strip()
        if not hedef:
            raise OrkestraHatasi("Bos hedef verilemez.")

        lider = self._lider_sec(lider_ad, kanat_id)
        kanat_id = kanat_id if kanat_id is not None else lider["kanat_id"]

        hata = ""
        for sira in range(max(1, deneme)):
            metin = self.plan_metni(hedef, kanat_id, hata,
                                    ek_klasorler=ek_klasorler, atanan=atanan,
                                    patron_sozu=patron_sozu)
            cevap = self._lideri_kostur(lider, metin, butce_usd, zaman_asimi)
            plan = _json_ayikla(cevap)
            hata = self._plani_dogrula(plan, kanat_id, ek_klasorler,
                                       atanan=atanan, patron_sozu=patron_sozu,
                                       son_sans=(sira == max(1, deneme) - 1))
            # KAPI GOREV BASINA BIR KEZ KOSAR, deneme basina degil.
            #
            # Olculdu (21.09.2026): tek bir sartname turu 46.773 jeton /
            # **$0,5571** tuttu -- haftalik $5 payin %11'i. Tasarlarken
            # "plan JSON'u kucuk, kisa tur" demistim; YANLISTI, cunku
            # kapiya gercek bir klasor ve okuma araclari verdim ve o da
            # kod tabanini gezdi (7 arac cagrisi).
            #
            # Gezmesi BOSUNA DEGILDI: bulgusu gercek dosya adlari
            # icerdi. Ama ayni hedefte IKINCI bir $0,56'lik tur kotu
            # degis tokus -- lider bulgulari zaten aldi. Bir kez
            # ogretir, sonra plan kendi kapilariyla ilerler.
            if not hata and sartname_denetimi and sira == 0:
                # SARTNAME KAPISI -- mekanik kapilar gectikten SONRA.
                # Once ucuz/kesin olanlar (gerekce var mi, alanlar
                # ayrik mi), sonra pahali/yargisal olan. Ters sirada
                # bozuk bir plan icin kapi modeli parasi odenirdi.
                hata = sartname.denetle(
                    self.ofis, hedef, plan, lider_ad=lider["ad"],
                    motor_fabrikasi=self.motor_fabrikasi,
                    tavan_usd=butce_usd or 0.0,
                    klasor=lider.get("klasor") or "",
                    # SON DENEMEDE kilitlemez: bulgular kayda gecer,
                    # is yurur. Sonsuza kadar reddedebilen bir YARGI
                    # kapisi, tek bir modelin fikrinin ofisi
                    # kilitlemesi demektir.
                    klasor_duzeni=self._klasor_duzeni(),
                    son_sans=(sira == max(1, deneme) - 1))
            if not hata:
                break
            # Ret OGRETIR: lider neyi yanlis yaptigini gorur ve duzeltir.
            self.db.olay_yaz(
                self.proje_id, "uyari",
                f"Plan reddedildi ({sira + 1}. deneme): {hata}",
                ajan_ad=lider["ad"])
        else:
            raise OrkestraHatasi(
                f"Lider gecerli bir plan veremedi. Son sebep: {hata}")

        acilan = self.lider.dagit(
            hedef, plan["kollar"], gerekce=plan["gerekce"],
            lider_ad=lider["ad"], kanat_id=kanat_id,
            ek_klasorler=ek_klasorler, tarayici_alani=tarayici_alani,
            tarayici_yazma=tarayici_yazma, baglayicilar=baglayicilar,
            tarayici_kabin=tarayici_kabin)

        # Birlestirme kolu otekileri BEKLER. Bagimlilik plan aninda sira
        # numarasiyla verilir (gorev numaralari henuz yok), burada gercek
        # numaraya cevrilir. Tahta donguyu zaten reddeder.
        for sira, kol in enumerate(plan["kollar"]):
            for b in (kol.get("bekler") or []):
                try:
                    self.ofis.tahta.bagimlilik_ekle(
                        acilan[sira]["no"], acilan[int(b)]["no"])
                except TahtaHatasi as exc:
                    self.db.olay_yaz(
                        self.proje_id, "uyari",
                        f"Bagimlilik kurulamadi #{acilan[sira]['no']} -> "
                        f"#{acilan[int(b)]['no']}: {exc}", ajan_ad=lider["ad"])
        acilan = [self.ofis.tahta.gorev(g["no"]) for g in acilan]

        # PATRONUN IZINLERI her kola yazilir: patron hedefin tamami icin
        # "pushla" dedi. Lider KAYNAK degildir -- izin patronun sozunden
        # gelir, alintisiyla birlikte kayda gecer ve kartta gorunur.
        izinler, _ = izin_mod.plan_izinleri(plan.get("izinler"), patron_sozu)
        # PATRONUN SOZU ISE YAZILIR (01.10.2026). Olculdu (gercek set G14,
        # codex): patron "formu doldur ve GONDER" dedi; lider izin yazmadi
        # (kapi o tiklamayi zaten sormuyordu), ajan patronun sozunu hic
        # gormedigi icin `onay_iste` ile kart acti ve is durdu. Ajan
        # brifinginde patronun KENDI cumlesini gorur (brifing K4).
        if patron_sozu:
            for g in acilan:
                self.db.olay_yaz(self.proje_id, "patron_sozu", patron_sozu[:1500],
                                 ajan_ad="insan", gorev_id=g["id"])
        verilen = []
        for iz in izinler:
            for g in acilan:
                try:
                    izin_mod.tanimla(self.db, self.proje_id, desen=iz["desen"],
                                     alinti=iz["alinti"], kaynak="patron_sozu",
                                     veren="insan", gorev_id=g["id"])
                except izin_mod.IzinHatasi as exc:
                    self.db.olay_yaz(self.proje_id, "uyari",
                                     f"Izin yazilamadi ({iz['desen']}): {exc}",
                                     ajan_ad=lider["ad"], gorev_id=g["id"])
                    continue
            verilen.append(iz["desen"])
        return {"hedef": hedef, "bol": len(acilan) > 1,
                "gerekce": plan["gerekce"], "gorevler": acilan,
                "lider": lider["ad"], "izinler": verilen}

    def _lider_sec(self, lider_ad: str, kanat_id) -> dict:
        """Hedefi kim dagitacak.

        Tek lider varsa SORULMAZ -- "hedef ver" demek icin once kanat
        kimligi ogrenmek zorunda kalmak, kullanimi kagit uzerinde birakir.
        Birden fazla lider varsa TAHMIN EDILMEZ: yanlis kanada dagitilan
        hedef, yanlis kadroya yanlis isi verir.
        """
        if lider_ad:
            return self.ofis.kadro.ajan(lider_ad)
        if kanat_id is not None:
            return self.ofis.kadro.lider(kanat_id)
        liderler = [a for a in self.ofis.kadro.liste() if a["lider_mi"]]
        if not liderler:
            raise OrkestraHatasi(
                "Bu ofiste lider yok. Hedefi dagitacak birine ihtiyac var.")
        if len(liderler) > 1:
            adlar = ", ".join(a["ad"] for a in liderler)
            raise OrkestraHatasi(
                f"Birden fazla lider var ({adlar}). Hangi kanada hedef "
                "verdigini soyle -- yanlis kanada dagitilan hedef, yanlis "
                "kadroya yanlis isi verir.")
        return liderler[0]

    def _lideri_kostur(self, lider: dict, metin: str, butce_usd, zaman_asimi,
                       ek_klasorler=(), akis=None) -> str:
        """Lider turu -- NOBET ZINCIRIYLE (bkz. `zincir.LIDER_ZINCIRI`).

        Claude limiti dolunca lider durmaz: AYNI istem codex'te (rolun
        kademesi, bugun gpt-6-sol) kosar. Lider turu temiz oturumdur ve
        baglamini defterden alir, yani devirde kaybolan bir sey yoktur.

        `akis` verilirse her metin parcasi ONA da gider (panelde cevabin
        yazilirken akmasi). Yeni basamakta `akis(None)` = bastan: devredilen
        turun yarim metni yenisinin basina yapismasin. Akis bir GOSTERIMDIR;
        onun hatasi lider turunu durdurmaz (asagida).
        """
        basamaklar, uyarilar = basamaklari_kur(
            self.db, self.proje_id, lider, fabrika=self.motor_fabrikasi,
            zincir=LIDER_ZINCIRI, butce_usd=butce_usd,
            kademe_haritasi=roller.kademe_haritasi(self.db, self.proje_id),
            rol="lider")
        # Koltukta gorunur olan uyarilar liderde YUTULUYORDU: cozulemeyen
        # bir hesap lider zincirinden sessizce dusuyordu.
        for u in uyarilar:
            self.db.olay_yaz(self.proje_id, "uyari", u, ajan_ad=lider["ad"])

        akis_durdu = {"hata": ""}

        def _akit(parca):
            # Gosterim, karari DEGISTIRMEZ: panelin akisini yazamamak (defter
            # mesgul, disk dolu...) lider turunu oldurmemeli. Ama SESSIZ de
            # kalmaz: ilk hatada akis kapanir ve bu bir kez yazilir.
            if akis is None or akis_durdu["hata"]:
                return
            try:
                akis(parca)
            except Exception as exc:          # noqa: BLE001 -- yalniz gosterim
                akis_durdu["hata"] = str(exc) or type(exc).__name__
                self.db.olay_yaz(self.proje_id, "uyari",
                                 "Liderin cevabi panele akitilamadi (cevap yine "
                                 "gelecek): " + akis_durdu["hata"][:200],
                                 ajan_ad=lider["ad"])

        def kostur(b):
            from .motor.tui import kipe_gore
            # GERCEK TERMINAL KIPI liderde de (29.09): her tur TEMIZ bir
            # terminal (oturum yok), panoda liderin son terminali gorunur.
            motor = kipe_gore(self.db, self.proje_id,
                              self.motor_fabrikasi(b["motor"]),
                              ajan_ad=lider["ad"], butce_usd=butce_usd)
            parcalar, ek, yedek = [], {}, []
            # Butce, DESTEKLEYEN motora verilir. Desteklemeyen motor (codex)
            # butce gelince turu hic baslatmadan reddeder -- para kontrolleri
            # kapali kalarak basarisiz olur. Burada filtrelemeseydik
            # `hedef --butce 0.5` bir codex liderde planlamayi oldururdu:
            # kullanicinin istedigi tavan, isi hic yapilmamis kilardi.
            motor_butcesi = tur_butcesi(b, motor, butce_usd)
            fren = tavan.KacakFreni()
            _akit(None)
            for olay in motor.tur_kos(
                metin, klasor=lider["klasor"], oturum_id="",
                model=b["model"],
                efor=roller.tur_eforu(self.db, self.proje_id, lider["efor"]),
                yazabilir=False,          # planlama dosya yazmaz
                # Lider BAKABILMELI: "su klasorde ne var" sorusunu
                # cevaplamak icin isi dagitmasi gerekmesin. Tur zaten
                # salt okunur, yani acilan klasor de salt okunurdur.
                ek_klasorler=tuple(ek_klasorler or ()),
                butce_usd=motor_butcesi, zaman_asimi=zaman_asimi,
                ek_ortam=b.get("ortam") or None,
            ):
                kesildi = tavan.lider_freni(
                    self.db, self.proje_id, fren, olay, ajan_ad=lider["ad"],
                    motor=b["motor"], hesap=b.get("hesap") or "", yol="lider")
                if kesildi:
                    return kesildi, []
                if olay.tur == "metin":
                    parcalar.append(olay.govde)
                    _akit(olay.govde)
                elif olay.tur == "arac":
                    # CEVAP, SON ARACTAN SONRA yazilandir (30.09.2026).
                    # Olculdu (gercek set G01): rapor "Once dosyanin var
                    # olup olmadigina bakiyorum." diye basladi -- aractan
                    # ONCEKI ara cumle cevaba yapismisti. Aractan once
                    # yazilan anlatimdir; yedek olarak saklanir (lider
                    # cevabi yazip SONRA bir arac cagirip susarsa kaybolmasin).
                    if parcalar:
                        yedek[:] = parcalar
                    parcalar = []
                    _akit(None)
                elif olay.tur == "hata":
                    # LIDER TURUNUN HATASI DA DEFTERE (30.09.2026). Olculdu
                    # (gercek set G06, claude): lider turu 11 sn'de dustu,
                    # defterde yalniz "basarili: false" vardi -- NEDENI hicbir
                    # yerde yoktu. Isci turunda hata yaziliyordu, liderde degil.
                    self.db.olay_yaz(self.proje_id, "hata",
                                     f"Lider turu: {str(olay.govde or '')[:600]}",
                                     ajan_ad=lider["ad"])
                elif olay.tur == "bitti":
                    ek = dict(olay.ek or {})
                    # LIDER TURU DA OLCULUR -- devredilen basamak dahil:
                    # limite carpan tur da bir harcamadir.
                    kullanim.tur_ozeti_yaz(
                        self.db, self.proje_id, ek, ajan_ad=lider["ad"],
                        motor=b["motor"], hesap=b.get("hesap") or "",
                        yol="lider")
            return ek, (parcalar or yedek)

        try:
            _b, ek, parcalar = limitte_devret(
                basamaklar, kostur,
                devir=lambda eski, yeni: lider_devri(self.ofis, lider, eski, yeni))
        except ZincirBitti as exc:
            raise OrkestraHatasi(str(exc)) from exc
        except MotorHatasi as exc:
            raise OrkestraHatasi(f"Lider motoru baslamadi: {exc}") from exc
        if not ek.get("basarili") and not parcalar:
            raise OrkestraHatasi("Lider planlama turu basarisiz oldu.")
        return "".join(parcalar)

    # -- 2. halkayi dondur ---------------------------------------------------

    def _bosta_mi(self, ajan_ad: str, haric_no: int = None) -> bool:
        """Ajan yeni bir ise girebilir mi.

        `haric_no` SORULAN gorevdir ve mesguliyet sayimina katilmaz.
        OLCULDU -- ve kilitlenme uretiyordu: soru sorup cevap alan bir
        ajan, kendi yarim isini surdurmek isterken "mesgul" sayiliyordu.
        Mesgul oldugu is, tam da surdurmesi gereken isti; dongu sonsuza
        kadar "ilerleme yok" diyordu. Bir ajan KENDI isine gore mesgul
        sayilmaz.
        """
        if self.ofis.postane.bekliyor_mu(ajan_ad)["bekliyor"]:
            return False
        return not [g for g in self.ofis.tahta.liste()
                    if g["sahip"] == ajan_ad
                    and g["no"] != haric_no
                    and g["durum"] in ("calisiyor", "inceleme")]

    def _kaynak_yuzunden_birakan(self, gorev: dict) -> str:
        """Isi KAYNAK TUKENMESI yuzunden birakan onceki sahip.

        Sebep listesi `Koltuk.KAYNAK_SEBEPLERI`den ODUNC alinir, burada
        yeniden yazilmaz: bu projede iki kopyadan biri duzeltilip oteki
        unutuldugu icin bes kez hata cikti. Devam kararini veren yer ile
        sahip secen yer AYNI tanimi kullanmali -- yoksa biri "devam
        edilebilir" der, oteki baska ajan secer ve devam hic olmaz.
        """
        # SAHIP `sahiplenildi`den okunur, `birakildi`dan DEGIL.
        # Iki katman `birakildi` yaziyor: `tahta.birak` ajan adi
        # OLMADAN, `koltuk` ajan adiyla. Birakma olayina dayansaydik
        # kimin biraktigi HANGI KATMANIN birak dedigine bagli olurdu --
        # ve ilk surumum tam bu yuzden sessizce bos donuyordu (sinama
        # yakaladi). `sahiplenildi`yi her zaman tahta yazar ve adi hep
        # doludur.
        with self.db.baglanti() as conn:
            sahiplenme = conn.execute(
                "SELECT ajan_ad FROM olay WHERE proje_id = ? AND gorev_id = ? "
                "AND tur = 'sahiplenildi' AND ajan_ad <> '' "
                "ORDER BY olusturuldu DESC, rowid DESC LIMIT 1",
                (self.proje_id, gorev["id"])).fetchone()
            birakma = conn.execute(
                "SELECT govde FROM olay WHERE proje_id = ? AND gorev_id = ? "
                "AND tur = 'birakildi' ORDER BY olusturuldu DESC, rowid DESC "
                "LIMIT 1", (self.proje_id, gorev["id"])).fetchone()
        if not sahiplenme or not birakma:
            return ""
        sebep = (birakma["govde"] or "").lower()
        if not any(k in sebep for k in Koltuk.KAYNAK_SEBEPLERI):
            return ""
        return sahiplenme["ajan_ad"] or ""

    def _uygun_ajan(self, gorev: dict, rezerve: set = frozenset()) -> str:
        """Bu isi kim yapmali. Lider atadiysa o; atamadiysa uygun bosta olan.

        'Uygun' iki seydir: ayni kanat ve yazma yetkisi. Meslek eslesmesi
        BURADA tahmin edilmez -- lider atamayi plana yazar, orkestra
        akilli davranmaya calisip liderin isini elinden almaz.
        """
        # `rezerve`: bu tikta zaten bir ise atanmis ajanlar. Veritabani
        # henuz "mesgul" demiyor cunku is daha BASLAMADI; rezerve olmasa
        # ayni ajan iki isi ayni anda uzerine alirdi.
        if (gorev["sahip"] and gorev["sahip"] not in rezerve
                and self._bosta_mi(gorev["sahip"], gorev["no"])):
            return gorev["sahip"]

        # KAYNAK TUKENMESIYLE BIRAKILAN IS, ONCE ESKI SAHIBINE.
        #
        # Olculdu (21.09.2026) ve bedeli $0,68'di: kilavuz isi butce
        # tavaninda kesildi, `birak` sahibi bosaltti, bir sonraki tik
        # bostaki BASKA bir ajani secti (cinar -> bilge) ve yeni ajan
        # isi SIFIRDAN kosmak zorunda kaldi -- 1,15M jetonluk baglam
        # cope gitti.
        #
        # Ofis "kesilen tur bastan kosmasin" duzeltmesini zaten yapmisti
        # ama o, oturumun AYNI ajanda olmasina dayaniyor: oturum kimligi
        # ajan+gorev ciftine ait. Yani duzeltme yalnizca isi ayni ajan
        # geri alirsa calisiyordu, ve onu garanti eden hicbir sey yoktu.
        #
        # Ayrimi yapan sey yine SEBEP: kaynak tukenmesi bir hata
        # degildir, is dogru gidiyordu ve baglam degerlidir. GERCEK bir
        # hatadan sonra tercih YAPILMAZ -- orada temiz baslangic dogru
        # ve baska bir ajan belki daha iyi sonuc verir.
        onceki = self._kaynak_yuzunden_birakan(gorev)
        if onceki and onceki not in rezerve and self._bosta_mi(onceki, gorev["no"]):
            for a in self.ofis.kadro.liste(gorev["kanat_id"]):
                if a["ad"] != onceki:
                    continue
                if a["lider_mi"] or a["faz"] == "basarisiz" or not a["klasor"]:
                    break
                if gorev["yazma_alani"] and a["tur"] == "kafa":
                    break
                return onceki

        for a in self.ofis.kadro.liste(gorev["kanat_id"]):
            if a["lider_mi"] or a["faz"] == "basarisiz" or not a["klasor"]:
                continue
            if a["ad"] in rezerve:
                continue
            if gorev["yazma_alani"] and a["tur"] == "kafa":
                continue
            if self._bosta_mi(a["ad"], gorev["no"]):
                return a["ad"]
        return ""

    def tik(self, *, butce_usd: float = None, zaman_asimi: float = None,
            izinli_araclar: tuple = (), paralel: int = 3,
            tarayici_gorunur: bool = False,
            tarayici_profili: str = "",
            tarayici_kabini: str = "") -> dict:
        """Halkanin bir adimi. Ne yapildigini anlatan ozet doner.

        Sira onemli: ONCE inceleme (biten isi kapat, yeri ac), SONRA yeni
        is baslat. Tersi olsaydi tahta incelenmemis islerle dolar ve lider
        hep geride kalirdi.
        """
        ozet = {"incelenen": [], "baslatilan": [], "bekleyen": [],
                "engel": [], "danisilan": [], "ilerleme": False, "paralel": 1}
        self.ofis.tahta.kilit_dusenleri_temizle()
        # LIMITLER TAZE OLSUN (27.09.2026): onceden gecis zinciri kurarken
        # hesabin yuzdesine bakar; insan CLI'i elle kullandiysa tur sonu
        # olcumu bayattir. Seyreltilmis (2 dk), kota harcamaz, patlarsa
        # halkayi durdurmaz.
        try:
            from . import kullanim
            kullanim.tazele(self.ofis.db, self.ofis.proje_id,
                            fabrika=self.motor_fabrikasi)
        except Exception:        # noqa: BLE001 -- olcum isi durdurmaz
            pass

        # a) incelemedekileri lidere incelet -- PARALEL (30.09.2026).
        #
        # Olculdu (gercek set G08, codex): iki is 67. ve 74. saniyede
        # bitti, incelemeleri 21 + 22 sn ARKA ARKAYA kostu. Incelemeler
        # birbirinden bagimsizdir (her biri kendi isinin kanitina bakar,
        # kapatma CAS'li); isciler gibi paralel kosar, en fazla `paralel`.
        incelenecek = self.ofis.tahta.liste(durum="inceleme")

        def _incele(g):
            try:
                return g, self.lider.incele(
                    g["no"], butce_usd=butce_usd, zaman_asimi=zaman_asimi), None
            except LiderHatasi as exc:
                return g, None, exc

        if len(incelenecek) > 1 and paralel > 1:
            from concurrent.futures import ThreadPoolExecutor as _Havuz
            with _Havuz(max_workers=min(paralel, len(incelenecek))) as havuz:
                sonuclar = list(havuz.map(_incele, incelenecek))
        else:
            sonuclar = [_incele(g) for g in incelenecek]
        for g, sonuc, hata in sonuclar:
            if hata is not None:
                ozet["engel"].append(f"#{g['no']} incelenemedi: {hata}")
                continue
            ozet["incelenen"].append({"no": g["no"], **sonuc})
            if sonuc["hukum"] != "belirsiz":
                ozet["ilerleme"] = True

        # b) AJANA sorulan sorulari TESLIM ET -- bu bir ILERLEMEDIR.
        #
        # Onceden butun bekleyen sorular ayrimsiz "insan cevabi bekleniyor"
        # sayiliyordu. Oysa `soru_sor` aracinin varsayilan alicisi LIDER,
        # yani bir ajan. Lidere sorulan soru kimseye ulasmiyor, insanin
        # kuyruguna dusup orada duruyordu: ofis, liderin cevaplamasi
        # gereken seyi sessizce insana havale ediyordu.
        for d in self.danisma.bekleyenleri_cevapla(butce_usd=butce_usd,
                                                   zaman_asimi=zaman_asimi):
            if d["durum"] == "cevaplandi":
                ozet["danisilan"].append(d)
                # Soran ajan artik beklemiyor: donguyu ilerletmeyi
                # HAK ETTI. Ilerleme saymasaydik, cevap gelmis olmasina
                # ragmen dongu "ilerleme yok" deyip durabilirdi.
                ozet["ilerleme"] = True
            else:
                ozet["engel"].append(
                    f"danisma yukseldi ({d['ajan']}): {d.get('sebep', '')}")

        # c) bekleyenleri bildir -- cevap uydurup devam ETMEZ.
        # Yalnizca INSANA dusenler: bir ajana sorulmus soruyu insana
        # gostermek, yanlis kisiyi bekletir.
        for m in self.ofis.postane.insan_bekleyenler():
            ozet["bekleyen"].append(
                {"tur": "soru", "kim": m["gonderen"], "metin": m["govde"],
                 "gorev_no": m["gorev_no"]})
        for o in self.ofis.postane.bekleyen_onaylar():
            ozet["bekleyen"].append(
                {"tur": "onay", "kim": o["isteyen"], "metin": o["eylem"],
                 "gorev_no": o["gorev_no"], "risk": o["risk"]})

        # d) ATAMA once (tek iplik), KOSU sonra (paralel)
        #
        # Sira onemli: atamayi da paralel yapsaydik iki iplik ayni bos
        # ajani secebilirdi -- veritabani henuz "mesgul" demiyor, cunku
        # is daha baslamadi.
        kosulacak = (self.ofis.tahta.liste(durum="hazir")
                     + self.ofis.tahta.liste(durum="calisiyor"))
        atamalar = []
        rezerve = set()
        # KABIN TEK YUZEYDIR -- ayni anda tek is kullanabilir.
        #
        # OLCULDU (22.09.2026): kabine baglanan ajan YENI SEKME ACMAZ,
        # var olan sekmede calisir. Iki is ayni anda baglaninca:
        #
        #   A -> example.com/?A=1 ; B -> example.com/?B=2
        #   A "neredeyim" diye sordu -> "?B=2"
        #
        # A kendi sayfasinda SANDI, B'nin sayfasini okudu. Hata vermedi.
        # Bu, Yasa 1'in tarayici halidir ve korkulugu yoktu: yazma
        # kilidi DOSYALARI korur, paylasilan bir yuzeyi degil.
        #
        # Kabin DISINDA boyle bir sorun yok -- her is kendi tarayicisini
        # alir (`--isolated`). Sinir yalnizca paylasilan kabine ait.
        kabin_alindi = False
        # ISE YAZILI KABIN. Halka kabinsiz koşsa bile (ornegin panelde
        # "Surdur"), kabin verilmis bir is kabinle koşar. Kabin
        # KAPALIYSA is BEKLETILIR ve sebebi soylenir: oturumsuz bir
        # tarayicida kosturmak, girisli sayfayi bekleyen isi sessizce
        # baska bir dunyada kosturmak olurdu.
        _kabin_simdi = None
        cdp_is = {}
        izleme_is = set()
        from . import devral as _devral
        # IZLEME KABINI (29.09.2026, kullanici: "muratin sisteminde ajanlar
        # gomulu tarayiciyi kullaniyor, bizde de olmali"). Anahtar ACIK ve
        # kabin aciksa, tarayici kullanacagi en belli olan TEK is kabinde
        # (panelde canli) kosar; otekiler kendi gorunmez tarayicisiyla.
        # Kabinli (insanin isaret ettigi) bir is varsa oncelik onundur.
        izleme_adayi = None
        if (kabin_izle_acik_mi(self.db, self.proje_id)
                and not any(g.get("tarayici_kabin") for g in kosulacak)):
            adaylar = [g for g in kosulacak
                       if not (g.get("tarayici_alani") or [])
                       and not _devral.devralinmis(self.db, self.proje_id, g["id"])]
            if adaylar:
                izleme_adayi = max(adaylar, key=_tarayici_puani)["no"]
        for g in kosulacak:
            # DEVRAL: insandaki is atlanir ve bu SOYLENIR -- sessizce
            # atlanan is, "neden ilerlemiyor" sorusunu cevapsiz birakir.
            if _devral.devralinmis(self.db, self.proje_id, g["id"]):
                ozet["engel"].append({"gorev_no": g["no"],
                                      "sebep": "insan devraldi (terminalde) -- "
                                               "'Ofise geri ver' ile surer"})
                continue
            cdp = tarayici_kabini
            if not cdp and g["no"] == izleme_adayi and not kabin_alindi:
                if _kabin_simdi is None:
                    _kabin_simdi = self.kabin_ucnoktasi() or ""
                if _kabin_simdi:
                    cdp = _kabin_simdi
                    izleme_is.add(g["no"])
            if not cdp and g.get("tarayici_kabin") and (g.get("tarayici_alani") or []):
                if _kabin_simdi is None:
                    _kabin_simdi = self.kabin_ucnoktasi() or ""
                if not _kabin_simdi:
                    ozet["engel"].append(
                        {"gorev_no": g["no"],
                         "sebep": "bu ise PAYLASILAN kabin verildi ama kabin "
                                  "KAPALI -- panelden tarayiciyi ac ya da isi "
                                  "iptal et (oturumsuz tarayicida kosturulmaz)"})
                    continue
                cdp = _kabin_simdi
            cdp_is[g["no"]] = cdp
            tarayicili = bool(cdp and ((g.get("tarayici_alani") or [])
                                       or g["no"] in izleme_is))
            if tarayicili and kabin_alindi:
                # Sessizce atlamak, isin neden kosmadigini cevapsiz
                # birakirdi. Sebep GORUNUR olur.
                ozet["engel"].append(
                    {"gorev_no": g["no"],
                     "sebep": "kabin baska bir iste -- kabin TEK yuzeydir, "
                              "ayni anda tek is kullanabilir"})
                continue
            ajan = self._uygun_ajan(g, rezerve)
            if not ajan:
                continue
            if tarayicili:
                kabin_alindi = True
            rezerve.add(ajan)
            atamalar.append((g, ajan))

        def tek_is(g, ajan):
            """Tek isi kosturur. Istisna KENDI icinde kalir -- bir kol
            duserse otekiler iptal olmamali."""
            try:
                # TARAYICI GORUNURLUGU ve PROFIL buradan gecer.
                # Gecmiyordu: `koltuk` ikisini de aliyordu, `tarayici.py`
                # ikisini de uyguluyordu, ama orkestra hicbirini
                # iletmiyordu -- yani insan icin YOK hukmundeydiler.
                # `video.py` bir kez tam bundan aylarca ajana
                # ulasmamisti: MODULUN VAR OLMASI BIR BAGLANTI DEGILDIR.
                sonuc = self.koltuk.kos(
                    g["no"], ajan, butce_usd=butce_usd,
                    zaman_asimi=zaman_asimi, izinli_araclar=izinli_araclar,
                    tarayici_gorunur=tarayici_gorunur,
                    tarayici_profili=tarayici_profili,
                    tarayici_kabini=cdp_is.get(g["no"], tarayici_kabini),
                    kabin_izleme=g["no"] in izleme_is)
                return ("tamam", g, ajan, sonuc)
            except KilitCakismasi as exc:
                # Yasa 1 calisti: alan baskasinda. Bu bir HATA degil,
                # dogru davranis -- is siraya girer.
                return ("kilit", g, ajan, exc)
            except Exception as exc:
                return ("hata", g, ajan, exc)

        if paralel > 1 and len(atamalar) > 1:
            ozet["paralel"] = min(paralel, len(atamalar))
            with ThreadPoolExecutor(max_workers=ozet["paralel"]) as havuz:
                sonuclar = list(havuz.map(lambda p: tek_is(*p), atamalar))
        else:
            ozet["paralel"] = 1
            sonuclar = [tek_is(g, a) for g, a in atamalar]

        for hal, g, ajan, veri in sonuclar:
            if hal == "kilit":
                ozet["engel"].append(f"#{g['no']} kilit: {veri}")
            elif hal == "hata":
                ozet["engel"].append(f"#{g['no']} calistirilamadi: {veri}")
            else:
                ozet["baslatilan"].append({"no": g["no"], "ajan": ajan, **veri})
                ozet["ilerleme"] = True
        return ozet

    def kos(self, *, azami_tik: int = 12, butce_usd: float = None,
            zaman_asimi: float = None, izinli_araclar: tuple = (),
            paralel: int = 3, tarayici_gorunur: bool = False,
            tarayici_profili: str = "", tarayici_kabini: str = ""):
        """Halkayi ILERLEME DURANA kadar dondurur, her adimda ozet akitir.

        Ilerlemeyen bir donguyu dondurmeye devam etmek jeton yakar ve
        panelde "calisiyor" gorunur -- en pahali yanilgi. Durma sebebi
        her zaman ACIKCA soylenir.
        """
        for sira in range(azami_tik):
            # INSAN DURDURDU: defterdeki istek (panel ya da kabuk). Yeni tur
            # BASLAMAZ; kosan turu koltuk zaten kesiyor. Istek burada
            # temizlenmez -- yalniz insan yeni bir sey baslatinca.
            if durdurma_istendi(self.db, self.proje_id):
                yield {"bitti": True, "sebep": "Insan DURDURDU.", "tik": sira}
                return
            ozet = self.tik(butce_usd=butce_usd, zaman_asimi=zaman_asimi,
                            izinli_araclar=izinli_araclar, paralel=paralel,
                            tarayici_gorunur=tarayici_gorunur,
                            tarayici_profili=tarayici_profili,
                            tarayici_kabini=tarayici_kabini)
            ozet["tik"] = sira + 1
            yield ozet
            if durdurma_istendi(self.db, self.proje_id):
                yield {"bitti": True, "sebep": "Insan DURDURDU.", "tik": sira + 1}
                return

            acik = [g for g in self.ofis.tahta.liste()
                    if g["durum"] in ("hazir", "calisiyor", "inceleme")]
            if not acik:
                yield {"bitti": True, "sebep": "Butun isler kapandi.",
                       "tik": sira + 1}
                return
            if not ozet["ilerleme"]:
                sebep = ("Insan cevabi bekleniyor." if ozet["bekleyen"]
                         else "Ilerleme yok.")
                yield {"bitti": True, "sebep": sebep, "tik": sira + 1,
                       "bekleyen": ozet["bekleyen"], "engel": ozet["engel"]}
                return
        yield {"bitti": True, "sebep": f"Tik siniri ({azami_tik}) doldu.",
               "tik": azami_tik}
