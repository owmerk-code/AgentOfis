# -*- coding: utf-8 -*-
"""GOOGLE FLOW KATALOGU (07.10.2026, Asama 5; patron: "Flow'u detayli olc, ileride
guncellenecegini unutma").

Flow (gomulu tarayicida, patronun hesabi) modelleri, secenekleri ve kredi
bedelleri ZAMANLA DEGISIR: yeni model gelir, fiyat degisir, secenek kalkar.
Ajanlar model secimini ezbere degil, bu OLCULMUS kataloga gore yapar.

Ne olculur (URETIM YOK -- yalniz ayar menusu tiklanip okunur):
  * kredi bakiyesi (hesap penceresi),
  * her kip (Video / Resim) x video turu (Kareler / Icerik ogeleri) x model
    icin: oranlar, cozunurlukler, sureler, adetler ve her bilesimin kredisi
    (`Uretme islemi icin N kredi kullanilir`).

KORUMA: ofis bu modulde HICBIR zaman uretim / silme / satin alma / paylasma
dugmesine basmaz (`_guvenli_mi`). 07.10 kesifte OLCULDU: Flow'da ayni adli
("Diger secenekler") iki dugme var, biri projenin SIL menusunu aciyor --
dugmeler yalniz ISIM listesiyle ve yalniz ayar penceresinin icinde tiklanir.

Kaynak SENIN EKRANIN: resmi yardim sayfasi (07.10) Veo icin 4/6/8 sn yaziyor,
patronun ekraninda Veo'da sure secenegi YOK; celiskide ekran kazanir.

Katalog `ev/flow_katalog.json`; her olcum bir oncekiyle karsilastirilir,
fark `ev/flow_katalog_gecmis.jsonl`e ve `flow_degisti` olayina yazilir.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from .yollar import OFIS_EVI

KATALOG = OFIS_EVI / "flow_katalog.json"
GECMIS = OFIS_EVI / "flow_katalog_gecmis.jsonl"
ANA = "https://flow.google.com"

#: Ajanin/ofisin ASLA tiklamayacagi dugmeler (uretim, silme, para, paylasim,
#: hesap). Olcum yalniz ayar penceresinde gezer; bu liste son kilit.
YASAK = re.compile(
    r"Oluşturmaya başla|Oluştur\b|Generate|Create\b|Sil\b|Çöp kutusu|Projeyi sil|"
    r"Satın al|Yükselt|Abonel|Ödeme|Oturum|Hesap değiştir|Paylaş|Yayınla|Gönder",
    re.IGNORECASE)
_KREDI = re.compile(r"(\d[\d.]*)\s*kredi")
_IKON = re.compile(r"^(image|videocam|crop_free|chrome_extension|crop_16_9|crop_9_16|crop_square|"
                   r"crop_portrait|crop_landscape|crop_3_4|crop_4_3|crop_\w+)\s+")


class FlowHatasi(RuntimeError):
    pass


def _guvenli_mi(ad: str) -> bool:
    return not YASAK.search(ad or "")


def _temiz(ad: str) -> str:
    ad = _IKON.sub("", (ad or "").strip())
    # Simge adi (Material ligature: `volume_up`, `videocam`...) ayni satira da
    # dusebilir; model/secenek adlari buyuk harf, rakam ya da emojiyle baslar.
    ad = re.sub(r"^(?:[a-z][a-z0-9_]*\s+)+(?=\S)", "", ad)
    ad = re.sub(r"\s+info$", "", ad).strip()
    return re.sub(r"^\W+\s*", "", ad).strip()     # model adindaki emoji (muz)


def _sayi(metin: str):
    m = _KREDI.search(metin or "")
    return int(m.group(1).replace(".", "")) if m else None


class _Menu:
    """Flow ayar penceresi uzerinde KORUMALI okuma/secim."""

    def __init__(self, sayfa) -> None:
        self.s = sayfa

    def _tikla(self, el, ad: str) -> None:
        if not _guvenli_mi(ad):
            raise FlowHatasi(f"Korumali dugmeye basilmadi: {ad!r}")
        el.click()

    def radyolar(self) -> list:
        out = []
        for r in self.s.get_by_role("radio").all():
            try:
                ham = r.get_attribute("aria-label") or r.inner_text().strip().replace("\n", " ")
                out.append({"ad": _temiz(ham), "secili": r.get_attribute("aria-checked") == "true",
                            "_el": r})
            except Exception:                       # noqa: BLE001 -- kaybolan oge
                pass
        return out

    def sec(self, ad: str) -> bool:
        for r in self.radyolar():
            if r["ad"] == ad:
                if not r["secili"]:
                    self._tikla(r["_el"], ad)
                    time.sleep(0.6)
                return True
        return False

    def grup(self, desen: str) -> list:
        return [r["ad"] for r in self.radyolar() if re.fullmatch(desen, r["ad"])]

    def kredi(self):
        for _ in range(8):
            v = _sayi(" ".join(x.inner_text() for x in self.s.locator("text=/kredi kullanılır/").all()))
            if v is not None:
                return v
            time.sleep(0.3)
        return None

    def modeller(self) -> list:
        d = self.s.get_by_role("button", name="Model ailesi seçin")
        self._tikla(d, "Model ailesi seçin")
        time.sleep(0.7)
        adlar = []
        for m in self.s.get_by_role("menuitem").all():
            try:
                adlar.append(_temiz(m.inner_text().strip().splitlines()[-1]))
            except Exception:                       # noqa: BLE001
                pass
        self.s.keyboard.press("Escape")
        time.sleep(0.4)
        return [a for a in adlar if a]

    def model_sec(self, ad: str) -> None:
        d = self.s.get_by_role("button", name="Model ailesi seçin")
        self._tikla(d, "Model ailesi seçin")
        time.sleep(0.7)
        for m in self.s.get_by_role("menuitem").all():
            if _temiz(m.inner_text().strip().splitlines()[-1]) == ad:
                self._tikla(m, ad)
                time.sleep(0.9)
                return
        self.s.keyboard.press("Escape")
        raise FlowHatasi(f"Model menude yok: {ad}")


def _kip_olc(m: _Menu, kip: str, turler: list) -> list:
    out = []
    if not m.sec(kip):
        return out
    for tur in turler or [None]:
        if tur and not m.sec(tur):
            continue
        for model in m.modeller():
            try:
                m.model_sec(model)
            except FlowHatasi as exc:
                out.append({"kip": kip, "tur": tur, "model": model, "hata": str(exc)})
                continue
            oranlar = m.grup(r"\d+:\d+")
            cozler = m.grup(r"\d+p|\dK")
            sureler = m.grup(r"\d+ sn\.?")
            adetler = m.grup(r"x\d")
            kayit = {"kip": kip, "tur": tur, "model": model, "oranlar": oranlar,
                     "cozunurlukler": cozler, "sureler": sureler, "adetler": adetler, "bedel": []}
            if adetler:
                m.sec(adetler[0])
            for coz in cozler or [None]:
                if coz:
                    m.sec(coz)
                for sure in sureler or [None]:
                    if sure:
                        m.sec(sure)
                    kayit["bedel"].append({"cozunurluk": coz, "sure": sure, "kredi": m.kredi()})
            out.append(kayit)
    return out


def _durum(m: _Menu) -> dict:
    """Olcumden ONCE patronun secili ayarlari. Olcum menuyu gezer (son kip
    Resim kalir); 07.10'da OLCULDU: Flow son ayari projede HATIRLIYOR -- bir
    sonraki acilista patron kendi ayarini degil olcumun biraktigini goruyordu."""
    secili = [r["ad"] for r in m.radyolar() if r["secili"]]
    try:
        model = " ".join(m.s.get_by_role("button", name="Model ailesi seçin").inner_text().split())
    except Exception:                               # noqa: BLE001 -- dugme yok
        model = ""
    return {"secili": secili, "model_metni": model}


def _geri_yukle(m: _Menu, durum: dict) -> bool:
    """Ayarlari olcum oncesine dondurur; dondu mu (OLCULUR, varsayilmaz)."""
    secili = durum.get("secili") or []
    once = [x for x in secili if x in ("Video", "Resim")]
    once += [x for x in secili if x in ("Kareler", "İçerik öğeleri")]
    for a in once:
        m.sec(a)
    metin = durum.get("model_metni") or ""
    if metin:
        uyan = [a for a in m.modeller() if a and a in metin]
        if uyan:
            m.model_sec(max(uyan, key=len))
    for a in secili:
        m.sec(a)
    return [r["ad"] for r in m.radyolar() if r["secili"]] == secili


def _katmani_kapat(sayfa) -> None:
    """Acik pencereyi (hesap paneli, menu) kapatir. 07.10'da OLCULDU: hesap
    paneli Escape ile KAPANMIYOR, saydam arka perdesi ayar dugmesinin onunu
    kesiyordu (30 sn bekleyip dustu). Perdeye tiklamak yalniz kapatir --
    perde bir dugme degil, altindakine tiklama gecmez."""
    sayfa.keyboard.press("Escape")
    time.sleep(0.4)
    for _ in range(3):
        perde = sayfa.locator(".cdk-overlay-backdrop-showing")
        if perde.count() == 0:
            return
        try:
            perde.last.click(force=True, timeout=2000)
        except Exception:                           # noqa: BLE001 -- kaybolan perde
            pass
        time.sleep(0.5)


def _bakiye(sayfa):
    try:
        d = sayfa.get_by_role("button", name="Hesap ayrıntıları")
        d.click()
        time.sleep(1.2)
        metin = sayfa.locator("body").inner_text()
        m = re.search(r"([\d.]+)\s*Google Flow kredisi", metin)
        return int(m.group(1).replace(".", "")) if m else None
    except Exception:                               # noqa: BLE001 -- bakiye olculemedi
        return None
    finally:
        _katmani_kapat(sayfa)


def olc(cdp: str, proje_url: str = "") -> dict:
    """Katalogu OLCER (uretim yok). `proje_url` yoksa Flow'daki ilk proje acilir;
    hic proje yoksa olcum yapilmaz (yeni proje acmak patronun Flow'unu kirletir)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(cdp)
        sayfa = b.contexts[0].new_page()
        try:
            if not proje_url:
                sayfa.goto(ANA, wait_until="domcontentloaded")
                time.sleep(5)
                link = sayfa.locator("a[href*='/project/']").first
                if link.count() == 0:
                    raise FlowHatasi("Flow'da proje yok (ya da giris yapilmamis).")
                proje_url = link.get_attribute("href")
                if proje_url.startswith("/"):
                    proje_url = ANA + proje_url
            sayfa.goto(proje_url, wait_until="domcontentloaded")
            time.sleep(6)
            if "accounts.google" in sayfa.url:
                raise FlowHatasi("Flow'a giris yapilmamis (Google giris sayfasi acildi).")
            bakiye = _bakiye(sayfa)
            ayar = sayfa.get_by_role("button", name="Ayarlar tetikleyicisi")
            ayar.click()
            time.sleep(1.2)
            m = _Menu(sayfa)
            once = _durum(m)
            try:
                video = _kip_olc(m, "Video", ["Kareler", "İçerik öğeleri"])
                resim = _kip_olc(m, "Resim", [])
            finally:
                try:
                    geri = _geri_yukle(m, once)
                except Exception:                   # noqa: BLE001 -- soylenir
                    geri = False
            sayfa.keyboard.press("Escape")
        finally:
            sayfa.close()
    return {"olculdu": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "kaynak": "Flow ekrani (patronun hesabi)", "proje_url": proje_url,
            "kredi_bakiyesi": bakiye, "video": video, "resim": resim,
            "ayarlar_geri_yuklendi": geri}


# ------------------------------------------------------------------ kayit
def oku() -> dict:
    try:
        return json.loads(KATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _anahtar(k: dict) -> str:
    return f"{k.get('kip')}|{k.get('tur') or '-'}|{k.get('model')}"


def fark(eski: dict, yeni: dict) -> list:
    """Iki olcum arasindaki DEGISIKLIKLER (insanin okuyacagi satirlar).
    Bakiye degisikligi fark sayilmaz (her uretimde degisir)."""
    if not eski:
        return []
    e = {_anahtar(k): k for k in (eski.get("video") or []) + (eski.get("resim") or [])}
    y = {_anahtar(k): k for k in (yeni.get("video") or []) + (yeni.get("resim") or [])}
    out = []
    for a in sorted(set(y) - set(e)):
        out.append(f"YENI: {a.replace('|', ' / ')}")
    for a in sorted(set(e) - set(y)):
        out.append(f"KALKTI: {a.replace('|', ' / ')}")
    for a in sorted(set(e) & set(y)):
        for alan in ("oranlar", "cozunurlukler", "sureler", "adetler"):
            if e[a].get(alan) != y[a].get(alan):
                out.append(f"DEGISTI: {a.replace('|', ' / ')} {alan}: {e[a].get(alan)} -> {y[a].get(alan)}")
        eb = {(b.get("cozunurluk"), b.get("sure")): b.get("kredi") for b in e[a].get("bedel") or []}
        yb = {(b.get("cozunurluk"), b.get("sure")): b.get("kredi") for b in y[a].get("bedel") or []}
        for k in sorted(set(eb) & set(yb), key=str):
            if eb[k] != yb[k]:
                out.append(f"FIYAT: {a.replace('|', ' / ')} {k[0] or ''} {k[1] or ''}: {eb[k]} -> {yb[k]} kredi")
    return out


def kaydet(katalog: dict, db=None, proje_id: str = "") -> list:
    """Kaydeder, oncekiyle karsilastirir; degisiklik varsa gecmise ve olaya yazar."""
    from .dosya import atomik_yaz
    eski = oku()
    d = fark(eski, katalog)
    atomik_yaz(KATALOG, json.dumps(katalog, ensure_ascii=False, indent=1))
    if d:
        try:
            onceki = GECMIS.read_text(encoding="utf-8") if GECMIS.exists() else ""
        except OSError:
            onceki = ""
        atomik_yaz(GECMIS, onceki + json.dumps({"an": katalog.get("olculdu"), "fark": d},
                                               ensure_ascii=False) + "\n")
        if db is not None and proje_id:
            db.olay_yaz(proje_id, "flow_degisti", "Flow degisti: " + " · ".join(d[:12]))
    return d


def yas_saat(katalog: dict = None):
    k = katalog if katalog is not None else oku()
    try:
        t = datetime.fromisoformat(k["olculdu"])
    except (KeyError, TypeError, ValueError):
        return None
    return (datetime.now(timezone.utc) - t).total_seconds() / 3600


#: Katalog bu kadar saatten eskiyse panel yeniden olcer (kosullar uygunsa).
TAZE_SAAT = 24
#: Basarisiz denemeden sonra en az bu kadar beklenir (Flow'u dovmesin).
DENEME_ARASI_SN = 6 * 3600
_son_deneme = {"an": 0.0}


def gerekirse_olc(db, proje_id: str, cdp: str = "", zorla: bool = False, olcer=None) -> dict:
    """Katalog BAYATSA olcer. Kosullar (hepsi): katalog TAZE_SAAT'ten eski ya
    da yok; gomulu tarayici ACIK (ofis bunun icin tarayici ACMAZ -- arka planda
    Chrome dogurmak patronun gormedigi bir is olurdu); ofis BOS (`guncelleme.
    mesgul`: ajan tarayiciyi kullanirken menu gezilmez); son basarisiz
    denemeden beri DENEME_ARASI_SN gecti. `zorla` yalniz yas/deneme sartini
    kaldirir, mesgul sarti HEP gecerli.
    Donus: {"yapildi", "sebep", "fark"}."""
    yas = yas_saat()
    if not zorla and yas is not None and yas < TAZE_SAAT:
        return {"yapildi": False, "sebep": f"taze ({yas:.1f} sa)", "fark": []}
    if not zorla and time.time() - _son_deneme["an"] < DENEME_ARASI_SN:
        return {"yapildi": False, "sebep": "son deneme yakin", "fark": []}
    from . import guncelleme
    if not cdp:
        from . import kabin, tarayici
        if not kabin.acik_mi():
            return {"yapildi": False, "sebep": "gomulu tarayici kapali", "fark": []}
        cdp = f"http://127.0.0.1:{tarayici.KABIN_KAPISI}"
    mesgul = guncelleme.mesgul(db)
    if mesgul:
        return {"yapildi": False, "sebep": f"ofis mesgul ({mesgul})", "fark": []}
    _son_deneme["an"] = time.time()
    db.olay_yaz(proje_id, "flow_olcum", "Flow katalogu olculuyor (uretim yok; ayarlar sonra geri konur)")
    try:
        katalog = (olcer or olc)(cdp)
    except Exception as exc:                        # noqa: BLE001 -- soylenir
        db.olay_yaz(proje_id, "uyari", f"Flow katalogu olculemedi: {exc}")
        return {"yapildi": False, "sebep": f"olculemedi: {exc}", "fark": []}
    d = kaydet(katalog, db, proje_id)
    if katalog.get("ayarlar_geri_yuklendi") is False:
        db.olay_yaz(proje_id, "uyari", "Flow olcumunden sonra secili ayarlar geri KONAMADI "
                                       "(model/oran/sure Flow ekraninda kontrol edilmeli)")
    return {"yapildi": True, "sebep": "olculdu", "fark": d}


#: Flow'un RESIM kipi modelleri (katalog yoksa da taninir).
RESIM_ISARETLERI = ("nano banana", "imagen", "resim")


def resim_ayari_mi(ayar_metni: str, katalog: dict = None) -> bool:
    """Flow'un su anki uretim ayari GORSEL (resim) mi. 08.10.2026 patron:
    "gorsel icin dogrudan Gemini ya da GPT; video icin Flow." Ayar okunamazsa
    False (o zaman kredi kapisi her zamanki gibi sorar)."""
    t = (ayar_metni or "").lower()
    if not t or t.startswith("video"):
        return False
    k = katalog if katalog is not None else oku()
    modeller = [str(x.get("model") or "").lower() for x in (k.get("resim") or [])]
    return any(m and m in t for m in modeller) or any(i in t for i in RESIM_ISARETLERI)


def ucretsiz_mi(ayar_metni: str, katalog: dict = None) -> bool:
    """Flow'un su anki uretim ayari (istem cubugundaki `Ayarlar tetikleyicisi`
    yazisi: "Video · 720p · 10 sn. x1" ya da "🍌 Nano Banana 2.1 · 9:16 · x1")
    KREDISIZ mi -- OLCULMUS kataloga gore. Video kipinde yazida model adi
    yok; bilinmeyen ya da katalogsuz her durum False (kapi SORAR)."""
    t = (ayar_metni or "").lower()
    if not t:
        return False
    k = katalog if katalog is not None else oku()
    uyan = [x for x in (k.get("video") or []) + (k.get("resim") or [])
            if x.get("model") and x["model"].lower() in t]
    if not uyan:
        return False
    x = max(uyan, key=lambda y: len(y["model"]))
    kr = [b.get("kredi") for b in x.get("bedel") or []]
    return bool(kr) and all(v == 0 for v in kr)


def kisa_ozet(katalog: dict = None) -> str:
    """Liderin TEK satiri: model -> kredi araligi. Lider blogu her triyajda
    kosar (~350 jeton siniri); tam katalog video ajaninin brifingindedir."""
    k = katalog if katalog is not None else oku()
    if not k:
        return "FLOW KATALOGU: henuz OLCULMEDI (`python -m ofis.kabuk flow olc`)."
    parca = {}
    for x in (k.get("video") or []) + (k.get("resim") or []):
        kr = [b.get("kredi") for b in x.get("bedel") or [] if b.get("kredi") is not None]
        p = parca.setdefault((x.get("kip"), x.get("model")), set())
        p.update(kr)

    def _aralik(s):
        if not s:
            return "?"
        return str(min(s)) if min(s) == max(s) else f"{min(s)}-{max(s)}"

    yas = yas_saat(k)
    video = " · ".join(f"{m} {_aralik(s)}" for (kip, m), s in parca.items() if kip == "Video")
    resim = " · ".join(f"{m} {_aralik(s)}" for (kip, m), s in parca.items() if kip == "Resim")
    return (f"FLOW KATALOGU (kredi; {round(yas) if yas is not None else '?'} sa once, "
            f"bakiye {k.get('kredi_bakiyesi') if k.get('kredi_bakiyesi') is not None else 'BILINMIYOR'}): "
            f"video {video or '-'} | resim {resim or '-'}.")


def ozet_metni(katalog: dict = None) -> str:
    """Ajana/lidere kisa katalog: model -> secenekler -> kredi. Olculmediyse SOYLER."""
    k = katalog if katalog is not None else oku()
    if not k:
        return "FLOW KATALOGU: henuz OLCULMEDI (`python -m ofis.kabuk flow olc`)."
    yas = yas_saat(k)
    satir = [f"FLOW KATALOGU (patronun ekranindan olculdu, {round(yas) if yas is not None else '?'} sa once; "
             f"kredi bakiyesi: {k.get('kredi_bakiyesi') if k.get('kredi_bakiyesi') is not None else 'BILINMIYOR'}; "
             f"adres {ANA} -- gomulu tarayicida, is icin yeni proje):"]
    gorulen = set()
    for x in (k.get("video") or []) + (k.get("resim") or []):
        a = (x.get("kip"), x.get("model"))
        if a in gorulen:
            continue                                   # tur farki bedeli degistirmiyorsa tek satir
        gorulen.add(a)
        bedel = x.get("bedel") or []
        if len(bedel) > 1:
            fiyat = ", ".join(f"{b['cozunurluk'] or ''} {b['sure'] or ''}={b['kredi']}".strip() for b in bedel)
        else:
            fiyat = f"{bedel[0]['kredi'] if bedel else '?'} kredi"
        sec = " ".join(filter(None, ["/".join(x.get("oranlar") or []),
                                     "/".join(x.get("cozunurlukler") or []),
                                     "/".join(x.get("sureler") or []) or ("sure secenegi yok" if x.get("kip") == "Video" else "")]))
        satir.append(f"- {x.get('kip')} · {x.get('model')}: {sec} | {fiyat}")
    return "\n".join(satir)
