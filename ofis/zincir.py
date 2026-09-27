# -*- coding: utf-8 -*-
"""Nobet zinciri: limit dolunca is durmaz, sira sonrakine gecer.

Olculmus problem (kullanicinin kendi sozleri, 18.09.2026): *"codex
hesapta limit yarin yenilenecek"* · *"fable tek promptta 5 saatlik limiti
bitiriyordu"*. Yani limit teorik bir kenar durum degil, GUNLUK gercek.

Limit gelince bugune kadar ne oluyordu: tur `basarili=False` donuyor,
koltuk kilidi birakiyor, is `hazir`a dusuyor ve orkestra "ilerleme yok"
deyip DURUYORDU. Insan geri gelene kadar ofis oluydu. Oysa limit bir
HATA degil, bir KAYNAGIN tukenmesidir -- caresi duzeltmek degil, baska
kaynaga gecmektir.

Rakip (Muratify) bunu "iki abonelik arasi otomatik gecis" olarak yapiyor.
Burada daha genel kuruldu: iki hesap degil, **N basamakli bir zincir** --
motor VE model birlikte. Ayni motorun ucuz modeline de dusebilir, baska
bir motora da gecebilir.

Kurallar:

* **Zincir ajanin KENDI motorundan baslar.** Ajanin ayari yok sayilmaz;
  zincir onun ARKASINA eklenir. Baslangici degistirmek, kullanicinin
  sectigi modeli sessizce iptal etmek olurdu.

* **Butce uygulayamayan basamak ARTIK ATLANMIYOR -- OFIS FRENI devreye
  giriyor** (22.09.2026). Onceki kural sunu diyordu: *"tavansiz kosmak,
  kullanicinin koydugunu sandigi sinirin olmamasi demektir; o yuzden
  atla."* Mantik dogruydu ama OLCULMUS sonucu agirdi:

      uyari | Zincirde atlandi: codex/gpt-5.6-sol --
              tur basina butce tavani uygulayamiyor

  Yani "tavan koy" demek pratikte "codex'i KAPAT" demekti; `cinar`
  aylarca codex ayarliyken her turu Claude'da kosti. Ve kullanici
  DeepSeek/Qwen/Kimi/Grok eklemek istiyor -- her yeni motor ayni
  duvara carpardi.

  **Gevseme DEGIL, yer degistirme:** kontrol CLI'dan OFISE tasindi
  (`tavan.py`). Basamak artik `ofis_freni: True` ile isaretleniyor ve
  koltuk o turda kacak freni + birikmis jeton tavani uyguluyor.
  Basamagin dolar tavani UYGULAYAMADIGI gorunur bir `uyari` olarak
  yaziliyor -- bir kontrolun yerine baskasi geciyorsa, bu sessiz
  olmaz.

* **Kurulu olmayan motor atlanir.** `musait_mi()` olcum yapar, tahmin
  degil; olmayan motora devretmek turu bir kez daha oldururdu.

* **Devir KARAR GUNLUGUNE yazilir.** "Neden bu is haiku yerine codex'te
  kosmus" sorusunun cevabi alti ay sonra da durmali. Gerekce zorunlu
  kuralinin buraya da uygulanmasi bilincli.

* **Zincir TUKENIRSE durulur.** Sonsuz devir, limitleri sirayla yakmaktir.
"""

from __future__ import annotations

from .motor import motor_ac, MotorHatasi

#: Varsayilan zincir: (motor, model). Bos model = motorun/hesabin
#: varsayilani. Sira UCUZA DOGRU gider -- limit dolduran genelde pahali
#: olandir ve is ucuz modelle de yurur; tersi, limitleri sirayla yakar.
#:
#: `fable` BILEREK YOK: kullanici olctu, tek prompt 5 saatlik limiti
#: bitiriyor (bkz. CLAUDE.md model politikasi).
VARSAYILAN_ZINCIR = (
    ("claude", "sonnet"),
    ("claude", "haiku"),
    ("codex", ""),
)


class ZincirBitti(RuntimeError):
    """Butun basamaklar tukendi. Devredecek yer kalmadi."""


