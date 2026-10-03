# -*- coding: utf-8 -*-
"""AYARLAR -- patronun ofis ayarlari TEK okumada, yazma IZINLI listeden.

Kullanici (02.10.2026): *"ayarlara tiklayinca ne gorunecek, ne gorunmeyecek
-- dogru durust sirala."* Ayarlar ust cubukta, ayri panolarda ve yalniz
komut satirinda daginiktI (kademe haritasi, gecis esikleri, liderin
terminal kipi panelde HIC yoktu).

Bu dosya KURAL TASIMAZ: her ayarin kurali kendi evinde (roller, zincir,
koltuk, guncelleme, izin, gorsel, yedek). Burada yalniz (1) hepsini tek
sozlukte toplayan `oku` ve (2) izinli anahtarlari dogrulayip o evdeki
yaziciya ileten `yaz` var. Iki kopya olmasin diye deger burada SAKLANMAZ.

Yazilamayanlar BILEREK yok: para kilidi (yalniz kabuktan, acan kisi neyi
kabul ettigini gorur), her zaman sorulan siniflar (para, silme -- kapatilmaz),
API anahtarlarinin kendisi (hic gosterilmez).
"""

from __future__ import annotations

import json

#: Masaustu bildiriminin olay turleri: anahtar -> (etiket, kapatilabilir mi).
#: Onay ve patrona soru KAPATILAMAZ: kapatilirsa is sessizce patronu bekler
#: ve kimse fark etmez (en pahali hata sinifi: saglikli gorunen durma).
BILDIRIM_TURLERI = {
    "onay": ("Onay bekliyor", False),
    "soru": ("Ajan sana soruyor", False),
    "cevap": ("Lider cevapladı", True),
    "donus": ("Sıradaki işler bitti", True),
    "takildi": ("Bir iş takıldı", True),
    "dustu": ("Bir iş düştü / iletilemedi", True),
    "hafiza": ("Hafıza yazısı durduruldu", True),
    "beceri": ("Ajan bir beceri önerdi", True),
    "zamanli": ("Zamanlanmış iş başladı", True),
    "kesinti": ("Ofis kaldığı yerden sürüyor", True),
}
BILDIRIM_KAPALI = "bildirim_kapali"


class AyarHatasi(ValueError):
    pass


def bildirim_kapalilar(db, proje_id: str) -> set:
    """Patronun kapattigi bildirim turleri (kapatilamayanlar asla girmez)."""
    try:
        v = json.loads(db.ayar_oku(proje_id, BILDIRIM_KAPALI, "[]") or "[]")
    except ValueError:
        return set()
    return {k for k in v if k in BILDIRIM_TURLERI and BILDIRIM_TURLERI[k][1]}


