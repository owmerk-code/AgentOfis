# -*- coding: utf-8 -*-
"""IZIN -- patronun SOYLEDIGI riskli is sorulmaz, SOYLEMEDIGI sorulur.

Kullanici (29.09.2026): *"git push, deploy yapmani istersem zaten ben
sana soyluyorum, onay verdigim icin yapiyorsun. Ama ben demeden git
push, deploy adimlarini bana sorarak yapiyorsun. Agent sistemimizde
nasil olacak?"*

Kural onun burada yasadiginin aynisi:

* sirada is (okumak, yazmak, test)  -> hic sorulmaz (`riskli.py`)
* patronun ACIKCA istedigi riskli is -> sorulmaz (BURASI)
* patronun istemedigi riskli is      -> sorulur (onay karti)

## Neden karar motorda degil ofiste

Olculdu (29.09): Claude'un Auto kipi ve Codex'in "Approve for me" kipi
gorev metnindeki "git push yap" cumlesini gordu ve push/rm/POST'u
SORMADAN yapti. Motor gorev metnini kimin yazdigini bilmez; ofis bilir.
Bir cumlenin PATRONUN sozu mu yoksa liderin yazdigi mi oldugunu
guvenle ayirabilen tek yer burasi.

## Uc emniyet -- izin YANLIS anlasilamasin

1. **Alinti kaniti.** Lider izni plan JSON'unda verir ama izin ancak
   patronun mesajinda KELIMESI KELIMESINE gecen bir alintiya dayanirsa
   kabul edilir. Lider izin UYDURAMAZ.
2. **Olumsuzluk kapisi.** Alintinin gectigi cumlecikte olumsuzluk varsa
   ("push etme", "pushlama", "sakin") izin VERILMEZ. Yanilmanin bedeli
   bir fazla soru olur, istenmeyen bir push degil.
3. **Dar.** Izin tek bir eylem deseni (`git push`) ve tek bir is icin.
   Is bitince biter. Desenin sinifi DESENIN KENDISINDEN olculur, liderin
   soyledigi siniftan degil.

## Her zaman sorulanlar -- patron "yap" dese bile

PARA ve GERI ALINAMAZ SILME (ve sifre alani, talimat suphesi, taninmayan
arac): hatanin bedeli geri donmuyor. Bu siniflara ne patronun sozu ne
kalici izin kapi acar.

## Kalici izin

Insan elle koyar ("bu projede `git push origin test` her zaman
serbest"). Ajan ve lider koyamaz. Silinmez, kaldirilir (gecmis okunur).
"""

from __future__ import annotations

import re
import uuid

from ofis import riskli
from ofis.db import simdi


class IzinHatasi(Exception):
    pass


#: Patronun sozuyle ya da kalici izinle ACILABILEN siniflar.
IZIN_VERILEBILIR = {
    "gonderim": "disariya gonderim (git push, veri gonderme)",
    "yayin": "yayina alma (deploy, publish)",
    "sistem": "sistem degisikligi (genel paket kurma vb.)",
}

#: Asla izinle gecmeyen siniflar -- ret metninde sebebi soylenir.
HER_ZAMAN_SORULUR = {
    "para": "PARA",
    "silme": "GERI ALINAMAZ SILME",
    "kimlik": "SIFRE / KIMLIK",
    "suphe": "TALIMAT SUPHESI SONRASI EYLEM",
    "belirsiz": "RISKLI SAYFADA ONAY",
    "kod": "SAYFAYI DEGISTIREN KOD",
    "bilinmiyor": "TANINMAYAN ARAC",
    # 30.09: kullanicinin kurali -- canli masaustu ve kendi tarayicisi
    # onaysiz surulmez; "tarayiciyi ac" demek masaustunu surme izni degil.
    "masaustu": "PATRONUN MASAUSTU / TARAYICISI",
}

#: Izin verilmis sinifta bile ZORLA/YIKICI bicim gecmez: "pushla" demek
#: "uzaktaki gecmisi ez" demek degildir.
YIKICI_BICIM = re.compile(
    r"--force\b|--force-with-lease\b|--mirror\b|--delete\b|--prune\b"
    r"|(?:^|\s)-f(?:\s|$)|(?:^|\s)\+\S+", re.IGNORECASE)

