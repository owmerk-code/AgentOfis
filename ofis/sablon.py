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
    # 05.10.2026 (patron): takim bir ISE bakar -- magaza, mobil uygulama,
    # SaaS, bot, icerik... Uyeler lider HARIC en fazla 5 (AZAMI_UYE 6).
    # Motor ve model MESLEK KATALOGUNDAN gelir (`roller.MESLEK_MOTORU`).
    "ticaret": Sablon(
        "ticaret", "Mağaza",
        "Mağazanın günlük işleri: ürün, metin, görsel, reklam, müşteri — "
        "riskli eylemler onaya düşer.",
        (("magaza", "Katalog, stok, siparis ve urun kayitlari."),
         ("metin", "Urun aciklamasi ve duyuru metni."),
         ("tasarim", "Urun ve kampanya gorselleri."),
         ("reklam", "Kampanya kurar; butce ve yayin onaydan gecer."),
         ("destek", "Musteri yanitlarinin TASLAGINI yazar, gondermez."))),
    # 09.10.2026 (patron): ajanlar OFISIN KENDISINI gelistirir. Takimin koku
    # calisan ofisin KOPYASIDIR (`gelistirme.kopya_hazirla`); kapanan isin
    # kaydi kopyada tam sinamadan gecer, patron kurulum kartiyla kurar.
    "gelistirme": Sablon(
        "gelistirme", "Ofis geliştirme",
        "Ajanlar AgentOfis'in kendisini geliştirir: ayrı kopyada çalışır, tam "
        "sınama geçerse kurulum kartı sana gelir; sen onaylamadan çalışan ofis değişmez.",
        (("backend", "Ofisin kodunu yazar (Python, panel); sinamasini da yazar."),
         ("kalite", "Bagimsiz sinama: degisiklik eski davranisi bozmadi, yeni sinama ateş ediyor."))),
    "mobil": Sablon(
        "mobil", "Mobil uygulama",
        "Mobil uygulama geliştirme: ölçüt, ekran, sunucu, test.",
        (("urun", "Kabul olcutunu yazar; belirtim hatasi en buyuk hata kumesi."),
         ("arayuz", "Uygulamanin ekranlari ve kullanici deneyimi."),
         ("backend", "Sunucu tarafi, veri ve is kurallari."),
         ("kalite", "Bagimsiz sinama: testler yesil VE iddia sayisi azalmadi."))),
    "urun": Sablon(
        "urun", "SaaS / web ürünü",
        "Web tabanlı ürün: ölçüt + geliştirme + yayın + sınama.",
        (("urun", "Kabul olcutunu yazar; belirtim hatasi en buyuk hata kumesi."),
         ("arayuz", "Ekranlar."),
         ("backend", "Sunucu tarafi."),
         ("devops", "Derleme, yayin, ortam; yayina alma onaya duser."),
         ("kalite", "Bagimsiz sinama."))),
    "yazilim": Sablon(
        "yazilim", "Web sitesi / yazılım",
        "Uygulama, web sitesi, servis: sunucu + arayüz + arama + test.",
        (("backend", "Sunucu tarafi, veri ve is kurallari."),
         ("arayuz", "Kullanicinin gordugu ekranlar."),
         ("seo", "Arama gorunurlugu: baslik, ustveri, ic baglanti."),
         ("kalite", "Testler yesil VE iddia sayisi azalmadi -- bagimsiz goz."))),
    "bot": Sablon(
        "bot", "Bot / otomasyon",
        "Bot ve otomasyon: dış servisleri bağlar, işletir, sınar.",
        (("entegrasyon", "Dis servisi baglar (API, baglayici, bot)."),
         ("backend", "Botun is mantigi ve verisi."),
         ("kalite", "Bagimsiz sinama."))),
    "icerik": Sablon(
        "icerik", "İçerik / sosyal medya",
        "Metin, görsel, video ve arama görünürlüğü: yayına hazır içerik.",
        (("metin", "Metni yazar."),
         ("tasarim", "Gorsel sartlara uygun uretir."),
         ("video", "Kisa video (Flow) uretir."),
         ("seo", "Aranabilirlik ve baslik/aciklama."))),
    "studyo": Sablon(
        "studyo", "Video / görsel stüdyo",
        "Video ve görsel üretimi: istem, üretim, metin.",
        (("video", "Videoyu gomulu tarayicida Flow ile uretir."),
         ("tasarim", "Gorselleri uretir."),
         ("metin", "Senaryo, alt yazi ve aciklama metni."))),
    "arastirma": Sablon(
        "arastirma", "Araştırma",
        "Kaynaklı araştırma ve ölçülü analiz.",
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

#: Eski tercih sirasi -- artik MESLEK KATALOGU belirler (`roller.meslek_motoru`).
#: Katalogun motoru kurulu degilse roller.MOTOR_YEDEK_SIRASI.
MOTOR_TERCIHI = roller.MOTOR_YEDEK_SIRASI


class SablonHatasi(RuntimeError):
    pass


#: PATRONUN SABLONLARI (05.10.2026): "iyi calisan takimi sablon yap".
#: Kod degil AYAR: `sablon_ozel` = JSON liste. Hazir sablonlarin ADINI
#: ezemez (iki ayni adli sablon, hangisinin kurulacagini belirsiz yapar).
ANAHTAR_OZEL = "sablon_ozel"


def ozel_liste(db=None, proje_id: str = "") -> list:
    if db is None or not proje_id:
        return []
    import json
    try:
        ham = json.loads(db.ayar_oku(proje_id, ANAHTAR_OZEL, "[]") or "[]")
    except ValueError:
        return []
    out = []
    for d in ham:
        try:
            out.append(Sablon(d["ad"], d["baslik"], d.get("aciklama", ""),
                              tuple((u[0], u[1]) for u in d["uyeler"])))
        except (KeyError, IndexError, TypeError):
            continue
    return out


def ozel_kaydet(db, proje_id: str, ad: str, baslik: str, aciklama: str,
                uyeler) -> Sablon:
    """Patronun sablonu. Uyeler (rol, neden); lider SAYILMAZ (kurarken
    lidersiz takima sablon kendisi ekler)."""
    import json
    import re
    ad = (ad or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", ad):
        raise SablonHatasi("Sablon adi kucuk harf/rakam/tire olmali (orn. magaza-2).")
    if ad in SABLONLAR:
        raise SablonHatasi(f"'{ad}' hazir bir sablonun adi; baska ad sec.")
    temiz = []
    for rol, neden in uyeler:
        r = roller.coz(rol)
        if r == "lider":
            continue
        temiz.append((r, (neden or "").strip() or roller.ROLLER[r].ozet))
    if not temiz:
        raise SablonHatasi("Sablonda liderden baska en az bir uye olmali.")
    if len(temiz) > 5:
        raise SablonHatasi("Sablon lider haric en fazla 5 uye tasir (ekip siniri 6).")
    kayit = [d for d in (json.loads(db.ayar_oku(proje_id, ANAHTAR_OZEL, "[]") or "[]"))
             if d.get("ad") != ad]
    kayit.append({"ad": ad, "baslik": (baslik or ad).strip()[:60],
                  "aciklama": (aciklama or "").strip()[:200],
                  "uyeler": [list(u) for u in temiz]})
    db.ayar_yaz(proje_id, ANAHTAR_OZEL, json.dumps(kayit, ensure_ascii=False))
    return Sablon(ad, (baslik or ad).strip()[:60], (aciklama or "").strip()[:200],
                  tuple(temiz))


def ozel_sil(db, proje_id: str, ad: str) -> bool:
    import json
    kayit = json.loads(db.ayar_oku(proje_id, ANAHTAR_OZEL, "[]") or "[]")
    kalan = [d for d in kayit if d.get("ad") != ad]
    db.ayar_yaz(proje_id, ANAHTAR_OZEL, json.dumps(kalan, ensure_ascii=False))
    return len(kalan) != len(kayit)


def liste(db=None, proje_id: str = "") -> list:
    return list(SABLONLAR.values()) + ozel_liste(db, proje_id)


def bul(ad: str, db=None, proje_id: str = ""):
    ad = (ad or "").strip().lower()
    return next((s for s in liste(db, proje_id) if s.ad == ad), None)


def motor_sec(rol_ad: str, musait=None) -> str:
    """Rol icin KURULU bir motor: once MESLEK KATALOGU (05.10.2026), o
    kurulu degilse yedek sira. Hic kurulu motor yoksa REDDEDILIR --
    kosamayacak ajan onerilmez."""
    musait = musait if musait is not None else {
        m for m, var in musait_motorlar().items() if var}
    roller.ROLLER[rol_ad]           # tanimsiz rol burada KeyError verir
    if musait:
        motor, _, _ = roller.meslek_motoru(rol_ad, musait={m: True for m in musait})
        if motor in musait:
            return motor
    raise SablonHatasi(
        f"'{rol_ad}' rolu icin kurulu bir motor yok (musait: "
        f"{', '.join(sorted(musait)) or 'hicbiri'}).")


def oneri_uret(ad: str, mevcut_adlar, *, lider_var: bool = True,
               musait=None, db=None, proje_id: str = "") -> dict:
    """Sablondan `Ekip.oneriyi_dogrula`nin bekledigi bicimde oneri.

    Kanadin lideri YOKSA sablon bir lider de ekler: lidersiz kanatta
    orkestra is dagitamaz ve incelemeyi kimse yapamaz -- kurulan kadro
    tahtada var gorunur, calismaz.
    """
    s = bul(ad, db, proje_id)
    if s is None:
        raise SablonHatasi(
            f"Bilinmeyen sablon: '{ad}'. Gecerli: "
            f"{', '.join(x.ad for x in liste(db, proje_id))}")
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
