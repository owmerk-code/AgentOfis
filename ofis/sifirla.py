# -*- coding: utf-8 -*-
"""GUVENLI SIFIRLAMA (08.10.2026; 06.10 listesi #38. Patron: "gercek is
yapmadik, denemeler yaptik; kalabalik ve kirlilik yapmasin, temizle").

Uc adim, sirasi DEGISMEZ:
  1. PLAN    -- silinecek her sey kategorisi, adedi ve boyutuyla listelenir;
               hicbir sey silinmez (`plan`).
  2. YEDEK   -- uygulamadan once ofisin yedegi alinir ve DOGRULANIR (defter
               + proje klasorleri, `yedek.al`). Yedek dogrulanmazsa SILINMEZ.
  3. UYGULA  -- yalniz patron onay metnini AYNEN yazarsa (`ONAY_METNI`).

KORUNAN (asla silinmez): kod; ofisin kadrosu (ajanlar, takimlar, proje
kaydi); ayarlar, hesaplar, kurallar, kalici izinler, zamanlanmis isler; kasa
(`gizli.env`); motor girisleri (Codex `auth.json`/`config.toml`, Gemini
anahtarligi); gomulu tarayici profili (patronun Google/Flow girisi);
beceriler; Flow katalogu; olcumler (fiyat, baglam siniri, motor matrisi);
medya araclari; proje klasorlerindeki PATRONUN dosyalari (yalniz ofisin
gizli `.ofis/` klasoru ve ajan tarayicisinin `.playwright-mcp/` dokumu
silinir; kod deposunun kokundeki `.playwright-mcp/` RAKIP DOKUMUDUR, dokunulmaz).

Neden bir arac: 05.10 ve 08.10'da temizlik elle yapildi; elle yapilan
temizlik bir yeri unutur (karne kaydi model secimini, onaylanmis eksik
kaydi gelistirici listesini, ajan evleri ve Claude oturum kayitlari diski
saptiriyordu). Kural TEK yerde.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from .yollar import OFIS_KODU, ofis_evi

#: Patronun aynen yazacagi onay.
ONAY_METNI = "SIFIRLA"

#: Defterde GECMIS (deneme izi) olan tablolar. Kadro, ayar, hesap, kural,
#: izin, zamanli, cihaz BILEREK yok: onlar yapilandirmadir.
GECMIS_TABLOLARI = ("gorev", "gorev_bagimlilik", "kanit", "karar", "onay", "mesaj", "olay",
                    "kuyruk", "ekip_onerisi", "hafiza_onerisi", "teslim_puani", "tur_anlik",
                    "degisim", "canli_degisim", "brifing", "yazma_kilidi")
#: Hafiza (bilgi, ders, belge) -- denemelerden ogrenilen ve yuklenen.
HAFIZA_TABLOLARI = ("olgu", "ders", "belge", "belge_parca", "konu_takma")

#: Codex evinde DENEME KAYDI olanlar (giris ve yapilandirma DEGIL). OLCULDU
#: (08.10): bunlar tasinip silindikten sonra `codex login status` gecti.
CODEX_KAYITLARI = ("sessions", "archived_sessions", "generated_images", "history.jsonl",
                   "session_index.jsonl", "log", "tmp", "logs_2.sqlite", "logs_2.sqlite-shm",
                   "logs_2.sqlite-wal", "thread_history_1.sqlite", "thread_history_1.sqlite-shm",
                   "thread_history_1.sqlite-wal", "memories_1.sqlite", "memories_1.sqlite-shm",
                   "memories_1.sqlite-wal")

KATEGORILER = {
    "gecmis": "Ofisin defterindeki gecmis: isler, kanitlar, kararlar, onaylar, sohbet, olaylar, sira",
    "hafiza": "Hafiza: bilgiler, dersler, yuklenen belgeler",
    "karne": "Karne ve onaylanmis eksik kayitlari (model secimi ve tahmin bunlardan beslenir)",
    "kopyalar": "Brifing kopyalari, tur geri alma golge depolari, eski tasima arsivi",
    "ajan_evleri": "Artik olmayan ajanlarin evleri; Codex'in oturum/gunluk kayitlari",
    "proje_izleri": "Proje ve takim klasorlerinde ofisin gizli .ofis/ klasoru ve tarayici dokumu",
    "claude_oturumlari": "Ajan kosularinin Claude Code oturum kayitlari (gecici klasorler ve ofis klasorleri)",
    "yedekler": "Eski yedekler (sifirlama oncesi alinan YENI yedek kalir)",
    "kayitlar": "Tarayici gunlugu ve Codex'in var olmayan klasorlere verdigi guven kayitlari",
}


class SifirlaHatasi(RuntimeError):
    pass


# ------------------------------------------------------------------ yardimci
def _boyut(yol: Path) -> int:
    try:
        if yol.is_file():
            return yol.stat().st_size
        return sum(f.stat().st_size for f in yol.rglob("*") if f.is_file())
    except OSError:
        return 0


def _kalem(kategori: str, tur: str, ad: str, yol=None, adet: int = 1, bayt: int = 0, **ek) -> dict:
    return {"kategori": kategori, "tur": tur, "ad": ad, "yol": str(yol) if yol else "",
            "adet": adet, "bayt": bayt, **ek}


def _kodla(yol) -> str:
    """Claude Code'un proje klasoru adi: harf/rakam disi her karakter '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(Path(yol)))


