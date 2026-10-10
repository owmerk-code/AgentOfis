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
#: SOHBET = PATRONUN KONUSMASI (30.09.2026).
#:
#: Kullanici (ekran goruntusuyle): *"sohbet kismi normal olacak, burada
#: seninle nasil konusuyorsam oyle; bir ekran goruntusu almak bu kadar zor
#: olmamali, bu kadar seyi sohbete neden yazdi?"* Tek bir is icin sohbete
#: ajanin tur raporu, liderin uzun ret gerekcesi, ikinci rapor ve
#: "kapandi" satiri dustu. Bunlar ISIN ayrintisidir: gorev cekmecesinde ve
#: terminalde durur. Sohbete yalniz patronu ilgilendiren girer: patronun
#: mesaji, liderin cevabi/raporu, patrona sorulan soru ve onay, ajanin
#: patrona gonderdigi dosya/engel (`sohbete_yaz`). Ajanlar arasi soru da
#: sohbete girmez (patron o konusmanin tarafi degil).
# `donus_raporu` (01.10.2026): kuyruk serisi bitince ofisin modelsiz ozeti.
AKIS_OLAYLARI = ("onay_istendi", "ajan_sohbet", "donus_raporu", "kesinti_toparlandi",
                 "zamanli_calisti", "takildi", "hafiza_reddi",
                 "beceri_taslagi", "hata_suphesi")
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


_KOD_ARACI = re.compile(r"tools\.(?:mcp__)?([A-Za-z0-9_]+?)(?:__([A-Za-z0-9_]+))?\s*\(\s*(\{[^}]{0,300})?")


def _sure(bas: str, son: str):
    """Iki ISO an arasi saniye; okunamazsa None (uydurmaz)."""
    from datetime import datetime
    try:
        return max(0, int((datetime.fromisoformat(son) - datetime.fromisoformat(bas))
                          .total_seconds()))
    except (TypeError, ValueError):
        return None


def kabul_et(ofis, mesaj_id: str) -> dict:
    """Patron teslimi KABUL etti: an yazilir, karar gunlugune girer.

    Ileride liderin karar kalitesi (E29) ve teslime puan (E78) bunu
    okur; bugun patronun "tamam" demesinin kalici izidir.
    """
    from .db import simdi
    with ofis.db.baglanti() as c:
        m = c.execute("SELECT * FROM mesaj WHERE proje_id = ? AND id = ?",
                      (ofis.proje_id, mesaj_id)).fetchone()
        if not m or m["gonderen"] != "insan" or not m["cevaplandi"]:
            raise TakimHatasi("Kabul edilecek, cevaplanmis bir istek bulunamadi.")
        if m["kabul"]:
            return dict(m)
        c.execute("UPDATE mesaj SET kabul = ? WHERE id = ?", (simdi(), mesaj_id))
    ofis.bellek.karar_yaz(f"Patron teslimi kabul etti: {' '.join(m['govde'].split())[:100]}",
                          "Patron panelde Kabul et'e basti.", "insan", tur="genel")
    return dict(m)


def adim_ozeti(govde: str) -> dict:
    """Arac olayi -> {ad, ozet}: insanin okuyacagi tek satir.
    `mcp__tarayici__browser_navigate` -> `browser_navigate`; Codex'in kod
    kipindeki `Bash` sarmali acilir."""
    satirlar = (govde or "").split("\n")
    ad = satirlar[0].strip()
    arg = " ".join(s.strip() for s in satirlar[1:] if s.strip())
    if ad == "Bash" and "tools." in arg:
        m = _KOD_ARACI.search(arg)
        if m:
            ad = m.group(2) or m.group(1)
            arg = (m.group(3) or "").lstrip("{")
    ad = ad.split("__")[-1]
    return {"ad": ad[:40], "ozet": arg[:110]}


