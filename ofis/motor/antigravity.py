# -*- coding: utf-8 -*-
"""ANTIGRAVITY adaptoru -- Google AI Pro aboneligi; sistemde motor adi `gemini`.

Neden Antigravity (04.10.2026): Gemini CLI 18.06.2026'dan beri Google AI Pro /
Ultra'ya KAPALI ("This client is no longer supported..."); yerine `agy`
(Antigravity CLI) geldi. Eski `gemini.py` (Gemini CLI) dosyada duruyor ama
deftere takili degil.

OLCULENLER (agy 1.x, bu makinede, bos gecici klasorde, 04.10.2026):

* `agy --output-format stream-json -p <istem>` -> NDJSON: `init`
  (conversation_id, model, araclar) · `step_update` (arac ACTIVE/DONE +
  parametreler, `agent_response` text_delta, adim basina `usage`) · `result`
  (status, response, denied_actions). `--conversation <id>` surdurur.
* AYRI EV: `USERPROFILE`/`HOME` baska klasore verilince ayarlar ve
  konusmalar ORAYA yazilir, giris (sistem anahtarligi) yine gecerli. Patronun
  kendi `agy`sine dokunulmaz. Her AJANIN kendi evi var: ayni anda kosan iki
  ajanin MCP/kanca ayarlari karismaz, konusma gecmisi ajanin evinde kalir.
* KAPI: `~/.gemini/config/hooks.json` `PreToolUse` kancasi her araci gorur
  (`toolCall.name/args`). Headless'ta `allow` YOK SAYILIR (Google #1053);
  RED calisir: cikis 2 + gerekce stderr'e (model gerekceyi aynen gordu).
  Izinsiz komut kendiliginden REDDEDILIR (kapali kalir); `rm` kancada
  durdu, dosya yerinde kaldi. Komutlar `permissions.allow: command(*)` ile
  kancaya ULASIR, karari kanca verir (`ofis/kanca.py --agy`).
* MCP: `~/.gemini/config/mcp_config.json` (`mcpServers`, Claude bicimi);
  araclar `call_mcp_tool {ServerName, ToolName}` ile cagrilir; surecin ORTAMI
  sunucuya gecer (kimlik dogru geldi). `mcp(<sunucu>/*)` izni gerekir.
* GORSEL: yerlesik `generate_image` (alt ajan) aboneliktan uretir; dosya
  agy'nin `brain/<konusma>/` klasorune duser ve tur, gorsel bitmeden
  kapanabilir (#1044). Tur sonunda yeni gorseller `.ofis/ekler/`e alinir.
* VIDEO araci YOK (model kendisi soyledi) -- video gomulu tarayicida Flow ile.

Bayraklar: `mcp_konusur=True` (ofis araclari), `izin_kancasi=True` (kanca),
`butce_destegi=False` (tur basina dolar tavani yok), `tui_destegi=False`
(gercek terminal kipi henuz olculmedi -- arka kipte kosar).
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Iterator

from .tip import (dokum_ekle, ortam_hazirla, Motor, MotorHatasi, MotorOlayi,
                  MotorYokHatasi, SurecKafesi)

_PENCERE_YOK = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_SON = object()

VARSAYILAN_ZAMAN_ASIMI = 1800.0
NABIZ_ARALIGI = 1.0
GORSEL_UZANTI = (".png", ".jpg", ".jpeg", ".webp")
#: Gorsel uretimi alt ajanda surer ve tur ondan once bitebilir (#1044):
#: tur sonunda bu kadar beklenir (yeni gorsel yoksa erken cikilir degil --
#: alt ajanin calistigi olculemiyor; kisa ve sabit).
GORSEL_BEKLE_SN = 20.0

SISTEM_EKI = (
    "AgentOfis agent sisteminde bir ajansin. Gorevin bu mesajin devamindadir; "
    "gorevini bir DOSYADA ARAMA. Turkce yaz. Yalniz brifingdeki YAZMA ALANI "
    "icine yaz.\n"
    "ARACLAR: Sistemin araclari `call_mcp_tool` ile, ServerName \"ofis\": "
    "`kanit_ekle` (kanitsiz is KAPANMAZ -- isi bitirince MUTLAKA cagir), "
    "`sohbete_yaz` (patrona mesaj/dosya), `soru_sor`, `onay_iste`, `gorsel_uret`. "
    "TARAYICI: yalniz ServerName \"tarayici\" araclari (gomulu tarayici); kendi "
    "browser_* araclarin KAPALI. Bir arac \"ONAY ISTENDI -- SIMDI DUR\" derse "
    "o eylemi TEKRAR DENEME: yaptiklarini kanit_ekle ile yaz ve turu bitir.\n"
    "GORSEL: generate_image ile urettigin gorseli proje icinde `.ofis/ekler/` "
    "altina kopyala ve sohbete_yaz(ekler=[...]) ile gonder.\n\n"
)

#: Efor bizim sozlugumuz -> agy `--effort`.
EFOR_CEVRIMI = {"dusuk": "low", "normal": "medium", "yuksek": "high",
                "cok_yuksek": "xhigh"}


def _calistirilabilir_bul() -> str:
    """agy.exe: `OFIS_AGY` > `%LOCALAPPDATA%\\agy\\bin\\agy.exe` > PATH."""
    adaylar = [os.environ.get("OFIS_AGY", ""),
               os.path.join(os.environ.get("LOCALAPPDATA", ""), "agy", "bin", "agy.exe"),
               shutil.which("agy") or ""]
    for a in adaylar:
        if a and Path(a).is_file():
            return a
    return ""


def kanca_komutu() -> str:
    """Kanca komutu -- agy onu Windows'ta `cmd /c` ile kosar.

    OLCULDU (04.10.2026, gercek set G03/G05/G11 gemini): `"C:/.../python.exe"
    "C:/.../kanca.py" --agy` -> cmd tirnaklari bozdu: "not recognized as an
    internal or external command"; kapi KAPALI kaldi (hicbir arac kosmadi) ama
    isci 8 tur bosa denedi. agy (Go) komutu cmd'ye TEK argumanla verir ve
    tirnaklari `\"` diye kacirir; cmd bunu anlamaz (olculdu, ayni hata). Bu
    yuzden komut HIC TIRNAK tasimaz: yolda bosluk varsa Windows'un bosluksuz
    KISA yol adi (8.3) kullanilir.
    """
    return f"{_bosluksuz(Path(sys.executable))} {_bosluksuz(Path(__file__).resolve().parent.parent / 'kanca.py')} --agy"


def _bosluksuz(yol: Path) -> str:
    duz = yol.as_posix()
    if " " not in duz or os.name != "nt":
        return duz
    try:
        import ctypes
        tampon = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.GetShortPathNameW(str(yol), tampon, 1024):
            return Path(tampon.value).as_posix()
    except Exception:                            # noqa: BLE001 -- kisa ad yoksa oldugu gibi
        pass
    return duz


def kanca_sina(komut: str, ortam: dict = None) -> str:
    """Kancayi agy'nin calistirdigi GIBI bir kez kostur: `cmd /c` + komut TEK
    argumanla (Go'nun kacirma kurali; Python liste bicimi ayni kurali uygular --
    olculdu, eski tirnakli bicim burada da agy'deki hatayi verdi). Silme
    REDDEDILMELI. Bos donus = calisiyor; aksi halde sebep (tur baslamaz)."""
    girdi = json.dumps({"toolCall": {"name": "run_command",
                                     "args": {"CommandLine": "Remove-Item oz-sinama.txt"}}})
    temiz = {k: v for k, v in (ortam or os.environ).items()
             if k not in ("OFIS_DB", "OFIS_PROJE", "OFIS_AJAN", "OFIS_GOREV")}
    try:
        p = subprocess.run(["cmd", "/c", komut], input=girdi, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60, env=temiz,
                           creationflags=_PENCERE_YOK)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"kanca baslatilamadi: {exc}"
    if p.returncode != 2:
        return (f"kanca silmeyi REDDETMEDI (cikis {p.returncode}): "
                + (p.stderr or p.stdout or "")[-300:])
    return ""


def _girdi_ozeti(arac: str, param) -> str:
    if not isinstance(param, dict):
        return ""
    for anahtar in ("CommandLine", "TargetFile", "AbsolutePath", "Query", "Url",
                    "DirectoryPath", "Pattern", "ToolName", "Prompt"):
        if param.get(anahtar):
            return f"{anahtar}: {str(param[anahtar])[:160]}"
    return json.dumps(param, ensure_ascii=False)[:160]


class AntigravityMotoru(Motor):
    """Google Antigravity CLI (`agy`) uzerinden Gemini (ve Google limitindeki
    Claude/GPT-OSS) modelleri."""

    ad = "gemini"
    mcp_konusur = True
    butce_destegi = False
    izin_kancasi = True
    tur_ici_mesaj = False
    araclar_kapatilabilir = False
    baglayici_tasir = False
    tui_destegi = False

    def __init__(self, *, calistirilabilir=None, zaman_asimi: float = None,
                 ev_koku: str = "") -> None:
        # `calistirilabilir` liste olabilir (sinama: [python, sahte_agy.py]).
        if calistirilabilir is None:
            calistirilabilir = _calistirilabilir_bul()
        self.calistirilabilir = calistirilabilir
        self.zaman_asimi = float(zaman_asimi or VARSAYILAN_ZAMAN_ASIMI)
        self._ev_koku = ev_koku

    # -- durum -------------------------------------------------------------

    def _onek(self) -> list:
        c = self.calistirilabilir
        return list(c) if isinstance(c, (list, tuple)) else ([c] if c else [])

    def musait_mi(self) -> bool:
        onek = self._onek()
        return bool(onek) and Path(onek[-1] if len(onek) > 1 else onek[0]).exists()

    def durum_notu(self) -> str:
        return "" if self.musait_mi() else (
            "Antigravity CLI (agy) kurulu degil -- patron kurar: "
            "irm https://antigravity.google/cli/install.ps1 | iex")

    def ev(self, ajan_ad: str) -> Path:
        """Ajanin AYRI evi (USERPROFILE): ayarlar, konusmalar, kanca, MCP."""
        if self._ev_koku:
            kok = Path(self._ev_koku)
        else:
            from ..yollar import ofis_evi
            kok = ofis_evi() / "gemini_ev"
        guvenli = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (ajan_ad or "_ortak"))
        return kok / guvenli

    def _evi_hazirla(self, ev: Path, sunucular: dict) -> None:
        """Kanca, MCP ve izin dosyalari -- her tur yeniden (ajan basina ev)."""
        cfg = ev / ".gemini" / "config"
        cli = ev / ".gemini" / "antigravity-cli"
        cfg.mkdir(parents=True, exist_ok=True)
        cli.mkdir(parents=True, exist_ok=True)
        komut = kanca_komutu()
        (cfg / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [
            {"matcher": "*", "hooks": [{"type": "command", "command": komut}]}]}}),
            encoding="utf-8")
        (cfg / "mcp_config.json").write_text(json.dumps({"mcpServers": sunucular},
                                                        ensure_ascii=False), encoding="utf-8")
        izin = ["command(*)"] + [f"mcp({ad}/*)" for ad in sunucular]
        (cli / "settings.json").write_text(json.dumps({"permissions": {"allow": izin}}),
                                           encoding="utf-8")

    @staticmethod
    def _sunucular(mcp_yapilandirma: str) -> tuple:
        """Sistemin MCP JSON'u -> (agy icin sunucular, surece verilecek ortam)."""
        if not mcp_yapilandirma:
            return {}, {}
        try:
            veri = json.loads(mcp_yapilandirma)
        except ValueError:
            p = Path(mcp_yapilandirma)
            veri = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
        sunucular, ortam = {}, {}
        for ad, s in (veri.get("mcpServers") or {}).items():
            s = dict(s or {})
            ortam.update({k: str(v) for k, v in (s.get("env") or {}).items()})
            s.pop("alwaysLoad", None)
            sunucular[ad] = s
        return sunucular, ortam

    # -- tur ---------------------------------------------------------------

    def tur_kos(self, metin: str, *, klasor: str, oturum_id: str = "", model: str = "",
                efor: str = "normal", yazabilir: bool = True, ek_klasorler: tuple = (),
                butce_usd: float = None, zaman_asimi: float = None,
                mcp_yapilandirma: str = "", izinli_araclar: tuple = (),
                ek_ortam: dict = None, araclar_kapali: bool = False,
                izin_araci: str = "", kanal=None) -> Iterator[MotorOlayi]:
        metin = str(metin or "").strip()
        if not metin:
            raise MotorHatasi("Bos brifing kosulamaz.")
        if not self.musait_mi():
            raise MotorYokHatasi(self.durum_notu())
        if butce_usd:
            raise MotorHatasi("Antigravity tur basina dolar tavani UYGULAYAMAZ "
                              "(butce_destegi=False); tavanli tur bu motora verilmez.")
        if araclar_kapali:
            raise MotorHatasi("Antigravity araclari kapatamaz (araclar_kapatilabilir=False).")
        kok = Path(klasor).expanduser().resolve()
        if not kok.is_dir():
            raise MotorHatasi(f"Ajan calisma klasoru yok: {kok}")

        sunucular, mcp_ortam = self._sunucular(mcp_yapilandirma)
        ajan_ad = mcp_ortam.get("OFIS_AJAN") or (ek_ortam or {}).get("OFIS_AJAN") or "_ortak"
        ev = self.ev(ajan_ad)
        self._evi_hazirla(ev, sunucular)
        # KAPI CALISMIYORSA TUR BASLAMAZ (bkz. `kanca_komutu`): sessizce
        # her araci reddeden bir kapiyla tur kosmak limit yakar, is ilerlemez.
        neden = kanca_sina(kanca_komutu())
        if neden:
            yield MotorOlayi("hata", f"Ofis kapisi calismiyor, tur BASLAMADI: {neden}",
                             {"sebep": "kapi"})
            yield MotorOlayi("bitti", "", {"basarili": False, "sebep": "kapi",
                                           "oturum_id": oturum_id})
            return

        komut = self._onek() + ["--output-format", "stream-json"]
        if model:
            komut += ["--model", str(model)]
        if EFOR_CEVRIMI.get(efor) and not str(model or "").endswith(("-low", "-medium", "-high")):
            komut += ["--effort", EFOR_CEVRIMI[efor]]
        if not yazabilir:
            komut += ["--mode", "plan"]          # salt okunur: yapiyla, ricayla degil
        for ek in ek_klasorler or ():
            komut += ["--add-dir", str(ek)]
        if oturum_id:
            komut += ["--conversation", str(oturum_id)]
        komut += ["-p", SISTEM_EKI + metin]

        ortam = ortam_hazirla(os.environ, ek={"USERPROFILE": str(ev), "HOME": str(ev),
                                              **mcp_ortam, **(ek_ortam or {})},
                              izinli=tuple(ek_ortam or ()) + tuple(mcp_ortam))
        sinir = float(zaman_asimi or self.zaman_asimi)
        basladi = time.monotonic()
        baslangic_an = time.time()
        try:
            surec = subprocess.Popen(komut, cwd=str(kok), env=ortam, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                     encoding="utf-8", errors="replace", bufsize=1,
                                     creationflags=_PENCERE_YOK)
        except OSError as exc:
            raise MotorYokHatasi(f"agy baslatilamadi: {exc}") from exc
        kafes = SurecKafesi(surec)
        yield MotorOlayi("basladi", f"{self.ad} turu basladi",
                         {"oturum_id": oturum_id, "devam": bool(oturum_id), "klasor": str(kok)})

        satirlar: queue.Queue = queue.Queue()
        hata_parca: list = []

        def _oku():
            for s in surec.stdout:
                satirlar.put(s)
            satirlar.put(_SON)

        def _hata():
            for s in surec.stderr:
                hata_parca.append(s)

        threading.Thread(target=_oku, daemon=True, name="agy-stdout").start()
        threading.Thread(target=_hata, daemon=True, name="agy-stderr").start()

        durum = {"oturum_id": oturum_id, "model": str(model or ""), "metin": [], "jeton": 0,
                 "dokum": {}, "arac_sayisi": 0, "sonuc": None, "reddedilen": []}
        zaman_asti = False
        try:
            while True:
                kalan = sinir - (time.monotonic() - basladi)
                if kalan <= 0:
                    zaman_asti = True
                    break
                try:
                    s = satirlar.get(timeout=min(NABIZ_ARALIGI, kalan))
                except queue.Empty:
                    yield MotorOlayi("nabiz", "", {})
                    continue
                if s is _SON:
                    break
                for olay in self._satir_cevir(s, durum):
                    yield olay
        finally:
            if zaman_asti or surec.poll() is None:
                kafes.kes() if hasattr(kafes, "kes") else surec.kill()
            try:
                surec.wait(timeout=10)
            except subprocess.TimeoutExpired:
                surec.kill()
            try:
                kafes.kapat()
            except Exception:                    # noqa: BLE001
                pass

        # GORSEL TESLIMI: alt ajanin urettigi gorsel tur bittikten sonra da
        # dusebilir (#1044). Bu tur icinde olusan yeni gorseller `.ofis/ekler/`e.
        teslim = self._gorselleri_al(ev, kok, baslangic_an, durum)
        for yol in teslim:
            yield MotorOlayi("arac_sonuc", f"gorsel teslim alindi: {yol}",
                             {"hatali": False, "cagri_id": "", "arac": "generate_image"})

        sonuc = durum["sonuc"] or {}
        stderr = "".join(hata_parca)
        durum_str = str(sonuc.get("status") or "")
        dusuk = (durum_str + " " + stderr + " " + str(sonuc.get("response") or "")).lower()
        limit = any(k in dusuk for k in ("quota", "resource_exhausted", "rate limit",
                                         "rate_limit", "429", "usage limit"))
        basarili = (not zaman_asti and surec.returncode == 0 and durum_str == "SUCCESS")
        cevap = "".join(durum["metin"]).strip() or str(sonuc.get("response") or "").strip()
        if teslim:
            cevap += "\n\nURETILEN GORSEL: " + ", ".join(teslim)
        if not basarili and not zaman_asti:
            yield MotorOlayi("hata", (stderr.strip() or durum_str or "agy turu basarisiz")[-600:],
                             {"sebep": "limit" if limit else "cikis"})
        yield MotorOlayi("bitti", cevap if basarili else "", {
            "basarili": basarili, "oturum_id": durum["oturum_id"],
            "model": durum["model"] or model, "cikis": surec.returncode,
            "sure_ms": round((time.monotonic() - basladi) * 1000, 1),
            "maliyet_usd": None,              # abonelik: dolar bildirmiyor (olculemedi)
            "jeton": durum["jeton"], "jeton_dokumu": durum["dokum"] or None,
            "arac_sayisi": durum["arac_sayisi"], "limit": limit,
            "zaman_asimi": zaman_asti, "limit_pencere": None,
            "uretilen_gorseller": teslim,
            "sebep": ("" if basarili else "zaman_asimi" if zaman_asti
                      else "limit" if limit else "cikis"),
        })

    def _satir_cevir(self, satir: str, durum: dict) -> list:
        """stream-json satiri -> olaylar (sinamada dogrudan cagrilir)."""
        try:
            j = json.loads(satir)
        except ValueError:
            return []
        if not isinstance(j, dict):
            return []
        olay = j.get("event")
        out = []
        if olay == "init":
            i = j.get("init") or {}
            durum["oturum_id"] = str(j.get("conversation_id") or i.get("conversation_id") or "")
            durum["model"] = str(i.get("model") or durum["model"])
            out.append(MotorOlayi("oturum", durum["model"], {
                "oturum_id": durum["oturum_id"], "model": durum["model"]}))
        elif olay == "step_update":
            su = j.get("step_update") or {}
            tur, hal = su.get("step_type"), su.get("state")
            u = su.get("usage") or {}
            if u and hal == "DONE":
                durum["jeton"] += int(u.get("total_tokens") or 0)
                dokum_ekle(durum["dokum"], {
                    "input_tokens": u.get("input_tokens"),
                    "output_tokens": int(u.get("output_tokens") or 0) + int(u.get("thinking_tokens") or 0),
                    "cache_read_input_tokens": u.get("cache_read_tokens")})
            if tur == "tool":
                info = su.get("tool_info") or {}
                ad = str(su.get("tool_name") or info.get("name") or "")
                param = info.get("parameters") or {}
                if ad == "call_mcp_tool":
                    ad = f"{param.get('ServerName', '')}.{param.get('ToolName', '')}"
                cagri = f"{su.get('conversation_id', '')}:{su.get('step_index')}"
                if hal == "ACTIVE":
                    durum["arac_sayisi"] += 1
                    out.append(MotorOlayi("arac", ad, {"ozet": _girdi_ozeti(ad, param),
                                                       "cagri_id": cagri}))
                elif hal in ("DONE", "ERROR", "FAILED", "CANCELED"):
                    hatali = hal != "DONE" or bool(su.get("error"))
                    out.append(MotorOlayi("arac_sonuc", f"{ad} {hal.lower()}",
                                          {"hatali": hatali, "cagri_id": cagri, "arac": ad}))
            elif tur == "agent_response" and su.get("text_delta"):
                parca = str(su["text_delta"])
                durum["metin"].append(parca)
                out.append(MotorOlayi("metin", parca))
        elif olay == "result":
            r = j.get("result") or {}
            durum["sonuc"] = r
            durum["oturum_id"] = durum["oturum_id"] or str(r.get("conversation_id") or "")
            for d in r.get("denied_actions") or []:
                out.append(MotorOlayi("izin", f"{d.get('display_name') or d.get('action')} reddedildi",
                                      {"hatali": True, "arac": d.get("action")}))
        return out

    @staticmethod
    def _gorselleri_al(ev: Path, kok: Path, baslangic: float, durum: dict) -> list:
        """Ajanin evinde BU TURDA olusan gorselleri projenin `.ofis/ekler/`ine kopyalar."""
        beyin = ev / ".gemini" / "antigravity-cli" / "brain"
        if not beyin.is_dir():
            return []
        # TESLIM DEFTERI: zaman damgasi tek basina yetmez (art arda iki tur
        # ayni saniyede biter; sinama yakaladi) -- teslim edilen gorsel bir
        # daha alinmaz.
        defter = ev / ".gemini" / "ofis_teslim.json"
        try:
            verilen = set(json.loads(defter.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            verilen = set()

        def _yeniler():
            try:
                return [p for p in beyin.rglob("*") if p.suffix.lower() in GORSEL_UZANTI
                        and p.is_file() and str(p) not in verilen
                        and p.stat().st_mtime >= baslangic - 1]
            except OSError:
                return []

        yeniler = _yeniler()
        # Alt ajan gorseli henuz bitirmemis olabilir: yanit "bekliyorum" diyorsa
        # kisa sure bekle (olculdu: tur, gorsel diske dusmeden kapandi).
        if not yeniler and "generate_image" in json.dumps(durum.get("sonuc") or {}) or (
                not yeniler and any("gorsel" in m.lower() or "image" in m.lower()
                                    for m in durum.get("metin") or [])):
            bitis = time.monotonic() + GORSEL_BEKLE_SN
            while time.monotonic() < bitis and not yeniler:
                time.sleep(2)
                yeniler = _yeniler()
        from ..yollar import EK_KLASORU
        hedef_klasor = kok / EK_KLASORU
        teslim = []
        for p in yeniler:
            try:
                hedef_klasor.mkdir(parents=True, exist_ok=True)
                hedef = hedef_klasor / p.name
                n = 1
                while hedef.exists():
                    hedef = hedef_klasor / f"{p.stem}-{n}{p.suffix}"
                    n += 1
                shutil.copy2(p, hedef)
                teslim.append(hedef.relative_to(kok).as_posix())
                verilen.add(str(p))
            except OSError:
                continue
        if teslim:
            try:
                defter.write_text(json.dumps(sorted(verilen)), encoding="utf-8")
            except OSError:
                pass
        return teslim
