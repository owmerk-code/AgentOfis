# -*- coding: utf-8 -*-
"""Gizli: API anahtarlarinin durdugu yer.

Kullanici sordu (19.09.2026): *"yani api keyleri girebilecegim bir yer
yok mu?"* -- yoktu. `setx` bir cevaptir ama ofisin cevabi degildir;
ofis kendi anahtarlarini kendi bilmelidir.

## Nerede DURMAZ -- ve neden

* **Proje klasorunde durmaz.** `eller` ajanlar projenin kok klasorunde
  calisir ve izin listesinde `Bash(cat *)` var. Kok altina konan bir
  `.env`, ajanin bir `cat` komutu kadar uzaktadir. Ustelik `--restricted`
  ajani kokun ICINDE tutar, disina degil: yani kok altindaki her sey
  erisilebilir, disi degil.
* **Veritabaninda durmaz.** Veritabani projenin icinde, yedeklenir,
  kopyalanir, panelde gorunur, brifinge sizabilir. Sir, kopyalanan bir
  yerde durmamali.
* **Kod icinde durmaz.** Soylemeye gerek yok ama yazili olsun.

## Nerede DURUR

`~/.agentofis/gizli.env` -- proje kokunun DISINDA. Ajan oraya
`--restricted` yuzunden erisemez; ofis surecinin kendisi okur.

## Nasil kullanilir

Ofis acilirken depo okunur ve KENDI surecinin ortamina yuklenir. Ajan
turuna gecmesi ayri bir karardir: `tip.ortam_hazirla(izinli=(...))`
yalnizca ACIKCA izin verilen anahtari gecirir, gerisini dusurur. Yani
depo dolu olsa bile ajan hicbir sey gormez -- gormesi gereken motor
gorur (orn. gemini adaptoru `GEMINI_API_KEY` ister).

**Varsayilan KAPALI:** unutulan bir yasak sizdirir, unutulan bir izin
yalnizca calismaz.

## Bu dosya DEGER BASMAZ

`liste()` yalnizca ADLARI ve bir parmak izini dondurur. Sir, onu
gostermek icin degil KULLANMAK icin saklanir; bir kez ekrana dusen
anahtar, kayda da dusmus sayilir (terminal gecmisi, oturum kaydi,
ekran goruntusu).
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import stat
import tempfile
from pathlib import Path

#: Depo, proje kokunun DISINDA. `OFIS_GIZLI_YOLU` ile degistirilebilir --
#: farkli makinede farkli yer isteyen olabilir, ama varsayilan guvenli.
VARSAYILAN_DEPO = Path.home() / ".agentofis" / "gizli.env"


class GizliHatasi(RuntimeError):
    pass


def depo_yolu() -> Path:
    ozel = os.environ.get("OFIS_GIZLI_YOLU", "").strip()
    return Path(ozel).expanduser().resolve() if ozel else VARSAYILAN_DEPO


def _parmak_izi(deger: str) -> str:
    """Degeri GOSTERMEDEN kimligini verir.

    "Dogru anahtari mi koydum" sorusunu cevaplamak icin yeterli, anahtari
    yeniden kurmak icin degil. Uzunluk da veriliyor cunku en sik hata
    yanlis yapistirma (eksik/fazla karakter).
    """
    ozet = hashlib.sha256(deger.encode("utf-8")).hexdigest()[:8]
    return f"{len(deger)} harf · {ozet}"


def _oku(yol: Path) -> dict:
    if not yol.exists():
        return {}
    veri = {}
    for satir in io.open(yol, encoding="utf-8").read().splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        ad, _, deger = satir.partition("=")
        veri[ad.strip()] = deger.strip()
    return veri


def _yaz(yol: Path, veri: dict) -> None:
    """ATOMIK yazar ve dosyayi SAHIBINE kapatir.

    open(yol, "w") dosyayi hemen kirpar; yazma sirasindaki bir hata
    depoyu YOK EDER. Bu projede tam boyle iki dosya kaybedildi.
    """
    yol.parent.mkdir(parents=True, exist_ok=True)
    govde = [
        "# AgentOfis gizli deposu -- BU DOSYAYI PAYLASMA, YEDEKLEME.",
        "# Ajanlar buraya erisemez: proje kokunun disinda ve tur ortamina",
        "# yalnizca ACIKCA izin verilen anahtar gecer (tip.ortam_hazirla).",
        "",
    ]
    govde += [f"{ad}={deger}" for ad, deger in sorted(veri.items())]
    fd, gecici = tempfile.mkstemp(dir=str(yol.parent), suffix=".tmp")
    os.close(fd)
    try:
        with io.open(gecici, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(govde) + "\n")
        try:
            os.chmod(gecici, stat.S_IRUSR | stat.S_IWUSR)   # yalniz sahibi
        except Exception:
            pass          # Windows'ta her zaman anlamli degil; sessizce gec
        shutil.move(gecici, yol)
    finally:
        if os.path.exists(gecici):
            os.unlink(gecici)


def liste() -> list:
    """Anahtar ADLARI ve parmak izleri. DEGER DONDURMEZ."""
    return [{"ad": ad, "parmak_izi": _parmak_izi(deger)}
            for ad, deger in sorted(_oku(depo_yolu()).items())]


def ekle(ad: str, deger: str) -> dict:
    ad = (ad or "").strip().upper()
    deger = (deger or "").strip()
    if not ad:
        raise GizliHatasi("Anahtar adi bos olamaz.")
    if not ad.replace("_", "").isalnum():
        raise GizliHatasi(
            f"Gecersiz anahtar adi: {ad}. Ortam degiskeni adi olmali "
            "(harf, rakam, alt cizgi).")
    if not deger:
        raise GizliHatasi(
            "Bos deger kaydedilmez. Silmek istiyorsan `sil` kullan -- "
            "bos bir anahtar, 'kurulu ama calismiyor' demektir ve bu, "
            "hic kurulu olmamaktan daha zor bulunur.")
    veri = _oku(depo_yolu())
    veri[ad] = deger
    _yaz(depo_yolu(), veri)
    return {"ad": ad, "parmak_izi": _parmak_izi(deger)}


def oku(ad: str) -> str:
    """Bir anahtarin GERCEK degeri. Depoda yoksa bos doner.

    **Bu, degeri donduren TEK islevdir** -- `liste()` bilerek yalnizca
    parmak izi verir, cunku listeleme ciktisi loglara, ekran
    goruntulerine ve sohbetlere dusuyor.

    Cagiran taraf iki seye dikkat etmeli:

    1. **Yazdirma.** Donen deger hicbir log, olay, kanit ya da hata
       metnine girmemeli. Bir kez sizan anahtar, sizmis anahtardir.
    2. **Ajan turuna gecirme.** Ortam degiskeni olarak gecirmek AYRI
       bir karardir: `motor/tip.py: ortam_hazirla` varsayilan olarak
       KAPALIDIR ve yalnizca acikca izin verilen anahtari gecirir --
       *"unutulan bir yasak sizdirir, unutulan bir izin yalnizca
       calismaz."*

    Bugunku tek mesterisi `hesap.ortam_coz`: bir hesabin kimligini
    kurmak icin gercek degere ihtiyaci var.
    """
    return _oku(depo_yolu()).get((ad or "").strip(), "")


def anahtar_oku(ad: str) -> str:
    """Bir anahtari ONCE ORTAMDAN, yoksa KASADAN okur.

    KASANIN KENDI MODULUNDE duruyor cunku bu bir KASA sorusudur --
    ve iki farkli modul ayni sorunun cevabini ayri ayri yazdiginda
    ikisinden biri eksik kaliyor. Nitekim oyle oldu:

    * `gorsel.py` (20.09.2026): yalnizca `os.environ`a bakiyordu.
      Kasada `GEMINI_API_KEY` durdugu halde `musait_ureticiler()`
      *"kurulu degil"* diyordu -- ve hata mesaji *"`kabuk anahtar ekle`
      calistir"* diyordu, o komut ise anahtari KASAYA yaziyordu.
      **Ofis, kendi verdigi talimat izlendiginde bile calismiyordu.**
    * `motor/gemini.py` (21.09.2026): AYNI HATA, ayri modulde. CLI
      kuruluydu (0.52.0), anahtar kasadaydi, ve `musait_mi()` yine
      False donuyordu -- yani dorduncu motor `yetenek`te, `saglik`ta
      ve `ekip oner`de "kurulu degil" gorunuyordu.

    Ikinci kez ayni hatanin cikmasi, yardimcinin yanlis yerde
    durdugunu gosterdi: `gorsel.py`de yasayan bir kasa okumasini bir
    MOTORUN ithal etmesi katmanlamaya aykiri olurdu, o yuzden motor
    kendi kopyasini yazmamis, hic okumamisti.

    SIRA: once ORTAM, sonra kasa. *"Acikca verilen deger HER ZAMAN
    kazanir"* -- rolun turu, zincirin ilk basamagi, hesabin ortami:
    ayni ilke. Ortam degiskeni o surec icin acikca verilmistir; kasa
    kalici bir VARSAYILANDIR.

    Ayrica testi yalitilabilir yapar: kullanicinin GERCEK kasasi bir
    sinamanin sonucunu degistirememeli.
    """
    ortam = (os.environ.get(ad) or "").strip()
    if ortam:
        return ortam
    try:
        return (oku(ad) or "").strip()
    except Exception:
        # Kasa okunamiyorsa (dosya yok, izin yok) SESSIZ kalmayiz:
        # cagiran "anahtar yok" diyecek ve sebebi gorunur olacak.
        return ""


def sil(ad: str) -> bool:
    ad = (ad or "").strip().upper()
    veri = _oku(depo_yolu())
    if ad not in veri:
        return False
    veri.pop(ad)
    _yaz(depo_yolu(), veri)
    return True


def yukle() -> list:
    """Depoyu OFIS surecinin ortamina yukler. Yuklenen ADLARI doner.

    Ajan turuna gecmesi AYRI bir karardir (`tip.ortam_hazirla`). Burada
    yuklenmesi yalnizca ofisin ve motor adaptorlerinin erisebilmesi icin.

    Ortamda ZATEN varsa dokunulmaz: makineye `setx` ile kurulmus bir
    anahtar, depodakinden onceliklidir -- kullanicinin acik tercihi,
    dosyadaki eski bir degerle sessizce ezilmemeli.
    """
    yuklenen = []
    for ad, deger in _oku(depo_yolu()).items():
        if os.environ.get(ad):
            continue
        os.environ[ad] = deger
        yuklenen.append(ad)
    return yuklenen