def istek_durumlari(ofis, istek_idleri) -> dict:
    """`{istek_id: {isler, aktif, son, adim}}` -- yalniz bagli isi olan istekler.

    `son`: calisan isin son durum notu ya da ajanin son cumlesi (tek satir).
    `adim`: bu istegin islerinde ajanlarin yaptigi islem (arac) sayisi.
    Hepsi DEFTERDEN; uydurulmaz."""
    out = {}
    soru = ",".join("?" * len(istek_idleri))
    with ofis.db.baglanti() as c:
        isler = c.execute(
            f"SELECT id, no, baslik, sahip, durum, istek_id, guncellendi FROM gorev WHERE proje_id = ? "
            f"AND istek_id IN ({soru}) "
            # DURUM SATIRI CALISANI gosterir (olculdu: incelemedeki is
            # calisanin onune geciyordu): calisiyor > inceleme > hazir.
            "ORDER BY CASE durum WHEN 'calisiyor' THEN 0 WHEN 'inceleme' THEN 1 "
            "WHEN 'hazir' THEN 2 ELSE 3 END, no", (ofis.proje_id, *istek_idleri)).fetchall()
        for g in isler:
            d = out.setdefault(g["istek_id"], {"isler": [], "aktif": None, "son": "",
                                               "adim": 0, "adimlar": []})
            # ADIMLAR (Claude Code'daki islem satirlari gibi): ajanin son
            # islemleri, kisa. Codex araclari kod kipinden cagirir
            # (`tools.mcp__x__y(...)`); asil arac adi oradan okunur.
            for r in c.execute("SELECT ajan_ad, govde FROM olay WHERE gorev_id = ? AND tur = 'arac' "
                               "ORDER BY rowid DESC LIMIT 25", (g["id"],)).fetchall()[::-1]:
                d["adimlar"].append({"ajan": r[0], **adim_ozeti(r[1] or "")})
            d["isler"].append({"no": g["no"], "sahip": g["sahip"], "durum": g["durum"],
                               "baslik": g["baslik"]})
            d["adim"] += c.execute("SELECT COUNT(*) FROM olay WHERE gorev_id = ? AND tur = 'arac'",
                                   (g["id"],)).fetchone()[0]
            if d["aktif"] is None and g["durum"] in ("calisiyor", "inceleme", "hazir"):
                bas = c.execute("SELECT olusturuldu FROM olay WHERE gorev_id = ? AND tur = 'sahiplenildi' "
                                "ORDER BY rowid DESC LIMIT 1", (g["id"],)).fetchone()
                son = c.execute("SELECT govde FROM olay WHERE gorev_id = ? AND tur IN ('durum_notu', 'cikti') "
                                "ORDER BY rowid DESC LIMIT 1", (g["id"],)).fetchone()
                d["aktif"] = {"no": g["no"], "sahip": g["sahip"], "durum": g["durum"],
                              "basladi": bas[0] if bas else ""}
                satir = next((s.strip() for s in (son[0] if son else "").splitlines() if s.strip()), "")
                d["son"] = satir[:140]
    return out


