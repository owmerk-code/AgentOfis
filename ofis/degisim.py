"""DEGISIM -- ajanin ne SOYLEDIGI degil, diskte NE DEGISTIGI.

Bu modul neden var: OLCULDU (22.09.2026) ve iki sey ayni anda cikti.

1. `diff` KANIT TURU LASTIK DAMGAYDI. Gercek ofiste 16 `diff` kaydi
   vardi ve hepsi ajanin KENDI ANLATISIYDI -- "ONCEKI / COZUM /
   satir 68-73". Okunakli, hatta dogru; ama bir dosyanin degistigini
   degil, ajanin degistirdigini SOYLEDIGINI kanitliyor. Kanit kapisi
   tam burada kor kaliyordu.

2. YAZMA KILIDI BIR BEYANDIR VE BEYAN HIC DENETLENMEDI. Kilit onek
   eslesmesiyle korur, ama ajanin beyan ettigi alanin DISINA yazmasini
   fiziksel olarak engellemez -- 18.09'da (B) karari alinirken bu
   bedel yaziyla kabul edilmisti ("ajanlar birbirinin dosyasina
   erisebilir"). Kabul edilen bir bedel, olculmedigi surece bir bedel
   degil bir VARSAYIMDIR.

Cozum ikisi icin de ayni: turdan ONCE proje kokunun anlik goruntusu
alinir, turdan SONRA yeniden alinir, fark OLCULUR. Kayit ajanin
elinden gecmez.

    olculen fark  ->  panelin Kod bolumu     (insan gorur)
                  ->  beyan_disi bayragi     (kilit gercekle sinanir)

NEDEN OLAY DEFTERINDEN URETILMIYOR: olculdu -- `olay` tablosunda `ek`
sutunu YOKTUR, yani bir `arac` olayinin hangi dosyaya dokundugu hic
saklanmiyor. Ustelik arac adi motora gore degisiyor (gemini turunda
govde duz "arac" yaziyor). Arac cagrisindan diff uretmek, motorun o
gunku ciktisina bagimli olurdu; disk her motor icin ayni.

OLCULMUS SINIR -- YAZILI, KESFEDILECEK DEGIL:

  * Yalniz PROJE KOKU olculur. Gorevin `ek_klasorler` ile acilan dis
    klasorleri (GuvenKart-3D, QUANTBOT gibi gercek projeler) olculmez;
    biri 2 GB olabilir ve her turu bekletirdi. Bu bir eksik degil bir
    sinir, ve `kapsam_notu` bunu SOYLER -- sessizce atlamak, "hic
    degismedi" ile ayni goruntuyu verirdi.
  * Buyuk ve ikili dosyalarda icerik degil OZET karsilastirilir:
    degistigi bilinir, nasil degistigi bilinmez ve kayit oyle yazar.
  * Olcumun kendisi patlarsa tur OLMEZ ama SESSIZ de kalmaz: bir
    'olculemedi' satiri yazilir (`saglik.py` kurali -- olcemedigine
    "iyi" demeyiz).
"""

from __future__ import annotations

import difflib
import hashlib
import os
import uuid
from pathlib import Path

from .db import simdi
from .tahta import yol_normalle, yollar_cakisir

#: Uretilen ciktilar ve arac artiklari. Bunlari olcmek gurultudur:
#: her turda degisirler ve hicbiri "ajan ne yapti" sorusunu cevaplamaz.
ATLANAN_KLASOR = frozenset({
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".venv", "venv", "env", "node_modules", "dist", "build",
    ".next", ".cache", ".idea", ".vscode", ".claude",
    # E80 (28.09): Playwright'in kendi ciktisi (anlik goruntu, konsol).
    # Olculunce "beyan disi yazma" gorunuyor ve ajan onu SILMEK icin
    # patrona onay soruyordu (D09, D18) -- gurultu, onay yorgunlugu.
    ".playwright-mcp",
    # 29.09: patronun sohbete ekledigi dosyalar (`ofis/ekler.py`). Ofis
    # yonetir; tur surerken eklenen dosya ajanin "beyan disi yazmasi"
    # sayilmasin.
    "ekler",
    # 01.10 (gercek set G17, claude): ajan belgeyi uretmek ve dogrulamak
    # icin kokte iki yardimci betik yazdi; olcum "beyan disi" dedi, lider
    # 4 kez geri gonderdi. Yardimci betiklerin yeri `karalama/`dir; ofis
    # onu olcmez, yazma alani gerekmez.
    "karalama",
})
ATLANAN_UZANTI = frozenset({".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe"})

