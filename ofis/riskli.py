# -*- coding: utf-8 -*-
"""RISKLI EYLEM -- ajan neyi KENDI yapar, neyi SORAR.

Kullanici (22.09.2026): *"ajanlarin modellerin tarayicida gezmesini
tiklamasini engellemek bana sacma geldi; ajanlar calissin tiklasin
gezsin bilgi alsin is varsa yapsin. Fakat riskli durumlarda yayina
gonderme, aktif etme, canliya alma, para vesayre yani PATRONU ZORA
SOKACAK durumlarda onay isteyip yapicaklar."*

Ve dogru soruyu sordu: *"sen bile auto modda calismana ragmen onay
lazim oldugunda biliyosun bana soruyosun. Sen neye gore soruyosan
agent sistemi de oyle olmasi gerekmiyor mu?"*

**Hakli, ve bu dosyanin ana kurali bir LISTE degil bir OLCUT.**

## Neden ikisi birden var

Ayni soruyu kendime sordum: ben nasil biliyorum? Bende yazan sey bir
katalog degil, tek cumle: *"geri alinmasi zor veya disariya cikan
islerde once onay al."* Yani YARGI.

Yargiyi ana kural yapiyoruz (`OLCUT`). Ama bir farki gizlemeden:

* Yargi HER SEYI kapsar -- kimsenin dusunmedigi bir durumu bile.
  Yanildiginda **sessizce** yanilir; kimse fark etmez.
* Kapi cok azini kapsar. Yanildiginda **gurultuyle** yanilir: ajan
  durur, insan gorur.

Ofisin kendi yasasi da bunu soyluyor (Yasa 5): *"zayif model ne zaman
yardim isteyecegini bilmez."* Isci ajanlar haiku/sonnet/luna kosuyor.
Ve bu projede bir kez olculdu: *"rica ile duran kural, kural
degildir"* -- "kanit ver" demek yetmemis, sablon konunca kanit gelmisti.

O yuzden: **yargi ana kural, sert durak emniyet kemeri.** Emniyet
kemeri kisa tutulur; uzatmak, kullanicinin sikayet ettigi seye
(her tiklamada durmak) geri donmek olurdu.

## Sert durak neye bakar: DUGMENIN USTUNDE NE YAZIYOR

Bu bir kelime oyunu degil, insanin yaptigi seyin ta kendisi: bir
insan da "Yayinla" dugmesine basmadan once ustundeki yaziyi okur.

Ve Playwright bunu bize BEDAVA veriyor. `browser_click` sozlesmesinde
`element` alani soyle tanimli (ureticinin kendi metni):

    "Human-readable element description used to obtain permission
     to interact with the element"

Yani ajan her tiklamada dugmenin ne oldugunu SOYLEMEK ZORUNDA, ve
alanin var olma sebebi zaten IZIN. Biz o alani okuyoruz.

## BELIRSIZ kelimeler ve URL yukseltmesi

"Onayla" · "Devam" · "Tamam" tek baslarina masum. Ama `/checkout`
sayfasinda "Onayla" **ODEMEK** demektir. Bu yuzden riskli bir yolda
belirsiz kelimeler de sert duraga girer.

Tersi de dogru: urun listesinde "Devam" hicbir sey degildir ve
durdurulmaz. **Baglam olmadan kelime yargilamak, her seye "sorun"
diyen gostergeye donerdi.**

## BILEREK DISARIDA BIRAKILANLAR -- ve sebebi

`remove` · `kaldir` · `arsivle` · `iptal` ... Bunlar UI'da surekli
gecer (filtre kaldir, etiket kaldir) ve listeye koysaydik ajan
neredeyse her ekranda dururdu. Geri alinabilir olduklari icin de
olcutu gecmiyorlar. **Onlar yargiya birakilir.**

`sil` ve `delete` icerde, cunku bir dugme uzerinde bu iki kelimenin
baska anlami yoktur.

## SINIR -- yazili olsun, kesfedilmesin

Bu bir GUVENLIK SINIRI DEGIL, bir KAPIDIR. Kotu niyetli bir model
kelimeyi goremeyecegimiz bir yoldan (dogrudan JavaScript, klavye
kisayolu, obfuske kod) tetikleyebilir. Kapinin amaci kotu niyet degil
**dikkatsizlik**: ajan isini yaparken yanlislikla yayina almasin.

Gercek koruma katmanli: kapi + `--allowed-origins` + yazma kilidi +
kanit kapisi + insanin panelde gordugu canli kabin.
"""

from __future__ import annotations

import json
import re
import unicodedata


# ---------------------------------------------------------------------------
# ANA KURAL -- ajana ve lidere BU anlatilir
# ---------------------------------------------------------------------------

