# -*- coding: utf-8 -*-
"""CodexMotoru sozlesme testleri.

Iki sey sinaniyor, ikisi de gercek `codex` kurulumundan BAGIMSIZ:

1. Sinif `tip.py`deki Motor yuzunu tasiyor mu (ad, mcp_konusur, musait_mi,
   tur_kos -- imzalariyla birlikte).
2. `tur_kos` akisi HER ZAMAN `bitti` ile kapaniyor mu: normalde de, cikis
   kodu sifir olmadiginda da, surec hic ayaga kalkmadiginda da, alt surec
   istisna firlattiginda da.

Alt surec sahte: `subprocess.Popen` monkeypatch'lenir. Gercek CLI'a
baglanmak testi yavas, pahali ve tekrarlanamaz yapardi -- ve dusen testin
bizden mi motordan mi geldigi bilinemezdi.
"""

from __future__ import annotations

import inspect
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from codex import CodexMotoru, _sozlesmeyi_yukle  # noqa: E402

# Sozlesme DOSYADAN okunur (`referans/tip.py`), paketten degil: `referans/
# __init__.py` var olmayan `.claude` modulunu cekiyor. Yukleyici tek kopya
# doner -- adaptorun gordugu `Motor` ile testin gordugu ayni sinif olmali,
# yoksa `issubclass` sinamasi hicbir sey kanitlamaz.
_tip = _sozlesmeyi_yukle()
Motor, MotorOlayi, MotorHatasi = _tip.Motor, _tip.MotorOlayi, _tip.MotorHatasi


# -- gecici calisma klasoru ------------------------------------------------


@pytest.fixture
def klasor():
    """`tur_kos`un isteyecegi var olan bir calisma klasoru.

    pytest'in `tmp_path` fixture'i KULLANILMIYOR: bu makinede sistem temp
    dizini ajan surecine kapali ve fixture daha kurulurken
    "PermissionError: [WinError 5] ... pytest-of-pc" ile duser -- yani
    adaptorle hic ilgisi olmayan bir sebeple butun testler kirmizi olur.
    Once sistem temp denenir, kapaliysa test dosyasinin yanina dusulur.
    """
    try:
        yol = Path(tempfile.mkdtemp(prefix="ofis-codex-"))
    except OSError:
        (KOK / ".gecici").mkdir(exist_ok=True)
        yol = Path(tempfile.mkdtemp(prefix="ofis-codex-", dir=KOK / ".gecici"))
    try:
        yield yol
    finally:
        shutil.rmtree(yol, ignore_errors=True)


# -- sahte alt surec -------------------------------------------------------


class SahteSurec:
    """`subprocess.Popen`in testte yeterli olan yuzu.

    Gercek borular yerine hazir satir listesi verir; `cikis` ile turun
    nasil bittigi secilir.
    """

    def __init__(self, satirlar, cikis: int = 0, hata_satirlari=()):
        self.pid = -1
        self.stdin = _SahteBoru()
        self.stdout = _SahteOkuma(satirlar)
        self.stderr = _SahteOkuma(hata_satirlari)
        self._cikis = cikis
        self.yazilan = self.stdin.yazilan

    def poll(self):
        return self._cikis

    def wait(self, timeout=None):
        return self._cikis

    def terminate(self):
        pass

    def kill(self):
        pass


class _SahteBoru:
    """stdin: yazilani saklar."""

    def __init__(self):
        self.yazilan = []

    def write(self, veri):
        self.yazilan.append(veri)

    def close(self):
        pass


class _SahteOkuma:
    """stdout/stderr: satirlar uzerinde donulur, `close` DESTEKLENIR.

    Duz bir `iter(...)` yetmiyor: adaptor temizlikte borulari kapatiyor ve
    `close`u olmayan bir sahte, gercekte var olmayan bir hata uretirdi.
    """

    def __init__(self, satirlar):
        self._satirlar = iter(list(satirlar))
        self.kapandi = False

    def __iter__(self):
        return self._satirlar

    def close(self):
        self.kapandi = True


NORMAL_AKIS = [
    '{"type":"thread.started","thread_id":"01a0b57a-0000-7000-8000-000000000000"}\n',
    '{"type":"turn.started"}\n',
    '{"type":"item.completed","item":{"item_type":"agent_message","text":"is bitti"}}\n',
    '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}\n',
]


