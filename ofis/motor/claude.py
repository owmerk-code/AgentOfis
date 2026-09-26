# -*- coding: utf-8 -*-
"""Claude Code adaptoru: `claude` CLI'ini stream-json modunda kosturur.

Calisan kodu yeniden yazmadik -- surec yonetimi JarvisForge'daki
`apps/jarvis/jarvis/claude_code.py`'den odunc alindi (Popen + okuyucu
iplik + surec agacini sonlandirma). Degistirilen yerler ve SEBEPLERI:

* **Yazma acik, ama hapiste.** Jarvis'te bu istemci salt-okunurdu; orada
  Claude bir danismandi. Burada calisandir, dosya yazmasi gerekir. Yazmayi
  guvenli kilan sey iyi niyet degil uc kapi: `--restricted` dosya
  araclarini calisma klasorune hapseder, `--permission-prompts none` izin
  isteyen her seyi reddeder, ve gorevin yazma alani zaten `yazma_kilidi`
  tablosunda kilitlidir.

* **Izin sorusu asilamaz.** `-p` modunda bir arac izin isterse ve cevap
  verecek kimse yoksa surec bekler; panelde bu "calisiyor" gorunur, oysa
  is olmustur. En sinsi hata turu budur: sistem saglikli gorunurken hicbir
  sey ilerlemez. `--permission-prompts none` bunu sessiz beklemeden
  ACIK REDDE cevirir -- red bir olaya donusur, gorunur olur.

* **Sessizlik olaya cevrilir.** Motor uzun sure konusmadiginda saniyede
  bir `nabiz` olayi akitilir. Sebep: yazma kilidi bir kiradir (db.py),
  nabiz gecmezse duser. Uzun dusunen bir ajanin kilidini kaybetmesi,
  isini yarida baska birine kaptirmasi demektir.

* **Denetci yok.** Jarvis'in `process_supervisor`i burada yok; ofiste
  surecin sagligini koltuk izler, cunku kilidi ve gorev durumunu o tutar.

WINDOWS -- iki ayri tuzak, ikisi de SESSIZ:

1. **`.CMD` sarmalayicisi satir sonlu argumani bozar.** OLCULDU: PATH'teki
   `claude` bir npm `.CMD` dosyasidir ve `cmd.exe` uzerinden kosar.
   Argumanlardan biri satir sonu tasirsa (bizde `--append-system-prompt`),
   cmd.exe onu KOMUT AYRACI sayar ve ONDAN SONRAKI BUTUN BAYRAKLARI
   dusurur. Hata cikmaz: surec `rc=0` doner, akis normal gorunur --
   ama `--permission-mode`, `--model`, `--allowedTools` hic ulasmamistir.
   Olcum: ayni istek, ayni bayraklar, tek fark sistem ekindeki `
`:
       .CMD -> model=opus, izin=default,     dosya YAZILMADI
       .exe -> model=haiku, izin=acceptEdits, dosya YAZILDI
   Cozum: `.CMD` atlanir, `bin/claude.exe` DOGRUDAN cagrilir. Ustune
   `_arguman_dogrula` kapisi konur ki bu tuzak bir daha sessizce
   kurulamasin.

2. **Surec agaci.** Yalniz dogrudan cocugu sonlandirmak node alt surecini
   oksuz birakir ve her turdan sonra bir surec sizar --
   `_surec_agacini_kes` bu yuzden var.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Iterator

from .tip import (ortam_hazirla, limit_penceresi, Motor, MotorOlayi,
                  MotorHatasi, MotorYokHatasi, SurecKafesi)

_PENCERE_YOK = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_SON = object()

#: Turun ust siniri. Sonsuz bekleyen bir tur, kilidi de sonsuza kadar
#: tutar; zaman asimi bu yuzden mimari bir kapidir, konfor degil.
VARSAYILAN_ZAMAN_ASIMI = 1800.0

#: Motor sessizken kac saniyede bir `nabiz` olayi akitilacak.
NABIZ_ARALIGI = 1.0

#: Bizim uc kademeli eforumuz (db.py) ile CLI'nin kademeleri arasindaki
#: cevrim. Cekirdek CLI'nin sozlugunu ogrenmek zorunda kalmasin diye
#: burada durur.
EFOR_CEVRIMI = {"dusuk": "low", "normal": "medium", "yuksek": "high",
                "cok_yuksek": "xhigh"}   # `max` BILEREK YOK (kullanici karari)

#: 'eller' ajanin kullanabilecegi araclar. `--restricted` komut calistiran
#: araclari kaldirir; Bash'i geri getirmek icin ADIYLA saymak gerekir.
#: Acikca sayilmasi iyidir: bir ajanin neye gucu yettigi tahmin edilmez.
ELLER_ARACLARI = "Read,Glob,Grep,Edit,Write,Bash,TodoWrite,WebSearch,WebFetch"

#: 'kafa' ajanin araclari. Yazan hicbir arac yok -- kural brifingde rica
#: edilmez, surec duzeyinde uygulanir. Yazma yasagini TASIYAN sey bu
#: liste: Write/Edit/Bash burada olmadigi icin ajan yazamaz. Izin kipine
#: ya da brifing metnine bagli degildir.
KAFA_ARACLARI = "Read,Glob,Grep,WebSearch,WebFetch"

#: 'kafa' ajanin IZIN listesi. OLCULDU (19.09.2026): plan kipi, acikca
#: izin verilmeyen her araci reddeder -- `--tools`ta bulunmasi yetmez.
#: Yani `tur='kafa'` olan ARASTIRMA ajani arama yapamiyordu: tanimi
#: geregi yapmasi gereken isi yapamiyordu. Kod isinde hic gorunmedi
#: cunku kod isi arama yapmaz.
#:
#: Yasa 5'in kastettigi sinir "yargi ve dosya yazma verilmez"di,
#: "okuyamaz" degil. Buradaki her arac SALT OKUNUR; plan kipi yazmayi
#: zaten surec duzeyinde kapali tutuyor, yani yazma yasagi bu listeyle
#: gevsemez -- iki kat kapali olan sey aciliyor degil, YANLIS kapali
#: olan sey duzeltiliyor.
#: `mcp__ofis`: ofisin KENDI araclari (kanit_ekle, soru_sor, onay_iste...).
#: Bunlar izin listesinde olmak ZORUNDA -- yoksa ajan kanit ekleyemez ve
#: kanit kapisi hicbir isi kapatamaz.
#:
#: OLCULDU ve BU HATAYI BEN YAPTIM (19.09.2026): `kafa` icin izin listesi
#: eklerken ofis araclarini unuttum. Onceden liste YOKTU, plan kipi MCP
#: aracina dokunmuyordu; liste gelince ofis araclari da disarida kaldi.
#: Sonraki gercek arastirma isinde goruldu:
#:     izin: mcp__ofis__kanit_ekle reddedildi: baslik, icerik, tur
#: Ajan isi yapti, kanit ekleyemedi, is kanitsiz kaldi. **Bir seyi
#: kisitlarken kisitlamak ISTEMEDIGIN seyi de kisitlarsin.**
#:
#: Erisim izni burada, YETKI sunucuda: `gorev_ac` zaten yalnizca lidere
#: aciktir ve kimlik ortamdan gelir. Iki kati ayri tutmak dogru katmanlama
#: -- burada "ulasabilir mi", orada "hakki var mi".
OFIS_ARACLARI = ("mcp__ofis",)

KAFA_IZINLI = ("Read", "Glob", "Grep", "WebSearch", "WebFetch") + OFIS_ARACLARI

#: Sorulmadan kosturulabilecek komutlar. OLCULDU: `acceptEdits` dosya
#: yazmaya izin verir ama komut calistirmaya VERMEZ; izin isteyen Bash
#: cagrisi `--permission-prompts none` ile reddedilir. Ilk gercek turda
#: ajan hesap.py ve testini yazdi ama `pytest`i kosturamadi -- yani
#: TERMINAL KANITI URETEMEDI ve kanit kapisi (dogru davranarak) isi
#: kapatmadi. Kanit kapisi calisacaksa ajanin test kosturabilmesi sart.
#:
#: Cozum listeyi acmak DEGIL, listeyi YAZMAK: ofisin kurali "kod yazmak
#: sormaz; para harcamak, yayina almak, disariya yazmak sorar" (db.py,
#: `onay` tablosu). Burasi o kuralin komut tarafi. Listede olmayan her
#: komut reddedilir ve gorunur bir `izin` olayina donusur -- Ofis MCP
#: sunucusu gelince ayni red, `onay` tablosuna dusup insana sorulacak.
#:
#: Yazma zaten `--restricted` ile ajanin klasorune hapis oldugundan, bu
#: komutlar o klasorun disina cikamaz.
#: OLCULDU (19.09.2026): `WebSearch` ve `WebFetch` `--tools` listesinde
#: vardi ama IZIN listesinde yoktu -- yani arac ajana taniniyor, kullanmasi
#: reddediliyordu. Gercek turda olculdu: ajan aramayi denedi, "izin
#: alinamadi" dedi ve ISI YAPAMADAN turu bitirdi. Kod isinde hic
#: gorunmuyordu cunku kod isi arama yapmaz; ARASTIRMA isinde sistem
#: tamamen calismaz halde.
#:
#: Ikisi de SALT OKUNUR. Ofisin kurali "kod yazmak sormaz; para harcamak,
#: yayina almak, disariya yazmak sorar" -- okumak sormaz. Web'den okumak
#: da okumaktir.
ELLER_IZINLI = (
    "Edit", "Write", "Read", "Glob", "Grep", "TodoWrite",
    "WebSearch", "WebFetch", "mcp__ofis",
    "Bash(python *)", "Bash(python3 *)", "Bash(py *)",
    "Bash(pytest *)", "Bash(python -m pytest *)", "Bash(python -m *)",
    "Bash(node *)", "Bash(npm test*)", "Bash(npm run *)",
    "Bash(ls *)", "Bash(ls)", "Bash(dir *)", "Bash(cat *)", "Bash(type *)",
    "Bash(mkdir *)", "Bash(echo *)", "Bash(pwd)",
    "Bash(git status*)", "Bash(git diff*)", "Bash(git log*)", "Bash(git add*)",
)

#: Hesabin kullanim limiti sinyalinde SORUN OLMAYAN durumlar. CLI uyari
#: da yollar ("yaklasiyorsun"); uyariyi limit saymak, calisan bir turu
#: bosuna basarisiz ilan eder. Yalnizca gercekten REDDEDILMIS olan sayilir.
LIMIT_SAYILMAYAN = ("", "allowed", "allowed_warning", "ok")


def claude_pencereleri(bilgi) -> dict | None:
    """`rate_limit_event.rate_limit_info` -> ortak bicim (`tip.limit_penceresi`).

    OLCULDU (23.09.2026, gercek tur):
      {"status": "allowed_warning", "rateLimitType": "seven_day",
       "utilization": 0.81, "resetsAt": 1790132400,
       "unifiedWindows": {"five_hour": {"utilization": 0.71, "resetsAt": ...},
                          "seven_day": {"utilization": 0.81, "resetsAt": ...}}}

    `unifiedWindows` yoksa tek pencereli bicim (`rateLimitType`) okunur.
    Taninmayan pencere adi ATILMAZ, kendi adiyla tasinir -- saglayici
    yarin yeni bir pencere eklerse sessizce kaybolmasin.
    """
    if not isinstance(bilgi, dict):
        return None
    adlar = {"five_hour": "5s", "seven_day": "7g"}
    pencereler = {}
    for anahtar, p in (bilgi.get("unifiedWindows") or {}).items():
        if isinstance(p, dict):
            pencereler[adlar.get(anahtar, anahtar)] = {
                "kullanim": p.get("utilization"), "yenilenme": p.get("resetsAt")}
    if not pencereler and bilgi.get("rateLimitType"):
        t = str(bilgi["rateLimitType"])
        pencereler[adlar.get(t, t)] = {"kullanim": bilgi.get("utilization"),
                                       "yenilenme": bilgi.get("resetsAt")}
    return limit_penceresi(pencereler, kaynak="claude CLI (rate_limit_event)",
                           hal=str(bilgi.get("status") or ""))

#: Ajan turunun ortami. OLCULDU: bunlar ayarlanmadan kosan turda akista
#: `ToolSearch` belirdi ("No matching deferred tools found") ve ardindan
#: `Write` REDDEDILDI -- arac arama modu araclari erteleyerek yukledigi
#: icin izin kurallari dogru baglanmiyor. Ajan kodu hazirladi, tek dosya
#: yazamadi. Tur ortami bu yuzden ACIKCA kurulur: varsayilana guvenmek,
#: makineden makineye degisen bir davranisa guvenmektir.
#: (Ayni degiskenler JarvisForge'da da bu sebeple ayarlaniyor.)
TUR_ORTAMI = {
    "ENABLE_TOOL_SEARCH": "false",          # araclar ertelenmesin, hepsi acik gelsin
    "ENABLE_CLAUDEAI_MCP_SERVERS": "false", # hesabin connector'lari yuklenmesin
    "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",  # tur bitince arka is kalmasin
}

#: Brifingin ustune eklenen kisa durus. Brifing ISI anlatir; bu metin
#: ajanin hangi evde oldugunu anlatir. Kisa tutuluyor: her jeton brifingin
#: dort katmanindan calinmis demektir.
#: OLCULDU: "kanit ver" demek yetmiyor. Ilk gercek turda ajan isi dogru
#: yapti (`pytest` -> 4 passed) ama kanit satirini yazmadi; kanit kapisi
#: da -- dogru davranarak -- isi kapatmadi. Is bitmisti, defterde
#: bitmemis gorunuyordu. Ders: bir kural ancak BICIMIYLE birlikte
#: verilirse uygulanir. Ricanin yerini sablon alir.
SISTEM_EKI_ORTAK = (
    "AgentOfis'te bir ajansin. Baglamin klasorundeki BRIFING.md dosyasidir; "
    "uzun bir iste savrulursan geri donup oku. "
    "Turkce yaz. "
    "Yalniz brifingdeki YAZMA ALANI icine yaz -- disina cikma; o alanlar "
    "baska ajanlara kilitli olabilir."
)

#: MCP varken: kanit bir ARAC CAGRISIDIR ve BIRIKTIREREK eklenir.
#:
#: OLCULDU (19.09.2026): "isi bitirince kanitini ekle" diyordu. Arastirma
#: turu butce tavanina takilip kesildi; 17 arama, 208.148 jetonluk yapilmis
#: is vardi ve SIFIR kanit dustu -- hepsi sona birakilmisti. Is bastan
#: kosulmak zorunda kaldi.
#:
#: Kanit bir TESLIMAT degil, bir DEFTER KAYDIDIR. Defter is bitince
#: doldurulmaz, is ilerledikce doldurulur. Boylece kesinti SONU
#: kaybettirir, her seyi degil.
#:
#: Tek kanal olmasi da onemli --
#: olculdu: iki kanal acik birakildiginda ajan ikisini de kullandi ve
#: ayni is icin ALTI kanit dustu, ucu cift. Cift kanit incelemeyi
#: zorlastirir ve "kac kanit var" olcutunu bozar.
KANIT_MCP = (
    "\n\n"
    "KANITI ISI BITIRINCE DEGIL, HER ADIMDA EKLE: bir seyi dogruladigin "
    "an `ofis` aracinin `kanit_ekle` cagrisini yap, sonra devam et. "
    "Testi kosturdun ve gecti -> hemen ekle. Bir kaynak buldun ve "
    "dogruladin -> hemen ekle. Bir dosyayi bitirdin -> hemen ekle. "
    "Sebep: tur SENIN ELINDE OLMAYAN sebeplerle kesilebilir -- butce "
    "tavani, kullanim limiti, zaman asimi. Kesildiginde eklenmemis her "
    "sey KAYBOLUR ve o is bastan kosulur. Eklenmis kanit KALICIDIR. "
    "Kanitsiz gorev kapanmaz -- yaptigin is defterde yapilmamis sayilir. "
    "Kanit satirini METIN olarak YAZMA, araci CAGIR. "
    "Her kanit ayri bir cagridir: kosturdugun komut ve gercek ciktisi, "
    "degistirdigin her dosya, dogruladigin her kaynak. "
    "Takilirsan `soru_sor`, riskli bir adim gerekiyorsa `onay_iste` "
    "araclarini kullan ve sonra DUR. Bir sey degisti mi diye merak "
    "edersen `durum` aracina bak. "
    "Ciktiyi UYDURMA: yalnizca gercekten kosturdugun komutun gercek "
    "ciktisini yaz. Uydurma kanit incelemede yakalanir ve siciline duser."
)

#: MCP yokken gecerli KOPRU. Motorun MCP destegi yoksa ya da yapilandirma
#: verilmediyse kanit tek yoldan gelir: metin. Kopru duruyor cunku motor
#: katmani "fise takilir" -- yarinki bir motor MCP konusmayabilir.
#:
#: BILINEN SINIR: metin koprusu BIRIKTIREMEZ. Metin ancak turun sonunda
#: gelir; tur kesilirse kanit da kesilir. Bu kopru bir SINIRDIR, tercih
#: degil -- ve MCP konusan motorlarda kopru zaten kullanilmaz. Sinirin
#: yazili olmasi, birgun MCP konusmayan bir motorla arastirma isi
#: kosturulunca "neden kanit yok" sorusunu cevaplar.
KANIT_METIN = (
    "\n\n"
    "ISI BITIRINCE KANIT SATIRI YAZMAK ZORUNDASIN. Kanitsiz gorev "
    "kapanmaz. Son mesajinin sonuna, her kanit icin ayri satir olarak, "
    "TAM OLARAK su bicimde yaz:"
    "\n\n"
    "KANIT terminal: <kosturdugun komut> -> <ciktinin ozeti>\n"
    "KANIT dosya: <yol> -> <ne yaptin>"
    "\n\n"
    "Ornek:\n"
    "KANIT terminal: python -m pytest testler -q -> 4 passed in 0.02s"
    "\n\n"
    "Ciktiyi UYDURMA: yalnizca gercekten kosturdugun komutun gercek "
    "ciktisini yaz."
)

#: Geriye donuk ad -- eski cagiranlar ve testler icin.
SISTEM_EKI = SISTEM_EKI_ORTAK + KANIT_METIN


def _kip(izin_araci: str) -> list:
    """Izin kipi -- kanca varken VERILMEZ.

    OLCULDU (22.09.2026), uc kosu, ayni istem (`dosya yaz, sonra
    `rm` ile sil`):

    | ayar                                  | kanca | `rm` |
    |---------------------------------------|-------|------|
    | `acceptEdits` + `--permission-prompts none` | 0 kez | CALISTI |
    | kanca + `acceptEdits`                  | 0 kez | CALISTI |
    | **kanca, kip verilmeden**              | 2 kez | ENGELLENDI |

    Iki sonuc cikti ve ikincisi daha agir:

    1. `acceptEdits` izin kancasini TAMAMEN devre disi birakiyor.
    2. **Bugunku ayarimiz keyfi kabuk komutu kosturuyordu.** Bu
       dosyada aylardir su yaziyordu:

           "acceptEdits dosya yazmaya izin verir ama komut
            calistirmaya VERMEZ; izin isteyen Bash cagrisi
            `--permission-prompts none` ile reddedilir."

       Bir zamanlar dogruydu; CLI degisti ve iddia BAYATLADI.
       `ELLER_IZINLI` boylece gercek bir kapi olmaktan cikip DEKOR
       olmustu -- liste disi bir komut sessizce kosuyordu ve kimse
       fark etmiyordu. Tam olarak bu projenin karsi kuruldugu sinif:
       *sistem saglikli gorunurken yanlis calisiyor.*

    Kanca yoksa eski davranis korunur: baska bir kapi olmadigi icin
    `acceptEdits` hala en iyisi. Kanca varsa kip VERILMEZ ve karar
    ofise gecer.
    """
    return [] if izin_araci else ["--permission-mode", "acceptEdits"]


class ClaudeMotoru(Motor):
    """`claude` CLI'ini tur basina bir surec olarak kosturur."""

    ad = "claude"
    mcp_konusur = True
    butce_destegi = True   # --max-budget-usd
    araclar_kapatilabilir = True
    izin_kancasi = True   # --tools ""

    def __init__(self, *, calistirilabilir: str = "",
                 zaman_asimi: float = VARSAYILAN_ZAMAN_ASIMI) -> None:
        self.calistirilabilir = calistirilabilir or self._calistirilabilir_bul()
        self.zaman_asimi = zaman_asimi

    @staticmethod
    def _calistirilabilir_bul() -> str:
        """Gercek ikiliyi bulur, `.CMD` sarmalayicisini ATLAR.

        Sebep dosya basindaki 1. tuzak: cmd.exe satir sonlu argumani
        keser ve sonraki bayraklari sessizce dusurur. `.CMD` icerigi
        zaten tek satirdir: bin/claude.exe cagirir. Dogrudan onu cagirmak
        hem sarmalayiciyi hem tuzagi ortadan kaldirir.
        """
        yol = os.environ.get("OFIS_CLAUDE_YOLU", "").strip()
        if yol and Path(yol).exists():
            return yol
        bulunan = shutil.which("claude") or ""
        if not bulunan:
            return ""
        if Path(bulunan).suffix.lower() in (".cmd", ".bat"):
            gercek = (Path(bulunan).parent / "node_modules" / "@anthropic-ai"
                      / "claude-code" / "bin" / "claude.exe")
            if gercek.exists():
                return str(gercek)
        return bulunan

    def _arguman_dogrula(self, komut: list) -> None:
        """Satir sonlu arguman + `.CMD` birlesimini REDDEDER.

        Bu kontrol, olculmus bir sessiz bozulmanin nobetcisidir. Uyari
        vermek yetmez: bozulma sessiz oldugu icin uyari da okunmaz.
        """
        if Path(self.calistirilabilir).suffix.lower() not in (".cmd", ".bat"):
            return
        for arguman in komut[1:]:
            if chr(10) in arguman or chr(13) in arguman:
                raise MotorHatasi(
                    "Satir sonu tasiyan arguman .CMD sarmalayicisindan gecirilemez: "
                    "cmd.exe onu komut ayraci sayar ve SONRAKI BUTUN BAYRAKLARI "
                    "sessizce dusurur (izin modu, model, arac listesi dahil). "
                    "bin/claude.exe dogrudan cagrilmali ya da OFIS_CLAUDE_YOLU "
                    "ayarlanmali."
                )

    def musait_mi(self) -> bool:
        return bool(self.calistirilabilir)

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
        araclar_kapali: bool = False,
        izin_araci: str = "",
    ) -> Iterator[MotorOlayi]:
        metin = str(metin or "").strip()
        if not metin:
            raise MotorHatasi("Bos brifing kosulamaz.")
        if not self.calistirilabilir:
            raise MotorYokHatasi(
                "claude CLI bulunamadi. Kurulu mu: 'claude --version'?"
            )
        kok = Path(klasor).expanduser().resolve()
        if not kok.is_dir():
            raise MotorHatasi(f"Ajan calisma klasoru yok: {kok}")

        oturum = self._oturum_dogrula(oturum_id)
        devam = bool(oturum_id)
        sinir = float(zaman_asimi or self.zaman_asimi)

        komut = self._komut_kur(
            oturum, devam=devam, model=model, efor=efor, yazabilir=yazabilir,
            ek_klasorler=ek_klasorler, butce_usd=butce_usd,
            mcp_yapilandirma=mcp_yapilandirma, izinli_araclar=izinli_araclar,
            araclar_kapali=araclar_kapali, izin_araci=izin_araci,
        )

        self._arguman_dogrula(komut)

        # SIRLAR AYIKLANIR. claude turu hicbir dis servis anahtarina
        # ihtiyac duymaz; `izinli` bos birakiliyor. Ajanin elinde
        # `Bash(echo *)` var -- gecen her anahtar, terminal kaniti olarak
        # tahtaya dusebilir (bkz. tip.SIR_ONEKLERI).
        ortam = ortam_hazirla(os.environ, ek={**TUR_ORTAMI, **(ek_ortam or {})},
                              izinli=tuple(ek_ortam or ()))
        # Safe mode acik kalirsa kendi MCP yapilandirmamiz da devre disi
        # kalir; turu yalitmanin yolu safe mode degil, acik bayraklar.
        ortam.pop("CLAUDE_CODE_SAFE_MODE", None)
        ortam.pop("CLAUDE_CODE_SIMPLE", None)

        basladi = time.monotonic()
        try:
            surec = subprocess.Popen(
                komut,
                cwd=str(kok),
                env=ortam,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",   # Windows konsolu cp1254; boru utf-8 olmali
                errors="replace",
                bufsize=1,
                creationflags=_PENCERE_YOK,
            )
        except OSError as exc:
            raise MotorYokHatasi(f"claude baslatilamadi: {exc}") from exc
        # KAFES: turun baslattigi HER SEY tur bitince biter (yetimler dahil).
        kafes = SurecKafesi(surec)

        yield MotorOlayi("basladi", f"{self.ad} turu basladi",
                         {"oturum_id": oturum, "devam": devam, "klasor": str(kok)})

        satirlar = queue.Queue()
        hata_parcalari = []
        okuyucu = threading.Thread(
            target=self._satir_oku, args=(surec.stdout, satirlar),
            name="ofis-claude-stdout", daemon=True,
        )
        hata_okuyucu = threading.Thread(
            target=self._hata_oku, args=(surec.stderr, hata_parcalari),
            name="ofis-claude-stderr", daemon=True,
        )
        okuyucu.start()
        hata_okuyucu.start()

        durum = {
            "oturum_id": oturum, "model": "", "metin": [],
            "hatali": False, "hata_notu": "", "limit": False, "sonuc": "",
            "maliyet": 0.0, "jeton": 0, "arac_sayisi": 0,
            # Turun SON `rate_limit_event`i: hesabin pencereleri.
            "limit_bilgi": None,
            # cagri_id -> arac adi. Ret mesaji aracin ADINI tasimaz;
            # "izin reddedildi" deyip neyin reddedildigini soylememek,
            # kullaniciya "bir sey oldu" demekten ibarettir.
            "arac_adlari": {},
        }
        zaman_asti = False
        cikis = -1
        try:
            if surec.stdin is None:
                raise MotorHatasi("claude stdin acilamadi.")
            surec.stdin.write(metin)
            surec.stdin.close()

            biter = time.monotonic() + sinir
            while True:
                kalan = biter - time.monotonic()
                if kalan <= 0:
                    zaman_asti = True
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
                except json.JSONDecodeError:
                    continue  # stream-json disi satir (banner, uyari) -- yok say
                if isinstance(mesaj, dict):
                    for olay in self._mesaji_cevir(mesaj, durum):
                        yield olay

            if zaman_asti:
                self._surec_agacini_kes(surec)
            else:
                try:
                    cikis = surec.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._surec_agacini_kes(surec)
        finally:
            # Cagiran dongudan cikarsa (GeneratorExit) da burasi koser:
            # surec sizmaz, durdurma kolu cagiranda kalir.
            if surec.poll() is None:
                self._surec_agacini_kes(surec)
            for boru in (surec.stdin, surec.stdout, surec.stderr):
                if boru is not None:
                    try:
                        boru.close()
                    except OSError:
                        pass
            kafes.kapat()
            okuyucu.join(timeout=1)
            hata_okuyucu.join(timeout=1)

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
                "limit_pencere": claude_pencereleri(durum["limit_bilgi"]),
            },
        )

    # -- komut -------------------------------------------------------------

    def _komut_kur(self, oturum: str, *, devam: bool, model: str, efor: str,
                   yazabilir: bool, ek_klasorler: tuple,
                   butce_usd: float, mcp_yapilandirma: str = "",
                   izinli_araclar: tuple = (),
                   araclar_kapali: bool = False,
                   izin_araci: str = "") -> list:
        komut = [
            self.calistirilabilir,
            "-p",
            "--input-format", "text",
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
            # IZIN: ya ofise sorulur ya otomatik reddedilir. Ikisi de
            # sessiz beklemeden iyidir -- cevap veren olmayinca bekleyen
            # bir tur panelde "calisiyor" gorunup aslinda olmus olur.
            #
            # `izin_araci` VERILDIGINDE ofis karar verir. Bu, dosyanin
            # aylardir yazili olan sozunun tutuldugu yer:
            #
            #   "Listede olmayan her komut reddedilir ve gorunur bir
            #    `izin` olayina donusur -- Ofis MCP sunucusu gelince
            #    ayni red, `onay` tablosuna dusup insana sorulacak."
            #
            # Olculdu (22.09.2026): kanca her arac cagrisinda cagriliyor,
            # `tool_name` ve girdinin TAMAMINI aliyor; allow dosyayi
            # yazdirdi, deny yazdirmadi.
            *(("--permission-prompts", "host",
               "--permission-prompt-tool", izin_araci) if izin_araci
              else ("--permission-prompts", "none")),
            # Dosya araclarini calisma klasorlerine hapseder ve insanin kendi
            # ayar dosyalarini yok sayar: ajan turu tekrarlanabilir olmali,
            # makinedeki kisisel ayara gore davranis degistirmemeli.
            "--restricted",
            # MCP YALITIMI -- olculdu, tahmin degil. Bu bayrak olmadan
            # insanin hesabina bagli HER connector (magaza, reklam, posta,
            # tarayici...) arac tanimi olarak ajanin baglamina yuklenir.
            # Olcum: bos bir klasorde "bir dosya olustur" isteyen tur,
            # brifing daha okunmadan 53.831 jetona ulasip "Prompt is too
            # long" ile dustu. Yasa 2'nin faturasi: jeton kullanimi
            # performans varyansinin %80'ini acikliyor.
            #
            # Dogru kural: ajan, ISININ gerektirdigi MCP sunucularini alir.
            # Magaza ajani Shopify'i alir, backend ajani almaz. Bu secim
            # gorevle birlikte gelir (`mcp_yapilandirma`), hesabin tamamiyla
            # degil.
            "--strict-mcp-config",
            "--append-system-prompt",
            SISTEM_EKI_ORTAK + (KANIT_MCP if mcp_yapilandirma else KANIT_METIN),
        ]
        if mcp_yapilandirma:
            komut += ["--mcp-config", mcp_yapilandirma]
            # Ofis araclari da izin ister. Izin listesine ALINMAZSA
            # `--permission-prompts none` onlari da reddeder ve ajan
            # kanitini ekleyemez -- yani koordinasyon araclari sessizce
            # calismaz. Sunucunun kendisi zaten kimlik dogruluyor
            # (kimlik argumandan degil ortamdan gelir), o yuzden ofis
            # araclarinin tamami acilir.
            komut += ["--allowedTools", "mcp__ofis"]
        if araclar_kapali:
            # SAF YARGI TURU: hicbir arac yok.
            #
            # OLCULDU (21.09.2026): sartname kapisi okuma araclariyla
            # kosuyordu ve fable her turda 8-11 cagri yapip kod tabanini
            # GEZDI; ucu de ciktisini yazamadan tavani bitirdi (4 turun
            # 3'u basarisiz, $1,94, sifir bulgu).
            #
            # Aracin varligi burada yetenek degil TUZAK: model "once
            # bakayim" der, bakmakla biter. `--tools ""` o secenegi
            # tamamen kaldirir; geriye tek yol kalir -- verilen metne
            # bakip hukum yazmak.
            komut += _kip(izin_araci) + ["--tools", ""]
        elif yazabilir:
            komut += _kip(izin_araci) + ["--tools", ELLER_ARACLARI]
            komut += ["--allowedTools", *ELLER_IZINLI, *(izinli_araclar or ())]
        else:
            # 'kafa' ajan: YAZAN ARAC YOK. Yasak, aracin hic olmamasiyla
            # uygulanir -- ricayla degil, kipin niyetiyle de degil.
            #
            # OLCULDU (19.09.2026) ve BURADA PLAN KIPI VARDI. "Iki kat
            # kapali" diye yazmistik; ikinci kilidin bilinmeyen bir bedeli
            # cikti: `plan` kipi ajana "hicbir sey YAPMA, sadece onaya
            # plan uret" der. Yani yetkisini degil, ISININ NE OLDUGUNU
            # sanma bicimini degistirir. Gercek arastirma isinde ajan
            # dort tur boyunca kendiyle tartisti:
            #
            #   "Plan mode aktif... WebSearch/WebFetch cagirip rapor
            #    yazmak 'execute' sayilir, plan yazmak degil."
            #
            # Dort tur, sifir kanit, $0,617. Ayni is plan kipi olmadan
            # ILK turda bitti, $0,054 -- ve `rapor.txt` yine YAZILAMADI,
            # cunku Write/Edit/Bash araclari listede yok.
            #
            # Yasa 5'in kastettigi sinir "yargi ve dosya yazma verilmez"di.
            # Plan kipi bundan fazlasini yapiyordu: ISI YAPMAYI da
            # engelliyordu. **Fazladan kilit bedava degildir.**
            komut += _kip(izin_araci) + ["--tools", KAFA_ARACLARI]
            komut += ["--allowedTools", *KAFA_IZINLI, *(izinli_araclar or ())]

        model = str(model or "").strip()
        if model:
            komut += ["--model", model]
        kademe = EFOR_CEVRIMI.get(str(efor or "").strip().lower(), "")
        if kademe:
            komut += ["--effort", kademe]
        if butce_usd:
            komut += ["--max-budget-usd", str(float(butce_usd))]
        for ek in ek_klasorler or ():
            komut += ["--add-dir", str(ek)]

        # Kimlik burada yasar: ilk turda kimligi BIZ veriyoruz ki
        # veritabanina yazabilelim; sonraki turlarda ayni kimligi surduruyoruz.
        if devam:
            komut += ["--resume", oturum]
        else:
            komut += ["--session-id", oturum]
        return komut

    @staticmethod
    def _oturum_dogrula(oturum_id: str) -> str:
        if not oturum_id:
            return str(uuid.uuid4())
        try:
            return str(uuid.UUID(str(oturum_id)))
        except ValueError as exc:
            raise MotorHatasi(
                f"Oturum kimligi gecerli bir UUID degil: {oturum_id!r}"
            ) from exc

    # -- akis cevrimi ------------------------------------------------------

    def _mesaji_cevir(self, mesaj: dict, durum: dict) -> list:
        """Bir stream-json mesajini sifir ya da daha cok MotorOlayi'na cevirir.

        Motorun sozlugu burada biter; disari yalnizca OLAY_TURLERI cikar.
        """
        olaylar = []
        tur = str(mesaj.get("type") or "")
        if mesaj.get("session_id"):
            durum["oturum_id"] = str(mesaj["session_id"])

        if tur == "system" and mesaj.get("subtype") == "init":
            durum["model"] = str(mesaj.get("model") or "")[:100]
            olaylar.append(MotorOlayi(
                "oturum", durum["model"],
                {"oturum_id": durum["oturum_id"], "model": durum["model"]},
            ))
            return olaylar

        if tur == "rate_limit_event":
            bilgi = mesaj.get("rate_limit_info") or {}
            hal = str(bilgi.get("status") or "").lower()
            durum["limit_bilgi"] = bilgi
            if hal not in LIMIT_SAYILMAYAN:
                durum["limit"] = True
            olaylar.append(MotorOlayi("limit", hal or "bilinmiyor", dict(bilgi)))
            return olaylar

        if tur == "stream_event":
            olay = mesaj.get("event") or {}
            if olay.get("type") == "content_block_delta":
                delta = olay.get("delta") or {}
                if delta.get("type") == "text_delta":
                    parca = str(delta.get("text") or "")
                    durum["metin"].append(parca)
                    olaylar.append(MotorOlayi("metin", parca))
                elif delta.get("type") == "thinking_delta":
                    olaylar.append(MotorOlayi(
                        "dusunce", str(delta.get("thinking") or "")))
            return olaylar

        if tur == "assistant":
            for blok in self._icerik_bloklari(mesaj):
                if isinstance(blok, dict) and blok.get("type") == "tool_use":
                    durum["arac_sayisi"] += 1
                    ad = str(blok.get("name") or "")
                    ozet = self._girdi_ozeti(blok.get("input"))
                    cagri = str(blok.get("id") or "")
                    if cagri:
                        durum["arac_adlari"][cagri] = (ad, ozet)
                    olaylar.append(MotorOlayi(
                        "arac", ad, {"ozet": ozet, "cagri_id": cagri},
                    ))
            return olaylar

        if tur == "user":
            for blok in self._icerik_bloklari(mesaj):
                if isinstance(blok, dict) and blok.get("type") == "tool_result":
                    reddedildi = bool(blok.get("is_error"))
                    ozet = self._metin_ozeti(blok.get("content"))
                    # Reddedilen izin ayri bir olaydir: brifingde yazma alani
                    # yanlis verilmisse bu satir onu ele verir.
                    izin_reddi = reddedildi and (
                        "permission" in ozet.lower() or "izin" in ozet.lower()
                    )
                    cagri = str(blok.get("tool_use_id") or "")
                    ad, girdi = durum["arac_adlari"].get(cagri, ("", ""))
                    if izin_reddi:
                        # Reddedilen SEYI one al; gerekce arkada kalsin.
                        govde = f"{ad or 'arac'} reddedildi"
                        if girdi:
                            govde += f": {girdi[:160]}"
                    else:
                        govde = ozet
                    olaylar.append(MotorOlayi(
                        "izin" if izin_reddi else "arac_sonuc",
                        govde,
                        {"hatali": reddedildi, "cagri_id": cagri,
                         "arac": ad, "girdi": girdi},
                    ))
            return olaylar

        if tur == "result":
            durum["hatali"] = bool(mesaj.get("is_error"))
            durum["hata_notu"] = str(mesaj.get("api_error_status") or "")
            durum["sonuc"] = str(mesaj.get("result") or "")
            durum["maliyet"] = float(mesaj.get("total_cost_usd") or 0.0)
            kullanim = mesaj.get("usage") or {}
            durum["jeton"] = int(
                (kullanim.get("input_tokens") or 0)
                + (kullanim.get("output_tokens") or 0)
                + (kullanim.get("cache_read_input_tokens") or 0)
                + (kullanim.get("cache_creation_input_tokens") or 0)
            )
            dusuk = (durum["hata_notu"] + " " + durum["sonuc"]).lower()
            if "rate limit" in dusuk or "usage limit" in dusuk:
                durum["limit"] = True
        return olaylar

    @staticmethod
    def _icerik_bloklari(mesaj: dict) -> list:
        """`message.content` blok listesini guvenle cikarir.

        OLCULDU: `message` her zaman sozluk degil -- bazi mesajlarda duz
        dize gelir ve `.get` cagrisi AttributeError atar. Akisin ortasinda
        atilan bir istisna, o ana kadarki ciktinin da kanit olmasini
        engeller; bicime korumasiz guvenmek bu yuzden pahalidir.
        """
        govde = mesaj.get("message")
        if not isinstance(govde, dict):
            return []
        icerik = govde.get("content")
        return icerik if isinstance(icerik, list) else []

    @staticmethod
    def _girdi_ozeti(girdi) -> str:
        """Arac girdisinin tek satirlik ozeti -- panel pano basligi icin.

        Tam girdi saklanmaz: olay tablosu canli akistir, arsiv degil.
        """
        if not isinstance(girdi, dict):
            return ""
        for anahtar in ("command", "file_path", "path", "pattern", "url", "query"):
            if girdi.get(anahtar):
                return str(girdi[anahtar])[:200]
        return ", ".join(sorted(girdi))[:200]

    @staticmethod
    def _metin_ozeti(icerik) -> str:
        if isinstance(icerik, str):
            return icerik.strip()[:300]
        if isinstance(icerik, list):
            parcalar = [
                str(b.get("text") or "") for b in icerik
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            return " ".join(parcalar).strip()[:300]
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

        `claude` npm .CMD sarmalayicisidir; yalniz dogrudan cocugu
        sonlandirmak node alt surecini oksuz birakir ve her turdan sonra
        bir surec sizar. Uzun kosan bir ofiste bu, makineyi yavas yavas
        doldurur -- belirtisi de "bilgisayar agirlasti"dan ibaret kalir.
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