#: Bunun ustundeki dosya OZETLE karsilastirilir, icerigi okunmaz.
#: Amac bellek degil SURE: her tur basinda ve sonunda okunuyor.
AZAMI_DOSYA_BAYT = 400_000

#: Anlik goruntu bu sureyi asarsa GORUNUR bir uyari duser.
#:
#: OLCULDU (22.09.2026): gercek proje koku 39 dosya / 0,58 MB -> 260 ms;
#: butun AgentOfis agaci 224 dosya / 9,07 MB -> 2,05 sn; GuvenKart-3D
#: 61 dosya / 15,9 MB -> 1,14 sn. Kabaca 200 ms/MB, ve tur basina IKI
#: kez kosuyor.
#:
#: Bugun bedava: bir tur dakikalar suruyor ve $0,09-2 tutuyor. Ama
#: buyuyen bir kokte bu bir TAVANDIR ve sinirin nerede oldugu YAZILI
#: olmali -- tek `RLock` icin de ayni karar verilmisti: olculmemis bir
#: sorunu erken cozmek yok, ama sessizce yavaslamak da yok.
YAVAS_ESIK_SN = 4.0

#: Tek bir yamanin azami satiri. Uzun yama panelde okunmaz hale gelir;
#: kesildigi GORUNUR bicimde soylenir -- yarim satir, kirpildigini
#: soylemeyen bir kirpmadir.
AZAMI_YAMA_SATIR = 400


class DegisimHatasi(RuntimeError):
    pass


def _ikili_mi(ham: bytes) -> bool:
    """NUL bayti metin dosyasinda bulunmaz.

    Kodlama tahmin etmekten ucuz, ve yanilma yonu guvenli: yanlislikla
    "ikili" dersek icerik olculmez ama DEGISIMIN KENDISI yine gorunur.
    """
    return b"\x00" in ham[:8192]


def anlik(kok, haric=()) -> dict:
    """Proje kokunun anlik goruntusu: `yol -> kayit`.

    Kayit: `{"ozet": sha1, "boyut": n, "metin": [...] | None,
    "olculemedi": ""}`. `metin` None ise dosya ikili ya da cok
    buyuktur ve `olculemedi` sebebi tasir.

    Yol her zaman KOK-GORELI ve `/` ayraclidir -- kilit de oyle
    saklanir (`tahta.kok_goreli`). Iki farkli gosterim kullansaydik
    beyan karsilastirmasi hicbir zaman eslesmezdi; ayni hata kilidin
    kendisinde bir kez odendi.
    """
    kokp = Path(kok)
    if not kokp.is_dir():
        return {}
    return {rel: dosya_kaydi(p) for rel, p in _gez(kokp, haric)}


def ofis_dosyalari(db_yolu) -> tuple:
    """Ofisin KENDI defteri ve yan dosyalari -- olcumden haric tutulur.

    OLCULDU (24.09.2026): defter proje kokunun ICINDEYSE her tur
    `o.sqlite3`u "beyan disina yazildi" diye isaretliyordu. Yazan ajan
    degil ofisin kendisi; sahte bir suclama. Uzanti ile toptan atlamak
    (`*.sqlite3`) yanlis olurdu: ajanin kendi projesindeki bir veritabani
    degisikligi gorunmez kalirdi. Yalniz BU defter atlanir.
    """
    if not db_yolu:
        return ()
    b = str(db_yolu)
    return tuple(b + ek for ek in ("", "-wal", "-shm", "-journal"))