def _musait_mi(motor_ad: str, fabrika) -> bool:
    try:
        return bool(fabrika(motor_ad).musait_mi())
    except MotorHatasi:
        return False
    except Exception:
        return False


def _neden(motor_ad: str, fabrika) -> str:
    try:
        notu = fabrika(motor_ad).durum_notu()
    except AttributeError:
        notu = ""
    except Exception as exc:          # noqa: BLE001
        notu = f"acilamadi: {exc}"
    return notu or "bu makinede kurulu degil"


def _butce_kaldirir_mi(motor_ad: str, fabrika) -> bool:
    try:
        return bool(getattr(fabrika(motor_ad), "butce_destegi", False))
    except Exception:
        return False


def zincir_kur(ajan: dict, *, butce_usd=None, zincir=None,
               fabrika=motor_ac, hesaplar=None, kademe_haritasi=None) -> list:
    """Bu ajan icin denenecek basamaklari sirayla verir.

    Her basamak: `{"motor", "model", "sebep"}`. Ilk basamak HER ZAMAN
    ajanin kendi ayaridir; gerisi yedektir.

    Elenen basamaklar sessizce yok olmaz -- cagiran `elenenler()` ile
    neden elendiklerini sorabilir.
    """
    basamaklar = []
    gorulen = set()

    kendi = (ajan.get("motor") or "", ajan.get("model") or "")
    aday_listesi = [kendi] + [a for a in (zincir or VARSAYILAN_ZINCIR)]

    # Rolun kademesi: MODELSIZ yedek basamak hesabin varsayilanina
    # dusmesin diye (bkz. asagidaki kural 3). Genel zincir de hesaplar
    # da ayni kurali kullanir -- iki yerde ayri yazilsaydi biri unutulurdu.
    from . import roller as _roller
    try:
        kademe = _roller.rol(ajan.get("meslek") or "").kademe
    except _roller.RolHatasi:
        kademe = ""          # eski/serbest meslek: kademe bilinmiyor
    # ONAYLANMIS kademe haritasi (ayar) koddaki varsayilani ezer; verilmezse
    # varsayilan. Yedek basamak da insanin onayladigi modeli kullanmali --
    # yoksa kademe "yeni model"e gecmis, zincir eskisinde kalmis olurdu.
    _harita = kademe_haritasi or _roller.KADEME_MODEL

    for sira_no, (motor_ad, model) in enumerate(aday_listesi):
        if not motor_ad:
            continue
        if sira_no > 0 and not model:
            # Genel zincirde MODELSIZ yedek (`("codex", "")`):
            #  - ajanin KENDI motoruysa, ayni (dolmus) kimligi bilinmeyen
            #    modelle tekrar denemektir -> atlanir.
            #  - baska motorsa kademeden model alir; bulunamazsa (gemini
            #    gibi kademesi olmayan motor) varsayilanda kalir.
            if motor_ad == kendi[0]:
                continue
            model = (_harita.get(motor_ad) or {}).get(kademe, "")
        anahtar = (motor_ad, model)
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        if not _musait_mi(motor_ad, fabrika):
            continue
        # Butce uygulayamayan basamak, butce ISTENDIGINDE atlanir.
        basamaklar.append({"motor": motor_ad, "model": model,
                           "hesap": "", "ortam": {},
                           # Dolar tavanini motor uygulayamiyorsa ofis
                           # freni devreye girer. Atlanmaz -- bkz. dosya basi.
                           "ofis_freni": bool(
                               butce_usd
                               and not _butce_kaldirir_mi(motor_ad, fabrika))})

    # HESAP BASAMAKLARI -- coklu hesap desteginin asil yeri.
    #
    # Zincir bugune kadar (motor, model) ciftleriydi. Dogrusu
    # (HESAP, model): "limit gelince otekine gec" derken kastedilen
    # sey buydu ve "iki abonelik arasi gecis" bunun ozel bir hali.
    # Ayni motorun iki hesabi (is/kisisel) ya da abonelik + API yan
    # yana durabilmeli.
    #
    # Hesaplar ARKAYA eklenir: ajanin kendi ayari her zaman ilk sirada
    # kalir (zincirin degismez kurali -- kullanicinin sectigini
    # sessizce iptal etmek yok).
    # OLCULMUS KUSUR (22.09.2026) -- ikinci Plus hesabi eklenirken.
    # Hesaplar zincirin SONUNA, bos modelle ekleniyordu. Gercek ofiste
    # codex ajani icin olculen sira:
    #
    #   0 codex sol (hesap 1) -> 1 claude sonnet -> 2 claude haiku ->
    #   3 codex VARSAYILAN (AYNI dolmus hesap) -> 4 claude VARSAYILAN
    #   (Opus 5.5 1M) -> 5 codex VARSAYILAN (AYNI hesap yine) ->
    #   6 codex2  <- ikinci hesap ancak burada
    #
    # Yani "limit dolunca oteki hesaba gec" -- hesap katmaninin var olma
    # sebebi -- pratikte hic calismiyordu: is Claude'a gidiyor ve Max
    # limitini yiyordu. Uc kural:
    #
    #   1. AYNI MOTORUN BASKA KIMLIKLI hesabi HEMEN ajanin kendi
    #      basamagindan sonra gelir ve ajanin MODELINI korur. Is ayni
    #      modelle, yalnizca baska hesaptan surer.
    #   2. Ayni motorun KIMLIKSIZ hesabi (ortam yok) ajanin kendi
    #      basamagiyla AYNI kimliktir -- dolmus hesabi tekrar denemek.
    #      Atlanir.
    #   3. Baska motora gecen hesap BOS modelle kosmaz: rolun
    #      KADEMESINDEN model alir. Bos model hesabin varsayilanina
    #      duser (claude'da Opus 5.5 1M; codex'te olculmedi, Astra
    #      olabilir) -- "model verilmeyen is on kat pahali" dersinin
    #      aynisi.
    kendi_motor, kendi_model = kendi
    ayni_motor, diger_motor = [], []
    for h in (hesaplar or []):
        if not h.get("aktif", True):
            continue
        ortam = h.get("_cozulmus_ortam") or {}
        ayni = h["motor"] == kendi_motor
        if ayni and not ortam and not h.get("ortam"):
            continue                      # kural 2: ajanin kendi kimligi
        if h.get("model"):
            model = h["model"]
        elif ayni:
            model = kendi_model            # kural 1
        else:
            model = (_harita.get(h["motor"]) or {}).get(kademe, "")
        # KIMLIKSIZ hesap (ortam yok) varsayilan kimliktir: ayni motor ve
        # ayni modelle genel zincirde zaten denendiyse, dolmus hesabi
        # IKINCI KEZ denemek olur. Olculdu: lider zincirinde `codex` genel
        # basamagi ile `codex` hesabi arka arkaya ayni evi deniyordu.
        if not ortam and not h.get("ortam") and (h["motor"], model) in gorulen:
            continue
        anahtar = (h["motor"], model, h["ad"])
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        if not _musait_mi(h["motor"], fabrika):
            continue
        _fren = bool(butce_usd and not _butce_kaldirir_mi(h["motor"], fabrika))
        # Kimlik zincirde COZULMEZ: `zincir` motor katmanini bilir,
        # gizli depoyu bilmez. Cagiran taraf hesabi cozup
        # `_cozulmus_ortam` ile verir. Katman sirasini bozmadan bilgi
        # ulastirmak -- tahtanin `duraklatilmis_kaynak`iyla ayni desen.
        basamak = {"motor": h["motor"], "model": model,
                   "hesap": h["ad"], "ortam": ortam, "ofis_freni": _fren}
        if h.get("_api_kalan") is not None:
            basamak["api_kalan"] = h["_api_kalan"]
        (ayni_motor if ayni else diger_motor).append(basamak)

    # Kural 1'in yeri: ajanin KENDI basamagi zincirde ilk siradaysa
    # hemen arkasina; kendi motoru musait degilse en basa.
    ilk_kendi = bool(basamaklar) and basamaklar[0]["motor"] == kendi_motor         and not basamaklar[0]["hesap"]
    konum = 1 if ilk_kendi else 0
    basamaklar[konum:konum] = ayni_motor
    basamaklar.extend(diger_motor)
    return basamaklar