def _motor(monkeypatch, surec_uretici) -> CodexMotoru:
    """Kurulu codex ARANMAZ: yol elle verilir, Popen sahteyle degistirilir."""
    motor = CodexMotoru(calistirilabilir="codex-sahte.exe")
    monkeypatch.setattr(subprocess, "Popen", surec_uretici)
    return motor


def _olaylar(motor, klasor) -> list:
    return list(motor.tur_kos("brifing", klasor=str(klasor)))


# -- 1) sozlesme -----------------------------------------------------------


def test_motor_arayuzunu_uygular():
    assert issubclass(CodexMotoru, Motor)
    for uye in ("ad", "mcp_konusur", "musait_mi", "tur_kos"):
        assert hasattr(CodexMotoru, uye), f"eksik uye: {uye}"
    assert CodexMotoru.ad == "codex"
    assert isinstance(CodexMotoru.mcp_konusur, bool)
    # Soyut uye kalmadiysa sinif ornek verilebilir olmalidir.
    assert not getattr(CodexMotoru, "__abstractmethods__", set())


def test_tur_kos_imzasi_sozlesmeye_uyar():
    beklenen = inspect.signature(Motor.tur_kos)
    gercek = inspect.signature(CodexMotoru.tur_kos)
    assert list(gercek.parameters) == list(beklenen.parameters)
    for ad, param in beklenen.parameters.items():
        assert gercek.parameters[ad].kind == param.kind, ad
        assert gercek.parameters[ad].default == param.default, ad


def test_musait_mi_ikiliye_bakar(monkeypatch):
    assert CodexMotoru(calistirilabilir="codex-sahte.exe").musait_mi() is True
    monkeypatch.setattr("shutil.which", lambda _ad: None)
    monkeypatch.delenv("OFIS_CODEX_YOLU", raising=False)
    assert CodexMotoru().musait_mi() is False


# -- 2) normal akis --------------------------------------------------------


def test_normal_akis_bitti_ile_kapanir(monkeypatch, klasor):
    motor = _motor(monkeypatch, lambda *a, **k: SahteSurec(NORMAL_AKIS, cikis=0))
    olaylar = _olaylar(motor, klasor)

    assert all(isinstance(o, MotorOlayi) for o in olaylar)
    assert olaylar[0].tur == "basladi"
    assert olaylar[-1].tur == "bitti"
    assert olaylar[-1].ek["basarili"] is True
    assert "is bitti" in olaylar[-1].govde
    # Oturum kimligi motordan dogar: `thread.started` satiri.
    assert olaylar[-1].ek["oturum_id"] == "01a0b57a-0000-7000-8000-000000000000"
    assert [o.tur for o in olaylar if o.tur == "hata"] == []


def test_brifing_stdinden_gecer_argumandan_degil(monkeypatch, klasor):
    kayit = {}

    def sahte_popen(komut, **kwargs):
        kayit["komut"] = komut
        return SahteSurec(NORMAL_AKIS, cikis=0)

    motor = _motor(monkeypatch, sahte_popen)
    _olaylar(motor, klasor)

    komut = kayit["komut"]
    assert komut[1] == "exec" and komut[-1] == "-"
    for bayrak in ("--json", "--strict-config", "--skip-git-repo-check",
                   "-C", "-s"):
        assert bayrak in komut, bayrak
    assert komut[komut.index("-s") + 1] == "workspace-write"
    assert not any("brifing" in str(a) for a in komut)


def test_resume_alt_komutunda_sandbox_bayragi_kullanilmaz(monkeypatch, klasor):
    """OLCULDU: `codex exec resume` -C/-s/--add-dir KABUL ETMEZ."""
    kayit = {}

    def sahte_popen(komut, **kwargs):
        kayit["komut"] = komut
        return SahteSurec(NORMAL_AKIS, cikis=0)

    motor = _motor(monkeypatch, sahte_popen)
    list(motor.tur_kos(
        "brifing", klasor=str(klasor),
        oturum_id="01a0b57a-0000-7000-8000-000000000000",
        ek_klasorler=(str(klasor),),
    ))

    komut = kayit["komut"]
    assert komut[1:3] == ["exec", "resume"]
    for yasak in ("-s", "-C", "--add-dir"):
        assert yasak not in komut, yasak
    assert 'sandbox_mode="workspace-write"' in komut


