# -*- coding: utf-8 -*-
"""Yedek: ofisin tamami -- kod, defter, ajan ciktilari -- tek arsivde.

PLAN F1, E02. Kullanici (25.09.2026): *"herhangi bir sey bozulursa geri
donebilelim."* Bugune kadar yedek ELLE aliniyordu (`*.tar.gz` koke,
`ofis.sqlite3.yedek-*` yanina) ve ne zaman alindigi, ne icerdigi, geri
yuklenip yuklenemedigi bilinmiyordu. **Geri yuklenmemis yedek, yedek
degil umuttur.**

## Ne girer, ne girmez

* Proje kokunun tamami (kod, belgeler, `calisma/`, `.git/`).
* Her `*.sqlite3` dosyasi sqlite'in KENDI yedek API'siyle kopyalanir.
  Dosyayi duz kopyalamak, WAL kipinde yazilmakta olan bir defterin
  YARIM halini alabilir -- ve bu, geri yuklenene kadar fark edilmez.
  `-wal`/`-shm`/`-journal` bu yuzden hic alinmaz: yedek API onlari
  zaten icine katar.
* **Sir GIRMEZ.** Anahtar kasasi (`~/.agentofis/gizli.env`), codex
  evleri (`auth.json`), kabin profili proje kokunun DISINDA ve oyle
  kalir. Arsiv buluta gidecek; bulut bir kopyalama yeridir ve sir
  kopyalanan yerde durmaz (`gizli.py` kurali). Kokun icine yanlislikla
  dusmus bir sir dosyasi da ALINMAZ ve atlandigi SOYLENIR.
* Yeniden uretilebilen ve buyuk olan alinmaz: `__pycache__`,
  `.pytest_cache`, `.playwright-mcp` (70 MB rakip ekran goruntusu),
  eski el yedekleri (`*.tar.gz`).

## Nereye

Once `~/.agentofis/yedekler` (proje kokunun disinda: kok bozulursa yedek
de bozulmasin). Sonra ayardaki EK hedeflere (Google Drive klasoru gibi)
kopyalanir. Ek hedef ulasilamazsa (Drive kapali, disk takili degil) is
DURMAZ ama sessiz de kalmaz: sonuc hangi hedefe yazilamadigini soyler.

## Uc kural

1. **Yazma ATOMIK.** Once `.part`, sonra yeniden adlandirma. 19.09'da
   `'w'` kipiyle iki dosya sifir bayta indi; yarim yazilmis bir arsiv
   "yedek var" deyip yalan soyler.
2. **Budama yalniz KENDI arsivlerimizi siler** (`AgentOfis-yedek-*.zip`)
   ve az once yazilani asla silmez. Hedef klasorde baska dosya varsa
   ona dokunulmaz.
3. **Geri yukleme CANLI klasorun uzerine YAZMAZ.** Bos bir klasore acar.
   Canliyi degistirmek insanin karari; once yeni klasorde denenir.
"""

from __future__ import annotations

import datetime as _dt
import fnmatch
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

PROJE_KOKU = Path(__file__).resolve().parent.parent
VARSAYILAN_YEDEK_KOK = Path.home() / ".agentofis" / "yedekler"
VARSAYILAN_AYAR = Path.home() / ".agentofis" / "yedek.json"

AD_ONEKI = "AgentOfis-yedek-"
SAKLANAN = 30                 # hedef basina son N arsiv
GUNLUK_ARALIK_SAAT = 24
BICIM = 1                     # manifest bicim surumu

#: Klasor adlari -- herhangi bir derinlikte atlanir.
ATLANAN_KLASOR = {"__pycache__", ".pytest_cache", ".playwright-mcp",
                  "node_modules"}
#: Dosya desenleri -- ad uzerinden.
ATLANAN_DOSYA = ("*.pyc", "*.tar.gz", "*.sqlite3-wal", "*.sqlite3-shm",
                 "*.sqlite3-journal", "*.part")
