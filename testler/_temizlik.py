# -*- coding: utf-8 -*-
"""Sinamalarin gecici klasorlerini sinama bitince SILER -- ve olcer.

PLAN F1, E05. Olculdu (26.09.2026): tam takim bir kez kosunca
`%TEMP%`'te ~45 `ofis-*` klasoru kaliyordu; birikmis 302 klasor
(~60 MB) bulundu. Diski bir kez dolduran da buydu.

Her dosyada ayri ayri `finally: rmtree` yazmak, 22 dosyadan birinde
unutulmanin garantisiydi (bu projede iki kopyadan biri alti kez
unutuldu). Bunun yerine: sinamanin EN BASINDA ice aktarilir,
`tempfile.mkdtemp` sarmalanir, acilan her klasor kaydedilir ve surec
biterken silinir.

* Git nesneleri Windows'ta SALT OKUNUR: silmeden once yazilabilir yapilir.
* Alt surec (MCP sunucusu, tarayici) dosyayi kisa sure tutabilir:
  birkac kez denenir.
* Silinemeyen kalirsa SESSIZ kalinmaz: stderr'e yazilir ve cikis kodu
  basarisiza cevrilir -- artik birakan sinama gecmis sayilmaz.
* Golge depolar (`geri_al.py`) de bu surecin gecici klasorune yonlenir;
  yoksa her sinama gecici klasorde bir golge depo birakirdi.
"""

from __future__ import annotations

import atexit
import gc
import os
import shutil
import sys
import tempfile
import time

_ACILAN: list = []
_ASIL_MKDTEMP = tempfile.mkdtemp


def _kaydeden_mkdtemp(*a, **kw):
    yol = _ASIL_MKDTEMP(*a, **kw)
    _ACILAN.append(yol)
    return yol


tempfile.mkdtemp = _kaydeden_mkdtemp

if not os.environ.get("OFIS_GOLGE_KOK"):
    os.environ["OFIS_GOLGE_KOK"] = tempfile.mkdtemp(prefix="ofis-golge-sinama-")

# GERCEK HAFIZAYA YAZILMAZ (27.09.2026). Ofisin butun calisma durumu
# (`ofis/yollar.py`: kasa, kota ve motor saglik defterleri, codex evi,
# kabin profili, yedekler) tek bir kokte ve o kok sinamada gecici bir
# klasore cevrilir. Olculdu: `duman_gorsel.py` her kosuda kullanicinin
# gercek kota defterine "Gemini kotasi doldu" yaziyordu -- sabiti
# yonlendirmeyi bir bolumde UNUTMUSTU. Tek kokle unutmak mumkun degil.
# PATRONUN KABINI (9222) sinamaya KAPALI: "ajanlar kabinde" varsayilan
# acik; sinama ofisi kendi (bos) kapisina bakar.
if not os.environ.get("OFIS_KABIN_KAPI"):
    os.environ["OFIS_KABIN_KAPI"] = "9399"

# Patronun Claude klasoru yerine BOS klasor (02.10.2026): becerileri ve
# MCP'leri otomatik getiren kod sinamada gercek klasoru okumasin.
if not os.environ.get("OFIS_CLAUDE_EV"):
    os.environ["OFIS_CLAUDE_EV"] = tempfile.mkdtemp(prefix="ofis-claude-sinama-")
    os.environ["OFIS_CLAUDE_JSON"] = os.path.join(os.environ["OFIS_CLAUDE_EV"], "claude.json")
if not os.environ.get("OFIS_EV"):
    os.environ["OFIS_EV"] = tempfile.mkdtemp(prefix="ofis-ev-sinama-")

#: Gercek kokteki hafiza dosyalari: sinama bunlara DOKUNMAMALI. Surec
#: basinda damgalari alinir, sonunda karsilastirilir (bekci).
# Gercek ev TEK kuraldan (01.10.2026: `Masaustu\AgentOfis\ev`, tasimadan
# once eski `~/.agentofis`). OFIS_EV yukarida GECICIYE cevrildi; yollar
# simdi ice aktarilir ve sabitleri geciciyi gorur.
import sys as _sys  # noqa: E402
_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in _sys.path:
    _sys.path.insert(0, _KOK)
from ofis.yollar import varsayilan_ev as _varsayilan_ev  # noqa: E402
_GERCEK_EV = str(_varsayilan_ev())
_BEKCI_DOSYALAR = ("kota.json", "baglayici_sorun.json", "motor_saglik.json",
                   "codex_oturum.json", "ayar.json", "gizli.env")


