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

    @property
    def kanat(self) -> str:
        """Bu turun TAKIMI (06.10.2026): isin takimi, yoksa ajanin takimi.
        Ikisi de okunamazsa "" -- yalniz ORTAK hafiza (sizinti yonune
        degil, eksik yonune yanilir)."""
        try:
            if self.gorev_no is not None:
                return self.gorev().get("kanat_id") or ""
            return self.ajan().get("kanat_id") or ""
        except Exception:                          # noqa: BLE001
            return ""

    @property
    def bellek(self):
        """Ajanin hafizaya bakan gozu: ortak + kendi takimi (baska takim YOK)."""
        return self.ofis.bellek.kapsam(self.kanat)

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

    bel = oturum.bellek
    kurallar = bel.kurallar()
    if kurallar:
        satirlar += ["", "## OFIS KURALLARI (insan onayli, HER iste gecerli)"]
        for k in kurallar:
            satirlar.append(f"- {k['metin']}")

    olgular = bel.gecerli_olgular()
    if olgular:
        satirlar += ["", "## GECERLI BILGILER"]
        for o in olgular[:40]:
            satirlar.append(f"- {o['konu']}: {o['icerik']}")

    kararlar = bel.son_kararlar(6)
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


def arac_belge_ara(oturum: Oturum, args: dict) -> str:
    """Patronun yukledigi belgelerde arama -- parca + KAYNAGI (06.10.2026)."""
    from ofis import belge as _belge
    sorgu = str(args.get("sorgu") or "").strip()
    if not sorgu:
        return "HATA: sorgu bos."
    try:
        azami = max(1, min(int(args.get("azami") or 5), 10))
    except (TypeError, ValueError):
        azami = 5
    belgeler = _belge.liste(oturum.ofis.db, oturum.proje_id, kanat=oturum.kanat)
    if not belgeler:
        return "Yuklu belge yok."
    bulunan = _belge.ara(oturum.ofis.db, oturum.proje_id, sorgu, azami=azami, kanat=oturum.kanat)
    if not bulunan:
        return ("Belgelerde bu kelimelerle bir sey bulunamadi ("
                + ", ".join(b["ad"] for b in belgeler[:10])
                + "). Baska kelimelerle dene; yoksa 'belgede yok' de, UYDURMA.")
    satir = ["Cevapta KAYNAGI yaz: (belge adi, yer)."]
    for b in bulunan:
        satir += ["", f"[{b['belge']} · {b['yer']}]", b["metin"][:1500]]
    return "\n".join(satir)


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
        r = oturum.bellek.bilgi_ekle(konu, icerik,
                                     yazan=oturum.ajan_ad,
                                     gorev_no=oturum.gorev_no)
    except BellekHatasi as exc:
        return f"HATA: {exc}"
    if r["durum"] == "ayni":
        return f"Zaten biliniyor: {r['konu']} (yeni surum acilmadi)."
    bag = baglar(r["icerik"])
    kirik = [b for b in bag if not oturum.bellek._konu_bul(b)]
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


def arac_beceri_oner(oturum: Oturum, args: dict) -> str:
    """Beceri TASLAGI (02.10.2026): kanitla gelir, patron onaylarsa yayina girer."""
    from ofis import beceri
    if not oturum.ajan_ad:
        return "HATA: kimliksiz tur -- taslagi kim oneriyor?"
    try:
        r = beceri.taslak_yaz(oturum.ofis, ad=str(args.get("ad") or ""),
                              aciklama=str(args.get("aciklama") or ""),
                              govde=str(args.get("yordam") or ""),
                              gorevler=args.get("kanit_isleri") or [],
                              gerekce=str(args.get("gerekce") or ""),
                              oneren=oturum.ajan_ad)
    except beceri.BeceriHatasi as exc:
        return f"HATA: {exc}"
    return (f"Beceri taslagi yazildi: {r['ad']} (kanit: "
            + ", ".join(f"#{n}" for n in r["gorevler"])
            + "). Patron onaylarsa butun ajanlar kullanir.")


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
    from ofis.bellek import BellekHatasi
    try:
        oturum.ofis.bellek.karar_yaz(karar, gerekce, oturum.ajan_ad, denetle=True,
                                     gorev_id=gorev_id)
    except BellekHatasi as exc:
        return f"HATA: {exc}"
    return f"Karar gunluge yazildi: {karar}"


#: Bir ajanin BIR IS icin takim sohbetine yazabilecegi azami bildirim.
#: Sohbet konusmadir, gunluk degil: her adimi yazan ajan insanin okumasi
#: gereken satiri kalabalikta kaybettirir. Ayrintinin yeri kanit ve akis.
SOHBET_AZAMI_IS_BASINA = 6
SOHBET_AZAMI_HARF = 1200
#: Bir bildirimde azami dosya (gorsel, pdf, video...).
SOHBET_AZAMI_EK = 5


def _kendi_yeni_dosyalari(ofis, gorev_id: str, girdi: dict, hedefler=None) -> bool:
    """Silme komutunun HER hedefi: kokun icinde, duz dosya, isin acilisindan
    SONRA yaratilmis mi. Olcemedigimiz her durumda False (= sorulur).

    `hedefler` verilirse (yama: `*** Delete File:` yollari, koke gore) komut
    ayristirilmaz -- 06.10.2026: kural yalniz kabukta vardi, codex'in yamayla
    sildigi KENDI dosyasi patrona soruluyordu."""
    import datetime as _dt
    from pathlib import Path as _P
    # Sunucu betik olarak kosar; `riskli` modul duzeyinde YOK (kapi
    # islevi kendi icinde ice aktarir). Ilk yazimda burada yoktu: NameError
    # asagidaki genis except'te yutuldu ve kural hic uygulanmadi (duman_mcp
    # yakaladi).
    from ofis import riskli
    try:
        kok = str(_P(ofis.isin_koku(gorev_id)).resolve())
        if hedefler is not None:
            cwd = str(girdi.get("workdir") or girdi.get("cwd") or kok)
            hedefler = [riskli._yol_coz(h, cwd) for h in hedefler]
        else:
            hedefler = riskli.silme_hedefleri(str(girdi.get("command") or ""), kok)
        if not hedefler:
            return False
        with ofis.db.baglanti() as c:
            r = c.execute("SELECT olusturuldu FROM gorev WHERE id = ?", (gorev_id,)).fetchone()
        if not r:
            return False
        acilis = _dt.datetime.fromisoformat(r["olusturuldu"]).timestamp()
        from ofis.yollar import KARALAMA as _KARALAMA
        karalama = (_P(kok) / _KARALAMA).resolve()
        for h in hedefler:
            p = _P(h).resolve()
            # KARALAMA (01.10.2026, G17 codex): ayni komut `karalama/`da
            # gecici dosya yazip siliyordu; kapi komuttan ONCE bakar, dosya
            # henuz yoktu -> soruldu, is durdu. Orasi yalniz yardimci
            # dosyalarin yeri; icindeki (klasorun kendisi degil) silme serbest.
            if p != karalama and p.is_relative_to(karalama) and ".git" not in p.parts:
                continue
            if not p.is_relative_to(kok) or not p.is_file() or ".git" in p.parts:
                return False
            # Acilis SANIYEYE yuvarli (db.simdi); ayni saniyede ama isten ONCE
            # yaratilan dosya "sonra" sayiliyordu (06.10, duman_kapi_kod
            # yakaladi). Supheli saniye SORULUR: +1 sn.
            if p.stat().st_ctime < acilis + 1:
                return False
        return True
    except Exception:                  # noqa: BLE001 -- supheliyse SORULUR
        return False


