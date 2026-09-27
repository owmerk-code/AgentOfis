# -*- coding: utf-8 -*-
"""KULLANIM -- hangi hesap, ne kadar tuketti, ne zaman yenilenir.

Kullanici (22.09.2026): *"ben API kullanmiyorum, aboneliklerimi
kullaniyorum... claude codex veya baska hesap bagladigimda sistemimizde
hangi hesap bagli, limitleri ne durumda, anlik kullanimi, ne zaman
yenilenecegini takip edebilecegim bir alan."*

Hakli bir istek ve ofiste karsiligi yoktu. Ama once neyin OLCULEBILIR
oldugu olculdu, cunku gorunmeyen bir sayiyi uydurmak, gostergesizlikten
kotudur.

## ~~OLCULDU: saglayici CANLI limiti VERMIYOR~~ -- YANLISTI (23.09.2026)

Asagidaki olcum dogruydu ama BAKILAN YER eksikti. Canli limit CLI'in
KOMUTLARINDA yok; turun AKISINDA var:

    claude -p --output-format stream-json  -> her turda `rate_limit_event`
        unifiedWindows.five_hour/seven_day: utilization, resetsAt
    codex exec -> oturum kaydi (sessions/**/rollout-*.jsonl) `token_count`
        rate_limits.primary/secondary: used_percent, window_minutes, resets_at

Ofis bunu 64 kez OKUMUS ve ATMISTI (`olay` tablosunda `ek` sutunu yok).
Artik adaptor `bitti.ek["limit_pencere"]`e koyuyor, `tur_ozeti_yaz`
defterde tutuyor, `son_pencereler` okuyor. Sayi HESABIN TOPLAMIDIR
(insanin elle kullanimi dahil) ve ancak ofis o hesapla bir tur
kostugunda tazelenir -- bu yuzden YASIYLA gosterilir.

Eski olcum (hala dogru, ama sorulan soruya cevap degil):

    claude auth status  -> loggedIn, email, subscriptionType: "max"
                           (kullanim YOK)
    claude --help       -> `usage` diye bir komut YOK
    ~/.claude/.credentials.json
                        -> subscriptionType, rateLimitTier
                           (CANLI SAYI YOK)
    codex --help        -> `usage` diye bir komut YOK

Yani *"haftalik payinin %47'si dolmus"* bilgisi **claude.ai
ayarlarinda** var ve ofis onu okuyamaz. Bu bir eksik degil SINIR, ve
yazili olmasi gerekiyordu.

## O ZAMAN NE GOSTERIYORUZ: OFISIN KENDI TUKETTIGI

Bu kesin bir olcum -- her tur `tur_ozeti` olayina jeton, sure, model,
motor ve hesap yaziyor. Gosterilen sey:

    "Ofis son 5 saatte: 7 tur, 1.2M jeton"    <- OLCULDU
    "Hesabinin TOPLAM kullanimi"              <- OLCEMIYORUZ, soyluyoruz

Ikisini ayirmak sart. Sen Claude Code'u elle de kullaniyorsun, claude.ai
sohbetini de; ofisin sayisi senin toplam kullaniminin yalnizca BIR
PARCASI. Bunu soylemeden gostermek, yanlis gosteren bir gosterge olurdu.

## PENCERELER

* **5 saat** -- Anthropic'in oturum penceresi. Kayan bir pencere;
  biz "son 5 saat" diye sayiyoruz. Tam hizalama iddia etmiyoruz.
* **7 gun** -- haftalik pencere. Anthropic'te Carsamba 06:00'da (ISTANBUL saati = 03:00 UTC; olculdu)
  yenileniyor (kullanicinin kendi ekranindan, 21.09.2026). Bu bir
  AYAR, kod degil: baska bir plan ya da saglayici baska bir gune
  denk gelir ve o zaman kodu degistirmek gerekmemeli (`plan.py` ile
  ayni karar).
"""

from __future__ import annotations

import json
import time
import threading
from datetime import datetime, timedelta, timezone