def test_kafa_ajan_read_only_kosar(monkeypatch, klasor):
    kayit = {}

    def sahte_popen(komut, **kwargs):
        kayit["komut"] = komut
        return SahteSurec(NORMAL_AKIS, cikis=0)

    motor = _motor(monkeypatch, sahte_popen)
    list(motor.tur_kos("brifing", klasor=str(klasor), yazabilir=False))
    komut = kayit["komut"]
    assert komut[komut.index("-s") + 1] == "read-only"


# -- 3) hata yollari: son olay yine `bitti` --------------------------------


def test_cikis_kodu_sifir_degilse_de_bitti_gelir(monkeypatch, klasor):
    motor = _motor(
        monkeypatch,
        lambda *a, **k: SahteSurec(NORMAL_AKIS[:2], cikis=1,
                                   hata_satirlari=["cokme\n"]),
    )
    olaylar = _olaylar(motor, klasor)

    assert olaylar[-1].tur == "bitti"
    assert olaylar[-1].ek["basarili"] is False
    assert olaylar[-1].ek["cikis"] == 1
    assert any(o.tur == "hata" for o in olaylar)


def test_surec_baslatilamazsa_da_bitti_gelir(monkeypatch, klasor):
    def patlat(*a, **k):
        raise OSError("boyle bir dosya yok")

    motor = _motor(monkeypatch, patlat)
    olaylar = _olaylar(motor, klasor)

    assert olaylar[-1].tur == "bitti"
    assert olaylar[-1].ek["basarili"] is False
    assert olaylar[-1].ek["sebep"] == "motor_yok"


def test_motor_kurulu_degilse_de_bitti_gelir(klasor):
    motor = CodexMotoru(calistirilabilir="")
    motor.calistirilabilir = ""  # musait_mi -> False yolu
    olaylar = list(motor.tur_kos("brifing", klasor=str(klasor)))

    assert motor.musait_mi() is False
    assert olaylar[-1].tur == "bitti"
    assert olaylar[-1].ek["basarili"] is False
    assert olaylar[-1].ek["sebep"] == "motor_yok"


def test_akis_ortasinda_istisna_yutulur_ve_bitti_gelir(monkeypatch, klasor):
    """Okuma katmani patlasa bile tur kapanmali -- kapanmayan tur kilit tutar."""
    class PatlayanSurec(SahteSurec):
        def wait(self, timeout=None):
            raise RuntimeError("beklenmeyen surec hatasi")

    motor = _motor(monkeypatch,
                   lambda *a, **k: PatlayanSurec(NORMAL_AKIS, cikis=0))
    olaylar = _olaylar(motor, klasor)

    assert olaylar[-1].tur == "bitti"
    assert olaylar[-1].ek["basarili"] is False
    assert any(o.tur == "hata" for o in olaylar)


def test_limit_olayi_bitti_ile_kapanir(monkeypatch, klasor):
    akis = [
        '{"type":"thread.started","thread_id":"01a0b57a-0000-7000-8000-000000000000"}\n',
        '{"type":"turn.failed","error":{"message":"You\'ve hit your usage limit."}}\n',
    ]
    motor = _motor(monkeypatch, lambda *a, **k: SahteSurec(akis, cikis=1))
    olaylar = _olaylar(motor, klasor)

    assert any(o.tur == "limit" for o in olaylar)
    assert olaylar[-1].tur == "bitti"
    assert olaylar[-1].ek["limit"] is True
    assert olaylar[-1].ek["basarili"] is False


# -- girdi ihlali: tur hic baslamaz, istisna atilir ------------------------


def test_bos_brifing_ve_olmayan_klasor_istisna_atar(klasor):
    motor = CodexMotoru(calistirilabilir="codex-sahte.exe")
    with pytest.raises(MotorHatasi):
        list(motor.tur_kos("   ", klasor=str(klasor)))
    with pytest.raises(MotorHatasi):
        list(motor.tur_kos("brifing", klasor=str(klasor / "yok")))