def oku(ofis) -> dict:
    """Ayarlar ekraninin butun verisi. Okunamayan parca SESSIZ kalmaz:
    `hatalar` listesine sebebiyle girer (bos gosterip "yok" demek yanlis
    gosterge olurdu)."""
    from . import roller, zincir, guncelleme, izin, gorsel, yedek, depo
    from .koltuk import Koltuk
    from .motor import tui
    from .orkestra import kabin_izle_acik_mi
    from . import karne
    db, pid = ofis.db, ofis.proje_id
    hatalar = []
    kapali = bildirim_kapalilar(db, pid)
    out = {
        "calisma": {
            "ajan_kipi": db.ayar_oku(pid, Koltuk.TERMINAL_KIPI, "arka") or "arka",
            "lider_kipi": db.ayar_oku(pid, tui.LIDER_KIP_AYARI, "arka") or "arka",
            "efor": roller.efor_modu(db, pid),
            "efor_modlari": list(roller.EFOR_MODLARI),
            "kabin_izle": kabin_izle_acik_mi(db, pid),
            # KARNE (03.10.2026): isin motorunu ofis tecrubesiyle secer.
            "motor_secimi": "karne" if karne.secim_acik_mi(db, pid) else "ajan",
            "capraz_inceleme": karne.capraz_acik_mi(db, pid),
            "karne": karne.ozet()["motorlar"],
        },
        "bildirim": {
            "turler": [{"anahtar": k, "etiket": e, "kapatilabilir": kp, "acik": k not in kapali}
                       for k, (e, kp) in BILDIRIM_TURLERI.items()],
        },
        "modeller": {
            "kademe": roller.kademe_haritasi(db, pid),
            "kademeler": list(roller.KADEMELER),
            "onceden_gecis": (db.ayar_oku(pid, "onceden_gecis", "acik") or "acik") != "kapali",
            "esikler": {},
            "guncelleme_otomatik": guncelleme.otomatik_mi(db, pid),
            "guncelleme_gecmis": guncelleme.gecmis(db, pid)[-10:][::-1],
        },
        "guvenlik": {
            "kalici_izinler": [{"id": i["id"], "desen": i["desen"], "veren": i.get("veren", ""),
                                "olusturuldu": i.get("olusturuldu", "")}
                               for i in izin.liste(db, pid)],
            "izin_verilebilir": izin.IZIN_VERILEBILIR,
            "her_zaman_sorulur": izin.HER_ZAMAN_SORULUR,
            "para_kilitli": gorsel.ucretsiz_sadece_mi(),
            "hafiza_reddi": [],
        },
        "yedek": {},
        "takimlar": [],
        "hatalar": hatalar,
    }
    from . import takim as _takim
    ajanlar = ofis.kadro.liste()
    for k in _takim.kanatlar(ofis):
        uyeler = [a for a in ajanlar if a.get("kanat_id") == k["id"]]
        out["takimlar"].append({
            "id": k["id"], "ad": k["ad"],
            "lider": next((a["ad"] for a in uyeler if a.get("lider_mi")), ""),
            "ajanlar": [{"ad": a["ad"], "meslek": a.get("meslek", ""),
                         "motor": a.get("motor", ""), "klasor": a.get("klasor", "")}
                        for a in uyeler],
        })
    for rol in ("isci", "lider"):
        esik, bozuk = zincir.gecis_esikleri(db, pid, rol)
        out["modeller"]["esikler"][rol] = esik or dict(zincir.ONCEDEN_GECIS_ESIKLERI[rol])
        if bozuk:
            hatalar.append(f"bozuk esik ayari: {', '.join(bozuk)}")
    with db.baglanti() as c:
        out["guvenlik"]["hafiza_reddi"] = [
            {"an": r["olusturuldu"], "kim": r["ajan_ad"], "metin": r["govde"]}
            for r in c.execute("SELECT olusturuldu, ajan_ad, govde FROM olay WHERE proje_id = ? "
                               "AND tur = 'hafiza_reddi' ORDER BY rowid DESC LIMIT 20", (pid,))]
    try:
        y = yedek.ayar_oku()
        out["yedek"]["son"] = y.get("son", "")
        out["yedek"]["hedefler"] = y.get("hedefler", [])
        saat = yedek.son_yedek_saat()
        out["yedek"]["son_saat"] = None if saat == float("inf") else round(saat, 1)
    except Exception as exc:                 # noqa: BLE001 -- sebebiyle gosterilir
        hatalar.append(f"yedek ayari okunamadi: {exc}")
    try:
        d = depo.ayar_oku()
        out["yedek"]["github"] = {"uzak": d.get("uzak", ""), "son": d.get("son", ""),
                                  "acik": bool(d.get("acik", True))}
    except Exception as exc:                 # noqa: BLE001
        hatalar.append(f"GitHub yedek ayari okunamadi: {exc}")
    return out


