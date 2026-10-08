# -*- coding: utf-8 -*-
"""EKLER -- sohbete dosya ve gorsel (29.09.2026).

Kullanici: *"dosya ya da gorsel yukleyemiyorum."* Rakipte gorev kartina
gorsel eklenebiliyor (surukle / Ctrl+V).

Nasil:
* Dosya PROJE KOKUNUN gizli `.ofis/ekler/` klasorune yazilir (01.10 ayrim) -- ajanlar kokte calisir,
  yani dosyayi okuyabilir (Claude `Read` ile gorsele bakar, Codex da).
* Mesaja `[ek] ekler/<ad>` satiri eklenir. Ek kaydi AYRI bir tabloda
  tutulmaz: mesajin kendisi tasir, akis satirdan cikarir (iki yerde
  tutulan her sey en az bir kez kayar).
* Ad TEMIZLENIR (yalniz harf/rakam/._-), zaman damgasiyla benzersiz;
  klasor disina yazilamaz, okunamaz (yol degil AD alinir).
* Boyut siniri `AZAMI_BAYT`. Yazma ATOMIK (`.part` -> ad).
* `.ofis/ekler/` GitHub yedegine GIRMEZ (.gitignore): ekran goruntusu ve belge
  ozel bilgi tasiyabilir; ZIP yedeginde (bilgisayar + Drive) durur.

## Ajan ve lider de dosya gonderir (30.09.2026)

Kullanici: *"hem sen hem ajanlar sohbete gorsel video pdf dosyalar
gonderebilsin."* Olculdu: ajan ekran goruntusunu aldi ama `sohbete_yaz`
yalniz metin tasiyordu, is "bilmiyorum" diye insana yukseldi.

Kural TEK YERDE (`paylas`): proje kokundeki bir dosya sohbete gosterilecekse
`.ofis/ekler/`e KOPYALANIR (ajanin dosyasi yerinde kalir, balon onun o anki
halini gosterir). Kok disi, gizli (`.env`, `.git/...`) ve sinirdan buyuk
dosya REDDEDILIR. Ajan `sohbete_yaz(ekler=[...])` ile, lider cevabina
`[ek] <yol>` satiri yazarak gonderir; ikisi de buradan gecer.
"""

from __future__ import annotations

import re
import time
import unicodedata
from pathlib import Path

