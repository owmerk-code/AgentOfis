# -*- coding: utf-8 -*-
"""GERCEK BAGLAYICI ARAC ADLARI kapi testi (06.10.2026). Jeton yakmaz.

Kapi baglayici araclarina ADIYLA karar verir (okuma serbest, riskli fiil
sorulur, degistiren kayda gecer). Bugune dek bu kural uydurma adlarla
sinanmisti. `veri/baglayici_adlari.txt` patronun hesabindaki GERCEK claude.ai
baglayicilarinin (Gmail, Drive, Shopify, Meta, Canva, Atria, Docs; 271 arac)
adlaridir. OLCULDU: Gmail `get_message` "DISARIYA GONDERIM" diye
soruluyordu, `get_image_generation` "PARA" sayiliyordu, Canva duzenlemeleri
"TANINMAYAN ARAC"ti; ters yonde Meta'ya musteri listesi yuklemek
(`ads_update_custom_audience_users`) SORULMADAN geciyordu.

Sinanan: (1) okuma fiiliyle baslayan HER gercek arac serbest, (2) silme
fiilli her arac silme, (3) kritik araclarin sinifi, (4) adi masum ama
argumani tehlikeli cagri yine yakalanir.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import riskli as R  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def sinif(arac: str, girdi: dict | None = None):
    b = R.arac_degerlendir(arac, girdi or {})
    return None if b is None else b["sinif"]


ADLAR = (Path(__file__).parent / "veri" / "baglayici_adlari.txt").read_text(encoding="utf-8").split()
print(f"== gercek baglayici adlari ({len(ADLAR)} arac) ==\n")
sina("ad listesi dolu", len(ADLAR) > 200, str(len(ADLAR)))

print("1. okuma fiiliyle baslayan her arac SERBEST")
OKUMA_ONEK = ("get", "list", "search", "read", "query", "export", "download", "resolve", "find")
yanlis = []
for ad in ADLAR:
    parcalar = R._arac_parcalari(ad)
    ilk = next((p for p in parcalar if p not in ("ads", "catalog", "experiment", "abtest", "lift")), "")
    if ilk in OKUMA_ONEK and sinif(ad) not in (None, "kayit"):
        yanlis.append((ad, sinif(ad)))
sina("okuma araclarinin hicbiri sorulmuyor", not yanlis, str(yanlis[:5]))

print("\n2. silme fiilli her arac SILME")
yanlis = [ad for ad in ADLAR
          if set(R._arac_parcalari(ad)) & {"delete", "trash"} and sinif(ad) != "silme"]
sina("delete/trash tasiyan her arac silme olarak soruluyor", not yanlis, str(yanlis[:5]))

print("\n3. kritik araclar")
B = "mcp__claude_ai_"
BEKLENEN = {
    B + "Gmail__get_message": None,
    B + "Gmail__search_threads": None,
    B + "Gmail__create_draft": "kayit",
    B + "Gmail__trash_thread": "silme",
    B + "Google_Drive__read_file_content": None,
    B + "Atria__get_image_generation": None,
    B + "Atria__create_image_generation": "para",
    B + "Canva__generate-image": "para",
    B + "Canva__get-generate-image-job": None,
    B + "Canva__edit-design": "kayit",
    B + "Canva__resize-design": "kayit",
    B + "Canva__remove-background": "kayit",
    B + "Canva__publish-brand-template": "yayin",
    B + "Shopify__generate-domain-names": "kayit",
    B + "Shopify__create-discount": "para",
    B + "Shopify__publish-digital-product": "yayin",
    B + "Shopify__list-customers": None,
    B + "Meta_Reklamlar__ads_boost_ig_post": "para",
    B + "Meta_Reklamlar__ads_activate_entity": "yayin",
    B + "Meta_Reklamlar__ads_update_custom_audience_users": "gonderim",
    B + "Meta_Reklamlar__ads_get_ad_accounts": None,
}
for ad, beklenen in BEKLENEN.items():
    sina(f"{ad.split('__')[-2]}.{ad.split('__')[-1]} -> {beklenen or 'SERBEST'}",
         ad in ADLAR and sinif(ad) == beklenen, f"{sinif(ad)} (listede: {ad in ADLAR})")

print("\n4. adi masum, argumani tehlikeli")
ARG = [
    (B + "Meta_Reklamlar__ads_create_campaign", {"name": "x", "status": "ACTIVE"}, "yayin"),
    (B + "Meta_Reklamlar__ads_create_campaign", {"name": "x", "status": "PAUSED"}, "kayit"),
    (B + "Meta_Reklamlar__ads_update_entity", {"status": "ACTIVE"}, "yayin"),
    (B + "Shopify__update-product", {"status": "ACTIVE"}, "yayin"),
    (B + "Shopify__graphql_mutation", {"query": "mutation { productDelete(input:{id:1}){id} }"}, "silme"),
    (B + "Claude_Docs__batch", {"batch": [{"op": "delete", "id": "x"}]}, "silme"),
    ("mcp__x__send_message", {}, "gonderim"),
    ("mcp__x__get_payment_method", {}, None),
    ("mcp__x__create_payment_method", {}, "para"),
]
for ad, girdi, beklenen in ARG:
    sina(f"{ad.split('__')[-1]} {girdi} -> {beklenen or 'SERBEST'}", sinif(ad, girdi) == beklenen,
         str(sinif(ad, girdi)))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
