# -*- coding: utf-8 -*-
"""BELGE KUTUPHANESI (06.10.2026, Asama 2 / E77).

Patron bir belge verir (iade politikasi PDF'i, fiyat listesi Excel'i,
marka rehberi Word'u); ajanlar ve lider sorulara o belgeden, KAYNAGIYLA
(belge adi + sayfa / bolum / satir) cevap verir.

Neden olgu degil: olgu kisa bir DEGERDIR (600 harf) ve her brifinge girer;
belge uzundur ve yalniz ILGILI parcasi lazimdir. Belge parcalara bolunur
(her parca yerini tasir), deftere yazilir; arama ilgili parcalari getirir.

Uc kapi, ucu de bir hata sinifina karsi:

* **Kaynak her parcada.** Kaynaksiz cevap dogrulanamaz; "belge oyle
  diyor" demek yetmez, NEREDE dedigi gorulmeli.
* **Okunamayan belge SESSIZ gecmez.** Taranmis PDF (metin yok) ya da
  desteklenmeyen tur yuklenirken soylenir -- bos belge "yuklendi"
  gorunup hicbir soruya cevap vermemeli degil.
* **Ayni belge iki kez girmez** (icerik ozetiyle): ayni parca iki kez
  donup aramayi sisirmesin.

Arama KELIME aramasidir (Turkce ek farki onekle tolere edilir, nadir
kelime agir basar). Anlamsal arama ayri bir olcumle karar verilecek (K9);
olculmeden eklenmez.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import uuid
from pathlib import Path

from .db import simdi
from .yollar import PROJE_GIZLI

KLASOR = PROJE_GIZLI + "/belgeler"
TURLER = (".pdf", ".docx", ".xlsx", ".xlsm", ".csv", ".txt", ".md")
AZAMI_BAYT = 30 * 1024 * 1024
#: Parca boyu: bir paragraf-iki paragraf. Kucuk parca kaynagi keskin
#: tutar, buyuk parca baglami; ~900 harf ikisinin arasi.
PARCA_HARF = 900
AZAMI_PARCA = 4000
#: Brifinge / triyaja giren parca sayisi ve boyu (her turun jetonundan).
BRIFING_PARCA = 3
BRIFING_HARF = 700


class BelgeHatasi(ValueError):
    pass


# ------------------------------------------------------------------ metin

def _sade(metin: str) -> str:
    cevrim = str.maketrans("çğıİöşüÇĞÖŞÜâîû", "cgiiosucgosuaiu")
    return (metin or "").translate(cevrim).lower()


_DURAK = frozenset("""
ve veya ile icin gibi ama fakat ancak cunku yani hem her bir bu su o
olan olarak olsun olmali var yok daha cok az en de da mi mu ki ise
uzere gore kadar sonra once nedir nasil hangi neler kac ne the and for
""".split())


def kelimeler(metin: str) -> list:
    temiz = re.sub(r"[^0-9a-z]+", " ", _sade(metin))
    return [k for k in temiz.split() if (len(k) >= 3 or k.isdigit()) and k not in _DURAK]


def _kok(k: str) -> str:
    """Turkce ek toleransi: ilk 5 harf (sayilar oldugu gibi)."""
    return k if k.isdigit() else k[:5]


def birimler(yol: Path) -> list:
    """Belgeyi (yer, metin) birimlerine cevirir. Desteklenmeyen tur hata."""
    uz = yol.suffix.lower()
    if uz == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise BelgeHatasi("PDF okumak icin `pypdf` kurulu degil (pip install pypdf).") from exc
        try:
            okur = PdfReader(str(yol))
            return [(f"s.{i}", (s.extract_text() or "").strip())
                    for i, s in enumerate(okur.pages, 1)]
        except Exception as exc:                      # noqa: BLE001 -- bozuk PDF
            raise BelgeHatasi(f"PDF okunamadi: {exc}") from exc
    if uz == ".docx":
        import docx
        d = docx.Document(str(yol))
        cikti, bolum = [], "giris"
        for p in d.paragraphs:
            t = p.text.strip()
            if not t:
                continue
            ad = (p.style.name or "").lower() if p.style is not None else ""
            if ad.startswith(("heading", "baslik", "başlık", "title")):
                bolum = t[:60]
            cikti.append((f"bolum: {bolum}", t))
        for i, tablo in enumerate(d.tables, 1):
            for satir in tablo.rows:
                t = " | ".join(c.text.strip() for c in satir.cells)
                if t.strip(" |"):
                    cikti.append((f"tablo {i}", t))
        return cikti
    if uz in (".xlsx", ".xlsm"):
        import openpyxl
        kitap = openpyxl.load_workbook(str(yol), read_only=True, data_only=True)
        cikti = []
        for sayfa in kitap.worksheets:
            for n, satir in enumerate(sayfa.iter_rows(values_only=True), 1):
                t = " | ".join("" if v is None else str(v) for v in satir).strip(" |")
                if t:
                    cikti.append((f"{sayfa.title} satir {n}", t))
        kitap.close()
        return cikti
    if uz == ".csv":
        import csv
        with open(yol, encoding="utf-8-sig", errors="replace", newline="") as f:
            return [(f"satir {n}", " | ".join(r)) for n, r in enumerate(csv.reader(f), 1) if any(r)]
    if uz in (".txt", ".md"):
        metin = yol.read_text(encoding="utf-8", errors="replace")
        cikti, bolum = [], "giris"
        for blok in re.split(r"\n\s*\n", metin):
            b = blok.strip()
            if not b:
                continue
            if b.startswith("#"):
                bolum = b.lstrip("# ").splitlines()[0][:60]
            cikti.append((f"bolum: {bolum}", b))
        return cikti
    raise BelgeHatasi(f"'{uz}' turu desteklenmiyor. Desteklenen: {', '.join(TURLER)}.")


def parcala(birim: list) -> list:
    """Birimleri ~PARCA_HARF'lik parcalara toplar; parca yerini tasir
    ("s.3" ya da "s.3-4")."""
    parcalar, tampon, yerler = [], [], []

    def bosalt():
        if not tampon:
            return
        yer = yerler[0] if yerler[0] == yerler[-1] else f"{yerler[0]} - {yerler[-1]}"
        parcalar.append((yer, "\n".join(tampon)))
        tampon.clear(); yerler.clear()

    for yer, metin in birim:
        metin = (metin or "").strip()
        # KAYNAK KESKIN KALIR: sayfa ve bolum siniri parcayi keser (kucuk iki
        # sayfa birlesince kaynak "s.1 - s.2" diye bulaniklasiyordu -- sinama
        # yakaladi). Yalniz tablo SATIRLARI birlesir (tek satir cok kucuk).
        if tampon and yer != yerler[-1] and not ("satir" in yer and "satir" in yerler[-1]):
            bosalt()
        while metin:
            if sum(len(t) for t in tampon) + len(metin) > PARCA_HARF and tampon:
                bosalt()
            parca, metin = metin[:PARCA_HARF * 2], metin[PARCA_HARF * 2:]
            tampon.append(parca); yerler.append(yer)
    bosalt()
    return parcalar[:AZAMI_PARCA]


# ------------------------------------------------------------------ defter

def klasor(ofis, kanat_id: str = None) -> Path:
    return Path(ofis.kok_klasoru(kanat_id or None)).resolve() / KLASOR


def yukle(ofis, ad: str, veri: bytes, *, ekleyen: str = "insan", kanat_id: str = "") -> dict:
    """Belgeyi kaydeder, parcalar ve deftere yazar."""
    from .ekler import ad_temizle
    if not veri:
        raise BelgeHatasi("Bos dosya yuklenemez.")
    if len(veri) > AZAMI_BAYT:
        raise BelgeHatasi(f"Belge cok buyuk; sinir {AZAMI_BAYT // 1024 // 1024} MB.")
    temiz = ad_temizle(ad)
    if Path(temiz).suffix.lower() not in TURLER:
        raise BelgeHatasi(f"'{Path(temiz).suffix or temiz}' turu desteklenmiyor. "
                          f"Desteklenen: {', '.join(TURLER)}.")
    ozet = hashlib.sha256(veri).hexdigest()
    with ofis.db.baglanti() as c:
        ayni = c.execute("SELECT ad FROM belge WHERE proje_id = ? AND ozet = ? AND kaldirildi IS NULL",
                         (ofis.proje_id, ozet)).fetchone()
    if ayni:
        raise BelgeHatasi(f"Bu belge zaten yuklu ('{ayni['ad']}').")
    k = klasor(ofis, kanat_id)
    k.mkdir(parents=True, exist_ok=True)
    hedef = k / temiz
    n = 1
    while hedef.exists():
        hedef = k / f"{Path(temiz).stem}-{n}{Path(temiz).suffix}"
        n += 1
    hedef.write_bytes(veri)
    try:
        parcalar = parcala(birimler(hedef))
    except BelgeHatasi:
        hedef.unlink(missing_ok=True)
        raise
    except Exception as exc:                          # noqa: BLE001 -- bozuk dosya
        hedef.unlink(missing_ok=True)
        raise BelgeHatasi(f"Belge okunamadi: {exc}") from exc
    if not parcalar:
        hedef.unlink(missing_ok=True)
        raise BelgeHatasi("Belgede okunabilir METIN yok (taranmis PDF ya da bos). Metinli "
                          "bir surumunu yukle; resimden yazi okuma (OCR) yok.")
    bid = uuid.uuid4().hex
    with ofis.db.baglanti() as c:
        c.execute("INSERT INTO belge (id, proje_id, ad, yol, ozet, tur, boyut, parca, ekleyen, "
                  "olusturuldu, kanat_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (bid, ofis.proje_id, hedef.name, f"{KLASOR}/{hedef.name}", ozet,
                   hedef.suffix.lower().lstrip("."), len(veri), len(parcalar), ekleyen, simdi(),
                   kanat_id or ""))
        c.executemany("INSERT INTO belge_parca (belge_id, sira, yer, metin) VALUES (?,?,?,?)",
                      [(bid, i, yer, m) for i, (yer, m) in enumerate(parcalar)])
    ofis.db.olay_yaz(ofis.proje_id, "belge_yuklendi",
                     f"{hedef.name} ({len(parcalar)} parca)", ajan_ad=ekleyen)
    return {"id": bid, "ad": hedef.name, "yol": f"{KLASOR}/{hedef.name}", "parca": len(parcalar)}


def yukle_yoldan(ofis, yol, *, ekleyen: str = "insan", kanat_id: str = "") -> dict:
    p = Path(yol).expanduser()
    if not p.is_file():
        raise BelgeHatasi(f"Dosya yok: {p}")
    return yukle(ofis, p.name, p.read_bytes(), ekleyen=ekleyen, kanat_id=kanat_id)


def _kapsam(kanat, on: str = "") -> tuple:
    if kanat is None:
        return "", ()
    return f" AND ({on}kanat_id = '' OR {on}kanat_id = ?)", (kanat,)


def liste(db, proje_id: str, *, kanat=None) -> list:
    """Belgeler; `kanat` verilirse ortak + o takim (takim gozu)."""
    k, prm = _kapsam(kanat)
    with db.baglanti() as c:
        rows = c.execute("SELECT id, ad, yol, tur, boyut, parca, ekleyen, olusturuldu, kanat_id FROM belge "
                         f"WHERE proje_id = ? AND kaldirildi IS NULL{k} ORDER BY olusturuldu, rowid",
                         (proje_id, *prm)).fetchall()
    return [dict(r) for r in rows]


def kaldir(ofis, belge_id: str, *, kim: str = "insan") -> dict:
    """Belge aramadan cikar; dosya ve parcalar SILINMEZ (gecmis okunur)."""
    if kim != "insan":
        raise BelgeHatasi("Belgeyi yalniz patron kaldirir.")
    onek = (belge_id or "").strip().replace("%", "")
    if not onek:
        raise BelgeHatasi("Belge kimligi bos.")
    with ofis.db.baglanti() as c:
        rows = c.execute("SELECT id, ad FROM belge WHERE proje_id = ? AND id LIKE ? AND kaldirildi IS NULL",
                         (ofis.proje_id, onek + "%")).fetchall()
        if len(rows) != 1:
            raise BelgeHatasi("Belge bulunamadi." if not rows else
                              f"'{onek}' birden cok belgeye uyuyor; daha uzun yaz.")
        r = rows[0]
        belge_id = r["id"]
        c.execute("UPDATE belge SET kaldirildi = ? WHERE id = ?", (simdi(), belge_id))
    ofis.db.olay_yaz(ofis.proje_id, "belge_kaldirildi", r["ad"], ajan_ad=kim)
    return {"id": belge_id, "ad": r["ad"]}


# ------------------------------------------------------------------ arama

def ara(db, proje_id: str, sorgu: str, *, azami: int = 5, kanat=None) -> list:
    """Sorguya en ilgili parcalar: [{belge, yer, metin, puan}].

    Siralama `arama.sirala` (kelime kapisi + harf dizisi sirasi; olculdu).
    Hicbir kelimesi gecmeyen ve harfce de uzak parca donmez -- ilgisiz
    parca getirmek, "belgede yok" demekten kotudur.
    """
    from .arama import sirala
    k, prm = _kapsam(kanat, "b.")
    with db.baglanti() as c:
        rows = c.execute(
            "SELECT b.ad, p.yer, p.metin FROM belge_parca p JOIN belge b ON b.id = p.belge_id "
            f"WHERE b.proje_id = ? AND b.kaldirildi IS NULL{k}", (proje_id, *prm)).fetchall()
    if not rows:
        return []
    sira = sirala(sorgu, [f"{r['ad']} {r['yer']} {r['metin']}" for r in rows])
    return [{"belge": rows[i]["ad"], "yer": rows[i]["yer"], "metin": rows[i]["metin"],
             "puan": round(kel + harf, 3), "ortak": kel} for i, kel, harf in sira[:azami]]


def kaynakli_blok(db, proje_id: str, metin: str, *, baslik: str,
                  azami: int = BRIFING_PARCA, kanat=None) -> str:
    """Brifing / triyaj icin: ilgili parcalar, KAYNAGIYLA. Belge yoksa bos."""
    try:
        belgeler = liste(db, proje_id, kanat=kanat)
    except Exception:                                 # noqa: BLE001 -- eski defter
        return ""
    if not belgeler:
        return ""
    bulunan = ara(db, proje_id, metin, azami=azami, kanat=kanat)
    satir = [f"## {baslik}", "",
             "Yuklu belgeler: " + ", ".join(b["ad"] for b in belgeler[:20])
             + (f" (+{len(belgeler) - 20})" if len(belgeler) > 20 else "") + ".",
             "Belgeden bir sey soyluyorsan KAYNAGINI yaz: (belge adi, yer). "
             "Belgede yoksa 'belgede yok' de, UYDURMA."]
    if bulunan:
        satir += ["", "Bu ise en ilgili parcalar:"]
        for b in bulunan:
            m = " ".join(b["metin"].split())
            satir.append(f"- [{b['belge']} · {b['yer']}] {m[:BRIFING_HARF]}"
                         + ("..." if len(m) > BRIFING_HARF else ""))
    return "\n".join(satir)
