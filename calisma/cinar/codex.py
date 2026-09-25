# -*- coding: utf-8 -*-
"""Codex CLI adaptoru: `codex exec` komutunu JSONL modunda kosturur.

Yapi `referans/claude_ornek.py`den alindi (Popen + okuyucu iplik + nabiz +
surec agacini kesme); degisen sey motorun SOZLUGUDUR, akisin sekli degil.
Cekirdek yine yalnizca `tip.py`deki olay turlerini gorur.

BAYRAKLAR TAHMIN DEGIL -- hepsi bu makinede `codex-cli 0.154.0` uzerinde
kosturularak ogrenildi:

* `codex --help` / `codex exec --help`: `exec` alt komutu "Run Codex
  non-interactively", `--json` "Print events to stdout as JSONL",
  `-C/--cd`, `-m/--model`, `-s/--sandbox {read-only, workspace-write,
  danger-full-access}`, `--add-dir`, `--skip-git-repo-check`,
  `-c key=value`, `--strict-config`.
* OLCULDU: `-a/--ask-for-approval` UST KOMUTTA var ama `codex exec`te
  YOKTUR -- `codex exec ... -a never` "error: unexpected argument '-a'
  found" ile dusuyor. Onay politikasi bu yuzden bayrakla degil, sandbox
  secimiyle kuruluyor; `exec` zaten etkilesimsizdir, soru sormaz.
* OLCULDU: `codex exec --json` akisinin gercek ilk satirlari
  (usage limit'e carpan bir tur):
      {"type":"thread.started","thread_id":"01a0b57a-..."}
      {"type":"turn.started"}
      {"type":"error","message":"You've hit your usage limit. ..."}
      {"type":"turn.failed","error":{"message":"You've hit your usage ..."}}
  `oturum` olayi bu yuzden `thread.started`tan doğar: kimligi biz
  veremiyoruz (claude'daki `--session-id`in karsiligi yok), motor
  bildiriyor. Devam eden tur `codex exec resume <UUID>` ile kosar.
* OLCULDU: `-c` ile verilen anahtarlar normalde DOGRULANMAZ (uydurma
  anahtar sessizce gecer), ama `--strict-config` ile dogrulanir:
      -c zirvana_anahtar=high  -> "Error loading config.toml: unknown
                                   configuration field `zirvana_anahtar`
                                   in -c/--config override"
      -c model_reasoning_effort=high      -> kabul
      -c mcp_servers.<ad>.command=python  -> kabul
  Bu yuzden komut HER ZAMAN `--strict-config` ile kurulur: efor ve MCP
  ayarlarini sessizce dusuren bir tur, "calisti" gorunup yanlis kosan
  turdur. Sessiz dusme, en pahali hata turudur.

TUR_KOS HER ZAMAN `bitti` ILE KAPANIR -- surec hic ayaga kalkamasa bile.
`tip.py` motorun kurulu olmamasini istisna sayar; burada gorevin acik
kurali uygulaniyor: akis basladiysa son olay `bitti`dir. Sebep pratiktir:
koltuk turu tek bir yerde (son olayda) kapatir; "bazen istisna, bazen
olay" iki ayri kapanis yolu demektir ve biri her zaman unutulur. Kurulum
bilgisi kaybolmaz, `bitti.ek["sebep"] == "motor_yok"` olarak durur.
Yalnizca GIRDI ihlali (bos brifing, olmayan klasor) istisna atar: bunlar
turun sonucu degil, turun hic baslayamamasidir.

WINDOWS: PATH'teki `codex` bir npm `.CMD` sarmalayicisidir (olculdu:
`shutil.which('codex')` -> `...\\npm\\codex.CMD`; yaninda `.exe` yok,
`bin/codex.js` var). `.CMD` cmd.exe uzerinden kosar ve satir sonu tasiyan
bir argumani KOMUT AYRACI sayip sonraki bayraklari sessizce dusurur --
bu yuzden brifing metni ARGUMAN OLARAK GECIRILMEZ: prompt yerine `-`
verilir ve metin stdin'den akitilir (`codex exec --help`: "If not
provided as an argument (or if `-` is used), instructions are read from
stdin"). `_arguman_dogrula` bu tuzagin bir daha kurulamamasi icin nobette
durur.
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
import uuid
from pathlib import Path
from typing import Iterator

#: Duz dosya olarak yuklenen sozlesme modulunun sys.modules'teki adi.
SOZLESME_MODULU = "ofis_motor_tip"


def _sozlesmeyi_yukle():
    """`referans/tip.py`yi TEK kopya olarak yukler.

    `referans` paketini import ETMIYORUZ: `__init__.py` henuz var olmayan
    kardes modulleri (`.claude`) cekiyor ve sozlesme dosyasi onlar yuzunden
    ulasilmaz kaliyor. Sozlesme tek dosyadir; dogrudan o dosya yuklenir.

    Modul `sys.modules`e KAYDEDILIR. Iki sebep de olculdu:

    1. Kaydedilmezse `@dataclass` isleyicisi kendi modulunu aramaya
       kalktiginda `sys.modules.get(...)` None doner ve yukleme
       "AttributeError: 'NoneType' object has no attribute '__dict__'"
       ile patlar -- yani sozlesme hic yuklenemez.
    2. Kaydedilmezse her cagiran AYRI bir kopya alir; iki ayri `Motor`
       sinifi olusur ve `issubclass(CodexMotoru, Motor)` yanlis yere
       False doner. Sozlesme testi boyle bir kopyada anlamsizdir.
    """
    var = sys.modules.get(SOZLESME_MODULU)
    if var is not None:
        return var
    import importlib.util as _iu
    yol = Path(__file__).resolve().parent / "referans" / "tip.py"
    belirtim = _iu.spec_from_file_location(SOZLESME_MODULU, yol)
    modul = _iu.module_from_spec(belirtim)
    sys.modules[SOZLESME_MODULU] = modul
    try:
        belirtim.loader.exec_module(modul)
    except Exception:
        del sys.modules[SOZLESME_MODULU]  # yarim modul birakma
        raise
    return modul


try:  # paket icinden de, duz dosya olarak da import edilebilsin
    from .tip import Motor, MotorOlayi, MotorHatasi, MotorYokHatasi
except ImportError:  # calisma klasorunde duz kullanim
    _tip = _sozlesmeyi_yukle()
    Motor, MotorOlayi = _tip.Motor, _tip.MotorOlayi
    MotorHatasi, MotorYokHatasi = _tip.MotorHatasi, _tip.MotorYokHatasi

_PENCERE_YOK = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_SON = object()

#: Turun ust siniri. Sonsuz bekleyen bir tur kilidi de sonsuza tutar.
VARSAYILAN_ZAMAN_ASIMI = 1800.0

#: Motor sessizken kac saniyede bir `nabiz` olayi akitilacak (kilit kirasi).
NABIZ_ARALIGI = 1.0

#: Bizim uc kademeli eforumuz -> Codex'in `model_reasoning_effort` degeri.
#: Alanin gecerliligi `--strict-config` ile dogrulandi (bkz. dosya basi).
EFOR_CEVRIMI = {"dusuk": "low", "normal": "medium", "yuksek": "high"}

#: Yazma yetkisi sandbox ile kurulur; `exec`te izin bayragi yoktur.
#: 'kafa' ajan (yazabilir=False) read-only kosar: kural brifingde rica
#: edilmez, SUREC duzeyinde uygulanir.
SANDBOX_YAZAR = "workspace-write"
SANDBOX_OKUR = "read-only"

#: Hesap limitini ele veren imzalar. Olculdu: gercek mesaj
#: "You've hit your usage limit. Upgrade to Pro ...".
LIMIT_IMZALARI = ("usage limit", "rate limit", "quota")

#: Codex'in `item` turlerinden bizim `arac` olayimiza cevrilenler.
#: Cekirdek Codex'in sozlugunu ogrenmesin diye cevrim burada durur.
ARAC_ADLARI = {
    "command_execution": "Bash",
    "file_change": "Edit",
    "mcp_tool_call": "MCP",
    "web_search": "WebSearch",
    "todo_list": "TodoWrite",
}

SISTEM_EKI_ORTAK = (
    "AgentOfis'te bir ajansin. Baglamin klasorundeki BRIFING.md dosyasidir; "
    "uzun bir iste savrulursan geri donup oku. "
    "Turkce yaz. "
    "Yalniz brifingdeki YAZMA ALANI icine yaz -- disina cikma; o alanlar "
    "baska ajanlara kilitli olabilir."
)

#: Codex'in `--append-system-prompt` karsiligi yoktur; sistem ekini metnin
#: basina BIZ koyariz. Kanit kanali tek olmali: MCP varsa arac, yoksa metin.
KANIT_MCP = (
    "\n\n"
    "ISI BITIRINCE KANITINI `ofis` araciyla ekle: `kanit_ekle`. "
    "Kanitsiz gorev kapanmaz. Kanit satirini METIN olarak YAZMA, araci CAGIR. "
    "Ciktiyi UYDURMA."
)
KANIT_METIN = (
    "\n\n"
    "ISI BITIRINCE KANIT SATIRI YAZMAK ZORUNDASIN. Kanitsiz gorev kapanmaz. "
    "Son mesajinin sonuna, her kanit icin ayri satir olarak, TAM OLARAK su "
    "bicimde yaz:"
    "\n\n"
    "KANIT terminal: <kosturdugun komut> -> <ciktinin ozeti>\n"
    "KANIT dosya: <yol> -> <ne yaptin>"
    "\n\n"
    "Ciktiyi UYDURMA: yalnizca gercekten kosturdugun komutun gercek "
    "ciktisini yaz."
)


class CodexMotoru(Motor):
    """`codex exec` komutunu tur basina bir surec olarak kosturur."""

    ad = "codex"
    #: Codex MCP istemcisidir: `codex mcp` sunucu yonetir, `-c mcp_servers.*`
    #: ile tur basina sunucu baglanir (ikisi de olculdu).
    mcp_konusur = True

    def __init__(self, *, calistirilabilir: str = "",
                 zaman_asimi: float = VARSAYILAN_ZAMAN_ASIMI) -> None:
        self.calistirilabilir = calistirilabilir or self._calistirilabilir_bul()
        self.zaman_asimi = zaman_asimi

    # -- kurulum -----------------------------------------------------------

    @staticmethod
    def _calistirilabilir_bul() -> str:
        """Codex ikilisini bulur; yoksa bos dize doner (musait_mi False)."""
        yol = os.environ.get("OFIS_CODEX_YOLU", "").strip()
        if yol and Path(yol).exists():
            return yol
        bulunan = shutil.which("codex") or ""
        if not bulunan:
            return ""
        # npm `.CMD`nin yaninda gercek bir ikili varsa onu yegle: sarmalayici
        # ne kadar az yolda durursa cmd.exe tuzagi da o kadar uzak kalir.
        if Path(bulunan).suffix.lower() in (".cmd", ".bat"):
            for aday in (Path(bulunan).with_suffix(".exe"),
                         Path(bulunan).parent / "node_modules" / "@openai"
                         / "codex" / "bin" / "codex.exe"):
                if aday.exists():
                    return str(aday)
        return bulunan

    def musait_mi(self) -> bool:
        return bool(self.calistirilabilir)

    def _arguman_dogrula(self, komut: list) -> None:
        """Satir sonlu argumani REDDEDER (`.CMD` sessiz bayrak dusurmesi).

        Brifing metni zaten stdin'den gectigi icin bu durum normalde
        olusmaz; kapi, bir gun birinin metni arguman yapmasini engellemek
        icin duruyor. Bozulma sessiz oldugundan uyari yetmez.
        """
        if Path(self.calistirilabilir).suffix.lower() not in (".cmd", ".bat"):
            return
        for arguman in komut[1:]:
            if "\n" in str(arguman) or "\r" in str(arguman):
                raise MotorHatasi(
                    "Satir sonu tasiyan arguman .CMD sarmalayicisindan "
                    "gecirilemez: cmd.exe onu komut ayraci sayar ve SONRAKI "
                    "BUTUN BAYRAKLARI sessizce dusurur. Metin stdin'den "
                    "verilmeli (prompt yerine '-')."
                )

    # -- tur ---------------------------------------------------------------

    def tur_kos(
        self,
        metin: str,
        *,
        klasor: str,
        oturum_id: str = "",
        model: str = "",
        efor: str = "normal",
        yazabilir: bool = True,
        ek_klasorler: tuple = (),
        butce_usd: float = None,
        zaman_asimi: float = None,
        mcp_yapilandirma: str = "",
        izinli_araclar: tuple = (),
    ) -> Iterator[MotorOlayi]:
        metin = str(metin or "").strip()
        if not metin:
            raise MotorHatasi("Bos brifing kosulamaz.")
        kok = Path(klasor).expanduser().resolve()
        if not kok.is_dir():
            raise MotorHatasi(f"Ajan calisma klasoru yok: {kok}")
        oturum = self._oturum_dogrula(oturum_id)
        devam = bool(oturum)
        sinir = float(zaman_asimi or self.zaman_asimi)

        istek = self._istek_metni(metin, mcp_yapilandirma)

        # Komut, akis BASLAMADAN once kurulur: `_komut_kur` ve
        # `_arguman_dogrula` sozlesme ihlalinde istisna atar (bozuk MCP
        # yapilandirmasi, satir sonlu arguman) -- bunlar turun sonucu degil,
        # turun hic baslayamamasidir. Akis bir kere basladiktan SONRA
        # istisna atilmaz, cunku o noktadan sonra tek cikis `bitti`dir.
        komut = []
        if self.calistirilabilir:
            komut = self._komut_kur(
                oturum, devam=devam, model=model, efor=efor,
                yazabilir=yazabilir, ek_klasorler=ek_klasorler,
                klasor=str(kok), mcp_yapilandirma=mcp_yapilandirma,
            )
            self._arguman_dogrula(komut)

        basladi = time.monotonic()
        durum = {
            "oturum_id": oturum, "model": model, "metin": [],
            "hatali": False, "hata_notu": "", "limit": False, "sonuc": "",
            "maliyet": 0.0, "jeton": 0, "arac_sayisi": 0,
        }
        zaman_asti = False
        cikis = -1
        surec = None
        okuyucu = hata_okuyucu = None
        hata_parcalari = []

        # Akis bir kere basladiysa mutlaka `bitti` ile kapanir: acilis da,
        # hata yolu da bu try'in icinde.
        try:
            yield MotorOlayi(
                "basladi", f"{self.ad} turu basladi",
                {"oturum_id": oturum, "devam": devam, "klasor": str(kok)},
            )

            if not komut:
                durum["hatali"] = True
                durum["hata_notu"] = "motor_yok"
                yield MotorOlayi(
                    "hata",
                    "codex CLI bulunamadi. Kurulu mu: 'codex --version'?",
                    {"sebep": "motor_yok"},
                )
            else:
                try:
                    surec = subprocess.Popen(
                        komut,
                        cwd=str(kok),
                        env=os.environ.copy(),
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding="utf-8",  # Windows konsolu cp1254; boru utf-8
                        errors="replace",
                        bufsize=1,
                        creationflags=_PENCERE_YOK,
                    )
                except OSError as exc:
                    durum["hatali"] = True
                    durum["hata_notu"] = "motor_yok"
                    yield MotorOlayi(
                        "hata", f"codex baslatilamadi: {exc}",
                        {"sebep": "motor_yok"},
                    )

            if surec is not None:
                yield from self._akisi_tuket(
                    surec, istek, durum, hata_parcalari, basladi, sinir,
                )
                zaman_asti = durum["zaman_asimi"]
                cikis = durum["cikis"]
        finally:
            # Cagiran dongudan cikarsa (GeneratorExit) da burasi koser:
            # surec sizmaz, durdurma kolu cagiranda kalir.
            if surec is not None:
                if surec.poll() is None:
                    self._surec_agacini_kes(surec)
                for boru in (surec.stdin, surec.stdout, surec.stderr):
                    if boru is None:
                        continue
                    try:
                        boru.close()
                    except Exception:
                        # Temizlikte atilan HER istisna `bitti` olayini
                        # yutar -- akis kapanmadan koparsa koltuk turu hic
                        # kapatamaz ve kilit ustunde kalir. Kapanmayan boru
                        # surec olunce zaten serbest kalir; kapanmayan tur
                        # kalmaz.
                        pass

        sure_ms = round((time.monotonic() - basladi) * 1000, 1)
        cevap = "".join(durum["metin"]).strip() or durum["sonuc"].strip()

        if zaman_asti:
            yield MotorOlayi(
                "hata", f"Tur {sinir:.0f} saniyede bitmedi, surec kesildi.",
                {"sebep": "zaman_asimi"},
            )
        elif durum["limit"]:
            yield MotorOlayi(
                "hata", "Hesap kullanim limitine ulasildi.", {"sebep": "limit"},
            )
        elif cikis != 0 or durum["hatali"]:
            ayrinti = (durum["sonuc"] or "".join(hata_parcalari)[-1200:]).strip()
            yield MotorOlayi(
                "hata", f"Tur basarisiz (cikis {cikis}): {ayrinti[:1200]}",
                {"sebep": durum["hata_notu"] or "cikis", "cikis": cikis},
            )

        basarili = (
            not zaman_asti and not durum["limit"]
            and cikis == 0 and not durum["hatali"]
        )
        yield MotorOlayi(
            "bitti",
            cevap if basarili else "",
            {
                "basarili": basarili,
                "oturum_id": durum["oturum_id"],
                "model": durum["model"] or model,
                "cikis": cikis,
                "sure_ms": sure_ms,
                "maliyet_usd": durum["maliyet"],
                "jeton": durum["jeton"],
                "arac_sayisi": durum["arac_sayisi"],
                "limit": durum["limit"],
                "zaman_asimi": zaman_asti,
                "sebep": durum["hata_notu"],
                "butce_usd": butce_usd,
                "izinli_araclar": tuple(izinli_araclar or ()),
            },
        )

    def _akisi_tuket(self, surec, istek: str, durum: dict, hata_parcalari: list,
                     basladi: float, sinir: float) -> Iterator[MotorOlayi]:
        """Surecin JSONL ciktisini olaylara cevirir; ISTISNA SIZDIRMAZ.

        Sonuc `durum` uzerinden doner (`zaman_asimi`, `cikis`): cagiran
        akisi `bitti` ile kapatacagi icin buradan istisna cikmamali --
        cikan her istisna, kapanmayan bir tur demektir.
        """
        satirlar = queue.Queue()
        okuyucu = threading.Thread(
            target=self._satir_oku, args=(surec.stdout, satirlar),
            name="ofis-codex-stdout", daemon=True,
        )
        hata_okuyucu = threading.Thread(
            target=self._hata_oku, args=(surec.stderr, hata_parcalari),
            name="ofis-codex-stderr", daemon=True,
        )
        okuyucu.start()
        hata_okuyucu.start()
        durum["zaman_asimi"] = False
        durum["cikis"] = -1
        try:
            if surec.stdin is not None:
                try:
                    surec.stdin.write(istek)
                    surec.stdin.close()
                except OSError as exc:  # surec erken oldu
                    durum["hatali"] = True
                    durum["hata_notu"] = f"stdin: {exc}"

            biter = time.monotonic() + sinir
            while True:
                kalan = biter - time.monotonic()
                if kalan <= 0:
                    durum["zaman_asimi"] = True
                    break
                try:
                    oge = satirlar.get(timeout=min(NABIZ_ARALIGI, kalan))
                except queue.Empty:
                    if surec.poll() is not None and not okuyucu.is_alive():
                        break
                    # Motor sessiz ama hayatta: kilidin kirasi tazelensin.
                    yield MotorOlayi(
                        "nabiz", "",
                        {"gecen_s": round(time.monotonic() - basladi, 1)},
                    )
                    continue
                if oge is _SON:
                    break
                try:
                    mesaj = json.loads(str(oge))
                except (json.JSONDecodeError, TypeError):
                    continue  # JSONL disi satir (banner, uyari) -- yok say
                if isinstance(mesaj, dict):
                    for olay in self._mesaji_cevir(mesaj, durum):
                        yield olay

            if durum["zaman_asimi"]:
                self._surec_agacini_kes(surec)
            else:
                try:
                    durum["cikis"] = surec.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._surec_agacini_kes(surec)
        except Exception as exc:  # surec katmaninda beklenmeyen her sey
            durum["hatali"] = True
            durum["hata_notu"] = durum["hata_notu"] or "surec"
            durum["sonuc"] = durum["sonuc"] or f"{type(exc).__name__}: {exc}"
            yield MotorOlayi("hata", f"Surec hatasi: {exc}"[:1200],
                             {"sebep": "surec"})
        finally:
            okuyucu.join(timeout=1)
            hata_okuyucu.join(timeout=1)

    # -- komut -------------------------------------------------------------

    def _istek_metni(self, metin: str, mcp_yapilandirma: str) -> str:
        """Sistem eki + brifing. Codex'te ayri bir sistem bayragi yok."""
        kanit = KANIT_MCP if mcp_yapilandirma else KANIT_METIN
        return SISTEM_EKI_ORTAK + kanit + "\n\n" + metin

    def _komut_kur(self, oturum: str, *, devam: bool, model: str, efor: str,
                   yazabilir: bool, ek_klasorler: tuple, klasor: str,
                   mcp_yapilandirma: str = "") -> list:
        sandbox = SANDBOX_YAZAR if yazabilir else SANDBOX_OKUR
        komut = [self.calistirilabilir, "exec"]
        if devam:
            # `codex exec resume <UUID> -`: kimlik motorun, bizim degil.
            komut += ["resume", oturum]
        komut += [
            "--json",             # olaylar JSONL olarak stdout'a
            "--strict-config",    # sessizce dusen ayar olmasin
            "--skip-git-repo-check",  # ajan klasoru git deposu olmak zorunda degil
        ]
        if devam:
            # OLCULDU: `codex exec resume` alt komutunda -C/--cd, -s/--sandbox
            # ve --add-dir YOKTUR -- `codex exec resume <uuid> -s read-only -`
            # "error: unexpected argument '-s' found" ile duser. Ayni ayarlar
            # `-c` ile kurulur; ikisi de `--strict-config` altinda dogrulandi.
            # Calisma klasoru zaten Popen'in `cwd`siyle verilir.
            komut += ["-c", f'sandbox_mode="{sandbox}"']
            if ek_klasorler:
                komut += ["-c", "sandbox_workspace_write.writable_roots="
                          + json.dumps([str(ek) for ek in ek_klasorler])]
        else:
            komut += ["-C", klasor, "-s", sandbox]
            for ek in ek_klasorler or ():
                komut += ["--add-dir", str(ek)]
        model = str(model or "").strip()
        if model:
            komut += ["-m", model]
        kademe = EFOR_CEVRIMI.get(str(efor or "").strip().lower(), "")
        if kademe:
            komut += ["-c", f'model_reasoning_effort="{kademe}"']
        for parca in self._mcp_ayarlari(mcp_yapilandirma):
            komut += ["-c", parca]
        # Brifing stdin'den gelir: '-' bunu acikca soyler ve satir sonlu
        # arguman hic olusmaz (bkz. .CMD tuzagi).
        komut.append("-")
        return komut

    @staticmethod
    def _mcp_ayarlari(mcp_yapilandirma: str) -> list:
        """`{"mcpServers": {...}}` JSON'unu `-c mcp_servers.*` satirlarina cevirir.

        Bos ise HICBIR sunucu baglanmaz. Varsayilanin "hepsi" olmamasi
        bilinclidir: her baglanti onlarca arac tanimi demektir ve ajanin
        baglami is baslamadan dolar.
        """
        ham = str(mcp_yapilandirma or "").strip()
        if not ham:
            return []
        if not ham.startswith("{"):
            yol = Path(ham).expanduser()
            if not yol.is_file():
                raise MotorHatasi(f"MCP yapilandirma dosyasi yok: {yol}")
            ham = yol.read_text(encoding="utf-8")
        try:
            veri = json.loads(ham)
        except json.JSONDecodeError as exc:
            raise MotorHatasi(f"MCP yapilandirmasi JSON degil: {exc}") from exc
        sunucular = veri.get("mcpServers") or veri.get("mcp_servers") or {}
        satirlar = []
        for ad, ayar in (sunucular or {}).items():
            if not isinstance(ayar, dict):
                continue
            if ayar.get("command"):
                satirlar.append(
                    f'mcp_servers.{ad}.command="{ayar["command"]}"')
            if ayar.get("args"):
                satirlar.append(
                    f"mcp_servers.{ad}.args={json.dumps(list(ayar['args']))}")
            if ayar.get("env"):
                satirlar.append(
                    f"mcp_servers.{ad}.env={json.dumps(dict(ayar['env']))}")
            if ayar.get("url"):
                satirlar.append(f'mcp_servers.{ad}.url="{ayar["url"]}"')
        return satirlar

    @staticmethod
    def _oturum_dogrula(oturum_id: str) -> str:
        """Bos ise BOS doner: kimligi Codex uretir, `thread.started` bildirir.

        claude'daki `--session-id`in karsiligi `codex exec`te yok; kimlik
        uydurup `resume`a vermek olmayan bir oturumu surdurmeye calismaktir.
        """
        if not oturum_id:
            return ""
        try:
            return str(uuid.UUID(str(oturum_id)))
        except ValueError as exc:
            raise MotorHatasi(
                f"Oturum kimligi gecerli bir UUID degil: {oturum_id!r}"
            ) from exc

    # -- akis cevrimi ------------------------------------------------------

    def _mesaji_cevir(self, mesaj: dict, durum: dict) -> list:
        """Bir JSONL satirini sifir ya da daha cok MotorOlayi'na cevirir.

        Codex'in sozlugu burada biter; disari yalnizca OLAY_TURLERI cikar.
        Tanimadigi satiri YOK SAYAR: CLI yeni bir olay turu eklediginde tur
        patlamasin, bilinmeyen sey sessizce gecsin.
        """
        olaylar = []
        tur = str(mesaj.get("type") or "")

        if tur == "thread.started":
            durum["oturum_id"] = str(mesaj.get("thread_id") or "")
            olaylar.append(MotorOlayi(
                "oturum", durum["model"],
                {"oturum_id": durum["oturum_id"], "model": durum["model"]},
            ))
            return olaylar

        if tur.startswith("item."):
            return self._ogeyi_cevir(mesaj, durum, tamamlandi=tur == "item.completed")

        if tur == "turn.completed":
            kullanim = mesaj.get("usage") or {}
            durum["jeton"] = int(
                (kullanim.get("input_tokens") or 0)
                + (kullanim.get("output_tokens") or 0)
                + (kullanim.get("cached_input_tokens") or 0)
            )
            return olaylar

        if tur in ("error", "turn.failed"):
            hata = mesaj.get("error") or {}
            ileti = str(mesaj.get("message") or hata.get("message") or "")
            durum["hatali"] = True
            durum["sonuc"] = ileti or durum["sonuc"]
            dusuk = ileti.lower()
            if any(imza in dusuk for imza in LIMIT_IMZALARI):
                durum["limit"] = True
                durum["hata_notu"] = "limit"
                olaylar.append(MotorOlayi("limit", ileti[:300], {"ham": ileti[:1200]}))
            else:
                durum["hata_notu"] = durum["hata_notu"] or "motor"
                olaylar.append(MotorOlayi("hata", ileti[:1200], {"sebep": "motor"}))
        return olaylar

    def _ogeyi_cevir(self, mesaj: dict, durum: dict, *, tamamlandi: bool) -> list:
        """`item.*` satirlarini olaya cevirir.

        Metin YALNIZCA `item.completed`ta akitilir: `item.started/updated`
        ayni ogenin buyuyen halini tasir, ikisini birden yayinlamak ayni
        cumleyi iki kez gorev gecmisine yazar. Canliligi `nabiz` saglar.
        """
        olaylar = []
        oge = mesaj.get("item")
        if not isinstance(oge, dict):
            return olaylar
        cins = str(oge.get("item_type") or oge.get("type") or "")

        if cins == "agent_message":
            if tamamlandi:
                parca = str(oge.get("text") or "")
                durum["metin"].append(parca)
                olaylar.append(MotorOlayi("metin", parca))
            return olaylar

        if cins == "reasoning":
            if tamamlandi:
                olaylar.append(MotorOlayi("dusunce", str(oge.get("text") or "")))
            return olaylar

        if cins in ARAC_ADLARI:
            ad = ARAC_ADLARI[cins]
            if cins == "mcp_tool_call":
                ad = f"{oge.get('server', '')}.{oge.get('tool', '')}".strip(".") or ad
            if not tamamlandi:
                durum["arac_sayisi"] += 1
                olaylar.append(MotorOlayi(
                    "arac", ad, {"ozet": self._oge_ozeti(oge),
                                 "cagri_id": str(oge.get("id") or "")},
                ))
                return olaylar
            cikis = oge.get("exit_code")
            hatali = bool(oge.get("error")) or (cikis not in (None, 0))
            ozet = self._oge_ozeti(oge, sonuc=True)
            # Reddedilen izin ayri bir olaydir: brifingde yazma alani yanlis
            # verilmisse bu satir onu ele verir.
            izin_reddi = hatali and (
                "permission" in ozet.lower() or "sandbox" in ozet.lower()
                or "izin" in ozet.lower()
            )
            olaylar.append(MotorOlayi(
                "izin" if izin_reddi else "arac_sonuc", ozet,
                {"hatali": hatali, "cagri_id": str(oge.get("id") or ""),
                 "cikis": cikis},
            ))
        return olaylar

    @staticmethod
    def _oge_ozeti(oge: dict, *, sonuc: bool = False) -> str:
        """Ogenin tek satirlik ozeti -- panel pano basligi icin.

        Tam govde saklanmaz: olay tablosu canli akistir, arsiv degil.
        """
        anahtarlar = (
            ("aggregated_output", "output", "result", "status")
            if sonuc else
            ("command", "query", "tool", "path", "changes", "status")
        )
        for anahtar in anahtarlar:
            deger = oge.get(anahtar)
            if deger:
                if isinstance(deger, (dict, list)):
                    deger = json.dumps(deger, ensure_ascii=False)
                return str(deger).strip()[:300]
        return ""

    # -- surec -------------------------------------------------------------

    @staticmethod
    def _satir_oku(boru, hedef) -> None:
        try:
            if boru is not None:
                for satir in boru:
                    hedef.put(satir)
        except (OSError, ValueError):
            pass  # sahip, iptal ya da zaman asiminda boruyu kapatmis olabilir
        finally:
            hedef.put(_SON)

    @staticmethod
    def _hata_oku(boru, hedef: list) -> None:
        if boru is None:
            return
        try:
            for satir in boru:
                hedef.append(satir)
                if sum(len(p) for p in hedef) > 8000:
                    del hedef[: len(hedef) // 2]  # son sozler daha degerli
        except (OSError, ValueError):
            pass

    @staticmethod
    def _surec_agacini_kes(surec) -> None:
        """Sureci ve BUTUN cocuklarini sonlandirir.

        PATH'teki `codex` npm `.CMD` sarmalayicisidir ve altinda node +
        yerel ikili kosar; yalniz dogrudan cocugu sonlandirmak altakileri
        oksuz birakir ve her turdan sonra bir surec sizar.
        """
        try:
            import psutil
            cocuklar = psutil.Process(surec.pid).children(recursive=True)
        except Exception:
            cocuklar = []
        for kurban in cocuklar:
            try:
                kurban.terminate()
            except Exception:
                pass
        if surec.poll() is None:
            try:
                surec.terminate()
            except OSError:
                pass
        try:
            surec.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                surec.kill()
            except OSError:
                pass
        for kurban in cocuklar:
            try:
                if kurban.is_running():
                    kurban.kill()
            except Exception:
                pass
