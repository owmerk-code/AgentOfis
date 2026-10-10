# -*- coding: utf-8 -*-
"""DURUM TABLOSU (08.10.2026, PLAN B2 + B4): her isin GERCEK durumu, her ajanin
ne yaptigi, sirada ne oldugu -- TEK ekranda, NEDENIYLE.

Patron (29.09): "her is gercek durumuyla" ekrani; "lider durum tablosu: kim
calisiyor, sirada ne var, neden". Kanban yalniz tahtadaki sutunu soyler
(`calisiyor`); is o an senin onayini mi, bir girisi mi, kredi onayini mi,
baska bir isi mi bekliyor -- orada yazmaz. Burada her isin "nerede" satiri
olculmus kayittan (onay, soru, bagimlilik, surec, son arac adimi) cikar.

UYDURMAZ: olculemeyen alan bos kalir. Yeni kural koymaz: teshisler var olan
kaynaklardan okunur (postane, tahta, surec, kuyruk, giris, tarayici).
"""

from __future__ import annotations

from datetime import datetime, timezone

ACIK_DURUMLAR = ("bekliyor", "hazir", "calisiyor", "inceleme")

#: "nerede" satirinin TURU -- panel renk ve sira icin kullanir. Sira: once
#: SENI bekleyenler, sonra durmus olanlar, sonra calisanlar, sonra sirada.
TUR_SIRASI = {"sen": 0, "durdu": 1, "calisiyor": 2, "inceleme": 3, "bekliyor": 4, "sirada": 5}


def _yas_sn(zaman: str):
    try:
        t = datetime.fromisoformat(str(zaman).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - t).total_seconds()))
    except (ValueError, TypeError):
        return None


DURDU_METNI = "durdu — Sürdür'e bas"
#: (Pay yok: `Koltuk.akit` isareti SAHIPLENMEDEN ONCE yazar, sahiplenme turun icinde.)