def _gez(kokp: Path, haric=()):
    """Olculecek dosyalar: `(kok-goreli yol, Path)`.

    TEK YERDE: tur sonu olcumu (`anlik`) ile canli tarama (`tarama`)
    ayni kurallarla gezer. Iki ayri gezinti olsaydi biri bir klasoru
    atlar oteki atlamaz ve canli izleme, tur sonunda hic gorunmeyecek
    bir dosyayi gosterirdi -- ya da tersi.
    """
    atla = {os.path.normcase(os.path.abspath(h)) for h in haric or ()}
    for dizin, altlar, dosyalar in os.walk(kokp):
        altlar[:] = [a for a in altlar if a not in ATLANAN_KLASOR]
        for ad in dosyalar:
            p = Path(dizin) / ad
            if p.suffix.lower() in ATLANAN_UZANTI:
                continue
            if atla and os.path.normcase(os.path.abspath(p)) in atla:
                continue
            try:
                rel = yol_normalle(str(p.relative_to(kokp)))
            except ValueError:
                continue
            yield rel, p


def dosya_kaydi(p, azami_bayt: int = AZAMI_DOSYA_BAYT) -> dict:
    """Tek dosyanin kaydi -- `anlik` ile canli izleme AYNI isi kullanir.

    `azami_bayt` canli izlemede daha dusuktur: tur sirasinda buyuk bir
    dosyayi iki saniyede bir okuyup difflemek turu yavaslatirdi. O
    zaman icerik degil ozet karsilastirilir ve kayit bunu SOYLER; tam
    yama tur sonu olcumunde gelir.
    """
    p = Path(p)
    try:
        boyut = p.stat().st_size
        if boyut > azami_bayt:
            ozetci = hashlib.sha1()
            with p.open("rb") as f:
                for parca in iter(lambda: f.read(65536), b""):
                    ozetci.update(parca)
            return {"ozet": ozetci.hexdigest(), "boyut": boyut,
                    "metin": None,
                    "olculemedi": "cok buyuk (%d bayt)" % boyut}
        ham = p.read_bytes()
    except OSError as exc:
        # Olcum turu OLDURMEZ ama sessiz de kalmaz.
        return {"ozet": "", "boyut": -1, "metin": None,
                "olculemedi": "okunamadi: %s" % exc.__class__.__name__}
    ozet_h = hashlib.sha1(ham).hexdigest()
    if _ikili_mi(ham):
        return {"ozet": ozet_h, "boyut": boyut, "metin": None,
                "olculemedi": "ikili dosya"}
    metin = ham.decode("utf-8", errors="replace").splitlines(keepends=True)
    return {"ozet": ozet_h, "boyut": boyut, "metin": metin,
            "olculemedi": ""}


def _yama(yol: str, once: list, sonra: list) -> tuple:
    satirlar = list(difflib.unified_diff(
        once or [], sonra or [],
        fromfile="a/" + yol, tofile="b/" + yol, n=3))
    eklenen = sum(1 for s in satirlar
                  if s.startswith("+") and not s.startswith("+++"))
    silinen = sum(1 for s in satirlar
                  if s.startswith("-") and not s.startswith("---"))
    kesildi = len(satirlar) > AZAMI_YAMA_SATIR
    if kesildi:
        satirlar = satirlar[:AZAMI_YAMA_SATIR]
    metin = "".join(s if s.endswith("\n") else s + "\n" for s in satirlar)
    if kesildi:
        metin += ("... yama %d satirda kesildi; tam hali dosyanin "
                  "kendisinde.\n" % AZAMI_YAMA_SATIR)
    return metin, eklenen, silinen