def claude_projeler_koku() -> Path:
    from .kaynaklar import _claude_ev
    return _claude_ev() / "projects"


def _ofis_kokleri(ofis) -> list:
    """Defterdeki proje kokleri, takim klasorleri ve ajan klasorleri.

    YALNIZ mutlak ve en az bir klasor DERINDEKI yollar: kok yanlislikla ev
    klasoru ya da masaustu olsaydi Claude oturumu eslesmesi patronun BUTUN
    projelerini yakalardi."""
    korunan = {Path.home().resolve(), (Path.home() / "Desktop").resolve(),
               Path(tempfile.gettempdir()).resolve()}
    korunan |= set(OFIS_KODU.resolve().parents)
    kokler = set()
    with ofis.db.baglanti() as c:
        for sorgu in ("SELECT kok_klasor FROM proje", "SELECT klasor FROM kanat",
                      "SELECT klasor FROM ajan"):
            try:
                kokler |= {r[0] for r in c.execute(sorgu) if r[0]}
            except Exception:                       # noqa: BLE001 -- eski defter
                pass
    out = []
    for k in kokler:
        p = Path(k)
        if not p.is_absolute():
            continue
        try:
            p = p.resolve()
        except OSError:
            continue
        if p in korunan or any(p == q or p in q.parents for q in korunan) or len(p.parts) < 4:
            continue
        out.append(p)
    return sorted(set(out))


