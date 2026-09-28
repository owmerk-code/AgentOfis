# -*- coding: utf-8 -*-
"""ROL KUTUPHANESI -- meslek bir ETIKET degil, bir SOZLESMEDIR.

Bu dosya var olmadan once `kadro.ise_al` mesleği **serbest metin** olarak
aliyordu: `meslek TEXT NOT NULL`. Semadaki yorum bile ornek sayiyordu
("lider | backend | arayuz | test | arastirma | metin") -- yani bir
sozluk olmasi dusunulmus ama hic olmamis.

Bedeli olculdu: gercek ofiste `bilge` (arastirma) ve `deniz` (icerik)
`tur='kafa'` olarak ise alindi. Ikisinin de isi DOSYA URETMEK -- rapor
yazmak, metin yazmak. Ama `kafa` ajanin yazan araci yoktur. Iki ajan
aylarca **tanimi geregi yapmasi gereken isi yapamaz** halde durdu ve
kimse fark etmedi, cunku "arastirma" yalnizca bir kelimeydi; neye
ihtiyac duydugunu soyleyen bir yer yoktu.

**Etiket yanlis kurulursa fark edilmez. Tanim yanlis kurulursa kurulmaz.**

## Bir rolun tasidigi sekiz alan -- her biri ODENMIS bir hatadan geliyor

| alan | hangi hata |
|---|---|
| `ozet` | brifing K1: ajan ne is yaptigini bilmeli |
| `tur` | bilge/deniz dosya yazamiyordu |
| `ek_izinler` | `WebSearch` izin listesinde yoktu -- arastirma HIC calismiyordu |
| `mcp` | 131.543 jeton: isin gerektirdigi baglayici, hesabin tamami degil |
| `kanit_turleri` | kanit kapisi lastik damgaya donmesin |
| `olcut_sablonu` | MAST %41,8 belirtim -- Gemini adaptoru tam bundan kullanilamaz cikti |
| `kademe` | model verilmeden kosan is $0,88, verilen $0,08 (on kat) |
| `butce_alt_siniri` | arastirma kod isinin ~7 kati yakiyor ($0,617 / $0,089) |

Karsilastirma icin: rakibin rol kutuphanesinde rol **iki** sey
dolduruyor -- avatar ve motor. Avatar sus. Ve alti rolunun altisi da
yazilim; pazarlama takimi kurabiliyorsun ama pazarlamaci rolu yok.
Bizim kutuphanemiz kullanicinin gercek isini kapsar: yazilim kadar
magaza, reklam, icerik, arastirma ve analiz de burada.

## Neden model adi degil KADEME

Rol `model="haiku"` deseydi kutuphane ilk model degisiminde bayatlardi
-- nitekim bayatladi: olculdu ki `gpt-5.6-luna` haiku'yu her eksende
yeniyor (zeka 21/17, hiz 135/92 tok-sn, baglam 1M/200K, ustelik daha
ucuz). Rol **ne kadar guc gerektigini** soyler; hangi modelin o gucu
verdigi motora gore degisir ve `KADEME_MODEL`'de tek yerde durur.

Ayni sebeple rol motoru SECMEZ, yalnizca onerir: hangi motorun kurulu
oldugu makineye gore degisir ve `musait_motorlar()` bunu olcer,
tahmin etmez.

## Kutuphanede OLMAYAN iki model -- bilerek

`fable` ve `astra` hicbir kademede yok. Ikisi de "isci modeli" degil
**kapi modeli**: turun kisa, kararin pahali oldugu yerlerde (sartname,
hakem, zor inceleme) elle cagrilir. Kullanicinin olcumu: *"tek promptta
5 saatlik limiti bitiriyordu."* Bir kademeye koysaydik donguye
girerlerdi -- limiti bitiren sey tam olarak budur.

Ikisi arasinda bizim icin belirleyici fark modelin gucu degil **kendi
korkulugumuz**: `claude` motoru `--max-budget-usd` uygular, `codex`
uygulamaz ve butce verilince turu hic baslatmadan reddeder. Yani
fable tavanla guvenle kosabilir, astra kosamaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Guc kademeleri. Rol bunu soyler, model adini DEGIL.
KADEMELER = ("hizli", "standart", "guclu")

#: Kademe -> gercek model. Motor basina ayri, cunku ayni kademenin
#: karsiligi motora gore baska bir modeldir.
#:
#: OLCULDU (20.09.2026):
#: - codex tarafinda `gpt-5.6-sol` Artificial Analysis Kodlama Ajani
#:   Indeksi'nin lideri (80) ve jeton verimli (ortalama 20.968 cikis
#:   jetonu; terra ayni iste 55.594 yakip GOREV BASINA pahaliya geldi).
#:   Terra yine de `standart`ta duruyor: bu tek bir dis olcum, bizim
#:   isimiz degil. Kendi sayimizi alinca yeri degisebilir.
#: - `haiku` claude tarafinin en ucuz basamagi olarak kaliyor ama
#:   isci koltugu icin artik onerilmiyor (bkz. modul docstring).
KADEME_MODEL = {
    "claude": {"hizli": "haiku", "standart": "sonnet", "guclu": "opus"},
    "codex": {"hizli": "gpt-5.6-luna", "standart": "gpt-5.6-terra",
              "guclu": "gpt-5.6-sol"},
    # Sahte motor jeton yakmaz; kademe ayrimi anlamsiz ama SESSIZ
    # kalmamali -- eksik anahtar KeyError verirdi, testte gurultu olur.
    "sahte": {"hizli": "", "standart": "", "guclu": ""},
}

#: Kapi modelleri: hicbir kademede YOK, elle cagrilir.
#: `tavan_zorunlu` -> bu modeli butce tavani olmadan kosturmak yasak.
KAPI_MODELLERI = {
    "fable": {"motor": "claude", "tavan_zorunlu": True,
              "not": "Tavan uygulanabilir -- guvenli sekilde otomatiklestirilebilir."},
    "astra": {"motor": "codex", "tavan_zorunlu": True,
              "not": "codex tavan UYGULAYAMAZ; bu yuzden yalnizca ELLE, "
                     "bilerek cagrilir. Otomatik hicbir yolda yer almaz."},
}


#: Liderin ISE verdigi zorluk. Tek yerde durur: koltuk da, sinamalar da
#: buradan okur -- iki kopya olsaydi biri kayardi.
ZORLUK_KADEME = {"kolay": "hizli", "orta": "standart", "zor": "guclu",
                 "cok_zor": "guclu"}

#: Zorluk EFORU da belirler (23.09.2026, kullanici karari). Once zorluk
#: yalniz MODELI degistiriyordu: zor is guclu modele gidiyor ama yine
#: `medium`da dusunuyordu. Kullanicinin iki sarti:
#:   - "max modda hicbirini kullanmayacagim" -> `max` bu sozlukte YOK;
#:     motor adaptorleri de yalniz uc seviye tanir. Yapiyla kapali.
#:   - kararin sahibi lider, TAVANIN sahibi insan -> `efor_tavani` ayari.
#:
#: DORDUNCU SEVIYE `cok_zor` (23.09.2026, kullanici istegi): en guclu
#: model + `cok_yuksek` (CLI'da `xhigh`). `max` DEGIL -- o yasak kaldi.
#: Olculdu: `--effort xhigh` Opus 5.5 ve Sonnet 5'te calisiyor; Haiku
#: efor almiyor ama hata da vermiyor (katalogda efor secenegi yok).
#: `cok_zor` da `zor` gibi GEREKCE ister (tahta.py).
ZORLUK_EFOR = {"kolay": "dusuk", "orta": "normal", "zor": "yuksek",
               "cok_zor": "cok_yuksek"}

#: Dusukten yuksege. Tavan bu siraya gore uygulanir. `max` YOK.
EFOR_SIRASI = ("dusuk", "normal", "yuksek", "cok_yuksek")

ANAHTAR_EFOR_TAVANI = "efor_tavani"
#: Varsayilan tavan en ust seviye: aksi halde `cok_zor` hic calismazdi.
#: Pahali seviyeyi sinirlayan sey tavan degil GEREKCE zorunlulugu.
VARSAYILAN_EFOR_TAVANI = "cok_yuksek"

#: EFOR MODU -- panelin dugmesi. "zorluk": her is kendi zorluguyla
#: (tavanla sinirli). Sabit bir seviye ("normal", "yuksek"...): BUTUN
#: turlar o seviyede -- lider, isci, danisma, kapi. Kullanici: *"tiklarim
#: hepsi medium olur, high yaparim hepsi high olur."*
ANAHTAR_EFOR_MODU = "efor_modu"
EFOR_MODLARI = ("zorluk",) + EFOR_SIRASI

#: Kademe degisikligi KOD degil AYAR: yeni model geldiginde insan onaylar
#: ve ofis bunu `ayar` tablosuna yazar (plan.py ile ayni karar -- her
#: model degisimi bir kod degisikligi olsaydi insan kodu duzeltmek
#: zorunda kalirdi). Anahtar: "kademe:<motor>:<kademe>".
KADEME_AYAR_ONEKI = "kademe:"


class RolHatasi(Exception):
    """Bilinmeyen ya da gecersiz rol."""


def kademe_haritasi(db=None, proje_id: str = "") -> dict:
    """Etkin kademe -> model haritasi: koddaki varsayilan + ONAYLANMIS ayar.

    `db` verilmezse yalniz koddaki varsayilan doner (saf cagri, sinama).
    Ayarda yazan model KAZANIR -- insanin onayi koddaki varsayilani ezer.
    """
    harita = {m: dict(k) for m, k in KADEME_MODEL.items()}
    if db is None or not proje_id:
        return harita
    for motor, kademeler in harita.items():
        for kademe in list(kademeler):
            deger = db.ayar_oku(proje_id,
                                f"{KADEME_AYAR_ONEKI}{motor}:{kademe}", "")
            if deger:
                kademeler[kademe] = deger
    return harita


def kademe_yaz(db, proje_id: str, motor: str, kademe: str, model: str) -> None:
    """Bir kademenin modelini AYAR olarak yazar (koddaki varsayilani ezer)."""
    if kademe not in KADEMELER:
        raise RolHatasi(f"Bilinmeyen kademe: {kademe!r}. "
                        f"Secenekler: {', '.join(KADEMELER)}")
    if motor not in KADEME_MODEL:
        raise RolHatasi(f"Kademesi tanimli olmayan motor: {motor!r}")
    model = str(model or "").strip()
    if not model:
        # Bos model hesabin varsayilanina duser (on kat maliyet).
        raise RolHatasi("Kademeye BOS model yazilmaz.")
    if any(k in model for k in KAPI_MODELLERI):
        raise RolHatasi(
            f"{model!r} bir KAPI modeli; hicbir kademeye konmaz "
            "(tavansiz dongu, limiti bitiren sey tam budur).")
    db.ayar_yaz(proje_id, f"{KADEME_AYAR_ONEKI}{motor}:{kademe}", model)


def efor_tavani(db=None, proje_id: str = "") -> str:
    if db is None or not proje_id:
        return VARSAYILAN_EFOR_TAVANI
    t = db.ayar_oku(proje_id, ANAHTAR_EFOR_TAVANI, VARSAYILAN_EFOR_TAVANI)
    return t if t in EFOR_SIRASI else VARSAYILAN_EFOR_TAVANI


def efor_tavani_yaz(db, proje_id: str, efor: str) -> None:
    if efor not in EFOR_SIRASI:
        raise RolHatasi(f"Efor tavani {EFOR_SIRASI} icinden olmali "
                        "('max' bilerek yok).")
    db.ayar_yaz(proje_id, ANAHTAR_EFOR_TAVANI, efor)


def efor_modu(db=None, proje_id: str = "") -> str:
    if db is None or not proje_id:
        return "zorluk"
    m = db.ayar_oku(proje_id, ANAHTAR_EFOR_MODU, "zorluk")
    return m if m in EFOR_MODLARI else "zorluk"


def efor_modu_yaz(db, proje_id: str, mod: str) -> None:
    if mod not in EFOR_MODLARI:
        raise RolHatasi(f"Efor modu {EFOR_MODLARI} icinden olmali ('max' bilerek yok).")
    db.ayar_yaz(proje_id, ANAHTAR_EFOR_MODU, mod)


def tur_eforu(db, proje_id: str, istenen: str) -> str:
    """Bir turun GERCEKTE kosacagi efor -- butun cagiranlar BUNU kullanir.

    Tek islev: koltuk, lider, planlama, danisma ve kapi ayni kurali
    uygulasin. Bes yerde ayri yazilsaydi biri unutulurdu (bu projede
    iki kopyadan biri alti kez unutuldu).
    """
    mod = efor_modu(db, proje_id)
    if mod != "zorluk":
        return mod
    return etkin_efor(istenen, efor_tavani(db, proje_id))


def etkin_efor(istenen: str, tavan: str = VARSAYILAN_EFOR_TAVANI) -> str:
    """Istenen eforu tavana gore sinirlar.

    Taninmayan istek (bos, eski kayit) `normal`e duser: bilinmeyen bir
    seviye adaptorde sessizce yok sayilirdi -- ne kostugu belirsiz kalirdi.
    """
    if istenen not in EFOR_SIRASI:
        istenen = "normal"
    if tavan not in EFOR_SIRASI:
        tavan = VARSAYILAN_EFOR_TAVANI
    return EFOR_SIRASI[min(EFOR_SIRASI.index(istenen),
                           EFOR_SIRASI.index(tavan))]


@dataclass(frozen=True)
class Rol:
    """Bir rolun TAM tanimi. Alanlarin gerekcesi modul docstring'inde."""

    ad: str
    kategori: str
    ozet: str
    #: 'eller' dosya yazar, 'kafa' yazamaz. YANLIS KURULURSA IS YAPILAMAZ.
    tur: str
    #: Varsayilan izin listesinin USTUNE bu rolun ihtiyac duydugu izinler.
    #: Varsayilan dar tutulur; genisletme ACIKCA yazilir ve kayda gecer.
    ek_izinler: tuple = ()
    #: Isin gerektirdigi baglayicilar. Hesabin tamami DEGIL (131k jeton dersi).
    mcp: tuple = ()
    #: Bu rolun uretmesi beklenen kanit turleri (tahta.py ile ayni sozluk).
    kanit_turleri: tuple = ("dosya",)
    #: Kabul olcutu SABLONU. Lider bunu doldurur; bos olcut, incelenecek
    #: bir sey olmamasi demektir.
    olcut_sablonu: str = ""
    kademe: str = "standart"
    #: Tur basina onerilen en dusuk tavan ($). Rol turune gore degisir:
    #: arastirma kod isinin ~7 kati yakiyor.
    butce_alt_siniri: float = 0.0
    #: Insana gosterilecek uyari (baglayici bekliyor gibi).
    uyari: str = ""


