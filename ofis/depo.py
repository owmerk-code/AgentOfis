# -*- coding: utf-8 -*-
"""Depo: ofisin kodu VE hafizasi, kullanicinin GIZLI GitHub deposunda.

Kullanici (26.09.2026): *"pc giderse github repodan agentofisle ilgili
hersye ulasirim... zaten paylasmicam sadece kendim gorebilcem."* Karar
bana birakildi; gerekce CLAUDE.md "F1 -- GITHUB GIZLI DEPO".

## Ne gider

* Kod, testler, belgeler, `calisma/` (ajan ciktilari; medya HARIC --
  buyuk dosya depoyu sisirir, o ZIP yedeginde ve ileride Drive'da).
* Ofis defteri **METIN** olarak (`veri/disari/ofis.sql`). Ham sqlite
  dosyasi her gun butunuyle yeni bir kopya olurdu; metinde git yalniz
  degisen satirlari saklar ve "gecen hafta hafizada ne vardi" sorusu
  depoda okunabilir.

## Uc SERT kapi -- kullanicinin "yanlis hesaba yukleme" endisesi

1. **Adres.** Yalniz ayardaki beklenen adrese (`owmerk-code/AgentOfis`)
   gonderilir. `origin` baska yeri gosteriyorsa gonderim REDDEDILIR.
2. **Gizlilik.** Depo `PRIVATE` degilse gonderilmez (her gonderimde
   sorulur; biri depoyu herkese acik yaparsa ertesi gun durur).
3. **Sir.** Gonderilecek her metinde kasadaki GERCEK anahtar degerleri
   ve bilinen anahtar bicimleri aranir; bulunursa gonderim durur ve
   hangi dosya oldugu (deger DEGIL) soylenir.

Her kapinin reddi gorunur olur; gonderim dusse bile is DURMAZ.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sqlite3
import subprocess
import tempfile
from pathlib import Path

PROJE_KOKU = Path(__file__).resolve().parent.parent
DISARI = Path("veri") / "disari" / "ofis.sql"
BEKLENEN_UZAK = "https://github.com/owmerk-code/AgentOfis.git"
VARSAYILAN_AYAR = Path.home() / ".agentofis" / "depo.json"
AZAMI_DOSYA_MB = 50

#: Bilinen anahtar bicimleri. Sinama dosyalarindaki bilerek uydurma
#: ornekler (`AIza-SINAMA-...`, `AIza-test`) bu desene UYMAZ: gercek
#: anahtarlar tire icermeyen uzun govdeye sahip.
ANAHTAR_DESENI = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{20,}"
    r"|sk-or-v1-[a-f0-9]{20,}|AIza[0-9A-Za-z_]{35}"
    r"|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})")


class DepoHatasi(RuntimeError):
    pass


def ayar_yolu() -> Path:
    return Path(os.environ.get("OFIS_DEPO_AYAR") or VARSAYILAN_AYAR)


def ayar_oku() -> dict:
    y = ayar_yolu()
    if not y.exists():
        return {"uzak": BEKLENEN_UZAK, "son": "", "acik": True}
    try:
        a = json.loads(y.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DepoHatasi(f"Depo ayari okunamadi ({y}): {exc}")
    a.setdefault("uzak", BEKLENEN_UZAK)
    a.setdefault("son", "")
    a.setdefault("acik", True)
    return a


def ayar_yaz(a: dict) -> None:
    y = ayar_yolu()
    y.parent.mkdir(parents=True, exist_ok=True)
    gecici = y.with_name(y.name + ".part")
    gecici.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(gecici, y)


def _git(kok: Path, *arg, zaman_asimi: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *arg], cwd=kok, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=zaman_asimi)


# ------------------------------------------------------------ defter -> metin

def defteri_metne_yaz(db_yolu: Path, hedef: Path) -> dict:
    """Defterin TUTARLI kopyasini (yedek API) metne doker. Atomik."""
    db_yolu, hedef = Path(db_yolu), Path(hedef)
    with tempfile.TemporaryDirectory(prefix="ofis-depo-") as tmp:
        kopya = Path(tmp) / "k.sqlite3"
        src = sqlite3.connect(str(db_yolu), timeout=30)
        dst = sqlite3.connect(str(kopya))
        try:
            src.backup(dst)
            satirlar = list(dst.iterdump())
        finally:
            dst.close()
            src.close()
    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_name(hedef.name + ".part")
    gecici.write_text("\n".join(satirlar) + "\n", encoding="utf-8", newline="\n")
    os.replace(gecici, hedef)
    return {"satir": len(satirlar), "boyut": hedef.stat().st_size}


# ---------------------------------------------------------------- sir tarama

def kasa_degerleri() -> list:
    """Kasadaki gercek degerler -- YALNIZ aramak icin, hic basilmaz."""
    from . import gizli
    try:
        veri = gizli._oku(gizli.depo_yolu())
    except Exception:            # noqa: BLE001 -- kasa yoksa aranacak deger yok
        return []
    return [v for v in veri.values() if isinstance(v, str) and len(v) >= 12]


def sir_tara(kok: Path, dosyalar: list, degerler: list = None) -> list:
    """Sir iceren dosyalarin YOLLARINI dondurur (deger asla)."""
    degerler = kasa_degerleri() if degerler is None else degerler
    bulgu = []
    for goreli in dosyalar:
        yol = Path(kok) / goreli
        try:
            metin = yol.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(v in metin for v in degerler) or ANAHTAR_DESENI.search(metin):
            bulgu.append(goreli)
    return bulgu


# ------------------------------------------------------------------ kapilar

def uzak_adresi(kok: Path) -> str:
    r = _git(kok, "remote", "get-url", "origin")
    return r.stdout.strip() if r.returncode == 0 else ""


def gorunurluk_gh(uzak: str) -> str:
    """GitHub'a sorar: PRIVATE / PUBLIC / '' (olculemedi)."""
    m = re.search(r"github\.com[/:]([^/]+/[^/.]+)", uzak)
    if not m:
        return ""
    try:
        r = subprocess.run(["gh", "repo", "view", m.group(1), "--json", "visibility"],
                           capture_output=True, text=True, timeout=60)
        return json.loads(r.stdout).get("visibility", "") if r.returncode == 0 else ""
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return ""


