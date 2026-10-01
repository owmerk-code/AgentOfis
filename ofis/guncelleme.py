"""GUNCELLEME -- yeni model ve CLI surumlerini FARK ET, insana SOR, onayla UYGULA.

Kullanici (23.09.2026): *"yeni modeller guncellemeler geldiginde agent
sistemimize bildirim gelse, ben onayladigimda gerekli CLI mi hesap mi
guncelleme neyse yapsa, yeni modelleri tanisa, ofiste onlarla da is yapsa."*

## Kaynak: saglayicinin KENDI verisi -- tahmin yok

Olculdu (23.09.2026): iki CLI de hesabin kullanabildigi modellerin
listesini sunucudan cekip diske yaziyor.

    claude : ~/.claude/cache/model-catalog/*.json
             id, ad, kisa ad, bolum (main/overflow), min_claude_code_version
    codex  : <CODEX_HOME>/models_cache.json
             slug, gorunurluk, oncelik, `upgrade` (EMEKLILIK tarihi + yerine gecen)

Yani ofis yeni modeli bir haber sitesinden ya da isim tahmininden degil,
saglayicinin hesaba acikladigi listeden ogrenir. Liste yoksa ya da
okunamazsa bu SOYLENIR ("olculemedi"); bos liste "yeni model yok" demek
degildir.

## OTOMATIK MOD (29.09.2026) -- ne kendiliginden, ne insana

Kullanici: *"ofis farkedip bana dusen her seyi kendisi yapip guncelleyebilir
mi, yeni modeli ekleyip uctan uca her sey hazir yapsa daha mi iyi olur?"*
Once her oneri onaya dusuyordu; olculdu ki kuyruktaki 4 kartin 2'si yanlis
alarmdi. Insana dusen karar yorucuysa ve yarisi yanlissa kapi ise yaramaz.

Bu projede CLI degisiklikleri ofisi uc kez SESSIZCE bozdu (`acceptEdits`,
`ENABLE_TOOL_SEARCH`, `opus` takma adinin haber vermeden Opus 5.5'e
kaymasi). Otomatik mod bu derslerin USTUNE kurulur, yerine degil:

1. **TAKMA AD SABITLENIR.** Ajanlar `sonnet` gibi takma ad tasir; hangi
   modele gittigine CLI karar verirse ofisin modeli haber vermeden kayar.
   Ofis takma adi kendi onayladigi GERCEK kimlige cevirir (`model_coz`,
   zincirin kurucusunda) -- CLI kendi yonlendirmesini degistirse bile ajan
   ofisin sectigi modelde kalir. Kayma bir ONERIDIR, olay degil.
2. **Once DENEME TURU.** Yeni model/surum kucuk bir gercek tur kosar.
   Dusmezse kalici olur; duserse ESKISINDE KALINIR ve sebep yazilir.
3. **CLI guncellemesi GERI ALINABILIR.** Guncelle -> surumu olc -> deneme.
   Duserse eski surume GERI DONULUR. Is kosarken CLI degistirilmez.
4. **OTOMATIK olanlar** (`OTOMATIK_TURLER`): ayni ailenin yeni nesli,
   takma adin yeni hedefi, CLI surumu. Deneme gecerse ofis KENDISI
   uygular ve bunu gorunur yapar (olay + panelde kart + GERI AL).
   Otomatik deneme duserse bir daha kendiliginden denenmez -- insana
   duser, sebebiyle.
5. **INSANA SORULANLAR:** yepyeni bir AILE (hangi kademeye -- bir maliyet
   karari) ve kapi modelleri (hic kademeye girmez). Otomatik mod bir
   AYARDIR (`guncelleme:otomatik`), kapatilabilir.
6. **Geri alinan bir daha kendiliginden GELMEZ** -- karar kaydi onu
   kapatir; yoksa ofis her gun ayni seyi yeniden uygulardi.

## Aile kurali -- neyi kendiliginden onerir, neyi SORAR

Ayni ailenin yeni NESLI (`gpt-5.6-sol` -> `gpt-6-sol`, `claude-opus-5` ->
`claude-opus-5-5`) o modeli kullanan kademe ve ajanlar icin tek bir
oneri olur. Adi bambaska YENI bir aile hicbir kademeye kendiliginden
yerlesmez: nereye koyacagini tahmin etmek, "olcmeden karar" olurdu --
oneri insana hangi kademeye girecegini SORAR.

Karar (onay/ret) ayara yazilir; reddedilen oneri bir daha gelmez. Ret
gerekcesiz olmaz (ofisin butun retleriyle ayni kural).
"""

from __future__ import annotations

import datetime as _dt
import glob
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from . import kullanim, roller

#: Claude'un model katalogu. Sinamada gecici bir yola cevrilir --
#: kullanicinin GERCEK katalogu bir sinamanin sonucunu degistirmemeli.
CLAUDE_KATALOG_DESENI = str(Path.home() / ".claude" / "cache"
                            / "model-catalog" / "*.json")

#: Yalnizca OKUNAN ek codex evleri. `~/.codex` masaustu uygulamasina ve
#: kullanicinin baska islerine aittir (bkz. motor/codex.py `_ev_bul`):
#: ofis oraya ASLA yazmaz; model listesini okumak zararsizdir ve ofisin
#: kendi evindeki liste bayat oldugunda yeni modeli erken gosterir.
#: Gercekten kullanilabilir olup olmadigini DENEME TURU olcer.
CODEX_EK_EVLER = [str(Path.home() / ".codex")]

#: CLI -> npm paketi. Gemini 24.09.2026'da motor defterinden cikarildi;
#: kullanilmayan bir CLI icin guncelleme onermek insanin kuyrugunu
#: bosuna doldururdu.
PAKETLER = {
    "claude": "@anthropic-ai/claude-code",
    "codex": "@openai/codex",
}

ANAHTAR_SON_KONTROL = "guncelleme:son_kontrol"
ANAHTAR_BEKLEYEN = "guncelleme:bekleyen"
KARAR_ONEKI = "guncelleme:karar:"
#: Takma adin OFISIN KULLANDIGI hedefi (sabit). Ilk olcumde katalogdan
#: yazilir; yalniz onaylanan (ya da otomatik uygulanan) oneri degistirir.
TAKMA_AD_ONEKI = "guncelleme:takma_ad:"
TAKMA_ADLAR = ("opus", "sonnet", "haiku")
ANAHTAR_OTOMATIK = "guncelleme:otomatik"
ANAHTAR_GECMIS = "guncelleme:gecmis"
#: Otomatik deneme bir kez duser; ikinci kez kendiliginden denenmez.
OTOMATIK_DENENDI_ONEKI = "guncelleme:otomatik_dustu:"
OTOMATIK_TURLER = ("cli", "takma_ad", "model")
#: Gecmis kaydinin tuttugu en fazla uygulama (panel son olanlari gosterir).
AZAMI_GECMIS = 50