#: Kanit turleri tahta.py ile AYNI sozlukten gelir. Ayri bir liste
#: tutsaydik biri digerinden kayar ve rol var olmayan bir kanit turu
#: isteyebilirdi -- ajan onu hic ekleyemezdi.
GECERLI_KANITLAR = ("terminal", "diff", "gorsel", "dosya", "baglanti")

TURLER = ("eller", "kafa")


def _r(*a, **k) -> Rol:
    return Rol(*a, **k)


#: ---------------------------------------------------------------- KUTUPHANE
ROLLER = {r.ad: r for r in (

    # ------------------------------------------------------------- YONETIM
    _r("lider", "YONETIM",
       "Patronun tek muhatabi. Triyaj yapar (cevap / kendi / dagit), "
       "bolme kararini GEREKCESIYLE verir, isi kanita karsi inceler.",
       tur="eller",                      # yazma yetkisi TUR ile degil,
       # cagri yeriyle kapatilir: lider.incele ve sohbet triyaji
       # `yazabilir=False` ile kosar. Turu 'kafa' yapsaydik lider
       # birlestirme kolunu da ustlenemezdi.
       kanit_turleri=("dosya",),
       olcut_sablonu="Hukum acik yazildi (kapat / geri + gerekce) ve "
                     "gerekce karar gunlugune dustu.",
       kademe="guclu",
       butce_alt_siniri=0.30),

    # ------------------------------------------------------------ YAZILIM
    _r("backend", "YAZILIM",
       "API, veri katmani, altyapi. Sunucu tarafi is mantigi.",
       tur="eller",
       ek_izinler=("Bash(npx *)", "Bash(pip *)"),
       kanit_turleri=("terminal", "diff"),
       olcut_sablonu="Testler yesil (komut ciktisi kanit olarak eklendi) "
                     "ve degisiklik yalnizca yazma alanina dokundu.",
       kademe="guclu",
       butce_alt_siniri=0.30),

    _r("arayuz", "YAZILIM",
       "Ekran, UI/UX, istemci tarafi. Gorunen yuzey.",
       tur="eller",
       ek_izinler=("Bash(npx *)", "Bash(npm *)"),
       kanit_turleri=("terminal", "gorsel", "diff"),
       olcut_sablonu="Arayuz calisiyor: testler yesil ya da ekran goruntusu "
                     "kanit olarak eklendi.",
       kademe="standart",
       butce_alt_siniri=0.30),

    _r("entegrasyon", "YAZILIM",
       "Adaptor, motor, baglayici. Disaridaki bir seyi ofise takar.",
       tur="eller",
       ek_izinler=("Bash(npx *)", "Bash(pip *)", "Bash(where *)", "Bash(which *)"),
       kanit_turleri=("terminal", "diff"),
       # Bu satir bir hatadan dogdu: Gemini adaptoru "pytest yesil +
       # Motor'dan turuyor" olcutunu TAM karsiladi ve kurulamaz cikti,
       # cunku sekiz sozlesme parametresini yok sayiyordu.
       olcut_sablonu="`python testler/dogrula_teslim.py <dosya>` SIFIR "
                     "bulguyla geciyor -- sozlesme butunlugu dahil.",
       kademe="guclu",
       butce_alt_siniri=0.40),

    _r("kalite", "YAZILIM",
       "Test, dogrulama, regresyon nobeti. Isin gercekten bittigini olcer.",
       tur="eller",
       ek_izinler=("Bash(npx *)", "Bash(npm *)"),
       kanit_turleri=("terminal",),
       # GuvenKart isinde olculdu: "once 15 assert, sonra 15" -- testi
       # duzeltmekle bosaltmak arasindaki fark budur.
       olcut_sablonu="Testler yesil VE iddia sayisi azalmadi "
                     "(test bosaltilarak gecirilmedi).",
       kademe="standart",
       butce_alt_siniri=0.25),

    # --------------------------------------------------------------- BILGI
    _r("arastirma", "BILGI",
       "Kaynakli arastirma, rakip analizi, karsilastirma. Bulur ve yazar.",
       # ESKIDEN 'kafa' IDI -- ve raporunu dosyaya yazamiyordu.
       tur="eller",
       kanit_turleri=("baglanti", "dosya"),
       olcut_sablonu="Her iddianin yaninda KAYNAK baglantisi var ve rapor "
                     "dosya olarak yazildi. Kaynaksiz iddia yok.",
       kademe="standart",
       # Olculdu: arastirma turu $0,617, kod isi $0,089. ~7 kat.
       # Kod icin uygun bir tavan arastirmayi ORTASINDA keser -- bir kez
       # kesti ve 208.148 jetonluk is sifir kanitla kayboldu.
       butce_alt_siniri=1.50),

    _r("analiz", "BILGI",
       "Veri, olcum, rapor. Sayiyi cikarir ve ne anlama geldigini yazar.",
       tur="eller",
       ek_izinler=("Bash(pip *)",),
       kanit_turleri=("terminal", "dosya"),
       olcut_sablonu="Sayilar YENIDEN URETILEBILIR: hesabi yapan komut ya "
                     "da betik kanit olarak eklendi.",
       kademe="standart",
       butce_alt_siniri=0.50),

    # -------------------------------------------------------------- ICERIK
    _r("metin", "ICERIK",
       "Turkce metin: urun aciklamasi, e-posta, duyuru, reklam metni.",
       # ESKIDEN 'kafa' IDI -- metin uretmek dosya yazmaktir.
       tur="eller",
       kanit_turleri=("dosya",),
       # Kod-disi iste kanit sorusunun cevabi: kapi kanit TURU degil
       # INCELEMEDIR. Kanit isin nerede oldugunu gosterir; olcute uyup
       # uymadigina lider BAKARAK karar verir. O yuzden olcut somut olmali.
       olcut_sablonu="Istenen sayida ve bicimde metin <dosya>'ya yazildi; "
                     "her biri verilen kisitlara uyuyor (uzunluk, ton, "
                     "yasakli ifadeler).",
       kademe="standart",
       butce_alt_siniri=0.30),

    _r("seo", "ICERIK",
       "Arama gorunurlugu: anahtar kelime, baslik, ustveri, ic baglanti.",
       tur="eller",
       kanit_turleri=("dosya", "baglanti"),
       olcut_sablonu="Oneriler dosyaya yazildi ve her biri bir OLCUME ya da "
                     "kaynaga dayaniyor -- genel gecer tavsiye degil.",
       kademe="standart",
       butce_alt_siniri=0.50),

    # ------------------------------------------------------------- TICARET
    _r("magaza", "TICARET",
       "Katalog, stok, siparis, fiyat. Magazanin gunluk isleri.",
       tur="eller",
       mcp=("shopify",),
       kanit_turleri=("baglanti", "gorsel"),
       olcut_sablonu="Degisiklik magazada GORUNUR: kayit baglantisi ya da "
                     "ekran goruntusu kanit olarak eklendi.",
       kademe="standart",
       butce_alt_siniri=0.40,
       uyari="Baglayici gerekiyor: Shopify. Yetki dolmus olabilir -- "
             "claude.ai baglayici ayarlarindan yenilenmeli, ofis yapamaz."),

    _r("reklam", "TICARET",
       "Reklam kreatifi ve performans analizi.",
       tur="eller",
       mcp=("meta",),
       kanit_turleri=("dosya", "gorsel"),
       olcut_sablonu="Kreatif dosyaya yazildi; performans iddiasi varsa "
                     "hangi olcumden geldigi belirtildi.",
       kademe="standart",
       butce_alt_siniri=0.40,
       uyari="Baglayici gerekiyor: Meta Reklamlar. Ajanlara baglayici "
             "verme yolu HENUZ ACIK DEGIL (olculdu: 131.543 jeton)."),

    # --------------------------------------------- YONETIM (ek, 20.09.2026)
    _r("urun", "YONETIM",
       "Sartname ve kabul olcutu. Isin NE oldugunu ve BITTIGININ nasil "
       "anlasilacagini yazar. Kod yazmaz, is dagitmaz.",
       tur="eller",
       # MAST'in EN BUYUK hata kumesi belirtim/sistem tasarimi (%41,8) ve
       # bu ofis onu bir kez odedi: Gemini adaptoru kabul olcutunu TAM
       # karsiladi ve yine de kurulamaz cikti. Kapi, kendisine verilen
       # olcutten daha iyi olamaz -- o olcutu yazan bir rol gerekiyordu.
       kanit_turleri=("dosya",),
       olcut_sablonu="Her kabul maddesi OLCULEBILIR: yaninda NASIL "
                     "dogrulanacagi yaziyor (komut, dosya, sayi). Kapsam "
                     "disi da acikca yazildi.",
       kademe="guclu",
       butce_alt_siniri=0.30),

    # --------------------------------------------- YAZILIM (ek, 20.09.2026)
    _r("devops", "YAZILIM",
       "Derleme, dagitim, ortam, CI. Kodun calistigi yeri kurar.",
       tur="eller",
       ek_izinler=("Bash(docker *)", "Bash(git *)", "Bash(gh *)",
                   "Bash(npm *)", "Bash(where *)"),
       kanit_turleri=("terminal", "diff"),
       olcut_sablonu="Komut CIKTISIYLA kanit olarak eklendi ve GERI ALMA "
                     "yolu yazildi. Yayina alma yapildiysa onay alinmisti.",
       kademe="guclu",
       butce_alt_siniri=0.30,
       # Ofisin kurali: "kod yazmak sormaz; para harcamak, YAYINA ALMAK,
       # disariya yazmak sorar." Bu rolun isi tam o sinirda duruyor.
       uyari="Yayina alma RISKLI eylemdir: `onay_iste` ile insana sorulur, "
             "kendi basina yapilmaz."),

    _r("guvenlik", "YAZILIM",
       "Guvenlik incelemesi: sir taramasi, bagimlilik denetimi, yetki "
       "yuzeyi. Bulur ve gosterir; duzeltmeyi baskasi yapar.",
       tur="eller",
       ek_izinler=("Bash(npm audit*)", "Bash(pip *)", "Bash(git *)"),
       kanit_turleri=("terminal", "dosya"),
       # "Bulgu yok" da bir sonuctur AMA neyin tarandigi yazilmadan
       # soylenirse olculemez -- hic bulgu vermeyen bir tarayici, "sorun
       # yok" diyen bir ariza olabilir (saglik aracinda ayni ders).
       olcut_sablonu="Her bulgu DOSYA:SATIR ile gosterildi ve nasil "
                     "somurulecegi yazildi. Bulgu yoksa NEYIN tarandigi "
                     "ve nasil tarandigi yazildi.",
       kademe="guclu",
       butce_alt_siniri=0.30,
       uyari="BULUR, DUZELTMEZ. Duzeltmeyi yapan, kendi isini incelemis "
             "olurdu (yapan inceleyemez)."),

    # --------------------------------------------- ICERIK (ek, 20.09.2026)
    _r("dokuman", "ICERIK",
       "Teknik dokuman: README, kurulum, API, kullanim kilavuzu. "
       "Pazarlama metni degil; calisan talimat.",
       tur="eller",
       ek_izinler=("Bash(npm *)", "Bash(pip *)"),
       kanit_turleri=("dosya", "terminal"),
       # Bir kurulum dokumaninin "iyi" olmasi, adimlarinin CALISMASIDIR.
       # Yalnizca "dosya yazildi" kaniti burada lastik damgadir.
       olcut_sablonu="Yazilan adimlar BIREBIR izlendi ve calistigi "
                     "gosterildi (komut ciktisi). Izlenemeyen adim varsa "
                     "hangisi oldugu yazildi.",
       kademe="standart",
       butce_alt_siniri=0.20),

    _r("ceviri", "ICERIK",
       "Ceviri ve yerellestirme. Terim tutarliligi, birim/tarih/para "
       "bicimi, hedef dilin tonu.",
       tur="eller",
       kanit_turleri=("dosya",),
       olcut_sablonu="Kaynak ve hedef YAN YANA verildi; terim sozlugune "
                     "uyuldu; sayi/tarih/para bicimi hedef dile uyarlandi. "
                     "Emin olunmayan terim UYDURULMADI, isaretlendi.",
       kademe="standart",
       butce_alt_siniri=0.20),

    _r("tasarim", "ICERIK",
       "Gorsel tasarim: banner, kapak, sosyal gorsel, arayuz taslagi.",
       tur="eller",
       kanit_turleri=("gorsel", "dosya"),
       # Gorselde "iyi" oznel; olculebilir olan SARTLARA UYGUNLUK.
       olcut_sablonu="Uretilen gorsel EKLENDI (gorsel kaniti) ve istenen "
                     "olcu/oran/metin sartlarini karsiladigi tek tek "
                     "gosterildi.",
       kademe="standart",
       butce_alt_siniri=0.20,
       # 28.09.2026: burada "gorsel uretimi saglayici bakiyesi bekliyor"
       # yaziyordu -- 25.09'dan beri BAYATTI (gorsel ChatGPT aboneliginden
       # uretiliyor). Codex ajan cumleyi kelimesi kelimesine uyguladi ve
       # gorseli insana sordu; Claude gormezden gelip uretmisti.
       uyari="Gorseli ONCE `gorsel_uret` ile KENDIN uret (abonelikten, "
             "para kilidine takilmaz). `gorsel_iste` yalniz `gorsel_uret` "
             "uretici yok / kota dolu derse."),

    _r("video", "ICERIK",
       "Hareketli icerik: reklam klibi, sosyal medya videosu, urun "
       "tanitimi. Istemi yazar, uretir, sonucu olcer.",
       tur="eller",
       kanit_turleri=("dosya", "gorsel"),
       # URETIM `mcp__ofis__video_uret` ile olur (anahtar ajanin eline
       # gecmez). KURGU ise kabuktan yapilir ve izni burada verilir.
       # `ffmpeg` bugun KURULU DEGIL (`kabuk yetenek` olcuyor) -- izin
       # yine de simdi veriliyor, cunku tersi tam olculmus bir tuzak:
       # `WebSearch` arac listesindeydi ama IZIN listesinde degildi ve
       # ofis aylarca hic arastirma yapamadi. Kurulu olmayan bir komut
       # icin izin zararsiz (komut zaten bulunamaz ve sebebi gorunur);
       # kurulu bir komut icin izin EKSIKLIGI sessiz bir olumdur.
       ek_izinler=("Bash(ffmpeg *)", "Bash(ffprobe *)"),
       # Bu rol, ONCE ARAC OLCULDUGU icin var. Ayni gun `video` rolunu
       # araci olmadan eklemeyi REDDETMISTIK: "araci olmayan rol, rol
       # degildir." `ofis/video.py` yazilip dort kapisi olculunce rol
       # mesru oldu. Sira boyle: once arac, sonra rol.
       olcut_sablonu="Video dosyasi URETILDI ve eklendi; sure/oran/"
                     "cozunurluk istenen sartlari karsiliyor. GERCEK "
                     "maliyet yazildi (tahmin degil).",
       kademe="standart",
       butce_alt_siniri=0.20,
       # Model turu degil URETIM parasi: video saniye basi fiyatlanir ve
       # 30 saniyelik standart bir klip $12'ye kadar cikar.
       uyari="URETIM PARA HARCAR ve ucretsiz katmani yok. Tavan "
             "`video.VARSAYILAN_TAVAN_USD` ($2) ile kapali kalarak "
             "calisir; asilirsa is HIC BASLAMAZ."),

    # --------------------------------------------- TICARET (ek, 20.09.2026)
    _r("destek", "TICARET",
       "Musteri yaniti taslagi: iade, kargo, sikayet, soru. TASLAK "
       "yazar; gondermez.",
       tur="eller",
       kanit_turleri=("dosya",),
       olcut_sablonu="Yanit taslagi dosyaya yazildi ve her iddia (kargo "
                     "suresi, iade kosulu) HANGI kaynaktan geldigi "
                     "belirtilerek verildi. Bilinmeyen UYDURULMADI.",
       kademe="standart",
       butce_alt_siniri=0.20,
       uyari="GONDERMEZ. Disariya yazmak riskli eylemdir: `onay_iste` "
             "ile insana sorulur."),

)}