#: Olumsuzluk: alintinin gectigi cumlecikte bunlardan biri varsa izin YOK.
#: Turkce olumsuz fiil ekleri (-ma/-me ve cekimleri) + acik kelimeler.
#: Yanlis pozitif (izin verilmemesi) GUVENLI yondur: bir fazla soru.
_OLUMSUZ_KELIME = re.compile(
    r"\b(?:sakin|asla|degil|olmadan|yasak|hayir|dont|don t|not|never|no)\b")
_OLUMSUZ_EK = re.compile(
    r"\b\w{2,}(?:ma|me|mayin|meyin|mayiniz|meyiniz|mazsin|mezsin|madan|meden)\b")
#: Olumsuz eke benzeyen ama olumsuz OLMAYAN yaygin kelimeler.
_OLUMSUZ_DEGIL = frozenset(
    "sonra hemen once simdi tema sistem problem program forma firma "
    "platforma kamera tamam bekleme sormadan beklemeden sormaksizin "
    "danismadan".split())

_AYRAC = re.compile(r"[.;!?\n]|,|\bama\b|\bfakat\b|\bancak\b")

#: OLUMSUZ EK YALNIZ EYLEMDE sayilir (01.10.2026). Olculdu (gercek set G14):
#: "formu Ad: Deneme ... ile doldur ve gonder" -- "deneme" (-me) olumsuz
#: fiil sanildi, izin reddedildi, plan DUSTU. Turkcede -me/-ma ile biten isim
#: cok (deneme, dolma, cizme). Ekli kelime ancak KOKU bir EYLEMSE olumsuzdur:
#: bilinen riskli eylem kokleri ya da alintinin kendi kelimeleri.
_EYLEM_KOKLERI = frozenset(
    "push pushla deploy deployla gonder yolla yayinla yayimla sil kaydet "
    "yukle commit commitle et yap calistir kur ac bas tikla ode al sat "
    "paylas gonderil yayinlan".split())
_OLUMSUZ_EKLER = ("meyiniz", "mayiniz", "meyin", "mayin", "mezsin", "mazsin",
                  "meden", "madan", "me", "ma")


def _olumsuz_eylem_mi(kelime: str, alinti_kelimeleri: set) -> bool:
    for ek in _OLUMSUZ_EKLER:
        if kelime.endswith(ek) and len(kelime) - len(ek) >= 2:
            kok = kelime[:-len(ek)]
            return kok in _EYLEM_KOKLERI or kok in alinti_kelimeleri
    return False


def _jeton(metin: str) -> list:
    metin = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(metin or ""))
    return re.findall(r"[a-z0-9]+", riskli.sadelestir(metin))


def _kokler(jetonlar) -> list:
    """Jetonlar + Turkce MASTAR kokleri (`gondermek` -> `gonder`).

    01.10.2026 olculdu (gercek set G14, codex lider): izin "...bilgileriyle
    gondermek" yazildi; kalip yalniz `gonder` kokunu taniyordu, izin
    "riskli eylem tanimlamiyor" diye reddedildi, gonderim patrona soruldu.
    """
    cikti = []
    for j in jetonlar:
        cikti.append(j)
        if len(j) > 5 and j.endswith(("mek", "mak")):
            cikti.append(j[:-3])
    return cikti


def _ardisik_icerir(buyuk: list, kucuk: list) -> bool:
    if not kucuk:
        return False
    n = len(kucuk)
    return any(buyuk[i:i + n] == kucuk for i in range(len(buyuk) - n + 1))


def desen_sinifi(desen: str) -> str:
    """Desen hangi riskli sinifi tanimliyor -- ofis OLCER, lidere sormaz.

    Bos doner = desen tek basina riskli bir eylem tanimlamiyor
    (`git`, `npm`): boyle bir izin her seyi acardi, reddedilir.
    """
    desen = (desen or "").strip()
    if not desen:
        return ""
    k = riskli.kabuk_degerlendir("Bash", {"command": desen})
    if k:
        return k["sinif"]
    # Mastar kokleri de denenir: "gondermek" -> "gonder" kalibina uyar.
    sade = riskli.sadelestir(desen) + " " + " ".join(_kokler(_jeton(desen)))
    for sinif, kaliplar in (("para", riskli.PARA), ("silme", riskli.SILME),
                            ("yayin", riskli.YAYIN),
                            ("gonderim", riskli.GONDERIM)):
        if riskli._esles(sade, kaliplar):
            return sinif
    kume = set(_jeton(desen))
    for sinif, fiiller in (("para", riskli.ARAC_PARA),
                           ("silme", riskli.ARAC_SILME),
                           ("yayin", riskli.ARAC_YAYIN),
                           ("gonderim", riskli.ARAC_GONDERIM)):
        if kume & fiiller:
            return sinif
    return ""