def gonder(neden: str = "elle", *, kok: Path = None, db_yolu: Path = None,
           gorunurluk=gorunurluk_gh, degerler: list = None) -> dict:
    """Defteri metne doker, isler, UC KAPIDAN gecerse gonderir.

    Donus: {"durum": "gonderildi"|"degisiklik_yok"|"reddedildi"|"hata",
            "sebep", "commit"}
    """
    kok = Path(kok or PROJE_KOKU)
    from .db import VARSAYILAN_YOL
    db_yolu = Path(db_yolu or VARSAYILAN_YOL)
    ayar = ayar_oku()
    if not ayar.get("acik", True):
        return {"durum": "reddedildi", "sebep": "depo gonderimi ayarda KAPALI"}

    # 1. ADRES
    uzak = uzak_adresi(kok)
    if not uzak:
        return {"durum": "reddedildi", "sebep": "origin tanimli degil"}
    if uzak.rstrip("/") != ayar["uzak"].rstrip("/"):
        return {"durum": "reddedildi",
                "sebep": f"origin BEKLENEN adres degil: {uzak} (beklenen {ayar['uzak']})"}

    # 2. GIZLILIK
    gor = gorunurluk(uzak)
    if gor != "PRIVATE":
        return {"durum": "reddedildi",
                "sebep": f"depo gizli degil ya da olculemedi (gorunurluk: {gor or 'bilinmiyor'})"}

    # Defter metni -- yalniz defter varsa (sinama/yeni kurulum icin).
    if db_yolu.exists():
        defteri_metne_yaz(db_yolu, kok / DISARI)

    if _git(kok, "add", "-A").returncode != 0:
        return {"durum": "hata", "sebep": "git add dustu"}
    r = _git(kok, "diff", "--cached", "--name-only", "-z")
    degisen = [d for d in r.stdout.split("\0") if d]
    if not degisen:
        return {"durum": "degisiklik_yok", "sebep": ""}

    # 3. SIR ve BOYUT -- islemeden ONCE; reddedilirse sahneleme geri alinir.
    buyuk = [d for d in degisen if (kok / d).exists()
             and (kok / d).stat().st_size > AZAMI_DOSYA_MB * 1e6]
    sirli = sir_tara(kok, [d for d in degisen if (kok / d).exists()], degerler)
    if buyuk or sirli:
        _git(kok, "reset", "-q")
        neden_ = []
        if sirli:
            neden_.append("SIR iceren dosya: " + ", ".join(sirli))
        if buyuk:
            neden_.append(f"{AZAMI_DOSYA_MB} MB ustu dosya: " + ", ".join(buyuk))
        return {"durum": "reddedildi", "sebep": " · ".join(neden_)}

    zaman = _dt.datetime.now().isoformat(timespec="seconds")
    c = _git(kok, "commit", "-q", "-m", f"Otomatik yedek: {neden} ({zaman})\n\n"
             f"{len(degisen)} dosya.")
    if c.returncode != 0:
        return {"durum": "hata", "sebep": f"commit dustu: {c.stderr.strip()[:200]}"}
    # Faz etiketleri de gider: "F1 bittiginde kod neydi" depoda da okunabilsin.
    p = _git(kok, "push", "-q", "origin", "HEAD", "--tags", zaman_asimi=300)
    if p.returncode != 0:
        # Commit YEREL olarak kaldi; bir sonraki gonderim onu da goturur.
        return {"durum": "hata", "sebep": f"push dustu: {p.stderr.strip()[:200]}"}
    ayar["son"] = zaman
    ayar_yaz(ayar)
    return {"durum": "gonderildi", "sebep": "", "dosya": len(degisen),
            "commit": _git(kok, "rev-parse", "--short", "HEAD").stdout.strip()}