#: Kategoriler, kutuphanedeki SIRAYLA. Ayri bir liste tutmuyoruz --
#: iki yerde tutulan bir sey birinde guncellenip otekinde unutulur.
#: (Bu projede tam bu yuzden bes kez hata cikti.)


def kategoriler() -> list:
    """Kategoriler, ilk gorunme sirasiyla."""
    out = []
    for r in ROLLER.values():
        if r.kategori not in out:
            out.append(r.kategori)
    return out


#: Eski, sozluk-oncesi meslek adlari. Gercek ofiste yazilmis kayitlar
#: var ve onlar KIRILMAMALI -- ama yeni ise almada da sessizce kabul
#: edilmemeli. Cozumluyoruz ve cozumu SOYLUYORUZ.
ESKI_ADLAR = {
    "yazilim": "backend",
    "backend": "backend",
    "arayuz": "arayuz",
    "test": "kalite",
    "qa": "kalite",
    "lider": "lider",
    "arastirma": "arastirma",
    "metin": "metin",
    "icerik": "metin",
}


def coz(ad: str) -> str:
    """Verilen meslek adini kutuphanedeki role cevirir.

    Eski ad verilirse cevirir; bilinmeyen ad verilirse REDDEDER ve
    gecerli adlari sayar. Yanlis yazilmis bir rol adi sessiz bir olum
    sebebidir: ajan ise alinir, ihtiyac duydugu araclar hic verilmez
    ve bunu ancak "yapamadim" dediginde ogrenirsin.
    """
    anahtar = (ad or "").strip().lower()
    if not anahtar:
        raise RolHatasi(
            "Rol bos birakilamaz. Rol bir etiket degil sozlesmedir: "
            "ajanin turunu, araclarini, kanitini ve olcutunu o belirler.\n"
            f"Gecerli roller: {', '.join(sorted(ROLLER))}")
    if anahtar in ROLLER:
        return anahtar
    if anahtar in ESKI_ADLAR:
        return ESKI_ADLAR[anahtar]
    raise RolHatasi(
        f"Bilinmeyen rol: {ad!r}\n"
        f"Gecerli roller: {', '.join(sorted(ROLLER))}\n"
        "Yeni bir rol gerekiyorsa kutuphaneye EKLENIR (ofis/roller.py); "
        "serbest metin olarak gecirilmez -- tanimsiz rol, yanlis kurulmus "
        "ajan demektir.")


