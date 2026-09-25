# -*- coding: utf-8 -*-
"""Geri al: bir ajan TURUNUN diskte yaptigini, yalniz onu, geri almak.

PLAN F1, E03. Yedek (`yedek.py`) BUTUN ofisi bir gune geri goturur;
aradaki her sey gider. Bir ajan tek bir dosyayi bozdugunda gereken sey
bu degil: **yalniz o turun dokundugu dosyalar**, turdan onceki hallerine.

## Nasil -- golge depo

Her turun ONCESINDE ve SONRASINDA proje kokunun anlik goruntusu ayri bir
git deposuna islenir. Depo proje kokunun DISINDA (`~/.agentofis/golge`):

* Ajan ona ulasamaz (`--restricted` kokun disina cikarmaz) -- geri alma
  kaydini ajan silemez.
* Projenin kendi git deposuna karismaz (`--git-dir` ayri, `--work-tree`
  kok).
* Git ikili dosyayi da, buyugu de saklar ve ayni icerigi bir kez saklar.
  `degisim.py`nin anlik goruntusu buyuk/ikili dosyanin ICERIGINI tutmaz
  (yalniz ozet); geri almak icin icerik gerekir.

Olcum ile ayni dosyalar izlenir: `degisim.ATLANAN_KLASOR/UZANTI` ve
ofisin kendi defteri disarida. Iki ayri kural olsaydi geri alma, olcumun
hic gostermedigi bir dosyayi degistirebilirdi.

## Uc kural

1. **Sonraki isi EZMEZ.** Turdan SONRA ayni dosya yeniden degistiyse
   (baska ajan, insan) geri alma REDDEDILIR ve hangi dosyalar oldugu
   soylenir. `zorla` ile gecilir -- o zaman o sonraki is de gider ve bu
   bilerek secilmistir.
2. **Kosan tur varken yapilmaz** (`zorla` haric): yazilmakta olan bir
   dosyanin altindan cekmek, ajanin gordugu ile diskin ayrismasidir.
3. **Geri alma da geri alinabilir.** Geri almanin kendisi yeni bir kayit
   olur (once/sonra); yanlis tura basildiysa o kayit geri alinir.

Paralel turda (`atif_belirsiz`) fark kimin oldugunu soyleyemez: o turu
geri almak komsunun dosyasini da geri alabilir -- `zorla` ister.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

from .db import simdi

VARSAYILAN_GOLGE_KOK = Path.home() / ".agentofis" / "golge"
_KILITLER: dict = {}
_KILITLER_KILIDI = threading.Lock()


class GeriAlHatasi(RuntimeError):
    pass


def golge_koku(kok=None) -> Path:
    """Golge depolarin klasoru.

    Gecici klasordeki bir proje (sinamalar, deneme ofisleri) golgesini de
    GECICI klasore yazar: ilk surumde her test kosusu gercek ev klasorune
    golge depo birakti.
    """
    if os.environ.get("OFIS_GOLGE_KOK"):
        return Path(os.environ["OFIS_GOLGE_KOK"])
    if kok is not None:
        gecici = Path(tempfile.gettempdir()).resolve()
        try:
            Path(kok).resolve().relative_to(gecici)
            return gecici / "ofis-golge"
        except ValueError:
            pass
    return VARSAYILAN_GOLGE_KOK


def sahipsizleri_temizle(klasor: Path) -> list:
    """Kok'u artik olmayan golge depolari siler (her depo kokunu yazar)."""
    silinen = []
    if not klasor.is_dir():
        return silinen
    for d in klasor.glob("*.git"):
        not_ = d / "ofis-kok.txt"
        try:
            kok = not_.read_text(encoding="utf-8").strip()
        except OSError:
            continue          # kimin oldugunu bilmedigimizi SILMEYIZ
        if kok and not Path(kok).exists():
            shutil.rmtree(d, onexc=lambda f, y, e: (os.chmod(y, 0o700), f(y)))
            silinen.append(d.name)
    return silinen


def _kilit(anahtar: str) -> threading.Lock:
    # Paralel turlar ayni surecte IPLIK olarak kosar; ayni golge depoya
    # ayni anda iki `git add` index.lock ile duser.
    with _KILITLER_KILIDI:
        return _KILITLER.setdefault(anahtar, threading.Lock())


