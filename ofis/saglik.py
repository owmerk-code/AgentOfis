# -*- coding: utf-8 -*-
"""Saglik: ofis KENDI tikandigini fark etsin.

Bu projenin karsi kuruldugu hata sinifi tek cumleyle sudur: **sistem
saglikli gorunurken yanlis calisiyor.** Bugune kadar bulunan her ciddi
hata sessizdi -- `.CMD` tuzagi, zaman damgasi beraberligi, sessizce yok
sayilan motor fabrikasi, yanlis klasorde kosan inceleme, sirali sanilan
paralellik, teslim edilmeyen soru, plan kipinin oldurdugu arastirma.

`durum` komutu ne oldugunu SAYAR ("2 bitti, 1 calisiyor"). Saymak
yetmiyor: 19.09.2026'da bir is `calisiyor` gorunuyordu, lider *"tamamlan-
inca sana sunacagim"* diyordu ve **hicbir sey onu ilerletmeyecekti.**
Tabloda her sey normaldi. Eksik olan soru suydu: *bu sayilar ANLAMLI mi?*

Buradaki her denetim bir SORUYA cevap verir ve cevabi olumsuzsa NE
YAPILACAGINI da soyler. Teshis koyup care soylemeyen gosterge, insani
bir kez daha dusunmeye zorlar.

Iki kural:

* **UYDURMAZ.** Olcemedigi seye "iyi" demez; olcemiyorsa onu soyler.
  Yanlis gosteren bir gosterge, gostergesizlikten kotudur.
* **KARAR VERMEZ, DUZELTMEZ.** Tikanmis bir isi kendi kendine serbest
  birakmaz. Otomatik duzelten bir teshis araci, duzelttigi seyi bir daha
  gostermez ve sorunun KOKU hic gorunmez. Ne yapilacagini soyler,
  yapmayi insana ya da ilgili komuta birakir.
"""

from __future__ import annotations

import re

from .db import simdi
from . import butce
from . import motor_saglik
from .motor import motor_ac, musait_motorlar
from .tahta import KILIT_KIRA_SANIYE, _yas_saniye

#: Bir isin "kimse ilerletmiyor" sayilmasi icin gecmesi gereken sure.
#: Kilit kirasindan uzun tutuldu: kira dolmadan is zaten canli sayilir.
TIKANMA_SANIYE = KILIT_KIRA_SANIYE * 2

#: Incelemede bu kadar bekleyen is, liderin ona hic bakmadigini gosterir.
INCELEME_SANIYE = KILIT_KIRA_SANIYE * 2

