# -*- coding: utf-8 -*-
"""Ofis MCP sunucusu: ajanin ofise DOKUNABILDIGI tek yuz.

Bagimliliksiz, elle yazilmis stdio JSON-RPC 2.0 sunucusu. Bir kutuphane
eklemedik cunku bu parca cekirdege bakiyor ve cekirdek dayanikli olmali;
disa bagimlilik, yarin bir surum degisikliginde ofisi sessizce bozar.

## KIMLIK ARGUMANDAN GELMEZ, ORTAMDAN GELIR

Bu dosyanin en onemli kurali. Hicbir arac "hangi ajan / hangi gorev" diye
SORMAZ; `OFIS_AJAN` ve `OFIS_GOREV` ortam degiskeninden okunur ve koltuk
bunlari tur basinda kurar.

Argumandan alsaydik bir ajan baskasinin adina kanit ekleyebilir,
baskasinin siciline ders yazdirabilirdi. Kotu niyet gerekmez: karisik bir
baglamda yanlis ad yazmak yeter. **Kimlik tasinmaz, kurulur.**

## Alti arac, iki ayri bekleme sebebi

`durum` · `kanit_ekle` · `karar_yaz` · `soru_sor` · `onay_iste` ·
`gorev_ac`.

* `soru_sor` -> ajanin BILGISI eksik.
* `onay_iste` -> ajanin YETKISI eksik.

Ikisinde de ajana "SIMDI DUR" denir; tahmine devam etmek, iki saat sonra
atilacak is uretir.

`gorev_ac` yalnizca LIDERE aciktir. Isci gorev acabilseydi tahta kimsenin
dagitmadigi isle dolar ve fan-out kapisi bosa duserdi.

## Olculmus tuzaklar (hepsi gercek turda yasandi)

* **`for satir in sys.stdin` sunucuyu ASAR.** O bicim okuma-onden
  tamponlamasi yapar ve ilk satiri EOF gelene kadar teslim etmez. MCP
  istek-yanit konusur: karsi taraf yanit bekler, biz EOF bekleriz, ikisi
  de sonsuza kadar durur. `readline()` sarttir.
* **BILDIRIMIN `id`si YOKTUR ve yaniti BEKLENMEZ.** Bildirime yanit
  donmek ya da bildirimden yanit beklemek, ayni sessiz kilitlenmeyi
  uretir.
* **stdio UTF-8'e sabitlenir.** Windows konsolu cp1254; emoji tek basina
  vekil karaktere donusuyor ve SQLite'a yazarken patliyordu. JSON-RPC
  zaten UTF-8'dir -- yerel kodlama burada hicbir zaman dogru cevap
  degildi.
* **Proje NOBETCISI.** Sunucu ayri bir surecte ve AJANIN klasorunde
  kosar; goreli bir veritabani yolu orada baska bir yere cozulur ve
  SQLite bombos yeni bir dosya yaratir. Yol artik mutlaklastiriliyor
  (db.py) ama nobetci, tuzak baska bir yoldan kurulursa hatanin DOGRU
  ADLA gorunmesi icin durur: "gorev bulunamadi" degil, "yanlis defter".
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Paket disindan da kosulabilmeli: koltuk bu dosyayi `python
# ofis/mcp_sunucu.py` diye ayri bir surec olarak baslatir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

#: Yapilandirmadaki sunucu adi. Araclar ajana `mcp__ofis__<arac>` diye
#: gorunur; ad degisirse izin listeleri ve brifing metinleri de degismeli.
SUNUCU_ADI = "ofis"

PROTOKOL = "2025-06-18"


class Oturum:
    """Tur boyunca sabit olan kimlik. Ortamdan okunur, asla argumandan."""

    def __init__(self) -> None:
        self.db_yolu = os.environ.get("OFIS_DB", "")
        self.proje_id = os.environ.get("OFIS_PROJE", "")
        self.ajan_ad = os.environ.get("OFIS_AJAN", "")
        gorev = os.environ.get("OFIS_GOREV", "").strip()
        self.gorev_no = int(gorev) if gorev.isdigit() else None
        self._ofis = None

    @property
    def ofis(self):
        if self._ofis is None:
            if not self.db_yolu or not self.proje_id:
                raise RuntimeError(
                    "Ofis MCP sunucusu kimliksiz baslatildi "
                    "(OFIS_DB / OFIS_PROJE eksik)."
                )
            from ofis import Ofis, Veritabani      # gecikmeli: bkz. dosya basi
            db = Veritabani(self.db_yolu)
            # NOBETCI: proje GERCEKTEN bu defterde mi?
            #
            # OLCULDU (19.09.2026): goreli db yolu, ajanin klasorunde
            # BOMBOS bir veritabani yaratti. `kanit_ekle` "gorev
            # bulunamadi" dedi (dogruydu, YANLIS defterde bakiyordu) ve
            # `durum` BOS bir ofis dondurdu -- ajan ofisin yanlis resmini
            # gordu. Ikincisi daha kotu: eksik kayit fark edilir, YANLIS
            # bilgi fark edilmez.
            with db.baglanti() as conn:
                var = conn.execute("SELECT 1 FROM proje WHERE id = ?",
                                   (self.proje_id,)).fetchone()
            if not var:
                raise RuntimeError(
                    f"Bu veritabaninda '{self.proje_id}' projesi YOK: "
                    f"{db.yol}. Muhtemelen yanlis veritabani acildi "
                    "(goreli yol baska bir klasore cozulmus olabilir). "
                    "Bu turda hicbir ofis araci guvenilir degildir."
                )
            self._ofis = Ofis(db, self.proje_id)
        return self._ofis

    def ajan(self) -> dict:
        return self.ofis.kadro.ajan(self.ajan_ad)

    def gorev(self) -> dict:
        if self.gorev_no is None:
            raise RuntimeError("Bu turda acik bir gorev yok.")
        return self.ofis.tahta.gorev(self.gorev_no)


# ---------------------------------------------------------------------------
# araclar
# ---------------------------------------------------------------------------

def arac_durum(oturum: Oturum, args: dict) -> str:
    """Ajanin ofise bakan penceresi: isi, olculeri, gecerli bilgiler.

    Brifing tur BASINDA verilir ve tur uzadikca bayatlar. Bu arac ajanin
    "bir sey degisti mi" diye sorabilmesi icin var -- tahmin etmesin.
    """
    ofis = oturum.ofis
    satirlar = []

    if oturum.gorev_no is not None:
        try:
            g = oturum.gorev()
            satirlar += [
                f"## ISIN: #{g['no']} {g['baslik']}",
                f"- neden: {g['neden']}",
                f"- ana hedef: {g['ana_hedef']}",
                f"- kabul olcutu: {g['kabul_olcutu']}",
                f"- durum: {g['durum']}",
                f"- yazma alani: {', '.join(g['yazma_alani']) or 'yok'}",
                f"- kanit: {len(ofis.tahta.kanitlar(g['no']))} tane",
            ]
        except Exception as exc:
            satirlar.append(f"(gorev okunamadi: {exc})")

    kurallar = ofis.bellek.kurallar()
    if kurallar:
        satirlar += ["", "## OFIS KURALLARI (insan onayli, HER iste gecerli)"]
        for k in kurallar:
            satirlar.append(f"- {k['metin']}")

    olgular = ofis.bellek.gecerli_olgular()
    if olgular:
        satirlar += ["", "## GECERLI BILGILER"]
        for o in olgular[:40]:
            satirlar.append(f"- {o['konu']}: {o['icerik']}")

    kararlar = ofis.bellek.son_kararlar(6)
    if kararlar:
        satirlar += ["", "## SON KARARLAR (baglayici)"]
        for k in kararlar:
            satirlar.append(f"- {k['veren']}: {k['karar']}")

    cevaplar = ofis.postane.cevaplar(oturum.ajan_ad,
                                     gorev_no=oturum.gorev_no)
    if cevaplar:
        satirlar += ["", "## SORDUKLARININ CEVABI"]
        for c in cevaplar:
            satirlar.append(f"- {c['govde'][:160]} -> {c['cevap'][:300]}")

    return "\n".join(satirlar) or "(ofis bos)"


def arac_kanit_ekle(oturum: Oturum, args: dict) -> str:
    """Kanit BIRIKTIREREK eklenir, sona birakilmaz.

    Olculdu: sona birakilan kanit, tur butce tavaninda kesilince tamamen
    kayboldu (208.148 jetonluk is, sifir kanit). Kanit bir TESLIMAT degil,
    bir DEFTER KAYDIDIR.
    """
    tur = str(args.get("tur") or "").strip()
    baslik = str(args.get("baslik") or "").strip()
    icerik = str(args.get("icerik") or "").strip()
    if not baslik:
        return "HATA: kanit basligi bos olamaz."
    if not icerik:
        return ("HATA: kanit icerigi bos olamaz. Kanit, isin yapildigini "
                "GOSTEREN seydir; bos bir kanit hicbir sey gostermez.")
    if oturum.gorev_no is None:
        return "HATA: bu turda acik bir gorev yok, kanit nereye eklenecek?"
    g = oturum.gorev()
    oturum.ofis.tahta.kanit_ekle(g["no"], tur, baslik, icerik,
                                 oturum.ajan_ad)
    toplam = len(oturum.ofis.tahta.kanitlar(g["no"]))
    return f"Kanit eklendi: [{tur}] {baslik} (#{g['no']} icin toplam {toplam} kanit)."


def arac_bilgi_yaz(oturum: Oturum, args: dict) -> str:
    """Olgu katmaninin ajana acilan kapisi.

    OLCULDU (24.09.2026): gercek ofiste 0 olgu vardi -- uretimde olgu
    yazan tek bir yol yoktu. Kalici bilgiyi ogrenen ajandir; yazmazsa
    bir sonraki ajan ayni seyi bastan arastirir ve hafiza isabeti
    olculse bile gercekte bos bir hafizanin isabetidir.

    KIMLIK ORTAMDAN: kaynak `ajan:<ad> #<gorev>` olarak yazilir, ajan
    kaynagi SECEMEZ. Insanin yazdigini devirmeye kalkarsa `bellek`
    reddeder (sessizce devirmek yok).
    """
    from ofis.bellek import BellekHatasi, baglar
    konu = str(args.get("konu") or "")
    icerik = str(args.get("icerik") or "")
    if not oturum.ajan_ad:
        return "HATA: kimliksiz tur -- bilgi kimin adina yazilacak?"
    try:
        r = oturum.ofis.bellek.bilgi_ekle(konu, icerik,
                                         yazan=oturum.ajan_ad,
                                         gorev_no=oturum.gorev_no)
    except BellekHatasi as exc:
        return f"HATA: {exc}"
    if r["durum"] == "ayni":
        return f"Zaten biliniyor: {r['konu']} (yeni surum acilmadi)."
    bag = baglar(r["icerik"])
    kirik = [b for b in bag if not oturum.ofis.bellek._konu_bul(b)]
    ek = ""
    if kirik:
        # Kirik bag bir HATA degil bir BILGIDIR: henuz yazilmamis bir
        # konuya isaret ediyor. Soylenir ki ajan uydurdugu bir konu adina
        # bag vermediginden emin olsun.
        ek = (" Uyari: su baglarin hedefi henuz yok: "
              + ", ".join(f"[[{b}]]" for b in kirik) + ".")
    fiil = "guncellendi (eski surum gecmiste duruyor)" \
        if r["durum"] == "guncellendi" else "yazildi"
    return f"Bilgi {fiil}: {r['konu']}.{ek}"


def arac_karar_yaz(oturum: Oturum, args: dict) -> str:
    """Gerekce ZORUNLU: gerekcesiz karar alti ay sonra sorgulanamaz."""
    karar = str(args.get("karar") or "").strip()
    gerekce = str(args.get("gerekce") or "").strip()
    if not karar:
        return "HATA: bos karar yazilamaz."
    if not gerekce:
        return ("HATA: gerekce zorunlu. Gerekcesiz karar, 'bunu neden boyle "
                "yapmistik' sorusuna cevap vermez ve ekip ayni tartismayi "
                "bastan yapar.")
    gorev_id = None
    if oturum.gorev_no is not None:
        try:
            gorev_id = oturum.gorev()["id"]
        except Exception:
            gorev_id = None
    oturum.ofis.bellek.karar_yaz(karar, gerekce, oturum.ajan_ad,
                                 gorev_id=gorev_id)
    return f"Karar gunluge yazildi: {karar}"


def arac_soru_sor(oturum: Oturum, args: dict) -> str:
    """Lidere ya da insana soru sorar ve TURU BITIRIR.

    Soru soran ajan beklemeye gecer. Sebep: cevabi olmayan bir varsayimla
    calismaya devam etmek, iki saat sonra atilacak is uretir. Soru sormak
    ucuzdur; yanlis varsayim pahalidir.
    """
    soru = str(args.get("soru") or "").strip()
    if not soru:
        return "HATA: bos soru sorulamaz."
    alici = str(args.get("kime") or "lider").strip() or "lider"
    if alici == "lider":
        try:
            g = oturum.gorev() if oturum.gorev_no is not None else None
            alici = oturum.ofis.kadro.lider(g["kanat_id"] if g else None)["ad"]
        except Exception:
            alici = "insan"
    oturum.ofis.postane.soru_sor(oturum.ajan_ad, alici, soru,
                                 gorev_no=oturum.gorev_no, mod="bekleyen")
    return (f"Soru '{alici}' adresine iletildi ve cevap bekleniyor.\n"
            "SIMDI DUR: tahminle devam etme, turu burada bitir. "
            "Cevap gelince kaldigin yerden surdurulecek.")


def arac_onay_iste(oturum: Oturum, args: dict) -> str:
    """Riskli adim insana takilir. Tam otonomi ISTENMEZ."""
    eylem = str(args.get("eylem") or "").strip()
    if not eylem:
        return "HATA: onay istenen eylem bos olamaz."
    risk = str(args.get("risk") or "orta").strip() or "orta"
    if risk not in ("dusuk", "orta", "yuksek"):
        return f"HATA: risk 'dusuk', 'orta' ya da 'yuksek' olmali ({risk} degil)."
    oturum.ofis.postane.onay_iste(
        oturum.ajan_ad, eylem, ayrinti=str(args.get("ayrinti") or ""),
        risk=risk, gorev_no=oturum.gorev_no)
    return ("Onay istegi kaydedildi, insan cevabi bekleniyor.\n"
            "SIMDI DUR: eylemi YAPMA, turu burada bitir.")


def arac_gorev_ac(oturum: Oturum, args: dict) -> str:
    """Yalnizca LIDER gorev acabilir.

    Isci acabilseydi tahta kimsenin dagitmadigi isle dolar ve fan-out
    kapisi bosa duserdi -- bolme karari liderin olmaktan cikardi.
    """
    try:
        ajan = oturum.ajan()
    except Exception as exc:
        return f"HATA: ajan okunamadi: {exc}"
    if not ajan["lider_mi"]:
        return ("HATA: gorev acmak lidere aittir. Sen isci bir ajansin; "
                "yeni is gerektigini dusunuyorsan `soru_sor` ile lidere bildir.")

    baslik = str(args.get("baslik") or "").strip()
    neden = str(args.get("neden") or "").strip()
    ana_hedef = str(args.get("ana_hedef") or "").strip()
    kabul_olcutu = str(args.get("kabul_olcutu") or "").strip()
    eksik = [ad for ad, deger in (("baslik", baslik), ("neden", neden),
                                  ("ana_hedef", ana_hedef),
                                  ("kabul_olcutu", kabul_olcutu)) if not deger]
    if eksik:
        return (f"HATA: su alanlar zorunlu ve bos: {', '.join(eksik)}. "
                "Belirtimsiz is, hatalarin en buyuk kaynagidir (%41,8).")

    yazma_alani = args.get("yazma_alani") or []
    if isinstance(yazma_alani, str):
        yazma_alani = [yazma_alani]
    g = oturum.ofis.tahta.gorev_ac(
        baslik, neden=neden, ana_hedef=ana_hedef,
        kabul_olcutu=kabul_olcutu, govde=str(args.get("govde") or ""),
        yazma_alani=list(yazma_alani), kanat_id=ajan["kanat_id"],
        acan=oturum.ajan_ad)
    return f"Gorev acildi: #{g['no']} {g['baslik']}"


def _medya_hedefi(kok, alanlar, ad):
    """Tek kaynak `tahta.medya_hedefi`; burada yalniz ice aktarma (betik
    kipinde mutlak -- goreli ice aktarma bu sunucuda bir kez patladi)."""
    from ofis.tahta import medya_hedefi
    return medya_hedefi(kok, alanlar, ad)


def arac_gorsel_uret(oturum: Oturum, args: dict) -> str:
    """Istemi gorsele cevirir ve dosyayi KANIT olarak tahtaya yazar.

    Kullanicinin gercek akisi buydu: *"promptu Claude ile yazdiriyorum,
    GPT'ye yapistirip gorseli urettiriyorum."* Yapistirma adimi insanin
    isi olmamali -- istemi yazan ajan, ayni turda gorseli de aldirir.

    UC KURAL:

    1. **Anahtar AJANIN ELINE GECMEZ.** Uretim ofisin kendi surecinde
       (bu sunucuda) olur; ajana yalnizca dosya yolu doner. Ajanin izin
       listesinde `Bash(echo *)` var -- ortamina giren her anahtar
       terminal kaniti olarak tahtaya dusebilirdi.

    2. **Dosya YAZMA ALANININ ICINE yazilir.** Disari yazmak Yasa 1'i
       deler: baska bir ajanin kilitli alanina dokunmus oluruz ve kilit
       makinesi bunu hic gormez.

    3. **Kanit OTOMATIK eklenir.** "Koltuk kanit uydurmaz" kurali burada
       ihlal EDILMIYOR: dosyayi ofisin kendisi uretti ve diskte oldugunu
       OLCUYOR. Uydurma, yapilmamis isi yapilmis saymaktir; burada is
       yapildi ve kanit o isin kendisi.
    """
    from pathlib import Path as _Path
    from ofis import gorsel as _gorsel

    istem = str(args.get("istem") or "").strip()
    if not istem:
        return "HATA: bos istemle gorsel uretilemez."
    if oturum.gorev_no is None:
        return "HATA: bu turda acik bir gorev yok; gorsel nereye ait olacak?"

    g = oturum.gorev()
    ad = str(args.get("dosya_adi") or "").strip() or f"gorsel-{g['no']}.png"
    ad = _Path(ad).name                     # yol enjeksiyonu yok: yalniz ad

    # YAZMA ALANI ICINE. Alan yoksa ajanin kendi klasorune.
    try:
        ajan = oturum.ajan()
    except Exception as exc:
        return f"HATA: ajan okunamadi: {exc}"
    kok = _Path(ajan["klasor"])
    alanlar = g.get("yazma_alani") or []
    try:
        hedef = _medya_hedefi(kok, alanlar, ad)
    except Exception as exc:                     # noqa: BLE001 -- ajana ANLATILIR
        return f"HATA: {exc}"

    try:
        sonuc = _gorsel.uret(istem, hedef,
                             uretici=str(args.get("uretici") or ""),
                             model=str(args.get("model") or ""))
    except _gorsel.GorselHatasi as exc:
        return f"HATA: {exc}"

    # Kanit: dosya GERCEKTEN diskte. Olculdu, iddia edilmedi.
    # MALIYET KANITA YAZILIR. Olcmedigimiz sey yonetilemez -- ve para
    # soz konusuysa "sonra bakariz" faturayla ogrenmek demektir.
    # Olculemiyorsa UYDURULMAZ: alan hic yazilmaz.
    para = (f" · ${sonuc['maliyet_usd']:.4f}"
            if sonuc.get("maliyet_usd") is not None else "")
    oturum.ofis.tahta.kanit_ekle(
        g["no"], "gorsel", sonuc["yol"],
        f"{sonuc['uretici']}/{sonuc['model']} ile uretildi, "
        f"{sonuc['bayt']} bayt{para}. Istem: {istem[:200]}",
        oturum.ajan_ad)

    satir = [f"Gorsel uretildi: {sonuc['yol']}",
             f"  uretici: {sonuc['uretici']} · model: {sonuc['model']} "
             f"· {sonuc['bayt']} bayt"
             + (f" · MALIYET ${sonuc['maliyet_usd']:.4f}"
                if sonuc.get("maliyet_usd") is not None else ""),
             "  KANIT olarak tahtaya yazildi (ayrica `kanit_ekle` cagirma)."]
    for a in (sonuc.get("atlananlar") or []):
        satir.append(f"  (atlandi: {a['uretici']} -- {a['sebep'][:120]})")
    return chr(10).join(satir)


def arac_gorsel_iste(oturum: Oturum, args: dict) -> str:
    """Gorseli INSANA urettirir: istemi yazar, ONAY kuyruguna dusurur.

    Neden var: kullanicinin ChatGPT **Plus** aboneligi var ama API
    erisimi YOK (olculdu: auth_mode=chatgpt, org yok). Uygulamada
    gorsel uretebiliyor; API'de uretmek ayri bir anahtar ve ayri bir
    fatura demek.

    Tarayiciyi otomatiklestirerek ChatGPT'ye baglanmak TEKNIK olarak
    mumkun ama OpenAI'in kullanim sartlari tuketici urunune programatik
    erisimi yasakliyor -- hesap kullanicinin olsa bile kisitlanan sey
    YONTEM. Bedeli hesabin askiya alinmasi olabilir. Ofis, kullanicinin
    hesabini riske atan bir yol acmaz.

    Bu arac ortadaki yolu kurar: **istemi ajan yazar** (isin zor kismi
    zaten oydu), insan onu diledigi araca yapistirir, ureteni indirir
    ve `kabuk gorsel ekle` ile tahtaya koyar. Yapistirmak disindaki her
    adim otomatik.

    Ajan BEKLEMEYE GECER -- `onay_iste` ile ayni mantik: ajanin YETKISI
    degil, ARACI eksik; devam etmesi icin insanin donmesi gerekiyor.
    """
    istem = str(args.get("istem") or "").strip()
    if not istem:
        return "HATA: bos istemle gorsel istenemez."
    if oturum.gorev_no is None:
        return "HATA: bu turda acik bir gorev yok."
    g = oturum.gorev()
    ad = str(args.get("dosya_adi") or "").strip() or f"gorsel-{g['no']}.png"

    oturum.ofis.postane.onay_iste(
        oturum.ajan_ad,
        f"Gorseli sen uret: {ad}",
        ayrinti=("ISTEM (kopyala-yapistir):" + chr(10) + chr(10) + istem
                 + chr(10) + chr(10)
                 + "Urettikten sonra:" + chr(10)
                 + f"  python -m ofis.kabuk gorsel ekle <indirdigin dosya> "
                   f"--gorev {g['no']} --ad {ad}"),
        risk="dusuk", gorev_no=g["no"])
    return ("Istem yazildi ve SENDEN BEKLENIYOR kuyruguna dusuruldu.\n"
            "SIMDI DUR: gorsel gelince is kaldigi yerden surer.\n"
            "(Otomatik uretim istiyorsan `gorsel_uret` kullan -- "
            "anahtar varsa o insanı beklemez.)")


#: Bir MCP arac cagrisinda en fazla ne kadar beklenir.
#: `video.AZAMI_BEKLEME_SN` (600) surecin kendi tavani; bu ondan KISA
#: olmali, cunku MCP istemcisinin kendi arac zaman asimi var ve ONU
#: asarsak yanit hic ulasmaz -- yani beklerken harcanan sure de, isin
#: kimligini iceren cevap da kaybolur. Istemcinin tavani OLCULMEDI;
#: bilmedigimiz bir sinirin altinda kalmak icin muhafazakar secildi.
#: Yanilmanin bedeli bir fazladan `video_durum` cagrisi -- cunku is
#: kimligi zaten deftere yazilmis oluyor.
MCP_AZAMI_BEKLEME_SN = 240


def _video_hedef(oturum: Oturum, g: dict, ad_arg, varsayilan: str):
    """Videonun yazilacagi yolu YAZMA ALANININ icinde cozer.

    `gorsel_uret` ile ayni kural ve ayni sebep: disari yazmak Yasa 1'i
    deler -- baska bir ajanin kilitli alanina dokunmus oluruz ve kilit
    makinesi bunu hic gormez. Ortak bir yardimci, cunku bu projede iki
    kopyadan biri duzeltilip oteki unutuldugu icin bes kez hata cikti.
    """
    from pathlib import Path as _Path
    ad = _Path(str(ad_arg or "").strip() or varsayilan).name
    kok = _Path(oturum.ajan()["klasor"])
    alanlar = g.get("yazma_alani") or []
    try:
        return _medya_hedefi(kok, alanlar, ad)
    except Exception as exc:                     # noqa: BLE001
        from ofis import video as _v
        raise _v.VideoHatasi(str(exc))


def _video_kanit(oturum: Oturum, g: dict, sonuc: dict,
                 istem: str, tahmin) -> str:
    """Inen videoyu KANIT olarak tahtaya yazar ve ajana ozet doner.

    "Koltuk kanit uydurmaz" kurali burada ihlal EDILMIYOR: dosyayi
    ofisin kendisi indirdi ve diskte oldugunu OLCUYOR. Uydurma,
    yapilmamis isi yapilmis saymaktir; burada is yapildi ve kanit o
    isin kendisi. (`gorsel_uret` ile ayni gerekce.)
    """
    # MALIYET ETIKETI DURUST OLMALI. Bu rakam saglayicinin FATURASI
    # degil: ilan edilen saniye basi fiyattan HESAPLANDI. `gorsel_uret`te
    # maliyet API yanitindan okunur, burada okunamaz -- ve ikisine ayni
    # etiketi koymak, olculen ile hesaplanani ayni sanmaya davet olurdu.
    # `video` rolunun olcutu ayrica GERCEK maliyeti istiyor; ajan onu
    # saglayici panelinden ayri bir kanit olarak ekler.
    para = (f" - hesaplanan ~${tahmin} (ilan edilen saniye basi fiyattan; "
            "saglayici faturasi DEGIL)" if tahmin is not None else "")
    oturum.ofis.tahta.kanit_ekle(
        g["no"], "gorsel", sonuc["yol"],
        f"{sonuc.get('uretici', '')}/{sonuc.get('model', '')} ile uretilen "
        f"VIDEO, {sonuc['bayt']} bayt{para}. Istem: {istem[:200]}",
        oturum.ajan_ad)
    return chr(10).join([
        f"Video indirildi: {sonuc['yol']}",
        f"  {sonuc.get('uretici', '')}/{sonuc.get('model', '')} - "
        f"{sonuc['bayt']} bayt" + (f" - HESAPLANAN ${tahmin}" if tahmin is not None else ""),
        "  KANIT olarak tahtaya yazildi (ayrica `kanit_ekle` cagirma).",
        "  NOT: bu rakam ilan edilen fiyattan hesaplandi, FATURA degil."
        " Olcutun gercek maliyet istiyorsa saglayici panelinden dogrula.",
    ])


def _video_isi_yaz(oturum: Oturum, g: dict, bilgi: dict,
                   istem: str, tahmin) -> None:
    """Is kimligini BASLAR BASLAMAZ deftere yazar.

    Bu fonksiyonun tek varlik sebebi: video dakikalarca surer ve tur
    kesilebilir (butce, limit, zaman asimi -- ucu de yasandi). Kimlik
    sona birakilsaydi kesilen tur PARASI ODENMIS bir isi cope atardi.
    Ayni ders arastirma isinde bir kez odendi: 208.148 jetonluk is,
    sifir kanit. **Defter is bitince degil, is ilerledikce dolar.**

    Govde JSON: `tur_ozeti` olayinin kurdugu duzen. Ikinci bir bicim
    icat etmek, okuyan tarafta ikinci bir ayristirici demek olurdu.
    """
    import json as _json
    oturum.ofis.db.olay_yaz(
        oturum.ofis.proje_id, "video_isi",
        _json.dumps({"is_id": bilgi["is_id"], "uretici": bilgi["uretici"],
                     "model": bilgi.get("model", ""),
                     "saniye": bilgi.get("saniye"),
                     "cozunurluk": bilgi.get("cozunurluk", ""),
                     "tahmini_maliyet_usd": tahmin,
                     "istem": istem[:500]}, ensure_ascii=False),
        ajan_ad=oturum.ajan_ad, gorev_id=g["id"])


def _video_isi_bul(oturum: Oturum, is_id: str) -> dict:
    """Defterden is kaydini bulur.

    Ajandan uretici adini tekrar yazmasini istemek, yanlis yazilmis bir
    adla SESSIZ BIR OLUM uretirdi: is sunucuda durur, ajan "bulunamadi"
    der ve odenmis is kaybolur. Kimlik tasinmaz, KAYITTAN okunur --
    `soru_sor`un alici dogrulamasiyla ayni ders.
    """
    import json as _json
    with oturum.ofis.db.baglanti() as conn:
        satirlar = conn.execute(
            "SELECT govde FROM olay WHERE proje_id = ? AND tur = 'video_isi' "
            "ORDER BY id DESC LIMIT 200",
            (oturum.ofis.proje_id,)).fetchall()
    for s in satirlar:
        try:
            d = _json.loads(s["govde"])
        except (ValueError, TypeError):
            continue
        if d.get("is_id") == is_id:
            return d
    return {}


def arac_video_uret(oturum: Oturum, args: dict) -> str:
    """Istemi videoya cevirir. KIMLIK ONCE YAZILIR, sonra beklenir.

    `gorsel_uret`in kardesi ama uc yapisal farki var, ucu de olculdu:

    1. **PARASI ODENMIS IS KAYBOLMAZ.** Is kimligi baslar baslamaz
       olaya yazilir, beklemeden once (`_video_isi_yaz`).

    2. **BEKLEMEK BIR SECIMDIR.** Bekleyen ajan KILIDINI TUTARAK bekler
       ve o sure boyunca hicbir sey uretmez. `bekle=false` ile is arkada
       surerken ajan baska is yapar, sonra `video_durum` ile toplar.

    3. **TAVAN ONCE OLCULUR.** Video saniye basi fiyatlanir, yani maliyet
       ONCEDEN bilinebilir. Once baslatip sonra olcmek, parayi yandiktan
       sonra bildiren bir gosterge olurdu (`video.py`).
    """
    import time as _time
    from ofis import video as _video

    istem = str(args.get("istem") or "").strip()
    if not istem:
        return "HATA: bos istemle video uretilemez."
    if oturum.gorev_no is None:
        return "HATA: bu turda acik bir gorev yok; video nereye ait olacak?"
    g = oturum.gorev()

    try:
        saniye = int(args.get("saniye") or 8)
    except (TypeError, ValueError):
        return "HATA: `saniye` bir tam sayi olmali."
    cozunurluk = str(args.get("cozunurluk") or "720p")
    bekle = args.get("bekle")
    bekle = True if bekle is None else bool(bekle)

    ek = {}
    if args.get("tavan_usd") is not None:
        try:
            ek["tavan_usd"] = float(args["tavan_usd"])
        except (TypeError, ValueError):
            return "HATA: `tavan_usd` bir sayi olmali."

    # 1. ADIM: isi BASLAT, bekleme. Tavan kapisi burada calisir ve
    # asilirsa surec HIC baslamaz -- jeton da para da yanmaz.
    try:
        bilgi = _video.uret(istem, "", saniye=saniye, cozunurluk=cozunurluk,
                            uretici=str(args.get("uretici") or ""),
                            model=str(args.get("model") or ""),
                            bekle=False, **ek)
    except _video.ButceAsimi as exc:
        # Ayri sinif, ayri cevap: bu bir HATA degil bir KARAR. Tek sinif
        # olsaydi ajan "tekrar dene" der ve tavan bir yavaslatmaya
        # donusurdu (`video.py`nin kendi gerekcesi).
        return (f"TAVAN: {exc}" + chr(10)
                + "Tekrar deneme -- sureyi kisalt ya da insandan tavan iste.")
    except _video.VideoHatasi as exc:
        return f"HATA: {exc}"

    tahmin = bilgi.get("tahmini_maliyet_usd")
    _video_isi_yaz(oturum, g, bilgi, istem, tahmin)

    basligi = (f"  {bilgi['uretici']}/{bilgi.get('model', '')} - {saniye} sn "
               f"{cozunurluk}"
               + (f" - ~${tahmin}" if tahmin is not None else ""))
    if not bekle:
        return chr(10).join([
            f"Video isi BASLATILDI: {bilgi['is_id']}", basligi,
            "  Kimlik deftere yazildi -- tur kesilse bile kaybolmaz.",
            "  Bitince `video_durum` ile indir. Beklerken baska is yap.",
        ])

    # 2. ADIM: bekle. Kilit ajanda kalir, motor nabzi akmaya devam eder.
    try:
        u = _video.uretici_ac(bilgi["uretici"])
        basla = _time.time()
        while True:
            hal = u.durum(bilgi["is_id"])
            if hal["bitti"]:
                break
            if _time.time() - basla > MCP_AZAMI_BEKLEME_SN:
                return chr(10).join([
                    f"Is SURUYOR ama bekleme tavanina gelindi "
                    f"({MCP_AZAMI_BEKLEME_SN} sn).",
                    f"  IS KIMLIGI: {bilgi['is_id']} -- deftere yazildi.",
                    "  Kaybolmadi: baska is yap, sonra `video_durum` ile al.",
                ])
            _time.sleep(_video.YOKLAMA_ARALIGI_SN)
        if not hal["basarili"]:
            return f"Is BASARISIZ: {hal['hata']}"
        hedef = _video_hedef(oturum, g, args.get("dosya_adi"),
                             f"video-{g['no']}.mp4")
        sonuc = u.indir(bilgi["is_id"], hedef)
    except _video.VideoHatasi as exc:
        return (f"HATA: {exc}" + chr(10)
                + f"  IS KIMLIGI: {bilgi['is_id']} -- deftere yazildi, "
                  "`video_durum` ile sonra sorulabilir.")
    sonuc.setdefault("uretici", bilgi["uretici"])
    sonuc.setdefault("model", bilgi.get("model", ""))
    return _video_kanit(oturum, g, sonuc, istem, tahmin)


def arac_video_durum(oturum: Oturum, args: dict) -> str:
    """Baslatilmis bir video isini sorar; bittiyse INDIRIR ve kanit yazar.

    `video_uret`ten ayri bir arac olmasinin sebebi: is dakikalarca surer.
    Tek arac olsaydi ajanin tek secenegi beklemek olurdu ve bekleyen ajan
    kilidini tutar -- yani ofis bir video yuzunden durur.
    """
    from ofis import video as _video

    is_id = str(args.get("is_id") or "").strip()
    if not is_id:
        return "HATA: `is_id` gerekli -- hangi is soruluyor?"
    if oturum.gorev_no is None:
        return "HATA: bu turda acik bir gorev yok."
    g = oturum.gorev()

    kayit = _video_isi_bul(oturum, is_id)
    uretici_ad = kayit.get("uretici") or str(args.get("uretici") or "").strip()
    if not uretici_ad:
        return (f"HATA: '{is_id}' defterde yok ve `uretici` verilmedi. "
                "Kimligi dogru yazdigindan emin ol.")
    tahmin = kayit.get("tahmini_maliyet_usd")
    istem = kayit.get("istem") or ""

    try:
        u = _video.uretici_ac(uretici_ad)
        hal = u.durum(is_id)
    except _video.VideoHatasi as exc:
        return f"HATA: {exc}"
    if not hal["bitti"]:
        return (f"Is SURUYOR: {is_id}" + chr(10)
                + "  Henuz bitmedi. Baska is yap, sonra yine sor.")
    if not hal["basarili"]:
        return f"Is BASARISIZ: {hal['hata']}"

    try:
        hedef = _video_hedef(oturum, g, args.get("dosya_adi"),
                             f"video-{g['no']}.mp4")
    except _video.VideoHatasi as exc:
        return f"HATA: {exc}"
    try:
        sonuc = u.indir(is_id, hedef)
    except _video.VideoHatasi as exc:
        return f"HATA: indirilemedi: {exc}"
    sonuc.setdefault("uretici", uretici_ad)
    sonuc.setdefault("model", kayit.get("model", ""))
    return _video_kanit(oturum, g, sonuc, istem, tahmin)


def arac_video_iste(oturum: Oturum, args: dict) -> str:
    """Videoyu INSANA urettirir: istemi yazar, ONAY kuyruguna dusurur.

    `gorsel_iste` ile ayni yapi ama gerekcesi DAHA GUCLU, cunku olculdu:
    **videoda ucretsiz bir API katmani YOK.** Veo gelistirici API'sinde
    ucretsiz katman yok (Google Cloud faturalandirmasi gerekiyor),
    Higgsfield'da bakiye yok. Ucretsiz olan tek yol Google Flow'un gunluk
    50 kredisi ve o bir TUKETICI ARAYUZU -- API degil.

    Yani bugun ofisin video uretebildigi tek ucretsiz yol bu: istemi ajan
    yazar (isin zor kismi zaten oydu), insan yapistirir, indirir, tahtaya
    koyar. Tuketici arayuzunu tarayiciyla surmek teknik olarak mumkun ama
    saglayicinin sartlarina aykiri; ofis kullanicinin hesabini riske atan
    bir yol acmaz (`gorsel_iste` ile ayni karar).
    """
    from pathlib import Path as _Path
    istem = str(args.get("istem") or "").strip()
    if not istem:
        return "HATA: bos istemle video istenemez."
    if oturum.gorev_no is None:
        return "HATA: bu turda acik bir gorev yok."
    g = oturum.gorev()
    ad = _Path(str(args.get("dosya_adi") or "").strip()
               or f"video-{g['no']}.mp4").name
    saniye = str(args.get("saniye") or "8")

    oturum.ofis.postane.onay_iste(
        oturum.ajan_ad,
        f"Videoyu sen uret: {ad}",
        ayrinti=("ISTEM (kopyala-yapistir):" + chr(10) + chr(10) + istem
                 + chr(10) + chr(10)
                 + f"Sure: ~{saniye} sn" + chr(10)
                 + "Ucretsiz yol: Google Flow (gunluk 50 kredi)." + chr(10)
                 + chr(10) + "Urettikten sonra:" + chr(10)
                 + f"  python -m ofis.kabuk video ekle <indirdigin dosya> "
                   f"--gorev {g['no']} --ad {ad}"),
        risk="dusuk", gorev_no=g["no"])
    return chr(10).join([
        "Istem yazildi ve SENDEN BEKLENIYOR kuyruguna dusuruldu.",
        "SIMDI DUR: video gelince is kaldigi yerden surer.",
        "(Otomatik uretim istiyorsan `video_uret` -- ama olculdu: "
        "ucretsiz API katmani YOK, para yanar.)",
    ])

def arac_izin_sor(oturum: Oturum, args: dict) -> str:
    """CLI'IN IZIN KANCASI -- ofisin TEK kapisi, her yuzey icin.

    `claude --permission-prompt-tool mcp__ofis__izin_sor` ile baglanir
    ve CLI, izin gerektiren HER arac cagrisini once buraya sorar
    (olculdu: her `Write` icin bir kez cagrildi, `allow` dosyayi
    yazdirdi, `deny` yazdirmadi).

    ## Neden bu, yuzey yuzey cozumden iyi

    Ajanin riskli bir sey yapabilecegi uc yuzey var: tarayici ·
    baglayici (Shopify/Meta/Gmail) · kabuk. Her birine ayri bir kapi
    yazmak, bu projede alti kez odenen "iki kopyadan biri unutulur"
    hatasinin davetiyesidir. Burasi TEK kapi ve olcut TEK yerde
    (`riskli.py`).

    ## Neden ARAC ADI saglam bir dayanak

    Tarayici kapisi dugmenin YAZISINA bakar: dile ve arayuz bicimine
    bagli, yani hep gercegin gerisinde. Arac adi (`ads_activate_entity`,
    `create-discount`) bir API kimligidir -- saglayici sabitler.

    Ve polarite dogru: OKUMA fiilleri serbest, TANINMAYAN arac SORULUR.
    Yarin eklenen bir arac sessizce iceri giremez.

    ## Uc cikis

    * `allow`  -- serbest (okuma), ya da onceden onaylanmis.
    * `allow` + KAYIT -- degistiren ama riskli olmayan cagri. Sorulmaz
      (ajan isini yapsin) ama deftere yazilir; insanin `degisim.py`den
      gordugu seyin baglayici karsiligi.
    * `deny`   -- riskli. Onay kaydi acilir, ajana neden durdugu ve ne
      yapacagi soylenir.

    Cevap bicimi CLI'in sozlesmesi: `{"behavior": ...}` JSON'u.
    """
    import json as _json
    from ofis import riskli

    arac = (args.get("tool_name") or "").strip()
    girdi = args.get("input")
    if not isinstance(girdi, dict):
        girdi = {}

    def izin(ek: str = "") -> str:
        return _json.dumps({"behavior": "allow", "updatedInput": girdi},
                           ensure_ascii=False)

    def ret(mesaj: str) -> str:
        return _json.dumps({"behavior": "deny", "message": mesaj},
                           ensure_ascii=False)

    try:
        bulgu = riskli.arac_degerlendir(arac, girdi)
    except Exception as exc:
        # Kapi patlarsa KAPALI kalir. Acik kalsaydi kapinin bozulmasi
        # her seyi sessizce serbest birakirdi -- para ve yayin
        # kontrolleri bu projede her zaman "fail closed" olur.
        return ret(f"Ofis kapisi degerlendirme yapamadi ({exc}). Guvenli "
                   "tarafta kaliyoruz: bu eylem YAPILMADI.")

    if bulgu is None:
        return izin()

    try:
        ofis = oturum.ofis
        postane = ofis.postane
    except Exception as exc:
        return ret(f"RISKLI EYLEM ve onay defterine ulasilamiyor ({exc}). "
                   "Eylem yapilmadi.")

    gorev_id = None
    if oturum.gorev_no is not None:
        try:
            gorev_id = ofis.tahta.gorev(oturum.gorev_no)["id"]
        except Exception:
            gorev_id = None

    # SORULMAYAN ama KAYDA GECEN sinif.
    if not bulgu.get("sorulur"):
        ofis.db.olay_yaz(
            oturum.proje_id, "arac_degisikligi",
            f"{arac} | {bulgu['esles']} | {str(girdi)[:200]}",
            ajan_ad=oturum.ajan_ad, gorev_id=gorev_id)
        return izin()

    im = postane.imza(bulgu)
    for kayit in postane.onay_ara(oturum.ajan_ad, im,
                                  gorev_no=oturum.gorev_no):
        if kayit["durum"] == "reddedildi":
            return ret(
                "REDDEDILDI. Patron bu eylemi onaylamadi.\n"
                f"Eylem  : {bulgu['eylem']}\n"
                f"Gerekce: {kayit['cevap_notu'] or '(yazilmamis)'}\n\n"
                "Bu yolu TEKRAR DENEME. Baska bir yol varsa onu dene, "
                "yoksa `soru_sor` ile lidere danis.")
        if kayit["durum"] == "onaylandi":
            # KAPSAM 'is' ise tuketilmez: insan bu gorev boyunca
            # acikca izin vermistir. Varsayilan 'eylem' ve o BIR KEZ
            # gecer -- yoksa tek bir "evet" surekli yetkiye donerdi.
            if (kayit.get("kapsam") or "eylem") == "is":
                return izin()
            if not postane.onay_kullanildi_mi(kayit["id"]):
                postane.onay_kullan(kayit["id"], ajan_ad=oturum.ajan_ad,
                                    ne=f"{arac} | {bulgu['esles']}",
                                    gorev_id=gorev_id)
                return izin()
        if kayit["durum"] == "bekliyor":
            return ret(
                "ONAY ZATEN BEKLIYOR -- SIMDI DUR.\n"
                f"Eylem: {bulgu['eylem']}\n"
                f"Onay : {kayit['id']}\n\n"
                "Bu turda bu eylemi TEKRAR DENEME ve baska yoldan yapmaya "
                "calisma. Buraya kadar yaptiklarini `kanit_ekle` ile yaz, "
                "sonra turu bitir.")

    ayrinti = (
        f"IMZA:{im}\n"
        f"arac  : {arac}\n"
        f"isaret: {bulgu['esles']!r}\n"
        f"girdi : {str(girdi)[:400]}\n"
        f"{bulgu['sebep']}"
    )
    try:
        onay = postane.onay_iste(oturum.ajan_ad, bulgu["eylem"],
                                 ayrinti=ayrinti, risk=bulgu["risk"],
                                 gorev_no=oturum.gorev_no)
    except Exception as exc:
        return ret(f"RISKLI EYLEM ve onay kaydi yazilamadi ({exc}). "
                   "Eylem yapilmadi.")
    ofis.db.olay_yaz(oturum.proje_id, "arac_onay_bekliyor",
                     f"{bulgu['ad']} -- {arac}",
                     ajan_ad=oturum.ajan_ad, gorev_id=gorev_id)
    return ret(
        "ONAY ISTENDI -- SIMDI DUR.\n"
        f"Sinif : {bulgu['ad']}\n"
        f"Eylem : {bulgu['eylem']}\n"
        f"Onay  : {onay['id']}\n\n"
        f"{bulgu['sebep']}\n\n"
        "SIMDI NE YAP: bu eylemi TEKRAR DENEME ve baska bir yoldan "
        "yapmaya calisma. Buraya kadar yaptiklarini `kanit_ekle` ile "
        "deftere yaz, sonra turu bitir. Patron onaylayinca is kaldigi "
        "yerden devam eder.")


ARACLAR = [
    {
        # IZIN ARACI ILK SIRADA ve ajana ANLATILMAZ: bunu ajan
        # cagirmaz, CLI cagirir. Aciklamasi yine de dogru yazilir --
        # araci goren bir insan ne oldugunu anlamali.
        "name": "izin_sor",
        "description": (
            "CLI'in izin kancasi. Ajan bunu KENDI CAGIRMAZ; izin "
            "gerektiren her arac cagrisinda CLI otomatik sorar ve ofis "
            "riskli olup olmadigina karar verir."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string"},
                "input": {"type": "object"},
            },
            "required": ["tool_name", "input"],
        },
        "islev": arac_izin_sor,
    },
    {
        "name": "durum",
        "description": (
            "Ofisin SU ANKI hali: isin, kabul olcutun, gecerli bilgiler, "
            "baglayici kararlar ve sorduklarinin cevabi. Brifing tur "
            "basinda verilir ve uzayan turda bayatlar; bir sey degisti mi "
            "diye merak edersen TAHMIN ETME, buna bak."
        ),
        "inputSchema": {"type": "object", "properties": {}},
        "islev": arac_durum,
    },
    {
        "name": "kanit_ekle",
        "description": (
            "Isin yapildigini GOSTEREN kaniti tahtaya yazar. Kanitsiz "
            "gorev kapanmaz. ISI BITIRINCE DEGIL, HER ADIMDA cagir: tur "
            "senin elinde olmayan sebeplerle kesilebilir (butce, limit, "
            "zaman asimi) ve eklenmemis her sey kaybolur. Ciktiyi UYDURMA."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tur": {"type": "string",
                        "description": "terminal | diff | gorsel | dosya | baglanti"},
                "baslik": {"type": "string",
                           "description": "Kosturdugun komut ya da dosya yolu."},
                "icerik": {"type": "string",
                           "description": "Gercek cikti ya da ne yaptigin."},
            },
            "required": ["tur", "baslik", "icerik"],
        },
        "islev": arac_kanit_ekle,
    },
    {
        "name": "bilgi_yaz",
        "description": (
            "Projeye dair KALICI bir bilgiyi ofisin hafizasina yazar (baska "
            "bir ajanin da bilmesi gereken: surum, adres, fiyat, kural, "
            "hesap adi). Ayni konuya yeni bilgi yazilirsa eskisi GECMISE "
            "gecer, silinmez. Ilgili bir konuya `[[konu]]` ile bagla: bagli "
            "bilgi, gorevle ortak kelimesi olmasa da brifinge gelir. Gecici "
            "is notu YAZMA. Insanin yazdigi bilgiyi degistiremezsin; farkli "
            "bir sey gorduysen soru_sor."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "konu": {"type": "string",
                         "description": "Kisa ad, cumle degil (orn. 'iade suresi')."},
                "icerik": {"type": "string",
                           "description": "Olgunun kendisi. En fazla 600 harf."},
            },
            "required": ["konu", "icerik"],
        },
        "islev": arac_bilgi_yaz,
    },
    {
        "name": "karar_yaz",
        "description": (
            "Kalici bir karari GEREKCESIYLE gunluge yazar. Gerekce "
            "zorunludur: gerekcesiz karar alti ay sonra sorgulanamaz ve "
            "ekip ayni tartismayi bastan yapar."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "karar": {"type": "string"},
                "gerekce": {"type": "string",
                            "description": "NEDEN boyle karar verildi. Zorunlu."},
            },
            "required": ["karar", "gerekce"],
        },
        "islev": arac_karar_yaz,
    },
    {
        "name": "soru_sor",
        "description": (
            "Lidere ya da insana soru sorar ve BEKLEMEYE GECER. "
            "Takildiginda, yazma alanin disina cikman gerektiginde ya da "
            "brifingle celisen bir sey gordugunde kullan. Soru sormak "
            "ucuz, yanlis varsayimla iki saat calismak pahalidir. Bunu "
            "cagirdiktan sonra DUR."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "soru": {"type": "string", "description": "Sorun, acik ve tek konulu."},
                "kime": {"type": "string",
                         "description": "'lider' (varsayilan), 'insan' ya da ajan adi."},
            },
            "required": ["soru"],
        },
        "islev": arac_soru_sor,
    },
    {
        "name": "onay_iste",
        "description": (
            "Riskli bir adim icin insan onayi ister ve BEKLEMEYE GECER. "
            "Kod yazmak, test kosmak onay istemez. Para harcamak, disariya "
            "yazmak (magaza, reklam, e-posta), yayina almak, `push` yapmak "
            "onay ISTER. Bunu cagirdiktan sonra DUR, eylemi yapma."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "eylem": {"type": "string", "description": "Yapmak istedigin sey."},
                "ayrinti": {"type": "string", "description": "Kapsam, tutar, etki."},
                "risk": {"type": "string",
                         "description": "dusuk | orta | yuksek (varsayilan orta)"},
            },
            "required": ["eylem"],
        },
        "islev": arac_onay_iste,
    },
    {
        "name": "gorsel_uret",
        "description": (
            "Bir ISTEMDEN gorsel uretir, dosyayi yazma alanina yazar ve "
            "KANIT olarak tahtaya gecirir. Istemi SEN yazarsin -- iyi bir "
            "istem isin yarisidir: konu, bicem, renk, oran, ne OLMAYACAGI. "
            "Uretici otomatik secilir (once ucretsiz olan). Uretilen "
            "dosya icin ayrica `kanit_ekle` CAGIRMA, iki kez sayilir."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "istem": {"type": "string",
                          "description": "Gorselin tam tarifi. Turkce ya da Ingilizce."},
                "dosya_adi": {"type": "string",
                              "description": "Orn. 'kreatif-1.png'. Yalniz dosya adi, yol degil."},
                "uretici": {"type": "string",
                            "description": "Bos birak (otomatik). 'gemini' ya da 'openai' zorlanabilir."},
                "model": {"type": "string", "description": "Bos birak (varsayilan)."},
            },
            "required": ["istem"],
        },
        "islev": arac_gorsel_uret,
    },
    {
        "name": "gorsel_iste",
        "description": (
            "Gorseli INSANA urettirir. Otomatik uretim mumkun degilse "
            "(anahtar yok, kota dolu) ya da is insanin kendi aracini "
            "kullanmasini gerektiriyorsa bunu cagir: istemi SEN yazarsin, "
            "istem insanin kuyruguna duser, o uretip tahtaya koyar. "
            "Bunu cagirdiktan sonra DUR."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "istem": {"type": "string",
                          "description": "Gorselin tam tarifi -- insan bunu oldugu gibi yapistiracak."},
                "dosya_adi": {"type": "string", "description": "Orn. 'kreatif-1.png'."},
            },
            "required": ["istem"],
        },
        "islev": arac_gorsel_iste,
    },
    {
        "name": "video_uret",
        "description": (
            "Bir ISTEMDEN video uretir, dosyayi yazma alanina yazar ve "
            "KANIT olarak tahtaya gecirir. Is kimligi HEMEN deftere "
            "yazilir: tur kesilse bile parasi odenmis is kaybolmaz. "
            "UCRETLI -- ucretsiz katman YOK; maliyet baslamadan once "
            "hesaplanir ve tavan asilirsa is HIC baslamaz. Uzun surer: "
            "`bekle=false` verirsen kimlik doner, sonra `video_durum`."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "istem": {"type": "string",
                          "description": "Videonun tam tarifi."},
                "saniye": {"type": "integer",
                           "description": "Sure. Tavan 30 sn -- daha uzunu parcalara bolunur."},
                "dosya_adi": {"type": "string", "description": "Orn. 'tanitim-1.mp4'."},
                "cozunurluk": {"type": "string", "description": "720p | 1080p | 4k"},
                "uretici": {"type": "string", "description": "Bos birak: ofis ucuz olani secer."},
                "model": {"type": "string"},
                "tavan_usd": {"type": "number",
                              "description": "Bu is icin para tavani. Asilirsa is BASLAMAZ."},
                "bekle": {"type": "boolean",
                          "description": "true (varsayilan): bitene kadar bekle. false: kimligi al, baska is yap."},
            },
            "required": ["istem"],
        },
        "islev": arac_video_uret,
    },
    {
        "name": "video_durum",
        "description": (
            "Baslatilmis bir video isini sorar; bittiyse INDIRIR, yazma "
            "alanina yazar ve kanit olarak gecirir. `video_uret`i "
            "`bekle=false` ile cagirdiysan ya da bekleme tavanina "
            "geldiysen bunu kullan."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "is_id": {"type": "string",
                          "description": "`video_uret`in dondurdugu kimlik."},
                "dosya_adi": {"type": "string", "description": "Orn. 'tanitim-1.mp4'."},
                "uretici": {"type": "string",
                            "description": "Genelde gereksiz -- defterden bulunur."},
            },
            "required": ["is_id"],
        },
        "islev": arac_video_durum,
    },
    {
        "name": "video_iste",
        "description": (
            "Videoyu INSANA urettirir. BUGUN UCRETSIZ OLAN TEK YOL: "
            "video API'lerinde ucretsiz katman yok, ucretsiz krediler "
            "yalnizca tuketici arayuzlerinde. Istemi SEN yazarsin, istem "
            "insanin kuyruguna duser, o uretip tahtaya koyar. Bunu "
            "cagirdiktan sonra DUR."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "istem": {"type": "string",
                          "description": "Videonun tam tarifi -- insan bunu oldugu gibi yapistiracak."},
                "saniye": {"type": "integer", "description": "Istenen sure."},
                "dosya_adi": {"type": "string", "description": "Orn. 'tanitim-1.mp4'."},
            },
            "required": ["istem"],
        },
        "islev": arac_video_iste,
    },
    {
        "name": "gorev_ac",
        "description": (
            "Yeni gorev acar. YALNIZCA LIDER kullanabilir. `neden`, "
            "`ana_hedef` ve `kabul_olcutu` zorunludur -- belirtimsiz is, "
            "hatalarin en buyuk kaynagidir."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "baslik": {"type": "string"},
                "neden": {"type": "string", "description": "Bu is NEDEN var."},
                "ana_hedef": {"type": "string", "description": "Hangi buyuk hedefe hizmet ediyor."},
                "kabul_olcutu": {"type": "string", "description": "Bittigini KANITLAYAN sey."},
                "govde": {"type": "string"},
                "yazma_alani": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["baslik", "neden", "ana_hedef", "kabul_olcutu"],
        },
        "islev": arac_gorev_ac,
    },
]

ARAC_DEFTERI = {a["name"]: a for a in ARACLAR}


# ---------------------------------------------------------------------------
# JSON-RPC
# ---------------------------------------------------------------------------

def _sonuc(istek_id, veri) -> dict:
    return {"jsonrpc": "2.0", "id": istek_id, "result": veri}


def _hata(istek_id, kod: int, mesaj: str) -> dict:
    return {"jsonrpc": "2.0", "id": istek_id,
            "error": {"code": kod, "message": mesaj}}


def istegi_isle(istek: dict, oturum: Oturum):
    """Tek bir JSON-RPC istegini isler. Bildirim ise None doner.

    BILDIRIMIN `id`si YOKTUR ve yaniti BEKLENMEZ. Yanit donmek, karsi
    tarafin beklemedigi bir satir yollamaktir ve akisi bozar.
    """
    istek_id = istek.get("id")
    yontem = istek.get("method") or ""
    parametre = istek.get("params") or {}

    if istek_id is None:
        return None                       # bildirim: yanit YOK

    if yontem == "initialize":
        # Istemcinin protokol surumu YANSITILIR. Kendi surumumuzu
        # dayatmak, uyumlu bir istemciyi sebepsiz reddetmek olurdu.
        surum = str(parametre.get("protocolVersion") or PROTOKOL)
        return _sonuc(istek_id, {
            "protocolVersion": surum,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SUNUCU_ADI, "version": "1.0.0"},
        })

    if yontem == "ping":
        return _sonuc(istek_id, {})

    if yontem == "tools/list":
        return _sonuc(istek_id, {"tools": [
            {"name": a["name"], "description": a["description"],
             "inputSchema": a["inputSchema"]} for a in ARACLAR
        ]})

    if yontem == "tools/call":
        ad = parametre.get("name") or ""
        arac = ARAC_DEFTERI.get(ad)
        if arac is None:
            return _sonuc(istek_id, {
                "content": [{"type": "text", "text": f"HATA: bilinmeyen arac: {ad}"}],
                "isError": True,
            })
        try:
            metin = arac["islev"](oturum, parametre.get("arguments") or {})
        except Exception as exc:
            # Istisna AKISI KOPARMAZ: ajan hatayi okuyup duzeltebilmeli.
            # Surecin olmesi, ajanin neyi yanlis yaptigini ogrenememesi
            # demektir.
            import traceback
            traceback.print_exc(file=sys.stderr)
            return _sonuc(istek_id, {
                "content": [{"type": "text", "text": f"HATA: {exc}"}],
                "isError": True,
            })
        hatali = isinstance(metin, str) and metin.startswith("HATA")
        return _sonuc(istek_id, {
            "content": [{"type": "text", "text": metin}],
            "isError": hatali,
        })

    return _hata(istek_id, -32601, f"Bilinmeyen yontem: {yontem}")


def yapilandirma(db_yolu: str, proje_id: str, ajan_ad: str,
                 gorev_no=None, ek_sunucular: dict = None) -> str:
    """Bu tur icin `--mcp-config` JSON'u uretir.

    Kimlik BURADA gomulur; araclar onu sormaz (bkz. dosya basi). Koltuk
    her tur icin yeniden uretir, cunku her turun sahibi ve gorevi baskadir.
    """
    ortam = {
        "OFIS_DB": str(db_yolu),
        "OFIS_PROJE": str(proje_id),
        "OFIS_AJAN": str(ajan_ad),
    }
    if gorev_no is not None:
        ortam["OFIS_GOREV"] = str(gorev_no)
    sunucular = {
        SUNUCU_ADI: {
            "command": sys.executable,
            "args": [str(Path(__file__).resolve())],
            "env": ortam,
        }
    }
    # EK SUNUCULAR isle gelir, hesapla degil: tarayici gibi yetenekler
    # gorevin ozelligidir. Hepsini her ture vermek, olculmus 131.543
    # jetonluk hatanin aynisi olurdu -- ajan, ISININ GEREKTIRDIGINI alir.
    #
    # Ofisin kendi sunucusu EZILEMEZ: ayni adi tasiyan bir ek sunucu
    # kanit/onay kanalini sessizce degistirebilirdi.
    for ad, girdi in (ek_sunucular or {}).items():
        if ad == SUNUCU_ADI:
            continue
        sunucular[ad] = girdi
    return json.dumps({"mcpServers": sunucular}, ensure_ascii=False)


def main() -> None:
    """stdio dongusu.

    `for satir in sys.stdin` KULLANILMAZ -- olculdu, sunucuyu asiyordu:
    o bicim okuma-onden tamponlamasi yapar ve ilk satiri EOF gelene kadar
    teslim etmez. MCP ise istek-yanit konusur; karsi taraf yanit bekler,
    biz EOF bekleriz ve iki taraf da sonsuza kadar durur. `readline()`
    satir teslim eder.
    """
    # STDIO UTF-8'E SABITLENIR.
    #
    # OLCULDU (19.09.2026): Windows konsolu cp1254. Sunucu stdin'i yerel
    # kodlamayla okuyordu ve emoji tek basina VEKIL karaktere donusuyor,
    # SQLite'a yazarken "surrogates not allowed" ile patliyordu. Gercek
    # bir turda ajan bunu dogru teshis etti ve duz Turkce soyledi:
    # "Emoji karakterler soruna neden oldu." Hata gorunurdu ama SEBEBI
    # sistemdeydi, ajanda degil.
    #
    # MCP protokolu JSON-RPC'dir ve JSON UTF-8'dir; yerel kodlama burada
    # hicbir zaman dogru cevap degildi.
    for akis in (sys.stdin, sys.stdout):
        try:
            akis.reconfigure(encoding="utf-8")
        except Exception:
            pass

    oturum = Oturum()
    while True:
        satir = sys.stdin.readline()
        if satir == "":
            break                       # karsi taraf boruyu kapatti
        satir = satir.strip()
        if not satir:
            continue
        try:
            istek = json.loads(satir)
        except json.JSONDecodeError:
            continue
        yanit = istegi_isle(istek, oturum)
        if yanit is None:
            continue
        sys.stdout.write(json.dumps(yanit, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
