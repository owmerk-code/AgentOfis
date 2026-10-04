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

from .surec import PENCERE_YOK
import tempfile
from pathlib import Path
from .yollar import OFIS_EVI

PROJE_KOKU = Path(__file__).resolve().parent.parent
DISARI = Path("veri") / "disari" / "ofis.sql"
BEKLENEN_UZAK = "https://github.com/owmerk-code/AgentOfis.git"
VARSAYILAN_AYAR = OFIS_EVI / "depo.json"
AZAMI_DOSYA_MB = 50

#: Bilinen anahtar bicimleri -- TEK yerde (gizli.py): maskeleme ve sir
#: taramasi ayni deseni kullanir.
from .gizli import ANAHTAR_DESENI  # noqa: E402


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
    # stdin kapali + GIT_TERMINAL_PROMPT=0: sifre isteyen push pencerede
    # BEKLEMEZ, hata verip biter.
    return subprocess.run(["git", *arg], cwd=kok, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=zaman_asimi,
                          stdin=subprocess.DEVNULL, creationflags=PENCERE_YOK,
                          env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))


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
            surum = dst.execute("PRAGMA user_version").fetchone()[0]
        finally:
            dst.close()
            src.close()
    # `iterdump` PRAGMA user_version TASIMAZ (27.09.2026 olculdu: metinden
    # geri kurulan defter 0'dan baslayip veri goclerini yeniden kosturacakti).
    satirlar.append(f"PRAGMA user_version={int(surum)};")
    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_name(hedef.name + ".part")
    gecici.write_text("\n".join(satirlar) + "\n", encoding="utf-8", newline="\n")
    os.replace(gecici, hedef)
    return {"satir": len(satirlar), "boyut": hedef.stat().st_size}


# ------------------------------------------------------- metin -> defter

#: Dokumun son satiri. `iterdump` PRAGMA user_version TASIMAZ (27.09.2026
#: olculdu: geri kurulan defterde surum 0 cikti, oysa asli 1'di).
SURUM_DESENI = re.compile(r"^PRAGMA user_version=(\d+);\r?$", re.M)


def _surumsuz(metin: str) -> str:
    return SURUM_DESENI.sub("", metin).rstrip("\n")


def metinden_defter(sql_yolu: Path, hedef: Path, *, surum: int | None = None) -> dict:
    """Metin dokumunden defteri GERI KURAR -- bos yere, OLCULEREK.

    27.09.2026: baska bir ajan araci (OpenCode, `create-tauri-app ...
    --yes`) `Desktop\\agentofis` yolunu sildi; Windows buyuk/kucuk harf
    ayirmadigi icin silinen bizim `AgentOfis` klasorumuzdu. Kod GitHub'dan
    geri geldi; defteri bu dokumden ELLE kurdum ve iki hata cikti:

    1. **Satir sonu cevrildi.** Dokumu `read_text` ile okudum; o
       evrensel satir sonu kipinde okur ve metin DEGERLERININ icindeki
       `\\r\\n`'leri `\\n`e cevirir. 339 karakter sessizce kayboldu;
       `integrity_check` "ok" dedi. Yakalayan tek sey geri donus
       karsilastirmasiydi: kurulan defterin dokumu asli ile bayt bayt
       ayni degildi.
    2. **Veri gocu surumu kayboldu.** `iterdump` `PRAGMA user_version`
       tasimiyor; kurulan defter 0'dan baslayip veri goclerini yeniden
       kosturacakti. Dokum artik surumu son satir olarak yaziyor.

    Kurallar:

    * **Canli defterin ustune yazmaz.** Hedef (ya da onun -wal/-shm'si)
      varsa REDDEDER; `yedek.geri_yukle`nin "yalniz BOS klasore" kuraliyla
      ayni. Canliyi degistirmek insanin karari.
    * **Geri donus olculur.** Kurulan defter yeniden dokulur ve kaynak
      metinle (surum satiri disinda) BIREBIR ayni olmalidir; degilse
      metinde defterde karsiligi olmayan bir sey vardir (elle
      duzenlenmis, bozulmus, ya da okuma cevirmis) ve kurulum
      REDDEDILIR. `integrity_check` bunu goremez: kayip veri tutarli
      bir defter birakir.
    * **Atomik:** `.part`'a kurulur, olculur, sonra adi verilir. Yarim
      kurulum hedefte kalmaz.
    * Eski bicimde (surum satiri olmayan) dokumde surum `surum` ile
      verilebilir; verilmezse 0 kalir ve bu SOYLENIR: veri gocleri
      bir sonraki acilista yeniden kosar.
    """
    sql_yolu, hedef = Path(sql_yolu), Path(hedef)
    for ek in ("", "-wal", "-shm"):
        if Path(str(hedef) + ek).exists():
            raise DepoHatasi(
                f"{hedef.name}{ek} zaten var -- geri kurulum CANLI defterin "
                f"ustune yazmaz. Bos bir yol ver; degistirmek senin kararin.")
    # SATIR SONU CEVRILMEDEN oku: degerlerin icindeki \r\n korunmali.
    with open(sql_yolu, encoding="utf-8", newline="") as f:
        sql = f.read()
    m = SURUM_DESENI.search(sql)
    dokum_surumu = int(m.group(1)) if m else None
    if dokum_surumu is not None:
        kaynak = "dokum"
    elif surum is not None:
        kaynak = "elle"
    else:
        kaynak = "yok"

    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_name(hedef.name + ".part")
    if gecici.exists():
        gecici.unlink()
    try:
        c = sqlite3.connect(str(gecici))
        try:
            c.executescript(sql)
            if dokum_surumu is None and surum is not None:
                c.execute(f"PRAGMA user_version = {int(surum)}")
            c.commit()
            butunluk = c.execute("PRAGMA integrity_check").fetchone()[0]
            son_surum = c.execute("PRAGMA user_version").fetchone()[0]
            sayilar = {t: c.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
                       for (t,) in c.execute(
                           "SELECT name FROM sqlite_master WHERE type='table' "
                           "AND name NOT LIKE 'sqlite_%'").fetchall()}
        finally:
            c.close()
        if butunluk != "ok":
            raise DepoHatasi(f"kurulan defter butunluk denetiminden gecmedi: {butunluk}")
        with tempfile.TemporaryDirectory(prefix="ofis-depo-geri-") as tmp:
            geri = Path(tmp) / "geri.sql"
            defteri_metne_yaz(gecici, geri)
            with open(geri, encoding="utf-8", newline="") as f:
                geri_metin = f.read()
        if _surumsuz(geri_metin) != _surumsuz(sql):
            raise DepoHatasi(
                "kurulan defter kaynak metni BIREBIR vermiyor -- metinde "
                "defterde karsiligi olmayan bir sey var (elle duzenlenmis ya "
                "da bozulmus olabilir). Kurulum REDDEDILDI; canli bir sey "
                "degismedi.")
    except sqlite3.Error as exc:
        if gecici.exists():
            gecici.unlink()
        raise DepoHatasi(f"metin defter olarak kurulamadi: {exc}")
    except DepoHatasi:
        if gecici.exists():
            gecici.unlink()
        raise
    os.replace(gecici, hedef)
    return {"hedef": str(hedef), "surum": son_surum, "surum_kaynagi": kaynak,
            "tablo": sayilar}


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
                           capture_output=True, text=True, timeout=60,
                           stdin=subprocess.DEVNULL, creationflags=PENCERE_YOK)
        return json.loads(r.stdout).get("visibility", "") if r.returncode == 0 else ""
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return ""


