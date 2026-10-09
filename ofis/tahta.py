# -*- coding: utf-8 -*-
"""Tahta: gorevler, DAG bagimliliklari, yazma kilidi ve kanit kapisi.

Dort degismez; her biri ihlal edildiginde sistemin sessizce guvenilmez
oldugu olculmus durumlar:

1. **Yazma alani GERCEK KILITTIR.** Bir yol oneki ayni anda tek ajana ait
   olur. Cakisan talep REDDEDILIR. (Cognition: birden fazla ajan ayni anda
   yazarsa cakisan kararlar cikar -- stil, kenar durumu, desen.) Uyari
   yetmez; uyari gorulmez, ret gorulur.

2. **Bagimliliklar DAG olmalidir.** Dongu eklenmeye calisilirsa reddedilir.
   Dongu = hicbir isin asla hazir olmamasi; tahta calisiyor gorunur ama
   hicbir sey ilerlemez.

3. **Her mutasyon revizyon tasir (CAS).** Bayat yazar reddedilir. Iki lider
   ayni isi es zamanli duzenlerse biri otekini sessizce ezmesin.

4. **Kanitsiz gorev kapanmaz.** `bitti` durumuna gecis, `kanit` tablosunda
   en az bir satir ister. (MAST: hatalarin %21,3'u dogrulama eksikligi.)
   "Calisiyor" demek kanit degil, iddiadir.

Ayrica: `neden`, `ana_hedef` ve `kabul_olcutu` bos birakilamaz. MAST'in en
buyuk hata kumesi (%41,8) belirtim/sistem tasarimi; gorev nicin var oldugunu
tasimazsa ajan isi kusursuz yapip projeyi iskalar.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

from .klasor import klasorleri_dogrula, metinler
from . import baglayici, tarayici
from .db import simdi

BEKLIYOR = "bekliyor"
HAZIR = "hazir"
CALISIYOR = "calisiyor"
INCELEME = "inceleme"
BITTI = "bitti"
IPTAL = "iptal"
DURUMLAR = (BEKLIYOR, HAZIR, CALISIYOR, INCELEME, BITTI, IPTAL)

#: Kilit kirasi. Ajan olur, elektrik giderse kilit sonsuza kadar kalmasin.
#: Nabiz bu sureyi asarsa kilit dusmus sayilir ve is yeniden sahiplenilebilir.
KILIT_KIRA_SANIYE = 180

from . import surec as _surec  # noqa: E402 -- kesintiden devam (01.10)

MAKS_GOREV = 512


#: Isin gerektirdigi guc. Rol KIMIN yapacagini, zorluk NE KADAR GUCLE
#: yapilacagini soyler. Ikisi ayri sorudur: ayni ajan kolay isi ucuz
#: modelde, zor isi guclu modelde kosabilmeli.
ZORLUKLAR = ("kolay", "orta", "zor", "cok_zor")


def medya_hedefi(kok, alanlar, ad: str) -> Path:
    """Uretilen dosyanin (gorsel/video) yazilacagi yer -- yazma alaninin ICI.

    TEK YERDE. Bu karar dort yerde kopyaydi (MCP gorsel/video, kabuk
    gorsel/video ekle) ve dordu de alanin ilk ogesini KLASOR sayiyordu.
    Olculdu (26.09.2026, deneme D08): alan `kapak.png` idi; gorsel
    `kapak.png/kapak.png` icine yazildi, `kapak.png` bir KLASOR oldu.

    Kural: alan bir DOSYA yoluysa (uzantisi var, klasor degil) tam oraya;
    klasorse icine `ad` ile. Birden cok alan varsa uzantisi `ad`inkine
    uyan dosya once secilir. Alan yoksa kokun kendisine.
    """
    kok = Path(kok)
    ad = Path(ad).name
    alanlar = [str(a).strip().rstrip("/\\") for a in (alanlar or []) if str(a).strip()]
    if not alanlar:
        return kok / ad

    def dosya_mi(a):
        return bool(Path(a).suffix) and not (kok / a).is_dir()

    uzanti = Path(ad).suffix.lower()
    for a in alanlar:
        if dosya_mi(a) and Path(a).suffix.lower() == uzanti:
            return kok / a
    for a in alanlar:
        if not dosya_mi(a):
            return kok / a / ad
    # Butun alanlar DOSYA ve hicbiri bu turde degil: `rapor.md`nin uzerine
    # bir PNG yazmak sessizce veri yok etmek olurdu. Reddedilir, sebep
    # soylenir -- alani genisletmek lider/insanin karari.
    raise TahtaHatasi(
        f"Yazma alaninda '{uzanti or ad}' turunde bir dosya ya da bir klasor "
        f"yok ({', '.join(alanlar)}). Uretilen dosya baska bir dosyanin "
        "uzerine yazilmaz; yazma alanina bir klasor ya da bu adda bir dosya "
        "eklenmeli.")



def kanat_koku(db, kanat_id) -> str:
    """Takimin kendi klasoru ("" = yok; proje koku kullanilir). TEK yer."""
    if not kanat_id:
        return ""
    try:
        with db.baglanti() as c:
            r = c.execute("SELECT klasor FROM kanat WHERE id = ?", (kanat_id,)).fetchone()
    except Exception:                         # noqa: BLE001 -- eski defter: sutun yok
        return ""
    return ((r["klasor"] if r else "") or "").strip()


def _kok_anahtari(kok: str) -> str:
    try:
        return str(Path(kok).resolve()).lower() if kok else ""
    except (OSError, ValueError):
        return str(kok).lower()

class TahtaHatasi(RuntimeError):
    pass


class RevizyonCakismasi(TahtaHatasi):
    """Bayat yazar: elindeki revizyon artik guncel degil."""


class KilitCakismasi(TahtaHatasi):
    """Talep edilen yol baskasinda. Uyari degil, ret."""


def yol_normalle(deger: str) -> str:
    temiz = str(deger or "").strip().replace("\\", "/").strip("/")
    parcalar = [p for p in temiz.split("/") if p not in ("", ".")]
    return "/".join(parcalar)


def _altinda(yol: "Path", kok: "Path") -> bool:
    """`yol`, `kok`un altinda mi -- diske dokunmadan, metinsel."""
    try:
        yol.relative_to(kok)
        return True
    except ValueError:
        return False


def kok_goreli(deger: str, kok: str) -> str:
    """Mutlak bir yazma alanini KOK-GORELI hale getirir.

    OLCULMUS HATA (21.09.2026) -- Yasa 1'i SESSIZCE deliyordu:

    Lider `C:/Users/pc/Desktop/AgentOfis/KILAVUZ.md` diye MUTLAK bir
    alan yazdi. `yol_normalle` onu oldugu gibi sakladi ve kilit, AYNI
    dosyayi gosteren `KILAVUZ.md` (kok-goreli) ile bu mutlak yolu
    FARKLI iki yol saydi. Yani iki is ayni dosyaya yazabilir ve kilit
    makinesi bunu HIC GORMEZ -- "cakisan talep reddedilir" kuralinin
    sessizce delinmesi.

    Kilit ONEK eslesmesiyle calisir (`yollar_cakisir`). Onek
    karsilastirmasinin anlamli olmasi icin butun yollarin AYNI KOKE
    gore ifade edilmis olmasi sarttir; karisik iki gosterim cakismayi
    gorunmez kilar.

    Kokun DISINDAKI mutlak yol oldugu gibi birakilir: o baska bir
    agactir ve kok-goreli bir yolla zaten karisamaz.
    """
    temiz = yol_normalle(deger)
    if not temiz or not kok:
        return temiz
    try:
        p = Path(temiz)
        if not p.is_absolute():
            return temiz
        return yol_normalle(str(p.relative_to(Path(kok))))
    except (ValueError, OSError):
        return temiz


def yollar_cakisir(a: str, b: str) -> bool:
    """Onek eslesmesi yeterlidir: `api` ile `api/orders` cakisir."""
    if not a or not b:
        return False
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _yas_saniye(zaman: str) -> float:
    try:
        t = datetime.fromisoformat(zaman)
    except ValueError:
        return 1e9
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds()


class Tahta:
    def __init__(self, db, proje_id: str) -> None:
        self.db = db
        self.proje_id = proje_id
        #: DURDURULMUS ajanlarin adlarini donduren islev. Ofis kurulurken
        #: baglanir (bkz. ofis/__init__.py). Tahta postaneyi ITHAL ETMEZ:
        #: katman sirasi tahta -> postane'dir, tersi degil. Bir islevle
        #: baglamak, bagimliligi ters cevirmeden bilgiyi ulastirir.
        self.duraklatilmis_kaynak = None

    def _duraklatilmis(self) -> tuple:
        if not self.duraklatilmis_kaynak:
            return ()
        try:
            return tuple(self.duraklatilmis_kaynak())
        except Exception:
            # Bilgi alinamiyorsa ESKI davranisa duseriz (kilit dusebilir).
            # Sessizce KILIDI KORUMAK daha tehlikeli olurdu: olmus bir
            # ajanin isi sonsuza kadar asili kalirdi.
            return ()

    # -- gorev acma --------------------------------------------------------

    def kok_klasor(self, kanat_id: str = None) -> str:
        """Isin kok klasoru -- takimin klasoru, yoksa projenin; yoksa bos.

        Iki yerden okunuyordu (dogrulama ve alan normallestirme); tek
        yere alindi. Bu projede iki kopyadan biri duzeltilip oteki
        unutuldugu icin bes kez hata cikti. TAKIM KLASORU (06.10.2026,
        patron: "her takim ayri"): takimin kendi koku varsa O.
        """
        tk = kanat_koku(self.db, kanat_id)
        if tk:
            return tk
        kok = ((self.ofis.proje or {}).get("kok_klasor")
               if hasattr(self, "ofis") else None)
        if kok:
            return kok
        with self.db.baglanti() as c:
            r = c.execute("SELECT kok_klasor FROM proje WHERE id=?",
                          (self.proje_id,)).fetchone()
        return (r["kok_klasor"] if r else "") or ""

    def gorev_koku(self, gorev_or_id) -> str:
        """Bir isin kok klasoru (isin takimina gore)."""
        g = gorev_or_id
        if not isinstance(g, dict):
            with self.db.baglanti() as c:
                r = c.execute("SELECT kanat_id FROM gorev WHERE id = ?", (g,)).fetchone()
            g = dict(r) if r else {}
        return self.kok_klasor(g.get("kanat_id") or None)

    def _alanlari_dogrula(self, alanlar, ek_klasorler=None, kok: str = None,
                          uyar: bool = True) -> None:
        """Yazma alani PROJE KOKUNDE gercekten var mi.

        OLCULMUS HATA (21.09.2026) -- ve bedeli $2'ydi:

        Hedefte *"`ofis/motor/` icine kur"* yazdim. Lider bunu
        `yazma_alani: ["ofis/motor"]` diye yazdi, tahta KABUL ETTI, is
        uc tur kostu. Ama ofisin proje koku `.../AgentOfis/calisma` --
        yani `kok/ofis/motor` diye bir yer YOK, ve ofisin kendi kaynak
        kodu proje kapsaminin TAMAMEN DISINDA.

        Ajan bunu turun ortasinda kesfetti, dogru davranip bildirdi ve
        yerine bir "PROVA paketi" uydurmak zorunda kaldi:

            "ofis/motor/ yazilamadigi icin, kurulmaya hazir dosyalari
             ayni paket duzeninde bir PROVA paketine..."

        Yani is *yapilmis gibi* gorundu ama hicbir yere kurulmadi --
        projenin karsi kuruldugu sinifin ta kendisi.

        **Var olmayan bir yazma alani, sessiz bir olum sebebidir.**
        Klasor kapisinda ayni kural zaten yaziliydi (*"var olmayan
        klasor reddedilir; `--add-dir` onu kabul eder, ajan
        'bulamadim' der"*) -- ama yazma alanina hic uygulanmamisti.

        UST KLASORE bakiyoruz, alanin kendisine degil: yeni bir dosya
        ya da alt klasor acmak mesrudur, olmayan bir AGACA yazmak
        degil. `ek_klasorler` ile acilan yerler de kabul edilir.
        """
        if not alanlar:
            return
        kok = kok if kok is not None else self.kok_klasor()
        # KOKUN TAMAMI yazma alani olamaz (27.09.2026, motor matrisi olctu):
        # `["."]` normallesince BOS kaliyordu ve gorev_ac onu SESSIZCE
        # suzuyordu. Gorev "yazma alani belirtilmemis" diye acildi ve HIC
        # KILIT ALINMADI (Yasa 1 delindi); codex dogru davranip sordu,
        # claude sormadan yazdi. Kokun tamamini kilitlemek de cozum degil:
        # her paralel isi durdururdu. Reddedilir ve NE yapilacagi soylenir.
        butun = [str(y) for y in alanlar
                 if str(y).strip() and not kok_goreli(str(y), kok or "")]
        if butun:
            raise TahtaHatasi(
                f"Yazma alani {butun} proje kokunun TAMAMI demek; kabul "
                "edilmez. Kokun tamami kilitlenirse her paralel is durur, "
                "kilitlenmezse yazma kilidi hic calismaz. Isin yazacagi "
                "dosya ya da klasorleri TEK TEK yaz (orn. [\"rapor.md\", \"src/\"]).")
        if not kok:
            return          # kok bilinmiyorsa OLCEMEYIZ; uydurmayiz
        kokp = Path(kok)
        if not kokp.exists():
            return          # kok yoksa bu denetim bir sey soyleyemez

        # IKI AYRI HAL, IKI AYRI DAVRANIS:
        #
        #  (a) Alan kokte YOK ama AYNI ADLA kokun DISINDA VAR. Bu bir
        #      tahmin degil, guclu bir isaret: yazan kisi disaridakini
        #      kastetti ve oraya ERISEMEZ. REDDEDILIR. (Benim hatam tam
        #      buydu: `ofis/motor` gercekte AgentOfis/ofis/motor'du,
        #      proje koku ise AgentOfis/calisma.)
        #
        #  (b) Alan hicbir yerde yok. Yazim hatasi OLABILIR ama yeni
        #      bir klasor acmak da mesrudur. Emin olmadigimiza "yanlis"
        #      demeyiz: GECER, ama gorunur bir `uyari` olur. (saglik.py
        #      kurali: olcemedigimize hukum vermeyiz, sessiz de kalmayiz.)
        #
        #  ACILAN KLASORLER DE SAYILIR. Bu parametre ALINIYOR ama HIC
        #  KULLANILMIYORDU -- ve docstring "kabul edilir" diye yaziyordu.
        #  Bedeli gercek kosuda cikti: `--klasor` ile AgentOfis acilmisken
        #  kapi yine reddetti ve care olarak *"o yeri --klasor ile ac"*
        #  dedi, yani ZATEN YAPILMIS olan seyi. Iki ders birden:
        #  sessizce yok sayilan ayar ayar degildir, ve teshis koyup
        #  ISLEMEYEN bir care soylemek care soylememekten kotudur.
        aciklar = []
        for d in (ek_klasorler or []):
            try:
                dp = Path(str(d))
                if dp.exists():
                    aciklar.append(dp)
            except (OSError, ValueError):
                continue

        disarida, supheli, kok_adli = [], [], []
        ust = kokp.parent
        for alan in alanlar:
            # MUTLAK YOL KOK DENETIMINI TAMAMEN ATLIYORDU.
            # pathlib'de `kok / "C:/x"` -> `C:/x`: kok DUSER. Yani
            # mutlak bir alanin "ust klasoru var mi" sorusu her zaman
            # kendi ust klasorune bakiyordu ve `C:/Windows/System32`
            # bile kapidan geciyordu. Olculdu (21.09.2026).
            p_alan = Path(alan)
            if p_alan.is_absolute():
                if _altinda(p_alan, kokp) or any(_altinda(p_alan, d)
                                                 for d in aciklar):
                    continue
                disarida.append(alan)
                continue
            hedef = kokp / alan
            if hedef.exists() or hedef.parent.exists():
                continue
            # Acilan bir klasorden ERISILEBILIYORSA olu yol degildir.
            if any((d / alan).exists() or (d / alan).parent.exists()
                   for d in aciklar):
                continue
            ilk = alan.split("/")[0]
            if ilk and ilk == kokp.name:
                kok_adli.append(alan)
            elif ilk and (ust / ilk).exists():
                disarida.append(alan)
            else:
                supheli.append(alan)
        # Uyari TEK KEZ yazilir (09.10 canli: plan kapisi + gorev_ac ayni
        # uyariyi iki kez yaziyordu); plan kapisi `uyar=False` ile sorar.
        for alan in (supheli if uyar else []):
            self.db.olay_yaz(
                self.proje_id, "uyari",
                f"Yazma alani '{alan}' proje kokunde yok -- yeni aciliyorsa "
                "sorun degil, yazim hatasiysa is bos yere kosar.")
        if kok_adli:
            # KOKUN KENDI ADI YOLA EKLENMIS -- ayri teshis. Genel mesaj
            # "kokun disini kastettin" diyordu; yanlis teshis, yanlis care:
            # lider ikinci denemede ayni hatayi yapti (D11, 26.09.2026).
            duzgun = [a.split("/", 1)[1] if "/" in a else a for a in kok_adli]
            raise TahtaHatasi(
                "Yazma alaninin basinda KOKUN KENDI ADI var: "
                + ", ".join(kok_adli)
                + f"\n  '{kokp.name}/' proje kokunun adi; yollar kokun ICINDEN "
                "yazilir. Dogrusu: " + ", ".join(duzgun))
        if not disarida:
            return
        mevcut = sorted(p.name for p in kokp.iterdir() if p.is_dir())[:12]
        raise TahtaHatasi(
            "Yazma alani proje kokunde YOK: " + ", ".join(disarida)
            + f"\n  proje koku : {kok}"
            + f"\n  kokte olan : {', '.join(mevcut) or '(bos)'}"
            + f"\n  AMA ayni ad kokun DISINDA var: {ust}"
            + (f"\n  acik klasorler DE denendi: "
               f"{', '.join(str(d) for d in aciklar)}" if aciklar else "")
            + "\n  Yani kokun disindaki bir yeri kastettin ve oraya"
              " ERISILEMEZ. Ajan bunu turun ORTASINDA kesfeder; is"
              " yapilmis GORUNUR ama hicbir yere yazilmaz."
            # "--klasor ile ac" tavsiyesi YALNIZ hic klasor acilmamissa
            # verilir. Acilmisken onu onermek, insana yapilmis olani
            # yaptirmaya calismaktir.
            + ("\n  Alani kokteki gercek bir yola gore yaz."
               if aciklar else
               "\n  Alani kokteki gercek bir yola gore yaz, ya da o yeri"
               " `--klasor` ile ac."))

    def gorev_ac(self, baslik: str, *, neden: str, ana_hedef: str,
                 kabul_olcutu: str, govde: str = "", yazma_alani=None,
                 sahip: str = "", kanat_id: str = None, oncelik: str = "normal",
                 bagli_oldugu=None, acan: str = "lider", ek_klasorler=None,
                 zorluk: str = "", zorluk_gerekce: str = "",
                 tarayici_alani=None, tarayici_yazma: bool = True,
                 baglayicilar=None, tarayici_kabin: bool = False) -> dict:
        """Yeni gorev. Uc alan zorunludur ve bu bilerek boyledir.

        `neden` olmadan ajan isin amacini bilmez.
        `ana_hedef` olmadan lider sonucu DOGRU seye karsi inceleyemez.
        `kabul_olcutu` olmadan 'bitti'nin ne demek oldugu belirsizdir.

        `ek_klasorler` ofisin DISINDA acilan mutlak yollardir (insanin
        masaustundeki bir proje gibi). Goreve yazilir, ajana degil:
        aciklik ISIN ozelligidir. Ajana yazsaydik bir kez acilan klasor
        o ajanin butun gelecek islerinde acik kalirdi -- kimse fark
        etmeden genisleyen bir yetki.
        """
        for alan, deger in (("neden", neden), ("ana_hedef", ana_hedef),
                            ("kabul_olcutu", kabul_olcutu)):
            if not (deger or "").strip():
                raise TahtaHatasi(
                    f"'{alan}' bos birakilamaz. Belirtim eksikligi, olculmus en buyuk "
                    "hata kumesidir (%41,8) -- gorev nicin var oldugunu tasimazsa "
                    "ajan isi kusursuz yapip hedefi iskalar."
                )

        # KOK-GORELI SAKLANIR. Mutlak bir alan oldugu gibi saklansaydi
        # kilit, ayni dosyayi gosteren iki yazimi (`KILAVUZ.md` ve
        # `C:/.../calisma/KILAVUZ.md`) farkli sayar ve cakismayi HIC
        # gormezdi -- Yasa 1'in sessizce delinmesi (bkz. `kok_goreli`).
        _kok = self.kok_klasor(kanat_id or None)
        # Bos girdi (`""`) atlanir; ama `"."` gibi normallesince bos kalan
        # bir alan SUZULMEZ, kapiya gider ve reddedilir (bkz. _alanlari_dogrula).
        ham = [str(y).strip() for y in (yazma_alani or []) if str(y).strip()]
        self._alanlari_dogrula([y for y in ham if not kok_goreli(y, _kok)],
                               ek_klasorler, kok=_kok)
        alanlar = [kok_goreli(y, _kok) for y in ham]
        self._alanlari_dogrula(alanlar, ek_klasorler, kok=_kok)
        # Var olmadigi ANINDA reddedilir; sessizce atlanan bir klasor,
        # ajanin "bulamadim" demesiyle ortaya cikardi.
        ekler = metinler(klasorleri_dogrula(ek_klasorler))

        # ZORLUK: gerekli guc ISIN ozelligidir. Bos birakilabilir --
        # o zaman ajanin kendi modeli kullanilir.
        # "cok zor" / "çok zor" / "cok-zor" -> "cok_zor": lider JSON'da
        # farkli yazabilir; bicim yuzunden plan dusmesin.
        zorluk = ((zorluk or "").strip().lower().replace("ç", "c")
                  .replace(" ", "_").replace("-", "_"))
        if zorluk and zorluk not in ZORLUKLAR:
            raise TahtaHatasi(
                f"Bilinmeyen zorluk: {zorluk!r}. Secenekler: {', '.join(ZORLUKLAR)}")
        # PAHALI SECIM GEREKCE ISTER -- fan-out kapisinin ayni mantigi.
        # Gerekcesiz 'zor', her isi guclu modele kaydirmanin en kolay
        # yoludur ve faturayi sessizce buyutur.
        if zorluk in ("zor", "cok_zor") and not (zorluk_gerekce or "").strip():
            raise TahtaHatasi(
                f"zorluk='{zorluk}' icin GEREKCE zorunlu. Guclu model pahalidir; "
                "neden gerektigini yazmadan secilmez.")
        # TARAYICI ALANI: yazma alaninin WEB hali. Beyan edilmeyen
        # kaynak acilmaz. Bos ise tarayici HIC verilmez -- klasor
        # gibi: acikligi is beyan eder, ajan degil.
        tarayici_kaynaklari = tarayici.kaynaklari_dogrula(tarayici_alani)
        # BAGLAYICILAR: yetki bekleyen ya da olmayan bir baglayici
        # KAPALI KALARAK reddedilir -- odenmis ama calismayacak bir
        # tur, hicbir tur olmamasindan kotudur.
        baglar = baglayici.dogrula(baglayicilar) if baglayicilar else []
        an = simdi()
        gorev_id = uuid.uuid4().hex

        with self.db.baglanti() as conn:
            adet = conn.execute(
                "SELECT COUNT(*) AS n FROM gorev WHERE proje_id = ? AND silindi = 0",
                (self.proje_id,),
            ).fetchone()["n"]
            if adet >= MAKS_GOREV:
                raise TahtaHatasi(f"Tahta doldu ({MAKS_GOREV}). Biten isleri arsivle.")

            # TAKIMSIZ IS ACILMAZ (01.10.2026, cok takim): takimi bos is
            # baska takimin halkasinda baska takimin ajanina gidiyordu. Sahibi
            # varsa onun takimi; yoksa projede LIDERI olan tek takim.
            if not kanat_id:
                r = (conn.execute("SELECT kanat_id FROM ajan WHERE proje_id = ? AND ad = ?",
                                  (self.proje_id, sahip)).fetchone() if sahip else None)
                if r and r["kanat_id"]:
                    kanat_id = r["kanat_id"]
                else:
                    liderli = conn.execute(
                        "SELECT DISTINCT kanat_id FROM ajan WHERE proje_id = ? AND lider_mi = 1 "
                        "AND kanat_id IS NOT NULL", (self.proje_id,)).fetchall()
                    if len(liderli) == 1:
                        kanat_id = liderli[0]["kanat_id"]
            son = conn.execute(
                "SELECT COALESCE(MAX(no), 0) AS n FROM gorev WHERE proje_id = ?",
                (self.proje_id,),
            ).fetchone()["n"]
            no = int(son) + 1

            conn.execute(
                "INSERT INTO gorev (id, proje_id, kanat_id, no, baslik, govde, neden, "
                "ana_hedef, kabul_olcutu, yazma_alani, ek_klasorler, zorluk, "
                "zorluk_gerekce, tarayici_alani, tarayici_yazma, tarayici_kabin, baglayicilar, "
                "sahip, durum, oncelik, revizyon, silindi, olusturuldu, guncellendi) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?)",
                (gorev_id, self.proje_id, kanat_id, no, baslik.strip(), govde.strip(),
                 neden.strip(), ana_hedef.strip(), kabul_olcutu.strip(),
                 json.dumps(alanlar, ensure_ascii=False),
                 json.dumps(ekler, ensure_ascii=False),
                 zorluk, (zorluk_gerekce or "").strip(),
                 json.dumps(tarayici_kaynaklari, ensure_ascii=False),
                 # YAZMA yalnizca tarayici alani VARSA anlamlidir.
                 # Alansiz yazma yetkisi, olmayan bir kapiya anahtar
                 # vermek olurdu -- ve defterde "yazabilir" diye
                 # gorunurdu: yanlis gosteren gosterge.
                 1 if (tarayici_yazma and tarayici_kaynaklari) else 0,
                 # Kabin de yalniz tarayici alani varsa anlamli -- ayni
                 # sebep: olmayan kapiya anahtar defterde yalan soyler.
                 1 if (tarayici_kabin and tarayici_kaynaklari) else 0,
                 json.dumps(baglar, ensure_ascii=False), sahip,
                 BEKLIYOR if bagli_oldugu else HAZIR, oncelik, an, an),
            )

        for blokci_no in (bagli_oldugu or []):
            self.bagimlilik_ekle(no, int(blokci_no))

        self.db.olay_yaz(self.proje_id, "gorev_acildi",
                         f"#{no} {baslik}", ajan_ad=acan, gorev_id=gorev_id)
        if baglar:
            # Baglayici acmak bir YETKI GENISLETMESIDIR ve ~225k jeton
            # yakar. Ikisi de sessizce olmaz.
            self.db.olay_yaz(
                self.proje_id, "baglayici_istendi",
                f"#{no} icin baglayici: " + " · ".join(baglar),
                ajan_ad=acan, gorev_id=gorev_id)
        if tarayici_kaynaklari:
            # Klasorle ayni kural: yetki genislemesi sessizce olmaz.
            self.db.olay_yaz(
                self.proje_id, "tarayici_alani",
                f"#{no} icin tarayici kaynagi: " + " · ".join(tarayici_kaynaklari)
                + (" · tiklayabilir (riskli eylem ONAYA duser)"
                   if tarayici_yazma else " · SALT OKUNUR (bilerek)")
                + (" · PAYLASILAN KABIN (patronun oturumu)"
                   if tarayici_kabin else ""),
                ajan_ad=acan, gorev_id=gorev_id)
        if ekler:
            # Klasor acmak bir YETKI GENISLETMESIDIR. Sessizce olmaz:
            # "hangi klasor hangi ise, kimin istegiyle acildi" sorusu
            # alti ay sonra da cevaplanabilmeli.
            self.db.olay_yaz(
                self.proje_id, "klasor_acildi",
                f"#{no} icin ofis disi klasor: " + " · ".join(ekler),
                ajan_ad=acan, gorev_id=gorev_id)
        return self.gorev(no)

    # -- okuma -------------------------------------------------------------

    def gorev(self, no: int) -> dict:
        with self.db.baglanti() as conn:
            row = conn.execute(
                "SELECT * FROM gorev WHERE proje_id = ? AND no = ? AND silindi = 0",
                (self.proje_id, int(no)),
            ).fetchone()
        if not row:
            raise TahtaHatasi(f"Gorev bulunamadi: #{no}")
        d = dict(row)
        d["yazma_alani"] = json.loads(d["yazma_alani"] or "[]")
        d["ek_klasorler"] = json.loads(d.get("ek_klasorler") or "[]")
        d["tarayici_alani"] = json.loads(d.get("tarayici_alani") or "[]")
        d["tarayici_yazma"] = bool(d.get("tarayici_yazma"))
        d["tarayici_kabin"] = bool(d.get("tarayici_kabin"))
        d["baglayicilar"] = json.loads(d.get("baglayicilar") or "[]")
        return d

    def liste(self, kanat_id: str = None, durum: str = None) -> list:
        sorgu = "SELECT * FROM gorev WHERE proje_id = ? AND silindi = 0"
        args = [self.proje_id]
        if kanat_id:
            sorgu += " AND kanat_id = ?"
            args.append(kanat_id)
        if durum:
            sorgu += " AND durum = ?"
            args.append(durum)
        sorgu += " ORDER BY no"
        with self.db.baglanti() as conn:
            rows = conn.execute(sorgu, args).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["yazma_alani"] = json.loads(d["yazma_alani"] or "[]")
            d["ek_klasorler"] = json.loads(d.get("ek_klasorler") or "[]")
            d["tarayici_alani"] = json.loads(d.get("tarayici_alani") or "[]")
            d["tarayici_yazma"] = bool(d.get("tarayici_yazma"))
            d["tarayici_kabin"] = bool(d.get("tarayici_kabin"))
            d["baglayicilar"] = json.loads(d.get("baglayicilar") or "[]")
            out.append(d)
        return out

    def ret_sayisi(self, no: int) -> int:
        """Bu is kac kez geri gonderildi.

        Ayri bir sayac tutmuyoruz: `ret` olayi zaten yaziliyor ve
        gorevle etiketli. Ikinci bir sayac, olay defteriyle kayabilir
        -- bu projede iki yerde tutulan her sey en az bir kez kaydi.
        """
        gorev = self.gorev(no)
        with self.db.baglanti() as conn:
            return conn.execute(
                "SELECT COUNT(*) AS n FROM olay WHERE tur = 'ret' AND gorev_id = ?",
                (gorev["id"],)).fetchone()["n"]

    def blokcular(self, no: int) -> list:
        """Bu isi bekleten, henuz bitmemis gorevler."""
        gorev = self.gorev(no)
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT t.no, t.baslik, t.durum FROM gorev_bagimlilik d "
                "JOIN gorev t ON t.id = d.bagli_oldugu "
                "WHERE d.gorev_id = ? AND t.silindi = 0 AND t.durum != ?",
                (gorev["id"], BITTI),
            ).fetchall()
        return [dict(r) for r in rows]

    # -- bagimlilik (DAG) --------------------------------------------------

    def bagimlilik_ekle(self, no: int, bagli_oldugu_no: int) -> dict:
        gorev = self.gorev(no)
        blokci = self.gorev(bagli_oldugu_no)
        if gorev["id"] == blokci["id"]:
            raise TahtaHatasi("Gorev kendine baglanamaz.")

        with self.db.baglanti() as conn:
            if self._dongu_olur_mu(conn, gorev["id"], blokci["id"]):
                raise TahtaHatasi(
                    f"#{bagli_oldugu_no} zaten dogrudan ya da dolayli olarak #{no}'a bagli. "
                    "Dongu eklenirse hicbir is asla hazir olmaz; tahta calisiyor "
                    "gorunur ama ilerlemez."
                )
            conn.execute(
                "INSERT OR IGNORE INTO gorev_bagimlilik (gorev_id, bagli_oldugu) VALUES (?, ?)",
                (gorev["id"], blokci["id"]),
            )
            if blokci["durum"] != BITTI and gorev["durum"] == HAZIR:
                conn.execute(
                    "UPDATE gorev SET durum = ?, revizyon = revizyon + 1, guncellendi = ? "
                    "WHERE id = ?",
                    (BEKLIYOR, simdi(), gorev["id"]),
                )
        return self.gorev(no)

    def _dongu_olur_mu(self, conn, gorev_id: str, blokci_id: str) -> bool:
        gorulen = set()
        yigin = [blokci_id]
        while yigin:
            simdiki = yigin.pop()
            if simdiki == gorev_id:
                return True
            if simdiki in gorulen:
                continue
            gorulen.add(simdiki)
            rows = conn.execute(
                "SELECT bagli_oldugu FROM gorev_bagimlilik WHERE gorev_id = ?",
                (simdiki,),
            ).fetchall()
            yigin.extend(r["bagli_oldugu"] for r in rows)
        return False

    def _bagimlilari_coz(self) -> None:
        """Butun blokcusu biten bekleyen isleri hazir yapar."""
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT id FROM gorev WHERE proje_id = ? AND silindi = 0 AND durum = ?",
                (self.proje_id, BEKLIYOR),
            ).fetchall()
            for row in rows:
                kalan = conn.execute(
                    "SELECT COUNT(*) AS n FROM gorev_bagimlilik d "
                    "JOIN gorev t ON t.id = d.bagli_oldugu "
                    "WHERE d.gorev_id = ? AND t.silindi = 0 AND t.durum != ?",
                    (row["id"], BITTI),
                ).fetchone()["n"]
                if kalan == 0:
                    # Yalnizca HALA bekliyorsa: bu arada biri durumu
                    # degistirdiyse onun karari gecerlidir.
                    conn.execute(
                        "UPDATE gorev SET durum = ?, revizyon = revizyon + 1, "
                        "guncellendi = ? WHERE id = ? AND durum = ?",
                        (HAZIR, simdi(), row["id"], BEKLIYOR),
                    )

    # -- yazma kilidi ------------------------------------------------------

    def kilit_dusenleri_temizle(self, *, duraklatilmis=()) -> int:
        """Nabzi gecmis kilitleri dusurur. Ajan olurse is asili kalmasin.

        `duraklatilmis`: nabzi gecse de DOKUNULMAYACAK ajan adlari.

        OLCULDU (19.09.2026): kira, OLEN ajana karsi var -- "ajan olur,
        elektrik giderse kilit sonsuza kadar kalmasin". Ama DURDURULMUS
        bir ajan olmemistir; onu sistemin kendisi durdurmustur ve nabiz
        atmamasi dogru davranistir.

        Soru sorup insan cevabi bekleyen ajanin kilidi 180 saniyede
        dusuyordu. Insan cevabi dakikalar surer, yani BU HER SEFERINDE
        oluyordu. Iki sonucu vardi:

        1. Bekleyen isin dosyalari korumasiz kaliyordu -- baskasi
           alabilirdi. Tam olarak Yasa 1'in onlemek istedigi sey.
        2. Gorev `hazir`a donuyor, `sahip` siliniyordu; cevap gelince
           `devam` kosulu tutmuyor ve is SIFIRDAN kosuyordu. `soru_sor`
           kapisinin butun degeri "iki saatlik yanlis isi onlemek"ti --
           ama turun bedeli yeniden odeniyordu.

        CLAUDE.md'de *"bekleyen ajanin kilidi onda kalir"* yaziyordu.
        Yazili kural, olculmus davranisla celisiyordu: **yanlis oldugu
        olculmemis bir kural, kural degil varsayimdir.**
        """
        dusen = 0
        duraklatilmis = set(duraklatilmis or ()) | set(self._duraklatilmis())
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT id, son_nabiz, gorev_id, ajan_ad FROM yazma_kilidi WHERE proje_id = ?",
                (self.proje_id,),
            ).fetchall()
            for row in rows:
                if row["ajan_ad"] in duraklatilmis:
                    continue
                if _yas_saniye(row["son_nabiz"]) > KILIT_KIRA_SANIYE:
                    conn.execute("DELETE FROM yazma_kilidi WHERE id = ?", (row["id"],))
                    conn.execute(
                        "UPDATE gorev SET durum = ?, sahip = '', revizyon = revizyon + 1, "
                        "guncellendi = ? WHERE id = ? AND durum = ?",
                        (HAZIR, simdi(), row["gorev_id"], CALISIYOR),
                    )
                    dusen += 1
        return dusen

    def alan_ekle(self, no: int, yollar, *, ekleyen: str) -> list:
        """Suren isin yazma alanina yol EKLER (ve sahip calisiyorsa kilidini alir).

        09.10 F1 canli (#6): ajan `web/panel.js` gerektigini bildirdi; lider
        danismada "alani ben genisletemem" dedi -- oyle bir yol YOKTU, soru
        patrona dustu. Ayni kapilar: kok-goreli, takimin kokunde olcum, baska
        isin kilidiyle cakisma RET (Yasa 1). Doner: eklenen yollar."""
        gorev = self.gorev(no)
        if gorev["durum"] in (BITTI, IPTAL):
            raise TahtaHatasi(f"#{no} kapali ('{gorev['durum']}'); alan eklenmez.")
        _kok = self.kok_klasor(gorev.get("kanat_id") or None)
        ham = [str(y).strip() for y in (yollar or []) if str(y).strip()]
        self._alanlari_dogrula([y for y in ham if not kok_goreli(y, _kok)], kok=_kok)
        yeni = [kok_goreli(y, _kok) for y in ham]
        self._alanlari_dogrula(yeni, kok=_kok, uyar=False)
        yeni = [y for y in dict.fromkeys(yeni) if y and y not in gorev["yazma_alani"]]
        if not yeni:
            return []
        cakisan = [c for c in self.cakisan_kilitler(yeni, kok=self.gorev_koku(gorev))
                   if c["gorev_id"] != gorev["id"]]
        if cakisan:
            detay = ", ".join(f"{c['yol_oneki']} -> {c['ajan_ad']}" for c in cakisan)
            raise KilitCakismasi(f"#{no} alani genisletilemez: yol baskasinda ({detay}).")
        an = simdi()
        with self.db.baglanti() as conn:
            conn.execute("UPDATE gorev SET yazma_alani = ?, guncellendi = ? WHERE id = ?",
                         (json.dumps(gorev["yazma_alani"] + yeni, ensure_ascii=False), an,
                          gorev["id"]))
            # INCELEMEDE de kilit sahipte kalir (geri gonderilince ayni ajan yazar).
            if gorev["durum"] in (CALISIYOR, INCELEME) and gorev.get("sahip"):
                for yol in yeni:
                    conn.execute(
                        "INSERT INTO yazma_kilidi (id, proje_id, yol_oneki, gorev_id, "
                        "ajan_ad, alindi, son_nabiz) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (uuid.uuid4().hex, self.proje_id, yol, gorev["id"], gorev["sahip"], an, an))
        self.db.olay_yaz(self.proje_id, "alan_eklendi",
                         f"#{no} yazma alanina eklendi: {', '.join(yeni)} ({ekleyen})",
                         ajan_ad=ekleyen, gorev_id=gorev["id"])
        return yeni

    def kosani_yaz(self, no: int) -> None:
        """Isi BU surec kosturuyor: `kosan_surec` tazelenir.

        09.10 F1 canli (#4): is lidere soru beklerken panel yeniden acildi;
        yeni panel isi surdurdu ama sahip ve durum degismedigi icin
        `sahiplen` cagrilmadi -- kayit OLU panelin kimligini tasidi. Sonuc:
        `guncelleme.mesgul` ofisi BOS sandi (Flow olcumu is ortasinda
        basladi) ve bir sonraki kesintide is yanlis toparlanirdi."""
        with self.db.baglanti() as conn:
            conn.execute("UPDATE gorev SET kosan_surec = ? WHERE proje_id = ? AND no = ? "
                         "AND durum = ?", (_surec.kimlik(), self.proje_id, no, CALISIYOR))

    def nabiz(self, no: int) -> None:
        gorev = self.gorev(no)
        with self.db.baglanti() as conn:
            conn.execute(
                "UPDATE yazma_kilidi SET son_nabiz = ? WHERE gorev_id = ?",
                (simdi(), gorev["id"]),
            )

    def cakisan_kilitler(self, alanlar, kok: str = None) -> list:
        """Talep edilen yollari kim tutuyor?

        `kok` verilirse yalniz AYNI KOKTE calisan islerin kilitleri sayilir
        (06.10.2026, takim klasoru): farkli koklerdeki `index.html` iki ayri
        dosyadir; ayni kokteki iki takim ise dosyayi gercekten paylasir.
        """
        self.kilit_dusenleri_temizle()
        istenen = [yol_normalle(a) for a in alanlar if yol_normalle(a)]
        if not istenen:
            return []
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT yol_oneki, ajan_ad, gorev_id FROM yazma_kilidi WHERE proje_id = ?",
                (self.proje_id,),
            ).fetchall()
        if kok is not None:
            hedef = _kok_anahtari(kok)
            rows = [r for r in rows if _kok_anahtari(self.gorev_koku(r["gorev_id"])) == hedef]
        cakisan = []
        for row in rows:
            for yol in istenen:
                if yollar_cakisir(yol, row["yol_oneki"]):
                    cakisan.append(dict(row))
                    break
        return cakisan

    # -- sahiplenme --------------------------------------------------------

    def sahiplen(self, no: int, ajan_ad: str, beklenen_revizyon: int, *,
                 devam: bool = False) -> dict:
        """Gorevi al ve yazma alanini KILITLE.

        Kilit alinamazsa gorev baslamaz. Bu, Yasa 1'in ("yazma tek iplikli
        kalir") uygulanma noktasidir -- iki ajan ayni dosyalara paralel
        yazmaya BASLAYAMAZ, sonradan birlestirme sorunu yasamaz.
        """
        gorev = self.gorev(no)
        if gorev["durum"] not in (HAZIR, INCELEME):
            raise TahtaHatasi(
                f"#{no} su an '{gorev['durum']}' -- sahiplenmek icin 'hazir' olmali."
            )
        blok = self.blokcular(no)
        if blok:
            adlar = ", ".join(f"#{b['no']}" for b in blok)
            raise TahtaHatasi(f"#{no} once {adlar} bitmeli.")

        cakisan = self.cakisan_kilitler(gorev["yazma_alani"], kok=self.gorev_koku(gorev))
        if cakisan:
            detay = ", ".join(f"{c['yol_oneki']} -> {c['ajan_ad']}" for c in cakisan)
            raise KilitCakismasi(
                f"#{no} baslatilamaz: yazma alani baskasinda ({detay}). "
                "Bu bir uyari degil rettir -- iki ajan ayni dosyalara yazarsa "
                "cakisan kararlar cikar."
            )

        an = simdi()
        with self.db.baglanti() as conn:
            self._revizyon_dogrula(conn, gorev["id"], beklenen_revizyon)
            conn.execute(
                "UPDATE gorev SET sahip = ?, durum = ?, revizyon = revizyon + 1, "
                "guncellendi = ?, kosan_surec = ? WHERE id = ?",
                (ajan_ad, CALISIYOR, an, _surec.kimlik(), gorev["id"]),
            )
            for yol in gorev["yazma_alani"]:
                conn.execute(
                    "INSERT INTO yazma_kilidi (id, proje_id, yol_oneki, gorev_id, "
                    "ajan_ad, alindi, son_nabiz) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (uuid.uuid4().hex, self.proje_id, yol, gorev["id"], ajan_ad, an, an),
                )
        # `devam`: ayni oturumdan surme isareti defterde KALIR (koltugun
        # ikinci kaydi kaldirilinca bu bilgi kayboluyordu; deneme D17 olcer).
        self.db.olay_yaz(self.proje_id, "sahiplenildi",
                         f"#{no} {gorev['baslik']} -> {ajan_ad}"
                         + (" (kaldigi yerden)" if devam else ""),
                         ajan_ad=ajan_ad, gorev_id=gorev["id"])
        return self.gorev(no)

    def birak(self, no: int, *, sebep: str = "") -> dict:
        """Gorevi birak ve kilitleri coz."""
        gorev = self.gorev(no)
        with self.db.baglanti() as conn:
            conn.execute("DELETE FROM yazma_kilidi WHERE gorev_id = ?", (gorev["id"],))
            # IPTAL/BITTI EZILMEZ (01.10.2026 OLCULDU): patron #37'yi iptal
            # etti, 9 sn sonra kosan tur dustu ve `birak` isi yeniden
            # "hazir" yapti -- iptal sessizce geri alindi, is yine kostu.
            conn.execute(
                "UPDATE gorev SET sahip = '', durum = ?, revizyon = revizyon + 1, "
                "guncellendi = ? WHERE id = ? AND durum NOT IN (?, ?)",
                (HAZIR, simdi(), gorev["id"], IPTAL, BITTI),
            )
        self.db.olay_yaz(self.proje_id, "birakildi", f"#{no} birakildi. {sebep}".strip(),
                         gorev_id=gorev["id"])
        return self.gorev(no)

    # -- kanit ve kapanis --------------------------------------------------

    def kanit_ekle(self, no: int, tur: str, baslik: str, icerik: str,
                   ekleyen: str) -> dict:
        gorev = self.gorev(no)
        if tur not in ("terminal", "diff", "gorsel", "dosya", "baglanti"):
            raise TahtaHatasi(f"Bilinmeyen kanit turu: {tur}")
        kanit_id = uuid.uuid4().hex
        with self.db.baglanti() as conn:
            conn.execute(
                "INSERT INTO kanit (id, gorev_id, tur, baslik, icerik, ekleyen, olusturuldu) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (kanit_id, gorev["id"], tur, baslik, icerik, ekleyen, simdi()),
            )
        self.db.olay_yaz(self.proje_id, "kanit", f"#{no} {tur}: {baslik}",
                         ajan_ad=ekleyen, gorev_id=gorev["id"])
        return {"id": kanit_id, "tur": tur, "baslik": baslik}

    def kanitlar(self, no: int) -> list:
        gorev = self.gorev(no)
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT tur, baslik, icerik, ekleyen, olusturuldu FROM kanit "
                "WHERE gorev_id = ? ORDER BY olusturuldu, rowid",
                (gorev["id"],),
            ).fetchall()
        return [dict(r) for r in rows]

    def incelemeye_ver(self, no: int, beklenen_revizyon: int) -> dict:
        """Isci isini bitirdi, lider baksin. Kilit HALA DURUR.

        Kilit incelemede de durur: lider 'geri gonder' derse ayni ajan ayni
        dosyalarda devam edecek. Kilidi burada birakmak, inceleme suresince
        baskasinin araya girmesine izin verir.
        """
        self._revizyon_kapisi(no, beklenen_revizyon)
        gorev = self.gorev(no)
        if gorev["durum"] != CALISIYOR:
            raise TahtaHatasi(f"#{no} 'calisiyor' degil, '{gorev['durum']}'.")
        if not self.kanitlar(no):
            raise TahtaHatasi(
                f"#{no} kanitsiz incelemeye verilemez. En az bir artefakt gerek: "
                "test ciktisi, diff ya da ekran goruntusu. "
                "'Calisiyor' demek kanit degil, iddiadir."
            )
        with self.db.baglanti() as conn:
            self._revizyon_dogrula(conn, gorev["id"], beklenen_revizyon)
            conn.execute(
                "UPDATE gorev SET durum = ?, revizyon = revizyon + 1, guncellendi = ? "
                "WHERE id = ?",
                (INCELEME, simdi(), gorev["id"]),
            )
        self.db.olay_yaz(self.proje_id, "incelemede", f"#{no} {gorev['baslik']}",
                         ajan_ad=gorev["sahip"], gorev_id=gorev["id"])
        return self.gorev(no)

    def kapat(self, no: int, beklenen_revizyon: int, *, kapatan: str) -> dict:
        """KANIT KAPISI. Kanit yoksa gecis yapilmaz -- aliskanlik degil, makine."""
        self._revizyon_kapisi(no, beklenen_revizyon)
        gorev = self.gorev(no)
        kanit = self.kanitlar(no)
        if not kanit:
            raise TahtaHatasi(
                f"#{no} kanitsiz kapatilamaz. Bu kapi bilerek serttir: "
                "dogrulama eksikligi, olculmus hatalarin %21,3'udur."
            )
        if gorev["durum"] not in (CALISIYOR, INCELEME):
            raise TahtaHatasi(f"#{no} '{gorev['durum']}' durumundan kapatilamaz.")

        with self.db.baglanti() as conn:
            self._revizyon_dogrula(conn, gorev["id"], beklenen_revizyon)
            conn.execute(
                "UPDATE gorev SET durum = ?, revizyon = revizyon + 1, guncellendi = ? "
                "WHERE id = ?",
                (BITTI, simdi(), gorev["id"]),
            )
            conn.execute("DELETE FROM yazma_kilidi WHERE gorev_id = ?", (gorev["id"],))

        self._bagimlilari_coz()
        self.db.olay_yaz(self.proje_id, "kapandi",
                         f"#{no} {gorev['baslik']} -- {len(kanit)} kanitla",
                         ajan_ad=kapatan, gorev_id=gorev["id"])
        # IS BASINA GIT KAYDI (06.10.2026, patron): proje git deposuysa isin
        # olculen dosyalari tek kayda girer. Hata isi geri acmaz (uyari olur).
        from . import git_kaydi
        git_kaydi.kaydet(self.db, self.proje_id, self.gorev_koku(gorev), gorev,
                         kapatan=kapatan)
        # OFIS GELISTIRME (09.10.2026): kok gelistirme kopyasiysa kapanan isin
        # kaydi kopyada TAM sinamadan gecer, gecerse patrona kurulum karti.
        from . import gelistirme
        gelistirme.kapanista(self.db, self.proje_id, self.gorev_koku(gorev), gorev)
        return self.gorev(no)

    def giris_uygula(self, no: int, *, kaynak: str = "",
                     baglayici_ad: str = "") -> dict:
        """Insan bir girisi YAPTI: isi o girisi gorecek hale getirir.

        `kaynak` (web): is PAYLASILAN KABINE tasinir, kaynak tarayici
        alanina eklenir, tiklama acilir (riskli eylem yine onaya duser).
        Ajanin kendi tarayicisi ayri ve oturumsuz bir profildir; insanin
        girisini ancak kabin gosterir. Kabin yalniz insanin isaret ettigi
        kaynaklara acilir -- isaret eden burada insanin kendi onayidir.

        `baglayici_ad` (baglayici): ise eklenir. Cagiran onu OLCMUS
        olmalidir (`giris.cevapla`); burada ikinci kez olculmez.

        Yetki genislemesidir: sessizce olmaz, olaya yazilir.
        """
        g = self.gorev(no)
        if g["durum"] in (BITTI, IPTAL):
            raise TahtaHatasi(f"#{no} {g['durum']}: kapanmis ise giris uygulanmaz.")
        alan = list(g.get("tarayici_alani") or [])
        baglar = list(g.get("baglayicilar") or [])
        notlar = []
        kabin = 1 if g.get("tarayici_kabin") else 0
        yazma = 1 if g.get("tarayici_yazma") else 0
        if kaynak:
            k = tarayici.kaynak_normalle(kaynak)
            if k not in alan:
                alan.append(k)
            kabin, yazma = 1, 1
            notlar.append(f"tarayici PAYLASILAN KABINE tasindi ({k}, tiklayabilir)")
        if baglayici_ad and baglayici_ad not in baglar:
            baglar.append(baglayici_ad)
            notlar.append(f"baglayici acildi: {baglayici_ad}")
        if not notlar:
            return g
        with self.db.baglanti() as conn:
            conn.execute(
                "UPDATE gorev SET tarayici_alani = ?, tarayici_kabin = ?, "
                "tarayici_yazma = ?, baglayicilar = ?, guncellendi = ? "
                "WHERE id = ?",
                (json.dumps(alan, ensure_ascii=False), kabin, yazma,
                 json.dumps(baglar, ensure_ascii=False), simdi(), g["id"]))
        self.db.olay_yaz(self.proje_id, "giris_uygulandi",
                         f"#{no}: " + " · ".join(notlar), gorev_id=g["id"])
        return self.gorev(no)

    #: Duraklatilabilen durumlar: henuz kapanmamis ve inceleme disinda.
    DURAKLAR = ("bekliyor", "hazir", "calisiyor")

    def insan_kabul(self, no: int) -> dict:
        """PATRON ISI OLDUGU GIBI KABUL ETTI (09.10.2026, ret freni). Is hangi
        ACIK durumda olursa olsun (kesintiden sonra 'hazir', duraklatilmis
        'calisiyor', 'inceleme') kapanir; KANIT KAPISI yine gecerli (`kapat`).
        Olculdu: kabul aninda is kesinti yuzunden 'hazir'di, eski yol kapatmadi."""
        g = self.gorev(no)
        if g["durum"] in (BITTI, IPTAL):
            raise TahtaHatasi(f"#{no} zaten '{g['durum']}'.")
        if g["durum"] != INCELEME:
            with self.db.baglanti() as conn:
                conn.execute("UPDATE gorev SET durum = ?, duraklatildi = '', revizyon = revizyon + 1, "
                             "guncellendi = ? WHERE id = ?", (INCELEME, simdi(), g["id"]))
        return self.kapat(no, self.gorev(no)["revizyon"], kapatan="insan")

    def duraklat(self, no: int, kim: str = "insan") -> dict:
        """ISI DURAKLATIR (02.10.2026; rakipte is basina "Duraklat" var).

        Ofisin genel Durdur'u BUTUN takimlari durdurur; patron tek bir isi
        beklemeye almak ister. Kosan tur kesilir (koltuk), halka bu isi
        SECMEZ; oturum, kilit ve kanit korunur. `devam_ettir` ayni
        oturumdan surdurur. Inceleme duraklatilmaz (lider karar veriyor).
        """
        g = self.gorev(no)
        if g["durum"] not in self.DURAKLAR:
            raise TahtaHatasi(f"#{no} '{g['durum']}' durumunda; yalniz bekleyen, "
                              "siradaki ya da calisan is duraklatilir.")
        if g.get("duraklatildi"):
            return g
        with self.db.baglanti() as conn:
            conn.execute("UPDATE gorev SET duraklatildi = ? WHERE id = ?",
                         (simdi(), g["id"]))
        self.db.olay_yaz(self.proje_id, "uyari",
                         f"{kim} #{no} isini DURAKLATTI: kosan tur kesilir, "
                         "'Surdur' ile kaldigi yerden devam eder.",
                         ajan_ad=kim, gorev_id=g["id"])
        return self.gorev(no)

    def devam_ettir(self, no: int, kim: str = "insan") -> dict:
        """Duraklatilan isi yeniden halkaya acar (ayni oturum)."""
        g = self.gorev(no)
        if not g.get("duraklatildi"):
            raise TahtaHatasi(f"#{no} duraklatilmamis.")
        with self.db.baglanti() as conn:
            conn.execute("UPDATE gorev SET duraklatildi = '' WHERE id = ?", (g["id"],))
        self.db.olay_yaz(self.proje_id, "surdur_istendi",
                         f"{kim} #{no} isini surdurdu", ajan_ad=kim, gorev_id=g["id"])
        return self.gorev(no)

    def iptal_et(self, no: int, *, sebep: str, iptal_eden: str) -> dict:
        """Isi IPTAL eder ve KILITLERINI BIRAKIR.

        Bu yontem bir olcumden dogdu. `IPTAL` `DURUMLAR` icinde gecerli
        bir durumdu ama ona GECIREN hicbir yontem yoktu -- yani duruma
        ancak elle SQL ile girilebiliyordu, ve o yolda kilit birakan da
        yoktu. Gercek ofiste tam bu oldu: #17 `iptal` idi, iki kilidi
        duruyordu ve `ofis/motor` alani baska bir ise SEBEPSIZ kapaliydi.
        Sagliktaki "oksuz kilit" denetimi bunu gosterdi.

        **Ulasilabilir ama yontemi olmayan bir durum, sizdiran bir
        durumdur.** Gecisin kendisi kadar gecisin YAN ETKISI de bir
        yerde yazili olmali; iki yerde olsaydi biri unutulurdu (bu
        projede bes kez oldu).

        Uc karar:

        - **Kanit kapisi YOKTUR** (`kapat`tan tek farki). Kanit, isin
          BITTIGINI kanitlar; iptal isin bitmedigini soyler. Iptali
          kanita baglamak, yarim kalmis bir isi kapatmayi imkansiz
          kilardi ve kilitler sonsuza kadar dururdu.

        - **SEBEP ZORUNLU.** Gerekcesiz iptal, altı ay sonra "bu is
          neden yarim kaldi" sorusunu cevapsiz birakir -- `karar_yaz`
          ve `onay_cevapla` ile ayni kural.

        - **Bitmis is iptal EDILEMEZ.** Kapanmis bir isi geri almak,
          kanit kapisindan gecmis bir hukmu sessizce bozmaktir.
        """
        sebep = (sebep or "").strip()
        if not sebep:
            raise TahtaHatasi(
                "Iptal sebebi zorunlu -- gerekcesiz iptal, isin neden "
                "yarim kaldigini cevapsiz birakir.")
        gorev = self.gorev(no)
        if gorev["durum"] == BITTI:
            raise TahtaHatasi(
                f"#{no} BITTI durumunda; kapanmis is iptal edilemez. "
                "Kanit kapisindan gecmis bir hukmu geri almak, hukmu "
                "sessizce bozmaktir.")
        # ZATEN IPTAL OLAN IS ICIN DE KILITLER TEMIZLENIR.
        # Ilk surumum burada erken donuyordu ve GERCEK ofiste ise
        # yaramadi: #17 zaten `iptal`di (elle SQL ile yapilmisti) ve
        # kilitleri tam bu yuzden duruyordu. Erken donen bir temizleyici,
        # temizlemesi gereken tek durumu atliyordu.
        # Bu yontem YAN ETKISI icin cagrilir; durum zaten dogruysa yan
        # etkinin de dogru oldugunu VARSAYAMAYIZ.
        with self.db.baglanti() as conn:
            conn.execute(
                "UPDATE gorev SET durum = ?, revizyon = revizyon + 1, "
                "guncellendi = ? WHERE id = ?",
                (IPTAL, simdi(), gorev["id"]),
            )
            # KILITLER BIRAKILIR. Olu bir is dosyalari rehin tutmasin --
            # "basarisiz tur kilidi birakir" kuralinin ayni gerekcesi.
            conn.execute("DELETE FROM yazma_kilidi WHERE gorev_id = ?",
                         (gorev["id"],))
            # BEKLEYEN ISTEKLER KAPANIR (28.09.2026, duman_giris gosterdi):
            # iptal edilmis isin onay karti ve sorusu insanin "senden
            # bekleniyor" kuyrugunda KALIYORDU -- artik hicbir ise
            # yaramayan bir karar isteniyordu. Silinmez, kapatilir:
            # gecmis okunur kalir, sebep yazilir.
            not_ = f"is iptal edildi: {sebep}"[:500]
            an = simdi()
            kapanan = conn.execute(
                "UPDATE onay SET durum = 'reddedildi', cevap_notu = ?, "
                "cevaplandi = ? WHERE gorev_id = ? AND durum = 'bekliyor'",
                (not_, an, gorev["id"])).rowcount
            kapanan += conn.execute(
                "UPDATE mesaj SET cevap = ?, cevaplandi = ? WHERE gorev_id = ? "
                "AND mod = 'bekleyen' AND cevaplandi IS NULL",
                ("(" + not_ + ")", an, gorev["id"])).rowcount

        # Bu isi bekleyenler var mi diye bakilir: bekleyen bir is, artik
        # asla gelmeyecek bir sonucu bekliyor olabilir. Coz(me)mek degil
        # GORUNUR kilmak yeterli -- karar insanindir.
        self._bagimlilari_coz()
        self.db.olay_yaz(
            self.proje_id, "iptal",
            f"#{no} {gorev['baslik']} iptal edildi: {sebep}"
            + (f" ({kapanan} bekleyen istek kapandi)" if kapanan else ""),
            ajan_ad=iptal_eden, gorev_id=gorev["id"])
        return self.gorev(no)

    def geri_gonder(self, no: int, beklenen_revizyon: int, *, gerekce: str,
                    gonderen: str) -> dict:
        """Lider isi geri cevirir. Kilit ayni ajanda kalir, is devam eder."""
        if not (gerekce or "").strip():
            raise TahtaHatasi("Geri gonderme gerekcesi zorunlu -- ajan neyi duzeltecegini bilmeli.")
        self._revizyon_kapisi(no, beklenen_revizyon)
        gorev = self.gorev(no)
        if gorev["durum"] != INCELEME:
            raise TahtaHatasi(f"#{no} incelemede degil, '{gorev['durum']}'.")
        with self.db.baglanti() as conn:
            self._revizyon_dogrula(conn, gorev["id"], beklenen_revizyon)
            conn.execute(
                "UPDATE gorev SET durum = ?, revizyon = revizyon + 1, guncellendi = ?, "
                "kosan_surec = ? WHERE id = ?",
                (CALISIYOR, simdi(), _surec.kimlik(), gorev["id"]),
            )
        self.db.olay_yaz(self.proje_id, "ret", f"#{no} geri gonderildi: {gerekce}",
                         ajan_ad=gonderen, gorev_id=gorev["id"])
        return self.gorev(no)

    # -- ic yardimcilar ----------------------------------------------------

    def _revizyon_kapisi(self, no: int, beklenen: int) -> None:
        """CAS kontrolu HER ZAMAN ilk kapidir.

        Sebebi: sonraki butun kontroller (durum, kanit, blokci) cagiranin
        elindeki goruse dayanir. Goru bayatsa o kontrollerin verdigi hata
        mesaji da yaniltir -- "kanitin yok" der, oysa gercek sorun isin
        araya giren biri tarafindan degistirilmis olmasidir.
        """
        with self.db.baglanti() as conn:
            row = conn.execute(
                "SELECT g.revizyon FROM gorev g WHERE g.proje_id = ? AND g.no = ? AND g.silindi = 0",
                (self.proje_id, int(no)),
            ).fetchone()
            if row is None:
                raise TahtaHatasi(f"Gorev bulunamadi: #{no}")
            if int(row["revizyon"]) != int(beklenen):
                raise RevizyonCakismasi(
                    f"Bayat yazar: elindeki revizyon {beklenen}, guncel {row['revizyon']}. "
                    "Gorevi yeniden oku ve tekrar dene."
                )

    def _revizyon_dogrula(self, conn, gorev_id: str, beklenen: int) -> None:
        row = conn.execute("SELECT revizyon FROM gorev WHERE id = ?", (gorev_id,)).fetchone()
        if row is None:
            raise TahtaHatasi("Gorev kayboldu.")
        if int(row["revizyon"]) != int(beklenen):
            raise RevizyonCakismasi(
                f"Bayat yazar: elindeki revizyon {beklenen}, guncel {row['revizyon']}. "
                "Gorevi yeniden oku ve tekrar dene."
            )
