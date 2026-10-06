# -*- coding: utf-8 -*-
"""IS BASINA GIT KAYDI (06.10.2026, Asama 4 / K13; patron: "is basina kayit").

Patronun projesi KENDI git deposuysa, lider bir isi kabul edip kapatinca
ofis YALNIZ o isin degistirdigi dosyalari tek bir git kaydina koyar:
`#12 sepet sayfasi`. Her is gecmiste ayri gorunur ve tek basina geri
alinabilir (`geri_al` -> `git revert`).

Neden DAL degil: ayni takimin ajanlari ayni klasorde ayni anda calisir
(yazma kilidi ancak cakisma fiziksel olarak mumkunse anlamli -- kurulus
karari). Tek klasorde ayni anda iki dal acilamaz; is basina kopya klasor
(worktree) buyuk bir mimari degisiklik olurdu. Patron kaydi secti.

Kurallar (her biri bir yanlisi onler):

* **Depo YOKSA hicbir sey yapilmaz** -- patronun klasorunde `git init`
  sormadan acilmaz.
* **Yalniz isin dosyalari**: kaynak defterin OLCTUGU degisiklikler
  (`degisim` tablosu, isin kimligiyle); atfi belirsiz (paralel iste
  hangisinin yazdigi olculemeyen) dosya alinmaz -- baska isin yarim
  isini kayda katmak yanlis gecmis olurdu. `git commit --only <yollar>`:
  patronun kendi HAZIRLADIGI (staged) degisiklikler kayda karismaz.
* **Yoksayilan dosya** (`.gitignore`) alinmaz; `.ofis/` zaten yoksayilir.
* **Kanca atlanmaz** (`--no-verify` YOK): deponun kendi kurali calisir;
  kanca reddederse kayit yapilmaz ve bu SOYLENIR.
* Kimlik: deponun kendi `user.name/email`i; yoksa "AgentOfis".
* Hata isi DURDURMAZ: is kapanmistir; kayit yapilamazsa `uyari` olayi.
* Ayar `git_is_kaydi` (varsayilan acik, Ayarlar > Calisma).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

AYAR = "git_is_kaydi"
ZAMAN_ASIMI = 120


def acik_mi(db, proje_id: str) -> bool:
    return (db.ayar_oku(proje_id, AYAR, "acik") or "acik") != "kapali"


def _git(kok, *arg, girdi: bytes = None):
    from .surec import PENCERE_YOK
    # `--literal-pathspecs`: dosya adindaki `*`/`:` git'te desen sayilmasin.
    return subprocess.run(["git", "--literal-pathspecs", "-C", str(kok), *arg], input=girdi,
                          capture_output=True, timeout=ZAMAN_ASIMI,
                          creationflags=PENCERE_YOK)


def depo_mu(kok) -> bool:
    if not kok or not Path(kok).is_dir():
        return False
    try:
        r = _git(kok, "rev-parse", "--is-inside-work-tree")
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and r.stdout.strip() == b"true"


def _isin_dosyalari(db, gorev_id: str) -> tuple:
    """(alinacak, belirsiz) -- kok-goreli yollar."""
    with db.baglanti() as c:
        rows = c.execute("SELECT yol, atif_belirsiz FROM degisim WHERE gorev_id = ?",
                         (gorev_id,)).fetchall()
    alin, belirsiz = [], []
    for r in rows:
        y = (r["yol"] or "").strip()
        if not y or y.startswith(".ofis/") or y == ".ofis":
            continue
        (belirsiz if r["atif_belirsiz"] else alin).append(y)
    alin = sorted(set(alin))
    return alin, sorted(set(belirsiz) - set(alin))


def _degisenler(kok, yollar: list) -> list:
    """Yollardan gercekten degismis ve yoksayilmamis olanlar (git'in olcumu)."""
    r = _git(kok, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *yollar)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or b"").decode("utf-8", "replace").strip()[:300])
    out, parcalar, i = [], r.stdout.split(b"\0"), 0
    while i < len(parcalar):
        p = parcalar[i]
        i += 1
        if len(p) < 4:
            continue
        hal, yol = p[:2].decode("ascii", "replace"), p[3:].decode("utf-8", "replace")
        if hal[0] in "RC":          # yeniden adlandirma: kaynak yol sonraki parca
            i += 1
        out.append(yol)
    return out


def _kimlik(kok) -> list:
    r = _git(kok, "config", "user.email")
    if r.returncode == 0 and r.stdout.strip():
        return []
    return ["-c", "user.name=AgentOfis", "-c", "user.email=agentofis@yerel"]


