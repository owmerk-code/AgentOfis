# -*- coding: utf-8 -*-
"""HESAP -- motorun KIMIN adina konustugu.

Kullanici (20.09.2026): *"abonelik hesaplari degisebilir veya api ile de
ai modelleri kullaniriz; agent sistemimizi ona gore yap, ilerde COKLU
HESAP bile olabilir."*

Bugune kadar **motor = adaptor** idi ve kimlik SABITTI: claude CLI'in
kendi oturumu, codex'in kendi evi. Yani "iki Claude hesabi", "abonelik
ile API yan yana" ya da "is hesabi / kisisel hesap" ifade edilemiyordu.

Ayrim su:

    MOTOR  -> NASIL konusulacak (CLI sozlesmesi, akis bicimi, bayraklar)
    HESAP  -> KIMIN adina konusulacak (kimlik, plan, tavan)

Ayni motorun iki hesabi olabilir. Ayni hesap abonelik ya da API olabilir.

## Nobet zinciri bundan sonra HESAP uzerinde yurur

Zincir `(motor, model)` ciftleriydi; dogrusu `(hesap, model)`. Zaten
istenen buydu -- *"limit gelince otekine gec"* -- ve "iki abonelik arasi
gecis" bunun yalnizca OZEL BIR HALI. Genel hali: birden cok hesap, her
biri kendi plani ve kendi tavaniyla, sirayla.

## Mekanizma OLCULDU, tahmin edilmedi

| motor | yalitim | nasil |
|---|---|---|
| codex | ev dizini | `CODEX_HOME` (ofis zaten kendi evini kullaniyor) |
| claude | API anahtari | `ANTHROPIC_API_KEY` ya da `--settings` icinde `apiKeyHelper` |

claude CLI'in kendi yardimi soyluyor: *"Anthropic auth is strictly
ANTHROPIC_API_KEY or apiKeyHelper via --settings (OAuth and keychain are
never read)"* -- yani API yolu acikca destekleniyor. Abonelik yolu ise
makinenin oturumuna bagli: **bir makinede tek abonelik claude hesabi.**
Bu bir SINIR ve yazili olmasi gerekiyor; kesfedilmesi degil.

## ANAHTAR BURAYA YAZILMAZ

`ortam` bir JSON'dur ama **degeri degil REFERANSI** tutar:

    {"ANTHROPIC_API_KEY": "@gizli:ANTHROPIC_API_KEY_IS"}

Gercek deger tur aninda `ofis/gizli.py`den cozulur -- o depo proje
kokunun DISINDA (`~/.agentofis/gizli.env`), cunku ajanlarin
`Bash(cat *)` izni var. Anahtari veritabanina yazsaydik ajan onu
okuyabilir ve terminal kaniti olarak tahtaya dusurebilirdi.

Referans cozulemezse hesap **KULLANILAMAZ sayilir** ve sebebi soylenir.
Sessizce bos bir anahtarla kosmak, "yanlis hesapla kostu" demektir ve
bunu ancak fatura ya da ret soylerdi.
"""

from __future__ import annotations

import json
import os
import uuid

from .db import simdi

TURLER = ("abonelik", "api")

#: Referans oneki. Duz metin bir deger de kabul edilir (ornegin
#: `CODEX_HOME` bir yoldur, sir degildir) -- yalniz bu onekli olanlar
#: gizli depodan cozulur.
GIZLI_ONEK = "@gizli:"


class HesapHatasi(Exception):
    pass


def ekle(db, proje_id: str, ad: str, motor: str, *, tur: str = "abonelik",
         plan: str = "", ortam: dict = None, sira: int = 100,
         not_: str = "") -> dict:
    """Yeni hesap. Ad proje genelinde tekildir ve geri donmez.

    Ad tekilligi gorevlerdeki ve ajanlardaki kuralla ayni sebebe
    dayaniyor: gecmis okunabilir kalmali. "su is hangi hesapta kosmus"
    sorusu alti ay sonra da cevaplanabilmeli.
    """
    ad = (ad or "").strip().lower()
    if not ad:
        raise HesapHatasi("Hesap adi bos birakilamaz.")
    if tur not in TURLER:
        raise HesapHatasi(f"Tur {TURLER} icinden olmali, {tur!r} degil.")

    from .motor import kayitli_motorlar
    if motor not in kayitli_motorlar():
        raise HesapHatasi(
            f"Bilinmeyen motor: {motor}. "
            f"Secenekler: {', '.join(kayitli_motorlar())}")

    with db.baglanti() as conn:
        var = conn.execute(
            "SELECT ad FROM hesap WHERE proje_id = ? AND ad = ?",
            (proje_id, ad)).fetchone()
        if var:
            raise HesapHatasi(f"{ad!r} adli hesap zaten var.")
        an = simdi()
        conn.execute(
            "INSERT INTO hesap (id, proje_id, ad, motor, tur, plan, ortam, "
            "sira, aktif, not_, olusturuldu, guncellendi) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
            (uuid.uuid4().hex, proje_id, ad, motor, tur, plan,
             json.dumps(ortam or {}, ensure_ascii=False), int(sira),
             not_, an, an))
    db.olay_yaz(proje_id, "hesap_eklendi", f"{ad} ({motor}/{tur})",
                ajan_ad="insan")
    return hesap(db, proje_id, ad)