def elenenler(ajan: dict, *, butce_usd=None, zincir=None,
              fabrika=motor_ac) -> list:
    """Hangi basamak NEDEN elendi. Gorunmeyen bosluk birakmamak icin."""
    sonuc = []
    gorulen = set()
    kendi = (ajan.get("motor") or "", ajan.get("model") or "")
    for motor_ad, model in [kendi] + [a for a in (zincir or VARSAYILAN_ZINCIR)]:
        if not motor_ad:
            continue
        anahtar = (motor_ad, model)
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        if not _musait_mi(motor_ad, fabrika):
            # Sebep MOTORUN kendi teshisi (E16): kurulu degil / giris yok /
            # oturum sunucuda dustu. Hepsine "kurulu degil" demek, girissiz
            # bir motoru kurmaya calistirirdi.
            sonuc.append({"motor": motor_ad, "model": model,
                          "sebep": _neden(motor_ad, fabrika)})
        # NOT: "butce uygulayamiyor" ARTIK ELEME SEBEBI DEGIL. Basamak
        # kosar, ofis freni uygulanir. Eleme listesi yalnizca GERCEKTEN
        # kosamayacak basamaklari sayar; yoksa insana calisan bir
        # basamagi "elendi" diye gosterirdik.
    return sonuc


#: LIDERIN YEDEK ZINCIRI (23.09.2026).
#:
#: OLCULEN BOSLUK: nobet zinciri yalnizca ISCILERDE vardi. Liderin
#: turlari (triyaj, planlama, rapor, inceleme) dogrudan kendi motorunda
#: kosuyordu -- Claude limiti dolunca LIDER DURUR, onunla BUTUN OFIS
#: durur. Iscinin limiti bir isi durdurur; liderinki hepsini.
#:
#: Neden ayni hesabin ucuz modeli (sonnet/haiku) YOK: limit HESABA
#: baglidir. Olculdu -- claude'un `rate_limit_event`i pencereleri
#: `unifiedWindows` altinda, model ayrimi olmadan bildiriyor. Dolmus
#: bir hesapta modeli dusurmek ayni duvara tekrar carpmaktir. Yedek
#: BASKA motordur; model rolun kademesinden gelir (lider `guclu` ->
#: codex'te onaylanmis kademe haritasi, bugun gpt-6-sol).
#:
#: Neden kayipsiz: liderin her turu zaten TEMIZ oturumla baslar ve
#: baglamini DEFTERDEN alir (brifing, kararlar, konusma ozeti) --
#: tasinacak bir oturum yok. Ayni istem sonraki motorla aynen kosar.
#:
#: Gemini 24.09.2026'da cikarildi (kullanici karari; bkz. motor/__init__).
LIDER_ZINCIRI = (("codex", ""),)