def kaydet(db, pid: str, kok: str, gorev: dict, *, kapatan: str = "") -> dict | None:
    """Kapanan isin dosyalarini tek git kaydina koyar. Doner: kayit ya da None.

    `kok`: isin kok klasoru (`tahta.gorev_koku`). Hicbir istisna disari
    cikmaz: is kapanmistir, kayit eki bir islemdir.
    """
    try:
        if not acik_mi(db, pid):
            return None
        if not depo_mu(kok):
            return None
        alin, belirsiz = _isin_dosyalari(db, gorev["id"])
        if not alin:
            return None
        # Kok deponun ALT klasoru olabilir; git'in `status --porcelain` yollari
        # DEPO KOKUNE goredir. Her sey depo kokunde, onekli yolla yapilir.
        ust = _git(kok, "rev-parse", "--show-toplevel").stdout.decode("utf-8").strip()
        onek = _git(kok, "rev-parse", "--show-prefix").stdout.decode("utf-8").strip()
        kok = ust or kok
        degisen = _degisenler(kok, [onek + y for y in alin])
        if not degisen:
            return None
        r = _git(kok, "add", "-A", "--", *degisen)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or b"").decode("utf-8", "replace").strip()[:300])
        mesaj = (f"#{gorev['no']} {gorev['baslik']}\n\n"
                 f"Ajan: {gorev.get('sahip') or '-'}\n"
                 f"Kabul eden: {kapatan or '-'}\n"
                 "AgentOfis is kaydi")
        r = _git(kok, *_kimlik(kok), "commit", "--only", "-F", "-", "--", *degisen,
                 girdi=mesaj.encode("utf-8"))
        if r.returncode != 0:
            hata = ((r.stderr or b"") + (r.stdout or b"")).decode("utf-8", "replace").strip()
            raise RuntimeError(hata[:400] or f"git commit cikis {r.returncode}")
        h = _git(kok, "rev-parse", "HEAD").stdout.decode().strip()
        kayit = {"commit": h, "dosyalar": degisen, "belirsiz": belirsiz}
        db.olay_yaz(pid, "git_kaydi",
                    f"#{gorev['no']}: {h} ({len(degisen)} dosya)"
                    + (f" -- atfi belirsiz {len(belirsiz)} dosya ALINMADI: {', '.join(belirsiz[:5])}"
                       if belirsiz else ""),
                    ajan_ad=kapatan or "ofis", gorev_id=gorev["id"])
        return kayit
    except Exception as exc:            # noqa: BLE001 -- is kapandi; kayit eki, SOYLENIR
        try:
            db.olay_yaz(pid, "uyari", f"#{gorev.get('no')} git kaydi yapilamadi: {exc}",
                        gorev_id=gorev.get("id"))
        except Exception:                # noqa: BLE001
            pass
        return None


def isin_kaydi(db, proje_id: str, gorev_id: str) -> str:
    """Isin son git kaydi (commit kimligi) ya da ''."""
    with db.baglanti() as c:
        r = c.execute("SELECT govde FROM olay WHERE proje_id = ? AND gorev_id = ? "
                      "AND tur = 'git_kaydi' ORDER BY rowid DESC LIMIT 1",
                      (proje_id, gorev_id)).fetchone()
    if not r:
        return ""
    parca = (r["govde"] or "").split(":", 1)[-1].strip().split(" ", 1)[0]
    return parca


def geri_al(ofis, no: int) -> dict:
    """Isin git kaydini geri alir (`git revert`): YENI bir kayit acar, gecmis
    silinmez. Yalniz insan cagirir (panel/kabuk). Cakisirsa yarim birakilmaz
    (`revert --abort`) ve sebep soylenir."""
    g = ofis.tahta.gorev(no)
    kok = ofis.tahta.gorev_koku(g)
    kisa = isin_kaydi(ofis.db, ofis.proje_id, g["id"])
    if not kisa:
        raise ValueError(f"#{no} icin ofisin yaptigi git kaydi yok.")
    if not depo_mu(kok):
        raise ValueError("Isin klasoru artik bir git deposu degil.")
    t = _git(kok, "rev-parse", "--verify", kisa + "^{commit}")
    if t.returncode != 0:
        raise ValueError(f"Kayit {kisa} depoda bulunamadi.")
    tam = t.stdout.decode().strip()
    r = _git(kok, *_kimlik(kok), "revert", "--no-edit", tam)
    if r.returncode != 0:
        _git(kok, "revert", "--abort")
        hata = ((r.stderr or b"") + (r.stdout or b"")).decode("utf-8", "replace").strip()
        raise ValueError(f"Geri alinamadi (sonraki degisikliklerle cakisiyor olabilir): {hata[:300]}")
    yeni = _git(kok, "rev-parse", "HEAD").stdout.decode().strip()
    ofis.db.olay_yaz(ofis.proje_id, "git_geri_alindi", f"#{no}: {tam[:10]} -> {yeni[:10]}",
                     ajan_ad="insan", gorev_id=g["id"])
    return {"geri_alinan": tam, "yeni_kayit": yeni}
