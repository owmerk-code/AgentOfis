"""KONSOL -- ofisten BAGIMSIZ, insanin kendi terminali (panelin icinde).

Kullanici (28.09.2026): *"agent sisteminde herhangi bir terminali acip
ofisten ya da takimdan bagimsiz kullanabilecek miyim?"* -- VS Code'daki
terminal gibi. `ofis/terminal.py` (Devral icin kuruldu) bunu zaten
yapabiliyor; bu modul onun OFIS DISI kullanimi.

Kurallar:

* **Ofisin calisma kokunde ACILMAZ.** Orada ajanlar calisir ve yazma
  kilidi bu terminali GOREMEZ: insanin yazdigi dosya bir ajanin isini
  sessizce ezebilirdi (Yasa 1). Ofisin bir isine elle girmek isteyen
  "Devral"i kullanir -- o kilitli, olculur ve ajana iletilir.
* **Klasor kapidan gecer** (`klasor.klasor_dogrula`): var olmayan, surucu
  koku, sistem klasoru reddedilir.
* **Kayda gecer, ama yalniz acildi/kapandi.** Konsolun ICI ofisin kaydi
  degildir (isin disinda); kim, nerede, hangi motorla actigi ise gorunur
  kalir -- "bu terminal ne zaman acilmis" sorusu cevapsiz kalmasin.
* **Yalniz bu bilgisayardan** (panel `TERMINAL_YEREL`).
* Motor komutlarini insan onaylar: Claude/Codex kendi izin sorularini
  sorar, klavyenin basinda insan var.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from . import klasor as _klasor
from . import terminal
from .motor import motor_ac, MotorHatasi

#: Motor adlari + duz kabuk. Yeni bir motor `etkilesimli_komut` yazarsa
#: kendiliginden buraya girer (`ac` motor adini fabrikaya sorar).
KABUK = "powershell"


class KonsolHatasi(RuntimeError):
    pass


def _ofis_kokunde_mi(ofis, yol: Path) -> bool:
    kok = ofis.tahta.kok_klasor()
    if not kok:
        return False
    k = Path(kok).resolve()
    y = yol.resolve()
    return y == k or k in y.parents


def ac(ofis, klasor: str, motor: str = KABUK, *, fabrika=motor_ac,
       sutun: int = 120, satir: int = 32) -> dict:
    try:
        yol = _klasor.klasor_dogrula(klasor)
    except Exception as exc:              # noqa: BLE001 -- sebep insana
        raise KonsolHatasi(str(exc)) from exc
    if _ofis_kokunde_mi(ofis, yol):
        raise KonsolHatasi(
            "Bu klasor OFISIN calisma koku -- orada ajanlar calisir ve bu "
            "terminal yazma kilidini goremez. Ofisin bir isine elle girmek "
            "icin o isi 'Devral'; konsolu baska bir klasorde ac.")
    durum = terminal.pty_durumu()
    if durum:
        raise KonsolHatasi(durum)
    motor = (motor or KABUK).strip().lower()
    if motor == KABUK:
        komut = {"argv": ["powershell.exe", "-NoLogo"], "ortam": None, "kapat": "exit",
                 "temizle": "\x1b"}
    else:
        try:
            m = fabrika(motor)
        except MotorHatasi as exc:
            raise KonsolHatasi(f"'{motor}' motoru acilamadi: {exc}") from exc
        komut = m.etkilesimli_komut(oturum_id="", klasor=str(yol), model="")
        if not komut:
            raise KonsolHatasi(f"'{motor}' motoru terminalde acilamiyor.")
    try:
        t = terminal.Terminal(komut["argv"], klasor=str(yol), ortam=komut.get("ortam"),
                              kapat_girdisi=komut.get("kapat", ""),
                              satir_temizle=komut.get("temizle", "\x15"),
                              sutun=sutun, satir=satir)
    except terminal.TerminalHatasi as exc:
        raise KonsolHatasi(str(exc)) from exc
    kimlik = "konsol-" + uuid.uuid4().hex[:10]
    terminal.kaydet(kimlik, t, konsol=True, motor=motor, klasor=str(yol),
                    acildi=time.time())
    ofis.db.olay_yaz(ofis.proje_id, "konsol_acildi",
                     f"insan ofis disi terminal acti: {motor} · {yol}")
    return {"kimlik": kimlik, "motor": motor, "klasor": str(yol),
            "kafes": t.kafes.kuruldu}


def liste() -> list:
    sonuc = []
    for anahtar, kayit in terminal.hepsi():
        if not kayit.get("konsol"):
            continue
        sonuc.append({"kimlik": anahtar, "motor": kayit.get("motor"),
                      "klasor": kayit.get("klasor"),
                      "canli": kayit["terminal"].canli(),
                      "acildi": kayit.get("acildi")})
    return sorted(sonuc, key=lambda x: x.get("acildi") or 0)


def kapat(ofis, kimlik: str) -> dict:
    kayit = terminal.al(kimlik)
    if not kayit or not kayit.get("konsol"):
        raise KonsolHatasi("Boyle bir konsol yok.")
    nasil = kayit["terminal"].kapat()
    terminal.cikar(kimlik)
    ofis.db.olay_yaz(ofis.proje_id, "konsol_kapandi",
                     f"ofis disi terminal kapandi ({kayit.get('motor')} · "
                     f"{kayit.get('klasor')}) -- {nasil}")
    return {"kimlik": kimlik, "kapanis": nasil}
