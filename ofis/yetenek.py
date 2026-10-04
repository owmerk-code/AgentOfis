# -*- coding: utf-8 -*-
"""YETENEK -- ofis NEYI YAPABILIR, tek yerde ve OLCULMUS.

Kullanici: *"baska araclarda, eklentilerde, API'lerde hesaplar
ekleyebilmeli cikarabilmeliyim; panelimizde bunlari yonetebilir,
gorebilir, silip ekleyebilirim diye dusunuyorum."*

Dogru istek, ama bes ayri kayit defterimiz vardi ve hicbiri otekini
gormuyordu: `hesap` · `gizli` · `baglayici` · motor defteri · `roller`.
Insanin *"bugun ne yapabiliyorum"* sorusunu cevaplayan tek bir yer yoktu.

## SAHIPLIK AYRIMI -- bu dosyanin ana fikri

Her yetenek iki sinifa ayrilir ve **ikisi ayni sekilde gosterilmez**:

| Sinif | Ornek | Ofis ne yapabilir |
|---|---|---|
| **Ofisin SAHIP oldugu** | `hesap` satirlari · kasadaki anahtarlar · roller | ekler, siler, degistirir |
| **Ofisin sahip OLMADIGI** | claude.ai baglayicilari · CLI kurulumlari · OAuth | yalnizca **OLCER** ve komutu SOYLER |

Bu ayrim kozmetik degil. Panelde *"Higgsfield'i Bagla"* dugmesi koyup
arkada hicbir sey yapamasaydik, **yanlis gosteren bir gosterge** olurdu
-- bu projenin en pahali hata sinifi. Rakipten almaya karar verdigimiz
sey de tam buydu: *entegrasyon koprusunun UC DURUMU (bagli / izin dar /
bagli degil) ve ASLA UYDURMAZ.*

## `saglik.py` ile farki

`saglik` sorar: *"su an tikanan bir sey var mi?"* -- anlik, ise bakar.
`yetenek` sorar: *"bu ofis neyi yapabilir?"* -- duragan, donanima bakar.

Ikisini birlestirseydik, her gun degisen bir sey (tikanan is) ile
ayda bir degisen bir sey (kurulu CLI) ayni ekrani paylasirdi ve insan
ikisine de bakmayi birakirdi.

## KURALLAR (saglik.py'den devralindi)

- **UYDURMAZ.** Olcemedigine "iyi" demez, `bilinmiyor` der.
- **Bir olcum patlarsa SESSIZ kalmaz** -- calismayan bir olcum, "sorun
  yok" demekle aynidir.
- **Her eksik CAREYI soyler.** Teshis koyup care soylemeyen gosterge,
  insani bir kez daha dusunmeye zorlar.
- **SIR GOSTERMEZ.** Anahtarlar yalnizca parmak iziyle gorunur
  (`gizli.liste()` zaten deger dondurmez).
"""

from __future__ import annotations

import shutil
import subprocess

from .surec import PENCERE_YOK

#: Durumlar. Uc hal + "olculemedi" -- dorduncusu olmadan, calismayan
#: bir olcum "yok" gibi gorunur ve insan var olmayan bir sorunu kovalar.
HAZIR = "hazir"
DAR = "dar"
YOK = "yok"
BILINMIYOR = "bilinmiyor"

#: Ofisin kullandigi komut satiri araclari ve NE ICIN gerektigi.
#: "Kurulu mu" sorusunu tahmin etmiyoruz, `shutil.which` ile olcuyoruz.
CLILER = (
    ("claude", "Claude motoru", True),
    ("codex", "Codex motoru", True),
    ("git", "surum kontrolu (devops · backend)", True),
    ("gh", "GitHub islemleri (devops rolu)", False),
    ("node", "JS/TS isleri (arayuz · kalite)", False),
    ("npx", "Playwright tarayicisi ve JS araclari", True),
    ("docker", "kapsayici isleri (devops)", False),
    ("ffmpeg", "video KURGU (video rolu URETIR ama kurgulayamaz)", False),
)


def _satir(ad, durum, not_="", care=""):
    return {"ad": ad, "durum": durum, "not": not_, "care": care}


