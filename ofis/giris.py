"""GIRIS ISTEGI -- ajan bir hesaba girilmesi gerektigini SOYLER, insan girer.

Kullanici (28.09.2026): *"burda da boyle isliyor: sen isi yapiyorsun, giris
yapilmasi gereken bir yer varsa soruyorsun, giriyorum, sonra sen devam
ediyorsun. Agent sisteminde de oyle olmali."*

Bugune kadar ajanin elinde bunun bir yolu yoktu. Giris sayfasina gelen ajan
ya "erisemedim" deyip durur, ya da -- daha kotusu -- sifreyi TAHMIN etmeye,
bir yerden bulmaya, forma yazmaya kalkardi. Ikisi de yanlis:

  * SIFRE AJANIN ELINE HIC GECMEZ. Ajan bir modeldir; yazdigi her sey olay
    defterine, saglayicinin sunucusuna ve belki GitHub'daki metin dokumune
    gider. Sifreyi insan, kendi eliyle, paylasilan tarayicida (kabin) yazar.
    Ajan yalniz "oturum acik" halini gorur -- insanin Claude Code'la
    calisirken yaptigi gibi.
  * GIRIS BIR ONAYDIR. Ayri bir tablo acilmadi: bekleyen ajan, korunan
    kilit, "senden bekleniyor" karti, cevap gelince halkanin surmesi ve
    devam metnindeki "cevaplanan onaylar" -- hepsi `onay` tablosunda zaten
    calisiyor. Iki yerde tutulan her sey en az bir kez kayar.

Uc tur:

  web        Bir sitenin girisi. Insan kabinde girer. "Giris yaptim"
             denince is PAYLASILAN KABINE tasinir (o sitenin kaynagiyla):
             ajanin kendi tarayicisi ayri, oturumsuz bir profildir ve
             insanin girisini gormez. Kabin yalniz insanin isaret ettigi
             kaynaklara acilir -- burada isaret eden, insanin onayidir.
  baglayici  claude.ai baglayicisi (Shopify, Gmail ...). Insan claude.ai
             ayarlarindan yetkilendirir. "Yaptim" denince ofis OLCER
             (`claude mcp list`); hala bagli degilse cevap REDDEDILIR --
             "yaptim" demek, yapildigini kanitlamaz. Olculunce baglayici
             bu ise acilir (bedeli ~225k jeton; kart bunu soyler).
  diger      Ofisin taniyamadigi bir giris (masaustu uygulamasi, SMS
             dogrulamasi, e-posta onayi). Insan yapar, "yaptim" der; ofis
             olcemedigini SOYLER, uydurmaz.

"Yapamam" da bir cevaptir: gerekcesi ajana gider, ajan baska yoldan
ilerler ya da isi yarim oldugunu soyleyerek bitirir.
"""
from __future__ import annotations

import json

from . import baglayici, tarayici
from .postane import PostaneHatasi

#: Onay kaydinin eylem metninin basi. Panel ve kabuk karti buna gore
#: cizer; `onayla` komutu bu kaydi buraya yonlendirir.
ONEK = "GIRIS:"
#: Ayrinti metninin sonuna eklenen, makinenin okudugu satir.
VERI = "GIRIS_VERI "
TURLER = ("web", "baglayici", "diger")


class GirisHatasi(ValueError):
    pass


def giris_mi(onay: dict) -> bool:
    return str((onay or {}).get("eylem") or "").startswith(ONEK)


def ayristir(onay: dict) -> dict | None:
    """Onay kaydindan giris istegini okur. Giris degilse None."""
    if not giris_mi(onay):
        return None
    ayrinti = str(onay.get("ayrinti") or "")
    i = ayrinti.rfind(VERI)
    if i < 0:
        return None
    try:
        v = json.loads(ayrinti[i + len(VERI):].strip())
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def insan_talimati(v: dict) -> str:
    """Insana NE yapacagi -- kart ve kabuk ayni cumleyi basar."""
    tur = v.get("tur")
    if tur == "web":
        return (f"Tarayici panosunda (kabin) {v.get('adres')} adresini ac ve "
                "KENDIN giris yap. Sifreyi ajana ya da ofise YAZMA. Bitince "
                "'Giris yaptim' de: is paylasilan kabine tasinir ve ajan "
                "senin oturumunla devam eder.")
    if tur == "baglayici":
        return (f"'{v.get('hizmet')}' baglayicisini yetkilendir: terminalde "
                f"`claude mcp login \"claude.ai {v.get('hizmet')}\"` (ofisin "
                "gordugu CLI'in hesabidir; claude.ai web sayfasi ayri "
                "olabilir). Bitince 'Giris yaptim' de: ofis "
                "baglandigini OLCER ve bu ise acar (~225k jeton/tur).")
    return ("Istenen girisi kendin yap (ayrinti asagida). Ofis bunu "
            "olcemez; 'Giris yaptim' dediginde sozune guvenilir.")