def beyan_disi_mi(yol: str, beyan) -> bool:
    """Bu dosya, isin BEYAN ETTIGI yazma alaninin disinda mi?

    Kilidin kendi onek kurali ODUNC alinir (`tahta.yollar_cakisir`),
    kopyalanmaz: iki yerde tutulan bir kural birinde kayar ve o zaman
    kilit "cakisiyor" derken denetim "beyan disi" demez.

    Beyan BOSSA denetim yapilmaz. Yazma alani olmayan bir is (lider
    triyaji, arastirma, inceleme) zaten hicbir sey beyan etmemistir;
    her dosyasini "beyan disi" isaretlemek, her seye "sorun" diyen
    gosterge olurdu -- ve oyle bir gostergeye insan bakmayi birakir.
    """
    alanlar = [a for a in (yol_normalle(x) for x in (beyan or [])) if a]
    if not alanlar:
        return False
    return not any(yollar_cakisir(yol, a) for a in alanlar)


def karsilastir(once: dict, sonra: dict, *, beyan=(),
                atif_belirsiz: bool = False) -> list:
    """Iki anlik goruntunun farki. Ajanin sozu hic gecmez.

    `atif_belirsiz`: bu tur koserken KOKTE BASKA BIR TUR DA kosuyordu.
    18.09'da (B) karari butun ajanlari ayni koke koydu ve paralellik
    19.09'da gercekten acildi; o zaman anlik goruntu farki "kim yazdi"
    sorusunu cevaplayamaz -- iki turun yazdigi tek bir farkta birikir.

    Fark yine KAYDEDILIR (diskte gercekten olan sey odur) ama
    `beyan_disi` BASTIRILIR. Bastirmasaydik ofis, komsu ajanin
    dosyasini bu ajana yazip onu "beyan disina yazdi" diye suclardi --
    bu projede bir kez odenen hata sinifinin ta kendisi: lider, isci
    dosyalari bulamadigi icin ona haksiz yere "kanit uydurma" dersi
    yazmisti. Yanlis suclama, olcmemekten pahalidir.
    """
    kayitlar = []
    for yol in sorted(set(once) | set(sonra)):
        a, b = once.get(yol), sonra.get(yol)
        if a and b and a["ozet"] == b["ozet"]:
            continue
        if a is None:
            hal = "eklendi"
            olculemedi = b.get("olculemedi", "")
            yama, ekl, sil = _yama(yol, [], b.get("metin") or [])
        elif b is None:
            hal = "silindi"
            olculemedi = a.get("olculemedi", "")
            yama, ekl, sil = _yama(yol, a.get("metin") or [], [])
        else:
            hal = "degisti"
            olculemedi = b.get("olculemedi") or a.get("olculemedi", "")
            if a.get("metin") is None or b.get("metin") is None:
                yama, ekl, sil = "", 0, 0
            else:
                yama, ekl, sil = _yama(yol, a["metin"], b["metin"])
        # Icerigi okunmamis bir dosyanin yamasi UYDURMA olurdu; yama
        # burada bir kapiyla degil DEGISMEZLE bos kalir: `anlik`,
        # `olculemedi` yazdigi her kayitta `metin`i None birakir, yani
        # difflib'e verecek icerik hic yoktur.
        #
        # Ilk surumde buraya bir `if olculemedi: yama = ""` kapisi
        # koymustum. Mutasyon onu KOPARDI ve HICBIR sinama ates etmedi --
        # cunku kapi hicbir sey yapmiyordu. Hic reddetmeyen kapi, kapi
        # degildir: kaldirildi ve degismezin kendisi sinaniyor
        # (`duman_degisim.py`, 1. bolum).
        kayitlar.append({
            "yol": yol, "hal": hal,
            "beyan_disi": (False if atif_belirsiz
                           else beyan_disi_mi(yol, beyan)),
            "atif_belirsiz": bool(atif_belirsiz),
            "eklenen": ekl, "silinen": sil,
            "yama": yama, "olculemedi": olculemedi,
        })
    return kayitlar


