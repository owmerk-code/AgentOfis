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
    # 07.10: patron "videoyu uretmeden once bana gelsin" -- sozu bile
    # ("video yap") senaryo paketini atlatmaz; "bu is boyunca" onayi acar.
    "kredi": "URETIM KREDISI (once senaryo paketi)",
}

#: TEK ARAC ADIYLA acilabilen sinif (06.10.2026, onay yorgunlugu E80).
#: Taninmayan bir baglayici araci (`mcp__claude_ai_Atria__load_skill`) her
#: cagrida soruluyordu; patron "bu projede hep" diyebilmeli. Izin DESENLE
#: degil yalniz ARACIN TAM ADIYLA eslesir ve yalniz insandan gelir (lider
#: plana yazamaz: `dogrula("", ...)` bu sinifi reddeder).
ARAC_ADIYLA = {"bilinmiyor": "taninmayan arac (yalniz bu arac)"}
_ARAC_ADI = re.compile(r"^mcp__[A-Za-z0-9_-]+__[A-Za-z0-9_.-]+$")

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
    if _ARAC_ADI.match(desen):
        # Baglayici ARACININ ADI: sinifi arac kapisinin kendi karari.
        b = riskli.arac_degerlendir(desen, {})
        return b["sinif"] if b and b.get("sorulur") else ""
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
    if sinif_istenen in ARAC_ADIYLA:
        if not _ARAC_ADI.match(desen or "") or olculen != sinif_istenen:
            raise IzinHatasi(
                f"'{desen}' icin {ARAC_ADIYLA[sinif_istenen]} izni yalniz "
                "ARACIN TAM ADIYLA verilir (mcp__sunucu__arac) ve kapi onu "
                f"gercekten '{sinif_istenen}' saymali (olculen: {olculen or 'serbest'}).")
        return olculen
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
    _ne = IZIN_VERILEBILIR.get(olculen) or ARAC_ADIYLA.get(olculen) or olculen
    db.olay_yaz(proje_id, "izin_verildi",
                f"{kapsam}: {desen} ({_ne})"
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
        arac_adi = str((bulgu or {}).get("arac") or "")
        if sinif in ARAC_ADIYLA:
            # Yalniz ARACIN TAM ADI; desen benzerligi yok.
            for iz in liste(db, proje_id, gorev_id=gorev_id):
                if iz["sinif"] == sinif and iz["desen"] == arac_adi:
                    return iz
            return None
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
        # 06.10 OLCULDU: kabuk bulgusu da `element` tasiyor (komutun kendisi);
        # bu gevsek yol ona da uygulaniyordu ve "git push origin main" izni
        # "git push origin canli"yi de geciriyordu. Kabuk SIKI eslesmede kalir.
        tarayici = (bool(bulgu.get("element")) and bool(bulgu.get("esles"))
                    and arac_adi not in riskli.KABUK_ARACLARI)
        sebep_j = _jeton(str(bulgu.get("esles") or "")) if tarayici else []
        for iz in liste(db, proje_id, gorev_id=gorev_id):
            if iz["sinif"] != sinif:
                continue
            if arac_adi and iz["desen"] == arac_adi:
                return iz                    # baglayici araci, tam adiyla
            if _ardisik_icerir(hedef_j, _jeton(iz["desen"])):
                return iz
            if sebep_j and _ardisik_icerir(_kokler(_jeton(iz["desen"])), sebep_j):
                return iz
    except Exception:
        return None
    return None


#: Onay kartindan KALICI izne: komut bu uzunlugu asarsa izin verilmez
#: (desen 120 harfte kesilir; kesik desen istenenden GENIS bir izin olurdu).
_KART_DESEN_SINIRI = 120
_COK_SATIR = "(cok satirli komut)"


def karttan_izin(onay: dict) -> dict:
    """Bu onay kartindan "bu projede hep" izni cikabilir mi -- TEK KURAL.

    Panel dugmeyi bununla gosterir, postane izni bununla yazar. Kartin
    `ayrinti`sindaki `sinif :` ve `desen :` satirlarini kapi (`izin_sor`)
    yazar; o satirlari tasimayan (eski ya da ajanin kendi `onay_iste`si)
    kart kalici izne donusmez.
    """
    ayr = str((onay or {}).get("ayrinti") or "")
    m_s = re.search(r"^sinif\s*:\s*(\S+)\s*$", ayr, re.M)
    m_d = re.search(r"^desen\s*:\s*(.+?)\s*$", ayr, re.M)
    if not (m_s and m_d):
        return {"verilebilir": False, "sebep": "Bu kart ofisin kapisindan gelmedi; kalici izne donusmez."}
    sinif, desen = m_s.group(1), m_d.group(1)
    if sinif in HER_ZAMAN_SORULUR and sinif not in ARAC_ADIYLA:
        return {"verilebilir": False, "sinif": sinif, "desen": desen,
                "sebep": f"{HER_ZAMAN_SORULUR[sinif]} her seferinde sorulur; kalici izinle acilmaz."}
    if desen == _COK_SATIR:
        return {"verilebilir": False, "sinif": sinif, "desen": "",
                "sebep": "Cok satirli komut; kalici izin tek bir komuta verilir."}
    if len(desen) > _KART_DESEN_SINIRI:
        return {"verilebilir": False, "sinif": sinif, "desen": desen,
                "sebep": "Komut cok uzun; kalici izin dar olmali (kabuk izin ile kisa desen ver)."}
    try:
        dogrula(sinif, desen)
    except IzinHatasi as exc:
        return {"verilebilir": False, "sinif": sinif, "desen": desen, "sebep": str(exc)}
    return {"verilebilir": True, "sinif": sinif, "desen": desen, "sebep": ""}


def kart_ayrintisi(arac: str, girdi: dict, bulgu: dict) -> str:
    """Kapinin onay kartina yazdigi `sinif`/`desen` satirlari (karttan_izin okur)."""
    komut = str((girdi or {}).get("command") or "") if arac in riskli.KABUK_ARACLARI else ""
    desen = re.sub(r"\s+", " ", komut).strip() if komut else arac
    if "\n" in komut.strip():
        desen = _COK_SATIR                  # cok satirli komut: kalici izne donusmez
    return f"sinif : {bulgu.get('sinif') or ''}\ndesen : {desen}\n"


def gun_sayaci(db, proje_id: str) -> dict:
    """Onay yorgunlugu OLCULUR (E80): bugun kac kez soruldu, kac adim
    izinle sorulmadan gecti, kac kalici izin var."""
    from datetime import datetime, timezone
    # Defter UTC yazar; "bugun" patronun YEREL gece yarisindan baslar.
    yerel = datetime.now().astimezone()
    bas = yerel.replace(hour=0, minute=0, second=0, microsecond=0)
    bas = bas.astimezone(timezone.utc).isoformat(timespec="seconds")
    with db.baglanti() as c:
        soruldu = c.execute("SELECT COUNT(*) FROM onay WHERE proje_id=? AND olusturuldu >= ?",
                            (proje_id, bas)).fetchone()[0]
        gecti = c.execute("SELECT COUNT(*) FROM olay WHERE proje_id=? AND tur='izinle_gecti' "
                          "AND olusturuldu >= ?", (proje_id, bas)).fetchone()[0]
    return {"bugun_soruldu": soruldu, "bugun_izinle_gecti": gecti,
            "kalici_izin": len(liste(db, proje_id))}


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


#: Patronun "kullanma" dedigini anlatan sozler (model cumlesinde). `olumsuz_mu`
#: eylem fiillerine bakar; "fable kullanma", "astra olmasin" onu gecer (olculdu).
_MODEL_OLUMSUZ = ("kullanma", "kullanmayin", "kullanmasin", "kullanmayalim", "olmasin",
                  "olmayacak", "istemiyorum", "istemem", "gerek yok", "gerekmez", "yapma",
                  "yapmayin", "yapmasin", "verme", "vermeyin", "degil", "haric", "disinda",
                  "yerine", "hayir")


#: Model adinin patronun cumlesinde aranmayan genel parcalari (efor, surum).
_MODEL_GENEL = {"high", "low", "medium", "xhigh", "max", "thinking", "preview", "latest"}


def _model_parcalari(mid: str) -> set:
    """`gpt-6.1-sol` -> {gpt, sol}; `gemini-3.8-flash-high` -> {gemini, flash}.
    Patron modeli bu parcalardan biriyle anar ("opus ile", "sol'a yaptir")."""
    return {x for x in re.split(r"[^a-z0-9.]+", (mid or "").lower())
            if x and x not in _MODEL_GENEL and not re.fullmatch(r"[0-9.]+", x)}


def model_secenekleri(db, proje_id: str) -> dict:
    """Motor -> secilebilir model kimlikleri (motorlarin kendi listeleri)."""
    from . import guncelleme
    try:
        liste = guncelleme.model_listesi(db, proje_id)
    except Exception:                            # noqa: BLE001
        liste = {}
    # Listede olmayan model UYDURULMAZ (fable/astra da listeden gelir:
    # `fable`, `gpt-6-astra` -- 08.10 olculdu).
    return {m: [x["id"] for x in v] for m, v in (liste or {}).items()}


def plan_modeli(kol: dict, patron_sozu: str, db=None, proje_id: str = "") -> tuple:
    """Bir isin MODELI -- yalniz patronun sozuyle.

    Patron (08.10.2026): "takim sohbetinde lidere soylersem ya da mesajda
    'su isi su ajana su modelle yaptir' dersem; fable ve astra da yalniz
    boyle". Lider bir kola `model` yazabilir ama yalniz patronun BU
    mesajindan, modeli ANAN kelimesi kelimesine alintiyla (`model_alinti`);
    olumsuz cumle ("fable kullanma") reddedilir; model motorlarin KENDI
    listesinde olmali (uydurulmaz). Patron demediyse ajanin modeli kalir.
    Doner: (`{"ad", "motor", "model", "alinti"}` ya da None, ret metni)."""
    from . import roller
    ad = str((kol or {}).get("model") or "").strip()
    if not ad:
        return None, ""
    secenek = (model_secenekleri(db, proje_id) if db is not None else
               {k["motor"]: [a] for a, k in roller.KAPI_MODELLERI.items()})
    motor, model = "", ""
    for mo, idler in secenek.items():
        tam = next((i for i in idler if i.lower() == ad.lower()), "")
        if tam:
            motor, model = mo, tam
            break
    if not motor:
        for mo, idler in secenek.items():
            yakin = next((i for i in idler if ad.lower() in i.lower()), "")
            if yakin:
                motor, model = mo, yakin
                break
    if not motor:
        return None, (f"'{ad}' modeli motorlarin listesinde yok. `model` alanina listedeki "
                      "adlardan birini yaz ya da bos birak (ajan kendi modeliyle calisir).")
    soz = (patron_sozu or "").strip()
    alinti = str((kol or {}).get("model_alinti") or "").strip()
    sade_soz, sade_al = riskli.sadelestir(soz), riskli.sadelestir(alinti)
    al_kelime = set(re.split(r"[^a-z0-9.]+", sade_al))
    if (not soz or len(sade_al) < 3 or sade_al not in sade_soz
            or not (_model_parcalari(model) | _model_parcalari(ad)) & al_kelime):
        return None, (f"'{model}' yalniz patron mesajinda bu modeli ACIKCA andiysa yazilir: "
                      "`model_alinti` patronun cumlesinden KELIMESI KELIMESINE, modelin "
                      "adini iceren bir parca olmali. Patron model demediyse `model` "
                      "alanini bos birak.")
    cumle = next((c for c in re.split(r"[.!?;\n]", sade_soz) if sade_al in c), sade_al)
    if olumsuz_mu(soz, alinti) or any(o in cumle for o in _MODEL_OLUMSUZ):
        return None, (f"Patron bu model icin olumsuz konusuyor olabilir ('{alinti}'). "
                      "`model` alanini bos birak.")
    return {"ad": ad, "motor": motor, "model": model, "alinti": alinti}, ""


def plan_blogu(modeller: dict = None) -> str:
    """Plan istemine giren tarif. `modeller`: motor -> secilebilir kimlikler."""
    liste = "; ".join(f"{m}: {', '.join(v)}" for m, v in (modeller or {}).items() if v)
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
        "bir fazla soru, istenmeyen bir push'tan ucuzdur.\n\n"
        "## ISIN MODELI (`model`, kolda; cogu iste YAZMA)\n\n"
        "Patron BU MESAJINDA bir is icin acikca bir model dediyse (\"bunu opus ile "
        "yap\", \"raporu fable yazsin\") o kola `\"model\"`: listedeki ad ve "
        "`\"model_alinti\"`: patronun cumlesinden KELIMESI KELIMESINE, model adini "
        "iceren parca yaz. O is o modelle (o modelin motorunda) kosar. Patron model "
        "demediyse YAZMA -- ajan kendi modeliyle calisir; FABLE ve ASTRA pahalidir, "
        "sistem onlari kendiliginden KULLANMAZ."
        + (f"\nSecilebilir modeller -- {liste}" if liste else ""))


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