def arac_sohbete_yaz(oturum: Oturum, args: dict) -> str:
    """Ajan TAKIM SOHBETINE kisa bir bildirim yazar (29.09.2026).

    Rakipte ajanlar sonuclarini ayni akisa birakiyor ([ODA] protokolu).
    Bizde de: engel, onemli bulgu, is bitti. Ama bu bir BILDIRIMDIR --
    cevap beklenmez, kimseye is vermez. Soru `soru_sor`, onay `onay_iste`;
    ikisinin yerine gecmez (ceviri bekleyen bir soru sohbette kaybolurdu).
    Kimlik ortamdan: ajan baskasi adina yazamaz.

    EKLER (30.09): `ekler=[yol, ...]` ile gorsel/pdf/video gonderilir;
    kural `ekler.paylas`ta (kok ici, gizli degil, sinir). Biri bile
    gonderilemezse HICBIR SEY yazilmaz ve sebep ajana doner -- yarim
    mesaj patrona "ekledim" deyip dosyasiz gelirdi.
    """
    metin = str(args.get("metin") or "").strip()
    ham_ekler = args.get("ekler") or []
    if isinstance(ham_ekler, str):
        ham_ekler = [ham_ekler]
    if not isinstance(ham_ekler, list):
        return "HATA: `ekler` bir yol listesi olmali."
    ham_ekler = [str(y).strip() for y in ham_ekler if str(y or "").strip()]
    if not metin and not ham_ekler:
        return "HATA: bos mesaj yazilamaz."
    if len(ham_ekler) > SOHBET_AZAMI_EK:
        return f"HATA: bir bildirimde en fazla {SOHBET_AZAMI_EK} dosya."
    if not oturum.ajan_ad:
        return "HATA: ajan kimligi yok; sohbete yazilamaz."
    kesildi = len(metin) > SOHBET_AZAMI_HARF
    metin = metin[:SOHBET_AZAMI_HARF]
    gorev_id = None
    if oturum.gorev_no is not None:
        try:
            gorev_id = oturum.gorev()["id"]
        except Exception:
            gorev_id = None
    db = oturum.ofis.db
    with db.baglanti() as conn:
        sayi = conn.execute(
            "SELECT COUNT(*) FROM olay WHERE proje_id = ? AND tur = 'ajan_sohbet' "
            "AND ajan_ad = ? AND gorev_id IS ?",
            (oturum.proje_id, oturum.ajan_ad, gorev_id)).fetchone()[0]
    if sayi >= SOHBET_AZAMI_IS_BASINA:
        return (f"HATA: bu is icin sohbete {SOHBET_AZAMI_IS_BASINA} kez yazdin; "
                "sohbet gunluk degil. Ayrintiyi `kanit_ekle` ile yaz; patrona "
                "sorun varsa `soru_sor`.")
    from ofis import ekler as _ek
    yollar, hatalar = [], []
    for y in ham_ekler:
        try:
            yollar.append(_ek.paylas(oturum.ofis, y, ajan_ad=oturum.ajan_ad))
        except _ek.EkHatasi as exc:
            hatalar.append(str(exc))
    if hatalar:
        return ("HATA: mesaj YAZILMADI, ek gonderilemedi: " + " · ".join(hatalar)
                + " (yol proje kokune gore olmali; dosyayi once kokte olustur).")
    govde = "\n".join(x for x in (metin, _ek.satirlar(yollar)) if x)
    db.olay_yaz(oturum.proje_id, "ajan_sohbet", govde, ajan_ad=oturum.ajan_ad,
                gorev_id=gorev_id)
    return ("Takim sohbetine yazildi." + (" (1200 harfte kesildi)" if kesildi else "")
            + (f" {len(yollar)} dosya eklendi." if yollar else "")
            + " Bu bir bildirimdir, cevap BEKLEME; isine devam et.")


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
            # Eski iste lider bulunamayinca soru SESSIZCE patrona gidiyordu
            # (01.10.2026); kural artik tek yerde (`gorevin_lideri`).
            alici = oturum.ofis.kadro.gorevin_lideri(g or {})["ad"]
        except Exception:
            alici = "insan"
    try:
        oturum.ofis.postane.soru_sor(oturum.ajan_ad, alici, soru,
                                     gorev_no=oturum.gorev_no, mod="bekleyen",
                                     secenekler=args.get("secenekler"),
                                     onerilen=args.get("onerilen"))
    except Exception as exc:                      # noqa: BLE001 -- ajana sebebi soylenir
        return f"HATA: soru iletilmedi -- {exc}. Duzeltip yeniden sor."
    return (f"Soru '{alici}' adresine iletildi ve cevap bekleniyor.\n"
            "SIMDI DUR: tahminle devam etme, turu burada bitir. "
            "Cevap gelince kaldigin yerden surdurulecek.")


#: Kredi paketi onayinin `ayrinti` ilk satiri -- TEK KAYNAK `tarayici`.
from ofis.tarayici import KREDI_PAKETI_ISARETI  # noqa: E402


def arac_onay_iste(oturum: Oturum, args: dict) -> str:
    """Riskli adim insana takilir. Tam otonomi ISTENMEZ."""
    eylem = str(args.get("eylem") or "").strip()
    if not eylem:
        return "HATA: onay istenen eylem bos olamaz."
    risk = str(args.get("risk") or "orta").strip() or "orta"
    if risk not in ("dusuk", "orta", "yuksek"):
        return f"HATA: risk 'dusuk', 'orta' ya da 'yuksek' olmali ({risk} degil)."
    ayrinti = str(args.get("ayrinti") or "")
    # KREDI PAKETI (07.10.2026, canli deneme): ajan paketi onay_iste ile
    # sordu, patron onayladi -- ve kapi gercek "Olusturmaya basla"da AYNI
    # seyi IKINCI KEZ sordu (paket onayi kapiya bagli degildi). Paket onayi
    # artik `uretim` kadar kredili tiklamayi acar; fazlasi yine sorulur.
    kredi, uretim = args.get("kredi"), args.get("uretim")
    if kredi not in (None, "") or uretim not in (None, ""):
        try:
            kredi, uretim = int(kredi), int(uretim)
        except (TypeError, ValueError):
            return ("HATA: kredi paketi icin `kredi` (toplam kredi) ve `uretim` (kredili "
                    "uretim tiklamasi sayisi, yeniden cekim payi dahil) TAM SAYI olmali.")
        if kredi <= 0 or uretim <= 0:
            return "HATA: `kredi` ve `uretim` sifirdan buyuk olmali."
        if oturum.gorev_no is None:
            return "HATA: kredi paketi bir ise baglidir; bu turda gorev yok."
        eylem = f"KREDI PAKETI ({kredi} kredi, {uretim} uretim): {eylem}"
        ayrinti = f"{KREDI_PAKETI_ISARETI} kredi={kredi} uretim={uretim}\n" + ayrinti
    oturum.ofis.postane.onay_iste(
        oturum.ajan_ad, eylem, ayrinti=ayrinti,
        risk=risk, gorev_no=oturum.gorev_no)
    if kredi not in (None, ""):
        return ("Kredi paketi onaya gonderildi. Patron onaylarsa bu isteki kredili "
                f"uretimlerden {uretim} tanesi kapida TEKRAR SORULMAZ; fazlasi sorulur.\n"
                "SIMDI DUR: uretme, turu burada bitir.")
    return ("Onay istegi kaydedildi, insan cevabi bekleniyor.\n"
            "SIMDI DUR: eylemi YAPMA, turu burada bitir.")


def arac_giris_iste(oturum: Oturum, args: dict) -> str:
    """Bir hesaba giris gerekiyor: insan girer, ajan bekler (28.09.2026).

    SIFRE AJANA GECMEZ: bu arac sifre ALMAZ, yalniz NEREYE ve NEDEN
    girilmesi gerektigini alir. Kayit onay defterine duser; bekleme,
    kilit ve surdurme onayla ayni yoldan isler.
    """
    from ofis import giris as _giris
    if oturum.gorev_no is None:
        return "HATA: giris istegi bir ise baglidir; bu turda gorev yok."
    try:
        _giris.iste(oturum.ofis, oturum.ajan_ad, oturum.gorev_no,
                    tur=str(args.get("tur") or "web"),
                    hizmet=str(args.get("hizmet") or ""),
                    adres=str(args.get("adres") or ""),
                    neden=str(args.get("neden") or ""))
    except _giris.GirisHatasi as exc:
        return f"HATA: {exc}"
    return ("Giris istegi patrona iletildi. Patron kendisi girecek; sifreyi "
            "sen ISTEME, yazma, tahmin etme.\n"
            "SIMDI DUR: buraya kadar yaptiklarini `kanit_ekle` ile yaz ve "
            "turu bitir. Giris yapilinca kaldigin yerden surdurulecek.")


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


def _video_kaniti(oturum: Oturum, d: dict, baslik: str) -> None:
    """Olcum ofisin: kanit OTOMATIK yazilir (ajan ayrica `kanit_ekle` cagirmaz)."""
    from ofis import kurgu as _k
    icerik = (_k.ozet_metni(d) + "\nvideo: " + d.get("video", "")
              + ("\nkapak: " + d["kapak"] if d.get("kapak") else "")
              + ("\nkareler: " + d["kareler"] if d.get("kareler") else ""))
    oturum.ofis.tahta.kanit_ekle(oturum.gorev_no, "dosya", baslik, icerik, oturum.ajan_ad)


def _goreli(yol: str, kok) -> str:
    from pathlib import Path as _P
    try:
        return _P(yol).resolve().relative_to(_P(kok).resolve()).as_posix()
    except (ValueError, OSError):
        return yol


def arac_video_kurgula(oturum: Oturum, args: dict) -> str:
    """Kurgu PLANINI paylasmaya hazir videoya cizer (`ofis/kurgu.py`).

    Ajan Remotion kodu yazmaz: plani yazar, ofis cizer ve OLCER. Cikti
    `.ofis/ekler/<ad>.mp4` + kapak + kare ozeti; olcum kanit olur.
    """
    import json as _json
    from ofis import kurgu as _k
    if oturum.gorev_no is None:
        return "HATA: bu turda acik bir gorev yok; video nereye ait olacak?"
    plan = args.get("plan")
    if isinstance(plan, str):
        try:
            plan = _json.loads(plan)
        except ValueError as exc:
            return f"HATA: plan JSON degil: {exc}"
    g = oturum.gorev()
    kok = oturum.ofis.isin_koku(g)
    ad = str(args.get("ad") or f"video-{g['no']}")
    try:
        d = _k.kurgula(plan, kok, ad)
    except _k.KurguHatasi as exc:
        return f"HATA: {exc}"
    _video_kaniti(oturum, d, f"video: {_goreli(d['video'], kok)} ({d['bicim']})")
    satirlar = [
        "VIDEO HAZIR (ofisin olcumu):", _k.ozet_metni(d), "",
        f"video  : {_goreli(d['video'], kok)}",
        f"kapak  : {_goreli(d['kapak'], kok)}" if d.get("kapak") else "kapak  : cikarilamadi",
        f"kareler: {_goreli(d['kareler'], kok)}" if d.get("kareler") else "kareler: cikarilamadi",
        "",
        "Kanit OTOMATIK yazildi; ayrica kanit_ekle CAGIRMA.",
        "Kare ozetine (kareler) BAK: yazi okunuyor mu, sahne dogru mu? Sorun varsa plani "
        "duzeltip yeniden ciz.",
    ]
    if d["sorunlar"]:
        satirlar.append("SORUN VAR: bu video paylasilamaz; once duzelt.")
    else:
        satirlar.append("Bitince patrona `sohbete_yaz(ekler=[video, kapak])` ile gonder ve "
                        "Instagram aciklama metnini (+ etiketler) mesaja yaz.")
    return "\n".join(satirlar)