#: Kayda gecmis olmasi ONEMLI olan sir desenleri.
#:
#: Ofis dis servislerle calisacak (Gemini, Shopify, Meta...) ve anahtarlar
#: ORTAM DEGISKENINDE durur -- kodda da veritabaninda da degil. Ama ajan
#: bir anahtari yanlislikla kanita, karara ya da hata metnine yazabilir:
#: `echo $GEMINI_API_KEY` bir terminal kaniti olarak dusebilir.
#:
#: **Sir, kayda gecerse sir olmaktan cikar.** Veritabani yedeklenir,
#: kopyalanir, brifinge girer, panelde gorunur. Bir kez sizan anahtar
#: geri alinamaz; yalnizca DEGISTIRILEBILIR.
#:
#: Tarayici DEGERI ASLA BASMAZ -- yalnizca nerede oldugunu soyler.
#: Sizinti raporu, sizintinin kendisi olmamali.
SIR_DESENLERI = (
    ("Google AI Studio anahtari", re.compile(r"AIza[0-9A-Za-z_-]{30,}")),
    ("OpenAI/Anthropic anahtari", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("GitHub belirteci", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("Slack belirteci", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("Genel 'gizli anahtar' atamasi",
     re.compile(r"(?i)(api[_-]?key|secret|token|password)[\"' :=]{1,4}[A-Za-z0-9_\-]{16,}")),
)

#: Agirlik sirasi: once isi DURDURAN seyler, sonra bilgi.
AGIRLIK = {"tikali": 0, "insan": 1, "uyari": 2, "bilgi": 3}


def _bulgu(agirlik, baslik, ayrinti, care, kod=""):
    """`kod` SABIT bir kimlik: panel, kendi kartini cizdigi bulguyu
    (ekip/guncelleme onerisi) basliga bakarak degil koda bakarak ayirir.
    Baslik metnine gore suzmek, metin degistigi gun sessizce kirilirdi."""
    return {"agirlik": agirlik, "baslik": baslik, "ayrinti": ayrinti,
            "care": care, "kod": kod}


class Saglik:
    def __init__(self, ofis) -> None:
        self.ofis = ofis
        self.db = ofis.db
        self.proje_id = ofis.proje_id

    def denetle(self) -> dict:
        bulgular = []
        for denetim in (self._motorlar, self._tikanan_isler, self._sahipsiz_isler,
                        self._bekleyen_inceleme, self._kosulamayan_isler,
                        self._insan_kuyrugu, self._oksuz_kilitler,
                        self._basarisiz_ajanlar, self._modelsiz_ajanlar,
                        self._sizan_sirlar, self._kapi_butcesi,
                        self._bekleyen_ekip, self._bekleyen_guncelleme):
            try:
                bulgular.extend(denetim() or [])
            except Exception as exc:
                # Denetimin kendisi dusse bile SESSIZ kalmaz. Calismayan
                # bir denetim, "sorun yok" demekle aynidir -- ve bu tam
                # olarak kacindigimiz sey.
                bulgular.append(_bulgu(
                    "uyari", f"Denetim calismadi: {denetim.__name__}",
                    str(exc), "Bu denetimin sonucu BILINMIYOR -- 'sorun yok' demek degil."))
        bulgular.sort(key=lambda b: AGIRLIK.get(b["agirlik"], 9))
        return {
            "an": simdi(),
            "bulgular": bulgular,
            "tikali": sum(1 for b in bulgular if b["agirlik"] == "tikali"),
            "insan": sum(1 for b in bulgular if b["agirlik"] == "insan"),
            "saglikli": not any(b["agirlik"] in ("tikali", "uyari")
                                for b in bulgular),
        }

    # -- denetimler --------------------------------------------------------

    def _kapi_butcesi(self) -> list:
        """Kapi modeline (fable) haftada ne kadar gitti.

        Tur basina tavan tek bir turu tutar; bu, COK SAYIDA makul turun
        toplamini tutar. Kullanicinin plani Max **5x** -- fable haftalik
        payin %50'sine kadar dahil, yani cep var ama sinirsiz degil.

        Tavana YAKLASMAK da bilgidir: insan ancak gorebildigi seyi
        yonetir. Sifir harcamada SESSIZ kalinir -- her sey hakkinda
        konusan gosterge, okunmaz.
        """
        h = butce.kapi_acik_mi(self.db, self.proje_id)
        if h["harcanan"] <= 0:
            return []
        oran = h["harcanan"] / h["tavan"] if h["tavan"] else 1.0
        ayrinti = (f"Son {h['pencere_gun']} gunde {h['tur']} kapi turu, "
                   f"${h['harcanan']:.2f} / ${h['tavan']:.2f}")
        if not h["acik"]:
            return [_bulgu(
                "uyari", "Kapi modeli haftalik tavani DOLDU", ayrinti,
                "Yukseltme kapali; inceleme liderin kendi modeliyle kosuyor. "
                "Is durmuyor. Tavan: ofis/butce.py HAFTALIK_TAVAN_USD")]
        if oran >= 0.75:
            return [_bulgu(
                "bilgi", "Kapi modeli haftalik tavanina yaklasildi", ayrinti,
                f"Kalan ${h['kalan']:.2f}. Dolunca yukseltme kendiliginden "
                "kapanir -- is durmaz.")]
        return [_bulgu("bilgi", "Kapi modeli kullanimi", ayrinti,
                       f"Kalan ${h['kalan']:.2f}. Sorun yok, bilgi.")]

    def _motorlar(self) -> list:
        musait = musait_motorlar()
        gercek = [ad for ad, var in musait.items() if var and ad != "sahte"]
        if not gercek:
            return [_bulgu("tikali", "Kurulu gercek motor yok",
                           f"Kayitli: {musait}",
                           "Hicbir is kosamaz. `claude` ya da `codex` CLI'ini kur.")]
        kullanilan = {a["motor"] for a in self.ofis.kadro.liste()}
        eksik = sorted(m for m in kullanilan if not musait.get(m))
        bulgular = []
        # MOTOR SAGLIGI (E16): kurulu ama KULLANILAMAZ (giris yok, oturum
        # sunucuda dustu, hesap askida). Once yalniz "kurulu degil" denirdi;
        # girissiz bir motor "sorun yok" gorunuyordu. Motor kendi sebebini
        # soyler (`durum_notu`) -- burada ikinci bir teshis YAZILMAZ.
        kurulu_degil, girissiz = [], []
        for m in eksik:
            try:
                motor = motor_ac(m)
                notu = motor.durum_notu()
                kurulu = bool(getattr(motor, "calistirilabilir", True))
            except Exception as exc:          # noqa: BLE001
                notu, kurulu = f"acilamadi: {exc}", False
            (girissiz if kurulu else kurulu_degil).append((m, notu))
        if kurulu_degil:
            bulgular.append(_bulgu(
                "tikali", "Ajanlarin motoru kurulu degil: "
                + ", ".join(m for m, _ in kurulu_degil),
                f"Musait motorlar: {sorted(gercek)}",
                "O ajanlarin isleri kosamaz. Motoru kur ya da "
                "`ise-al --motor` ile degistir."))
        for m, notu in girissiz:
            # Tikali DEGIL: zincir o motoru atlar, is sonraki basamakta
            # kosar. Ama insan eylemi ister (giris) -- yoksa o hesap hic
            # kullanilmaz ve yuk oteki hesaplara biner.
            bulgular.append(_bulgu(
                "insan", f"{m} motoru kurulu ama KULLANILAMIYOR", notu,
                "Giris yapilana kadar o ajanlarin isleri zincirdeki sonraki "
                "motorda kosar."))
        # KOTASI DOLU hesap: saglayicinin kendi bildirimi (pencere %100).
        try:
            for d in motor_saglik.dolu_hesaplar(self.db, self.proje_id):
                if d["motor"] not in kullanilan:
                    continue
                ad = d["motor"] + (f" [{d['hesap']}]" if d["hesap"] else "")
                bulgular.append(_bulgu(
                    "uyari", f"{ad} hesabi DOLU ({d['pencere']} penceresi)",
                    f"Yenilenme: {d['yenilenme']:%d.%m %H:%M} UTC "
                    f"(~{d['kalan_saat']} sa); olcum {d.get('yas_dk')} dk once.",
                    "Is durmaz: zincir bu hesabi sona alir, sonraki basamak "
                    "kosar. Yenilenince kendiliginden geri gelir."))
        except Exception as exc:              # noqa: BLE001
            bulgular.append(_bulgu("bilgi", "Kota doluluk denetimi BILINMIYOR",
                                   str(exc), "Denetim patladi; sonucu olculemedi."))
        return bulgular

    def _tikanan_isler(self) -> list:
        """`calisiyor` gorunen ama KIMSENIN ilerletmedigi isler.

        Tam olarak 19.09.2026'da yasanan hal: lider "tamamlaninca
        sunacagim" dedi, is tahtada `calisiyor` yaziyordu, hicbir surec
        onu kosturmuyordu. Tabloda normal gorunuyordu.
        """
        bulgular = []
        for g in self.ofis.tahta.liste(durum="calisiyor"):
            if g["sahip"] and self.ofis.postane.bekliyor_mu(g["sahip"])["bekliyor"]:
                continue          # bekliyor: durdurulmus, tikali degil
            yas = _yas_saniye(g["guncellendi"])
            if yas > TIKANMA_SANIYE:
                bulgular.append(_bulgu(
                    "tikali",
                    f"#{g['no']} '{g['baslik']}' calisiyor gorunuyor ama ilerlemiyor",
                    f"{int(yas)} saniyedir degismedi, sahibi: {g['sahip'] or '-'}. "
                    "Hicbir surec onu kosturmuyor.",
                    "`python -m ofis.kabuk devam` ile halkayi dondur."))
        return bulgular

    def _sahipsiz_isler(self) -> list:
        return [_bulgu(
            "uyari", f"#{g['no']} '{g['baslik']}' calisiyor ama SAHIBI YOK",
            "Bu bir tutarsizlik: calisan isin sahibi olmali.",
            "`devam` ile yeniden dagitilir; tekrarlarsa tahtada hata var.")
            for g in self.ofis.tahta.liste(durum="calisiyor") if not g["sahip"]]

    def _bekleyen_inceleme(self) -> list:
        bulgular = []
        for g in self.ofis.tahta.liste(durum="inceleme"):
            yas = _yas_saniye(g["guncellendi"])
            if yas > INCELEME_SANIYE:
                bulgular.append(_bulgu(
                    "tikali",
                    f"#{g['no']} '{g['baslik']}' {int(yas)} saniyedir INCELEMEDE",
                    "Isci isini bitirdi, lider hukum vermedi. Kilit hala tutuluyor.",
                    "`devam` ile lideri incelemeye sok."))
        return bulgular

    def _kosulamayan_isler(self) -> list:
        """Hazir ama kosacak ajani OLMAYAN isler.

        Sessiz olma sebebi: dongu "ilerleme yok" der ve durur; NEDEN
        ilerlemedigini soylemez. Iki ayri sebep var ve careleri farkli.
        """
        bulgular = []
        kadro = [a for a in self.ofis.kadro.liste()
                 if not a["lider_mi"] and a["faz"] != "basarisiz"]
        for g in self.ofis.tahta.liste(durum="hazir"):
            if self.ofis.tahta.blokcular(g["no"]):
                continue          # bagimlilik bekliyor: dogru davranis
            uygun = [a for a in kadro
                     if a["kanat_id"] == g["kanat_id"]
                     and not (g["yazma_alani"] and a["tur"] == "kafa")]
            if not uygun:
                sebep = ("Bu kanatta hic uygun ajan yok"
                         if not any(a["kanat_id"] == g["kanat_id"] for a in kadro)
                         else "Bu is dosya yaziyor ama kanattaki ajanlarin "
                              "hepsi 'kafa' -- kafa ajan dosya yazamaz")
                bulgular.append(_bulgu(
                    "tikali", f"#{g['no']} '{g['baslik']}' hazir ama KOSACAK AJAN YOK",
                    sebep,
                    "`ise-al` ile bu kanada 'eller' bir ajan ekle, "
                    "ya da isi baska kanada tasi."))
        return bulgular

    def _insan_kuyrugu(self) -> list:
        sorular = self.ofis.postane.insan_bekleyenler()
        onaylar = self.ofis.postane.bekleyen_onaylar()
        if not sorular and not onaylar:
            return []
        return [_bulgu(
            "insan", f"{len(sorular)} soru, {len(onaylar)} onay SENI bekliyor",
            "Bu istekler cevaplanmadan ilgili isler ilerlemez.",
            "`python -m ofis.kabuk bekleyen` ile gor, `cevapla` / `onayla` ile yanitla.",
            kod="insan_kuyrugu")]

    def _bekleyen_ekip(self) -> list:
        """Lider kadro ONERDI ama insan ne kurdu ne reddetti.

        Olculdu (20.09.2026): oneri #1 diskte `bekliyor` dururken saglik
        *"senden beklenen yok"* diyordu. Insan kuyrugu yalnizca `soru` ve
        `onay` tablolarina bakiyordu; ekip onerisi AYRI bir tabloda yasar
        (bilerek -- yapili veri, onaya sigmaz) ve denetim onu hic gormedi.

        Bu, projenin karsi kuruldugu sinifin ta kendisi: **yanlis gosteren
        bir gosterge, gostergesizlikten kotudur.** Ustelik bekleyen bir
        oneri, kadroda eksik rol demektir -- lider bir sonraki iste ya
        yanlis ajana verir ya ayni oneriyi tekrar uretir.
        """
        bekleyen = self.ofis.ekip.bekleyenler()
        if not bekleyen:
            return []
        adlar = ", ".join(f"#{o['no']}" for o in bekleyen)
        return [_bulgu(
            "insan", f"{len(bekleyen)} ekip onerisi SENI bekliyor ({adlar})",
            "Lider kadro onerdi; onay gelene kadar kimse ise alinmaz ve "
            "o roller kadroda EKSIK kalir.",
            "`ekip liste` ile gor, `ekip kur <no>` ya da "
            "`ekip red <no> --sebep \"...\"` ile karara bagla.",
            kod="ekip_onerisi")]

    def _bekleyen_guncelleme(self) -> list:
        """Yeni model / CLI surumu bulundu, insan karar vermedi.

        Ekip onerisiyle ayni ders: ayri bir yerde (ayar) yasayan veri eski
        denetimlere kendiliginden GORUNMEZ. Bu denetim olmasaydi oneri
        diskte durur, kimse bilmezdi -- "bildirim gelsin" istegi yarim kalirdi.
        """
        from . import guncelleme
        bekleyen = guncelleme.bekleyenler(self.db, self.proje_id)
        if not bekleyen:
            return []
        ozet = "; ".join(f"#{o['no']} {o['ozet']}" for o in bekleyen[:4])
        return [_bulgu(
            "insan", f"{len(bekleyen)} guncelleme onayini bekliyor",
            ozet + (" ..." if len(bekleyen) > 4 else ""),
            "`guncelle liste` ile gor; `guncelle onayla <no>` (deneme turu "
            "gecerse uygulanir, dusmezse eskisi kalir) ya da "
            "`guncelle reddet <no> --sebep \"...\"`.",
            kod="guncelleme")]

    def _oksuz_kilitler(self) -> list:
        """Isi bitmis ama kilidi duran yollar.

        Oksuz kilit, baska bir isi SEBEPSIZ reddettirir -- ve reddin
        sebebi dogru gorunur ("alan baskasinda"), yani yanlis oldugu
        anlasilmaz.
        """
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT k.yol_oneki, k.ajan_ad, g.no, g.durum, g.baslik "
                "FROM yazma_kilidi k JOIN gorev g ON g.id = k.gorev_id "
                "WHERE k.proje_id = ?", (self.proje_id,)).fetchall()
        # CARE DURUMA GORE DEGISIR. Once tek bir genel cumle vardi
        # ("kilit isin kapanisiyla cozulmeli") ve `iptal` icin YANLISTI:
        # iptal olmus bir is bir daha kapanmaz, yani o care hic
        # islemezdi. Teshis koyup islemeyen bir care soylemek, care
        # soylememekten kotudur -- insan denedigi seyin neden ise
        # yaramadigini da cozmek zorunda kalir.
        careler = {
            "iptal": "`kabuk iptal {no} --sebep \"...\"` kilitleri birakir "
                     "(is zaten iptalse de calisir).",
            "bitti": "Is kapandigi halde kilit kalmis -- `kapat` yolunda "
                     "hata var demektir, tahtaya bakilmali.",
            "hazir": "Is dagitilmayi bekliyor ama alani kapali; "
                     "`kabuk durum` ile sahibini ara.",
        }
        return [_bulgu(
            "uyari", f"Oksuz kilit: '{r['yol_oneki']}' -> #{r['no']} ({r['durum']})",
            f"Is '{r['durum']}' durumunda ama yazma kilidi duruyor "
            f"({r['ajan_ad']}). Bu alan baska bir ise SEBEPSIZ kapali.",
            careler[r["durum"]].format(no=r["no"]))
            for r in rows if r["durum"] in careler]

    def _basarisiz_ajanlar(self) -> list:
        basarisiz = [a for a in self.ofis.kadro.liste() if a["faz"] == "basarisiz"]
        if not basarisiz:
            return []
        return [_bulgu(
            "uyari", f"{len(basarisiz)} ajan 'basarisiz' fazinda: "
            + ", ".join(a["ad"] for a in basarisiz),
            "Bu ajanlara is verilmiyor ve danisma sorulari onlara ulasmiyor.",
            "Sebebini `durum` ve olay gunlugunden bak; duzelince fazini "
            "'aktif'e cek.")]

    def _sizan_sirlar(self) -> list:
        """Veritabanina SIR sizmis mi?

        Anahtarlar ortam degiskeninde durur ve ofis ortami hicbir yere
        yazmaz -- ama AJAN yazabilir: `echo $GEMINI_API_KEY` bir terminal
        kaniti olarak duser, bir hata metni anahtari tasiyabilir.

        Sir kayda gecerse sir olmaktan cikar: veritabani yedeklenir,
        kopyalanir, brifinge girer, panelde gorunur. Sizan anahtar geri
        alinamaz; yalnizca DEGISTIRILEBILIR -- bu yuzden care "sil" degil
        "once DEGISTIR, sonra sil".

        DEGERI ASLA BASMAZ. Sizinti raporu, sizintinin kendisi olmamali.
        """
        hedefler = (
            ("kanit", "baslik", "icerik"),
            ("karar", "karar", "gerekce"),
            ("mesaj", "govde", "cevap"),
            ("olay", "govde", None),
            ("olgu", "konu", "icerik"),
        )
        bulunan = {}
        with self.db.baglanti() as conn:
            for tablo, a1, a2 in hedefler:
                alanlar = [x for x in (a1, a2) if x]
                try:
                    rows = conn.execute(
                        f"SELECT rowid AS rid, {', '.join(alanlar)} FROM {tablo}"
                    ).fetchall()
                except Exception:
                    continue
                for r in rows:
                    for alan in alanlar:
                        deger = r[alan] or ""
                        if not isinstance(deger, str):
                            continue
                        for ad, desen in SIR_DESENLERI:
                            if desen.search(deger):
                                bulunan.setdefault(ad, []).append(
                                    f"{tablo}.{alan} (satir {r['rid']})")
                                break
        if not bulunan:
            return []
        return [_bulgu(
            "uyari", f"SIR SIZMIS OLABILIR: {ad}",
            f"{len(yerler)} yerde: " + ", ".join(yerler[:5])
            + (" ..." if len(yerler) > 5 else "")
            + ". Deger BASILMADI -- rapor sizintinin kendisi olmamali.",
            "Once ANAHTARI DEGISTIR (sizan anahtar geri alinamaz), sonra "
            "kaydi temizle. Anahtarlar ortam degiskeninde tutulur, "
            "veritabaninda degil.")
            for ad, yerler in bulunan.items()]

    def _modelsiz_ajanlar(self) -> list:
        """Modeli verilmemis ajan, hesabin VARSAYILANINA duser.

        Olculdu: model verilmeden kosan ilk is $0,88; acik model verilen
        ikinci is $0,08. ON KAT. Bu bir maliyet sizintisidir ve faturaya
        kadar gorunmez -- yani tam olarak "sessiz" siniftan.
        """
        modelsiz = [a["ad"] for a in self.ofis.kadro.liste() if not a["model"]]
        if not modelsiz:
            return []
        return [_bulgu(
            "uyari", f"{len(modelsiz)} ajanin MODELI verilmemis: "
            + ", ".join(modelsiz),
            "Model verilmezse hesabin varsayilanina duser. Olculdu: ayni "
            "is model verilmeden $0,88, acik model verilince $0,08 -- on kat.",
            "`ise-al --model haiku|sonnet|opus` ile acikca ver.")]