def devam_metni(istek: str) -> str:
    """Kadro kurulunca suren istegin sohbetteki OFIS NOTU (07.10.2026).

    Patron: "Kur ve baslat dedikten sonra ayni mesaji neden bir daha sohbete
    atiyor? Claude Code / Codex boyle mi calisiyor?" -- onaydan sonra is
    kaldigi yerden surer, mesaj ikinci kez patronun agzindan yazilmaz.
    Lidere giden metin degismez (patronun sozu, izin alintisi ona dayanir)."""
    kisa = " ".join((istek or "").split())
    return "Kadro kuruldu, iş başlıyor: «" + (kisa[:90] + ("…" if len(kisa) > 90 else "")) + "»"


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
        # TAKIMIN DOGUMU (05.10.2026, patron: "yeni takim kurdum, bu mesaj ne?"):
        # ise baglanmayan ofis olayi (donus raporu, kesinti...) her takimda
        # gorunuyordu -- takim kurulmadan ONCEKILER de. Takim kendinden eski
        # ofis olayini gormez.
        _k = conn.execute("SELECT olusturuldu FROM kanat WHERE id = ?",
                          (kanat_id,)).fetchone() if kanat_id else None
        kanat_dogum = _k["olusturuldu"] if _k else ""
        mesajlar = conn.execute(
            "SELECT m.rowid AS sira, m.*, g.no AS gorev_no, g.istek_id AS gorev_istek FROM mesaj m "
            "LEFT JOIN gorev g ON g.id = m.gorev_id WHERE m.proje_id = ? "
            "AND m.mod != 'sessiz' ORDER BY m.rowid DESC LIMIT ?",
            (ofis.proje_id, adet)).fetchall()
        olaylar = conn.execute(
            "SELECT o.rowid AS sira, o.*, g.no AS gorev_no, g.kanat_id AS gorev_kanat, "
            "g.sahip AS gorev_sahip, g.istek_id AS gorev_istek FROM olay o "
            "LEFT JOIN gorev g ON g.id = o.gorev_id WHERE o.proje_id = ? "
            "AND o.tur IN (%s) ORDER BY o.rowid DESC LIMIT ?"
            % ",".join("?" * len(AKIS_OLAYLARI)),
            (ofis.proje_id, *AKIS_OLAYLARI, adet)).fetchall()
    for m in mesajlar:
        m = dict(m)
        if not takimda(m["gonderen"], m["alici"]):
            continue
        if "insan" not in (m["gonderen"], m["alici"]):
            continue          # ajanlar arasi: isin ayrintisi, sohbet degil
        if m["mod"] == "yonlendirme":
            tur = "not"
        elif m["gonderen"] == "insan" and kadro.get(m["alici"], {}).get("lider_mi"):
            tur = "sohbet"
        else:
            tur = "soru"
        devam = (m.get("kaynak") or "") == "ekip"
        ogeler.append({"an": m["olusturuldu"], "sira": (m["sira"], 0),
                       "kimden": "ofis" if devam else m["gonderen"], "kime": m["alici"],
                       "tur": tur, "metin": devam_metni(m["govde"]) if devam else _kes(m["govde"]),
                       "gorev_no": m["gorev_no"], "id": m["id"],
                       "istek": m["id"] if tur == "sohbet" else (m["gorev_istek"] or ""),
                       "bekliyor": (tur != "not" and not m["cevaplandi"]),
                       "ulasti": bool(m["okundu"]) if tur == "not" else None})
        if m["cevaplandi"] and tur != "not":
            ogeler.append({"an": m["cevaplandi"], "sira": (m["sira"], 1),
                           "kimden": m["alici"], "kime": m["gonderen"],
                           "tur": "cevap", "metin": _kes(m["cevap"]),
                           "gorev_no": m["gorev_no"], "id": m["id"],
                           "istek": m["id"] if tur == "sohbet" else "",
                           "bekliyor": False, "ulasti": None,
                           # TESLIM (02.10.2026; rakipte "6 dakika surdu ·
                           # Duzeltme iste · Kabul et"): istekten cevaba sure.
                           "sure_sn": _sure(m["olusturuldu"], m["cevaplandi"]),
                           "kabul": m.get("kabul") or ""})
    tur_adi = {"rapor": "rapor", "gorev_acildi": "is", "kapandi": "kapandi",
               "ret": "ret", "onay_istendi": "onay",
               "ajan_sohbet": "bildirim", "donus_raporu": "ozet",
               "kesinti_toparlandi": "ozet", "zamanli_calisti": "ozet",
               "takildi": "ozet", "hafiza_reddi": "ozet",
               "beceri_taslagi": "ozet", "hata_suphesi": "ozet"}
    for o in olaylar:
        o = dict(o)
        ajan = o["ajan_ad"] or ""
        # OFISIN KENDI OLAYI (takildi, kesinti, donus raporu: ajan "ofis")
        # 01.10.2026: takim gorunumunde HIC gorunmuyordu -- "ofis" hicbir
        # takimin ajani degil. Bir ise bagliysa o isin takiminda, degilse
        # her takimda gorunur (ayni kural: Orkestra.takimin_isi).
        if ajan in ("", "ofis") and kanat_id is not None:
            if o["gorev_id"] and not ofis.orkestra.takimin_isi(
                    {"kanat_id": o["gorev_kanat"], "sahip": o["gorev_sahip"]}, kanat_id):
                continue
            if not o["gorev_id"] and kanat_dogum and (o["olusturuldu"] or "") < kanat_dogum:
                continue
        elif not takimda(ajan):
            continue
        # DONUS RAPORU ayni saniyedeki her seyin SONUNDA (01.10.2026, canli
        # deneme: son isin cevabiyla ayni saniyede yazildi ve onun ustune dustu).
        _bas = (1 << 29) if o["tur"] == "donus_raporu" else 0
        ogeler.append({"an": o["olusturuldu"], "sira": (_bas, o["sira"]),
                       "kimden": ajan or "ofis", "kime": "", "tur": tur_adi[o["tur"]],
                       "metin": _kes(o["govde"]), "gorev_no": o["gorev_no"],
                       "istek": o["gorev_istek"] or "",
                       "id": "", "bekliyor": False, "ulasti": None})
    # Zaman saniye cozunurluklu: ayni saniyedekiler kendi tablosundaki
    # sirayla kalir (karar tablosunda odenen beraberlik tuzagi).
    ogeler.sort(key=lambda x: (x["an"] or "", x["sira"]))
    ogeler = ogeler[-adet:]
    # SIRADAKI ISLER (01.10.2026): kuyrukta bekleyen patron mesaji EN ALTTA
    # balon olarak gorunur (zamana gore dizilseydi kosan isin ustune duserdi).
    # Is baslayinca `Sohbet.konus` mesaji kendisi yazar ve bu balon kalkar --
    # ayni cumle iki kez gorunmez.
    from . import kuyruk as _kuyruk
    for _i, k in enumerate(_kuyruk.bekleyenler(ofis), 1):
        if not takimda(k["lider_ad"]):
            continue
        ogeler.append({"an": k["olusturuldu"], "sira": (1 << 30, _i),
                       "kimden": "insan", "kime": k["lider_ad"], "tur": "sirada",
                       "metin": _kes(k["metin"]), "gorev_no": None,
                       "id": k["id"], "bekliyor": False, "ulasti": None,
                       "sira_no": _i})
    # ILETILEMEDI (02.10.2026): dusen is sohbette kalir, sebebiyle.
    for k in _kuyruk.iletilemeyenler(ofis):
        if not takimda(k["lider_ad"]):
            continue
        ogeler.append({"an": k["bitti"], "sira": (1 << 30, 0),
                       "kimden": "ofis", "kime": "insan", "tur": "iletilemedi",
                       "metin": _kes(k["metin"]), "sebep": (k.get("not_") or "")[:300],
                       "gorev_no": None, "id": k["id"], "bekliyor": False,
                       "ulasti": None})
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
    # ISTEGIN CANLI DURUMU (02.10.2026, patron: "burada seninle konusur gibi"):
    # Claude Code'da is surerken tek satir durum gorunur, islemler katlanir.
    # Her patron istegi icin: bagli isler, calisani, son durum notu, adim sayisi.
    _istekler = [x["id"] for x in ogeler if x["tur"] == "sohbet"]
    _durum = istek_durumlari(ofis, _istekler) if _istekler else {}
    for x in ogeler:
        if x["tur"] == "sohbet" and x["id"] in _durum:
            x["istek_durum"] = _durum[x["id"]]
        # Cevabin altindaki teslim satiri: istegin isleri ne durumda.
        if x["tur"] == "cevap" and x.get("istek") in _durum:
            x["isler"] = _durum[x["istek"]]["isler"]
    # SONRADAN BITEN IS (02.10.2026, sinama panelinde olculdu: patron isi
    # duraklatti, cevap "bitmedi" diye yazildi, Surdur'den sonra is BITTI
    # ama sohbet hala "bitmedi" diyordu). Istegin cevabindan SONRA kapanan
    # is sohbete GUNCELLEME olarak duser: liderin patrona taslagi, yoksa
    # ofisin kaydi (modelsiz). Normal akista is cevaptan ONCE kapanir.
    _cevaplar = {x["istek"]: x for x in ogeler
                 if x["tur"] == "cevap" and x.get("istek") in _durum}
    guncel = []
    if _cevaplar:
        with ofis.db.baglanti() as conn:
            for ist, cv in _cevaplar.items():
                for r in conn.execute(
                        "SELECT g.id, g.no, g.baslik, o.olusturuldu AS an, o.rowid AS sira "
                        "FROM gorev g JOIN olay o ON o.gorev_id = g.id AND o.tur = 'kapandi' "
                        "WHERE g.proje_id = ? AND g.istek_id = ? AND g.durum = 'bitti' "
                        "AND o.olusturuldu > ?", (ofis.proje_id, ist, cv["an"])).fetchall():
                    t = conn.execute("SELECT govde FROM olay WHERE gorev_id = ? AND "
                                     "tur = 'rapor_taslak' ORDER BY rowid DESC LIMIT 1",
                                     (r["id"],)).fetchone()
                    k = conn.execute("SELECT COUNT(*) FROM kanit WHERE gorev_id = ?",
                                     (r["id"],)).fetchone()[0]
                    metin = ((t[0] if t else "") or
                             f"#{r['no']} {r['baslik']} bitti ({k} kanıt, lider kontrol etti).")
                    guncel.append({"an": r["an"], "sira": (r["sira"], 2),
                                   "kimden": cv["kimden"], "kime": "insan",
                                   "tur": "guncelleme", "metin": _kes(metin),
                                   "gorev_no": r["no"], "id": "", "istek": "",
                                   "bekliyor": False, "ulasti": None})
    if guncel:
        durumlar.update({x["gorev_no"]: "bitti" for x in guncel})   # cip "#40 bitti"
        _sabit = ("sirada", "iletilemedi")   # bilerek en altta kalanlar
        _akan = [x for x in ogeler if x["tur"] not in _sabit] + guncel
        _akan.sort(key=lambda x: (x["an"] or "", x["sira"]))
        ogeler = _akan + [x for x in ogeler if x["tur"] in _sabit]
    from . import ekler as _ek
    for x in ogeler:
        # EKLER mesaj satirindan cikarilir, balonda resim/baglanti olur.
        x["metin"], x["ekler"] = _ek.ayikla(x.get("metin") or "")
        x.pop("sira", None)
        a = kadro.get(x["kimden"])
        x["meslek"] = (a or {}).get("meslek", "")
        x["gorev_durum"] = durumlar.get(x.get("gorev_no"), "")
        # NOTUN GERCEK DURUMU (02.10.2026): is kapandiysa okunmamis not
        # ARTIK ULASMAYACAK -- "iletilecek" demek yanlis gosterge olurdu.
        if x["tur"] == "not" and not x["ulasti"]:
            if x["gorev_durum"] in ("bitti", "iptal"):
                x["ulasmadi"] = True
            elif x["gorev_durum"] == "inceleme":
                x["incelemede"] = True
    return ogeler