def rol(ad: str) -> Rol:
    """Rol tanimini getirir. Bilinmeyen ad reddedilir."""
    return ROLLER[coz(ad)]


def model_sec(motor: str, kademe: str, harita: dict = None) -> str:
    """Kademeyi o motordaki gercek model adina cevirir.

    Bilinmeyen motor icin BOS doner, patlamaz: yeni bir motor takildiginda
    (adaptor yazmak tek dosya) rol kutuphanesi onu bilmiyor olabilir ve
    bu ise alimi engellememeli -- model acikca verilebilir. Ama bos donus
    gorunur olmali; cagiran taraf "model verilmedi" uyarisini zaten
    veriyor (saglik denetimi: modelsiz ajan -> on kat maliyet).
    """
    if kademe not in KADEMELER:
        raise RolHatasi(
            f"Bilinmeyen kademe: {kademe!r}. Secenekler: {', '.join(KADEMELER)}")
    return ((harita or KADEME_MODEL).get(motor) or {}).get(kademe, "")


def kapi_modeli(motor: str, *, tavansiz_izinli: bool = False) -> dict:
    """Bu motorda KAPI modeli kullanilabilir mi.

    Kapi modeli (fable / astra) isci modeli degildir: yalnizca turun
    KISA, kararin PAHALI oldugu yerlerde cagrilir -- sartname yazmak,
    ikinci kez geri donen ise hakemlik etmek, supheli bir incelemeyi
    guclendirmek.

    Donus: `{"model", "tavan_zorunlu"}` ya da None.

    **None donmesinin sebebi modelin gucu degil BIZIM KORKULUGUMUZ.**
    Kapi modelleri tavansiz kosturulmaz -- kullanicinin olcumu: *"tek
    promptta 5 saatlik limiti bitiriyordu."* `codex` tur basina tavan
    UYGULAYAMIYOR (`butce_destegi=False`, bkz. motor/codex.py), o yuzden
    `astra` otomatik hicbir yola baglanamaz; elle cagrilir.

    Motorun tavan uygulayip uygulamadigi TAHMIN EDILMEZ, ADAPTORDEN
    OKUNUR: yarin codex tavan destegi eklerse bu islev kendiliginden
    dogru cevabi verir.
    """
    from .motor import motor_ac

    for ad, k in KAPI_MODELLERI.items():
        if k["motor"] != motor:
            continue
        if not k["tavan_zorunlu"]:
            return {"model": ad, "tavan_zorunlu": False}
        try:
            uygular = bool(getattr(motor_ac(motor), "butce_destegi", False))
        except Exception:
            # Motor acilamiyorsa KAPALI KALARAK basarisiz ol: tavan
            # uygulanip uygulanmadigini bilmeden pahali model kosturmak,
            # para kontrolunu varsayima birakmaktir.
            return None
        if uygular:
            return {"model": ad, "tavan_zorunlu": True}
        # Motor tavan uygulayamiyor. Varsayilan: YASAK.
        #
        # Plan yukseltmek bunu ACMAZ -- sebep payin darligi degil,
        # kacan bir turu DURDURACAK bir seyimizin olmamasi. GPT Pro
        # 20x'te bile codex tavan uygulamiyor; yalnizca daha fazla
        # payin olur. Acmak, insanin neyi kabul ettigini gorerek
        # verdigi AYRI bir karardir (`plan --tavansiz-kapi ac`).
        return {"model": ad, "tavan_zorunlu": False} if tavansiz_izinli else None
    return None