def _grup(ad, sahiplik, satirlar):
    """`sahiplik`: 'ofis' (ekleyip silebiliriz) ya da 'dis' (yalniz olceriz)."""
    return {"ad": ad, "sahiplik": sahiplik, "satirlar": satirlar}


def _cliler() -> list:
    out = []
    for ad, ne, zorunlu in CLILER:
        yol = shutil.which(ad)
        if yol:
            surum = ""
            try:
                p = subprocess.run([ad, "--version"], capture_output=True,
                                   text=True, timeout=15, shell=True,
                                   stdin=subprocess.DEVNULL, creationflags=PENCERE_YOK,
                                   encoding="utf-8", errors="replace")
                surum = (p.stdout or p.stderr or "").strip().splitlines()[:1]
                surum = surum[0][:40] if surum else ""
            except Exception:
                surum = "(surum okunamadi)"
            out.append(_satir(ad, HAZIR, f"{ne} · {surum}"))
        else:
            out.append(_satir(
                ad, YOK if zorunlu else DAR, ne,
                f"`{ad}` kurulu degil. Gerekirse kurulmali; ofis kuramaz."))
    return out


def _motorlar() -> list:
    """Kurulu mu VE kullanilabilir mi -- motorun KENDI teshisiyle (E16).

    Once yalniz kurulu olup olmadigi soruluyordu: girissiz ya da oturumu
    sunucuda dusmus bir motor "hazir" gorunuyordu. Kurulu ama
    kullanilamayan motor DAR'dir (insan eylemi -- giris -- ister).
    """
    from .motor import motor_ac, musait_motorlar
    out = []
    for ad, musait in sorted(musait_motorlar().items()):
        if musait:
            out.append(_satir(ad, HAZIR, "motor adaptoru"))
            continue
        try:
            m = motor_ac(ad)
            kurulu = bool(getattr(m, "calistirilabilir", True))
            notu = m.durum_notu()
        except Exception as exc:          # noqa: BLE001 -- gosterge dusmesin
            kurulu, notu = False, f"acilamadi: {exc}"
        out.append(_satir(ad, DAR if kurulu else YOK, "motor adaptoru",
                          notu or f"`{ad}` CLI'i kurulu degil."))
    return out


def _hesaplar(db, proje_id) -> list:
    from . import hesap
    satirlar = []
    kayitli = hesap.liste(db, proje_id)
    if not kayitli:
        # ORTUK hesap: ofis hesap tanimlanmadan da calisir. Bunu "hesap
        # yok" diye gostermek yanlis alarm olurdu.
        return [_satir("(ortuk)", HAZIR,
                       "hicbir hesap tanimlanmamis -- her kurulu motor "
                       "kendi oturumuyla kosuyor (bugunku davranis)",
                       "Coklu hesap icin: `kabuk hesap ekle`")]
    for h in kayitli:
        # Anahtar `olur` (hesap.kullanilabilir_mi). 27.09.2026'ya kadar
        # burada `kullanilabilir` okunuyordu -- olmayan anahtar: tanimli
        # HER hesap, saglam olsa bile hep "dar" gorunuyordu.
        k = hesap.kullanilabilir_mi(h)
        satirlar.append(_satir(
            h["ad"], HAZIR if k.get("olur") else DAR,
            f"{h['motor']} · {h['tur']}" + (f" · {h['plan']}" if h.get("plan") else ""),
            "" if k.get("olur") else k.get("sebep", "")))
    return satirlar


def _anahtarlar() -> list:
    """SIR GOSTERMEZ -- `gizli.liste()` zaten yalnizca parmak izi doner."""
    from . import gizli
    kayit = gizli.liste()
    if not kayit:
        return [_satir("(kasa bos)", DAR, "hicbir API anahtari kurulu degil",
                       "`kabuk anahtar ekle <AD>`")]
    return [_satir(k["ad"], HAZIR, k.get("parmak_izi", "")) for k in kayit]


