"""TAKIM SOHBETI -- insanin tek satirdan butun ekiple konusmasi.

Rakipte (Muratify, 29.09.2026 yayini) "Cekirdek takim sohbeti": insan
yazar, mesaj dogrudan bir ajana gider, ajan kendi adiyla cevap verir ve
sonucunu ayni akisa birakir. Bizde parcalarin HEPSI zaten vardi ama
daginiktI: lidere yazmak (sohbet), ajana sormak (danisma), calisan ajana
not (postane), ajanlarin birbirine sorulari, raporlar ve hukumler -- her
biri ayri bir yerde.

Bu dosya YENI BIR YETENEK eklemez, iki sey yapar:

1. **YONLENDIRIR.** Satirin basindaki `@ad` kime gittigini soyler; ne
   olacagina ofisin VAR OLAN kurallari karar verir:

   | yazilan                  | ne olur                                  |
   |--------------------------|------------------------------------------|
   | (adres yok) / `@lider`   | lidere (triyaj: cevap / kendi / dagit)   |
   | `@ajan` + elinde is var  | patronun NOTU (tur surerken ulasir)      |
   | `@ajan` + bosta          | SORU (danisma: salt okunur, arac yok)    |
   | `@ajan is: ...`          | IS -- ama liderin planindan gecer        |

   Son satir bilincli: rakipte ajana dogrudan is verilir ve kanit kapisi
   yoktur. Bizde "kimin yapacagi" patronun, "neye bitti denir" (kabul
   olcutu, yazma alani, kanit) liderin -- kapi atlanmaz, yalniz lider
   ajani secemez (`orkestra._plani_dogrula(atanan=)`).

2. **TEK AKIS verir.** Defterdeki mesajlar ve anlamli olaylar ayni zaman
   cizgisinde. Kopya tutulmaz: akis her istekte TURETILIR (sohbet
   `mesaj` tablosunda yasiyor kararinin aynisi -- iki yerde tutulan
   her sey en az bir kez kayar).
"""

from __future__ import annotations

import re

from .kadro import KadroHatasi

#: `@ad` + istege bagli `is:` oneki. Ad Turkce harf tasiyabilir.
_ADRES = re.compile(r"^\s*@([0-9A-Za-z_\-çğıöşüÇĞİÖŞÜ]+)[\s,:]*(.*)$", re.S)
_IS = re.compile(r"^\s*(?:is|iş|IS|İŞ|Is|İş)\s*[:\-]\s*(.*)$", re.S)

#: Akista gosterilen olaylar. Terminal olaylari (arac, cikti, nabiz)
#: GIRMEZ: sohbet bir kayit defteri degil, konusmadir.
AKIS_OLAYLARI = ("rapor", "gorev_acildi", "kapandi", "ret", "onay_istendi")
AZAMI_METIN = 600


class TakimHatasi(ValueError):
    pass


def ayristir(metin: str) -> dict:
    """`{"ad": str|"", "metin": str, "is_mi": bool}`. Adres yoksa ad bos."""
    metin = (metin or "").strip()
    m = _ADRES.match(metin)
    if not m:
        return {"ad": "", "metin": metin, "is_mi": False}
    ad, kalan = m.group(1), m.group(2).strip()
    i = _IS.match(kalan)
    if i:
        return {"ad": ad, "metin": i.group(1).strip(), "is_mi": True}
    return {"ad": ad, "metin": kalan, "is_mi": False}


def _elindeki_is(ofis, ad: str):
    with ofis.db.baglanti() as conn:
        row = conn.execute(
            "SELECT no FROM gorev WHERE proje_id = ? AND sahip = ? "
            "AND durum IN ('calisiyor', 'inceleme') AND silindi = 0 "
            "ORDER BY guncellendi DESC, rowid DESC LIMIT 1",
            (ofis.proje_id, ad)).fetchone()
    return row["no"] if row else None


def yonlendir(ofis, metin: str) -> dict:
    """Satirin nereye gidecegine KARAR verir; hicbir sey yazmaz.

    Doner: `{yol, ajan, lider, metin, gorev_no}`; `yol` lider | not |
    soru | is. Bilinmeyen ad REDDEDILIR ve gecerli adlar sayilir --
    yanlis yazilmis bir adin sessizce lidere dusmesi, mesajin yanlis
    kisiye gittigini insana hic gostermezdi.
    """
    a = ayristir(metin)
    if not a["metin"]:
        raise TakimHatasi("Bos mesaj gonderilemez.")
    if not a["ad"] or a["ad"].lower() in ("lider", "hepsi", "ekip"):
        return {"yol": "lider", "ajan": "", "lider": "", "metin": a["metin"],
                "gorev_no": None}
    kadro = {x["ad"]: x for x in ofis.kadro.liste()}
    ajan = kadro.get(a["ad"])
    if ajan is None:
        # Buyuk/kucuk harf farki bir yazim hatasidir, baska bir kisi degil.
        eslesen = [x for ad, x in kadro.items() if ad.lower() == a["ad"].lower()]
        ajan = eslesen[0] if len(eslesen) == 1 else None
    if ajan is None:
        raise TakimHatasi(
            f"'@{a['ad']}' diye biri yok. Ofistekiler: "
            + ", ".join("@" + ad for ad in kadro) + " (ya da @ olmadan lidere yaz).")
    if ajan["lider_mi"]:
        if a["is_mi"]:
            raise TakimHatasi(
                f"{ajan['ad']} lider: is dagitir, kendisi yapmaz. `is:` "
                "olmadan yaz; kime verecegine lider karar verir.")
        return {"yol": "lider", "ajan": "", "lider": ajan["ad"],
                "metin": a["metin"], "gorev_no": None}
    try:
        lider_ad = ofis.kadro.lider(ajan["kanat_id"])["ad"]
    except KadroHatasi:
        lider_ad = ""
    if a["is_mi"]:
        if not lider_ad:
            raise TakimHatasi(
                f"{ajan['ad']}'in takiminda lider yok: isi planlayacak kimse "
                "yok. Once o takima bir lider ise al.")
        return {"yol": "is", "ajan": ajan["ad"], "lider": lider_ad,
                "metin": a["metin"], "gorev_no": None}
    no = _elindeki_is(ofis, ajan["ad"])
    if no is not None:
        return {"yol": "not", "ajan": ajan["ad"], "lider": lider_ad,
                "metin": a["metin"], "gorev_no": no}
    return {"yol": "soru", "ajan": ajan["ad"], "lider": lider_ad,
            "metin": a["metin"], "gorev_no": None}


