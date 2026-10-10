# -*- coding: utf-8 -*-
"""OFIS KENDINI GELISTIRIR, KENDINI KURMAZ (09.10.2026, patron: "ajanlar
agent sistemi de gelistirebilecek mi" -- F1'den once).

Rakip (Murat) ajanlarinin sistemi gelistirdigini soyluyor. Calisan sistemin
KENDI kodunu degistiren ajan, altindaki zemini degistirir: bozarsa onu
duzeltecek ajan da kalmaz. Bizim yolumuz (kurulus karari "teslim eder,
insan inceler ve kurar"):

1. GELISTIRME TAKIMI ayri bir KOPYADA calisir: `Masaustu\\AgentOfis-gelistirme`
   (calisan kodun `git clone`u; yalniz KAYDEDILMIS kod). Kopyanin KENDI bos
   `ev/` klasoru vardir: yoksa kopyanin kodu evi bulamayip eski eve
   (`~/.agentofis`) duserdi (`yollar.varsayilan_ev`).
2. Is kapaninca iscinin dosyalari kopyada `#no baslik` kaydina girer (her
   proje gibi, `git_kaydi`). Ofis o kaydi alir ve kopyada TAM SINAMA TAKIMINI
   kosar (duman_*.py, cikis koduyla). OFIS_* ortami SILINEREK: panelin
   gercek evi sinamaya sizmasin (`_temizlik` bos `OFIS_EV`i kendisi kurar).
3. Sinama gecerse patrona KURULUM KARTI (siradan onay karti: panel, telefon,
   bildirim hazir). Gecmezse kart YOK; sebep isin sohbetine ve olaya.
4. Patron "Onayla" der -> kayit calisan depoya `cherry-pick` edilir (calisan
   depoda kaydedilmemis degisiklik varsa REDDEDILIR: kimsenin yarim isi
   ezilmez). Paneli patron yeniden baslatir. Geri alma `git revert`
   (`kabuk gelistirme geri-al <no>`). Reddedilen kayit kopyada geri alinir.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from .surec import PENCERE_YOK

SABLON = "gelistirme"
KLASOR_ADI = "AgentOfis-gelistirme"
#: Kart ayrintisinin ilk satiri: panelin onay ucu karti bundan tanir.
ISARET = "GELISTIRME_TESLIM:"
#: Sinama dosyasi basina sure siniri (tam takim ~45 dk; tek dosya 15 dk'yi asmaz).
DOSYA_SINIRI_SN = 900
GIT_SINIRI_SN = 120


class GelistirmeHatasi(RuntimeError):
    pass


def kaynak() -> Path:
    """Calisan ofisin kodu (kurulumun hedefi)."""
    ozel = (os.environ.get("OFIS_GELISTIRME_KAYNAK") or "").strip()
    if ozel:
        return Path(ozel).resolve()
    from .yollar import OFIS_KODU
    return OFIS_KODU.resolve()


def varsayilan_klasor() -> Path:
    ozel = (os.environ.get("OFIS_GELISTIRME_KLASOR") or "").strip()
    if ozel:
        return Path(ozel).resolve()
    from .yollar import MASAUSTU
    return MASAUSTU / KLASOR_ADI


def _git(kok, *arg, girdi: bytes = None, sure: float = GIT_SINIRI_SN):
    ortam = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_EDITOR="true")
    return subprocess.run(["git", "-C", str(kok), *arg], input=girdi, capture_output=True,
                          timeout=sure, env=ortam, creationflags=PENCERE_YOK)


def _metin(r) -> str:
    return ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", "replace").strip()


def _kimlik() -> list:
    return ["-c", "user.name=AgentOfis gelistirme", "-c", "user.email=gelistirme@agentofis.yerel"]


def kopya_mi(kok) -> bool:
    """Bu klasor ofisin gelistirme kopyasi mi (kaynagi calisan ofis)."""
    try:
        r = _git(kok, "config", "--get", "agentofis.gelistirme")
        return r.returncode == 0 and r.stdout.decode().strip() == "1"
    except (OSError, subprocess.SubprocessError):
        return False


def kopya_hazirla(hedef=None) -> str:
    """Kopyayi kurar (yoksa) ve eşitler. Doner: kopyanin mutlak yolu."""
    hedef = Path(hedef) if hedef else varsayilan_klasor()
    kay = kaynak()
    from .yollar import ofis_icinde_mi
    if ofis_icinde_mi(hedef):
        raise GelistirmeHatasi("Gelistirme kopyasi ofisin kendi yerinde olamaz.")
    if hedef.exists() and any(hedef.iterdir()) and not (hedef / ".git").exists():
        raise GelistirmeHatasi(f"{hedef} bos degil ve git deposu degil; baska bir klasor sec.")
    if not (hedef / ".git").exists():
        hedef.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["git", "clone", "--no-hardlinks", "-q", str(kay), str(hedef)],
                           capture_output=True, timeout=600, creationflags=PENCERE_YOK,
                           env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
        if r.returncode != 0:
            raise GelistirmeHatasi("Kopya kurulamadi: " + _metin(r)[:300])
        _git(hedef, "config", "agentofis.gelistirme", "1")
        # KOPYADAN GONDERME YOK: `origin` calisan ofisin deposu; `git push`
        # oraya yazardi. Kurulumun tek yolu patronun karti.
        _git(hedef, "remote", "set-url", "--push", "origin", "KAPALI-kurulum-yalniz-patron-kartiyla")
    # KOPYANIN KENDI EVI: yoksa kopyanin kodu eski eve (~/.agentofis) duser.
    (hedef / "ev").mkdir(exist_ok=True)
    esitle(hedef)
    try:
        bagimliliklari_kur(hedef)
    except GelistirmeHatasi:
        pass                          # sinamadan once yeniden denenir ve SOYLENIR
    return str(hedef.resolve())


def _kararli_mi(konu: str, cikar) -> bool:
    """Kayit konusu karara baglanmis bir ise mi ait (`#n ...` ya da onun
    `Revert "#n ..."` kaydi)."""
    for n in cikar or ():
        if konu.startswith(f"#{n} ") or konu.startswith(f'Revert "#{n} '):
            return True
    return False


def esitle(kok, cikar=()) -> dict:
    """Kopyayi calisan ofisin son KAYITLI koduna getirir; karar BEKLEYEN islerin
    kayitlari onun ustune tasinir.

    `cikar`: karara baglanmis (kurulmus/reddedilmis/geri alinmis) is numaralari
    -- kayitlari ve geri-alma kayitlari kopyadan DUSER. 10.10 F1 canli (#9):
    kopyada #5 (reddedildi) + onun geri alinisi + kurulmus #6 duruyordu; her
    esitleme onlari yeniden son kodun ustune koymaya calisti, #5 son kodla
    CAKISTI ve hic ilgisi olmayan #9 "kurulamaz" oldu."""
    r = _git(kok, "fetch", "-q", "origin")
    if r.returncode != 0:
        return {"tamam": False, "sebep": "fetch: " + _metin(r)[:200]}
    if _git(kok, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        return {"tamam": False, "sebep": "kopyada kaydedilmemis degisiklik var (calisan is)"}
    dal = _git(kok, "rev-parse", "--abbrev-ref", "origin/HEAD").stdout.decode().strip() or "origin/main"
    satirlar = _git(kok, "log", "--reverse", "--format=%H%x09%s", f"{dal}..HEAD").stdout.decode(
        "utf-8", "replace").splitlines()
    kayitlar = [s.partition("\t")[::2] for s in satirlar if s.strip()]
    kalan = [h for h, konu in kayitlar if not _kararli_mi(konu, cikar)]
    if len(kalan) == len(kayitlar):
        r = _git(kok, *_kimlik(), "rebase", "-q", dal)
        if r.returncode != 0:
            _git(kok, "rebase", "--abort")
            return {"tamam": False, "sebep": "rebase cakisti: " + _metin(r)[:200]}
        return {"tamam": True}
    # Kararlasmis kayitlar dusurulur: son kod + yalniz karar bekleyenler.
    yedek = _git(kok, "rev-parse", "HEAD").stdout.decode().strip()
    _git(kok, "reset", "-q", "--hard", dal)
    for h in kalan:
        r = _git(kok, *_kimlik(), "cherry-pick", h)
        if r.returncode != 0:
            _git(kok, "cherry-pick", "--abort")
            _git(kok, "reset", "-q", "--hard", yedek)      # kopya eski haline doner
            return {"tamam": False, "sebep": "rebase cakisti: " + _metin(r)[:200]}
    return {"tamam": True, "dusen": len(kayitlar) - len(kalan)}


def kararli_isler(db, pid: str) -> set:
    """Teslimi karara baglanmis is numaralari (kopyadan dusulecek kayitlar)."""
    out = set()
    with db.baglanti() as c:
        for (deger,) in c.execute("SELECT deger FROM ayar WHERE proje_id = ? AND anahtar LIKE ?",
                                  (pid, _kayit_anahtari("%"))):
            try:
                d = json.loads(deger or "{}")
            except ValueError:
                continue
            if d.get("durum") in ("kuruldu", "reddedildi", "geri_alindi") and d.get("no") is not None:
                out.add(d["no"])
    return out


def _isin_kayitlari(kok, no: int) -> list:
    """Kopyada `#no ` ile baslayan, calisan ofiste OLMAYAN kayitlar (eskiden yeniye)."""
    _git(kok, "fetch", "-q", "origin")
    dal = _git(kok, "rev-parse", "--abbrev-ref", "origin/HEAD").stdout.decode().strip() or "origin/main"
    r = _git(kok, "log", "--reverse", "--format=%H%x09%s", f"{dal}..HEAD")
    out = []
    for satir in r.stdout.decode("utf-8", "replace").splitlines():
        h, _, konu = satir.partition("\t")
        if konu.startswith(f"#{no} "):
            out.append({"commit": h, "konu": konu})
    return out


def _ozet(kok, kayitlar: list) -> str:
    satirlar = []
    for k in kayitlar:
        r = _git(kok, "show", "--stat", "--format=%h %s", k["commit"])
        satirlar.append(r.stdout.decode("utf-8", "replace").strip()[:1500])
    return "\n".join(satirlar)


#: Gelistirme takiminin BITTI TANIMI (takim kurulurken kite yazilir; patron
#: Ayarlar'dan degistirebilir). Claude ajani kopyanin CLAUDE.md'sini zaten
#: okur; codex ve gemini ajanlari bunu brifingden alir.
BITTI_TANIMI = [
    "Kod YALNIZ bu takimin klasorunde (gelistirme kopyasi) degisir; calisan ofisin koduna yazmak kapida REDDEDILIR.",
    "Her davranis degisikliginin sinamasi var (testler/duman_*.py); sinama, degisiklik geri alininca ATES ediyor.",
    "Ilgili sinama dosyalari kopyada gecti (kanit: komut + sonuc satiri). Tam takimi is kapaninca ofis kosar.",
    "Panel/arayuz degisikligi ONIZLEMEDE denendi: `python -m ofis.gelistirme onizle` (kopyanin kendi paneli, "
    "ayri defter), adres gomulu tarayicida acildi, tiklandi; ekran goruntusu kanit.",
    "Kurmak patronun karari: is kapaninca ofis tam sinamayi kosar, gecerse patrona kurulum karti gider.",
]
#: 09.10 F1 canli dersleri (#5, #6). Defter yolu kurulurken eklenir (bkz. `bitti_tanimi`).
BITTI_TANIMI_EK = [
    "Defterden OKUYAN/YAZAN degisiklik (kart, pano, rapor, hafiza) GERCEK DEFTERIN KOPYASINDA "
    "denendi: {defter} dosyasini sqlite3 backup ile gecici klasore kopyala (aslina YAZMA), "
    "her kayit icin sonucu kanita yaz. Sahte sinama sahnesi gercek defterdeki gibi kurulur "
    "(isci turu + liderin BASKA modelle inceleme turu, ret, kesinti). #5 yalniz isci turu "
    "kuran sinamayla gecti, gercek defterde 5 kartin 5'i yanlisti.",
    "Satir sonlari KORUNUR: `sed -i` ya da dosyayi toptan yeniden yazma YOK (dosyalar karisik "
    "CRLF/LF). Python ile newline='' oku, tek yeri degistir (s.count(eski)==1), ayni bicimde yaz; "
    "`git diff --stat` yalniz gercek degisikligi gostermeli.",
    "Yazma alani DISINDA bir dosya gerekiyorsa yazmadan once lidere `soru_sor` ile sor; lider "
    "danisma cevabinda `ALAN_EKLE: yol` yazar, ofis kilidi olcer ve alani genisletir.",
]


def bitti_tanimi() -> list:
    """Gelistirme takiminin bitti tanimi (calisan ofisin defter yolu icinde)."""
    defter = str(Path(kaynak()) / "veri" / "ofis.sqlite3").replace("\\", "/")
    return BITTI_TANIMI + [m.format(defter=defter) for m in BITTI_TANIMI_EK]


def takimi_hazirla(db, proje_id: str, kanat_id: str) -> None:
    """Gelistirme takimi kuruldu: bitti tanimi kite yazilir. Kit bossa ya da
    hala ESKI varsayilansa (patron degistirmediyse) yenisi yazilir; patronun
    elle yazdigina dokunulmaz."""
    from . import kit
    mevcut = kit.oku(db, kanat_id).get("bitti_tanimi") or []
    if not mevcut or list(mevcut) == list(BITTI_TANIMI):
        kit.yaz(db, proje_id, kanat_id, bitti_tanimi=bitti_tanimi())


# -- sinama -------------------------------------------------------------------

def arac_ortami() -> dict:
    """Calisan ofisin evindeki ikili araclar (ffmpeg, RIFE): kopya onlari
    CALISTIRIR, kopyalamaz/baglamaz. 09.10 F1 canli (#6): kopyanin evi bos,
    `duman_kurgu` "ffmpeg ajan PATH'inde" sinamasindan kaldi; kurulum karti
    yine acilmadi. Yalniz var olan yol verilir."""
    araclar = Path(kaynak()) / "ev" / "araclar"
    adaylar = {"OFIS_FFMPEG_KLASORU": araclar / "ffmpeg" / "bin",
               "OFIS_RIFE": araclar / "rife" / "rife-ncnn-vulkan.exe"}
    return {k: str(v) for k, v in adaylar.items() if v.exists()}


def _temiz_ortam() -> dict:
    """OFIS_* degiskenleri SILINIR: panelin gercek evi/defteri/kabini sinamaya
    sizmasin (`_temizlik` bos olani kendisi kurar)."""
    return {k: v for k, v in os.environ.items() if not k.upper().startswith("OFIS_")}


def sinama_kos(kok, *, dosyalar=None, sinir: float = DOSYA_SINIRI_SN) -> dict:
    """Kopyada sinama takimini kosar. Doner: dosya/gecti/kaldi/kotu."""
    kok = Path(kok)
    liste = sorted((kok / "testler").glob("duman_*.py")) if dosyalar is None else \
        [kok / "testler" / d for d in dosyalar]
    sonuc = {"dosya": 0, "gecti": 0, "kaldi": 0, "kotu": [], "sure_sn": 0.0}
    bas = time.time()
    ortam = dict(_temiz_ortam(), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                 **arac_ortami())
    for f in liste:
        sonuc["dosya"] += 1
        try:
            p = subprocess.run([sys.executable, str(f)], cwd=str(kok), capture_output=True,
                               timeout=sinir, env=ortam, creationflags=PENCERE_YOK)
            cikti, kod = p.stdout.decode("utf-8", "replace"), p.returncode
        except subprocess.TimeoutExpired:
            cikti, kod = "", "zaman_asimi"
        g, k = cikti.count("[gecti]"), cikti.count("[KALDI]")
        sonuc["gecti"] += g
        sonuc["kaldi"] += k
        if kod != 0 or k:
            ilk = [s.strip() for s in cikti.splitlines() if "[KALDI]" in s][:3]
            sonuc["kotu"].append({"dosya": f.name, "kod": kod, "kaldi": ilk})
    sonuc["sure_sn"] = round(time.time() - bas, 1)
    sonuc["tamam"] = not sonuc["kotu"] and sonuc["dosya"] > 0
    return sonuc


# -- teslim -------------------------------------------------------------------

def _kayit_anahtari(no) -> str:
    return f"gelistirme_teslim:{no}"


def teslim_durumu(db, pid: str, no) -> dict:
    try:
        return json.loads(db.ayar_oku(pid, _kayit_anahtari(no), "") or "{}")
    except ValueError:
        return {}


def _yaz(db, pid, no, d: dict) -> None:
    db.ayar_yaz(pid, _kayit_anahtari(no), json.dumps(d, ensure_ascii=False))


#: Depoya girmeyen ama sinamanin ve ajanin istedigi paketler (npm kilidiyle).
NPM_PROJELERI = ("medya/remotion",)


def bagimliliklari_kur(kok) -> list:
    """Kopyada EKSIK npm paketlerini kilit dosyasindan kurar (`npm ci`).

    09.10 F1 canli: `node_modules` depoya girmez; kopyada Remotion yoktu ve tam
    sinama `duman_kurgu`dan kaldi -- hicbir gelistirme kurulamazdi. Calisan
    ofisin paketlerine BAGLANTI (junction) verilmez: kendi koduna yazma kapisi
    yolu metin olarak olcer, baglantinin arkasini gormez; ajan kopyadan calisan
    ofisin paketlerine yazabilirdi. Olculdu: npm onbellekten 257 paket 10 sn.
    Doner: kurulan projeler (hata SOYLENIR, sinamayi durdurmaz)."""
    kurulan = []
    for alt in NPM_PROJELERI:
        yer = Path(kok) / alt
        if not (yer / "package-lock.json").is_file() or (yer / "node_modules").is_dir():
            continue
        p = subprocess.run(["npm", "ci", "--prefer-offline", "--no-audit", "--no-fund"],
                           cwd=str(yer), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=900, shell=(os.name == "nt"),
                           stdin=subprocess.DEVNULL, creationflags=PENCERE_YOK)
        if p.returncode != 0:
            raise GelistirmeHatasi(f"{alt}: npm ci basarisiz: " + ((p.stderr or "") + (p.stdout or ""))[-300:])
        kurulan.append(alt)
    return kurulan


def satir_sonlarini_geri_koy(eski: bytes, yeni: bytes) -> bytes:
    """`yeni`nin satir sonlarini `eski`deki gibi yapar; ICERIGE dokunmaz.
    Degisen/eklenen satir, komsu eski satirin satir sonunu alir."""
    import difflib

    def ayir(veri):
        parca = veri.split(b"\n")
        govde, son = [], []
        for i, s in enumerate(parca):
            if i == len(parca) - 1:
                govde.append(s)
                son.append(b"")
            elif s.endswith(b"\r"):
                govde.append(s[:-1])
                son.append(b"\r\n")
            else:
                govde.append(s)
                son.append(b"\n")
        return govde, son

    e_govde, e_son = ayir(eski)
    y_govde, _ = ayir(yeni)
    hedef = [b"\n"] * len(y_govde)
    for etiket, a1, a2, b1, b2 in difflib.SequenceMatcher(None, e_govde, y_govde,
                                                          autojunk=False).get_opcodes():
        for j in range(b1, b2):
            if etiket == "equal":
                hedef[j] = e_son[a1 + (j - b1)]
            else:
                hedef[j] = e_son[min(max(a1 - 1, 0), len(e_son) - 1)] or b"\n"
    hedef[-1] = b""
    return b"".join(g + s for g, s in zip(y_govde, hedef))


def satir_sonu_onar(kok, no: int) -> list:
    """Isin kayitlari bir dosyanin SATIR SONLARINI toptan degistirdiyse geri
    koyar ve `#no` kaydi olarak yazar. Doner: onarilan dosyalar.

    09.10 F1 canli (#6): ajan `sed -i` ile `web/panel.js`'i degistirdi; asil
    degisiklik 7 satirdi, fark 14.793 satir oldu (karisik CRLF/LF dosya tumden
    CRLF'e dondu). Boyle bir kayit kurulumda cakisir ve okunamaz; ajan onu yine
    `sed` ile "duzeltmeye" calisti. Olcu: satir sonu yok sayilinca fark
    kuculuyorsa (yari bile degil) bozulma satir sonundadir."""
    dal = _git(kok, "rev-parse", "--abbrev-ref", "origin/HEAD").stdout.decode().strip() or "origin/main"

    def sayi(*ek):
        r = _git(kok, "diff", "--numstat", *ek, f"{dal}..HEAD")
        out = {}
        for satir in r.stdout.decode("utf-8", "replace").splitlines():
            parca = satir.split("\t")
            if len(parca) == 3 and parca[0].isdigit() and parca[1].isdigit():
                out[parca[2]] = int(parca[0]) + int(parca[1])
        return out

    ham, cr_haric = sayi(), sayi("--ignore-cr-at-eol")
    onarilan = []
    for yol, n in ham.items():
        if n < 40 or n <= 2 * cr_haric.get(yol, 0) + 20:
            continue
        eski = _git(kok, "show", f"{dal}:{yol}")
        if eski.returncode != 0:
            continue
        p = Path(kok) / yol
        try:
            p.write_bytes(satir_sonlarini_geri_koy(eski.stdout, p.read_bytes()))
        except OSError:
            continue
        onarilan.append(yol)
    if onarilan:
        _git(kok, "add", "--", *onarilan)
        _git(kok, *_kimlik(), "commit", "-q", "-m",
             f"#{no} satir sonlari kayitli haline geri kondu (ofis): " + ", ".join(onarilan))
    return onarilan


def is_basinda(db, pid: str, kok, gorev: dict) -> None:
    """Gelistirme isi BASLARKEN kopya son koda esitlenir (kararlasmis kayitlar
    duser). 10.10 F1 canli (#9): kopya yalniz is BITINCE esitleniyordu; ajan
    eski kodun ustunde calisti, son koda giren degisiklikle cakisti. Kopyada
    kaydedilmemis is (baska bir is suruyor) varsa dokunulmaz -- SOYLENIR."""
    try:
        if not kok or not kopya_mi(kok):
            return
        e = esitle(kok, cikar=kararli_isler(db, pid))
    except Exception as exc:                     # noqa: BLE001 -- is yine baslar
        e = {"tamam": False, "sebep": str(exc)}
    if not e.get("tamam"):
        db.olay_yaz(pid, "uyari", f"#{gorev.get('no')}: is basinda kopya son koda esitlenemedi "
                    f"({str(e.get('sebep'))[:200]}); ajan kopyanin bugunku haliyle calisiyor.",
                    gorev_id=gorev.get("id"))


def _esitle_once(db, pid: str, kok, gorev: dict) -> bool:
    """Sinamadan ONCE kopya calisan ofisin son koduna esitlenir (isin kaydi
    ustune tasinir). Doner: sinama yapilabilir mi.

    09.10 F1 canli (#5): kopya takim kurulurken alinmisti; sonra calisan
    ofise giren duzeltmeler kopyada YOKTU ve tam sinama o eski hatalardan
    kaldi (D17). Sinanan sey, KURULACAK seyin aynisi olmali: kurulum zaten
    son koda cherry-pick'tir. Cakisma = kurulamaz -> sinanmaz, SOYLENIR."""
    try:
        e = esitle(kok, cikar=kararli_isler(db, pid))
    except Exception as exc:                     # noqa: BLE001
        e = {"tamam": False, "sebep": str(exc)}
    try:
        bagimliliklari_kur(kok)
    except Exception as exc:                     # noqa: BLE001 -- sinama yine kosar, sebep yazili
        db.olay_yaz(pid, "uyari", f"#{gorev['no']}: kopyaya paket kurulamadi: {exc}"[:500],
                    gorev_id=gorev.get("id"))
    if e.get("tamam"):
        return True
    sebep = str(e.get("sebep") or "")
    if sebep.startswith("rebase cakisti"):
        # Durum KAYDEDILIR (karta ve `kabuk gelistirme`ye gorunur; cakisma
        # cozulunce `gelistirme sina <no>` yeniden dener).
        _yaz(db, pid, gorev["no"], {"no": gorev["no"], "baslik": gorev.get("baslik", ""),
                                    "kok": str(kok), "durum": "cakisti", "sebep": sebep[:500]})
        db.olay_yaz(pid, "gelistirme", f"#{gorev['no']}: isin kaydi calisan ofisin son koduyla "
                    f"CAKISTI, kurulamaz; sinanmadi. {sebep[:300]}", gorev_id=gorev.get("id"))
        return False
    db.olay_yaz(pid, "uyari", f"#{gorev['no']}: kopya son koda esitlenemedi ({sebep[:200]}); "
                "sinama kopyanin bugunku haliyle kosuyor.", gorev_id=gorev.get("id"))
    return True


def kapanista(db, pid: str, kok: str, gorev: dict, *, arkada: bool = True) -> dict | None:
    """Is kapandi (`tahta.kapat`): kok gelistirme kopyasiysa teslimi baslat.
    Sinama uzun (tam takim) -> arka iplikte. Hata isi geri acmaz, SOYLENIR."""
    try:
        if not kok or not kopya_mi(kok):
            return None
        if not _esitle_once(db, pid, kok, gorev):
            return None
        _onarilan = satir_sonu_onar(kok, gorev["no"])
        if _onarilan:
            db.olay_yaz(pid, "gelistirme", f"#{gorev['no']}: satir sonlari toptan degismisti "
                        f"({', '.join(_onarilan)}); ofis kayitli haline geri koydu.",
                        gorev_id=gorev["id"])
        kayitlar = _isin_kayitlari(kok, gorev["no"])
    except Exception as exc:                     # noqa: BLE001 -- is kapandi
        db.olay_yaz(pid, "uyari", f"#{gorev.get('no')} gelistirme teslimi okunamadi: {exc}",
                    gorev_id=gorev.get("id"))
        return None
    if not kayitlar:
        db.olay_yaz(pid, "gelistirme", f"#{gorev['no']}: kopyada bu isin kaydi yok "
                    "(degisen kod yok ya da git kaydi kapali) -- kurulacak bir sey yok.",
                    gorev_id=gorev["id"])
        return None
    d = {"no": gorev["no"], "baslik": gorev.get("baslik", ""), "kok": str(kok),
         "kayitlar": kayitlar, "durum": "sinaniyor", "basladi": time.time()}
    _yaz(db, pid, gorev["no"], d)
    db.olay_yaz(pid, "gelistirme", f"#{gorev['no']}: {len(kayitlar)} kayit -- kopyada TAM "
                "sinama basladi (kurulum karti sinama gecince acilir).", gorev_id=gorev["id"])
    if arkada:
        threading.Thread(target=_sinan_ve_kartla, args=(db, pid, gorev, d), daemon=True,
                         name=f"gelistirme-{gorev['no']}").start()
        return d
    return _sinan_ve_kartla(db, pid, gorev, d)


def yeniden_sina(db, pid: str, no: int) -> dict:
    """Sinamasi KALAN teslimi yeniden sinar (sebep ortamdaydi, isteydi degil:
    09.10 #6 -- kopyada ffmpeg yoktu). Kurulmus/reddedilmis teslime dokunmaz."""
    d = teslim_durumu(db, pid, no)
    if d.get("durum") == "cakisti":
        # Cakisma cozulduyse (ya da kararlasmis kayitlar dusunce) is bastan:
        # esitle -> satir sonu -> sinama -> kart (kapanistaki yolun aynisi).
        with db.baglanti() as c:
            g = c.execute("SELECT id, no, baslik FROM gorev WHERE proje_id = ? AND no = ?",
                          (pid, no)).fetchone()
        if not g:
            raise GelistirmeHatasi(f"#{no} bulunamadi.")
        kapanista(db, pid, d.get("kok") or str(varsayilan_klasor()),
                  {"id": g[0], "no": g[1], "baslik": g[2]}, arkada=False)
        return teslim_durumu(db, pid, no)
    if d.get("durum") != "sinama_kaldi":
        raise GelistirmeHatasi(f"#{no} yeniden sinanmaz: durumu '{d.get('durum') or 'yok'}'.")
    d["durum"] = "sinaniyor"
    _yaz(db, pid, no, d)
    sonuc = yarim_sinamalari_surdur(db, pid, arkada=False)
    return teslim_durumu(db, pid, no) if no in sonuc else d


def yarim_sinamalari_surdur(db, pid: str, *, arkada: bool = True) -> list:
    """Panel ACILIRKEN: sinamasi yarim kalmis teslimleri yeniden sinar.

    09.10 F1 canli (#5): sinama panelin ICINDE (arka iplik) kosuyordu; panel
    kapaninca iplik oldu, defterde "TAM sinama basladi"dan sonra hicbir sey
    yazilmadi, kurulum karti hic gelmedi ve bunu soyleyen de olmadi. Kayit
    `sinaniyor`da kalan her teslim bastan sinanir (yarim sinama sonucu
    olcu degildir). Doner: yeniden baslatilan is numaralari."""
    with db.baglanti() as c:
        satirlar = c.execute("SELECT anahtar, deger FROM ayar WHERE proje_id = ? AND anahtar LIKE ?",
                             (pid, _kayit_anahtari("%"))).fetchall()
    baslayan = []
    for anahtar, deger in satirlar:
        try:
            d = json.loads(deger or "{}")
        except ValueError:
            continue
        if d.get("durum") != "sinaniyor":
            continue
        with db.baglanti() as c:
            g = c.execute("SELECT id, no, baslik FROM gorev WHERE proje_id = ? AND no = ?",
                          (pid, d.get("no"))).fetchone()
        if not g:
            continue
        gorev = {"id": g[0], "no": g[1], "baslik": g[2]}
        if d.get("kok") and _esitle_once(db, pid, d["kok"], gorev):
            d["kayitlar"] = _isin_kayitlari(d["kok"], gorev["no"]) or d.get("kayitlar") or []
        d["basladi"] = time.time()
        _yaz(db, pid, gorev["no"], d)
        db.olay_yaz(pid, "gelistirme", f"#{gorev['no']}: panel kapanmadan once sinama YARIM "
                    "kalmisti -- kopyada TAM sinama yeniden basladi.", gorev_id=gorev["id"])
        if arkada:
            threading.Thread(target=_sinan_ve_kartla, args=(db, pid, gorev, d), daemon=True,
                             name=f"gelistirme-{gorev['no']}").start()
        else:
            _sinan_ve_kartla(db, pid, gorev, d)
        baslayan.append(gorev["no"])
    return baslayan


def _sinan_ve_kartla(db, pid, gorev, d, *, dosyalar=None) -> dict:
    try:
        s = sinama_kos(d["kok"], dosyalar=dosyalar if dosyalar is not None else d.get("dosyalar"))
    except Exception as exc:                     # noqa: BLE001
        s = {"tamam": False, "kotu": [{"dosya": "-", "kod": str(exc)}], "dosya": 0,
             "gecti": 0, "kaldi": 0}
    d["sinama"] = s
    if not s.get("tamam"):
        d["durum"] = "sinama_kaldi"
        _yaz(db, pid, d["no"], d)
        kotu = "; ".join(f"{k['dosya']} ({k['kod']}) {' | '.join(k.get('kaldi') or [])[:200]}"
                         for k in s.get("kotu", [])[:5])
        db.olay_yaz(pid, "gelistirme", f"#{d['no']}: SINAMA GECMEDI, kurulum karti ACILMADI. "
                    f"{s.get('gecti')} gecti, {s.get('kaldi')} kaldi; {kotu}", gorev_id=gorev["id"])
        return d
    from . import Ofis
    ofis = Ofis(db, pid)
    ayrinti = (f"{ISARET}{d['no']}\n"
               f"Ofisin KENDI kodunda degisiklik (gelistirme kopyasi: {d['kok']}).\n"
               f"Sinama: {s['dosya']} dosya, {s['gecti']} gecti, 0 kaldi ({s.get('sure_sn')} sn).\n"
               "Onaylarsan kayit calisan ofise kurulur; paneli SEN yeniden baslatirsin.\n"
               f"Geri alma: python -m ofis.kabuk gelistirme geri-al {d['no']}\n\n"
               + _ozet(d["kok"], d["kayitlar"]))
    onay = ofis.postane.onay_iste("ofis", f"OFIS DEGISIKLIGINI KUR: #{d['no']} {d['baslik']}"[:200],
                                  ayrinti=ayrinti, risk="yuksek", gorev_no=d["no"])
    d["durum"], d["onay"] = "kart", onay["id"]
    _yaz(db, pid, d["no"], d)
    return d


def karar(ofis, onay: dict, onayla: bool) -> dict:
    """Kurulum karti cevaplandi (panelin onay ucu cagirir)."""
    ayr = str(onay.get("ayrinti") or "")
    if not ayr.startswith(ISARET):
        return {}
    no = int(ayr[len(ISARET):].splitlines()[0].strip())
    d = teslim_durumu(ofis.db, ofis.proje_id, no)
    if not d:
        raise GelistirmeHatasi(f"#{no} teslim kaydi yok.")
    return kur(ofis, no) if onayla else reddet(ofis, no)


def _calisan_temiz_mi(hedef) -> str:
    r = _git(hedef, "status", "--porcelain", "--untracked-files=no")
    kirli = [s for s in r.stdout.decode("utf-8", "replace").splitlines() if s.strip()]
    return "" if not kirli else ", ".join(s[3:] for s in kirli[:8])


def kur(ofis, no: int) -> dict:
    d = teslim_durumu(ofis.db, ofis.proje_id, no)
    if d.get("durum") == "kuruldu":
        return d
    hedef = kaynak()
    kirli = _calisan_temiz_mi(hedef)
    if kirli:
        raise GelistirmeHatasi(
            "Calisan ofiste KAYDEDILMEMIS degisiklik var (" + kirli + "); kurulum onu "
            "ezmesin diye DURDU. Once o degisiklik kaydedilsin, sonra karti yeniden onayla.")
    r = _git(hedef, "fetch", "-q", d["kok"], "HEAD")
    if r.returncode != 0:
        raise GelistirmeHatasi("Kopyadan alinamadi: " + _metin(r)[:300])
    once = _git(hedef, "rev-parse", "HEAD").stdout.decode().strip()
    r = _git(hedef, *_kimlik(), "cherry-pick", "-x", *[k["commit"] for k in d["kayitlar"]])
    if r.returncode != 0:
        _git(hedef, "cherry-pick", "--abort")
        raise GelistirmeHatasi("Kurulum CAKISTI (calisan kod kopyadan beri degismis); hicbir "
                               "sey degismedi. Ayrinti: " + _metin(r)[:300])
    yeni = _git(hedef, "log", "--reverse", "--format=%H", f"{once}..HEAD").stdout.decode().split()
    d.update(durum="kuruldu", kurulan=yeni, kuruldu=time.time())
    _yaz(ofis.db, ofis.proje_id, no, d)
    ofis.db.olay_yaz(ofis.proje_id, "gelistirme",
                     f"#{no} OFISE KURULDU ({len(yeni)} kayit). Paneli yeniden baslat. Geri alma: "
                     f"python -m ofis.kabuk gelistirme geri-al {no}", ajan_ad="insan")
    esitle(d["kok"])
    return d


def reddet(ofis, no: int) -> dict:
    """Patron kurmadi: kopyada o kayitlar geri alinir (kopya calisan koda doner)."""
    d = teslim_durumu(ofis.db, ofis.proje_id, no)
    if not d:
        raise GelistirmeHatasi(f"#{no} bir gelistirme teslimi degil.")
    if d.get("durum") in ("kuruldu", "reddedildi", "geri_alindi"):
        raise GelistirmeHatasi(f"#{no} zaten '{d.get('durum')}'.")
    # Sinama SURERKEN geri alinmaz: kopyanin dosyalari sinamanin altindan degisir.
    if d.get("durum") == "sinaniyor":
        raise GelistirmeHatasi(f"#{no} su an sinaniyor; sinama bitince reddedilir.")
    hl = [k["commit"] for k in reversed(d.get("kayitlar") or [])]
    if hl:
        r = _git(d["kok"], *_kimlik(), "revert", "--no-edit", *hl)
        if r.returncode != 0:
            # YALAN KAYIT YOK (09.10): eskiden geri alma dussa da "kopyada geri
            # alindi" yaziliyor ve durum 'reddedildi' oluyordu.
            _git(d["kok"], "revert", "--abort")
            raise GelistirmeHatasi(f"#{no} kopyada geri alinamadi: " + _metin(r)[:300])
    d["durum"] = "reddedildi"
    _yaz(ofis.db, ofis.proje_id, no, d)
    ofis.db.olay_yaz(ofis.proje_id, "gelistirme", f"#{no} kurulmadi (patron reddetti); kopyada "
                     "geri alindi.", ajan_ad="insan")
    return d


def geri_al(ofis, no: int) -> dict:
    """Kurulmus degisikligi calisan ofiste `git revert` ile geri alir."""
    d = teslim_durumu(ofis.db, ofis.proje_id, no)
    if d.get("durum") != "kuruldu" or not d.get("kurulan"):
        raise GelistirmeHatasi(f"#{no} kurulmus bir teslim degil.")
    hedef = kaynak()
    kirli = _calisan_temiz_mi(hedef)
    if kirli:
        raise GelistirmeHatasi("Calisan ofiste kaydedilmemis degisiklik var (" + kirli + ").")
    r = _git(hedef, *_kimlik(), "revert", "--no-edit", *reversed(d["kurulan"]))
    if r.returncode != 0:
        _git(hedef, "revert", "--abort")
        raise GelistirmeHatasi("Geri alma cakisti: " + _metin(r)[:300])
    d["durum"] = "geri_alindi"
    _yaz(ofis.db, ofis.proje_id, no, d)
    ofis.db.olay_yaz(ofis.proje_id, "gelistirme", f"#{no} GERI ALINDI. Paneli yeniden baslat.",
                     ajan_ad="insan")
    esitle(d["kok"])
    return d


# -- onizleme paneli (kopyanin KENDI paneli) ------------------------------------

def _bos_kapi(baslangic: int = 0) -> int:
    import socket
    for k in (range(baslangic, baslangic + 80) if baslangic else (0,)):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", k))
                return s.getsockname()[1]
            except OSError:
                continue
    raise GelistirmeHatasi("Bos kapi bulunamadi.")


def onizleme_proje_koku() -> Path:
    """Onizleme ofisinin proje klasoru: kopyanin `ev/`i "ofisin kendi yeri"
    sayilir (orada proje acilmaz, `yollar.ofis_icinde_mi`); gecici klasorde
    SABIT bir yer (her acilista yenisi birikmesin)."""
    import tempfile
    return Path(tempfile.gettempdir()) / "agentofis-onizleme-proje"


def onizleme_hazirla() -> dict:
    """Kopyanin panelini ACMAYA hazirlar (09.10.2026, patron: "paneli gorurler,
    tiklarlar, test ederler"). YALNIZ gelistirme kopyasinin kodu icinden:
    calisan ofiste ikinci bir panel acilmaz. Patronun paneli (8900), sinama
    paneli (8911) ve patronun kabini (9222) KULLANILMAZ: panel 8920'den bos
    kapi, kabin isletim sisteminden bos kapi; defter kopyanin evinde AYRI
    (gercek defter degil); masaustu bildirimi kapali."""
    from .yollar import OFIS_KODU
    if not kopya_mi(OFIS_KODU):
        raise GelistirmeHatasi("Onizleme yalniz GELISTIRME KOPYASININ icinden acilir "
                               "(calisan ofiste ikinci panel acilmaz).")
    ev = OFIS_KODU / "ev"
    ev.mkdir(exist_ok=True)
    os.environ["OFIS_EV"] = str(ev)
    os.environ["OFIS_KABIN_KAPI"] = str(_bos_kapi())
    for _k, _v in arac_ortami().items():          # ffmpeg/RIFE calisan ofisten
        os.environ.setdefault(_k, _v)
    kapi = _bos_kapi(8920)
    db_yolu = ev / "onizleme" / "ofis.sqlite3"
    db_yolu.parent.mkdir(parents=True, exist_ok=True)
    from . import Ofis, Veritabani
    db = Veritabani(db_yolu)
    ofis = Ofis.proje_ac(db, "Onizleme", amac="gelistirme onizlemesi",
                         basari_olcutu="degisiklik panelde calisiyor",
                         kok_klasor=str(onizleme_proje_koku()))
    from . import bildirim
    db.ayar_yaz(ofis.proje_id, bildirim.AYAR, "kapali")
    return {"kapi": kapi, "kabin": int(os.environ["OFIS_KABIN_KAPI"]), "db": str(db_yolu),
            "adres": f"http://127.0.0.1:{kapi}"}


if __name__ == "__main__":
    if sys.argv[1:2] == ["onizle"]:
        h = onizleme_hazirla()
        print(f"ONIZLEME PANELI: {h['adres']}  (kabin {h['kabin']}, defter {h['db']})", flush=True)
        from .panel import kos
        kos("127.0.0.1", h["kapi"], h["db"], "Onizleme")
    else:
        print("kullanim: python -m ofis.gelistirme onizle   (gelistirme kopyasinin icinden)")