# ---------------------------------------------------------------------------
# SOHBET KARTLARI (09.10.2026, patron: "verilen islerin yaniti karisik; ne is
# verdim, ne isi yapti hepsi birbirine girmis" -> "A, basla"). Claude Code /
# Codex gibi: HER ISTEK TEK KART, tek durum, tek cevap. Ic isleyis (dagitim
# notu, ret, inceleme, kesinti, donus raporu) sohbete girmez; kartin katli
# ayrintisinda ya da gunlukte durur. Kart DEFTERDEN turetilir (`akis`), kopya
# tutulmaz.

#: Kart durumlari -- panelin tek durum dili.
KART_DURUMLARI = ("sirada", "dusunuyor", "calisiyor", "karar", "durdu", "bitti",
                  "iptal", "iletilemedi", "cevapsiz")
#: Sohbetten CIKAN ofis olaylari (gunlukte ve bildirimde kalirlar).
_KARTA_GIRMEZ = ("ozet",)


def _rapor_taslaklari(ofis, nolar) -> dict:
    """{is_no: liderin PATRONA taslagi} -- kapanan isin temiz sonucu."""
    if not nolar:
        return {}
    out = {}
    with ofis.db.baglanti() as c:
        # Liderin taslagi yoksa (is patronun KABULUYLE kapandi) ajanin patrona
        # son teslim mesaji; ikisi de yoksa sonuc yok (uydurulmaz).
        for r in c.execute(
                "SELECT g.no, o.tur, o.govde FROM olay o JOIN gorev g ON g.id = o.gorev_id "
                "WHERE g.proje_id = ? AND o.tur IN ('rapor_taslak', 'ajan_sohbet') AND g.no IN (%s) "
                "ORDER BY o.rowid" % ",".join("?" * len(nolar)), (ofis.proje_id, *nolar)):
            metin = (r["govde"] or "").strip()
            if r["tur"] == "rapor_taslak":
                out[r["no"]] = ("lider", metin)
            elif (out.get(r["no"]) or ("", ""))[0] != "lider":
                out[r["no"]] = ("ajan", metin)
    return {n: m for n, (_k, m) in out.items()}