# ---------------------------------------------------------------------- plan
def plan(ofis) -> list:
    """Silinecekler -- HICBIR SEY SILMEZ."""
    out = []
    with ofis.db.baglanti() as c:
        for kat, tablolar in (("gecmis", GECMIS_TABLOLARI), ("hafiza", HAFIZA_TABLOLARI)):
            for t in tablolar:
                try:
                    n = c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                except Exception:                   # noqa: BLE001 -- tablo yok
                    continue
                if n:
                    out.append(_kalem(kat, "tablo", f"defter: {t}", adet=n, tablo=t))
    for ad in ("karne.jsonl", "ofis_eksikleri.jsonl"):
        y = ofis_evi() / ad
        if y.is_file() and y.stat().st_size:
            out.append(_kalem("karne", "dosya_bosalt", f"ev/{ad}", y, bayt=y.stat().st_size))
    from .geri_al import golge_koku
    for kok, etiket in ((ofis_evi() / "brifing", "brifing kopyasi"), (golge_koku(), "golge depo"),
                        (ofis_evi() / "arsiv", "eski arsiv")):
        if kok.is_dir():
            for p in sorted(kok.iterdir()):
                out.append(_kalem("kopyalar", "sil", f"{etiket}: {p.name}", p, bayt=_boyut(p)))
    # Ajan evleri: kadroda OLMAYAN ajanin Gemini evi; ortak evin konusmalari.
    aktif = {a["ad"] for a in ofis.kadro.liste()}
    gev = ofis_evi() / "gemini_ev"
    if gev.is_dir():
        for p in sorted(gev.iterdir()):
            if p.name == "_ortak":
                for alt in ("brain", "conversations"):
                    q = p / ".gemini" / "antigravity-cli" / alt
                    if q.is_dir() and any(q.iterdir()):
                        out.append(_kalem("ajan_evleri", "icini_sil", f"gemini ortak ev: {alt}", q,
                                          bayt=_boyut(q)))
            elif p.is_dir() and p.name not in aktif:
                out.append(_kalem("ajan_evleri", "sil", f"gemini ajan evi: {p.name} (kadroda yok)",
                                  p, bayt=_boyut(p)))
    cev = ofis_evi() / "codex"
    for ad in CODEX_KAYITLARI:
        p = cev / ad
        if p.exists():
            out.append(_kalem("ajan_evleri", "sil", f"codex kaydi: {ad}", p, bayt=_boyut(p)))
    # Proje izleri: yalniz ofisin gizli klasoru ve ajan tarayicisinin dokumu.
    for kok in _ofis_kokleri(ofis):
        if not kok.is_dir() or kok.resolve() == OFIS_KODU.resolve():
            continue
        for ad in (".ofis", ".playwright-mcp"):
            p = kok / ad
            if p.is_dir() and any(p.iterdir()):
                out.append(_kalem("proje_izleri", "icini_sil", f"{kok.name}/{ad}", p, bayt=_boyut(p)))
    # Claude Code oturum kayitlari: gecici klasorler + ofis klasorleri (+ eski
    # `AgentOfis\\calisma` koku). Kod deposunun KENDI kaydi ve patronun baska
    # projeleri ESLESMEZ.
    pk = claude_projeler_koku()
    if pk.is_dir():
        gecici = _kodla(Path(tempfile.gettempdir()).resolve())
        # Eski duzenin artiklari: `AgentOfis\calisma*` (01.10 ayrimindan once
        # ajanlarin koku) ve ev klasorundeki uctan uca ofis kopyalari.
        onekler = [gecici + "-", _kodla(OFIS_KODU / "calisma"),
                   _kodla(Path.home() / "ofis-uctan-uca")]
        tam = {_kodla(k).lower() for k in _ofis_kokleri(ofis)} | {gecici.lower()}
        onekler += [t + "-" for t in tam if t != gecici.lower()]
        onekler = [o.lower() for o in onekler]
        kod = _kodla(OFIS_KODU).lower()
        for p in sorted(pk.iterdir()):
            a = p.name.lower()
            if a == kod:
                continue
            if a in tam or any(a.startswith(o) for o in onekler):
                out.append(_kalem("claude_oturumlari", "sil", f"claude oturumu: {p.name}", p,
                                  bayt=_boyut(p)))
    # Eski yedekler: yerel yedek klasoru, ek hedefler (Drive), elle yedekler,
    # defterin eski kopyalari. Sifirlama oncesi alinacak yedek PLANDA YOK.
    from . import yedek as _y
    hedefler = [_y.yedek_koku()] + [Path(h) for h in (_y.ayar_oku().get("hedefler") or [])]
    # EN YENI yedek (her hedefteki kopyasiyla) HER ZAMAN kalir: sifirlama
    # oncesi alinan yedek bir sonraki sifirlamada silinmesin; ofis hicbir
    # an yedeksiz kalmasin. Ad zaman damgasiyla basladigi icin ad sirasi =
    # zaman sirasi.
    tumu = [p for h in hedefler if Path(h).is_dir() for p in Path(h).glob(_y.AD_ONEKI + "*")]
    tam_arsiv = sorted(p.name for p in tumu if p.suffix == ".zip")
    en_yeni = tam_arsiv[-1] if tam_arsiv else ""
    for h in hedefler:
        if Path(h).is_dir():
            for p in sorted(Path(h).glob(_y.AD_ONEKI + "*")):
                if p.name == en_yeni:
                    continue
                out.append(_kalem("yedekler", "sil", f"yedek: {p.name} ({Path(h).name})", p,
                                  bayt=_boyut(p)))
    for p in sorted((ofis_evi() / "yedek" / "elle").glob("*")) if (ofis_evi() / "yedek" / "elle").is_dir() else []:
        out.append(_kalem("yedekler", "sil", f"elle yedek: {p.name}", p, bayt=_boyut(p)))
    veri = Path(ofis.db.yol).parent
    for desen in ("*.sqlite3.yedek-*", "ofis-yedek-*.sqlite3", "ofis.yedek-*.sqlite3"):
        for p in sorted(veri.glob(desen)):
            out.append(_kalem("yedekler", "sil", f"defter kopyasi: {p.name}", p, bayt=_boyut(p)))
    # Gunlukler ve var olmayan klasorlere verilmis Codex guveni.
    kl = ofis_evi() / "kabin.log"
    if kl.is_file() and kl.stat().st_size:
        out.append(_kalem("kayitlar", "dosya_bosalt", "ev/kabin.log", kl, bayt=kl.stat().st_size))
    bayat = codex_bayat_guvenler()
    if bayat:
        out.append(_kalem("kayitlar", "codex_guven", f"codex guven kaydi: {len(bayat)} yok olan klasor",
                          cev / "config.toml", adet=len(bayat)))
    return out