def _gonderilmemis_dosyalar(kok: Path):
    """(commit sayisi, dosyalar) -- uzakta olmayan yerel commit'ler.

    Uzak dal hic yoksa (ilk gonderim) butun gecmis gonderilmemistir.
    Olculemezse None: o zaman gonderim yine denenir, git kendisi karar verir.
    """
    dal = _git(kok, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    uzak_dal = f"origin/{dal}"
    if _git(kok, "rev-parse", "--verify", "-q", uzak_dal).returncode != 0:
        aralik = ["HEAD"]
    else:
        aralik = [f"{uzak_dal}..HEAD"]
    r = _git(kok, "rev-list", "--count", *aralik)
    if r.returncode != 0:
        return None
    sayi = int(r.stdout.strip() or 0)
    if not sayi:
        return (0, [])
    if aralik == ["HEAD"]:
        d = _git(kok, "ls-files", "-z")
    else:
        d = _git(kok, "diff", "--name-only", "-z", aralik[0])
    return (sayi, [x for x in d.stdout.split("\0") if x])


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
    # Yerelde islenmis ama GONDERILMEMIS commit'ler de gider. Ilk surum
    # yalniz sahnelenmis degisikligi goruyordu: elle islenen bir commit
    # "degisiklik yok" denip GitHub'a HIC gitmiyordu (gercek kosuda cikti).
    gonderilmemis = _gonderilmemis_dosyalar(kok)
    if not degisen and gonderilmemis is not None and not gonderilmemis[0]:
        # Degisiklik yok ama yeni bir FAZ ETIKETI olabilir (olculdu:
        # `f1-bitti` bu yolda hic gitmedi). Etiket sir tasimaz -- zaten
        # gonderilmis bir commit'i isaret eder; uc kapi yukarida gecildi.
        _git(kok, "push", "-q", "origin", "--tags", zaman_asimi=120)
        return {"durum": "degisiklik_yok", "sebep": ""}
    taranacak = sorted(set(degisen) | set((gonderilmemis or ([], []))[1]))

    # 3. SIR ve BOYUT -- islemeden ONCE; reddedilirse sahneleme geri alinir.
    buyuk = [d for d in taranacak if (kok / d).exists()
             and (kok / d).stat().st_size > AZAMI_DOSYA_MB * 1e6]
    sirli = sir_tara(kok, [d for d in taranacak if (kok / d).exists()], degerler)
    if buyuk or sirli:
        _git(kok, "reset", "-q")
        neden_ = []
        if sirli:
            neden_.append("SIR iceren dosya: " + ", ".join(sirli))
        if buyuk:
            neden_.append(f"{AZAMI_DOSYA_MB} MB ustu dosya: " + ", ".join(buyuk))
        return {"durum": "reddedildi", "sebep": " · ".join(neden_)}

    zaman = _dt.datetime.now().isoformat(timespec="seconds")
    if degisen:
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
    return {"durum": "gonderildi", "sebep": "", "dosya": len(taranacak),
            "commit": _git(kok, "rev-parse", "--short", "HEAD").stdout.strip()}