def basamaklari_kur(db, proje_id: str, ajan: dict, *, fabrika=motor_ac,
                    zincir=None, butce_usd=None, kademe_haritasi=None,
                    rol: str = "isci") -> tuple:
    """Hesaplari cozup zinciri kurar -> `(basamaklar, uyarilar)`.

    `uyarilar`: zincire alinmayan hesaplar + ONCEDEN GECIS notlari
    (`pencereye_gore_sirala`). Cagiran ikisini de GORUNUR kilar.

    Koltuk ile lider AYNI islevi kullanir. Once yalnizca koltukta
    yaziliydi; lidere ikinci bir kopyasini yazmak, bu projede alti kez
    odenen "biri duzeltilir oteki unutulur" hatasinin davetiyesiydi.
    Cozulemeyen hesap zincire GIRMEZ ve sebebi ikinci listede doner --
    cagiran onu gorunur kilar.
    """
    from . import hesap
    hesaplar, alinmayan = [], []
    for h in hesap.zincir_hesaplari(db, proje_id):
        if h.get("ortuk"):
            continue          # ortuk hesap zaten ajanin kendi basamagi
        olur = hesap.kullanilabilir_mi(h)
        if not olur["olur"]:
            alinmayan.append(f"'{h['ad']}' hesabi zincire alinmadi: {olur['sebep']}")
            continue
        api = None
        if h.get("tur") == "api":
            # API: gercek para. Sinir yoksa, dolduysa ya da motor tur
            # basina harcamayi SINIRLAYAMIYORSA zincire girmez -- kapali
            # kalarak basarisiz olur.
            try:
                sinirlar = getattr(fabrika(h["motor"]), "butce_destegi", False)
            except Exception:
                sinirlar = False
            if not sinirlar:
                alinmayan.append(f"'{h['ad']}' API hesabi zincire alinmadi: "
                                 f"{h['motor']} tur harcamasini sinirlayamiyor")
                continue
            api = hesap.api_kalan(db, proje_id, h)
            if not api["olur"]:
                alinmayan.append(f"'{h['ad']}' API hesabi zincire alinmadi: {api['sebep']}")
                continue
        hesaplar.append(dict(h, _cozulmus_ortam=hesap.ortam_coz(h),
                             _api_kalan=api["kalan"] if api else None))
    basamaklar = zincir_kur(ajan, butce_usd=butce_usd, zincir=zincir,
                            fabrika=fabrika, hesaplar=hesaplar,
                            kademe_haritasi=kademe_haritasi)
    basamaklar, notlar = pencereye_gore_sirala(db, proje_id, basamaklar, rol=rol)
    return basamaklar, alinmayan + notlar