#: Haftalik pencerenin yenilendigi gun/saat (UTC). Kullanicinin kendi
#: claude.ai ekranindan okundu: "Carsamba 06:00".
#:
#: AYAR olmasinin sebebi: sabit kodlamak, baska plani olan herkesi
#: kodu degistirmeye zorlardi -- zincirde ve `plan.py`de ayni karar.
AYAR_HAFTALIK_GUN = "kullanim.haftalik_gun"      # 0=Pazartesi .. 6=Pazar
AYAR_HAFTALIK_SAAT = "kullanim.haftalik_saat"

VARSAYILAN_GUN = 2        # Carsamba
#: 03:00 UTC = Istanbul 06:00. OLCULDU (23.09.2026): saglayicinin kendi
#: `resetsAt`i 1790132400 = Carsamba 03:00 UTC. Once burada "06:00 UTC"
#: yaziyordu -- kullanicinin ekranindaki YEREL saati UTC diye okumustum;
#: hesaplanan yenilenme 3 saat kayikti. Artik olculen varsa o kullanilir
#: (`_haftalik`); bu deger yalniz olcum yokken dusulen yedektir.
VARSAYILAN_SAAT = 3       # 03:00 UTC (Istanbul 06:00)

#: Oturum penceresi. Anthropic'te 5 saat.
OTURUM_SAAT = 5

#: `tur_ozeti` olayinin alanlari -- TEK YERDE.
#:
#: Bu olay uc ayri yerde yaziliyordu ve her biri alanlari KENDISI
#: seciyordu: koltuk `motor/hesap` ekliyordu, lider ve sartname
#: eklemiyordu. Hic yazmayan uc yol da vardi (inceleme, danisma,
#: guncelleme deneme turu) -- ve hakem (fable) tam inceleme turunda
#: kosuyor, yani haftalik kapi butcesi onun harcamasini GORMUYORDU.
#: Iki kopyadan biri duzeltilip oteki unutuluyor; bu projede bu desen
#: alti kez odendi.
OZET_ALANLARI = ("jeton", "maliyet_usd", "sure_ms", "model",
                 "arac_sayisi", "basarili")


def tur_ozeti_yaz(db, proje_id: str, ek: dict, *, ajan_ad: str = "",
                  gorev_id: str = None, motor: str = "", hesap: str = "",
                  yol: str = "") -> None:
    """Bir motor turunun olcumunu KALICI yazar -- her yol, tek bicim.

    `ek` motorun `bitti.ek`idir. Hesabin kullanim pencereleri
    (`limit_pencere`, bkz. `motor/tip.py`) varsa tasinir: saglayicinin
    kendi bildirimi defterde KAYBOLMASIN.
    `yol`: turu hangi yol kosturdu (lider, inceleme, danisma, ...).
    """
    ek = ek or {}
    veri = {k: ek.get(k) for k in OZET_ALANLARI}
    veri["motor"] = motor or ""
    veri["hesap"] = hesap or ""
    if yol:
        veri["yol"] = yol
    if isinstance(ek.get("limit_pencere"), dict):
        veri["limit_pencere"] = ek["limit_pencere"]
    db.olay_yaz(proje_id, "tur_ozeti", json.dumps(veri, ensure_ascii=False),
                ajan_ad=ajan_ad, gorev_id=gorev_id)


def _ayar(db, proje_id: str, anahtar: str, varsayilan):
    try:
        with db.baglanti() as conn:
            r = conn.execute(
                "SELECT deger FROM ayar WHERE proje_id = ? AND anahtar = ?",
                (proje_id, anahtar)).fetchone()
        if r:
            return int(dict(r)["deger"])
    except Exception:
        pass
    return varsayilan