def arac_video_denetle(oturum: Oturum, args: dict) -> str:
    """Herhangi bir videoyu (orn. Flow'dan inen) OLCER; kanit olarak yazar."""
    from pathlib import Path as _P
    from ofis import kurgu as _k
    if oturum.gorev_no is None:
        return "HATA: bu turda acik bir gorev yok."
    g = oturum.gorev()
    kok = _P(oturum.ofis.isin_koku(g)).resolve()
    p = _P(str(args.get("dosya") or "").strip())
    if not str(p):
        return "HATA: dosya gerekli."
    if not p.is_absolute():
        p = kok / p
    try:
        p.resolve().relative_to(kok)
    except ValueError:
        return "HATA: dosya isin klasorunun disinda; once klasore indir."
    if not p.is_file():
        return f"HATA: {args.get('dosya')} bulunamadi."
    try:
        d = _k.denetle(p, str(args.get("bicim") or ""))
    except _k.KurguHatasi as exc:
        return f"HATA: {exc}"
    d["video"] = str(p)
    _video_kaniti(oturum, d, f"video olcumu: {_goreli(str(p), kok)}")
    return ("OLCUM (ofisin):\n" + _k.ozet_metni(d)
            + (f"\nkareler: {_goreli(d['kareler'], kok)}" if d.get("kareler") else "")
            + (f"\nkapak: {_goreli(d['kapak'], kok)}" if d.get("kapak") else "")
            + "\nKanit otomatik yazildi.")


def arac_medya_isle(oturum: Oturum, args: dict) -> str:
    """YEREL MEDYA ARACLARI (07.10.2026, `ofis/medya_arac.py`): gorsel buyutme
    (Real-ESRGAN), altyazi (Whisper; replik verilirse yazim replikten), arka
    plan silme (rembg). Yerelde kosar, KREDI HARCAMAZ; cikti olculur, kanit
    otomatik yazilir."""
    import json as _json
    from pathlib import Path as _P
    from ofis import medya_arac as _m
    from ofis import video_islem as _vi
    from ofis.kurgu import KurguHatasi as _KH
    if oturum.gorev_no is None:
        return "HATA: bu turda acik bir gorev yok."
    islem = str(args.get("islem") or "").strip()
    g = oturum.gorev()
    kok = _P(oturum.ofis.isin_koku(g)).resolve()

    def _ic(ham: str):
        p = _P(str(ham or "").strip())
        if not str(p) or str(p) == ".":
            return None
        if not p.is_absolute():
            p = kok / p
        try:
            p.resolve().relative_to(kok)
        except ValueError:
            raise _m.MedyaHatasi(f"{ham} isin klasorunun disinda; once klasore al.")
        return p

    ekler = kok / ".ofis" / "ekler"
    try:
        p = _ic(args.get("dosya"))
        if p is None or not p.is_file():
            return f"HATA: dosya bulunamadi: {args.get('dosya')!r}"
        cikti = _ic(args.get("cikti"))
        if islem == "gorsel_buyut":
            uz = p.suffix.lower() if p.suffix.lower() in (".png", ".jpg", ".jpeg") else ".png"
            d = _m.gorsel_buyut(p, cikti or ekler / f"{p.stem}-buyuk{uz}",
                                olcek=int(args.get("olcek") or 2), en=int(args.get("en") or 0))
            ozet = (f"BUYUTULDU (ofisin olcumu): {d['kaynak_boyut'][0]}x{d['kaynak_boyut'][1]} -> "
                    f"{d['boyut'][0]}x{d['boyut'][1]}, {d['sure_sn']} sn, siyah degil\n"
                    f"cikti: {_goreli(d['cikti'], kok)}")
        elif islem == "altyazi":
            d = _m.altyazi(p, replik=str(args.get("replik") or ""),
                           srt=cikti or ekler / f"{p.stem}.srt")
            ozet = ("ALTYAZI (ofisin olcumu)"
                    + (f", replikle uyum %{round(d['uyum'] * 100)}" if d["uyum"] is not None else "")
                    + f"\nduyulan: {d['duyulan'] or '(konusma yok)'}\n"
                    + (f"UYARI: {d['uyari']}\n" if d["uyari"] else "")
                    + f"srt: {_goreli(d['srt'], kok)}\n"
                    + "video_kurgula plani icin \"altyazi\" (klibin kendi zamani; sahne "
                      "kurguda baska yerdeyse kaydir):\n"
                    + _json.dumps(d["satirlar"], ensure_ascii=False))
        elif islem == "arka_plan":
            d = _m.arka_plan(p, cikti or ekler / f"{p.stem}-arkasiz.png",
                             model=str(args.get("model") or "birefnet-general-lite"))
            ozet = (f"ARKA PLAN SILINDI (ofisin olcumu): on plan %{round(d['on_plan_orani'] * 100)}, "
                    f"{d['sure_sn']} sn, model {d['model']}\n"
                    + (f"UYARI: {d['uyari']}\n" if d["uyari"] else "")
                    + f"cikti: {_goreli(d['cikti'], kok)} (saydam PNG)")
        elif islem == "sahneler":
            d = _vi.sahneler(p, cikti or ekler / f"{p.stem}-sahneler.jpg",
                             esik=float(args.get("esik") or 0.3))
            ozet = (f"SAHNELER (ofisin olcumu): {len(d['sahneler'])} sahne, {d['sure']} sn\n"
                    + "\n".join(f"  #{s['no']}  {s['bas']:.2f}-{s['son']:.2f} sn ({s['sure']:.1f} sn)"
                                 for s in d["sahneler"][:60])
                    + f"\nkare panosu: {_goreli(d['pano'], kok)} (DOSYAYI AC VE BAK; her kutu bir "
                      "sahnenin ortasi, altinda zamani)")
        elif islem == "kes":
            d = _vi.kes(p, cikti or ekler / f"{p.stem}-kes.mp4",
                        bas=float(args.get("bas") or 0), son=float(args.get("son") or 0))
            ozet = (f"KESILDI (ofisin olcumu): {d['bas']}-{d['son']} sn -> "
                    f"{d['olcum'].get('sure')} sn, {d['olcum'].get('genislik')}x"
                    f"{d['olcum'].get('yukseklik')}\ncikti: {_goreli(d['cikti'], kok)}")
        elif islem == "ses_ayir":
            d = _vi.ses_ayir(p, cikti or ekler / f"{p.stem}-ses.m4a")
            ozet = (f"SES AYRILDI (ofisin olcumu): {d['olcum'].get('sure')} sn\n"
                    f"cikti: {_goreli(d['cikti'], kok)} (video_kurgula'da muzik ya da sesler[])")
        elif islem == "sessizlik_kes":
            d = _vi.sessizlik_kes(p, cikti or ekler / f"{p.stem}-sikistirilmis.mp4",
                                  esik_db=float(args.get("esik_db") or -35),
                                  en_az=float(args.get("en_az") or 0.6))
            if not d.get("cikti"):
                return f"DEGISMEDI: {d['not']}"
            ozet = (f"SESSIZLIK ATILDI (ofisin olcumu): {d['sure_once']} -> {d['sure_sonra']} sn "
                    f"({d['atilan_sn']} sn atildi, {d['parca']} parca)\n"
                    f"cikti: {_goreli(d['cikti'], kok)}")
        elif islem == "vokal_ayir":
            uz = ".wav"
            d = _m.vokal_ayir(p, ekler / f"{p.stem}-vokal{uz}", ekler / f"{p.stem}-muzik{uz}")
            ozet = (f"VOKAL / MUZIK AYRILDI (yapay zeka, ofisin olcumu): {d['sure']} sn ses, "
                    f"{d['sure_sn']} sn surdu; vokal {d['vokal_db']} dB, muzik {d['muzik_db']} dB\n"
                    + (f"UYARI: {d['uyari']}\n" if d["uyari"] else "")
                    + f"vokal: {_goreli(d['vokal'], kok)}\nmuzik: {_goreli(d['muzik'], kok)}\n"
                      "(video_kurgula: klibin sesini kapat, vokali sesler[]'e koy, yeni muzik ekle)")
        elif islem == "kare_ara":
            d = _vi.kare_ara(p, cikti or ekler / f"{p.stem}-akici.mp4",
                             carpan=int(args.get("carpan") or 2))
            ozet = (f"ARA KARE (RIFE, ofisin olcumu): {d['fps_once']:g} -> {d['fps_sonra']:g} kare/sn, "
                    f"sure {d['sure_once']} -> {d['sure_sonra']} sn, {d['sure_sn']} sn surdu\n"
                    f"cikti: {_goreli(d['cikti'], kok)} (video_kurgula'da hiz 0.5 / 0.25 ile AKICI agir cekim)")
        else:
            return ("HATA: islem 'gorsel_buyut', 'altyazi', 'arka_plan', 'sahneler', 'kes', "
                    "'ses_ayir', 'sessizlik_kes', 'kare_ara' ya da 'vokal_ayir' olmali.")
    except (_m.MedyaHatasi, _KH) as exc:
        return f"HATA: {exc}"
    except (ValueError, TypeError) as exc:
        return f"HATA: {exc}"
    oturum.ofis.tahta.kanit_ekle(oturum.gorev_no, "dosya", f"medya: {islem} {_goreli(str(p), kok)}",
                                 ozet, oturum.ajan_ad)
    return ozet + "\nKanit OTOMATIK yazildi; ayrica kanit_ekle CAGIRMA."


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

    # AJANIN SECTIGI URETICI DUSERSE OFIS SIRAYI DENER (01.10.2026).
    # Olculdu (gercek set G11, claude): ajan once 'gemini'yi (gunluk kota
    # dolu), sonra 'openai'yi (ucretli, para kilidi) ACIKCA secti; ofisin
    # sirasindaki ABONELIK yolu (codex, fatura yok) hic denenmedi ve patrona
    # "kendi AI aracinda uret" diye istem dosyasi birakildi. Ureticiyi
    # AJAN secti, patron degil: dusunce otomatik siraya donulur. Para kilidi
    # korunur -- otomatik sira ucretliyi zaten atlar.
    # REFERANS FOTOGRAF (08.10.2026, Brave): gercek urunun fotografi
    # ureticiye EK olarak gider; yollar ajanin kokunde olmali (kok disi
    # dosyayi ofis disariya tasimaz).
    ham = args.get("referanslar") or []
    if isinstance(ham, str):
        ham = [ham]
    referanslar = []
    kok_r = kok.resolve()
    for r in ham:
        p = _Path(str(r).strip())
        p = (p if p.is_absolute() else kok / p).resolve()
        try:
            p.relative_to(kok_r)
        except ValueError:
            return f"HATA: referans kokun disinda: {r}"
        referanslar.append(p)

    secilen = str(args.get("uretici") or "")
    notlar = []
    try:
        sonuc = _gorsel.uret(istem, hedef, uretici=secilen,
                             model=str(args.get("model") or ""),
                             referanslar=referanslar, oran=str(args.get("oran") or ""))
    except _gorsel.GorselHatasi as exc:
        if not secilen:
            return f"HATA: {exc}"
        notlar.append(f"(secilen '{secilen}' olmadi: {str(exc)[:160]} -- otomatik sira denendi)")
        try:
            sonuc = _gorsel.uret(istem, hedef, uretici="", model="",
                                 referanslar=referanslar, oran=str(args.get("oran") or ""))
        except _gorsel.GorselHatasi as exc2:
            return f"HATA: {exc2}\n" + notlar[0]

    # Kanit: dosya GERCEKTEN diskte. Olculdu, iddia edilmedi.
    # MALIYET KANITA YAZILIR. Olcmedigimiz sey yonetilemez -- ve para
    # soz konusuysa "sonra bakariz" faturayla ogrenmek demektir.
    # Olculemiyorsa UYDURULMAZ: alan hic yazilmaz.
    para = (f" · ${sonuc['maliyet_usd']:.4f}"
            if sonuc.get("maliyet_usd") is not None else "")
    oturum.ofis.tahta.kanit_ekle(
        g["no"], "gorsel", sonuc["yol"],
        f"{sonuc['uretici']}/{sonuc['model']} ile uretildi, "
        f"{sonuc['bayt']} bayt{para}"
        + (f" · referans: {', '.join(sonuc['referanslar'])}"
           if sonuc.get("referanslar") else "")
        + f". Istem: {istem[:200]}",
        oturum.ajan_ad)

    satir = [f"Gorsel uretildi: {sonuc['yol']}",
             f"  uretici: {sonuc['uretici']} · model: {sonuc['model']} "
             f"· {sonuc['bayt']} bayt"
             + (f" · MALIYET ${sonuc['maliyet_usd']:.4f}"
                if sonuc.get("maliyet_usd") is not None else ""),
             "  KANIT olarak tahtaya yazildi (ayrica `kanit_ekle` cagirma)."]
    for a in (sonuc.get("atlananlar") or []):
        satir.append(f"  (atlandi: {a['uretici']} -- {a['sebep'][:120]})")
    satir += notlar
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