_GUVEN = re.compile(r"^\[projects\.'(?P<yol>[^']+)'\]\s*\n(?:(?!\[)[^\n]*\n?)*", re.M)


def codex_bayat_guvenler(config: Path = None) -> list:
    """Codex `config.toml`unda ARTIK VAR OLMAYAN klasorlere verilmis guven."""
    config = config or (ofis_evi() / "codex" / "config.toml")
    try:
        metin = config.read_text(encoding="utf-8")
    except OSError:
        return []
    return [m.group("yol") for m in _GUVEN.finditer(metin) if not Path(m.group("yol")).exists()]


def _codex_guven_temizle(config: Path) -> int:
    from .dosya import atomik_yaz
    metin = config.read_text(encoding="utf-8")
    silinen = 0

    def _degistir(m):
        nonlocal silinen
        if Path(m.group("yol")).exists():
            return m.group(0)
        silinen += 1
        return ""

    yeni = _GUVEN.sub(_degistir, metin)
    if silinen:
        atomik_yaz(config, re.sub(r"\n{3,}", "\n\n", yeni))
    return silinen


def ozet(kalemler: list) -> dict:
    """Kategori -> {kalem, adet, bayt}."""
    out = {}
    for k in kalemler:
        o = out.setdefault(k["kategori"], {"kalem": 0, "adet": 0, "bayt": 0,
                                           "aciklama": KATEGORILER.get(k["kategori"], "")})
        o["kalem"] += 1
        o["adet"] += k["adet"]
        o["bayt"] += k["bayt"]
    return out


# ---------------------------------------------------------------------- uygula
def uygula(ofis, onay: str, *, kategoriler=None, yedek_al: bool = True,
           yedek_secenek: dict = None) -> dict:
    """Yedek alir, dogrular, sonra yalniz secili kategorileri siler.

    `onay` ONAY_METNI'ne AYNEN esit degilse HICBIR SEY yapilmaz. Ofis
    mesgulse (calisan is, sirada mesaj) yapilmaz: kosan ajanin dosyasi ve
    defteri silinmez."""
    if (onay or "").strip() != ONAY_METNI:
        raise SifirlaHatasi(f"Onay metni yanlis: sifirlama icin '{ONAY_METNI}' yazilmali.")
    from . import guncelleme
    mesgul = guncelleme.mesgul(ofis.db)
    if mesgul:
        raise SifirlaHatasi(f"Ofis su an calisiyor ({mesgul}); is bitince sifirla.")
    secili = set(kategoriler or KATEGORILER)
    bilinmeyen = secili - set(KATEGORILER)
    if bilinmeyen:
        raise SifirlaHatasi(f"Bilinmeyen kategori: {', '.join(sorted(bilinmeyen))}")
    # GUNCELLEME KILIDI (08.10, gercek ofiste olculdu): otomatik CLI
    # guncellemesinin deneme turu sifirlamayla AYNI SANIYEDE basladi; deneme
    # turunun yeni kayitlari silinenlerin arasina karisti. Sifirlama surerken
    # guncelleme baslamaz; guncelleme surerken sifirlama yapilmaz.
    sahip = f"sifirla:{os.getpid()}"
    if not guncelleme._kilit_al(ofis.db, ofis.proje_id, sahip):
        raise SifirlaHatasi("Otomatik guncelleme su an deneme turu kosuyor; birkac dakika sonra sifirla.")
    try:
        return _uygula(ofis, secili, yedek_al, yedek_secenek)
    finally:
        guncelleme._kilit_birak(ofis.db, ofis.proje_id, sahip)