def _duraklatilmis(ofis, nolar) -> set:
    if not nolar:
        return set()
    with ofis.db.baglanti() as c:
        return {r[0] for r in c.execute(
            "SELECT no FROM gorev WHERE proje_id = ? AND duraklatildi != '' AND no IN (%s)"
            % ",".join("?" * len(nolar)), (ofis.proje_id, *nolar))}


#: Ofisin ARA notlari -- patrona SONUC degildir (kesinti, dagitim, devam).
_OFIS_NOTLARI = ("Ofis kapanmadan önce", "İş tamamlandı (ofisin özeti", "Bu işi ekibe dağıtıyorum",
                 "Kadro kuruldu, iş başlıyor")


def _ofis_notu_mu(metin: str) -> bool:
    return str(metin or "").lstrip().startswith(_OFIS_NOTLARI)


#: Gelistirme teslim durumlarinin patrona gorunen adi.
KURULUM_ADI = {"sinaniyor": "kopyada sınanıyor", "sinama_kaldi": "sınama geçmedi — kurulmadı",
               "cakisti": "son kodla çakıştı — kurulmadı",
               "kart": "kurulum onayını bekliyor", "kuruldu": "ofise kuruldu",
               "reddedildi": "reddedildi — kurulmadı", "geri_alindi": "geri alındı"}


