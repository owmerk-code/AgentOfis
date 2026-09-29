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
AKIS_OLAYLARI = ("rapor", "gorev_acildi", "kapandi", "ret", "onay_istendi",
                 "ajan_sohbet")
#: Akista metin KESILMEZ (4000 = cevap siniri, yalniz bellek korumasi).
#: OLCULDU (29.09.2026): ilk surum her ogeyi 600 harfte kesiyordu ve
#: liderin uzun cevabi panelde "**3..." diye yarida kaldi -- eski sohbet
#: panosu TAM gosteriyordu, yani yeni akis geriye gitmisti. Uzun metni
#: katlamak ARAYUZUN isi ("Tamamini oku"), veriyi kirpmak degil.
AZAMI_METIN = 4000


class TakimHatasi(ValueError):
    pass


# ---------------------------------------------------------------------------
# GENEL KANAL (29.09.2026) -- birden cok takimli ofiste "Tum ofis"ten yazmak
#
# Kullanici ile kararlastirildi: genel mudur YOK; her takimin lideri ve
# sohbeti var; "Genel" kanal bir YONLENDIRICIDIR. `@TAKIM ...` o takimin
# liderine gider; adres yoksa ofis en uygun takimi ONERIR, insan secer.
# Ofis KENDI BASINA SECMEZ: yanlis kanada verilen hedef, yanlis kadroya
# yanlis isi verir (orkestra._lider_sec'in reddettigi hata).
#
# Oneri model CAGIRMADAN hesaplanir (kota harcamaz): mesajin kelimeleri
# ile takimin adi, uyelerinin rolleri ve son islerinin basliklari. Kelime
# eslesmesi hafizanin kullandigiyla AYNI (`bellek._kelimeler/_ortak`,
# Turkce ek icin onek) -- ikinci bir kopya yazilmadi.
# ---------------------------------------------------------------------------

def kanatlar(ofis) -> list:
    with ofis.db.baglanti() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, ad, onek FROM kanat WHERE proje_id = ? "
            "ORDER BY olusturuldu, rowid", (ofis.proje_id,)).fetchall()]


def kanat_bul(ofis, ad: str):
    """`@URUN`, `@urun`, `@Ürün` ya da onek (`@UR`) -> kanat; yoksa None."""
    from .bellek import _sadelestir
    hedef = _sadelestir(ad)
    for k in kanatlar(ofis):
        if hedef in (_sadelestir(k["ad"]), _sadelestir(k["onek"])):
            return k
    return None


def takim_oner(ofis, metin: str, azami: int = 4) -> list:
    """Liderli takimlari mesaja uygunluguna gore siralar.

    Doner: [{kanat_id, ad, lider, puan, sebep}] -- puan ortak kelime sayisi.
    Hepsi 0 ise ONERI YOKTUR (siralama yalniz kurulus sirasidir) ve bu
    `puan` alanindan okunur: uydurma bir "en uygun" gosterilmez.
    """
    from .bellek import _kelimeler, _ortak
    from . import roller
    mesaj = _kelimeler(metin)
    kadro = ofis.kadro.liste()
    sonuc = []
    for k in kanatlar(ofis):
        uyeler = [a for a in kadro if a["kanat_id"] == k["id"]]
        lider = next((a["ad"] for a in uyeler if a["lider_mi"]), "")
        if not lider:
            continue
        parca = [k["ad"]]
        for a in uyeler:
            parca.append(a["meslek"])
            try:
                parca.append(roller.rol(a["meslek"]).ozet)
            except Exception:                    # noqa: BLE001 -- eski meslek adi
                pass
        with ofis.db.baglanti() as conn:
            parca += [r["baslik"] for r in conn.execute(
                "SELECT baslik FROM gorev WHERE proje_id = ? AND kanat_id = ? "
                "AND silindi = 0 ORDER BY rowid DESC LIMIT 40",
                (ofis.proje_id, k["id"])).fetchall()]
        havuz = _kelimeler(" ".join(parca))
        ortak = sorted(x for x in mesaj if _ortak({x}, havuz))
        sonuc.append({"kanat_id": k["id"], "ad": k["ad"], "lider": lider,
                      "puan": len(ortak), "sebep": ", ".join(ortak[:5])})
    sonuc.sort(key=lambda x: -x["puan"])
    return sonuc[:azami]


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
        # GENEL KANAL: `@TAKIM` o takimin LIDERINE gider. Ayni adda bir
        # ajan varsa ajan kazanir (yukarida) -- kisi, takimdan ozeldir.
        k = kanat_bul(ofis, a["ad"])
        if k is not None:
            if a["is_mi"]:
                raise TakimHatasi(
                    f"`@{k['ad']} is:` olmaz: takima is LIDERI uzerinden verilir. "
                    f"`is:` olmadan yaz ya da `@ajan is:` kullan.")
            try:
                lider_ad = ofis.kadro.lider(k["id"])["ad"]
            except KadroHatasi:
                raise TakimHatasi(f"{k['ad']} takiminin lideri yok. Once o "
                                  "takima bir lider ise al.")
            return {"yol": "lider", "ajan": "", "lider": lider_ad,
                    "metin": a["metin"], "gorev_no": None, "kanat": k["ad"]}
        takimlar = [k["ad"] for k in kanatlar(ofis)]
        raise TakimHatasi(
            f"'@{a['ad']}' diye biri ya da bir takim yok. Ofistekiler: "
            + ", ".join("@" + ad for ad in kadro)
            + (" · takimlar: " + ", ".join("@" + t for t in takimlar) if takimlar else "")
            + " (ya da @ olmadan lidere yaz).")
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
               "ret": "ret", "onay_istendi": "onay",
               "ajan_sohbet": "bildirim"}
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
    ogeler = ogeler[-adet:]
    # Kimin konustugu (meslegi) ve isin SU ANKI durumu: rakipteki gibi
    # "Kamil Amca · frontend" ve bir durum etiketi. Durum defterden
    # okunur, ogeye yazilmis eski hal degil -- "basliyor" diyen bir
    # etiket is bittikten sonra da oyle kalirsa yanlis gosterir.
    nolar = sorted({x["gorev_no"] for x in ogeler if x.get("gorev_no")})
    durumlar = {}
    if nolar:
        with ofis.db.baglanti() as conn:
            for r in conn.execute(
                    "SELECT no, durum FROM gorev WHERE proje_id = ? AND no IN (%s)"
                    % ",".join("?" * len(nolar)), (ofis.proje_id, *nolar)):
                durumlar[r["no"]] = r["durum"]
    for x in ogeler:
        x.pop("sira", None)
        a = kadro.get(x["kimden"])
        x["meslek"] = (a or {}).get("meslek", "")
        x["gorev_durum"] = durumlar.get(x.get("gorev_no"), "")
    return ogeler
