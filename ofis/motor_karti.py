"""DURUST MOTOR KARTI (E60) -- "bu motor neyi yapar, neyi YAPAMAZ".

Motorlar esit degil ve bu gizlenmez: Codex tur basina tavan uygulayamaz,
arac kapatamaz, claude.ai baglayicilarini tasiyamaz. Rakip yol haritasindaki
motorlari soluk gosteriyor; bizde kart OLCUMDEN gelir:

* **Hucre tanimi TEK yerde** (`HUCRELER`): motor matrisi (`testler/matris.py`)
  olcerken, panel gosterirken ayni listeyi okur. Iki liste olsaydi biri
  yeni hucreyi bilir, oteki bilmezdi.
* **Kaynak son olcum** (`~/.agentofis/motor_matris.json`). Olcum yoksa
  kart "olculmedi" der: bayragin iddiasi ("tasir") olcum DEGILDIR -- bu
  projede `mcp_konusur = True` bir kez yalan cikti.
* **Bayrak olcumden sonra degistiyse** hucre "yeniden olculmeli" der; eski
  olcumu yeni koda mal etmek yanlis gosteren gosterge olurdu.
* **"yok" kusur degildir**, motorun durust bildirimidir; **YALAN** kusurdur.
"""

from __future__ import annotations

import json

from .motor import kayitli_motorlar, motor_ac
from .yollar import OFIS_EVI

SON_OLCUM = OFIS_EVI / "motor_matris.json"

#: (ad, bayrak, zorunlu, ne olculur). Bayrak None: her motordan beklenir.
HUCRELER = (
    ("tur", None, True, "tur kosar, biter, jeton olculur"),
    ("dosya_yazar", None, True, "istenen dosyayi istenen icerikle yazar"),
    ("komut_kosar", None, True, "kabuk komutu kosar, modelin bilemeyecegi ciktiyi getirir"),
    ("kanit", None, True, "kanit tahtaya duser (bayrak kanali secer: MCP ya da metin koprusu)"),
    ("kafa_yazamaz", None, True, "yazabilir=False iken dosya YAZILMAZ (Yasa 5)"),
    ("oturum_surer", None, True, "ayni oturum ikinci turda ilk turu hatirlar (Surdur)"),
    ("onay_kapisi", "izin_kancasi", False, "riskli komut ofise sorulur, KOSMAZ"),
    ("tur_ici_not", "tur_ici_mesaj", False, "tur surerken yazilan not ulasir"),
    ("durdurma", "tur_ici_mesaj", False, "tur surerken Durdur turu keser"),
    ("araclar_kapali", "araclar_kapatilabilir", False, "butun araclar kapatilinca hic arac cagrilmaz"),
    ("butce_tavani", "butce_destegi", False, "tur basina dolar tavani (yalniz API hesabi ve Fable kapisi icin; abonelikte limit saglayicinin yuzdesi); uygulayamayan BASLAMADAN reddeder"),
    ("tarayici", "mcp_konusur", False, "JS ile cizilen sayfayi tarayiciyla okur"),
    ("limit_penceresi", None, False, "saglayicinin 5 saat / 7 gun dolulugunu bildirir (bilgi)"),
    ("baglayici", "baglayici_tasir", False, "claude.ai baglayicilari (~225k jeton; varsayilan olculmez)"),
)
ZORUNLU = tuple(h[0] for h in HUCRELER if h[2])

#: Insanin okuyacagi kisa adlar (panel).
TURKCE = {
    "tur": "tur koşar", "dosya_yazar": "dosya yazar", "komut_kosar": "komut koşar",
    "kanit": "kanıt ekler", "kafa_yazamaz": "salt okunur kip tutar",
    "oturum_surer": "kaldığı yerden sürer", "onay_kapisi": "riskli komutu sorar",
    "tur_ici_not": "çalışırken not alır", "durdurma": "Durdur keser",
    "araclar_kapali": "araçsız koşabilir", "butce_tavani": "dolar tavanı",
    "tarayici": "tarayıcı kullanır", "limit_penceresi": "limit yüzdesini bildirir",
    "baglayici": "claude.ai bağlayıcıları",
}


def son_olcumler(yol=None) -> dict:
    try:
        return json.loads((yol or SON_OLCUM).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def kart(ad: str, olcum: dict = None, fabrika=motor_ac) -> dict:
    """Tek motorun karti. `olcum` = o motorun son matris kaydi (ya da None)."""
    try:
        m = fabrika(ad)
        kurulu = bool(m.musait_mi())
        notu = "" if kurulu else m.durum_notu()
        bayrak = {b: bool(getattr(m, b, False)) for _, b, _, _ in HUCRELER if b}
    except Exception as exc:              # noqa: BLE001 -- kart dusmesin, sebep soylensin
        kurulu, notu, bayrak = False, f"{ad} acilamadi: {exc}", {}
    olcum = olcum or {}
    eski_bayrak = olcum.get("bayraklar") or {}
    hucreler = []
    for h_ad, b, zorunlu, ne in HUCRELER:
        o = (olcum.get("hucreler") or {}).get(h_ad)
        iddia = True if b is None else bayrak.get(b, False)
        if o:
            durum, aciklama = o.get("durum", "?"), o.get("not", "")
            if b and b in eski_bayrak and eski_bayrak[b] != iddia:
                durum, aciklama = "bayat", (
                    f"olcumden sonra adaptorun iddiasi degisti ({b}: "
                    f"{eski_bayrak[b]} -> {iddia}); yeniden olculmeli")
        elif b and not iddia:
            durum, aciklama = "yok", "adaptor bu yetenegi bildirmiyor"
        else:
            durum, aciklama = "olculmedi", ("adaptor 'var' diyor ama matris bu hucreyi "
                                            "olcmedi -- iddia olcum degildir")
        hucreler.append({"ad": h_ad, "ad_tr": TURKCE.get(h_ad, h_ad), "zorunlu": zorunlu,
                         "ne": ne, "durum": durum, "not": aciklama})
    return {"motor": ad, "kurulu": kurulu, "durum_notu": notu,
            "olculdu": bool(olcum), "zaman": olcum.get("zaman"), "model": olcum.get("model"),
            "hukum": (olcum.get("hukum") or {}).get("karar") if olcum else None,
            "hucreler": hucreler}


def kartlar(fabrika=motor_ac, yol=None) -> list:
    """Kayitli her gercek motorun karti (sahte, sinama motorudur: disarida)."""
    olc = son_olcumler(yol)
    return [kart(ad, olc.get(ad), fabrika) for ad in kayitli_motorlar() if ad != "sahte"]
