# -*- coding: utf-8 -*-
"""Sahte motor: jeton yakmadan kosan, senaryosu onceden yazilmis adaptor.

Neden bir sahte motor cekirdegin parcasi:

* **Duman testi gercek CLI'a bagli kalmamali.** Koltuk, tahta, kilit ve
  kanit kapisi test edilirken sinanan sey KOORDINASYON'dur, modelin
  zekasi degil. Gercek motorla kosan bir test yavas, pahali ve
  tekrarlanamaz olur; basarisiz oldugunda da hatanin bizde mi modelde mi
  oldugu bilinemez.

* **Kenar durumlari ancak boyle uretilir.** Zaman asimi, kullanim limiti,
  izin reddi, yarida olen surec -- gercek motorda bunlari istege bagli
  uretemezsin. Burada `senaryo` ile uretilir. Yasa 3'un en buyuk hata
  kumesi (%41,8 belirtim/sistem tasarimi) tam da bu yollarda saklanir.

* **Panel bos veriyle tasarlanmaz.** Arayuzu cizerken akan gercek bir
  olay akisi gerekir; sahte motor onu bedavaya verir.
"""

from __future__ import annotations

import time
import uuid
from typing import Iterator

from .tip import Motor, MotorOlayi, MotorHatasi

#: Hazir senaryolar. Anahtar, `tur_kos`a `model` alani uzerinden gecilir --
#: boylece sahte motor gercek motorla AYNI sozlesmeyi kullanir, testin
#: ozel bir yola sapmasi gerekmez.
SENARYOLAR = ("basarili", "hata", "limit", "zaman_asimi", "izin_reddi", "sessiz")


class SahteMotor(Motor):
    """Onceden yazilmis bir olay akisini, gercek motor gibi akitir."""

    ad = "sahte"

    def __init__(self, *, senaryo: str = "basarili", gecikme: float = 0.0,
                 mcp_konusur: bool = False,
                 cevap: str = "Is bitti. Kanit: `pytest -q` -> 9 passed.") -> None:
        # Varsayilan KAPALI: sahte motor bir MCP istemcisi degildir, arac
        # cagiramaz. Acik hali, koltugun MCP yolunu sinamak icindir.
        self.mcp_konusur = mcp_konusur
        if senaryo not in SENARYOLAR:
            raise MotorHatasi(f"Bilinmeyen senaryo: {senaryo}")
        self.senaryo = senaryo
        self.gecikme = gecikme
        self.cevap = cevap
        #: Cagrilarin kaydi -- test "koltuk motora ne verdi" diye sorabilsin.
        self.cagrilar = []

    def musait_mi(self) -> bool:
        return True

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
        senaryo = model if model in SENARYOLAR else self.senaryo
        oturum = oturum_id or str(uuid.uuid4())
        self.cagrilar.append({
            "metin": metin, "klasor": klasor, "oturum_id": oturum_id,
            "efor": efor, "yazabilir": yazabilir, "senaryo": senaryo,
            "mcp_yapilandirma": mcp_yapilandirma,
            "izinli_araclar": tuple(izinli_araclar or ()),
        })

        yield MotorOlayi("basladi", "sahte tur basladi",
                         {"oturum_id": oturum, "devam": bool(oturum_id),
                          "klasor": klasor})
        yield MotorOlayi("oturum", "sahte-model",
                         {"oturum_id": oturum, "model": "sahte-model"})

        if senaryo == "sessiz":
            # Motor hicbir sey soylemiyor ama hayatta: koltugun nabiz
            # atmayi surdurup surdurmedigini sinar.
            for _ in range(3):
                if self.gecikme:
                    time.sleep(self.gecikme)
                yield MotorOlayi("nabiz", "", {"gecen_s": 1.0})

        if senaryo == "izin_reddi":
            yield MotorOlayi("arac", "Write", {"ozet": "gizli/ayarlar.json"})
            yield MotorOlayi(
                "izin", "permission denied: yazma alani disi",
                {"hatali": True},
            )

        if senaryo in ("basarili", "zaman_asimi", "hata"):
            yield MotorOlayi("arac", "Read", {"ozet": "BRIFING.md"})
            yield MotorOlayi("arac_sonuc", "4 katman okundu", {"hatali": False})
            for parca in self.cevap.split(" "):
                if self.gecikme:
                    time.sleep(self.gecikme)
                yield MotorOlayi("metin", parca + " ")

        if senaryo == "limit":
            yield MotorOlayi("limit", "exhausted", {"status": "exhausted"})
            yield MotorOlayi("hata", "Hesap kullanim limitine ulasildi.",
                             {"sebep": "limit"})
        elif senaryo == "zaman_asimi":
            yield MotorOlayi("hata", "Tur 1800 saniyede bitmedi, surec kesildi.",
                             {"sebep": "zaman_asimi"})
        elif senaryo == "hata":
            yield MotorOlayi("hata", "Tur basarisiz (cikis 1): sahte hata",
                             {"sebep": "cikis", "cikis": 1})

        basarili = senaryo in ("basarili", "izin_reddi", "sessiz")
        yield MotorOlayi(
            "bitti",
            self.cevap if basarili else "",
            {
                "basarili": basarili,
                "oturum_id": oturum,
                "model": "sahte-model",
                "cikis": 0 if basarili else 1,
                "sure_ms": 1.0,
                "maliyet_usd": 0.0,
                "jeton": len(metin) // 3,
                "arac_sayisi": 1,
                "limit": senaryo == "limit",
                "zaman_asimi": senaryo == "zaman_asimi",
            },
        )