def _kurulum_durumlari(ofis) -> dict:
    """{is_no: okunur kurulum durumu} -- yalniz gelistirme teslimi olan isler."""
    import json as _json
    out = {}
    try:
        with ofis.db.baglanti() as c:
            for (deger,) in c.execute("SELECT deger FROM ayar WHERE proje_id = ? AND anahtar LIKE ?",
                                      (ofis.proje_id, "gelistirme_teslim:%")):
                try:
                    d = _json.loads(deger or "{}")
                except ValueError:
                    continue
                if d.get("no") is not None and d.get("durum"):
                    out[d["no"]] = KURULUM_ADI.get(d["durum"], d["durum"])
    except Exception:                            # noqa: BLE001 -- olcemezsek yazmayiz
        return {}
    return out


def _ajan_takimlari(ofis) -> dict:
    """{ajan_adi: takim adi} (arsivdekiler dahil degil; bilinmezse yok)."""
    try:
        with ofis.db.baglanti() as c:
            return {r[0]: r[1] for r in c.execute(
                "SELECT a.ad, k.ad FROM ajan a JOIN kanat k ON k.id = a.kanat_id "
                "WHERE a.proje_id = ?", (ofis.proje_id,))}
    except Exception:                            # noqa: BLE001
        return {}


def _sahip_modelleri(ofis, kartlar_) -> dict:
    """{(is_no, sahip_ajan): okunur model adi}. Yalniz `olay.ajan_ad == sahip`
    olan tur_ozeti'leri; modeli bos (olculmemis) turlar atlanir, sonuncusu kazanir."""
    import json as _json
    from .guncelleme import model_adi as _model_adi
    cift = {(i.get("no"), i.get("sahip")) for k in kartlar_ for i in (k.get("isler") or [])
            if i.get("no") and i.get("sahip")}
    cikti = {}
    if not cift:
        return cikti
    nolar = sorted({n for n, _ in cift})
    with ofis.db.baglanti() as c:
        for no, ajan, govde in c.execute(
                "SELECT g.no, o.ajan_ad, o.govde FROM olay o JOIN gorev g ON g.id = o.gorev_id "
                "WHERE g.proje_id = ? AND o.tur = 'tur_ozeti' AND g.no IN (%s) ORDER BY o.rowid"
                % ",".join("?" * len(nolar)), (ofis.proje_id, *nolar)):
            if (no, ajan) not in cift:
                continue
            try:
                d = _json.loads(govde)
            except (ValueError, TypeError):
                continue
            if not isinstance(d, dict):
                continue
            ad = _model_adi(d.get("motor") or "", d.get("model") or "")
            # Takma ad (`sonnet`) cozulmemis: surum OLCULMEMIS -> kartta yalniz ajan adi.
            if ad and "olculmedi" not in ad:
                cikti[(no, ajan)] = ad
    return cikti