def _tur_suphesi(oturum) -> str:
    """Bu gorevin SU ANKI turunda `talimat_suphesi` olayi var mi? Varsa
    ilk alintiyi dondurur. Tur siniri: gorevin son `basladi` olayi."""
    if oturum.gorev_no is None:
        return ""
    ofis = oturum.ofis
    gid = ofis.tahta.gorev(oturum.gorev_no)["id"]
    with ofis.db.baglanti() as c:
        bas = c.execute("SELECT COALESCE(MAX(rowid), 0) FROM olay WHERE gorev_id=? "
                        "AND tur='basladi'", (gid,)).fetchone()[0]
        r = c.execute("SELECT govde FROM olay WHERE gorev_id=? AND tur='talimat_suphesi' "
                      "AND rowid > ? ORDER BY rowid DESC LIMIT 1", (gid, bas)).fetchone()
    return (r["govde"] or "suphe")[:200] if r else ""


from ofis.postane import KART_ACILDI as _KART_ACILDI  # noqa: E402


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
        if bulgu is None and arac in riskli.KABUK_ARACLARI:
            # BETIK DOSYASI (01.10.2026): komut serbest gorunse de
            # calistirdigi betigin ICI taranir.
            # Kok alinamazsa (defter yok) betik yolu surecin klasorunden
            # cozulur -- `ls` gibi serbest bir komut bu yuzden REDDEDILMEZ.
            try:
                _kok = oturum.ofis.kok_klasoru(oturum.kanat or None)
            except Exception:            # noqa: BLE001
                _kok = ""
            bulgu = riskli.betik_degerlendir(arac, girdi, _kok)
    except Exception as exc:
        # Kapi patlarsa KAPALI kalir. Acik kalsaydi kapinin bozulmasi
        # her seyi sessizce serbest birakirdi -- para ve yayin
        # kontrolleri bu projede her zaman "fail closed" olur.
        return ret(f"Ofis kapisi degerlendirme yapamadi ({exc}). Guvenli "
                   "tarafta kaliyoruz: bu eylem YAPILMADI.")

    # SUPHE SONRASI SIKILASMA (F3 / E22). Bu turda tarayici kapisi talimat
    # benzeri bir dis icerik gorduyse (`talimat_suphesi` olayi), normalde
    # serbest ya da yalniz kaydedilen DISARI CIKABILEN eylemler sorulur:
    # ag komutu (curl, iwr...) ve baglayicida kayit. Yerel dosya yazma
    # serbest kalir (geri alinabilir, disk olcumu goruyor).
    aday = ((bulgu is None and arac in riskli.KABUK_ARACLARI
             and riskli.AG_KOMUTU.search(str(girdi.get("command") or "")))
            or (bulgu is not None and not bulgu.get("sorulur")))
    if aday:
        try:
            alinti = _tur_suphesi(oturum)
        except Exception:
            alinti = None
        if alinti:
            bulgu = riskli.suphe_bulgusu(
                arac, str(girdi.get("command") or girdi)[:200], alinti)

    # CANLI SISTEM (08.10.2026, patron: "sahte kip istemiyorum, her sey gercek
    # calisacak"): 06.10'daki takim "deneme kipi" canliya dokunan eylemi
    # SORMADAN reddediyordu. Artik REDDEDILMEZ, SORULUR (yayin sinifi; kural
    # `canli.py`). Riskli olcutu onu zaten soruyorsa o bulgu kalir. Olcum
    # patlarsa kapi KAPALI kalir.
    from ofis import canli as _canli
    _kok_c = ""
    try:
        _kok_c = oturum.ofis.kok_klasoru(getattr(oturum, "kanat", "") or None)
    except Exception:                    # noqa: BLE001 -- betik yolu surecin klasorunden
        pass
    try:
        _sebep = _canli.degerlendir(arac, girdi, bulgu, _kok_c)
    except Exception as exc:             # noqa: BLE001
        return ret(f"Ofis kapisi canli denetimini yapamadi ({exc}). Eylem YAPILMADI.")
    if _sebep and (bulgu is None or not bulgu.get("sorulur")):
        bulgu = _canli.bulgu(arac, girdi, _sebep)

    if bulgu is None:
        return izin()
    if bulgu.get("ret"):
        # KURAL RET (09.10, kendi kodu): kart acilmaz, dogru yol soylenir.
        return ret("REDDEDILDI (kural): " + bulgu["sebep"])
    _m = _kapi_karari(oturum, arac, girdi, bulgu)
    return izin() if _m is None else ret(_m)