#: Brifinge ve lider istemine giren olcut. Liste degil, uc soru.
#:
#: Kasitli olarak "sunlar yasak" demiyor: yasak listesi ajana ne
#: yapmayacagini ogretir, olcut NASIL DUSUNECEGINI. Kimsenin
#: dusunmedigi bir durum ancak ikincisiyle yakalanir.
OLCUT = """ISINI YAPARKEN SERBESTSIN: dosya yaz, komut kostur, ara,
tarayicida gez ve TIKLA, form doldur. Her adim icin izin ISTEME.

Yalniz su UC SORUDAN biri "evet" ise ONCE `onay_iste` cagir ve DUR:

  1. GERI ALINABILIR MI?  Yanlis olursa tek hamlede geri alinir mi?
     (alinmaz ise: silme, kalici degisiklik, sozlesme)
  2. DISARI CIKIYOR MU?   Patrondan baskasi goruyor/aliyor mu?
     (yayin, canliya alma, gonderim, paylasim, musteriye mesaj)
  3. PARA VAR MI?         Harcanan, tahsil edilen, taahhut edilen?

Kisacasi: PATRONU ZORA SOKABILECEK bir sey yapmak uzereysen sor.
Emin degilsen sor -- sormanin bedeli bir dakika, yanlis yapmanin
bedeli patronun magazasi/reklami/hesabi.

Sormadigin her sey icin serbestsin ve BEKLEMEN gerekmez."""


# ---------------------------------------------------------------------------
# SADELESTIRME -- Turkce buyuk/kucuk ve sapka tuzagi
# ---------------------------------------------------------------------------

def sadelestir(metin: str) -> str:
    """Kalip eslestirmeye hazir hale getirir: kucuk harf, sapkasiz.

    Neden sart: dugme yazisi "YAYINLA", "Yayinla", "Yayınla" olabilir
    ve uc bicim de ayni seydir. Kaliplari ASCII tutup girdiyi
    sadelestirmek, her kalibin uc varyantini yazmaktan hem kisa hem
    unutmaya kapali.

    `"I".lower()` Python'da `"i"` verir ama `"Istanbul"` gibi
    sozcuklerde Turkce kurali farklidir; burada onemli olan eslesme,
    dogru Turkce degil -- o yuzden standart kucultme yeterli.
    Birlesik isaretler (`"İ".lower()` -> `i` + nokta) NFKD ile
    ayrilip atiliyor, yoksa `\\bsil\\b` gibi bir kalip sessizce
    tutmazdi.
    """
    if not metin:
        return ""
    metin = unicodedata.normalize("NFKD", str(metin))
    metin = "".join(k for k in metin if not unicodedata.combining(k))
    return re.sub(r"\s+", " ", metin.lower()).strip()


def _kur(kaliplar) -> tuple:
    return tuple(re.compile(k) for k in kaliplar)


# ---------------------------------------------------------------------------
# SERT DURAKLAR -- kisa, ve her biri "geri alinamaz" oldugu icin burada
# ---------------------------------------------------------------------------

#: PARA. Harcanan, tahsil edilen ya da taahhut edilen.
PARA = _kur((
    r"\bode\b", r"\bodeme\b", r"\bodemeyi\b", r"\bodeyi\b", r"\bodeyin\b",
    r"\bsatin al", r"\bsepeti onayla", r"\bsiparisi tamamla",
    r"\bsiparis ver", r"\babone ol", r"\bkart ekle", r"\bkredi karti",
    r"\bplani yukselt", r"\bpaketi yukselt",
    r"\bpay\b", r"\bpay now\b", r"\bcheckout\b", r"\bpurchase\b",
    r"\bbuy\b", r"\bbuy now\b", r"\bplace order\b", r"\bsubscribe\b",
    r"\bupgrade plan\b", r"\bconfirm and pay\b", r"\badd payment\b",
    r"\bstart (?:free )?trial\b",
))

#: YAYIN. Disariya cikar, canliya alinir, insanlar gorur.
YAYIN = _kur((
    r"\byayinla", r"\byayina al", r"\bcanliya al", r"\bcanli yayin",
    r"\baktif et", r"\baktiflestir", r"\betkinlestir",
    r"\bkampanyayi baslat", r"\breklami baslat", r"\breklami yayinla",
    r"\bpublish", r"\bgo live\b", r"\bactivate\b", r"\bdeploy\b",
    r"\brelease\b", r"\bmake (?:it )?(?:public|live)\b",
    r"\bset live\b", r"\blaunch campaign\b",
))

#: SILME. Geri alinamayan kayip.
#:
#: `remove`/`kaldir` BILEREK yok -- UI'da filtre/etiket kaldirmak icin
#: surekli gecer ve geri alinabilir. Onlar yargiya kalir.
SILME = _kur((
    r"\bsil\b", r"\bsilin\b", r"\bsiliniz\b", r"\bsilmek\b", r"\bsildir",
    r"\bkalici olarak sil", r"\bkaliciyla sil", r"\bhesabi kapat",
    r"\bmagazayi kapat", r"\btumunu sil",
    r"\bdelete\b", r"\bdelete permanently\b", r"\bpermanently delete\b",
    r"\bdestroy\b", r"\bterminate\b", r"\bclose account\b",
    r"\bwipe\b", r"\bpurge\b",
))