def haftalik_yenilenme(db=None, proje_id: str = "", *, simdi_=None) -> dict:
    """Haftalik pencere ne zaman yenilenecek.

    YEDEK: saglayicinin kendi ani olculduyse `_haftalik` onu kullanir;
    bu islev yalniz olcum yokken insanin verdigi ayardan hesaplar. Bu yuzden cikti "hesaplanan" diye
    isaretleniyor: olculen ile hesaplanani ayirt edememek, bu projede
    video maliyetinde bir kez odendi.
    """
    gun = _ayar(db, proje_id, AYAR_HAFTALIK_GUN, VARSAYILAN_GUN) if db else VARSAYILAN_GUN
    saat = _ayar(db, proje_id, AYAR_HAFTALIK_SAAT, VARSAYILAN_SAAT) if db else VARSAYILAN_SAAT
    su_an = simdi_ or datetime.now(timezone.utc)
    ileri = (gun - su_an.weekday()) % 7
    hedef = (su_an + timedelta(days=ileri)).replace(
        hour=saat, minute=0, second=0, microsecond=0)
    if hedef <= su_an:
        hedef += timedelta(days=7)
    kalan = hedef - su_an
    return {
        "ne_zaman": hedef,
        "kalan_saat": round(kalan.total_seconds() / 3600, 1),
        "kaynak": ("hesaplanan (ayardan; henuz OLCULMEDI -- ofis bir "
                   "claude turu kostugunda saglayicinin kendi ani kullanilir)"),
    }


def _zaman(metin: str):
    try:
        z = datetime.fromisoformat(str(metin))
    except (TypeError, ValueError):
        return None
    return z if z.tzinfo else z.replace(tzinfo=timezone.utc)


#: Canli olcumun ayar anahtari: `limit_canli:<motor>:<hesap>`. Hesap
#: basina TEK kayit, her tazelemede UZERINE yazilir -- olay tablosu
#: buyumez (olay tablosu kayit defteridir, saniye sayaci degil).
CANLI_ONEK = "limit_canli:"
#: Iki tazeleme arasi en az bu kadar sn. Okuma kota harcamaz ama her
#: seferinde bir CLI sureci baslatir (claude ~1,3-2,6 sn, codex ~0,8-2,7).
TAZELEME_SN = 120
_TAZELEME_KILIDI = threading.Lock()


def _canli_kayitlar(db, proje_id: str) -> list:
    with db.baglanti() as conn:
        satirlar = conn.execute(
            "SELECT anahtar, deger FROM ayar WHERE proje_id = ? AND anahtar LIKE ?",
            (proje_id, CANLI_ONEK + "%")).fetchall()
    out = []
    for r in satirlar:
        try:
            veri = json.loads(r["deger"])
        except (ValueError, TypeError):
            continue
        if isinstance(veri, dict):
            out.append(veri)
    return out


def tazele(db, proje_id: str, *, fabrika=None, zorla: bool = False,
           en_az_sn: float = None) -> dict:
    """Her abonelik hesabinin limitini SAGLAYICIDAN TUR KOSMADAN okur.

    Kullanici (27.09.2026): *"kalan kullanim limitleri guncel olmali
    surekli."* Once yuzde yalniz ofis o hesapla TUR KOSTUKCA tazeleniyordu;
    insan CLI'i elle kullaninca ofisin gordugu sayi bayatliyordu -- olculdu:
    codex'in 5 saatlik penceresi %100 doluyken ofis sabahki yuzdeyi
    gosteriyordu ve onceden gecis o hesaba is vermeye devam ederdi.

    * Okuma kota HARCAMAZ (claude `get_usage`, codex `account/rateLimits`).
    * Seyreltilir (`TAZELEME_SN`); `zorla` insan istediginde.
    * Okuyamayan motor (`limit_oku` -> None) UYDURULMAZ: eski olcum yasiyla
      kalir, bu yazilir.
    * API hesabi okunmaz: onun siniri dolardir (`hesap.api_kalan`).

    Donus: `{"okundu": [...], "okunamadi": [...], "atlandi": bool}`.
    """
    en_az = TAZELEME_SN if en_az_sn is None else en_az_sn
    if not _TAZELEME_KILIDI.acquire(blocking=False):
        return {"okundu": [], "okunamadi": [], "atlandi": True,
                "sebep": "baska bir tazeleme suruyor"}
    try:
        simdi_sn = time.time()
        try:
            son = float(db.ayar_oku(proje_id, "limit_canli_son", "0") or 0)
        except (TypeError, ValueError):
            son = 0.0
        if not zorla and simdi_sn - son < en_az:
            return {"okundu": [], "okunamadi": [], "atlandi": True,
                    "sebep": f"son tazeleme {int(simdi_sn - son)} sn once"}
        db.ayar_yaz(proje_id, "limit_canli_son", str(simdi_sn))
        from . import hesap as H
        if fabrika is None:
            from .motor import motor_ac as fabrika
        okundu, okunamadi = [], []
        for h in H.zincir_hesaplari(db, proje_id):
            if h.get("tur") != "abonelik" or not h.get("aktif", True):
                continue
            try:
                coz = H.ortam_coz(h)
                m = fabrika(h["motor"])
                lp = m.limit_oku(ek_ortam=coz or None)
            except Exception as exc:      # bir hesabin bozuklugu digerini durdurmaz
                okunamadi.append(f"{h['ad']}: {str(exc).splitlines()[0][:120]}")
                continue
            if not lp or not lp.get("pencereler"):
                okunamadi.append(f"{h['ad']}: saglayici yuzde vermedi")
                continue
            hesap = "" if h["ad"] == h["motor"] else h["ad"]
            db.ayar_yaz(proje_id, f"{CANLI_ONEK}{h['motor']}:{hesap}", json.dumps({
                "motor": h["motor"], "hesap": hesap,
                "olculdu": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "limit_pencere": lp}))
            okundu.append(h["ad"])
        return {"okundu": okundu, "okunamadi": okunamadi, "atlandi": False}
    finally:
        _TAZELEME_KILIDI.release()