def tur_olcumu(ofis, gorev: dict):
    """`calisiyor` bir isin icin OFIS O AN TUR KOSTURUYOR MU? -> (True/False/None, kaynak).

    TEK OLCUM: durum panosu (`isler`), sohbet raporu (`sohbet._gercek_durum`) ve
    sohbet karti (`takim.kartlar`) ayni cevabi buradan alir. Tahmin yok.

    KAYNAK: `ayar` tablosundaki TUR ISARETI (`tur_kosuyor:<gorev_id>`,
    surec.tur_isaretle/tur_isareti). Koltuk (`Koltuk.akit`) turu BASLATINCA
    `surec_kimligi|zaman` yazar, tur sirasinda 15 sn'de bir tazeler, tur
    NASIL biterse bitsin `|zaman` (kimliksiz) yapar. Yazma kilidinin
    `son_nabiz`i KULLANILMAZ: o `sahiplen`de turdan once dogar ve tur
    bittikten sonra 180 sn "taze" kalir (inceleme 10.10).

    Karar (sirayla):
    1. `gorev.kosan_surec` olu -> False.
    2. Isaret yok: is, kaynagin ilk etkin oldugu andan (ayar `tur_isareti_ilk`)
       SONRA sahiplenildiyse hic tur baslamamis -> False. Once sahiplenildiyse
       (isaret yazmayan eski kod, gecis) ya da kaynak hic yazilmadiysa -> None.
    3. Isaret temizlenmis (tur bitti) -> False.
    4. Isaretin sureci olu -> False; zamani okunamadi -> None.
    5. Isaret `tahta.KILIT_KIRA_SANIYE` icinde tazelenmis -> True, degilse False.
    Okuma hatasi -> None: cagiran ESKI gostergeyi korur.

    Onay/soru bekleyen ve duraklatilmis isleri cagiran AYIRIR.
    """
    from . import surec
    from .tahta import KILIT_KIRA_SANIYE
    kosan = gorev.get("kosan_surec") or ""
    if kosan and surec.yasiyor(kosan) is False:
        return False, "gorev.kosan_surec: isi ustlenen surec kapanmis"
    try:
        iz = surec.tur_isareti(ofis.db, ofis.proje_id, gorev["id"])
    except Exception:                            # noqa: BLE001 -- okunamadi: olculemedi
        return None, "ayar tur_kosuyor okunamadi"
    if iz is None:
        # Isaret yok: "tur kosmuyor" demek icin kaynagin BU ISTEN ONCE etkin
        # olmasi sart. Isaret yazmayan ESKI kodla baslamis is (gecis) ya da
        # kaynagin hic yazilmadigi defter -> OLCULEMEZ, eski gosterge kalir.
        try:
            ilk = surec.tur_kaynagi_ilk(ofis.db, ofis.proje_id)
            with ofis.db.baglanti() as c:
                r = c.execute("SELECT olusturuldu FROM olay WHERE proje_id = ? AND gorev_id = ? "
                              "AND tur = 'sahiplenildi' ORDER BY rowid DESC LIMIT 1",
                              (ofis.proje_id, gorev["id"])).fetchone()
        except Exception:                        # noqa: BLE001
            return None, "ayar tur_isareti_ilk okunamadi"
        if not ilk:
            return None, "tur isareti kaynagi bu defterde henuz hic yazilmamis (eski kod)"
        yas_ilk = _yas_sn(ilk)
        yas_alis = _yas_sn(r[0] if r else gorev.get("guncellendi"))
        if yas_ilk is None or yas_alis is None:
            return None, "sahiplenme/kaynak zamani okunamadi"
        if yas_alis > yas_ilk:
            return None, "is isaret kaynagindan ONCE baslamis (eski kod): olculemez"
        return False, "ayar tur_kosuyor: bu is icin hic tur baslamamis"
    kim, zaman = iz
    yas_z = _yas_sn(zaman)
    if not kim:
        return False, f"ayar tur_kosuyor: tur {yas_z} sn once bitti"
    if surec.yasiyor(kim) is False:
        return False, "ayar tur_kosuyor: turu kosturan surec kapanmis"
    if yas_z is None:
        return None, "ayar tur_kosuyor zamani okunamadi"
    if yas_z <= KILIT_KIRA_SANIYE:
        return True, f"ayar tur_kosuyor: isaret {yas_z} sn once tazelendi (<= {KILIT_KIRA_SANIYE})"
    return False, f"ayar tur_kosuyor: isaret {yas_z} sn once tazelendi (> {KILIT_KIRA_SANIYE}): kosan tur yok"


#: Panel kurulunca baglanir: `islev(kanat_id) -> bool` -- ofis o takimin halkasini
#: (ya da butun ofisin halkasini) SU AN kosturuyor mu. Bos ise (kabuk, sinama)
#: bilinmiyor sayilir ve eski gosterge kalir.
HALKA_SORGUSU = {"islev": None}
SIRADA_METNI = "sırada — ofis çalışıyor, sırası gelince sürer"


def halka_kosuyor(gorev: dict) -> bool:
    """Isin takiminin halkasi su an kosuyor mu (panelin `_KOSU`su).

    10.10: tur kosmayan `calisiyor` is ofis CALISIRKEN de olur -- geri
    gonderildikten sonraki birkac saniye, kabin baska takimdayken, ya da
    ayni takimin baska isi kosarken. Ona "durdu -- Surdur'e bas" demek
    yanlis: patron basar, panel "zaten kosuyor" der. Dogrusu "sirada"."""
    islev = HALKA_SORGUSU.get("islev")
    if islev is None:
        return False
    try:
        return bool(islev(gorev.get("kanat_id") or ""))
    except Exception:                            # noqa: BLE001 -- bilinmiyor: eski gosterge
        return False


def tur_kosuyor_mu(ofis, gorev: dict):
    """True: tur kosuyor. False: kosmuyor. None: olculemedi (bkz. `tur_olcumu`)."""
    return tur_olcumu(ofis, gorev)[0]


