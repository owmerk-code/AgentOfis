# -*- coding: utf-8 -*-
"""Panel: ofisin yuzu. FastAPI + duz HTML.

Panel bir YUZEYDIR -- degisebilir, degismeli. Bu yuzden burada hicbir
karar verilmez: kilit alinmaz, kanit uretilmez, hukum yazilmaz. Panel
cekirdege SORAR ve cekirdegin cevabini gosterir. Bir kural panelde
uygulaniyorsa yanlis yerdedir; CLI'dan ya da MCP'den girildiginde
atlanabilir demektir.

Tasarimin iki kurali:

1. **Oda bir GOSTERGEDIR, dekor degil.** Ajanin bulundugu oda, durumunu
   SOYLER: masa (calisiyor) · inceleme odasi · bekleme odasi (soru sordu)
   · onay kapisi (insan bekliyor) · mola (bos). Rakipte ofis gorseli bir
   sustur; burada her piksel bir sorgudan gelir. Oda TURETILIR (bkz.
   `_oda`), ayri bir alanda tutulmaz -- tutulsaydi iki kaynak olur ve
   biri bayatlardi.

2. **Uydurmaz.** Bir sayi yoksa bos gosterilir, tahmin edilmez. Rakibin
   dogru yaptigi sey buydu: entegrasyon rozeti "bagli / izin dar / bagli
   degil" der, asla varsaymaz.

Guvenlik: `0.0.0.0` baglanmasi KODDA reddedilir. Telefondan erisim
Tailscale (100.x) uzerinden yapilir; butun arayuzlere acilmak, ev agindaki
her cihaza ofisin tamamini vermek olurdu.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

from . import Ofis, Veritabani
from . import degisim
from . import bellek as _bellek
from .bellek import BellekHatasi
from . import kabin
from .koltuk import durdurma_iste, durdurma_istendi, durdurma_temizle
from .kabin import KabinHatasi
from .db import VARSAYILAN_YOL
from .motor import motor_ac, musait_motorlar
from typing import Optional
from .postane import PostaneHatasi
from .tahta import TahtaHatasi

WEB = Path(__file__).resolve().parent.parent / "web"

#: Panelin bagli olduguna izin verilen adresler. `0.0.0.0` bilincli olarak
#: yok: butun arayuzlere acilmak, ev agindaki her cihaza (ve misafir
#: telefonlara) ofisin tamamini vermek demektir.
GUVENLI_ADRESLER = ("127.0.0.1", "localhost", "::1")

#: Tahtanin bes sutunu. Bekleme BURADA YOK -- bekleme gorevin durumu
#: degil, ajanin turetilmis halidir (bkz. postane.py).
SUTUNLAR = ("bekliyor", "hazir", "calisiyor", "inceleme", "bitti")


#: PANELDEN baslatilan turlarda DOLAR TAVANI YOK (27.09.2026 karari).
#: Kullanici abonelik kullaniyor; dolar bir kavram degil. Kacan bir turu
#: ofisin kendi freni durdurur (`tavan.py`: arac sayisi, cikti hacmi,
#: birikmis jeton) -- her motorda ayni. Hesabin dolmasini saglayicinin
#: kendi yuzdesi ve onceden gecis yonetir. Dolar yalniz API HESABININ
#: aylik sinirinda vardir (`hesap.py`).
PANEL_TUR_TAVANI_USD = None

#: TEK UCUS nobetcisi. Panelden ayni anda iki lider turu baslatilamaz:
#: cift tiklama jetonu ikiye katlar ve iki lider ayni ofiste ayni ise
#: ayri kararlar verir.
_KOSU = {"calisiyor": False, "mesaj": "", "dur": False}

#: Ajana sorulan sorunun AYRI tek-ucus nobetcisi. Danisma salt okunurdur
#: (yazamaz, kilit almaz), halka kosarken de sorulabilir -- ama ayni anda
#: tek soru: cift tiklama iki tur yakardi.
_DANISMA = {"calisiyor": False, "ajan": ""}

#: KUYRUK (01.10.2026): sirayi isleyen ipligi YALNIZ BIRI baslatir.
#: `_KOSU` kontrolu ile isaretlenmesi arasinda iki istek birden girerse iki
#: isci ayni sirayi isler (kayit `sira_al` ile yine tek alinir ama iki
#: lider ayni anda kosar -- tek ucus kurali delinir).
_KUYRUK_KILIDI = threading.Lock()

#: Panel kurulunca baglanir: kabin aciksa CDP adresi, degilse "". Kuyruk
#: isi SONRA kosar; kabinin o anki hali o zaman sorulur.
_KABIN_CDP = {"islev": None}


def _onaylar_giris_ile(onaylar: list) -> list:
    """Giris isteklerine ayristirilmis `giris` alanini ekler (kart onu cizer)."""
    from . import giris as _giris
    out = []
    for o in onaylar:
        v = _giris.ayristir(o)
        if v is not None:
            o = {**o, "giris": {**v, "talimat": _giris.insan_talimati(v)}}
        out.append(o)
    return out


def _durdurulduysa(o, adi: str) -> bool:
    """YUMUSAK DURDURMA: insan istediyse kosan tur BITINCE yenisi baslamaz.

    Sert kesme (surec agacini oldurmek) bilerek YOK: tur ortasinda kesmek
    kaniti ve kilidi yarim birakabilir; olculmeden acilmaz. Durdurma
    SESSIZ OLMAZ -- deftere yazilir, insan neden durdugunu gorur.
    """
    if not _KOSU.get("dur"):
        return False
    o.db.olay_yaz(o.proje_id, "uyari",
                  f"{adi} insanin istegiyle DURDURULDU (kosan tur bitince; "
                  "kismi kanit korunur, yarim is 'surdur' ile devam eder).")
    return True

#: Motor fabrikasi kancasi -- None ise gercek motor. VAR OLMA SEBEBI
#: SINAMA: bu yolun gercekten kostugu, sahte motorla (jeton yakmadan)
#: olculebilmeli. *Kosturmadiysan bilmiyorsun* -- ve gercek motora
#: baglanan bir test, kullanicinin o anki hesabini olcer.
MOTOR_FABRIKASI = None


#: Hesap tablosu onbellegi. Tablo her hesap icin musaitlik sorar (claude
#: `auth status` onbellekli, codex dosya okur); ray her yenilemede ister.
#: Tazele dugmesi onbellegi bosaltir.
_HESAP_ONBELLEK = {}
HESAP_ONBELLEK_SN = 20


def _fabrika_denetle(h: dict) -> dict:
    """SINAMA yolu: gercek motora uzanmadan musaitlik (`MOTOR_FABRIKASI`)."""
    m = MOTOR_FABRIKASI(h["motor"])
    if not m.musait_mi():
        return {"olur": False, "sebep": m.durum_notu() or "motor kurulu degil"}
    return {"olur": True, "sebep": ""}


def _hesap_tablosu(ofis, *, taze: bool = False) -> dict:
    """Ray dugmesi VE hesap panosu ayni cevabi okur (iki okuyucu iki an)."""
    import time
    from . import kullanim as _k
    anahtar = (str(ofis.db.yol), ofis.proje_id)
    kayit = _HESAP_ONBELLEK.get(anahtar)
    if kayit and not taze and time.time() - kayit[0] < HESAP_ONBELLEK_SN:
        return kayit[1]
    with ofis.db.baglanti() as c:
        ajanlar = [dict(r) for r in c.execute(
            "SELECT ad, motor FROM ajan WHERE proje_id = ?", (ofis.proje_id,))]
    tablo = _k.hesap_tablosu(
        ofis.db, ofis.proje_id, ajanlar=ajanlar,
        denetle=_fabrika_denetle if MOTOR_FABRIKASI else None,
        fabrika=MOTOR_FABRIKASI)
    _HESAP_ONBELLEK[anahtar] = (time.time(), tablo)
    return tablo


def _katla(m: str) -> str:
    """Turkce buyuk/kucuk harf KATLAMASI. `casefold` 'I'yi 'i'ye, 'İ'yi
    'i̇'ye cevirir; Turkce metinde "Iptal" ile "iptal" ayni kelimedir ve
    aranan kelime harf buyuklugu yuzunden kacmamali."""
    return (m or "").replace("İ", "i").replace("I", "i").replace("ı", "i").casefold()


def ara(db, proje_id: str, sorgu: str, *, azami: int = 60) -> list:
    """Gorev · kanit · karar · olgu · olay defterinde METIN arar.

    SQL `LIKE` Turkce harfleri katlayamaz (yalniz ASCII); aramak ancak
    Python'da katlanarak dogru olur. Olay defteri buyuyebilir, o yuzden
    yalniz son 5000 satiri taranir ve bu SOYLENIR (`kapsam`).
    """
    q = _katla(sorgu.strip())
    if len(q) < 2:
        return []

    def parca(metin: str) -> str:
        k = _katla(metin)
        i = k.find(q)
        if i < 0:
            return (metin or "")[:160]
        bas = max(0, i - 60)
        return ("…" if bas else "") + metin[bas:i + len(q) + 90].replace("\n", " ")

    out = []
    with db.baglanti() as conn:
        for r in conn.execute(
                "SELECT no, baslik, govde, neden, ana_hedef, kabul_olcutu, durum, "
                "sahip, guncellendi FROM gorev WHERE proje_id = ? AND silindi = 0 "
                "ORDER BY no DESC", (proje_id,)).fetchall():
            metin = " · ".join(str(r[k] or "") for k in
                               ("baslik", "govde", "neden", "ana_hedef", "kabul_olcutu"))
            if q in _katla(metin):
                out.append({"tur": "gorev", "gorev_no": r["no"], "kim": r["sahip"] or "",
                            "baslik": f"#{r['no']} {r['baslik']} ({r['durum']})",
                            "parca": parca(metin), "zaman": r["guncellendi"]})
        for r in conn.execute(
                "SELECT k.baslik, k.icerik, k.tur, k.ekleyen, k.olusturuldu, g.no "
                "FROM kanit k JOIN gorev g ON g.id = k.gorev_id "
                "WHERE g.proje_id = ? ORDER BY k.rowid DESC", (proje_id,)).fetchall():
            metin = f"{r['baslik']} · {r['icerik'] or ''}"
            if q in _katla(metin):
                out.append({"tur": "kanit", "gorev_no": r["no"], "kim": r["ekleyen"],
                            "baslik": f"kanıt #{r['no']} · {r['tur']}: {r['baslik']}",
                            "parca": parca(metin), "zaman": r["olusturuldu"]})
        for r in conn.execute(
                "SELECT k.karar, k.gerekce, k.tur, k.veren, k.olusturuldu, g.no "
                "FROM karar k LEFT JOIN gorev g ON g.id = k.gorev_id "
                "WHERE k.proje_id = ? ORDER BY k.rowid DESC", (proje_id,)).fetchall():
            metin = f"{r['karar']} · {r['gerekce'] or ''}"
            if q in _katla(metin):
                out.append({"tur": "karar", "gorev_no": r["no"], "kim": r["veren"],
                            "baslik": f"karar ({r['tur']}): " + (r["karar"] or "")[:80],
                            "parca": parca(metin), "zaman": r["olusturuldu"]})
        for r in conn.execute(
                "SELECT konu, icerik, gecerli_bitis, kaydedildi FROM olgu "
                "WHERE proje_id = ? ORDER BY rowid DESC", (proje_id,)).fetchall():
            metin = f"{r['konu']} · {r['icerik']}"
            if q in _katla(metin):
                out.append({"tur": "olgu", "gorev_no": None, "kim": "",
                            "baslik": f"bilgi: {r['konu']}"
                                      + (" (ESKİ)" if r["gecerli_bitis"] else ""),
                            "parca": parca(metin), "zaman": r["kaydedildi"]})
        for r in conn.execute(
                "SELECT o.tur, o.govde, o.ajan_ad, o.olusturuldu, g.no FROM olay o "
                "LEFT JOIN gorev g ON g.id = o.gorev_id WHERE o.proje_id = ? "
                "ORDER BY o.id DESC LIMIT 5000", (proje_id,)).fetchall():
            if r["tur"] in ("nabiz", "tur_ozeti"):
                continue                     # makine kaydi, insan aramaz
            if q in _katla(r["govde"]):
                out.append({"tur": "olay", "gorev_no": r["no"], "kim": r["ajan_ad"],
                            "baslik": f"{r['tur']}" + (f" · #{r['no']}" if r["no"] else ""),
                            "parca": parca(r["govde"]), "zaman": r["olusturuldu"]})
            if len(out) >= azami * 3:
                break
    return out[:azami]


def _proje_id_bul(db, proje_ad: str):
    """Panelin `ofis_ac`i ile AYNI secim kurali -- ikinci bir kopya degil.

    Ayri bir secim yazsaydik, panel bir projeyi gosterip lider baska bir
    projede kosabilirdi. Bu projede iki kopyadan biri duzeltilip oteki
    unutuldugu icin alti kez hata cikti.
    """
    with db.baglanti() as conn:
        if proje_ad:
            row = conn.execute("SELECT id FROM proje WHERE ad = ?",
                               (proje_ad,)).fetchone()
        else:
            row = conn.execute("SELECT id FROM proje WHERE durum = 'acik' "
                               "ORDER BY olusturuldu LIMIT 1").fetchone()
    return row["id"] if row else None


def _lideri_kostur(db_yolu, proje_ad: str, mesaj: str,
                   lider_ad: str = "", web=None, kabin_cdp: str = "",
                   atanan: str = "") -> None:
    """Arka planda lider turu. Olaylar zaten deftere yazilir; panel onlari
    SSE ile gorur, yani burada ayrica bir kanal kurmaya gerek yok."""
    def isi(o):
        if MOTOR_FABRIKASI is None:
            sohbet = o.sohbet
        else:
            from .sohbet import Sohbet
            sohbet = Sohbet(o, motor_fabrikasi=MOTOR_FABRIKASI)
        for _olay in sohbet.konus(mesaj, lider_ad=lider_ad,
                                  butce_usd=PANEL_TUR_TAVANI_USD,
                                  tarayici_alani=web or None,
                                  tarayici_kabini=kabin_cdp, atanan=atanan):
            if _durdurulduysa(o, "Lider turu"):
                break
    _arkada_calistir(db_yolu, proje_ad, isi, "lider turu")


def _kuyrugu_baslat(db_yolu, proje_ad: str) -> bool:
    """Siradaki isleri isleyen ipligi baslatir -- ofis bossa. Doner: basladi mi.

    Ofis mesgulse bir sey yapmaz: kosan is (lider turu ya da halka) bitince
    `_arkada_calistir` sirayi yeniden yoklar. Yani bekleyen is ASILI KALMAZ.
    """
    with _KUYRUK_KILIDI:
        if _KOSU["calisiyor"]:
            return False
        try:
            _db = Veritabani(db_yolu)
            pid = _proje_id_bul(_db, proje_ad)
            if pid is None:
                return False
            from . import kuyruk as _kuyruk
            o = Ofis(_db, pid)
            if not _kuyruk.bekleyenler(o):
                return False
            durdurma_temizle(o.db, o.proje_id)
        except Exception:                # noqa: BLE001 -- basaramazsa baslatmaz
            return False
        _KOSU.update(dur=False, calisiyor=True, mesaj="sira isleniyor")
    threading.Thread(target=_kuyrugu_kostur, args=(db_yolu, proje_ad),
                     daemon=True).start()
    return True


def _kuyrugu_kostur(db_yolu, proje_ad: str) -> None:
    """Sirayi BOSALANA kadar isler; seri bitince donus raporu yazar.

    Bir isin dusmesi sirayi DURDURMAZ: o is `hata` olur, sebebi deftere
    yazilir, siradakine gecilir (patron yokken tek hata butun kuyrugu
    bekletmesin). Insan Durdur'a basarsa kosan is bitince sira durur;
    bekleyenler SILINMEZ, rapor bunu soyler.
    """
    def isi(o):
        import uuid as _uuid
        from . import kuyruk as _kuyruk
        seri = _uuid.uuid4().hex
        try:
            while True:
                if _durdurulduysa(o, "Sira"):
                    break
                k = _kuyruk.sira_al(o, seri)
                if k is None:
                    break
                _KOSU["mesaj"] = k["metin"][:80]
                kabin_cdp = ""
                if k.get("kabin") and _KABIN_CDP["islev"]:
                    try:
                        kabin_cdp = _KABIN_CDP["islev"]() or ""
                    except Exception:    # noqa: BLE001 -- kabinsiz kosar, blok soyler
                        kabin_cdp = ""
                try:
                    if k.get("devam"):
                        # KESINTIDEN DEVAM: mesaj yeniden PLANLANMAZ (isler
                        # kopyalanirdi); acik isleri halka surdurur.
                        from .orkestra import Orkestra
                        ork = (o.orkestra if MOTOR_FABRIKASI is None
                               else Orkestra(o, motor_fabrikasi=MOTOR_FABRIKASI))
                        for adim in ork.kos(azami_tik=12, butce_usd=PANEL_TUR_TAVANI_USD,
                                            paralel=3):
                            if adim.get("bitti") or _durdurulduysa(o, "Halka"):
                                break
                        _kuyruk.bitir(o, k["id"], "bitti", "kesintiden sonra surduruldu")
                        _kuyruk.devam_cevabi(o, k["id"])
                        continue
                    if MOTOR_FABRIKASI is None:
                        sohbet = o.sohbet
                    else:
                        from .sohbet import Sohbet
                        sohbet = Sohbet(o, motor_fabrikasi=MOTOR_FABRIKASI)
                    for _olay in sohbet.konus(k["metin"], lider_ad=k["lider_ad"],
                                              butce_usd=PANEL_TUR_TAVANI_USD,
                                              tarayici_alani=k["tarayici_alani"] or None,
                                              tarayici_kabini=kabin_cdp,
                                              atanan=k["atanan"]):
                        if _durdurulduysa(o, "Lider turu"):
                            break
                    _kuyruk.bitir(o, k["id"], "bitti")
                except Exception as exc:   # noqa: BLE001 -- hata YUTULMAZ, sira surer
                    import traceback
                    traceback.print_exc()
                    _kuyruk.bitir(o, k["id"], "hata", f"{exc}")
                    o.db.olay_yaz(o.proje_id, "hata",
                                  f"Siradaki is dustu ({k['metin'][:60]}): {exc}")
        finally:
            _kuyruk.raporu_yaz(o, seri)
    _arkada_calistir(db_yolu, proje_ad, isi, "sira")


#: Zamanlayici ne siklikla bakar. Vakit dakikalik konusulur; 20 sn
#: gecikme fark edilmez, defteri de yormaz.
ZAMAN_ARALIGI_S = 20.0


def zamanlayici_tik(db_yolu, proje_ad: str) -> int:
    """Vakti gelen zamanli isleri siraya koyar ve sirayi baslatir."""
    from . import zamanlayici as _z
    _db = Veritabani(db_yolu)
    pid = _proje_id_bul(_db, proje_ad)
    if pid is None:
        return 0
    giren = _z.vadesi_gelenleri_sirala(Ofis(_db, pid))
    if giren:
        _kuyrugu_baslat(db_yolu, proje_ad)
    return len(giren)


def zamanlayiciyi_baslat(db_yolu, proje_ad: str) -> None:
    """F5/4: panel acikken zamanli isler. Ilk tur ACILISTA: PC kapaliyken
    kacirilan is bir kez kosar. Dusus sessiz yutulmaz (bir kez yazilir)."""
    import time

    def dongu():
        soylendi = False
        while True:
            try:
                zamanlayici_tik(db_yolu, proje_ad)
            except Exception as exc:   # noqa: BLE001 -- dongu durmaz, SOYLER
                if not soylendi:
                    soylendi = True
                    import traceback
                    traceback.print_exc()
                    try:
                        _db = Veritabani(db_yolu)
                        _db.olay_yaz(_proje_id_bul(_db, proje_ad), "hata",
                                     f"Zamanlayici dustu: {exc}")
                    except Exception:  # noqa: BLE001
                        pass
            time.sleep(ZAMAN_ARALIGI_S)
    threading.Thread(target=dongu, name="zamanlayici", daemon=True).start()


def bildirimleri_baslat(db_yolu, proje_ad: str, adres: str) -> None:
    """Masaustu bildirimi (F5/3): yalniz GERCEK panel acar; sinamalar
    `olustur` kullanir ve ekrana bildirim dusmez."""
    from . import bildirim as _b
    _b.ACIK = True

    def ofis_ac():
        _db = Veritabani(db_yolu)
        return Ofis(_db, _proje_id_bul(_db, proje_ad))
    _b.arkada_izle(ofis_ac, adres)


def acilista_toparla(db_yolu, proje_ad: str = None) -> dict:
    """Panel ACILIRKEN: kesintide yarim kalani toparla, sirayi baslat.

    Hata paneli acilmaktan alikoymaz ama YUTULMAZ: deftere `hata` yazilir.
    """
    try:
        _db = Veritabani(db_yolu)
        pid = _proje_id_bul(_db, proje_ad)
        if pid is None:
            return {}
        from .toparla import acilista_toparla as _toparla
        sonuc = _toparla(Ofis(_db, pid))
    except Exception as exc:          # noqa: BLE001 -- panel yine acilir
        import traceback
        traceback.print_exc()
        try:
            _db.olay_yaz(pid, "hata", f"Acilista toparlama dustu: {exc}")
        except Exception:             # noqa: BLE001
            pass
        return {}
    _kuyrugu_baslat(db_yolu, proje_ad)
    return sonuc


def _halkayi_kostur(db_yolu, proje_ad: str) -> None:
    """`kabuk devam`in panel karsiligi: halkayi YENI HEDEF VERMEDEN dondurur.

    OLCULMUS KUSUR (23.09.2026): panel soru cevaplatiyor ve onay
    aldiriyordu ama isi SURDURECEK bir sey yoktu -- kabuk bunu acikca
    soyluyordu (*"halkayi surdurmek icin: `kabuk devam`"*), panelde
    boyle bir dugme yoktu. Yani panelde onay veren insan, hicbir seyin
    olmadigini gorurdu. Komut cubugunda bir kez odenen *"dugme var,
    arkasinda kosturan yok"* hatasinin aynisi.

    Ayarlar lider turundakiyle ayni ve paralellik
    kabuktaki varsayilanla ayni (3) -- iki yuzey ayni halkayi farkli
    ayarla dondurseydi ayni is iki farkli bicimde kosardi.
    """
    def isi(o):
        from .orkestra import Orkestra
        ork = (o.orkestra if MOTOR_FABRIKASI is None
               else Orkestra(o, motor_fabrikasi=MOTOR_FABRIKASI))
        for adim in ork.kos(azami_tik=12, butce_usd=PANEL_TUR_TAVANI_USD,
                            paralel=3):
            if adim.get("bitti") or _durdurulduysa(o, "Halka"):
                break
    _arkada_calistir(db_yolu, proje_ad, isi, "halka")


def _ajana_sor_kostur(db_yolu, proje_ad: str, mesaj_id: str) -> None:
    """Insanin ajana sorusunu teslim eder (tavanli, salt okunur)."""
    try:
        _db = Veritabani(db_yolu)
        pid = _proje_id_bul(_db, proje_ad)
        if pid is None:
            return
        o = Ofis(_db, pid)
        with _db.baglanti() as conn:
            m = dict(conn.execute(
                "SELECT m.*, g.no AS gorev_no FROM mesaj m LEFT JOIN gorev g "
                "ON g.id = m.gorev_id WHERE m.id = ?", (mesaj_id,)).fetchone())
        from .danisma import Danisma
        d = (o.danisma if MOTOR_FABRIKASI is None
             else Danisma(o, motor_fabrikasi=MOTOR_FABRIKASI))
        d.insana_cevapla(m, butce_usd=PANEL_TUR_TAVANI_USD)
    except Exception as exc:       # noqa: BLE001 -- hata YUTULMAZ
        try:
            _hdb = Veritabani(db_yolu)
            _hpid = _proje_id_bul(_hdb, proje_ad)
            if _hpid is not None:
                _hdb.olay_yaz(_hpid, "hata", f"Ajana sorulan soru dustu: {exc}")
        except Exception:
            pass
    finally:
        _DANISMA.update(calisiyor=False, ajan="")


def _arkada_calistir(db_yolu, proje_ad: str, isi, adi: str) -> None:
    """Panelden baslatilan HER arka plan isinin tek iskeleti.

    TEK ISKELET: lider turu ve halka ayni kodu kullanir. Iki kopya
    olsaydi hata yutmama kurali birinde duzeltilir, oteki unutulurdu --
    bu projede tam o desen alti kez odendi.

    KENDI BAGLANTISINI ACAR: `Veritabani` butun baglantilari tek `RLock`
    ile siraya dizer ama nesneyi iplikler arasinda tasimak yerine taze
    acmak daha guvenli -- ve hayalet veritabani dersi geregi yol zaten
    MUTLAK saklaniyor.
    """
    o = None
    try:
        _db = Veritabani(db_yolu)
        pid = _proje_id_bul(_db, proje_ad)
        if pid is None:
            return
        o = Ofis(_db, pid)
        isi(o)
    except Exception as exc:       # noqa: BLE001 -- hata YUTULMAZ
        # Arka plan ipliginde patlayan sey sessizce kaybolur. Ilk surumum
        # tam bunu yapiyordu: olayi yalnizca `o` kurulabilmisse yaziyordu,
        # yani en erken hatalar -- veritabani acilamadi, proje bulunamadi --
        # HICBIR IZ birakmadan kayboluyordu. Docstring'de "hata yutulmaz"
        # yaziyordu ve kod yutuyordu.
        import traceback
        _KOSU["son_hata"] = f"{exc}"
        try:
            _hdb = Veritabani(db_yolu)
            _hpid = _proje_id_bul(_hdb, proje_ad)
            if _hpid is not None:
                _hdb.olay_yaz(_hpid, "hata",
                              f"Panelden baslatilan {adi} dustu: {exc}")
        except Exception:
            pass
        traceback.print_exc()
    finally:
        durduruldu = bool(_KOSU.get("dur"))
        _KOSU.update(calisiyor=False, mesaj="", dur=False)
        # SIRA YOKLAMASI (01.10.2026): halka kosarken siraya giren is ya da
        # isci cikarken gelen is burada baslar -- yoksa ASILI kalirdi.
        # Insan durdurduysa sira kendiliginden SURMEZ.
        if not durduruldu:
            _kuyrugu_baslat(db_yolu, proje_ad)


class CevapGovdesi(BaseModel):
    metin: str
    surdur: bool = True


class KabinIzleGovdesi(BaseModel):
    acik: bool


class KabinGovdesi(BaseModel):
    """Kabin acilirken gidilecek ilk adres (istege bagli).

    `gorunur` bir KACIS KOLU, varsayilan degil: kabin bassiz kosar ve
    yalnizca panelde yasar. Bazi siteler bassiz tarayiciya giris
    vermeyebilir -- bunu OLCMEDIK, o yuzden kol duruyor.
    """

    url: str = ""
    gorunur: bool = False


class LidereGovdesi(BaseModel):
    """Panelin lidere yazdigi satir + HANGI KANAT.

    Kanat ayri bir alan cunku ofiste birden fazla lider olabilir ve
    *yanlis kanada verilen hedef, yanlis kadroya yanlis isi verir*
    (`orkestra._lider_sec`). Panelin ustunde zaten kanat sekmeleri var;
    secili kanadi gondermemek, panelin BILDIGI bir seyi cekirdekten
    saklamak olurdu.
    """
    metin: str
    kanat: str = ""
    #: Kabinde SECILEN oge (varsa). Sunucuda YENIDEN suzulur: istemci
    #: guvenilmez girdidir, ayni suzgec sayfadan gelene de uygulanir.
    oge: dict | None = None


class EforGovdesi(BaseModel):
    mod: str


class OnayGovdesi(BaseModel):
    """`kapsam`: `eylem` (bir kez, VARSAYILAN) ya da `is` (bu gorev boyunca).

    Varsayilan DAR olan -- bir "evet" sessizce surekli yetkiye donmemeli.
    `surdur`: cevap isi acan son istekse halka kendiliginden doner.
    """
    onayla: bool
    not_: str = ""
    kapsam: str = "eylem"
    surdur: bool = True


class DevralGovdesi(BaseModel):
    sutun: int = 120
    satir: int = 32


class GeriVerGovdesi(BaseModel):
    """Insanin ajana kisa notu -- istege bagli; degisen dosyalari ofis
    kendisi olcup ekler."""
    not_: str = ""


#: Terminal yalniz BU bilgisayardan acilir. Terminal bilgisayarda komut
#: calistirabilen bir penceredir; telefondan (Tailscale) ya da agdaki baska
#: bir cihazdan acilmasi, o cihaza bu bilgisayarin kabugunu vermek olurdu.
#: `testclient` Starlette'in sinama istemcisinin adidir, bir ag adresi degil.
TERMINAL_YEREL = ("127.0.0.1", "::1", "localhost", "testclient")


class KonsolGovdesi(BaseModel):
    klasor: str = ""
    motor: str = "powershell"
    sutun: int = 120
    satir: int = 32


class KipGovdesi(BaseModel):
    kip: str = ""


class EkGovdesi(BaseModel):
    ad: str = ""
    veri: str = ""      # base64 (python-multipart bagimliligi eklenmesin)


class SebepGovdesi(BaseModel):
    """Ret ve iptal icin. Sebep ZORUNLU -- cekirdek zaten reddediyor;
    burada ayrica alan olmasi, panelin onu SORMASI icin."""
    sebep: str = ""


class GuncelleGovdesi(BaseModel):
    kademe: str = ""


class SablonGovdesi(BaseModel):
    ad: str = ""
    kanat: str = ""


class BilgiGovdesi(BaseModel):
    konu: str = ""
    icerik: str = ""


class KuralGovdesi(BaseModel):
    """Uc kaynak, biri: duz metin, bir bilginin konusu ya da bir ders.
    Gerekce ZORUNLU -- cekirdek de reddediyor (iki bagimsiz kapi)."""
    metin: str = ""
    olgu: str = ""
    ders_id: str = ""
    gerekce: str = ""


class IseAlGovdesi(BaseModel):
    """Panelden ise alma. Bos birakilan tur/model ROLDEN dolar
    (`kadro.ise_al`); acikca verilen deger her zaman kazanir."""
    ad: str
    meslek: str
    motor: str = "claude"
    model: str = ""
    efor: str = "normal"
    kanat: str = ""
    lider: bool = False


class AnahtarGovdesi(BaseModel):
    """Kasaya yazilacak anahtar. DEGER BIR KEZ GELIR, bir daha DONMEZ:
    cevapta yalniz parmak izi var (`gizli.liste` ile ayni kural)."""
    ad: str
    deger: str


class AjanaSorGovdesi(BaseModel):
    ajan: str
    metin: str


class NotGovdesi(BaseModel):
    metin: str
    gorev_no: Optional[int] = None


class KanatGovdesi(BaseModel):
    ad: str
    onek: str = ""
    renk: str = "#6BA3C7"


class AktifGovdesi(BaseModel):
    aktif: bool


class AjanAyarGovdesi(BaseModel):
    """Yalniz VERILEN alan degisir; `None` dokunulmaz demektir."""
    motor: str | None = None
    model: str | None = None
    efor: str | None = None
    meslek: str | None = None


def _oda(ofis, ajan: dict) -> dict:
    """Ajan hangi odada. TURETILIR -- saklanmaz.

    Saklansaydi iki kaynak olurdu: gercek durum ve odanin kaydi. Biri
    bayatladiginda panel yanlis yeri gosterir ve yanlis gosteren bir
    gosterge, gostergesizlikten kotudur.
    """
    # `kime` HER dalda var (bos da olsa): harita soru soran ajani
    # sorulanin yanina yurutur; alan bazen var bazen yoksa, "yok" ile
    # "bos" ayirt edilemez ve tuketici tahmin etmek zorunda kalir.
    bekleme = ofis.postane.bekliyor_mu(ajan["ad"])
    if bekleme["bekliyor"]:
        return {"oda": "bekleme" if bekleme["tur"] == "soru" else "onay_kapisi",
                "not": bekleme["aciklama"], "gorev_no": None,
                "kime": bekleme.get("kime") or ""}

    kendi = [g for g in ofis.tahta.liste() if g["sahip"] == ajan["ad"]]
    calisan = [g for g in kendi if g["durum"] == "calisiyor"]
    if calisan:
        return {"oda": "masa", "not": calisan[0]["baslik"],
                "gorev_no": calisan[0]["no"], "kime": ""}
    incelemede = [g for g in kendi if g["durum"] == "inceleme"]
    if incelemede:
        return {"oda": "inceleme", "not": incelemede[0]["baslik"],
                "gorev_no": incelemede[0]["no"], "kime": ""}
    if ajan["lider_mi"]:
        # Lider KENDI kanadinin islerine bakar. Kanat filtresi olmadan
        # pazarlama lideri urun kanadinin isini inceliyor gorunurdu --
        # yanlis gosteren bir gosterge, gostergesizlikten kotudur.
        bekleyen = [g for g in ofis.tahta.liste(durum="inceleme")
                    if g["kanat_id"] == ajan["kanat_id"]]
        if bekleyen:
            return {"oda": "inceleme",
                    "not": f"#{bekleyen[0]['no']} inceleniyor",
                    "gorev_no": bekleyen[0]["no"], "kime": ""}
    return {"oda": "mola", "not": "", "gorev_no": None, "kime": ""}


def _kullanim(rows) -> dict:
    """Jeton ve API karsiligi -- FIYATLANAMAYAN TUR SAYILARAK.

    Neden ayri bir islev: bu sayilar panoya konan "kullanim kartini"
    besliyor ve karti dogru yapan sey toplamin kendisi degil, toplamin
    NEYI ICERMEDIGINI soylemesi.

    OLCULMUS ILKE (rakipten alindi, 21.09.2026): AgentSpace kullanim
    karti fiyati bilinmeyen turda sahte bir `$0` basmak yerine
    *"unpriced"* yaziyor. Ayni cumleyi biz zaten baska yerde yazmistik
    -- *"olcemedigine 'iyi' demez"* (`saglik.py`) ve *"motorlar kotanin
    ne kadari kaldigini yayinlamiyor, o yuzden cubuk cizmiyoruz"*.
    Panelde karsiligi YOKTU.

    Fark onemli ve sinsi: `maliyet_usd = 0.0` OLCULMUS bir sifirdir
    (sahte motor, ya da onbellekten donen tur); `None` ise OLCULEMEMIS
    demektir. Ikisini toplarken ayni saymak, bilinmeyen maliyeti sifir
    ilan etmektir -- ve bu tam olarak *"gorunmeyen butce, butce
    degildir"* kuralinin sessizce delinmesi olurdu.

    Bu yuzden maliyet toplanirken yalnizca FIYATLI turlar toplanir ve
    `fiyatsiz` ayri sayilir. Hicbir tur fiyatlanamadiysa toplam `None`
    doner -- `0.0` degil.
    """
    import json as _json
    bos = {"jeton": 0, "maliyet_usd": None, "fiyatli": 0, "fiyatsiz": 0,
           "tur": 0}
    tum = dict(bos)
    ise_gore: dict = {}
    for r in rows:
        try:
            d = _json.loads(r["govde"])
        except (ValueError, TypeError):
            continue
        no = r["gorev_no"]
        hedefler = [tum]
        if no is not None:
            hedefler.append(ise_gore.setdefault(no, dict(bos)))
        m = d.get("maliyet_usd")
        j = d.get("jeton")
        for h in hedefler:
            h["tur"] += 1
            if isinstance(j, (int, float)):
                h["jeton"] += int(j)
            if isinstance(m, (int, float)):
                h["maliyet_usd"] = (h["maliyet_usd"] or 0.0) + float(m)
                h["fiyatli"] += 1
            else:
                h["fiyatsiz"] += 1
    return {"tum": tum, "ise_gore": ise_gore}


def _ajan_sicili(ofis, ad: str) -> dict:
    """Bir ajanin PANOSUNDA gorunecek olculmus bilgiler.

    OLCULMUS TASARIM HATASI (21.09.2026): panele gercek veriyle
    bakildiginda ofis 9 is bitirmis, $14,84 harcamis, 40 karar
    uretmisti -- ve ana gorunum "bos . bos . bos . bos" diyordu. Her
    ajanin altinda *"is verilmedi"* yaziyordu; `cinar` 8 is yapmisti.
    Yani DINLENEN bir ofis ile HIC KULLANILMAMIS bir ofis panelde
    birebir ayni gorunuyordu.

    Rakibin ekrani canli duruyor cunku ana icerigi TERMINAL: akan
    cikti, model, plan, dal, limit. Bizimki ana icerik olarak ODALARI
    koymustu -- ve oda bir soyutlama; is yokken ici bos.

    Bu islev, panonun basligina konacak seyi uretir. Ozellikle bizim
    OLCEBILDIGIMIZ ve rakipte OLMAYAN alanlar onemli: yazma kilidi,
    kanit sayisi, turun maliyeti. Gucumuz vardi, ekranda yoktu.

    UYDURMAZ: olculemeyen alan `None` doner ve istemci onu basmaz.
    """
    import json as _json
    sicil = {"tur": 0, "is": 0, "son_tur": None, "kilit": [],
             "son_gorev": None, "kullanim": None}
    with ofis.db.baglanti() as conn:
        rows = conn.execute(
            "SELECT o.govde, g.no AS gorev_no FROM olay o "
            "LEFT JOIN gorev g ON g.id = o.gorev_id "
            "WHERE o.proje_id = ? AND o.ajan_ad = ? "
            "AND o.tur = 'tur_ozeti' ORDER BY o.id DESC LIMIT 60",
            (ofis.proje_id, ad)).fetchall()
        sicil["tur"] = len(rows)
        sicil["kullanim"] = _kullanim(rows)
        for r in rows:
            try:
                d = _json.loads(r["govde"])
            except (ValueError, TypeError):
                continue
            if sicil["son_tur"] is None:
                sicil["son_tur"] = {
                    "jeton": d.get("jeton"), "maliyet_usd": d.get("maliyet_usd"),
                    "model": d.get("model"), "basarili": d.get("basarili"),
                    "arac": d.get("arac_sayisi"),
                    # MOTOR: 22.09'da `tur_ozeti`ye eklendi ama panele
                    # hic ulasmiyordu. Pano rozetinde OLCULEN motor
                    # yazmali, ajanin AYARI degil -- zincir devrettiginde
                    # ayar yanlis cevabi verir.
                    "motor": d.get("motor"),
                    # HESAP: pano basligindaki limit rozeti HANGI hesabin
                    # penceresine bakacagini buradan bilir. Olmasaydi
                    # ikinci bir codex hesabiyla kosan turda rozet
                    # birinci hesabin yuzdesini gosterirdi.
                    "hesap": d.get("hesap") or "",
                }
                break
        sicil["kilit"] = [x["yol_oneki"] for x in conn.execute(
            "SELECT yol_oneki FROM yazma_kilidi WHERE proje_id = ? "
            "AND ajan_ad = ?", (ofis.proje_id, ad)).fetchall()]
        sicil["is"] = int(conn.execute(
            "SELECT COUNT(*) n FROM gorev WHERE proje_id = ? AND sahip = ?",
            (ofis.proje_id, ad)).fetchone()["n"])
        g = conn.execute(
            "SELECT no, baslik, durum FROM gorev WHERE proje_id = ? "
            "AND sahip = ? ORDER BY guncellendi DESC LIMIT 1",
            (ofis.proje_id, ad)).fetchone()
    if g:
        sicil["son_gorev"] = {"no": g["no"], "baslik": g["baslik"],
                              "durum": g["durum"],
                              "kanit": len(ofis.tahta.kanitlar(g["no"]))}
    return sicil


def _para_durumu(ofis) -> dict:
    """Paranin gorunur hali: haftalik kapi butcesi + medya para kilidi.

    PANELDE HIC YOKTU. Olculdu (21.09.2026): haftalik kapi butcesinin
    $2,14'u harcanmisti, para kilidi kapaliydi, gorsel kotasi doluydu --
    ve panele bakan biri bunlarin hicbirini goremiyordu.

    Ofisin kendi kurali: *gorunmeyen butce, butce degildir.* Ayni cumle
    `saglik.py`de yaziliydi ama yalnizca CLI'a baglanmisti; panel
    ayni koreligi tasiyordu.

    Kota BURADA OLCULMEZ -- son gercek denemenin sonucu hatirlanir
    (`gorsel.kota_notu`). Olcmek bir istek harcar ve tam tuketmeye
    calistigimiz seyi tuketirdi.
    """
    from . import butce as _butce, gorsel as _gorsel, kullanim as _k
    try:
        h = _butce.kapi_acik_mi(ofis.db, ofis.proje_id)
    except Exception:
        h = {}
    # HESAPLARIN DOLULUGU (27.09.2026 karari): abonelikte dolar yok; ust
    # cubukta saglayicinin KENDI yuzdesi durur. Olculmeyen hesap gosterilmez
    # (uydurulmaz), yenilenen pencere yuzde yerine "yenilendi" der.
    limitler = []
    try:
        for p in _k.son_pencereler(ofis.db, ofis.proje_id):
            limitler.append({
                "ad": p["motor"] + (f"/{p['hesap']}" if p["hesap"] else ""),
                "yas_dk": p["yas_dk"],
                "pencereler": {ad: w["kullanim"] for ad, w in p["pencereler"].items()},
                # YENILENME ANI (27.09.2026, kullanici: "limiti biten ne zaman
                # yenilenecek"). Kalan sure istemcide hesaplanir: an mutlak
                # oldugu icin dakikalik tazelemede sayi kendiliginden geri sayar.
                "yenilenmeler": {ad: w["yenilenme"].isoformat()
                                 for ad, w in p["pencereler"].items()
                                 if not w.get("yenilendi")}})
    except Exception:
        pass
    return {
        "limitler": limitler,
        "kapi_kullanim": h.get("kullanim"),
        "kapi_esik": h.get("esik"),
        "kapi_acik": h.get("acik"),
        "kilit_kapali": _gorsel.ucretsiz_sadece_mi(),
        "gorsel_kota": _gorsel.kota_notu("gemini"),
    }


def _bekleyen_ekip(ofis) -> int:
    """Karar bekleyen ekip onerisi sayisi.

    `saglik.py`ye 12. denetim tam bu gorunmedigi icin eklenmisti:
    ofis bosken *"senden beklenen yok"* diyordu, oysa iki ajan onay
    bekliyordu. Panel ayni koru noktayi tasiyordu -- ve orasi insanin
    eylem kuyrugunun DURDUGU yer.
    """
    with ofis.db.baglanti() as conn:
        r = conn.execute(
            "SELECT COUNT(*) n FROM ekip_onerisi "
            "WHERE proje_id = ? AND durum = 'bekliyor'",
            (ofis.proje_id,)).fetchone()
    return int(r["n"] if r else 0)


def _olcumler(ofis) -> dict:
    """Jeton ve maliyet toplami -- `tur_ozeti` olaylarindan.

    Olculmeyen sey yonetilemez. Yasa 2'nin faturasi (coklu ajan ~15x
    jeton) ancak burada gorunur hale gelir.
    """
    toplam = {"jeton": 0, "maliyet_usd": 0.0, "tur": 0, "basarisiz": 0}
    with ofis.db.baglanti() as conn:
        rows = conn.execute(
            "SELECT govde FROM olay WHERE proje_id = ? AND tur = 'tur_ozeti'",
            (ofis.proje_id,),
        ).fetchall()
    for r in rows:
        try:
            o = json.loads(r["govde"])
        except (json.JSONDecodeError, TypeError):
            continue
        toplam["jeton"] += int(o.get("jeton") or 0)
        toplam["maliyet_usd"] += float(o.get("maliyet_usd") or 0.0)
        toplam["tur"] += 1
        if not o.get("basarili"):
            toplam["basarisiz"] += 1
    toplam["maliyet_usd"] = round(toplam["maliyet_usd"], 4)
    return toplam


def _baglam_sagligi(ofis) -> dict:
    """Bize ozgu gosterge: ajanin kafasindaki baglam saglikli mi.

    Rakipte yok. Olcum sebebi: hafiza isabeti iyilestirmeden sonra bile
    ~%25 -- yani dortte uc iskalaniyor. Baglami GORUNUR kilmak, iskalayi
    da gorunur kilar. Sisen brifing, biriken eski olgu ve kabaran karar
    sayisi burada okunur.
    """
    with ofis.db.baglanti() as conn:
        son = conn.execute(
            "SELECT ajan_ad, jeton_tahmini, olusturuldu FROM brifing "
            "WHERE gorev_id IN (SELECT id FROM gorev WHERE proje_id = ?) "
            "ORDER BY olusturuldu DESC, rowid DESC LIMIT 1",
            (ofis.proje_id,),
        ).fetchone()
        gecerli = conn.execute(
            "SELECT COUNT(*) n FROM olgu WHERE proje_id = ? AND gecerli_bitis IS NULL",
            (ofis.proje_id,),
        ).fetchone()["n"]
        eski = conn.execute(
            "SELECT COUNT(*) n FROM olgu WHERE proje_id = ? AND gecerli_bitis IS NOT NULL",
            (ofis.proje_id,),
        ).fetchone()["n"]
        karar = conn.execute(
            "SELECT COUNT(*) n FROM karar WHERE proje_id = ?", (ofis.proje_id,),
        ).fetchone()["n"]
    return {
        "son_brifing_jeton": int(son["jeton_tahmini"]) if son else 0,
        "son_brifing_ajan": son["ajan_ad"] if son else "",
        "gecerli_olgu": gecerli,
        "eski_olgu": eski,
        "karar": karar,
        # brifing.JETON_UYARI_ESIGI ile ayni esik
        "sisme": bool(son and int(son["jeton_tahmini"]) > 6000),
    }


def olustur(db_yolu=None, proje_ad: str = None) -> FastAPI:
    db = Veritabani(db_yolu or VARSAYILAN_YOL)
    uygulama = FastAPI(title="AgentOfis", docs_url=None, redoc_url=None)

    def ofis_ac() -> Ofis:
        with db.baglanti() as conn:
            if proje_ad:
                row = conn.execute("SELECT id FROM proje WHERE ad = ?",
                                   (proje_ad,)).fetchone()
            else:
                row = conn.execute(
                    "SELECT id FROM proje WHERE durum = 'acik' "
                    "ORDER BY olusturuldu LIMIT 1").fetchone()
        if not row:
            # NOBETCI: "proje yok" demek insani YANLIS YONE gonderir.
            #
            # Olculdu (21.09.2026): paneli POSIX bicimli bir yolla
            # (`/c/Users/...`) acmaya calistim; Windows Python onu
            # baska bir koke cozdu, SQLite olmayan dosyayi YARATTI ve
            # panel yalnizca "Acik proje yok" dedi. Ayni turda ajanin
            # biraktigi ikinci bir hayalet defter daha bulundu -- tuzak
            # ayni gun IKI KEZ isirdi.
            #
            # `mcp_sunucu.py` bu nobetciyi tasiyordu, panel tasimiyordu:
            # ayni ders iki tuketiciden yalnizca birine uygulanmisti.
            # Surec sinirini gecen her goreli yol bir tuzaktir.
            with db.baglanti() as conn:
                adlar = [r["ad"] for r in conn.execute(
                    "SELECT ad FROM proje ORDER BY olusturuldu").fetchall()]
            raise HTTPException(404, (
                f"Bu veritabaninda proje YOK: {db.yol}"
                + (f" | Icindeki projeler: {', '.join(adlar)}" if adlar
                   else " | Veritabani BOS -- yeni olusturulmus olabilir.")
                + (f" | Aranan: '{proje_ad}'" if proje_ad else "")
                + " | Muhtemelen yanlis veritabani acildi: goreli ya da"
                  " POSIX bicimli bir yol baska bir klasore cozulmus"
                  " olabilir. Yolu MUTLAK ve Windows bicimiyle ver."))
        return Ofis(db, row["id"])

    # -- sayfa -------------------------------------------------------------

    # Kabin PANELIN omrunu paylasir: panel kapaninca surec de
    # birakilir. Istenmedikce ACILMAZ -- CDP yerel bir arka
    # kapidir ve varsayilan dar olmali.
    _kabin = kabin.Kabin()

    def _kabin_cdp_ver() -> str:
        if not _kabin.durum().get("acik"):
            return ""
        from . import tarayici as _t
        return _t.cdp_adresi(_kabin.kapi)
    _KABIN_CDP["islev"] = _kabin_cdp_ver

    def _kabin_ajan_icin_ac() -> str:
        """Ajan tarayici gereken ise basliyor, kabin kapali: ofis ACAR
        (02.10.2026, patron: "otomatik olmali"). Kayda gecer; panel
        `yenile`de gorup gosterir."""
        _kabin.ac("about:blank")
        _kabin_kaydi("kabin_acildi", "Kabin acildi (ajan tarayici kullanacak)")
        return _kabin_cdp_ver()
    # Acici YALNIZ calisan sunucuda kaydedilir (`calistir`). Burada
    # kaydedilseydi paneli kuran her SINAMA gercek Chrome acardi (02.10.2026
    # olculdu: duman_panel kabini 9399'da acik birakti).
    _KABIN_CDP["acici"] = _kabin_ajan_icin_ac

    # ONBELLEK: `no-cache` = "kullanmadan once SOR". Basliksiz dosyada
    # tarayici kendi tahminiyle tazelik uydurur (son degisimden bu yana
    # gecen surenin ~%10'u) ve panel guncellenince ESKI arayuzu
    # gostermeye devam eder. Olculdu (23.09.2026): sunucu yeni harita
    # kodunu veriyordu, sayfa eski kart izgarasini ciziyordu -- hata
    # vermeden. Yanlis gosteren gosterge, bu kez panelin kendisiydi.
    # Panel yerel; her acilista ~100 KB yeniden gelmesi bedava.
    ONBELLEKSIZ = {"Cache-Control": "no-cache"}

    @uygulama.get("/")
    def sayfa():
        return FileResponse(WEB / "index.html", headers=ONBELLEKSIZ)

    @uygulama.get("/favicon.ico")
    def favicon():
        # Tarayici her acilista ister; 404 konsolu kirletiyordu. Ikon
        # dosyasi tutmak yerine tek satirlik SVG donuyoruz.
        nokta = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
                 '<circle cx="16" cy="16" r="11" fill="#e0785a"/></svg>')
        return Response(nokta, media_type="image/svg+xml")

    @uygulama.get("/varlik/{dosya:path}")
    def varlik(dosya: str):
        yol = (WEB / dosya).resolve()
        # Klasor disina cikilamaz: panel yerelde kossa da yol enjeksiyonu
        # dosya sistemini disari acar.
        if WEB.resolve() not in yol.parents or not yol.is_file():
            raise HTTPException(404, "Bulunamadi.")
        return FileResponse(yol, headers=ONBELLEKSIZ)

    # -- okuma -------------------------------------------------------------

    @uygulama.get("/api/ofis")
    def api_ofis():
        ofis = ofis_ac()
        with db.baglanti() as conn:
            proje = dict(conn.execute("SELECT * FROM proje WHERE id = ?",
                                      (ofis.proje_id,)).fetchone())
            kanatlar = [dict(r) for r in conn.execute(
                "SELECT * FROM kanat WHERE proje_id = ? ORDER BY olusturuldu",
                (ofis.proje_id,)).fetchall()]

        gorevler = ofis.tahta.liste()
        sayim = {s: 0 for s in SUTUNLAR}
        for g in gorevler:
            if g["durum"] in sayim:
                sayim[g["durum"]] += 1
        for k in kanatlar:
            k["gorev"] = len([g for g in gorevler if g["kanat_id"] == k["id"]])
            k["calisan"] = len([g for g in gorevler
                                if g["kanat_id"] == k["id"] and g["durum"] == "calisiyor"])

        ajanlar = []
        for a in ofis.kadro.liste():
            yer = _oda(ofis, a)
            ajanlar.append({
                "ad": a["ad"], "meslek": a["meslek"], "lider_mi": bool(a["lider_mi"]),
                "motor": a["motor"], "model": a["model"] or "hesap varsayilani",
                "efor": a["efor"], "tur": a["tur"], "faz": a["faz"],
                "kanat_id": a["kanat_id"], "oturum_var": bool(a["oturum_id"]),
                "ders": len(ofis.kadro.dersler(a["ad"])),
                "sicil": _ajan_sicili(ofis, a["ad"]),
                **yer,
            })

        return {
            "proje": proje,
            "kanatlar": kanatlar,
            "ajanlar": ajanlar,
            "sayim": sayim,
            "bekleyen_soru": len(ofis.postane.insan_bekleyenler()),
            "bekleyen_onay": len(ofis.postane.bekleyen_onaylar()),
            "olcum": _olcumler(ofis),
            "baglam": _baglam_sagligi(ofis),
            "motorlar": musait_motorlar(),
            "para": _para_durumu(ofis),
            "bekleyen_ekip": _bekleyen_ekip(ofis),
            "son_olay_id": ofis.bellek.son_olay_id(),
        }

    @uygulama.get("/api/saglik")
    def api_saglik():
        """Ofis tikali mi -- 12 denetim, teshis + care.

        AYRI UC NOKTA, `/api/ofis`e gomulmedi: `/api/ofis` her saniye
        yoklanir, saglik ise tahtayi bastan tarar. Her yoklamaya
        bindirmek, gostergeyi olctugu seyi yavaslatan bir sey yapardi.

        PANELDE HIC YOKTU ve bu olculdu (21.09.2026): `saglik.py` 12
        denetimle yazildi, `panel.py` icinde adi bile gecmiyordu --
        yalnizca bir yorum satirinda. Yani panelin cevapladigini
        soyledigi tek soru (*"neye bakmam gerekiyor?"*) icin yazilmis
        arac, panele hic baglanmamisti.
        """
        from .saglik import Saglik
        return Saglik(ofis_ac()).denetle()

    @uygulama.get("/api/tahta")
    def api_tahta(kanat: str = ""):
        ofis = ofis_ac()
        sutunlar = {s: [] for s in SUTUNLAR}
        for g in ofis.tahta.liste():
            if kanat and g["kanat_id"] != kanat:
                continue
            if g["durum"] not in sutunlar:
                continue
            kilitler = ofis.tahta.cakisan_kilitler(g["yazma_alani"]) \
                if g["yazma_alani"] else []
            sutunlar[g["durum"]].append({
                "no": g["no"], "baslik": g["baslik"], "sahip": g["sahip"],
                "ana_hedef": g["ana_hedef"], "oncelik": g["oncelik"],
                "yazma_alani": g["yazma_alani"],
                # Kilit BIZE OZGU gostergedir: kartta asma kilit + yol.
                "kilitli": bool([k for k in kilitler if k["gorev_id"] == g["id"]]),
                "kanit": len(ofis.tahta.kanitlar(g["no"])),
                "blokci": [b["no"] for b in ofis.tahta.blokcular(g["no"])],
            })
        return sutunlar

    @uygulama.get("/api/gorev/{no}")
    def api_gorev(no: int):
        ofis = ofis_ac()
        try:
            g = ofis.tahta.gorev(no)
        except TahtaHatasi as exc:
            raise HTTPException(404, str(exc))
        with db.baglanti() as conn:
            brifing = conn.execute(
                "SELECT ajan_ad, jeton_tahmini, olusturuldu FROM brifing "
                "WHERE gorev_id = ? ORDER BY olusturuldu DESC, rowid DESC LIMIT 1",
                (g["id"],)).fetchone()
            rapor = conn.execute(
                "SELECT govde, ajan_ad, olusturuldu FROM olay "
                "WHERE gorev_id = ? AND tur = 'rapor' "
                "ORDER BY id DESC LIMIT 1", (g["id"],)).fetchone()
        g["kanitlar"] = ofis.tahta.kanitlar(no)
        g["blokcular"] = ofis.tahta.blokcular(no)
        from . import izin as izin_mod
        g["izinler"] = izin_mod.liste(db, ofis.proje_id, gorev_id=g["id"])
        g["brifing"] = dict(brifing) if brifing else None
        g["rapor"] = dict(rapor) if rapor else None
        return g

    @uygulama.get("/api/olaylar")
    def api_olaylar(sonra: int = 0, adet: int = 120):
        ofis = ofis_ac()
        with db.baglanti() as conn:
            rows = conn.execute(
                "SELECT o.id, o.ajan_ad, o.tur, o.govde, o.olusturuldu, g.no AS gorev_no "
                "FROM olay o LEFT JOIN gorev g ON g.id = o.gorev_id "
                "WHERE o.proje_id = ? AND o.id > ? ORDER BY o.id DESC LIMIT ?",
                (ofis.proje_id, sonra, adet)).fetchall()
        return [dict(r) for r in rows][::-1]

    @uygulama.get("/api/hafiza")
    def api_hafiza():
        """HAFIZA: bilgiler (baglariyla), kurallar, adaylar, dersler.

        Cizge istemcide cizilir ama KENARLAR burada, sunucuda cikarilir
        (`bellek.baglar`): brifing secimi hangi baglari izliyorsa panel de
        TAM OLARAK onlari gostermeli. Istemcide ikinci bir ayristirici
        olsaydi ikisi kayar ve cizge, secimin izlemedigi bir bagi
        gosterirdi.
        """
        ofis = ofis_ac()
        with db.baglanti() as conn:
            rows = conn.execute(
                "SELECT konu, icerik, kaynak, gecerli_baslangic, gecerli_bitis "
                "FROM olgu WHERE proje_id = ? ORDER BY konu, gecerli_baslangic DESC",
                (ofis.proje_id,)).fetchall()
            dersler = conn.execute(
                "SELECT id, ajan_ad, ders, tekrar FROM ders WHERE proje_id = ? "
                "ORDER BY tekrar DESC, guncellendi DESC", (ofis.proje_id,)
            ).fetchall()
        hepsi = [dict(r) for r in rows]
        surum = {}
        for o in hepsi:
            a = _bellek.konu_anahtari(o["konu"])
            surum[a] = surum.get(a, 0) + 1
        gecerli = [o for o in hepsi if o["gecerli_bitis"] is None]
        var = {_bellek.konu_anahtari(o["konu"]) for o in gecerli}
        for o in gecerli:
            o["anahtar"] = _bellek.konu_anahtari(o["konu"])
            o["surum"] = surum.get(o["anahtar"], 1)
            # KIRIK BAG bir hata degil bir BILGI: henuz yazilmamis bir konu.
            o["baglar"] = [{"konu": b, "anahtar": _bellek.konu_anahtari(b),
                            "kirik": _bellek.konu_anahtari(b) not in var}
                           for b in _bellek.baglar(o["icerik"])]
        adaylar = {d["id"] for d in ofis.bellek.kural_adaylari()}
        # Eski olgu SILINMEZ, gosterilir -- ama 'gecersiz' olarak. Ajana
        # gitmez, insana gider: "eskiden ne kadardi" sorusu icin.
        return {"gecerli": gecerli,
                "eski": [o for o in hepsi if o["gecerli_bitis"] is not None],
                "kurallar": ofis.bellek.kurallar(),
                "kural_maliyeti": ofis.bellek.kural_maliyeti(),
                "dersler": [dict(d, aday=d["id"] in adaylar) for d in dersler],
                "secim_esigi": _bellek.OLGU_SECIM_ESIGI}

    @uygulama.get("/api/hafiza/gecmis")
    def api_hafiza_gecmis(konu: str):
        ofis = ofis_ac()
        k = ofis.bellek._konu_bul(konu) or konu
        return {"konu": k, "gecmis": ofis.bellek.konu_gecmisi(k)}

    @uygulama.post("/api/bilgi")
    def api_bilgi(govde: BilgiGovdesi):
        """Insanin hafizaya yazdigi bilgi. Kaynak 'insan': ajan onu
        sessizce devremez (`bellek.bilgi_ekle`)."""
        ofis = ofis_ac()
        try:
            r = ofis.bellek.bilgi_ekle(govde.konu, govde.icerik, yazan="insan")
        except BellekHatasi as exc:
            raise HTTPException(400, str(exc))
        return r

    @uygulama.post("/api/kural")
    def api_kural(govde: KuralGovdesi):
        """Kural ekler ya da bir bilgiyi / dersi KURALA YUKSELTIR.

        Panel karar VERMEZ: yalniz-insan kapisi, gerekce ve tekrar
        denetimi `bellek`te. Bu uc insan adina konusur -- lider ya da ajan
        bu uca ulasmaz."""
        ofis = ofis_ac()
        if not govde.gerekce.strip():
            raise HTTPException(400, "Gerekce zorunlu: kural HER brifinge "
                                     "girer; neden konuldugu bilinmeli.")
        try:
            if govde.olgu:
                r = ofis.bellek.olgudan_kural(govde.olgu, govde.gerekce)
            elif govde.ders_id:
                r = ofis.bellek.dersten_kural(govde.ders_id, govde.gerekce)
            else:
                r = ofis.bellek.kural_ekle(govde.metin, govde.gerekce)
        except BellekHatasi as exc:
            raise HTTPException(400, str(exc))
        return r

    @uygulama.post("/api/kural/{kural_id}/kaldir")
    def api_kural_kaldir(kural_id: str, govde: SebepGovdesi):
        ofis = ofis_ac()
        try:
            return ofis.bellek.kural_kaldir(kural_id, govde.sebep)
        except BellekHatasi as exc:
            raise HTTPException(400, str(exc))

    @uygulama.get("/api/kararlar")
    def api_kararlar(adet: int = 50):
        return ofis_ac().bellek.son_kararlar(adet)

    @uygulama.get("/api/raporlar")
    def api_raporlar(adet: int = 30):
        ofis = ofis_ac()
        with db.baglanti() as conn:
            rows = conn.execute(
                "SELECT o.govde, o.ajan_ad, o.olusturuldu, g.no AS gorev_no, "
                "g.baslik FROM olay o LEFT JOIN gorev g ON g.id = o.gorev_id "
                "WHERE o.proje_id = ? AND o.tur = 'rapor' "
                "ORDER BY o.id DESC LIMIT ?", (ofis.proje_id, adet)).fetchall()
        return [dict(r) for r in rows]

    @uygulama.get("/api/hesaplar")
    def api_hesaplar():
        """Butun hesaplar tek listede: durum, pencereler, is sirasi.

        Kullanici (27.09.2026): *"ilerde baska hesaplar olacak, karmasik
        olmasin."* Rayda hesap basina cip yerine tek dugme; tiklayinca bu
        tablo acilir. Olculemeyen uydurulmaz (`olculmedi`).
        """
        return _hesap_tablosu(ofis_ac())

    @uygulama.post("/api/hesaplar/tazele")
    def api_hesaplar_tazele():
        """Insan istedi: saglayicidan SIMDI oku (kota harcamaz)."""
        from . import kullanim as _k
        o = ofis_ac()
        t = _k.tazele(o.db, o.proje_id, fabrika=MOTOR_FABRIKASI, zorla=True)
        tablo = _hesap_tablosu(o, taze=True)
        return {**tablo, "okundu": t.get("okundu", []),
                "okunamadi": t.get("okunamadi", [])}

    @uygulama.get("/api/kullanim")
    def api_kullanim():
        """Hangi hesap bagli · OFIS ne tuketti · ne zaman yenilenir.

        Kullanicinin istegi buydu ve panelde karsiligi yoktu.

        IKI SAYIYI BIRBIRINE KARISTIRMIYORUZ ve bunu SOYLUYORUZ:
        * `pencereler` -- HESABIN TOPLAMI (5 saat / 7 gun yuzdesi),
          saglayicinin KENDI bildirimi; ofis o hesapla tur kostukca
          tazelenir, bu yuzden YASIYLA gelir. (22.09'da burada "ofis
          okuyamaz" yaziyordu -- YANLISTI: CLI her turda bildiriyor,
          ofis okuyup atiyordu. Bkz. `kullanim.py`.)
        * `oturum`/`hafta` -- yalniz OFISIN kendi turlari.
        """
        from . import kullanim as _k
        try:
            # `ofis` her uc noktada AYRI alinir (`ofis_ac()`); kapsamda
            # hazir DURMUYOR. Ilk surumde bunu varsaydim ve panel
            # "kullanim olculemedi: name 'proje_id' is not defined"
            # yazdi -- yani gosterge kendi hatasini gosterdi.
            # *Cikarim yapma, kayda bak* (bu kez kod kaydi).
            ofis = ofis_ac()
            o = _k.ozet(ofis.db, ofis.proje_id)
        except Exception as exc:
            # Patlarsa SESSIZ kalmaz: calismayan bir gosterge,
            # "sorun yok" diyen bir arizadir (`saglik.py` kurali).
            return {"hata": f"kullanim olculemedi: {exc}"}
        y = o["yenilenme"]
        return {
            "hesaplar": _k.hesap_durumu(),
            "pencereler": o["pencereler"],
            "oturum": o["oturum"],
            "hafta": o["hafta"],
            "oturum_saat": o["oturum_saat"],
            "yenilenme": {"ne_zaman": y["ne_zaman"].isoformat(),
                          "kalan_saat": y["kalan_saat"],
                          "kaynak": y["kaynak"]},
            "not": ("Yuzdeler hesabin TOPLAMIDIR ama ancak ofis o hesapla "
                    "tur kostukca tazelenir; arada elle kullandiysan gercek "
                    "daha yuksektir. Tur/jeton satirlari yalniz OFISIN "
                    "kendi turlaridir."),
        }

    @uygulama.get("/api/efor")
    def api_efor():
        """Efor modu: zorluga gore mi, butun turlar sabit bir seviyede mi.

        Panel KARAR VERMEZ: yalnizca insanin sectigini ayara yazar; kural
        (hangi tur hangi eforda kosar) `roller.tur_eforu`da tek yerde.
        """
        from . import roller as _r
        ofis = ofis_ac()
        return {"mod": _r.efor_modu(ofis.db, ofis.proje_id),
                "tavan": _r.efor_tavani(ofis.db, ofis.proje_id),
                "modlar": list(_r.EFOR_MODLARI)}

    @uygulama.post("/api/efor")
    def api_efor_yaz(govde: EforGovdesi):
        from . import roller as _r
        ofis = ofis_ac()
        try:
            _r.efor_modu_yaz(ofis.db, ofis.proje_id, govde.mod)
        except _r.RolHatasi as exc:
            raise HTTPException(400, str(exc))
        ofis.db.olay_yaz(ofis.proje_id, "efor_modu", f"{govde.mod} (panelden)")
        return {"mod": govde.mod}

    @uygulama.get("/api/degisim")
    def api_degisim(adet: int = 80, gorev_no: int = 0):
        """Diskte OLCULEN degisiklikler -- ajanin anlattigi degil.

        Panelin Kod bolumu bunu okur. Oturumlar arasi acik kalmasi bir
        arayuz numarasi degil, verinin nerede yasadiginin sonucu: fark
        bellekte degil DEFTERDE durur, yani tarayiciyi kapatmak dun
        gece kosan bir isin degisikligini kaybettirmez.

        `kanat_id` satira eklenir cunku orta sutun kanata gore
        suzuluyor; suzmeyi istemci yapar, iki ayri sorgu tutmak ayni
        bilgiyi iki yerde tutmak olurdu.
        """
        ofis = ofis_ac()
        sorgu = (
            "SELECT d.*, g.no AS gorev_no, g.baslik AS gorev_baslik, "
            "g.kanat_id AS kanat_id, g.ek_klasorler AS ek_klasorler "
            "FROM degisim d LEFT JOIN gorev g ON g.id = d.gorev_id "
            "WHERE d.proje_id = ?")
        par = [ofis.proje_id]
        if gorev_no:
            sorgu += " AND g.no = ?"
            par.append(int(gorev_no))
        sorgu += " ORDER BY d.olusturuldu DESC, d.rowid DESC LIMIT ?"
        par.append(int(adet))
        with db.baglanti() as conn:
            rows = conn.execute(sorgu, par).fetchall()
        kayitlar = []
        for r in rows:
            d = dict(r)
            d["beyan_disi"] = bool(d["beyan_disi"])
            d["atif_belirsiz"] = bool(d.get("atif_belirsiz"))
            # Olculmeyen yerler SOYLENIR. Bos bir Kod bolumu gorup
            # "ajan hicbir sey yazmadi" diye okumak, yanlis gosteren
            # gostergenin ta kendisi olurdu.
            try:
                disar = json.loads(d.pop("ek_klasorler", None) or "[]")
            except (TypeError, ValueError):
                disar = []
            d["kapsam_notu"] = degisim.kapsam_notu(disar)
            kayitlar.append(d)
        return {"kok": ofis.tahta.kok_klasor(), "kayitlar": kayitlar}

    @uygulama.get("/api/canli")
    def api_canli(adet: int = 40):
        """CANLI IZLEME: tur SURERKEN diskte olculen ara fark.

        Rakipte ajan yazdikca dosya editorde kendiliginden aciliyor.
        Bizde kaynak yine DISK (motordan ve ajanin sozunden bagimsiz,
        `degisim.CanliIzleyici`), ve kayit ARA olcumdur: tur bitince
        silinir, yerini `/api/degisim`deki kesin kayit alir.

        SALT OKUNUR ve bu bilincli: panelden dosya duzenlemek, yazma
        kilidinin gormedigi ikinci bir yazar olurdu (Yasa 1).

        Yalniz HALA KOSAN islerin kaydi doner (`canli_oku`): surec dusup
        silme hic kosmadiysa bitmis bir turun ara olcumunu "canli" diye
        gostermek yanlis gosteren gosterge olurdu.
        """
        ofis = ofis_ac()
        adet = max(1, min(int(adet), 200))
        satirlar = degisim.canli_oku(db, ofis.proje_id, limit=adet)
        gorevler = {}
        with db.baglanti() as conn:
            for s in satirlar:
                gid = s["gorev_id"]
                if gid not in gorevler:
                    r = conn.execute(
                        "SELECT no, baslik, kanat_id FROM gorev WHERE id = ?",
                        (gid,)).fetchone()
                    gorevler[gid] = dict(r) if r else {}
        kayitlar = []
        for s in satirlar:
            g = gorevler.get(s["gorev_id"]) or {}
            s["gorev_no"] = g.get("no")
            s["gorev_baslik"] = g.get("baslik", "")
            s["kanat_id"] = g.get("kanat_id")
            s["beyan_disi"] = bool(s["beyan_disi"])
            s["atif_belirsiz"] = bool(s["atif_belirsiz"])
            kayitlar.append(s)
        return {"kayitlar": kayitlar,
                "aralik_sn": degisim.CANLI_ARALIK_S}


    # ---------------------------------------------------------------
    # KABIN -- panelin ICINDE gercek tarayici
    # ---------------------------------------------------------------
    #
    # Kullanici: *"sistemden cikip chrome acip ugrasmak istemem."*
    #
    # `iframe` ile YAPILAMAZ ve bu OLCULDU: admin.shopify.com,
    # mail.google.com, www.google.com hepsi `X-Frame-Options:
    # SAMEORIGIN`. Bir sure bundan "ancak Tauri ile olur" sonucunu
    # cikardim -- YANLISTI. ChatGPT'nin ajan tarayicisi da iframe
    # kullanmaz: uzaktaki tarayicinin KARELERINI akitir, ve o yol bir
    # web sayfasinda aciktir.
    #
    # OLCULDU (22.09.2026): kare ~16,8 KB · ~0,03 MB/sn ·
    # `Input.dispatchMouseEvent` ile tiklama hatasiz. Yani izlenmiyor,
    # KULLANILIYOR.
    #
    # BASSIZ OLCUMU (ayni gun, kusur duzeltildikten sonra): gorunur
    # pencere 0 (PID suzgecli) · ilk kare 20 ms -- basliyken 445 ms'ti.
    # Kabin artik gercekten panelin icinde; oncesinde ayri bir
    # Chrome'un aynasiydi ve bunu kullanici kullanirken gordu.

    # KABIN KAYDA GECER (24.09.2026). Acilis, kapanis ve KENDILIGINDEN
    # olum hicbir yere yazilmiyordu; kullanici "calismiyor" dediginde
    # neyin oldugunu soyleyecek bir iz yoktu. Kayit ofisin defterine
    # yazilamazsa (acik proje yok) kabin yine calisir -- kayit bir kolaylik.
    def _kabin_kaydi(tur: str, govde: str) -> None:
        try:
            o = ofis_ac()
            o.db.olay_yaz(o.proje_id, tur, govde)
        except Exception:  # noqa: BLE001 -- kabin kayit yuzunden olmez
            pass

    def _kabin_olumu() -> None:
        o = _kabin.olum()
        if o:
            _kabin_kaydi("kabin_dustu",
                         f"Kabin Chrome'u kendiliginden kapandi (cikis "
                         f"{o['cikis']}). {o['son_hata'][-300:]}".strip())

    @uygulama.get("/api/kabin")
    def api_kabin():
        _kabin_olumu()
        return _kabin.durum()

    @uygulama.post("/api/kabin/ac")
    def api_kabin_ac(govde: KabinGovdesi):
        _kabin_olumu()
        try:
            d = _kabin.ac(govde.url or "about:blank",
                          gorunur=bool(govde.gorunur))
        except KabinHatasi as exc:
            # UYDURMAZ: acilmadiysa sebebi soylenir -- ve kayda gecer.
            _kabin_kaydi("kabin_dustu", f"Kabin acilamadi: {exc}"[:500])
            raise HTTPException(status_code=503, detail=str(exc))
        _kabin_kaydi("kabin_acildi",
                     "Kabin acildi" + (" (panel acti)" if d.get("bizim_surec")
                                       else " (zaten acikti, baglanildi)"))
        return d

    @uygulama.get("/api/kabin/izle")
    def api_kabin_izle():
        from .orkestra import kabin_izle_acik_mi
        o = ofis_ac()
        return {"acik": kabin_izle_acik_mi(o.db, o.proje_id)}

    @uygulama.post("/api/kabin/izle")
    def api_kabin_izle_ayarla(govde: KabinIzleGovdesi):
        """"Ajanlar kabinde" anahtari. Acmak bir YETKI genisletmesidir:
        kabinde girdigin hesaplar tarayicili ise acilir. Karar insanin,
        kayda gecer; koruma tiklamada (riskli eylem onaya duser) durur."""
        from .orkestra import KABIN_IZLE_ANAHTARI
        o = ofis_ac()
        o.db.ayar_yaz(o.proje_id, KABIN_IZLE_ANAHTARI,
                      "acik" if govde.acik else "kapali")
        o.db.olay_yaz(o.proje_id, "kabin_izle",
                      "Ajanlar kabinde: ACIK -- tarayicili bir is panelde canli "
                      "kosacak, kabindeki oturumlarla (riskli tiklama onaya duser)"
                      if govde.acik else
                      "Ajanlar kabinde: KAPALI -- ajanlar kendi gorunmez "
                      "tarayicilarini kullanir", ajan_ad="insan")
        return {"acik": bool(govde.acik)}

    @uygulama.post("/api/kabin/kapat")
    def api_kabin_kapat():
        d = _kabin.kapat()
        _kabin_kaydi("kabin_kapandi", "Kabin panelden kapatildi"
                     + (" -- ama baska bir surec hala acik tutuyor"
                        if d.get("acik") else ""))
        return d

    @uygulama.websocket("/ws/kabin")
    async def ws_kabin(soket: WebSocket):
        """Kabinin karelerini panele akitir, girdiyi geri tasir.

        SAYFAYA HAM CDP VERILMEZ. Istemci yalnizca kucuk bir sozluk
        konusur (fare · tekerlek · tus · metin · git · yenile · geri) ve
        burada CDP'ye CEVRILIR. Ham boru acsaydik panel sayfasi,
        tarayiciyi surmenin IKINCI bir kapisi olurdu -- `Filesystem MCP`
        icin verdigimiz kararin aynisi: *ikinci bir kapi acan sey
        alinmaz.*

        INSANIN GEZINMESI KAPIDAN GECMEZ ve bu bilincli: `--allowed-
        origins` AJANI kisitlar, insani degil. Yetki insandan gelir
        (klasor ve kadro kurallarindaki ayni ilke). Ajan ayni tarayiciya
        bagliyken kapi ONUN icin tutmaya devam ediyor -- olculdu.
        """
        await soket.accept()
        try:
            hedef = kabin.sayfa_ws(_kabin.kapi)
        except KabinHatasi as exc:
            await soket.send_json({"tur": "hata", "govde": str(exc)})
            await soket.close()
            return

        sayac = {"n": 0}
        olcu = {"en": 1280, "boy": 800}

        try:
            import websockets
        except ImportError:                       # pragma: no cover
            await soket.send_json(
                {"tur": "hata", "govde": "websockets kurulu degil."})
            await soket.close()
            return

        async with websockets.connect(hedef, max_size=None) as cdp:

            # Cevabi beklenen istekler: CDP kimligi -> kalici mi.
            bekleyen = {}

            async def gonder(yontem, params=None):
                sayac["n"] += 1
                await cdp.send(json.dumps(
                    {"id": sayac["n"], "method": yontem,
                     "params": params or {}}))
                return sayac["n"]

            await gonder("Page.enable")
            await gonder("Runtime.enable")
            # ILK ADRES de sorulur. Olculdu (24.09): kabin panelden ONCE
            # acildiysa adres yalniz gezinmede geldigi icin cubuk BOS
            # kaliyordu -- sayfa acikken "adres yok" diyen bir gosterge.
            bekleyen[await gonder("Runtime.evaluate",
                                  {"expression": "location.href",
                                   "returnByValue": True})] = "adres"
            await gonder("Page.startScreencast",
                         {"format": "jpeg", "quality": 70,
                          "maxWidth": 1600, "maxHeight": 1000})

            async def kabinden_panele():
                async for ham in cdp:
                    v = json.loads(ham)
                    y = v.get("method")
                    if bekleyen.get(v.get("id")) == "adres":
                        bekleyen.pop(v["id"])
                        a = (((v.get("result") or {}).get("result") or {})
                             .get("value"))
                        if isinstance(a, str):
                            await soket.send_json({"tur": "adres", "govde": a})
                    elif v.get("id") in bekleyen:
                        kalici = bekleyen.pop(v["id"])
                        sonuc = (v.get("result") or {})
                        deger = None if sonuc.get("exceptionDetails") else (
                            (sonuc.get("result") or {}).get("value"))
                        # SAYFANIN dondurdugu de guvenilmez: suzgecten gecer.
                        await soket.send_json(
                            {"tur": "oge", "kalici": kalici,
                             "oge": kabin.oge_ozeti(deger, olcu["en"],
                                                    olcu["boy"])})
                    elif y == "Page.screencastFrame":
                        p = v["params"]
                        m = p.get("metadata") or {}
                        olcu["en"] = m.get("deviceWidth") or olcu["en"]
                        olcu["boy"] = m.get("deviceHeight") or olcu["boy"]
                        await soket.send_json(
                            {"tur": "kare", "govde": p["data"],
                             "en": olcu["en"], "boy": olcu["boy"]})
                        sayac["n"] += 1
                        await cdp.send(json.dumps(
                            {"id": sayac["n"],
                             "method": "Page.screencastFrameAck",
                             "params": {"sessionId": p["sessionId"]}}))
                    elif y == "Page.frameNavigated" and not (
                            v["params"]["frame"].get("parentId")):
                        # URL cubugu GERCEGI gostersin: yonlendirme
                        # olursa yazdigin adres degil GIDILEN adres.
                        await soket.send_json(
                            {"tur": "adres",
                             "govde": v["params"]["frame"].get("url", "")})

            async def panelden_kabine():
                while True:
                    istek = await soket.receive_json()
                    t = istek.get("tur")
                    if t == "fare":
                        # Koordinat NORMALLESTIRILMIS gelir (0..1).
                        # Piksel gonderseydik panel yeniden
                        # boyutlandiginda tiklama kayardi ve sebebi
                        # gorunmezdi.
                        x = float(istek.get("x", 0)) * olcu["en"]
                        yk = float(istek.get("y", 0)) * olcu["boy"]
                        await gonder("Input.dispatchMouseEvent", {
                            "type": {"bas": "mousePressed",
                                     "birak": "mouseReleased",
                                     "hareket": "mouseMoved"}.get(
                                         istek.get("alt"), "mouseMoved"),
                            "x": x, "y": yk,
                            "button": istek.get("dugme", "left"),
                            "buttons": int(istek.get("dugmeler", 0)),
                            "clickCount": int(istek.get("tik", 1)),
                        })
                    elif t == "tekerlek":
                        await gonder("Input.dispatchMouseEvent", {
                            "type": "mouseWheel",
                            "x": float(istek.get("x", 0)) * olcu["en"],
                            "y": float(istek.get("y", 0)) * olcu["boy"],
                            "deltaX": float(istek.get("dx", 0)),
                            "deltaY": float(istek.get("dy", 0)),
                        })
                    elif t == "tus":
                        await gonder("Input.dispatchKeyEvent", {
                            "type": "keyDown" if istek.get("alt") == "bas"
                                    else "keyUp",
                            "key": istek.get("tus", ""),
                            "code": istek.get("kod", ""),
                            "windowsVirtualKeyCode": int(istek.get("kk", 0)),
                            "nativeVirtualKeyCode": int(istek.get("kk", 0)),
                            # Basilabilir karakter `text` ile gider.
                            # Yalniz sanal kod gonderseydik harfler
                            # sayfaya hic yazilmazdi -- tuslar "calisiyor"
                            # gorunur, yazi cikmazdi.
                            "text": str(istek.get("metin", "")),
                        })
                    elif t == "metin":
                        await gonder("Input.insertText",
                                     {"text": str(istek.get("govde", ""))})
                    elif t == "git":
                        await gonder("Page.navigate",
                                     {"url": str(istek.get("url", ""))})
                    elif t == "yenile":
                        await gonder("Page.reload", {})
                    elif t == "geri":
                        await gonder("Runtime.evaluate",
                                     {"expression": "history.back()"})
                    elif t == "ileri":
                        await gonder("Runtime.evaluate",
                                     {"expression": "history.forward()"})
                    elif t == "oge":
                        # OGE SECICI. Istemci yalniz IKI SAYI gonderir;
                        # sayfada kosan ifade sunucuda sabittir
                        # (`kabin.oge_ifadesi`). Salt okunur: tiklamaz,
                        # yazmaz, giris degeri okumaz.
                        try:
                            nx = min(max(float(istek.get("x", 0)), 0.0), 1.0)
                            ny = min(max(float(istek.get("y", 0)), 0.0), 1.0)
                            ifade = kabin.oge_ifadesi(nx * olcu["en"],
                                                      ny * olcu["boy"])
                        except (TypeError, ValueError, KabinHatasi):
                            continue
                        i = await gonder("Runtime.evaluate",
                                         {"expression": ifade,
                                          "returnByValue": True})
                        bekleyen[i] = bool(istek.get("sec"))
                    # Bilinmeyen tur SESSIZCE dusurulur -- sozluk bir
                    # KAPIDIR; genisletmek acik bir karar olmali.

            try:
                await asyncio.gather(kabinden_panele(), panelden_kabine())
            except WebSocketDisconnect:
                pass
            except Exception:
                # Kopru koparsa panel olmez; kabin acik kalir.
                pass

    @uygulama.get("/api/bekleyenler")
    def api_bekleyenler():
        ofis = ofis_ac()
        # `sorular` insanin EYLEM kuyrugu: yalnizca ona dusenler.
        # `danisilanlar` ayri anahtarda, cunku insan onlari GORMELI ama
        # CEVAPLAMAMALI -- ofis kendi icinde danisiyor demektir. Ayni
        # kuyruga koymak, insana kendisine dusmeyen isi gosterirdi;
        # tamamen gizlemek ise ofisi sessiz kilardi.
        return {"sorular": ofis.postane.insan_bekleyenler(),
                "danisilanlar": ofis.postane.ajana_bekleyenler(),
                "onaylar": _onaylar_giris_ile(ofis.postane.bekleyen_onaylar())}

    # -- insanin mudahalesi ------------------------------------------------

    def _surdur_gerekirse(ofis, istendi: bool) -> dict:
        """Insan bir istegi cevapladiysa ve baska istek KALMADIYSA halka
        doner. SONUC SOYLENIR: surdurulmediyse sebebi yazilir -- insan
        "neden hicbir sey olmadi" diye sormamali.

        Baska istek bekliyorsa DONDURULMEZ: o isler zaten ilerleyemez ve
        halka "ilerleme yok" deyip durur; bir tur bosuna jeton yakar.
        """
        if not istendi:
            return {"surduruldu": False, "sebep": "istenmedi"}
        kalan = (len(ofis.postane.insan_bekleyenler())
                 + len(ofis.postane.bekleyen_onaylar()))
        if kalan:
            return {"surduruldu": False,
                    "sebep": f"{kalan} istek daha SENI bekliyor; hepsi "
                             "cevaplaninca halka doner (ya da 'surdur')."}
        if _KOSU["calisiyor"]:
            return {"surduruldu": False,
                    "sebep": "ofis zaten kosuyor: " + (_KOSU["mesaj"] or "?")}
        # DURDURULMUS ofis kendiliginden KALKMAZ: insan "dur" dedi; son
        # cevabi vermesi "devam et" demek degildir. Surdur dugmesi acik.
        if durdurma_istendi(ofis.db, ofis.proje_id):
            return {"surduruldu": False,
                    "sebep": "ofis DURDURULMUS; devam icin 'Surdur'e bas."}
        _KOSU.update(dur=False, calisiyor=True, mesaj="halka surduruluyor")
        threading.Thread(target=_halkayi_kostur, args=(db.yol, proje_ad),
                         daemon=True).start()
        return {"surduruldu": True, "sebep": ""}

    @uygulama.post("/api/soru/{mesaj_id}/cevap")
    def api_cevapla(mesaj_id: str, govde: CevapGovdesi):
        ofis = ofis_ac()
        try:
            r = ofis.postane.cevapla(mesaj_id, govde.metin)
        except PostaneHatasi as exc:
            raise HTTPException(400, str(exc))
        return {**dict(r or {}), **_surdur_gerekirse(ofis, govde.surdur)}

    @uygulama.post("/api/onay/{onay_id}")
    def api_onay(onay_id: str, govde: OnayGovdesi):
        # Kapsam SUNUCUDA dogrulanir: bilinmeyen bir deger sessizce
        # `eylem`e dusseydi, insan "is boyunca" verdigini sanip her
        # seferinde yeniden sorulurdu (ya da tersi).
        if govde.kapsam not in ("eylem", "is"):
            raise HTTPException(400, "kapsam 'eylem' ya da 'is' olmali.")
        ofis = ofis_ac()
        from . import giris as _giris
        # GIRIS ISTEGI siradan onay gibi cevaplanamaz: "yaptim" OLCULUR
        # ve is kabine/baglayiciya tasinir. Arka kapidan gecmesin.
        if any(o["id"] == onay_id and _giris.giris_mi(o)
               for o in ofis.postane.bekleyen_onaylar()):
            try:
                r = _giris.cevapla(ofis, onay_id, yapildi=govde.onayla,
                                   not_=govde.not_)
            except _giris.GirisHatasi as exc:
                raise HTTPException(400, str(exc))
            return {**dict(r or {}), **_surdur_gerekirse(ofis, govde.surdur)}
        try:
            r = ofis.postane.onay_cevapla(
                onay_id, onayla=govde.onayla, not_=govde.not_,
                kapsam=govde.kapsam)
        except PostaneHatasi as exc:
            raise HTTPException(400, str(exc))
        return {**dict(r or {}), **_surdur_gerekirse(ofis, govde.surdur)}

    @uygulama.post("/api/devam")
    def api_devam():
        """Halkayi elle surdur -- `kabuk devam`. Tek ucus, tavanli."""
        ofis = ofis_ac()
        if _KOSU["calisiyor"]:
            raise HTTPException(
                409, "Ofis zaten kosuyor: " + (_KOSU["mesaj"] or "?"))
        acik = [g for g in ofis.tahta.liste()
                if g["durum"] not in ("bitti", "iptal")]
        if not acik:
            # Acik is yokken donen halka "ilerleme yok" der ve durur --
            # bosuna tur. Bunu SOYLERIZ, sessizce dugmeyi yutmayiz.
            raise HTTPException(400, "Acik is yok; surdurulecek bir sey yok. "
                                     "Yeni is icin lidere yaz.")
        # Insan yeni bir sey baslatiyor: eski durdurma istegi KALKAR.
        durdurma_temizle(ofis.db, ofis.proje_id)
        # Patron Surdur'e basti: TAKILAN islerin bekleme sayaci sifirlanir.
        ofis.db.olay_yaz(ofis.proje_id, "surdur_istendi", "Patron Surdur'e basti", ajan_ad="insan")
        _KOSU.update(dur=False, calisiyor=True, mesaj="halka surduruluyor")
        threading.Thread(target=_halkayi_kostur, args=(db.yol, proje_ad),
                         daemon=True).start()
        return {"kosuyor": True, "acik_is": len(acik)}

    # -- DEVRAL (E18): insan ajanin isini gercek terminalde alir ----------
    @uygulama.post("/api/gorev/{no}/devral")
    def api_devral(no: int, govde: DevralGovdesi, istek: Request):
        if istek.client and istek.client.host not in TERMINAL_YEREL:
            raise HTTPException(403, "Terminal yalniz bu bilgisayardan acilir.")
        from . import devral as _dv
        ofis = ofis_ac()
        try:
            return _dv.devral(ofis, no, fabrika=MOTOR_FABRIKASI or motor_ac,
                              sutun=govde.sutun, satir=govde.satir)
        except (_dv.DevralHatasi, TahtaHatasi) as exc:
            raise HTTPException(400, str(exc)) from exc

    @uygulama.post("/api/gorev/{no}/geri_ver")
    def api_geri_ver(no: int, govde: GeriVerGovdesi):
        from . import devral as _dv
        ofis = ofis_ac()
        try:
            return _dv.geri_ver(ofis, no, not_=govde.not_)
        except (_dv.DevralHatasi, TahtaHatasi) as exc:
            raise HTTPException(400, str(exc)) from exc

    @uygulama.get("/api/devralinanlar")
    def api_devralinanlar():
        from . import devral as _dv
        from . import terminal as _tr
        ofis = ofis_ac()
        from .motor import tui as _tui
        # GERCEK TERMINAL KIPI: canli ajan terminalleri (bu surecte).
        # Halka kabuktan baslatildiysa terminal O surectedir ve burada
        # GORUNMEZ -- panel uydurmaz, liste bos gelir.
        acik = [{"ajan": x["ajan"], "gorev": x["gorev"], "oturum": x["oturum_id"]}
                for x in _tui.acik_oturumlar()]
        return {"isler": _dv.devralinanlar(ofis.db, ofis.proje_id),
                "pty": _tr.pty_durumu() or "hazir", "tui": acik}

    @uygulama.post("/api/ek")
    def api_ek(govde: EkGovdesi):
        """Sohbete dosya/gorsel: proje kokunun gizli `.ofis/ekler/` klasorune yazilir
        (kural `ofis/ekler.py`de; panel yalniz ulasan kapi)."""
        import base64
        import binascii
        from . import ekler as _ek
        if len(govde.veri) > _ek.AZAMI_BAYT * 4 // 3 + 16:
            raise HTTPException(400, f"Dosya cok buyuk; sinir {_ek.AZAMI_BAYT // 1024 // 1024} MB.")
        try:
            veri = base64.b64decode(govde.veri, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(400, "Dosya okunamadi (bozuk veri).")
        try:
            return _ek.kaydet(ofis_ac(), govde.ad, veri)
        except _ek.EkHatasi as exc:
            raise HTTPException(400, str(exc))

    @uygulama.get("/api/ek/{ad}")
    def api_ek_oku(ad: str):
        from . import ekler as _ek
        try:
            yol = _ek.dosya(ofis_ac(), ad)
        except _ek.EkHatasi as exc:
            raise HTTPException(404, str(exc))
        return FileResponse(yol)

    @uygulama.get("/api/terminal_kipi")
    def api_terminal_kipi():
        """Ajanlar hangi kipte kosar: 'arka' (yapili akis) | 'gercek'
        (Claude/Codex'in kendi terminali). Kural koltukta (`_motor_ac`);
        panel yalniz ayari okur/yazar."""
        from . import terminal as _tr
        from .koltuk import Koltuk
        ofis = ofis_ac()
        return {"kip": ofis.db.ayar_oku(ofis.proje_id, Koltuk.TERMINAL_KIPI, "arka"),
                "pty": _tr.pty_durumu() or "hazir"}

    @uygulama.post("/api/terminal_kipi")
    def api_terminal_kipi_yaz(govde: KipGovdesi):
        from . import terminal as _tr
        from .koltuk import Koltuk
        if govde.kip not in ("arka", "gercek"):
            raise HTTPException(400, "Kip 'arka' ya da 'gercek' olmali.")
        if govde.kip == "gercek" and _tr.pty_durumu():
            raise HTTPException(400, _tr.pty_durumu())
        ofis = ofis_ac()
        ofis.db.ayar_yaz(ofis.proje_id, Koltuk.TERMINAL_KIPI, govde.kip)
        ofis.db.olay_yaz(ofis.proje_id, "terminal_kipi",
                         f"{govde.kip} (panelden) -- sonraki turlardan itibaren")
        return {"kip": govde.kip}

    @uygulama.websocket("/ws/tui/{oturum}")
    async def ws_tui(soket: WebSocket, oturum: str):
        """Ajanin CANLI gercek terminali: ekran -> panel, tuslar -> terminal.
        Insan araya yazabilir (terminalde yazar gibi). Yalniz bu bilgisayar."""
        from .motor import tui as _tui
        await soket.accept()
        if soket.client and soket.client.host not in TERMINAL_YEREL:
            await soket.send_json({"tur": "hata",
                                   "govde": "Terminal yalniz bu bilgisayardan acilir."})
            await soket.close()
            return
        t = _tui.oturum_terminali(oturum)
        if t is None:
            await soket.send_json({"tur": "hata", "govde": "Bu ajan terminali kapali."})
            await soket.close()
            return
        await _terminal_kopru(soket, t)

    @uygulama.websocket("/ws/terminal/{no}")
    async def ws_terminal(soket: WebSocket, no: int):
        """Devralinmis isin terminali: ekran -> panel, tuslar -> terminal.

        Sozluk kucuk: `girdi` (tuslar) ve `boyut` (sutun/satir). Yeniden
        baglanan panel son ekran gecmisini alir -- bos acilmaz."""
        from . import terminal as _tr
        await soket.accept()
        if soket.client and soket.client.host not in TERMINAL_YEREL:
            await soket.send_json({"tur": "hata",
                                   "govde": "Terminal yalniz bu bilgisayardan acilir."})
            await soket.close()
            return
        ofis = ofis_ac()
        try:
            gid = ofis.tahta.gorev(no)["id"]
        except TahtaHatasi as exc:
            await soket.send_json({"tur": "hata", "govde": str(exc)})
            await soket.close()
            return
        acik = _tr.al(gid)
        if not acik or not acik["terminal"].canli():
            await soket.send_json({"tur": "hata",
                                   "govde": "Bu is icin acik terminal yok."})
            await soket.close()
            return
        await _terminal_kopru(soket, acik["terminal"])

    # -- KONSOL: ofisten bagimsiz terminal (28.09) -----------------------
    @uygulama.post("/api/konsol")
    def api_konsol_ac(govde: KonsolGovdesi, istek: Request):
        if istek.client and istek.client.host not in TERMINAL_YEREL:
            raise HTTPException(403, "Terminal yalniz bu bilgisayardan acilir.")
        from . import konsol as _ks
        try:
            return _ks.ac(ofis_ac(), govde.klasor, govde.motor,
                          fabrika=MOTOR_FABRIKASI or motor_ac,
                          sutun=govde.sutun, satir=govde.satir)
        except _ks.KonsolHatasi as exc:
            raise HTTPException(400, str(exc)) from exc

    @uygulama.get("/api/konsol")
    def api_konsol_liste():
        from . import konsol as _ks
        from . import terminal as _tr
        return {"konsollar": _ks.liste(), "pty": _tr.pty_durumu() or "hazir",
                "motorlar": ["powershell"] + sorted(
                    m for m, var in musait_motorlar().items() if var and m != "sahte"),
                "oneriler": _ks.oneriler(ofis_ac())}

    @uygulama.get("/api/denetim")
    def api_denetim(sinif: str = "", ajan: str = "", gorev: int = None, azami: int = 300):
        """Denetim kaydi (F3 / E27): kim, neyi, hangi yetkiyle. Yeni kayit
        tutmaz; olay + onay tablolarini tek listeye toplar."""
        from . import denetim as _dn
        if sinif and sinif not in _dn.SINIFLAR:
            raise HTTPException(400, f"sinif: {', '.join(_dn.SINIFLAR)} ya da bos")
        ofis = ofis_ac()
        s = _dn.kayit(ofis, sinif=sinif, ajan=ajan, gorev_no=gorev,
                      azami=max(1, min(int(azami), 1000)))
        return {"satirlar": s, "ozet": _dn.ozet(_dn.kayit(ofis))}

    @uygulama.get("/api/motor_karti")
    def api_motor_karti():
        """Durust motor karti (E60): her motor neyi yapar, neyi YAPAMAZ --
        motor matrisinin son olcumunden; olcum yoksa 'olculmedi' der."""
        from . import motor_karti as _mk
        return {"kartlar": _mk.kartlar(fabrika=MOTOR_FABRIKASI or motor_ac)}

    @uygulama.post("/api/konsol/gozat")
    async def api_konsol_gozat(istek: Request):
        # Pencere INSANIN masaustunde acilir: yalniz bu bilgisayardan.
        if istek.client and istek.client.host not in TERMINAL_YEREL:
            raise HTTPException(403, "Klasor secme yalniz bu bilgisayardan.")
        from . import konsol as _ks
        try:
            govde = await istek.json()
        except ValueError:
            govde = {}
        baslangic = str((govde or {}).get("baslangic") or "")
        try:
            yol = await asyncio.get_running_loop().run_in_executor(
                None, lambda: _ks.gozat(baslangic))
        except _ks.KonsolHatasi as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"yol": yol}

    @uygulama.post("/api/konsol/{kimlik}/kapat")
    def api_konsol_kapat(kimlik: str):
        from . import konsol as _ks
        try:
            return _ks.kapat(ofis_ac(), kimlik)
        except _ks.KonsolHatasi as exc:
            raise HTTPException(400, str(exc)) from exc

    @uygulama.websocket("/ws/konsol/{kimlik}")
    async def ws_konsol(soket: WebSocket, kimlik: str):
        from . import terminal as _tr
        await soket.accept()
        if soket.client and soket.client.host not in TERMINAL_YEREL:
            await soket.send_json({"tur": "hata",
                                   "govde": "Terminal yalniz bu bilgisayardan acilir."})
            await soket.close()
            return
        acik = _tr.al(kimlik)
        if not acik or not acik.get("konsol") or not acik["terminal"].canli():
            await soket.send_json({"tur": "hata", "govde": "Bu konsol kapali."})
            await soket.close()
            return
        await _terminal_kopru(soket, acik["terminal"])

    async def _terminal_kopru(soket: WebSocket, t):
        """Terminal <-> panel koprusu (devral ve konsol AYNI kopruyu
        kullanir -- iki kopya olsaydi biri duzeltilir oteki unutulurdu).
        Sozluk kucuk: `girdi` ve `boyut`; bilinmeyen tur dusurulur."""
        from . import terminal as _tr
        dongu = asyncio.get_running_loop()
        kuyruk: asyncio.Queue = asyncio.Queue()

        def gelen(veri):
            dongu.call_soon_threadsafe(kuyruk.put_nowait, veri)

        gecmis = t.dinle(gelen)
        try:
            await soket.send_json({"tur": "veri", "govde": gecmis})

            async def terminalden():
                while True:
                    veri = await kuyruk.get()
                    if veri is None:
                        await soket.send_json({"tur": "kapandi"})
                        return
                    await soket.send_json({"tur": "veri", "govde": veri})

            async def panelden():
                while True:
                    istek = await soket.receive_json()
                    tur = istek.get("tur")
                    if tur == "girdi":
                        try:
                            t.yaz(str(istek.get("govde") or ""))
                        except _tr.TerminalHatasi:
                            return
                    elif tur == "boyut":
                        t.boyutla(istek.get("sutun") or 120, istek.get("satir") or 32)
                    # Bilinmeyen tur SESSIZCE dusurulur (kabin ile ayni kural).

            gorevler = [asyncio.ensure_future(terminalden()),
                        asyncio.ensure_future(panelden())]
            await asyncio.wait(gorevler, return_when=asyncio.FIRST_COMPLETED)
            for g in gorevler:
                g.cancel()
        except WebSocketDisconnect:
            pass
        except Exception:                          # noqa: BLE001 -- panel olmesin
            pass
        finally:
            t.birak(gelen)

    @uygulama.post("/api/durdur")
    def api_durdur():
        """Ofisi DURDURUR: kosan turlar KESILIR, yenisi baslamaz.

        Istek DEFTERE yazilir (`koltuk.durdurma_iste`): kabuktan baslatilan
        halka da gorur ve koltuk kosan turu kanal uzerinden aninda keser
        (olculdu: claude 8,1 sn). Kanal tasiyamayan motorda tur bitince
        durulur ve bu SOYLENIR. Durdurulan is ariza sayilmaz: 'Surdur'
        ayni ajanla, ayni oturumdan devam eder.
        """
        ofis = ofis_ac()
        kosan = [g for g in ofis.tahta.liste() if g["durum"] == "calisiyor"]
        if not _KOSU["calisiyor"] and not kosan:
            raise HTTPException(400, "Kosan bir sey yok; durdurulacak bir sey "
                                     "yok.")
        _KOSU["dur"] = True
        durdurma_iste(ofis.db, ofis.proje_id, "insan (panel)")
        return {"durduruluyor": True,
                "not": "Kosan turlar kesiliyor (kismi kanit korunur). Yarim "
                       "kalan is 'Surdur' ile kaldigi yerden devam eder."}

    @uygulama.post("/api/izin/{izin_id}/kaldir")
    def api_izin_kaldir(izin_id: str, govde: SebepGovdesi):
        """Patronun verdigi izni geri alir. Sebep zorunlu; kural
        `izin.kaldir`da (panel yalniz ona ulasan bir kapi)."""
        from . import izin as izin_mod
        ofis = ofis_ac()
        try:
            k = izin_mod.kaldir(db, ofis.proje_id, izin_id, sebep=govde.sebep)
        except izin_mod.IzinHatasi as exc:
            raise HTTPException(400, str(exc))
        return {"id": k["id"], "desen": k["desen"]}

    @uygulama.post("/api/gorev/{no}/iptal")
    def api_iptal(no: int, govde: SebepGovdesi):
        """Yarim kalan isi iptal eder ve KILITLERINI birakir. Birakilan
        kilitler OLCULUR, iddia edilmez (`kabuk iptal` ile ayni kural)."""
        if not govde.sebep.strip():
            raise HTTPException(400, "Sebep zorunlu: gerekcesiz iptal, alti ay "
                                     "sonra 'bu is neden yarim kaldi' sorusunu "
                                     "cevapsiz birakir.")
        ofis = ofis_ac()
        def kilitler(gid):
            with ofis.db.baglanti() as conn:
                return {r["yol_oneki"] for r in conn.execute(
                    "SELECT yol_oneki FROM yazma_kilidi WHERE gorev_id = ?",
                    (gid,)).fetchall()}
        try:
            g = ofis.tahta.gorev(no)
            once = kilitler(g["id"])
            y = ofis.tahta.iptal_et(no, sebep=govde.sebep, iptal_eden="insan")
        except Exception as exc:     # noqa: BLE001 -- sebebi insana doner
            raise HTTPException(400, f"Iptal edilemedi: {exc}")
        sonra = kilitler(g["id"])
        return {"no": y["no"], "durum": y["durum"],
                "birakilan": sorted(once - sonra), "kalan": sorted(sonra)}

    # -- KADRO: ise alma ve ajan ayari -------------------------------------
    #
    # Olculdu (23.09.2026): kadroyu degistirmenin TEK yolu komut satiriydi.
    # 21.09'da kullanici "panelde ekleyip silip yonetebilmeliyim" demisti;
    # istek yetenek katmaninda kaldi, panele gelmedi. Kurallar YENIDEN
    # YAZILMADI: rol kapisi, ad kapisi, tek-lider kapisi `kadro`da -- panel
    # yalniz ona ulasan bir kapi. Bir kural panelde uygulaniyorsa yanlis
    # yerdedir.

    @uygulama.post("/api/kanat")
    def api_kanat_ac(govde: KanatGovdesi):
        """Yeni TAKIM (kanat). Rakipte "+ Team" var; bizde yalniz CLI'daydi.

        `kanat_ac` ayni adda istek gelince SESSIZCE var olani doner --
        kabuk icin zararsiz, ama panelde "kuruldu" deyip hicbir sey
        kurmamak yanlis gosteren bir gosterge olurdu. Burada ACIKCA
        reddedilir. Renk ve onek dogrulanir: bozuk bir renk kat planinin
        halisini, bozuk onek gorev kimliklerini kirletir.
        """
        import re as _re
        ofis = ofis_ac()
        ad = govde.ad.strip().upper()
        if not ad or len(ad) > 24:
            raise HTTPException(400, "Takim adi bos olamaz (en fazla 24 harf).")
        onek = (govde.onek or ad[:2]).strip().upper()
        if not _re.fullmatch(r"[A-Z0-9]{1,4}", onek):
            raise HTTPException(400, "Onek 1-4 harf/rakam olmali (gorev kimligi on eki).")
        if not _re.fullmatch(r"#[0-9A-Fa-f]{6}", govde.renk or ""):
            raise HTTPException(400, "Renk #RRGGBB biciminde olmali.")
        with ofis.db.baglanti() as conn:
            if conn.execute("SELECT 1 FROM kanat WHERE proje_id = ? AND ad = ?",
                            (ofis.proje_id, ad)).fetchone():
                raise HTTPException(400, f"'{ad}' adinda bir takim zaten var.")
        kid = ofis.kanat_ac(ad, onek, govde.renk)
        ofis.db.olay_yaz(ofis.proje_id, "kanat_acildi",
                         f"Yeni takim: {ad} ({onek}) -- once bir lider ise al.",
                         ajan_ad="insan")
        return {"id": kid, "ad": ad, "onek": onek, "renk": govde.renk}

    @uygulama.get("/api/kadro/secenek")
    def api_kadro_secenek():
        """Ise alma formunun secenekleri -- hepsi OLCULUR, uydurulmaz:
        motorlar gercekten kurulu mu, kademe haritasi ETKIN olan mi."""
        from . import roller as R
        from .kadro import EFORLAR
        ofis = ofis_ac()
        with ofis.db.baglanti() as conn:
            kanatlar = [dict(r) for r in conn.execute(
                "SELECT id, ad FROM kanat WHERE proje_id = ? "
                "ORDER BY olusturuldu", (ofis.proje_id,)).fetchall()]
        return {
            "roller": [{"ad": r.ad, "kategori": r.kategori, "ozet": r.ozet,
                        "tur": r.tur, "kademe": r.kademe, "uyari": r.uyari}
                       for r in R.ROLLER.values()],
            "kategoriler": R.kategoriler(),
            "motorlar": musait_motorlar(),
            "kanatlar": kanatlar,
            "eforlar": list(EFORLAR),
            "kademe_harita": R.kademe_haritasi(ofis.db, ofis.proje_id),
        }

    @uygulama.post("/api/ajan")
    def api_ise_al(govde: IseAlGovdesi):
        from .kadro import KadroHatasi
        ofis = ofis_ac()
        # KURULU OLMAYAN MOTORLA ISE ALINMAZ: hic kosamayacak bir ajan,
        # ekip onerisi kapisinin reddettigi seyin aynisi. Burada da
        # reddedilir -- iki kapidan biri gevserse digeri bosluk birakmaz.
        if not musait_motorlar().get(govde.motor):
            raise HTTPException(400, f"'{govde.motor}' motoru bu makinede "
                                     "kurulu degil ya da kimligi yok; o motorla "
                                     "ise alinan ajan HIC kosamaz.")
        # ORTAK KOK (karar 18.09.2026): butun ajanlar projenin kokunde
        # calisir; kilit ancak cakisma fiziksel olarak mumkunse anlamlidir.
        # Kural TEK YERDE (`Ofis.kok_klasoru`) -- kabuk da onu cagirir.
        kok = ofis.kok_klasoru()
        Path(kok).mkdir(parents=True, exist_ok=True)
        try:
            a = ofis.kadro.ise_al(
                govde.ad.strip().lower(), govde.meslek, motor=govde.motor,
                model=govde.model, efor=govde.efor, klasor=kok,
                kanat_id=govde.kanat or None, lider_mi=govde.lider)
        except KadroHatasi as exc:
            raise HTTPException(400, str(exc))
        return a

    @uygulama.post("/api/ajan/{ad}/not")
    def api_ajan_not(ad: str, govde: NotGovdesi):
        """CALISAN ajana not (E17). Not isin tanimina EKTIR.

        Panel ILETMEZ, deftere YAZAR: turu kosturan koltuk (panelde ya da
        kabukta, hangi surecte olursa) saniyede bir defterden okur ve motor
        tasiyorsa tur surerken iletir. Cevap notun NE ZAMAN gidecegini
        soyler (`tasir`); ulastigi an ayrica `not_iletildi` olayidir.
        """
        from .postane import PostaneHatasi
        ofis = ofis_ac()
        try:
            n = ofis.postane.not_birak(ad, govde.metin, gorev_no=govde.gorev_no)
        except PostaneHatasi as exc:
            raise HTTPException(400, str(exc))
        ajan = ofis.kadro.ajan(ad)
        try:
            fabrika = MOTOR_FABRIKASI or motor_ac
            tasir = bool(getattr(fabrika(ajan["motor"]), "tur_ici_mesaj", False))
        except Exception:
            tasir = False
        return {**n, "tasir": tasir, "motor": ajan["motor"]}

    @uygulama.post("/api/ajan/{ad}/ayar")
    def api_ajan_ayar(ad: str, govde: AjanAyarGovdesi):
        """Motor/model/efor/rol. SONUC BASILIR: degismeyen alan da doner,
        cunku basmayan cikti sessizce yok sayilan bir ayari fark ettirmez
        (`ajan degistir --rol` bir kez tam bundan odendi)."""
        from .kadro import KadroHatasi
        from . import roller as R
        ofis = ofis_ac()
        if govde.motor and not musait_motorlar().get(govde.motor):
            raise HTTPException(400, f"'{govde.motor}' motoru kurulu degil.")
        try:
            return ofis.kadro.motor_ayarla(
                ad, motor=govde.motor or None,
                model=govde.model if govde.model is not None else None,
                efor=govde.efor or None, meslek=govde.meslek or None)
        except (KadroHatasi, R.RolHatasi) as exc:
            raise HTTPException(400, str(exc))

    # -- YETENEK: hesaplar, anahtarlar, araclar -----------------------------
    #
    # Kullanici (21.09.2026): *"araclarda, eklentilerde, API'lerde hesaplar
    # ekleyebilmeli cikarabilmeliyim; panelde bunlari yonetebilir, gorebilir,
    # silip ekleyebilirim."* Katman yazildi ama yalniz `kabuk yetenek`teydi.
    #
    # SAHIPLIK AYRIMI korunur: ofisin sahip olduklari (hesap, kasa) panelden
    # degisir; olmadiklari (baglayici, CLI, OAuth) yalniz OLCULUR ve komut
    # soylenir. "Bagla" dugmesi koyup arkada hicbir sey yapamamak, yanlis
    # gosteren bir gosterge olurdu.
    #
    # PARA KILIDI panelden ACILMAZ: yalniz durumu gosterilir. Kullanicinin
    # acik kisiti "sadece free"; tek tiklik bir dugme baska bir botun
    # bakiyesini yanlis tiklamaya acardi. Acmak komut satirinda kalir.

    @uygulama.get("/api/yetenek")
    def api_yetenek(tam: int = 0):
        """`tam=1` baglayicilari da olcer (~15 sn, `claude mcp list`).
        Hizli taramada atlandigi SOYLENIR, sessizce eksik gosterilmez."""
        from . import yetenek as Y, gorsel as G, hesap as H
        ofis = ofis_ac()
        t = Y.tara(ofis, baglayici_dahil=bool(tam))
        # Hesaplarin aktifligi eylem icin gerekir; ORTAM gonderilmez --
        # referans bile olsa panelin isi degil.
        t["hesaplar"] = [{"ad": h["ad"], "motor": h["motor"], "tur": h["tur"],
                          "plan": h.get("plan") or "", "sira": h["sira"],
                          "aktif": h["aktif"]}
                         for h in H.liste(ofis.db, ofis.proje_id)]
        t["para_kilidi"] = G.ucretsiz_sadece_mi()
        return t

    @uygulama.post("/api/anahtar")
    def api_anahtar_ekle(govde: AnahtarGovdesi):
        from . import gizli
        try:
            r = gizli.ekle(govde.ad, govde.deger)
        except gizli.GizliHatasi as exc:
            raise HTTPException(400, str(exc))
        # Yeni anahtar BU surecin ortamina da yuklenir: yoksa kasada durur
        # ama ofis onu yeniden baslayana kadar gormez -- "kurulu ama
        # calismiyor" hali, hic kurulu olmamaktan zor bulunur.
        gizli.yukle()
        return {"ad": r["ad"], "parmak_izi": r["parmak_izi"]}

    @uygulama.post("/api/anahtar/{ad}/sil")
    def api_anahtar_sil(ad: str):
        from . import gizli
        if not gizli.sil(ad):
            raise HTTPException(404, f"Kasada '{ad.upper()}' yok.")
        return {"silindi": ad.upper()}

    @uygulama.post("/api/hesap/{ad}/aktif")
    def api_hesap_aktif(ad: str, govde: AktifGovdesi):
        """Hesabi zincire al / zincirden cikar. Kayit DURUR (gecmis
        okunur) -- limit dolan hesabi silmek degil kapatmak dogru."""
        from . import hesap as H
        ofis = ofis_ac()
        try:
            return H.ayarla(ofis.db, ofis.proje_id, ad, aktif=govde.aktif) \
                | {"ortam": None}
        except Exception as exc:     # noqa: BLE001 -- sebebi insana doner
            raise HTTPException(400, f"Hesap ayarlanamadi: {exc}")

    # -- insanin KARARI: ekip ve guncelleme onerileri ----------------------
    #
    # Olculdu: panel bunlari "senden bekleniyor" kuyrugunda SAYIYOR ama
    # insani komut satirina yolluyordu (*"`kabuk ekip liste` ile gor"*).
    # Gosterip karar verdirmemek, insana ofisin disinda is cikarmaktir.

    @uygulama.get("/api/oneriler")
    def api_oneriler():
        from . import guncelleme as G
        ofis = ofis_ac()
        # Otomatik moddaki oneriler insana DUSMEZ; otomatik UYGULANANLAR
        # ise gorulene kadar kart olarak durur (Geri al dugmesiyle).
        return {"ekip": ofis.ekip.bekleyenler(),
                "guncelleme": G.insana_dusenler(ofis.db, ofis.proje_id),
                "uygulanan": G.gorulmemisler(ofis.db, ofis.proje_id),
                "otomatik": G.otomatik_mi(ofis.db, ofis.proje_id)}

    @uygulama.get("/api/sablonlar")
    def api_sablonlar():
        """Takim sablonlari -- lider cagrilmaz, sonuc kararli."""
        from . import sablon as _s
        return [{"ad": s.ad, "baslik": s.baslik, "aciklama": s.aciklama,
                 "roller": [r for r, _ in s.uyeler]} for s in _s.liste()]

    @uygulama.post("/api/sablon")
    def api_sablon(govde: SablonGovdesi):
        """Sablondan EKIP ONERISI uretir -- KURMAZ. Oneri siradan bir ekip
        onerisidir: ayni kapidan gecer, "senden bekleniyor"da onizlemesiyle
        durur, kurmak yine insanin `Kur` karari."""
        from .ekip import EkipHatasi
        try:
            return ofis_ac().ekip.sablondan(govde.ad,
                                            kanat_id=govde.kanat or None)
        except EkipHatasi as exc:
            raise HTTPException(400, str(exc))

    @uygulama.post("/api/ekip/{no}/kur")
    def api_ekip_kur(no: int):
        from .ekip import EkipHatasi
        try:
            return {"alinan": ofis_ac().ekip.kur(no)}
        except EkipHatasi as exc:
            raise HTTPException(400, str(exc))

    @uygulama.post("/api/ekip/{no}/red")
    def api_ekip_red(no: int, govde: SebepGovdesi):
        from .ekip import EkipHatasi
        try:
            return ofis_ac().ekip.reddet(no, govde.sebep)
        except EkipHatasi as exc:
            raise HTTPException(400, str(exc))

    @uygulama.post("/api/guncelle/{no}/onayla")
    def api_guncelle_onayla(no: int, govde: GuncelleGovdesi):
        """Once DENEME TURU kosar (gercek motor, kisa); duserse eskisi kalir.
        Sonuc mesaji aynen doner -- 'uygulanmadi' da bir sonuctur."""
        from . import guncelleme as G
        from . import roller as R
        try:
            return G.uygula(ofis_ac(), no, kademe=govde.kademe,
                            fabrika=MOTOR_FABRIKASI)
        except (G.GuncellemeHatasi, R.RolHatasi) as exc:
            raise HTTPException(400, str(exc))

    @uygulama.post("/api/guncelle/gecmis/{sira}/geri_al")
    def api_guncelle_geri_al(sira: int, govde: SebepGovdesi):
        """Uygulanmis guncellemeyi ESKISINE dondurur; bir daha kendiliginden gelmez."""
        from . import guncelleme as G
        try:
            return G.geri_al(ofis_ac(), sira, sebep=govde.sebep)
        except G.GuncellemeHatasi as exc:
            raise HTTPException(400, str(exc))

    @uygulama.post("/api/guncelle/gecmis/{sira}/goruldu")
    def api_guncelle_goruldu(sira: int):
        from . import guncelleme as G
        try:
            o = ofis_ac()
            return G.goruldu(o.db, o.proje_id, sira)
        except G.GuncellemeHatasi as exc:
            raise HTTPException(400, str(exc))

    @uygulama.post("/api/guncelle/{no}/reddet")
    def api_guncelle_reddet(no: int, govde: SebepGovdesi):
        from . import guncelleme as G
        from . import roller as R
        try:
            return G.reddet(ofis_ac(), no, govde.sebep)
        except (G.GuncellemeHatasi, R.RolHatasi) as exc:
            raise HTTPException(400, str(exc))

    @uygulama.post("/api/lidere")
    def api_lidere(govde: LidereGovdesi):
        """Insanin lidere yazdigi satir -- ve liderin GERCEKTEN kosmasi.

        OLCULMUS KUSUR (21.09.2026): bu uc yalnizca `mesaj` tablosuna bir
        satir yaziyordu ve **hicbir sey onu kosturmuyordu.** Insan komut
        cubuguna yaziyor, hata almiyor, ve hicbir sey olmuyordu.

        Tam bu projenin avladigi sinif: *sistem saglikli gorunurken
        yanlis calisiyor.* Ustelik ayni hatayi bir kez odemistik --
        *"lider dogru soyledi, sistem onu yalanci cikardi"* (`cevap`
        yolu halkayi dondurmuyordu).

        Gorunur bir eylem sunup arkasinda kosturan koymamak, olmayan bir
        dugme cizmektir.

        Uc korkuluk:

        1. **TEK UCUS.** Ayni anda ikinci bir lider turu baslatilmaz.
           Cift tiklama jetonu ikiye katlardi ve iki lider ayni ofiste
           ayni ise karar verirdi (Yasa 1'in karar tarafi).
        2. **KACAK FRENI.** Panelde klavyenin basinda bekleyen biri
           yok; kontrolden cikan turu ofisin kendi freni durdurur
           (`tavan.py`). Dolar tavani yok (27.09: abonelik).
        3. **HATA YUTULMAZ.** Arka plan ipliginde patlayan bir sey
           sessizce kaybolurdu; `hata` olayina yazilir ve panele duser.
        """
        ofis = ofis_ac()
        # TAKIM SOHBETI: satirin basindaki `@ad` kime gittigini soyler;
        # ne olacagina ofisin var olan kurallari karar verir (`takim.py`).
        from . import takim as _takim
        try:
            yon = _takim.yonlendir(ofis, govde.metin)
        except _takim.TakimHatasi as exc:
            raise HTTPException(400, str(exc))
        if yon["yol"] == "not":
            try:
                m = ofis.postane.not_birak(yon["ajan"], yon["metin"],
                                           gorev_no=yon["gorev_no"])
            except PostaneHatasi as exc:
                raise HTTPException(400, str(exc))
            return {"yol": "not", "alici": yon["ajan"], "id": m["id"],
                    "gorev_no": yon["gorev_no"], "kosuyor": False}
        if yon["yol"] == "soru":
            return dict(_ajana_sor_baslat(ofis, yon["ajan"], yon["metin"]),
                        yol="soru", alici=yon["ajan"], kosuyor=False)
        atanan = yon["ajan"] if yon["yol"] == "is" else ""
        liderler = [a for a in ofis.kadro.liste() if a["lider_mi"]]
        if not liderler:
            raise HTTPException(400, "Bu ofiste lider yok. Once lider ise al.")
        if yon["lider"]:
            # `@lider_adi` ya da `@ajan is:` -- lider ADRESTEN gelir; secili
            # kanat sekmesi baska bir takimi gosteriyor olsa bile.
            lider = ofis.kadro.ajan(yon["lider"])
        elif govde.kanat:
            eslesen = [a for a in liderler if str(a["kanat_id"]) == str(govde.kanat)]
            if not eslesen:
                raise HTTPException(
                    400, "Secili kanadin lideri yok. Once o kanada bir lider "
                         "ise al ya da kanat sekmesini degistir.")
            lider = eslesen[0]
        elif len(liderler) == 1:
            lider = liderler[0]
        else:
            # GENEL KANAL (29.09): adres yok, kanat secili degil, birden cok
            # lider. SESSIZCE BIRINI SECMEYIZ (ilk surum `kadro[0]` aliyordu:
            # isi yanlis kanada vermenin en sessiz yolu). Ofis en uygun
            # takimi ONERIR -- model cagirmadan, kota harcamadan -- insan
            # secer; secim gelince ayni istek kanatla yeniden gelir. Mesaj
            # yazilmaz, lider kosmaz.
            return {"yol": "oneri", "kosuyor": False,
                    "oneriler": _takim.takim_oner(ofis, yon["metin"])}
        # KUYRUK (01.10.2026): lider mesgulken gelen mesaj artik REDDEDILMEZ
        # (ilk surum 409 "bitmesini bekle" diyordu); siraya girer. Tek ucus
        # korunur: ayni anda yine tek lider turu kosar.
        # MESAJI BURADA YAZMIYORUZ. `Sohbet.konus` onu zaten `mesaj`
        # tablosuna yaziyor; ikisi birden yazinca insanin tek cumlesi
        # deftere IKI KEZ dusuyordu (olculdu). Liderin baglami "son 6
        # konusma" ozetinden geliyor, yani kopya dogrudan onu kirletir.
        # *Iki yerde tutulan her sey en az bir kez kayar.*
        # KABINDE SECILEN OGE. Metin BURADA, tek yerde kurulur
        # (`kabin.oge_metni`) ve sayfanin kaynagi ise TARAYICI ALANI olur:
        # patron bir ogeyi isaret ettiyse o sayfada is yapilacaktir, ve
        # yetki insandan gelir -- isaret etmek, o kaynagi acmaktir.
        # Kabin aciksa is PAYLASILAN kabinde kosar (patronun oturumu);
        # kapaliysa ayri, oturumsuz tarayici -- ve blok bunu SOYLER.
        metin, web, kabin_cdp = yon["metin"], [], ""
        oge = kabin.oge_ozeti(govde.oge) if govde.oge else None
        if govde.oge and not oge:
            raise HTTPException(400, "Secilen oge okunamadi; yeniden sec.")
        if oge:
            kay = kabin.oge_kaynagi(oge)
            if kay:
                web = [kay]
                if _kabin.durum().get("acik"):
                    from . import tarayici as _t
                    kabin_cdp = _t.cdp_adresi(_kabin.kapi)
            metin = (metin + "\n\n"
                     + kabin.oge_metni(oge, kabin_paylasildi=bool(kabin_cdp)))
        from . import kuyruk as _kuyruk
        try:
            k = _kuyruk.ekle(ofis, metin, lider["ad"], atanan=atanan,
                             tarayici_alani=web, kabin=bool(kabin_cdp))
        except _kuyruk.KuyrukHatasi as exc:
            raise HTTPException(400, str(exc))
        basladi = _kuyrugu_baslat(db.yol, proje_ad)
        return {"yol": yon["yol"], "alici": lider["ad"], "atanan": atanan,
                "kosuyor": True, "tarayici": web, "kabin": bool(kabin_cdp),
                "sirada": not basladi, "sira": k["sira"], "kuyruk_id": k["id"]}

    @uygulama.get("/api/zamanli")
    def api_zamanli():
        from . import zamanlayici as _z
        return {"ogeler": _z.liste(ofis_ac())}

    @uygulama.post("/api/zamanli/{no}/iptal")
    def api_zamanli_iptal(no: str):
        from . import zamanlayici as _z
        try:
            r = _z.iptal(ofis_ac(), no)
        except _z.ZamanHatasi as exc:
            raise HTTPException(400, str(exc))
        return {"iptal": True, "no": r["no"]}

    @uygulama.get("/api/bildirim")
    def api_bildirim_durum():
        from . import bildirim as _b
        o = ofis_ac()
        return {"acik": (o.db.ayar_oku(o.proje_id, _b.AYAR, "acik") or "acik") != "kapali",
                "panelde_calisiyor": _b.ACIK}

    @uygulama.post("/api/bildirim")
    def api_bildirim_ayar(govde: dict):
        """Masaustu bildirimini acar/kapatir (patronun ayari, defterde)."""
        from . import bildirim as _b
        o = ofis_ac()
        o.db.ayar_yaz(o.proje_id, _b.AYAR, "acik" if govde.get("acik") else "kapali")
        return api_bildirim_durum()

    @uygulama.get("/api/kuyruk")
    def api_kuyruk():
        """Siradaki isler (eklenme sirasiyla) ve ofisin su anki isi."""
        from . import kuyruk as _kuyruk
        return {"bekleyenler": _kuyruk.bekleyenler(ofis_ac()), "kosu": dict(_KOSU)}

    @uygulama.post("/api/kuyruk/{kayit_id}/iptal")
    def api_kuyruk_iptal(kayit_id: str):
        """Siradaki isi iptal eder. Kosan is iptal edilmez -- Durdur."""
        from . import kuyruk as _kuyruk
        try:
            k = _kuyruk.iptal(ofis_ac(), kayit_id)
        except _kuyruk.KuyrukHatasi as exc:
            raise HTTPException(400, str(exc))
        return {"iptal": True, "metin": k["metin"]}

    @uygulama.post("/api/ajana-sor")
    def api_ajana_sor(govde: AjanaSorGovdesi):
        """Bir ajana DOGRUDAN soru. Cevap Sohbet panosuna duser.

        Rakipte her ajanin kendi konusma cekmecesi var. Bizde karsiligi
        zaten yazili olan DANISMA katmani: danisilan yazamaz, is acamaz,
        arac kutusu yok, temiz oturumla cevaplar. Yani bu bir bilgi
        alisverisidir, EMIR degil -- is vermek hala yalniz liderde.
        `uyandiran` kipinde yazilir: halka onu ajanin bekleyen sorusu
        sanip IKINCI kez teslim etmez ve ajanin isini durdurmaz.
        """
        return _ajana_sor_baslat(ofis_ac(), govde.ajan, govde.metin)

    def _ajana_sor_baslat(ofis, ajan_ad: str, metin: str) -> dict:
        """"Ajana sor" ile takim sohbetindeki `@ajan` sorusunun TEK yolu --
        iki kopya olsaydi biri tek-ucus kilidini unuturdu."""
        metin = (metin or "").strip()
        if not metin:
            raise HTTPException(400, "Bos soru sorulamaz.")
        try:
            ajan = ofis.kadro.ajan(ajan_ad)
        except Exception:
            raise HTTPException(400, f"'{ajan_ad}' diye bir ajan yok.")
        if _DANISMA["calisiyor"]:
            raise HTTPException(409, f"{_DANISMA['ajan']} su an bir soruyu "
                                     "cevapliyor -- bitmesini bekle.")
        try:
            m = ofis.postane.soru_sor("insan", ajan["ad"], metin, mod="uyandiran")
        except PostaneHatasi as exc:
            raise HTTPException(400, str(exc))
        _DANISMA.update(calisiyor=True, ajan=ajan["ad"])
        threading.Thread(target=_ajana_sor_kostur,
                         args=(db.yol, proje_ad, m["id"]), daemon=True).start()
        return {"id": m["id"], "ajan": ajan["ad"]}

    @uygulama.get("/api/sohbet")
    def api_sohbet(adet: int = 40):
        """Insanin lidere yazdiklari ve liderin TAM cevaplari.

        OLCULMUS KUSUR (23.09.2026): liderin patrona cevabi -- rapor dahil --
        yalnizca `mesaj.cevap`ta duruyordu; panel onu en fazla 200 harfe
        kesilmis bir olay satiri olarak gosteriyordu. Insanin TEK muhatabinin
        cevabi panelde OKUNAMIYORDU. Defterden okunur, kopyasi tutulmaz.
        """
        ofis = ofis_ac()
        with ofis.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT m.id, m.alici, m.govde, m.cevap, m.olusturuldu, "
                "m.cevaplandi, g.no AS gorev_no FROM mesaj m "
                "LEFT JOIN gorev g ON g.id = m.gorev_id "
                "WHERE m.proje_id = ? AND m.gonderen = 'insan' "
                "AND m.mod = 'uyandiran' ORDER BY m.rowid DESC LIMIT ?",
                (ofis.proje_id, max(1, min(int(adet), 200)))).fetchall()
        from .sohbet import akislar
        akan = akislar(ofis.db, ofis.proje_id)
        mesajlar = [dict(r) for r in reversed(rows)]
        for m in mesajlar:
            # Cevabi dusmus mesajin akisi GOSTERILMEZ (kayit silinmemis
            # olsa bile): yarim metin, tam cevabin yerini almaz.
            m["akis"] = "" if m["cevap"] else akan.get(str(m["id"]), "")
        return {"mesajlar": mesajlar,
                "kosu": dict(_KOSU), "danisma": dict(_DANISMA)}

    @uygulama.get("/api/takim")
    def api_takim(kanat: str = "", adet: int = 80):
        """Takim sohbeti: lidere yazilanlar, ajanlara sorular ve notlar,
        cevaplar, ajanlarin birbirine sorulari, raporlar ve hukumler --
        TEK akista, defterden TURETILIR (kopya yok). Liderin YAZILMAKTA
        olan cevabi da bekleyen ogeye eklenir."""
        from . import takim as _takim
        from .sohbet import akislar
        ofis = ofis_ac()
        ogeler = _takim.akis(ofis, kanat_id=(kanat or None), adet=adet)
        akan = akislar(ofis.db, ofis.proje_id)
        for x in ogeler:
            x["akis"] = akan.get(str(x["id"]), "") if x["bekliyor"] else ""
        return {"ogeler": ogeler, "kosu": dict(_KOSU),
                "danisma": dict(_DANISMA)}

    @uygulama.get("/api/sohbet/akis")
    def api_sohbet_akis():
        """Liderin YAZILMAKTA olan cevaplari -- panel bunu kosu surerken
        sik yoklar. Sohbetin tamamini her seferinde cekmemek icin ayri uc."""
        ofis = ofis_ac()
        from .sohbet import akislar
        return {"akis": akislar(ofis.db, ofis.proje_id),
                "kosu": dict(_KOSU)}

    @uygulama.get("/api/ara")
    def api_ara(q: str = ""):
        """Gorev · kanit · karar · bilgi · olay -- tek kutudan arama.
        Olay defterinin yalniz SON 5000 satiri taranir ve bu soylenir."""
        ofis = ofis_ac()
        return {"sonuclar": ara(ofis.db, ofis.proje_id, q),
                "kapsam": "gorev · kanit · karar · bilgi · olay (son 5000)"}

    @uygulama.get("/api/lider-durum")
    def api_lider_durum():
        """Lider su an kosuyor mu. Panelin 'gonder' dugmesi buna bakar --
        kosarken tekrar gondermek 409 alir, ama insan bunu dugme
        kilitlenmeden ONCE gormeli."""
        return dict(_KOSU)

    # -- canli akis --------------------------------------------------------

    @uygulama.get("/api/akis")
    async def api_akis(sonra: int = 0):
        """SSE. Yoklama ile beslenir: SQLite'ta bildirim yok, WAL sayesinde
        okuma yazani bloklamaz (db.py). Yarim saniye, insanin 'takildi mi'
        esiginin altinda kalir."""
        async def uret():
            son = sonra
            while True:
                ofis = ofis_ac()
                with db.baglanti() as conn:
                    rows = conn.execute(
                        "SELECT o.id, o.ajan_ad, o.tur, o.govde, o.olusturuldu, "
                        "g.no AS gorev_no FROM olay o "
                        "LEFT JOIN gorev g ON g.id = o.gorev_id "
                        "WHERE o.proje_id = ? AND o.id > ? ORDER BY o.id LIMIT 200",
                        (ofis.proje_id, son)).fetchall()
                for r in rows:
                    son = r["id"]
                    yield f"data: {json.dumps(dict(r), ensure_ascii=False)}\n\n"
                if not rows:
                    yield ": nabiz\n\n"
                await asyncio.sleep(0.5)
        return StreamingResponse(uret(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    return uygulama


def kos(adres: str = "127.0.0.1", kapi: int = 8900, db_yolu=None,
        proje_ad: str = None) -> None:
    """Paneli baslatir. `0.0.0.0` KODDA reddedilir.

    Butun arayuzlere acilmak, ev agindaki her cihaza ofisin tamamini
    vermektir: kanitlar, kararlar, ajan siciller, onay kuyrugu. Telefondan
    erisim Tailscale (100.x) uzerinden yapilir -- o zaman adres acikca
    verilir ve ne yapildigi bilinir.
    """
    import uvicorn
    if adres in ("0.0.0.0", "::", ""):
        raise SystemExit(
            "0.0.0.0 reddedildi: butun arayuzlere acilmak, ev agindaki her "
            "cihaza ofisin tamamini vermektir. Yerel icin 127.0.0.1, "
            "telefon icin Tailscale adresini (100.x) acikca ver."
        )
    if adres not in GUVENLI_ADRESLER and not adres.startswith("100."):
        print(f"UYARI: {adres} yerel ya da Tailscale adresi degil.")
    uygulama = olustur(db_yolu, proje_ad)
    # OTOMATIK TARAYICI (02.10.2026): ajan tarayici gereken ise basliyor,
    # kabin kapali -> ofis acar. Yalniz gercekten calisan panelde.
    from . import orkestra as _ork_mod
    _ork_mod.KABIN_ACICI["islev"] = _KABIN_CDP.get("acici")
    # ESKI KIMLIKLI KABIN (02.10.2026, patronun ekrani: Google robot
    # dogrulamasi): onceki oturumdan acik kalan kabin panel yeniden
    # baslayinca yeniden kullaniliyordu. Kapatilir; sonraki acilis
    # (patron ya da ajan) yeni ayarlarla olur.
    try:
        if kabin.acik_mi() and kabin.eski_kimlikli_mi():
            kabin.cdp_kapat()
            print("Eski ayarli tarayici kapatildi; sonraki acilis yeni ayarlarla.")
    except Exception:                    # noqa: BLE001 -- panel acilisini durdurmaz
        pass
    acilista_toparla(db_yolu or VARSAYILAN_YOL, proje_ad)
    bildirimleri_baslat(db_yolu or VARSAYILAN_YOL, proje_ad,
                        f"http://{adres}:{kapi}/")
    zamanlayiciyi_baslat(db_yolu or VARSAYILAN_YOL, proje_ad)
    _gunluk_yedek_arkada(db_yolu)
    _limit_tazele_arkada(db_yolu, proje_ad)
    _guncelleme_arkada(db_yolu, proje_ad)
    uvicorn.run(uygulama, host=adres, port=kapi, log_level="warning")


def _gunluk_yedek_arkada(db_yolu) -> None:
    """Panel acikken gunluk yedek -- arka planda, paneli bekletmeden.

    Panel gunlerce acik kalabilir; yalniz acilista bakmak, uzun acik bir
    panelde yedegi gunlerce geciktirirdi. Bu yuzden saatte bir bakar;
    gercekten alma karari `gerekirse_al` icinde (24 saat).
    """
    import threading
    import time
    from . import yedek as Y
    from .db import VARSAYILAN_YOL
    if not Y.gercek_defter_mi(db_yolu or VARSAYILAN_YOL):
        return

    def dongu():
        while True:
            try:
                db = Veritabani(db_yolu or VARSAYILAN_YOL)
                with db.baglanti() as c:
                    r = c.execute("SELECT id FROM proje WHERE durum='acik' "
                                  "ORDER BY olusturuldu LIMIT 1").fetchone()
                pid = r["id"] if r else None
                Y.gerekirse_al((lambda tur, govde: db.olay_yaz(pid, tur, govde))
                               if pid else None, depo_gonder=True)
            except Exception:     # noqa: BLE001 -- panel olmesin
                pass
            time.sleep(3600)

    threading.Thread(target=dongu, name="gunluk-yedek", daemon=True).start()


def _guncelleme_arkada(db_yolu, proje_ad=None) -> None:
    """Panel acikken YENI MODEL / CLI -- fark et ve (otomatik mod aciksa) uygula.

    Kullanici (29.09.2026): *"ofis farkedip bana dusen her seyi kendisi
    yapsa."* On dakikada bir bakilir; asil denetim `kontrol_gerekirse`
    icinde yarim saatte bir (30.09: "hemen yapsin"). Uygulama `otomatik_ilerle`: deneme turu gecerse kalici,
    duserse insana duser; is kosarken CLI degistirilmez. Yalniz GERCEK
    defterde -- test ve ornek ofis kullanicinin makinesine npm kurmasin.
    """
    import threading
    import time
    from . import guncelleme as G
    from . import yedek as Y
    from .db import VARSAYILAN_YOL
    if not Y.gercek_defter_mi(db_yolu or VARSAYILAN_YOL):
        return

    def dongu():
        time.sleep(60)          # panel once ayaga kalksin
        while True:
            try:
                db = Veritabani(db_yolu or VARSAYILAN_YOL)
                with db.baglanti() as c:
                    if proje_ad:
                        r = c.execute("SELECT ad FROM proje WHERE ad = ?",
                                      (proje_ad,)).fetchone()
                    else:
                        r = c.execute("SELECT ad FROM proje WHERE durum='acik' "
                                      "ORDER BY olusturuldu LIMIT 1").fetchone()
                if r:
                    ofis = Ofis.proje_ac(db, r["ad"])
                    G.olc_ve_ilerle(ofis, fabrika=MOTOR_FABRIKASI, zorla=False)
            except Exception as exc:     # noqa: BLE001 -- panel olmesin
                try:
                    db.olay_yaz(None, "uyari", f"Otomatik guncelleme calismadi: {exc}")
                except Exception:        # noqa: BLE001
                    pass
            # Is kosarken ertelenen guncelleme de en gec 10 dakikada denenir.
            time.sleep(600)

    threading.Thread(target=dongu, name="guncelleme", daemon=True).start()


def _limit_tazele_arkada(db_yolu, proje_ad=None) -> None:
    """Panel acikken hesap limitleri SUREKLI guncel (27.09.2026).

    Kullanici: *"kalan kullanim limitleri guncel olmali surekli."* Iki
    dakikada bir saglayicidan okunur (kota harcamaz); panel rayi ve
    onceden gecis ayni kaydi gorur. Seyreltme `kullanim.tazele` icinde --
    halka da ayni anda tazelerse ikinci okuma yapilmaz.
    """
    import threading
    import time
    from . import kullanim
    from .db import VARSAYILAN_YOL

    def dongu():
        while True:
            try:
                db = Veritabani(db_yolu or VARSAYILAN_YOL)
                with db.baglanti() as c:
                    if proje_ad:
                        r = c.execute("SELECT id FROM proje WHERE ad = ?",
                                      (proje_ad,)).fetchone()
                    else:
                        r = c.execute("SELECT id FROM proje WHERE durum='acik' "
                                      "ORDER BY olusturuldu LIMIT 1").fetchone()
                if r:
                    kullanim.tazele(db, r["id"])
            except Exception:     # noqa: BLE001 -- panel olmesin
                pass
            time.sleep(kullanim.TAZELEME_SN)

    threading.Thread(target=dongu, name="limit-tazele", daemon=True).start()


if __name__ == "__main__":
    import argparse
    ayrıstirici = argparse.ArgumentParser(description="AgentOfis paneli")
    ayrıstirici.add_argument("--adres", default="127.0.0.1")
    ayrıstirici.add_argument("--kapi", type=int, default=8900)
    ayrıstirici.add_argument("--db", default=None)
    ayrıstirici.add_argument("--proje", default=None)
    a = ayrıstirici.parse_args()
    kos(a.adres, a.kapi, a.db, a.proje)