def _damgalar() -> dict:
    d = {}
    for ad in _BEKCI_DOSYALAR:
        try:
            s = os.stat(os.path.join(_GERCEK_EV, ad))
            d[ad] = (s.st_mtime_ns, s.st_size)
        except OSError:
            d[ad] = None
    return d


_BASTAKI_DAMGALAR = _damgalar()
_BASLANGIC = time.time()


def _brifing_artiklarini_sil() -> int:
    """GERCEK EVLE kosan duzenegin (gercek set, deneme, matris) biraktigi
    brifing kopyalari (`ev/brifing/<proje>/`) silinir.

    OLCULDU (06.10.2026): gercek evde 366 brifing klasoru vardi, YALNIZ
    BIRI gercek projenindi -- her gercek set isi gecici bir proje acar,
    defteri silinir ama brifing kopyasi evde kalir. Silinen: bu SURECTE
    acilmis ve gercek defterde OLMAYAN proje klasoru. Gercek projeye ve
    surecten once var olana dokunulmaz.
    """
    if os.environ.get("OFIS_EV", "") != _GERCEK_EV:
        return 0                     # gecici ev zaten butunuyle silinir
    kok = os.path.join(_GERCEK_EV, "brifing")
    if not os.path.isdir(kok):
        return 0
    import sqlite3
    gercek = set()
    defter = os.path.join(_KOK, "veri", "ofis.sqlite3")
    try:
        c = sqlite3.connect(f"file:{defter}?mode=ro", uri=True)
        gercek = {r[0] for r in c.execute("SELECT id FROM proje")}
        c.close()
    except sqlite3.Error:
        return 0                     # gercek defter okunamadiysa hicbir sey silinmez
    silinen = 0
    for ad in os.listdir(kok):
        y = os.path.join(kok, ad)
        try:
            if (os.path.isdir(y) and ad not in gercek
                    and os.stat(y).st_ctime >= _BASLANGIC - 1):
                shutil.rmtree(y, ignore_errors=True)
                silinen += 1
        except OSError:
            pass
    return silinen



def _yazilabilir_yap(islev, yol, _hata):
    try:
        os.chmod(yol, 0o700)
        islev(yol)
    except FileNotFoundError:
        pass


def temizle() -> list:
    # SICAK BEKLEYEN SURECLER ONCE (06.10.2026 OLCULDU): gercek set her Claude
    # isinde bir gecici klasoru silemedi -- liderin bekleyen sureci (ve MCP
    # yan sureci, defteri acik) o klasorde yasiyordu; kapatma kancasi
    # temizlikten SONRA kosabiliyordu.
    _cl = sys.modules.get("ofis.motor.claude")
    if _cl is not None:
        try:
            _cl.sicaklari_kapat()
        except Exception:                 # noqa: BLE001 -- temizlik durmasin
            pass
    gc.collect()
    kalan = []
    for yol in reversed(_ACILAN):
        for _ in range(5):
            if not os.path.exists(yol):
                break
            try:
                shutil.rmtree(yol, onexc=_yazilabilir_yap)
            except OSError:
                time.sleep(0.4)
        if os.path.exists(yol):
            kalan.append(yol)
    _ACILAN.clear()
    return kalan


def _cikista():
    kalan = temizle()
    _brifing_artiklarini_sil()
    # BEKCI: sinama gercek hafizaya yazdiysa SESSIZ kalinmaz. Gercek ofis
    # (panel, kabuk) ayni anda calisiyorsa yanlis alarm olabilir -- bu
    # yuzden hangi dosyanin degistigi soylenir, karar okuyanin.
    degisen = [ad for ad, d in _damgalar().items() if d != _BASTAKI_DAMGALAR.get(ad)]
    if degisen and os.environ.get("OFIS_EV", "") != _GERCEK_EV:
        print("\n[GERCEK HAFIZA] sinama sirasinda kullanicinin gercek "
              f"~/.agentofis dosyalari DEGISTI: {', '.join(degisen)} "
              "(gercek ofis ayni anda calismiyorsa bu bir SIZINTIDIR).",
              file=sys.stderr)
        os._exit(3)
    if kalan:
        print(f"\n[ARTIK] {len(kalan)} gecici klasor SILINEMEDI:", file=sys.stderr)
        for y in kalan:
            print(f"  {y}", file=sys.stderr)
        # Artik birakan sinama gecmis sayilmaz (sys.exit(0) cagrilmis olsa bile).
        os._exit(3)


atexit.register(_cikista)
