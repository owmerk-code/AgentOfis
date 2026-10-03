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


def klasor(ofis) -> Path:
    return Path(ofis.kok_klasoru()).resolve() / KLASOR


def kaydet(ofis, ad: str, veri: bytes, *, ajan_ad: str = "insan") -> dict:
    if not veri:
        raise EkHatasi("Bos dosya eklenemez.")
    if len(veri) > AZAMI_BAYT:
        raise EkHatasi(f"Dosya cok buyuk ({len(veri) // 1024 // 1024} MB); "
                       f"sinir {AZAMI_BAYT // 1024 // 1024} MB.")
    k = klasor(ofis)
    k.mkdir(parents=True, exist_ok=True)
    temiz = time.strftime("%Y%m%d-%H%M%S-") + ad_temizle(ad)
    hedef = k / temiz
    sayac = 1
    while hedef.exists():
        hedef = k / f"{hedef.stem}-{sayac}{hedef.suffix}"
        sayac += 1
    gecici = hedef.with_name(hedef.name + ".part")
    gecici.write_bytes(veri)
    gecici.replace(hedef)
    ofis.db.olay_yaz(ofis.proje_id, "ek_eklendi",
                     f"{KLASOR}/{hedef.name} ({len(veri)} bayt)", ajan_ad=ajan_ad)
    return {"yol": f"{KLASOR}/{hedef.name}", "ad": hedef.name, "boyut": len(veri),
            "gorsel": hedef.suffix.lower() in GORSEL}


def dosya(ofis, ad: str) -> Path:
    """Ada gore ek dosyasi; klasor disi ve olmayan dosya REDDEDILIR."""
    temiz = Path(str(ad or "")).name
    if not temiz or temiz != ad or temiz.startswith("."):
        raise EkHatasi("Gecersiz ek adi.")
    k = klasor(ofis)
    yol = (k / temiz).resolve()
    if yol.parent != k or not yol.is_file():
        raise EkHatasi("Ek bulunamadi.")
    return yol


def paylas(ofis, yol: str, *, ajan_ad: str = "") -> str:
    """Kokteki bir dosyayi sohbette GOSTERILEBILIR yapar -> 'ekler/<ad>'.

    Yol koke gore ya da kok icinde mutlak olabilir. Zaten `ekler/`deki
    (ve adi balon kuralina uyan) dosya kopyalanmaz.
    """
    ham = str(yol or "").strip().strip("`'\"<>").strip()
    if not ham:
        raise EkHatasi("Bos yol.")
    kok = Path(ofis.kok_klasoru()).resolve()
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
    ek_mi = p.parent == klasor(ofis)
    if not ek_mi and any(parca.startswith(".") for parca in goreli.parts):
        raise EkHatasi(f"'{ham}' gizli dosya/klasor; sohbete gonderilmez.")
    if not p.is_file():
        raise EkHatasi(f"'{ham}' bulunamadi.")
    boyut = p.stat().st_size
    if boyut > AZAMI_BAYT:
        raise EkHatasi(f"'{ham}' cok buyuk ({boyut // 1024 // 1024} MB); "
                       f"sinir {AZAMI_BAYT // 1024 // 1024} MB.")
    if ek_mi and _SATIR.fullmatch(f"[ek] {KLASOR}/{p.name}"):
        return f"{KLASOR}/{p.name}"
    return kaydet(ofis, p.name, p.read_bytes(), ajan_ad=ajan_ad or "ajan")["yol"]


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
        kok = Path(ofis.kok_klasoru()).resolve()
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