def olumsuz_mu(patron_sozu: str, alinti: str) -> bool:
    """Alintinin gectigi CUMLECIKTE olumsuzluk var mi."""
    soz = riskli.sadelestir(patron_sozu)
    al = riskli.sadelestir(alinti)
    yer = soz.find(al)
    if yer < 0:
        return True
    bas = 0
    for m in _AYRAC.finditer(soz[:yer]):
        bas = m.end()
    son_m = _AYRAC.search(soz, yer + len(al))
    son = son_m.start() if son_m else len(soz)
    cumle = re.sub(r"[^a-z0-9 ]", " ", soz[bas:son])
    if _OLUMSUZ_KELIME.search(cumle):
        return True
    alinti_kelimeleri = set(re.sub(r"[^a-z0-9 ]", " ", al).split())
    for m in _OLUMSUZ_EK.finditer(cumle):
        if m.group(0) in _OLUMSUZ_DEGIL:
            continue
        if _olumsuz_eylem_mi(m.group(0), alinti_kelimeleri):
            return True
    return False


def dogrula(sinif_istenen: str, desen: str) -> str:
    """Desen izin verilebilir mi. Donen: olculen sinif. Degilse hata."""
    olculen = desen_sinifi(desen)
    if not olculen:
        raise IzinHatasi(
            f"'{desen}' tek basina riskli bir eylem tanimlamiyor; boyle bir "
            "izin her seyi acardi. Eylemi tam yaz (ornek: 'git push', "
            "'npm run deploy').")
    if olculen in HER_ZAMAN_SORULUR:
        raise IzinHatasi(
            f"'{desen}' bir {HER_ZAMAN_SORULUR[olculen]} eylemi. Bu sinif "
            "patron 'yap' dese bile HER SEFERINDE sorulur (hatanin bedeli "
            "geri donmuyor); izinle acilmaz.")
    if olculen not in IZIN_VERILEBILIR:
        raise IzinHatasi(f"'{desen}' ({olculen}) izinle acilabilen bir sinif degil.")
    if sinif_istenen and sinif_istenen != olculen:
        raise IzinHatasi(
            f"'{desen}' {olculen} sinifinda, {sinif_istenen} degil.")
    if YIKICI_BICIM.search(desen):
        raise IzinHatasi(
            f"'{desen}' yikici bir bicim iceriyor (--force, --delete...). "
            "Bu bicim izinle acilmaz, her seferinde sorulur.")
    return olculen


# -- defter -----------------------------------------------------------------

def tanimla(db, proje_id: str, *, desen: str, veren: str, kaynak: str,
            gorev_id: str = None, alinti: str = "", gerekce: str = "",
            sinif: str = "") -> dict:
    """Izin yaz. `kaynak`: 'patron_sozu' (gorev icin) | 'insan' (kalici
    ya da elle). Ajan ve lider KAYNAK olamaz: izin insandan gelir."""
    if kaynak not in ("patron_sozu", "insan"):
        raise IzinHatasi("Izin yalniz patronun sozunden ya da insandan gelir.")
    desen = re.sub(r"\s+", " ", (desen or "").strip())[:120]
    olculen = dogrula(sinif, desen)
    if gorev_id is None and not (gerekce or "").strip():
        raise IzinHatasi("Kalici izin GEREKCE ister: alti ay sonra 'bu neden "
                         "serbestti' sorusunun cevabi o satirdir.")
    kayit = {
        "id": uuid.uuid4().hex, "proje_id": proje_id, "gorev_id": gorev_id,
        "sinif": olculen, "desen": desen, "alinti": (alinti or "")[:300],
        "kaynak": kaynak, "gerekce": (gerekce or "").strip()[:300],
        "veren": veren, "olusturuldu": simdi(),
    }
    with db.baglanti() as c:
        c.execute(
            "INSERT INTO izin (id, proje_id, gorev_id, sinif, desen, alinti, "
            "kaynak, gerekce, veren, olusturuldu) VALUES "
            "(:id,:proje_id,:gorev_id,:sinif,:desen,:alinti,:kaynak,:gerekce,"
            ":veren,:olusturuldu)", kayit)
    kapsam = "bu is icin" if gorev_id else "KALICI"
    db.olay_yaz(proje_id, "izin_verildi",
                f"{kapsam}: {desen} ({IZIN_VERILEBILIR[olculen]})"
                + (f" | patron: \"{alinti[:120]}\"" if alinti else ""),
                ajan_ad="insan", gorev_id=gorev_id)
    return kayit