def _onay_turu(o: dict) -> str:
    from . import giris
    from .tarayici import KREDI_PAKETI_ISARETI
    if giris.giris_mi(o):
        return "giris"
    metin = f"{o.get('eylem') or ''} {o.get('ayrinti') or ''}"
    if KREDI_PAKETI_ISARETI in metin or "KREDI" in metin.upper():
        return "kredi"
    return "onay"


def isler(ofis) -> list:
    """Acik her is: nerede, neyi bekliyor, son adim. En acil ustte."""
    from . import surec
    db, pid = ofis.db, ofis.proje_id
    onaylar = ofis.postane.bekleyen_onaylar()
    sorular = ofis.postane.bekleyen_sorular()
    with db.baglanti() as c:
        gorevler = [dict(r) for r in c.execute(
            "SELECT g.*, k.ad AS takim FROM gorev g LEFT JOIN kanat k ON k.id = g.kanat_id "
            "WHERE g.proje_id = ? AND g.silindi = 0 AND g.durum IN (?, ?, ?, ?) "
            "ORDER BY g.no", (pid, *ACIK_DURUMLAR))]
        son_adim = {}
        for r in c.execute(
                "SELECT gorev_id, tur, govde, olusturuldu FROM olay WHERE proje_id = ? "
                "AND gorev_id IS NOT NULL AND tur IN ('arac', 'kanit', 'not_iletildi', "
                "'incelemede', 'ret', 'birakildi', 'hata') ORDER BY rowid", (pid,)):
            son_adim[r["gorev_id"]] = dict(r)
        retler = {r[0]: r[1] for r in c.execute(
            "SELECT gorev_id, COUNT(*) FROM olay WHERE proje_id = ? AND tur = 'ret' "
            "GROUP BY gorev_id", (pid,))}
    kadro = {a["ad"]: a for a in ofis.kadro.liste()}
    out = []
    for g in gorevler:
        no = g["no"]
        bekleyen_onay = [o for o in onaylar if o.get("gorev_no") == no]
        bekleyen_soru = [s for s in sorular if s.get("gorev_no") == no]
        tur, nerede, olcum = "", "", ""
        if bekleyen_onay:
            o = bekleyen_onay[0]
            ot = _onay_turu(o)
            tur = "sen"
            nerede = {"giris": "giriş bekliyor — gömülü tarayıcıda senin girmen gerekiyor",
                      "kredi": "kredi onayını bekliyor — üretim senin onayınla başlar",
                      }.get(ot, f"onayını bekliyor: {str(o.get('eylem') or '')[:120]}")
        elif bekleyen_soru:
            s = bekleyen_soru[0]
            if s.get("alici") == "insan":
                tur, nerede = "sen", f"cevabını bekliyor: {str(s.get('govde') or '')[:120]}"
            else:
                tur, nerede = "bekliyor", f"sordu → {s.get('alici')}, cevabını bekliyor"
        elif g.get("duraklatildi"):
            tur, nerede = "durdu", "durduruldu — devam için Sürdür"
        elif g["durum"] == "calisiyor":
            canli, olcum = tur_olcumu(ofis, g)
            if canli is False and halka_kosuyor(g):
                tur, nerede = "sirada", SIRADA_METNI
            elif canli is False:
                tur, nerede = "durdu", DURDU_METNI
            else:
                tur, nerede = "calisiyor", "çalışıyor"
        elif g["durum"] == "inceleme":
            try:
                lider = ofis.kadro.gorevin_lideri(g)["ad"]
            except Exception:                    # noqa: BLE001
                lider = "lider"
            tur, nerede = "inceleme", f"{lider} inceliyor / incelemesini bekliyor"
        else:
            blok = ofis.tahta.blokcular(no)
            if blok:
                tur = "bekliyor"
                nerede = "önce bitmesi gereken: " + ", ".join(f"#{b['no']} {b['baslik'][:40]}" for b in blok)
            else:
                sahip = g.get("sahip") or ""
                mesgul = [x for x in gorevler if x["sahip"] == sahip and x["durum"] == "calisiyor"
                          and x["no"] != no] if sahip else []
                tur = "sirada"
                nerede = (f"sırada — {sahip} şu an #{mesgul[0]['no']} üzerinde" if mesgul
                          else "sırada — ajan boşalınca başlar")
        adim = son_adim.get(g["id"]) or {}
        ajan = kadro.get(g.get("sahip") or "") or {}
        out.append({
            "olcum": olcum,
            "no": no, "baslik": g["baslik"], "takim": g.get("takim") or "",
            "sahip": g.get("sahip") or "", "durum": g["durum"], "tur": tur, "nerede": nerede,
            "model": g.get("patron_modeli") or "/".join(x for x in (ajan.get("motor"), ajan.get("model")) if x),
            "ret": int(retler.get(g["id"]) or 0),
            "son_adim": (str(adim.get("govde") or "").splitlines() or [""])[0][:140] if adim else "",
            "son_adim_turu": adim.get("tur") or "",
            "son_adim_yas_sn": _yas_sn(adim.get("olusturuldu")) if adim else None,
            "yas_sn": _yas_sn(g.get("guncellendi")),
        })
    out.sort(key=lambda x: (TUR_SIRASI.get(x["tur"], 9), x["no"]))
    return out


