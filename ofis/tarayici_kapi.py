# -*- coding: utf-8 -*-
"""TARAYICI KAPISI -- ajan ile Playwright'in ARASINA giren ofis.

Kullanici (22.09.2026) net soyledi: *"ajanlar calissin tiklasin gezsin
bilgi alsin is varsa yapsin, fakat riskli durumlarda -- yayina
gonderme, aktif etme, canliya alma, para -- onay isteyip yapicaklar."*

Bugune kadar iki uc nokta vardi ve ikisi de yanlisti:

* **Once:** tarayici acilan HER is tiklayabiliyordu. Ajan bir "Yayinla"
  dugmesine basabilirdi ve ofis bunu hic gormezdi.
* **Sonra (bugun, gecici):** tiklama araclari hic verilmiyordu. Guvenli
  ama kullanicinin hakli itirazi: *"engellemek bana sacma geldi."*

Dogrusu ucuncu yol: **araclar acik, ama ofis araya giriyor.**

## Neden vekil (proxy), neden baska bir sey degil

Uc yol olculdu:

| yol | neden olmadi |
|---|---|
| Playwright'in kendi onay mekanizmasi | **YOK.** Tum `--help` okundu (100+ bayrak); onay kancasi yok. |
| Ofisin kendi tarayicisini yazmak | Playwright'in erisilebilirlik agacini (`ref`) ve 25 aracini bastan yazmak demek. Calisan bir parcayi atmak. |
| **Vekil MCP sunucusu** | Playwright isini yapmaya devam eder, biz yalniz BORUDA otururuz. |

    ajan
      | mcp__tarayici__browser_click(element="Yayinla dugmesi", ...)
      v
    BU DOSYA  -- riskli mi?
      |  hayir -> aynen ilet (gecikme yok)
      |  evet  -> onay_iste + ajana "SIMDI DUR"
      v
    @playwright/mcp  (gercek is)

Bunun en onemli ozelligi **motordan bagimsiz** olmasi. Claude'un izin
listesi var, codex'in yok, gemini `izinli_araclar` verilince turu hic
baslatmiyor. Kural izin listesinde yasasaydi yalniz Claude'da gecerli
olurdu. Vekilde yasayinca **her motorda** gecerli.

## KIMLIK ARGUMANDAN GELMEZ, ORTAMDAN GELIR

`mcp_sunucu.py`nin kurali burada da gecerli ve ayni sebeple: ajan
kendi adini soyleseydi, baskasinin adina onay isteyebilirdi.

## KIMLIK YOKSA KAPALI KALARAK BASARISIZ OLUR

Ofis defteri verilmemisse onay istenemez. O halde riskli eylem
**reddedilir** -- sessizce gecirilmez. Para ve yayin kontrolleri bu
projede her zaman "fail closed" olur (bkz. `codex.py` butce tavani).

## BU BIR GUVENLIK SINIRI DEGIL, BIR KAPIDIR

Kotu niyetli bir model kelimeyi goremeyecegimiz bir yoldan tetikleyebilir.
Kapinin hedefi kotu niyet degil **dikkatsizlik**. Yazili sinir:
`riskli.py` dosya basi.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

# ICE AKTARMALAR TEK YERDE VE TEK BICIMDE COZULUR.
#
# OLCULDU (22.09.2026, gercek tur): vekil `python tarayici_kapi.py` diye
# BETIK olarak kosuyor, yani `__package__` bostur ve `from .postane
# import ...` **calismaz**. Islev govdesine gomulu goreli bir ice
# aktarma o yuzden ancak GERCEK TURDA patladi:
#
#   "RISKLI EYLEM ve onay kaydi yazilamadi
#    (attempted relative import with no known parent package)"
#
# Kapi dogru davrandi (kapali kalarak reddetti) ama onay insana HIC
# ULASMADI -- yani is cikissiz kalirdi. Bu, `danisma.py`de bir kez
# odenen hata sinifinin aynisi: soru kimseye teslim edilmiyor.
#
# Cozum bir `try/except` degil, ice aktarmalari TEK YERE toplamak:
# islev icine dagilmis her ice aktarma, bu tuzagin yeniden kurulabilecegi
# ayri bir yerdir.
if __package__ in (None, ""):                 # dogrudan `python ...py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ofis import riskli, tarayici         # noqa: E402
    from ofis.db import Veritabani            # noqa: E402
    from ofis.postane import Postane          # noqa: E402
else:
    from . import riskli, tarayici
    from .db import Veritabani
    from .postane import Postane

#: Ofisin sunmadigi araclar -- TEK KAYNAK `tarayici.py`de.
#:
#: Kendi kopyasini tutsaydi iki liste ayrisirdi: vekil bir araci
#: duserirken izin listesi onu acik gosterirdi. Bu projede iki kopyadan
#: biri alti kez unutuldu.
SUNULMAYAN = tarayici.SUNULMAYAN

#: Sayfanin o anki adresi arac SONUCLARINDA geliyor; argumanlarda degil.
#: Kapi onu takip etmeseydi "/checkout sayfasindaki Onayla" hali
#: gorunmezdi.
_URL_KALIBI = re.compile(r"Page URL:\s*(\S+)")
_DIALOG_KALIBI = re.compile(
    r"dialog with message[:\s]*[\"'](.*?)[\"']", re.S)


_REF_SATIRI = re.compile(r"\[ref=(e\d+)\]")
_REF_KIMLIGI = re.compile(r"^e\d+$")
#: Hedef tasiyan arguman adlari (browser_drag iki uclu).
HEDEF_ALANLARI = ("target", "startTarget", "endTarget")


def _satir_metni(satir: str) -> str:
    """Anlik goruntu satirindan insan okunur metin: rol, ad, metin."""
    s = satir.strip().lstrip("-").strip().strip("'")
    s = re.sub(r"\[[^\]]*\]", " ", s)            # [ref=e4] [level=1] ...
    s = s.replace('\\"', '"').replace('"', " ")
    return re.sub(r"\s+", " ", s).strip(" :")


def ref_haritasi(metin: str, azami: int = 300) -> dict:
    """Anlik goruntu YAML'inden `ref -> ogenin metni` (alt ogeleri dahil).

    Ad dugmenin kendi satirinda olmayabilir (`- button [ref=e7]:` ve
    altinda `- text: Sil`); o yuzden alt satirlar da eklenir.
    """
    satirlar = (metin or "").splitlines()
    harita = {}
    for i, satir in enumerate(satirlar):
        m = _REF_SATIRI.search(satir)
        if not m:
            continue
        girinti = len(satir) - len(satir.lstrip())
        parca = [_satir_metni(satir)]
        for alt in satirlar[i + 1:]:
            if not alt.strip():
                continue
            if len(alt) - len(alt.lstrip()) <= girinti:
                break
            parca.append(_satir_metni(alt))
            if sum(len(p) for p in parca) > azami:
                break
        harita[m.group(1)] = " ".join(p for p in parca if p)[:azami]
    return harita


class Durum:
    """Vekilin hafizasi: son gorulen sayfa ve acik onay kutusu."""

    def __init__(self) -> None:
        self.url = ""
        self.dialog = ""
        self.kilit = threading.Lock()

    def sonuctan_ogren(self, metin: str) -> None:
        """Arac SONUCUNUN METNINDEN ogrenir -- ham JSON satirindan DEGIL.

        Ham satirdan okumak olculdu ve BOZUKTU: JSON'da satir sonu
        kacirildigi icin adres kalibi, adresin ardindaki JSON
        noktalamasini da yutuyordu. Kapi yine tutuyordu (alt dize
        eslesmesi) ama onay kartinda insana YANLIS adres yazilirdi --
        ve yanlis gosteren bir gosterge, gostergesizlikten kotudur.
        """
        m = _URL_KALIBI.search(metin)
        if m:
            with self.kilit:
                self.url = m.group(1).strip().strip("\"',")
        d = _DIALOG_KALIBI.search(metin)
        with self.kilit:
            # Kutu kapaninca metni birakiyoruz: bayat bir kutu metni,
            # sonraki masum tiklamayi yanlislikla durdurur.
            self.dialog = d.group(1).strip() if d else ""

    def oku(self) -> tuple:
        with self.kilit:
            return self.url, self.dialog


# ---------------------------------------------------------------------------
# OFIS TARAFI -- onay defteri
# ---------------------------------------------------------------------------

#: Onay kaydinda yeni sitenin makinece okunan satiri -- TEK KAYNAK
#: `tarayici.py`de (koltuk da oradan okur; vekili ice aktarmaz).
KAYNAK_ISARETI = tarayici.KAYNAK_ISARETI


def izinli_kaynaklar(cocuk_argv) -> set:
    """Playwright'a verilen `--allowed-origins` degeri, normallestirilmis."""
    argv = list(cocuk_argv or [])
    if "--allowed-origins" not in argv:
        return set()
    i = argv.index("--allowed-origins")
    ham = argv[i + 1] if i + 1 < len(argv) else ""
    out = set()
    for k in ham.split(";"):
        try:
            out.add(tarayici.kaynak_normalle(k))
        except tarayici.TarayiciHatasi:
            continue
    return out