def yaz(db, proje_id: str, gorev_id, ajan_ad: str, kayitlar) -> int:
    """Olculen farki deftere gecirir. Tur BASARISIZ olsa da yazilir.

    Basarisiz tur de dosya yazmis olabilir; "is bitmedi" ile "hicbir
    sey degismedi" ayri iki seydir ve ikincisini varsaymak, diskte
    duran bir degisikligi gorunmez kilardi.
    """
    if not kayitlar:
        return 0
    an = simdi()
    with db.baglanti() as conn:
        for k in kayitlar:
            conn.execute(
                "INSERT INTO degisim (id, proje_id, gorev_id, ajan_ad, yol,"
                " hal, beyan_disi, eklenen, silinen, yama, olculemedi,"
                " atif_belirsiz, olusturuldu)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, proje_id, gorev_id, ajan_ad, k["yol"],
                 k["hal"], 1 if k["beyan_disi"] else 0, int(k["eklenen"]),
                 int(k["silinen"]), k["yama"], k["olculemedi"],
                 1 if k.get("atif_belirsiz") else 0, an))
    return len(kayitlar)


def oku(db, proje_id: str, *, gorev_id=None, ajan_ad=None, limit: int = 60):
    """Defterden okur -- en yenisi ustte.

    Panelin Kod bolumu bunu okur ve BU YUZDEN oturumlar arasi acik
    kalir: fark bellekte degil DEFTERDE yasar. Tarayiciyi kapatip
    acmak, dun gece kosan bir isin degisikligini kaybettirmez.

    Beraberlik `rowid` ile bozulur: `simdi()` saniye cozunurluklu ve
    ayni turda yazilan dosyalar ayni damgayi tasir -- sirasiz donerse
    "once sunu, sonra sunu degistirdi" okumasi yalan olur. Ayni
    duzeltme `karar`/`kanit`/`ders` icin bir kez odendi.
    """
    kosul = ["proje_id = ?"]
    par = [proje_id]
    if gorev_id:
        kosul.append("gorev_id = ?")
        par.append(gorev_id)
    if ajan_ad:
        kosul.append("ajan_ad = ?")
        par.append(ajan_ad)
    par.append(int(limit))
    with db.baglanti() as conn:
        satirlar = conn.execute(
            "SELECT * FROM degisim WHERE " + " AND ".join(kosul)
            + " ORDER BY olusturuldu DESC, rowid DESC LIMIT ?", par
        ).fetchall()
    return [dict(s) for s in satirlar]


def ozet(kayitlar) -> dict:
    """Panel basligi icin: kac dosya, kac satir, kaci beyan disi."""
    return {
        "dosya": len(kayitlar),
        "eklenen": sum(int(k["eklenen"]) for k in kayitlar),
        "silinen": sum(int(k["silinen"]) for k in kayitlar),
        "beyan_disi": sum(1 for k in kayitlar if k["beyan_disi"]),
        "olculemeyen": sum(1 for k in kayitlar if k["olculemedi"]),
        "atif_belirsiz": sum(1 for k in kayitlar if k.get("atif_belirsiz")),
    }


def kapsam_notu(ek_klasorler) -> str:
    """Olculmeyen yerleri SOYLER.

    Bos donerse "her sey olculdu" demektir. Dis klasor aciksa insan
    bunu bilmeli: panelde bos bir Kod bolumu gorup "ajan hicbir sey
    yazmadi" diye okumak, yanlis gosteren gostergenin ta kendisi olur.
    """
    disar = [str(x) for x in (ek_klasorler or []) if str(x).strip()]
    if not disar:
        return ""
    return ("Yalniz proje koku olculdu. Su klasorlerdeki degisiklikler "
            "OLCULMEDI: " + ", ".join(disar))