def son_pencereler(db, proje_id: str, *, simdi_=None) -> list:
    """Her hesap icin EN SON olculen kullanim pencereleri.

    IKI kaynak, ikisi de saglayicinin KENDI bildirimi (tahmin degil):
    `tur_ozeti.limit_pencere` (tur sonunda) ve CANLI okuma (`tazele`, tur
    kosmadan). Pencere basina hangisi YENIYSE o kazanir.

    * YENILENMIS PENCERENIN YUZDESI GOSTERILMEZ. Olcum pencere yenilenmeden
      once alindiysa o yuzde artik YANLIS; `yenilendi` der, yuzde `None`.
    * OLCUMUN YASI HER ZAMAN YAZILIR (pencere basina).

    Hesap adi normallesir: ajanin kendi basamagi (`""`) ve ortuk hesap
    (motorun kendi adi) AYNI hesaptir -- ayri gostermek, tek hesabi iki
    kez saymak olurdu.
    """
    su_an = simdi_ or datetime.now(timezone.utc)
    with db.baglanti() as conn:
        satirlar = conn.execute(
            "SELECT govde, olusturuldu FROM olay WHERE proje_id = ? "
            "AND tur = 'tur_ozeti' AND govde LIKE '%limit_pencere%' "
            "ORDER BY id DESC LIMIT 500", (proje_id,)).fetchall()
    kayitlar = []           # (olculdu, sira, veri) -- sira: esitlikte tur yeni
    for i, r in enumerate(satirlar):
        try:
            veri = json.loads(r["govde"])
        except (ValueError, TypeError):
            continue
        if isinstance(veri, dict):
            kayitlar.append((_zaman(r["olusturuldu"]), -i, veri))
    for veri in _canli_kayitlar(db, proje_id):
        kayitlar.append((_zaman(veri.get("olculdu")), 1, veri))
    en_eski = datetime.min.replace(tzinfo=timezone.utc)
    kayitlar.sort(key=lambda k: (k[0] or en_eski, k[1]), reverse=True)

    gorulen, cikti = {}, []
    for olculdu, _, veri in kayitlar:
        lp = veri.get("limit_pencere")
        if not isinstance(lp, dict) or not isinstance(lp.get("pencereler"), dict):
            continue
        motor = (veri.get("motor") or "").strip() or "(kayitta yok)"
        hesap = (veri.get("hesap") or "").strip()
        if hesap == motor:
            hesap = ""
        yas = (round((su_an - olculdu).total_seconds() / 60) if olculdu else None)
        # PENCERE BASINA en yeni olcum (27.09.2026): Fable penceresi
        # (`7g_kapi`) turda YALNIZ fable turunda gelir; hesabin en yeni
        # olcumu onu tasimiyorsa eski olcumdeki pencere KENDI yasiyla eklenir.
        onceki = gorulen.get((motor, hesap))
        if onceki is not None:
            for ad, p in lp["pencereler"].items():
                ad = ESKI_AD.get(ad, ad)
                if ad in onceki["pencereler"]:
                    continue
                w = _pencere(p, su_an)
                if w:
                    w["yas_dk"], w["olculdu"] = yas, olculdu
                    onceki["pencereler"][ad] = w
            continue
        pencereler = {}
        for ad, p in lp["pencereler"].items():
            ad = ESKI_AD.get(ad, ad)
            w = _pencere(p, su_an)
            if w:
                w["yas_dk"], w["olculdu"] = yas, olculdu
                pencereler[ad] = w
        if not pencereler:
            continue
        cikti.append({
            "motor": motor, "hesap": hesap,
            "kaynak": lp.get("kaynak") or "", "plan": lp.get("plan") or "",
            "hal": lp.get("hal") or "",
            "olculdu": olculdu, "yas_dk": yas,
            "pencereler": pencereler,
        })
        gorulen[(motor, hesap)] = cikti[-1]
    return cikti