def yeni_kaynak_bulgusu(arac: str, argumanlar: dict, izinli, url: str = ""):
    """Beyan EDILMEMIS bir siteye gidis mi? Oyleyse onay bulgusu, degilse None.

    Onceden bu gidis Playwright'in `--allowed-origins`i tarafindan SERT
    reddediliyordu (`ERR_BLOCKED_BY_CLIENT`): ajan "erisemedim" diyor, insan
    hicbir sey gormuyordu. Rakipte ayni durum insana SORULUYOR ("bilinmeyen
    site -- bu is icin izin ver / reddet"). Artik bizde de soruluyor --
    ama kapi yerinde: onay gelmeden site ACILMAZ.

    Yalniz `browser_navigate`: bir baglantiya tiklamak Playwright'a gider
    ve orada sert ret kalir; ajan ayni adrese gitmeyi denerse soru buraya
    duser. Liste bossa (kaynak bilinmiyor) karar Playwright'a birakilir.
    """
    if arac != "browser_navigate" or not izinli:
        return None
    hedef = str((argumanlar or {}).get("url") or "").strip()
    if not hedef.lower().startswith(("http://", "https://")):
        return None
    try:
        kaynak = tarayici.kaynak_normalle(hedef)
    except tarayici.TarayiciHatasi:
        return None
    if kaynak in izinli:
        return None
    return {
        "sinif": "yeni_kaynak", "ad": "BEYAN EDILMEMIS SITE",
        "arac": arac, "hedef": kaynak, "element": kaynak, "kaynak": kaynak,
        "eylem": f"Beyan edilmemis siteye gitmek: {kaynak}",
        "url": url, "esles": kaynak, "risk": "orta",
        "sebep": ("Bu is bu siteye izinli degil (izinli: "
                  + ", ".join(sorted(izinli)) + "). Onaylarsan site bu IS "
                  "boyunca acilir -- bir sonraki turda."),
    }