def _kapi_karari(oturum: Oturum, arac: str, girdi: dict, bulgu: dict):
    """Riskli bulgunun KARARI -- TEK yer (izin_sor ve masaustu araclari)."
    `None` = gecer (onayli / izinli / kayda gecen); metin = durmasi gereken
    sebep (onay karti acildiysa onu da soyler). 08.10.2026: masaustu araclari
    kapiyi KENDI icinde sorar (ofis araclari CLI kancasindan serbest gecer);
    kural ikiye bolunmesin diye karar izin_sor'dan buraya alindi.
    """
    from ofis import riskli
    try:
        ofis = oturum.ofis
        postane = ofis.postane
    except Exception as exc:
        return (f"RISKLI EYLEM ve onay defterine ulasilamiyor ({exc}). "
                   "Eylem yapilmadi.")

    gorev_id = None
    if oturum.gorev_no is not None:
        try:
            gorev_id = ofis.tahta.gorev(oturum.gorev_no)["id"]
        except Exception:
            gorev_id = None

    # AJANIN BU ISTE KENDI YARATTIGI DOSYAYI SILMESI sorulmaz, kayda gecer
    # (01.10.2026, gercek set G11; kural `riskli.silme_hedefleri`).
    if (bulgu.get("sinif") == "silme" and arac in riskli.KABUK_ARACLARI
            and gorev_id and _kendi_yeni_dosyalari(ofis, gorev_id, girdi)):
        ofis.db.olay_yaz(oturum.proje_id, "kendi_dosyasini_sildi",
                         f"{arac} | {str(girdi.get('command') or '')[:200]}",
                         ajan_ad=oturum.ajan_ad, gorev_id=gorev_id)
        return None
    if (bulgu.get("sinif") == "silme" and arac in riskli.YAMA_ARACLARI
            and gorev_id and bulgu.get("yama_hedefleri")
            and _kendi_yeni_dosyalari(ofis, gorev_id, girdi, bulgu["yama_hedefleri"])):
        ofis.db.olay_yaz(oturum.proje_id, "kendi_dosyasini_sildi",
                         f"{arac} | yama: {', '.join(bulgu['yama_hedefleri'])[:200]}",
                         ajan_ad=oturum.ajan_ad, gorev_id=gorev_id)
        return None

    # SORULMAYAN ama KAYDA GECEN sinif.
    if not bulgu.get("sorulur"):
        ofis.db.olay_yaz(
            oturum.proje_id, "arac_degisikligi",
            f"{arac} | {bulgu['esles']} | {str(girdi)[:200]}",
            ajan_ad=oturum.ajan_ad, gorev_id=gorev_id)
        return None

    # PATRONUN IZNI (ofis/izin.py): patron bu eylemi ACIKCA istediyse
    # ya da kalici izin varsa SORULMAZ, ama kayda gecer. Para ve silme
    # bu yoldan hic gecmez (izin.HER_ZAMAN_SORULUR).
    from ofis import izin as izin_mod
    iz = izin_mod.eslesen(ofis.db, oturum.proje_id, gorev_id, bulgu)
    if iz:
        izin_mod.gecti_kaydi(ofis.db, oturum.proje_id, izin=iz, bulgu=bulgu,
                             ajan_ad=oturum.ajan_ad, gorev_id=gorev_id)
        return None

    im = postane.imza(bulgu)
    for kayit in postane.onay_ara(oturum.ajan_ad, im,
                                  gorev_no=oturum.gorev_no):
        if kayit["durum"] == "reddedildi":
            return (
                "REDDEDILDI. Patron bu eylemi onaylamadi.\n"
                f"Eylem  : {bulgu['eylem']}\n"
                f"Gerekce: {kayit['cevap_notu'] or '(yazilmamis)'}\n\n"
                "Bu yolu TEKRAR DENEME. Baska bir yol varsa onu dene, "
                "yoksa `soru_sor` ile lidere danis.")
        if kayit["durum"] == "onaylandi":
            # KAPSAM 'is' ise tuketilmez: insan bu gorev boyunca
            # acikca izin vermistir. Varsayilan 'eylem' ve o BIR KEZ
            # gecer -- yoksa tek bir "evet" surekli yetkiye donerdi.
            # 'proje' karti burada BIR KEZ gecer (eylem gibi); sonrasini
            # karttan yazilan DAR kalici izin tasir (`izin.eslesen`, tam
            # desen). Imza kabadir (`git push`): 'is' gibi davransaydi ayni
            # iste baska dala push da sorulmadan gecerdi (06.10 olculdu).
            if (kayit.get("kapsam") or "eylem") == "is":
                return None
            if not postane.onay_kullanildi_mi(kayit["id"]):
                postane.onay_kullan(kayit["id"], ajan_ad=oturum.ajan_ad,
                                    ne=f"{arac} | {bulgu['esles']}",
                                    gorev_id=gorev_id)
                return None
        if kayit["durum"] == "bekliyor":
            return (
                "ONAY ZATEN BEKLIYOR -- SIMDI DUR.\n"
                f"Eylem: {bulgu['eylem']}\n"
                f"Onay : {kayit['id']}\n\n"
                "Bu turda bu eylemi TEKRAR DENEME ve baska yoldan yapmaya "
                "calisma. Buraya kadar yaptiklarini `kanit_ekle` ile yaz, "
                "sonra turu bitir. " + _KART_ACILDI)

    ayrinti = (
        f"IMZA:{im}\n"
        f"arac  : {arac}\n"
        f"isaret: {bulgu['esles']!r}\n"
        f"girdi : {str(girdi)[:400]}\n"
        # "Bu projede hep" dugmesinin okudugu satirlar (izin.karttan_izin).
        + izin_mod.kart_ayrintisi(arac, girdi, bulgu)
        + f"{bulgu['sebep']}"
    )
    try:
        onay = postane.onay_iste(oturum.ajan_ad, bulgu["eylem"],
                                 ayrinti=ayrinti, risk=bulgu["risk"],
                                 gorev_no=oturum.gorev_no)
    except Exception as exc:
        return (f"RISKLI EYLEM ve onay kaydi yazilamadi ({exc}). "
                   "Eylem yapilmadi.")
    ofis.db.olay_yaz(oturum.proje_id, "arac_onay_bekliyor",
                     f"{bulgu['ad']} -- {arac}",
                     ajan_ad=oturum.ajan_ad, gorev_id=gorev_id)
    return (
        "ONAY ISTENDI -- SIMDI DUR.\n"
        f"Sinif : {bulgu['ad']}\n"
        f"Eylem : {bulgu['eylem']}\n"
        f"Onay  : {onay['id']}\n\n"
        f"{bulgu['sebep']}\n\n"
        "SIMDI NE YAP: bu eylemi TEKRAR DENEME ve baska bir yoldan "
        "yapmaya calisma. Buraya kadar yaptiklarini `kanit_ekle` ile "
        "deftere yaz, sonra turu bitir. Patron onaylayinca is kaldigi "
        "yerden devam eder. " + _KART_ACILDI)


# ---------------------------------------------------------------------------
# MASAUSTU (D1, 08.10.2026) -- `ofis/masaustu.py`. Kapi BURADA sorulur:
# ofis araclari CLI kancasindan serbest gecer; karar `_kapi_karari`nda
# (izin_sor ile ayni yer).

import time  # noqa: E402 -- masaustu araclari

#: Son ekran goruntusu (bu MCP sureci = bu ajanin CLI oturumu).
_MASAUSTU = {"goruntu": None, "sayac": 0}
#: Goruntu bundan eskiyse koordinatli eylem yapilmaz (ekran degismis olabilir).
MASAUSTU_GORUNTU_OMRU_SN = 120
_MASAUSTU_GORUNTU_SAKLA = 12


def _masaustu_klasoru(oturum: Oturum):
    from pathlib import Path as _P
    from ofis.yollar import KARALAMA as _KARALAMA
    if oturum.gorev_no is not None:
        kok = _P(oturum.ofis.isin_koku(oturum.gorev()))
    else:
        kok = _P(oturum.ofis.kok_klasoru(getattr(oturum, "kanat", "") or None))
    k = (kok / _KARALAMA / "masaustu").resolve()
    k.mkdir(parents=True, exist_ok=True)
    return kok.resolve(), k


def _masaustu_goruntu(oturum: Oturum):
    """Ekran goruntusu al, eskileri sil (son 12 kalir)."""
    from ofis import masaustu as _m
    kok, k = _masaustu_klasoru(oturum)
    _MASAUSTU["sayac"] += 1
    ad = f"ekran-{(oturum.ajan_ad or 'ajan')}-{int(time.time())}-{_MASAUSTU['sayac']}.png"
    g = _m.goruntu_al(k / ad)
    _MASAUSTU["goruntu"] = g
    eskiler = sorted(k.glob(f"ekran-{oturum.ajan_ad or 'ajan'}-*.png"),
                     key=lambda f: f.stat().st_mtime)
    for f in eskiler[:-_MASAUSTU_GORUNTU_SAKLA]:
        try:
            f.unlink()
        except OSError:
            pass
    return g, kok


def _masaustu_kapisi(oturum: Oturum, eylem: str, girdi: dict, **ayrinti) -> str | None:
    """None = gecer; metin = durma sebebi (HATA ile baslar)."""
    from ofis import riskli
    try:
        bulgu = riskli.masaustu_degerlendir(eylem, **ayrinti)
    except Exception as exc:                 # noqa: BLE001 -- kapi KAPALI kalir
        return f"HATA: ofis kapisi degerlendiremedi ({exc}); eylem YAPILMADI."
    if bulgu.get("ret"):
        return "HATA: " + bulgu["sebep"]
    m = _kapi_karari(oturum, "masaustu_" + eylem, girdi, bulgu)
    return None if m is None else "HATA: " + m


def _masaustu_olay(oturum: Oturum, metin: str) -> None:
    try:
        gid = oturum.gorev()["id"] if oturum.gorev_no is not None else None
        oturum.ofis.db.olay_yaz(oturum.proje_id, "masaustu", metin[:400],
                                ajan_ad=oturum.ajan_ad, gorev_id=gid)
    except Exception:                        # noqa: BLE001 -- kayit eylemi dusurmez
        pass


