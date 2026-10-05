# -*- coding: utf-8 -*-
"""Koltuk: bir ajanin bir gorevi kostugu yer.

Tahta isi TUTAR, motor isi YAPAR, koltuk ikisini birbirine baglar. Sirasi
degismez cunku her adim bir oncekinin kazandigi hakka dayanir:

    sahiplen (kilidi al)  ->  brifing uret  ->  motoru kostur
        ->  cikti olaya donsun  ->  nabiz at  ->  kanit topla  ->  incelemeye ver

Kararlar ve olculmus sebepleri:

* **Kilit ONCE alinir, brifing SONRA uretilir.** Ters sirada, kilidi
  alamayacak bir ajan icin brifing uretmis oluruz -- bos jeton. Daha
  kotusu: brifingin K3 katmani "su an kim ne yapiyor" bilgisini tasir ve
  kilit alinmadan once uretilen K3 zaten bayattir.

* **Kilit cakismasi YUTULMAZ.** `KilitCakismasi` yukari birakilir. Koltuk
  "sonra tekrar denerim" deseydi, Yasa 1 bir kuyruk mekanigine donusur ve
  lider iki isi ayni dosyalara verdigini HIC ogrenmezdi. Ret gorunur
  olmali ki lider bolmeyi duzeltsin.

* **Metin parcalari tek tek olaya YAZILMAZ.** Motor jeton jeton akitir;
  her parcayi `olay` tablosuna yazmak saniyede yuzlerce satir demektir.
  Canli akis bellekte tutulur, veritabanina ANLAMLI SINIRLARDA dokulur
  (arac cagrisi, izin reddi, tur sonu, ya da `OLAY_TAMPON_S` saniyede bir).
  Olay tablosu bir kayit defteridir, terminal degil.

* **Yeni gorev = TEMIZ oturum.** Yasa 4: temiz baglam birikmis baglami
  yener ("context rot"). Ajan yeni bir ise girerken onceki isin
  transkriptini tasimaz; tasidigi sey brifingin dort katmanidir --
  ozetlenmis, taze ve o ise gore secilmis. Oturum YALNIZCA ayni gorev
  surerken devam eder (lider geri gonderdiginde), o zaman da tam brifing
  degil UYANIS FARKI verilir.

* **Koltuk KANIT UYDURMAZ.** Turun ciktisini kanit diye kaydetmek, kanit
  kapisini anlamsiz kilardi -- ajanin kendi anlatisi kanit degildir
  (MAST: hatalarin %21,3'u dogrulama eksikligi). Kanit, ajanin ACIKCA
  bildirdigi seydir. Bugun bunu `KANIT:` satirlariyla bildirir; Ofis MCP
  sunucusu gelince `kanit_ekle` cagrisiyla bildirecek. Ikisinde de kanit
  ICERIGI ajanindir, koltugun degil.

* **Basarisiz tur kilidi BIRAKIR.** Yoksa olmus bir tur, dosyalari kira
  suresi dolana kadar rehin tutar.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

import subprocess

from . import baglayici, degisim, geri_al, hesap, kullanim, roller, tarayici, tavan
from .roller import RolHatasi
from .db import simdi
from .mcp_sunucu import (yapilandirma as mcp_yapilandirmasi,
                         SUNUCU_ADI as OFIS_SUNUCU_ADI)
from .motor import motor_ac, MotorHatasi
from .motor.tip import TurKanali
from .postane import NOT_KURALI
from .tahta import TahtaHatasi
from .zincir import basamaklari_kur, elenenler, sonraki, tur_butcesi, ZincirBitti

#: Canli metin en fazla bu kadar saniye bellekte bekler, sonra `olay`a
#: dokulur. Kisa tutmak tabloyu sisirir, uzun tutmak paneli gecikmeli
#: gosterir. Iki saniye, insanin "takildi mi" diye merak etme esiginin
#: altinda kalir.
OLAY_TAMPON_S = 2.0

#: Kilit nabzi bu araliktan sik atilmaz. Kira 180 saniye (tahta.py);
#: 15 saniye, kirayi kaciramayacak kadar sik, veritabanini yormayacak
#: kadar seyrek.
NABIZ_ARALIGI_S = 15.0

#: Ajanin kanit bildirme bicimi -- Ofis MCP sunucusuna kadar gecerli kopru.
#: Ornek:  KANIT terminal: pytest -q -> 9 passed
#: Ajanin durum notu: `DURUM: <ne bitti> | <sirada ne var>`. METINDEN
#: okunur, cunku metin HER motorda akar -- MCP'ye bagli bir arac olsaydi
#: codex/gemini'de ikinci bir kanal gerekirdi ve iki kanal, kanitta bir
#: kez olculen CIFT kaydi dogururdu.
#:
#: SATIR BASI ARANMAZ ve BUYUK HARF sarttir. OLCULDU (23.09.2026): gercek
#: haiku turu satiri yazdi ama deftere DUSMEDI -- metin olaylari satir
#: degil PARCA (delta) olarak akiyor, birlesince `...ekliyorum.DURUM: ...`
#: oluyor ve `^` onu kaciriyordu. Kucuk harf "durum:" siradan Turkce
#: metinde gecer; buyuk harf sablonun kendisidir.
DURUM_DESENI = re.compile(r"DURUM\s*:\s*([^\n]+)")

KANIT_DESENI = re.compile(
    r"^\s*KANIT\s+(terminal|diff|gorsel|dosya|baglanti)\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


class KoltukHatasi(RuntimeError):
    pass


#: DURDURMA ISTEGI -- defterde, surec bellekte degil.
#:
#: Panelin "Durdur"u bir bellek bayragiydi (`_KOSU["dur"]`): yalniz
#: panelin KENDI surecinde kosan halkayi, o da tur BITINCE durdurabiliyordu.
#: Kabuktan baslatilan halkayi hic goremiyordu. Istek artik deftere yazilir:
#: halka (orkestra) tur sinirinda durur, koltuk KOSAN turu kanal uzerinden
#: aninda keser (olculdu: claude 8,1 sn'de, $0,007). Yeni bir kosu
#: baslarken temizlenir -- takili kalan istek sonraki isi oldurmesin.
DURDUR_ANAHTARI = "durdur_istegi"


def durdurma_iste(db, proje_id: str, kim: str = "insan") -> str:
    zaman = simdi()
    db.ayar_yaz(proje_id, DURDUR_ANAHTARI, zaman)
    db.olay_yaz(proje_id, "uyari",
                f"{kim} ofisi DURDURDU: kosan turlar kesiliyor, yenisi "
                "baslamayacak. Yarim is 'Surdur' ile kaldigi yerden devam eder.")
    return zaman


def durdurma_istendi(db, proje_id: str) -> str:
    """Bos degilse durdurma istenmis demektir (deger: isteme ani)."""
    return db.ayar_oku(proje_id, DURDUR_ANAHTARI, "")


def durdurma_temizle(db, proje_id: str) -> None:
    if durdurma_istendi(db, proje_id):
        db.ayar_yaz(proje_id, DURDUR_ANAHTARI, "")


#: Izleme kabininde kosan tura eklenen not (bkz. `orkestra` izleme kabini).
KABIN_IZLEME_NOTU = (
    "## TARAYICIN: PAYLASILAN KABIN (patron CANLI izliyor)\n\n"
    "Bu turda tarayicin, patronun panelde canli izledigi paylasilan kabin. "
    "Patronun kabinde actigi oturumlar burada gecerli. YENI SEKME ACMA: acik "
    "sekmede calis (panel yalniz onu gosterir). Sayfayi okumak icin "
    "`browser_find`/`browser_evaluate` tercih et; tam anlik goruntu pahali. "
    "YAZMAK icin `browser_type`, TIKLAMAK icin `browser_click` (kodla degil). "
    "Riskli tiklama (yayin, silme, para, gonderim) yine patronun onayina "
    "duser; sifre ya da kod YAZMA -- giris gerekiyorsa `giris_iste`.")


class Koltuk:
    """Tek bir ajanin tek bir gorev icin oturdugu koltuk."""

    def __init__(self, ofis, *, motor_fabrikasi=motor_ac,
                 olay_tamponu_s: float = OLAY_TAMPON_S,
                 zincir=None) -> None:
        self.ofis = ofis
        self.db = ofis.db
        self.proje_id = ofis.proje_id
        self.motor_fabrikasi = motor_fabrikasi
        self.olay_tamponu_s = olay_tamponu_s
        # Nobet zinciri AYARLANABILIR. Sabit kodlanmis bir zincir, baska
        # bir hesap/model duzenine sahip her kullaniciyi kodu degistirmeye
        # zorlar. None ise zincir.VARSAYILAN_ZINCIR kullanilir.
        self.zincir = zincir
        # Gorev kimligi -> turdan ONCEKI golge commit'i (geri_al.py).
        # Gorev basina anahtar: paralel turlar ayri iplikte, ayri gorevde.
        self._golge_once: dict = {}
        # Gorev kimligi -> turun basladigi an (atif belirsizligi icin).
        self._tur_basi: dict = {}

    #: Ayar anahtari: ajanlar hangi kipte kosar. 'arka' (varsayilan,
    #: bugunku yapili akis) | 'gercek' (insanin kullandigi Claude/Codex
    #: terminali, `motor/tui.py`). Iki kip ayni kapidan, ayni kurallarla
    #: gecer; gercek kip olculup esitlenene kadar varsayilan degismez.
    from .motor.tui import KIP_AYARI as TERMINAL_KIPI  # tek yerde

    def _motoru_sec(self, gorev: dict, ajan: dict, harita: dict, zorluk: str):
        """Isin motoru: once kaydedilen (is boyunca ayni), yoksa karneyle secilir.

        `None` = ajanin kendi motoru kalir (secim kapali, sahte ajan, tek motor).
        Secim kayda gecer (`motor_secimi`) ve isin satirina yazilir.
        """
        from . import karne
        kayitli = (gorev.get("motor_secimi") or "").strip()
        if kayitli:
            return kayitli
        if not karne.secim_acik_mi(self.db, self.proje_id):
            return None
        motor, gerekce = karne.sec(self.db, self.proje_id, ajan_motoru=ajan.get("motor") or "",
                                   meslek=ajan.get("meslek") or "", zorluk=zorluk,
                                   fabrika=self.motor_fabrikasi, harita=harita)
        if not motor:
            return None
        with self.db.baglanti() as c:
            c.execute("UPDATE gorev SET motor_secimi = ? WHERE id = ?", (motor, gorev["id"]))
        self.db.olay_yaz(self.proje_id, "motor_secimi", f"#{gorev['no']} -> {motor}: {gerekce}",
                         ajan_ad=ajan.get("ad") or "", gorev_id=gorev["id"])
        return motor

    def _motor_ac(self, ad: str):
        """Motoru acar; gercek terminal kipi aciksa ve motor destekliyorsa
        sarmalar. Desteklemeyen motor SESSIZCE arka plana dusmez: gorunur
        bir uyari yazilir."""
        from .motor.tui import kipe_gore
        return kipe_gore(self.db, self.proje_id, self.motor_fabrikasi(ad))

    # -- ana akis ----------------------------------------------------------

    def akit(self, no: int, ajan_ad: str, *, butce_usd: float = None,
             mcp_yapilandirma: str = "", zaman_asimi: float = None,
             tarayici_profili: str = "", tarayici_gorunur: bool = False,
             tarayici_kabini: str = "", kabin_izleme: bool = False,
             izinli_araclar: tuple = ()):
        """Gorevi kostur, panelin okuyacagi olaylari akit.

        Akan sozlukler `{tur, govde, ek}` bicimindedir -- motorun olay
        sozlugunun ustune koltugun kendi olaylari eklenir:
        `sahiplenildi`, `brifing`, `kanit`, `incelemede`, `birakildi`.
        """
        # `ekler/` HER ISTE HAZIR (01.10.2026). Olculdu (gercek set G13,
        # codex): plan dosyayi `ekler/urunler.xlsx`e yazdirdi, klasor yoktu;
        # brifingin "DOSYA -- klasor ACMA" satiriyla celisti, ajan patrona
        # "klasoru siz acin" diye sordu ve is durdu. Klasoru ofis acar --
        # yalniz kok TANIMLIYSA (bos kok bulunulan klasore acardi).
        try:
            if self.ofis.kok_klasoru():
                from .ekler import klasor as _ek_klasor
                _ek_klasor(self.ofis).mkdir(parents=True, exist_ok=True)
                # `karalama/` da hazir: codex sistem eki yardimci betigi
                # `[IO.File]::WriteAllText('karalama/x.py')` ile yazdirir;
                # klasor yoksa o cagri hata verir (01.10.2026).
                from .yollar import KARALAMA as _KARALAMA
                (Path(self.ofis.kok_klasoru()) / _KARALAMA).mkdir(parents=True, exist_ok=True)
                # Patronun projesi KENDI git deposunu kullaniyorsa `.ofis/`
                # oraya girmesin (ofisin izi projeye karismaz).
                _gi = Path(self.ofis.kok_klasoru()) / ".ofis" / ".gitignore"
                if not _gi.exists():
                    _gi.write_text("*\n", encoding="utf-8")
        except (OSError, Exception):             # noqa: BLE001 -- is durmasin
            pass
        ajan = self.ofis.kadro.ajan(ajan_ad)
        if ajan["faz"] == "basarisiz":
            raise KoltukHatasi(
                f"{ajan_ad} 'basarisiz' fazinda -- is verilemez."
            )

        gorev = self.ofis.tahta.gorev(no)
        # DEVRAL (E18): is insandaysa ajan turu KOSMAZ -- ayni dosyalara iki
        # yazar olurdu (Yasa 1). Insan "Ofise geri ver" deyince surer.
        from . import devral as _devral
        if _devral.devralinmis(self.db, self.proje_id, gorev["id"]):
            raise KoltukHatasi(
                f"#{no} su an INSANDA (devralindi) -- ajan turu kosmaz. "
                "'Ofise geri ver' ile ajana doner.")
        # Rolun ihtiyac duydugu izinler. Rol tanimsizsa (kutuphane
        # oncesi kayit) bos gecer -- eski bir kayit isi durdurmasin.
        try:
            rol_ek_izinler = roller.rol(ajan["meslek"]).ek_izinler
        except RolHatasi:
            rol_ek_izinler = ()
        # Kafa yazamaz: kural kadroda konur, burada UYGULANIR. Yazma alani
        # olan bir isi kafa ajana vermek, brifingde rica edilecek bir sey
        # degil; basta reddedilir.
        if ajan["tur"] == "kafa" and gorev["yazma_alani"]:
            raise KoltukHatasi(
                f"#{no} yazma alani tasiyor ({', '.join(gorev['yazma_alani'])}); "
                f"{ajan_ad} 'kafa' turunde ve dosya yazamaz. "
                "Bu gorevi 'eller' bir ajana ver."
            )

        klasor = self._klasor_hazirla(ajan)

        # 1 -- KILIT ONCE. Cakisma yutulmaz, yukari birakilir.
        devam = self._devam_mi(no, ajan_ad, ajan, gorev)

        # DEVAM ile SAHIPLENME ayri sorulardir.
        #   devam        = model tarafinda oturum surecek mi (baglam)
        #   sahiplenme   = tahta tarafinda is ve KILIT bizde mi (yetki)
        # Kaynak tukenmesinden birakilmis bir isi surdururken ikisi de
        # gerekir: oturum devam eder AMA kilit silinmistir. Ikisini tek
        # bayrakla yonetseydik is kilitsiz kosardi ve Yasa 1 sessizce
        # delinirdi -- kilit makinesi bunu hic gormezdi.
        if gorev["sahip"] != ajan_ad or gorev["durum"] != "calisiyor":
            gorev = self.ofis.tahta.sahiplen(no, ajan_ad, gorev["revizyon"])
            yield self._olay(
                "sahiplenildi",
                f"#{no} {gorev['baslik']} -> {ajan_ad}"
                + (" (kaldigi yerden)" if devam else ""),
                {"gorev_no": no, "ajan": ajan_ad, "devam": devam})

        # BIRIKMIS JETON TAVANI -- tur BASLAMADAN.
        #
        # Tur ORTASINDA bakilamaz: codex ve gemini jetonu yalnizca
        # turun sonunda bildiriyor (olculdu). Bilmedigimiz bir sayiya
        # gore kesmek, tavan koymus gibi gorunup kesmemek olurdu.
        # Turlar ARASI ise sayi kesindir ve her motorda var.
        _tsebep = tavan.jeton_tavani_denetle(
            self.db, self.proje_id, gorev["id"])
        if _tsebep:
            # Is OLMEZ, tur BASLAMAZ -- zincirdeki ayni ayrim.
            self.ofis.tahta.birak(no, sebep="jeton tavani doldu")
            yield self._olay("uyari", _tsebep, {"gorev_no": no},
                             ajan_ad=ajan_ad, gorev_id=gorev["id"])
            return

        # Uyanis isareti: ajan calisirken dunyada ne degisti sorusunun
        # baslangic noktasi. Tur BASLAMADAN alinir.
        isaret = self.ofis.bellek.son_olay_id()

        # 2 -- BRIFING. Yeni is ise dort katman, devam ise yalniz fark.
        if devam:
            metin = self._devam_metni(no, ajan_ad)
            jeton = len(metin) // 3
        else:
            b = self.ofis.brifing.uret(no, ajan_ad, diske_yaz=True)
            metin, jeton = b["metin"], b["jeton_tahmini"]
            if b["sisme_uyarisi"]:
                yield self._olay("uyari",
                                 f"Brifing sisti: {jeton} jeton. Baglam bozulabilir.",
                                 {"jeton": jeton})
        yield self._olay(
            "brifing",
            f"brifing okundu — {'uyanis farki' if devam else 'K1..K4'} · {jeton} jeton",
            {"jeton": jeton, "devam": devam},
        )
        # Bu metne GIREN patron notlari (K4 ulasmamislari YENI diye yazar).
        # Motor ilk olayini verince "tur basinda ulasti" diye isaretlenir;
        # motor hic baslayamazsa isaretlenmez -- yazilmak ulasmak degildir.
        baslangic_notlari = self._bekleyen_not_idleri(no, ajan_ad)

        # 2b -- DISK ANLIK GORUNTUSU (tur BASLAMADAN once).
        #
        # Brifingden SONRA alinir: `brifing.uret(diske_yaz=True)` ajanin
        # klasorune BRIFING.md yazar ve o ofisin yazisidir, ajanin degil.
        # Once alsaydik her turun farkinda ofisin kendi dosyasi gorunurdu.
        #
        # Olcum turu OLDURMEZ: diskten okuma patlarsa tur yine kosar ve
        # bunu bir `uyari` soyler -- olcemedigimize "degismedi" demeyiz.
        kok_klasor = self.ofis.tahta.kok_klasor()
        try:
            _t0 = time.time()
            once_anlik = (degisim.anlik(kok_klasor,
                                        degisim.ofis_dosyalari(self.db.yol))
                          if kok_klasor else None)
            _sure = time.time() - _t0
            # SESSIZCE YAVASLAMAK YOK. Olcum tur basina IKI kez kosar;
            # kok buyudukce bu bir tavana donusur ve "panel neden agir"
            # sorusu cevapsiz kalir. Esigin altinda sessiz -- her seye
            # "sorun" diyen gosterge de gostergesizlikten farksizdir.
            if once_anlik is not None and _sure > degisim.YAVAS_ESIK_SN:
                yield self._olay(
                    "uyari",
                    f"Degisim olcumu yavas: {len(once_anlik)} dosya, "
                    f"{_sure:.1f} sn (tur basina iki kez kosar).",
                    {"degisim_sure_sn": round(_sure, 2),
                     "dosya": len(once_anlik)},
                    ajan_ad=ajan_ad, gorev_id=gorev["id"])
        except OSError as exc:
            once_anlik = None
            yield self._olay("uyari",
                             f"Degisim olcumu baslayamadi: {exc}",
                             {"degisim": False}, ajan_ad=ajan_ad,
                             gorev_id=gorev["id"])

        # 2c -- GOLGE ANLIK (geri alma icin, geri_al.py). Olcumun
        # gosterdigi dosyalarin ICERIGI de saklanir; ikili/buyuk dahil.
        # Dusse tur yine kosar ama geri alinamayacagi SOYLENIR.
        self._golge_once.pop(gorev["id"], None)
        # Turun BASLANGICI: atif penceresi (bkz. `_komsu_kostu_mu`). Zaman
        # degil defterin SIRA NUMARASI: `simdi()` saniye cozunurluklu ve ayni
        # saniyedeki onceki bir olay pencereye "girer" (olculdu) -- ayni
        # beraberlik tuzagi `karar` tablosunda bir kez odendi.
        with self.db.baglanti() as _c:
            self._tur_basi[gorev["id"]] = _c.execute(
                "SELECT COALESCE(MAX(rowid), 0) FROM olay").fetchone()[0]
        if once_anlik is not None and kok_klasor:
            try:
                self._golge_once[gorev["id"]] = geri_al.Golge(
                    kok_klasor, degisim.ofis_dosyalari(self.db.yol)).anlik(
                        f"once #{no} {ajan_ad}")
            except (geri_al.GeriAlHatasi, OSError,
                    subprocess.SubprocessError) as exc:
                yield self._olay("uyari",
                                 f"Geri alma kaydi alinamadi (bu tur geri "
                                 f"ALINAMAZ): {exc}", {"geri_al": False},
                                 ajan_ad=ajan_ad, gorev_id=gorev["id"])

        # 3 -- MOTOR (nobet zinciriyle)
        #
        # Limit bir HATA degil, bir KAYNAGIN tukenmesidir. Once tur
        # oluyordu, kilit birakiliyordu ve orkestra "ilerleme yok" deyip
        # duruyordu -- insan geri gelene kadar ofis oluydu. Artik zincir
        # sonraki basamaga devrediyor (bkz. zincir.py).
        # ZORLUK MODELI BELIRLER -- ama yalnizca lider ISE yazdiysa.
        #
        # Rol KIMIN yapacagini soyler, zorluk NE KADAR GUCLE. Ikisi ayri
        # sorudur: ayni ajan kolay bir isi ucuz modelde, zor bir isi
        # guclu modelde kosabilmeli. Gerekli guc ISIN ozelligidir,
        # kisinin degil -- rakip bunu ise alirken seciyor, yani kisiye
        # yaziyor, ve o zaman ayni kisi her ise ayni gucle girer.
        #
        # Zincirin ILK basamagi ajanin kendi ayaridir; zorluk o ilk
        # basamagin modelini degistirir, YEDEKLERE dokunmaz -- limit
        # gelince devir yine calisir.
        kosan_ajan = ajan
        harita = roller.kademe_haritasi(self.db, self.proje_id)
        zorluk = (gorev.get("zorluk") or "").strip()
        # MOTOR SECIMI (03.10.2026, `karne`): isin motoru ofisin KENDI
        # tecrubesine ve iki aboneligin limit doluluguna gore secilir; is
        # boyunca ayni kalir. Model, secilen motorun kademesinden gelir.
        secilen = self._motoru_sec(gorev, ajan, harita, zorluk)
        if secilen and secilen != ajan["motor"]:
            try:
                _rol_kademe = roller.rol(ajan.get("meslek") or "").kademe
            except roller.RolHatasi:
                _rol_kademe = "standart"
            # Model rolun kademesinden; zorluk varsa asagidaki blok duzeltir.
            kosan_ajan = dict(ajan, motor=secilen,
                              model=roller.model_sec(secilen, _rol_kademe, harita))
        # 05.10.2026 (patron karari, "her ajanin sabit modeli"): varsayilan
        # kipte zorluk MODELE dokunmaz, yalniz eforu belirler -- yoksa
        # katalogun secimi her iste eziliyordu. Ajanin modeli bossa ya da
        # motor karneyle degistiyse kademe yine gecerli.
        from . import karne as _karne
        _zorluk_modele = (roller.zorluk_modeli(self.db, self.proje_id) == "kademe"
                          or _karne.secim_acik_mi(self.db, self.proje_id)
                          or not ajan.get("model")
                          or kosan_ajan["motor"] != ajan["motor"])
        if zorluk and _zorluk_modele:
            zorluk_modeli = roller.model_sec(
                kosan_ajan["motor"], roller.ZORLUK_KADEME[zorluk], harita)
            if zorluk_modeli and zorluk_modeli != kosan_ajan["model"]:
                kosan_ajan = dict(kosan_ajan, model=zorluk_modeli)
                # Sessizce degismez: hangi modelin NEDEN kostugunu
                # sonradan sorabilmek gerek.
                self.db.olay_yaz(
                    self.proje_id, "zorluk_modeli",
                    f"#{no} zorluk={zorluk} -> {kosan_ajan['motor']}/{zorluk_modeli} "
                    f"(ajanin kendi modeli: {ajan['model'] or '(yok)'})",
                    ajan_ad=ajan_ad, gorev_id=gorev["id"])

        # EFOR: zorluk belirler, TAVAN insanindir (23.09.2026).
        # Zorluk yoksa ajanin kendi eforu kalir. Tavan her durumda
        # uygulanir -- limit darken insan tek ayarla butun ofisi medium'a
        # cekebilmeli. `max` hic yok (roller.EFOR_SIRASI).
        istenen_efor = (roller.ZORLUK_EFOR.get(zorluk)
                        or ajan.get("efor") or "normal")
        # Ad `efor_tavani`: `tavan` bu dosyada MODULDUR (ofis/tavan.py);
        # yerel degiskene o adi vermek modulu golgeler ve fonksiyonun
        # BASINDAKI tavan.jeton_tavani_denetle cagrisini oldurur.
        efor_tavani = roller.efor_tavani(self.db, self.proje_id)
        efor_modu = roller.efor_modu(self.db, self.proje_id)
        etkin = roller.tur_eforu(self.db, self.proje_id, istenen_efor)
        if etkin != (ajan.get("efor") or "normal"):
            kosan_ajan = dict(kosan_ajan, efor=etkin)
        # Olay, efor DEGISTIGINDE ya da tavan SINIRLADIGINDA yazilir. Ikinci
        # kosul ayri: tavan "zor"u normal'e indirip sonuc ajanin kendi
        # eforuna esit dusunce sinirlama GORUNMEZ oluyordu (sinama yakaladi).
        if etkin != (ajan.get("efor") or "normal") or etkin != istenen_efor:
            self.db.olay_yaz(
                self.proje_id, "efor",
                f"#{no} efor={etkin}"
                + (f" (zorluk={zorluk})" if zorluk else "")
                + (f" -- panelde SABIT efor '{efor_modu}' secili (istenen {istenen_efor})"
                   if efor_modu != "zorluk" else
                   f" -- tavan '{efor_tavani}' sinirladi (istenen {istenen_efor})"
                   if etkin != istenen_efor else ""),
                ajan_ad=ajan_ad, gorev_id=gorev["id"])

        # HESAPLAR: zincir (motor, model) degil (HESAP, model) uzerinde
        # yurur. Kimlik burada cozulur -- `zincir` gizli depoyu bilmez.
        # Cozulemeyen hesap zincire HIC girmez ve sebebi gorunur olur:
        # anahtari eksik bir hesap, kosmayan bir basamaktir.
        # (Kurucu `zincir.basamaklari_kur` -- lider de AYNISINI kullanir.)
        basamaklar, alinmayan = basamaklari_kur(
            self.db, self.proje_id, kosan_ajan, fabrika=self.motor_fabrikasi,
            zincir=self.zincir, butce_usd=butce_usd, kademe_haritasi=harita)
        for sebep in alinmayan:
            self.db.olay_yaz(self.proje_id, "uyari", sebep,
                             ajan_ad=ajan_ad, gorev_id=gorev["id"])
        if not basamaklar:
            raise KoltukHatasi(
                f"{ajan_ad} icin calistirilabilir motor yok. "
                f"Elenenler: {elenenler(ajan, butce_usd=butce_usd, zincir=self.zincir, fabrika=self.motor_fabrikasi)}")
        # Elenen basamak SESSIZCE yok olmaz: gorunmeyen bosluk, sonra
        # "neden devretmedi" sorusunu cevapsiz birakir.
        for elenen in elenenler(ajan, butce_usd=butce_usd, zincir=self.zincir,
                                fabrika=self.motor_fabrikasi):
            yield self._olay(
                "uyari",
                f"Zincirde atlandi: {elenen['motor']}"
                + (f"/{elenen['model']}" if elenen["model"] else "")
                + f" -- {elenen['sebep']}",
                dict(elenen), ajan_ad=ajan_ad, gorev_id=gorev["id"])

        sira = 0
        basamak = basamaklar[0]
        motor = self._motor_ac(basamak["motor"])
        # Kanit kanali TEK olmali. Motor MCP konusuyorsa ofis sunucusu
        # baglanir ve kanit arac cagrisiyla gelir; konusmuyorsa metin
        # koprusu gecerli kalir. Ikisi birden acilirsa ayni is icin cift
        # kanit duser (olculdu: 3 cagri + 3 metin satiri = 6 kanit).
        # Ofis MCP sunucusu her tur icin YENIDEN kurulur: kimlik (ajan +
        # gorev) yapilandirmaya gomulur, araclar onu sormaz.
        # Dalin DISINDA baslatilir: asagida izin listesi bunu okuyor
        # ve `mcp_yapilandirma` disaridan verildiginde dal hic
        # calismiyordu -> UnboundLocalError. Bir degisken, onu OKUYAN
        # her yolda tanimli olmali.
        ek_sunucular = {}
        bag_ortam = {}
        # BAGLAYICILAR: isin beyan ettigi claude.ai connector'lari.
        #
        # Klasor/tarayici ile ayni kural (aciklik ISIN ozelligi) ama
        # bir farkla: burada bildirim teknik bir SUZGEC DEGIL --
        # ortam degiskeni hesabin TUMUNU yukluyor (olculdu). Bildirim
        # 'o ~225k jetonu odemeye deger mi' kararini verir ve niyeti
        # kayda gecirir. Bos ise hicbir sey yuklenmez, bedel odenmez.
        # OFISIN TEK KAPISI -- motor uygulayabiliyorsa.
        #
        # Yetenek TAHMIN EDILMEZ, adaptorden OKUNUR: yarin codex bu
        # kancayi eklerse ayni satir kendiliginden dogru cevabi verir.
        # Uygulayamayan motora bos gecer ve o motor baglayici da almaz
        # (asagida) -- kapisiz bir kapi acmaktansa kapali kalmak.
        izin_araci = (f"mcp__{OFIS_SUNUCU_ADI}__izin_sor"
                      if getattr(motor, "izin_kancasi", False) else "")

        bag = list(gorev.get("baglayicilar") or [])
        # DAR PENCERELI MODELE BAGLAYICI VERILMEZ.
        #
        # OLCULDU (22.09.2026): baglayici katalogu 225.765 jeton ve
        # haiku'nun penceresi 200.000 -- tur "Prompt is too long" ile
        # DUSER. Sessizce baglayicisiz kosturmak daha kotu olurdu: is
        # yapilir gibi gorunur, ajan aradigi araci bulamaz ve sebebini
        # kimse bilmez.
        #
        # Onun yerine KAPALI KALARAK reddediyoruz ve CAREYI soyluyoruz
        # (teshis koyup care soylemeyen gosterge, insani bir kez daha
        # dusundurur -- `saglik.py` kurali).
        _model = str(basamak.get("model") or "")
        if bag and any(d in _model for d in baglayici.DAR_PENCERELI_MODELLER):
            raise KoltukHatasi(
                f"#{no} baglayici istiyor ({', '.join(bag)}) ama "
                f"{ajan_ad} '{_model}' ile kosuyor. Baglayici katalogu "
                f"~{baglayici.OLCULEN_EK_JETON:,} jeton ve bu modelin "
                "penceresine SIGMAZ; tur 'Prompt is too long' ile "
                "duserdi. "
                f"Care: `python -m ofis.kabuk ajan degistir {ajan_ad} "
                "--model sonnet` (ya da opus), veya isi baglayicisiz "
                "kur ve tarayiciyla yap.")
        if bag and not izin_araci:
            # BAGLAYICI KAPISIZ VERILMEZ.
            #
            # Baglayici araclari para harcar (`ads_boost_ig_post`),
            # yayina alir (`ads_activate_entity`), siler
            # (`trash_message`). Kancasi olmayan bir motorda bunlarin
            # hicbiri hicbir kapidan gecmez. Sessizce vermek yerine
            # gorunur sekilde vazgeciyoruz.
            self.db.olay_yaz(
                self.proje_id, "uyari",
                f"#{no} baglayici VERILMEDI: {basamak['motor']} izin "
                "kancasini uygulayamiyor, riskli cagrilar kapidan "
                "gecemezdi.",
                ajan_ad=ajan_ad, gorev_id=gorev["id"])
            bag = []
        if bag and not getattr(motor, "baglayici_tasir", False):
            # BAGLAYICIYI YUKLEYEMEYEN MOTORA "ACILDI" DENMEZ (26.09.2026).
            # claude.ai baglayicilari yalniz claude CLI'da yasar; codex
            # app-server kancali ama onlari hic yuklemez. "Acildi" yazmak
            # yanlis gosteren gosterge olurdu -- ajan araci bulamaz.
            self.db.olay_yaz(
                self.proje_id, "uyari",
                f"#{no} baglayici VERILMEDI: {basamak['motor']} claude.ai "
                "baglayicilarini yukleyemez (yalniz claude). Isi claude'lu "
                "bir ajana ver ya da tarayiciyla yap.",
                ajan_ad=ajan_ad, gorev_id=gorev["id"])
            bag = []
        if bag:
            bag_ortam = baglayici.ortam(bag)
            self.db.olay_yaz(
                self.proje_id, "baglayici_acildi",
                f"#{no} " + baglayici.ozet(bag),
                ajan_ad=ajan_ad, gorev_id=gorev["id"])
        if not mcp_yapilandirma and getattr(motor, "mcp_konusur", False):
            # TARAYICI: isin beyan ettigi kaynaklar varsa verilir.
            #
            # Klasorle ayni kural -- aciklik ISIN ozelligidir, ajanin
            # degil. `tarayici_alani` bos olan gorev tarayici HIC
            # gormez; beyan edilmeyen kaynak da `--allowed-origins`
            # tarafindan reddedilir (yazma kilidinin web hali).
            #
            # Yerel bir stdio sunucusu oldugu icin hesabin claude.ai
            # baglayicilarindaki 131.543 jetonluk sorun buna
            # uygulanmiyor.
            #
            # KABIN: ajan, panelde GORDUGUN tarayiciya baglanir.
            # Kullanicinin istegi buydu ("sistemden cikmayayim"), ama
            # varsayilan DEGIL ve olamaz: kabinde insanin actigi
            # oturumlar yasar (magaza paneli, e-posta). Otomatik
            # baglamak, ajana insanin cerezlerini SESSIZCE vermek olurdu
            # -- yetki insandan gelir, bu yuzden acik bir istek.
            #
            # OLCULDU: CDP'ye baglaninca `--allowed-origins` HALA
            # TUTUYOR (beyan disi gidis `ERR_BLOCKED_BY_CLIENT`).
            # Tutmasaydi bu yol hic acilmazdi: kabin, yazma kilidinin
            # web halini sessizce kaldirirdi.
            alan = list(gorev.get("tarayici_alani") or [])
            # ONAYLANAN YENI SITELER. Vekil beyan edilmemis bir siteye
            # gidisi sert reddetmek yerine patrona soruyor; onay gelince
            # site bu IS boyunca acilir -- Playwright'in izin listesi surec
            # baslarken sabitlendigi icin bir SONRAKI turda, burada.
            # Gorevin kaydi DEGISTIRILMEZ: genisleme onay defterinden
            # turetilir, "bu site neden acildi" sorusunun cevabi orada.
            #
            #
            # Yalniz ALANI OLAN iste: serbest tarayiciya onayli siteleri
            # eklemek onu o sitelerle DARALTIRDI.
            if alan:
                for k in self._onayli_kaynaklar(gorev):
                    if k not in alan:
                        alan.append(k)
                        self.db.olay_yaz(
                            self.proje_id, "tarayici_alani",
                            f"#{no} patron onayiyla acilan site: {k}",
                            ajan_ad=ajan_ad, gorev_id=gorev["id"])
            # SERBEST TARAYICI HER ISTE (24.09.2026, kullanici karari).
            #
            # OLCULDU (gercek ofis, is #30): patron "sitemizi musteri
            # gozuyle analiz et" dedi; lider gorev metnine "yalniz
            # tarayiciyi kullan" yazdi ama alan bos kaldi. Isci yalniz
            # WebFetch aldi, sepet/odeme adimlarina bakamadi, uc kez
            # "bende tarayici yok" diye sordu -- patron "kullan" dedi
            # ve HICBIR SEY degismedi. Claude Code'u terminalde kullanan
            # insan bir siteyi acmak icin izin vermez; tarayiciyi bir
            # listeye baglamak, ajani terminaldekinden ZAYIF yapiyordu.
            # Koruma tiklamada, vekilde, her kipte duruyor.
            #
            # Kabin istenmisse (insanin oturumlari) serbest OLMAZ:
            # `sunucu_girdisi` kabinde bos listeyle tarayici vermez.
            serbest = not alan
            # IZLEME KABINI: patron "Ajanlar kabinde" anahtarini acti ve
            # halka bu isi kabine verdi -- is serbest ama panelde CANLI.
            kabinde = bool(tarayici_kabini) and (bool(alan) or kabin_izleme)
            if alan or not tarayici_kabini or kabin_izleme:
                # KIMLIK VEKILE DE GIDER. Tarayici artik dogrudan
                # Playwright degil, `tarayici_kapi.py` uzerinden
                # veriliyor ve o vekil riskli bir tiklamayi gorunce
                # `onay_iste` yazacak. Defteri bulamazsa riskli eylemi
                # REDDEDER -- yani kimligi gecirmemek, kapiyi acmak
                # degil ise yaramaz hale getirmek olurdu.
                girdi = tarayici.sunucu_girdisi(
                    alan, profil=tarayici_profili, gorunur=tarayici_gorunur,
                    cdp=tarayici_kabini if kabinde else "", serbest=serbest,
                    kabin_izleme=kabin_izleme and not alan,
                    kimlik={"OFIS_DB": str(self.db.yol),
                            "OFIS_PROJE": str(self.proje_id),
                            "OFIS_AJAN": str(ajan_ad),
                            "OFIS_GOREV": str(no)})
                if girdi:
                    ek_sunucular[tarayici.SUNUCU_ADI] = girdi
                    self.db.olay_yaz(
                        self.proje_id, "tarayici_acildi",
                        f"#{no} " + tarayici.ozet(
                            alan, profil=tarayici_profili,
                            gorunur=tarayici_gorunur,
                            cdp=tarayici_kabini if kabinde else "",
                            yazma=self._tarayici_yazar(gorev),
                            kabin_izleme=kabin_izleme and not alan),
                        ajan_ad=ajan_ad, gorev_id=gorev["id"])
            mcp_yapilandirma = mcp_yapilandirmasi(
                str(self.db.yol), self.proje_id, ajan_ad, no,
                ek_sunucular=ek_sunucular)
            if (kabinde and kabin_izleme and not alan
                    and tarayici.SUNUCU_ADI in ek_sunucular):
                # Uygulanan ama SOYLENMEYEN kural, ogrenilemeyen kuraldir:
                # ajan panelin yalniz ACIK SEKMEYI gosterdigini bilmezse
                # yeni sekme acar ve patron bos bir ekran izler (olculdu
                # 22.09: kabine baglanan ajan var olan sekmede calisir).
                metin = metin + "\n\n" + KABIN_IZLEME_NOTU
        sonuc = {"basarili": False}
        tampon = []
        son_dokum = time.monotonic()
        son_nabiz = time.monotonic()
        # CANLI IZLEME: tur SURERKEN diskte ne degisiyor (degisim.py).
        # Onceki bir surecin dusup silemedigi ara kayit once temizlenir:
        # bu is icin gosterilecek tek canli kayit BU turunki olmali.
        canli = self._canli_izleyici(once_anlik, kok_klasor, gorev)
        tam_metin = []
        # `arac_sonuc` hangi araca ait oldugunu SOYLEMEZ; onceki `arac`
        # olayindan tasinir. Dongunun DISINDA tanimli, cunku onu okuyan
        # her yolda tanimli olmali -- bu tuzak bu projede iki kez odendi
        # (`ek_sunucular`, `bag_ortam`: `UnboundLocalError`).
        son_arac = None

        # NOBET DONGUSU: limit gelirse sonraki basamakla TEKRAR kosulur.
        # Tur yeniden baslar cunku limit, uretilen isi degil KAYNAGI
        # bitirir; ayni brifing baska bir motorda gecerlidir. Oturum
        # kimligi tasinmaz -- o kimlik onceki motorun defterinde yasar.
        while True:
            try:
                # Fren HER basamakta sifirdan baslar: bir onceki
                # basamakta sayilanlar bu basamaga borc degildir.
                fren = tavan.KacakFreni()
                # TUR ICI KANAL: yalniz tasiyabilen motora. Tasiyamayana
                # (codex exec) not bir SONRAKI turun basinda gider --
                # sessizce "ulasti" sanilmaz, olay yalniz ulasinca yazilir.
                kanal = (TurKanali() if getattr(motor, "tur_ici_mesaj", False)
                         else None)
                # Bu turda kanala itilen notlar + durdurmanin soylenip
                # soylenmedigi (bir kez soylenir, her saniye degil).
                kd = {"itilen": set(baslangic_notlari), "durdur_soylendi": False}
                ilk_olay = True
                son_not = 0.0
                if basamak.get("ofis_freni"):
                    # Bir kontrolun yerine baskasi geciyorsa SESSIZ
                    # olmaz. Insan, dolar tavaninin bu turda
                    # UYGULANMADIGINI bilmeli.
                    yield self._olay(
                        "uyari",
                        f"{basamak['motor']} tur basina DOLAR tavani "
                        "uygulayamiyor; yerine ofis freni gecerli "
                        f"(en cok {fren.azami_arac} arac cagrisi, "
                        f"{fren.azami_cikti_harf:,} harf) + birikmis "
                        "jeton tavani.",
                        fren.olcum(), ajan_ad=ajan_ad,
                        gorev_id=gorev["id"])
                for olay in motor.tur_kos(
                    metin,
                    klasor=klasor,
                    oturum_id=ajan["oturum_id"] if devam else "",
                    model=basamak["model"],
                    efor=kosan_ajan.get("efor") or ajan["efor"],
                    yazabilir=(ajan["tur"] == "eller"),
                    # DOLAR TAVANI yalniz UYGULAYABILENE verilir.
                    # Veremedigimizde sessiz kalmiyoruz: yerine ofis
                    # freni geciyor ve bu gorunur bir uyari oluyor --
                    # bir kontrolun yerine baskasi geciyorsa insan
                    # bilmeli.
                    butce_usd=tur_butcesi(basamak, motor, butce_usd),
                    zaman_asimi=zaman_asimi,
                    mcp_yapilandirma=mcp_yapilandirma,
                    # ROLUN EK IZINLERI + ISE OZEL izinler.
                    #
                    # Varsayilan liste bilerek DARDIR ve rol onu kendi
                    # ihtiyaci kadar acar: `kalite` rolu `npx`siz test
                    # kosturamaz, `entegrasyon` rolu `where`siz CLI
                    # bulamaz. Bunu her iste elle yazmak, bir gun
                    # unutmak demektir -- ve unutuldugunda ajan isi
                    # yapamaz, sebebini de soyleyemez.
                    #
                    # Tam bu hatayi bir kez odedik: `WebSearch` arac
                    # listesindeydi ama IZIN listesinde degildi; ofis
                    # aylarca hic arastirma yapamadi ve 437 test bunu
                    # gormedi.
                    # ARAC VERILDIYSE IZIN DE VERILIR.
                    #
                    # Bu tam olarak bir kez odedigimiz hata: `WebSearch`
                    # arac listesindeydi ama IZIN listesinde degildi ve
                    # ofis aylarca hic arastirma yapamadi. Tarayici
                    # sunucusunu verip iznini vermemek ayni hata olurdu.
                    izinli_araclar=(
                        tuple(rol_ek_izinler)
                        # TARAYICI ARACLARI ARAC ARAC verilir (onek
                        # degil): yarin Playwright'in ekledigi bir arac,
                        # biz hic gormeden ajanin eline gecmesin.
                        #
                        # TIKLAMA ARTIK VARSAYILAN OLARAK ACIK. Bir sure
                        # kapaliydi ve kullanici hakli olarak itiraz
                        # etti: *"tiklamasini engellemek bana sacma
                        # geldi; ajanlar calissin tiklasin gezsin."*
                        # Koruma cite degil KAPIYA tasindi
                        # (`tarayici_kapi.py`): riskli tiklama -- yayin,
                        # silme, para, gonderim -- insana sorulur, geri
                        # kalani serbest gecer.
                        #
                        # `tarayici_yazma=0` olan ESKI gorevler salt
                        # okunur kalir. Saklanan bir degerin anlamini
                        # sonradan cevirmek, bu projede alti kez odenen
                        # "sessizce yok sayilan ayar" sinifidir.
                        + (tarayici.izinli_araclar(
                            yazma=self._tarayici_yazar(gorev))
                           if ek_sunucular else ())
                        # BAGLAYICILAR ARTIK ONEKLE ACILMIYOR.
                        #
                        # Onek (`mcp__claude_ai`) verilince HER baglayici
                        # araci izin listesine giriyordu -- `create-discount`
                        # (para), `ads_activate_entity` (reklami baslatir,
                        # PARA HARCAR), `graphql_mutation` (her seyi yapar).
                        # Hicbiri hicbir kapidan gecmiyordu. Tarayicida
                        # ayni hatayi yeni kapatmistik.
                        #
                        # Simdi izin listesine ALINMIYORLAR: CLI her
                        # cagriyi `izin_araci`na soruyor, ofis olcute gore
                        # karar veriyor. Okuma serbest, degistiren kaydedilir,
                        # riskli insana dusuyor.
                        #
                        # Kancasi olmayan bir motora baglayici verilirse
                        # onek DE verilmez ve cagri reddedilir: kapisiz bir
                        # kapi acmaktansa kapali kalmak.
                        + ((baglayici.IZIN_ONEKI,)
                           if (bag and not izin_araci) else ())
                        + tuple(izinli_araclar or ())),
                    # Isin ofis disi klasorleri. Lidere verip isciye
                    # vermeseydik lider, iscinin DOKUNAMAYACAGI bir
                    # klasore gore plan yapardi -- ve isci "dosya yok"
                    # derdi. Olculmus hata sinifi: eksik baglam, kotu
                    # niyet gibi gorunur.
                    ek_klasorler=tuple(gorev.get("ek_klasorler") or ()),
                    # Tur ici kanal yalniz VARSA gecer: kanal tanimayan
                    # bir adaptore bos anahtar gondermek sozlesmeyi kirardi.
                    **({"kanal": kanal} if kanal is not None else {}),
                    # Bu turun KIMLIGI. Bos ise CLI kendi oturumunu
                    # kullanir (bugunku davranis); dolu ise hesap
                    # baska bir kimlige isaret eder.
                    # Hesabin kimligi + baglayici ortami BIRLIKTE.
                    # Biri otekini ezmemeli: ikisi ayri sorulara
                    # cevap veriyor (KIM adina / NEYE erisimle).
                    ek_ortam=({**(basamak.get("ortam") or {}), **bag_ortam}
                              or None),
                    # OFISIN TEK KAPISI. Motor uygulayamiyorsa BOS gecer
                    # (sessizce yok sayilan ayar olmasin diye yetenek
                    # bayragindan okunuyor, tahmin edilmiyor).
                    izin_araci=izin_araci,
                ):
                    simdiki = time.monotonic()

                    if ilk_olay:
                        # Motor basladi: brifinge giren notlar ULASTI.
                        ilk_olay = False
                        for _nid in baslangic_notlari:
                            self.ofis.postane.not_iletildi(_nid, yol="tur_basinda")

                    # PATRONUN NOTU ve DURDURMA -- defterden, saniyede bir.
                    # Defter kanaldir cunku notu yazan (panel/kabuk) ile turu
                    # kosturan (halka) AYRI surecler olabilir.
                    if simdiki - son_not >= self.NOT_ARALIGI_S:
                        son_not = simdiki
                        yield from self._kanali_besle(kanal, kd, no,
                                                      ajan_ad, gorev)

                    if olay.tur == "mesaj":
                        # Motor notu GERCEKTEN iletti (claude: yanki, codex:
                        # kabul edilen steer). Defter tek yazicidir.
                        self.ofis.postane.not_iletildi(
                            str((olay.ek or {}).get("kimlik") or ""), yol="tur_ici")
                        yield self._olay("not_iletildi", olay.govde, olay.ek,
                                         yaz=False)
                        continue

                    # KACAK FRENI -- motor sozlesmesinden BAGIMSIZ.
                    #
                    # Yalnizca koltugun zaten gordugu olaylara bakar
                    # (arac sayisi, cikti hacmi), o yuzden YARIN
                    # EKLENEN bir motor icin de calisir; yeni motorun
                    # hicbir sey bildirmesi gerekmez.
                    #
                    # Bir PARA tavani DEGIL ve oyle adlandirilmiyor:
                    # jeton tur ortasinda bilinmiyor (olculdu). Bu,
                    # donguye girmis ya da megabaytlarca metin ureten
                    # bir turu durdurur.
                    fren.olay(olay.tur, olay.govde or "")
                    _fsebep = fren.asildi_mi()
                    if _fsebep:
                        yield self._olay("uyari", _fsebep, fren.olcum(),
                                         ajan_ad=ajan_ad,
                                         gorev_id=gorev["id"])
                        sonuc["basarili"] = False
                        sonuc["sebep"] = "kacak freni"
                        break

                    # Kilidin kirasi: motor sessizken bile tazelenir.
                    if simdiki - son_nabiz >= NABIZ_ARALIGI_S:
                        self.ofis.tahta.nabiz(no)
                        son_nabiz = simdiki

                    # Canli tarama da nabizdan ONCE: motor sessizken
                    # (uzun bir Bash) dosyalar yine degisiyor olabilir
                    # ve nabiz olaylari saniyede bir akar.
                    yield from self._canli_tara(canli, no, ajan_ad, gorev)

                    if olay.tur == "nabiz":
                        continue  # kilit tazelendi; panele tasimaya deger bilgi yok

                    if olay.tur == "oturum":
                        # Kimlik burada dogar; kaydedilmezse ajan hafizasini yitirir.
                        self.ofis.kadro.oturum_kaydet(ajan_ad, olay.ek["oturum_id"])
                        if ajan["faz"] == "kuruluyor":
                            self.ofis.kadro.faz_ayarla(ajan_ad, "aktif")
                            ajan = self.ofis.kadro.ajan(ajan_ad)
                        # Olay ajan ve gorevle ETIKETLENIR: "hangi oturum
                        # kime, hangi is icin acildi" sorusunun cevabi
                        # sonra devam kararini verecek (bkz. _devam_mi).
                        yield self._olay("oturum", olay.govde, olay.ek,
                                         ajan_ad=ajan_ad,
                                         gorev_id=gorev["id"])
                        continue

                    if olay.tur in ("metin", "dusunce"):
                        if olay.tur == "metin":
                            tam_metin.append(olay.govde)
                            tampon.append(olay.govde)
                        # Canli akis panele HER parcayi verir; veritabanina
                        # dokulmesi anlamli sinirlarda olur.
                        yield self._olay(olay.tur, olay.govde, olay.ek, yaz=False)
                        if simdiki - son_dokum >= self.olay_tamponu_s:
                            self._tamponu_dok(tampon, no, ajan_ad)
                            son_dokum = simdiki
                        continue

                    # Arac, izin, limit, hata: bunlar kayit defterine girer.
                    self._tamponu_dok(tampon, no, ajan_ad)
                    son_dokum = simdiki

                    if olay.tur == "bitti":
                        sonuc = dict(olay.ek)
                        sonuc["cevap"] = "".join(tam_metin).strip() or olay.govde
                        # Turun GERCEKTEN kostugu motor/hesap. Zincir
                        # devrettiyse ajanin ayari yanlis cevabi verir;
                        # dogru cevap o an kosan BASAMAKtir.
                        sonuc["motor"] = basamak.get("motor") or ""
                        sonuc["hesap"] = basamak.get("hesap") or ""
                        continue

                    # BAGLAYICI SORUN HAFIZASI.
                    #
                    # `claude mcp list` yalnizca "bagli / yetki yok" der;
                    # kapsam bilgisi YOKTUR (olculdu). Yani bir baglayici
                    # bagli gorunup yine de ise yaramayabilir ve bunu
                    # SORARAK ogrenemeyiz.
                    #
                    # Ogrenilebilecek tek gercek sey burada geciyor: bir
                    # ajan o araci GERCEKTEN cagirdi ve sonuc ne oldu.
                    # `gorsel.py`nin kota hafizasiyla ayni desen --
                    # *olcmek kaynagi tuketir, o yuzden hatirlariz.*
                    if olay.tur == "arac":
                        son_arac = olay.govde
                    elif olay.tur == "arac_sonuc" and son_arac:
                        hedef = baglayici.arac_adindan(son_arac)
                        if hedef:
                            if olay.ek.get("hatali"):
                                baglayici.sorun_yaz(hedef, olay.govde)
                            else:
                                # Duzelmis bir baglayiciyi bozuk
                                # gostermeye devam etmek, yanlis gosteren
                                # gostergenin ta kendisi olurdu.
                                baglayici.sorunu_temizle(hedef)
                        son_arac = None

                    # ARAC SATIRI: deftere yalniz ADI yaziliyordu ("Bash");
                    # hangi komutun kostugu, hangi dosyaya dokunuldugu
                    # motorun olayinda VARDI ama panel yenilenince
                    # kayboluyordu. Terminal gorunumu (28.09) onu ister:
                    # ilk satir arac, ikinci satir NE. Ilk satiri okuyan
                    # eski tuketiciler bozulmaz.
                    _govde = olay.govde
                    if olay.tur == "arac" and (olay.ek or {}).get("ozet"):
                        _govde = f"{olay.govde}\n{str(olay.ek['ozet'])[:300]}"
                    yield self._olay(olay.tur, _govde, olay.ek,
                                     ajan_ad=ajan_ad, gorev_id=gorev["id"])
            except MotorHatasi as exc:
                # Motor hic baslayamadi (kurulu degil, klasor yok, kimlik bozuk).
                # Kilidi tutmanin anlami yok.
                self._birak(no, f"motor baslamadi: {exc}")
                self._canli_temizle(gorev)
                yield self._olay("hata", f"Motor baslamadi: {exc}",
                                 {"sebep": "motor"}, ajan_ad=ajan_ad,
                                 gorev_id=gorev["id"])
                yield self._olay("tur_bitti", "", {"basarili": False, "gorev_no": no})
                return
            finally:
                self._tamponu_dok(tampon, no, ajan_ad)
                # Durum notu HER tur sonunda (basarili, dusen, limitte
                # kesilen) yakalanir: devir paketinin en degerli parcasi
                # tam da kesilen turun son notudur.
                self._durum_notu_yaz(no, ajan_ad, gorev, tam_metin)

            # DEVIR SEBEPLERI: kaynak tukenmesi (limit) ve HESABIN
            # kullanilamaz hale gelmesi (oturum sunucuda dustu, hesap askida
            # -- E16). Ikisinde de bu hesap bu isi SU AN yapamaz, baska hesap
            # yapabilir. Oturum dusmesinde once tur biraklip bir sonraki
            # tikte baska motor seciliyordu: bir tik bosa, sebep dagiliyordu.
            oturum_dustu = sonuc.get("sebep") == "oturum_kapandi"
            if not (sonuc.get("limit") or oturum_dustu):
                break
            neden = ("hesabi KULLANILAMIYOR (oturum/hesap sorunu)"
                     if oturum_dustu else "kullanim limitine ulasti")

            # Devret. Once kaynagin bittigini gorunur kil.
            yield self._olay(
                "limit",
                f"{basamak['motor']}"
                + (f"/{basamak['model']}" if basamak["model"] else "")
                + f" {neden}.",
                dict(basamak), ajan_ad=ajan_ad, gorev_id=gorev["id"])
            try:
                yeni = sonraki(basamaklar, sira)
            except ZincirBitti as exc:
                yield self._olay("uyari", str(exc), {"zincir_bitti": True},
                                 ajan_ad=ajan_ad, gorev_id=gorev["id"])
                break

            # Devir bir KARARDIR: gerekcesiyle gunluge yazilir ki
            # 'bu is neden baska motorda kosmus' sorusu alti ay sonra
            # da cevaplanabilsin.
            self.ofis.bellek.karar_yaz(
                f"#{no} {basamak['motor']}"
                + (f"/{basamak['model']}" if basamak["model"] else "")
                + f" yerine {yeni['motor']}"
                + (f"/{yeni['model']}" if yeni["model"] else "")
                + " ile kosuldu.",
                (f"Onceki basamagin {neden}. Hesap kullanilamaz olunca "
                 "caresi baska hesaba gecmektir; giris insanin isidir."
                 if oturum_dustu else
                 "Onceki basamak kullanim limitine ulasti; limit bir hata "
                 "degil kaynagin tukenmesidir, caresi baska kaynaga "
                 "gecmektir."),
                ajan_ad, tur="teknik", gorev_id=gorev["id"])

            # DEVIR PAKETI -- yeni motor onceki oturumu GOREMEZ. Kesilen
            # turun olculen izi (diskte ne degisti, son sozu) SIFIRLANMADAN
            # once toplanir.
            try:
                _diskte = (degisim.karsilastir(once_anlik,
                                               degisim.anlik(
                                                   kok_klasor,
                                                   degisim.ofis_dosyalari(
                                                       self.db.yol)))
                           if (once_anlik is not None and kok_klasor) else [])
            except OSError:
                _diskte = []   # olculemedi: paket diski SOYLEMEZ, uydurmaz
            kesilen = {"motor": basamak["motor"], "model": basamak["model"],
                       "son_soz": "".join(tam_metin), "diskte": _diskte}

            sira += 1
            basamak = yeni
            motor = self._motor_ac(basamak["motor"])
            # Yeni motor MCP konusmuyorsa yapilandirmayi BIRAKMA:
            # konusmayan motora MCP vermek anlamsiz, konusana vermemek
            # kanit kanalini kapatir.
            if getattr(motor, "mcp_konusur", False):
                if not mcp_yapilandirma:
                    # Tarayici sunucusu da tasinir: bos gecseydik devirden
                    # sonra tarayicili is tarayicisiz kosardi.
                    mcp_yapilandirma = mcp_yapilandirmasi(
                        str(self.db.yol), self.proje_id, ajan_ad, no,
                        ek_sunucular=ek_sunucular)
            else:
                mcp_yapilandirma = ""
            # MOTORA BAGLI KARARLAR YENI MOTORA GORE YENIDEN VERILIR.
            #
            # OLCULEN HATA (23.09.2026, gercek codex turu): izin kancasi
            # ilk basamak (claude) icin kurulup devirde codex'e de
            # geciriliyordu; codex onu uygulayamadigi icin (dogru
            # davranarak) turu HIC BASLATMIYORDU. Yani tek kapi geldigi
            # gunden beri claude'dan codex'e isci devri pratikte hic
            # calismiyordu -- sahte motorlu sinamalar bunu goremezdi,
            # cunku sahte motor kancayi reddetmiyor.
            izin_araci = (f"mcp__{OFIS_SUNUCU_ADI}__izin_sor"
                          if getattr(motor, "izin_kancasi", False) else "")
            _dar = any(d in str(basamak.get("model") or "")
                       for d in baglayici.DAR_PENCERELI_MODELLER)
            _tasir = getattr(motor, "baglayici_tasir", False)
            if bag and (not izin_araci or _dar or not _tasir):
                # Baslangicta KAPALI KALARAK reddediyorduk; devirin
                # ortasinda reddetmek isi oldururdu. Baglayici birakilir
                # ve bu GORUNUR olur -- sessizce kapisiz vermek yok.
                yield self._olay(
                    "uyari",
                    f"#{no} devirde baglayici BIRAKILDI: {basamak['motor']}"
                    + (" izin kancasini uygulayamiyor" if not izin_araci
                       else " claude.ai baglayicilarini yukleyemez" if not _tasir
                       else " modelinin penceresi katalogu tasimaz") + ".",
                    {"gorev_no": no}, ajan_ad=ajan_ad, gorev_id=gorev["id"])
                bag, bag_ortam = [], {}
            devam = False          # yeni motorda onceki oturum yok
            # OLCULEN HATA (23.09.2026): metin burada YENIDEN KURULMUYORDU.
            # Tur bir DEVAM turuysa `metin` yalnizca uyanis farkiydi --
            # onceki oturumu hic gormeyen yeni motor isin NE oldugunu
            # bilmeden kosuyordu. Yeni motor her zaman TAM brifing + devir
            # paketi alir. Diske YAZILMAZ: BRIFING.md kokte ve anlik
            # goruntu alindi; yeniden yazmak ofisin dosyasini ajanin
            # degisikligi gibi gosterirdi.
            _b = self.ofis.brifing.uret(no, ajan_ad, diske_yaz=False,
                                        kesilen=kesilen)
            metin = _b["metin"]
            # Yeni motorun brifingi de notlari tasir (K4): ulasmamislar bu
            # motorun ilk olayinda "tur basinda" ulasir.
            baslangic_notlari = self._bekleyen_not_idleri(no, ajan_ad)
            yield self._olay(
                "brifing",
                f"devir paketi — K1..K4 + gecmis · {_b['jeton_tahmini']} jeton",
                {"jeton": _b["jeton_tahmini"], "devam": False, "devir": True},
                ajan_ad=ajan_ad, gorev_id=gorev["id"])
            sonuc = {"basarili": False}
            tam_metin = []
            yield self._olay(
                "basladi",
                f"Nobet devri: {basamak['motor']}"
                + (f"/{basamak['model']}" if basamak["model"] else "")
                + " ile yeniden deneniyor.",
                dict(basamak), ajan_ad=ajan_ad, gorev_id=gorev["id"])

        # 4 -- SONUC
        cevap = sonuc.get("cevap", "")
        for olay in self._sonucu_isle(no, ajan_ad, gorev, sonuc, cevap, isaret,
                                      mcp_yapilandirma, butce_usd=butce_usd,
                                      once_anlik=once_anlik,
                                      kok_klasor=kok_klasor):
            yield olay

    def kos(self, no: int, ajan_ad: str, **ayar) -> dict:
        """Akisi bastan sona tuketir, ozeti dondurur.

        Panel `akit`i kullanir (canli), lider ve testler `kos`u (toplu).
        """
        ozet = {"basarili": False, "olaylar": 0, "kanit": 0}
        for olay in self.akit(no, ajan_ad, **ayar):
            ozet["olaylar"] += 1
            if olay["tur"] == "tur_bitti":
                ozet.update(olay["ek"])
        # Kanit sayisi TAHTADAN okunur, akistan sayilmaz. OLCULDU: MCP ile
        # kanit AYRI BIR SUREC (mcp_sunucu) tarafindan ekleniyor ve koltugun
        # akisinda hic gorunmuyor; akistan sayinca gercek kanit varken "0
        # kanit" yaziyordu. Sayan yer, kaydin TUTULDUGU yer olmali.
        try:
            ozet["kanit"] = len(self.ofis.tahta.kanitlar(no))
        except TahtaHatasi:
            pass
        return ozet

    # -- sonuc isleme ------------------------------------------------------

    def _sonucu_isle(self, no, ajan_ad, gorev, sonuc, cevap, isaret,
                     mcp_yapilandirma="", *, butce_usd=None,
                     once_anlik=None, kok_klasor=""):
        """Tur bitti; gorev hangi duruma gecmeli?

        Basarisiz  -> kilit birakilir, is yeniden dagitilabilir.
        Kanit var  -> incelemeye gider, lider bakar.
        Kanit yok  -> 'calisiyor' kalir. Koltuk kanit UYDURMAZ; kanitsiz
                      bir isi incelemeye itmek, kanit kapisini kandirmaktir.
        """
        # DISK FARKI -- her uc yol icin de olculur.
        #
        # Bekleyen ajan da yazmis olabilir (soru sormadan once), basarisiz
        # tur de: "is bitmedi" ile "hicbir sey degismedi" AYRI iki seydir.
        # Ikincisini varsaymak, diskte duran bir degisikligi gorunmez
        # kilardi -- basarisiz turun olculmemesi bir kez odendi.
        for olay in self._degisimi_olc(no, ajan_ad, gorev,
                                       once_anlik, kok_klasor):
            yield olay

        # Ajan soru sordu ya da onay istedi mi? Bekleyen bir ajan
        # BASARISIZ degildir: isi yarim degil, DURDURULMUS. Kilit onda
        # kalir cunku cevap gelince ayni yerden devam edecek; kilidi
        # birakmak, bekleyen isin dosyalarini baskasina acmak olurdu.
        bekleme = self.ofis.postane.bekliyor_mu(ajan_ad)
        if bekleme["bekliyor"]:
            yield self._olay(
                "bekliyor",
                f"#{no} {bekleme['tur']} bekliyor: {bekleme['aciklama'][:200]}",
                {"gorev_no": no, **bekleme}, ajan_ad=ajan_ad,
                gorev_id=gorev["id"],
            )
            # BEKLEYEN tur da OLCULUR. Olculdu (26.09.2026, deneme seti):
            # bu dal `tur_ozeti` yazmadan donuyordu -- ajan soru sorup ya
            # da onay isteyip durdugunda turun jetonu ve maliyeti kullanim
            # ekranina ve haftalik butceye HIC girmiyordu. Basarisiz tur
            # icin bir kez odenen dersin ucuncu yolu.
            self._olcum_yaz(ajan_ad, gorev, sonuc)
            yield self._olay("tur_bitti", cevap,
                             {"basarili": bool(sonuc.get("basarili")),
                              "gorev_no": no, "bekliyor": bekleme["tur"],
                              **sonuc})
            return

        if not sonuc.get("basarili"):
            # BASARISIZ tur da olculur. OLCULDU: uc tur ust uste dustu ve
            # hicbiri kayda gecmedi; toplam maliyet tek basarili turu
            # gosteriyordu. Kacagin oldugu yeri olcmemek, olcmemenin en
            # pahali halidir.
            self._olcum_yaz(ajan_ad, gorev, sonuc)
            # Butce tukenmesi CLI'dan ayri bir isaretle gelmiyor: tur
            # `cikis 1` ile duser, stderr bos. Ama OLCUM elimizde --
            # tavan verildiyse ve maliyet ona dayandiysa sebep bellidir.
            # Sebebi dogru yazmak sus degil: bir sonraki tur DEVAM mi
            # edecek yoksa SIFIRDAN mi kosacak, buna bakarak karar veriyor.
            butce_bitti = bool(
                butce_usd and (sonuc.get("maliyet_usd") or 0) >= float(butce_usd))
            # INSAN DURDURDU bir ARIZA degildir: is dogru gidiyordu, insan
            # "dur" dedi. Kaynak tukenmesi gibi sayilir (KAYNAK_SEBEPLERI):
            # "Surdur" ayni ajanla, ayni oturumdan devam eder.
            sebep = ("insan durdurdu" if sonuc.get("sebep") == "durduruldu"
                     else "kullanim limiti" if sonuc.get("limit")
                     else "zaman asimi" if sonuc.get("zaman_asimi")
                     else "butce tavani doldu" if butce_bitti
                     else "tur basarisiz")
            # BASARISIZ TUR SEBEBINI SOYLER -- ve bunu KOLTUK yapar.
            #
            # OLCULDU (21.09.2026), ilk gercek gemini turunda: tur
            # `cikis 41` ile dustu ve defterde TEK BIR aciklama yoktu.
            # `tur_ozeti` butun alanlari `null`, `birakildi` yalnizca
            # "tur basarisiz" -- yani neden dustugu HICBIR yerde
            # yazmiyordu. (Sebep, kasadaki `GEMINI_API_KEY`in tur
            # ortamina hic ulasmamasiydi ve motor bunu acikca
            # soyluyordu.)
            #
            # Adaptor sebebi `bitti.ek["hata"]` icinde veriyordu; onu
            # gorunur bir olaya ceviren yoktu. Duzeltme HER adaptore
            # ayri ayri degil BURAYA konuyor: "basarisiz tur sebebini
            # soyler" kurali koltugun kuralidir, ve her adaptorde
            # tekrarlanan bir kural en az birinde unutulur -- bu
            # projede iki kopyadan biri alti kez unutuldu.
            ham = str(sonuc.get("hata") or "").strip()
            if ham:
                yield self._olay("hata", ham[:600],
                                 {"sebep": sebep, "cikis": sonuc.get("cikis")},
                                 ajan_ad=ajan_ad, gorev_id=gorev["id"])
            self._birak(no, sebep)
            yield self._olay("birakildi", f"#{no} birakildi: {sebep}",
                             {"sebep": sebep}, ajan_ad=ajan_ad,
                             gorev_id=gorev["id"])
            # TEKRARLAYAN TAVAN KESINTISI GORUNUR OLMALI.
            #
            # Olculdu (21.09.2026): kilavuz isi $0,60 tavanda UC KEZ
            # ust uste kesildi. Her kesinti tek basina dogru davranisti
            # -- para kontrolu calisti -- ama toplamda $2,02 hicbir
            # teslimat uretmeden yandi ve dorduncu tur isi $0,16'ya
            # bitirdi. Yani tavan bu is turu icin yanlisti, ve bunu
            # SOYLEYEN hicbir sey yoktu.
            #
            # Ofis DUZELTMEZ, tavani kendi yukseltmez: bu bir para
            # karari ve para kararlari insanindir (`saglik.py`nin
            # "karar vermez, duzeltmez" kurali). Ama gormedigi bir seyi
            # insan yonetemez -- ikinci kesintiden itibaren soyler.
            if butce_bitti:
                yield from self._tavan_uyarisi(no, gorev, butce_usd)
            yield self._olay("tur_bitti", "",
                             {"basarili": False, "gorev_no": no, **sonuc})
            return

        # MCP acikken metin koprusu CALISMAZ: iki kanal acik kalirsa ayni
        # is icin cift kanit duser (olculdu: 3 arac cagrisi + 3 metin
        # satiri = 6 kanit). Kanit sayisi bir olcuttur; cift sayilirsa
        # olcut bozulur.
        eklenen = ([] if mcp_yapilandirma
                   else self._kanitlari_isle(no, ajan_ad, cevap))
        for k in eklenen:
            yield self._olay("kanit", f"#{no} {k['tur']}: {k['baslik']}",
                             dict(k), yaz=False)

        self.db.olay_yaz(
            self.proje_id, "rapor", cevap[:2000],
            ajan_ad=ajan_ad, gorev_id=gorev["id"],
        )

        if self.ofis.tahta.kanitlar(no):
            guncel = self.ofis.tahta.gorev(no)
            try:
                self.ofis.tahta.incelemeye_ver(no, guncel["revizyon"])
                yield self._olay("incelemede", f"#{no} incelemeye verildi",
                                 {"gorev_no": no}, ajan_ad=ajan_ad,
                                 gorev_id=gorev["id"])
            except TahtaHatasi as exc:
                yield self._olay("uyari", f"Incelemeye verilemedi: {exc}",
                                 {"gorev_no": no})
        else:
            yield self._olay(
                "uyari",
                f"#{no} kanitsiz kaldi -- 'calisiyor' durumunda bekliyor. "
                "Ajan KANIT bildirmedi.",
                {"gorev_no": no},
            )

        self._olcum_yaz(ajan_ad, gorev, sonuc)
        yield self._olay("tur_bitti", cevap,
                         {"basarili": True, "gorev_no": no,
                          "son_gorulen_olay_id": isaret, **sonuc})

    def _degisimi_olc(self, no, ajan_ad, gorev, once_anlik, kok_klasor):
        """Tur oncesi/sonrasi anlik goruntuyu karsilastirir ve yazar.

        Bu, kanit DEGILDIR ve kanit yerine de gecmez: kanit ajanin
        BILDIRDIGI seydir, bu ofisin KENDI olcumudur. Ikisi ayri
        defterlerde durur, yoksa olculen ile beyan edilen ayirt
        edilemez hale gelir.
        """
        # Canli ara kayit HER yolda silinir: kesin olcum alinsa da
        # alinamasa da tur bitti ve ara olcum artik "canli" degildir.
        try:
            yield from self._degisimi_olc_ic(no, ajan_ad, gorev,
                                             once_anlik, kok_klasor)
        finally:
            self._canli_temizle(gorev)

    @staticmethod
    def _tarayici_yazar(gorev) -> bool:
        """Tarayicida tiklama/form acik mi.

        Gorevin KENDI alani varsa kayitli deger gecer (`--web-salt-okur`
        ile bilincli daraltilmis is salt okunur kalir). Alani hic yoksa
        tarayici SERBEST kiptedir; o zaman kayitli 0 bir daraltma degil
        "alan yoktu" demektir (`gorev_ac` alansiz iste yazmayi 0 yazar)
        ve tiklama varsayilan olarak aciktir -- riskli eylem yine
        vekilde sorulur.
        """
        if not (gorev.get("tarayici_alani") or []):
            return True
        return bool(gorev.get("tarayici_yazma"))

    def _onayli_kaynaklar(self, gorev) -> list:
        """Bu is icin ONAYLANMIS yeni siteler (vekilin onay kayitlarindan).
        Yalniz alani DARALTILMIS iste anlamlidir; serbest tarayicida
        listeye bir sey eklemek onu daraltirdi."""
        KAYNAK_ISARETI = tarayici.KAYNAK_ISARETI
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT ayrinti FROM onay WHERE proje_id = ? AND gorev_id = ? "
                "AND durum = 'onaylandi' AND ayrinti LIKE ?",
                (self.proje_id, gorev["id"], f"%{KAYNAK_ISARETI}%")).fetchall()
        out = []
        for r in rows:
            for satir in str(r["ayrinti"] or "").splitlines():
                if satir.startswith(KAYNAK_ISARETI):
                    try:
                        k = tarayici.kaynak_normalle(satir[len(KAYNAK_ISARETI):])
                    except tarayici.TarayiciHatasi:
                        continue
                    if k not in out:
                        out.append(k)
        return out

    def _canli_izleyici(self, once_anlik, kok_klasor, gorev):
        self._canli_temizle(gorev)
        if once_anlik is None or not kok_klasor:
            return None
        try:
            return degisim.CanliIzleyici(
                kok_klasor, once_anlik,
                beyan=gorev.get("yazma_alani") or (),
                haric=degisim.ofis_dosyalari(self.db.yol))
        except OSError:
            return None

    def _canli_temizle(self, gorev) -> None:
        try:
            degisim.canli_sil(self.db, self.proje_id, gorev["id"])
        except sqlite3.Error:
            pass

    def _canli_tara(self, izleyici, no, ajan_ad, gorev):
        """Zamani geldiyse diski tarar, ara kaydi gunceller.

        Kayit defterine (olay) YALNIZ bir dosyaya bu turda ILK KEZ
        dokunuldugunda yazilir. Icerik guncellemeleri defteri buyutmez:
        olay tablosu kayit defteridir, terminal degil; panel ara kaydi
        `canli_degisim`den okur.
        """
        # Zamani gelmemisse HICBIR SEY yapilmaz -- sorgu bile: bu islev
        # her olayda (saniyede bir nabiz, her metin parcasi) cagrilir.
        if izleyici is None or not izleyici.zamani_mi():
            return
        try:
            kosan = len(self.ofis.tahta.liste(durum="calisiyor"))
        except TahtaHatasi:
            kosan = 1
        try:
            sonuc = izleyici.belki_tara(atif_belirsiz=kosan > 1)
            if sonuc:
                degisim.canli_yaz(self.db, self.proje_id, gorev["id"],
                                  ajan_ad, sonuc["degisen"], sonuc["kalkan"])
        except (OSError, sqlite3.Error) as exc:
            izleyici.kapali = ("canli izleme dustu: %s -- tur sonu olcumu "
                               "yine kosar" % exc.__class__.__name__)
            sonuc = None
        if sonuc and sonuc["yeni"]:
            yield self._olay(
                "dosya_canli",
                "yaziyor: " + ", ".join(sonuc["yeni"][:6])
                + (f" (+{len(sonuc['yeni']) - 6})"
                   if len(sonuc["yeni"]) > 6 else ""),
                {"gorev_no": no, "yollar": sonuc["yeni"]},
                ajan_ad=ajan_ad, gorev_id=gorev["id"])
        if izleyici.kapali:
            # Kapanis SESSIZ olmaz -- ve bir kez soylenir.
            yield self._olay("uyari", "Canli izleme: " + izleyici.kapali,
                             {"canli": False}, ajan_ad=ajan_ad,
                             gorev_id=gorev["id"])

    def _komsu_kostu_mu(self, gorev, ajan_ad) -> bool:
        """Bu turun PENCERESINDE baska bir ajan da kostu mu?

        OLCULDU (26.09.2026, deneme D11 -- gercek paralel is): uc isci ayni
        anda kostu; isci2'nin turu surerken oteki ikisi kendi dosyalarini
        yazip BITIRDI. Kural yalniz tur BITTIGI an "baska is calisiyor mu"
        diye bakiyordu -- o an ikisi coktan incelemedeydi. Fark onlarin
        dosyalarini isci2'ye yazdi, "BEYAN DISI" dedi, lider isi bu yanlis
        olcume dayanarak GERI GONDERDI ve isci2 baskalarinin dosyalarini
        silmeye kalkti (kapi durdurdu). Yanlis suclama, olcmemekten
        pahalidir: pencere turun BASINDAN SONUNA kadar bakilir.
        """
        try:
            if len(self.ofis.tahta.liste(durum="calisiyor")) > 1:
                return True
        except TahtaHatasi:
            return True
        bas = self._tur_basi.pop(gorev["id"], None)
        if bas is None:
            return True          # pencere bilinmiyor: suclamayiz
        with self.db.baglanti() as c:
            n = c.execute(
                "SELECT count(*) FROM olay WHERE proje_id = ? AND rowid > ?"
                " AND ajan_ad NOT IN ('', ?) AND tur IN"
                " ('sahiplenildi', 'basladi', 'tur_ozeti', 'arac', 'degisim')"
                " AND (gorev_id IS NULL OR gorev_id != ?)",
                (self.proje_id, bas, ajan_ad, gorev["id"])).fetchone()[0]
        return n > 0

    def _degisimi_olc_ic(self, no, ajan_ad, gorev, once_anlik, kok_klasor):
        if once_anlik is None or not kok_klasor:
            return
        try:
            sonra = degisim.anlik(kok_klasor,
                                  degisim.ofis_dosyalari(self.db.yol))
        except OSError as exc:
            yield self._olay("uyari", f"Degisim olculemedi: {exc}",
                             {"degisim": False}, ajan_ad=ajan_ad,
                             gorev_id=gorev["id"])
            return

        # ATIF: kokte baska bir tur da kosuyor mu? Paralellik acikken
        # (19.09) butun ajanlar ayni kokte calisir ve anlik goruntu
        # farki "kim yazdi" sorusunu cevaplayamaz. Fark yine yazilir,
        # ama beyan denetimi BASTIRILIR -- yanlis suclama, olcmemekten
        # pahalidir.
        belirsiz = self._komsu_kostu_mu(gorev, ajan_ad)

        kayitlar = degisim.karsilastir(
            once_anlik, sonra, beyan=gorev.get("yazma_alani") or (),
            atif_belirsiz=belirsiz)
        if not kayitlar:
            return
        # Yanlis yere birakilan YARDIMCI dosya ofisce dogru yere tasinir
        # (bkz. `degisim.yardimcilari_topla`); tasinan farktan duser.
        tasinan = degisim.yardimcilari_topla(kok_klasor, kayitlar,
                                             gorev.get("yazma_alani") or ())
        if tasinan:
            _t = {e for e, _ in tasinan}
            kayitlar = [k for k in kayitlar if k["yol"] not in _t]
            yield self._olay("yardimci_tasindi",
                             "Yardimci dosya dogru yere tasindi: "
                             + ", ".join(f"{e} -> {y}" for e, y in tasinan),
                             {"tasinan": tasinan}, ajan_ad=ajan_ad, gorev_id=gorev["id"])
            if not kayitlar:
                return
        degisim.yaz(self.db, self.proje_id, gorev["id"], ajan_ad, kayitlar)
        o = degisim.ozet(kayitlar)
        once_sha = self._golge_once.pop(gorev["id"], None)
        if once_sha:
            try:
                g = geri_al.Golge(kok_klasor, degisim.ofis_dosyalari(self.db.yol))
                geri_al.kaydet(self.db, self.proje_id, gorev["id"], ajan_ad,
                               kok_klasor, once_sha,
                               g.anlik(f"sonra #{no} {ajan_ad}"),
                               len(kayitlar), atif_belirsiz=belirsiz)
            except (geri_al.GeriAlHatasi, OSError,
                    subprocess.SubprocessError) as exc:
                yield self._olay("uyari",
                                 f"Geri alma kaydi yazilamadi: {exc}",
                                 {"geri_al": False}, ajan_ad=ajan_ad,
                                 gorev_id=gorev["id"])

        parcalar = [f"{o['dosya']} dosya", f"+{o['eklenen']}/-{o['silinen']}"]
        if o["beyan_disi"]:
            parcalar.append(f"{o['beyan_disi']} BEYAN DISI")
        if o["olculemeyen"]:
            parcalar.append(f"{o['olculemeyen']} olculemedi")
        if belirsiz:
            parcalar.append("atif belirsiz (paralel tur)")
        yield self._olay("degisim", "diskte degisen: " + " · ".join(parcalar),
                         {"gorev_no": no, **o}, ajan_ad=ajan_ad,
                         gorev_id=gorev["id"])

        # BEYAN DISI YAZMA GORUNUR OLUR -- ama is DURDURULMAZ.
        #
        # Kilit bir beyandir; beyanin disina yazmak 18.09'da (B) karari
        # alinirken kabul edilen bir bedeldi. Burada yapilan o bedeli
        # ilk kez OLCMEK. Isi burada kesmek, bugune kadar sessizce olan
        # bir seyi bir anda kirmak olurdu; karar insanin ve incelemenin.
        if o["beyan_disi"]:
            disari = [k["yol"] for k in kayitlar if k["beyan_disi"]][:8]
            yield self._olay(
                "uyari",
                "Beyan edilen yazma alaninin DISINA yazildi: "
                + ", ".join(disari)
                + f"  (alan: {', '.join(gorev.get('yazma_alani') or []) or '-'})",
                {"beyan_disi": disari}, ajan_ad=ajan_ad,
                gorev_id=gorev["id"])

    def _olcum_yaz(self, ajan_ad: str, gorev: dict, sonuc: dict) -> None:
        """Tur olcumlerini KALICI yazar -- basarili da basarisiz da.

        Akistan gecen sayilar surec bitince kaybolur; panelin durum rayi
        ve maliyet toplami bu kayittan okunur. Olcmedigimiz sey
        yonetilemez -- Yasa 2'nin faturasi tam burada okunur.
        """
        kullanim.tur_ozeti_yaz(
            self.db, self.proje_id, sonuc,
            # MOTOR ve HESAP da yazilir.
            #
            # Eksikti ve bedeli somuttu: "hangi hesabin limitinden ne
            # kadar gitti" sorusu cevaplanamiyordu. Modelden CIKARIM
            # yapilabilirdi ama bu projede bir kez odendi:
            # *cikarim yapma, kayda bak.* Ayrica zincir devrettiginde
            # tur baska bir motorda kosmus olabilir -- ajanin ayarina
            # bakmak YANLIS cevabi verir.
            motor=sonuc.get("motor") or "", hesap=sonuc.get("hesap") or "",
            ajan_ad=ajan_ad, gorev_id=gorev["id"],
        )

    def _kanitlari_isle(self, no: int, ajan_ad: str, cevap: str) -> list:
        """Ajanin bildirdigi kanitlari tahtaya gecirir.

        Kanit ICERIGI ajanindir. Koltuk yalnizca tasir -- uretmez, sushar,
        yorumlamaz. Uretseydi kapi kendi kendini onaylardi.
        """
        eklenen = []
        for tur, govde in KANIT_DESENI.findall(cevap or ""):
            govde = govde.strip()
            if not govde:
                continue
            baslik, _, icerik = govde.partition("->")
            kayit = self.ofis.tahta.kanit_ekle(
                no, tur.lower(), baslik.strip()[:200],
                (icerik or govde).strip()[:4000], ajan_ad,
            )
            eklenen.append(kayit)
        return eklenen

    # -- yardimcilar -------------------------------------------------------

    def _devam_metni(self, no: int, ajan_ad: str) -> str:
        """Ayni gorev surerken verilen metin: tam brifing DEGIL.

        Oturum zaten dolu; dort katmani tekrar vermek baglami sisirir ve
        dikkati bozar. Verilen sey yalnizca DEGISEN dunyadir + isin fisi.
        """
        parcalar = []
        # Bekledigin cevap geldiyse ONCE onu gor: soru sorup beklemeye
        # gecmis bir ajan icin en degerli bilgi budur.
        cevaplar = self.ofis.postane.cevaplar(ajan_ad, gorev_no=no)
        if cevaplar:
            satirlar = ["**Sorduklarinin cevabi geldi:**", ""]
            for c in cevaplar:
                satirlar.append(f"- _{c['govde'][:200]}_")
                satirlar.append(f"  -> **{c['cevap'][:400]}**")
            parcalar.append(chr(10).join(satirlar))
        # ONAYIN CEVABI DA VERILIR -- ve bu satir bir gercek turun
        # faturasiyla yazildi.
        #
        # Ofisin iki ayri bekleme sebebi var (*"soru_sor -> BILGISI
        # eksik, onay_iste -> YETKISI eksik"*) ve burada yalnizca
        # birincisi baglanmisti. OLCULDU: insan onayi verdi, ajan
        # bir sonraki turda bunu HIC ogrenmedi, eylemi tekrar
        # denemedi. Yalnizca durduran bir kapi isi kalici olarak
        # oldurur -- o zaman "onay" diye bir sey yoktur, yalnizca
        # yasak vardir.
        onaylar = self.ofis.postane.cevaplanan_onaylar(ajan_ad, gorev_no=no)
        if onaylar:
            satirlar = ["**Onay istediklerinin sonucu:**", ""]
            for x in onaylar:
                karar = ("ONAYLANDI -- simdi yapabilirsin"
                         if x["durum"] == "onaylandi"
                         else "REDDEDILDI -- BU YOLU TEKRAR DENEME")
                satirlar.append(f"- _{x['eylem'][:200]}_")
                satirlar.append(f"  -> **{karar}**")
                if (x["cevap_notu"] or "").strip():
                    satirlar.append(f"  patronun notu: {x['cevap_notu'][:300]}")
            # Onay TEK SEFERLIKTIR: yazmasaydik ajan bir kez alinan
            # izni surekli yetki sanardi.
            satirlar += [
                "",
                "Onaylanan eylem BIR KEZ gecer. Ayni eylemi sonra tekrar "
                "yapman gerekirse yeniden onay istenir.",
            ]
            parcalar.append(chr(10).join(satirlar))
        # DURDURULDUKTAN SONRA SURDURME (01.10.2026). Olculdu (gercek set
        # G16, claude): Durdur suren arac cagrisini keser; CLI bunu modele
        # "kullanici bu araci reddetti" diye bildirir. Surdurulen ajan
        # "Bash reddedildi, Write calismiyor" deyip iki kez lidere danisti.
        # Durdurmanin ne oldugu ACIKCA soylenir.
        try:
            with self.db.baglanti() as _c:
                _son = _c.execute(
                    "SELECT govde FROM olay WHERE proje_id = ? AND gorev_id = "
                    "(SELECT id FROM gorev WHERE proje_id = ? AND no = ?) AND tur = 'birakildi' "
                    "ORDER BY rowid DESC LIMIT 1", (self.proje_id, self.proje_id, no)).fetchone()
        except Exception:                        # noqa: BLE001
            _son = None
        if _son and "durdur" in (_son[0] or "").lower():
            parcalar.append(
                "**Onceki turun PATRON TARAFINDAN DURDURULDU; simdi 'Surdur' dedi.** "
                "Durdurma aninda suren aracin 'reddedildi / interrupted' sonucu "
                "DURDURMADAN geldi -- araclarin calisiyor, yasak yok. Kaldigin "
                "yerden devam et: once diske bak (hangi dosya yazilmis), yarim "
                "kalan adimi tamamla. Var olan bir dosyayi yazmadan once OKU.")
        uyanis = self.ofis.brifing.uyanis_metni(ajan_ad, self._son_isaret(ajan_ad))
        if uyanis:
            parcalar.append(uyanis)
        # OLCUT TEKRARLANMAZ: devam AYNI OTURUMDA kosar ve ajan
        # onu bu oturumun basinda okudu. Her devam turuna tekrar
        # bindirmek, Yasa 4'un tam tersi (birikmis baglam).
        parcalar.append(self.ofis.brifing.k4_gorev(no, olcut=False))
        # KANIT TALIMATI BURAYA YAZILMAZ.
        #
        # Kanit kanali MOTORA gore secilir: MCP konusan motora arac
        # cagrisi, konusmayana metin koprusu (motor/claude.py: KANIT_MCP /
        # KANIT_METIN). O secim sistem ekinde, her turda dogru motora
        # gore kuruluyor.
        #
        # Burada bir KOPYASI vardi ve kosulsuz METIN koprusunu dayatiyordu.
        # OLCULDU (daha once): iki kanal acik kalinca ajan ikisini de
        # kullandi, ayni is icin ALTI kanit dustu, ucu cift -- "kac kanit
        # var" olcutu bozuldu. Ayni hata devam yolunda yeniden kurulmustu
        # ve devam yolu, butce kesintisinden sonra artik cok daha sik
        # kosuyor.
        #
        # Kural TEK YERDE kalir. Iki yerde olsaydi biri duzeltilir, oteki
        # unutulurdu; bu projede tam olarak boyle iki hata cikti.
        return "\n\n---\n\n".join(parcalar)

    def _son_isaret(self, ajan_ad: str) -> int:
        """Ajanin en son gordugu olay. Kaba ama dogru yonde: ajanin kendi
        son olayindan sonrasi, onun gormedigi seydir."""
        with self.db.baglanti() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(id), 0) AS n FROM olay "
                "WHERE proje_id = ? AND ajan_ad = ?",
                (self.proje_id, ajan_ad),
            ).fetchone()
        return int(row["n"])

    def _klasor_hazirla(self, ajan: dict) -> str:
        """Her ajan KENDI klasorunde kosar.

        Ortak cwd, iki ajanin birbirinin gecici dosyasini ezmesi demektir
        -- ve bu, yazma kilidinin yakalayamadigi bir cakismadir: kilit
        gorev alanlarini korur, motorun kendi cop dosyalarini degil.
        """
        klasor = (ajan["klasor"] or "").strip()
        if not klasor:
            raise KoltukHatasi(
                f"{ajan['ad']} icin calisma klasoru tanimli degil. "
                "Ajan ise alinirken 'klasor' verilmeli."
            )
        yol = Path(klasor).expanduser()
        yol.mkdir(parents=True, exist_ok=True)
        return str(yol.resolve())

    def _durum_notu_yaz(self, no: int, ajan_ad: str, gorev: dict,
                        tam_metin: list) -> None:
        """Turun SON `DURUM:` satirini deftere gecirir.

        Yalnizca SONUNCUSU: ajan ilerledikce notunu yeniler ve gecerli olan
        en yenisidir. Ayni not tekrar yazilmaz -- devam turunda eski satir
        yeniden gecerse defter ayni cumleyle dolmasin.

        Not ajanin SOZUDUR; devir paketi onu oyle etiketler. Yazamamak
        turu durdurmaz: not bir kolaylik, kapi degil.
        """
        bulunan = DURUM_DESENI.findall("".join(tam_metin or []))
        if not bulunan:
            return
        yeni = bulunan[-1].strip()[:500]
        if not yeni:
            return
        with self.db.baglanti() as conn:
            son = conn.execute(
                "SELECT govde FROM olay WHERE proje_id = ? AND gorev_id = ?"
                " AND tur = 'durum_notu' ORDER BY olusturuldu DESC, rowid DESC"
                " LIMIT 1", (self.proje_id, gorev["id"])).fetchone()
        if son and son["govde"] == yeni:
            return
        self.db.olay_yaz(self.proje_id, "durum_notu", yeni,
                         ajan_ad=ajan_ad, gorev_id=gorev["id"])

    def _birak(self, no: int, sebep: str) -> None:
        try:
            self.ofis.tahta.birak(no, sebep=sebep)
        except TahtaHatasi:
            pass  # gorev araya girip kapanmis olabilir; kilit zaten yok

    def _tamponu_dok(self, tampon: list, no: int, ajan_ad: str) -> None:
        if not tampon:
            return
        govde = "".join(tampon).strip()
        tampon.clear()
        if not govde:
            return
        gorev = self.ofis.tahta.gorev(no)
        self.db.olay_yaz(self.proje_id, "cikti", govde[:4000],
                         ajan_ad=ajan_ad, gorev_id=gorev["id"])

    #: Turun KAYNAK tukenmesinden kesildigini soyleyen birakilma sebepleri.
    #: Bunlar HATA degildir: is dogru gidiyordu, kaynak bitti.
    # "kesinti" (01.10.2026): panel/bilgisayar is ortasinda kapandi. Is
    # dogru gidiyordu; acilista ofis birakir, ajan AYNI oturumdan surer.
    KAYNAK_SEBEPLERI = ("kullanim limiti", "zaman asimi", "butce",
                        "insan durdurdu", "kesinti")

    #: Patron notu ve durdurma istegi defterden ne siklikla okunur. Motor
    #: sessizken bile saniyede bir `nabiz` akar, yani gecikme ~1 sn +
    #: motorun iletme ani (claude: bir sonraki arac siniri).
    NOT_ARALIGI_S = 1.0

    def _bekleyen_not_idleri(self, no: int, ajan_ad: str) -> list:
        try:
            return [n["id"] for n in
                    self.ofis.postane.bekleyen_notlar(ajan_ad, gorev_no=no)]
        except sqlite3.Error:
            return []

    def _kanali_besle(self, kanal, kd: dict, no: int, ajan_ad: str,
                      gorev: dict):
        """Defterdeki YENI notlari kanala, durdurma istegini motora tasir.

        Kanal yoksa (motor tasiyamiyor) hicbir sey itilmez: not defterde
        bekler ve bir sonraki turun basinda gider. Durdurma da o motorda
        tur ortasinda UYGULANAMAZ -- halka tur sinirinda durur; bu SOYLENIR.
        """
        if (durdurma_istendi(self.db, self.proje_id)
                or self._duraklatildi_mi(gorev["id"])):
            if kanal is not None and not kanal.durdurulsun:
                kanal.durdur()
                yield self._olay("uyari",
                                 f"#{no} {ajan_ad} turu insanin istegiyle "
                                 "KESILIYOR (kismi kanit korunur).",
                                 {"gorev_no": no}, ajan_ad=ajan_ad,
                                 gorev_id=gorev["id"])
            elif kanal is None and not kd["durdur_soylendi"]:
                kd["durdur_soylendi"] = True
                yield self._olay("uyari",
                                 f"#{no} {ajan_ad}'in motoru turu ortasinda "
                                 "kesemiyor; tur bitince durulacak.",
                                 {"gorev_no": no}, ajan_ad=ajan_ad,
                                 gorev_id=gorev["id"])
            return
        if kanal is None:
            return
        for n in self.ofis.postane.bekleyen_notlar(ajan_ad, gorev_no=no):
            if n["id"] in kd["itilen"]:
                continue
            kd["itilen"].add(n["id"])
            kanal.gonder(n["id"], self.not_metni(n["govde"]))

    def _duraklatildi_mi(self, gorev_id: str) -> bool:
        """Patron bu isi DURAKLATTI mi (tahta.duraklat)? Defterden, taze."""
        try:
            with self.db.baglanti() as conn:
                r = conn.execute("SELECT duraklatildi FROM gorev WHERE id = ?",
                                 (gorev_id,)).fetchone()
        except sqlite3.Error:
            return False
        return bool(r and r[0])

    @staticmethod
    def not_metni(govde: str) -> str:
        """Tur surerken ajana giden notun bicimi. Adaptor BICIMLENDIRMEZ."""
        return ("PATRONUN NOTU (sen calisirken geldi): " + govde.strip()
                + "\n\n" + NOT_KURALI + " Ona gore devam et.")

    def _devam_mi(self, no: int, ajan_ad: str, ajan: dict, gorev: dict) -> bool:
        """Bu tur, oncekinin USTUNE mi kosacak yoksa SIFIRDAN mi?

        Iki durumda devam edilir:

        1. Gorev hala bu ajanda ve `calisiyor` -- klasik hal (soru sorup
           cevap almis ajan, yarim isini surduruyor).
        2. Gorev BIRAKILMIS ama sebebi KAYNAK TUKENMESI ve oturum hala bu
           ise ait. OLCULDU (19.09.2026): arastirma turu butce tavanina
           takildi, `birak` calisti, gorev `hazir`a dondu ve bir sonraki
           tur SIFIRDAN kostu -- 17 arama, 208.148 jeton yeniden. Oysa
           model tarafinda oturum duruyordu; tek eksik onu kullanmakti.

        Ayrimi yapan sey SEBEPTIR: kaynak tukenmesi bir hata degildir, is
        dogru gidiyordu. Gercek bir hatadan sonra devam etmek ise ayni
        hatali durumu tasimak olurdu -- orada temiz baslangic dogrudur.

        Oturumun BU ISE ait oldugu ayrica dogrulanir: ajan arada baska bir
        is yaptiysa oturumu artik o isi tasir ve buraya baglanmamalidir.
        """
        if not ajan.get("oturum_id"):
            return False
        if gorev["sahip"] == ajan_ad and gorev["durum"] == "calisiyor":
            return True
        if gorev["durum"] != "hazir":
            return False

        with self.db.baglanti() as conn:
            son_oturum = conn.execute(
                "SELECT gorev_id FROM olay WHERE proje_id = ? AND tur = 'oturum' "
                "AND ajan_ad = ? ORDER BY olusturuldu DESC, rowid DESC LIMIT 1",
                (self.proje_id, ajan_ad),
            ).fetchone()
            if not son_oturum or son_oturum["gorev_id"] != gorev["id"]:
                return False
            son_birakma = conn.execute(
                "SELECT govde FROM olay WHERE proje_id = ? AND tur = 'birakildi' "
                "AND gorev_id = ? ORDER BY olusturuldu DESC, rowid DESC LIMIT 1",
                (self.proje_id, gorev["id"]),
            ).fetchone()
        if not son_birakma:
            return False
        sebep = (son_birakma["govde"] or "").lower()
        return any(k in sebep for k in self.KAYNAK_SEBEPLERI)

    #: Kacinci tavan kesintisinden sonra insana soylenir.
    #: 1 olsaydi her sıradan kesinti gurultu olurdu; 3 olsaydi bir tur
    #: daha bosa giderdi. Ikinci kesinti bir DESENDIR -- ret sayacinin
    #: esigiyle (`YUKSELTME_ESIGI = 2`) ayni mantik.
    TAVAN_UYARI_ESIGI = 2

    def _tavan_uyarisi(self, no: int, gorev: dict, butce_usd):
        """Ayni is tekrar tekrar tavanda kesiliyorsa insana SOYLE."""
        import json as _json
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT govde FROM olay WHERE proje_id = ? AND gorev_id = ? "
                "AND tur = 'tur_ozeti'", (self.proje_id, gorev["id"])).fetchall()
            kesinti = conn.execute(
                "SELECT COUNT(*) n FROM olay WHERE proje_id = ? AND gorev_id = ? "
                "AND tur = 'birakildi' AND govde LIKE '%butce%'",
                (self.proje_id, gorev["id"])).fetchone()["n"]
        if kesinti < self.TAVAN_UYARI_ESIGI:
            return
        toplam = 0.0
        for r in rows:
            try:
                toplam += _json.loads(r["govde"]).get("maliyet_usd") or 0
            except (ValueError, TypeError):
                continue
        yield self._olay(
            "uyari",
            f"#{no} butce tavaninda {kesinti}. kez kesildi "
            f"(tur tavani ${float(butce_usd or 0):.2f}, bu ise toplam "
            f"${toplam:.2f} gitti). Tavan bu IS TURU icin dusuk olabilir: "
            "olculen profil kod ~$0,09 · arastirma ~$0,62 · tarayici ~$0,67 "
            "· dokuman ~$2,18. Tavani yukseltmek ya da isi bolmek gerekir; "
            "ofis kendi yukseltmez, para karari senindir.",
            gorev_id=gorev["id"])

    def _olay(self, tur: str, govde: str = "", ek: dict = None, *,
              yaz: bool = True, ajan_ad: str = "", gorev_id: str = None) -> dict:
        if yaz:
            self.db.olay_yaz(self.proje_id, tur, govde[:2000],
                             ajan_ad=ajan_ad, gorev_id=gorev_id)
        return {"tur": tur, "govde": govde, "ek": ek or {}, "an": simdi()}