def _kes(m: str) -> str:
    m = (m or "").strip()
    return m if len(m) <= AZAMI_METIN else m[:AZAMI_METIN] + "…"


def akis(ofis, *, kanat_id=None, adet: int = 80) -> list:
    """Takimin konusmasi -- yeni en altta. Her oge:

    `{an, kimden, kime, tur, metin, gorev_no, id, bekliyor}`
    `tur`: sohbet · soru · not · cevap · rapor · is · kapandi · ret · onay.
    Kanat verilirse yalniz o takimin ajanlarina degen ogeler kalir.
    """
    adet = max(1, min(int(adet or 80), 300))
    kadro = {a["ad"]: a for a in ofis.kadro.liste()}

    def takimda(*adlar) -> bool:
        if kanat_id is None:
            return True
        return any(kadro.get(ad, {}).get("kanat_id") == kanat_id for ad in adlar)

    ogeler = []
    with ofis.db.baglanti() as conn:
        mesajlar = conn.execute(
            "SELECT m.rowid AS sira, m.*, g.no AS gorev_no FROM mesaj m "
            "LEFT JOIN gorev g ON g.id = m.gorev_id WHERE m.proje_id = ? "
            "AND m.mod != 'sessiz' ORDER BY m.rowid DESC LIMIT ?",
            (ofis.proje_id, adet)).fetchall()
        olaylar = conn.execute(
            "SELECT o.rowid AS sira, o.*, g.no AS gorev_no FROM olay o "
            "LEFT JOIN gorev g ON g.id = o.gorev_id WHERE o.proje_id = ? "
            "AND o.tur IN (%s) ORDER BY o.rowid DESC LIMIT ?"
            % ",".join("?" * len(AKIS_OLAYLARI)),
            (ofis.proje_id, *AKIS_OLAYLARI, adet)).fetchall()
    for m in mesajlar:
        m = dict(m)
        if not takimda(m["gonderen"], m["alici"]):
            continue
        if m["mod"] == "yonlendirme":
            tur = "not"
        elif m["gonderen"] == "insan" and kadro.get(m["alici"], {}).get("lider_mi"):
            tur = "sohbet"
        else:
            tur = "soru"
        ogeler.append({"an": m["olusturuldu"], "sira": (m["sira"], 0),
                       "kimden": m["gonderen"], "kime": m["alici"],
                       "tur": tur, "metin": _kes(m["govde"]),
                       "gorev_no": m["gorev_no"], "id": m["id"],
                       "bekliyor": (tur != "not" and not m["cevaplandi"]),
                       "ulasti": bool(m["okundu"]) if tur == "not" else None})
        if m["cevaplandi"] and tur != "not":
            ogeler.append({"an": m["cevaplandi"], "sira": (m["sira"], 1),
                           "kimden": m["alici"], "kime": m["gonderen"],
                           "tur": "cevap", "metin": _kes(m["cevap"]),
                           "gorev_no": m["gorev_no"], "id": m["id"],
                           "bekliyor": False, "ulasti": None})
    tur_adi = {"rapor": "rapor", "gorev_acildi": "is", "kapandi": "kapandi",
               "ret": "ret", "onay_istendi": "onay"}
    for o in olaylar:
        o = dict(o)
        ajan = o["ajan_ad"] or ""
        if not takimda(ajan):
            continue
        ogeler.append({"an": o["olusturuldu"], "sira": (0, o["sira"]),
                       "kimden": ajan or "ofis", "kime": "", "tur": tur_adi[o["tur"]],
                       "metin": _kes(o["govde"]), "gorev_no": o["gorev_no"],
                       "id": "", "bekliyor": False, "ulasti": None})
    # Zaman saniye cozunurluklu: ayni saniyedekiler kendi tablosundaki
    # sirayla kalir (karar tablosunda odenen beraberlik tuzagi).
    ogeler.sort(key=lambda x: (x["an"] or "", x["sira"]))
    for x in ogeler:
        x.pop("sira", None)
    return ogeler[-adet:]