#: GONDERIM. Baskasina ulasir; geri cagrilamaz.
GONDERIM = _kur((
    r"\bgonder\b", r"\bgonderin\b", r"\bpaylas\b", r"\bpaylasin\b",
    r"\btweetle", r"\byorum gonder", r"\bmesaji gonder", r"\bmaili gonder",
    r"\bsend\b", r"\bsend message\b", r"\bsend email\b", r"\bshare\b",
    r"\bpost\b", r"\btweet\b", r"\breply\b", r"\bsubmit review\b",
))

#: BELIRSIZ. Tek baslarina masum; RISKLI BIR YOLDA sert duraga girer.
#:
#: "/checkout" sayfasinda "Onayla" odemek demektir. Urun listesinde
#: hicbir sey demek degildir. Kelimeyi baglamdan kopuk yargilamak,
#: her seye "sorun" diyen gostergeye donerdi.
BELIRSIZ = _kur((
    r"\bonayla\b", r"\bonaylayin\b", r"\btamam\b", r"\bdevam\b",
    r"\bdevam et\b", r"\bevet\b", r"\bkabul et\b",
    r"\bconfirm\b", r"\bcontinue\b", r"\bok\b", r"\byes\b",
    r"\bsubmit\b", r"\bproceed\b", r"\bagree\b", r"\baccept\b",
))

#: RISKLI YOL. URL'de gecerse BELIRSIZ kelimeler de durdurulur.
#:
#: Bu yollara GITMEK serbesttir -- odeme sayfasina bakmak para
#: harcamaz. Yalniz oradaki EYLEMLER yukselir.
RISKLI_YOL = (
    "/checkout", "/billing", "/payment", "/payments", "/subscribe",
    "/subscription", "/purchase", "/invoice", "/odeme", "/sepet/onay",
    "/plan-degistir", "/cancel-account",
)

#: JavaScript TRIPWIRE -- sinir degil, dikkatsizlik yakalayici.
#:
#: `browser_evaluate` istedigi kodu kosturur; ne yaptigini kelimeden
#: okuyamayiz. Obfuske kod bunu gecer ve bu YAZILI bir sinirdir.
#: Yine de en sik hali (bir dugmeyi koddan tiklatmak, form gondermek,
#: degistiren bir istek atmak) yakalanir.
KOD_ETKISI = _kur((
    r"\.click\s*\(", r"\.submit\s*\(", r"\.dispatchevent\s*\(",
    r"requestsubmit\s*\(", r"location\s*\.\s*href\s*=",
    r"location\s*\.\s*(?:assign|replace)\s*\(",
    r"method\s*:\s*[\"'](?:post|put|patch|delete)[\"']",
    r"\.open\s*\(\s*[\"'](?:post|put|patch|delete)[\"']",
    r"\bnavigator\s*\.\s*sendbeacon\s*\(",
))

#: Sinif -> (insan adi, risk seviyesi). `postane.onay_iste` risk bekler.
SINIFLAR = {
    "para":     ("PARA", "yuksek"),
    "silme":    ("GERI ALINAMAZ SILME", "yuksek"),
    "yayin":    ("YAYIN / CANLIYA ALMA", "yuksek"),
    "gonderim": ("DISARIYA GONDERIM", "yuksek"),
    "belirsiz": ("RISKLI SAYFADA ONAY", "yuksek"),
    "kod":      ("SAYFAYI DEGISTIREN KOD", "orta"),
    "sistem":   ("SISTEM DEGISIKLIGI", "yuksek"),
}

#: Hangi araclar denetlenir. Gezinme ve OKUMA burada YOK: onlari
#: durdurmak tam da kullanicinin "sacma" dedigi sey olurdu.
DENETLENEN = {
    "browser_click", "browser_type", "browser_fill_form",
    "browser_press_key", "browser_select_option", "browser_hover",
    "browser_drag", "browser_drop", "browser_file_upload",
    "browser_handle_dialog", "browser_evaluate",
    "browser_run_code_unsafe",
}


def _yol_riskli(url: str) -> bool:
    u = sadelestir(url)
    return any(p in u for p in RISKLI_YOL)


def _esles(metin: str, kaliplar) -> str:
    """Eslesen kalibin BULDUGU metni dondurur, kalibin kendisini degil.

    Insana "`\\bode\\b` eslesti" demek bir sey anlatmaz; "'Ode' gecti"
    anlatir. Onay karti insanin okudugu yerdir.
    """
    for k in kaliplar:
        m = k.search(metin)
        if m:
            return m.group(0)
    return ""