# ===========================================================================
# CANLI IZLEME -- tur SURERKEN diskte ne degisiyor
# ===========================================================================
#
# Kullanici rakipte gordu: ajan bir dosyaya yazdikca o dosya editorde
# kendiliginden aciliyor ("Izleniyor: Nova"). Bizde fark yalniz TUR
# BITINCE olculuyordu; yirmi dakikalik bir turda insan yirmi dakika
# boyunca diskte ne oldugunu goremiyordu.
#
# NEDEN ARAC OLAYLARINDAN DEGIL (olculdu, 24.09.2026): `arac` olayinin
# govdesi yalniz ARAC ADINI tasiyor ("Edit", "Bash"; gemini'de duz
# "arac"). Hangi dosyaya dokunuldugu defterde yok -- ve olsaydi bile
# `Bash(sed -i ...)` ile yazilan dosya hic gorunmezdi. Kaynak yine disk:
# motordan bagimsiz, ajanin sozunden bagimsiz.
#
# UCUZ OLMAK ZORUNDA: tarama yalniz zaman damgasi + boyut okur
# (`tarama`); icerik yalniz DEGISEN dosyada okunur, tarama basina en
# fazla `CANLI_AZAMI_DOSYA` tane. Tarama `CANLI_YAVAS_SN`i asarsa canli
# izleme O TUR ICIN kapanir ve bu GORUNUR bir uyaridir -- sessizce
# yavaslamak yok; tur sonu olcumu yine kosar.
#
# CANLI KAYIT ARA OLCUMDUR, KESIN DEGIL: ayri tabloda (`canli_degisim`)
# durur ve tur bitince silinir -- yerini kesin `degisim` kaydi alir.
# Ayni tabloya yazsaydik bir dosyanin ara hali ile son hali ayni
# defterde iki "degisiklik" olarak gorunurdu.

#: Iki tarama arasi (sn). Insanin "takildi mi" esiginin altinda, diske
#: yuk bindirmeyecek kadar seyrek.
CANLI_ARALIK_S = 2.0
#: Bir tarama bundan uzun surerse canli izleme o tur icin kapanir.
CANLI_YAVAS_SN = 1.0
#: Tarama basina en fazla bu kadar dosyanin icerigi okunur; kalanlar
#: bir sonraki taramaya kalir (kaybolmaz: son tarama onlar icin
#: GUNCELLENMEZ, yani yine "degismis" gorunurler).
CANLI_AZAMI_DOSYA = 12
#: Canli icerik okumasinin ust siniri. Ustu ozetle karsilastirilir.
CANLI_AZAMI_BAYT = 200_000
#: YARIS PAYI (ns). Olculdu (24.09.2026): Windows'ta dosya zaman damgasi
#: kaba artiyor; son taramayla AYNI tikte yapilan ve boyutu degistirmeyen
#: bir yazma, damga+boyut taramasina GORUNMEZ -- sinama bir kosuda bu
#: yuzden kaldi. git'in "racy clean" cozumu: damgasi son taramanin
#: basladigi ana bu paydan yakin olan dosyanin icerigi BIR KEZ DAHA
#: okunur. Maliyeti yalniz o an yazilmakta olan birkac dosya.
CANLI_YARIS_NS = 2_000_000_000


def tarama(kok, haric=()) -> dict:
    """Ucuz tarama: `yol -> (mtime_ns, boyut)`. Icerik OKUNMAZ."""
    kokp = Path(kok)
    sonuc: dict = {}
    if not kokp.is_dir():
        return sonuc
    for rel, p in _gez(kokp, haric):
        try:
            st = p.stat()
        except OSError:
            continue
        sonuc[rel] = (st.st_mtime_ns, st.st_size)
    return sonuc