class Golge:
    def __init__(self, kok, haric=()):
        self.kok = Path(kok).resolve()
        ad = hashlib.sha1(os.path.normcase(str(self.kok)).encode("utf-8")).hexdigest()[:16]
        self.git_dir = golge_koku(self.kok) / f"{ad}.git"
        self.haric = tuple(haric or ())
        self._kilit = _kilit(str(self.git_dir))

    # ------------------------------------------------------------ git
    def _git(self, *arg, girdi: bytes = None, metin: bool = True):
        ortam = {k: v for k, v in os.environ.items()
                 if not k.startswith("GIT_")}
        ortam["GIT_DIR"] = str(self.git_dir)
        ortam["GIT_WORK_TREE"] = str(self.kok)
        r = subprocess.run(["git", *arg], cwd=self.kok, input=girdi,
                           capture_output=True, env=ortam, timeout=300)
        if metin:
            r.stdout = r.stdout.decode("utf-8", "replace")
        r.stderr = r.stderr.decode("utf-8", "replace")
        return r

    def _hazirla(self) -> None:
        if (self.git_dir / "HEAD").exists():
            self._dislama_yaz()
            return
        self.git_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            sahipsizleri_temizle(self.git_dir.parent)
        except OSError:
            pass              # temizlik isi DURDURMAZ
        r = subprocess.run(["git", "init", "-q", "--bare", str(self.git_dir)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise GeriAlHatasi(f"golge depo kurulamadi: {r.stderr.strip()}")
        for k, v in (("core.bare", "false"), ("core.autocrlf", "false"),
                     ("core.quotepath", "false"), ("core.longpaths", "true"),
                     ("user.name", "ofis-golge"), ("user.email", "golge@yerel"),
                     ("gc.auto", "256")):
            self._git("config", k, v)
        (self.git_dir / "ofis-kok.txt").write_text(str(self.kok), encoding="utf-8")
        self._dislama_yaz()

    def _dislama_yaz(self) -> None:
        from . import degisim
        satirlar = [f"{k}/" for k in sorted(degisim.ATLANAN_KLASOR)]
        satirlar += [f"*{u}" for u in sorted(degisim.ATLANAN_UZANTI)]
        for h in self.haric:
            try:
                rel = Path(h).resolve().relative_to(self.kok).as_posix()
                satirlar.append("/" + rel)
            except (ValueError, OSError):
                pass
        yol = self.git_dir / "info" / "exclude"
        yol.parent.mkdir(parents=True, exist_ok=True)
        yeni = "\n".join(satirlar) + "\n"
        if not yol.exists() or yol.read_text(encoding="utf-8") != yeni:
            yol.write_text(yeni, encoding="utf-8")

    # ------------------------------------------------------- anlik
    def anlik(self, etiket: str) -> str:
        """Kokun o anki halini isler, commit kimligini dondurur."""
        with self._kilit:
            self._hazirla()
            r = self._git("add", "-A", ".")
            if r.returncode != 0:
                raise GeriAlHatasi(f"golge git add dustu: {r.stderr.strip()[:300]}")
            r = self._git("commit", "-q", "--allow-empty", "--no-verify",
                          "-m", etiket[:200])
            if r.returncode != 0:
                raise GeriAlHatasi(f"golge commit dustu: {r.stderr.strip()[:300]}")
            return self._git("rev-parse", "HEAD").stdout.strip()

    def fark(self, once: str, sonra: str) -> list:
        """[(hal, yol)] -- hal: A eklendi / M degisti / D silindi."""
        r = self._git("diff", "--name-status", "--no-renames", "-z", once, sonra)
        if r.returncode != 0:
            raise GeriAlHatasi(f"golge fark okunamadi: {r.stderr.strip()[:300]}")
        parca = [p for p in r.stdout.split("\0") if p]
        return [(parca[i][0], parca[i + 1]) for i in range(0, len(parca) - 1, 2)]

    def blob(self, commit: str, yol: str):
        """Dosyanin o committeki baytlari; yoksa None."""
        r = self._git("rev-parse", "-q", "--verify", f"{commit}:{yol}")
        if r.returncode != 0:
            return None
        return self._git("cat-file", "blob", r.stdout.strip(), metin=False).stdout

    def blob_ozeti(self, commit: str, yol: str):
        r = self._git("rev-parse", "-q", "--verify", f"{commit}:{yol}")
        return r.stdout.strip() if r.returncode == 0 else None

    def diskteki_ozet(self, yol: str):
        p = self.kok / yol
        if not p.is_file():
            return None
        r = self._git("hash-object", "--no-filters", "--", yol)
        return r.stdout.strip() if r.returncode == 0 else None


# ---------------------------------------------------------------- defter

def kaydet(db, proje_id: str, gorev_id, ajan_ad: str, kok, once: str,
           sonra: str, dosya: int, atif_belirsiz: bool = False,
           not_: str = "") -> str:
    kimlik = uuid.uuid4().hex
    with db.baglanti() as conn:
        conn.execute(
            "INSERT INTO tur_anlik (id, proje_id, gorev_id, ajan_ad, kok, once,"
            " sonra, dosya, atif_belirsiz, not_, olusturuldu)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (kimlik, proje_id, gorev_id, ajan_ad, str(kok), once, sonra,
             int(dosya), 1 if atif_belirsiz else 0, not_, simdi()))
    return kimlik


def liste(db, proje_id: str, limit: int = 20) -> list:
    with db.baglanti() as conn:
        rows = conn.execute(
            "SELECT t.*, g.no AS gorev_no, g.baslik AS gorev_baslik"
            " FROM tur_anlik t LEFT JOIN gorev g ON g.id = t.gorev_id"
            " WHERE t.proje_id = ? ORDER BY t.olusturuldu DESC, t.rowid DESC"
            " LIMIT ?", (proje_id, limit)).fetchall()
    return [dict(r) for r in rows]


def bul(db, proje_id: str, kimlik: str) -> dict:
    """Tam ya da BENZERSIZ kisa kimlik. Iki kaydin ilkini secmek, insanin
    kastetmedigi bir turu geri almak olurdu."""
    with db.baglanti() as conn:
        rows = conn.execute(
            "SELECT * FROM tur_anlik WHERE proje_id = ? AND id LIKE ?",
            (proje_id, kimlik + "%")).fetchall()
    if not rows:
        raise GeriAlHatasi(f"Boyle bir tur kaydi yok: {kimlik}")
    if len(rows) > 1:
        raise GeriAlHatasi(f"Kisa kimlik belirsiz ({len(rows)} kayit): daha uzun yaz.")
    return dict(rows[0])


# --------------------------------------------------------------- geri al

def geri_al(ofis, kimlik: str, *, sebep: str, zorla: bool = False,
            haric=()) -> dict:
    """Bir turun degistirdigi dosyalari turdan onceki hallerine dondurur."""
    if not (sebep or "").strip():
        raise GeriAlHatasi("Sebep zorunlu: 'bu dosya neden eski haline dondu' "
                           "sorusu alti ay sonra da cevaplanmali.")
    k = bul(ofis.db, ofis.proje_id, kimlik)
    if k["geri_alindi"]:
        raise GeriAlHatasi(f"Bu tur zaten geri alindi ({k['geri_alindi']}).")
    golge = Golge(k["kok"], haric)
    if not golge.git_dir.exists():
        raise GeriAlHatasi("Golge depo yok; bu turun onceki hali saklanmamis.")

    engel = []
    if not zorla:
        kosan = [g for g in ofis.tahta.liste(durum="calisiyor")]
        if kosan:
            engel.append(f"su an {len(kosan)} is calisiyor (#"
                         + ", #".join(str(g["no"]) for g in kosan) + ")")
        if k["atif_belirsiz"]:
            engel.append("tur paralel kostu; fark komsu turun dosyalarini da "
                         "iceriyor olabilir")

    degisen = golge.fark(k["once"], k["sonra"])
    sonradan = []
    for _hal, yol in degisen:
        if golge.diskteki_ozet(yol) != golge.blob_ozeti(k["sonra"], yol):
            sonradan.append(yol)
    if sonradan and not zorla:
        engel.append("turdan SONRA yeniden degisen dosya: " + ", ".join(sonradan[:10]))
    if engel:
        raise GeriAlHatasi("Geri alinmadi -- " + " · ".join(engel)
                           + ". Bilerek yapmak icin: --zorla")

    etiket = f"geri alma oncesi ({k['id'][:8]})"
    oncesi = golge.anlik(etiket)
    geri = []
    for hal, yol in degisen:
        hedef = golge.kok / yol
        eski = golge.blob(k["once"], yol)
        if eski is None:
            if hedef.exists():
                hedef.unlink()
            geri.append(("silindi", yol))
        else:
            hedef.parent.mkdir(parents=True, exist_ok=True)
            gecici = hedef.with_name(hedef.name + ".geri-al.part")
            gecici.write_bytes(eski)
            os.replace(gecici, hedef)
            geri.append(("eski haline dondu", yol))
    sonrasi = golge.anlik(f"geri alindi ({k['id'][:8]})")

    an = simdi()
    yeni = kaydet(ofis.db, ofis.proje_id, k["gorev_id"], "insan (geri alma)",
                  k["kok"], oncesi, sonrasi, len(geri),
                  not_=f"{k['id'][:8]} turunun geri alinmasi")
    with ofis.db.baglanti() as conn:
        conn.execute("UPDATE tur_anlik SET geri_alindi = ? WHERE id = ?",
                     (f"{an} · {yeni[:8]}", k["id"]))
    ozet = ", ".join(y for _h, y in geri[:8]) + (" …" if len(geri) > 8 else "")
    ofis.db.olay_yaz(ofis.proje_id, "geri_alindi",
                     f"{k['ajan_ad']} turu geri alindi ({len(geri)} dosya): {ozet}",
                     ajan_ad=k["ajan_ad"], gorev_id=k["gorev_id"])
    ofis.bellek.karar_yaz(
        f"{k['ajan_ad']} ajaninin {k['id'][:8]} turu geri alindi "
        f"({len(geri)} dosya).", sebep, "insan", tur="teknik",
        gorev_id=k["gorev_id"], etkilenen_yollar=[y for _h, y in geri])
    return {"dosyalar": geri, "yeni_kayit": yeni, "zorla": zorla,
            "sonradan_ezilen": sonradan if zorla else []}