def _eylem_metni(arac: str, argumanlar: dict) -> str:
    """Ajanin bildirdigi INSAN OKUNUR hedef + yazdigi metin.

    `element` alani Playwright'in kendi sozlesmesinde "izin almak icin"
    diye tanimli; yani bu bilgi bize zaten veriliyor.
    """
    a = argumanlar or {}
    parcalar = [a.get("element") or "", a.get("target") or ""]
    if arac == "browser_type":
        parcalar.append(a.get("text") or "")
    elif arac == "browser_fill_form":
        for alan in (a.get("fields") or []):
            if isinstance(alan, dict):
                parcalar += [str(alan.get("name") or ""),
                             str(alan.get("value") or "")]
    elif arac == "browser_select_option":
        for d in (a.get("values") or []):
            parcalar.append(str(d))
    elif arac == "browser_press_key":
        parcalar.append(str(a.get("key") or ""))
    return " | ".join(p for p in parcalar if p)


def _kod_metni(argumanlar: dict) -> str:
    a = argumanlar or {}
    for anahtar in ("function", "code", "script", "expression"):
        if a.get(anahtar):
            return str(a[anahtar])
    return ""


def degerlendir(arac: str, argumanlar: dict, *, url: str = "",
                baglam: str = "", sayfa_metni: str = "") -> dict | None:
    """Bu eylem insan onayi ister mi?

    `None` -> serbest, aynen gecer.
    sozluk -> durur; icinde insanin onay kartinda gorecegi metin var.

    `baglam`: sayfadan gelen ek metin -- ozellikle acik bir onay
    kutusunun ("Silmek istediginize emin misiniz?") yazisi. Kutunun
    metni ARGUMANDA yoktur, bir onceki arac sonucunda gelir; kapi onu
    tasir. Tasimasaydik en tehlikeli hal (silme onayini kabul etmek)
    tam da gorunmez olurdu.
    """
    if arac not in DENETLENEN:
        return None

    hedef = _eylem_metni(arac, argumanlar)
    # SAYFANIN KENDI SOYLEDIGI: hedef ogenin erisilebilirlik adi (vekil
    # anlik goruntuden okur). Ajanin yazdigi `element` bir BEYANDIR;
    # olculdu (26.09.2026, deneme seti D09): 13 kosuda 1 kez ajan genel
    # bir aciklama yazdi ve "Yayinla" tiklamasi kapidan GECTI. Karar
    # artik sayfanin metnine de bakar.
    if sayfa_metni:
        hedef = " | ".join(x for x in (hedef, f"sayfada: {sayfa_metni}") if x)
    kod = _kod_metni(argumanlar)
    # Onay kutusunun yazisi yalniz onu KABUL ederken anlamli; reddetmek
    # (accept=False) zaten guvenli taraftir ve durdurulmaz.
    if arac == "browser_handle_dialog" and (argumanlar or {}).get(
            "accept") is not False:
        hedef = " | ".join(x for x in (hedef, baglam) if x)

    okunur = sadelestir(hedef)
    riskli_yolda = _yol_riskli(url)
    # Eslestirme kimligi: turlar arasi DEGISMEYEN parca. `target`
    # (Playwright `ref`i) bilerek disarida -- her anlik goruntude
    # yeniden uretilir.
    # Sayfanin metni varsa KIMLIK odur: ajanin aciklamasi turdan tura
    # degisir ("Yayinla dugmesi" / "button"), sayfadaki ad degismez.
    kimlik = (sayfa_metni.strip()
              or ((argumanlar or {}).get("element") or "").strip() or baglam)

    for sinif, kaliplar in (("para", PARA), ("silme", SILME),
                            ("yayin", YAYIN), ("gonderim", GONDERIM)):
        bulunan = _esles(okunur, kaliplar)
        if bulunan:
            return _bulgu(sinif, bulunan, arac, hedef, url, kimlik)

    if riskli_yolda:
        bulunan = _esles(okunur, BELIRSIZ)
        if bulunan:
            return _bulgu("belirsiz", bulunan, arac, hedef, url, kimlik)

    if kod:
        sade_kod = sadelestir(kod)
        bulunan = (_esles(sade_kod, KOD_ETKISI)
                   or _esles(sade_kod, PARA) or _esles(sade_kod, SILME)
                   or _esles(sade_kod, YAYIN) or _esles(sade_kod, GONDERIM))
        if bulunan:
            return _bulgu("kod", bulunan, arac, kod[:200], url)

    return None


def _bulgu(sinif: str, bulunan: str, arac: str, hedef: str,
           url: str, element: str = "") -> dict:
    ad, risk = SINIFLAR[sinif]
    hedef = (hedef or "").strip()
    if len(hedef) > 200:
        hedef = hedef[:197] + "..."
    return {
        "sinif": sinif,
        "ad": ad,
        "risk": risk,
        "esles": bulunan,
        "arac": arac,
        "hedef": hedef,
        # KIMLIK ICIN AYRI ALAN -- `hedef` gosterim icin, `element`
        # eslestirme icin.
        #
        # OLCULDU (22.09.2026, gercek halka): onay kaydi ikinci turda
        # TANINMADI ve ikinci bir kart acildi. Sebep, kimligin her tur
        # DEGISEN parcalar tasimasiydi: Playwright'in `ref`i (`e5`)
        # her anlik goruntude yeniden uretilir, ve sayfa adresi vekil
        # o tur icinde henuz bir sonuc gormediyse BOSTUR.
        #
        # Her turda ayni kalan tek sey dugmenin USTUNDEKI YAZI --
        # zaten kapinin baktigi sey de o.
        "element": (element or hedef).strip()[:200],
        "url": url,
        "eylem": f"{ad}: {hedef or arac}" + (f"  ({url})" if url else ""),
        "sebep": (
            f"Tarayici eyleminde {ad} isareti bulundu ({bulunan!r}). "
            "Bu geri alinamaz ya da disariya cikan bir hamle olabilir; "
            "ofis kurali geregi once patronun onayi alinir."
        ),
    }