#: ONCEDEN GECIS ESIKLERI (23.09.2026) -- olculen pencere yuzdesiyle.
#:
#: Limit gelince devir zaten var; ama limite CARPMAK bir turun ortasinda
#: kesilmek demektir -- is yarida kalir, devir paketi ne kadar iyi olsa da
#: yeni motor baglami yeniden kurar (olculdu: codex tarafi 528.366 jeton).
#: Saglayici doluluk yuzdesini her turda bildiriyor (`kullanim.son_pencereler`);
#: dolmak UZERE olan hesaba yeni bir tur baslatmamak ucuzdur.
#:
#: Iki rol, iki esik -- ve fark bilinclidir: isciler ortak Claude hesabini
#: LIDERDEN ONCE birakir. Lider durursa butun ofis durur; isci baska
#: motorda da ayni isi yapar.
#:
#: Esikler AYARDIR, kod degil (`gecis_esigi:<rol>:<pencere>`); tamamen
#: kapatilabilir (`onceden_gecis = kapali`). Sabit kodlanmis bir esik,
#: farkli plani olan herkesi kodu degistirmeye zorlardi (plan.py karari).
ONCEDEN_GECIS_ESIKLERI = {
    "isci":  {"5s": 0.80, "7g": 0.85},
    "lider": {"5s": 0.95, "7g": 0.97},
}
PENCERE_ETIKETI = {"5s": "5 saatlik", "7g": "haftalik"}


def gecis_esikleri(db, proje_id: str, rol: str = "isci"):
    """Etkin esikler -- ya da `None` (onceden gecis KAPALI).

    Bozuk bir ayar degeri varsayilana duser ama SESSIZ kalmaz: ikinci
    donus degeri okunamayan anahtarlari sayar, cagiran onu gorunur kilar.
    """
    if (db.ayar_oku(proje_id, "onceden_gecis", "acik") or "acik") == "kapali":
        return None, []
    esik = dict(ONCEDEN_GECIS_ESIKLERI.get(rol) or ONCEDEN_GECIS_ESIKLERI["isci"])
    bozuk = []
    for pencere in list(esik):
        anahtar = f"gecis_esigi:{rol}:{pencere}"
        deger = (db.ayar_oku(proje_id, anahtar, "") or "").strip()
        if not deger:
            continue
        try:
            sayi = float(deger)
        except ValueError:
            bozuk.append(anahtar)
            continue
        if not 0 < sayi <= 1:
            bozuk.append(anahtar)
            continue
        esik[pencere] = sayi
    return esik, bozuk


