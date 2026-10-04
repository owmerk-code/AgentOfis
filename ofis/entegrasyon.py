# -*- coding: utf-8 -*-
"""ENTEGRASYONLAR -- hangi dis hesap bagli, OLCULMUS; nasil baglanir, YAZILI.

Kullanici (02.10.2026): *"Shopify ve Meta icin baglanmasi gereken altyapi
hazir olsun; gerektiginde ben hesaplara girip baglayacagim."* Rakipte
(Muratify) ayarlarda entegrasyon kartlari var: anahtar adi, Bagla,
"anahtar nasil alinir". Bizden farki ayni kural: **asla uydurmaz**.

Uc kaynak, uc olcum:
  * claude.ai baglayicilari (Shopify, Meta Reklamlari, Gmail, Drive, Canva,
    Supabase...): `baglayici.durum()` -- `claude mcp list`. Gecerli olan
    CLI'in gordugu (web'de bagli gorunup CLI'da "yetki yok" olabilir;
    olculdu 21.09). Giris: `claude mcp login "claude.ai <Ad>"` (CLI'in
    kendi --help'inde: "Authenticate with an MCP server (HTTP, SSE, or
    claude.ai connector)").
  * komut satiri araclari: GitHub (`gh auth status`), Vercel
    (`vercel whoami`). Kurulu degilse "kurulu degil" + kurulum komutu.
  * API anahtarlari: ofisin kasasi (`gizli.liste()` -- DEGER DONMEZ).

Ofis giris YAPMAZ, cikis YAPMAZ: komutu soyler, insan kendi terminalinde
kosturur (sifre ve OAuth insanin -- `giris.py` ile ayni kural).

Durumlar: `bagli` · `giris_gerekli` · `hesapta_yok` (claude.ai'da
eklenmemis) · `kurulu_degil` · `sorunlu` (bagli ama son gercek cagri
dustu) · `olculemedi`. Dorduncu hal olmadan calismayan olcum "yok" gibi
gorunurdu.
"""

from __future__ import annotations

import re
import shutil
import subprocess

from .surec import PENCERE_YOK
import time

#: claude.ai baglayicilari icin TEK cumle -- kapinin OLCULEN kurali
#: (`riskli.arac_degerlendir`, 02.10.2026 gercek arac adlariyla olculdu):
#: okuma serbest; olusturma/duzenleme SORULMAZ ama kayda gecer (Shopify
#: create-product, Meta ads_create_campaign PAUSED -> kayit); argumanda
#: yayina alma varsa (status ACTIVE) yayin sayilir ve sorulur; yayinlama,
#: gonderme, silme, para (create-discount, boost) her zaman sorulur.
#: Ilk yazilan cumle "yazan her cagri sorulur" diyordu -- olcunce YANLIS
#: cikti; kart kapinin yapmadigini vaat etmemeli.
CLAUDE_RISK = ("Okumak serbest. Taslak oluşturma ve düzenleme sorulmaz, kayda geçer. "
               "Yayına alma, gönderme, silme ve para harcayan her adım sana sorulur.")

#: Bilinen servisler ve kategorileri. Liste SUZGEC DEGIL: hesapta olculen
#: her claude.ai baglayicisi (burada yazmasa da) "Diger" altinda gorunur.
KATALOG = [
    # ad (claude mcp list'teki ad), kategori, kaynak
    ("Shopify", "Mağaza", "claude"),
    ("Meta Reklamları", "Reklam", "claude"),
    ("Gmail", "E-posta", "claude"),
    ("Google Drive", "Dosya", "claude"),
    ("Canva", "Tasarım", "claude"),
    ("Supabase", "Veritabanı", "claude"),
    ("GitHub", "Kod", "gh"),
    ("Vercel", "Yayın", "vercel"),
    ("Higgsfield", "Medya", "claude"),
    ("WordPress.com", "Web sitesi", "claude"),
    ("n8n", "Otomasyon", "claude"),
    ("Microsoft 365", "E-posta", "claude"),
]
CLAUDE_BAGLAYICI_SAYFASI = "https://claude.ai/settings/connectors"

_ONBELLEK = {"an": 0.0, "cli": {}}
CLI_ONBELLEK_SN = 300


def _kos(argv, zaman_asimi=20):
    try:
        p = subprocess.run(argv, capture_output=True, timeout=zaman_asimi,
                           stdin=subprocess.DEVNULL, creationflags=PENCERE_YOK)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    cikti = (p.stdout or b"") + b"\n" + (p.stderr or b"")
    return p.returncode, cikti.decode("utf-8", errors="replace")


def _gh() -> dict:
    yol = shutil.which("gh")
    if not yol:
        return {"durum": "kurulu_degil", "ayrinti": "GitHub CLI (gh) kurulu değil.",
                "bagla": "winget install GitHub.cli ; gh auth login"}
    kod, cikti = _kos([yol, "auth", "status"])
    if kod is None:
        return {"durum": "olculemedi", "ayrinti": cikti[:200]}
    m = re.search(r"account (\S+)", cikti)
    if kod == 0:
        return {"durum": "bagli", "ayrinti": f"hesap: {m.group(1)}" if m else "giriş yapılmış"}
    return {"durum": "giris_gerekli", "ayrinti": "gh kurulu, giriş yok."}