#: SIR desenleri: ALINMAZ ve atlandigi raporlanir.
SIR_DESENI = ("gizli.env", ".env", "*.env", "auth.json", "*.pem", "*.key")


class YedekHatasi(RuntimeError):
    pass


def yedek_koku() -> Path:
    return Path(os.environ.get("OFIS_YEDEK_KOK") or VARSAYILAN_YEDEK_KOK)


def ayar_yolu() -> Path:
    return Path(os.environ.get("OFIS_YEDEK_AYAR") or VARSAYILAN_AYAR)


# ------------------------------------------------------------------ ayar

def ayar_oku() -> dict:
    y = ayar_yolu()
    if not y.exists():
        return {"hedefler": [], "son": ""}
    try:
        a = json.loads(y.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # Bozuk ayar sessizce bos sayilmaz: ek hedefler kaybolur ve
        # kimse bulut kopyasinin durdugunu fark etmez.
        raise YedekHatasi(f"Yedek ayari okunamadi ({y}): {exc}")
    a.setdefault("hedefler", [])
    a.setdefault("son", "")
    return a


def _atomik_yaz(yol: Path, metin: str) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_name(yol.name + ".part")
    gecici.write_text(metin, encoding="utf-8")
    os.replace(gecici, yol)


def ayar_yaz(a: dict) -> None:
    _atomik_yaz(ayar_yolu(), json.dumps(a, ensure_ascii=False, indent=2))


def hedef_ekle(klasor: str) -> str:
    """Ek hedef (orn. Google Drive klasoru). Var olmali -- yanlis yazilmis
    bir yol, yedeklerin hic bir yere gitmedigi sessiz bir hedef olurdu."""
    p = Path(klasor).expanduser()
    if not p.is_absolute():
        raise YedekHatasi("Hedef MUTLAK yol olmali (goreli yol baska "
                          "klasore cozulur -- hayalet veritabani dersi).")
    p = p.resolve()
    if not p.is_dir():
        raise YedekHatasi(f"Klasor yok: {p}")
    try:
        p.relative_to(PROJE_KOKU)
        raise YedekHatasi("Hedef proje kokunun ICINDE olamaz: yedek kendini "
                          "yedeklerdi ve kok bozulunca yedek de giderdi.")
    except ValueError:
        pass
    a = ayar_oku()
    if str(p) not in a["hedefler"]:
        a["hedefler"].append(str(p))
        ayar_yaz(a)
    return str(p)


def hedef_cikar(klasor: str) -> bool:
    a = ayar_oku()
    p = str(Path(klasor).expanduser().resolve())
    if p not in a["hedefler"]:
        return False
    a["hedefler"].remove(p)
    ayar_yaz(a)
    return True


# --------------------------------------------------------------- toplama

def _sir_mi(ad: str) -> bool:
    return any(fnmatch.fnmatch(ad.lower(), d) for d in SIR_DESENI)


def _atlanir_mi(ad: str) -> bool:
    return any(fnmatch.fnmatch(ad.lower(), d) for d in ATLANAN_DOSYA)


def dosyalari_topla(kok: Path) -> dict:
    """Arsive girecek dosyalari ve atlanan sirlari dondurur."""
    kok = Path(kok).resolve()
    dosyalar, sirlar = [], []
    for dizin, altlar, adlar in os.walk(kok):
        altlar[:] = sorted(a for a in altlar if a not in ATLANAN_KLASOR)
        for ad in sorted(adlar):
            tam = Path(dizin) / ad
            goreli = tam.relative_to(kok).as_posix()
            if _sir_mi(ad):
                sirlar.append(goreli)
                continue
            if _atlanir_mi(ad):
                continue
            dosyalar.append(goreli)
    return {"dosyalar": dosyalar, "sirlar": sirlar}


def _sha(yol: Path) -> str:
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()


def _sqlite_kopyala(kaynak: Path, hedef: Path) -> dict:
    """Yedek API'siyle tutarli kopya + butunluk denetimi."""
    src = sqlite3.connect(str(kaynak), timeout=30)
    try:
        dst = sqlite3.connect(str(hedef))
        try:
            src.backup(dst)
            durum = dst.execute("PRAGMA integrity_check").fetchone()[0]
            tablo = dst.execute("SELECT count(*) FROM sqlite_master "
                                "WHERE type='table'").fetchone()[0]
        finally:
            dst.close()
    finally:
        src.close()
    return {"butunluk": durum, "tablo": tablo}


# ------------------------------------------------------------------ alma

def _ad(zaman: _dt.datetime, neden: str) -> str:
    temiz = "".join(c if c.isalnum() or c in "-_" else "-" for c in neden)[:30]
    return f"{AD_ONEKI}{zaman.strftime('%Y%m%d-%H%M%S')}-{temiz or 'elle'}.zip"


def al(neden: str = "elle", *, kok: Path = None, hedef_kok: Path = None,
       ek_hedefler: list = None, saklanan: int = SAKLANAN) -> dict:
    """Yedek alir, dogrular, ek hedeflere dagitir, budar.

    Donus: {"arsiv", "boyut", "dosya", "db", "sirlar_atlandi",
            "hedefler": [{"klasor", "durum", "hata"}], "budanan"}
    """
    kok = Path(kok or PROJE_KOKU).resolve()
    hedef_kok = Path(hedef_kok or yedek_koku())
    hedef_kok.mkdir(parents=True, exist_ok=True)
    try:
        hedef_kok.resolve().relative_to(kok)
        raise YedekHatasi("Yedek klasoru proje kokunun icinde olamaz.")
    except ValueError:
        pass

    zaman = _dt.datetime.now()
    ad = _ad(zaman, neden)
    topla = dosyalari_topla(kok)
    manifest = {"bicim": BICIM, "zaman": zaman.isoformat(timespec="seconds"),
                "neden": neden, "kaynak": str(kok), "dosyalar": [],
                "db": [], "sirlar_atlandi": topla["sirlar"]}

    gecici_arsiv = hedef_kok / (ad + ".part")
    with tempfile.TemporaryDirectory(prefix="ofis-yedek-") as tmp:
        tmp = Path(tmp)
        try:
            with zipfile.ZipFile(gecici_arsiv, "w", zipfile.ZIP_DEFLATED,
                                 compresslevel=6) as z:
                for goreli in topla["dosyalar"]:
                    kaynak = kok / goreli
                    if goreli.lower().endswith(".sqlite3"):
                        kopya = tmp / f"db{len(manifest['db'])}.sqlite3"
                        bilgi = _sqlite_kopyala(kaynak, kopya)
                        if bilgi["butunluk"] != "ok":
                            raise YedekHatasi(
                                f"{goreli} butunluk denetiminden gecmedi: "
                                f"{bilgi['butunluk']}")
                        kaynak = kopya
                        manifest["db"].append({"yol": goreli, **bilgi})
                    try:
                        z.write(kaynak, goreli)
                    except (PermissionError, FileNotFoundError) as exc:
                        # Tur sirasinda silinen/kilitli dosya yedegi
                        # OLDURMEZ ama gizlenmez de.
                        manifest.setdefault("okunamayan", []).append(
                            f"{goreli}: {exc.__class__.__name__}")
                        continue
                    manifest["dosyalar"].append(
                        {"yol": goreli, "boyut": kaynak.stat().st_size,
                         "sha256": _sha(kaynak)})
                z.writestr("_manifest.json",
                           json.dumps(manifest, ensure_ascii=False, indent=1))
        except BaseException:
            gecici_arsiv.unlink(missing_ok=True)
            raise
    arsiv = hedef_kok / ad
    os.replace(gecici_arsiv, arsiv)

    # Yazilan arsiv OLCULUR, varsayilmaz.
    d = dogrula(arsiv)
    if not d["tamam"]:
        raise YedekHatasi(f"Yeni arsiv dogrulanamadi: {d['bulgular'][:3]}")

    sonuc = {"arsiv": str(arsiv), "boyut": arsiv.stat().st_size,
             "dosya": len(manifest["dosyalar"]), "db": manifest["db"],
             "sirlar_atlandi": manifest["sirlar_atlandi"],
             "okunamayan": manifest.get("okunamayan", []),
             "hedefler": [], "budanan": budama(hedef_kok, saklanan, arsiv)}

    if ek_hedefler is None:
        try:
            ek_hedefler = ayar_oku()["hedefler"]
        except YedekHatasi as exc:
            ek_hedefler = []
            sonuc["hedefler"].append({"klasor": "(ayar)", "durum": "hata",
                                      "hata": str(exc)})
    for h in ek_hedefler:
        sonuc["hedefler"].append(_dagit(arsiv, Path(h), saklanan))

    try:
        a = ayar_oku()
        a["son"] = zaman.isoformat(timespec="seconds")
        a["son_arsiv"] = str(arsiv)
        ayar_yaz(a)
    except YedekHatasi:
        pass
    return sonuc


def _dagit(arsiv: Path, klasor: Path, saklanan: int) -> dict:
    if not klasor.is_dir():
        return {"klasor": str(klasor), "durum": "ulasilamadi",
                "hata": "klasor yok (Drive kapali ya da cikarilmis olabilir)"}
    try:
        gecici = klasor / (arsiv.name + ".part")
        shutil.copyfile(arsiv, gecici)
        os.replace(gecici, klasor / arsiv.name)
        if _sha(klasor / arsiv.name) != _sha(arsiv):
            return {"klasor": str(klasor), "durum": "hata",
                    "hata": "kopya ozeti tutmadi"}
        budama(klasor, saklanan, klasor / arsiv.name)
        return {"klasor": str(klasor), "durum": "tamam", "hata": ""}
    except OSError as exc:
        return {"klasor": str(klasor), "durum": "hata", "hata": str(exc)}


def arsivler(klasor: Path = None) -> list:
    k = Path(klasor or yedek_koku())
    if not k.is_dir():
        return []
    return sorted((p for p in k.glob(AD_ONEKI + "*.zip") if p.is_file()),
                  key=lambda p: p.name)


def budama(klasor: Path, saklanan: int, korunan: Path = None) -> list:
    """En eski arsivleri siler; yalniz bizim adlandirdiklarimizi."""
    saklanan = max(1, int(saklanan))
    liste = arsivler(klasor)
    fazla = liste[:-saklanan] if len(liste) > saklanan else []
    silinen = []
    for p in fazla:
        if korunan and p.resolve() == Path(korunan).resolve():
            continue
        p.unlink()
        silinen.append(p.name)
    return silinen


# -------------------------------------------------------------- dogrulama

def dogrula(arsiv: Path) -> dict:
    """Arsivi ACAR ve olcer: her dosyanin ozeti, her defterin butunlugu."""
    bulgular = []
    arsiv = Path(arsiv)
    try:
        with zipfile.ZipFile(arsiv) as z:
            if z.testzip() is not None:
                bulgular.append("zip CRC hatasi")
            manifest = json.loads(z.read("_manifest.json").decode("utf-8"))
            icerik = set(z.namelist())
            for d in manifest["dosyalar"]:
                if d["yol"] not in icerik:
                    bulgular.append(f"eksik: {d['yol']}")
                    continue
                h = hashlib.sha256(z.read(d["yol"])).hexdigest()
                if h != d["sha256"]:
                    bulgular.append(f"ozet tutmadi: {d['yol']}")
            with tempfile.TemporaryDirectory(prefix="ofis-dogrula-") as tmp:
                for db in manifest["db"]:
                    yol = Path(tmp) / "d.sqlite3"
                    yol.write_bytes(z.read(db["yol"]))
                    c = sqlite3.connect(str(yol))
                    try:
                        s = c.execute("PRAGMA integrity_check").fetchone()[0]
                    finally:
                        c.close()
                    if s != "ok":
                        bulgular.append(f"defter bozuk: {db['yol']}: {s}")
                    yol.unlink()
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        return {"tamam": False, "bulgular": [f"arsiv okunamadi: {exc}"],
                "manifest": None}
    return {"tamam": not bulgular, "bulgular": bulgular, "manifest": manifest}


# ---------------------------------------------------------------- geri yukleme

def geri_yukle(arsiv: Path, hedef: Path) -> dict:
    """Arsivi BOS bir klasore acar. Canli klasorun uzerine yazmaz."""
    hedef = Path(hedef).expanduser().resolve()
    if hedef == PROJE_KOKU or PROJE_KOKU in hedef.parents \
            or hedef in PROJE_KOKU.parents:
        raise YedekHatasi("Canli proje klasorune ya da onun ustune geri "
                          "yuklenmez; bos bir klasor ver.")
    if hedef.exists() and any(hedef.iterdir()):
        raise YedekHatasi(f"Hedef bos degil: {hedef}")
    d = dogrula(arsiv)
    if not d["tamam"]:
        raise YedekHatasi(f"Arsiv dogrulanamadi, acilmadi: {d['bulgular'][:3]}")
    hedef.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(arsiv) as z:
        for ad in z.namelist():
            if ad == "_manifest.json":
                continue
            # Zip yol kacisi (../) reddedilir.
            yol = (hedef / ad).resolve()
            if hedef not in yol.parents:
                raise YedekHatasi(f"Arsivde kok disina cikan yol: {ad}")
            yol.parent.mkdir(parents=True, exist_ok=True)
            yol.write_bytes(z.read(ad))
    return {"hedef": str(hedef), "dosya": len(d["manifest"]["dosyalar"]),
            "zaman": d["manifest"]["zaman"]}


# ------------------------------------------------------------- gunluk kapi

def gercek_defter_mi(db_yolu) -> bool:
    """Gunluk yedek YALNIZ gercek ofiste tetiklenir.

    `OFIS_YEDEK_KAPALI=1` hepsini kapatir (sinama ortami icin).
    """
    if os.environ.get("OFIS_YEDEK_KAPALI") == "1":
        return False
    from .db import VARSAYILAN_YOL
    try:
        return Path(db_yolu).resolve() == Path(VARSAYILAN_YOL).resolve()
    except OSError:
        return False


def son_yedek_saat() -> float:
    """Son yedekten bu yana gecen saat; hic yoksa sonsuz."""
    try:
        son = ayar_oku().get("son", "")
    except YedekHatasi:
        return float("inf")
    if not son:
        return float("inf")
    try:
        return (_dt.datetime.now() - _dt.datetime.fromisoformat(son)
                ).total_seconds() / 3600
    except ValueError:
        return float("inf")


def gerekirse_al(olay=None) -> dict:
    """Son yedek GUNLUK_ARALIK_SAAT'ten eskiyse alir.

    Yedek dusse bile is DURMAZ -- ama sessiz de kalmaz: `olay(tur, govde)`
    verildiyse `uyari` yazilir. Yedegi alinamayan bir ofis, bir sonraki
    bozulmada geri donusu olmayan bir ofistir; bunu insan bilmeli.
    """
    if son_yedek_saat() < GUNLUK_ARALIK_SAAT:
        return {}
    try:
        s = al("gunluk")
    except Exception as exc:          # noqa: BLE001 -- is durmasin
        if olay:
            olay("uyari", f"Gunluk yedek ALINAMADI: {exc}")
        return {"hata": str(exc)}
    if olay:
        eksik = [h for h in s["hedefler"] if h["durum"] != "tamam"]
        olay("yedek_alindi", f"{Path(s['arsiv']).name} · {s['dosya']} dosya"
             + (f" · {len(eksik)} hedefe YAZILAMADI" if eksik else ""))
        for h in eksik:
            olay("uyari", f"Yedek {h['klasor']} hedefine yazilamadi: {h['hata']}")
    return s