def liste(db, proje_id: str, *, gorev_id=None, kalici: bool = True,
          kaldirilanlar: bool = False) -> list:
    """`gorev_id` verilirse o isin izinleri (+ kaliciler); verilmezse
    yalniz kaliciler."""
    kosul = ["proje_id = ?"]
    deg = [proje_id]
    if not kaldirilanlar:
        kosul.append("kaldirildi IS NULL")
    if gorev_id is not None:
        kosul.append("(gorev_id = ?" + (" OR gorev_id IS NULL)" if kalici else ")"))
        deg.append(gorev_id)
    elif kalici:
        kosul.append("gorev_id IS NULL")
    with db.baglanti() as c:
        rows = c.execute("SELECT * FROM izin WHERE " + " AND ".join(kosul)
                         + " ORDER BY olusturuldu, rowid", deg).fetchall()
    return [dict(r) for r in rows]


def kaldir(db, proje_id: str, izin_id: str, *, sebep: str,
           kaldiran: str = "insan") -> dict:
    sebep = (sebep or "").strip()
    if kaldiran != "insan":
        raise IzinHatasi("Izni yalniz insan kaldirabilir.")
    if not sebep:
        raise IzinHatasi("Kaldirma sebebi zorunlu.")
    with db.baglanti() as c:
        rows = c.execute("SELECT * FROM izin WHERE proje_id = ? AND id LIKE ? "
                         "AND kaldirildi IS NULL",
                         (proje_id, izin_id.strip() + "%")).fetchall()
        if len(rows) != 1:
            raise IzinHatasi("Gecerli tek bir izin bulunamadi: "
                             f"{izin_id} ({len(rows)} eslesme)")
        k = dict(rows[0])
        c.execute("UPDATE izin SET kaldirildi = ?, kaldirma_sebebi = ? "
                  "WHERE id = ?", (simdi(), sebep, k["id"]))
    db.olay_yaz(proje_id, "izin_kaldirildi", f"{k['desen']} | {sebep}",
                ajan_ad="insan", gorev_id=k["gorev_id"])
    return k


# -- kapi -------------------------------------------------------------------

def eslesen(db, proje_id: str, gorev_id, bulgu: dict):
    """Bu riskli eylemi kapsayan gecerli bir izin var mi. Yoksa None.

    Hic PATLAMAZ: izin defterine ulasilamazsa None doner, yani eylem
    SORULUR -- kapi kapali kalarak basarisiz olur.
    """
    try:
        sinif = (bulgu or {}).get("sinif") or ""
        if sinif not in IZIN_VERILEBILIR:
            return None
        hedef = f"{bulgu.get('hedef') or ''} {bulgu.get('element') or ''}"
        if YIKICI_BICIM.search(str(bulgu.get("hedef") or "")):
            return None
        hedef_j = _jeton(hedef)
        # TARAYICI tiklamasi (01.10.2026, G14): hedef, ajanin dugmeyi
        # ANLATISIDIR ("Bulten formunu Kaydol dugmesiyle gonder"); izin
        # patronun cumlesinden gelir ("formu ... gondermek"). Kelimesi
        # kelimesine ortusmezler. Olculen sey: kapinin SORMA SEBEBI olan
        # kelime (`esles`, orn. "gonder") izinde koku ile geciyor mu.
        # Kabuk komutu (`git push`) SIKI eslesmede kalir.
        tarayici = bool(bulgu.get("element")) and bool(bulgu.get("esles"))
        sebep_j = _jeton(str(bulgu.get("esles") or "")) if tarayici else []
        for iz in liste(db, proje_id, gorev_id=gorev_id):
            if iz["sinif"] != sinif:
                continue
            if _ardisik_icerir(hedef_j, _jeton(iz["desen"])):
                return iz
            if sebep_j and _ardisik_icerir(_kokler(_jeton(iz["desen"])), sebep_j):
                return iz
    except Exception:
        return None
    return None