class CanliIzleyici:
    """Bir turun canli izleyicisi. Koltuk her olayda `belki_tara` cagirir;
    zamani gelmemisse hicbir sey yapmaz.

    `once` turun ONCESINDEKI anlik goruntudur (`anlik`): canli fark hep
    ona gore olculur, bir onceki taramaya gore degil. Yoksa ajan bir
    dosyayi on kez duzenlediginde insan on ayri kucuk parca gorur,
    turun o dosyaya toplamda ne yaptigini goremezdi.
    """

    def __init__(self, kok, once: dict, *, beyan=(), aralik=None,
                 yavas_sn=None, azami_dosya=None, azami_bayt=None,
                 saat=None, yaris_ns=None, haric=()):
        # Varsayilanlar CAGRI ANINDA modul sabitlerinden okunur (tanim
        # aninda degil): sinama sabiti degistirebilsin, ve koltuk
        # izleyiciyi arguman gecmeden kursun.
        import time as _time
        self.kok = Path(kok)
        self.haric = tuple(haric or ())
        self.once = once or {}
        self.beyan = tuple(beyan or ())
        self.aralik = float(CANLI_ARALIK_S if aralik is None else aralik)
        self.yavas_sn = float(CANLI_YAVAS_SN if yavas_sn is None
                              else yavas_sn)
        self.azami_dosya = int(CANLI_AZAMI_DOSYA if azami_dosya is None
                               else azami_dosya)
        self.azami_bayt = int(CANLI_AZAMI_BAYT if azami_bayt is None
                              else azami_bayt)
        self.saat = saat or _time.monotonic
        self.yaris_ns = int(CANLI_YARIS_NS if yaris_ns is None
                            else yaris_ns)
        # Her dosyanin icerigi EN SON hangi duvar saatinde okundu (dosya
        # damgasiyla ayni eksen). Hic okunmamis dosya icin baslangic.
        # Dosya BASINA tutulur: tek bir genel esik, sinira takilan
        # taramada ilerleyemez ve ayni dosyalari sonsuza kadar okuturdu.
        self.bas_duvar = _time.time_ns()
        self.okundu: dict = {}
        self.kapali = ""          # doluysa sebep: bu tur icin kapandi
        self.canli: dict = {}     # yol -> ozet (tabloda duran hal)
        self.son = tarama(self.kok, self.haric)
        self.sonraki = self.saat() + self.aralik

    def zamani_mi(self) -> bool:
        return not self.kapali and self.saat() >= self.sonraki

    def belki_tara(self, *, atif_belirsiz: bool = False, zorla=False):
        """Zamani geldiyse tarar. Donus: None (tarama yok) ya da
        `{"degisen": [kayit], "kalkan": [yol], "yeni": [yol],
        "sure": sn}`.

        `kalkan`: canli listeden cikan dosyalar -- once haline geri
        donen ya da tur icinde acilip silinen. `yeni`: bu turda ILK kez
        dokunulan dosyalar (koltuk bunlari kayit defterine yazar;
        icerik guncellemeleri deftere yazilmaz, olay tablosu terminal
        degildir).
        """
        if self.kapali:
            return None
        an = self.saat()
        if not zorla and an < self.sonraki:
            return None
        import time as _time
        t0 = self.saat()
        duvar = _time.time_ns()
        yeni_tarama = tarama(self.kok, self.haric)
        # Damgasi, icerigin son okundugu ana YARIS PAYINDAN yakin olan
        # dosya "temiz" sayilamaz: ayni tikte yazilmis olabilir (bkz.
        # CANLI_YARIS_NS). Gercekten degisenler ONCE islenir.
        def _yarisli(y):
            st = yeni_tarama.get(y)
            return bool(st) and st[0] >= (self.okundu.get(y, self.bas_duvar)
                                          - self.yaris_ns)
        degisik = sorted(
            (y for y in set(self.son) | set(yeni_tarama)
             if self.son.get(y) != yeni_tarama.get(y) or _yarisli(y)),
            key=lambda y: (self.son.get(y) == yeni_tarama.get(y), y))
        degisen, kalkan, ilk = [], [], []
        for yol in degisik[:self.azami_dosya]:
            simdiki = yeni_tarama.get(yol)
            if simdiki is None:
                self.son.pop(yol, None)
                kayit_b = None
            else:
                self.son[yol] = simdiki
                kayit_b = dosya_kaydi(self.kok / yol, self.azami_bayt)
                self.okundu[yol] = duvar
            kayit_a = self.once.get(yol)
            if kayit_b is None and kayit_a is None:
                # Tur icinde acildi ve silindi: diskte iz yok.
                if self.canli.pop(yol, None) is not None:
                    kalkan.append(yol)
                continue
            if (kayit_a is not None and kayit_b is not None
                    and kayit_a["ozet"] == kayit_b["ozet"]):
                # Once haline dondu: artik bir degisiklik degil.
                if self.canli.pop(yol, None) is not None:
                    kalkan.append(yol)
                continue
            ozet_b = (kayit_b or {}).get("ozet", "-")
            if self.canli.get(yol) == ozet_b:
                continue          # zaman damgasi degisti, icerik degil
            fark = karsilastir({yol: kayit_a} if kayit_a else {},
                               {yol: kayit_b} if kayit_b else {},
                               beyan=self.beyan,
                               atif_belirsiz=atif_belirsiz)
            if not fark:
                continue
            if yol not in self.canli:
                ilk.append(yol)
            self.canli[yol] = ozet_b
            degisen.append(fark[0])
        sure = self.saat() - t0
        self.sonraki = self.saat() + self.aralik
        if sure > self.yavas_sn:
            self.kapali = ("canli tarama %.1f sn surdu (%d dosya); bu tur "
                           "icin canli izleme KAPATILDI, tur sonu olcumu "
                           "yine kosar" % (sure, len(yeni_tarama)))
        return {"degisen": degisen, "kalkan": kalkan, "yeni": ilk,
                "sure": round(sure, 3)}