def _pencere(p, su_an):
    try:
        yenilenme = datetime.fromtimestamp(int(p["yenilenme"]), timezone.utc)
        kullanim = float(p["kullanim"])
    except (KeyError, TypeError, ValueError, OSError):
        return None
    kalan = (yenilenme - su_an).total_seconds()
    return {"kullanim": None if kalan <= 0 else kullanim,
            "yenilendi": kalan <= 0, "yenilenme": yenilenme,
            "kalan_saat": round(max(kalan, 0) / 3600, 1)}


def _turlar(db, proje_id: str, *, saat: float) -> list:
    """Son N saatteki tur ozetleri.

    Kaynak `tur_ozeti` -- yani KAYDIN TUTULDUGU YER. Koltugun kendi
    sayacindan okumak, zincir devrettiginde ya da MCP ayri surecte
    calistiginda eksik sayardi.
    """
    esik = (datetime.now(timezone.utc) - timedelta(hours=saat)
            ).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    with db.baglanti() as conn:
        satirlar = conn.execute(
            "SELECT govde, olusturuldu FROM olay WHERE proje_id = ? "
            "AND tur = 'tur_ozeti' AND olusturuldu >= ? "
            "ORDER BY olusturuldu", (proje_id, esik)).fetchall()
    cikti = []
    for r in satirlar:
        try:
            veri = json.loads(dict(r)["govde"])
        except (ValueError, TypeError):
            continue
        if isinstance(veri, dict):
            cikti.append(veri)
    return cikti


def _topla(turlar: list) -> dict:
    """Motor/hesap kirilimiyla toplar.

    MALIYET: yalniz OLCULEBILENLER toplanir, olculemeyen AYRI sayilir.
    Hicbiri olculemediyse toplam `None` doner -- `0.0` DEGIL. Bu ayrim
    panelde bir kez odendi: bilinmeyen maliyeti sifir ilan etmek,
    gorunmeyen butceyi butce sanmaktir.
    """
    ozet = {"tur": 0, "jeton": 0, "maliyet": None, "fiyatsiz": 0,
            "basarisiz": 0, "motorlar": {}}
    for t in turlar:
        ozet["tur"] += 1
        try:
            ozet["jeton"] += int(t.get("jeton") or 0)
        except (TypeError, ValueError):
            pass
        m = t.get("maliyet_usd")
        if m is None:
            ozet["fiyatsiz"] += 1
        else:
            try:
                ozet["maliyet"] = (ozet["maliyet"] or 0.0) + float(m)
            except (TypeError, ValueError):
                ozet["fiyatsiz"] += 1
        if not t.get("basarili"):
            ozet["basarisiz"] += 1

        motor = (t.get("motor") or "").strip()
        hesap = (t.get("hesap") or "").strip()
        if not motor:
            # ESKI KAYITLAR motor tasimiyor (alan 22.09'da eklendi).
            # "bilinmiyor" diye gostermek, uydurup modelden CIKARIM
            # yapmaktan durust.
            motor = "(kayitta yok)"
        ad = f"{motor}/{hesap}" if hesap else motor
        k = ozet["motorlar"].setdefault(
            ad, {"tur": 0, "jeton": 0, "model": set()})
        k["tur"] += 1
        try:
            k["jeton"] += int(t.get("jeton") or 0)
        except (TypeError, ValueError):
            pass
        if t.get("model"):
            k["model"].add(str(t["model"]))
    for k in ozet["motorlar"].values():
        k["model"] = sorted(k["model"])
    return ozet