def gecti_kaydi(db, proje_id: str, *, izin: dict, bulgu: dict, ajan_ad: str,
                gorev_id=None) -> None:
    db.olay_yaz(proje_id, "izinle_gecti",
                f"{bulgu.get('ad', '')}: {str(bulgu.get('hedef', ''))[:150]} "
                f"| izin: {izin['desen']} ({'kalici' if not izin['gorev_id'] else 'patronun sozu'})",
                ajan_ad=ajan_ad, gorev_id=gorev_id)


# -- plan -------------------------------------------------------------------

def plan_izinleri(izinler, patron_sozu: str) -> tuple:
    """Liderin plana yazdigi izinleri PATRONUN SOZUNE karsi dogrular.

    Doner: (gecerli liste, ret metni). Ret metni bossa hepsi gecti.
    Gecersiz izin plani REDDEDER (ret ogretir): sessizce atmak, liderin
    yanlis anladigini hic ogrenmemesi demekti.
    """
    if not izinler:
        return [], ""
    if not isinstance(izinler, list):
        return [], "`izinler` bir LISTE olmali."
    soz = (patron_sozu or "").strip()
    if not soz:
        return [], ("`izinler` yalniz PATRONUN kendi mesajindan cikar; bu "
                    "hedefte patron mesaji yok. `izinler` alanini bos birak.")
    sade_soz = riskli.sadelestir(soz)
    temiz = []
    for iz in izinler:
        if not isinstance(iz, dict):
            return [], "Her izin {\"eylem\": ..., \"alinti\": ...} olmali."
        eylem = str(iz.get("eylem") or "").strip()
        alinti = str(iz.get("alinti") or "").strip()
        if len(riskli.sadelestir(alinti)) < 3 or riskli.sadelestir(alinti) not in sade_soz:
            return [], (f"'{eylem}' izninin alintisi ('{alinti}') patronun "
                        "mesajinda KELIMESI KELIMESINE gecmiyor. Izin yalniz "
                        "patronun acikca soyledigi seye verilir; emin degilsen "
                        "izin YAZMA, eylem sorulur.")
        if olumsuz_mu(soz, alinti):
            return [], (f"'{alinti}' olumsuz bir cumlede geciyor (patron bunu "
                        "YAPMA diyor olabilir). Bu eyleme izin YAZMA.")
        try:
            sinif = dogrula("", eylem)
        except IzinHatasi as exc:
            return [], f"Izin gecersiz: {exc}"
        temiz.append({"desen": re.sub(r"\s+", " ", eylem)[:120],
                      "alinti": alinti, "sinif": sinif})
    return temiz, ""


def plan_blogu() -> str:
    """Plan istemine giren tarif."""
    return (
        "## PATRONUN IZINLERI (`izinler`, cogu iste BOS)\n\n"
        "Riskli bir eylemi (git push, deploy, publish, genel paket kurma) "
        "patron BU MESAJINDA ACIKCA istediyse `izinler`e yaz; o eylem "
        "sorulmadan gecer. Istemediyse YAZMA -- sorulur.\n"
        "- `eylem`: tam komut ya da eylem (\"git push\", \"npm run deploy\"). "
        "Tek basina 'git' ya da 'npm' olmaz.\n"
        "- `alinti`: patronun mesajindan KELIMESI KELIMESINE parca. Mesajda "
        "gecmeyen alinti plani REDDETTIRIR.\n"
        "- PARA ve SILME izne yazilamaz: patron 'yap' dese bile her seferinde "
        "sorulur. Zorla push (--force) da oyle.\n"
        "- Olumsuz cumleye (\"push etme\") izin yazma. Emin degilsen yazma: "
        "bir fazla soru, istenmeyen bir push'tan ucuzdur.")


def brifing_blogu(db, proje_id: str, gorev_id) -> str:
    """Ajana: bu iste neye izin var -- `onay_iste` ile bosuna durmasin."""
    try:
        iz = liste(db, proje_id, gorev_id=gorev_id)
    except Exception:
        return ""
    if not iz:
        return ""
    satir = ["**Patronun bu iste ONCEDEN izin verdikleri** (bunlar icin "
             "`onay_iste` CAGIRMA, sorulmadan gecer):"]
    for i in iz:
        kim = "kalici izin" if not i["gorev_id"] else f"patron: \"{i['alinti'][:80]}\""
        satir.append(f"- `{i['desen']}` ({kim})")
    satir.append("Yalniz bu desenler; baska riskli eylem yine sorulur. PARA, "
                 "SILME ve --force her zaman sorulur.")
    return "\n".join(satir)