class OfisBagi:
    """Onay defterine tek dokunma noktasi.

    Ayri bir sinif, cunku kimlik verilmeyen halde (test, ofissiz
    kullanim) bu parcanin TAMAMI devre disi kalir ve kapi kapali
    kalarak reddeder. Dagitilmis `if db:` kontrolleri birini unutmanin
    garantisiydi.
    """

    def __init__(self) -> None:
        self.hazir = False
        self.hata = ""
        self.ajan = os.environ.get("OFIS_AJAN", "").strip()
        self.gorev_no = os.environ.get("OFIS_GOREV", "").strip()
        db_yolu = os.environ.get("OFIS_DB", "").strip()
        proje_id = os.environ.get("OFIS_PROJE", "").strip()
        if not (db_yolu and proje_id and self.ajan):
            self.hata = "ofis kimligi verilmemis (OFIS_DB/OFIS_PROJE/OFIS_AJAN)"
            return
        try:
            self.db = Veritabani(db_yolu)
            self.proje_id = proje_id
            self.gorev_id = None
            if self.gorev_no:
                with self.db.baglanti() as conn:
                    r = conn.execute(
                        "SELECT id FROM gorev WHERE proje_id = ? AND no = ?",
                        (proje_id, int(self.gorev_no))).fetchone()
                    if r:
                        self.gorev_id = r["id"]
            self.hazir = True
        except Exception as exc:                # defter acilamadi
            self.hata = f"ofis defteri acilamadi: {exc}"

    # -- imza --------------------------------------------------------------

    @staticmethod
    def imza(bulgu: dict) -> str:
        """Ayni eylemin tekrar tekrar onay istememesi icin kimlik.

        Hedef metni SADELESTIRILMIS haliyle giriyor: "Yayinla" ile
        "YAYINLA" ayni eylemdir ve iki ayri onay karti cikarsa insan
        ayni seyi iki kez cevaplar.

        ## SAYFA ADRESI ve `ref` KIMLIGE GIRMEZ -- olculdu

        Ilk surumde imza `hedef` (element + `ref`) ve `url` tasiyordu.
        Gercek halkada iki tur kosuldu ve **onay ikinci turda
        taninmadi**; ikinci bir kart acildi, `onay_kullanildi` sifir
        kaldi. Iki sebep birden:

        * Playwright'in `ref`i (`e5`) her anlik goruntude yeniden
          uretilir.
        * Vekil her tur YENI bir surectir; o tur icinde henuz bir arac
          sonucu gormediyse sayfa adresi BOSTUR (`(bilinmiyor)`).

        Yani kimlik, her turda degisebilen seylere dayaniyordu.

        BEDELI YAZILI: adres imzada olmadigi icin ayni yazili dugme
        baska bir sayfada da ayni kimligi tasir. Kabul edildi, cunku
        eslesme zaten **proje + isteyen ajan + gorev** ile sinirli, ve
        onay **tek seferlik** (tuketiliyor). Adres yine onay kartinda
        insana gosteriliyor -- karar veren o.
        """
        ham = "|".join((
            bulgu.get("sinif", ""), bulgu.get("arac", ""),
            riskli.sadelestir(bulgu.get("element") or bulgu.get("hedef", "")),
        ))
        return hashlib.sha1(ham.encode("utf-8")).hexdigest()[:16]

    def _ayni_imzalar(self, im: str) -> list:
        with self.db.baglanti() as conn:
            sorgu = ("SELECT * FROM onay WHERE proje_id = ? AND isteyen = ? "
                     "AND ayrinti LIKE ?")
            degerler = [self.proje_id, self.ajan, f"%IMZA:{im}%"]
            if self.gorev_id:
                sorgu += " AND gorev_id IS ?"
                degerler.append(self.gorev_id)
            sorgu += " ORDER BY olusturuldu DESC, rowid DESC"
            return [dict(r) for r in conn.execute(sorgu, degerler).fetchall()]

    def _kullanildi_mi(self, onay_id: str) -> bool:
        with self.db.baglanti() as conn:
            r = conn.execute(
                "SELECT 1 FROM olay WHERE proje_id = ? AND tur = "
                "'onay_kullanildi' AND govde LIKE ?",
                (self.proje_id, onay_id + "%")).fetchone()
            return bool(r)

    def _kullan(self, onay_id: str, bulgu: dict) -> None:
        self.db.olay_yaz(
            self.proje_id, "onay_kullanildi",
            f"{onay_id} | {bulgu.get('arac')} | {bulgu.get('hedef', '')[:120]}",
            ajan_ad=self.ajan, gorev_id=self.gorev_id)

    # -- karar -------------------------------------------------------------

    def karar(self, bulgu: dict) -> dict:
        """`{'izin': True}` ya da `{'izin': False, 'metin': ...}`.

        BIR ONAY = BIR EYLEM. Onaylanmis bir kayit tuketilir
        (`onay_kullanildi` olayi) ve ikinci kez gecmez. Tuketmeseydik
        tek bir "evet" o eylem icin **surekli yetki** olurdu -- insan
        bir kez "bu urunu yayinla" der, ajan her urunu yayinlardi.
        """
        im = self.imza(bulgu)
        for kayit in self._ayni_imzalar(im):
            if kayit["durum"] == "onaylandi" and not self._kullanildi_mi(
                    kayit["id"]):
                self._kullan(kayit["id"], bulgu)
                return {"izin": True}
            if kayit["durum"] == "reddedildi":
                return {"izin": False, "metin": (
                    f"REDDEDILDI. Patron bu eylemi onaylamadi.\n"
                    f"Eylem : {bulgu['eylem']}\n"
                    f"Gerekce: {kayit['cevap_notu'] or '(yazilmamis)'}\n\n"
                    "Bu yolu TEKRAR DENEME. Baska bir yol varsa onu dene, "
                    "yoksa `soru_sor` ile lidere danis.")}
            if kayit["durum"] == "bekliyor":
                return {"izin": False, "metin": self._bekle_metni(
                    bulgu, kayit["id"], yeni=False)}

        onay = self.postane_onay(bulgu, im)
        return {"izin": False, "metin": self._bekle_metni(
            bulgu, onay["id"], yeni=True)}

    def postane_onay(self, bulgu: dict, im: str) -> dict:
        kutu = _SahteOfis(self.db, self.proje_id, self.gorev_no)
        p = Postane(kutu)
        ayrinti = (
            f"IMZA:{im}\n"
            f"arac  : {bulgu['arac']}\n"
            f"hedef : {bulgu['hedef']}\n"
            f"sayfa : {bulgu['url'] or '(bilinmiyor)'}\n"
            f"isaret: {bulgu['esles']!r}\n"
            f"{bulgu['sebep']}"
        )
        if bulgu.get("kaynak"):
            ayrinti += f"\n{KAYNAK_ISARETI}{bulgu['kaynak']}"
        kayit = p.onay_iste(self.ajan, bulgu["eylem"], ayrinti=ayrinti,
                            risk=bulgu["risk"],
                            gorev_no=int(self.gorev_no) if self.gorev_no
                            else None)
        self.db.olay_yaz(
            self.proje_id, "tarayici_onay_bekliyor",
            f"{bulgu['ad']} -- {bulgu['hedef'][:120]}",
            ajan_ad=self.ajan, gorev_id=self.gorev_id)
        return kayit

    def kaynak_karari(self, bulgu: dict) -> str:
        """Yeni site icin ajana donen metin. Site BU TURDA hic acilmaz:
        Playwright'in izin listesi surec baslarken sabitlenir. Onay, is
        BOYUNCA gecerlidir ve bir sonraki turda koltuk tarafindan eklenir.
        Tuketilmez: bir site bir eylem degildir."""
        im = self.imza(bulgu)
        for kayit in self._ayni_imzalar(im):
            if kayit["durum"] == "reddedildi":
                return (f"REDDEDILDI. Patron {bulgu['hedef']} sitesine "
                        f"gidilmesini onaylamadi.\nGerekce: "
                        f"{kayit['cevap_notu'] or '(yazilmamis)'}\n\nBu siteye "
                        "TEKRAR GITMEYE CALISMA. Izinli sitelerle devam et ya "
                        "da `soru_sor` ile lidere danis.")
            if kayit["durum"] == "onaylandi":
                return (f"ONAYLANDI ama bu turun tarayicisi {bulgu['hedef']} "
                        "olmadan basladi; site BIR SONRAKI turda acilacak. "
                        "Simdi buraya kadar yaptiklarini `kanit_ekle` ile yaz "
                        "ve turu bitir -- is kaldigi yerden devam eder.")
            if kayit["durum"] == "bekliyor":
                return self._kaynak_bekle(bulgu, kayit["id"], yeni=False)
        onay = self.postane_onay(bulgu, im)
        return self._kaynak_bekle(bulgu, onay["id"], yeni=True)

    @staticmethod
    def _kaynak_bekle(bulgu: dict, onay_id: str, *, yeni: bool) -> str:
        bas = "ONAY ISTENDI" if yeni else "ONAY ZATEN BEKLIYOR"
        return (f"{bas} -- SIMDI DUR.\n\n{bulgu['hedef']} bu isin izinli "
                "siteleri arasinda DEGIL. Patrona soruldu "
                f"(onay {onay_id}).\n\nSIMDI NE YAP: bu siteye baska bir "
                "yoldan gitmeye calisma. Buraya kadar yaptiklarini "
                "`kanit_ekle` ile yaz ve turu bitir. Patron onaylarsa site bu "
                "IS boyunca acilir ve is kaldigi yerden devam eder.")

    @staticmethod
    def _bekle_metni(bulgu: dict, onay_id: str, *, yeni: bool) -> str:
        bas = ("ONAY ISTENDI" if yeni else "ONAY ZATEN BEKLIYOR")
        return (
            f"{bas} -- SIMDI DUR.\n\n"
            f"Sinif : {bulgu['ad']}\n"
            f"Eylem : {bulgu['eylem']}\n"
            f"Onay  : {onay_id}\n\n"
            "Bu eylem geri alinamaz ya da disariya cikiyor olabilir; ofis "
            "kurali geregi once patronun onayi alinir.\n\n"
            "SIMDI NE YAP: bu turda BU EYLEMI TEKRAR DENEME ve baska bir "
            "yoldan yapmaya calisma. Buraya kadar yaptiklarini `kanit_ekle` "
            "ile deftere yaz, sonra turu bitir. Patron onaylayinca is "
            "kaldigi yerden devam eder ve ayni eylem bir kez gecer.")