def _uretici_grubu(modul, etiket) -> list:
    out = []
    for ad, h in modul.musait_ureticiler().items():
        ek = ""
        if h.get("saniye_basi_usd"):
            ek = f" · ${h['saniye_basi_usd']}/sn"
        elif h.get("ucretli") is False:
            ek = " · ucretsiz kota"
        # ANAHTAR VAR != URETEBILIYOR.
        # Olculdu (21.09.2026): gunluk kota doluyken bu satir HAZIR
        # gosteriyordu. Kotayi burada olcmek bir istek harcar ve tam
        # tuketmeye calistigimiz seyi tuketir; onun yerine son gercek
        # denemenin sonucu HATIRLANIR. Bilinmeyen bir hale "hazir"
        # demek, bu dosyanin varlik sebebine aykiri.
        # PARA KILIDI ACIKSA ucretli uretici KULLANILAMAZ -- anahtari
        # olsa bile. Bunu gostermemek, "hazir" sanip is acmaya davettir.
        if h.get("ucretli") and modul.__name__.endswith(("gorsel", "video")):
            from . import gorsel as _g
            if _g.ucretsiz_sadece_mi():
                out.append(_satir(
                    ad, DAR, etiket + ek,
                    "PARA KILIDI acik: ucretli uretici kullanilmiyor. "
                    "Acmak: `kabuk gorsel para ac`"))
                continue
        not_ = h.get("kota_notu") or ""
        if not h["musait"]:
            durum, care = DAR, h.get("sebep", "")
        elif not_:
            durum, care = BILINMIYOR, (
                f"Son gercek denemede {not_}. Anahtar duruyor ama uretim "
                "su an basarisiz olabilir; ucretsiz kota gunluk yenilenir.")
        else:
            durum, care = HAZIR, ""
        out.append(_satir(ad, durum, etiket + ek, care))
    return out


def _baglayicilar() -> list:
    from . import baglayici
    d = baglayici.durum()
    if not d:
        # Olcemedik. "Yok" demek YANLIS olurdu -- bagli olabilirler.
        return [_satir("(olculemedi)", BILINMIYOR,
                       "`claude mcp list` kosmadi",
                       "Elle dene; sonucu bilmeden is acma.")]
    out = []
    for ad in sorted(d):
        bagli = d[ad]["bagli"]
        out.append(_satir(
            ad, HAZIR if bagli else DAR,
            d[ad].get("url", ""),
            "" if bagli else f'`claude mcp login "claude.ai {ad}"`'))
    return out


def tara(ofis, *, baglayici_dahil: bool = True) -> dict:
    """Butun yetenekleri OLCER.

    `baglayici_dahil=False`: `claude mcp list` saglik denetimi yaptigi
    icin yavas (~15 sn). Hizli bakista atlanabilir -- ama atlandigi
    SOYLENIR, sessizce eksik gosterilmez.
    """
    from . import gorsel, video
    gruplar = []
    olcumler = [
        ("Motorlar", "dis", _motorlar, ()),
        ("Komut satiri araclari", "dis", _cliler, ()),
        ("Hesaplar", "ofis", _hesaplar, (ofis.db, ofis.proje_id)),
        ("Anahtar kasasi", "ofis", _anahtarlar, ()),
        ("Gorsel ureticileri", "ofis", _uretici_grubu, (gorsel, "gorsel")),
        ("Video ureticileri", "ofis", _uretici_grubu, (video, "video")),
    ]
    if baglayici_dahil:
        olcumler.append(("claude.ai baglayicilari", "dis", _baglayicilar, ()))

    for ad, sahiplik, islev, arg in olcumler:
        try:
            gruplar.append(_grup(ad, sahiplik, islev(*arg)))
        except Exception as exc:
            # Bir olcum patlarsa SESSIZ kalinmaz: "bilinmiyor" demek,
            # "sorun yok" demekten farklidir ve tam olarak gerekendir.
            gruplar.append(_grup(ad, sahiplik, [_satir(
                "(olcum patladi)", BILINMIYOR, str(exc)[:160],
                "Bu grubun sonucu BILINMIYOR -- 'sorun yok' demek degil.")]))

    if not baglayici_dahil:
        gruplar.append(_grup("claude.ai baglayicilari", "dis", [_satir(
            "(atlandi)", BILINMIYOR, "hizli tarama istendi",
            "Tam olcum: `kabuk yetenek` (bayraksiz)")]))

    sayim = {}
    for g in gruplar:
        for s in g["satirlar"]:
            sayim[s["durum"]] = sayim.get(s["durum"], 0) + 1
    return {"gruplar": gruplar, "sayim": sayim}
