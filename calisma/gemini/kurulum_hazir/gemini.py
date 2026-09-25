import os
import subprocess
import shutil
import json
from pathlib import Path
from typing import Iterator

from .tip import Motor, MotorOlayi, MotorHatasi

_PENCERE_YOK = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_VARSAYILAN_ZAMAN_ASIMI = 300.0


class GeminiMotoru(Motor):
    ad = "gemini"
    mcp_konusur = False
    butce_destegi = False

    def __init__(self, *, calistirilabilir: str = "",
                 zaman_asimi: float = _VARSAYILAN_ZAMAN_ASIMI) -> None:
        self.calistirilabilir = calistirilabilir if calistirilabilir else self._calistirilabilir_bul()
        self.zaman_asimi = zaman_asimi

    @staticmethod
    def _calistirilabilir_bul() -> str:
        """Gerçek ikiliyi bulur, `.CMD` sarmalayıcısını ATLAR.

        Sebep: cmd.exe satır sonlu argümanı keser ve sonraki bayrakları
        sessizce düşürür. node_modules altındaki gerçek executable'ı çağırmak
        hem sarmalayıcıyı hem tuzağı ortadan kaldırır.
        """
        yol = os.environ.get("OFIS_GEMINI_YOLU", "").strip()
        if yol and Path(yol).exists():
            return yol
        bulunan = shutil.which("gemini") or ""
        if not bulunan:
            return ""
        if Path(bulunan).suffix.lower() in (".cmd", ".bat"):
            parent_dir = Path(bulunan).parent / "node_modules"
            if parent_dir.exists():
                for entry in parent_dir.iterdir():
                    if entry.is_dir() and (entry.name.startswith("@google") or
                                           entry.name.startswith("google")):
                        gercek = entry / "bin" / "gemini.exe"
                        if gercek.exists():
                            return str(gercek)
        return bulunan

    def _arguman_dogrula(self, komut: list) -> None:
        """Satır sonlu argüman + `.CMD` birleşimini REDDEDER.

        cmd.exe satır sonlu argümanı komut ayırıcı sayar ve SONRAKI BUTUN
        BAYRAKLARI sessizce düşürür. Bu kontrol, ölçülmüş bir sessiz
        bozulmanın nöbetçisidir.
        """
        if Path(self.calistirilabilir).suffix.lower() not in (".cmd", ".bat"):
            return
        for arguman in komut[1:]:
            if chr(10) in arguman or chr(13) in arguman:
                raise MotorHatasi(
                    "Satir sonu tasiyan arguman .CMD sarmalayicisindan gecirilemez: "
                    "cmd.exe onu komut ayricisi sayar ve SONRAKI BUTUN BAYRAKLARI "
                    "sessizce dusurur (izin modu, model, arac listesi dahil). "
                    "node_modules altindaki gercek gemini.exe dogrudan cagrilmali ya da "
                    "OFIS_GEMINI_YOLU ayarlanmali."
                )

    def musait_mi(self) -> bool:
        return bool(self.calistirilabilir)

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

        if butce_usd:
            raise MotorHatasi(
                "gemini tur basina butce tavani uygulayamaz "
                "(gemini --help'de boyle bir bayrak yok). Butce sinirini kaldir ya da "
                "bu isi butce destekleyen bir motora ver (claude). "
                "Sessizce yok sayilan ayar, ayar degildir."
            )

        if efor != "normal":
            raise MotorHatasi(
                f"gemini efor seviyesi uygulayamaz (bayrak yok: gemini --help'de "
                f"model_reasoning_effort karsiligi bulunmadi). Efor=normal ile kosurun."
            )

        approval_mode = "plan" if not yazabilir else "default"

        if zaman_asimi:
            raise MotorHatasi(
                "gemini zaman_asimi (timeout) uygulayamaz "
                "(gemini --help'de timeout bayrak yok)."
            )

        if not os.environ.get("GEMINI_API_KEY"):
            raise MotorHatasi(
                "GEMINI_API_KEY ortam degiskeni ayarlanmamis. "
                "Gemini CLI'nin API anahtarini icin bu degiskeni set edin."
            )

        komut = [self.calistirilabilir, "-p", metin]

        if oturum_id:
            komut.extend(["--session-id", oturum_id])

        if model:
            komut.extend(["--model", model])

        if ek_klasorler:
            for klasor_ek in ek_klasorler:
                komut.extend(["--include-directories", str(klasor_ek)])

        if mcp_yapilandirma:
            raise MotorHatasi(
                "gemini mcp_yapilandirma uygulayamaz "
                "(gemini --help'de --allowed-mcp-server-names sadece sunucu ADLARI, "
                "yapilandirma DEGIL). JSON'da verilen sunucu command/args/env tamamen "
                "atilir, sessizce yanlis uygulanir. Durustce reddediliyor."
            )

        if izinli_araclar:
            for arac in izinli_araclar:
                komut.extend(["--allowed-tools", str(arac)])

        komut.extend(["--skip-trust"])
        komut.extend(["--approval-mode", approval_mode])
        komut.extend(["--output-format", "json"])

        self._arguman_dogrula(komut)

        env = os.environ.copy()

        try:
            process = subprocess.Popen(
                komut,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(kok),
                env=env,
                creationflags=_PENCERE_YOK,
            )

            cikti = []
            for satir in process.stdout:
                if satir.strip():
                    cikti.append(satir.rstrip("\n\r"))
                    yield MotorOlayi("nabiz", "", {})

            stderr_metni = process.stderr.read()
            process.wait()

            if process.returncode == 0:
                yield MotorOlayi(
                    "bitti",
                    "\n".join(cikti),
                    {"basarili": True},
                )
            else:
                yield MotorOlayi(
                    "bitti",
                    "",
                    {"basarili": False, "sebep": "cikis", "hata": stderr_metni},
                )

        except FileNotFoundError:
            yield MotorOlayi(
                "bitti",
                "",
                {"basarili": False, "sebep": "motor_yok", "hata": "Gemini CLI bulunamadi"},
            )
        except Exception as e:
            yield MotorOlayi(
                "bitti",
                "",
                {"basarili": False, "sebep": "surec", "hata": str(e)},
            )
