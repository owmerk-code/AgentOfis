# -*- coding: utf-8 -*-
"""TAKIM SABLONLARI -- lideri cagirmadan, ucretsiz ve kararli kadro onerisi.

Rakipten alinan madde: *"sablon secici + KURMADAN ONCE ekip onizlemesi"*.
Bizde ekip onerisi zaten vardi (`ofis/ekip.py`) ama her oneri bir LIDER
TURU demekti -- jeton, sure ve modelin o gunku yorumu. Cogu takim bir
kalip: "yazilim isi" hep benzer rollerle kurulur.

Karar: sablon YENI BIR YOL DEGILDIR. Sablondan uretilen sey siradan bir
ekip onerisidir -- ayni kapidan gecer (`Ekip.oneriyi_dogrula`: tanimsiz
rol, kurulu olmayan motor, kadroda olan ad, gerekcesiz uye, 6 uye
siniri), ayni tabloya yazilir, ayni onizlemeyle insana gosterilir ve
ayni `kur`/`reddet` ile karara baglanir. Ayri bir kurma yolu acsaydik
kurallar iki yerde olurdu ve biri otekinden kayardi.

ALAN-BAGIMSIZ: sablonlar sektor degil TAKIM BICIMIDIR (yazilim, icerik,
ticaret, arastirma, urun). Cekirdekte tek bir sektor adi gecmez.

MODEL ONIZLEMEDE GORUNUR: motor musaitlikten, model rolun KADEMESINDEN
secilir (`Ekip._sakla`) -- onizlemede gorunmeyen bir secim, onay
alinmamis bir secimdir.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import roller
from .motor import musait_motorlar


@dataclass(frozen=True)
class Sablon:
    ad: str
    baslik: str
    aciklama: str
    #: (rol, bu takimda NEDEN var) -- gerekce bos olamaz (ekip kapisi).
    uyeler: tuple


SABLONLAR = {
    "yazilim": Sablon(
        "yazilim", "Yazilim",
        "Uygulama, web sitesi, servis: sunucu + arayuz + test.",
        (("backend", "Sunucu tarafi, veri ve is kurallari."),
         ("arayuz", "Kullanicinin gordugu ekranlar."),
         ("kalite", "Testler yesil VE iddia sayisi azalmadi -- bagimsiz goz."))),
    "urun": Sablon(
        "urun", "Urun gelistirme",
        "Olcut yazan dahil tam urun ekibi: ne yapilacagi + yapilmasi + sinanmasi.",
        (("urun", "Kabul olcutunu yazar; belirtim hatasi en buyuk hata kumesi."),
         ("backend", "Sunucu tarafi."),
         ("arayuz", "Ekranlar."),
         ("kalite", "Bagimsiz sinama."))),
    "icerik": Sablon(
        "icerik", "Icerik",
        "Metin, arama gorunurlugu ve gorsel: yayina hazir icerik.",
        (("metin", "Metni yazar."),
         ("seo", "Aranabilirlik ve baslik/aciklama."),
         ("tasarim", "Gorsel sartlara uygun uretir ya da istemini yazar."))),
    "ticaret": Sablon(
        "ticaret", "Satis ve musteri",
        "Magaza/katalog, reklam ve musteri iletisimi -- riskli eylemler ONAYA duser.",
        (("magaza", "Katalog ve urun kayitlari."),
         ("reklam", "Kampanya kurar; butce ve yayin onaydan gecer."),
         ("destek", "Musteri yanitlarinin TASLAGINI yazar, gondermez."))),
    "arastirma": Sablon(
        "arastirma", "Arastirma",
        "Kaynakli arastirma ve olculu analiz.",
        (("arastirma", "Kaynakli tarama, her iddia icin baglanti."),
         ("analiz", "Sayilar ve karsilastirma."))),
}

#: Ad havuzu -- kararli: ayni kadroda ayni sablon ayni adlari onerir.
#: Kadroda olan ad ATLANIR (ad geri donmez, sicil okunabilir kalsin).
AD_HAVUZU = (
    "ada", "arda", "asli", "baris", "ceren", "cem", "defne", "derin", "ece",
    "ekin", "elif", "emre", "eren", "ilgaz", "irem", "kaan", "lale", "mert",
    "nehir", "nil", "ozan", "pelin", "sena", "toprak", "tuna", "umut",
    "yigit", "zeynep", "atlas", "bora", "duru", "efe", "gizem", "kuzey",
)

#: Motor tercih sirasi. Ilk MUSAIT olan secilir -- olculur, varsayilmaz.
MOTOR_TERCIHI = ("claude", "codex")


class SablonHatasi(RuntimeError):
    pass


def liste() -> list:
    return list(SABLONLAR.values())


def motor_sec(rol_ad: str, musait=None) -> str:
    """Rol icin KURULU bir motor, `MOTOR_TERCIHI` sirasiyla.

    Tercih listesinde olmayan motor (ornegin defterden cikarilmis
    gemini) musait gorunse bile SECILMEZ: sablon, insanin kullanmamaya
    karar verdigi bir motoru kadroya sokmamali."""
    musait = musait if musait is not None else {
        m for m, var in musait_motorlar().items() if var}
    roller.ROLLER[rol_ad]           # tanimsiz rol burada KeyError verir
    for m in MOTOR_TERCIHI:
        if m in musait:
            return m
    raise SablonHatasi(
        f"'{rol_ad}' rolu icin kurulu bir motor yok (musait: "
        f"{', '.join(sorted(musait)) or 'hicbiri'}).")


def oneri_uret(ad: str, mevcut_adlar, *, lider_var: bool = True,
               musait=None) -> dict:
    """Sablondan `Ekip.oneriyi_dogrula`nin bekledigi bicimde oneri.

    Kanadin lideri YOKSA sablon bir lider de ekler: lidersiz kanatta
    orkestra is dagitamaz ve incelemeyi kimse yapamaz -- kurulan kadro
    tahtada var gorunur, calismaz.
    """
    s = SABLONLAR.get((ad or "").strip().lower())
    if s is None:
        raise SablonHatasi(
            f"Bilinmeyen sablon: '{ad}'. Gecerli: {', '.join(SABLONLAR)}")
    kullanilan = {str(a).lower() for a in mevcut_adlar}
    havuz = [x for x in AD_HAVUZU if x not in kullanilan]
    uyeler_kaynak = list(s.uyeler)
    if not lider_var:
        uyeler_kaynak.insert(0, ("lider", "Bu kanadin lideri yok: isi bolen "
                                          "ve inceleyen olmadan kadro calismaz."))
    if len(havuz) < len(uyeler_kaynak):
        raise SablonHatasi("Ad havuzu tukendi; ajani elle ise al.")
    uyeler = []
    for (rol, neden), isim in zip(uyeler_kaynak, havuz):
        uyeler.append({"ad": isim, "rol": rol,
                       "motor": motor_sec(rol, musait), "gerekce": neden})
    return {"gerekce": f"Sablon: {s.baslik} -- {s.aciklama}",
            "uyeler": uyeler}