def _sil(p: Path) -> None:
    """Salt okunur dosyayi da siler. OLCULDU (08.10): golge depolarin git
    nesneleri Windows'ta salt okunurdur; duz `rmtree` onlarda dustu ve
    gercek ofiste iki golge depo silinemedi."""
    import stat

    def _yazilabilir_yap(islev, yol, _hata):
        os.chmod(yol, stat.S_IWRITE)
        islev(yol)

    if p.is_dir():
        try:
            shutil.rmtree(p, onexc=_yazilabilir_yap)
        except TypeError:                           # Python < 3.12
            shutil.rmtree(p, onerror=_yazilabilir_yap)
    elif p.exists():
        try:
            p.unlink()
        except PermissionError:
            os.chmod(p, stat.S_IWRITE)
            p.unlink()


def _uygula(ofis, secili, yedek_al, yedek_secenek) -> dict:
    rapor = {"yedek": None, "silinen": [], "hatalar": []}
    if yedek_al:
        from . import yedek as _y
        try:
            y = _y.al("sifirlama-oncesi", **(yedek_secenek or {}))
        except (_y.YedekHatasi, OSError) as exc:
            raise SifirlaHatasi(f"Yedek alinamadi ya da dogrulanmadi, HICBIR SEY SILINMEDI: {exc}")
        d = _y.dogrula(Path(y["arsiv"]))
        if not d.get("tamam"):
            raise SifirlaHatasi(f"Yedek dogrulanmadi, HICBIR SEY SILINMEDI: {d.get('bulgular')}")
        rapor["yedek"] = y["arsiv"]
    kalemler = [k for k in plan(ofis) if k["kategori"] in secili
                and not (rapor["yedek"] and k["yol"] and Path(k["yol"]).name == Path(rapor["yedek"]).name)]
    with ofis.db.baglanti() as c:
        for k in kalemler:
            if k["tur"] == "tablo":
                c.execute(f"DELETE FROM [{k['tablo']}]")
                rapor["silinen"].append(k)
    for k in kalemler:
        if k["tur"] == "tablo":
            continue
        p = Path(k["yol"])
        try:
            if k["tur"] == "sil":
                _sil(p)
            elif k["tur"] == "icini_sil":
                for q in list(p.iterdir()):
                    _sil(q)
            elif k["tur"] == "dosya_bosalt":
                p.write_text("", encoding="utf-8")
            elif k["tur"] == "codex_guven":
                _codex_guven_temizle(p)
            rapor["silinen"].append(k)
        except OSError as exc:
            rapor["hatalar"].append(f"{k['ad']}: {exc}")
    ofis.db.olay_yaz(ofis.proje_id, "sifirlandi",
                     f"Guvenli sifirlama: {len(rapor['silinen'])} kalem silindi"
                     + (f", {len(rapor['hatalar'])} kalem silinemedi ({'; '.join(rapor['hatalar'][:5])})"
                        if rapor["hatalar"] else "")
                     + (f"; yedek {Path(rapor['yedek']).name}" if rapor["yedek"] else ""),
                     ajan_ad="insan")
    return rapor


def okunur_bayt(n: int) -> str:
    for birim in ("B", "KB", "MB", "GB"):
        if n < 1024 or birim == "GB":
            return f"{n:.0f} {birim}" if birim == "B" else f"{n:.1f} {birim}"
        n /= 1024
    return str(n)