def _vercel() -> dict:
    yol = shutil.which("vercel")
    if not yol:
        return {"durum": "kurulu_degil", "ayrinti": "Vercel CLI kurulu değil.",
                "bagla": "npm i -g vercel ; vercel login"}
    kod, cikti = _kos([yol, "whoami"], 30)
    if kod is None:
        return {"durum": "olculemedi", "ayrinti": cikti[:200]}
    if kod == 0:
        ad = next((s.strip() for s in cikti.splitlines()
                   if s.strip() and not s.lower().startswith("vercel cli")), "")
        return {"durum": "bagli", "ayrinti": f"hesap: {ad}" if ad else "giriş yapılmış"}
    return {"durum": "giris_gerekli", "ayrinti": "Vercel CLI kurulu, giriş yok."}


CLI_OLCER = {"gh": _gh, "vercel": _vercel}
CLI_KOPAR = {"gh": "gh auth logout", "vercel": "vercel logout"}
CLI_BAGLA = {"gh": "gh auth login", "vercel": "vercel login"}
CLI_RISK = {
    "gh": ("Push ve yayın sana sorulur (mesajında açıkça istediğin push o iş için "
           "izindir); silme ve zorla push her zaman sorulur."),
    "vercel": "Canlıya alma (deploy) sana sorulur.",
}


def _cli_olc(taze: bool) -> dict:
    if taze or time.time() - _ONBELLEK["an"] > CLI_ONBELLEK_SN or not _ONBELLEK["cli"]:
        _ONBELLEK["cli"] = {k: f() for k, f in CLI_OLCER.items()}
        _ONBELLEK["an"] = time.time()
    return _ONBELLEK["cli"]


def _kapali_baglayici() -> set:
    from .kaynaklar import kapalilar
    return kapalilar("claude_baglayici")


def _claude_karti(ad: str, kategori: str, d: dict, olculdu: bool) -> dict:
    kayit = d.get(ad)
    if not olculdu:
        durum, ayrinti = "olculemedi", "claude mcp list koşmadı; 'yok' denemez."
    elif kayit is None:
        durum, ayrinti = "hesapta_yok", "claude.ai hesabında bu bağlayıcı eklenmemiş."
    elif kayit.get("bagli") and kayit.get("sorun"):
        durum = "sorunlu"
        ayrinti = f"bağlı görünüyor ama son gerçek çağrı düştü ({kayit['sorun'].get('dakika', '?')} dk önce)."
    elif kayit.get("bagli"):
        durum, ayrinti = "bagli", "Claude CLI erişebiliyor."
    else:
        durum, ayrinti = "giris_gerekli", "tanımlı ama Claude CLI girişi yapılmamış."
    ad_cli = f"claude.ai {ad}"
    return {
        "ad": ad, "kategori": kategori, "kaynak": "claude.ai bağlayıcısı",
        "durum": durum, "ayrinti": ayrinti,
        "bagla": {"komut": f'claude mcp login "{ad_cli}"', "url": CLAUDE_BAGLAYICI_SAYFASI},
        "kopar": {"komut": f'claude mcp logout "{ad_cli}"'},
        "risk": CLAUDE_RISK, "arac_motoru": "claude",
        "grup": "claude_baglayici",
        "ajanlara_acik": ad not in _kapali_baglayici(),
    }


def kartlar(*, taze: bool = False) -> dict:
    """Ayarlar > Entegrasyonlar'in verisi. `taze`: olcumu bekler (~15-20 sn)."""
    from . import baglayici, gizli
    d = baglayici.durum(taze=True) if taze else baglayici.durum()
    if not taze:
        baglayici.arkada_tazele()
    olculdu = bool(d)
    cli = _cli_olc(taze)
    out, gorulen = [], set()
    for ad, kategori, kaynak in KATALOG:
        gorulen.add(ad)
        if kaynak == "claude":
            out.append(_claude_karti(ad, kategori, d, olculdu))
        else:
            o = cli.get(kaynak) or {"durum": "olculemedi", "ayrinti": ""}
            out.append({
                "ad": ad, "kategori": kategori, "kaynak": "komut satırı aracı",
                "durum": o["durum"], "ayrinti": o.get("ayrinti", ""),
                "bagla": {"komut": o.get("bagla") or CLI_BAGLA[kaynak]},
                "kopar": {"komut": CLI_KOPAR[kaynak]},
                "risk": CLI_RISK[kaynak], "arac_motoru": "hepsi",
            })
    for ad in sorted(d):
        if ad not in gorulen:
            out.append(_claude_karti(ad, "Diğer", d, True))
    try:
        anahtarlar = gizli.liste()
    except Exception as exc:                 # noqa: BLE001 -- sebebiyle gosterilir
        anahtarlar, hata = [], f"kasa okunamadı: {exc}"
    else:
        hata = ""
    return {"kartlar": out, "olcum_zamani": baglayici.olcum_zamani() or "",
            "anahtarlar": anahtarlar, "kasa_hatasi": hata}