class _SahteOfis:
    """`Postane`nin bekledigi en kucuk yuz.

    `Ofis` nesnesinin tamamini kurmuyoruz: o proje acar, kadro yukler,
    tahta kurar -- vekil surecte hepsi bos yere. Postane'nin
    kullandiklari yalniz `db`, `proje_id` ve gorev cozumu.
    """

    def __init__(self, db, proje_id: str, gorev_no: str) -> None:
        self.db = db
        self.proje_id = proje_id
        self.tahta = _SahteTahta(db, proje_id)


class _SahteTahta:
    def __init__(self, db, proje_id: str) -> None:
        self.db = db
        self.proje_id = proje_id

    def gorev(self, no) -> dict:
        with self.db.baglanti() as conn:
            r = conn.execute(
                "SELECT * FROM gorev WHERE proje_id = ? AND no = ?",
                (self.proje_id, int(no))).fetchone()
        if not r:
            raise LookupError(f"Gorev bulunamadi: {no}")
        return dict(r)


# ---------------------------------------------------------------------------
# VEKIL
# ---------------------------------------------------------------------------

def _hata_sonucu(istek_id, metin: str) -> dict:
    return {"jsonrpc": "2.0", "id": istek_id,
            "result": {"content": [{"type": "text", "text": metin}],
                       "isError": True}}