#: Denetim araligi. Katalog okumak bedava; `npm view` birkac saniye surer.
#: 30.09.2026: gunde birden YARIM SAATE indi. Kullanici: *"yeni model ya da
#: guncelleme geldiginde ofis HEMEN yapsin."* Olculdu: masaustu uygulamasi
#: `gpt-6.1-sol`u getirmisti, ofis ancak ertesi gece gorecekti. Denetim
#: yalniz OLCER; deneme turu (kota) yalniz YENI bir sey varsa kosar.
KONTROL_ARALIGI_SAAT = 0.5

DENEME_ISTEMI = "Sadece OK yaz. Baska hicbir sey yazma, hicbir arac kullanma."


class GuncellemeHatasi(RuntimeError):
    """Oneri uygulanamadi -- sebebi mesajda."""


# ---------------------------------------------------------------------------
# Olcum: surumler ve kataloglar
# ---------------------------------------------------------------------------

def _komut(argv: list, zaman_asimi: float = 60) -> tuple:
    """(rc, cikti). Sinamada bu islev degistirilir -- gercek npm KOSMAZ."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=zaman_asimi,
                           shell=(os.name == "nt"))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, str(exc)


def _surum_ayikla(metin: str) -> str:
    m = re.search(r"(\d+\.\d+\.\d+)", metin or "")
    return m.group(1) if m else ""


def surum_tuple(s: str) -> tuple:
    try:
        return tuple(int(x) for x in s.split("."))
    except (ValueError, AttributeError):
        return ()


def kurulu_surum(motor: str) -> str:
    rc, cikti = _komut([motor, "--version"], 30)
    return _surum_ayikla(cikti) if rc == 0 else ""


def guncel_surum(paket: str) -> str:
    rc, cikti = _komut(["npm", "view", paket, "version"], 60)
    return _surum_ayikla(cikti) if rc == 0 else ""


def claude_katalogu() -> dict:
    """{"modeller": [...], "olculdu": bool, "not": str}. En taze dosya esas."""
    dosyalar = glob.glob(CLAUDE_KATALOG_DESENI)
    if not dosyalar:
        return {"modeller": [], "olculdu": False,
                "not": "claude model katalogu diskte yok"}
    dosyalar.sort(key=os.path.getmtime, reverse=True)
    try:
        d = json.loads(Path(dosyalar[0]).read_text(encoding="utf-8"))
        ham = d["catalog"]["config"]["models"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"modeller": [], "olculdu": False,
                "not": f"claude katalogu okunamadi: {exc}"}
    modeller = []
    for m in ham:
        if not isinstance(m, dict) or not m.get("id"):
            continue
        modeller.append({
            "id": m["id"], "ad": m.get("name") or m["id"],
            "kisa": (m.get("short_name") or "").lower(),
            "ana": m.get("section") == "main",
            "min_surum": m.get("min_claude_code_version") or "",
        })
    return {"modeller": modeller, "olculdu": True, "not": dosyalar[0]}


def codex_katalogu(evler: list) -> dict:
    """Butun evlerdeki listelerin BIRLESIMI (gorunur modeller).

    Evler hesap basina ayri liste tutar ve farkli saatte cekilmis
    olabilir (olculdu: ofis evi GPT-6 Sol'u henuz gormuyordu, masaustu
    evi goruyordu). Birlesim yeni modeli erken gosterir; gercekten
    kullanilabildigini deneme turu olcer.
    """
    modeller, kaynaklar = {}, []
    for ev in evler:
        p = Path(ev) / "models_cache.json"
        if not p.is_file():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        kaynaklar.append(str(p))
        for m in d.get("models") or []:
            if not isinstance(m, dict) or m.get("visibility") != "list":
                continue
            slug = m.get("slug") or ""
            if not slug:
                continue
            up = m.get("upgrade") or None
            modeller.setdefault(slug, {
                "id": slug, "ad": m.get("display_name") or slug,
                "oncelik": m.get("priority", 99),
                "emeklilik": ({"yerine": up.get("model") or "",
                               "tarih": up.get("retirement_at") or "",
                               "not": up.get("migration_markdown") or ""}
                              if isinstance(up, dict) else None),
            })
    return {"modeller": sorted(modeller.values(), key=lambda m: m["oncelik"]),
            "olculdu": bool(kaynaklar),
            "not": ", ".join(kaynaklar) or "codex model listesi diskte yok"}


def codex_evleri(db, proje_id: str) -> list:
    """Ofisin codex evleri (kendi + hesaplar) ve yalniz-okunan ek evler."""
    evler = []
    try:
        from .motor.codex import CodexMotoru
        evler.append(CodexMotoru._ev_bul())
    except Exception:
        pass
    try:
        from . import hesap as _hesap
        for h in _hesap.zincir_hesaplari(db, proje_id):
            if h.get("motor") == "codex":
                ev = (_hesap.ortam_coz(h) or {}).get("CODEX_HOME")
                if ev:
                    evler.append(ev)
    except Exception:
        pass
    evler.extend(CODEX_EK_EVLER)
    tekil = []
    for e in evler:
        e = str(Path(e).expanduser())
        if e not in tekil:
            tekil.append(e)
    return tekil


# ---------------------------------------------------------------------------
# Aile: hangi model hangisinin YENI NESLI
# ---------------------------------------------------------------------------

_CODEX_AILE = re.compile(r"^gpt-(\d+(?:\.\d+)*)-([a-z]+)$")
_CLAUDE_AILE = re.compile(r"^claude-([a-z]+)-(\d+(?:-\d+)?)(?:-\d{8})?$")


def aile(motor: str, model: str):
    """(aile, nesil_tuple) ya da None. Adi kalibina uymayan model ailesiz."""
    if motor == "codex":
        m = _CODEX_AILE.match(model or "")
        if m:
            return m.group(2), surum_tuple(m.group(1))
    elif motor == "claude":
        m = _CLAUDE_AILE.match(model or "")
        if m:
            return m.group(1), surum_tuple(m.group(2).replace("-", "."))
    return None


def _en_yeni_nesil(motor: str, model: str, katalog: list):
    a = aile(motor, model)
    if not a:
        return None
    en = None
    for m in katalog:
        b = aile(motor, m["id"])
        if b and b[0] == a[0] and b[1] > a[1]:
            if en is None or b[1] > aile(motor, en["id"])[1]:
                en = m
    return en


# ---------------------------------------------------------------------------
# Oneri uretimi
# ---------------------------------------------------------------------------

def _kullanim(db, proje_id: str, motor: str) -> dict:
    """model -> {"kademeler": [...], "ajanlar": [...]} (bu motor icin)."""
    k = {}
    harita = roller.kademe_haritasi(db, proje_id)
    for kademe, model in (harita.get(motor) or {}).items():
        if model:
            k.setdefault(model, {"kademeler": [], "ajanlar": []})["kademeler"].append(kademe)
    with db.baglanti() as conn:
        rows = conn.execute(
            "SELECT ad, model FROM ajan WHERE proje_id = ? AND motor = ?",
            (proje_id, motor)).fetchall()
    for r in rows:
        if r["model"]:
            k.setdefault(r["model"], {"kademeler": [], "ajanlar": []})["ajanlar"].append(r["ad"])
    return k


def _karar(db, proje_id: str, anahtar: str) -> str:
    return db.ayar_oku(proje_id, KARAR_ONEKI + anahtar, "")


def model_coz(db, proje_id: str, motor: str, model: str) -> str:
    """Takma adi ofisin SABITLEDIGI gercek kimlige cevirir.

    Olculdu (29.09.2026): claude.ai katalogu `sonnet`i Sonnet 5.5'e
    gosterirken CLI hala Sonnet 5'e gidiyordu; CLI guncellendigi an ajan
    HABER VERMEDEN kayacakti (Opus 5 -> 5.5'te oldugu gibi). Sabit yoksa
    (ilk olcum henuz yapilmadi) takma ad oldugu gibi gecer -- bilmedigimiz
    bir kimligi uydurmak, kaymadan daha kotu olurdu.
    """
    if motor != "claude" or model not in TAKMA_ADLAR:
        return model
    try:
        return db.ayar_oku(proje_id, TAKMA_AD_ONEKI + model, "") or model
    except Exception:          # noqa: BLE001 -- zincir kurulumu olmesin
        return model


def oneriler(db, proje_id: str, *, npm: bool = True) -> dict:
    """Bekleyen onerileri OLCER. Karara baglanmislar dahil edilmez.

    Donus: {"oneriler": [...], "olcum": {...}} -- olcum, neyin olculup
    neyin olculemedigini soyler (bos oneri listesi tek basina "her sey
    guncel" demek DEGILDIR).
    """
    liste = []
    olcum = {}

    # 1 -- CLI surumleri
    kat_claude = claude_katalogu()
    for motor, paket in PAKETLER.items():
        kurulu = kurulu_surum(motor)
        guncel = guncel_surum(paket) if npm else ""
        olcum[f"cli:{motor}"] = {"kurulu": kurulu or "olculemedi",
                                 "guncel": guncel or ("atlandi" if not npm else "olculemedi")}
        if kurulu and guncel and surum_tuple(guncel) > surum_tuple(kurulu):
            gereken = [m["ad"] for m in kat_claude["modeller"]
                       if motor == "claude" and m["min_surum"]
                       and surum_tuple(m["min_surum"]) > surum_tuple(kurulu)]
            liste.append({
                "tur": "cli", "motor": motor, "paket": paket,
                "eski": kurulu, "yeni": guncel,
                "anahtar": f"cli:{motor}:{guncel}",
                "ozet": f"{motor} CLI {kurulu} -> {guncel}"
                        + (f" (su modeller icin gerekli: {', '.join(gereken)})"
                           if gereken else ""),
            })

    # 2 -- codex: ayni ailenin yeni nesli + emeklilik
    kat_codex = codex_katalogu(codex_evleri(db, proje_id))
    olcum["katalog:codex"] = kat_codex["not"]
    olcum["katalog:claude"] = kat_claude["not"]
    ids_codex = {m["id"]: m for m in kat_codex["modeller"]}
    for eski, kul in _kullanim(db, proje_id, "codex").items():
        yeni_m = _en_yeni_nesil("codex", eski, kat_codex["modeller"])
        sebep = "ayni ailenin yeni nesli"
        emek = (ids_codex.get(eski) or {}).get("emeklilik")
        if not yeni_m and emek and emek.get("yerine"):
            yeni_m = ids_codex.get(emek["yerine"]) or {"id": emek["yerine"],
                                                       "ad": emek["yerine"]}
            sebep = f"EMEKLILIK: {emek.get('tarih') or 'tarih yok'}"
        if not yeni_m:
            continue
        liste.append({
            "tur": "model", "motor": "codex", "eski": eski,
            "yeni": yeni_m["id"], "kademeler": kul["kademeler"],
            "ajanlar": kul["ajanlar"], "sebep": sebep,
            "anahtar": f"model:codex:{eski}->{yeni_m['id']}",
            "ozet": f"codex {eski} -> {yeni_m['id']} ({sebep})",
        })

    # 3 -- claude: acik model adlari (claude-opus-5 gibi) ayni aile kuraliyla;
    #      TAKMA ADLAR (opus/sonnet/haiku) kendiliginden kayar -- SESSIZ
    #      kalmasin diye kaymasi bildirilir.
    for eski, kul in _kullanim(db, proje_id, "claude").items():
        if eski in ("opus", "sonnet", "haiku", "fable"):
            continue
        yeni_m = _en_yeni_nesil("claude", eski, kat_claude["modeller"])
        if not yeni_m:
            continue
        liste.append({
            "tur": "model", "motor": "claude", "eski": eski,
            "yeni": yeni_m["id"], "kademeler": kul["kademeler"],
            "ajanlar": kul["ajanlar"], "sebep": "ayni ailenin yeni nesli",
            "anahtar": f"model:claude:{eski}->{yeni_m['id']}",
            "ozet": f"claude {eski} -> {yeni_m['id']}",
        })
    for takma in ("opus", "sonnet", "haiku"):
        hedef = next((m["id"] for m in kat_claude["modeller"]
                      if m["ana"] and m["kisa"] == takma), "")
        if not hedef:
            continue
        onceki = db.ayar_oku(proje_id, TAKMA_AD_ONEKI + takma, "")
        if not onceki:
            # Ilk olcum: bugunku hedef kaydedilir, oneri URETILMEZ -- ilk
            # gorulen hali bir "degisim" diye sunmak uydurma olurdu.
            db.ayar_yaz(proje_id, TAKMA_AD_ONEKI + takma, hedef)
            continue
        if onceki != hedef:
            liste.append({
                "tur": "takma_ad", "motor": "claude", "ad": takma,
                "eski": onceki, "yeni": hedef,
                "anahtar": f"takma_ad:{takma}:{hedef}",
                "ozet": f"`{takma}` takma adi artik {hedef} (once {onceki}). "
                        "Onay: kabul et. Ret: kademeyi eskisine SABITLE.",
            })

    # 4 -- hicbir aileye oturmayan YENI model: kademeye kendiliginden girmez
    bilinen = {"codex": set(_kullanim(db, proje_id, "codex")),
               "claude": set(_kullanim(db, proje_id, "claude"))}
    # Takma ad (opus/sonnet/haiku) bir model KIMLIGI degildir; kullanimdaki
    # takma adin bugunku HEDEFI bilinen sayilir. Yoksa `opus` kullanan ofis
    # Opus 5.5'i "hic gorulmemis yeni model" sanardi (olculdu).
    for takma in ("opus", "sonnet", "haiku"):
        if takma in bilinen["claude"]:
            hedef = next((m["id"] for m in kat_claude["modeller"]
                          if m["ana"] and m["kisa"] == takma), "")
            if hedef:
                bilinen["claude"].add(hedef)

    def _eski_ya_da_ayni(motor, mid):
        a = aile(motor, mid)
        if not a:
            return False
        nesiller = []
        for b in bilinen[motor]:
            bb = aile(motor, b)
            if not bb:
                continue
            nesiller.append(bb[1])
            if bb[0] == a[0] and bb[1] >= a[1]:
                return True
        # YANLIS ALARM (29.09.2026): gercek ofis gpt-6-* kullaniyor ve
        # gpt-5.6-terra "yeni model" diye insanin kuyruguna dustu. Aile
        # bilinmese de kullanilan en yeni NESILDEN eski olan yeni degildir.
        # Yalniz codex: orada surum numarasi aileler arasi ORTAKTIR
        # (gpt-<surum>-<aile>). Claude'da yeni bir aile kendi numarasiyla
        # baslayabilir; onu "eski" saymak gercek yeniyi gizlerdi.
        return motor == "codex" and bool(nesiller) and a[1] < max(nesiller)

    for motor, kat in (("codex", kat_codex), ("claude", kat_claude)):
        for m in kat["modeller"]:
            if motor == "claude" and not m.get("ana"):
                continue
            if m.get("emeklilik"):
                continue   # emekliye ayrilan model "yeni" diye sunulmaz
            if m["id"] in bilinen[motor] or any(o.get("yeni") == m["id"] for o in liste):
                continue
            if any(k in m["id"] for k in roller.KAPI_MODELLERI):
                continue   # kapi modelleri kademeye girmez (roller.py)
            if _eski_ya_da_ayni(motor, m["id"]):
                continue   # kullanilandan ESKI ya da ayni nesil
            liste.append({
                "tur": "yeni_model", "motor": motor, "yeni": m["id"],
                "anahtar": f"yeni_model:{motor}:{m['id']}",
                "ozet": f"{motor}: yeni model {m['id']} ({m['ad']}) -- hicbir "
                        "kademede yok. Onaylarken HANGI kademeye girecegini sec.",
            })

    liste = [o for o in liste if not _karar(db, proje_id, o["anahtar"])]
    for i, o in enumerate(liste, 1):
        o["no"] = i
    return {"oneriler": liste, "olcum": olcum}


def kontrol(db, proje_id: str, *, npm: bool = True) -> dict:
    """Olcer, bekleyenleri ayara yazar, YENI olanlari olay defterine duser."""
    sonuc = oneriler(db, proje_id, npm=npm)
    eski = {o.get("anahtar") for o in bekleyenler(db, proje_id)}
    db.ayar_yaz(proje_id, ANAHTAR_BEKLEYEN,
                json.dumps(sonuc["oneriler"], ensure_ascii=False))
    db.ayar_yaz(proje_id, ANAHTAR_SON_KONTROL,
                _dt.datetime.now(_dt.timezone.utc).isoformat())
    for o in sonuc["oneriler"]:
        if o["anahtar"] not in eski:
            db.olay_yaz(proje_id, "guncelleme_var", o["ozet"])
    return sonuc


def kontrol_gerekirse(db, proje_id: str) -> None:
    """Son denetim KONTROL_ARALIGI_SAAT'ten eskiyse denetler.

    Denetim dusse bile is DURMAZ -- ama sessiz de kalmaz: uyari yazilir.
    """
    son = db.ayar_oku(proje_id, ANAHTAR_SON_KONTROL, "")
    try:
        if son:
            gecen = (_dt.datetime.now(_dt.timezone.utc)
                     - _dt.datetime.fromisoformat(son)).total_seconds() / 3600
            if gecen < KONTROL_ARALIGI_SAAT:
                return
    except ValueError:
        pass
    try:
        kontrol(db, proje_id)
    except Exception as exc:
        db.olay_yaz(proje_id, "uyari", f"Guncelleme denetimi calismadi: {exc}")


def bekleyenler(db, proje_id: str) -> list:
    try:
        liste = json.loads(db.ayar_oku(proje_id, ANAHTAR_BEKLEYEN, "[]") or "[]")
    except ValueError:
        return []
    return [o for o in liste if not _karar(db, proje_id, o.get("anahtar", ""))]


def _bul(db, proje_id: str, no: int) -> dict:
    for o in bekleyenler(db, proje_id):
        if o.get("no") == no:
            return o
    raise GuncellemeHatasi(f"#{no} numarali bekleyen oneri yok "
                           "(once `guncelle kontrol`).")


# ---------------------------------------------------------------------------
# Uygulama
# ---------------------------------------------------------------------------

def deneme_turu(motor_ad: str, model: str, *, fabrika=None, ek_ortam=None,
                gercek_terminal: bool = False) -> dict:
    """Yeni model/surum GERCEKTEN calisiyor mu -- kucuk bir tur, yazma yok.

    `gercek_terminal`: ayni istem CLI'in KENDI terminalinde de denenir.
    OLCULDU (30.09.2026): claude 2.1.285'e otomatik gecildi, arka kipteki
    deneme gecti -- ama yeni surumun guven sorusu gercek terminal kipini
    TAMAMEN dusurmustu. Ofis hangi kipte calisiyorsa deneme o kipi de
    kosmali; yoksa "deneme gecti" yanlis gosterir.
    """
    if fabrika is None:
        from .motor import motor_ac as fabrika
    try:
        motor = fabrika(motor_ad)
    except Exception as exc:
        return {"basarili": False, "sebep": f"motor acilamadi: {exc}"}
    metin, basarili, sebep, olcum = [], False, "", {}
    with tempfile.TemporaryDirectory(prefix="ofis-deneme-") as klasor:
        try:
            for olay in motor.tur_kos(DENEME_ISTEMI, klasor=klasor, model=model,
                                      efor="dusuk", yazabilir=False,
                                      zaman_asimi=240, ek_ortam=ek_ortam):
                if olay.tur == "metin":
                    metin.append(olay.govde or "")
                elif olay.tur == "hata":
                    sebep = olay.govde or sebep
                elif olay.tur == "bitti":
                    olcum = dict(olay.ek or {})
                    basarili = bool((olay.ek or {}).get("basarili"))
                    sebep = sebep or (olay.ek or {}).get("hata") or ""
        except Exception as exc:
            return {"basarili": False, "sebep": f"tur patladi: {exc}"}
    yazi = "".join(metin).strip()
    if basarili and "OK" not in yazi.upper():
        basarili, sebep = False, f"beklenen cevap gelmedi: {yazi[:120]!r}"
    if basarili and gercek_terminal and getattr(motor, "tui_destegi", False):
        t = _terminal_denemesi(motor, model, ek_ortam)
        # IKINCI DENEME (01.10.2026, kullanici: "guncelleme gelmisse otomatik
        # guncellenecek, eski surum olmayacak"). Panelde 2.1.286 bir kez
        # dustu, ayni surum ayni denemeyi elle ilk seferde gecti: tek dusus
        # anlik olabilir. Temiz klasorde bir kez daha denenir; ikisi de
        # duserse geri donulur (ajanlarin hic calisamamasi daha kotu) ve
        # ILK dususun sebebi de soylenir.
        if not t["basarili"]:
            ilk = t["sebep"]
            t = _terminal_denemesi(motor, model, ek_ortam)
            if t["basarili"]:
                sebep = "(ilk terminal denemesi dustu, ikincisi gecti: " + ilk[:300] + ")"
            else:
                t["sebep"] = (t["sebep"] + " | ilk deneme: " + ilk[:600])
        if not t["basarili"]:
            basarili, sebep = False, "GERCEK TERMINAL denemesi dustu: " + t["sebep"]
    return {"basarili": basarili, "sebep": sebep or "", "cevap": yazi[:120],
            "olcum": olcum}


def _terminal_denemesi(motor, model: str, ek_ortam=None) -> dict:
    """Ayni deneme istemi GERCEK terminalde (ConPTY). Terminal her durumda
    kapatilir; gecici klasor ondan sonra silinir."""
    from .motor import tui
    ad = "guncelleme-deneme"
    metin, basarili, sebep = [], False, ""
    with tempfile.TemporaryDirectory(prefix="ofis-deneme-tui-") as klasor:
        try:
            for olay in tui.TuiMotoru(motor, ajan_ad=ad).tur_kos(
                    DENEME_ISTEMI, klasor=klasor, model=model, efor="dusuk",
                    yazabilir=False, zaman_asimi=240, ek_ortam=ek_ortam):
                if olay.tur == "metin":
                    metin.append(olay.govde or "")
                elif olay.tur == "hata":
                    sebep = olay.govde or sebep
                elif olay.tur == "bitti":
                    basarili = bool((olay.ek or {}).get("basarili"))
        except Exception as exc:          # noqa: BLE001 -- sebep olarak doner
            sebep = f"terminal patladi: {exc}"
        finally:
            for x in tui.acik_oturumlar():
                if x.get("ajan") == ad:
                    tui.kapat(x["oturum_id"])
    yazi = "".join(metin).strip()
    if basarili and "OK" not in yazi.upper():
        basarili, sebep = False, f"beklenen cevap gelmedi: {yazi[:120]!r}"
    # Sebep KESILMEZ (01.10.2026): 300 harfte kesilen ekran, panelde dusen
    # denemenin asil sebebini gormeyi engelledi.
    return {"basarili": basarili, "sebep": (sebep or "")[:2000]}


def _denemeyi_olc(db, pid: str, motor: str, deneme: dict) -> None:
    """Deneme turu da bir motor turudur ve OLCULUR -- hic yazilmiyordu."""
    if deneme.get("olcum"):
        kullanim.tur_ozeti_yaz(db, pid, deneme["olcum"], motor=motor,
                               yol="guncelleme-deneme")


def _karar_yaz(db, proje_id: str, anahtar: str, deger: str) -> None:
    db.ayar_yaz(proje_id, KARAR_ONEKI + anahtar, deger)


def _gunluge(ofis, karar: str, gerekce: str, veren: str = "insan") -> None:
    try:
        ofis.bellek.karar_yaz(karar, gerekce, veren, tur="guncelleme")
    except Exception as exc:
        ofis.db.olay_yaz(ofis.proje_id, "uyari",
                         f"Guncelleme karari gunluge yazilamadi: {exc}")


# ---------------------------------------------------------------------------
# Gecmis -- ne uygulandi, geri nasil alinir
# ---------------------------------------------------------------------------

def gecmis(db, proje_id: str) -> list:
    """Uygulanan guncellemeler, en yenisi SONDA. Her kayit geri alinabilir."""
    try:
        v = json.loads(db.ayar_oku(proje_id, ANAHTAR_GECMIS, "[]") or "[]")
    except ValueError:
        return []
    return v if isinstance(v, list) else []


def _gecmise_yaz(db, proje_id: str, kayit: dict) -> dict:
    liste = gecmis(db, proje_id)
    kayit = dict(kayit, sira=(max([k.get("sira", 0) for k in liste] or [0]) + 1),
                 zaman=_dt.datetime.now(_dt.timezone.utc).isoformat(),
                 durum="uygulandi", goruldu=False)
    liste.append(kayit)
    db.ayar_yaz(proje_id, ANAHTAR_GECMIS,
                json.dumps(liste[-AZAMI_GECMIS:], ensure_ascii=False))
    return kayit


def _gecmisi_guncelle(db, proje_id: str, sira: int, **alan) -> dict:
    liste = gecmis(db, proje_id)
    for k in liste:
        if k.get("sira") == sira:
            k.update(alan)
            db.ayar_yaz(proje_id, ANAHTAR_GECMIS, json.dumps(liste, ensure_ascii=False))
            return k
    raise GuncellemeHatasi(f"#{sira} numarali uygulanmis guncelleme yok.")


def goruldu(db, proje_id: str, sira: int) -> dict:
    """Insan bildirimi gordu -- kart kalkar, kayit durur."""
    return _gecmisi_guncelle(db, proje_id, sira, goruldu=True)


def gorulmemisler(db, proje_id: str) -> list:
    return [k for k in gecmis(db, proje_id) if not k.get("goruldu")]


# ---------------------------------------------------------------------------
# Uygulama
# ---------------------------------------------------------------------------

def _yontem(veren: str) -> str:
    return "onayla" if veren == "insan" else "otomatik"


def uygula(ofis, no: int, *, kademe: str = "", fabrika=None,
           veren: str = "insan") -> dict:
    """Oneriyi uygular. Deneme dusmezse kalici olur, duserse eskisi kalir.

    `veren`: "insan" (onay) ya da "ofis" (otomatik mod). Karar gunlugune
    kimin karari oldugu boyle yazilir -- otomatik uygulanan bir seyi insan
    onaylamis gibi gostermek yanlis bir kayit olurdu.
    """
    db, pid = ofis.db, ofis.proje_id
    o = _bul(db, pid, no)
    tur = o["tur"]
    kim = "Insan onayladi" if veren == "insan" else "OTOMATIK (ofis)"
    karar_degeri = "onay" if veren == "insan" else "otomatik"

    if tur == "takma_ad":
        # Takma adin yeni hedefi de bir MODEL degisimidir: deneme turu
        # olmadan kabul etmek, denenmemis modeli butun `sonnet` ajanlarina
        # vermek olurdu (once boyleydi).
        deneme = deneme_turu("claude", o["yeni"], fabrika=fabrika)
        _denemeyi_olc(db, pid, "claude", deneme)
        if not deneme["basarili"]:
            db.olay_yaz(pid, "guncelleme_dustu",
                        f"`{o['ad']}` -> {o['yeni']}: deneme turu DUSTU, "
                        f"{o['eski']} kullanilmaya devam ediyor. Sebep: {deneme['sebep']}")
            return {"basarili": False,
                    "mesaj": f"Deneme turu dustu -- `{o['ad']}` {o['eski']} "
                             f"olarak kaliyor. Sebep: {deneme['sebep']}"}
        db.ayar_yaz(pid, TAKMA_AD_ONEKI + o["ad"], o["yeni"])
        _karar_yaz(db, pid, o["anahtar"], karar_degeri)
        _gunluge(ofis, o["ozet"], f"{kim}; deneme turu gecti ({deneme['cevap']!r}). "
                 f"`{o['ad']}` kullanan her ajan ve kademe artik {o['yeni']}.", veren)
        k = _gecmise_yaz(db, pid, {"tur": tur, "motor": "claude", "ad": o["ad"],
                                   "eski": o["eski"], "yeni": o["yeni"],
                                   "anahtar": o["anahtar"], "veren": veren,
                                   "deneme": deneme["cevap"]})
        db.olay_yaz(pid, "guncelleme_uygulandi",
                    f"#{k['sira']} `{o['ad']}` {o['eski']} -> {o['yeni']} "
                    f"({_yontem(veren)}; deneme gecti)")
        return {"basarili": True, "sira": k["sira"],
                "mesaj": f"`{o['ad']}` -> {o['yeni']} kullanimda (deneme gecti)."}

    if tur in ("model", "yeni_model"):
        hedef_kademeler = list(o.get("kademeler") or [])
        if tur == "yeni_model":
            if not kademe:
                raise GuncellemeHatasi(
                    "Yeni bir aile kademeye kendiliginden girmez: "
                    "`--kademe hizli|standart|guclu` ile hangisine girecegini sec.")
            hedef_kademeler = [kademe]
        deneme = deneme_turu(o["motor"], o["yeni"], fabrika=fabrika)
        _denemeyi_olc(db, pid, o["motor"], deneme)
        if not deneme["basarili"]:
            db.olay_yaz(pid, "guncelleme_dustu",
                        f"Deneme turu DUSTU, {o['yeni']} kullanilmadi: {deneme['sebep']}")
            return {"basarili": False,
                    "mesaj": f"Deneme turu dustu -- {o.get('eski') or 'mevcut'} "
                             f"kullanilmaya devam ediyor. Sebep: {deneme['sebep']}"}
        harita = roller.kademe_haritasi(db, pid).get(o["motor"]) or {}
        eski_kademe = {k: harita.get(k, "") for k in hedef_kademeler}
        for k in hedef_kademeler:
            roller.kademe_yaz(db, pid, o["motor"], k, o["yeni"])
        degisen = []
        for ad in o.get("ajanlar") or []:
            try:
                ofis.kadro.motor_ayarla(ad, model=o["yeni"])
                degisen.append(ad)
            except Exception as exc:
                db.olay_yaz(pid, "uyari", f"{ad} gecirilemedi: {exc}")
        _karar_yaz(db, pid, o["anahtar"], karar_degeri)
        _gunluge(ofis, o["ozet"],
                 f"{kim}; deneme turu gecti ({deneme['cevap']!r}). "
                 f"Kademeler: {', '.join(hedef_kademeler) or '-'}; "
                 f"ajanlar: {', '.join(degisen) or '-'}.", veren)
        k = _gecmise_yaz(db, pid, {"tur": tur, "motor": o["motor"],
                                   "eski": o.get("eski") or "", "yeni": o["yeni"],
                                   "eski_kademe": eski_kademe, "ajanlar": degisen,
                                   "anahtar": o["anahtar"], "veren": veren,
                                   "deneme": deneme["cevap"]})
        db.olay_yaz(pid, "guncelleme_uygulandi",
                    f"#{k['sira']} {o['motor']} {o.get('eski') or '(yeni aile)'} -> "
                    f"{o['yeni']} ({_yontem(veren)}; deneme gecti)")
        return {"basarili": True, "kademeler": hedef_kademeler, "ajanlar": degisen,
                "sira": k["sira"],
                "mesaj": f"{o['yeni']} kullanimda. Kademeler: "
                         f"{', '.join(hedef_kademeler) or '-'}; ajanlar: "
                         f"{', '.join(degisen) or '-'}."}

    if tur == "cli":
        eski, yeni, paket, motor = o["eski"], o["yeni"], o["paket"], o["motor"]
        rc, cikti = _komut(["npm", "install", "-g", f"{paket}@{yeni}"], 600)
        if rc != 0:
            db.olay_yaz(pid, "guncelleme_dustu",
                        f"{motor} CLI {yeni} kurulamadi, {eski} yerinde: {cikti[-200:]}")
            return {"basarili": False,
                    "mesaj": f"Kurulum dustu, {eski} yerinde kaldi: {cikti[-300:]}"}
        olculen = kurulu_surum(motor)
        model = roller.model_sec(motor, "hizli", roller.kademe_haritasi(db, pid))
        model = model_coz(db, pid, motor, model)
        from .motor.tui import KIP_AYARI
        gercek = db.ayar_oku(pid, KIP_AYARI, "arka") == "gercek"
        deneme = (deneme_turu(motor, model, fabrika=fabrika, gercek_terminal=gercek)
                  if olculen == yeni else
                  {"basarili": False, "sebep": f"surum olculdu: {olculen or 'yok'}"})
        _denemeyi_olc(db, pid, motor, deneme)
        if not deneme["basarili"]:
            _komut(["npm", "install", "-g", f"{paket}@{eski}"], 600)
            geri = kurulu_surum(motor)
            db.olay_yaz(pid, "guncelleme_dustu",
                        f"{motor} {yeni} deneme turunu gecemedi ({deneme['sebep']}); "
                        f"GERI ALINDI -> {geri or 'OLCULEMEDI'}")
            return {"basarili": False,
                    "mesaj": f"{yeni} denemeyi gecemedi, {eski} surumune geri "
                             f"donuldu (olculen: {geri or 'OLCULEMEDI'}). "
                             f"Sebep: {deneme['sebep']}"}
        _karar_yaz(db, pid, o["anahtar"], karar_degeri)
        _gunluge(ofis, o["ozet"], f"{kim}; surum olculdu ({olculen}) "
                                  "ve deneme turu gecti.", veren)
        k = _gecmise_yaz(db, pid, {"tur": tur, "motor": motor, "paket": paket,
                                   "eski": eski, "yeni": olculen,
                                   "anahtar": o["anahtar"], "veren": veren,
                                   "deneme": deneme.get("cevap", "")})
        db.olay_yaz(pid, "guncelleme_uygulandi",
                    f"#{k['sira']} {motor} CLI {eski} -> {olculen} "
                    f"({_yontem(veren)}; deneme gecti)")
        return {"basarili": True, "sira": k["sira"],
                "mesaj": f"{motor} CLI {olculen} kuruldu, deneme gecti."}

    raise GuncellemeHatasi(f"Bilinmeyen oneri turu: {tur}")


def reddet(ofis, no: int, sebep: str) -> dict:
    """Reddeder. Takma adda ret = ofis ESKI hedefte kalir (sabit degismez).

    Sabit (`TAKMA_AD_ONEKI`) ajanlarin gercekte kostugu kimliktir; ret onu
    degistirmez. Kademe ve takma adi acikca tasiyan ajanlar da eski kimlige
    yazilir -- sabit silinse bile ajan kaymasin (iki kat).
    """
    sebep = (sebep or "").strip()
    if not sebep:
        raise GuncellemeHatasi("Gerekcesiz ret olmaz -- `--sebep` yaz.")
    db, pid = ofis.db, ofis.proje_id
    o = _bul(db, pid, no)
    if o["tur"] == "takma_ad":
        harita = roller.kademe_haritasi(db, pid)
        for k, m in (harita.get("claude") or {}).items():
            if m == o["ad"]:
                roller.kademe_yaz(db, pid, "claude", k, o["eski"])
        with db.baglanti() as conn:
            adlar = [r["ad"] for r in conn.execute(
                "SELECT ad FROM ajan WHERE proje_id = ? AND motor = 'claude' "
                "AND model = ?", (pid, o["ad"])).fetchall()]
        for ad in adlar:
            ofis.kadro.motor_ayarla(ad, model=o["eski"])
        db.ayar_yaz(pid, TAKMA_AD_ONEKI + o["ad"], o["eski"])
    _karar_yaz(db, pid, o["anahtar"], f"ret: {sebep}")
    _gunluge(ofis, f"REDDEDILDI: {o['ozet']}", sebep)
    return {"basarili": True, "mesaj": f"#{no} reddedildi."}


def geri_al(ofis, sira: int, *, sebep: str = "", veren: str = "insan") -> dict:
    """Uygulanmis bir guncellemeyi ESKI haline dondurur.

    Deneme turu gecmis olsa da gercek iste begenilmeyebilir (kalite, kota,
    uslup). Geri alinan bir daha KENDILIGINDEN gelmez: karar kaydi
    "geri_alindi" olur -- otomatik mod onu ertesi gun yeniden uygulamasin.
    """
    db, pid = ofis.db, ofis.proje_id
    k = next((x for x in gecmis(db, pid) if x.get("sira") == sira), None)
    if k is None:
        raise GuncellemeHatasi(f"#{sira} numarali uygulanmis guncelleme yok.")
    if k.get("durum") == "geri_alindi":
        raise GuncellemeHatasi(f"#{sira} zaten geri alinmis.")
    sebep = (sebep or "").strip() or "insan geri aldi"
    tur, eski = k["tur"], k.get("eski") or ""
    if tur == "takma_ad":
        db.ayar_yaz(pid, TAKMA_AD_ONEKI + k["ad"], eski)
    elif tur in ("model", "yeni_model"):
        for kad, m in (k.get("eski_kademe") or {}).items():
            if m:
                roller.kademe_yaz(db, pid, k["motor"], kad, m)
        for ad in k.get("ajanlar") or []:
            if eski:
                try:
                    ofis.kadro.motor_ayarla(ad, model=eski)
                except Exception as exc:
                    db.olay_yaz(pid, "uyari", f"{ad} geri alinamadi: {exc}")
    elif tur == "cli":
        rc, cikti = _komut(["npm", "install", "-g", f"{k['paket']}@{eski}"], 600)
        olculen = kurulu_surum(k["motor"])
        if rc != 0 or olculen != eski:
            raise GuncellemeHatasi(
                f"{k['motor']} CLI {eski} surumune donulemedi "
                f"(olculen: {olculen or 'yok'}): {cikti[-200:]}")
    _karar_yaz(db, pid, k["anahtar"], f"geri_alindi: {sebep}")
    _gecmisi_guncelle(db, pid, sira, durum="geri_alindi", goruldu=True,
                      geri_alma_sebebi=sebep)
    _gunluge(ofis, f"GERI ALINDI: #{sira} {k.get('yeni')} -> {eski}", sebep, veren)
    db.olay_yaz(pid, "guncelleme_geri_alindi",
                f"#{sira} {k.get('ad') or k['motor']} {k.get('yeni')} -> {eski} ({sebep})")
    return {"basarili": True, "mesaj": f"#{sira} geri alindi: {eski} kullanimda."}


# ---------------------------------------------------------------------------
# Otomatik mod
# ---------------------------------------------------------------------------

def otomatik_mi(db, proje_id: str) -> bool:
    return (db.ayar_oku(proje_id, ANAHTAR_OTOMATIK, "ac") or "ac") != "kapali"


def otomatik_ayarla(db, proje_id: str, acik: bool) -> None:
    db.ayar_yaz(proje_id, ANAHTAR_OTOMATIK, "ac" if acik else "kapali")


def otomatik_uygulanir_mi(db, proje_id: str, o: dict) -> bool:
    """Bu oneri insana SORULMADAN uygulanabilir mi."""
    return (o.get("tur") in OTOMATIK_TURLER
            and not db.ayar_oku(proje_id, OTOMATIK_DENENDI_ONEKI + o.get("anahtar", ""), ""))


def insana_dusenler(db, proje_id: str) -> list:
    """Insanin karar vermesi gerekenler -- panelin kuyrugu bunu gosterir.

    Otomatik mod aciksa otomatik uygulanabilecek oneriler insana DUSMEZ
    (ofis onlari kendisi dener); yalniz yeni aileler ve otomatik denemesi
    DUSMUS olanlar duser. Kapaliysa hepsi insana duser (eski davranis).
    """
    liste = bekleyenler(db, proje_id)
    if not otomatik_mi(db, proje_id):
        return liste
    return [dict(o, otomatik_dustu=db.ayar_oku(
                proje_id, OTOMATIK_DENENDI_ONEKI + o.get("anahtar", ""), ""))
            for o in liste if not otomatik_uygulanir_mi(db, proje_id, o)]


def _kosan_is_var(db, proje_id: str) -> bool:
    with db.baglanti() as c:
        return bool(c.execute(
            "SELECT 1 FROM gorev WHERE proje_id = ? AND durum = 'calisiyor' LIMIT 1",
            (proje_id,)).fetchone())


ANAHTAR_KILIT = "guncelleme:kilit"
#: Kilit bu sureden eskiyse sahibinin oldugu varsayilir (CLI kurulumu +
#: deneme turlari olculdu: birkac dakika). Olen surec kilidi rehin tutmasin.
KILIT_BAYAT_SN = 30 * 60


def _kilit_al(db, proje_id: str, sahip: str) -> bool:
    """Surecler ARASI kilit. Ayni anda iki otomatik ilerleme olmaz.

    OLCULDU (29.09.2026, gercek test): panelin arka plan denetimi ile
    kabuktaki `guncelle otomatik simdi` AYNI ANDA calisti ve codex CLI iki
    kez kuruldu. Surec ici kilit (RLock) bunu goremez; kilit defterdedir.
    INSERT catismasi atomiktir -- ikinci surec giremez.
    """
    import sqlite3
    with db.baglanti() as c:
        r = c.execute("SELECT deger, guncellendi FROM ayar WHERE proje_id = ? "
                      "AND anahtar = ?", (proje_id, ANAHTAR_KILIT)).fetchone()
        if r is not None:
            try:
                yas = (_dt.datetime.now(_dt.timezone.utc)
                       - _dt.datetime.fromisoformat(r["guncellendi"])).total_seconds()
            except (ValueError, TypeError):
                yas = KILIT_BAYAT_SN + 1
            if yas <= KILIT_BAYAT_SN:
                return False
            c.execute("DELETE FROM ayar WHERE proje_id = ? AND anahtar = ? "
                      "AND deger = ?", (proje_id, ANAHTAR_KILIT, r["deger"]))
        try:
            c.execute("INSERT INTO ayar (proje_id, anahtar, deger, guncellendi) "
                      "VALUES (?, ?, ?, ?)",
                      (proje_id, ANAHTAR_KILIT, sahip,
                       _dt.datetime.now(_dt.timezone.utc).isoformat()))
        except sqlite3.IntegrityError:
            return False
    return True


def _kilit_birak(db, proje_id: str, sahip: str) -> None:
    with db.baglanti() as c:
        c.execute("DELETE FROM ayar WHERE proje_id = ? AND anahtar = ? AND deger = ?",
                  (proje_id, ANAHTAR_KILIT, sahip))


def otomatik_ilerle(ofis, *, fabrika=None) -> list:
    """Kilitli sarmalayici: baska bir surec ilerletiyorsa hicbir sey yapmaz."""
    db, pid = ofis.db, ofis.proje_id
    if not otomatik_mi(db, pid):
        return []
    sahip = f"{os.getpid()}:{_dt.datetime.now().timestamp()}"
    if not _kilit_al(db, pid, sahip):
        return [{"anahtar": "", "basarili": False, "ertelendi": True,
                 "ozet": "otomatik guncelleme",
                 "mesaj": "baska bir surec su an guncelliyor -- beklenmedi, atlandi"}]
    try:
        return _otomatik_ilerle(ofis, fabrika=fabrika)
    finally:
        _kilit_birak(db, pid, sahip)


#: Bir "simdi" cagrisinda en fazla kac olcum+uygulama gecisi.
AZAMI_GECIS = 3


def olc_ve_ilerle(ofis, *, fabrika=None, npm: bool = True, zorla: bool = True) -> list:
    """Olc -> otomatik uygula -> bir sey UYGULANDIYSA YENIDEN olc.

    OLCULDU (30.09.2026): masaustu uygulamasi `gpt-6.1-sol`u getirmisti.
    Ofis CLI'lari guncelledi (deneme gecti) ama yeni modeli UYGULAMADI:
    olcum CLI guncellemesinden ONCE yapilmisti ve modelin ofisin codex
    evindeki katalogda gorunmesi, yeni CLI'nin ilk turuyla oldu. Ikinci
    olcumde model onerisi cikti. Yani yeni CLI yeni model getirebilir:
    uygulanan her seyden sonra yeniden olculur (en fazla AZAMI_GECIS).
    `zorla=False` ise ilk olcum araliga uyar (panel dongusu).
    """
    tum = []
    for gecis in range(AZAMI_GECIS):
        if zorla or gecis > 0:
            kontrol(ofis.db, ofis.proje_id, npm=npm)
        else:
            kontrol_gerekirse(ofis.db, ofis.proje_id)
        sonuc = otomatik_ilerle(ofis, fabrika=fabrika)
        tum += sonuc
        if not any(r.get("basarili") for r in sonuc):
            break
    return tum


def _otomatik_ilerle(ofis, *, fabrika=None) -> list:
    """Otomatik uygulanabilecek bekleyen onerileri SIRAYLA uygular.

    Sira: once CLI (yeni model yeni CLI isteyebilir), sonra modeller. Is
    kosarken CLI DEGISTIRILMEZ -- kosan turun altindan programi cekmek
    olurdu; ertelenir ve bu SOYLENIR. Donus: her oneri icin sonuc.
    """
    db, pid = ofis.db, ofis.proje_id
    if not otomatik_mi(db, pid):
        return []
    sonuclar = []
    sira = {"cli": 0, "takma_ad": 1, "model": 2}
    adaylar = sorted((o for o in bekleyenler(db, pid)
                      if otomatik_uygulanir_mi(db, pid, o)),
                     key=lambda o: sira.get(o["tur"], 9))
    for o in adaylar:
        if o["tur"] == "cli" and _kosan_is_var(db, pid):
            sonuclar.append({"anahtar": o["anahtar"], "basarili": False,
                             "ertelendi": True, "ozet": o["ozet"],
                             "mesaj": "is kosuyor, CLI sonra guncellenecek"})
            continue
        # Numaralar her olcumde yeniden verilir: uygulamadan hemen once
        # guncel numarayi ANAHTARLA bul.
        guncel = next((x for x in bekleyenler(db, pid)
                       if x["anahtar"] == o["anahtar"]), None)
        if guncel is None:
            continue
        db.olay_yaz(pid, "guncelleme_basladi",
                    f"OTOMATIK: {o['ozet']} -- deneme turu kosuyor")
        try:
            r = uygula(ofis, guncel["no"], fabrika=fabrika, veren="ofis")
        except GuncellemeHatasi as exc:
            r = {"basarili": False, "mesaj": str(exc)}
        if not r.get("basarili"):
            # Bir kez duser: bir daha kendiliginden denenmez, insana duser.
            db.ayar_yaz(pid, OTOMATIK_DENENDI_ONEKI + o["anahtar"],
                        (r.get("mesaj") or "dustu")[:300])
        sonuclar.append(dict(r, anahtar=o["anahtar"], ozet=o["ozet"]))
    return sonuclar