def pencereye_gore_sirala(db, proje_id: str, basamaklar: list, *,
                          rol: str = "isci", simdi_=None) -> tuple:
    """Dolmak UZERE olan hesabin basamaklarini zincirin SONUNA alir.

    -> `(basamaklar, notlar)`.

    SILMEZ, SONA ALIR: "dolmak uzere" dolu demek degildir; oteki
    basamaklar da duserse bu hesap yine denenir. Silseydik esigin yanlis
    ayarlandigi bir gunde is hic kosamazdi.

    Bu, zincirin "ilk basamak ajanin KENDI ayaridir" kuralinin TEK
    istisnasidir ve olcume dayanir: ajanin secimi iptal edilmiyor,
    olculen bir doluluk yuzunden bu tur icin ertesine birakiliyor -- ve
    bu gorunur bir notla soyleniyor.

    Olcum yoksa, pencere yenilendiyse (`kullanim None`) ya da hepsi
    esikteyse sira DEGISMEZ: bilmedigimiz bir sayiya gore yer degistirmek
    tahmin olurdu.
    """
    if len(basamaklar) < 2:
        return basamaklar, []
    esik, bozuk = gecis_esikleri(db, proje_id, rol)
    notlar = [f"gecis esigi okunamadi, varsayilan kullanildi: {a}" for a in bozuk]
    if not esik:
        return basamaklar, notlar
    dolu, sebep = esikteki_basamaklar(db, proje_id, basamaklar, esik,
                                      simdi_=simdi_)
    if not dolu:
        return basamaklar, notlar
    if len(dolu) == len(basamaklar):
        return basamaklar, notlar + [
            "ONCEDEN GECIS yapilmadi: zincirdeki butun hesaplar esikte ("
            + "; ".join(sebep.values()) + ") -- sira degismedi."]
    yeni = ([b for i, b in enumerate(basamaklar) if i not in dolu]
            + [b for i, b in enumerate(basamaklar) if i in dolu])
    ilk = yeni[0]
    return yeni, notlar + [
        f"ONCEDEN GECIS: {s} -> basamaklari sona alindi; bu tur "
        f"{ilk['motor']}" + (f"/{ilk['model']}" if ilk.get("model") else "")
        + " ile basliyor." for s in sebep.values()]


def esikteki_basamaklar(db, proje_id: str, basamaklar: list, esik: dict, *,
                        simdi_=None) -> tuple:
    """Hangi basamaklarin hesabi esikte -> `(indisler, {anahtar: sebep})`.

    TEK kural: zincir sirayi buna gore degistirir, panelin hesap panosu
    ayni cevabi "sonda" diye gosterir. Iki ayri hesap olsaydi panel ofisin
    yapmadigi bir seyi yapiyor gibi gosterebilirdi.
    """
    from . import kullanim
    olcum = {(p["motor"], p["hesap"]): p
             for p in kullanim.son_pencereler(db, proje_id, simdi_=simdi_)}
    dolu, sebep = set(), {}
    for i, b in enumerate(basamaklar):
        hesap = b.get("hesap") or ""
        if hesap == b["motor"]:
            hesap = ""
        anahtar = (b["motor"], hesap)
        p = olcum.get(anahtar)
        if not p:
            continue
        for pencere, sinir in esik.items():
            k = (p["pencereler"].get(pencere) or {}).get("kullanim")
            if k is not None and k >= sinir:
                dolu.add(i)
                sebep.setdefault(anahtar, (
                    f"{b['motor']}" + (f" [{hesap}]" if hesap else "")
                    + f" hesabi {PENCERE_ETIKETI.get(pencere, pencere)} "
                    f"pencerenin %{round(k * 100)}'inde (esik "
                    f"%{round(sinir * 100)}, olcum {p.get('yas_dk')} dk once)"))
                break
    return dolu, sebep