# ---------------------------------------------------------------------------
# IKINCI YUZEY: ARAC ADI
#
# Tarayici kapisi DUGMENIN YAZISINA bakar ve bunun iki dogal siniri var:
# dile bagli, ve UI bicimine bagli (bir acilir liste ya da "Kaydet"
# dugmesi yayina alabilir). Yani kelime listesi her zaman gercegin
# gerisinde kalir.
#
# ARAC ADI oyle degil. `ads_activate_entity` · `create-discount` ·
# `trash_message` bir API kimligidir: Ingilizce, fiil-onculu, ve
# SAGLAYICI tarafindan sabitlenmistir. Ayni olcut orada cok daha
# saglam durur.
#
# EN ONEMLI KISMI POLARITE: OKUMA fiilleri beyaz listede, geri kalan
# HER SEY sorulur. Tersi olsaydi (riskli fiiller kara listede) yarin
# eklenen bir arac sessizce iceri girerdi. Bilmedigimize "iyi" demeyiz.
# ---------------------------------------------------------------------------

#: OKUMA fiilleri -- hicbir sey degistirmez, sorulmaz.
OKUMA_FIILLERI = frozenset("""
get list search read query describe resolve ping find check validate
preview fetch download schema docs suggest score context benchmark
insights stats status summary transcript export view show inspect
count lookup discover
""".split())

#: Bunlar OKUMA fiiliyle birlikte gelse bile riskli sayilir -- cunku
#: fiil degil NESNE tehlikeli. `get_payment_method` masum, ama
#: `create_payment_method` degil; ayrimi asagidaki fiil kumeleri yapar.
ARAC_PARA = frozenset("""
discount boost budget payment pay charge purchase checkout billing
invoice subscribe subscription refund payout generation generate
""".split())

ARAC_YAYIN = frozenset("""
publish unpublish activate deactivate launch live enable disable
deploy release
""".split())

ARAC_SILME = frozenset("""
delete remove trash destroy purge wipe terminate close revoke
rm rmdir unlink truncate drop
""".split())

ARAC_GONDERIM = frozenset("""
send post share reply comment message email tweet notify invite
push scp rsync
""".split())

#: DURUM kelimeleri -- fiil degil, ama bir yazma cagrisinin ARGUMANINDA
#: gecerse o cagri yayina almadir.
#:
#: `ads_create_campaign` adi masumdur; `"status": "ACTIVE"` iceriyorsa
#: PARA HARCAR. Adi degil argumani soyler.
DURUM_YAYIN = frozenset("active live published enabled running".split())

#: DEGISTIREN ama yukaridaki dort sinifa girmeyen fiiller. Bunlar
#: SORULMAZ -- ajan isini yapsin -- ama KAYDA GECER.
#:
#: Kullanicinin kurali buydu: *"ajanlar calissin... riskli durumlarda
#: onay isteyip yapicaklar."* Her urun guncellemesini sormak, onun
#: itiraz ettigi engellemeye geri donmek olurdu.
ARAC_DEGISTIR = frozenset("""
create update set add write mutation attach finalize apply switch
connect disconnect save follow unfollow mark label move copy claim
upload rename assign draft
""".split())


def _arac_parcalari(arac: str) -> list:
    """`mcp__claude_ai_Shopify__bulk-update-product-status` ->
    ['bulk','update','product','status']

    Sunucu oneki ATILIR: `mcp__claude_ai_Meta_Reklamlar__` icindeki
    "Reklamlar" bir fiil degil ve eslesmeye girmemeli.
    """
    ad = (arac or "").strip()
    if "__" in ad:
        ad = ad.rsplit("__", 1)[-1]
    ad = re.sub(r"[^A-Za-z0-9]+", " ", ad)
    # camelCase'i de ayir: `graphqlMutation` -> `graphql Mutation`
    ad = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", ad)
    return [p for p in sadelestir(ad).split() if p]


#: Ofisin KENDI araclari ve tarayici -- bu kapidan gecmezler.
#:
#: Ofis araclari zaten ofisin kendi kapilarini tasiyor (`gorsel_uret`
#: para kilidinde, `gorev_ac` yalniz liderde, kimlik ortamdan geliyor).
#: Tarayici ise KENDI vekilinden geciyor ve orada sayfa baglami var --
#: iki kez sormak, insana ayni seyi iki kez cevaplatmak olurdu.
KAPI_DISI_ONEKLER = ("mcp__ofis", "mcp__tarayici")