def yaz(ofis, anahtar: str, deger) -> None:
    """Izinli anahtari dogrular ve KURALIN evindeki yaziciya iletir.

    Her degisiklik olay olur (kim neyi ne zaman degistirdi): ayar degisikligi
    bir karardir ve sonradan "bu neden boyle" sorusu cevapsiz kalmamali.
    """
    from . import roller, zincir, guncelleme
    from .koltuk import Koltuk
    from .motor import tui
    from .orkestra import KABIN_IZLE_ANAHTARI
    from . import karne
    db, pid = ofis.db, ofis.proje_id
    if anahtar in ("ajan_kipi", "lider_kipi"):
        if deger not in ("arka", "gercek"):
            raise AyarHatasi("Kip 'arka' ya da 'gercek' olmali.")
        if deger == "gercek":
            from . import terminal as _tr
            if _tr.pty_durumu():
                raise AyarHatasi(_tr.pty_durumu())
        db.ayar_yaz(pid, Koltuk.TERMINAL_KIPI if anahtar == "ajan_kipi"
                    else tui.LIDER_KIP_AYARI, deger)
    elif anahtar == "efor":
        try:
            roller.efor_modu_yaz(db, pid, str(deger))
        except roller.RolHatasi as exc:
            raise AyarHatasi(str(exc))
    elif anahtar == "motor_secimi":
        if deger not in ("karne", "ajan"):
            raise AyarHatasi("Motor secimi 'karne' ya da 'ajan' olmali.")
        db.ayar_yaz(pid, karne.AYAR, deger)
    elif anahtar == "capraz_inceleme":
        db.ayar_yaz(pid, karne.CAPRAZ_AYAR, "acik" if deger else "kapali")
    elif anahtar == "kabin_izle":
        db.ayar_yaz(pid, KABIN_IZLE_ANAHTARI, "acik" if deger else "kapali")
    elif anahtar == "bildirim_turu":
        tur, acik = (deger or {}).get("tur"), bool((deger or {}).get("acik"))
        if tur not in BILDIRIM_TURLERI:
            raise AyarHatasi(f"Bilinmeyen bildirim turu: {tur!r}")
        if not BILDIRIM_TURLERI[tur][1] and not acik:
            raise AyarHatasi(f"'{BILDIRIM_TURLERI[tur][0]}' kapatilamaz: is seni bekler ve "
                             "bildirim gelmezse sessizce durur.")
        k = bildirim_kapalilar(db, pid)
        (k.discard if acik else k.add)(tur)
        db.ayar_yaz(pid, BILDIRIM_KAPALI, json.dumps(sorted(k)))
    elif anahtar == "kademe":
        d = deger or {}
        try:
            roller.kademe_yaz(db, pid, str(d.get("motor", "")), str(d.get("kademe", "")),
                              str(d.get("model", "")))
        except roller.RolHatasi as exc:
            raise AyarHatasi(str(exc))
    elif anahtar == "esik":
        d = deger or {}
        rol, pencere = d.get("rol"), d.get("pencere")
        if rol not in zincir.ONCEDEN_GECIS_ESIKLERI or pencere not in zincir.PENCERE_ETIKETI:
            raise AyarHatasi("Esik icin rol (isci/lider) ve pencere (5s/7g) gerekli.")
        try:
            sayi = float(d.get("deger"))
        except (TypeError, ValueError):
            raise AyarHatasi("Esik bir sayi olmali (ornek 0.8 = %80).")
        if not 0.5 <= sayi <= 1:
            raise AyarHatasi("Esik %50 ile %100 arasinda olmali.")
        db.ayar_yaz(pid, f"gecis_esigi:{rol}:{pencere}", f"{sayi:.2f}")
    elif anahtar == "onceden_gecis":
        db.ayar_yaz(pid, "onceden_gecis", "acik" if deger else "kapali")
    elif anahtar == "guncelleme_otomatik":
        guncelleme.otomatik_ayarla(db, pid, bool(deger))
    else:
        raise AyarHatasi(f"Bu ayar panelden degistirilemez: {anahtar!r}")
    db.olay_yaz(pid, "ayar", f"{anahtar} = {json.dumps(deger, ensure_ascii=False)[:200]} "
                "(Ayarlar ekranindan)", ajan_ad="insan")