def canli_yaz(db, proje_id: str, gorev_id, ajan_ad: str, kayitlar,
              kalkan=()) -> None:
    """Canli kaydi gunceller: (gorev, yol) basina TEK satir."""
    import time as _time
    if not kayitlar and not kalkan:
        return
    an = simdi()
    with db.baglanti() as conn:
        for k in kayitlar:
            conn.execute(
                "INSERT INTO canli_degisim (id, proje_id, gorev_id, ajan_ad,"
                " yol, hal, beyan_disi, eklenen, silinen, yama, olculemedi,"
                " atif_belirsiz, guncellendi, damga)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(gorev_id, yol) DO UPDATE SET"
                " ajan_ad=excluded.ajan_ad, hal=excluded.hal,"
                " beyan_disi=excluded.beyan_disi, eklenen=excluded.eklenen,"
                " silinen=excluded.silinen, yama=excluded.yama,"
                " olculemedi=excluded.olculemedi,"
                " atif_belirsiz=excluded.atif_belirsiz,"
                " guncellendi=excluded.guncellendi, damga=excluded.damga",
                (uuid.uuid4().hex, proje_id, gorev_id, ajan_ad, k["yol"],
                 k["hal"], 1 if k["beyan_disi"] else 0, int(k["eklenen"]),
                 int(k["silinen"]), k["yama"], k["olculemedi"],
                 1 if k.get("atif_belirsiz") else 0, an, _time.time_ns()))
        for yol in kalkan:
            conn.execute("DELETE FROM canli_degisim WHERE gorev_id = ?"
                         " AND yol = ?", (gorev_id, yol))


def canli_sil(db, proje_id: str, gorev_id) -> int:
    """Gorevin canli kaydini siler (tur bitti: yerini kesin kayit alir)."""
    with db.baglanti() as conn:
        cur = conn.execute("DELETE FROM canli_degisim WHERE proje_id = ?"
                           " AND gorev_id = ?", (proje_id, gorev_id))
        return cur.rowcount or 0


def canli_oku(db, proje_id: str, limit: int = 40) -> list:
    """Yalniz HALA KOSAN islerin canli kaydi -- en son dokunulan ustte.

    Surec dusup silme hic kosmadiysa kayit kalabilir; o isin durumu
    artik 'calisiyor' degildir ve kayit gosterilmez. Bitmis bir turun
    ara olcumunu canli diye gostermek, yanlis gosteren gosterge olurdu.
    """
    with db.baglanti() as conn:
        satirlar = conn.execute(
            "SELECT c.* FROM canli_degisim c JOIN gorev g ON g.id = c.gorev_id"
            " WHERE c.proje_id = ? AND g.durum = 'calisiyor'"
            " ORDER BY c.damga DESC LIMIT ?", (proje_id, int(limit))
        ).fetchall()
    return [dict(s) for s in satirlar]