def ozet_satiri(r: Rol) -> str:
    """Insana tek satirda rol. Panelde ve onizlemede ayni bicim kullanilir."""
    parca = [f"{r.ad:<12} {r.kategori:<8} {r.tur:<5}"]
    parca.append(r.ozet)
    return "  ".join(parca)


def brifing_blogu(ad: str) -> str:
    """Rolun brifinge (K1) giren hali.

    Ajan ne is yaptigini, neyin kanit sayildigini ve neyin bittigini
    BRIFINGDEN ogrenir. Bugune kadar bunlar yalnizca kodda vardi:
    kural uygulaniyordu ama ajana hic soylenmiyordu. Uygulanan ama
    soylenmeyen kural, ajanin ondan ogrenemedigi kuraldir.
    """
    r = rol(ad)
    satir = [
        f"## ROLUN: {r.ad}  ({r.kategori})",
        "",
        r.ozet,
        "",
        f"- Dosya yazabilir misin: {'EVET' if r.tur == 'eller' else 'HAYIR'}",
        f"- Senden beklenen kanit turu: {', '.join(r.kanit_turleri)}",
    ]
    if r.olcut_sablonu:
        satir += ["- Bu rolde 'bitti' genellikle su demektir:",
                  f"  {r.olcut_sablonu}"]
    if r.uyari:
        satir += ["", f"! {r.uyari}"]
    return "\n".join(satir)


