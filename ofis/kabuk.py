# -*- coding: utf-8 -*-
"""Kabuk: ofisi komut satirindan kullanmak.

Panelden once bu gelir. Sebebi: arayuz GERCEK KULLANIMDAN dogmali.
Kullanilmamis bir ofis icin panel tasarlamak, neye ihtiyac duyulacagini
tahmin etmektir -- ve tahmin, bu projede iki kez iskaladi.

Kabuk ayrica panelin yapamadigi seyi yapar: ofisi KURAR. Panel bir
gostergedir, kurulum araci degil.

Komutlar:

    kur        yeni ofis ac
    ise-al     ajan ise al
    hedef      HEDEF ver -- halka doner, bitene ya da sana ihtiyac
               duyulana kadar
    durum      ofisin su anki hali
    bekleyen   senden bekleneni goster
    cevapla    bekleyen soruyu cevapla
    onayla     bekleyen onayi ver ya da reddet
    panel      paneli ac

Ornek:

    python -m ofis.kabuk kur --ad "Projem" --amac "..." --olcut "..."
    python -m ofis.kabuk ise-al demir lider --lider
    python -m ofis.kabuk ise-al cinar backend
    python -m ofis.kabuk hedef "Siparis toplami dogru hesaplansin"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani            # noqa: E402
from ofis.db import VARSAYILAN_YOL           # noqa: E402
from ofis.kadro import KadroHatasi           # noqa: E402
from ofis.orkestra import OrkestraHatasi     # noqa: E402
from ofis.postane import PostaneHatasi       # noqa: E402
from ofis.sohbet import SohbetHatasi         # noqa: E402
from ofis import gizli                       # noqa: E402
from ofis.tahta import medya_hedefi, TahtaHatasi  # noqa: E402
from ofis.gizli import GizliHatasi           # noqa: E402
from ofis.roller import RolHatasi            # noqa: E402
from ofis.ekip import EkipHatasi             # noqa: E402
from ofis.koltuk import (durdurma_iste,       # noqa: E402
                         durdurma_temizle)
from ofis.klasor import (                    # noqa: E402
    KlasorHatasi, klasorleri_dogrula, metinler)

# Windows konsolu cp1254; Turkce karakterler ve tire isaretleri `print`te
# patlar. Cikti akisini utf-8'e cevirmek, her satirda ASCII'ye inmekten
# iyidir -- kabuk INSANA konusur, insana Turkce konusulur.
for akis in (sys.stdout, sys.stderr):
    try:
        akis.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def yaz(*parcalar) -> None:
    print(*parcalar)


def ofis_yetenek(ofis, **kw):
    from .yetenek import tara
    return tara(ofis, **kw)


def ofis_ac(db_yolu, proje_ad: str = None) -> Ofis:
    # Gizli depo OFIS surecinin ortamina yuklenir. Ajan turuna
    # gecmesi AYRI bir karardir: `tip.ortam_hazirla` yalnizca acikca
    # izin verilen anahtari gecirir, gerisini dusurur.
    gizli.yukle()
    db = Veritabani(db_yolu or VARSAYILAN_YOL)
    with db.baglanti() as conn:
        if proje_ad:
            row = conn.execute("SELECT id FROM proje WHERE ad = ?",
                               (proje_ad,)).fetchone()
        else:
            row = conn.execute("SELECT id FROM proje WHERE durum = 'acik' "
                               "ORDER BY olusturuldu LIMIT 1").fetchone()
    if not row:
        raise SystemExit(
            "Bu veritabaninda acik proje yok.\n"
            "Once kur:  python -m ofis.kabuk kur --ad \"Projem\" "
            "--amac \"...\" --olcut \"...\"")
    return Ofis(db, row["id"])


# ---------------------------------------------------------------------------
# komutlar
# ---------------------------------------------------------------------------

def komut_kur(a) -> None:
    db = Veritabani(a.db or VARSAYILAN_YOL)
    ofis = Ofis.proje_ac(db, a.ad, amac=a.amac, basari_olcutu=a.olcut,
                         kapsam_disi=a.kapsam_disi, kisitlar=a.kisitlar,
                         kok_klasor=a.klasor or "")
    kanat = ofis.kanat_ac(a.kanat, a.kanat[:2].upper())
    yaz(f"Ofis kuruldu: {a.ad}")
    yaz(f"  kanat      : {a.kanat}")
    yaz(f"  veritabani : {db.yol}")
    yaz("")
    yaz("Simdi kadro kur:")
    yaz("  python -m ofis.kabuk ise-al demir lider --lider")
    yaz("  python -m ofis.kabuk ise-al cinar backend")


def komut_ise_al(a) -> None:
    ofis = ofis_ac(a.db, a.proje)
    kanatlar = {k["ad"]: k["id"] for k in _kanatlar(ofis)}
    kanat_id = kanatlar.get(a.kanat) if a.kanat else (
        list(kanatlar.values())[0] if kanatlar else None)
    # ORTAK KLASOR (karar: 18.09.2026). Butun 'eller' ajanlar projenin
    # kok klasorunde calisir; yazma alani artik MANTIKSAL ETIKET degil
    # GERCEK YOL. Sebep: yazma kilidi, cakisma fiziksel olarak mumkunse
    # anlamlidir. Herkes kendi kumunda oynarken kilit dekordur ve
    # mimarinin yarisi bosa calisir.
    #
    # Koruma uc katmanda: `--restricted` kokun disina cikartmaz, yazma
    # kilidi cakisani reddeder, kanit kapisi sonucu denetler.
    #
    # `--kendi-klasoru` ile ajan yine yalitilabilir -- disari acilmamasi
    # gereken bir is icin.
    kok = ofis.kok_klasoru(kanat_id)
    if a.klasor:
        klasor = a.klasor
    elif a.kendi_klasoru:
        klasor = str(Path(kok) / a.ad)
    else:
        klasor = kok
    Path(klasor).mkdir(parents=True, exist_ok=True)
    try:
        ajan = ofis.kadro.ise_al(
            a.ad, a.meslek, kanat_id=kanat_id, lider_mi=a.lider,
            tur=a.tur, motor=a.motor, model=a.model or "", efor=a.efor,
            klasor=klasor)
    except KadroHatasi as exc:
        raise SystemExit(f"Ise alinamadi: {exc}")
    # Meslegi zaten "lider" ise isareti tekrarlama: "(lider, lider, eller)".
    etiketler = [ajan["meslek"]]
    if ajan["lider_mi"] and ajan["meslek"] != "lider":
        etiketler.append("lider")
    etiketler.append(ajan["tur"])
    yaz(f"{ajan['ad']} ise alindi ({', '.join(etiketler)})")
    yaz(f"  motor  : {ajan['motor']}  model: {ajan['model'] or 'hesap varsayilani'}")
    yaz(f"  klasor : {ajan['klasor']}")


def komut_konus(a) -> None:
    """LIDERLE KONUS -- ofisin on kapisi.

    `hedef` her istegi ZORLA bir goreve cevirir; bu komut cevirmez.
    Karari lider verir: cevaplar, kendi yapar ya da dagitir. Basit bir
    soru icin butun makineyi calistirmak jetonu da zamani da bosa yakar.
    """
    ofis = ofis_ac(a.db, a.proje)
    # Insan yeni bir sey baslatiyor: eski durdurma istegi KALKAR.
    durdurma_temizle(ofis.db, ofis.proje_id)
    _guncelleme_bildir(ofis)
    # Klasor ACILDIGI YERDE dogrulanir ve GOSTERILIR. Sessizce kabul
    # edilen bir yol, ajan "bulamadim" diyene kadar dogru gorunur.
    try:
        ekler = metinler(klasorleri_dogrula(a.klasor))
    except KlasorHatasi as exc:
        raise SystemExit(f"Klasor acilamadi: {exc}")

    yaz(f"SEN: {a.mesaj}")
    for e in ekler:
        yaz(f"  + klasor acildi: {e}")
    yaz("")
    # TAKIM SOHBETI: `@ad` ile yazilan satir panelle AYNI yonlendiriciden
    # gecer (`takim.yonlendir`) -- iki yuzey iki ayri kural tasimasin.
    from . import takim as _takim
    try:
        yon = _takim.yonlendir(ofis, a.mesaj)
    except _takim.TakimHatasi as exc:
        raise SystemExit(str(exc))
    if yon["yol"] == "not":
        from .postane import PostaneHatasi
        try:
            ofis.postane.not_birak(yon["ajan"], yon["metin"],
                                   gorev_no=yon["gorev_no"])
        except PostaneHatasi as exc:
            raise SystemExit(str(exc))
        yaz(f"NOT -> {yon['ajan']} (#{yon['gorev_no']}): calisirken ulasir; "
            "ulasinca kayda gecer.")
        return
    if yon["yol"] == "soru":
        m = ofis.postane.soru_sor("insan", yon["ajan"], yon["metin"],
                                  mod="uyandiran")
        with ofis.db.baglanti() as conn:
            m = dict(conn.execute(
                "SELECT m.*, g.no AS gorev_no FROM mesaj m LEFT JOIN gorev g "
                "ON g.id = m.gorev_id WHERE m.id = ?", (m["id"],)).fetchone())
        sonuc = ofis.danisma.insana_cevapla(m, zaman_asimi=a.zaman_asimi)
        yaz(f"{yon['ajan'].upper()} (salt okunur cevap):")
        yaz(sonuc["cevap"])
        return
    if not (yon["lider"] or a.lider) and sum(
            1 for x in ofis.kadro.liste() if x["lider_mi"]) > 1:
        # GENEL KANAL: ofis secmez, ONERIR (model cagrilmaz).
        oneriler = _takim.takim_oner(ofis, yon["metin"])
        satir = [f"  @{o['ad']}  (lider {o['lider']}"
                 + (f", eslesen: {o['sebep']})" if o["puan"] else ")")
                 for o in oneriler]
        raise SystemExit("Ofiste birden cok takim var; mesaji hangi takima "
                         "gondereyim? Satirin basina takimi yaz:\n"
                         + "\n".join(satir))
    if yon["yol"] == "is":
        yaz(f"IS -> {yon['ajan']} (plani {yon['lider']} yazar: olcut, "
            "yazma alani, kanit)")
        yaz("")
    try:
        for olay in ofis.sohbet.konus(
                yon["metin"], lider_ad=(yon["lider"] or a.lider or ""),
                butce_usd=None,
                zaman_asimi=a.zaman_asimi, azami_tik=a.azami_tik,
                paralel=a.paralel, izinli_araclar=tuple(a.izin),
                ek_klasorler=ekler,
                atanan=(yon["ajan"] if yon["yol"] == "is" else "")):
            if olay["tur"] == "triyaj":
                # `.get` ile: bilinmeyen bir yol eklendiginde komut
                # KeyError ile PATLAMASIN. Dorduncu yol (`kadro`)
                # eklenirken bu sozluk guncellenmemisti ve tam bu
                # hatayi uretirdi -- sozlukten okunan her sey, sozlukte
                # olmayan bir deger gelebilecegini varsaymali.
                etiket = {
                    "cevap": "KENDI CEVAPLIYOR (ajan kosturulmuyor)",
                    "kendi": "KENDI YAPIYOR (incelemeyi SEN yapacaksin)",
                    "dagit": "KADROYA DAGITIYOR",
                    "kadro": "KADRO YETMIYOR -- oneri getiriyor",
                }.get(olay["govde"], olay["govde"])
                yaz(f"LIDER: {etiket}")
                yaz(f"  gerekce: {olay['ek']['gerekce']}")
                yaz("")
            elif olay["tur"] == "cevap":
                yaz("LIDER:")
                yaz(olay["govde"])
            elif olay["tur"] == "ekip_onerisi":
                # Onizlemenin butun degeri GORUNMESINDE. Basmasaydik
                # oneri sessizce diske yazilir, insan hicbir sey
                # gormezdi -- kurmadan once gosterme fikri bosa giderdi.
                yaz(olay["govde"])
            elif olay["tur"] == "plan":
                # BOLME KARARI VE GEREKCESI GOSTERILIR.
                #
                # OLCULDU (19.09.2026): hedefte patron acikca "bu is
                # BOLUNEBILIR ve bolunmeli" dedi; lider gerekceyle KARSI
                # CIKTI ("test koda siki bagli, bolmek arayuz tahmini
                # gerektirir") ve BOLMEDI. Karari dogruydu -- ama `konus`
                # yolu yalnizca gorev listesini basiyordu, gerekceyi
                # DEGIL. Patron liderin kendisiyle celistigini goremezdi.
                #
                # `hedef` komutu bunu zaten basiyordu: yine iki kopya,
                # biri duzeltilmis oteki unutulmus. Fan-out kapisinin
                # butun degeri gerekcenin GORUNMESINDE.
                yaz(f"  karar  : {'BOLDU' if olay['ek'].get('bol') else 'BOLMEDI'}"
                    f" ({len(olay['ek']['gorevler'])} is)")
                if olay["govde"]:
                    yaz(f"  gerekce: {olay['govde']}")
                yaz("")
                for g in olay["ek"]["gorevler"]:
                    yaz(f"  #{g['no']} {g['baslik']} -> "
                        f"{g['sahip'] or '(atanmadi)'}")
                yaz("")
                yaz("Halka donuyor...")
                yaz("")
            elif olay["tur"] == "tik":
                _tik_yaz(olay["ek"])
            elif olay["tur"] == "rapor":
                yaz("")
                yaz("=" * 60)
                yaz("LIDERIN RAPORU")
                yaz("=" * 60)
                yaz(olay["govde"])
    except (SohbetHatasi, OrkestraHatasi) as exc:
        # OrkestraHatasi da: iki liderli ofiste `konus` lider SECEMEZ ve
        # bunu soyler -- yakalanmadiginda insana yigin izi dusuyordu
        # (takim sohbeti mutasyonu gosterdi, 29.09.2026).
        raise SystemExit("Liderle konusulamadi: " + str(exc))
    yaz("")
    _durum_yaz(ofis)


def komut_hedef(a) -> None:
    ofis = ofis_ac(a.db, a.proje)
    durdurma_temizle(ofis.db, ofis.proje_id)
    _guncelleme_bildir(ofis)
    try:
        ekler = metinler(klasorleri_dogrula(a.klasor))
    except KlasorHatasi as exc:
        raise SystemExit(f"Klasor acilamadi: {exc}")

    yaz(f"HEDEF: {a.hedef}")
    for e in ekler:
        yaz(f"  + klasor acildi: {e}")
    yaz("")
    yaz("Lider planliyor...")
    try:
        plan = ofis.orkestra.hedef_ver(
            a.hedef, lider_ad=a.lider or "", butce_usd=None,
            zaman_asimi=a.zaman_asimi, ek_klasorler=ekler,
            tarayici_alani=a.web,
            tarayici_yazma=not bool(getattr(a, "web_salt_okur", False)),
            baglayicilar=a.baglayici,
            sartname_denetimi=a.sartname,
            patron_sozu=a.hedef)
    except OrkestraHatasi as exc:
        raise SystemExit(f"\nPlan alinamadi: {exc}")

    yaz(f"  karar  : {'BOLDU' if plan['bol'] else 'BOLMEDI'} "
        f"({len(plan['gorevler'])} is)")
    yaz(f"  gerekce: {plan['gerekce']}")
    if plan.get("izinler"):
        yaz(f"  sorulmadan gecer (senin sozun): {', '.join(plan['izinler'])}")
    yaz("")
    for g in plan["gorevler"]:
        alan = ", ".join(g["yazma_alani"]) or "dosya yazmiyor"
        yaz(f"  #{g['no']} {g['baslik']}  ->  {g['sahip'] or '(atanmadi)'}")
        yaz(f"       olcut: {g['kabul_olcutu']}")
        yaz(f"       alan : {alan}")
    yaz("")
    if a.sadece_plan:
        yaz("(--sadece-plan verildi, is baslatilmadi)")
        return

    yaz("Halka donuyor...")
    yaz("")
    _dongu_yaz(ofis, a)
    yaz("")
    _durum_yaz(ofis)


def komut_devam(a) -> None:
    """Halkayi kaldigi yerden dondurur -- yeni hedef VERMEDEN.

    Soru cevaplandiktan ya da onay verildikten sonra gereken sey budur.
    Yeni hedef vermek, bekleyen isin ustune ikinci bir is yigmak olurdu.
    """
    ofis = ofis_ac(a.db, a.proje)
    durdurma_temizle(ofis.db, ofis.proje_id)
    # Patronun Surdur'u: bayat ve takilan isler yeniden denenir.
    ofis.db.olay_yaz(ofis.proje_id, "surdur_istendi", "Patron kabuk devam", ajan_ad="insan")
    _gunluk_yedek(ofis)
    bekleyen = (len(ofis.postane.insan_bekleyenler())
                + len(ofis.postane.bekleyen_onaylar()))
    if bekleyen:
        yaz(f"UYARI: {bekleyen} istek hala cevapsiz; o isler ilerlemeyecek.")
        yaz("  python -m ofis.kabuk bekleyen")
        yaz("")
    yaz("Halka donuyor...")
    yaz("")
    _dongu_yaz(ofis, a)
    yaz("")
    _durum_yaz(ofis)


def komut_anahtar(a) -> None:
    """API anahtarlarini yonetir. DEGER BASMAZ.

    Anahtar `~/.agentofis/gizli.env` icinde durur -- proje kokunun
    DISINDA. Sebep: `eller` ajanlar kok klasorde calisir ve izin
    listesinde `Bash(cat *)` var; kok altina konan bir `.env`, ajanin bir
    `cat` komutu kadar uzaktadir.
    """
    if a.eylem == "liste":
        kayitlar = gizli.liste()
        yaz(f"Depo: {gizli.depo_yolu()}")
        if not kayitlar:
            yaz("(bos)")
            yaz("")
            yaz("Eklemek icin:")
            yaz("  python -m ofis.kabuk anahtar ekle GEMINI_API_KEY")
            return
        yaz("")
        for k in kayitlar:
            yaz(f"  {k['ad']:28} {k['parmak_izi']}")
        yaz("")
        yaz("Degerler BASILMAZ. Parmak izi 'dogru anahtari mi koydum'")
        yaz("sorusunu cevaplar, anahtari yeniden kurmaya yetmez.")
        return

    if a.eylem == "sil":
        if not a.ad:
            raise SystemExit("Hangi anahtar? Ornek: anahtar sil GEMINI_API_KEY")
        yaz("Silindi." if gizli.sil(a.ad) else f"'{a.ad}' zaten yok.")
        return

    # ekle -- DEGER ARGUMANDAN ALINMAZ, STDIN'DEN OKUNUR.
    #
    # Komut satirina yazilan bir sir, kabuk gecmisine (`history`), surec
    # listesine (`ps`/Gorev Yoneticisi) ve oturum kaydina duser. Ucu de
    # kalicidir ve ucu de paylasilir. Stdin bunlarin hicbirine dusmez.
    if not a.ad:
        raise SystemExit("Hangi anahtar? Ornek: anahtar ekle GEMINI_API_KEY")

    # DEGER GORUNMEDEN OKUNUR.
    #
    # OLCULDU (19.09.2026), gercek kullanicida: ilk surum `readline()`
    # kullaniyordu ve deger EKRANA yansiyordu. Kullanicinin yapistirmasi
    # iki satir halinde gitti; ilk satir programa ulasti, IKINCI SATIR
    # PowerShell'e dustu ve komut sanilip anahtar ekrana basildi:
    #
    #   'AQ.Ab8...' is not recognized as the name of a cmdlet
    #
    # Yani anahtar hem terminal kaydirmasinda hem PSReadLine gecmisinde
    # hem de ekran goruntusunde kaldi. Anahtar degistirilmek zorunda
    # kaldi. **Yanlis yapmasi kolay olan bir arayuz, kullanicinin degil
    # arayuzun kusurudur.**
    #
    # `getpass` yankilamaz; cok satirli yapistirmada da yalnizca ilk
    # satiri alir ve gerisi ekrana DUSMEZ (terminal gizli kipte).
    import getpass
    yaz(f"{a.ad} degerini yapistir ve Enter'a bas.")
    yaz("(Yazdigin GORUNMEYECEK -- bos gorunmesi normal.)")
    try:
        deger = getpass.getpass("> ").strip()
    except (KeyboardInterrupt, EOFError):
        raise SystemExit("Iptal edildi.")
    except Exception:
        # Gizli okuma desteklenmiyorsa SESSIZCE yankilamaya DUSMEYIZ.
        # Kullanici "gorunmuyor" sanip yapistirirsa sir ekranda kalir.
        raise SystemExit(
            "Bu terminal gizli giris desteklemiyor. Anahtari dosyaya elle "
            "yaz:" + chr(10) + f"  {gizli.depo_yolu()}" + chr(10)
            + f"  icine tek satir:  {a.ad}=deger")
    if any(ch.isspace() for ch in deger):
        # Bosluk iceren bir "anahtar" neredeyse her zaman yanlis
        # yapistirmadir. Sessizce kaydetmek, sonra "neden calismiyor"
        # sorusuna cevapsiz birakir.
        raise SystemExit(
            "Degerde bosluk var -- muhtemelen fazladan bir sey yapistirildi. "
            "Kaydedilmedi. Yalnizca anahtari kopyalayip tekrar dene.")
    try:
        sonuc = gizli.ekle(a.ad, deger)
    except GizliHatasi as exc:
        raise SystemExit(f"Kaydedilemedi: {exc}")
    yaz("")
    yaz(f"Kaydedildi: {sonuc['ad']}  ({sonuc['parmak_izi']})")
    yaz(f"Yer: {gizli.depo_yolu()}")
    yaz("")
    yaz("Bu anahtar ajanlara GECMEZ. Yalnizca ona ihtiyaci olan motor")
    yaz("adaptoru acikca ister (tip.ortam_hazirla izinli=...).")


def _codex_hesabi(ev: str) -> dict:
    """Bir CODEX_HOME dizinindeki hesabin KIMLIGINI okur.

    Gerceklestirme `ofis/motor/codex.hesap_kimligi`de -- cekirdek de ayni
    soruyu soruyor (`hesap.kullanilabilir_mi`) ve iki kopya bu projede
    alti kez birbirinden kaydi. Burada yalnizca ad korunuyor.
    """
    from ofis.motor.codex import hesap_kimligi
    return hesap_kimligi(ev)


def komut_roller(a) -> None:
    """ROL KUTUPHANESINI gosterir.

    Gorunmeyen kutuphane kullanilmaz: ise alirken hangi adi
    yazacagini bilmiyorsan serbest metne donersin -- ki tam olarak
    bundan kactik.
    """
    from ofis import roller as R

    if a.rol:
        try:
            r = R.rol(a.rol)
        except R.RolHatasi as exc:
            raise SystemExit(str(exc))
        yaz(f"{r.ad}   ({r.kategori})")
        yaz("")
        yaz(f"  {r.ozet}")
        yaz("")
        yaz(f"  tur       : {r.tur}"
            f"{'   <- dosya YAZAMAZ' if r.tur == 'kafa' else '   (dosya yazabilir)'}")
        yaz(f"  kanit     : {', '.join(r.kanit_turleri)}")
        yaz(f"  kademe    : {r.kademe}")
        for motor in ("claude", "codex"):
            m = R.model_sec(motor, r.kademe)
            if m:
                yaz(f"      {motor:7} -> {m}")
        if r.ek_izinler:
            yaz(f"  ek izin   : {', '.join(r.ek_izinler)}")
        if r.mcp:
            yaz(f"  baglayici : {', '.join(r.mcp)}")
        if r.butce_alt_siniri:
            yaz(f"  butce     : tur basina en az ${r.butce_alt_siniri:.2f} onerilir")
        yaz("")
        yaz("  bu rolde 'bitti' genellikle:")
        yaz(f"    {r.olcut_sablonu}")
        if r.uyari:
            yaz("")
            yaz(f"  ! {r.uyari}")
        return

    for kat in R.kategoriler():
        yaz(kat)
        for r in R.ROLLER.values():
            if r.kategori != kat:
                continue
            isaret = " " if r.tur == "eller" else "*"
            uyari = "  ! baglayici bekliyor" if r.uyari else ""
            yaz(f"  {isaret}{r.ad:<13}{r.ozet[:58]}{uyari}")
        yaz("")
    yaz("* = dosya yazamaz (kafa)")
    yaz("Ayrinti:  python -m ofis.kabuk roller --rol arastirma")


def komut_ekip(a) -> None:
    """EKIP ONERISI: lider onerir, SEN onaylarsin, ofis ise alir.

    Kadro kurmak bir yetki genislemesidir -- lider senin limitini
    harcayacak bir kadroyu kendi kuramaz. Onizlemenin butun degeri,
    kararin UYGULANMADAN once gorunmesinde.
    """
    ofis = ofis_ac(a.db, a.proje)

    if a.eylem == "liste":
        bekleyen = ofis.ekip.bekleyenler()
        if not bekleyen:
            yaz("Bekleyen ekip onerisi yok.")
            yaz('Oner:  python -m ofis.kabuk ekip oner "uctan uca web uygulamasi"')
            return
        for o in bekleyen:
            yaz(ofis.ekip.onizleme(o["no"]))
            yaz("")
        return

    if a.eylem == "sablon":
        # SABLON: lider cagrilmaz, jeton yanmaz. Uretilen sey bir ONERIDIR
        # ve ayni kapidan gecer; kurmak yine `ekip kur <no>`.
        from . import sablon as _s
        if not a.istek:
            yaz("TAKIM SABLONLARI (ekip sablon AD --kanat KANAT):")
            for s in _s.liste():
                yaz(f"  {s.ad:<10} {s.baslik}: {s.aciklama}")
                yaz(f"  {'':<10} roller: {', '.join(r for r, _ in s.uyeler)}")
            return
        try:
            o = ofis.ekip.sablondan(a.istek, kanat_id=a.kanat or None)
        except EkipHatasi as exc:
            raise SystemExit(str(exc))
        yaz(ofis.ekip.onizleme(o["no"]))
        yaz("")
        yaz(f"KURULMADI. Kurmak icin:  ekip kur {o['no']}   "
            f"reddetmek icin:  ekip red {o['no']} --sebep \"...\"")
        return

    if a.eylem == "oner":
        if not a.istek:
            raise SystemExit(
                'Ne icin kadro? Ornek: ekip oner "uctan uca web uygulamasi"')
        yaz(f"ISTEK: {a.istek}")
        yaz("")
        yaz("Lider kadro dusunuyor...")
        try:
            o = ofis.ekip.oner(a.istek, lider_ad=a.lider or "",
                               butce_usd=None, zaman_asimi=a.zaman_asimi)
        except EkipHatasi as exc:
            raise SystemExit(f"Oneri alinamadi: {exc}")
        yaz("")
        yaz(ofis.ekip.onizleme(o["no"]))
        return

    # `ekip kur 1` de `ekip kur --no 1` de calissin: numara konumsal
    # alandan da okunur. Kullanicinin iki bicimi ezberlemesi gerekmesin.
    no = a.no
    if no is None and a.istek.strip().isdigit():
        no = int(a.istek.strip())
    if no is None:
        raise SystemExit(f"Hangi oneri? Ornek: ekip {a.eylem} 1")
    a.no = no

    if a.eylem == "kur":
        try:
            alinan = ofis.ekip.kur(a.no, klasor=a.klasor or "")
        except EkipHatasi as exc:
            raise SystemExit(f"Kurulamadi: {exc}")
        yaz(f"Ekip #{a.no} KURULDU:")
        for x in alinan:
            yaz(f"  {x['ad']:<10}{x['meslek']:<13}{x['motor']}/"
                f"{x['model'] or '(model yok!)'}  {x['tur']}")
        yaz("")
        yaz("Simdi is verebilirsin:")
        yaz('  python -m ofis.kabuk konus "..."')
        return

    if a.eylem == "red":
        # Sebep ZORUNLU: gerekcesiz ret, liderin ayni oneriyi baska
        # bicimde tekrar getirmesi demektir.
        try:
            o = ofis.ekip.reddet(a.no, a.sebep)
        except EkipHatasi as exc:
            raise SystemExit(f"Reddedilemedi: {exc}")
        yaz(f"Ekip #{o['no']} reddedildi.")
        yaz(f"  sebep: {o['sebep']}")
        return


def _gunluk_yedek(ofis) -> None:
    """Gunde bir kez yedek alir -- yalniz GERCEK ofis defterinde.

    Sinamalar ve ornek ofis kendi gecici defterleriyle kosar; onlarda
    yedek tetiklenseydi her test kosusu gercek yedek klasorune bir arsiv
    birakir, 30'luk sinirla GERCEK yedekleri budardi.
    """
    from ofis import yedek as Y
    if not Y.gercek_defter_mi(ofis.db.yol):
        return
    s = Y.gerekirse_al(lambda tur, govde: ofis.db.olay_yaz(
        ofis.proje_id, tur, govde), depo_gonder=True)
    if s.get("hata"):
        yaz(f"[!] Gunluk yedek ALINAMADI: {s['hata']}")
        yaz("")
    elif s:
        yaz(f"Gunluk yedek alindi: {Path(s['arsiv']).name}")
        for h in s["hedefler"]:
            if h["durum"] != "tamam":
                yaz(f"  [!] {h['klasor']}: {h['hata']}")
        d = s.get("depo") or {}
        if d:
            yaz(f"  GitHub: {d['durum']}" + (f" -- {d['sebep']}" if d.get("sebep") else ""))
        yaz("")


def _guncelleme_bildir(ofis) -> None:
    """Gunde bir kez yeni model/CLI denetler; bekleyen varsa TEK SATIR soyler.

    Denetim insanin isini durdurmaz ve uygulamaz -- yalnizca haber verir.
    Bildirim gorunmezse "yeni model gelince haber versin" istegi kagitta
    kalir.
    """
    _gunluk_yedek(ofis)
    from ofis import guncelleme as G
    G.kontrol_gerekirse(ofis.db, ofis.proje_id)
    n = len(G.insana_dusenler(ofis.db, ofis.proje_id))
    if n:
        yaz(f"[!] {n} guncelleme onayini bekliyor -- `guncelle liste`")
        yaz("")


def komut_guncelle(a) -> None:
    """YENI MODEL / CLI SURUMU -- ofis fark eder, sen onaylarsin, ofis uygular.

    Onaylanan oneri once DENEME TURU kosar: dusmezse kalici olur, duserse
    eskisi kalir (CLI'da eski surume GERI donulur). Onaysiz hicbir sey
    kurulmaz -- bu projede CLI degisiklikleri ofisi uc kez sessizce bozdu.
    """
    from ofis import guncelleme as G

    ofis = ofis_ac(a.db, a.proje)
    if a.eylem == "otomatik":
        # OTOMATIK MOD (29.09.2026): ayni aile / takma ad / CLI -> ofis
        # kendisi dener ve uygular; yeni aile ve dusenler insana duser.
        secim = (a.no or "durum").lower()
        if secim in ("ac", "kapat"):
            G.otomatik_ayarla(ofis.db, ofis.proje_id, secim == "ac")
            yaz(f"Otomatik guncelleme: {'ACIK' if secim == 'ac' else 'KAPALI'}")
            return
        if secim == "durum":
            yaz(f"Otomatik guncelleme: "
                f"{'ACIK' if G.otomatik_mi(ofis.db, ofis.proje_id) else 'KAPALI'}")
            return
        if secim != "simdi":
            raise SystemExit("`guncelle otomatik [simdi|ac|kapat]`")
        yaz("Olculuyor (kataloglar + npm surumleri)...")
        sonuc = G.olc_ve_ilerle(ofis, npm=not a.npm_yok)
        if not sonuc:
            yaz("Otomatik uygulanacak bir sey yok.")
        for r in sonuc:
            durum = ("ERTELENDI" if r.get("ertelendi") else
                     "UYGULANDI" if r.get("basarili") else "DUSTU (sana dustu)")
            yaz(f"  {durum}: {r.get('ozet', r.get('anahtar'))}")
            yaz(f"      {r.get('mesaj', '')}")
        kalan = G.insana_dusenler(ofis.db, ofis.proje_id)
        if kalan:
            yaz(f"\n{len(kalan)} karar SANA dustu -- `guncelle liste`")
        return
    if a.eylem == "gecmis":
        liste = G.gecmis(ofis.db, ofis.proje_id)
        if not liste:
            yaz("Uygulanmis guncelleme yok.")
            return
        for k in liste[-15:]:
            yaz(f"  #{k['sira']}  {k['zaman'][:16].replace('T', ' ')}  "
                f"{k.get('ad') or k['motor']}: {k.get('eski')} -> {k.get('yeni')}  "
                f"[{k.get('veren')}] {k.get('durum')}")
        yaz("\nGeri almak: `guncelle geri-al <no> --sebep \"...\"`")
        return
    if a.eylem == "geri-al":
        try:
            r = G.geri_al(ofis, int(a.no), sebep=a.sebep)
        except (TypeError, ValueError):
            raise SystemExit("`guncelle geri-al <no>`")
        except G.GuncellemeHatasi as exc:
            raise SystemExit(str(exc))
        yaz(r["mesaj"])
        return
    if a.no is not None:
        try:
            a.no = int(a.no)
        except ValueError:
            raise SystemExit("Numara bir sayi olmali.")
    if a.eylem == "kontrol":
        yaz("Olculuyor (kataloglar + npm surumleri)...")
        sonuc = G.kontrol(ofis.db, ofis.proje_id, npm=not a.npm_yok)
        for k, v in sonuc["olcum"].items():
            if k.startswith("cli:"):
                yaz(f"  {k[4:]:7} kurulu {v['kurulu']:>10} · guncel {v['guncel']}")
        yaz(f"  claude katalogu: {sonuc['olcum'].get('katalog:claude')}")
        yaz(f"  codex listeleri: {sonuc['olcum'].get('katalog:codex')}")
        yaz("")
        bekleyen = G.insana_dusenler(ofis.db, ofis.proje_id)
        oto = [o for o in sonuc["oneriler"] if o not in bekleyen
               and G.otomatik_uygulanir_mi(ofis.db, ofis.proje_id, o)]
        if oto and G.otomatik_mi(ofis.db, ofis.proje_id):
            yaz(f"{len(oto)} oneri OTOMATIK uygulanacak (deneme turuyla; "
                "hemen icin `guncelle otomatik simdi`):")
            for o in oto:
                yaz(f"  -  {o['ozet']}")
            yaz("")
    elif a.eylem == "liste":
        bekleyen = G.insana_dusenler(ofis.db, ofis.proje_id)
    elif a.eylem == "onayla":
        if a.no is None:
            raise SystemExit("`guncelle onayla <no>`")
        yaz(f"#{a.no} uygulaniyor -- once deneme turu...")
        try:
            r = G.uygula(ofis, a.no, kademe=a.kademe)
        except (G.GuncellemeHatasi, roller_hatasi()) as exc:
            raise SystemExit(f"Uygulanamadi: {exc}")
        yaz(("TAMAM: " if r["basarili"] else "UYGULANMADI: ") + r["mesaj"])
        return
    elif a.eylem == "reddet":
        if a.no is None:
            raise SystemExit("`guncelle reddet <no> --sebep \"...\"`")
        try:
            r = G.reddet(ofis, a.no, a.sebep)
        except (G.GuncellemeHatasi, roller_hatasi()) as exc:
            raise SystemExit(str(exc))
        yaz(r["mesaj"])
        return
    if not bekleyen:
        yaz("Bekleyen guncelleme yok."
            + (" (Bu 'her sey guncel' demek degil: son denetim "
               f"{ofis.db.ayar_oku(ofis.proje_id, G.ANAHTAR_SON_KONTROL, 'HIC yapilmadi')})"
               if a.eylem == "liste" else ""))
        return
    yaz(f"{len(bekleyen)} oneri SENI bekliyor:")
    for o in bekleyen:
        yaz(f"  #{o['no']}  {o['ozet']}")
        if o.get("otomatik_dustu"):
            yaz(f"        OTOMATIK DENEME DUSTU: {o['otomatik_dustu']}")
        if o.get("kademeler"):
            yaz(f"        kademe: {', '.join(o['kademeler'])}")
        if o.get("ajanlar"):
            yaz(f"        ajan  : {', '.join(o['ajanlar'])}")
        if o["tur"] == "cli":
            yaz("        not   : bilgisayardaki BUTUN bu CLI kullanicilarini etkiler")
    yaz("")
    yaz("`guncelle onayla <no>` · yeni aile icin `--kademe hizli|standart|guclu` · "
        "`guncelle reddet <no> --sebep \"...\"`")


def roller_hatasi():
    from ofis import roller as R
    return R.RolHatasi


def komut_model(a) -> None:
    """ETKIN kademe haritasi + efor tavani. Elle atama da buradan.

    Harita = koddaki varsayilan + ONAYLANMIS ayar. `roller` komutu kodun
    varsayilanini gosterir; ofisin GERCEKTE ne kosturdugu burada.
    """
    from ofis import roller as R

    ofis = ofis_ac(a.db, a.proje)
    try:
        if a.eylem == "ata":
            if not (a.motor and a.kademe and a.model):
                raise SystemExit("`model ata --motor codex --kademe standart --model gpt-6-sol`")
            R.kademe_yaz(ofis.db, ofis.proje_id, a.motor, a.kademe, a.model)
            ofis.db.olay_yaz(ofis.proje_id, "kademe",
                             f"{a.motor}/{a.kademe} -> {a.model} (elle)")
            yaz(f"{a.motor}/{a.kademe} -> {a.model}")
        elif a.eylem == "efor-tavani":
            if a.efor:
                R.efor_tavani_yaz(ofis.db, ofis.proje_id, a.efor)
                ofis.db.olay_yaz(ofis.proje_id, "efor_tavani", a.efor)
        elif a.eylem == "efor-modu":
            if a.efor:
                R.efor_modu_yaz(ofis.db, ofis.proje_id, a.efor)
                ofis.db.olay_yaz(ofis.proje_id, "efor_modu", a.efor)
    except R.RolHatasi as exc:
        raise SystemExit(str(exc))
    harita = R.kademe_haritasi(ofis.db, ofis.proje_id)
    yaz("KADEME -> MODEL (etkin: kod varsayilani + onaylanan ayar)")
    for motor, kademeler in harita.items():
        if motor == "sahte":
            continue
        for k in R.KADEMELER:
            varsayilan = R.KADEME_MODEL.get(motor, {}).get(k, "")
            m = kademeler.get(k, "")
            yaz(f"  {motor:7} {k:9} {m or '-':22}"
                + ("   (ayar)" if m != varsayilan else ""))
    tavan = R.efor_tavani(ofis.db, ofis.proje_id)
    mod = R.efor_modu(ofis.db, ofis.proje_id)
    yaz("")
    yaz(f"EFOR MODU  : {mod}" + ("   (her is kendi zorluguyla)" if mod == "zorluk"
                                 else "   (BUTUN turlar bu seviyede)"))
    yaz(f"EFOR TAVANI: {tavan}   (yalniz 'zorluk' modunda; max YOK)")
    yaz("  zorluk -> efor: " + " · ".join(
        f"{z}={R.tur_eforu(ofis.db, ofis.proje_id, e)}" for z, e in R.ZORLUK_EFOR.items()))


def komut_plan(a) -> None:
    """ABONELIK PLANI -- goster ya da degistir.

    Plan KOD DEGIL AYAR: hesap degisince kod degismez. Tavan buradan
    olceklenir; kapi modelinin haftalik butcesi plandan okunur.
    """
    from ofis import plan as _plan

    ofis = ofis_ac(a.db, a.proje)
    degisti = (a.claude or a.gpt or a.tavansiz_kapi)
    if degisti:
        tavansiz = None
        if a.tavansiz_kapi:
            tavansiz = a.tavansiz_kapi == "ac"
        try:
            _plan.yaz(ofis.db, ofis.proje_id, claude=a.claude or None,
                      gpt=a.gpt or None, tavansiz_kapi=tavansiz)
        except _plan.PlanHatasi as exc:
            raise SystemExit(f"Plan degistirilemedi: {exc}")
        yaz("Plan guncellendi.")
        yaz("")
    yaz(_plan.ozet(ofis.plan))
    if degisti:
        yaz("")
        yaz("Kapi butcesi bu plandan okunuyor -- kod degismedi.")


def komut_hesap(a) -> None:
    """HESAPLAR -- motor KIMIN adina konusacak.

    Motor NASIL konusulacagini bilir; hesap KIMIN adina. Ayni motorun
    iki hesabi (is/kisisel), ya da abonelik + API yan yana durabilir.
    Nobet zinciri bu hesaplar uzerinde yurur.

    ANAHTAR BURAYA YAZILMAZ: `--ortam ANAHTAR=@gizli:ISIM` bir
    REFERANS tutar; gercek deger proje kokunun DISINDAKI depodan
    (`kabuk anahtar ekle`) tur aninda cozulur.
    """
    from ofis import hesap as _h

    ofis = ofis_ac(a.db, a.proje)

    if a.eylem == "durum":
        # CANLI hal: CLI'lar su an hangi hesaba girisli.
        _hesap_canli(a)
        return

    if a.eylem == "liste":
        hepsi = _h.liste(ofis.db, ofis.proje_id)
        if not hepsi:
            yaz("Tanimli hesap yok -- ortuk hesaplar kullaniliyor:")
            for x in _h.varsayilan_hesaplar(ofis.db, ofis.proje_id):
                yaz(f"  {x['ad']:<14}{x['motor']:<9}{x['tur']:<10}(ortuk)")
            yaz("")
            yaz('Ekle:  kabuk hesap ekle <ad> --motor codex '
                '--ortam CODEX_HOME=~/.agentofis/codex2')
            return
        for x in hepsi:
            olur = _h.kullanilabilir_mi(x)
            isaret = " " if olur["olur"] else "!"
            yaz(f" {isaret}{x['ad']:<14}{x['motor']:<9}{x['tur']:<10}"
                f"{x['plan'] or '-':<8}sira={x['sira']:<5}"
                f"{'aktif' if x['aktif'] else 'KAPALI'}")
            if x["ortam"]:
                yaz(f"     ortam: {', '.join(x['ortam'])}")
            if x["tur"] == "api":
                k = _h.api_kalan(ofis.db, ofis.proje_id, x)
                yaz(f"     bu ay: ${k['harcanan']:.2f} / "
                    + (f"${k['sinir']:.2f}" if k["sinir"] else "SINIR YOK"))
            if not olur["olur"]:
                yaz(f"     ! {olur['sebep']}")
        yaz("")
        yaz("! = su an kullanilamaz. Zincir bu hesaplarin uzerinde yurur.")
        return

    if not a.ad:
        raise SystemExit(f"Hangi hesap? Ornek: hesap {a.eylem} codex-is ...")

    if a.eylem == "ekle":
        ortam = {}
        for parca in (a.ortam or []):
            if "=" not in parca:
                raise SystemExit(
                    f"--ortam ANAHTAR=DEGER bicimde olmali: {parca!r}")
            k, v = parca.split("=", 1)
            ortam[k.strip()] = v.strip()
        try:
            x = _h.ekle(ofis.db, ofis.proje_id, a.ad, a.motor, tur=a.tur,
                        plan=a.plan, ortam=ortam, sira=a.sira, not_=a.not_,
                        aylik_sinir_usd=a.aylik_sinir)
        except _h.HesapHatasi as exc:
            raise SystemExit(f"Eklenemedi: {exc}")
        yaz(f"{x['ad']} eklendi ({x['motor']}/{x['tur']}, sira={x['sira']})")
        olur = _h.kullanilabilir_mi(x)
        yaz(f"  kullanilabilir: {'EVET' if olur['olur'] else 'HAYIR'}")
        if not olur["olur"]:
            yaz(f"  ! {olur['sebep']}")
        return

    if a.eylem == "sinir":
        # Yalniz API hesabi: ayda en cok ne kadar dolar (27.09.2026 karari).
        try:
            x = _h.ayarla(ofis.db, ofis.proje_id, a.ad,
                          aylik_sinir_usd=a.aylik_sinir or 0)
        except _h.HesapHatasi as exc:
            raise SystemExit(f"Degistirilemedi: {exc}")
        yaz(f"{x['ad']}: aylik sinir ${x['aylik_sinir_usd']:.2f}")
        return

    if a.eylem in ("ac", "kapat"):
        try:
            x = _h.ayarla(ofis.db, ofis.proje_id, a.ad,
                          aktif=(a.eylem == "ac"))
        except _h.HesapHatasi as exc:
            raise SystemExit(f"Degistirilemedi: {exc}")
        yaz(f"{x['ad']}: {'aktif' if x['aktif'] else 'KAPALI'}")
        return


def komut_ajan(a) -> None:
    """Kadroyu gosterir ya da bir ajanin motorunu/modelini DEGISTIRIR.

    Ajan bir KIMLIKTIR: adi, meslegi, klasoru ve SICILI kalicidir --
    ders sayaci ancak ayni ajan birikirse anlam tasir. Motor ve model
    ise birer AYARDIR, fise takilidir ve degistirilebilir.

    Bu ayrim bilincli: "ajani degistirmek" ile "ajanin modelini
    degistirmek" ayni sey degildir. Ilki sicili siler, ikincisi silmez.
    """
    ofis = ofis_ac(a.db, a.proje)
    if a.eylem == "liste":
        for x in ofis.kadro.liste():
            etiket = "LIDER" if x["lider_mi"] else x["tur"]
            ders = len(ofis.kadro.dersler(x["ad"]))
            yaz(f"  {x['ad']:10} {x['meslek']:14} {etiket:6} "
                f"{x['motor']:8} {x['model'] or '(varsayilan!)':22} "
                f"efor={x['efor']:7} faz={x['faz']:10} {ders} ders")
        yaz("")
        yaz("(varsayilan!) = model verilmemis; hesabin varsayilanina duser.")
        yaz("Olculdu: model verilmeden kosan is $0,88, acik model verilen $0,08.")
        return

    if not a.ad:
        raise SystemExit("Hangi ajan? Ornek: ajan degistir cinar --model sonnet")
    if not (a.motor or a.model or a.efor or a.rol or a.klasor):
        raise SystemExit(
            "Ne degisecek? --motor / --model / --efor / --rol / --klasor ver.\n"
            "Ornek: python -m ofis.kabuk ajan degistir cinar --model haiku")
    try:
        yeni = ofis.kadro.motor_ayarla(a.ad, meslek=a.rol or None,
                                       motor=a.motor or None,
                                       model=a.model or None,
                                       efor=a.efor or None,
                                       klasor=a.klasor or None)
    except (KadroHatasi, RolHatasi) as exc:
        raise SystemExit(f"Degistirilemedi: {exc}")
    yaz(f"{yeni['ad']} guncellendi:")
    # Rolu de BAS. Basmayan cikti, sessizce yok sayilan bir ayari fark
    # ettirmez -- bu hata tam burada, bu satir yokken yasandi: `--rol`
    # gecmiyordu, komut "guncellendi" diyordu ve rol degismemisti.
    yaz(f"  rol  : {yeni['meslek']}   tur: {yeni['tur']}")
    yaz(f"  motor: {yeni['motor']}  model: {yeni['model'] or 'hesap varsayilani'}"
        f"  efor: {yeni['efor']}")
    # Klasor de basilir: ajanin klasoru `--restricted` sinirini belirler,
    # yani bir YETKI alanidir. Basmayan cikti, yok sayilan ayari fark
    # ettirmez -- ayni ders `--rol`de bir kez odendi.
    yaz(f"  klasor: {yeni['klasor']}")
    yaz("")
    yaz("Yeni ayar BIR SONRAKI gorevde gecerli olur -- suren oturum")
    yaz("basladigi motorla kalir; yarida degistirmek baglami koparir.")


def komut_gorsel(a) -> None:
    """Elle gorsel uretir. Ajanlar ayni isi `gorsel_uret` araciyla yapar.

    Bu komut iki ise yarar: saglayicilarin durumunu gormek, ve ofis
    kurulmadan hizli bir deneme yapmak.
    """
    from ofis import gorsel as _gorsel
    gizli.yukle()

    if a.eylem == "para":
        # Para harcamak ACIK bir tercih olmali; komut da acik olmali.
        # Acan kisi neyi kabul ettigini GORMELI -- `plan --tavansiz-kapi`
        # ile ayni ilke.
        istek = (a.istem or "").strip().lower()
        if istek not in ("ac", "kapat"):
            yaz(f"Su an: para harcama {'KAPALI' if _gorsel.ucretsiz_sadece_mi() else 'ACIK'}")
            yaz("Degistirmek icin: `gorsel para ac` ya da `gorsel para kapat`")
            return
        _gorsel.para_harca_ayarla(istek == "ac")
        if istek == "ac":
            yaz("Para harcama ACILDI.")
            yaz("  Ucretli ureticiler artik kullanilabilir.")
            yaz("  OLCULDU: OpenRouter'da BEDAVA gorsel modeli YOK --")
            yaz("  gorsel cikti veren 11 modelin hepsi ucretli.")
            yaz("  Video'da da ucretsiz katman YOK.")
            yaz("  Kapatmak: `gorsel para kapat`")
        else:
            yaz("Para harcama KAPATILDI -- yalnizca ucretsiz uretici kosar.")
        return

    if a.eylem == "durum":
        yaz(f"  para harcama: {'KAPALI (yalniz ucretsiz)' if _gorsel.ucretsiz_sadece_mi() else 'ACIK'}")
        yaz("")
        for ad, b in _gorsel.musait_ureticiler().items():
            # "MUSAIT" ASLA yalniz anahtara bakarak yazilmaz.
            # Olculdu (21.09.2026): gunluk kota doluyken bu satir
            # "MUSAIT" diyordu ve saglayici hicbir sey uretemiyordu.
            # Anahtarin olmasi ile URETEBILIYOR olmak ayri iki seydir.
            if not b["musait"]:
                etiket = "yok"
            elif b.get("kota_notu"):
                etiket = "KOTA?"
            else:
                etiket = "anahtar"
            para = "ucretli" if b["ucretli"] else "ucretsiz"
            yaz(f"  {ad:8} {etiket:7} ({para})")
            if b.get("kota_notu"):
                yaz(f"      son deneme: {b['kota_notu']}")
            if b["sebep"]:
                for satir in b["sebep"].split(". "):
                    if satir.strip():
                        yaz(f"      {satir.strip()}")
        yaz("")
        yaz("Tercih sirasi: " + " -> ".join(_gorsel.TERCIH_SIRASI)
            + "  (once UCRETSIZ olan denenir)")
        return

    if a.eylem == "ekle":
        # INSANIN urettigi gorseli tahtaya KANIT olarak koyar.
        # Dosyanin varligi OLCULUR, iddia edilmez.
        from pathlib import Path as _P
        import shutil as _sh
        if not a.istem:
            raise SystemExit("Hangi dosya? Ornek: gorsel ekle C:/indirilenler/a.png --gorev 7")
        kaynak = _P(a.istem).expanduser()
        if not kaynak.is_file():
            raise SystemExit(f"Dosya yok: {kaynak}")
        if a.gorev is None:
            raise SystemExit("--gorev <no> gerekli: kanit hangi ise ait?")
        ofis = ofis_ac(a.db, a.proje)
        g = ofis.tahta.gorev(a.gorev)
        sahip = g["sahip"] or "insan"
        kok = _P(ofis.kadro.ajan(sahip)["klasor"]) if g["sahip"] else _P(ofis.isin_koku(g))
        alanlar = g["yazma_alani"] or []
        try:
            hedef = medya_hedefi(kok, alanlar, a.ad or kaynak.name)
        except TahtaHatasi as exc:
            raise SystemExit(f"Eklenmedi: {exc}")
        hedef.parent.mkdir(parents=True, exist_ok=True)
        _sh.copy2(kaynak, hedef)
        ofis.tahta.kanit_ekle(
            g["no"], "gorsel", str(hedef),
            f"Insan tarafindan uretildi ve ofise alindi ({hedef.stat().st_size} bayt).",
            sahip)
        yaz(f"Alindi: {hedef}")
        yaz(f"  #{g['no']} icin KANIT olarak yazildi.")
        yaz("")
        yaz("Bekleyen onay varsa kapat:  python -m ofis.kabuk bekleyen")
        yaz("Sonra halkayi dondur:       python -m ofis.kabuk devam")
        return

    if not a.istem:
        raise SystemExit('Istem gerekli. Ornek: gorsel uret "koyu mavi logo"')
    hedef = a.cikti or "gorsel.png"
    try:
        sonuc = _gorsel.uret(a.istem, hedef, uretici=a.uretici or "",
                             model=a.model or "", kalite=a.kalite or "",
                             ucretsiz_sadece=False if a.para_harca else None)
    except _gorsel.ParaKilidi as exc:
        # AYRI YAKALANIR: bu bir ariza degil bir KARAR. "Uretilemedi"
        # demek, kullaniciyi bozuk bir sey aramaya gonderirdi.
        raise SystemExit(str(exc))
    except _gorsel.GorselHatasi as exc:
        raise SystemExit(f"Uretilemedi:{chr(10)}{exc}")
    yaz(f"Uretildi: {sonuc['yol']}")
    para = (f" · ${sonuc['maliyet_usd']:.4f}"
            if sonuc.get("maliyet_usd") is not None else "  (maliyet olculemedi)")
    yaz(f"  {sonuc['uretici']}/{sonuc['model']} · {sonuc['bayt']} bayt{para}")
    if sonuc.get("jeton"):
        yaz(f"  cikti jetonu: {sonuc['jeton']}")
    for at in (sonuc.get("atlananlar") or []):
        yaz(f"  (atlandi: {at['uretici']} -- {at['sebep'][:110]})")


def _kilitler(ofis, gorev_id: str) -> list:
    """Bir isin SU AN tuttugu kilitler -- olculur, tahmin edilmez."""
    with ofis.db.baglanti() as conn:
        return [r["yol_oneki"] for r in conn.execute(
            "SELECT yol_oneki FROM yazma_kilidi WHERE gorev_id = ?",
            (gorev_id,)).fetchall()]


def komut_not(a) -> None:
    """CALISAN bir ajana not birak: "dur, sunu degistir".

    Not isin tanimina EKTIR. Ajanin motoru tasiyabiliyorsa (claude, codex
    app-server) tur SURERKEN iletilir -- claude'da bir sonraki arac
    sinirinda, codex'te hemen; tasiyamiyorsa bir sonraki turun basinda.
    Ulastigi an deftere yazilir (`not_iletildi`); yazilmak ulasmak degildir.
    """
    ofis = ofis_ac(a.db, a.proje)
    try:
        n = ofis.postane.not_birak(a.ajan, a.metin, gorev_no=a.gorev)
    except Exception as exc:
        raise SystemExit(f"Not birakilamadi: {exc}")
    ajan = ofis.kadro.ajan(a.ajan)
    from ofis.motor import motor_ac
    try:
        tasir = bool(getattr(motor_ac(ajan["motor"]), "tur_ici_mesaj", False))
    except Exception:
        tasir = False
    yaz(f"not -> {n['alici']} (#{n['gorev_no']}): {n['govde'][:120]}")
    yaz("  " + ("tur SURERKEN iletilecek (ajan calisiyorsa); ulastiginda "
                "defterde 'not_iletildi' gorunur." if tasir else
                f"{ajan['motor']} tur surerken not alamiyor: bir SONRAKI "
                "turun basinda iletilecek."))


def komut_durdur(a) -> None:
    """Ofisi DURDURUR: kosan turlar kesilir, halka yeni tur baslatmaz.

    Istek deftere yazilir; baska bir surecte kosan halka da gorur. Yarim
    kalan is ariza sayilmaz: `devam` ayni ajanla, ayni oturumdan surdurur.
    """
    ofis = ofis_ac(a.db, a.proje)
    durdurma_iste(ofis.db, ofis.proje_id, "insan (kabuk)")
    kosan = [g for g in ofis.tahta.liste() if g["durum"] == "calisiyor"]
    yaz("DURDURMA istendi. " + (f"{len(kosan)} kosan is kesiliyor."
                                if kosan else "Kosan is yok."))
    yaz("  surdurmek icin: python -m ofis.kabuk devam")


def komut_iptal(a) -> None:
    """Yarim kalan bir isi iptal eder ve KILITLERINI birakir.

    Kabuga baglanmasinin sebebi olculdu: `iptal` gecerli bir durumdu ama
    ona gecirecek ne bir yontem ne bir komut vardi. Sonuc: gercek ofiste
    #17 elle `iptal` yapilmis, iki kilidi kalmis ve `ofis/motor` alani
    baska bir ise SEBEPSIZ kapali durmustu.

    **Cagrilamayan bir yontem, olmayan bir yontemdir** -- ayni ders
    `video.py`de ayni gun odendi: modul vardi, ajanin ona ulasacagi yol
    yoktu.
    """
    ofis = ofis_ac(a.db, a.proje)
    g = ofis.tahta.gorev(a.no)
    kilitli_once = _kilitler(ofis, g["id"])
    if not a.sebep.strip():
        raise SystemExit(
            "--sebep zorunlu. Gerekcesiz iptal, alti ay sonra "
            "'bu is neden yarim kaldi' sorusunu cevapsiz birakir.")
    try:
        y = ofis.tahta.iptal_et(a.no, sebep=a.sebep, iptal_eden="insan")
    except Exception as exc:
        raise SystemExit(f"Iptal edilemedi: {exc}")
    yaz(f"#{y['no']} {y['baslik']} -> {y['durum']}")
    # BIRAKILAN KILITLER OLCULUR, IDDIA EDILMEZ.
    # Ilk surumum gorevin yazma alanini basiyordu -- yani "sunlar
    # birakildi" DIYORDU, birakildigini olcmuyordu. Gercek kosuda tam
    # bu yalan cikti: is zaten `iptal`di, hicbir kilit silinmedi ve
    # komut yine "kilit birakildi" yazdi. Yanlis gosteren bir gosterge,
    # gostergesizlikten kotudur -- ve bu kez gosterge benim yazdigimdi.
    for alan in sorted(set(kilitli_once) - set(_kilitler(ofis, g["id"]))):
        yaz(f"  kilit birakildi: {alan}")
    kalan = _kilitler(ofis, g["id"])
    if kalan:
        yaz(f"  DIKKAT: hala kilitli: {', '.join(sorted(kalan))}")
    yaz(f"  sebep: {a.sebep}")


def komut_belge(a) -> None:
    """BELGE KUTUPHANESI (06.10.2026): yukle / liste / ara / kaldir.
    Kural `ofis/belge.py`de; kabuk ve panel yalniz ulasan kapilar."""
    from . import belge as B
    ofis = ofis_ac(a.db, a.proje)
    try:
        if a.eylem == "yukle":
            if not a.deger:
                raise SystemExit("kullanim: belge yukle DOSYA_YOLU")
            r = B.yukle_yoldan(ofis, a.deger)
            yaz(f"{r['ad']} yuklendi: {r['parca']} parca ({r['yol']})")
        elif a.eylem == "ara":
            for b in B.ara(ofis.db, ofis.proje_id, a.deger, azami=5):
                yaz(f"[{b['belge']} - {b['yer']}] {' '.join(b['metin'].split())[:200]}")
        elif a.eylem == "kaldir":
            r = B.kaldir(ofis, a.deger)
            yaz(f"{r['ad']} kaldirildi (dosya silinmedi)")
        else:
            bl = B.liste(ofis.db, ofis.proje_id)
            if not bl:
                yaz("Belge yok. Yuklemek icin: belge yukle DOSYA_YOLU")
            for b in bl:
                yaz(f"{b['id'][:8]}  {b['ad']}  ({b['parca']} parca, {b['tur']})")
    except B.BelgeHatasi as exc:
        raise SystemExit(str(exc))


def komut_bilgi(a) -> None:
    """Ofisin HAFIZASI: bilgi ekle, listele, gecmisini gor.

    Olculdu (24.09.2026): gercek ofiste 0 olgu vardi -- insanin da
    ajanin da bilgi yazacagi bir yol yoktu. Insanin yazdigi bilgiyi ajan
    sessizce devremez (`bellek.bilgi_ekle`).
    """
    from .bellek import BellekHatasi, baglar
    ofis = ofis_ac(a.db, a.proje)
    bel = ofis.bellek
    if a.eylem == "ekle":
        if not a.konu or not a.icerik:
            raise SystemExit("kullanim: bilgi ekle KONU ICERIK")
        try:
            r = bel.bilgi_ekle(a.konu, a.icerik, yazan="insan")
        except BellekHatasi as exc:
            raise SystemExit(str(exc))
        fiil = {"yeni": "yazildi", "guncellendi": "guncellendi (eskisi "
                "gecmiste)", "ayni": "zaten boyle -- yeni surum acilmadi"}
        yaz(f"{r['konu']}: {fiil[r['durum']]}")
        for b in baglar(r["icerik"]):
            if not bel._konu_bul(b):
                yaz(f"  UYARI: [[{b}]] henuz yazilmamis bir konu")
        return
    if a.eylem == "gecmis":
        if not a.konu:
            raise SystemExit("kullanim: bilgi gecmis KONU")
        konu = bel._konu_bul(a.konu) or a.konu
        g = bel.konu_gecmisi(konu)
        if not g:
            yaz(f"'{a.konu}' diye bir bilgi yok.")
        for o in g:
            durum = "GECERLI" if not o["gecerli_bitis"] else "devrildi"
            yaz(f"  [{durum}] {o['gecerli_baslangic']}  {o['icerik']}"
                f"  ({o['kaynak'] or '-'})")
        return
    olgular = bel.gecerli_olgular()
    if not olgular:
        yaz("Hafizada gecerli bilgi yok. Eklemek icin: bilgi ekle KONU ICERIK")
    for o in olgular:
        yaz(f"- {o['konu']}: {o['icerik']}  ({o['kaynak'] or '-'})")


def komut_eksikler(a) -> None:
    """OFISIN KENDI EKSIKLERI (06.10.2026, K17): bekleyen oneriler ve patronun
    ONAYLADIGI eksikler (gelistiricinin listesi, `ev/ofis_eksikleri.jsonl`)."""
    from . import eksik
    ofis = ofis_ac(a.db, a.proje)
    bekleyen = eksik.topla(ofis)
    yaz(f"bekleyen oneri: {len(bekleyen)}")
    for o in bekleyen:
        yaz(f"  [{o['anahtar']}] {o['baslik']} -- {o['oneri']}")
    onayli = eksik.liste(ofis.proje_id)
    yaz(f"onaylanmis eksik: {len(onayli)}")
    for o in onayli:
        yaz(f"  {o.get('an', '')[:16]} {o['baslik']} -- {o['oneri']}"
            + (f" (not: {o['not']})" if o.get("not") else ""))


def komut_izin(a) -> None:
    """IZINLER -- patronun onceden izin verdigi riskli eylemler.

    Kalici izin ("bu projede `git push origin test` hep serbest") yalniz
    insandan gelir ve gerekce ister. Is izinleri patronun mesajindan
    gelir; burada gorulur ve kaldirilabilir. PARA ve SILME izinle acilmaz.
    """
    from . import izin as izin_mod
    ofis = ofis_ac(a.db, a.proje)
    try:
        if a.eylem == "ekle":
            if not a.desen:
                raise SystemExit('kullanim: izin ekle "git push origin test" '
                                 '--gerekce "..." [--is NO]')
            gid = ofis.tahta.gorev(int(a.is_no))["id"] if a.is_no else None
            r = izin_mod.tanimla(ofis.db, ofis.proje_id, desen=a.desen,
                                 veren="insan", kaynak="insan", gorev_id=gid,
                                 gerekce=a.gerekce)
            yaz(f"izin verildi: {r['desen']} ({izin_mod.IZIN_VERILEBILIR[r['sinif']]})"
                + (f" -- yalniz #{a.is_no}" if gid else " -- KALICI"))
            return
        if a.eylem == "kaldir":
            if not a.desen:
                raise SystemExit("kullanim: izin kaldir IZIN_ID --sebep ...")
            r = izin_mod.kaldir(ofis.db, ofis.proje_id, a.desen, sebep=a.sebep)
            yaz(f"izin kaldirildi: {r['desen']}")
            return
    except izin_mod.IzinHatasi as exc:
        raise SystemExit(str(exc))
    kaliciler = izin_mod.liste(ofis.db, ofis.proje_id)
    yaz(f"KALICI IZINLER ({len(kaliciler)}):")
    for i in kaliciler:
        yaz(f"  {i['id'][:8]}  {i['desen']}  -- {i['gerekce']}")
    with ofis.db.baglanti() as c:
        rows = c.execute(
            "SELECT i.*, g.no FROM izin i JOIN gorev g ON g.id = i.gorev_id "
            "WHERE i.proje_id = ? AND i.kaldirildi IS NULL AND g.durum NOT IN "
            "('bitti','iptal') ORDER BY g.no", (ofis.proje_id,)).fetchall()
    yaz(f"ACIK ISLERIN IZINLERI ({len(rows)}):")
    for r in rows:
        yaz(f"  {r['id'][:8]}  #{r['no']}  {r['desen']}  "
            f"(patron: \"{r['alinti'][:60]}\")")
    yaz("PARA ve SILME izinle acilmaz: her seferinde sorulur.")


def komut_kural(a) -> None:
    """OFIS KURALLARI -- her brifinge KOSULSUZ girer, yalniz insandan.

    Kural bir politika kararidir: her ajanin her turuna girer ve her
    turda odenir. Bu yuzden gerekce zorunlu, kaldirma sebebi zorunlu, ve
    ikisi de karar gunlugune yazilir.
    """
    from .bellek import BellekHatasi
    ofis = ofis_ac(a.db, a.proje)
    bel = ofis.bellek
    try:
        if a.eylem == "ekle":
            if not a.metin:
                raise SystemExit("kullanim: kural ekle METIN --gerekce ...")
            r = bel.kural_ekle(a.metin, a.gerekce)
            yaz(f"kural eklendi: {r['metin']}")
        elif a.eylem == "yukselt":
            if a.olgu:
                r = bel.olgudan_kural(a.olgu, a.gerekce)
            elif a.ders:
                r = bel.dersten_kural(a.ders, a.gerekce)
            else:
                raise SystemExit("kullanim: kural yukselt --olgu KONU | "
                                 "--ders DERS_ID --gerekce ...")
            yaz(f"kurala yukseltildi: {r['metin']}")
        elif a.eylem == "kaldir":
            if not a.metin:
                raise SystemExit("kullanim: kural kaldir KURAL_ID --sebep ...")
            r = bel.kural_kaldir(a.metin, a.sebep)
            yaz(f"kural kaldirildi: {r['metin']}")
            return
    except BellekHatasi as exc:
        raise SystemExit(str(exc))
    kurallar = bel.kurallar()
    yaz(f"OFIS KURALLARI ({len(kurallar)}) -- her brifinge girer:")
    for k in kurallar:
        yaz(f"  {k['id'][:8]}  {k['metin']}  [{k['kaynak_tur']}]")
    m = bel.kural_maliyeti()
    yaz(f"  yuk: ~{m['jeton_yaklasik']} jeton / brifing"
        + ("  -- UYARI: kural blogu buyudu, her turda odeniyor" if m["uyari"]
           else ""))
    adaylar = bel.kural_adaylari()
    if adaylar:
        yaz("ADAYLAR (tekrarlayan dersler -- kural yukselt --ders ID):")
        for d in adaylar:
            yaz(f"  {d['id'][:8]}  {d['ajan_ad']} x{d['tekrar']}: "
                f"{' '.join(d['ders'].split())[:160]}")


def komut_video(a) -> None:
    """Elle video uretir / saglayici durumunu gosterir / insanin urettigini alir.

    `komut_gorsel`in kardesi, ve `ekle` eylemi ONUN KADAR onemli degil --
    DAHA onemli: olculdu ki videoda ucretsiz bir API katmani YOK. Ajanin
    `video_iste` araci insanin kuyruguna bir komut birakiyor ve o komut
    BU. Komut olmasaydi arac, calismayan bir talimat verirdi -- ofisin
    bir kez odedigi hata (`gorsel.py`nin kapali dongusu: kod kasaya
    bakmadigi icin kendi verdigi talimat izlendiginde bile calismiyordu).
    """
    from ofis import video as _video
    gizli.yukle()

    if a.eylem == "durum":
        for ad, b in _video.musait_ureticiler().items():
            etiket = "MUSAIT" if b["musait"] else "yok"
            yaz(f"  {ad:12} {etiket:7} (${b['saniye_basi_usd']}/sn)")
            if b["sebep"]:
                for satir in b["sebep"].split(". "):
                    if satir.strip():
                        yaz(f"      {satir.strip()}")
        yaz("")
        yaz("Tercih sirasi: " + " -> ".join(_video.TERCIH_SIRASI)
            + "  (once UCUZ olan denenir)")
        # Ucretsizlik iddia ETMIYORUZ. `gorsel.py`de siralama "once
        # ucretsiz"di; burada olculdu ki ucretsiz katman yok, ve olmayan
        # bir seye gore siralamak kullaniciya olmayan bir guvence vermek
        # olurdu.
        yaz("UCRETSIZ KATMAN YOK -- her uretim para. Ucretsiz tek yol")
        yaz("tuketici arayuzleri (orn. Google Flow); ajanlar onu")
        yaz("`video_iste` ile SANA birakir.")
        return

    if a.eylem == "ekle":
        # INSANIN urettigi videoyu tahtaya KANIT olarak koyar.
        # Dosyanin varligi OLCULUR, iddia edilmez (`gorsel ekle` ile ayni).
        from pathlib import Path as _P
        import shutil as _sh
        if not a.istem:
            raise SystemExit("Hangi dosya? Ornek: video ekle C:/indirilenler/a.mp4 --gorev 7")
        kaynak = _P(a.istem).expanduser()
        if not kaynak.is_file():
            raise SystemExit(f"Dosya yok: {kaynak}")
        if a.gorev is None:
            raise SystemExit("--gorev <no> gerekli: kanit hangi ise ait?")
        ofis = ofis_ac(a.db, a.proje)
        g = ofis.tahta.gorev(a.gorev)
        sahip = g["sahip"] or "insan"
        kok = _P(ofis.kadro.ajan(sahip)["klasor"]) if g["sahip"] else _P(ofis.isin_koku(g))
        alanlar = g["yazma_alani"] or []
        try:
            hedef = medya_hedefi(kok, alanlar, a.ad or kaynak.name)
        except TahtaHatasi as exc:
            raise SystemExit(f"Eklenmedi: {exc}")
        hedef.parent.mkdir(parents=True, exist_ok=True)
        _sh.copy2(kaynak, hedef)
        ofis.tahta.kanit_ekle(
            g["no"], "gorsel", str(hedef),
            f"VIDEO, insan tarafindan uretildi ve ofise alindi "
            f"({hedef.stat().st_size} bayt).",
            sahip)
        yaz(f"Alindi: {hedef}")
        yaz(f"  #{g['no']} icin KANIT olarak yazildi.")
        yaz("")
        yaz("Bekleyen onay varsa kapat:  python -m ofis.kabuk bekleyen")
        yaz("Sonra halkayi dondur:       python -m ofis.kabuk devam")
        return

    if not a.istem:
        raise SystemExit('Istem gerekli. Ornek: video uret "denizde gun batimi" --saniye 8')
    hedef = a.cikti or "video.mp4"
    try:
        sonuc = _video.uret(a.istem, hedef, saniye=a.saniye,
                            uretici=a.uretici or "", model=a.model or "",
                            cozunurluk=a.cozunurluk,
                            tavan_usd=(a.tavan if a.tavan is not None
                                       else _video.VARSAYILAN_TAVAN_USD))
    except _video.ButceAsimi as exc:
        # Ayri sinif, ayri cikis mesaji: bu bir arizanin degil bir
        # KARARIN sonucu. "Tekrar dene" demek yanlis yonlendirme olurdu.
        raise SystemExit(f"TAVAN:{chr(10)}{exc}")
    except _video.VideoHatasi as exc:
        raise SystemExit(f"Uretilemedi:{chr(10)}{exc}")
    yaz(f"Uretildi: {sonuc['yol']}")
    tahmin = sonuc.get("tahmini_maliyet_usd")
    yaz(f"  {sonuc.get('uretici', '')}/{sonuc.get('model', '')} · "
        f"{sonuc['bayt']} bayt"
        + (f" · ~${tahmin}" if tahmin is not None else ""))


def _hesap_canli(a) -> None:
    """CANLI durum: CLI'lar su an HANGI hesaba girisli. Anahtar BASILMAZ.

    `hesap liste` TANIMLI hesaplari gosterir (ofisin defterinden);
    bu ise makinenin GERCEK halini olcer. Ikisi ayri sorudur ve ikisi
    de gerekli: defterde yazan bir hesap, CLI'da girisli olmayabilir.
    """
    from pathlib import Path as _Path
    from ofis.motor.codex import CodexMotoru

    yaz("CODEX")
    ofis_evi = CodexMotoru._ev_bul()
    o = _codex_hesabi(ofis_evi)
    yaz(f"  ofis evi : {ofis_evi}")
    if o["girisli"]:
        yaz(f"  hesap    : {o.get('eposta')}  (plan: {o.get('plan')})")
    else:
        yaz("  hesap    : GIRIS YAPILMAMIS")
        yaz("  girmek icin (PowerShell):")
        yaz(f'    $env:CODEX_HOME = "{ofis_evi}"')
        yaz('    mkdir $env:CODEX_HOME -Force')
        yaz("    codex login")

    # Varsayilan ev SADECE BILGI olarak gosterilir -- ofis oraya
    # DOKUNMAZ. Kullanicinin baska bir isine bagli olabilir ve iki
    # sistemin ayni aboneligi paylasmasi, limitin nerede bittigini
    # gorunmez kilar.
    varsayilan = str(_Path.home() / ".codex")
    if varsayilan != ofis_evi:
        v = _codex_hesabi(varsayilan)
        yaz("")
        yaz(f"  (bilgi) varsayilan ev: {varsayilan}")
        yaz(f"  (bilgi) oradaki hesap: "
            + (f"{v.get('eposta')}" if v["girisli"] else "giris yok")
            + " -- OFIS BURAYA DOKUNMAZ")

    yaz("")
    yaz("GEMINI")
    anahtarlar = {k["ad"]: k for k in gizli.liste()}
    if "GEMINI_API_KEY" in anahtarlar or os.environ.get("GEMINI_API_KEY"):
        kayit = anahtarlar.get("GEMINI_API_KEY")
        nereden = "depo" if kayit else "ortam degiskeni"
        iz = f"  ({kayit['parmak_izi']})" if kayit else ""
        yaz(f"  anahtar  : KURULU [{nereden}]{iz}")
    else:
        yaz("  anahtar  : YOK")
        yaz("  eklemek icin:")
        yaz("    python -m ofis.kabuk anahtar ekle GEMINI_API_KEY")

    yaz("")
    yaz("CLAUDE")
    yaz("  bu oturumun hesabi kullaniliyor (ayri kimlik gerekmez)")


def komut_kullanim(a) -> None:
    """Hangi hesap bagli, OFIS ne tuketti, ne zaman yenilenir.

    Kullanicinin istegi: *"hangi hesap bagli, limitleri ne durumda,
    anlik kullanimi, ne zaman yenilenecegini takip edebilecegim bir
    alan."*

    `yetenek` ile farki bilincli: `yetenek` "neyi YAPABILIRIZ" diye
    sorar (duragan), bu komut "ne TUKETTIK" diye sorar (akan). Tek
    ekrana koymak, ayda bir degisenle her tur degiseni karistirirdi.
    """
    from ofis import kullanim
    from ofis.zincir import ONCEDEN_GECIS_ESIKLERI
    ofis = ofis_ac(a.db, a.proje)
    # ONCEDEN GECIS AYARI. Bozuk deger REDDEDILIR (yazilmaz): yazilsaydi
    # kurucu onu varsayilana dusurup uyarirdi ama insan ayarladigini sanirdi.
    for ifade in getattr(a, "esik", None) or []:
        anahtar, _, deger = ifade.partition("=")
        rol, _, pencere = anahtar.partition(":")
        try:
            sayi = float(deger)
        except ValueError:
            sayi = -1
        if (rol not in ONCEDEN_GECIS_ESIKLERI or pencere not in ("5s", "7g")
                or not 0 < sayi <= 1):
            raise SystemExit(
                f"gecersiz esik: {ifade!r} -- bicim ROL:PENCERE=ORAN, "
                "ROL isci|lider, PENCERE 5s|7g, ORAN 0-1 arasi (or. isci:5s=0.8)")
        ofis.db.ayar_yaz(ofis.proje_id, f"gecis_esigi:{rol}:{pencere}", str(sayi))
        yaz(f"esik yazildi: {rol} {pencere} -> %{round(sayi * 100)}")
    if getattr(a, "gecis", None):
        ofis.db.ayar_yaz(ofis.proje_id, "onceden_gecis",
                         "kapali" if a.gecis == "kapat" else "acik")
        yaz(f"onceden gecis: {'KAPALI' if a.gecis == 'kapat' else 'ACIK'}")
    # Insan baktiginda sayi CANLI olsun -- saglayicidan okunur, kota harcamaz.
    t = kullanim.tazele(ofis.db, ofis.proje_id, zorla=True)
    if t.get("okundu"):
        yaz(f"limitler saglayicidan okundu: {', '.join(t['okundu'])}")
    for s in t.get("okunamadi") or []:
        yaz(f"  okunamadi -- {s} (eski olcum yasiyla gosteriliyor)")
    yaz(kullanim.metin(ofis.db, ofis.proje_id))


def komut_yetenek(a) -> None:
    """Ofis NEYI yapabilir -- tek ekran, hepsi OLCULMUS.

    `saglik` "su an tikanan bir sey var mi" diye sorar (anlik, ise
    bakar). Bu komut "bu ofis neyi yapabilir" diye sorar (duragan,
    donanima bakar). Ikisini tek ekrana koysaydik, her gun degisen sey
    ile ayda bir degisen sey karisir ve insan ikisine de bakmayi
    birakirdi.

    SAHIPLIK gosterilir: ofisin ekleyip silebildigi seyler ile yalnizca
    OLCEBILDIGI seyler ayni sekilde gosterilmez. "Bagla" diyip arkada
    hicbir sey yapamamak, yanlis gosteren bir gostergedir.
    """
    ofis = ofis_ac(a.db, a.proje)
    if not a.hizli:
        yaz("Olculuyor (baglayici saglik denetimi ~15 sn surer)...")
        yaz("")
    r = ofis_yetenek(ofis, baglayici_dahil=not a.hizli)
    IM = {"hazir": "[+]", "dar": "[~]", "yok": "[-]", "bilinmiyor": "[?]"}
    for g in r["gruplar"]:
        sahip = ("ofis yonetir -- ekleyip silebilirsin"
                 if g["sahiplik"] == "ofis"
                 else "OLCULUR, yonetilmez -- komut sende")
        yaz("")
        yaz(f"{g['ad'].upper()}  ({sahip})")
        for st in g["satirlar"]:
            yaz(f"  {IM.get(st['durum'], '[ ]')} {st['ad']:26} {st['not'][:46]}")
            if st["care"]:
                yaz(f"        -> {st['care']}")
    sy = r["sayim"]
    yaz("")
    yaz(f"{sy.get('hazir', 0)} hazir · {sy.get('dar', 0)} dar · "
        f"{sy.get('yok', 0)} yok · {sy.get('bilinmiyor', 0)} bilinmiyor")


def komut_saglik(a) -> None:
    """Ofis KENDI tikandigini fark etsin.

    `durum` ne oldugunu SAYAR; bu komut o sayilarin ANLAMLI olup
    olmadigini sorar. Olculdu: bir is `calisiyor` gorunuyordu, lider
    "tamamlaninca sunacagim" diyordu ve hicbir sey onu ilerletmeyecekti
    -- tabloda her sey normaldi.
    """
    ofis = ofis_ac(a.db, a.proje)
    r = ofis.saglik.denetle()
    if not r["bulgular"]:
        yaz("SAGLIKLI -- tikanan is yok, senden beklenen yok.")
        return
    simge = {"tikali": "[TIKALI]", "insan": "[SENDEN]",
             "uyari": "[UYARI ]", "bilgi": "[BILGI ]"}
    for b in r["bulgular"]:
        yaz(f"{simge.get(b['agirlik'], '[?]')} {b['baslik']}")
        if b["ayrinti"]:
            yaz(f"          {b['ayrinti']}")
        yaz(f"          -> {b['care']}")
        yaz("")
    yaz(f"{r['tikali']} tikali, {r['insan']} senden bekleniyor.")


def komut_durum(a) -> None:
    _durum_yaz(ofis_ac(a.db, a.proje))


def komut_bekleyen(a) -> None:
    ofis = ofis_ac(a.db, a.proje)
    sorular = ofis.postane.insan_bekleyenler()
    onaylar = ofis.postane.bekleyen_onaylar()
    if not sorular and not onaylar:
        yaz("Senden beklenen bir sey yok.")
        return
    for s in sorular:
        yaz(f"[soru] {s['id'][:8]}  {s['gonderen']}"
            + (f" (#{s['gorev_no']})" if s["gorev_no"] else ""))
        yaz(f"       {s['govde']}")
        yaz(f"       cevapla: python -m ofis.kabuk cevapla {s['id'][:8]} \"...\"")
    from ofis import giris as _giris
    for o in onaylar:
        v = _giris.ayristir(o)
        if v is not None:
            yaz(f"[giris] {o['id'][:8]}  {o['isteyen']}  #{o.get('gorev_no') or '?'}"
                f"  {v['hizmet']} ({v['tur']})")
            if v.get("adres"):
                yaz(f"       adres : {v['adres']}")
            yaz(f"       neden : {v['neden']}")
            yaz(f"       yap   : {_giris.insan_talimati(v)}")
            yaz(f"       yaptim: python -m ofis.kabuk onayla {o['id'][:8]}")
            yaz(f"       yapamam: python -m ofis.kabuk onayla {o['id'][:8]} "
                "--hayir --not \"gerekce\"")
            continue
        yaz(f"[onay] {o['id'][:8]}  {o['isteyen']}  risk: {o['risk']}")
        yaz(f"       {o['eylem']}")
        if o["ayrinti"]:
            yaz(f"       {o['ayrinti']}")
        yaz(f"       onayla : python -m ofis.kabuk onayla {o['id'][:8]}")
        yaz(f"       reddet : python -m ofis.kabuk onayla {o['id'][:8]} "
            "--hayir --not \"gerekce\"")


def komut_cevapla(a) -> None:
    ofis = ofis_ac(a.db, a.proje)
    tam = _kimlik_coz(ofis.postane.insan_bekleyenler(), a.kimlik, "soru")
    try:
        ofis.postane.cevapla(tam, a.metin)
    except PostaneHatasi as exc:
        raise SystemExit(f"Cevaplanamadi: {exc}")
    yaz("Cevap iletildi. Halkayi surdurmek icin:")
    yaz("  python -m ofis.kabuk devam")


def komut_onayla(a) -> None:
    ofis = ofis_ac(a.db, a.proje)
    bekleyen = ofis.postane.bekleyen_onaylar()
    tam = _kimlik_coz(bekleyen, a.kimlik, "onay")
    from ofis import giris as _giris
    kayit = next((o for o in bekleyen if o["id"] == tam), None)
    if kayit and _giris.giris_mi(kayit):
        # GIRIS: "yaptim" olculur, is kabine/baglayiciya tasinir.
        try:
            _giris.cevapla(ofis, tam, yapildi=not a.hayir, not_=a.not_ or "")
        except _giris.GirisHatasi as exc:
            raise SystemExit(f"Cevaplanamadi: {exc}")
        yaz("Giris yapildi olarak isaretlendi." if not a.hayir
            else "Giris yapilmadi; gerekce ajana iletilecek.")
        yaz("Halkayi surdurmek icin:")
        yaz("  python -m ofis.kabuk devam")
        return
    kapsam = "is" if getattr(a, "is_boyunca", False) else "eylem"
    try:
        sonuc = ofis.postane.onay_cevapla(tam, onayla=not a.hayir,
                                          not_=a.not_ or "", kapsam=kapsam)
    except PostaneHatasi as exc:
        raise SystemExit(f"Cevaplanamadi: {exc}")
    # KAPSAM BASILIR. Basmayan cikti, sessizce genisleyen bir yetkiyi
    # fark ettirmez -- `--rol` bayraginda bir kez odenmisti.
    if sonuc["durum"] == "onaylandi":
        if sonuc.get("kapsam") == "is":
            yaz("Onaylandi -- BU IS BOYUNCA. Ayni eylem tekrar sorulmayacak.")
        else:
            yaz("Onaylandi -- BIR KEZ. Ayni eylem tekrar gerekirse yeniden "
                "sorulur.")
    else:
        yaz("Reddedildi. Gerekce ajana iletilecek.")
    yaz("Halkayi surdurmek icin:")
    yaz("  python -m ofis.kabuk devam")


def komut_tasi(a) -> None:
    """TASI (01.10.2026 ayrim): ofisin evi AgentOfis\\ev'e, projeler masaustune.

    Varsayilan DENEME: hicbir seye dokunmaz, plani gosterir. `--uygula` ile
    tasir (panel KAPALI olmali). Eski yerler silinmez.
    """
    from ofis import tasima as T
    pl = T.plan(a.db)
    ev = pl["ev"]
    yaz("TASIMA PLANI" + ("" if a.uygula else " (DENEME -- hicbir seye dokunulmadi)"))
    if ev["gerekli"]:
        yaz(f"  ev: {ev['kaynak']} -> {ev['hedef']} ({ev['boyut'] / 1e9:.2f} GB, KOPYA; eski yerinde kalir)")
    else:
        yaz(f"  ev: tasima gerekmiyor ({ev['hedef']})")
    for x in pl["projeler"]:
        yaz(f"  proje {x['ad']}: {x['eski']} -> {x['hedef']} ({len(x['dosyalar'])} dosya, "
            f"{x['boyut'] / 1e6:.1f} MB)")
        if x["arsiv"]:
            yaz("    eski brifingler evin arsivine: " + ", ".join(g for g, _ in x["arsiv"]))
        if x["ajanlar"]:
            yaz("    klasoru cevrilecek ajanlar: " + ", ".join(x["ajanlar"]))
    if not pl["projeler"]:
        yaz("  ofisin icinde koku olan proje yok.")
    for e in pl["engeller"]:
        yaz(f"  [ENGEL] {e}")
    if not a.uygula:
        yaz("Uygulamak icin: python -m ofis.kabuk tasi --uygula")
        return
    try:
        r = T.uygula(pl)
    except T.TasimaHatasi as exc:
        raise SystemExit(f"Tasima: {exc}")
    yaz("TASINDI.")
    yaz(f"  defter yedegi: {r['db_yedek']}")
    if r["ev"]:
        yaz(f"  ev: {r['ev']}")
    for x in r["projeler"]:
        yaz(f"  {x}")
    yaz("  geri donus:")
    for g in r["geri_donus"]:
        yaz(f"    - {g}")
    yaz("Paneli yeniden ac: baslat.bat")


def komut_yedek(a) -> None:
    """YEDEK: al, listele, dogrula, geri yukle, hedef yonet.

    Geri yukleme CANLI klasorun uzerine yazmaz -- bos bir klasore acar.
    Canliyi degistirmek insanin karari ve once yeni klasorde denenir.
    """
    from ofis import yedek as Y
    try:
        if a.eylem == "al":
            s = Y.al(a.neden or "elle")
            yaz(f"Yedek alindi: {s['arsiv']}")
            yaz(f"  {s['dosya']} dosya · {s['boyut'] / 1e6:.1f} MB · "
                f"{len(s['db'])} defter (butunluk: "
                + ", ".join(d["butunluk"] for d in s["db"]) + ")")
            if s["sirlar_atlandi"]:
                yaz("  SIR oldugu icin ALINMADI: " + ", ".join(s["sirlar_atlandi"]))
            for o in s["okunamayan"]:
                yaz(f"  [!] okunamadi: {o}")
            for h in s["hedefler"]:
                yaz(f"  hedef {h['klasor']}: {h['durum']}"
                    + (f" -- {h['hata']}" if h["hata"] else ""))
            if not s["hedefler"]:
                yaz("  ek hedef yok (bulut kopyasi YOK) -- "
                    "`yedek hedef ekle --hedef <klasor>`")
            for b in s["budanan"]:
                yaz(f"  budandi: {b}")
        elif a.eylem == "liste":
            ayar = Y.ayar_oku()
            yaz(f"Yedek klasoru: {Y.yedek_koku()}")
            for h in ayar["hedefler"]:
                var = "var" if Path(h).is_dir() else "ULASILAMIYOR"
                yaz(f"  ek hedef: {h} ({var})")
            if not ayar["hedefler"]:
                yaz("  ek hedef yok (bulut kopyasi YOK)")
            saat = Y.son_yedek_saat()
            yaz("  son yedek: " + ("hic alinmadi" if saat == float("inf")
                                  else f"{saat:.1f} saat once"))
            for p in Y.arsivler():
                yaz(f"  {p.name}  {p.stat().st_size / 1e6:.1f} MB")
        elif a.eylem == "dogrula":
            yol = Path(a.yol) if a.yol else (Y.arsivler() or [None])[-1]
            if not yol:
                raise SystemExit("Dogrulanacak yedek yok.")
            d = Y.dogrula(yol)
            yaz(f"{yol.name}: " + ("SAGLAM" if d["tamam"] else "BOZUK"))
            for b in d["bulgular"][:20]:
                yaz(f"  {b}")
        elif a.eylem == "geri-yukle":
            if not a.yol or not a.hedef:
                raise SystemExit("kullanim: yedek geri-yukle <arsiv> --hedef <bos klasor>")
            r = Y.geri_yukle(Path(a.yol), Path(a.hedef))
            yaz(f"{r['dosya']} dosya acildi: {r['hedef']} ({r['zaman']} yedegi)")
            yaz("  Canli ofis DEGISMEDI. Once bu klasorde dene; sonra "
                "canliyla degistirmek senin kararin.")
        elif a.eylem == "metinden":
            # Defteri GitHub'daki metin dokumunden kurar -- BOS yere, olculerek
            # (27.09: proje klasoru silindi, elle kurulum iki hata yapti).
            from ofis import depo
            if not a.hedef:
                raise SystemExit("kullanim: yedek metinden [dokum.sql] --hedef <yeni defter yolu> [--surum N]")
            kaynak = Path(a.yol) if a.yol else depo.PROJE_KOKU / depo.DISARI
            try:
                r = depo.metinden_defter(kaynak, Path(a.hedef), surum=a.surum)
            except depo.DepoHatasi as exc:
                raise SystemExit(f"Geri kurulum: {exc}")
            yaz(f"Defter kuruldu: {r['hedef']} (butunluk ok, metin BIREBIR geri geldi)")
            yaz("  " + ", ".join(f"{t} {n}" for t, n in sorted(r["tablo"].items()) if n))
            if r["surum_kaynagi"] == "yok":
                yaz("  DIKKAT: dokumde veri gocu surumu yok -- gocler bir sonraki acilista "
                    "YENIDEN kosar. Biliyorsan --surum N ile ver.")
            else:
                yaz(f"  veri gocu surumu {r['surum']} ({r['surum_kaynagi']})")
            yaz("  Canli ofis DEGISMEDI. Degistirmek senin kararin.")
        elif a.eylem == "github":
            from ofis import depo
            try:
                d = depo.gonder(a.neden or "elle")
            except depo.DepoHatasi as exc:
                raise SystemExit(f"GitHub: {exc}")
            yaz(f"GitHub: {d['durum']}" + (f" -- {d['sebep']}" if d.get("sebep") else "")
                + (f" ({d['dosya']} dosya, {d['commit']})" if d.get("commit") else ""))
        elif a.eylem == "hedef":
            if a.yol == "ekle" and a.hedef:
                yaz(f"Ek hedef eklendi: {Y.hedef_ekle(a.hedef)}")
            elif a.yol == "cikar" and a.hedef:
                yaz("Cikarildi." if Y.hedef_cikar(a.hedef) else "Boyle bir hedef yok.")
            else:
                raise SystemExit("kullanim: yedek hedef ekle|cikar --hedef <klasor>")
    except Y.YedekHatasi as exc:
        raise SystemExit(f"Yedek: {exc}")


def komut_geri_al(a) -> None:
    """Bir ajan TURUNUN diskte yaptigini -- yalniz onu -- geri alir.

    Yedek butun ofisi bir gune dondurur; bu yalniz o turun dokundugu
    dosyalari. Geri alma da yeni bir kayit olur, o da geri alinabilir.
    """
    from ofis import geri_al as G
    from ofis import degisim
    ofis = ofis_ac(a.db, a.proje)
    if a.kimlik in (None, "liste"):
        kayitlar = G.liste(ofis.db, ofis.proje_id, limit=a.limit)
        if not kayitlar:
            yaz("Geri alinabilir tur yok (dosya degistiren tur olmadi).")
            return
        for k in kayitlar:
            is_ = (f"#{k['gorev_no']} {k['gorev_baslik'][:40]}"
                   if k.get("gorev_no") else "-")
            durum = f"  [GERI ALINDI {k['geri_alindi']}]" if k["geri_alindi"] else ""
            belirsiz = "  (paralel tur)" if k["atif_belirsiz"] else ""
            yaz(f"{k['id'][:8]}  {k['olusturuldu'][:16]}  {k['ajan_ad']:<18} "
                f"{k['dosya']} dosya  {is_}{belirsiz}{durum}")
        yaz("")
        yaz("Geri almak: geri-al <kimlik> --sebep \"...\"   (once: --goster)")
        return
    try:
        k = G.bul(ofis.db, ofis.proje_id, a.kimlik)
        golge = G.Golge(k["kok"], degisim.ofis_dosyalari(ofis.db.yol))
        if a.goster:
            yaz(f"{k['id'][:8]} -- {k['ajan_ad']} -- {k['olusturuldu'][:16]}")
            ad = {"A": "EKLEDI (geri alinca SILINIR)",
                  "M": "DEGISTIRDI (eski haline doner)",
                  "D": "SILDI (geri gelir)"}
            for hal, yol in golge.fark(k["once"], k["sonra"]):
                yaz(f"  {ad.get(hal, hal):32s} {yol}")
            return
        r = G.geri_al(ofis, a.kimlik, sebep=a.sebep or "", zorla=a.zorla,
                      haric=degisim.ofis_dosyalari(ofis.db.yol))
    except G.GeriAlHatasi as exc:
        raise SystemExit(f"Geri alinmadi: {exc}")
    yaz(f"{len(r['dosyalar'])} dosya geri alindi:")
    for hal, yol in r["dosyalar"]:
        yaz(f"  {hal:18s} {yol}")
    for y in r["sonradan_ezilen"]:
        yaz(f"  DIKKAT: turdan sonraki degisiklik de gitti: {y}")
    yaz(f"Bunu da geri almak icin: geri-al {r['yeni_kayit'][:8]} --sebep \"...\"")


def komut_panel(a) -> None:
    from ofis.panel import kos
    yaz(f"Panel: http://{a.adres}:{a.kapi}")
    kos(a.adres, a.kapi, a.db, a.proje)


# ---------------------------------------------------------------------------
# yardimcilar
# ---------------------------------------------------------------------------

def _tik_yaz(adim) -> None:
    """Orkestranin TEK adimini insan diline cevirip basar.

    `hedef` ve `konus` ayni halkayi dondurur; iki ayri yazici olsaydi
    biri duzeltilip oteki unutulurdu.
    """
    if adim.get("bitti"):
        yaz("")
        yaz(f"DURDU: {adim['sebep']}")
        for b in adim.get("bekleyen", []):
            yaz(f"  [{b['tur']}] {b['kim']}: {b['metin'][:160]}")
        for e in adim.get("engel", []):
            yaz(f"  [engel] {e}")
        return
    yaz(f"-- {adim['tik']}. tur")
    for i in adim["baslatilan"]:
        durum = "tamam" if i.get("basarili") else "BASARISIZ"
        yaz(f"   {i['ajan']} -> #{i['no']}  ({durum}, {i.get('kanit', 0)} kanit)")
    for i in adim["incelenen"]:
        yaz(f"   lider #{i['no']}: {i['hukum'].upper()}"
            + (f" -- {i['gerekce'][:120]}" if i["gerekce"] else ""))
    for b in adim["bekleyen"]:
        yaz(f"   BEKLIYOR [{b['tur']}] {b['kim']}: {b['metin'][:120]}")
    for e in adim["engel"]:
        yaz(f"   engel: {e}")


from . import tarayici as tarayici_modulu  # noqa: E402


def _kabin_ucnoktasi(a) -> str:
    """`--kabin` istendiyse CDP ucnoktasi, yoksa bos.

    KABIN KAPALIYSA IS REDDEDILIR. Sessizce ayri bir tarayici acsaydik
    kullanici "ajan benim tarayicimda calisiyor" sanirdi ve baska bir
    yerde kosan bir turu izlemeye calisirdi -- yanlis gosteren
    gostergenin en sinsi turu: dogru gorunur.
    """
    if not getattr(a, "kabin", False):
        return ""
    from . import kabin as _kb
    if not _kb.acik_mi():
        raise SystemExit(
            "--kabin istendi ama kabin KAPALI. Panelden 'tarayıcı' "
            "dugmesiyle ac, sonra tekrar dene.")
    return tarayici_modulu.cdp_adresi()


def _dongu_yaz(ofis, a) -> None:
    # TEK KOSUCU. `hedef` ve `devam` ayni halkayi dondurur; iki ayri
    # kopya olsaydi biri duzeltilir oteki unutulurdu -- bu projede o
    # hata alti kez cikti. Yeni bayraklar `getattr` ile okunuyor cunku
    # her komut hepsini tanimlamiyor (`konus`ta tarayici alani zaten
    # yok, dolayisiyla gorunurlugun de anlami yok).
    for adim in ofis.orkestra.kos(azami_tik=a.azami_tik, butce_usd=None,
                                  zaman_asimi=a.zaman_asimi,
                                  izinli_araclar=tuple(getattr(a, "izin", None) or ()),
                                  paralel=getattr(a, "paralel", 3),
                                  tarayici_gorunur=bool(
                                      getattr(a, "tarayici_gorunur", False)),
                                  tarayici_profili=str(
                                      getattr(a, "tarayici_profili", "") or ""),
                                  tarayici_kabini=_kabin_ucnoktasi(a)):
        _tik_yaz(adim)
        if adim.get("bitti"):
            return


def _kanatlar(ofis) -> list:
    with ofis.db.baglanti() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM kanat WHERE proje_id = ? ORDER BY olusturuldu",
            (ofis.proje_id,)).fetchall()]


def _kok_klasor(ofis) -> str:
    # Kural cekirdekte (`Ofis.kok_klasoru`); panel de ayni yeri cagirir.
    return ofis.kok_klasoru()


def _kimlik_coz(liste, onek: str, tur: str) -> str:
    """Kisa kimligi tam kimlige cevirir.

    Tam uuid yazdirmak insana zulumdur; ama iki kayit ayni onekle
    baslarsa TAHMIN EDILMEZ -- yanlis soruyu cevaplamak, yanlis ajani
    yanlis bilgiyle calistirir.
    """
    eslesen = [x for x in liste if x["id"].startswith(onek)]
    if not eslesen:
        raise SystemExit(f"Bekleyen {tur} bulunamadi: {onek}")
    if len(eslesen) > 1:
        raise SystemExit(
            f"'{onek}' birden fazla {tur} ile eslesiyor. Daha uzun yaz.")
    return eslesen[0]["id"]


def _durum_yaz(ofis) -> None:
    gorevler = ofis.tahta.liste()
    sayim = {}
    for g in gorevler:
        sayim[g["durum"]] = sayim.get(g["durum"], 0) + 1
    yaz("DURUM")
    yaz("  isler   : " + (", ".join(f"{v} {k}" for k, v in sayim.items())
                          or "is yok"))
    bekleyen = (len(ofis.postane.insan_bekleyenler())
                + len(ofis.postane.bekleyen_onaylar()))
    if bekleyen:
        yaz(f"  SENDEN BEKLENEN: {bekleyen}  "
            "(python -m ofis.kabuk bekleyen)")
    for g in gorevler:
        if g["durum"] in ("bitti", "iptal"):
            continue
        kanit = len(ofis.tahta.kanitlar(g["no"]))
        yaz(f"  #{g['no']} [{g['durum']}] {g['baslik']}"
            f"  {g['sahip'] or '-'}  {kanit} kanit")


# ---------------------------------------------------------------------------

def ayristirici() -> argparse.ArgumentParser:
    a = argparse.ArgumentParser(
        prog="python -m ofis.kabuk", description="AgentOfis komut satiri")
    a.add_argument("--db", default=None, help="veritabani yolu")
    a.add_argument("--proje", default=None, help="proje adi")
    alt = a.add_subparsers(dest="komut", required=True)

    k = alt.add_parser("kur", help="yeni ofis ac")
    k.add_argument("--ad", required=True)
    k.add_argument("--amac", default="")
    k.add_argument("--olcut", default="", help="basari olcutu")
    k.add_argument("--kapsam-disi", dest="kapsam_disi", default="")
    k.add_argument("--kisitlar", default="")
    k.add_argument("--kanat", default="ANA")
    k.add_argument("--klasor", default="", help="ajanlarin calisma koku")
    k.set_defaults(islev=komut_kur)

    i = alt.add_parser("ise-al", help="ajan ise al")
    i.add_argument("ad")
    i.add_argument("meslek", help="rol kutuphanesinden bir ad "
                                  "(`kabuk roller` ile listele)")
    i.add_argument("--lider", action="store_true")
    # Varsayilan BOS: rol kendi turunu doldursun. Onceden "eller"di ve
    # ROLUN TURUNU HER ZAMAN EZIYORDU -- yani rol tanimi burada sessizce
    # etkisiz kaliyordu. "Sessizce yok sayilan ayar, ayar degildir."
    i.add_argument("--tur", default="", choices=("", "eller", "kafa"),
                   help="bos birak: rol kendi turunu belirler")
    i.add_argument("--motor", default="claude")
    i.add_argument("--model", default="")
    i.add_argument("--efor", default="normal",
                   choices=("dusuk", "normal", "yuksek"))
    i.add_argument("--kanat", default="")
    i.add_argument("--klasor", default="")
    i.add_argument("--kendi-klasoru", dest="kendi_klasoru",
                   action="store_true",
                   help="ortak kok yerine kendi yalitilmis klasorunde calissin")
    i.set_defaults(islev=komut_ise_al)

    s = alt.add_parser("konus", help="LIDERLE KONUS -- ofisin on kapisi")
    s.add_argument("mesaj")
    s.add_argument("--lider", default="")
    s.add_argument("--zaman-asimi", dest="zaman_asimi", type=float, default=None)
    s.add_argument("--azami-tik", dest="azami_tik", type=int, default=8)
    s.add_argument("--paralel", type=int, default=3,
                   help="ayni anda kac is kossun (1 = sirali)")
    s.add_argument("--izin", action="append", default=[], metavar="ARAC")
    s.add_argument("--klasor", action="append", default=[], metavar="YOL",
                   help='ofis DISINDA bir klasoru bu ise ac (tekrarlanabilir), orn: --klasor "C:/Users/pc/Desktop/projem"')
    s.set_defaults(islev=komut_konus)

    h = alt.add_parser("hedef", help="hedef ver, halkayi dondur")
    h.add_argument("hedef")
    h.add_argument("--lider", default="")
    h.add_argument("--zaman-asimi", dest="zaman_asimi", type=float, default=None)
    h.add_argument("--azami-tik", dest="azami_tik", type=int, default=12)
    h.add_argument("--sadece-plan", dest="sadece_plan", action="store_true",
                   help="plani goster, is baslatma")
    # Izin INSAN tarafindan, is basina verilir. Varsayilan liste dar
    # tutulur (motor/claude.py: ELLER_IZINLI); bu isin gerektirdigi fazla
    # yetki buradan acilir ve ACIKCA yazilmis olur.
    h.add_argument("--paralel", type=int, default=3,
                   help="ayni anda kac is kossun (1 = sirali)")
    h.add_argument("--izin", action="append", default=[],
                   metavar="ARAC",
                   help="bu is icin ek izin, orn: --izin \"Bash(codex *)\"")
    h.add_argument("--klasor", action="append", default=[], metavar="YOL",
                   help='ofis DISINDA bir klasoru bu ise ac (tekrarlanabilir), orn: --klasor "C:/Users/pc/Desktop/projem"')
    h.add_argument("--web", action="append", default=[], metavar="URL",
                   help='acilacak web kaynagi (tekrarlanabilir), orn: --web https://rakip.com')
    h.add_argument("--web-salt-okur", dest="web_salt_okur",
                   action="store_true",
                   help="bu isi tarayicida SALT OKUNUR yap: gezer, okur, "
                        "ekran goruntusu alir ama tiklayamaz. VARSAYILAN "
                        "DEGIL -- normalde ajan tiklar ve calisir; riskli "
                        "eylem (yayin, silme, para, gonderim) otomatik olarak "
                        "senin onayina duser. Bunu yalniz tiklamaya HIC gerek "
                        "olmayan islerde kullan (orn. rakip fiyat taramasi).")
    h.add_argument("--sartname", action="store_true",
                   help="kabul olcutlerini KAPI MODELI (fable) denetlesin. "
                        "Zayif bulursa plan lidere geri doner. Tavan zorunlu; "
                        "haftalik pay dolduysa ATLANIR ve soylenir.")
    h.add_argument("--baglayici", action="append", default=[], metavar="AD",
                   help='hesabin claude.ai baglayicisini bu ise ac (tekrarlanabilir), '
                        'orn: --baglayici Shopify. DIKKAT: teknik olarak hesabin TUMU '
                        'yuklenir ve tur ~225k ek jeton yakar; bildirim bir suzgec degil, '
                        'odemeye deger mi kararidir. Liste: `kabuk baglayici`')
    h.add_argument("--tarayici-gorunur", dest="tarayici_gorunur",
                   action="store_true",
                   help="tarayiciyi GORUNUR ac -- ajan tiklarken sen izlersin. "
                        "Varsayilan gizli (headless): daha hizli ve ekrani "
                        "mesgul etmez, ama olup biteni goremezsin.")
    h.add_argument("--tarayici-profili", dest="tarayici_profili", default="",
                   metavar="YOL",
                   help="tarayici profili klasoru -- oturum DISKTE kalir, "
                        "bir kez giris yapinca sonraki turlar girisli baslar. "
                        "Verilmezse yalitilmis: her tur temiz, hicbir sey yazmaz.")
    h.add_argument("--kabin", action="store_true",
                   help="ajan PANELDEKI tarayiciyi kullansin (ayni Chrome). "
                        "Varsayilan KAPALI ve oyle kalmali: kabinde senin "
                        "actigin oturumlar yasar; otomatik baglamak ajana "
                        "cerezlerini sessizce vermek olurdu. Kabin kapaliysa "
                        "is REDDEDILIR -- sessizce ayri tarayici acmaz.")
    h.set_defaults(islev=komut_hedef)

    v = alt.add_parser("devam", help="halkayi kaldigi yerden surdur")
    v.add_argument("--zaman-asimi", dest="zaman_asimi", type=float, default=None)
    v.add_argument("--azami-tik", dest="azami_tik", type=int, default=12)
    v.add_argument("--paralel", type=int, default=3,
                   help="ayni anda kac is kossun (1 = sirali)")
    v.add_argument("--izin", action="append", default=[], metavar="ARAC")
    v.add_argument("--tarayici-gorunur", dest="tarayici_gorunur",
                   action="store_true",
                   help="tarayiciyi GORUNUR ac -- ajan tiklarken sen izlersin. "
                        "Varsayilan gizli (headless): daha hizli ve ekrani "
                        "mesgul etmez, ama olup biteni goremezsin.")
    v.add_argument("--tarayici-profili", dest="tarayici_profili", default="",
                   metavar="YOL",
                   help="tarayici profili klasoru -- oturum DISKTE kalir, "
                        "bir kez giris yapinca sonraki turlar girisli baslar. "
                        "Verilmezse yalitilmis: her tur temiz, hicbir sey yazmaz.")
    v.add_argument("--kabin", action="store_true",
                   help="ajan PANELDEKI tarayiciyi kullansin (ayni Chrome). "
                        "Varsayilan KAPALI ve oyle kalmali: kabinde senin "
                        "actigin oturumlar yasar; otomatik baglamak ajana "
                        "cerezlerini sessizce vermek olurdu. Kabin kapaliysa "
                        "is REDDEDILIR -- sessizce ayri tarayici acmaz.")
    v.set_defaults(islev=komut_devam)

    ek = alt.add_parser("ekip", help="EKIP ONERISI -- lider onerir, sen onaylarsin")
    ek.add_argument("eylem", choices=["oner", "liste", "kur", "red", "sablon"])
    ek.add_argument("istek", nargs="?", default="",
                    help="`oner` icin: ne yapilacak")
    ek.add_argument("--no", type=int, default=None,
                    help="`kur`/`red` icin oneri numarasi")
    ek.add_argument("--sebep", default="", help="`red` icin ZORUNLU gerekce")
    ek.add_argument("--lider", default="")
    ek.add_argument("--zaman-asimi", dest="zaman_asimi", type=float, default=None)
    ek.add_argument("--klasor", default="", help="ajanlarin calisma koku")
    ek.add_argument("--kanat", default="",
                    help="`sablon` icin: hangi takima (kanat kimligi)")
    ek.set_defaults(islev=komut_ekip)

    hs = alt.add_parser("hesap", help="HESAPLAR -- motor kimin adina konussun")
    hs.add_argument("eylem", choices=["liste", "durum", "ekle", "ac", "kapat", "sinir"])
    hs.add_argument("--aylik-sinir", dest="aylik_sinir", type=float, default=None,
                    help="YALNIZ API hesabi: ayda en cok $ (zorunlu). "
                         "Abonelikte dolar yok -- limit saglayicinin yuzdesi.")
    hs.add_argument("ad", nargs="?", default="")
    hs.add_argument("--motor", default="claude")
    hs.add_argument("--tur", default="abonelik", choices=["abonelik", "api"])
    hs.add_argument("--plan", default="")
    hs.add_argument("--ortam", action="append", default=[], metavar="A=D",
                    help="ANAHTAR=DEGER; sir icin @gizli:ISIM kullan")
    hs.add_argument("--sira", type=int, default=100,
                    help="nobet zincirindeki sira (kucuk once)")
    hs.add_argument("--not", dest="not_", default="")
    hs.set_defaults(islev=komut_hesap)

    gu = alt.add_parser("guncelle",
                        help="YENI MODEL / CLI -- ofis fark eder, sen onaylarsin")
    gu.add_argument("eylem", choices=["kontrol", "liste", "onayla", "reddet",
                                      "otomatik", "gecmis", "geri-al"])
    gu.add_argument("no", nargs="?", default=None,
                    help="oneri/gecmis numarasi; `otomatik` icin: simdi | ac | kapat")
    gu.add_argument("--kademe", default="", choices=["", "hizli", "standart", "guclu"],
                    help="yeni bir AILE hangi kademeye girsin")
    gu.add_argument("--sebep", default="", help="`reddet` icin ZORUNLU")
    gu.add_argument("--npm-yok", dest="npm_yok", action="store_true",
                    help="npm surum sorgusunu atla (cevrimdisi)")
    gu.set_defaults(islev=komut_guncelle)

    be = alt.add_parser("belge", help="BELGELER -- PDF/Word/Excel yukle, ara, listele")
    be.add_argument("eylem", nargs="?", default="liste",
                    choices=["liste", "yukle", "ara", "kaldir"])
    be.add_argument("deger", nargs="?", default="",
                    help="yukle: dosya yolu · ara: sorgu · kaldir: belge kimligi")
    be.set_defaults(islev=komut_belge)

    bl = alt.add_parser("bilgi", help="HAFIZA -- kalici bilgi ekle / listele")
    bl.add_argument("eylem", nargs="?", default="liste",
                    choices=["liste", "ekle", "gecmis"])
    bl.add_argument("konu", nargs="?", default="")
    bl.add_argument("icerik", nargs="?", default="")
    bl.set_defaults(islev=komut_bilgi)

    ek = alt.add_parser("eksikler", help="ofisin kendi eksik onerileri ve onaylananlar")
    ek.set_defaults(islev=komut_eksikler)

    iz = alt.add_parser("izin", help="patronun onceden verdigi izinler (push, deploy...)")
    iz.add_argument("eylem", nargs="?", default="liste",
                    choices=["liste", "ekle", "kaldir"])
    iz.add_argument("desen", nargs="?", default="",
                    help="`ekle` icin eylem (\"git push origin test\"), "
                         "`kaldir` icin izin kimligi")
    iz.add_argument("--gerekce", default="", help="kalici izin icin ZORUNLU")
    iz.add_argument("--sebep", default="", help="kaldir icin ZORUNLU")
    iz.add_argument("--is", dest="is_no", default="",
                    help="yalniz bu is icin (verilmezse KALICI)")
    iz.set_defaults(islev=komut_izin)

    kr = alt.add_parser("kural", help="OFIS KURALLARI -- her brifinge girer")
    kr.add_argument("eylem", nargs="?", default="liste",
                    choices=["liste", "ekle", "yukselt", "kaldir"])
    kr.add_argument("metin", nargs="?", default="",
                    help="`ekle` icin kural metni, `kaldir` icin kural kimligi")
    kr.add_argument("--gerekce", default="", help="ekle/yukselt icin ZORUNLU")
    kr.add_argument("--sebep", default="", help="kaldir icin ZORUNLU")
    kr.add_argument("--olgu", default="", help="yukselt: bilginin konusu")
    kr.add_argument("--ders", default="", help="yukselt: ders kimligi")
    kr.set_defaults(islev=komut_kural)

    md = alt.add_parser("model", help="kademe -> model haritasi ve EFOR TAVANI")
    md.add_argument("eylem", nargs="?", default="liste",
                    choices=["liste", "ata", "efor-tavani", "efor-modu"])
    md.add_argument("efor", nargs="?", default="",
                    help="efor-tavani: dusuk|normal|yuksek|cok_yuksek · "
                         "efor-modu: zorluk|dusuk|normal|yuksek|cok_yuksek")
    md.add_argument("--motor", default="")
    md.add_argument("--kademe", default="", choices=["", "hizli", "standart", "guclu"])
    md.add_argument("--model", default="")
    md.set_defaults(islev=komut_model)

    pl = alt.add_parser("plan", help="ABONELIK PLANI -- tavanlar buradan olceklenir")
    pl.add_argument("--claude", default="", choices=["", "pro", "max5", "max20"])
    pl.add_argument("--gpt", default="", choices=["", "plus", "pro100", "pro200"])
    pl.add_argument("--tavansiz-kapi", dest="tavansiz_kapi", default="",
                    choices=["", "ac", "kapat"],
                    help="tavan uygulanamayan kapi modeline (astra) izin")
    pl.set_defaults(islev=komut_plan)

    rl = alt.add_parser("roller", help="ROL KUTUPHANESI -- hangi rol ne is yapar")
    rl.add_argument("--rol", default="", help="tek bir rolun ayrintisi")
    rl.set_defaults(islev=komut_roller)

    aj = alt.add_parser("ajan", help="kadroyu gor / ajanin motorunu degistir")
    aj.add_argument("eylem", choices=["liste", "degistir"])
    aj.add_argument("ad", nargs="?", default="")
    aj.add_argument("--motor", default="")
    aj.add_argument("--model", default="")
    aj.add_argument("--efor", default="", choices=["", "dusuk", "normal", "yuksek"])
    aj.add_argument("--klasor", default="", metavar="YOL",
                    help="ajanin CALISMA klasoru. Bu bir YETKI degisikligidir: "
                         "ajanin `--restricted` siniri burasidir ve gorevin "
                         "`ek_klasorler` alaninin aksine is bitince KAPANMAZ. "
                         "Klasor kapisindan gecer (var olmali; surucu koku ve "
                         "sistem klasoru reddedilir) ve kayda gecer.")
    aj.add_argument("--rol", default="",
                    help="rolu degistir (tur/arac/kanit/olcut birlikte gelir)")
    aj.set_defaults(islev=komut_ajan)

    gr = alt.add_parser("gorsel", help="gorsel uret / saglayici durumu")
    gr.add_argument("eylem", choices=["durum", "uret", "ekle", "para"])
    gr.add_argument("istem", nargs="?", default="")
    gr.add_argument("--cikti", default="", help="hedef dosya (varsayilan gorsel.png)")
    gr.add_argument("--uretici", default="", help="gemini | openai (bos = otomatik)")
    gr.add_argument("--model", default="")
    gr.add_argument("--kalite", default="",
                    help="low|medium|high (openrouter/openai) -- maliyeti bu belirler")
    gr.add_argument("--gorev", type=int, default=None,
                    help="`ekle` icin: kanit hangi ise ait")
    gr.add_argument("--ad", default="", help="`ekle` icin: hedef dosya adi")
    gr.add_argument("--para-harca", action="store_true",
                    dest="para_harca",
                    help="TEK SEFERLIK: ucretli uretici kullanmaya izin ver")
    gr.set_defaults(islev=komut_gorsel)

    vd = alt.add_parser("video", help="video uret / saglayici durumu")
    vd.add_argument("eylem", choices=["durum", "uret", "ekle"])
    vd.add_argument("istem", nargs="?", default="")
    vd.add_argument("--cikti", default="", help="hedef dosya (varsayilan video.mp4)")
    vd.add_argument("--saniye", type=int, default=8,
                    help="sure (tavan 30 sn -- daha uzunu parcalara bolunur)")
    vd.add_argument("--cozunurluk", default="720p", help="720p | 1080p | 4k")
    vd.add_argument("--uretici", default="", help="veo | higgsfield (bos = otomatik)")
    vd.add_argument("--model", default="")
    vd.add_argument("--tavan", type=float, default=None,
                    help="para tavani USD -- asilirsa is HIC baslamaz")
    vd.add_argument("--gorev", type=int, default=None,
                    help="`ekle` icin: kanit hangi ise ait")
    vd.add_argument("--ad", default="", help="`ekle` icin: hedef dosya adi")
    vd.set_defaults(islev=komut_video)

    nt = alt.add_parser("not", help="CALISAN ajana not birak (isin tanimina ek)")
    nt.add_argument("ajan", help="notun gidecegi ajan")
    nt.add_argument("metin", help="not -- orn. 'dur, once testleri duzelt'")
    nt.add_argument("--gorev", type=int, default=None,
                    help="gorev no (verilmezse ajanin elindeki is)")
    nt.set_defaults(islev=komut_not)

    dr = alt.add_parser("durdur", help="ofisi durdur: kosan turlar kesilir")
    dr.set_defaults(islev=komut_durdur)

    ip = alt.add_parser("iptal", help="yarim isi iptal et (kilitleri birakir)")
    ip.add_argument("no", type=int, help="gorev numarasi")
    ip.add_argument("--sebep", default="", help="ZORUNLU -- is neden yarim kaldi")
    ip.set_defaults(islev=komut_iptal)

    an = alt.add_parser("anahtar", help="API anahtarlarini yonet (deger basilmaz)")
    an.add_argument("eylem", choices=["liste", "ekle", "sil"])
    an.add_argument("ad", nargs="?", default="")
    an.set_defaults(islev=komut_anahtar)

    yt = alt.add_parser("yetenek",
                        help="ofis neyi yapabilir? motor · hesap · anahtar · "
                             "baglayici · CLI -- hepsi olculmus")
    yt.add_argument("--hizli", action="store_true",
                    help="baglayici saglik denetimini ATLA (hizli ama EKSIK; "
                         "atlandigi soylenir)")
    yt.set_defaults(islev=komut_yetenek)

    kl = alt.add_parser("kullanim",
                        help="hangi hesap bagli · OFIS ne tuketti · "
                             "haftalik yenilenme")
    kl.add_argument("--esik", action="append", default=[],
                    metavar="ROL:PENCERE=ORAN",
                    help="onceden gecis esigi (or. isci:5s=0.8); tekrar edilebilir")
    kl.add_argument("--gecis", choices=("ac", "kapat"),
                    help="onceden gecisi ac/kapat")
    kl.set_defaults(islev=komut_kullanim)

    sg = alt.add_parser("saglik", help="ofis tikali mi? teshis + care")
    sg.set_defaults(islev=komut_saglik)

    d = alt.add_parser("durum", help="ofisin su anki hali")
    d.set_defaults(islev=komut_durum)

    b = alt.add_parser("bekleyen", help="senden bekleneni goster")
    b.set_defaults(islev=komut_bekleyen)

    c = alt.add_parser("cevapla", help="bekleyen soruyu cevapla")
    c.add_argument("kimlik")
    c.add_argument("metin")
    c.set_defaults(islev=komut_cevapla)

    o = alt.add_parser("onayla", help="bekleyen onayi cevapla")
    o.add_argument("kimlik")
    o.add_argument("--hayir", action="store_true", help="reddet")
    o.add_argument("--is-boyunca", dest="is_boyunca", action="store_true",
                   help="BU IS BOYUNCA onayla: ayni eylem bu gorevde bir "
                        "daha sorulmaz. Varsayilan TEK SEFERLIK -- genis "
                        "kapsam senin ACIK tercihin olmali, yoksa bir "
                        "'evet' sessizce surekli yetkiye doner.")
    o.add_argument("--not", dest="not_", default="",
                   help="ret icin ZORUNLU gerekce")
    o.set_defaults(islev=komut_onayla)

    ts = alt.add_parser("tasi", help="TASI -- ofisin evi AgentOfis\\ev, projeler masaustu (varsayilan DENEME)")
    ts.add_argument("--uygula", action="store_true", help="gercekten tasi (panel kapali olmali)")
    ts.set_defaults(islev=komut_tasi)

    yd = alt.add_parser("yedek", help="YEDEK -- al / liste / dogrula / geri-yukle / hedef / github / metinden")
    yd.add_argument("eylem", choices=["al", "liste", "dogrula", "geri-yukle",
                                      "hedef", "github", "metinden"])
    yd.add_argument("yol", nargs="?", default=None,
                    help="arsiv yolu (dogrula/geri-yukle) ya da ekle|cikar (hedef)")
    yd.add_argument("--hedef", default=None, help="klasor")
    yd.add_argument("--neden", default=None, help="yedegin nedeni (orn. faz-F1)")
    yd.add_argument("--surum", type=int, default=None,
                    help="metinden: eski dokumde veri gocu surumu")
    yd.set_defaults(islev=komut_yedek)

    ga = alt.add_parser("geri-al", help="bir ajan TURUNU geri al (yalniz o turun dosyalari)")
    ga.add_argument("kimlik", nargs="?", default=None, help="liste ya da tur kimligi")
    ga.add_argument("--sebep", default=None, help="neden geri aliniyor (zorunlu)")
    ga.add_argument("--zorla", action="store_true",
                    help="turdan sonraki degisiklikleri / kosan isi bilerek ez")
    ga.add_argument("--goster", action="store_true", help="geri almadan once neyin donecegini goster")
    ga.add_argument("--limit", type=int, default=20)
    ga.set_defaults(islev=komut_geri_al)

    p = alt.add_parser("panel", help="paneli ac")
    p.add_argument("--adres", default="127.0.0.1")
    p.add_argument("--kapi", type=int, default=8900)
    p.set_defaults(islev=komut_panel)
    return a


def main() -> None:
    a = ayristirici().parse_args()
    a.islev(a)


if __name__ == "__main__":
    main()