def tur_butcesi(basamak: dict, motor, istenen=None):
    """Bu turun motora verilecek harcama siniri -- TEK kural, uc cagiran.

    * API hesabi: kalan aylik paydan fazlasi istenemez (gercek para).
    * Aksi halde `istenen` (ic kacak freni: fable kapisi) yalniz UYGULAYABILEN
      motora gider; codex tavan gelince turu hic baslatmadan reddeder.
    * Abonelikte normal turda `None`: limit saglayicinin yuzdesidir.
    """
    api = basamak.get("api_kalan")
    if api is not None:
        return min(float(api), float(istenen)) if istenen else float(api)
    if basamak.get("ofis_freni") or not getattr(motor, "butce_destegi", False):
        return None
    return istenen


def limitte_devret(basamaklar: list, kostur, *, devir) -> tuple:
    """TEMIZ oturumla kosan turlar (lider) icin: limitte sonraki basamak.

    `kostur(basamak)` -> `(bitti_ek, parcalar)`. `bitti_ek["limit"]`
    gelirse `devir(eski, yeni)` cagrilir (karar gunlugu, gorunur olay)
    ve AYNI istem sonraki basamakla bastan kosar. Isci turundaki gibi
    bir oturum kaybedilmez: lider baglamini defterden alir.

    Zincir biterse son sonuc doner; cagiran "basarisiz" gorur ve
    bugunku davranis korunur -- sonsuz devir, limitleri sirayla yakmaktir.
    Doner: `(basamak, bitti_ek, parcalar)`.
    """
    if not basamaklar:
        raise ZincirBitti("Lider icin calistirilabilir motor yok.")
    son = None
    for i, b in enumerate(basamaklar):
        ek, parcalar = kostur(b)
        son = (b, ek or {}, parcalar)
        # Devir: limit (kaynak tukendi) YA DA hesap kullanilamaz (oturum
        # sunucuda dustu -- E16). Ikisinde de bu hesap SU AN is yapamaz.
        oturum_dustu = (ek or {}).get("sebep") == "oturum_kapandi"
        if not ((ek or {}).get("limit") or oturum_dustu):
            return son
        if i + 1 < len(basamaklar):
            devir(dict(b, devir_nedeni=("hesabi KULLANILAMIYOR (oturum/hesap "
                                        "sorunu)" if oturum_dustu else
                                        "kullanim limitine ulasti")),
                  basamaklar[i + 1])
    return son


def lider_devri(ofis, lider: dict, eski: dict, yeni: dict, gorev_id=None) -> None:
    """Liderin motor devri GORUNUR ve KAYITLI olur.

    Devir bir KARARDIR (isci zincirindeki kuralin aynisi): "bu plan neden
    codex'te yapilmis" sorusu alti ay sonra da cevaplanabilmeli. Ayrica
    `limit` olayi -- panel ve saglik limitin nerede dolduguna bakar.
    """
    neden = eski.get("devir_nedeni") or "kullanim limitine ulasti"
    ad = lambda b: b["motor"] + (f"/{b['model']}" if b.get("model") else "") \
        + (f" [{b['hesap']}]" if b.get("hesap") else "")
    ofis.db.olay_yaz(ofis.proje_id, "limit",
                     f"Lider {lider['ad']}: {ad(eski)} {neden} "
                     f"-> {ad(yeni)} ile devam.",
                     ajan_ad=lider["ad"], gorev_id=gorev_id)
    ofis.bellek.karar_yaz(
        f"Lider {lider['ad']} {ad(eski)} yerine {ad(yeni)} ile kosuldu.",
        f"Onceki basamagin {neden}. Lider durursa butun ofis "
        "durur; liderin turu temiz oturumdur ve baglamini defterden alir, "
        "devirde kaybolan bir sey yoktur.",
        lider["ad"], tur="teknik", gorev_id=gorev_id)



def sonraki(basamaklar: list, simdiki_sira: int) -> dict:
    """Bir sonraki basamak. Yoksa `ZincirBitti`."""
    if simdiki_sira + 1 >= len(basamaklar):
        raise ZincirBitti(
            "Nobet zinciri tukendi: devredecek baska motor/model kalmadi. "
            "Limitler yenilenene kadar bu is bekleyecek."
        )
    return basamaklar[simdiki_sira + 1]