def _masaustu_ozeti(g, *, pencere_adi: str = "", ogeler: bool = True) -> str:
    from ofis import masaustu as _m
    satirlar = [f"EKRAN GORUNTUSU: {g.genislik}x{g.yukseklik} piksel (koordinatlari BU "
                "goruntunun pikseliyle ver)."]
    try:
        pler = _m.pencereler(25)
    except Exception:                        # noqa: BLE001
        pler = []
    hedef = None
    if pencere_adi:
        hedef = next((p for p in pler if pencere_adi.lower() in p["baslik"].lower()
                      or pencere_adi.lower() in p["uygulama"].lower()), None)
    if hedef is None:
        hedef = next((p for p in pler if p["onde"]), None)
    if pler:
        satirlar.append("PENCERELER (onde olan *):")
        for p in pler[:15]:
            sol, ust = g.goruntuye(p["kutu"][0], p["kutu"][1])
            sag, alt = g.goruntuye(p["kutu"][2], p["kutu"][3])
            satirlar.append(f"  {'*' if p['onde'] else ' '} {p['baslik'][:70]} "
                            f"[{p['uygulama']}]{' (simge)' if p['simge'] else ''} "
                            f"kutu=({sol},{ust})-({sag},{alt})")
    if ogeler and hedef and not hedef.get("simge"):
        try:
            liste = _m.ogeler(hedef["hwnd"], 120)
        except Exception:                    # noqa: BLE001
            liste = []
        if liste:
            satirlar.append(f"OGELER ({hedef['baslik'][:50]}; ad, tur, merkez):")
            for o in liste[:120]:
                k = o.get("kutu") or [0, 0, 0, 0]
                x, y = g.goruntuye((k[0] + k[2]) / 2, (k[1] + k[3]) / 2)
                if not (0 <= x <= g.genislik and 0 <= y <= g.yukseklik):
                    continue
                satirlar.append(f"  {o.get('tur')}: {_m.oge_etiketi(o)[:60]!r} @({x},{y})"
                                + ("" if o.get("etkin", True) else " (pasif)")
                                + (" [sifre]" if o.get("sifre") else ""))
    return "\n".join(satirlar)


def arac_masaustu_bak(oturum: Oturum, args: dict):
    """Ekranin goruntusu + pencereler + one cikan pencerenin ogeleri."""
    from ofis import masaustu as _m
    girdi = {k: v for k, v in (args or {}).items()}
    dur = _masaustu_kapisi(oturum, "bak", girdi)
    if dur:
        return dur
    try:
        g, kok = _masaustu_goruntu(oturum)
        ozet = _masaustu_ozeti(g, pencere_adi=str(args.get("pencere") or ""),
                               ogeler=args.get("ogeler", True) is not False)
    except _m.MasaustuHatasi as exc:
        return f"HATA: {exc}"
    _masaustu_olay(oturum, f"bak: {_goreli(g.yol, kok)}")
    return {"metin": ozet + f"\nGORUNTU: {_goreli(g.yol, kok)}", "gorseller": [g.yol]}


