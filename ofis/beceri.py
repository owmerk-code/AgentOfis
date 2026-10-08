# -*- coding: utf-8 -*-
"""BECERILER (skills) -- ofisin TEK beceri deposu, iki motora birden.

Patron (02.10.2026): *"beceriler genel olsa daha iyi degil mi; her takim icin
neden ugrasiyoruz, otomatik olsun"* + *"ai ajanlari beceri yazip kaydedecek
mi?"* Karar: (1) beceriler GENEL, tek tek kapatilabilir; (2) ajan beceri
TASLAGI yazar, kanitla gelir, patron onaylarsa yayina girer.

Neden genel olmasi ucuz: beceri bastan yuklenmez. Her turda yalniz ADI ve
tek satirlik ACIKLAMASI modele gider; ajan ise yarayacagini gorurse tamamini
o an acar (olculdu: 22 yerlesik beceri + Task/Skill araclari tur basina
~5.400 jeton).

## Depo (ofisin evinde, `beceriler/`)

    .claude-plugin/plugin.json   depo AYNI ZAMANDA bir Claude eklentisi
    skills/<ad>/SKILL.md         YAYINDA ve ACIK (iki motor bunu kullanir)
    kapali/<ad>/                 yayinda ama patron kapatti
    taslak/<ad>/SKILL.md         ajanin onerisi; patron onaylayana kadar
    kayit.json                   kaynak, oneren, kanit isleri, tarihler

## Motora verilis (OLCULDU, 02.10.2026)

* **Claude:** `--plugin-dir <depo>`. `--restricted` kisisel ayarlari yok
  sayar ama acikca verilen eklenti klasoru YUKLENIR; haiku ajan depodaki
  beceriyi gordu ve kullandi.
* **Codex:** `$CODEX_HOME/skills/<ad>/SKILL.md` okunur (Codex belgesi:
  kullanici katmani beceri koku). Ofisin Codex evi ofisindir; acik
  beceriler oraya ESITLENIR (isaretli kopya), kapali/silinen kaldirilir.
  Ofisin isaretlemedigi klasore DOKUNULMAZ. Patronun `~/.codex`'i salt okunur.
* **Gemini (Antigravity, 07.10.2026):** `~/.gemini/config/skills/<ad>/` --
  ajan basina evde (`gemini_ev/<ajan>`), Codex'le ayni isaretli kopya.
  OLCULDU (gercek agy, flash-low): beceriyi `view_file` ile acip kullandi.
  Bu tarihe kadar Gemini ajanlarina HICBIR beceri ulasmiyordu -- video
  rolunun varsayilan motoru Gemini oldugu halde `flow-video` dahil.

## Ofisin kendi becerileri (`ofis/hazir_beceriler/`, 07.10.2026)

Kodla birlikte gelir (git'te izlenir, ev kaybolsa da kaybolmaz), depoya
kopyalanir ve kod guncellenince depodaki kopya da guncellenir. Patron
kapatirsa kapali kalir; silerse bir daha gelmez.

Beceri yalniz TALIMATTIR: icindeki her arac cagrisi onay kapisindan gecer.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path

from .yollar import OFIS_EVI

#: `OFIS_BECERI_KOK` (OFIS_GOLGE_KOK gibi): olcum betigi depoyu gecici klasore
#: cevirir; MCP sunucusu AYRI surec oldugu icin modul degiskeni degil ORTAM
#: tasir (olculdu 02.10: taslak gercek depoya yazilmisti).
KOK = Path(os.environ.get("OFIS_BECERI_KOK") or (OFIS_EVI / "beceriler"))
EKLENTI_ADI = "agentofis-beceriler"
ISARET = ".agentofis"            # Codex evine ofisin koydugu kopyanin isareti
AD_DESENI = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
AZAMI_TASLAK_HARF = 12000
AZAMI_KLASOR_BAYT = 60 * 1024 * 1024


class BeceriHatasi(ValueError):
    pass


# -- depo ------------------------------------------------------------------

def _kok() -> Path:
    for alt in ("skills", "kapali", "taslak", ".claude-plugin"):
        (KOK / alt).mkdir(parents=True, exist_ok=True)
    pj = KOK / ".claude-plugin" / "plugin.json"
    if not pj.exists():
        pj.write_text(json.dumps({"name": EKLENTI_ADI, "version": "1.0.0",
                                  "description": "AgentOfis ortak becerileri"}),
                      encoding="utf-8")
    return KOK


def _kayit_oku() -> dict:
    y = _kok() / "kayit.json"
    try:
        v = json.loads(y.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def _kayit_yaz(v: dict) -> None:
    from .dosya import atomik_yaz
    atomik_yaz(_kok() / "kayit.json", json.dumps(v, ensure_ascii=False, indent=1))


def _an() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def on_bilgi(skill_md: Path) -> dict:
    """SKILL.md'nin basligi (name, description). Okunamazsa bos."""
    try:
        metin = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    m = re.match(r"^---\s*\n(.*?)\n---", metin, re.S)
    if not m:
        return {}
    out = {}
    for satir in m.group(1).splitlines():
        if ":" in satir and not satir.startswith((" ", "\t")):
            k, _, v = satir.partition(":")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _ad_dogrula(ad: str) -> str:
    ad = (ad or "").strip().lower()
    if not AD_DESENI.match(ad):
        raise BeceriHatasi("Beceri adi kucuk harf, rakam ve tire olmali (2-63 harf), "
                           f"orn. 'urun-aciklamasi-yaz'. Verilen: {ad!r}")
    return ad