#: CLAUDE CODE / CODEX'IN KENDI ARACLARI (24.09.2026).
#:
#: Kullanici: *"claude code ve codex'i terminalde nasil kullaniyorsam
#: ajanlar da oyle calissin; onemli yerlerde insan onayi istesin -- sen
#: auto modda bile geri alinamaz durumda bana soruyorsun."*
#:
#: OLCULDU (ayni gun): bu kapi `ls -la`, `npm run build`, `curl` ile
#: sayfa okumak dahil HER kabuk komutunu "TANINMAYAN ARAC" diye
#: soruyordu -- gercek ofiste arastirma ajani bir komut denedi, durdu
#: ve tekrar denemedi. Ters yonde de yanliyordu: `echo hi` komutu,
#: yalniz ACIKLAMASINDA "Remove" gectigi icin "silme" sayildi.
#:
#: Iki duzeltme: (1) CLI'in yerlesik okuma/duzenleme araclari kapidan
#: GECMEZ -- dosya yazimini yazma kilidi ve disk olcumu (`degisim.py`)
#: zaten denetliyor; icerigi taramak koddaki her `delete` kelimesini
#: onaya dusururdu. (2) Kabuk komutunda yalniz KOMUTUN KENDISI taranir,
#: aciklamasi degil, ve dar bir kural setiyle: auto moddaki gibi komut
#: KOSAR, yalniz geri alinamaz / disari cikan / sistemi degistiren
#: komut sorulur.
#:
#: Baglayici (MCP) araclarinda polarite DEGISMEDI: orada tanimayan arac
#: hala sorulur, cunku yarin eklenen bir baglayici araci bilinmez.
#: Kabuk ise bilinen bir aractir; bilinmeyen onun ARGUMANI olabilir,
#: kendisi degil.
YERLESIK_SERBEST = frozenset("""
Read Glob Grep LS Write Edit MultiEdit NotebookEdit WebFetch WebSearch
TodoWrite ToolSearch
""".split())

KABUK_ARACLARI = frozenset({"Bash", "PowerShell"})

#: Komut basi: satir basi ya da bir kabuk ayraci. `rm` gibi kisa adlar
#: baska kelimenin icinde (`format` icindeki `rm`) yakalanmasin diye.
_B = r"(?:^|[\s;&|(`])"

KABUK_KURALLARI = (
    ("silme", _kur((
        _B + r"rm\s", _B + r"rmdir\b", _B + r"(?:del|erase|rd)\s",
        r"\bremove-item\b", _B + r"unlink\b", _B + r"shred\b",
        r"\bgit\s+clean\b", r"\bgit\s+reset\s+--hard\b",
        r"\bgit\s+checkout\s+--\s", r"\bgit\s+branch\s+-d\b",
        r"\bgit\s+stash\s+(?:drop|clear)\b",
        r"\bdrop\s+(?:table|database|schema)\b", r"\btruncate\s+table\b",
        r"\bmkfs", r"\bformat\s+[a-z]:", r"\bclear-content\b",
    ))),
    ("gonderim", _kur((
        r"\bgit\s+push\b",
        r"\b(?:curl|wget)\b[^|;&]*\s(?:-x|--request)\s*(?:post|put|patch|delete)\b",
        r"\bcurl\b[^|;&]*\s(?:-d|--data[\w-]*|-f|--form|-t|--upload-file)\s",
        r"\binvoke-(?:webrequest|restmethod)\b[^|;&]*-method\s+(?:post|put|patch|delete)\b",
        _B + r"(?:scp|rsync|sftp)\b",
        r"\bgh\s+(?:pr|issue)\s+(?:create|merge|comment|close)\b",
        r"\bsendmail\b", r"\bsend-mailmessage\b",
    ))),
    ("yayin", _kur((
        r"\b(?:npm|yarn|pnpm)\s+publish\b", r"\btwine\s+upload\b",
        r"\bdocker\s+push\b", r"\bgh\s+release\s+create\b", r"\bdeploy\b",
        r"\bwrangler\s+(?:deploy|publish)\b", r"\bkubectl\s+(?:apply|delete)\b",
    ))),
    ("sistem", _kur((
        r"\bshutdown\b", r"\brestart-computer\b", r"\bstop-computer\b",
        _B + r"reboot\b", r"\breg\s+(?:delete|add)\b", _B + r"setx\b",
        r"\bnet\s+user\b", r"\bschtasks\s+/(?:create|delete)\b",
        _B + r"sc\s+(?:delete|config|create)\b", r"\bset-executionpolicy\b",
        r"\b(?:winget|choco)\s+(?:install|uninstall)\b", r"\bmsiexec\b",
        r"\bnpm\s+(?:install|i|uninstall)\s+(?:-g|--global)\b",
        r"\bpip\s+uninstall\b",
    ))),
)