def hesap(db, proje_id: str, ad: str) -> dict:
    with db.baglanti() as conn:
        row = conn.execute(
            "SELECT * FROM hesap WHERE proje_id = ? AND ad = ?",
            (proje_id, ad)).fetchone()
    if not row:
        raise HesapHatasi(f"Hesap bulunamadi: {ad!r}")
    d = dict(row)
    d["ortam"] = json.loads(d["ortam"] or "{}")
    d["aktif"] = bool(d["aktif"])
    return d


def liste(db, proje_id: str, *, motor: str = None,
          yalniz_aktif: bool = False) -> list:
    """Hesaplar, ZINCIR SIRASIYLA."""
    sorgu = "SELECT * FROM hesap WHERE proje_id = ?"
    args = [proje_id]
    if motor:
        sorgu += " AND motor = ?"
        args.append(motor)
    if yalniz_aktif:
        sorgu += " AND aktif = 1"
    sorgu += " ORDER BY sira, ad"
    with db.baglanti() as conn:
        rows = conn.execute(sorgu, args).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["ortam"] = json.loads(d["ortam"] or "{}")
        d["aktif"] = bool(d["aktif"])
        out.append(d)
    return out


def ayarla(db, proje_id: str, ad: str, *, plan: str = None,
           sira: int = None, aktif: bool = None, ortam: dict = None,
           not_: str = None) -> dict:
    """Hesabi degistirir. AD ve MOTOR degismez.

    Ad degismez cunku gecmis ona bagli; motor degismez cunku motor
    degisirse o artik baska bir hesaptir.
    """
    mevcut = hesap(db, proje_id, ad)
    with db.baglanti() as conn:
        conn.execute(
            "UPDATE hesap SET plan = ?, sira = ?, aktif = ?, ortam = ?, "
            "not_ = ?, guncellendi = ? WHERE proje_id = ? AND ad = ?",
            (mevcut["plan"] if plan is None else plan,
             mevcut["sira"] if sira is None else int(sira),
             int(mevcut["aktif"] if aktif is None else bool(aktif)),
             json.dumps(mevcut["ortam"] if ortam is None else ortam,
                        ensure_ascii=False),
             mevcut["not_"] if not_ is None else not_,
             simdi(), proje_id, ad))
    return hesap(db, proje_id, ad)


# -- kimligin COZULMESI -----------------------------------------------------

def ortam_coz(h: dict) -> dict:
    """Hesabin ortam degiskenlerini GERCEK degerlere cevirir.

    `@gizli:ISIM` referanslari `ofis/gizli.py` deposundan okunur.
    Duz metin degerler oldugu gibi gecer (ornegin `CODEX_HOME` bir
    yoldur, sir degildir).

    Cozulemeyen referans **HATA**dir, bos deger degil: bos bir
    `ANTHROPIC_API_KEY` ile kosmak, hesabin kimliginin sessizce
    kaybolmasi demektir -- tur ya baska bir kimlikle kosar ya
    anlasilmaz bir hatayla duser.
    """
    from . import gizli

    cozulen = {}
    eksik = []
    for anahtar, deger in (h.get("ortam") or {}).items():
        metin = str(deger)
        if metin.startswith(GIZLI_ONEK):
            isim = metin[len(GIZLI_ONEK):].strip()
            gercek = gizli.oku(isim) if hasattr(gizli, "oku") else ""
            if not gercek:
                eksik.append(isim)
                continue
            cozulen[anahtar] = gercek
        else:
            cozulen[anahtar] = os.path.expanduser(metin)
    if eksik:
        raise HesapHatasi(
            f"'{h['ad']}' hesabinin anahtari gizli deposunda YOK: "
            f"{', '.join(eksik)}.\n"
            "Ekle:  python -m ofis.kabuk anahtar ekle <ISIM>\n"
            "Bos anahtarla kosmak, kimligin sessizce kaybolmasi demektir.")
    return cozulen