def _yer(ad: str):
    for durum, alt in (("acik", "skills"), ("kapali", "kapali"), ("taslak", "taslak")):
        p = _kok() / alt / ad
        if (p / "SKILL.md").exists():
            return durum, p
    return None, None


def liste() -> list:
    """Butun beceriler: yayinda (acik/kapali) ve taslak."""
    kayit = _kayit_oku()
    out = []
    for durum, alt in (("acik", "skills"), ("kapali", "kapali"), ("taslak", "taslak")):
        for p in sorted((_kok() / alt).iterdir()):
            md = p / "SKILL.md"
            if not md.exists():
                continue
            bilgi = on_bilgi(md)
            k = kayit.get(p.name, {})
            out.append({"ad": p.name, "durum": durum,
                        "aciklama": bilgi.get("description", "")[:400],
                        "kaynak": k.get("kaynak", ""), "oneren": k.get("oneren", ""),
                        "gorevler": k.get("gorevler", []), "gerekce": k.get("gerekce", ""),
                        "eklendi": k.get("eklendi", "")})
    return out


def _klasor_boyu(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def klasorden_ekle(kaynak: str, *, kaynak_adi: str = "klasor") -> dict:
    """Bir beceri klasorunu (icinde SKILL.md) depoya KOPYALAR, yayinda ve acik.

    Insanin eylemi: kaynak onun klasoru ya da kendi Claude becerisi.
    """
    k = Path(kaynak).expanduser().resolve()
    md = k / "SKILL.md"
    if not md.is_file():
        raise BeceriHatasi(f"Bu klasorde SKILL.md yok: {k}")
    bilgi = on_bilgi(md)
    if not bilgi.get("name") or not bilgi.get("description"):
        raise BeceriHatasi("SKILL.md basliginda 'name' ve 'description' olmali.")
    ad = _ad_dogrula(bilgi["name"])
    if _yer(ad)[0]:
        raise BeceriHatasi(f"'{ad}' adinda bir beceri zaten var.")
    if _klasor_boyu(k) > AZAMI_KLASOR_BAYT:
        raise BeceriHatasi("Beceri klasoru cok buyuk (60 MB ustu).")
    shutil.copytree(k, _kok() / "skills" / ad,
                    ignore=shutil.ignore_patterns("__pycache__", ".git", ISARET))
    kayit = _kayit_oku()
    kayit[ad] = {"kaynak": kaynak_adi, "eklendi": _an()}
    _kayit_yaz(kayit)
    return {"ad": ad, "durum": "acik"}


def claude_becerileri() -> list:
    """Patronun claude.ai'dan esitlenmis becerileri (salt okunur kaynak).

    `~/.claude/skills/synced/<hesap>/<ad>/SKILL.md`. Ofis buradan yalniz
    KOPYALAR; patronun klasorune yazmaz.
    """
    from .kaynaklar import _claude_ev
    kok = _claude_ev() / "skills"
    out, var = [], {b["ad"] for b in liste()}
    for md in sorted(kok.glob("*/*/*/SKILL.md")) + sorted(kok.glob("*/SKILL.md")):
        bilgi = on_bilgi(md)
        ad = (bilgi.get("name") or md.parent.name).strip().lower()
        if not AD_DESENI.match(ad) or any(o["ad"] == ad for o in out):
            continue
        out.append({"ad": ad, "aciklama": bilgi.get("description", "")[:300],
                    "yol": str(md.parent), "eklenmis": ad in var})
    return out


#: Patronun claude.ai becerileri OTOMATIK gelir (02.10.2026 karari: "ne varsa
#: otomatik gelsin, gerekirse ben kapatirim"). Kaynak salt okunur; degisen
#: beceri guncellenir; patronun SILDIGI otomatik beceri bir daha eklenmez.
OTOMATIK = "claude-otomatik"
_ESITLEME = {"an": 0.0}
#: Otomatik gelirken KAPALI gelenler (02.10.2026 patron karari: tarayici tek,
#: gomulu; kisisel Chrome acilmaz; masaustu kapida sorulur). Bunlar ofiste
#: OLMAYAN araclari (Claude in Chrome, bilgisayar kullanimi) tarif eder ve
#: ajani bos ugrastirir. Ayarlar'da gorunur; patron isterse acar.
VARSAYILAN_KAPALI = {"chrome-browser": "kisisel Chrome'u surer (ofiste tarayici: gomulu)",
                     "built-in-browser": "baska bir uygulamanin tarayicisi (ofiste: gomulu)",
                     "computer-use": "masaustunu surer (ofiste masaustu isi kapida sorulur)"}
ESITLEME_ARALIGI_SN = 300


#: Kodla gelen ofis becerileri ve depodaki kaynak adlari.
HAZIR_KOK = Path(__file__).resolve().parent / "hazir_beceriler"
HAZIR = "ofis-hazir"


def _kaynak_surumu(p: Path) -> float:
    try:
        return max((f.stat().st_mtime for f in p.rglob("*") if f.is_file()), default=0.0)
    except OSError:
        return 0.0


#: EMEKLI ofis becerileri: koddan kalkti, depoda da kalmaz (yalniz ofisin
#: getirdigi kopya; patron kendi adina yazdiysa dokunulmaz). 08.10.2026:
#: `flow-gorsel` ajani gorseli Flow'da uretmeye yonlendiriyordu (patron:
#: "gorsel icin gemini ya da gpt") -> yerine `gorsel`.
EMEKLI = ("flow-gorsel",)


def hazir_esitle() -> list:
    """Ofisin KENDI becerilerini (kodla gelen) depoya getirir/gunceller.
    Doner: yeni eklenenler. 04.10'da depoya elle konan `flow-video`
    ("agent sistemi" kaynakli) bu kaynaga BENIMSENIR."""
    if not HAZIR_KOK.is_dir():
        return []
    kayit = _kayit_oku()
    silinen = set(kayit.get("_silinen") or [])
    eklenen, degisti = [], False
    for ad in EMEKLI:
        k = kayit.get(ad) or {}
        if k.get("kaynak") == HAZIR or str(k.get("kaynak") or "").startswith("agent sistemi"):
            durum, p = _yer(ad)
            try:
                if p is not None and Path(p).exists():
                    shutil.rmtree(p)
            except OSError:
                continue
            kayit.pop(ad, None)
            degisti = True
    for src in sorted(p for p in HAZIR_KOK.iterdir() if (p / "SKILL.md").exists()):
        ad = src.name
        if ad in silinen:
            continue
        surum = _kaynak_surumu(src)
        durum, p = _yer(ad)
        k = kayit.get(ad) or {}
        bizim = k.get("kaynak") == HAZIR or str(k.get("kaynak") or "").startswith("agent sistemi")
        try:
            if durum is None:
                shutil.copytree(src, _kok() / "skills" / ad,
                                ignore=shutil.ignore_patterns("__pycache__", ".git", ISARET))
                kayit[ad] = {"kaynak": HAZIR, "eklendi": _an(), "surum": surum}
                eklenen.append(ad)
                degisti = True
            elif durum != "taslak" and bizim and float(k.get("surum") or 0) < surum:
                shutil.rmtree(p)
                shutil.copytree(src, p, ignore=shutil.ignore_patterns("__pycache__", ".git", ISARET))
                kayit[ad] = {**k, "kaynak": HAZIR, "surum": surum}
                degisti = True
        except OSError:
            continue                    # bir beceri bozuksa digerleri gelir
    if degisti:
        _kayit_yaz(kayit)
    return eklenen


def claude_esitle(*, zorla: bool = False) -> list:
    """Patronun Claude becerilerini depoya getirir. Doner: yeni eklenenler."""
    hazir_esitle()
    if not zorla and time.time() - _ESITLEME["an"] < ESITLEME_ARALIGI_SN:
        return []
    _ESITLEME["an"] = time.time()
    kayit = _kayit_oku()
    silinen = set(kayit.get("_silinen") or [])
    eklenen = []
    for b in claude_becerileri():
        ad, src = b["ad"], Path(b["yol"])
        if ad in silinen:
            continue
        surum = _kaynak_surumu(src)
        durum, p = _yer(ad)
        try:
            if durum is None:
                shutil.copytree(src, _kok() / ("kapali" if ad in VARSAYILAN_KAPALI else "skills") / ad,
                                ignore=shutil.ignore_patterns("__pycache__", ".git", ISARET))
                kayit[ad] = {"kaynak": OTOMATIK, "eklendi": _an(), "surum": surum}
                eklenen.append(ad)
            elif (durum != "taslak" and (kayit.get(ad) or {}).get("kaynak") == OTOMATIK
                  and float(kayit[ad].get("surum") or 0) < surum):
                shutil.rmtree(p)
                shutil.copytree(src, p, ignore=shutil.ignore_patterns("__pycache__", ".git", ISARET))
                kayit[ad]["surum"] = surum
        except OSError:
            continue                    # bir beceri bozuksa digerleri gelir
    _kayit_yaz(kayit)
    return eklenen


def kapat(ad: str) -> None:
    durum, p = _yer(_ad_dogrula(ad))
    if durum != "acik":
        raise BeceriHatasi(f"'{ad}' acik bir beceri degil.")
    shutil.move(str(p), str(_kok() / "kapali" / p.name))


def ac(ad: str) -> None:
    durum, p = _yer(_ad_dogrula(ad))
    if durum != "kapali":
        raise BeceriHatasi(f"'{ad}' kapali bir beceri degil.")
    shutil.move(str(p), str(_kok() / "skills" / p.name))


def sil(ad: str) -> None:
    durum, p = _yer(_ad_dogrula(ad))
    if not durum:
        raise BeceriHatasi(f"'{ad}' diye bir beceri yok.")
    shutil.rmtree(p)
    kayit = _kayit_oku()
    if (kayit.pop(p.name, None) or {}).get("kaynak") in (OTOMATIK, HAZIR):
        # Patron otomatik geleni SILDI: bir daha getirilmez.
        kayit["_silinen"] = sorted(set(kayit.get("_silinen") or []) | {p.name})
    _kayit_yaz(kayit)


# -- ajanin taslagi ---------------------------------------------------------

TASLAK_KURALI = (
    "Ayni yordami birden cok iste tekrar ettiysen ve bir sonraki ajana zaman "
    "kazandiracaksa `beceri_oner` ile BECERI TASLAGI yaz: kisa ad, ne zaman "
    "kullanilacagini soyleyen tek cumle, adim adim yordam ve bu yordamin ISE "
    "YARADIGI kapanmis islerin numaralari (kanit). Patron onaylarsa butun "
    "ajanlar kullanir. Tek seferlik isi beceri yapma.")


def taslak_yaz(ofis, *, ad: str, aciklama: str, govde: str, gorevler, gerekce: str,
               oneren: str) -> dict:
    """Ajanin beceri taslagi. KANITSIZ taslak olmaz: en az bir KAPANMIS is."""
    from .riskli import koruma_asma
    ad = _ad_dogrula(ad)
    aciklama = " ".join((aciklama or "").split())
    govde = (govde or "").strip()
    if not aciklama or len(aciklama) > 400:
        raise BeceriHatasi("Aciklama tek cumle olmali (1-400 harf): ne zaman kullanilir.")
    if not govde or len(govde) > AZAMI_TASLAK_HARF:
        raise BeceriHatasi(f"Yordam bos olamaz, en fazla {AZAMI_TASLAK_HARF} harf.")
    if _yer(ad)[0]:
        raise BeceriHatasi(f"'{ad}' adinda bir beceri ya da taslak zaten var; baska ad ver.")
    nolar = []
    for n in gorevler or []:
        try:
            nolar.append(int(str(n).lstrip("#")))
        except ValueError:
            raise BeceriHatasi(f"Gorev numarasi gecersiz: {n!r}")
    kanitli = []
    for n in nolar:
        try:
            g = ofis.tahta.gorev(n)
        except Exception:
            continue
        if g["durum"] == "bitti":
            kanitli.append(n)
    if not kanitli:
        raise BeceriHatasi("KANIT gerekli: yordamin ise yaradigi en az bir KAPANMIS (bitti) "
                           "isin numarasini ver. Kanitsiz beceri onerilmez.")
    bulunan = koruma_asma(f"{aciklama}\n{govde}")
    if bulunan:
        ofis.db.olay_yaz(ofis.proje_id, "hafiza_reddi",
                         f"{oneren} beceri taslagi yazmak istedi; ofis DURDURDU (korumayi "
                         f"asmayi anlatiyor: '{bulunan}'). Ad: {ad}", ajan_ad=oneren)
        raise BeceriHatasi("HAFIZA KAPISI: bu yordam ofisin bir korumasini asmayi anlatiyor; "
                           "beceri olamaz. Gercek bir engel varsa soru_sor ile patrona sor.")
    p = _kok() / "taslak" / ad
    p.mkdir(parents=True)
    (p / "SKILL.md").write_text(f"---\nname: {ad}\ndescription: {aciklama}\n---\n\n{govde}\n",
                                encoding="utf-8")
    kayit = _kayit_oku()
    kayit[ad] = {"kaynak": "ajan", "oneren": oneren, "gorevler": kanitli,
                 "gerekce": " ".join((gerekce or "").split())[:600], "eklendi": _an()}
    _kayit_yaz(kayit)
    ofis.db.olay_yaz(ofis.proje_id, "beceri_taslagi",
                     f"{oneren} beceri onerdi: {ad} -- {aciklama} (kanit: "
                     + ", ".join(f"#{n}" for n in kanitli) + "). Ayarlar > Beceriler'den onayla.",
                     ajan_ad=oneren)
    return {"ad": ad, "durum": "taslak", "gorevler": kanitli}


def taslak_onayla(ad: str) -> None:
    durum, p = _yer(_ad_dogrula(ad))
    if durum != "taslak":
        raise BeceriHatasi(f"'{ad}' bir taslak degil.")
    shutil.move(str(p), str(_kok() / "skills" / p.name))
    kayit = _kayit_oku()
    kayit.setdefault(p.name, {})["onaylandi"] = _an()
    _kayit_yaz(kayit)


def taslak_reddet(ad: str) -> None:
    durum, p = _yer(_ad_dogrula(ad))
    if durum != "taslak":
        raise BeceriHatasi(f"'{ad}' bir taslak degil.")
    shutil.rmtree(p)
    kayit = _kayit_oku()
    kayit.pop(p.name, None)
    _kayit_yaz(kayit)


# -- motorlara verilis -----------------------------------------------------

def claude_eklentisi() -> str:
    """Claude'a `--plugin-dir` olarak verilecek klasor; acik beceri yoksa ''."""
    claude_esitle()
    try:
        if any((p / "SKILL.md").exists() for p in (_kok() / "skills").iterdir()):
            return str(KOK)
    except OSError:
        pass
    return ""


def codex_esitle(codex_evi) -> list:
    """Acik becerileri ofisin Codex evine esitler. Doner: oradaki ofis becerileri."""
    return ev_esitle(Path(codex_evi) / "skills")


def ev_esitle(hedef) -> list:
    """Acik becerileri bir motorun beceri klasorune esitler (Codex
    `$CODEX_HOME/skills`, Gemini `~/.gemini/config/skills`). Doner: oradaki
    ofis becerileri.

    Yalniz ISARETLI (ofisin koydugu) klasorler silinir/guncellenir; baska bir
    yoldan konmus beceriye dokunulmaz. Hata isi DURDURMAZ (beceri yardimcidir);
    cagiran bos listeyle devam eder.
    """
    hedef = Path(hedef)
    claude_esitle()
    try:
        acik = {p.name: p for p in (_kok() / "skills").iterdir() if (p / "SKILL.md").exists()}
        hedef.mkdir(parents=True, exist_ok=True)
        for p in hedef.iterdir():
            if (p / ISARET).exists() and p.name not in acik:
                shutil.rmtree(p, ignore_errors=True)
        for ad, kaynak in acik.items():
            h = hedef / ad
            surum = str(int((kaynak / "SKILL.md").stat().st_mtime))
            if h.exists():
                if not (h / ISARET).exists():
                    continue            # ofisin degil: dokunma
                if (h / ISARET).read_text(encoding="utf-8").strip() == surum:
                    continue
                shutil.rmtree(h, ignore_errors=True)
            shutil.copytree(kaynak, h)
            (h / ISARET).write_text(surum, encoding="utf-8")
        return sorted(p.name for p in hedef.iterdir() if (p / ISARET).exists())
    except OSError:
        return []
