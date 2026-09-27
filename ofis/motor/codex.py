# -*- coding: utf-8 -*-
"""Codex CLI adaptoru -- iki kip: `app-server` (VARSAYILAN) ve `exec`.

APP-SERVER KIPI (26.09.2026, PLAN F0 A2 -- olculdu, CLAUDE.md "A2"):
`codex app-server` stdio uzerinden JSON-RPC konusur. `exec` tek yonludur:
tur basladiktan sonra ne onay ne mesaj gecebilir. App-server ikisini de
verir ve ikisi de gercek turla olculdu:

* HER KOMUT ISTEMCIYE SORULUR (`approvalPolicy: untrusted`) ->
  `item/commandExecution/requestApproval`, `mcpServer/elicitation/request`.
  Adaptor soruyu KENDISI cevaplamaz: ofisin TEK kapisina -- claude'un
  `--permission-prompt-tool`u ile AYNI arac, `izin_sor` -- codex'in KENDI
  MCP baglantisi uzerinden (`mcpServer/tool/call`) sorar (olculdu: onay
  beklerken cagri 0,1-0,2 sn'de dondu). Karar tek yerde kalir ve motor
  katmani ofisin ic modullerini hic bilmez.
* Reddedilen eylemin SEBEBI ajana `turn/steer` ile iletilir: `decline`
  modele yalniz "rejected by user" der; ofisin "SIMDI DUR, soyle yap"
  mesaji olmadan ajan ayni seyi baska bicimde tekrar dener.
* Limit ve oturum hatalari YAPISAL gelir (`codexErrorInfo`:
  `usageLimitExceeded`, `unauthorized`) -- metin taramasina yedek olarak.
* Hesabin kullanim penceresi tur SURERKEN bildirilir
  (`account/rateLimits/updated`); oturum kaydini taramaya gerek kalmaz.

`exec` KIPI korunur ve ACIKCA secilir (`kip="exec"` ya da
`OFIS_CODEX_KIP=exec`): app-server semasi `[experimental]` etiketli ve bir
CLI surumunde bozulabilir (PLAN §8 kacis yolu). Sessiz geri dusme YOK --
dusmek, onay kapisinin sessizce kalkmasi olurdu. Gorsel uretimi `exec`te
kalir: o yol gercek turla olculdu, app-server'da olculmedi.

Asagidaki notlar `exec` kipinin olcumleridir.

Codex CLI adaptoru: `codex exec` komutunu JSONL modunda kosturur.

Yapi `claude.py`den alindi (Popen + okuyucu iplik + nabiz +
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
from ..yollar import OFIS_EVI
from .. import motor_saglik
from typing import Iterator

#: Duz dosya olarak yuklenen sozlesme modulunun sys.modules'teki adi.
# Sozlesme dogrudan paketten gelir. Bu dosya `calisma/` altinda duz bir
# dosya olarak yazildi ve orada `referans/tip.py`yi elle yukleyen bir
# yedek yol tasiyordu; pakete tasinirken o yol KALDIRILDI cunku pakette
# `referans/` diye bir klasor yok -- var olmayan bir yolu isaret eden kod,
# sonraki okuyucuyu yanlis yere gonderir.
#
# Not: o yedek yolun cozdugu sorun gercekti ve kayda degerdir --
# sozlesme iki kez yuklenirse IKI AYRI `Motor` sinifi olusur ve
# `issubclass(CodexMotoru, Motor)` yanlis yere False doner. Paket icinde
# tek kopya garanti oldugu icin sorun ortadan kalkar.
from .tip import (ortam_hazirla, limit_penceresi, PENCERE_DAKIKA_ADI, Motor,
                  MotorOlayi, MotorHatasi, MotorYokHatasi, SurecKafesi)

_PENCERE_YOK = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_SON = object()

#: Turun ust siniri. Sonsuz bekleyen bir tur kilidi de sonsuza tutar.
VARSAYILAN_ZAMAN_ASIMI = 1800.0

#: Motor sessizken kac saniyede bir `nabiz` olayi akitilacak (kilit kirasi).
NABIZ_ARALIGI = 1.0

#: Bizim uc kademeli eforumuz -> Codex'in `model_reasoning_effort` degeri.
#: Alanin gecerliligi `--strict-config` ile dogrulandi (bkz. dosya basi).
EFOR_CEVRIMI = {"dusuk": "low", "normal": "medium", "yuksek": "high",
                "cok_yuksek": "xhigh"}   # `max` BILEREK YOK (kullanici karari)

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

#: Iki kip; varsayilan app-server. Bilinmeyen kip REDDEDILIR (sessizce
#: varsayilana dusmek, istenen kipin hic kullanilmamasi olurdu).
KIPLER = ("app-server", "exec")
VARSAYILAN_KIP = "app-server"

#: app-server `ThreadItem` turlerinden bizim `arac` olayimiza (semadan).
APP_ARAC_ADLARI = {
    "commandExecution": "Bash",
    "fileChange": "Edit",
    "mcpToolCall": "MCP",
    "dynamicToolCall": "Arac",
    "webSearch": "WebSearch",
    "imageGeneration": "Gorsel",
    "collabAgentToolCall": "AltAjan",
}

#: Yapisal hata kodlari (`codexErrorInfo`, sema). Metin imzalarinin YEDEGI
#: degil ONCULU: kod varsa ona bakilir, yoksa metin taranir.
LIMIT_KODLARI = ("usageLimitExceeded", "rateLimitExceeded")
OTURUM_KODLARI = ("unauthorized",)

#: Adaptorun TANIMADIGI sunucu istegine verilen JSON-RPC hatasi. Her istek
#: CEVAPLANIR: cevapsiz istegin turu ne kadar bekletecegi olculmedi ve
#: olculmemis bir bekleme kilidi rehin tutabilir. (Olculen: yanlis BICIMDE
#: cevap -- `action` alani eksik -- sunucuda "failed to deserialize" ile
#: dustu ve cagri REDDEDILMIS sayildi; tur surdu.)
DESTEKSIZ_ISTEK_KODU = -32601

#: Tur, bagli MCP sunuculari HAZIR olmadan BASLATILMAZ.
#:
#: OLCULDU (26.09.2026): adaptor `turn/start`i `thread/start`in hemen
#: ardindan gonderiyordu; ofis MCP'si o an hala "starting" durumundaydi ve
#: ajan *"`ofis` araci bu oturumda kullanilabilir araclar arasinda yok"*
#: dedi -- kanit ekleyemedi, is hic kapanamazdi. Ayni tur, sunucular
#: "ready" olana dek beklenince (0,3-0,7 sn) kaniti DUSURDU (iki kosuda iki).
#: Sistem saglikli gorunur, yanlis calisir: tipik bir yaris.
#:
#: Ust sinir: sunucu hic cevap vermezse tur sonsuza kadar bekletilmez;
#: sure dolunca tur baslar ve bu GORUNUR bir olay olur.
MCP_HAZIR_SN = 30.0

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


#: Oturumun SUNUCU TARAFINDA oldugunu soyleyen imzalar (olculdu, 25.09.2026):
#:   stream: "workspace routing discovery unauthorized (401)"
#:   stderr: "auth error code: token_revoked" · "refresh_token_invalidated"
#:           "Your session has ended. Please log in again."
OTURUM_OLU_IMZALARI = ("token_revoked", "refresh_token_invalidated",
                       "session has ended", "unauthorized (401)",
                       "401 unauthorized")

#: Olu oturum defteri. 27.09.2026'dan beri TEK motor saglik hafizasi
#: (`ofis/motor_saglik.py`): Claude'a ikinci bir kopya yazilmadi, bu
#: hafiza ortaklastirildi. Ad korunuyor -- sinamalar onu gecici bir
#: dosyaya yonlendiriyor.
OTURUM_DEFTERI = motor_saglik.DEFTER


def _ev_anahtari(ev: str) -> str:
    return str(Path(ev).expanduser().resolve()).lower()


def _parmak_izi(ev: str) -> str:
    return motor_saglik.parmak_izi_dosya(Path(ev).expanduser() / "auth.json")


def oturum_olu_yaz(ev: str, kategori: str = "token_revoked") -> None:
    """Bu evin oturumunun sunucuda OLDUGUNU hatirlar.

    OLCULDU (25.09.2026): ofisin codex evinde `auth.json` DURUYORDU ama
    sunucu her istege `401 token_revoked` donuyordu. `musait_mi` yalniz
    dosyanin varligina baktigi icin codex "HAZIR" gorunuyordu; `cinar`
    tek satir is yapamiyordu ve bunu ofiste hicbir sey soylemiyordu.
    *Anahtar var != uretebiliyor* dersinin KIMLIK hali.

    Olcmek (bos bir tur kosmak) kotadan yer; o yuzden tahmin etmiyoruz,
    HATIRLIYORUZ: gercek bir tur 401 aldiginda kaydedilir. Kayit
    `auth.json`in O ANKI damgasini tutar; kullanici yeniden giris yapinca
    kayit KENDILIGINDEN gecersiz olur.
    """
    motor_saglik.olu_yaz("codex", _ev_anahtari(ev), _parmak_izi(ev), kategori,
                         defter=OTURUM_DEFTERI)


def oturum_olu_mu(ev: str) -> bool:
    """Son gercek turda 401 alinmis VE o zamandan beri giris yapilmamis mi."""
    return motor_saglik.olu_kaydi("codex", _ev_anahtari(ev), _parmak_izi(ev),
                                  defter=OTURUM_DEFTERI) is not None


def oturum_olu_metni(ev: str) -> str:
    return ("codex oturumu KAPANMIS (sunucu 401 token_revoked donduruyor; "
            "auth.json duruyor ama gecersiz). Yeniden giris -- PowerShell: "
            f"$env:CODEX_HOME=\"{ev}\"; codex login   "
            "(--device-auth KULLANMA). Giris yapilinca bu kayit "
            "kendiliginden duser.")


def hesap_kimligi(ev: str) -> dict:
    """Bir CODEX_HOME dizininde KIM girisli -- olcer, tahmin etmez.

    Once `kabuk.py`de yasiyordu. Cekirdek (`hesap.kullanilabilir_mi`)
    da bunu sormak zorunda kalinca iki yol vardi: kopyalamak ya da
    tasimak. Kopya bu projede alti kez odendi (biri duzeltilir, oteki
    unutulur); `anahtar_oku` da ayni sebeple `gizli.py`ye tasinmisti.
    Codex evinin bicimini bilen yer codex adaptorudur -- soru burada.

    JETON BASILMAZ. `id_token` bir JWT'dir; ortadaki bolumu base64 ve
    icinde e-posta ile plan var. Yalnizca o ikisi okunur -- imza ve
    jetonlar hic ellenmez, hic yazilmaz.
    """
    import base64

    yol = Path(ev).expanduser() / "auth.json"
    if not yol.exists():
        return {"girisli": False, "yol": str(yol)}
    try:
        d = json.loads(yol.read_text(encoding="utf-8"))
        jeton = ((d.get("tokens") or {}).get("id_token") or "")
        parca = jeton.split(".")
        if len(parca) < 2:
            return {"girisli": True, "yol": str(yol), "eposta": "(okunamadi)"}
        govde = parca[1].replace("-", "+").replace("_", "/")
        govde += "=" * (-len(govde) % 4)
        ic = json.loads(base64.b64decode(govde).decode("utf-8"))
        yetki = ic.get("https://api.openai.com/auth") or {}
        return {"girisli": True, "yol": str(yol),
                "eposta": ic.get("email") or "(yok)",
                "plan": yetki.get("chatgpt_plan_type") or "(yok)"}
    except Exception as exc:
        return {"girisli": True, "yol": str(yol), "eposta": f"(okunamadi: {exc})"}


def codex_pencereleri(ev: str, oturum_id: str) -> dict | None:
    """Turun oturum kaydindan hesabin kullanim pencereleri.

    OLCULDU (23.09.2026): `codex exec --json` stdout'u limit TASIMIYOR
    (`turn.completed` yalniz `usage` verir). Codex ayni bilgiyi
    `<CODEX_HOME>/sessions/**/rollout-*-<thread_id>.jsonl` icine
    `token_count` olayiyla yaziyor:

        "rate_limits": {"primary": {"used_percent": 6.0,
                                    "window_minutes": 300,
                                    "resets_at": 1790130903},
                        "secondary": {... "window_minutes": 10080 ...},
                        "plan_type": "plus", ...}

    Yalniz BU turun oturumu okunur (kimlik `thread.started`tan) ve
    yalniz o hesabin evinde -- baska bir hesabin kaydini bu hesabin
    olcumu sanmak, yanlis gosteren bir gostergedir. Okunamazsa `None`:
    tur bundan olmez, olcum "olculemedi" kalir.
    """
    if not oturum_id or not ev:
        return None
    try:
        adaylar = sorted(Path(ev, "sessions").rglob(f"rollout-*{oturum_id}.jsonl"),
                         key=lambda p: p.stat().st_mtime)
    except OSError:
        return None
    if not adaylar:
        return None
    son = None
    try:
        with open(adaylar[-1], encoding="utf-8", errors="replace") as f:
            for satir in f:
                if '"rate_limits"' not in satir:
                    continue
                try:
                    rl = (json.loads(satir).get("payload") or {}).get("rate_limits")
                except ValueError:
                    continue
                if isinstance(rl, dict):
                    son = rl
    except OSError:
        return None
    if not son:
        return None
    pencereler = {}
    for anahtar in ("primary", "secondary"):
        p = son.get(anahtar)
        if not isinstance(p, dict) or not isinstance(p.get("used_percent"), (int, float)):
            continue
        dk = p.get("window_minutes")
        pencereler[PENCERE_DAKIKA_ADI.get(dk, f"{dk}dk")] = {
            "kullanim": p["used_percent"] / 100.0, "yenilenme": p.get("resets_at")}
    return limit_penceresi(pencereler, kaynak="codex oturum kaydi (token_count)",
                           hal=str(son.get("rate_limit_reached_type") or ""),
                           plan=str(son.get("plan_type") or ""))


class CodexMotoru(Motor):
    """`codex exec` komutunu tur basina bir surec olarak kosturur."""

    ad = "codex"
    # Codex CLI'da tur basina harcama tavani YOK (`codex exec --help`).
    # Bu yuzden butce verilirse sessizce yok sayilmaz, reddedilir.
    butce_destegi = False
    #: MCP KONUSMAZ -- ve bu, ilk GERCEK codex turunda olculdu (21.09.2026).
    #:
    #: Burada uzun sure `True` yaziyordu ve dogru GORUNUYORDU: `codex mcp`
    #: sunucu yonetiyor, `-c mcp_servers.*` kabul ediliyor, sunucu ayaga
    #: kalkiyor, ajan araci CAGIRIYOR. Zincirin her halkasi calisiyor --
    #: sonuncusu haric:
    #:
    #:   {"type":"mcp_tool_call","server":"ofis","tool":"durum",
    #:    "error":{"message":"MCP tool call requires approval,
    #:              but approval policy is never"},"status":"failed"}
    #:
    #: `codex exec` ETKILESIMSIZDIR: onay verecek kimse yok. O gun ucu
    #: de olculdu -- `approval_policy` "on-failure"/"on-request" yine
    #: onay istiyor; guvenilir ilan edecek anahtar YOK (`trust_level`,
    #: `trusted`, `auto_approve`, `approval`, `tool_approval` -> hepsi
    #: "unknown configuration field").
    #:
    #: BU BOLUM BAYATLADI (22.09.2026) -- `--approve-for-me` VAR:
    #:   "Route approval requests through automatic review using the
    #:    workspace-write sandbox"
    #: Yani onay duvari SANDBOX KALKMADAN asiliyor. Gercek turla
    #: olculdu: ajan `kanit_ekle`yi cagirdi ve kanit tahtaya DUSTU.
    #: Tek sart: bayrak kendi sandbox'ini kurdugu icin bizim `-s`
    #: bayragimiz dusmeli ("cannot be used with --sandbox").
    #:
    #: Once "limit doluydu belki" diye dusunuldu; olculdu ve DEGILDI --
    #: limit yenilendikten sonra da ayni onay hatasi geldi. Duvari asan
    #: sey eksik bir BAYRAKTI. *Cikarim yapma, olc.*
    #:
    #: (Tarihsel: yetenek bir sure DURUSTCE False bildirildi, koltuk
    #: METIN KOPRUSUNU secti -- yani codex ajani kanitini yine ekleyebilir.
    #: `True` birakmak, kanit eklemenin HICBIR yolu olmamasi demekti:
    #: koltuk MCP kanalini secer, metin koprusunu kapatir ve her MCP
    #: cagrisi reddedilir. Is yapilir, defter bos kalir.
    #:
    #: `-c mcp_servers.*` uretimi KALDIRILMADI: yarin codex bir guven
    #: anahtari eklerse tek satir (`True`) geri cevrilir.
    #:
    #: DERS: `dogrula_teslim.py` linti "parametre kullanildi mi" diye
    #: sorar ve burada GECERDI -- yapilandirma gercekten geciriliyordu.
    #: Kablonun bagli olmasi, icinden akim gectigi anlamina gelmez;
    #: bunu yalnizca gercek tur soyler.
    mcp_konusur = True

    #: SINIF duzeyinde KAPALI: yetenek kipe baglidir ve ornekte kurulur.
    #: Sinifa bakan biri (ornek kurmadan) "kanca var" sanmasin -- yanlis
    #: yonde yanilmanin bedeli kapisiz bir tur olurdu.
    izin_kancasi = False

    def __init__(self, *, calistirilabilir: str = "",
                 zaman_asimi: float = VARSAYILAN_ZAMAN_ASIMI,
                 kip: str = "") -> None:
        self.calistirilabilir = calistirilabilir or self._calistirilabilir_bul()
        self.zaman_asimi = zaman_asimi
        kip = str(kip or os.environ.get("OFIS_CODEX_KIP", "")
                  or VARSAYILAN_KIP).strip().lower()
        if kip not in KIPLER:
            raise MotorHatasi(
                f"Bilinmeyen codex kipi: {kip!r}. Secenekler: {', '.join(KIPLER)}")
        self.kip = kip
        # Onay kancasi yalniz app-server'da VAR (olculdu, A2/A3).
        self.izin_kancasi = kip == "app-server"
        # Tur ici not + durdurma da yalniz app-server'da: `turn/steer` ve
        # `turn/interrupt` (olculdu, A2: 2/2 ve 1/1). `exec` tek yonludur.
        self.tur_ici_mesaj = kip == "app-server"

    # -- kurulum -----------------------------------------------------------

    @staticmethod
    def _ev_bul() -> str:
        """Codex'in kimlik/ayar dizini -- OFISE AYRI BIR HESAP.

        OLCULDU (19.09.2026): `codex login status` varsayilan `~/.codex`
        dizinini okur ve orada kullanicinin BASKA bir isine bagli hesabi
        vardi (trader bot). Ofis oraya dokunursa iki sistem ayni
        aboneligi paylasir: limit birinde dolunca oteki de durur, ve
        `codex logout` biri icin yapilinca otekini de dusurur.

        `CODEX_HOME` bunu ayirir -- olculdu:

            CODEX_HOME=~/.codex-ofis  -> "Not logged in"   (temiz)
            varsayilan ~/.codex        -> "Logged in..."    (dokunulmadi)

        Ofis KENDI evini kullanir: `~/.agentofis/codex`. Kullanicinin
        oteki hesabi gorunmez ve etkilenmez.

        `OFIS_CODEX_HOME` ile degistirilebilir. Bos birakilirsa ve ofis
        evi henuz kurulmamissa VARSAYILANA DUSMEYIZ: dusmek, sessizce
        yanlis hesabi kullanmak olurdu -- ve fatura baska bir ise cikar.
        """
        ozel = os.environ.get("OFIS_CODEX_HOME", "").strip()
        if ozel:
            return str(Path(ozel).expanduser())
        return str(OFIS_EVI / "codex")

    @staticmethod
    def _evi_hazirla(ev: str, klasor: str) -> None:
        """Ofis codex evinin `config.toml`unu KOSMADAN ONCE tamamlar.

        OLCULDU (21.09.2026), ilk gercek codex turlarinda: ajan
        `-s workspace-write` ile kostugu halde her denemede *"salt-okunur
        ortam"* diyordu ve TEK BIR dosya bile yazamadi. Ayni komut elle
        kosturuldugunda YAZIYORDU -- tek fark `CODEX_HOME`du.

        Sebep: ofis KENDI codex evini kullaniyor (kullanicinin oteki
        hesabina dokunmamak icin, dogru bir karar) ama o ev BOSTU --
        icinde `config.toml` yoktu. Varsayilan evde ise iki sey vardi ve
        ikisi de gerekiyor:

          [windows] sandbox = "elevated"   <- Windows'ta yazmayi acan sey
          [projects.'<klasor>'] trust_level = "trusted"

        Ikisi tek tek olculdu: yalniz `trust_level` yetmedi (yine
        salt-okunur), `[windows] sandbox` eklenince dosya YAZILDI.

        Bu, bu projenin avladigi sinifin en saf orneklerinden:
        `musait_motorlar()` codex'i "kurulu" gosteriyordu, adaptorun 37
        sozlesme testi geciyordu, tur `basarili=True` donuyordu -- ve
        ajan hicbir sey yazamiyordu. *Sistem saglikli gorunurken yanlis
        calisiyor.*

        VAR OLAN DOSYA EZILMEZ: yalnizca eksik olan bolum eklenir.
        Kullanicinin kendi elle koydugu ayari silmek, sessizce ayar
        degistirmek olurdu.

        Yazamamak turu DURDURMAZ: bu bir kolaylik, bir kapi degil. Ayni
        kurali kota ve baglayici hafizasinda da uyguluyoruz.
        """
        try:
            evp = Path(ev)
            evp.mkdir(parents=True, exist_ok=True)
            cfg = evp / "config.toml"
            metin = cfg.read_text(encoding="utf-8") if cfg.is_file() else ""
            ekler = []
            # Windows sandbox: yalnizca Windows'ta anlamli.
            if os.name == "nt" and "[windows]" not in metin:
                ekler.append('[windows]\nsandbox = "elevated"\n')
            # Proje guveni: codex guvenilmeyen klasorde salt-okunur kosar.
            # TOML LITERAL dizgi (tek tirnak) -- ters bolu kacirilmaz.
            anahtar = str(Path(klasor).resolve()).lower()
            if f"[projects.'{anahtar}']" not in metin:
                ekler.append(f"[projects.'{anahtar}']\ntrust_level = \"trusted\"\n")
            if ekler:
                gecici = cfg.with_suffix(".tmp")
                gecici.write_text(
                    (metin.rstrip("\n") + "\n\n" if metin.strip() else "")
                    + "\n".join(ekler), encoding="utf-8")
                gecici.replace(cfg)        # yerinde yazma ATOMIK olmali
        except OSError:
            pass

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
        """CLI kurulu MI ve OFIS HESABI girisli mi.

        Ikisi ayri sart. CLI kurulu ama giris yoksa tur baslar ve
        "not logged in" ile duser: jeton yakmaz ama zaman yakar ve
        orkestra bunu "ilerleme yok" diye okur -- yani sebep gorunmez.
        Musaitligi ONCEDEN olcmek, sebebi gorunur kilar.

        Giris kontrolu OFISIN KENDI evinde yapilir (`_ev_bul`), varsayilan
        `~/.codex`te degil: kullanicinin oteki hesabi baska bir ise bagli
        olabilir ve onun girisli olmasi BIZIM girisli oldugumuz anlamina
        gelmez.
        """
        return bool(self.calistirilabilir) and not self.durum_notu()

    def durum_notu(self) -> str:
        """Musait DEGILSE sebebi + caresi; musaitse bos (tek desen, E16)."""
        if not self.calistirilabilir:
            return "codex CLI kurulu degil."
        ev = self._ev_bul()
        if not (Path(ev) / "auth.json").exists():
            return (f"codex'e bu evde giris YOK: {ev} -- PowerShell: "
                    f"$env:CODEX_HOME=\"{ev}\"; codex login "
                    "(--device-auth KULLANMA).")
        # Dosyanin varligi YETMEZ (25.09.2026): sunucuda olmus bir oturum
        # dosyayi silmez. Son gercek tur 401 aldiysa ve o zamandan beri
        # giris yapilmadiysa musait DEGIL.
        if oturum_olu_mu(ev):
            return oturum_olu_metni(ev)
        return ""

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
        ek_ortam: dict = None,
        izin_araci: str = "",
        kanal=None,
    ) -> Iterator[MotorOlayi]:
        # TUR ICI KANAL tasinamiyorsa REDDEDILIR: sessizce yok saysaydik
        # insan notunun ulastigini sanirdi. Koltuk bu motora zaten vermez.
        if kanal is not None and not self.tur_ici_mesaj:
            raise MotorHatasi(
                f"{self.ad} ({self.kip} kipi) tur surerken not alamiyor; "
                "not bir sonraki turun basinda iletilmeli. Tasiyan kip: app-server.")
        # IZIN KANCASI UYGULANAMIYOR -> KAPALI KALARAK REDDEDILIR.
        #
        # Sessizce yok saysaydik cagiran, riskli her cagrinin ofise
        # soruldugunu SANIRDI -- oysa hicbiri sorulmazdi. Para ve yayin
        # kontrolleri bu projede her zaman fail-closed olur (codex'in
        # butce tavanini reddetmesiyle ayni ilke).
        if izin_araci and not self.izin_kancasi:
            raise MotorHatasi(
                f"{self.ad} ({self.kip} kipi) izin kancasini uygulayamiyor "
                "(`exec` etkilesimsizdir, onay soracak kanal yok); riskli "
                "cagrilar ofise sorulamazdi. Kancali kip: app-server.")
        # Kanca adi bir SOZLESMEDIR: `mcp__<sunucu>__<arac>`. Bozuk ad tur
        # BASLAMADAN reddedilir -- tur ortasinda anlasilsaydi her onay
        # sorusu kapali kalarak reddedilir ve ajan hic ilerleyemezdi.
        izin_hedefi = self._izin_hedefi(izin_araci) if izin_araci else None
        metin = str(metin or "").strip()
        if not metin:
            raise MotorHatasi("Bos brifing kosulamaz.")
        kok = Path(klasor).expanduser().resolve()
        if not kok.is_dir():
            raise MotorHatasi(f"Ajan calisma klasoru yok: {kok}")
        # Ev, TUR BASLAMADAN once hazirlanir: guvenilmeyen klasorde codex
        # `-s workspace-write` verilse bile salt-okunur kosar (olculdu).
        #
        # HAZIRLANAN EV = KOSULAN EV (22.09.2026). Burada hep VARSAYILAN
        # ev hazirlaniyordu, oysa tur ortamina HESABIN `CODEX_HOME`u
        # gidiyordu (asagida, "hesap kazanir"). Yani ikinci bir codex
        # hesabi hazirlanmamis bir evde -- `[windows] sandbox` ve guven
        # kaydi olmadan -- kosardi ve 21.09'da olculen hata aynen geri
        # gelirdi: ajan "salt-okunur" der, dosya yazilmaz, is yapilmis
        # gibi gorunur. Iki yerde ayri ayri hesaplanan ayni deger, bu
        # projede bir kez daha kopya hatasi olurdu; tek degiskende tutuluyor.
        ev = (ek_ortam or {}).get("CODEX_HOME") or self._ev_bul()
        self._evi_hazirla(ev, str(kok))
        oturum = self._oturum_dogrula(oturum_id)
        devam = bool(oturum)
        sinir = float(zaman_asimi or self.zaman_asimi)

        if butce_usd:
            # Para kontrolu KAPALI KALIR. Codex tur basina tavan
            # uygulayamaz; sessizce kosmak, kullanicinin koydugunu
            # sandigi sinirin olmadigi anlamina gelir ve bunu ancak
            # fatura soyler. Sureci hic baslatmadan reddediyoruz --
            # jeton da yanmaz.
            raise MotorHatasi(
                "codex tur basina butce tavani uygulayamaz "
                "(CLI'da boyle bir bayrak yok). Butce sinirini kaldir ya da "
                "bu isi butce destekleyen bir motora ver (claude). "
                "Sessizce yok sayilan ayar, ayar degildir."
            )
        istek = self._istek_metni(metin, mcp_yapilandirma)

        # Komut, akis BASLAMADAN once kurulur: `_komut_kur` ve
        # `_arguman_dogrula` sozlesme ihlalinde istisna atar (bozuk MCP
        # yapilandirmasi, satir sonlu arguman) -- bunlar turun sonucu degil,
        # turun hic baslayamamasidir. Akis bir kere basladiktan SONRA
        # istisna atilmaz, cunku o noktadan sonra tek cikis `bitti`dir.
        komut = []
        if self.calistirilabilir and self.kip == "app-server":
            komut = self._app_komutu(ek_klasorler=ek_klasorler,
                                     mcp_yapilandirma=mcp_yapilandirma)
            self._arguman_dogrula(komut)
        elif self.calistirilabilir:
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
            # codex DOLAR BILDIRMEZ (`turn.completed` yalniz `usage`).
            # 0.0 "olculmus sifir" demektir ve hic guncellenmiyordu: her
            # codex turu defterde BEDAVA gorunuyordu. None = olculemedi.
            "maliyet": None, "jeton": 0, "arac_sayisi": 0,
        }
        zaman_asti = False
        cikis = -1
        surec = None
        kafes = None
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
                        # HESAP KAZANIR: `ek_ortam` sonra geliyor, yani
                        # hesabin verdigi `CODEX_HOME` adaptorun
                        # varsayilanini EZER. Ters sirada olsaydi ikinci
                        # bir codex hesabi tanimlanabilir ama hicbir
                        # zaman kullanilamazdi -- adaptor onu sessizce
                        # kendi evine geri cevirirdi.
                        env=ortam_hazirla(os.environ, izinli=tuple(ek_ortam or ()),
                                          ek={**(ek_ortam or {}),
                                              "CODEX_HOME": ev}),
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
                # KAFES: turun baslattigi HER SEY tur bitince biter.
                kafes = SurecKafesi(surec)
                if self.kip == "app-server":
                    yield from self._app_akisi(
                        surec, istek, durum, hata_parcalari, basladi, sinir,
                        kok=str(kok), oturum=oturum, devam=devam, model=model,
                        efor=efor, yazabilir=yazabilir, izin_hedefi=izin_hedefi,
                        mcp_adlari=self._mcp_adlari(mcp_yapilandirma),
                        kanal=kanal,
                    )
                else:
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
                if kafes is not None:
                    kafes.kapat()
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

        # OLU OTURUM: imza akista ya da stderr'de. Kaydedilir ki bir
        # sonraki `musait_mi` codex'i HAZIR gostermesin.
        if durum["hata_notu"] != "oturum_kapandi" and (
                cikis != 0 or durum["hatali"]):
            hata_metni = "".join(hata_parcalari).lower()
            if any(imza in hata_metni for imza in OTURUM_OLU_IMZALARI):
                durum["hatali"] = True
                durum["hata_notu"] = "oturum_kapandi"
        if durum["hata_notu"] == "oturum_kapandi":
            oturum_olu_yaz(ev)
            durum["sonuc"] = oturum_olu_metni(ev)

        if zaman_asti:
            yield MotorOlayi(
                "hata", f"Tur {sinir:.0f} saniyede bitmedi, surec kesildi.",
                {"sebep": "zaman_asimi"},
            )
        elif durum["limit"]:
            yield MotorOlayi(
                "hata", "Hesap kullanim limitine ulasildi.", {"sebep": "limit"},
            )
        elif durum.get("durduruldu"):
            # Insanin istegi, ariza degil: sebep ayri ki koltuk isi kaldigi
            # yerden surdurebilsin.
            durum["hata_notu"] = "durduruldu"
            yield MotorOlayi("hata", "Tur insanin istegiyle DURDURULDU.",
                             {"sebep": "durduruldu", "cikis": cikis})
        elif cikis != 0 or durum["hatali"]:
            ayrinti = (durum["sonuc"] or "".join(hata_parcalari)[-1200:]).strip()
            yield MotorOlayi(
                "hata", f"Tur basarisiz (cikis {cikis}): {ayrinti[:1200]}",
                {"sebep": durum["hata_notu"] or "cikis", "cikis": cikis},
            )

        basarili = (
            not zaman_asti and not durum["limit"]
            and cikis == 0 and not durum["hatali"]
            and not durum.get("durduruldu")
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
                # app-server pencereyi TUR SURERKEN bildirir; yoksa (exec
                # ya da bildirim gelmediyse) oturum kaydi okunur.
                "limit_pencere": (durum.get("pencere")
                                  or codex_pencereleri(ev, durum["oturum_id"])),
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

    # -- app-server --------------------------------------------------------

    @staticmethod
    def _izin_hedefi(izin_araci: str) -> tuple:
        """`mcp__<sunucu>__<arac>` -> (sunucu, arac); bozuksa istisna."""
        parca = str(izin_araci or "").split("__")
        if len(parca) != 3 or parca[0] != "mcp" or not parca[1] or not parca[2]:
            raise MotorHatasi(
                f"izin araci adi `mcp__<sunucu>__<arac>` bicimde olmali: {izin_araci!r}")
        return parca[1], parca[2]

    def _app_komutu(self, *, ek_klasorler: tuple, mcp_yapilandirma: str) -> list:
        """app-server sureci. Tur ayarlari (model, efor, sandbox) JSON-RPC ile
        gider; burada yalniz surec BASINDA sabitlenmesi gerekenler var."""
        komut = [self.calistirilabilir, "app-server",
                 "--strict-config"]   # sessizce dusen ayar olmasin (exec ile ayni)
        if ek_klasorler:
            komut += ["-c", "sandbox_workspace_write.writable_roots="
                      + json.dumps([str(ek) for ek in ek_klasorler])]
        for parca in self._mcp_ayarlari(mcp_yapilandirma):
            komut += ["-c", parca]
        return komut

    @staticmethod
    def _onay_cevir(yontem: str, prm: dict):
        """Bir sunucu istegini ofis kapisinin diline cevirir.

        Doner: (arac_adi, girdi, bicim) -- bicim cevabin sekli -- ya da
        None (onay istegi degil). Kapi (`riskli.arac_degerlendir`) claude'un
        arac adlarini konusur; codex'in komutu `Bash`, dosya yazimi
        `Write`, MCP cagrisi `mcp__<sunucu>__<arac>` olur. Boylece KURAL
        TEK YERDE kalir: ayni `rm`, hangi motordan gelirse gelsin ayni
        karari alir.

        TANINAMAYAN onay turu kapiya KENDI ADIYLA gider: kapi bilmedigi
        araci SORAR (polarite) -- yarin eklenen bir onay turu sessizce
        serbest gecemez.
        """
        prm = prm if isinstance(prm, dict) else {}
        if yontem in ("item/commandExecution/requestApproval", "execCommandApproval"):
            komut = prm.get("command")
            if isinstance(komut, list):
                komut = " ".join(str(k) for k in komut)
            bicim = "karar" if yontem.startswith("item/") else "eski"
            return "Bash", {"command": str(komut or "")}, bicim
        if yontem in ("item/fileChange/requestApproval", "applyPatchApproval"):
            bicim = "karar" if yontem.startswith("item/") else "eski"
            return "Write", {"file_path": str(prm.get("grantRoot") or ""),
                             "sebep": str(prm.get("reason") or "")}, bicim
        if yontem == "mcpServer/elicitation/request":
            meta = prm.get("_meta") or {}
            sunucu = str(prm.get("serverName") or "")
            # Arac adi YAPISAL bir alanda DEGIL, yalniz mesajda (olculdu):
            #   'Allow the ofis MCP server to run tool "kanit_ekle"?'
            # Cikarilamazsa ad bos kalir -> kapi taninmayan arac olarak SORAR.
            import re
            m = re.search(r'run tool "([^"]+)"', str(prm.get("message") or ""))
            if meta.get("codex_approval_kind") == "mcp_tool_call" and sunucu and m:
                arac = f"mcp__{sunucu}__{m.group(1)}"
            else:
                arac = f"mcp_istegi__{sunucu or 'bilinmeyen'}"
            girdi = meta.get("tool_params")
            return arac, (girdi if isinstance(girdi, dict) else {}), "eylem"
        if yontem == "item/permissions/requestApproval":
            return "izin_genisletme", {"izinler": prm.get("permissions"),
                                       "sebep": prm.get("reason")}, "izinler"
        return None

    @staticmethod
    def _onay_cevabi(bicim: str, izin: bool, prm: dict) -> dict:
        """Kararin, istegin kendi semasindaki bicimi (her biri olculdu/semada)."""
        if bicim == "karar":
            return {"decision": "accept" if izin else "decline"}
        if bicim == "eski":
            return {"decision": "approved" if izin else "denied"}
        if bicim == "eylem":
            return ({"action": "accept", "content": {}} if izin
                    else {"action": "decline"})
        if bicim == "izinler":
            return {"permissions": (prm.get("permissions") or {}) if izin else {}}
        return {"decision": "decline"}

    def limit_oku(self, *, ek_ortam: dict = None) -> dict | None:
        """`account/rateLimits/read` -- TUR KOSMADAN (26.09 A2 + 27.09 olculdu).

        app-server ayaga kalkar, `initialize` + tek okuma, kapanir. ~2,7 sn,
        kota harcamaz. HESABIN KENDI EVINDE okunur: ikinci bir codex hesabinin
        yuzdesini birincininki sanmak yanlis gosteren gosterge olurdu.
        """
        if not self.calistirilabilir:
            return None
        ev = (ek_ortam or {}).get("CODEX_HOME") or self._ev_bul()
        ortam = ortam_hazirla(os.environ, ek={**(ek_ortam or {}), "CODEX_HOME": str(ev)},
                              izinli=tuple(ek_ortam or ()) + ("CODEX_HOME",))
        try:
            p = subprocess.Popen([self.calistirilabilir, "app-server"],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                 errors="replace", env=ortam)
        except OSError:
            return None
        sonuc = None
        try:
            def yaz(o):
                p.stdin.write(json.dumps(o) + "\n")
                p.stdin.flush()
            yaz({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"clientInfo": {"name": "agentofis", "version": "1"}}})
            bitis = time.monotonic() + 25
            while time.monotonic() < bitis:
                satir = p.stdout.readline()
                if not satir:
                    break
                try:
                    o = json.loads(satir)
                except ValueError:
                    continue
                if o.get("id") == 1:
                    yaz({"jsonrpc": "2.0", "method": "initialized"})
                    yaz({"jsonrpc": "2.0", "id": 2, "method": "account/rateLimits/read",
                         "params": {}})
                elif o.get("id") == 2:
                    sonuc = (o.get("result") or {}).get("rateLimits")
                    break
        except (OSError, ValueError):
            sonuc = None
        finally:
            try:
                p.stdin.close()
            except OSError:
                pass
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        return self._app_pencere(sonuc) if sonuc else None

    @staticmethod
    def _app_pencere(rl: dict):
        """`account/rateLimits/updated` -> ortak pencere bicimi (`tip.py`)."""
        if not isinstance(rl, dict):
            return None
        pencereler = {}
        for anahtar in ("primary", "secondary"):
            p = rl.get(anahtar)
            if not isinstance(p, dict) or not isinstance(p.get("usedPercent"), (int, float)):
                continue
            dk = p.get("windowDurationMins")
            pencereler[PENCERE_DAKIKA_ADI.get(dk, f"{dk}dk")] = {
                "kullanim": p["usedPercent"] / 100.0, "yenilenme": p.get("resetsAt")}
        return limit_penceresi(pencereler, kaynak="codex app-server (account/rateLimits)",
                               hal=str(rl.get("rateLimitReachedType") or ""),
                               plan=str(rl.get("planType") or ""))

    def _app_akisi(self, surec, istek: str, durum: dict, hata_parcalari: list,
                   basladi: float, sinir: float, *, kok: str, oturum: str,
                   devam: bool, model: str, efor: str, yazabilir: bool,
                   izin_hedefi, mcp_adlari: tuple = (),
                   kanal=None) -> Iterator[MotorOlayi]:
        """app-server ile TEK turluk konusma; `_akisi_tuket` ile ayni sozlesme.

        TEK IPLIK, ENGELLEMEYEN: onay sorusu kapiya gider ve cevabi AYNI
        boru uzerinden gelir; soruyu bekleyerek donguyu durdurmak cevabi
        hic okuyamamak olurdu. Istekler kimlikle eslenir (`bekleyen`,
        `kararlar`), dongu hic durmaz.

        ISTISNA SIZDIRMAZ: sonuc `durum` uzerinden doner (`zaman_asimi`,
        `cikis`); akis `bitti` ile kapanacagi icin buradan istisna cikmamali.
        """
        satirlar = queue.Queue()
        okuyucu = threading.Thread(target=self._satir_oku, args=(surec.stdout, satirlar),
                                   name="ofis-codex-app-stdout", daemon=True)
        hata_okuyucu = threading.Thread(target=self._hata_oku,
                                        args=(surec.stderr, hata_parcalari),
                                        name="ofis-codex-app-stderr", daemon=True)
        okuyucu.start()
        hata_okuyucu.start()
        durum["zaman_asimi"] = False
        durum["cikis"] = -1
        sayac = [0]
        bekleyen = {}     # bizim istek kimligi -> amac
        kararlar = {}     # bizim tool/call kimligi -> bekleyen onay istegi
        not_istekleri = {}  # bizim turn/steer kimligi -> (not kimligi, metin)
        baglam = {"thread": "", "tur": "", "bitti": False, "durum": "",
                  # Beklenen MCP sunuculari -> son bildirilen durum.
                  "mcp": {ad: "" for ad in mcp_adlari}, "tur_bekliyor": False,
                  "mcp_son": 0.0}

        def yaz(paket: dict) -> None:
            surec.stdin.write(json.dumps(paket, ensure_ascii=False) + "\n")
            surec.stdin.flush()

        def iste(yontem: str, prm: dict, amac: str) -> int:
            sayac[0] += 1
            bekleyen[sayac[0]] = amac
            yaz({"jsonrpc": "2.0", "id": sayac[0], "method": yontem, "params": prm})
            return sayac[0]

        # Yazabilirlik SUREC duzeyinde: sandbox (exec ile ayni kural).
        politika = "untrusted" if izin_hedefi else "never"
        thread_ayari = {"cwd": kok, "approvalPolicy": politika,
                        "sandbox": SANDBOX_YAZAR if yazabilir else SANDBOX_OKUR}
        model = str(model or "").strip()
        if model:
            thread_ayari["model"] = model
        tur_ayari = {"input": [{"type": "text", "text": istek}]}
        kademe = EFOR_CEVRIMI.get(str(efor or "").strip().lower(), "")
        if kademe:
            tur_ayari["effort"] = kademe

        try:
            iste("initialize", {"clientInfo": {"name": "agentofis", "version": "1"}},
                 "init")
            biter = time.monotonic() + sinir
            while True:
                kalan = biter - time.monotonic()
                if kalan <= 0:
                    durum["zaman_asimi"] = True
                    if baglam["tur"]:
                        try:   # nazikce dur; surec zaten sonra kesilir
                            iste("turn/interrupt", {"threadId": baglam["thread"],
                                                    "turnId": baglam["tur"]}, "kes")
                        except OSError:
                            pass
                    break
                if baglam["tur_bekliyor"]:
                    hazir = all(d in ("ready", "failed") for d in baglam["mcp"].values())
                    if hazir or time.monotonic() >= baglam["mcp_son"]:
                        if not hazir:
                            bekleyenler = [a for a, d in baglam["mcp"].items()
                                           if d not in ("ready", "failed")]
                            yield MotorOlayi(
                                "hata", f"MCP sunucusu {MCP_HAZIR_SN:.0f} sn'de hazir "
                                f"olmadi: {', '.join(bekleyenler)} -- tur yine basliyor, "
                                "araclari eksik olabilir.",
                                {"sebep": "mcp_gecikti", "sunucular": bekleyenler})
                        baglam["tur_bekliyor"] = False
                        iste("turn/start", {**tur_ayari, "threadId": baglam["thread"]},
                             "tur")
                # TUR ICI KANAL: yalniz tur BASLADIKTAN sonra ve bitmeden.
                # Oncesinde alinmaz (steer'in gidecegi tur yok); sonrasinda
                # da alinmaz -- kanalda kalan not sonraki turun basinda.
                if (kanal is not None and baglam["tur"] and not baglam["bitti"]
                        and not durum.get("durduruldu")):
                    if kanal.durdurulsun:
                        durum["durduruldu"] = True
                        iste("turn/interrupt", {"threadId": baglam["thread"],
                                                "turnId": baglam["tur"]}, "durdur")
                    else:
                        for not_kimlik, not_metni in kanal.al():
                            cid = iste("turn/steer", {
                                "threadId": baglam["thread"],
                                "expectedTurnId": baglam["tur"],
                                "input": [{"type": "text", "text": not_metni}]}, "not")
                            not_istekleri[cid] = (not_kimlik, not_metni)
                try:
                    oge = satirlar.get(timeout=min(NABIZ_ARALIGI, kalan))
                except queue.Empty:
                    if surec.poll() is not None and not okuyucu.is_alive():
                        break
                    yield MotorOlayi("nabiz", "", {"gecen_s": round(time.monotonic() - basladi, 1)})
                    continue
                if oge is _SON:
                    break
                try:
                    mesaj = json.loads(str(oge))
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(mesaj, dict):
                    continue

                yontem = mesaj.get("method")
                kimlik = mesaj.get("id")
                # 1) BIZIM isteklerimize cevap
                if yontem is None and kimlik is not None:
                    if kimlik in not_istekleri:
                        # `turn/steer` KABUL edildiyse not ULASTI (olculdu:
                        # kabul edilen steer dosyayi yazdirdi). Reddedildiyse
                        # (tur o an bitmis) ulasmadi -- olay yayilmaz, koltuk
                        # onu sonraki turda verir.
                        bekleyen.pop(kimlik, None)
                        not_kimlik, not_metni = not_istekleri.pop(kimlik)
                        if not mesaj.get("error"):
                            yield MotorOlayi("mesaj", not_metni[:200],
                                             {"kimlik": not_kimlik, "yol": "tur_ici"})
                        continue
                    if kimlik in kararlar:
                        bekleyen.pop(kimlik, None)
                        yield from self._karari_uygula(kararlar.pop(kimlik), mesaj,
                                                       yaz, iste, baglam)
                        continue
                    amac = bekleyen.pop(kimlik, "")
                    hata = mesaj.get("error")
                    if hata and amac in ("init", "thread", "tur"):
                        ileti = str((hata or {}).get("message") or hata)
                        for olay in self._hata_siniflandir(
                                f"app-server {amac}: {ileti}", "", durum):
                            yield olay
                        break
                    sonuc = mesaj.get("result") or {}
                    if amac == "init":
                        yaz({"jsonrpc": "2.0", "method": "initialized"})
                        if devam:
                            iste("thread/resume", {**thread_ayari, "threadId": oturum},
                                 "thread")
                        else:
                            iste("thread/start", thread_ayari, "thread")
                    elif amac == "thread":
                        baglam["thread"] = str((sonuc.get("thread") or {}).get("id") or "")
                        durum["oturum_id"] = baglam["thread"]
                        durum["model"] = str(sonuc.get("model") or durum["model"])
                        yield MotorOlayi("oturum", durum["model"],
                                         {"oturum_id": durum["oturum_id"],
                                          "model": durum["model"]})
                        # Tur MCP HAZIR olunca baslar (bkz. MCP_HAZIR_SN).
                        baglam["tur_bekliyor"] = True
                        baglam["mcp_son"] = time.monotonic() + MCP_HAZIR_SN
                    elif amac == "tur":
                        baglam["tur"] = str((sonuc.get("turn") or {}).get("id") or "")
                    continue
                # 2) SUNUCUNUN bize istegi (onay vb.) -- HER ZAMAN cevaplanir
                if yontem and kimlik is not None:
                    yield from self._sunucu_istegi(mesaj, yaz, iste, kararlar,
                                                   izin_hedefi, baglam)
                    continue
                # 3) Bildirim
                if yontem:
                    prm = mesaj.get("params") or {}
                    if yontem == "mcpServer/startupStatus/updated":
                        ad = str(prm.get("name") or "")
                        if ad in baglam["mcp"]:
                            baglam["mcp"][ad] = str(prm.get("status") or "")
                            if baglam["mcp"][ad] == "failed":
                                # Sessizce dusen sunucu: ajan araci bulamaz ve
                                # "yok" der; sebebi burada gorunur olmali.
                                yield MotorOlayi(
                                    "hata", f"MCP sunucusu acilamadi: {ad} -- "
                                    f"{prm.get('failureReason') or prm.get('error') or ''}"[:600],
                                    {"sebep": "mcp_acilamadi", "sunucu": ad})
                    for olay in self._app_bildirim(yontem, prm, durum, baglam):
                        yield olay
                    if baglam["bitti"]:
                        break

            if not durum["zaman_asimi"] and baglam["bitti"]:
                # app-server tur bitince KENDILIGINDEN kapanmaz; cikisi biz
                # turun durumundan yazariz (surec sonra kesilir).
                durum["cikis"] = 0 if baglam["durum"] == "completed" else 1
            elif not durum["zaman_asimi"] and not durum["hatali"]:
                durum["hatali"] = True
                durum["hata_notu"] = durum["hata_notu"] or "surec"
                durum["sonuc"] = durum["sonuc"] or "app-server tur bitmeden kapandi"
        except Exception as exc:
            durum["hatali"] = True
            durum["hata_notu"] = durum["hata_notu"] or "surec"
            durum["sonuc"] = durum["sonuc"] or f"{type(exc).__name__}: {exc}"
            yield MotorOlayi("hata", f"Surec hatasi: {exc}"[:1200], {"sebep": "surec"})
        finally:
            try:
                surec.stdin.close()
            except Exception:
                pass
            okuyucu.join(timeout=1)
            hata_okuyucu.join(timeout=1)

    def _sunucu_istegi(self, mesaj: dict, yaz, iste, kararlar: dict,
                       izin_hedefi, baglam: dict) -> Iterator[MotorOlayi]:
        yontem = str(mesaj.get("method"))
        kimlik = mesaj.get("id")
        prm = mesaj.get("params") or {}
        ceviri = self._onay_cevir(yontem, prm)
        if ceviri is None:
            # Onay degil (kullanicidan girdi, jeton yenileme, ...): ofis bu
            # istekleri karsilamaz. CEVAPSIZ birakilmaz, hata ile cevaplanir.
            yaz({"jsonrpc": "2.0", "id": kimlik,
                 "error": {"code": DESTEKSIZ_ISTEK_KODU,
                           "message": f"agentofis bu istegi karsilamiyor: {yontem}"}})
            yield MotorOlayi("izin", f"desteklenmeyen istek reddedildi: {yontem}",
                             {"hatali": True, "arac": yontem, "girdi": ""})
            return
        arac, girdi, bicim = ceviri
        if not izin_hedefi:
            # Kanca yok ama onay soruldu: KAPALI KALIR. (politika "never"
            # iken gelmemeli; gelirse sessizce kabul etmek kapisiz tur olur.)
            yaz({"jsonrpc": "2.0", "id": kimlik,
                 "result": self._onay_cevabi(bicim, False, prm)})
            yield MotorOlayi("izin", f"{arac} reddedildi: ofis kapisi bu turda bagli degil",
                             {"hatali": True, "arac": arac, "girdi": str(girdi)[:160]})
            return
        sunucu, kapi_araci = izin_hedefi
        cid = iste("mcpServer/tool/call",
                   {"threadId": str(prm.get("threadId") or baglam["thread"]),
                    "server": sunucu, "tool": kapi_araci,
                    "arguments": {"tool_name": arac, "input": girdi}}, "kapi")
        kararlar[cid] = {"kimlik": kimlik, "bicim": bicim, "arac": arac,
                         "girdi": girdi, "prm": prm}

    def _karari_uygula(self, bekleyen: dict, cevap: dict, yaz, iste,
                       baglam: dict) -> Iterator[MotorOlayi]:
        """Kapinin cevabini okur ve codex'e iletir. OKUNAMAZSA KAPALI KALIR."""
        izin, gerekce = False, ""
        try:
            metin = cevap["result"]["content"][0]["text"]
            karar = json.loads(metin)
            izin = karar.get("behavior") == "allow"
            gerekce = str(karar.get("message") or "")
        except Exception:
            ham = cevap.get("error") or cevap.get("result")
            gerekce = (f"Ofis kapisi cevap veremedi ({str(ham)[:200]}). Guvenli "
                       "tarafta kaliyoruz: bu eylem YAPILMADI.")
        yaz({"jsonrpc": "2.0", "id": bekleyen["kimlik"],
             "result": self._onay_cevabi(bekleyen["bicim"], izin, bekleyen["prm"])})
        if izin:
            return
        girdi = str(bekleyen["girdi"])[:160]
        yield MotorOlayi("izin", f"{bekleyen['arac']} reddedildi: {girdi}",
                         {"hatali": True, "arac": bekleyen["arac"], "girdi": girdi,
                          "gerekce": gerekce[:600]})
        # `decline` modele yalniz "rejected by user" der. Ofisin gerekcesi
        # (SIMDI DUR, onay istendi, baska yol dene) ajana ULASMALI; yoksa ayni
        # seyi baska bicimde tekrar dener. Tur bittiyse steer reddedilir --
        # zararsiz, cevap `bekleyen`de yutulur.
        if gerekce and baglam["tur"] and not baglam["bitti"]:
            try:
                iste("turn/steer", {"threadId": baglam["thread"],
                                    "expectedTurnId": baglam["tur"],
                                    "input": [{"type": "text",
                                               "text": "OFIS KAPISI: " + gerekce}]},
                     "steer")
            except OSError:
                pass

    def _app_bildirim(self, yontem: str, prm: dict, durum: dict,
                      baglam: dict) -> list:
        """Bildirimi olaya cevirir. Tanimadigini YOK SAYAR (CLI yeni tur
        eklediginde tur patlamasin)."""
        olaylar = []
        if yontem == "turn/started":
            baglam["tur"] = str((prm.get("turn") or {}).get("id") or baglam["tur"])
            return olaylar
        if yontem == "turn/completed":
            tur = prm.get("turn") or {}
            # Alt ajanlarin (collab) turlari da bildirilebilir: yalniz BIZIM
            # turumuz donguyu bitirir.
            if baglam["tur"] and str(tur.get("id") or "") not in ("", baglam["tur"]):
                return olaylar
            baglam["bitti"] = True
            baglam["durum"] = str(tur.get("status") or "")
            hata = tur.get("error")
            if baglam["durum"] == "failed" and isinstance(hata, dict):
                olaylar += self._hata_siniflandir(hata.get("message"),
                                                  hata.get("codexErrorInfo"), durum)
            elif baglam["durum"] == "interrupted" and not durum["zaman_asimi"]:
                durum["hatali"] = True
                durum["hata_notu"] = ("durduruldu" if durum.get("durduruldu")
                                      else durum["hata_notu"] or "kesildi")
            return olaylar
        if yontem == "error":
            if prm.get("willRetry"):
                return olaylar          # motor kendisi yeniden deneyecek
            hata = prm.get("error") or {}
            return self._hata_siniflandir(hata.get("message"),
                                          hata.get("codexErrorInfo"), durum)
        if yontem == "thread/tokenUsage/updated":
            toplam = (prm.get("tokenUsage") or {}).get("total") or {}
            # exec kipiyle AYNI hesap (girdi + cikti + onbellek): iki kipin
            # jetonu ayni defterde toplaniyor, farkli formul tavani kaydirir.
            durum["jeton"] = int((toplam.get("inputTokens") or 0)
                                 + (toplam.get("outputTokens") or 0)
                                 + (toplam.get("cachedInputTokens") or 0))
            return olaylar
        if yontem == "account/rateLimits/updated":
            pencere = self._app_pencere(prm.get("rateLimits"))
            if pencere:
                durum["pencere"] = pencere
            return olaylar
        if yontem not in ("item/started", "item/completed"):
            return olaylar
        oge = prm.get("item") or {}
        cins = str(oge.get("type") or "")
        tamam = yontem == "item/completed"
        if cins == "agentMessage":
            if tamam:
                parca = str(oge.get("text") or "")
                durum["metin"].append(parca)
                olaylar.append(MotorOlayi("metin", parca))
            return olaylar
        if cins == "reasoning":
            if tamam:
                ozet = oge.get("summary") or []
                metin = " ".join(str(s) for s in ozet) if isinstance(ozet, list) else str(ozet)
                if metin.strip():
                    olaylar.append(MotorOlayi("dusunce", metin))
            return olaylar
        if cins not in APP_ARAC_ADLARI:
            return olaylar
        ad = APP_ARAC_ADLARI[cins]
        if cins == "mcpToolCall":
            ad = f"{oge.get('server', '')}.{oge.get('tool', '')}".strip(".") or ad
        cagri = str(oge.get("id") or "")
        if not tamam:
            durum["arac_sayisi"] += 1
            olaylar.append(MotorOlayi("arac", ad, {"ozet": self._app_oge_ozeti(oge),
                                                  "cagri_id": cagri}))
            return olaylar
        cikis = oge.get("exitCode")
        durum_ = str(oge.get("status") or "")
        hatali = (bool(oge.get("error")) or cikis not in (None, 0)
                  or durum_ in ("failed", "declined"))
        olaylar.append(MotorOlayi("arac_sonuc", self._app_oge_ozeti(oge, sonuc=True),
                                  {"hatali": hatali, "cagri_id": cagri, "cikis": cikis}))
        return olaylar

    @staticmethod
    def _app_oge_ozeti(oge: dict, *, sonuc: bool = False) -> str:
        anahtarlar = (("aggregatedOutput", "error", "result", "status") if sonuc
                      else ("command", "query", "tool", "changes", "arguments", "status"))
        for anahtar in anahtarlar:
            deger = oge.get(anahtar)
            if deger:
                if isinstance(deger, (dict, list)):
                    deger = json.dumps(deger, ensure_ascii=False)
                return str(deger).strip()[:300]
        return ""

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
            if mcp_yapilandirma:
                komut.append("--approve-for-me")
            else:
                komut += ["-c", f'sandbox_mode="{sandbox}"']
            if ek_klasorler:
                komut += ["-c", "sandbox_workspace_write.writable_roots="
                          + json.dumps([str(ek) for ek in ek_klasorler])]
        else:
            komut += ["-C", klasor]
            if mcp_yapilandirma:
                # `--approve-for-me`: onay isteklerini workspace-write
                # sandbox'i icinde OTOMATIK incelemeye yonlendirir.
                # SANDBOX KALKMAZ -- yalnizca onu kimin kurdugu degisir;
                # bu yuzden `-s` bayragimiz DUSER (olculdu: "cannot be
                # used with --sandbox").
                komut.append("--approve-for-me")
            else:
                komut += ["-s", sandbox]
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
    def _mcp_adlari(mcp_yapilandirma: str) -> tuple:
        """Bu turda baglanan MCP sunucularinin adlari (hazir olmalari beklenir)."""
        adlar = []
        for satir in CodexMotoru._mcp_ayarlari(mcp_yapilandirma):
            ad = satir.split(".", 2)[1] if satir.startswith("mcp_servers.") else ""
            if ad and ad not in adlar:
                adlar.append(ad)
        return tuple(adlar)

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
                # KACIRILARAK yazilir. Ham interpolasyon Windows yolunda
                # GECERSIZ TOML uretiyordu: yoldaki ters bolu + buyuk U
                # dizisi TOML temel dizgisinde sekiz haneli bir kacis
                # bekler ve ayristirici "Invalid hex value" ile duser.
                # Olculdu (21.09.2026): ofis MCP'sinin komutu tam boyle
                # bir yoldu, sunucu hic ayaga kalkmadi ve ajanin BUTUN
                # `ofis.*` cagrilari "failed" dondu -- ajan da bunu
                # "dosya sistemi salt-okunur" diye yanlis teshis etti.
                satirlar.append(
                    "mcp_servers.%s.command=%s"
                    % (ad, json.dumps(str(ayar["command"]))))
            if ayar.get("args"):
                satirlar.append(
                    f"mcp_servers.{ad}.args={json.dumps(list(ayar['args']))}")
            if ayar.get("env"):
                # TOML SATIR ICI TABLOSU -- JSON DEGIL.
                #
                # OLCULDU (21.09.2026), ilk GERCEK codex turunda: burada
                # `json.dumps({...})` yaziliyordu ve codex `-c` degerini
                # TOML olarak ayristirdigi icin JSON nesnesini bir STRING
                # sanip 157 ms'de dusuyordu:
                #
                #   Error loading config.toml: invalid type: string
                #   "{\"OFIS_DB\": \"C:\\\\...\\\\ofis.sqlite3\", ...}"
                #
                # Fark sinsi: TOML dizisi ile JSON dizisi AYNI gorunur
                # (`["a","b"]`), o yuzden `args` tesadufen calisiyordu ve
                # hata yalnizca `env` verildiginde -- yani ofis MCP'si
                # baglandiginda, yani HER GERCEK ISTE -- cikiyordu.
                #
                # Anahtarlar tirnakli yaziliyor: TOML ciplak anahtari
                # sinirli bir karakter kumesi kabul eder, ortam degiskeni
                # adi yarin onun disina cikabilir. Degerler `json.dumps`
                # ile kaciriliyor -- TOML temel dizgisi ile JSON dizgisi
                # ayni kacis kurallarini kullanir (Windows ters bolu
                # dahil).
                icerik = ", ".join(
                    f"{json.dumps(str(k))} = {json.dumps(str(v))}"
                    for k, v in dict(ayar["env"]).items())
                satirlar.append("mcp_servers.%s.env={%s}" % (ad, icerik))
            if ayar.get("url"):
                # Ayni kacis kurali: ham interpolasyon guvenilmez.
                satirlar.append("mcp_servers.%s.url=%s"
                                % (ad, json.dumps(str(ayar["url"]))))
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
            olaylar += self._hata_siniflandir(ileti, "", durum)
        return olaylar

    @staticmethod
    def _hata_siniflandir(ileti: str, kod, durum: dict) -> list:
        """Bir motor hatasini SINIFINA gore olaya cevirir -- iki kipin TEK yeri.

        Sira bilincli: once OTURUM, sonra LIMIT. Olu oturum limit sayilsaydi
        zincir sessizce devreder ve sebep (yeniden giris gerekiyor) hic
        gorunmezdi -- beklemek ise yaramaz, giris gerekir.

        `kod` app-server'in YAPISAL hata kodudur (`codexErrorInfo`); varsa
        metinden once ona bakilir. exec kipinde bos gelir, metin taranir.
        """
        ileti = str(ileti or "")
        kod = kod if isinstance(kod, str) else ""
        durum["hatali"] = True
        durum["sonuc"] = ileti or durum["sonuc"]
        dusuk = ileti.lower()
        if kod in OTURUM_KODLARI or any(i in dusuk for i in OTURUM_OLU_IMZALARI):
            durum["hata_notu"] = "oturum_kapandi"
            return [MotorOlayi("hata", ileti[:1200], {"sebep": "oturum_kapandi"})]
        if kod in LIMIT_KODLARI or any(i in dusuk for i in LIMIT_IMZALARI):
            durum["limit"] = True
            durum["hata_notu"] = "limit"
            return [MotorOlayi("limit", ileti[:300], {"ham": ileti[:1200]})]
        durum["hata_notu"] = durum["hata_notu"] or "motor"
        return [MotorOlayi("hata", ileti[:1200], {"sebep": "motor"})]

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