#: Liderin gordugu rol ozetinde bir rolun aciklamasi kac harfe kesilir.
#: Triyaj HER `konus` mesajinda kosar; tam aciklamalar (~2100 harf)
#: her mesaja binerdi. Kesmek bilgi kaybi ama SECIM icin ad + bir
#: cumle yetiyor -- ayrinti zaten `kabuk roller`de ve brifingde var.
LIDER_OZET_HARF = 78


def lider_blogu(mevcut_meslekler=()) -> str:
    """Liderin GORDUGU rol envanteri: kadroda olan ve OLMAYAN roller.

    OLCULMUS BOSLUK (21.09.2026): liderin dorduncu yolu (`kadro`) iki
    gercek kosuda da HIC atesmedi. Is tam bir dokuman isiydi, kadroda
    `dokuman` rolu YOKTU, kutuphanede VARDI -- ve lider ekip onermek
    yerine isi `bilge`ye (arastirma) verdi.

    Sebep yapisaldi: triyaj metni `kadro` yolunu ANLATIYOR ama liderin
    onerebilecegi rollerin listesini HIC vermiyordu. `roller` modulu
    `sohbet.py`ye ice aktarilmamisti bile. Yani lider *"gereken rol
    kadroda yok"* diye karar vermek icin neyin var oldugunu bilmiyordu;
    uydursa `Ekip` reddedecekti (tanimsiz rol kapisi).

    Baglayici envanteriyle ayni sinif ve ayni cozum: **gormeden karar
    vermek tahmindir.**

    Is sonucta iyi cikti, yani karar yanlis degildi -- ama `dokuman`
    rolunun sozlesmesi (olcut sablonu, `terminal` kaniti, ek izinler)
    HIC uygulanmadi ve olcut tesadufen dogru yazildigi icin is kurtuldu.

    TERS RISK BILEREK KARSILANDI: kutuphaneyi gorunur kilmak, hata
    modunu *"hic onermiyor"*dan *"her ise yeni ajan oneriyor"*a
    cevirebilir. Blok bu yuzden oneriyi tesvik etmez, yalnizca gorunur
    kilar; ve secim kuralini tekrar eder. Kalabalik kadro Yasa 2'nin
    faturasidir.
    """
    mevcut = {coz(m) for m in (mevcut_meslekler or []) if m}
    satir = ["# ROL KUTUPHANESI", "",
             "Kadronda OLAN roller: "
             + (", ".join(f"`{a}`" for a in sorted(mevcut)) or "(yok)"),
             ""]
    eksik = [r for ad, r in ROLLER.items() if ad not in mevcut]
    if not eksik:
        satir += ["Kutuphanedeki butun roller kadroda mevcut -- `kadro`",
                  "yoluna bu iste gerek yok."]
        return "\n".join(satir)

    satir += [f"Kadroda OLMAYAN, onerebilecegin {len(eksik)} rol:", ""]
    # KATEGORIYE GORE GRUPLA, `ROLLER` sirasina gore DEGIL.
    # Sozluk sirasi, sonradan eklenen rolleri sona koyuyor ve ayni
    # kategori BIRDEN FAZLA kez basiliyordu ("YAZILIM" iki kez). Iki
    # kez gorunen bir baslik, okuyana "burada bir hata var" dedirtir --
    # yanlis gosteren bir gosterge, gostergesizlikten kotudur.
    for kategori in kategoriler():
        bu = [r for r in eksik if r.kategori == kategori]
        if not bu:
            continue
        satir.append(f"  {kategori}")
        for r in bu:
            ozet = r.ozet[:LIDER_OZET_HARF].rstrip()
            if len(r.ozet) > LIDER_OZET_HARF:
                ozet += "..."
            satir.append(f"    `{r.ad}` -- {ozet}")
    satir += [
        "",
        "Bu liste yalnizca GORMEN icin. Rol eksik diye ajan onermek",
        "YANLISTIR: kalabalik kadro ~15 kat jeton yakar (Yasa 2) ve",
        "her yeni ajan senin limitinden yer. `kadro` yolunu ancak isin",
        "GEREKTIRDIGI rol kadroda yoksa sec; var olan bir ajan isi",
        "yapabiliyorsa `dagit` de.",
        "",
        "Onermek ise almak DEGILDIR: sen onerirsin, patron onaylar,",
        "ofis ise alir. Uydurma rol adi REDDEDILIR -- yalnizca yukaridaki",
        "adlardan sec.",
    ]
    return "\n".join(satir)