def arac_masaustu_eylem(oturum: Oturum, args: dict):
    """Fare/klavye/pencere/uygulama eylemi; ardindan (varsayilan) yeni goruntu."""
    from ofis import masaustu as _m
    a = dict(args or {})
    eylem = str(a.get("eylem") or "").strip()
    if eylem not in ("tikla", "cift_tikla", "sag_tikla", "surukle", "kaydir", "yaz", "tus",
                     "pencere", "uygulama_ac", "bekle"):
        return ("HATA: eylem su degerlerden biri olmali: tikla, cift_tikla, sag_tikla, "
                "surukle, kaydir, yaz, tus, pencere, uygulama_ac, bekle.")
    g = _MASAUSTU.get("goruntu")
    koordinatli = eylem in ("tikla", "cift_tikla", "sag_tikla", "surukle", "kaydir")
    try:
        ex = ey = None
        oge, pencere = {}, {}
        if koordinatli:
            if g is None:
                return "HATA: once `masaustu_bak` ile ekrana bak; koordinatlar o goruntunun pikseliyle verilir."
            if time.time() - g.zaman > MASAUSTU_GORUNTU_OMRU_SN:
                return ("HATA: son ekran goruntusu eski (ekran degismis olabilir). Once "
                        "`masaustu_bak`, sonra yeni koordinatla dene.")
            if a.get("x") is None or a.get("y") is None:
                return "HATA: x ve y gerekli (son goruntunun pikseli)."
            ex, ey = g.ekrana(a["x"], a["y"])
            if eylem != "kaydir":
                # OKUNAMAYAN OGE (09.10 canli olculdu): ad yoksa kapi riskli dugmeyi
                # goremez -> 'okunamadi' isaretiyle SORULUR (kapali kalir).
                oge = _m.oge_noktada(ex, ey) or {"okunamadi": True, "hata": _m.SON_HATA[0][:200]}
            pencere = _m.on_pencere() or {}
        elif eylem in ("yaz", "tus"):
            oge = _m.odak_ogesi() or {"okunamadi": True, "hata": _m.SON_HATA[0][:200]}
            pencere = _m.on_pencere() or {}
        elif eylem == "pencere":
            pencere = _m.pencere_bul(str(a.get("pencere") or "")) or {}
            if not pencere:
                return f"HATA: {a.get('pencere')!r} adli pencere yok. `masaustu_bak` pencereleri listeler."
        dur = _masaustu_kapisi(oturum, eylem if eylem != "bekle" else "bak", a, oge=oge,
                               pencere=pencere, metin=str(a.get("metin") or ""),
                               tuslar=str(a.get("tuslar") or ""),
                               uygulama=str(a.get("uygulama") or ""))
        if dur:
            return dur
        if eylem != "bekle":
            _surucu = _m.kira_al(f"{oturum.ajan_ad} (#{oturum.gorev_no})")
            if _surucu:
                return (f"HATA: MASAUSTUNU SU AN {_surucu} KULLANIYOR (tek masaustu, tek "
                        "surucu). Eylem YAPILMADI. Bitmesini bekle (`masaustu_eylem` "
                        "eylem=bekle) ya da `soru_sor` ile lidere danis.")
        if eylem != "bekle" and _m.patron_etkin_mi():
            return ("HATA: PATRON SU AN BILGISAYARI KULLANIYOR (ofisin son eyleminden sonra "
                    "klavye/fare hareketi var). Eylem YAPILMADI. Biraz bekleyip `masaustu_bak` "
                    "ile yeniden bak; uzun surerse `soru_sor` ile patrona sor.")
        if eylem in ("tikla", "cift_tikla", "sag_tikla"):
            _m.tikla(ex, ey, dugme="sag" if eylem == "sag_tikla" else "sol",
                     kez=2 if eylem == "cift_tikla" else 1)
            yapilan = f"{eylem} ({a['x']},{a['y']}) -> {oge.get('ad') or 'adsiz'} ({oge.get('tur') or '?'})"
        elif eylem == "surukle":
            if a.get("x2") is None or a.get("y2") is None:
                return "HATA: surukle icin x2 ve y2 gerekli."
            ex2, ey2 = g.ekrana(a["x2"], a["y2"])
            _m.surukle(ex, ey, ex2, ey2)
            yapilan = f"surukle ({a['x']},{a['y']}) -> ({a['x2']},{a['y2']})"
        elif eylem == "kaydir":
            adim = int(a.get("adim") or -3)
            _m.kaydir(ex, ey, adim)
            yapilan = f"kaydir {adim} @({a['x']},{a['y']})"
        elif eylem == "yaz":
            metin = str(a.get("metin") or "")
            if not metin:
                return "HATA: metin gerekli."
            _m.yaz(metin)
            yapilan = (f"yaz {len(metin)} harf -> {oge.get('ad') or 'odaktaki alan'}"
                       + ("" if oge.get("sifre") else f": {metin[:80]!r}"))
        elif eylem == "tus":
            _m.tus(str(a.get("tuslar") or ""))
            yapilan = f"tus {a.get('tuslar')} -> {oge.get('ad') or 'odaktaki oge'}"
        elif eylem == "pencere":
            onde = _m.pencere_one(pencere["hwnd"])
            yapilan = f"pencere one: {pencere['baslik'][:60]}" + ("" if onde else " (Windows one almadi)")
        elif eylem == "uygulama_ac":
            pid = _m.uygulama_ac(str(a.get("uygulama") or ""),
                                 [str(x) for x in (a.get("argumanlar") or [])])
            time.sleep(min(10.0, float(a.get("bekle_sn") or 2.5)))
            yapilan = f"uygulama acildi: {a.get('uygulama')} (surec {pid or '?'})"
        else:
            time.sleep(max(0.5, min(30.0, float(a.get("sn") or 2))))
            yapilan = f"bekle {a.get('sn') or 2} sn"
    except _m.MasaustuHatasi as exc:
        return f"HATA: {exc}"
    _masaustu_olay(oturum, yapilan)
    if a.get("bak", True) is False:
        return f"YAPILDI: {yapilan}"
    time.sleep(0.6)
    try:
        g2, kok = _masaustu_goruntu(oturum)
        ozet = _masaustu_ozeti(g2, ogeler=a.get("ogeler", True) is not False)
    except _m.MasaustuHatasi as exc:
        return f"YAPILDI: {yapilan}\n(yeni goruntu alinamadi: {exc})"
    return {"metin": f"YAPILDI: {yapilan}\n\nSONRAKI EKRAN:\n{ozet}\nGORUNTU: {_goreli(g2.yol, kok)}",
            "gorseller": [g2.yol]}


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
        "name": "belge_ara",
        "description": (
            "Patronun yukledigi belgelerde (PDF, Word, Excel, metin) arama "
            "yapar; en ilgili parcalari KAYNAGIYLA (belge adi + sayfa/bolum/"
            "satir) dondurur. Belgeden bir sey soyluyorsan kaynagi yaz; "
            "belgede yoksa uydurma."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sorgu": {"type": "string",
                          "description": "Aranan sey, birkac kelime (orn. 'iade suresi kargo ucreti')."},
                "azami": {"type": "integer", "description": "En fazla kac parca (1-10, varsayilan 5)."},
            },
            "required": ["sorgu"],
        },
        "islev": arac_belge_ara,
    },
    {
        "name": "beceri_oner",
        "description": (
            "Tekrar eden, ise yaramis bir yordami BECERI TASLAGI olarak onerir. "
            "Patron onaylarsa butun ajanlar kullanir. KANIT zorunlu: yordamin "
            "ise yaradigi kapanmis islerin numaralari. Tek seferlik isi beceri yapma."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ad": {"type": "string", "description": "kucuk-harf-tireli ad, orn. 'urun-aciklamasi-yaz'"},
                "aciklama": {"type": "string", "description": "Ne ZAMAN kullanilir, tek cumle."},
                "yordam": {"type": "string", "description": "Adim adim yordam (markdown)."},
                "kanit_isleri": {"type": "array", "items": {"type": "integer"},
                                 "description": "Ise yaradigi KAPANMIS islerin numaralari."},
                "gerekce": {"type": "string", "description": "Neden beceri olmali."},
            },
            "required": ["ad", "aciklama", "yordam", "kanit_isleri"],
        },
        "islev": arac_beceri_oner,
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
        "name": "sohbete_yaz",
        "description": (
            "Patronun sohbetine KISA bir bildirim yazar -- YALNIZ patronun "
            "gormesi gereken bir dosya ya da seni durduran bir engel icin. "
            "'Is bitti' / ara durum YAZMA (lider rapor eder). DOSYA "
            "gonderir (gorsel, pdf, video, "
            "belge): `ekler` alanina proje kokune gore yollarini yaz; "
            "patron sohbette gorur. Sohbet OFIS ICIDIR (patronun paneli): "
            "disari cikmaz, ONAY GEREKMEZ -- `onay_iste` cagirma. "
            "Cevap beklenmez, kimseye is vermez; is "
            "basina en fazla 6 kez. Soru icin `soru_sor`, onay icin "
            "`onay_iste` kullan."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "metin": {"type": "string",
                          "description": "Takimin gorecegi 1-3 cumle."},
                "ekler": {"type": "array", "items": {"type": "string"},
                          "description": "Sohbete eklenecek dosyalar (proje "
                                         "kokune gore yol, en fazla 5). "
                                         "Orn. [\".ofis/ekler/ekran.png\", \"rapor.pdf\"]"},
            },
            "required": ["metin"],
        },
        "islev": arac_sohbete_yaz,
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
                "secenekler": {"type": "array", "items": {"type": "string"},
                               "description": ("Istege bagli: cevap birkac secenekten biriyse "
                                               "2-6 kisa secenek. Patron tek tikla secer.")},
                "onerilen": {"type": "string",
                             "description": ("Istege bagli: senin onerdigin secenegin AYNI "
                                             "metni. Patron onerilenleri topluca kabul edebilir.")},
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
                "kredi": {"type": "integer",
                          "description": "KREDI PAKETI (Flow vb.): paketin TOPLAM kredisi."},
                "uretim": {"type": "integer",
                           "description": "KREDI PAKETI: kredili uretim tiklamasi sayisi "
                                          "(yeniden cekim payi dahil). Onaylanirsa bu kadar "
                                          "uretim kapida tekrar sorulmaz."},
            },
            "required": ["eylem"],
        },
        "islev": arac_onay_iste,
    },
    {
        "name": "giris_iste",
        "description": (
            "Bir siteye, hesaba ya da baglayiciya GIRIS (oturum acma, "
            "uyelik, dogrulama kodu, 2FA) gerekiyorsa bunu cagir ve DUR. "
            "Patron kendisi girer; sen sifre ISTEME, YAZMA, TAHMIN ETME, "
            "baska yerden bulmaya calisma. Tur: 'web' (bir sitenin girisi; "
            "adres ver -- patron paylasilan tarayicida girer, sonra sen "
            "onun oturumuyla devam edersin), 'baglayici' (claude.ai "
            "baglayicisi, hizmet = baglayici adi), 'diger'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tur": {"type": "string", "description": "web | baglayici | diger"},
                "hizmet": {"type": "string",
                           "description": "Hangi hizmet/hesap (orn. 'Shopify yonetim')."},
                "adres": {"type": "string",
                          "description": "web icin giris sayfasinin adresi."},
                "neden": {"type": "string",
                          "description": "Bu is icin neden giris gerektigi."},
            },
            "required": ["hizmet", "neden"],
        },
        "islev": arac_giris_iste,
    },
    {
        "name": "video_kurgula",
        "description": (
            "Flow kliplerinden / gorsellerden PAYLASMAYA HAZIR video yapar (Instagram "
            "Reels/hikaye 9:16, gonderi 4:5 ya da 1:1, 16:9): sahneler, ekran yazisi, "
            "altyazi, solma gecisi, muzik, kapanis karti. Sen yalniz PLANI yazarsin; ofis "
            "cizer, OLCER (boyut, sure, ses, siyah ekran), kapak ve kare ozeti cikarir, "
            "kaniti otomatik yazar. Dosyalar isin klasorunde olmali (orn. Flow'dan "
            "indirdigin `.ofis/ekler/klip1.mp4`). Plan ornegi: {\"bicim\":\"9:16\","
            "\"sahneler\":[{\"tur\":\"video\",\"dosya\":\".ofis/ekler/klip1.mp4\","
            "\"sure\":4,\"yazi\":\"Yeni sezon\",\"yazi_konum\":\"ust\"},{\"tur\":"
            "\"gorsel\",\"dosya\":\"urun.jpg\",\"sure\":3,\"hareket\":\"yakinlas\"}],"
            "\"gecis\":\"solma\",\"muzik\":\".ofis/ekler/muzik.mp3\",\"altyazi\":[{\"bas\":0,"
            "\"son\":2,\"metin\":\"...\"}],\"son_kart\":{\"metin\":\"Marka\",\"alt_metin\":"
            "\"site.com\",\"sure\":2}}. Sahne turleri: video (kirp_bas: bastan atlanacak sn, "
            "ses: klibin kendi sesi, hiz: 0.25-4 -- 0.5 agir cekim), gorsel (hareket: "
            "yakinlas|uzaklas|yok), renk (renk: #hex). Her sahnede: yerlesim kapla|bulanik|sigdir "
            "(yatay klip dikey videoda: 'bulanik' -- kirpmadan, arkasi bulanik dolgu), odak "
            "orta|sol|sag|ust|alt ya da '30% 50%' (kapla'da kirpma merkezi), filtre yok|sicak|soguk|"
            "siyah_beyaz|canli|sinematik. Plan: gecis solma|kesme|kayma|silme|yukari; muzik_bas "
            "(muzigin kacinci sn'sinden), muzik_ses/klip_ses 0-2; sesler: [{dosya, bas, ses, "
            "kirp_bas}] seslendirme/efekt izleri (calarken muzik muzik_alcalt carpanina iner, "
            "varsayilan 0.3); logo: {dosya, konum sag_ust|sol_ust|sag_alt|sol_alt|orta_ust|orta_alt, "
            "boyut 0.05-0.5, saydamlik}. Hazir videoyu duzenlerken once medya_isle 'sahneler' ile anla."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "plan": {"type": "object", "description": "Kurgu plani (yukaridaki bicim)."},
                "ad": {"type": "string", "description": "Cikti adi, orn. 'belle-reels-15sn'."},
            },
            "required": ["plan"],
        },
        "islev": arac_video_kurgula,
    },
    {
        "name": "video_denetle",
        "description": (
            "Bir videoyu (orn. Flow'dan indirdigin) OLCER: boyut/oran, sure, kare hizi, "
            "kodlayici, ses var mi, siyah ekran, sessizlik; kare ozeti ve kapak cikarir; "
            "olcum kanit olarak yazilir. Paylasmaya hazir mi diye `bicim` ver (9:16, 4:5, 1:1, 16:9)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dosya": {"type": "string", "description": "Isin klasorune gore yol."},
                "bicim": {"type": "string", "description": "Beklenen oran (bos = oran denetlenmez)."},
            },
            "required": ["dosya"],
        },
        "islev": arac_video_denetle,
    },
    {
        "name": "masaustu_bak",
        "description": (
            "BILGISAYARIN EKRANINA BAK (masaustu uygulamalari icin; web sitesi icin gomulu "
            "tarayiciyi kullan). Ekran goruntusu (gorsel olarak doner) + acik pencereler + "
            "ondeki pencerenin ogeleri (ad, tur, merkez koordinati). Koordinatlar BU "
            "goruntunun pikseliyle. Patronun masaustu oldugu icin ILK kullanimda patrona "
            "sorulur ('bu is boyunca' onayi isi acar). `pencere`: ogeleri listelenecek "
            "pencerenin adindan bir parca; `ogeler`: false = liste yok (hizli)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pencere": {"type": "string"},
                "ogeler": {"type": "boolean"},
            },
        },
        "islev": arac_masaustu_bak,
    },
    {
        "name": "masaustu_eylem",
        "description": (
            "MASAUSTUNDE FARE / KLAVYE. eylem: 'tikla' | 'cift_tikla' | 'sag_tikla' (x,y) · "
            "'surukle' (x,y -> x2,y2) · 'kaydir' (x,y, adim: + yukari / - asagi) · 'yaz' "
            "(metin; odaktaki alana; Turkce harf olur; satir sonu = Enter) · 'tus' (tuslar: "
            "'ctrl+s', 'enter', 'alt+tab', 'f5') · 'pencere' (pencere: adindan parca, one "
            "getirir) · 'uygulama_ac' (uygulama: 'notepad', 'excel' ya da tam yol; "
            "argumanlar) · 'bekle' (sn). x,y SON `masaustu_bak` goruntusunun pikseli (120 "
            "sn'den eski goruntuyle tiklanmaz). Eylemden sonra yeni ekran goruntusu doner "
            "(`bak`: false = donmez). Kapi: siradan eylem 'bu is boyunca' onayiyla acilir; "
            "gonder/sil/ode/satin al/yayinla gibi dugmeler ve sifre alani HER SEFERINDE "
            "sorulur; terminal penceresine komut yazilmaz (kendi kabugunu kullan). Patron "
            "klavye/fareyi kullaniyorsa eylem yapilmaz."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "eylem": {"type": "string"},
                "x": {"type": "number"}, "y": {"type": "number"},
                "x2": {"type": "number"}, "y2": {"type": "number"},
                "adim": {"type": "integer"},
                "metin": {"type": "string"},
                "tuslar": {"type": "string"},
                "pencere": {"type": "string"},
                "uygulama": {"type": "string"},
                "argumanlar": {"type": "array", "items": {"type": "string"}},
                "bekle_sn": {"type": "number"},
                "sn": {"type": "number"},
                "bak": {"type": "boolean"},
                "ogeler": {"type": "boolean"},
            },
            "required": ["eylem"],
        },
        "islev": arac_masaustu_eylem,
    },
    {
        "name": "medya_isle",
        "description": (
            "YEREL medya araclari -- kredi/para HARCAMAZ, cikti olculur, kanit otomatik. "
            "islem: 'gorsel_buyut' (gorseli yapay zekayla buyutur, Real-ESRGAN; `olcek` 2-4 "
            "ya da `en` piksel; ~1 dk. VIDEO buyutmez), 'altyazi' (video/sesten Turkce "
            "altyazi, Whisper; `replik` verirsen yazim replikten zaman sesten -- marka adi "
            "dogru cikar -- ve ses repligi yanlis soyluyorsa UYARIR; cikti video_kurgula'nin "
            "\"altyazi\" bicimi + .srt; ~15 sn/8 sn klip), 'arka_plan' (gorselin arka "
            "planini siler, saydam PNG; `model` birefnet-general-lite ince kenar ~20 sn / "
            "isnet-general-use hizli). VIDEO DUZENLEME (hazir video / Flow klibi): 'sahneler' "
            "(kesme noktalari + zaman damgali KARE PANOSU -- videoyu once bununla ANLA; `esik` "
            "0.05-0.9), 'kes' (`bas`-`son` sn araligini yeni dosyaya), 'ses_ayir' (sesi .m4a/.wav), "
            "'sessizlik_kes' (konusmali videoda sessiz bosluklari atar; `esik_db` -35, `en_az` 0.6 sn), "
            "'kare_ara' (yapay zekayla ARA KARE, RIFE: `carpan` 2|4 -- 24 kare/sn Flow klibini 48/96'ya "
            "cikarir, sure ayni; AGIR CEKIMDEN ONCE yap, yoksa goruntu takilir; 8 sn 1080p ~2 dk), "
            "'vokal_ayir' (yapay zekayla KONUSMA/SARKI ile MUZIGI ayirir -- hazir videonun muzigini "
            "degistirmek ya da konusmayi temizlemek icin; ~2,5 x ses suresi). "
            "Birlestirme/hiz/yazi/muzik/seslendirme/logo: video_kurgula. "
            "Dosyalar isin klasorunde; cikti varsayilan `.ofis/ekler/`."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "islem": {"type": "string", "description": "gorsel_buyut | altyazi | arka_plan | "
                                                            "sahneler | kes | ses_ayir | sessizlik_kes | kare_ara | "
                                                            "vokal_ayir"},
                "dosya": {"type": "string", "description": "Isin klasorune gore girdi yolu."},
                "cikti": {"type": "string", "description": "Istege bagli cikti yolu."},
                "replik": {"type": "string", "description": "altyazi: klipte soylenmesi gereken metin."},
                "olcek": {"type": "integer", "description": "gorsel_buyut: 2, 3 ya da 4 (varsayilan 2)."},
                "en": {"type": "integer", "description": "gorsel_buyut: hedef genislik (piksel)."},
                "model": {"type": "string", "description": "arka_plan modeli."},
                "bas": {"type": "number", "description": "kes: baslangic (sn)."},
                "son": {"type": "number", "description": "kes: bitis (sn)."},
                "esik": {"type": "number", "description": "sahneler: kesim hassasiyeti (0.3)."},
                "esik_db": {"type": "number", "description": "sessizlik_kes: sessizlik esigi (dB, -35)."},
                "en_az": {"type": "number", "description": "sessizlik_kes: en kisa sessizlik (sn, 0.6)."},
                "carpan": {"type": "integer", "description": "kare_ara: 2 ya da 4."},
            },
            "required": ["islem", "dosya"],
        },
        "islev": arac_medya_isle,
    },
    {
        "name": "gorsel_uret",
        "description": (
            "Bir ISTEMDEN gorsel uretir, dosyayi yazma alanina yazar ve "
            "KANIT olarak tahtaya gecirir. Istemi SEN yazarsin -- iyi bir "
            "istem isin yarisidir: konu, bicem, renk, oran, ne OLMAYACAGI. "
            "Uretici otomatik secilir (once ucretsiz olan). Uretilen "
            "dosya icin ayrica `kanit_ekle` CAGIRMA, iki kez sayilir. "
            "GERCEK BIR URUNUN gorseliyse urunun fotograflarini `referanslar`a "
            "VER: uretici urunu, etiketi ve yazilarini fotograftan birebir alir "
            "(referanssiz uretim urunu UYDURUR). Etiketteki yazilari, hacmi "
            "(orn. '50 ml · 1.7 FL.OZ') istemde de aynen yaz."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "istem": {"type": "string",
                          "description": "Gorselin tam tarifi. Turkce ya da Ingilizce."},
                "dosya_adi": {"type": "string",
                              "description": "Orn. 'kreatif-1.png'. Yalniz dosya adi, yol degil."},
                "uretici": {"type": "string",
                            "description": "'codex' (GPT, abonelik) ya da 'gemini' (Nano "
                                           "Banana, ucretsiz kota). BOS: once codex, sonra "
                                           "gemini. Ikisi de referans fotograf alir. Secilen "
                                           "olmazsa ofis otomatik siraya doner."},
                "oran": {"type": "string",
                         "description": "Cikti orani: 9:16 (hikaye/reels), 4:5 (gonderi), 1:1, "
                                        "16:9 ... Gemini bunu tam uygular; GPT yakin bir dikey/"
                                        "yatay uretir (gerekirse kirp)."},
                "model": {"type": "string", "description": "Bos birak (varsayilan)."},
                "referanslar": {"type": "array", "items": {"type": "string"},
                                "description": "Gercek urunun fotograflari (kok icinde yol, "
                                               "orn. '.ofis/ekler/sise.png'); en cok 8. "
                                               "Arka plani temizlenmis fotograf en iyisi."},
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
        gorseller = []
        if isinstance(metin, dict):
            # GORSEL DONDUREN ARAC (08.10.2026, masaustu): ekran goruntusu
            # modele dogrudan gider (MCP `image` icerigi); yol metinde de var.
            gorseller = list(metin.get("gorseller") or [])
            metin = str(metin.get("metin") or "")
        hatali = isinstance(metin, str) and metin.startswith("HATA")
        icerik = [{"type": "text", "text": metin}]
        for _g in gorseller:
            try:
                import base64 as _b64
                icerik.append({"type": "image", "mimeType": "image/png",
                               "data": _b64.b64encode(open(_g, "rb").read()).decode("ascii")})
            except OSError:
                pass
        return _sonuc(istek_id, {
            "content": icerik,
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
    # EVIN YOLU DA SUREC SINIRINI GECER (02.10.2026, olculdu): iki motor da
    # MCP sunucusunu YALNIZ burada yazan ortamla baslatiyor. Gecici evle
    # (sinama paneli, olcum betigi) kosan ofisin MCP sunucusu GERCEK eve
    # dusuyordu -- ajanin beceri taslagi gercek depoya yazildi. Hayalet
    # veritabani dersinin aynisi: surec sinirini gecen her yol acikca verilir.
    for _ad in ("OFIS_EV", "OFIS_BECERI_KOK", "OFIS_GIZLI_YOLU", "OFIS_GOLGE_KOK",
                "OFIS_KABIN_KAPI", "OFIS_KABIN_PROFIL"):
        if os.environ.get(_ad):
            ortam[_ad] = os.environ[_ad]
    sunucular = {
        SUNUCU_ADI: {
            "command": sys.executable,
            "args": [str(Path(__file__).resolve())],
            "env": ortam,
            # OFISIN ARACLARI HEP HAZIR (02.10.2026, olculdu): ertelenmis
            # yuklemede kanit_ekle bile once ToolSearch ile aranmisti (fazladan
            # adim). Claude Code: `alwaysLoad: true` sunucunun araclarini
            # ertelemez; hesabin baglayicilari ertelenmis kalir.
            "alwaysLoad": True,
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