def _haftalik(db, proje_id: str, pencereler: list) -> dict:
    """Haftalik yenilenme: OLCULDUYSE olculen, degilse hesaplanan.

    Iki kaynak ayni anda gosterilmez -- ikisi ayrisirsa hangisinin
    dogru oldugu okuyana birakilmis olur. Olculen kazanir ve kaynagi
    yasiyla yazilir; yoksa ayar tabanli hesap "hesaplanan" diye kalir.
    """
    for p in pencereler:
        h = p["pencereler"].get("7g")
        if p["motor"] == "claude" and h and not h["yenilendi"]:
            return {"ne_zaman": h["yenilenme"], "kalan_saat": h["kalan_saat"],
                    "kaynak": f"olculen (claude CLI, {p['yas_dk']} dk once)"}
    return haftalik_yenilenme(db, proje_id)


def ozet(db, proje_id: str) -> dict:
    """Panel ve kabuk icin tek kaynak."""
    pencereler = son_pencereler(db, proje_id)
    return {
        "oturum": _topla(_turlar(db, proje_id, saat=OTURUM_SAAT)),
        "hafta": _topla(_turlar(db, proje_id, saat=24 * 7)),
        "yenilenme": _haftalik(db, proje_id, pencereler),
        "pencereler": pencereler,
        "oturum_saat": OTURUM_SAAT,
    }


PENCERE_ETIKETI = {"5s": "5 saat", "7g": "7 gun", "7g_kapi": "Fable (7 gun)"}
#: 27.09 oncesi kayitlarda Fable penceresi saglayicinin ham adiyla duruyor.
ESKI_AD = {"seven_day_overage_included": "7g_kapi"}


def pencere_metni(p: dict) -> str:
    """Tek hesabin olculen pencereleri, insanin okuyacagi tek satir."""
    parcalar = []
    for ad, w in p["pencereler"].items():
        etiket = PENCERE_ETIKETI.get(ad, ad)
        if w["yenilendi"]:
            parcalar.append(f"{etiket}: YENILENDI (olcum yenilenmeden onceydi)")
        else:
            parcalar.append(f"{etiket}: %{round(w['kullanim'] * 100)} "
                            f"(yenilenme {w['yenilenme']:%d.%m %H:%M} UTC, "
                            f"~{w['kalan_saat']} sa)")
    return " · ".join(parcalar)


def hesap_durumu() -> list:
    """Hangi hesaplar BAGLI ve hangi planla -- OLCULUR, uydurulmaz.

    Limit yuzdesi BURADA degil `son_pencereler`de: hesabin durumu
    `auth status`tan, kullanimi turun akisindan olculur -- iki farkli
    kaynak, iki farkli tazelik. "limit" alani yalnizca nereye
    bakilacagini soyler; uydurmaz.
    """
    sonuc = []

    # claude: giris OLCULUR (`auth status`, motorun kendi olcumu -- tek kopya,
    # onbellekli). Oturum sunucuda dustuyse `durum_notu` soyler (E16).
    try:
        from .motor.claude import ClaudeMotoru
        m = ClaudeMotoru()
        g = m.giris_durumu()
        notu = m.durum_notu()
        sonuc.append({
            "motor": "claude",
            "bagli": (None if g["girisli"] is None else
                      bool(g["girisli"]) and not notu),
            "kimlik": g["eposta"],
            "plan": g["plan"],
            "limit": (notu or "turun akisindan olculur -- bkz. PENCERELER"),
        })
    except Exception as exc:
        sonuc.append({"motor": "claude", "bagli": None, "kimlik": "",
                      "plan": "", "limit": f"olculemedi: {exc}"})

    # codex: kimlik dosyasindan plan okunur; kullanim yine YOK.
    try:
        from pathlib import Path
        from .motor.codex import CodexMotoru
        ev = Path(CodexMotoru._ev_bul())
        d = json.loads((ev / "auth.json").read_text(encoding="utf-8"))
        # DEGER DEGIL, VARLIK okunuyor: bu dosya kimlik tasiyor.
        bilgi = d.get("tokens") or {}
        # Dosya duruyor olabilir ama oturum sunucuda dusmus olabilir (E16).
        notu = CodexMotoru().durum_notu()
        sonuc.append({
            "motor": "codex",
            "bagli": bool(d.get("OPENAI_API_KEY") or bilgi) and not notu,
            "kimlik": str(bilgi.get("account_id") or "")[:12] or "(kayitli)",
            "plan": "",
            "limit": notu or "turun akisindan olculur -- bkz. PENCERELER",
        })
    except Exception as exc:
        sonuc.append({"motor": "codex", "bagli": None, "kimlik": "",
                      "plan": "", "limit": f"olculemedi: {exc}"})
    return sonuc