def kartlar(ofis, *, kanat_id=None, adet: int = 120, kosuyor: bool = False) -> list:
    """Sohbetin kartlari, eskiden yeniye. Her kart:

    `{id, tip, an, metin, ekler, kime, durum, canli, sonuc, sonuc_ekler, isler,
      sure_sn, kabul, ayrinti, akis, sira_no, sebep}`
    `tip`: istek (lidere) · soru_ajana (@ajan soru) · soru_sana (ajan sana
    soruyor, istege bagli degil) · sirada · iletilemedi.
    """
    ogeler = akis(ofis, kanat_id=kanat_id, adet=adet)
    kartlar_, istek_kart, id_kart = [], {}, {}
    for x in ogeler:
        t = x["tur"]
        if t == "sohbet":
            k = {"id": x["id"], "tip": "istek", "an": x["an"], "metin": x["metin"],
                 "ekler": x.get("ekler") or [], "kime": x["kime"],
                 "bekliyor": x["bekliyor"], "istek_durum": x.get("istek_durum") or {},
                 "akis": x.get("akis") or "", "ayrinti": [], "sonuc": "",
                 "sonuc_ekler": [], "isler": (x.get("istek_durum") or {}).get("isler") or []}
            kartlar_.append(k)
            istek_kart[x["id"]] = k
            id_kart[x["id"]] = k
        elif t == "sirada":
            kartlar_.append({"id": x["id"], "tip": "sirada", "an": x["an"], "metin": x["metin"],
                             "ekler": x.get("ekler") or [], "kime": x["kime"],
                             "durum": "sirada", "sira_no": x.get("sira_no"), "ayrinti": []})
        elif t == "iletilemedi":
            kartlar_.append({"id": x["id"], "tip": "iletilemedi", "an": x["an"],
                             "metin": x["metin"], "ekler": x.get("ekler") or [],
                             "durum": "iletilemedi", "sebep": x.get("sebep") or "",
                             "ayrinti": []})
        elif t == "soru" and x["kimden"] == "insan":
            k = {"id": x["id"], "tip": "soru_ajana", "an": x["an"], "metin": x["metin"],
                 "ekler": x.get("ekler") or [], "kime": x["kime"], "bekliyor": x["bekliyor"],
                 "ayrinti": [], "sonuc": "", "sonuc_ekler": [], "isler": [],
                 "gorev_no": x.get("gorev_no")}
            kartlar_.append(k)
            id_kart[x["id"]] = k
        elif t == "cevap":
            k = id_kart.get(x["id"])
            if k is not None:
                k["cevap"] = x["metin"]
                k["cevap_ekler"] = x.get("ekler") or []
                k["sure_sn"] = x.get("sure_sn")
                k["kabul"] = x.get("kabul") or ""
                if x.get("isler"):
                    k["isler"] = x["isler"]
        elif t == "soru" and x["kime"] == "insan" and not x.get("istek"):
            if x["bekliyor"]:
                kartlar_.append({"id": x["id"], "tip": "soru_sana", "an": x["an"],
                                 "metin": x["metin"], "kimden": x["kimden"],
                                 "gorev_no": x.get("gorev_no"), "durum": "karar",
                                 "ayrinti": []})
        elif t in _KARTA_GIRMEZ:
            continue
        else:
            k = istek_kart.get(x.get("istek") or "")
            if k is None and x.get("gorev_no"):
                k = next((c for c in istek_kart.values()
                          if any(i.get("no") == x["gorev_no"] for i in c["isler"])), None)
            if k is not None:
                k["ayrinti"].append(x)
                if t == "bildirim" and x.get("ekler"):
                    # Yalniz SON teslimin dosyalari (eski surumler ayrintida).
                    k.setdefault("_son_ek", {})[x.get("gorev_no") or 0] = list(x["ekler"])
    # ---- durum, canli satir, sonuc
    tum_nolar = sorted({i["no"] for k in kartlar_ for i in (k.get("isler") or []) if i.get("no")})
    taslak = _rapor_taslaklari(ofis, tum_nolar)
    durakli = _duraklatilmis(ofis, tum_nolar)
    bekleyen_soru = {}
    for s in ofis.postane.insan_bekleyenler():
        if s.get("gorev_id"):
            bekleyen_soru.setdefault(s["gorev_id"], []).append(s["id"])
    gid = {}
    if tum_nolar:
        with ofis.db.baglanti() as c:
            gid = {r[0]: r[1] for r in c.execute(
                "SELECT no, id FROM gorev WHERE proje_id = ? AND no IN (%s)"
                % ",".join("?" * len(tum_nolar)), (ofis.proje_id, *tum_nolar))}
    bekleyen_onay = {o.get("gorev_no") for o in ofis.postane.bekleyen_onaylar() if o.get("gorev_no")}
    # ISI KIM YAPTI: kesintide is birakilinca `sahip` bosalir (09.10 canli);
    # defterdeki SON sahiplenme kaydi yazilir.
    if tum_nolar:
        with ofis.db.baglanti() as c:
            son_sahip = {r[0]: r[1] for r in c.execute(
                "SELECT g.no, o.ajan_ad FROM olay o JOIN gorev g ON g.id = o.gorev_id "
                "WHERE g.proje_id = ? AND o.tur = 'sahiplenildi' AND o.ajan_ad != '' "
                "AND g.no IN (%s) ORDER BY o.rowid" % ",".join("?" * len(tum_nolar)),
                (ofis.proje_id, *tum_nolar))}
        for _k in kartlar_:
            for _i in _k.get("isler") or []:
                if not _i.get("sahip") and son_sahip.get(_i.get("no")):
                    _i["sahip"] = son_sahip[_i["no"]]
    # MODEL: isin SAHIBININ (gorev sahibi ajan) KENDI turlarinda OLCULEN model.
    # Liderin inceleme turu ve baska ajanlarin turlari SAYILMAZ; birden cok
    # olculmus tur varsa en sonuncusu. Olculmediyse bos (yalniz ajan adi).
    model_sec = _sahip_modelleri(ofis, kartlar_)
    for _k in kartlar_:
        for _i in _k.get("isler") or []:
            _i["model_ad"] = model_sec.get((_i.get("no"), _i.get("sahip") or "")) or ""
    # KURULUM DURUMU (09.10 F1 canli): gelistirme takiminin isi "Bitti" gorunuyordu
    # ama degisiklik reddedilmis/kurulmamisti. Teslim kaydi olan iste yazilir.
    kurulum = _kurulum_durumlari(ofis)
    for _k in kartlar_:
        for _i in _k.get("isler") or []:
            if kurulum.get(_i.get("no")):
                _i["kurulum"] = kurulum[_i["no"]]
    # TAKIM ADI (09.10, patron: "her takimin sohbeti neden ayni?"): Tum Ofis
    # gorunumu butun takimlarin kartlarini birlikte gosterir; kart takimini soyler.
    _takim = _ajan_takimlari(ofis)
    for _k in kartlar_:
        _ad = _k.get("kime") or _k.get("kimden") or ""
        _k["takim"] = _takim.get(_ad, "")
    for k in kartlar_:
        if k["tip"] not in ("istek", "soru_ajana"):
            continue
        isler = k.get("isler") or []
        nolar = [i["no"] for i in isler]
        d = k.pop("istek_durum", {}) or {}
        aktif = d.get("aktif")
        karar = any(n in bekleyen_onay or gid.get(n) in bekleyen_soru for n in nolar)
        acik = [i for i in isler if i.get("durum") not in ("bitti", "iptal")]
        if karar:
            durum = "karar"
        elif any(n in durakli for n in nolar if any(i["no"] == n and i["durum"] not in ("bitti", "iptal") for i in isler)):
            durum = "durdu"
        elif acik:
            durum = "calisiyor"
        elif isler:
            durum = "iptal" if all(i.get("durum") == "iptal" for i in isler) else "bitti"
        elif k.get("cevap"):
            durum = "bitti"
        elif k.get("bekliyor"):
            durum = "dusunuyor" if kosuyor else "cevapsiz"
        else:
            durum = "bitti"
        k["durum"] = durum
        k["canli"] = ({"kim": aktif.get("sahip") or "", "ne": aktif.get("durum") or "",
                       "basladi": aktif.get("basladi") or "", "son": d.get("son") or "",
                       "no": aktif.get("no"),
                       "model_ad": model_sec.get((aktif.get("no"), aktif.get("sahip") or "")) or ""} if aktif and durum in ("calisiyor", "karar", "durdu") else None)
        k["adim"] = d.get("adim") or 0
        k["adimlar"] = d.get("adimlar") or []
        # SONUC: is varsa liderin PATRONA taslaklari (temiz, sonuc ilk cumlede);
        # yoksa cevabin kendisi. Ara notu ("ekibe dagitiyorum") sonuc degildir.
        parca = [taslak[n] for n in nolar if taslak.get(n)]
        if parca and not acik:
            k["sonuc"] = "\n\n".join(parca)
        elif k.get("cevap") and not acik and not _ofis_notu_mu(k["cevap"]):
            k["sonuc"] = k["cevap"]
        for _l in (k.pop("_son_ek", {}) or {}).values():
            for e in _l:
                if e not in k["sonuc_ekler"]:
                    k["sonuc_ekler"].append(e)
        for e in k.pop("cevap_ekler", []) or []:
            if e not in k["sonuc_ekler"]:
                k["sonuc_ekler"].append(e)
        if k["sonuc"]:
            from . import ekler as _ek
            k["sonuc"], _yeni = _ek.ayikla(k["sonuc"])
            for e in _yeni:
                if e not in k["sonuc_ekler"]:
                    k["sonuc_ekler"].append(e)
        k.pop("cevap", None)
    return kartlar_