def kullanilabilir_mi(h: dict) -> dict:
    """Bu hesap SIMDI kullanilabilir mi. Olcer, tahmin etmez.

    Donus: `{"olur", "sebep"}`.
    """
    if not h.get("aktif"):
        return {"olur": False, "sebep": "hesap kapali (aktif=0)"}
    try:
        coz = ortam_coz(h)
    except HesapHatasi as exc:
        return {"olur": False, "sebep": str(exc).splitlines()[0]}
    from .motor import motor_ac
    try:
        m = motor_ac(h["motor"])
    except Exception as exc:
        return {"olur": False, "sebep": f"motor acilamadi: {exc}"}
    # Abonelik hesabinda CLI'in kendi girisine bakilir; API hesabinda
    # anahtarin varligi yeterli (CLI kurulu olmali ama giris gerekmez).
    # KENDI EVI OLAN CODEX HESABI kendi evinde olculur (22.09.2026).
    # `musait_mi` ofisin VARSAYILAN evine bakar; ikinci bir hesap icin
    # "birinci hesap girisli" cevabi verirdi -- yani girissiz bir hesap
    # HAZIR gorunur, nobet devri aninda "Not logged in" ile duser ve
    # devrin kendisi, tam ihtiyac duyuldugu anda calismazdi. Anahtar
    # var != uretebiliyor dersinin hesap hali.
    if h["tur"] == "abonelik" and h["motor"] == "codex" and coz.get("CODEX_HOME"):
        from .motor.codex import hesap_kimligi, oturum_olu_mu, oturum_olu_metni
        if not getattr(m, "calistirilabilir", ""):
            return {"olur": False, "sebep": "codex CLI kurulu degil"}
        kim = hesap_kimligi(coz["CODEX_HOME"])
        if not kim.get("girisli"):
            return {"olur": False,
                    "sebep": (f"bu evde giris YOK: {coz['CODEX_HOME']} -- "
                              "PowerShell: $env:CODEX_HOME=\"" + coz["CODEX_HOME"]
                              + "\"; codex login")}
        # Giris dosyasi var ama sunucu oturumu oldurmus olabilir
        # (25.09.2026: 401 token_revoked, dosya duruyordu).
        if oturum_olu_mu(coz["CODEX_HOME"]):
            return {"olur": False, "sebep": oturum_olu_metni(coz["CODEX_HOME"])}
        return {"olur": True, "sebep": "", "eposta": kim.get("eposta", ""),
                "plan": kim.get("plan", "")}
    if h["tur"] == "abonelik":
        try:
            # Motor KENDI sebebini soyler (giris yok, oturum dustu, hesap
            # askida -- E16). "kurulu/girisli degil" hangisi oldugunu
            # soylemiyordu; insan neyi duzeltecegini bilemiyordu.
            notu = m.durum_notu()
            if notu:
                return {"olur": False, "sebep": notu}
        except Exception as exc:
            return {"olur": False, "sebep": f"musaitlik olculemedi: {exc}"}
    return {"olur": True, "sebep": ""}


def varsayilan_hesaplar(db, proje_id: str) -> list:
    """Hic hesap tanimlanmamissa: her KURULU motor icin ortuk bir hesap.

    Geriye donuk uyum: hesap kavramindan onceki ofisler calismaya
    devam etsin. Ortuk hesap ortam DEGISKENI KURMAZ -- yani bugunku
    davranisin aynisi: CLI kendi oturumunu kullanir.
    """
    from .motor import musait_motorlar
    out = []
    for i, (ad, var) in enumerate(sorted(musait_motorlar().items())):
        if not var or ad == "sahte":
            continue
        out.append({"id": "", "proje_id": proje_id, "ad": ad, "motor": ad,
                    "tur": "abonelik", "plan": "", "ortam": {},
                    "sira": 100 + i, "aktif": True, "not_": "(ortuk)",
                    "ortuk": True})
    return out


def zincir_hesaplari(db, proje_id: str, motor: str = None) -> list:
    """Nobet zincirinin uzerinde yuruyecegi hesaplar, SIRAYLA.

    Tanimli hesap yoksa ortuk listeye duser -- ofis hesap kurmadan da
    calisir, ama kurunca zincir onlarin uzerinde yurur.
    """
    tanimli = liste(db, proje_id, motor=motor, yalniz_aktif=True)
    if tanimli:
        return tanimli
    hepsi = varsayilan_hesaplar(db, proje_id)
    return [h for h in hepsi if not motor or h["motor"] == motor]