class Vekil:
    def __init__(self, cocuk_argv: list) -> None:
        self.durum = Durum()
        self.ofis = OfisBagi()
        # Isin IZINLI kaynaklari -- cocugun kendi bayragindan okunur, ayri
        # bir kopya tutulmaz (iki liste ayrisirsa kapi yanlis sorar).
        self.izinli = izinli_kaynaklar(cocuk_argv)
        self.yaz_kilidi = threading.Lock()
        # Vekilin KENDI istekleri (sayfanin anlik goruntusu). Kimlikleri
        # "vekil-" onekli; pompa onlari ajana iletmez, burada bekletir.
        self._kendi_sayac = 0
        self._kendi_bekleyen: dict = {}
        self._kendi_kilit = threading.Lock()
        # F3 / E22: bu turda gorulen TALIMAT SUPHELI icerik (alintilar).
        # Doluysa denetlenen her tarayici eylemi patrona sorulur.
        self.suphe: list = []
        self.cocuk = subprocess.Popen(
            cocuk_argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=None, text=True, encoding="utf-8", errors="replace",
            bufsize=1,
            creationflags=(subprocess.CREATE_NO_WINDOW
                           if os.name == "nt" else 0),
        )

    # -- yazma -------------------------------------------------------------

    def _ajana(self, nesne: dict) -> None:
        with self.yaz_kilidi:
            sys.stdout.write(json.dumps(nesne, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    def _cocuga(self, satir: str) -> None:
        self.cocuk.stdin.write(satir + "\n")
        self.cocuk.stdin.flush()

    # -- cocuktan gelen ----------------------------------------------------

    def cocuk_pompasi(self) -> None:
        """Playwright -> ajan. Yolda sayfa adresini ve onay kutusunu ogrenir."""
        for satir in self.cocuk.stdout:
            satir = satir.strip()
            if not satir:
                continue
            try:
                nesne = json.loads(satir)
            except json.JSONDecodeError:
                continue
            kimlik = nesne.get("id")
            if isinstance(kimlik, str) and kimlik.startswith("vekil-"):
                with self._kendi_kilit:
                    bekleyen = self._kendi_bekleyen.get(kimlik)
                if bekleyen is not None:
                    bekleyen["yanit"] = nesne
                    bekleyen["olay"].set()
                continue                        # ajana GITMEZ
            metin = self._metin(nesne)
            self.durum.sonuctan_ogren(metin)
            alinti = riskli.talimat_suphesi(metin)
            if alinti:
                nesne = self._suphe_isle(nesne, alinti)
            nesne = self._araclari_suz(nesne)
            self._ajana(nesne)

    def _suphe_isle(self, nesne: dict, alinti: list) -> dict:
        """Sayfa sonucunda talimat benzeri metin: sonucun BASINA uyari,
        deftere `talimat_suphesi` (insan gorur), tur boyu sikilasma."""
        self.suphe.extend(alinti)
        if self.ofis.hazir:
            try:
                self.ofis.db.olay_yaz(
                    self.ofis.proje_id, "talimat_suphesi",
                    "sayfada talimat benzeri metin: " + " | ".join(a[:120] for a in alinti),
                    ajan_ad=self.ofis.ajan, gorev_id=self.ofis.gorev_id)
            except Exception:                   # noqa: BLE001 -- uyari yine gider
                pass
        sonuc = nesne.get("result")
        if isinstance(sonuc, dict) and isinstance(sonuc.get("content"), list):
            sonuc["content"] = ([{"type": "text", "text": riskli.suphe_uyarisi(alinti)}]
                                + sonuc["content"])
        return nesne

    @staticmethod
    def _metin(nesne: dict) -> str:
        """Yanittaki insan okunur metin parcalarini birlestirir."""
        sonuc = nesne.get("result")
        if not isinstance(sonuc, dict):
            return ""
        parcalar = []
        for p in (sonuc.get("content") or []):
            if isinstance(p, dict) and isinstance(p.get("text"), str):
                parcalar.append(p["text"])
        return chr(10).join(parcalar)

    @staticmethod
    def _araclari_suz(nesne: dict) -> dict:
        """`tools/list` yanitindan sunulmayan araclari cikarir.

        Listede birakip cagrinca reddetmek de olurdu ama ajan o zaman
        var olmayan bir yetenegi dener ve jeton yakar. Gorunmeyen arac
        denenmez.
        """
        sonuc = nesne.get("result")
        if isinstance(sonuc, dict) and isinstance(sonuc.get("tools"), list):
            sonuc["tools"] = [t for t in sonuc["tools"]
                              if t.get("name") not in SUNULMAYAN]
        return nesne

    def sayfa_haritasi(self, zaman_asimi: float = 20.0):
        """Sayfanin SU ANKI anlik goruntusu -> `ref -> metin`.

        Vekil kendisi ister; yanit modele GITMEZ (jeton yakmaz). Basarisiz
        olursa None -- cagiran kapali kalir.
        """
        with self._kendi_kilit:
            self._kendi_sayac += 1
            kimlik = f"vekil-{self._kendi_sayac}"
            bekleyen = {"olay": threading.Event(), "yanit": None}
            self._kendi_bekleyen[kimlik] = bekleyen
        try:
            self._cocuga(json.dumps({"jsonrpc": "2.0", "id": kimlik,
                                     "method": "tools/call",
                                     "params": {"name": "browser_snapshot",
                                                "arguments": {}}}))
            if not bekleyen["olay"].wait(zaman_asimi):
                return None
            yanit = bekleyen["yanit"] or {}
            if "error" in yanit or (yanit.get("result") or {}).get("isError"):
                return None
            return ref_haritasi(self._metin(yanit))
        finally:
            with self._kendi_kilit:
                self._kendi_bekleyen.pop(kimlik, None)

    def _sayfa_metni(self, arac: str, argumanlar: dict):
        """Hedef ref'lerin SAYFADAKI metni. '' = soracak bir sey yok ya da
        ref sayfada yok (Playwright zaten reddeder); None = okunamadi."""
        if arac not in riskli.DENETLENEN:
            return ""
        refler = [str(argumanlar.get(a) or "").strip() for a in HEDEF_ALANLARI]
        refler = [r for r in refler if _REF_KIMLIGI.match(r)]
        if not refler:
            return ""
        harita = self.sayfa_haritasi()
        if harita is None:
            return None
        return " | ".join(harita.get(r, "") for r in refler if harita.get(r))

    # -- ajandan gelen -----------------------------------------------------

    def istegi_isle(self, satir: str) -> None:
        try:
            istek = json.loads(satir)
        except json.JSONDecodeError:
            self._cocuga(satir)                 # anlamadigimizi bozmayiz
            return

        if istek.get("method") != "tools/call":
            self._cocuga(satir)
            return

        par = istek.get("params") or {}
        arac = par.get("name") or ""
        argumanlar = par.get("arguments") or {}
        istek_id = istek.get("id")

        if arac in SUNULMAYAN:
            self._ajana(_hata_sonucu(istek_id, (
                f"{arac} bu ofiste SUNULMUYOR. Istedigi JavaScript'i "
                "kosturdugu icin ofis onun ne yaptigini okuyamaz, dolayisiyla "
                "riskli olup olmadigina karar veremez. Gezme ve tiklama "
                "serbest: `browser_click`, `browser_type`, `browser_find`, "
                "`browser_evaluate` kullan.")))
            return

        url, dialog = self.durum.oku()

        # BEYAN EDILMEMIS SITE -- sert ret yerine SORU (kapi yerinde).
        yk = yeni_kaynak_bulgusu(arac, argumanlar, self.izinli, url)
        if yk is not None:
            if not self.ofis.hazir:
                self._ajana(_hata_sonucu(istek_id, (
                    f"{yk['hedef']} bu isin izinli siteleri arasinda degil ve "
                    f"onay istenemiyor -- {self.ofis.hata}. Gidilmedi.")))
                return
            try:
                metin = self.ofis.kaynak_karari(yk)
            except Exception as exc:
                metin = (f"{yk['hedef']} icin onay kaydi yazilamadi ({exc}). "
                         "Gidilmedi.")
            self._ajana(_hata_sonucu(istek_id, metin))
            return

        # Karar icin SAYFANIN metni: ajanin yazdigi aciklama bir beyandir.
        sayfa_metni = self._sayfa_metni(arac, argumanlar)
        if sayfa_metni is None:
            self._ajana(_hata_sonucu(istek_id, (
                "Tarayici kapisi hedef ogenin sayfadaki adini OKUYAMADI. "
                "Neye tiklandigini bilmeden gecirmeyiz: bu eylem yapilmadi. "
                "`browser_snapshot` al ve tekrar dene.")))
            return
        try:
            bulgu = riskli.degerlendir(arac, argumanlar, url=url,
                                       baglam=dialog, sayfa_metni=sayfa_metni)
        except Exception as exc:
            # Kapi patlarsa KAPALI kalir. Acik kalsaydi, kapinin
            # bozulmasi sessizce her seyi serbest birakirdi.
            self._ajana(_hata_sonucu(istek_id, (
                f"Tarayici kapisi degerlendirme yapamadi ({exc}). Guvenli "
                "tarafta kaliyoruz: bu eylem yapilmadi. Lidere danis.")))
            return

        # SUPHE SONRASI SIKILASMA (E22): bu turda sayfa ajani kandirmaya
        # calismis olabilir; normalde serbest olan tiklama/yazma sorulur.
        if bulgu is None and self.suphe and arac in riskli.DENETLENEN:
            bulgu = riskli.suphe_bulgusu(
                arac, sayfa_metni or json.dumps(argumanlar, ensure_ascii=False)[:200],
                self.suphe[0])

        if bulgu is None:
            self._cocuga(satir)                 # serbest, aynen gecer
            return

        if not self.ofis.hazir:
            self._ajana(_hata_sonucu(istek_id, (
                f"RISKLI EYLEM ve ONAY ISTENEMIYOR -- {self.ofis.hata}.\n"
                f"Eylem: {bulgu['eylem']}\n\n"
                "Para ve yayin kontrolleri kapali kalarak basarisiz olur: "
                "onay defterine ulasamadigimiz icin bu eylem YAPILMADI.")))
            return

        try:
            karar = self.ofis.karar(bulgu)
        except Exception as exc:
            self._ajana(_hata_sonucu(istek_id, (
                f"RISKLI EYLEM ve onay kaydi yazilamadi ({exc}). Eylem "
                "yapilmadi.")))
            return

        if karar.get("izin"):
            self._cocuga(satir)                 # patron onaylamisti
            return
        self._ajana(_hata_sonucu(istek_id, karar["metin"]))

    def kos(self) -> int:
        t = threading.Thread(target=self.cocuk_pompasi, daemon=True)
        t.start()
        while True:
            satir = sys.stdin.readline()        # `for ... in stdin` ASAR
            if satir == "":
                break
            satir = satir.strip()
            if not satir:
                continue
            try:
                self.istegi_isle(satir)
            except BrokenPipeError:
                break
        try:
            self.cocuk.stdin.close()
        except Exception:
            pass
        try:
            return self.cocuk.wait(timeout=10)
        except Exception:
            self.cocuk.kill()
            return 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" not in argv:
        sys.stderr.write(
            "Kullanim: python -m ofis.tarayici_kapi -- <playwright bayraklari>\n")
        return 2
    cocuk_bayraklari = argv[argv.index("--") + 1:]

    # STDIO UTF-8 -- `mcp_sunucu.py`de bir kez odendi: Windows konsolu
    # cp1254 ve emoji "surrogates not allowed" ile patliyordu. JSON-RPC
    # her zaman UTF-8'dir.
    for akis in (sys.stdin, sys.stdout):
        try:
            akis.reconfigure(encoding="utf-8")
        except Exception:
            pass

    cocuk_argv = ["npx", "--no-install", "@playwright/mcp@latest"] + \
        cocuk_bayraklari
    if os.name == "nt":
        cocuk_argv[0] = "npx.cmd"
    return Vekil(cocuk_argv).kos()


if __name__ == "__main__":
    raise SystemExit(main())
