# -*- coding: utf-8 -*-
"""MASAUSTU BILDIRIMI -- patron ekranin basinda degilken haber (01.10.2026).

Kullanici: ofis "ben yokken" calisacak (F5); ajan onay ya da cevap
beklerken patron bunu panele bakmadan bilmeli. Claude Code is bitince ve
izin isteyince haber verir; ofis de verir.

Nasil:
* Panel DEFTERI izler (birkac saniyede bir). Uretici ici kanca yetmez:
  onay isteyen ajanin MCP sunucusu AYRI bir surectir, panelin bellegine
  ulasmaz. Defter tek ortak yer.
* Izleyici acildigi andan SONRAKI olaylari bildirir -- eski kayitlar
  ekrani doldurmaz.
* Windows bildirimi PowerShell + WinRT ile, ek kurulum yok. Metin
  `-EncodedCommand` (UTF-16) ile gider: BOM'suz betik dosyasi Windows
  PowerShell 5'te ANSI okunur ve Turkce harf bozulur (olculdu, 01.10 G13).
* VARSAYILAN KAPALI (`ACIK`): kutuphane sinamada ekrana bildirim atmasin.
  Panel `calistir` acar. Patron ayarla kapatabilir (`bildirim` = kapali).
* Gonderim BEKLETMEZ (Popen) ve DUSERSE izleyiciyi durdurmaz; dusus bir
  kez deftere yazilir (sessiz yutulmaz).
"""

from __future__ import annotations

import base64
import subprocess
import sys
import threading
import time
from xml.sax.saxutils import escape

ACIK = False
AYAR = "bildirim"
ARALIK_S = 2.0
#: Ayni anda cok olay gelirse TEK bildirim (onay yagmuru ekrani doldurmasin).
AZAMI_SATIR = 3

_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"


def _kisa(metin: str, n: int = 140) -> str:
    metin = " ".join(str(metin or "").split())
    return metin if len(metin) <= n else metin[:n - 1].rstrip() + "…"


def toast_xml(baslik: str, metin: str, adres: str = "") -> str:
    """Windows bildirim XML'i -- metin KACIRILIR (ajan metni `<` tasiyabilir)."""
    bas = (f'<toast activationType="protocol" launch="{escape(adres, {chr(34): "&quot;"})}">'
           if adres else "<toast>")
    return (bas + '<visual><binding template="ToastGeneric">'
            f"<text>{escape(_kisa(baslik, 80))}</text>"
            f"<text>{escape(_kisa(metin, 300))}</text>"
            "</binding></visual></toast>")


def powershell_komutu(xml: str) -> list:
    """`-EncodedCommand` (UTF-16LE base64): kodlamadan bagimsiz."""
    betik = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        "ContentType = WindowsRuntime] | Out-Null;"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, "
        "ContentType = WindowsRuntime] | Out-Null;"
        "$d = New-Object Windows.Data.Xml.Dom.XmlDocument;"
        f"$d.LoadXml('{xml.replace(chr(39), chr(39) * 2)}');"
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{_APP_ID}')"
        ".Show([Windows.UI.Notifications.ToastNotification]::new($d))")
    kod = base64.b64encode(betik.encode("utf-16-le")).decode("ascii")
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
            "-EncodedCommand", kod]