def iste(ofis, ajan: str, gorev_no, *, tur: str, hizmet: str,
         adres: str = "", neden: str = "") -> dict:
    """Ajanin giris istegi. Kayit `onay` tablosuna, beklemeyle."""
    tur = (tur or "").strip().lower()
    hizmet = (hizmet or "").strip()
    neden = (neden or "").strip()
    if tur not in TURLER:
        raise GirisHatasi(f"Bilinmeyen giris turu: {tur!r}. "
                          f"Secenekler: {', '.join(TURLER)}")
    if not hizmet:
        raise GirisHatasi("Hangi hizmete giris gerektigi (hizmet) bos olamaz.")
    if not neden:
        raise GirisHatasi("Neden giris gerektigi (neden) bos olamaz -- insan "
                          "neye yetki verdigini bilmeli.")
    if gorev_no is None:
        raise GirisHatasi("Giris istegi bir ise baglidir; gorev yok.")
    v = {"tur": tur, "hizmet": hizmet[:120], "neden": neden[:400]}
    if tur == "web":
        try:
            v["adres"] = (adres or "").strip()
            v["kaynak"] = tarayici.kaynak_normalle(v["adres"])
        except Exception as exc:                       # noqa: BLE001
            raise GirisHatasi(f"Giris adresi gecersiz: {exc}")
        if not v["kaynak"].startswith(("http://", "https://")):
            raise GirisHatasi("Web girisi icin http(s) adresi gerekir.")
    elif tur == "baglayici":
        # Ad baglayici defterinin adlandirmasina yakin tutulur; olcum
        # cevap aninda yapilir (simdi bagli olmasi gerekmez -- sorunun
        # kendisi "bagli degil").
        v["adres"] = ""
    else:
        v["adres"] = (adres or "").strip()[:300]
    metin = (f"{neden}\n\nNE YAPACAKSIN: {insan_talimati(v)}\n\n"
             f"{VERI}{json.dumps(v, ensure_ascii=False)}")
    onay = ofis.postane.onay_iste(
        ajan, f"{ONEK} {hizmet} ({tur})", ayrinti=metin, risk="orta",
        gorev_no=gorev_no)
    ofis.db.olay_yaz(ofis.proje_id, "giris_istendi",
                     f"#{gorev_no}: {hizmet} ({tur}) -- {neden[:200]}",
                     ajan_ad=ajan,
                     gorev_id=ofis.tahta.gorev(gorev_no)["id"])
    return {**onay, "giris": v}


def cevapla(ofis, onay_id: str, *, yapildi: bool, not_: str = "",
            cevaplayan: str = "insan") -> dict:
    """Insanin cevabi. "Yapildi" olculebiliyorsa OLCULUR."""
    kayit = None
    for o in ofis.postane.bekleyen_onaylar():
        if o["id"] == onay_id:
            kayit = o
            break
    if kayit is None:
        raise GirisHatasi("Bekleyen boyle bir giris istegi yok (cevaplanmis "
                          "ya da kimlik yanlis).")
    v = ayristir(kayit)
    if v is None:
        raise GirisHatasi("Bu kayit bir giris istegi degil.")
    no = kayit.get("gorev_no")
    if not yapildi:
        if not (not_ or "").strip():
            raise GirisHatasi("'Yapamam' icin gerekce zorunlu -- ajan neden "
                              "girilmedigini bilmeli.")
        try:
            r = ofis.postane.onay_cevapla(onay_id, onayla=False, not_=not_,
                                          cevaplayan=cevaplayan)
        except PostaneHatasi as exc:
            raise GirisHatasi(str(exc))
        ofis.db.olay_yaz(ofis.proje_id, "giris_yapilmadi",
                         f"#{no}: {v['hizmet']} -- {not_[:200]}",
                         gorev_id=kayit.get("gorev_id"))
        return {**r, "giris": v}

    aciklama = ""
    if v["tur"] == "web":
        ofis.tahta.giris_uygula(no, kaynak=v["kaynak"])
        aciklama = (f"Patron {v['hizmet']} icin GIRIS YAPTI. Is artik "
                    f"PAYLASILAN KABINDE ({v['kaynak']}) kosuyor: tarayicin "
                    "patronun oturumunu goruyor. Sifre sende YOK ve olmasi "
                    "gerekmiyor; giris sayfasini yeniden gorursen tekrar "
                    "`giris_iste` cagir.")
    elif v["tur"] == "baglayici":
        # "YAPTIM" KANIT DEGIL: olculur. Bayat onbellek yanlis "hala bagli
        # degil" derdi -- taze olcum.
        try:
            baglayici.durum(taze=True)
            ad = baglayici.dogrula([v["hizmet"]])[0]
        except Exception as exc:                       # noqa: BLE001
            raise GirisHatasi(
                f"'{v['hizmet']}' hala BAGLI gorunmuyor ({exc}). claude.ai "
                "ayarlarindan yetkilendirdiysen birkac saniye sonra tekrar dene.")
        ofis.tahta.giris_uygula(no, baglayici_ad=ad)
        aciklama = (f"Patron {ad} baglayicisini yetkilendirdi ve ofis "
                    "baglandigini OLCTU. Bir sonraki turda bu ise acik.")
    else:
        aciklama = (f"Patron {v['hizmet']} icin gerekeni yaptigini soyledi "
                    "(ofis bunu olcemedi). Devam et; hala engel varsa sor.")
    if (not_ or "").strip():
        aciklama += f" Patronun notu: {not_.strip()}"
    try:
        r = ofis.postane.onay_cevapla(onay_id, onayla=True, not_=aciklama,
                                      cevaplayan=cevaplayan)
    except PostaneHatasi as exc:
        raise GirisHatasi(str(exc))
    ofis.db.olay_yaz(ofis.proje_id, "giris_yapildi",
                     f"#{no}: {v['hizmet']} ({v['tur']})",
                     gorev_id=kayit.get("gorev_id"))
    return {**r, "giris": v}