AZAMI_BAYT = 20 * 1024 * 1024
#: VIDEO/SES BUYUK OLUR (08.10.2026, patron: "hazir bir videoyu sohbetten
#: konusarak duzenlesin"). Flow 1080p klip 10-30 MB, telefon videosu yuzlerce
#: MB. Bunlar base64 JSON'la degil AKISLA gelir (`/api/ek_akis`), sinir 2 GB.
MEDYA = (".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi",
         ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")
MEDYA_AZAMI_BAYT = 2 * 1024 * 1024 * 1024
# Fiziksel yer `.ofis/ekler` (01.10.2026, ayrim). Eski mesajlardaki
# `[ek] ekler/<ad>` satirlari da TANINIR (gecmis sohbet bozulmasin).
from .yollar import EK_KLASORU as KLASOR, KARALAMA as _KARALAMA  # noqa: E402
SATIR_ONEKI = "[ek] "
GORSEL = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
_SATIR = re.compile(r"^\[ek\] ((?:\.ofis/)?ekler/[A-Za-z0-9._-]+)\s*$", re.M)


class EkHatasi(ValueError):
    pass


def ad_temizle(ad: str) -> str:
    ad = unicodedata.normalize("NFKD", str(ad or "").replace("ı", "i").replace("İ", "I"))
    ad = "".join(k for k in ad if not unicodedata.combining(k))
    ad = Path(ad.replace("\\", "/")).name          # yol parcasi atilir
    ad = re.sub(r"[^A-Za-z0-9._-]+", "-", ad).strip("-.")
    return (ad or "ek")[-80:]


def klasor(ofis, kanat_id: str = None) -> Path:
    """Eklerin klasoru: takimin kokunde (06.10.2026; ajan `[ek] .ofis/ekler/x`
    satirini KENDI kokune gore okur)."""
    return Path(ofis.kok_klasoru(kanat_id)).resolve() / KLASOR


def _ajan_kanati(ofis, ajan_ad: str):
    try:
        return ofis.kadro.ajan(ajan_ad).get("kanat_id") or None
    except Exception:                          # noqa: BLE001 -- insan / bilinmeyen: proje koku
        return None


def sinir(ad: str) -> int:
    """Bu ada izin verilen en buyuk boyut: video/ses 2 GB, oteki 20 MB."""
    return MEDYA_AZAMI_BAYT if Path(str(ad or "")).suffix.lower() in MEDYA else AZAMI_BAYT


def _mb(n: int) -> str:
    return f"{n // 1024 // 1024} MB"


def yeni_hedef(ofis, ad: str, kanat_id: str = None) -> Path:
    """Ekin benzersiz yeri (zaman damgali, temiz ad). Dosya YAZILMAZ."""
    k = klasor(ofis, kanat_id)
    k.mkdir(parents=True, exist_ok=True)
    hedef = k / (time.strftime("%Y%m%d-%H%M%S-") + ad_temizle(ad))
    sayac = 1
    while hedef.exists() or hedef.with_name(hedef.name + ".part").exists():
        hedef = k / f"{hedef.stem}-{sayac}{hedef.suffix}"
        sayac += 1
    return hedef


def tamamla(ofis, gecici: Path, hedef: Path, *, ajan_ad: str = "insan") -> dict:
    """`.part` dosyasini yerine koyar (ATOMIK) ve olayi yazar."""
    boyut = gecici.stat().st_size
    if not boyut:
        gecici.unlink(missing_ok=True)
        raise EkHatasi("Bos dosya eklenemez.")
    gecici.replace(hedef)
    ofis.db.olay_yaz(ofis.proje_id, "ek_eklendi",
                     f"{KLASOR}/{hedef.name} ({boyut} bayt)", ajan_ad=ajan_ad)
    return {"yol": f"{KLASOR}/{hedef.name}", "ad": hedef.name, "boyut": boyut,
            "gorsel": hedef.suffix.lower() in GORSEL,
            "medya": hedef.suffix.lower() in MEDYA}


def kaydet(ofis, ad: str, veri: bytes, *, ajan_ad: str = "insan", kanat_id: str = None) -> dict:
    if not veri:
        raise EkHatasi("Bos dosya eklenemez.")
    if len(veri) > sinir(ad):
        raise EkHatasi(f"Dosya cok buyuk ({_mb(len(veri))}); sinir {_mb(sinir(ad))}.")
    hedef = yeni_hedef(ofis, ad, kanat_id)
    gecici = hedef.with_name(hedef.name + ".part")
    gecici.write_bytes(veri)
    return tamamla(ofis, gecici, hedef, ajan_ad=ajan_ad)


def kopyala(ofis, kaynak: Path, *, ajan_ad: str = "insan", kanat_id: str = None) -> dict:
    """Diskteki dosyayi eke KOPYALAR (bellege okumadan -- video yuzlerce MB)."""
    import shutil
    kaynak = Path(kaynak)
    boyut = kaynak.stat().st_size
    if boyut > sinir(kaynak.name):
        raise EkHatasi(f"'{kaynak.name}' cok buyuk ({_mb(boyut)}); sinir {_mb(sinir(kaynak.name))}.")
    hedef = yeni_hedef(ofis, kaynak.name, kanat_id)
    gecici = hedef.with_name(hedef.name + ".part")
    shutil.copyfile(kaynak, gecici)
    return tamamla(ofis, gecici, hedef, ajan_ad=ajan_ad)


def takima_getir(ofis, metin: str, kanat_id) -> list:
    """Mesajdaki `[ek]` dosyalarini ISI YAPACAK takimin klasorune koyar.

    08.10.2026 OLCULDU (canli): patron "Tum ofis" sekmesinden ekledi, dosya
    projenin kokune yazildi; lider isi GENEL takima verdi, takimin ajani kendi
    kokunde `.ofis/ekler/<ad>`i BULAMADI ("fotograflari yeniden yukler
    misiniz?"). Satirdaki yol (`.ofis/ekler/<ad>`) her kokte AYNI anlama
    gelsin diye dosya takimin klasorune kopyalanir. Doner: kopyalananlar.
    """
    import shutil
    hedef_k = klasor(ofis, kanat_id or None)
    kopyalanan = []
    for yol in ayikla(metin or "")[1]:
        ad = Path(yol).name
        hedef = hedef_k / ad
        if hedef.exists():
            continue
        for kok in ofis.kokler():
            kaynak = Path(kok).resolve() / KLASOR / ad
            if kaynak.is_file() and kaynak.resolve() != hedef.resolve():
                hedef_k.mkdir(parents=True, exist_ok=True)
                shutil.copy2(kaynak, hedef)
                kopyalanan.append(ad)
                break
    return kopyalanan


def dosya(ofis, ad: str) -> Path:
    """Ada gore ek dosyasi; klasor disi ve olmayan dosya REDDEDILIR."""
    temiz = Path(str(ad or "")).name
    if not temiz or temiz != ad or temiz.startswith("."):
        raise EkHatasi("Gecersiz ek adi.")
    # Ekler takimlarin koklerinde: hepsine bakilir (ad benzersiz uretilir).
    for kok in ofis.kokler():
        k = (Path(kok).resolve() / KLASOR)
        yol = (k / temiz).resolve()
        if yol.parent == k and yol.is_file():
            return yol
    raise EkHatasi("Ek bulunamadi.")


def paylas(ofis, yol: str, *, ajan_ad: str = "") -> str:
    """Kokteki bir dosyayi sohbette GOSTERILEBILIR yapar -> 'ekler/<ad>'.

    Yol koke gore ya da kok icinde mutlak olabilir. Zaten `ekler/`deki
    (ve adi balon kuralina uyan) dosya kopyalanmaz.
    """
    ham = str(yol or "").strip().strip("`'\"<>").strip()
    if not ham:
        raise EkHatasi("Bos yol.")
    _kanat = _ajan_kanati(ofis, ajan_ad)
    kok = Path(ofis.kok_klasoru(_kanat)).resolve()
    p = Path(ham)
    if not p.is_absolute():
        p = kok / p
    try:
        p = p.resolve()
        goreli = p.relative_to(kok)
    except (OSError, ValueError):
        raise EkHatasi(f"'{ham}' proje kokunun disinda; yalniz kok icindeki "
                       "dosya gonderilir.")
    # `.ofis/ekler` gizli ama OFISIN eki: oradan paylasmak serbest. Baska
    # gizli yer (`.env`, `.git/...`) REDDEDILIR.
    # TAKIMIN eki (06.10.2026 canli gosteri OLCTU): once projenin klasorune
    # bakiliyordu; takim kokundeki `.ofis/ekler/` "gizli" sayilip reddedildi.
    ek_mi = p.parent == klasor(ofis, _kanat)
    if not ek_mi and any(parca.startswith(".") for parca in goreli.parts):
        raise EkHatasi(f"'{ham}' gizli dosya/klasor; sohbete gonderilmez.")
    if not p.is_file():
        raise EkHatasi(f"'{ham}' bulunamadi.")
    boyut = p.stat().st_size
    if boyut > sinir(p.name):
        raise EkHatasi(f"'{ham}' cok buyuk ({_mb(boyut)}); sinir {_mb(sinir(p.name))}.")
    if ek_mi and _SATIR.fullmatch(f"[ek] {KLASOR}/{p.name}"):
        return f"{KLASOR}/{p.name}"
    return kopyala(ofis, p, ajan_ad=ajan_ad or "ajan", kanat_id=_kanat)["yol"]


#: Liderin cevabindaki ek satiri: `[ek] <herhangi bir yol>`.
_HAM_SATIR = re.compile(r"^[ \t]*\[ek\][ \t]+(\S[^\r\n]*?)[ \t]*$", re.M)


def metni_hazirla(ofis, metin: str, *, ajan_ad: str = "") -> tuple:
    """Liderin cevabi -> (ek satirlari `ekler/`e cevrilmis metin, hatalar).

    Gonderilemeyen ek SESSIZCE dusmez: satirin yerine sebebi yazilir,
    patron neyin gelmedigini gorur.
    """
    hatalar = []

    def cevir(m):
        try:
            return SATIR_ONEKI + paylas(ofis, m.group(1), ajan_ad=ajan_ad)
        except EkHatasi as exc:
            hatalar.append(str(exc))
            return f"(ek gonderilemedi: {exc})"

    return _HAM_SATIR.sub(cevir, metin or ""), hatalar


_KANITTA_EK = re.compile(r"(?:\.ofis/)?ekler/[A-Za-z0-9._-]+")
_KANITTA_BELGE = re.compile(
    r"[\w./\\:-]+\.(?:png|jpe?g|gif|webp|pdf|docx|xlsx|pptx|mp4|webm|mov|mp3|wav)\b", re.I)


def gonderilmemisler(ofis, gorev_idleri, ek_metinler=()) -> list:
    """Islerin KANITINDA gecen ama patronun sohbetine HIC gitmemis ekler.

    `ek_metinler`: kanit disinda bakilacak metinler -- patronun mesaji ve
    liderin patrona yazdigi cevap. OLCULDU (03.10.2026, gercek set G17,
    claude): `toplanti.docx` kanitta gecmedi, ama patron "toplanti.docx ...
    bana gonder" demisti ve lider "Dosya: toplanti.docx" yazdi; dosya patrona
    hic gitmedi. Bu metinlerde de yalniz BELGE/MEDYA turu ve diskte BU ISTE
    uretilmis dosya sayilir (asagidaki iki kural aynen gecerli).

    OLCULDU (30.09.2026, gercek set G01, claude): ajan ekran goruntusunu
    `ekler/menu.png`ye kaydetti, kanitina yazdi, ama `sohbete_yaz`i
    cagirmadi; lider isi bu yuzden geri gonderdi. Rica ("gondermeyi
    unutma") yerine YAPI: ofis eksigi olcer, lider raporuna ekler.
    Yalniz diskte GERCEKTEN duran dosya sayilir.
    """
    idler = [g for g in (gorev_idleri or []) if g]
    if not idler:
        return []
    soru = ",".join("?" * len(idler))
    with ofis.db.baglanti() as c:
        gidenler = set()
        for r in c.execute(f"SELECT govde FROM olay WHERE proje_id = ? AND tur = 'ajan_sohbet' "
                           f"AND gorev_id IN ({soru})", (ofis.proje_id, *idler)):
            gidenler.update(ayikla(r["govde"] or "")[1])
        adaylar = []
        kok = Path(ofis.isin_koku(idler[0])).resolve()
        for r in c.execute(f"SELECT tur, baslik, icerik FROM kanit WHERE gorev_id IN ({soru}) "
                           "ORDER BY rowid", idler):
            for y in _KANITTA_EK.findall(f"{r['baslik'] or ''} {r['icerik'] or ''}"):
                y = y.rstrip(".")
                if not y.startswith(KLASOR + "/"):
                    y = f"{KLASOR}/{Path(y).name}"      # eski `ekler/<ad>` yazimi
                if y not in adaylar:
                    adaylar.append(y)
            # BELGE/MEDYA YOLU (01.10.2026, gercek set G17): kokte uretilen
            # `toplanti.docx` kanitta geciyordu ama `ekler/` altinda olmadigi
            # icin sayilmadi, patrona hic gitmedi. Patrona gosterilecek TURDEN
            # (belge, gorsel, video, ses) dosya adi kanitta geciyorsa sayilir;
            # kod dosyasi sayilmaz.
            _belgeler(f"{r['baslik'] or ''} {r['icerik'] or ''}", kok, adaylar)
            # GORSEL KANIT: `gorsel_uret` dosyayi isin yazma alanina koyar,
            # `ekler/`e degil; kanitin icerigi dosyanin yoludur.
            if r["tur"] == "gorsel":
                y = str(r["icerik"] or "").strip().strip("`'\"")
                p = Path(y) if Path(y).is_absolute() else kok / y
                try:
                    if (p.suffix.lower() in GORSEL and p.is_file()
                            and p.resolve().is_relative_to(kok)):
                        y = p.resolve().relative_to(kok).as_posix()
                        if y not in adaylar:
                            adaylar.append(y)
                except (OSError, ValueError):
                    pass
        for _m in ek_metinler or ():
            _belgeler(str(_m or ""), kok, adaylar)
        # YANLIS EK (01.10.2026 OLCULDU): #39'un kaniti stil ornegi olarak
        # `bilge-gorsel.png`yi andi; o dosya #38'de patrona ZATEN gitmisti
        # ama yalniz #39'un gonderdikleri sayildigi icin "gitmemis" sanildi
        # ve Demir'in raporuna Bilge'nin resmi eklendi. Iki kural:
        # (1) projede patrona HERHANGI bir iste gitmis dosya gitmistir
        # (ad ya da ICERIK ayni); (2) isten ONCE diskte duran dosya o isin
        # urunu degildir (girdi/ornek), patrona yeniden gonderilmez.
        for r in c.execute("SELECT govde FROM olay WHERE proje_id = ? AND tur = 'ajan_sohbet'",
                           (ofis.proje_id,)):
            gidenler.update(ayikla(r["govde"] or "")[1])
        en_eski = c.execute(f"SELECT MIN(olusturuldu) FROM gorev WHERE id IN ({soru})",
                            idler).fetchone()[0] or ""
    adlar = {Path(g).name for g in gidenler}
    giden_ozler = _klasor_ozleri(kok / KLASOR)
    try:
        from datetime import datetime as _dt
        is_basi = _dt.fromisoformat(en_eski).timestamp() if en_eski else 0.0
    except ValueError:
        is_basi = 0.0

    def gitti(y: str) -> bool:
        # Kokten paylasilan dosya `ekler/`e ZAMAN DAMGALI adla kopyalanir.
        ad = Path(y).name
        if y in gidenler or ad in adlar or any(a.endswith("-" + ad) for a in adlar):
            return True
        p = kok / y
        try:
            if is_basi and p.stat().st_mtime < is_basi - 1:
                return True                      # isten once vardi: girdi
        except OSError:
            return False
        return not y.startswith(KLASOR + "/") and _oz(p) in giden_ozler

    # KARALAMA (01.10.2026, patronun ofis kopyasi, is 3): ajan arka plan
    # gorselini `karalama/`da uretip kanitta andi; ofis onu "gitmemis" sayip
    # patrona ekledi -- asil gorsel zaten gitmisti. Yardimci dosya patrona
    # hic gitmez.
    return [y for y in adaylar if not gitti(y) and (kok / y).is_file()
            and not y.startswith(_KARALAMA + "/")]


def _belgeler(metin: str, kok: Path, adaylar: list) -> None:
    """Metinde adi gecen, kokun icinde (gizli klasor disinda) DURAN belge/medya."""
    for y in _KANITTA_BELGE.findall(metin or ""):
        y = y.strip("`'\"<>()[]").replace("\\", "/")
        p = Path(y) if Path(y).is_absolute() else kok / y
        try:
            if p.is_file() and p.resolve().is_relative_to(kok) and not any(
                    parca.startswith(".") for parca in p.resolve().relative_to(kok).parts):
                y = p.resolve().relative_to(kok).as_posix()
                if y not in adaylar:
                    adaylar.append(y)
        except (OSError, ValueError):
            pass


def _oz(yol: Path) -> str:
    import hashlib
    try:
        return hashlib.sha256(yol.read_bytes()).hexdigest()
    except OSError:
        return ""


def _klasor_ozleri(klasor_: Path) -> set:
    """Patrona gitmis eklerin icerik ozleri (ad degisse de ayni dosya)."""
    try:
        return {_oz(p) for p in klasor_.iterdir() if p.is_file()} - {""}
    except OSError:
        return set()


#: Teslim sayilan ek turleri (rapor tekrar tasir): medya ve belge.
TESLIM_UZANTI = (".mp4", ".mov", ".webm", ".m4v", ".png", ".jpg", ".jpeg", ".webp", ".gif",
                 ".pdf", ".docx", ".xlsx", ".pptx", ".mp3", ".wav", ".m4a")


def teslim_ekleri(ofis, gorev_idleri) -> list:
    """Islerin ajanlarca SOHBETE GONDERILMIS teslim dosyalari (video, gorsel,
    belge), gonderilis sirasiyla.

    06.10.2026 canli gosteri OLCTU: video ajanin ara mesajinda kaldi, liderin
    SON raporu yalniz "gonderildi" diyordu -- patron raporu okudu, videoyu
    bulamadi ("sohbete gizli atmis gibi"). Rapor teslimi KENDI tasir; kare
    ozeti gibi yardimci dosyalar (`-kareler.`) tasinmaz."""
    idler = [g for g in (gorev_idleri or []) if g]
    if not idler:
        return []
    soru = ",".join("?" * len(idler))
    out = []
    with ofis.db.baglanti() as c:
        for r in c.execute(f"SELECT govde FROM olay WHERE proje_id = ? AND tur = 'ajan_sohbet' "
                           f"AND gorev_id IN ({soru}) ORDER BY rowid", (ofis.proje_id, *idler)):
            for y in ayikla(r["govde"] or "")[1]:
                ad = y.lower()
                if ad.endswith(TESLIM_UZANTI) and "-kareler." not in ad and y not in out:
                    out.append(y)
    return out


def satirlar(yollar) -> str:
    return "\n".join(SATIR_ONEKI + y for y in yollar)


def ayikla(metin: str) -> tuple:
    """Mesaj -> (ek satirlari cikarilmis metin, [ekler/ad, ...])."""
    yollar = _SATIR.findall(metin or "")
    temiz = _SATIR.sub("", metin or "").strip()
    return temiz, yollar


def ajan_notu(yollar) -> str:
    """Isi yapacak ajana: dosyalar nerede, nasil bakilir."""
    if not yollar:
        return ""
    return ("Patron dosya ekledi (proje kokune gore yol; OKU, gorselse bak):\n"
            + "\n".join("- " + y for y in yollar))