def _windows_gonder(baslik: str, metin: str, adres: str = "") -> None:
    subprocess.Popen(powershell_komutu(toast_xml(baslik, metin, adres)),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


#: Sinama bunu degistirir (ekrana gercek bildirim atmadan toplar).
GONDERICI = _windows_gonder if sys.platform == "win32" else (lambda *a, **k: None)


def acik_mi(ofis) -> bool:
    if not ACIK:
        return False
    try:
        return (ofis.db.ayar_oku(ofis.proje_id, AYAR, "acik") or "acik") != "kapali"
    except Exception:                  # noqa: BLE001 -- ayar okunamazsa acik (varsayilan)
        return True


def tur_anahtari(baslik: str) -> str:
    """Bildirim basligi -> Ayarlar'daki tur anahtari (`ayarlar.BILDIRIM_TURLERI`)."""
    if baslik == "Onay bekliyor":
        return "onay"
    if baslik.endswith("sana soruyor"):
        return "soru"
    if baslik.endswith("cevapladı"):
        return "cevap"
    return {"Sıradaki işler bitti": "donus", "Bir iş takıldı": "takildi",
            "Bir iş düştü": "dustu", "Ofis bir hafıza yazısını durdurdu": "hafiza",
            "Zamanlanmış iş başladı": "zamanli",
            "Ofis kaldığı yerden sürüyor": "kesinti"}.get(baslik, "")


class Izleyici:
    """Defterdeki YENI olaylari bildirime cevirir. `tik()` bir tarama yapar."""

    OLAYLAR = ("onay_istendi", "donus_raporu", "kesinti_toparlandi", "hata",
               "zamanli_calisti", "takildi", "hafiza_reddi")

    def __init__(self, ofis, adres: str = ""):
        self.ofis, self.adres = ofis, adres
        with ofis.db.baglanti() as c:
            self.son_olay = c.execute("SELECT COALESCE(MAX(rowid), 0) FROM olay").fetchone()[0]
            self.son_mesaj = c.execute("SELECT COALESCE(MAX(rowid), 0) FROM mesaj").fetchone()[0]
            self.son_cevap = c.execute("SELECT COALESCE(MAX(cevaplandi), '') FROM mesaj "
                                       "WHERE proje_id = ?", (ofis.proje_id,)).fetchone()[0]
        self.dustu = False

    def topla(self) -> list:
        """Yeni olaylar -> [(baslik, metin)], en fazla AZAMI_SATIR + ozet."""
        pid = self.ofis.proje_id
        ogeler = []
        with self.ofis.db.baglanti() as c:
            for r in c.execute(
                    "SELECT rowid AS sira, tur, ajan_ad, govde FROM olay WHERE proje_id = ? AND rowid > ? "
                    "AND tur IN (%s) ORDER BY rowid" % ",".join("?" * len(self.OLAYLAR)),
                    (pid, self.son_olay, *self.OLAYLAR)):
                self.son_olay = max(self.son_olay, r["sira"])
                g = r["govde"] or ""
                if r["tur"] == "onay_istendi":
                    ogeler.append(("Onay bekliyor", g))
                elif r["tur"] == "donus_raporu":
                    ogeler.append(("Sıradaki işler bitti", "Dönüş raporu hazır."))
                elif r["tur"] == "hafiza_reddi":
                    ogeler.append(("Ofis bir hafıza yazısını durdurdu", g))
                elif r["tur"] == "takildi":
                    ogeler.append(("Bir iş takıldı", g))
                elif r["tur"] == "zamanli_calisti":
                    ogeler.append(("Zamanlanmış iş başladı", g))
                elif r["tur"] == "kesinti_toparlandi":
                    ogeler.append(("Ofis kaldığı yerden sürüyor", g))
                elif r["tur"] == "hata" and g.startswith("Siradaki is dustu"):
                    ogeler.append(("Bir iş düştü", g))
            for r in c.execute(
                    "SELECT rowid AS sira, gonderen, govde FROM mesaj WHERE proje_id = ? AND rowid > ? "
                    "AND alici = 'insan' ORDER BY rowid", (pid, self.son_mesaj)):
                self.son_mesaj = max(self.son_mesaj, r["sira"])
                ogeler.append((f"{r['gonderen']} sana soruyor", r["govde"]))
            for r in c.execute(
                    "SELECT alici, cevap, cevaplandi FROM mesaj WHERE proje_id = ? AND "
                    "gonderen = 'insan' AND cevaplandi > ? ORDER BY cevaplandi",
                    (pid, self.son_cevap or "")):
                self.son_cevap = max(self.son_cevap or "", r["cevaplandi"])
                from . import ekler as _ek
                ogeler.append((f"{r['alici']} cevapladı", _ek.ayikla(r["cevap"] or "")[0]))
        # PATRONUN SECIMI (Ayarlar > Bildirimler): kapattigi turler gelmez.
        # Onay ve soru kapatilamaz (kural `ayarlar.BILDIRIM_TURLERI`).
        from .ayarlar import bildirim_kapalilar
        _kapali = bildirim_kapalilar(self.ofis.db, pid)
        if _kapali:
            ogeler = [o for o in ogeler if tur_anahtari(o[0]) not in _kapali]
        # ONCELIK: senden bir sey BEKLEYEN (onay, soru) once, sonra liderin
        # cevabi, en son bilgi. Sinama yakaladi: tablo sirasiyla kesilince
        # liderin cevabi ozete dusup kayboluyordu.
        def _oncelik(o):
            b = o[0]
            return (0 if b == "Onay bekliyor" or b.endswith("sana soruyor")
                    else 1 if b.endswith("cevapladı") else 2)
        ogeler.sort(key=_oncelik)
        if len(ogeler) > AZAMI_SATIR:
            kalan = len(ogeler) - AZAMI_SATIR
            ogeler = ogeler[:AZAMI_SATIR] + [("Ofiste başka gelişmeler",
                                             f"{kalan} bildirim daha — paneli aç.")]
        return ogeler

    def tik(self) -> int:
        ogeler = self.topla()
        if not ogeler or not acik_mi(self.ofis):
            return 0
        for baslik, metin in ogeler:
            try:
                GONDERICI(baslik, metin, self.adres)
            except Exception as exc:   # noqa: BLE001 -- izleyici durmaz, ama SOYLER
                if not self.dustu:
                    self.dustu = True
                    self.ofis.db.olay_yaz(self.ofis.proje_id, "uyari",
                                          f"Masaustu bildirimi gonderilemedi: {exc}")
        return len(ogeler)


def arkada_izle(ofis_ac, adres: str = "") -> threading.Thread:
    """Panel icin: `ofis_ac()` her turda TAZE Ofis verir (iplikler arasi)."""
    def dongu():
        iz, soylendi = None, False
        while True:
            try:
                if iz is None:
                    iz = Izleyici(ofis_ac(), adres)
                else:
                    iz.ofis = ofis_ac()
                    iz.tik()
            except Exception as exc:   # noqa: BLE001 -- bir tur duserse sonraki dener
                # SESSIZ YUTULMAZ: ilk dusus konsola ve deftere bir kez yazilir.
                if not soylendi:
                    soylendi = True
                    import traceback
                    traceback.print_exc()
                    try:
                        o = ofis_ac()
                        o.db.olay_yaz(o.proje_id, "uyari", f"Bildirim izleyicisi dustu: {exc}")
                    except Exception:  # noqa: BLE001
                        pass
            time.sleep(ARALIK_S)
    t = threading.Thread(target=dongu, name="bildirim", daemon=True)
    t.start()
    return t