def ajanlar(ofis, is_listesi: list = None) -> list:
    """Her ajan ne yapiyor: elindeki is, bekledigi sey, siradaki isi."""
    is_listesi = is_listesi if is_listesi is not None else isler(ofis)
    out = []
    for a in ofis.kadro.liste():
        elindeki = [x for x in is_listesi if x["sahip"] == a["ad"]]
        calisan = next((x for x in elindeki if x["durum"] == "calisiyor"), None)
        if calisan:
            ne = f"#{calisan['no']} {calisan['baslik'][:50]} — {calisan['nerede']}"
            hal = "sen" if calisan["tur"] == "sen" else ("durdu" if calisan["tur"] == "durdu" else "calisiyor")
        elif any(x["durum"] == "inceleme" for x in elindeki):
            x = next(x for x in elindeki if x["durum"] == "inceleme")
            ne, hal = f"#{x['no']} incelemede", "inceleme"
        else:
            ne, hal = "boşta", "bos"
        sira = [x for x in elindeki if x["tur"] in ("sirada", "bekliyor") and x is not calisan]
        out.append({"ad": a["ad"], "meslek": a.get("meslek") or "", "lider": bool(a.get("lider_mi")),
                    "takim": a.get("kanat_id") or "",
                    "model": "/".join(x for x in (a.get("motor"), a.get("model")) if x),
                    "hal": hal, "ne": ne,
                    "sirada": [f"#{x['no']} {x['baslik'][:40]}" for x in sira][:3]})
    out.sort(key=lambda x: ({"sen": 0, "durdu": 1, "calisiyor": 2, "inceleme": 3}.get(x["hal"], 4), x["ad"]))
    return out


def sira(ofis) -> list:
    """Lidere giden ama henuz baslamamis patron istekleri (is kuyrugu)."""
    from . import kuyruk
    try:
        return [{"metin": str(k.get("metin") or "")[:160], "lider": k.get("lider_ad") or "",
                 "durum": k.get("durum") or "", "yas_sn": _yas_sn(k.get("olusturuldu"))}
                for k in kuyruk.bekleyenler(ofis)]
    except Exception:                            # noqa: BLE001 -- olculemedi: bos
        return []


def tablo(ofis) -> dict:
    i = isler(ofis)
    return {"isler": i, "ajanlar": ajanlar(ofis, i), "sira": sira(ofis),
            "ozet": {t: sum(1 for x in i if x["tur"] == t) for t in TUR_SIRASI}}
