# -*- coding: utf-8 -*-
"""KESINTIDEN DEVAM -- acilista yarim kalani toparlar (01.10.2026).

Kullanici: *"elektrikler gitti"* (30.09), *"pc kapandi yarida kaldigin
yerler"* (01.10). Olculmus bosluk: panel is ortasinda kapaninca

* `calisiyor` gorunen is ASILI kalir. Yazma alani olan isin kilidi 180 sn
  sonra duser ve is SAHIBI SILINEREK sifirdan kosar (oturum bosa gider);
  yazma alani OLMAYAN is (arastirma) hic kilit almaz -- kira onu hic
  bulmaz, is sonsuza kadar "calisiyor" gorunur.
* kuyrukta `kosuyor` gorunen satir kalir; acilista hicbir sey yarim isi
  surdurmez -- insan "Surdur"e basmak zorundadir.

Kural: is, onu kosturan surecin kimligini tasir (`surec.kimlik`). Acilista
o surec OLMUSSE:

* is `kesinti` sebebiyle BIRAKILIR -- kaynak sebebi sayilir, ajan AYNI
  oturumdan surer (`Koltuk.KAYNAK_SEBEPLERI`).
* kuyruk satiri: lider plan yazarken oldu ve HIC is acilmadiysa mesaj
  BASTAN kosar (yarim "dusunuyor" balonu kapatilir); is acildiysa mesaj
  yeniden PLANLANMAZ (is kopyalanirdi) -- halka acik isleri surdurur.
* Kuyruga bagli olmayan birakilan is varsa (halka "Surdur" ile kosuyordu)
  ofis bir `devam` satiri ekler.

Yasayan ya da olculemeyen (`None`) surecin isine DOKUNULMAZ: ayni anda
kabuktan kosan bir halka olabilir.
"""

from __future__ import annotations

from . import kuyruk as _kuyruk
from . import surec as _surec
from .db import simdi

SEBEP = "kesinti (panel ya da bilgisayar is ortasinda kapandi)"
DEVAM_METNI = "Kesintide yarım kalan işleri kaldığı yerden sürdür."


def _olu(kim: str) -> bool:
    return bool(kim) and _surec.yasiyor(kim) is False


def acilista_toparla(ofis) -> dict:
    """Doner: {'birakilan': [no...], 'yeniden': n, 'devam': n}. Bir sey
    yapildiysa sohbete tek not dusulur."""
    # AYRIM (01.10.2026): kok ofisin kendi yerindeyse SESSIZ kalinmaz --
    # ajanlar ofisin kodunu/kurallarini gorur. Tasima: `kabuk tasi`.
    from .yollar import ofis_icinde_mi
    try:
        if ofis_icinde_mi(ofis.kok_klasoru()):
            ofis.db.olay_yaz(ofis.proje_id, "uyari",
                             f"Bu projenin klasoru ({ofis.kok_klasoru()}) ofisin KENDI yerinde: "
                             "ajanlar ofisin kodunu ve kurallarini gorur. Masaustune tasi: "
                             "python -m ofis.kabuk tasi")
    except Exception:                 # noqa: BLE001 -- uyari toparlamayi durdurmaz
        pass
    birakilan, yeniden, devam = [], 0, 0
    with ofis.db.baglanti() as c:
        gorevler = [dict(r) for r in c.execute(
            "SELECT no, id, sahip, kosan_surec, olusturuldu FROM gorev WHERE proje_id = ? "
            "AND durum = 'calisiyor'", (ofis.proje_id,))]
        satirlar = [dict(r) for r in c.execute(
            "SELECT * FROM kuyruk WHERE proje_id = ? AND durum = 'kosuyor'",
            (ofis.proje_id,))]
    # PATRONU BEKLEYEN is yarim degildir (01.10.2026 canli deneme): onay
    # bekleyen #42 her acilista birakildi, ayni onay YENIDEN soruldu ve sahibi
    # "bosta degil" sayildigi icin is BASKA ajana gitti (deniz -> bilge ->
    # cinar, oturum kayboldu). Cevap gelince is zaten kaldigi yerden surer.
    bekleyen = set(ofis._duraklatilmis_ajanlar())
    for g in gorevler:
        if g.get("sahip") in bekleyen:
            continue
        if _olu(g["kosan_surec"]):
            ofis.tahta.birak(g["no"], sebep=SEBEP)
            birakilan.append(g["no"])
    bagli = set()
    for k in satirlar:
        if not _olu(k["kosan_surec"]):
            continue
        bas = k.get("basladi") or k["olusturuldu"]
        with ofis.db.baglanti() as c:
            acilan = [g["no"] for g in _kuyruk.acilan_gorevler(c, ofis.proje_id, k)]
            if acilan:
                # Is acildi: mesaj yeniden planlanmaz, halka surdurur.
                c.execute("UPDATE kuyruk SET durum = 'bekliyor', devam = 1, kosan_surec = '', "
                          "not_ = ? WHERE id = ?", (SEBEP, k["id"]))
                bagli.update(acilan)
                devam += 1
            else:
                # Lider plan yazarken oldu: yarim balon kapanir, mesaj bastan.
                c.execute("UPDATE mesaj SET cevap = ?, cevaplandi = ? WHERE proje_id = ? "
                          "AND gonderen = 'insan' AND alici = ? AND olusturuldu >= ? "
                          "AND (cevap = '' OR cevap IS NULL)",
                          ("(yarıda kaldı — ofis kapanmıştı; istek baştan çalıştırılıyor)",
                           simdi(), ofis.proje_id, k["lider_ad"], bas))
                c.execute("UPDATE kuyruk SET durum = 'bekliyor', kosan_surec = '', not_ = ?, "
                          "basladi = NULL, gorev_sinir = 0 WHERE id = ?", (SEBEP, k["id"]))
                yeniden += 1
    sahipsiz = [n for n in birakilan if n not in bagli]
    if sahipsiz and not any(x.get("devam") for x in _kuyruk.bekleyenler(ofis)):
        lider = next((a["ad"] for a in ofis.kadro.liste() if a["lider_mi"]), "")
        if lider:
            k = _kuyruk.ekle(ofis, DEVAM_METNI, lider, kaynak="kesinti")
            with ofis.db.baglanti() as c:
                c.execute("UPDATE kuyruk SET devam = 1 WHERE id = ?", (k["id"],))
            devam += 1
    if birakilan or yeniden or devam:
        parca = []
        if birakilan:
            parca.append("yarım kalan iş: " + ", ".join(f"#{n}" for n in birakilan)
                         + " (aynı ajanla, kaldığı yerden sürecek)")
        if yeniden:
            parca.append(f"{yeniden} istek plan aşamasında kalmıştı, baştan çalışacak")
        ofis.db.olay_yaz(ofis.proje_id, "kesinti_toparlandi",
                         "Ofis kapanmadan önce yarım kalanlar bulundu: " + "; ".join(parca) + ".",
                         ajan_ad="ofis")
    return {"birakilan": birakilan, "yeniden": yeniden, "devam": devam}