def metin(db, proje_id: str) -> str:
    """Kabugun bastigi insan okunur ozet."""
    o = ozet(db, proje_id)
    s = ["HESAPLAR  (olculur, uydurulmaz)", ""]
    for h in hesap_durumu():
        durum = ("BAGLI" if h["bagli"] else
                 ("BAGLI DEGIL" if h["bagli"] is False else "OLCULEMEDI"))
        plan = f" · plan: {h['plan']}" if h["plan"] else ""
        kimlik = f" · {h['kimlik']}" if h["kimlik"] else ""
        s.append(f"  {h['motor']:8} {durum}{plan}{kimlik}")
    s += ["", "PENCERELER  (saglayicinin KENDI bildirimi -- hesabin TOPLAMI)", ""]
    if not o["pencereler"]:
        s.append("  henuz OLCULMEDI -- ofis bu hesaplarla tur kostukca dolar")
    for p in o["pencereler"]:
        ad = p["motor"] + (f"/{p['hesap']}" if p["hesap"] else "")
        yas = "?" if p["yas_dk"] is None else f"{p['yas_dk']} dk once"
        s.append(f"  {ad:14} {pencere_metni(p)}")
        s.append(f"  {'':14} olcum: {yas} · {p['kaynak']}"
                 + (f" · plan {p['plan']}" if p["plan"] else ""))
    # ONCEDEN GECIS esikleri -- gorunmeyen ayar, ayar degildir.
    from .zincir import gecis_esikleri
    s += ["", "ONCEDEN GECIS  (dolmak uzere olan hesaba yeni tur baslatilmaz)", ""]
    for rol in ("isci", "lider"):
        esik, _ = gecis_esikleri(db, proje_id, rol)
        if esik is None:
            s.append("  KAPALI -- ac: kullanim --gecis ac")
            break
        s.append(f"  {rol:6} " + " · ".join(
            f"{p} %{round(v * 100)}" for p, v in esik.items()))
    s += ["", "OFISIN TUKETTIGI  (senin TOPLAM kullanimin DEGIL)", ""]
    for ad, p in (("son %d saat" % o["oturum_saat"], o["oturum"]),
                  ("son 7 gun", o["hafta"])):
        # 27.09.2026: abonelikte dolar YAZILMAZ -- olcu jeton ve hesabin
        # kendi yuzdesi (yukarida). Dolar yalniz API hesabinin satirinda.
        s.append(f"  {ad:12} {p['tur']:>3} tur · {p['jeton']:>10,} jeton")
        for m, k in sorted(p["motorlar"].items(),
                           key=lambda x: -x[1]["jeton"]):
            s.append(f"       {m:22} {k['tur']:>3} tur · "
                     f"{k['jeton']:>10,} jeton")
    y = o["yenilenme"]
    s += ["", f"HAFTALIK YENILENME: {y['ne_zaman']:%d.%m.%Y %H:%M} UTC "
              f"(~{y['kalan_saat']} saat)",
          f"  kaynak: {y['kaynak']}",
          "",
          "NOT: PENCERELER hesabin TOPLAMIDIR ama ancak ofis o hesapla",
          "tur kostugunda tazelenir; arada elle kullandiysan gercek daha",
          "yuksektir (olcumun yasi bu yuzden yazili). OFISIN TUKETTIGI ise",
          "yalniz ofisin kendi turlaridir."]
    return "\n".join(s)