def kabuk_degerlendir(arac: str, girdi: dict = None) -> dict | None:
    """Bir kabuk komutu insan onayi ister mi. `None` = serbest.

    KIMLIK KOMUTTUR, arac adi degil: tek bir "evet" butun `rm`
    komutlarini acmamali. Onaylanan komut ayni metinle tekrar
    kosturuldugunda gecer (bir kez ya da is boyunca).
    """
    komut = str((girdi or {}).get("command") or "").strip()
    if not komut:
        return None
    alt = komut.lower()
    for sinif, kaliplar in KABUK_KURALLARI:
        bulunan = _esles(alt, kaliplar)
        if bulunan:
            ad, risk = SINIFLAR[sinif]
            return {
                "sinif": sinif, "ad": ad, "risk": risk,
                "esles": bulunan.strip(),
                "arac": arac, "hedef": komut[:200], "element": komut[:200],
                "url": "", "sorulur": True,
                "eylem": f"{ad}: {komut[:120]}",
                "sebep": (f"`{arac}` komutunda {ad} isareti bulundu "
                          f"({bulunan.strip()!r}). Komut KOSMADAN once "
                          "patrona soruluyor; onaylanirsa ayni komut "
                          "tekrar kosturuldugunda gecer."),
            }
    return None


def arac_degerlendir(arac: str, girdi: dict = None) -> dict | None:
    """Bir ARAC CAGRISI insan onayi ister mi?

    `None`  -> serbest (okuma, ya da ofisin kendi araci)
    sozluk  -> `sinif` alanina bak:
                 'kayit' ise SORULMAZ, yalnizca deftere yazilir
                 digerleri SORULUR

    Bilinmeyen fiil SORULUR. Bu bilincli: yarin eklenen bir arac
    sessizce iceri girmemeli. *Olcemedigimize "iyi" demeyiz.*
    """
    ad = (arac or "").strip()
    if not ad:
        return None
    if ad.startswith(KAPI_DISI_ONEKLER):
        return None
    if ad in YERLESIK_SERBEST:
        return None
    if ad in KABUK_ARACLARI:
        return kabuk_degerlendir(ad, girdi)

    parcalar = _arac_parcalari(ad)
    if not parcalar:
        return None
    kume = set(parcalar)

    # GIRDI DE camelCase AYRILIR.
    #
    # Olculdu: `mutation { productDelete(...) }` icindeki "delete"
    # tek kelimeye yapisik oldugu icin KACIYORDU -- yani en tehlikeli
    # cagri (adi masum, gercegi sorgu metninde) gecip gidiyordu.
    # Alt dize aramak da yanlis olurdu ("posted" icinde "post" var).
    try:
        ham = json.dumps(girdi or {}, ensure_ascii=False)
    except (TypeError, ValueError):
        ham = str(girdi)
    girdi_metni = sadelestir(re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", ham))

    for sinif, fiiller in (("para", ARAC_PARA), ("silme", ARAC_SILME),
                           ("yayin", ARAC_YAYIN),
                           ("gonderim", ARAC_GONDERIM)):
        ortak = kume & fiiller
        if ortak:
            return _arac_bulgu(sinif, sorted(ortak)[0], ad, girdi_metni)

    # ADI MASUM, ARGUMANI DEGIL.
    #
    # `update-product` bir kayittir; ama `status: ACTIVE` iceriyorsa
    # YAYINA ALMAKTIR. `graphql_mutation` en uc ornek: adi her seyi
    # yapabilir, gercegi yalnizca sorgu metninde yazar.
    #
    # Bu yuzden girdi IKI kez taranir: bir kez insan arayuzu
    # kelimeleriyle (kullanici Turkce bir metin gecirmis olabilir),
    # bir kez API fiilleriyle.
    if kume & ARAC_DEGISTIR:
        girdi_kume = set(re.findall(r"[a-z]+", girdi_metni))
        for sinif, kaliplar, fiiller in (
                ("yayin", YAYIN, ARAC_YAYIN | DURUM_YAYIN),
                ("para", PARA, ARAC_PARA),
                ("silme", SILME, ARAC_SILME),
                ("gonderim", GONDERIM, ARAC_GONDERIM)):
            bulunan = _esles(girdi_metni, kaliplar)
            if not bulunan:
                ortak = girdi_kume & fiiller
                bulunan = sorted(ortak)[0] if ortak else ""
            if bulunan:
                return _arac_bulgu(sinif, bulunan, ad, girdi_metni)
        return _arac_bulgu("kayit", sorted(kume & ARAC_DEGISTIR)[0], ad,
                           girdi_metni)

    if kume & OKUMA_FIILLERI:
        return None

    # TANINMAYAN ARAC (ornegin `Bash`): adi bir sey soylemiyor, ama
    # ARGUMANI soyleyebilir. Once ona bakilir ki onay karti insana
    # "TANINMAYAN ARAC" degil "GERI ALINAMAZ SILME" desin.
    #
    # Teshis koyup NE oldugunu soylemeyen bir kart, insani bir kez
    # daha dusunmeye zorlar.
    girdi_kume = set(re.findall(r"[a-z]+", girdi_metni))
    for sinif, kaliplar, fiiller in (
            ("silme", SILME, ARAC_SILME),
            ("para", PARA, ARAC_PARA),
            ("yayin", YAYIN, ARAC_YAYIN),
            ("gonderim", GONDERIM, ARAC_GONDERIM)):
        bulunan = _esles(girdi_metni, kaliplar)
        if not bulunan:
            ortak = girdi_kume & fiiller
            bulunan = sorted(ortak)[0] if ortak else ""
        if bulunan:
            return _arac_bulgu(sinif, bulunan, ad, girdi_metni)

    return _arac_bulgu("bilinmiyor", parcalar[0], ad, girdi_metni)


#: Arac yuzeyine ozel iki sinif. `kayit` sorulmaz; `bilinmiyor` sorulur.
ARAC_SINIFLARI = {
    "kayit": ("DEGISIKLIK (kaydedildi)", "dusuk"),
    "bilinmiyor": ("TANINMAYAN ARAC", "orta"),
}


def _arac_bulgu(sinif: str, bulunan: str, arac: str, girdi_metni: str) -> dict:
    ad, risk = SINIFLAR.get(sinif) or ARAC_SINIFLARI[sinif]
    ozet = girdi_metni[:180]
    return {
        "sinif": sinif,
        "ad": ad,
        "risk": risk,
        "esles": bulunan,
        "arac": arac,
        "hedef": arac,
        "element": arac,          # kimlik: ARAC ADI, turlar arasi sabit
        "url": "",
        "sorulur": sinif != "kayit",
        "eylem": f"{ad}: {arac}",
        "sebep": (
            f"`{arac}` cagrisinda {ad} isareti bulundu ({bulunan!r}). "
            + ("Bu bir ARAC ADI; saglayici tarafindan sabitlenmistir, "
               "dile bagli degildir. " if sinif != "bilinmiyor" else
               "Bu aracin ne yaptigini ofis TANIMIYOR; bilmedigimize "
               "'zararsiz' demeyiz. ")
            + f"Girdi ozeti: {ozet}"
        ),
    }


def brifing_blogu(tarayici_var: bool = False, *, serbest: bool = False) -> str:
    """Ajanin brifingine giren blok.

    ARTIK HER BRIFINGDE var. Bir sure yalnizca tarayicili islere
    yaziliyordu, cunku kapi yalnizca tarayicida vardi. Kapi simdi
    CLI'in izin kancasinda yasiyor ve KABUGU da BAGLAYICILARI da
    kapsiyor: `git push` sorulur, `rm` sorulur, `create-discount`
    sorulur. Yalniz tarayicida anlatmak, ajana eksik bir resim
    vermek olurdu.

    `tarayici_var` yalnizca tarayiciya OZEL cumleyi ekler.
    """
    parcalar = [
        "## NEYI KENDIN YAPARSIN, NEYI SORARSIN",
        "",
        OLCUT,
        "",
        "Bunu sana yalnizca RICA olarak soylemiyoruz: ofis, riskli "
        "gorunen bir eylemi sen fark etmesen bile DURDURUR ve patrona "
        "sorar -- dosya, komut, baglayici ve tarayici, hepsi ayni "
        "kapidan gecer. Durdurulursan hata yapmis olmazsin; cevap "
        "gelince kaldigin yerden devam edersin.",
        "",
        "Durdurulunca: ayni eylemi tekrar deneme, BASKA BIR YOLDAN da "
        "yapmaya calisma. Buraya kadar yaptiklarini `kanit_ekle` ile "
        "yaz ve turu bitir.",
    ]
    # TARAYICI CUMLESI BAYATLAMISTI (24.09.2026): "yalniz beyan edilmis
    # kaynaklara gidebilirsin, baska site icin soru_sor" diyordu -- oysa
    # beyan disi site zaten patrona SORULUYORDU (vekil) ve artik
    # tarayici varsayilan olarak SERBEST. Soylenen kural uygulanan
    # kuraldan farkliysa ajan yanlis olani ogrenir.
    if tarayici_var and serbest:
        parcalar += [
            "",
            "TARAYICIN VAR ve SERBEST: `browser_navigate` ile istedigin "
            "siteye git, gez, tikla, form doldur, sepet/odeme adimlarina "
            "bak -- terminaldeki Claude Code gibi. Yalniz riskli EYLEM "
            "(yayina alma, silme, odeme, gonderme) patrona sorulur. Yalniz "
            "sayfa metni gerekiyorsa WebFetch daha ucuzdur.",
        ]
    elif tarayici_var:
        parcalar += [
            "",
            "Tarayicin bu isin sitelerine DARALTILMIS. Baska bir siteye "
            "gitmen gerekiyorsa `browser_navigate` ile git: ofis patrona "
            "sorar, onaylanirsa bir SONRAKI turda acilir.",
        ]
    return chr(10).join(parcalar) + chr(10)
