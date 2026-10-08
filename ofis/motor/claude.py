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

from .. import motor_saglik
from .tip import (ortam_hazirla, limit_penceresi, dokum_ekle, Motor, MotorOlayi,
                  MotorHatasi, MotorYokHatasi, SurecKafesi, TurKanali,
                  baglam_bilgisi, baglam_siniri_ogren)

_PENCERE_YOK = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_SON = object()

# -- SICAK BEKLEYEN SUREC (05.10.2026) ----------------------------------------
#
# OLCULDU (Sonnet, bos klasor, liderin TAM komutu): liderin triyaj turu
# 10-11,6 sn; bunun ~7 sn'si MODELDEN ONCE -- her turda 6 claude.ai eklenti
# paketi, Context7 ve hesabin baglayicilari (Gmail, Drive, Shopify...)
# yeniden yukleniyor ("init" olayi 7-10. sn'de). Ayni komutla ONCEDEN
# baslatilip bekletilen surec: istemden sonuca 3,0-4,0 sn (init 0,2 sn).
# Patron: "gucu etkileyecek bir sey yapma" -- model, efor, araclar, baglayicilar
# AYNI; yalniz yukleme turdan ONCE yapilir. Her tur yine TEMIZ bir oturumdur
# (sicak surec yeni bir --session-id ile acilir, mesaj gelene kadar bekler).
# Anahtar komutun KENDISI (oturum kimligi haric) + klasor + ortam: model, efor
# ya da ayar degisirse bekleyen surec KULLANILMAZ. Mesaj gelmeden kimseye
# jeton harcatmaz; panel kapanirsa stdin kapanir ve surec cikar.
SICAK_OMUR_SN = 600
#: Tazeleme omrun bu kadar oncesinde yapilir (bekleyen hic bayatlamasin).
SICAK_TAZELE_PAYI_SN = 180
SICAK_AZAMI = 3
_SICAK: dict = {}
_SICAK_KILIT = threading.Lock()


def _oturumsuz(komut: list) -> list:
    k = list(komut)
    if "--session-id" in k:
        i = k.index("--session-id")
        del k[i:i + 2]
    return k


def _sicak_anahtar(komut: list, kok, ortam: dict) -> str:
    return json.dumps([_oturumsuz(komut), str(kok), sorted(ortam.items())],
                      ensure_ascii=False)


def _sicak_al(anahtar: str):
    """Bekleyen surec -> (surec, oturum, kafes) ya da None. Bayat/olu olan kapatilir."""
    with _SICAK_KILIT:
        k = _SICAK.pop(anahtar, None)
    if not k:
        return None
    if k["surec"].poll() is None and time.monotonic() - k["an"] < SICAK_OMUR_SN:
        return k["surec"], k["oturum"], k.get("kafes")
    _sicak_oldur(k)
    return None


def _sicak_oldur(k) -> None:
    """Bekleyen sureci AGACIYLA kapatir.

    06.10.2026 OLCULDU: yalniz `claude.exe` oldurulunce acilista baslattigi
    yan surecler (ofisin MCP sunucusu, tarayici araci) bir sure klasorde
    acik kaldi; gercek set iki gecici klasoru silemedi. Panel her 10 dk'da
    bekleyeni yeniler -- her seferinde yetim birakmamali. Kafes (is nesnesi)
    surec dogar dogmaz kurulur, kapaninca icindeki HER SEY biter.
    """
    surec = k["surec"] if isinstance(k, dict) else k
    kafes = k.get("kafes") if isinstance(k, dict) else None
    try:
        if kafes is not None:
            kafes.kapat()
        surec.kill()
        surec.wait(timeout=5)
    except Exception:                            # noqa: BLE001 -- zaten olmus olabilir
        pass


def _sicak_hazirla(anahtar: str, komut: list, kok, ortam: dict) -> None:
    """Ayni komutla, YENI oturum kimligiyle bir sonraki sureci baslatir."""
    oturum = str(uuid.uuid4())
    k = _oturumsuz(komut) + ["--session-id", oturum]
    try:
        surec = subprocess.Popen(k, cwd=str(kok), env=ortam, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 encoding="utf-8", errors="replace", bufsize=1,
                                 creationflags=_PENCERE_YOK)
    except OSError:
        return
    # KAFES HEMEN: bekleyen surec acilista yan surecler baslatir; sonradan
    # kurulan kafes onlari kapsamaz.
    kafes = SurecKafesi(surec)
    eskiler = []
    with _SICAK_KILIT:
        eski = _SICAK.pop(anahtar, None)
        if eski:
            eskiler.append(eski)
        _SICAK[anahtar] = {"surec": surec, "oturum": oturum, "an": time.monotonic(),
                           "kafes": kafes}
        while len(_SICAK) > SICAK_AZAMI:
            en_eski = min(_SICAK, key=lambda x: _SICAK[x]["an"])
            eskiler.append(_SICAK.pop(en_eski))
    for s in eskiler:
        _sicak_oldur(s)


def sicaklari_kapat() -> int:
    """Bekleyen butun surecleri kapatir (panel kapanisi, sinama)."""
    with _SICAK_KILIT:
        hepsi = list(_SICAK.values())
        _SICAK.clear()
    for s in hepsi:
        _sicak_oldur(s)
    return len(hepsi)


import atexit as _atexit                           # noqa: E402
_atexit.register(sicaklari_kapat)

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
#: ALT AJAN (Task) ve BECERI (Skill) -- 02.10.2026, patron: "ai modellerin
#: alt ajanlari calistirmasi bize ne zarar verir?" OLCULDU (haiku, bos
#: klasor): alt ajanin HER arac cagrisi hem kancaya (PreToolUse, gercek
#: terminal) hem onay aracina (--permission-prompt-tool, arka plan)
#: DUSUYOR; ikisinde de `rm` durduruldu. Alt ajan ust ajanin arac
#: sinirini MIRAS alir (yazamayan ajanin alt ajani dosya yazamadi).
#: Bedel: tur basina ~5.400 jeton (13.907 -> 19.308, cogu onbellekten).
ALT_AJAN_ARACLARI = "Task,Skill,ToolSearch"
ELLER_ARACLARI = ("Read,Glob,Grep,Edit,Write,Bash,TodoWrite,WebSearch,WebFetch,"
                  + ALT_AJAN_ARACLARI)

#: 'kafa' ajanin araclari. Yazan hicbir arac yok -- kural brifingde rica
#: edilmez, surec duzeyinde uygulanir. Yazma yasagini TASIYAN sey bu
#: liste: Write/Edit/Bash burada olmadigi icin ajan yazamaz. Izin kipine
#: ya da brifing metnine bagli degildir.
KAFA_ARACLARI = "Read,Glob,Grep,WebSearch,WebFetch," + ALT_AJAN_ARACLARI

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

KAFA_IZINLI = ("Read", "Glob", "Grep", "WebSearch", "WebFetch", "Task", "Skill",
               "ToolSearch") + OFIS_ARACLARI

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
    # Alt ajani BASLATMAK ve beceri yuklemek kendisi bir sey degistirmez;
    # alt ajanin ICINDEKI her cagri kapidan gecer (olculdu).
    "Task", "Skill", "ToolSearch",
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
    # `seven_day_overage_included` -> "7g_kapi" (27.09.2026 OLCULDU): yalniz
    # FABLE turunda geliyor, haiku turunda yok (ayni dakika, ayni hesap).
    # claude.ai ayarlarindaki ayri "Haftalik -- Fable" cubugunun karsiligi.
    # Adi saglayicinin; anlami olcumle baglandi, tahminle degil.
    adlar = {"five_hour": "5s", "seven_day": "7g",
             "seven_day_overage_included": "7g_kapi"}
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
#: Sonuc geldikten sonra yankisi gelmemis bir notun yeni tur acmasi icin
#: beklenen en uzun sure. Olculen: 0,7 sn. Genis tutuldu (yavas ag), ama
#: sonsuz degil -- asili surec kilidi rehin tutar.
NOT_BEKLEME_SN = 45.0

TUR_ORTAMI = {
    # ERTELENMIS YUKLEME + HESABIN BAGLAYICILARI (02.10.2026, patron: "ne
    # varsa gelsin"). OLCULDU: arama acikken butun baglayicilar 18.848
    # jeton/tur (kapaliyken 18.611), arama kapaliyken 91.323. Kural ve
    # kapatilanlar `ofis/kaynaklar.py`.
    "ENABLE_TOOL_SEARCH": "true",
    "ENABLE_CLAUDEAI_MCP_SERVERS": "true",
    "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",  # tur bitince arka is kalmasin
    # ONBELLEK 5 DAKIKA (03.10.2026, resmi ayar, CLI 2.1.242+). Abonelikte
    # varsayilan 1 SAAT ve yazma 2x fiyat; 5 dakikada 1,25x. Ofis her turu
    # yeni oturumla acar ve Claude hesabin listelerini her yeni oturumda
    # bastan yazar (12-23 bin jeton) -- bu yazma ucuzlar. OLCULDU (bos
    # klasor, sicak): haiku $0,027-0,035 -> $0,015-0,023; sonnet $0,094 ->
    # $0,061 (~%35). Bedeli: 5 dakikadan uzun aradan sonraki ilk tur
    # (sonnet $0,100 -> $0,128). Hicbir sey kapanmaz; Codex'e dokunmaz.
    "CLAUDE_CODE_PROMPT_CACHE_TTL": "5m",
    # UZUN ARAC (06.10.2026, video kurgu): MCP arac cagrisinin zaman asimi
    # ACIKCA 15 dk -- varsayilan CLI surumune bagli; codex'teki ayarin esi.
    "MCP_TOOL_TIMEOUT": "900000",
}
#: Saf yargi turu (araclar kapali) ve limit okuma baglayici TASIMAZ.
BAGLAYICISIZ = {"ENABLE_CLAUDEAI_MCP_SERVERS": "false"}

#: Brifingin ustune eklenen kisa durus. Brifing ISI anlatir; bu metin
#: ajanin hangi evde oldugunu anlatir. Kisa tutuluyor: her jeton brifingin
#: dort katmanindan calinmis demektir.
#: OLCULDU: "kanit ver" demek yetmiyor. Ilk gercek turda ajan isi dogru
#: yapti (`pytest` -> 4 passed) ama kanit satirini yazmadi; kanit kapisi
#: da -- dogru davranarak -- isi kapatmadi. Is bitmisti, defterde
#: bitmemis gorunuyordu. Ders: bir kural ancak BICIMIYLE birlikte
#: verilirse uygulanir. Ricanin yerini sablon alir.
SISTEM_EKI_ORTAK = (
    "AgentOfis'te bir ajansin. Gorevin bu konusmanin ILK mesajidir "
    "(bir brifing ya da ofisin istemi -- ne istiyorsa onu, istedigi "
    "bicimde yap). Gorevini bir DOSYADA ARAMA: gereken her sey bu "
    "mesajdadir; kokte gorev/brifing gibi gorunen bir dosya baska "
    "ajana ait olabilir, ona guvenme. "
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


def _supur_eski_limit(kok, *, omur_sn: float = 3600) -> list:
    """`ofis-limit-*` klasorlerinden `omur_sn`'den eski olanlari siler.

    Olcum ~1,3 sn surer; saatten eski klasor hicbir canli olcume ait
    olamaz. Silinen adlar doner (sinama icin).
    """
    import shutil as _sh
    silinen = []
    sinir = time.time() - omur_sn
    try:
        for p in Path(kok).glob("ofis-limit-*"):
            try:
                if p.is_dir() and p.stat().st_mtime < sinir:
                    _sh.rmtree(p, ignore_errors=True)
                    if not p.exists():
                        silinen.append(p.name)
            except OSError:
                pass
    except OSError:
        pass
    return silinen


class ClaudeMotoru(Motor):
    """`claude` CLI'ini tur basina bir surec olarak kosturur."""

    ad = "claude"
    mcp_konusur = True
    butce_destegi = True   # --max-budget-usd
    araclar_kapatilabilir = True
    izin_kancasi = True   # --tools ""
    #: Sicak bekleyen surec destegi (`tur_kos(sicak=True)`), bkz. modul ustu.
    sicak_destegi = True
    #: Tur SURERKEN not ve durdurma (`TurKanali`). OLCULDU (26.09.2026):
    #: `--input-format stream-json` ile yazilan mesaj bir sonraki arac
    #: sinirinda AYNI tura girer; arac siniri yoksa ikinci bir tur acar.
    #: `control_request interrupt` turu aninda keser (8,1 sn, $0,007).
    tur_ici_mesaj = True
    #: claude.ai baglayicilarini YALNIZ claude CLI yukler (koltuk buna bakar).
    baglayici_tasir = True

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

    #: Yeniden giris -- CLI'in kendi yardimindan (`claude auth --help`).
    GIRIS_CARESI = ("Yeniden giris: bir terminalde `claude auth login` "
                    "(ya da claude'u acip /login).")

    #: `claude auth status` onbellegi: yapilandirma dizini -> (an, sonuc).
    #: Olcum bedava ama 0,4-0,5 sn (olculdu); musaitlik bir tikte birden cok
    #: kez sorulur. Bes dakikada bir yeter -- giris, dakikalar icinde
    #: degisen bir sey degil.
    GIRIS_ONBELLEK_SN = 300.0
    _giris_onbellek: dict = {}

    @staticmethod
    def _yapilandirma_dizini(ek_ortam: dict = None) -> str:
        d = ((ek_ortam or {}).get("CLAUDE_CONFIG_DIR")
             or os.environ.get("CLAUDE_CONFIG_DIR")
             or str(Path.home() / ".claude"))
        return str(Path(d).expanduser().resolve())

    def _kimlik(self, ek_ortam: dict = None) -> tuple:
        """-> (kimlik, parmak izi). API anahtari varsa anahtarin OZETI, yoksa
        abonelik girisinin dosyasi (yeniden giris onu yeniden yazar)."""
        anahtar = (ek_ortam or {}).get("ANTHROPIC_API_KEY")
        if anahtar:
            pi = motor_saglik.parmak_izi_anahtar(anahtar)
            return "api:" + pi, pi
        dizin = self._yapilandirma_dizini(ek_ortam)
        return dizin, motor_saglik.parmak_izi_dosya(Path(dizin) / ".credentials.json")

    def giris_durumu(self, *, tazele: bool = False) -> dict:
        """Yerel giris OLCULUR (`claude auth status`, jeton yakmaz).

        Donus: `{"girisli": True/False/None, "eposta", "plan"}`. `None` =
        olculemedi -- bilinmeyene "giris yok" DENMEZ (musaitligi keserdi).
        """
        if not self.calistirilabilir:
            return {"girisli": None, "eposta": "", "plan": ""}
        dizin = self._yapilandirma_dizini()
        an = time.monotonic()
        eski = self._giris_onbellek.get(dizin)
        if eski and not tazele and an - eski[0] < self.GIRIS_ONBELLEK_SN:
            return eski[1]
        try:
            p = subprocess.run([self.calistirilabilir, "auth", "status"],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=20,
                               creationflags=_PENCERE_YOK)
            d = json.loads(p.stdout or "{}")
            sonuc = {"girisli": bool(d.get("loggedIn")),
                     "eposta": str(d.get("email") or ""),
                     "plan": str(d.get("subscriptionType") or "")}
        except (OSError, ValueError, subprocess.SubprocessError):
            sonuc = {"girisli": None, "eposta": "", "plan": ""}
        self._giris_onbellek[dizin] = (an, sonuc)
        return sonuc

    #: Plan limitlerinin adi -> ortak pencere adi. `weekly_scoped` +
    #: model "Fable" -> `7g_kapi` (turdaki `seven_day_overage_included`in
    #: karsiligi; ikisi de 27.09'da ayni %10'u verdi).
    LIMIT_ADLARI = {"session": "5s", "weekly_all": "7g"}

    def limit_oku(self, *, ek_ortam: dict = None) -> dict | None:
        """`get_usage` kontrol istegi -- MODEL CAGRILMAZ (27.09.2026 olculdu).

        CLI'in SDK kanalinda kullanim sayaclari icin bir istek var: kullanici
        mesaji gonderilmeden sorulur, cevap ~1,3 sn'de gelir, turun maliyeti
        0. Donen sayilar claude.ai / VS Code "Account & Usage" ekraniyla
        AYNI (oturum %20 · haftalik %51 · Fable %10).
        """
        if not self.calistirilabilir:
            return None
        ortam = ortam_hazirla(os.environ, ek={**TUR_ORTAMI, **BAGLAYICISIZ, **(ek_ortam or {})},
                              izinli=tuple(ek_ortam or ()))
        import tempfile
        # GECICI KLASOR ELLE silinir (02.10.2026, olculdu): `with
        # TemporaryDirectory` cikista, Claude sureci klasoru hala tutarken
        # silmeye kalkiyordu; Windows reddedince PermissionError (OSError)
        # asagidaki `except`e dusup OKUNMUS limiti de None yapiyordu ve
        # %TEMP%'te bos `ofis-limit-*` kaliyordu. Simdi: surec biter,
        # klasor birkac denemeyle silinir, silinemese de olcum kaybolmaz.
        cevap = None
        # Panel olcum ortasinda OLDURULURSE `finally` kosmaz ve klasor kalir
        # (08.10.2026 olculdu: gosteri paneli yeniden baslatilinca bos
        # `ofis-limit-*`). Bir sonraki olcum saatten eski artiklari supurur.
        _supur_eski_limit(tempfile.gettempdir())
        dizin = tempfile.mkdtemp(prefix="ofis-limit-")
        try:
            if True:
                p = subprocess.Popen(
                    [self.calistirilabilir, "-p", "--input-format", "stream-json",
                     "--output-format", "stream-json", "--verbose",
                     "--strict-mcp-config", "--no-chrome", "--tools", ""],
                    cwd=dizin, env=ortam, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                    encoding="utf-8", errors="replace", creationflags=_PENCERE_YOK)
                try:
                    p.stdin.write(json.dumps({
                        "type": "control_request", "request_id": "limit",
                        "request": {"subtype": "get_usage", "skip_behaviors": True}}) + "\n")
                    p.stdin.flush()
                    cevap = None
                    bitis = time.monotonic() + 25
                    while time.monotonic() < bitis:
                        satir = p.stdout.readline()
                        if not satir:
                            break
                        try:
                            o = json.loads(satir)
                        except ValueError:
                            continue
                        if (o.get("type") == "control_response"
                                and (o.get("response") or {}).get("request_id") == "limit"):
                            cevap = o["response"]
                            break
                finally:
                    try:
                        p.stdin.close()
                    except OSError:
                        pass
                    try:
                        p.wait(5)
                    except subprocess.TimeoutExpired:
                        p.kill()
                        try:
                            p.wait(5)
                        except subprocess.TimeoutExpired:
                            pass
        except (OSError, ValueError):
            return None
        finally:
            import shutil as _sh
            for _ in range(10):
                _sh.rmtree(dizin, ignore_errors=True)
                if not os.path.exists(dizin):
                    break
                time.sleep(0.2)
        if not cevap or cevap.get("subtype") != "success":
            return None
        return self.usage_pencereleri(cevap.get("response") or {})

    @classmethod
    def usage_pencereleri(cls, r: dict) -> dict | None:
        """`get_usage` cevabi -> ortak bicim. Yuzde 0-100 gelir, 0-1'e cevrilir."""
        from datetime import datetime
        pencereler = {}
        for lim in (r.get("rate_limits") or {}).get("limits") or []:
            if not isinstance(lim, dict):
                continue
            ad = cls.LIMIT_ADLARI.get(lim.get("kind"))
            if lim.get("kind") == "weekly_scoped":
                model = (((lim.get("scope") or {}).get("model") or {})
                         .get("display_name") or "")
                ad = "7g_kapi" if model.lower() == "fable" else (
                    "7g_" + model.lower().replace(" ", "_") if model else None)
            if not ad or not isinstance(lim.get("percent"), (int, float)):
                continue
            try:
                yen = int(datetime.fromisoformat(lim["resets_at"]).timestamp())
            except (KeyError, TypeError, ValueError):
                continue
            pencereler[ad] = {"kullanim": lim["percent"] / 100.0, "yenilenme": yen}
        return limit_penceresi(pencereler, kaynak="claude CLI (get_usage, tur yok)",
                               plan=str(r.get("subscription_type") or ""))

    def durum_notu(self) -> str:
        """Musait DEGILSE sebebi + caresi; musaitse (ya da bilinmiyorsa) bos."""
        if not self.calistirilabilir:
            return "claude CLI kurulu degil."
        kimlik, parmak = self._kimlik()
        kayit = motor_saglik.olu_kaydi("claude", kimlik, parmak)
        if kayit:
            return motor_saglik.kayit_metni("claude", kayit, self.GIRIS_CARESI)
        if self.giris_durumu()["girisli"] is False:
            return "claude'a giris YOK (`claude auth status`). " + self.GIRIS_CARESI
        return ""

    def etkilesimli_komut(self, *, oturum_id: str = "", klasor: str = "",
                          model: str = "", ek_ortam: dict = None) -> dict | None:
        """Devral: `claude --resume <oturum>` -- ajanin kendi oturumu, kendi
        klasorunde (Claude oturumu klasore gore saklar; baska klasorde
        acilirsa bulunamaz). Guven sorusu cikabilir: INSAN cevaplar."""
        if not self.calistirilabilir:
            return None
        argv = [self.calistirilabilir]
        if oturum_id:
            argv += ["--resume", oturum_id]
        if model:
            argv += ["--model", model]
        ortam = ortam_hazirla(os.environ, ek={**TUR_ORTAMI, **(ek_ortam or {})},
                              izinli=tuple(ek_ortam or ()))
        return {"argv": argv, "ortam": ortam, "kapat": "/exit"}

    def musait_mi(self) -> bool:
        """Kurulu MU, girisli MI ve hesabi son gercek turda REDDEDILMEDI mi.

        27.09.2026'ya kadar yalniz kurulu olmasina bakiyordu: girissiz ya
        da oturumu sunucuda dusmus bir claude "HAZIR" gorunur, zincir onu
        ilk basamakta dener ve her tur dusardi (E16).
        """
        return bool(self.calistirilabilir) and not self.durum_notu()

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
        kanal=None,
        sicak: bool = False,
    ) -> Iterator[MotorOlayi]:
        metin = str(metin or "").strip()
        if not metin:
            raise MotorHatasi("Bos brifing kosulamaz.")
        # SICAK (bkz. modul ustu): yalniz YENI oturumlu turda. Istem stdin
        # json kanalindan gider (surec mesaji bekler); bos kanal = not yok.
        sicak = bool(sicak) and not oturum_id
        if sicak and kanal is None:
            kanal = TurKanali()
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

        komut, ortam = self._komut_ve_ortam(
            oturum, devam=devam, model=model, efor=efor, yazabilir=yazabilir,
            ek_klasorler=ek_klasorler, butce_usd=butce_usd,
            mcp_yapilandirma=mcp_yapilandirma, izinli_araclar=izinli_araclar,
            araclar_kapali=araclar_kapali, izin_araci=izin_araci,
            akis_girdi=kanal is not None, ek_ortam=ek_ortam)


        basladi = time.monotonic()
        surec = None
        sicak_kafes = None
        if sicak:
            anahtar = _sicak_anahtar(komut, kok, ortam)
            hazir = _sicak_al(anahtar)
            if hazir:
                surec, oturum, sicak_kafes = hazir
        try:
            if surec is None:
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
        if sicak:
            # SIRADAKI tur icin hemen yukle: liderin plan/rapor turu cogu kez
            # saniyeler icinde gelir.
            _sicak_hazirla(anahtar, komut, kok, ortam)
        # KAFES: turun baslattigi HER SEY tur bitince biter (yetimler dahil).
        # Sicak surec kendi kafesiyle gelir (dogdugu anda kuruldu).
        kafes = sicak_kafes if sicak_kafes is not None else SurecKafesi(surec)

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
            "jeton_dokumu": {},
            # Turun SON `rate_limit_event`i: hesabin pencereleri.
            "limit_bilgi": None,
            # cagri_id -> arac adi. Ret mesaji aracin ADINI tasimaz;
            # "izin reddedildi" deyip neyin reddedildigini soylememek,
            # kullaniciya "bir sey oldu" demekten ibarettir.
            "arac_adlari": {},
            # HESAP SORUNU (E16): assistant mesajinin `error` alani
            # (`authentication_failed`, `billing_error`, ...). Limit gibi
            # gecici degildir -- insan eylemi ister ve HATIRLANIR.
            "hesap_hatasi": "",
        }
        zaman_asti = False
        cikis = -1
        # TUR ICI KANAL: gonderilmis ama YANKISI gelmemis notlar. Yanki
        # (`--replay-user-messages`) notun modele GERCEKTEN ulastigi andir
        # -- olculdu: 8. sn'de yazilan not 21,8. sn'de, arac sinirinda
        # yankilandi. Yazmak ulasmak degildir.
        bekleyen_not: list = []
        stdin_acik = kanal is not None
        # Sonuc geldi ama stdin bekleyen not yuzunden acik birakildi: CLI
        # notu yeni bir tur olarak isler (olculdu, 0,7 sn). Islemezse surec
        # zaman asimina kadar ASILI kalirdi -- bu an o korumanin saatidir.
        bosta_an = None
        try:
            if surec.stdin is None:
                raise MotorHatasi("claude stdin acilamadi.")
            if kanal is None:
                surec.stdin.write(metin)
                surec.stdin.close()
            else:
                surec.stdin.write(self._kullanici_satiri(metin))
                surec.stdin.flush()

            biter = time.monotonic() + sinir
            while True:
                kalan = biter - time.monotonic()
                if kalan <= 0:
                    zaman_asti = True
                    break
                if stdin_acik:
                    stdin_acik = self._kanali_tasi(surec, kanal, bekleyen_not, durum)
                try:
                    oge = satirlar.get(timeout=min(NABIZ_ARALIGI, kalan))
                except queue.Empty:
                    if surec.poll() is not None and not okuyucu.is_alive():
                        break
                    if (stdin_acik and bosta_an is not None
                            and time.monotonic() - bosta_an > NOT_BEKLEME_SN):
                        # Not yazildi ama yeni tur acilmadi: bekleme biter,
                        # yankisiz not ULASMAMIS sayilir (sonraki turda).
                        stdin_acik = self._stdin_kapat(surec)
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
                    if mesaj.get("type") not in ("result", "system"):
                        bosta_an = None
                    if kanal is not None and mesaj.get("type") == "user":
                        yield from self._yankilar(mesaj, bekleyen_not)
                    for olay in self._mesaji_cevir(mesaj, durum):
                        yield olay
                    if kanal is not None and mesaj.get("type") == "result":
                        if durum.get("durduruldu"):
                            durum["hata_notu"] = "durduruldu"
                        if stdin_acik:
                            # Tur bitti. Bu anda kanala dusmus not da
                            # gonderilir: CLI onu YENI bir tur olarak isler
                            # (olculdu), yani patronun sozu kaybolmaz.
                            stdin_acik = self._kanali_tasi(
                                surec, kanal, bekleyen_not, durum)
                        if stdin_acik and (not bekleyen_not
                                           or durum.get("durduruldu")):
                            # Bekleyen yoksa (ya da tur DURDURULDUYSA) stdin
                            # kapanir, surec cikar. Kapandiktan sonra gelen
                            # not kanalda kalir ve koltuk onu bir SONRAKI
                            # turun basinda verir.
                            stdin_acik = self._stdin_kapat(surec)
                        elif stdin_acik:
                            # Bekleyen not var: stdin ACIK kalir. Notu
                            # kurtarmak icin DEGIL -- CLI stdin kapansa da
                            # kuyruktaki notu isler (olculdu 26.09, iki kipte
                            # 2/2). Acik tutmanin sebebi notun actigi IKINCI
                            # turda da DURDUR'un calismasi: stdin kapaliyken
                            # interrupt yazilamaz.
                            bosta_an = time.monotonic()

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

        if durum["hesap_hatasi"]:
            # Hatirlanir: sonraki turlar bu hesabi DENEMEZ (zincir atlar),
            # gostergeler "hazir" demez. Kullanici yeniden giris yapinca
            # parmak izi degisir ve kayit kendiliginden duser.
            kimlik, parmak = self._kimlik(ek_ortam)
            motor_saglik.olu_yaz("claude", kimlik, parmak, durum["hesap_hatasi"])
            yield MotorOlayi(
                "hata", motor_saglik.kayit_metni(
                    "claude", {"kategori": durum["hesap_hatasi"], "an": time.time()},
                    self.GIRIS_CARESI),
                {"sebep": "oturum_kapandi", "kategori": durum["hesap_hatasi"]},
            )
        elif zaman_asti:
            yield MotorOlayi(
                "hata", f"Tur {sinir:.0f} saniyede bitmedi, surec kesildi.",
                {"sebep": "zaman_asimi"},
            )
        elif durum["limit"]:
            yield MotorOlayi(
                "hata", "Hesap kullanim limitine ulasildi.", {"sebep": "limit"},
            )
        elif durum.get("durduruldu"):
            # Insanin istegi: bir ARIZA degil. Sebep ayri yazilir ki koltuk
            # isi "kaldigi yerden" surdurebilsin (kaynak tukenmesi gibi).
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
            and not durum.get("durduruldu") and not durum["hesap_hatasi"]
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
                "jeton_dokumu": durum.get("jeton_dokumu") or None,
                "arac_sayisi": durum["arac_sayisi"],
                "limit": durum["limit"],
                "zaman_asimi": zaman_asti,
                "limit_pencere": claude_pencereleri(durum["limit_bilgi"]),
                "baglam": baglam_bilgisi(durum.get("son_baglam"), durum.get("baglam_siniri"),
                                         model=durum["model"] or model),
                "sebep": ("" if basarili else
                          "oturum_kapandi" if durum["hesap_hatasi"] else
                          "zaman_asimi" if zaman_asti else
                          "limit" if durum["limit"] else
                          "durduruldu" if durum.get("durduruldu") else
                          (durum["hata_notu"] or "cikis")),
            },
        )

    # -- gercek terminal (TUI) kipi -----------------------------------------
    #
    # 29.09.2026, olculdu: ajan gercek `claude` terminalinde (ConPTY)
    # kosunca ofisin kapisi PreToolUse kancasiyla durduruyor, onaydan sonra
    # ajan kaldigi yerden devam ediyor, oturum dosyasi arac cagrilarini
    # arka plan kipindekiyle AYNI bicimde tasiyor. Genel dongu
    # `motor/tui.py`de; burada yalniz claude'a ozel olan var.

    tui_destegi = True

    #: Arka plan kipine ozgu bayraklar -- etkilesimli terminalde anlamsiz.
    _TUI_DUSEN_TEK = ("-p", "--verbose", "--include-partial-messages",
                      "--replay-user-messages")
    _TUI_DUSEN_CIFT = ("--input-format", "--output-format", "--permission-prompts",
                       "--permission-prompt-tool", "--max-budget-usd")

    def tui_plani(self, *, oturum_id: str, model: str, efor: str,
                  yazabilir: bool, ek_klasorler: tuple, mcp_yapilandirma: str,
                  izinli_araclar: tuple, ek_ortam: dict, kanca_komutu: str,
                  gecici: Path, klasor: str = "") -> dict:
        """Gercek terminalde acilacak `claude` komutu ve oturum dosyasi.

        Arka plan kipinin komutu (`_komut_kur`) TEMEL alinir: arac listesi,
        izin listesi, MCP yalitimi, sistem eki, model, efor, klasorler --
        iki kip ayni kurallarla kosar. Yalniz arka plana ozgu bayraklar
        duser ve izin karari KANCAYA gecer (`--settings` ile PreToolUse).
        Izin kipi VERILMEZ: kanca `allow` dedigi seyi CLI sormaz, `deny`
        dedigini yapmaz (olculdu, `_kip` belgesi).
        """
        devam = bool(oturum_id)
        oturum = self._oturum_dogrula(oturum_id)
        ham = self._komut_kur(
            oturum, devam=devam, model=model, efor=efor, yazabilir=yazabilir,
            ek_klasorler=ek_klasorler, butce_usd=None,
            mcp_yapilandirma=mcp_yapilandirma, izinli_araclar=izinli_araclar,
            izin_araci="kanca")
        argv, i = [ham[0]], 1
        while i < len(ham):
            if ham[i] in self._TUI_DUSEN_TEK:
                i += 1
                continue
            if ham[i] in self._TUI_DUSEN_CIFT:
                i += 2
                continue
            argv.append(ham[i])
            i += 1
        ayar = Path(gecici) / f"kanca-{oturum}.json"
        kanca = [{"matcher": "*", "hooks": [{"type": "command",
                                             "command": kanca_komutu}]}]
        ayar.write_text(json.dumps({"hooks": {"PreToolUse": kanca}}),
                        encoding="utf-8")
        argv += ["--settings", str(ayar)]
        ortam = ortam_hazirla(os.environ, ek={**TUR_ORTAMI,
                                              **self._baglayici_ortami(),
                                              **(ek_ortam or {})},
                              izinli=tuple(ek_ortam or ()))
        # Ic ice oturum isareti dokum KAYDINI kapatir (olculdu).
        for ad in list(ortam):
            if ad.startswith(("CLAUDE_CODE_SAFE_MODE", "CLAUDE_CODE_SIMPLE",
                              "CLAUDECODE", "CLAUDE_CODE_CHILD", "CLAUDE_CODE_ENTRYPOINT")):
                ortam.pop(ad, None)
        projeler = Path(self._yapilandirma_dizini(ek_ortam)) / "projects"
        return {
            "argv": argv, "ortam": ortam, "kapat": "/exit",
            "oturum_id": oturum,
            "dokum": lambda: next(iter(projeler.rglob(f"{oturum}.jsonl")), None),
            # Guven sorusunun varsayilani "No, exit": asagi ok + Enter.
            # `\x1b[B` Esc sayildi (olculdu), `\x1bOB` dogru.
            "guven": ("\x1bOB", "\r"),
            # 30.09 (2.1.285): sabit dizi "No"da kaldi; artik EKRANA
            # bakilarak secilir (tui._guven_sec).
            "guven_evet": "Yes, I trust",
            "guven_isareti": "trust",
            # Giris kutusu cizildi: cizgi + imlec (olculdu, 01.10).
            "hazir_mi": lambda e: "\u276f" in e[-500:] and "\u2500" * 10 in e[-900:],
            "durdur": "\x1b",
        }

    @staticmethod
    def tui_kullanici_metni(kayit: dict) -> str:
        """Kayit satiri ajana VERILMIS bir kullanici mesajiysa metni.

        OLCULDU (Claude Code oturum dosyalari): tur surerken yazilan mesaj
        once `queue-operation enqueue` (yalniz SIRADA -- ulasmadi), arac
        sinirinda `attachment.type == queued_command` (ULASTI); bos anda
        yazilan ise duz `user` mesaji.
        """
        def _metin(icerik):
            if isinstance(icerik, str):
                return icerik
            if isinstance(icerik, list):
                return " ".join(str(b.get("text") or "") for b in icerik
                                if isinstance(b, dict) and b.get("type") == "text")
            return ""
        tur = kayit.get("type")
        if tur == "attachment":
            ek = kayit.get("attachment") if isinstance(kayit.get("attachment"), dict) else {}
            return _metin(ek.get("prompt")) if ek.get("type") == "queued_command" else ""
        if tur == "user":
            m = kayit.get("message") if isinstance(kayit.get("message"), dict) else {}
            return _metin(m.get("content"))
        return ""

    def tui_cevir(self, kayit: dict, durum: dict) -> tuple:
        """Oturum dosyasinin bir satiri -> (olaylar, tur_bitti).

        Arac cagrisi ve sonucu arka plan kipinin cevirisinden (`_mesaji_cevir`)
        gecer -- iki kipte ayni olaylar. Farkli olan: metin parca parca degil
        blok olarak gelir; kullanim mesaj basina yinelenir (ayni `id` her
        icerik bloguyla tekrar yazilir), son deger alinir.
        """
        olaylar = []
        tur = kayit.get("type")
        if tur == "system" and kayit.get("subtype") == "turn_duration":
            return olaylar, True
        mesaj = kayit.get("message") if isinstance(kayit.get("message"), dict) else {}
        if tur == "assistant":
            if not durum.get("model") and mesaj.get("model"):
                durum["model"] = str(mesaj["model"])[:100]
                olaylar.append(MotorOlayi("oturum", durum["model"], {
                    "oturum_id": durum.get("oturum_id", ""), "model": durum["model"]}))
            kul = mesaj.get("usage") or {}
            if mesaj.get("id") and kul:
                durum.setdefault("kullanim", {})[mesaj["id"]] = int(
                    (kul.get("input_tokens") or 0) + (kul.get("output_tokens") or 0)
                    + (kul.get("cache_read_input_tokens") or 0)
                    + (kul.get("cache_creation_input_tokens") or 0))
                # Ayni `id` her blokla YINELENIR: dokumde de son deger.
                durum.setdefault("dokum_mesaj", {})[mesaj["id"]] = dokum_ekle({}, kul)
            for blok in self._icerik_bloklari(kayit):
                if isinstance(blok, dict) and blok.get("type") == "text":
                    parca = str(blok.get("text") or "")
                    if parca:
                        # AYRI MESAJLAR YAPISMASIN (29.09, olculdu): rapor
                        # "...dogrulayacagim.**Patrona rapor**" diye birlesti.
                        # Satir basi arayan `KARAR:`/`DURUM:` desenleri bozulur
                        # (codex'te bir kez odendi, `_mesaj_parcasi`).
                        if durum.get("metin"):
                            parca = "\n\n" + parca
                        durum.setdefault("metin", []).append(parca)
                        olaylar.append(MotorOlayi("metin", parca))
        if tur in ("assistant", "user"):
            durum.setdefault("oturum_id", "")
            durum.setdefault("arac_adlari", {})
            durum.setdefault("arac_sayisi", 0)
            durum.setdefault("limit", False)
            durum.setdefault("hesap_hatasi", "")
            olaylar += self._mesaji_cevir(kayit, durum)
        return olaylar, False

    # -- tur ici kanal -----------------------------------------------------

    @staticmethod
    def _kullanici_satiri(metin: str) -> str:
        """stream-json girdisinin tek kullanici mesaji (olculen bicim)."""
        return json.dumps({"type": "user", "message": {
            "role": "user", "content": [{"type": "text", "text": metin}]}},
            ensure_ascii=False) + "\n"

    def _kanali_tasi(self, surec, kanal, bekleyen_not: list, durum: dict) -> bool:
        """Kanaldaki notlari ve durdurma istegini surece yazar.

        Doner: stdin hala acik mi. Yazma patlarsa (surec olmus) not
        kanaldan cikmis ama ULASMAMISTIR -- `mesaj` olayi yayilmaz, koltuk
        onu bir sonraki turda iletir. Kaybolan not yoktur.
        """
        try:
            if kanal.durdurulsun and not durum.get("durduruldu"):
                durum["durduruldu"] = True
                surec.stdin.write(json.dumps({
                    "type": "control_request", "request_id": "ofis-durdur",
                    "request": {"subtype": "interrupt"}}) + "\n")
                surec.stdin.flush()
                # Durdurulan turda yeni not gonderilmez; kanalda kalanlar
                # sonraki turun basinda verilir.
                return True
            if durum.get("durduruldu"):
                return True
            for kimlik, not_metni in kanal.al():
                surec.stdin.write(self._kullanici_satiri(not_metni))
                bekleyen_not.append((kimlik, not_metni))
            surec.stdin.flush()
            return True
        except (OSError, ValueError):
            return False

    @staticmethod
    def _stdin_kapat(surec) -> bool:
        try:
            surec.stdin.close()
        except (OSError, ValueError):
            pass
        return False

    @staticmethod
    def _yankilar(mesaj: dict, bekleyen_not: list):
        """Yankisi gelen notu `mesaj` olayina cevirir (ulasti = yanki)."""
        icerik = (mesaj.get("message") or {}).get("content")
        if not isinstance(icerik, list) or not bekleyen_not:
            return
        for blok in icerik:
            if not (isinstance(blok, dict) and blok.get("type") == "text"):
                continue
            yazi = str(blok.get("text") or "")
            for i, (kimlik, not_metni) in enumerate(bekleyen_not):
                if yazi.strip() == not_metni.strip():
                    del bekleyen_not[i]
                    yield MotorOlayi("mesaj", not_metni[:200],
                                     {"kimlik": kimlik, "yol": "tur_ici"})
                    break

    # -- komut -------------------------------------------------------------

    def _baglayici_ortami(self, araclar_kapali: bool = False) -> dict:
        """Hesabin claude.ai baglayicilari bu turda YUKLENMEZ mi (tek kural, iki kip)."""
        return dict(BAGLAYICISIZ) if araclar_kapali else {}

    def _komut_kur(self, oturum: str, *, devam: bool, model: str, efor: str,
                   yazabilir: bool, ek_klasorler: tuple,
                   butce_usd: float, mcp_yapilandirma: str = "",
                   izinli_araclar: tuple = (),
                   araclar_kapali: bool = False,
                   izin_araci: str = "",
                   akis_girdi: bool = False) -> list:
        komut = [
            self.calistirilabilir,
            "-p",
            # AKIS GIRDISI yalniz kanal verilince: tur surerken not
            # yazilabilsin. Diger turlar (lider, danisma, sartname) olculmus
            # `text` yolunda kalir -- degismeyen yolun riski yoktur.
            *(("--input-format", "stream-json", "--replay-user-messages")
              if akis_girdi else ("--input-format", "text")),
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
            # MCP: saf yargi turu yalniz ofisinkini alir (--strict). Arac
            # kullanan tur hesabin baglayicilarini ve patronun MCP'lerini
            # de alir (asagida, `kaynaklar.claude_bayraklari`).
            *(("--strict-mcp-config",) if araclar_kapali else ()),
            # KISISEL CHROME KAPALI (02.10.2026 OLCULDU): patronun Claude
            # ayari "Claude in Chrome varsayilan acik"; etkilesimli (gercek
            # terminal) kipte ajana 21 `claude-in-chrome` araci geliyordu --
            # PATRONUN KISISEL Chrome'unu suren (navigate, computer,
            # javascript_tool, read_page). `--strict-mcp-config` ve `--tools`
            # bunlari ENGELLEMIYOR (olculdu); `--no-chrome` engelliyor.
            # Ajanin tarayicisi ofisin kabinidir.
            "--no-chrome",
            "--append-system-prompt",
            SISTEM_EKI_ORTAK + (KANIT_MCP if mcp_yapilandirma else KANIT_METIN),
        ]
        # OFISIN BECERILERI (02.10.2026): depo bir Claude eklentisidir;
        # `--restricted` altinda da yuklenir (olculdu). Saf yargi turu
        # (araclar kapali) beceri kullanamaz, verilmez.
        if not araclar_kapali:
            from .. import beceri as _beceri
            _bk = _beceri.claude_eklentisi()
            if _bk:
                komut += ["--plugin-dir", _bk]
            # MOTORLARDAN GELENLER: eklentiler, patronun MCP'leri, kapatilan
            # baglayicilar listeden cikar (olculdu: --disallowedTools ile).
            from .. import kaynaklar as _kay
            _kb = _kay.claude_bayraklari()
            komut += _kb["argv"]
            if _kb["mcp"]:
                komut += ["--mcp-config", _kb["mcp"]]
            if _kb["yasak"]:
                komut += ["--disallowedTools", *_kb["yasak"]]
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

    def _komut_ve_ortam(self, oturum: str, *, devam: bool, model: str, efor: str,
                        yazabilir: bool, ek_klasorler, butce_usd, mcp_yapilandirma: str,
                        izinli_araclar, araclar_kapali: bool, izin_araci: str,
                        akis_girdi: bool, ek_ortam) -> tuple:
        """Turun komutu ve ortami -- TEK yerde: tur da onceden isitma da
        (`sicak_isit`) buradan gecer; iki kopya olsaydi anahtar kayardi ve
        bekleyen surec hic kullanilmazdi."""
        komut = self._komut_kur(
            oturum, devam=devam, model=model, efor=efor, yazabilir=yazabilir,
            ek_klasorler=ek_klasorler, butce_usd=butce_usd,
            mcp_yapilandirma=mcp_yapilandirma, izinli_araclar=izinli_araclar,
            araclar_kapali=araclar_kapali, izin_araci=izin_araci,
            akis_girdi=akis_girdi,
        )
        self._arguman_dogrula(komut)
        # SIRLAR AYIKLANIR. claude turu hicbir dis servis anahtarina
        # ihtiyac duymaz; `izinli` bos birakiliyor. Ajanin elinde
        # `Bash(echo *)` var -- gecen her anahtar, terminal kaniti olarak
        # tahtaya dusebilir (bkz. tip.SIR_ONEKLERI).
        ortam = ortam_hazirla(os.environ, ek={**TUR_ORTAMI,
                                              **self._baglayici_ortami(araclar_kapali),
                                              **(ek_ortam or {})},
                              izinli=tuple(ek_ortam or ()))
        # Safe mode acik kalirsa kendi MCP yapilandirmamiz da devre disi
        # kalir; turu yalitmanin yolu safe mode degil, acik bayraklar.
        ortam.pop("CLAUDE_CODE_SAFE_MODE", None)
        ortam.pop("CLAUDE_CODE_SIMPLE", None)
        return komut, ortam

    def sicak_isit(self, *, klasor: str, model: str = "", efor: str = "normal",
                   yazabilir: bool = True, ek_klasorler: tuple = (), butce_usd=None,
                   mcp_yapilandirma: str = "", izinli_araclar: tuple = (),
                   ek_ortam: dict = None, araclar_kapali: bool = False,
                   izin_araci: str = "") -> bool:
        """Bir turu KOSMADAN, ayni komutla bekleyen sureci hazirlar (panel
        acilisi ve tazeleme). Ayni anahtarda taze bir surec varsa dokunmaz.
        Mesaj gonderilmez, limit harcanmaz. Donus: yeni surec acildi mi."""
        if not self.calistirilabilir:
            return False
        kok = Path(klasor).expanduser().resolve()
        if not kok.is_dir():
            return False
        komut, ortam = self._komut_ve_ortam(
            str(uuid.uuid4()), devam=False, model=model, efor=efor, yazabilir=yazabilir,
            ek_klasorler=ek_klasorler, butce_usd=butce_usd,
            mcp_yapilandirma=mcp_yapilandirma, izinli_araclar=izinli_araclar,
            araclar_kapali=araclar_kapali, izin_araci=izin_araci,
            akis_girdi=True, ek_ortam=ek_ortam)
        anahtar = _sicak_anahtar(komut, kok, ortam)
        with _SICAK_KILIT:
            k = _SICAK.get(anahtar)
            taze = (k is not None and k["surec"].poll() is None
                    and time.monotonic() - k["an"] < SICAK_OMUR_SN - SICAK_TAZELE_PAYI_SN)
        if taze:
            return False
        _sicak_hazirla(anahtar, komut, kok, ortam)
        return True

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
            # BAGLAM: son model cagrisinin girdisi + ciktisi (06.10.2026).
            _kul = ((mesaj.get("message") or {}).get("usage") or {}) \
                if isinstance(mesaj.get("message"), dict) else {}
            if _kul:
                durum["son_baglam"] = int(
                    (_kul.get("input_tokens") or 0) + (_kul.get("output_tokens") or 0)
                    + (_kul.get("cache_read_input_tokens") or 0)
                    + (_kul.get("cache_creation_input_tokens") or 0))
            # CLI hesap sorununu AYRI bir alanla bildirir (semasi CLI'in
            # kendi kodundan okundu, 27.09.2026). Okunmasaydi dusen oturum
            # siradan bir "basarisiz tur" gibi gorunur ve hatirlanmazdi.
            hata = str(mesaj.get("error") or "")
            if hata in motor_saglik.HESAP_SORUNLARI:
                durum["hesap_hatasi"] = hata
            elif hata == "rate_limit":
                durum["limit"] = True
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
            # `+=`: akis girdisinde bir tur birden cok `result` uretebilir
            # (olculdu: kullanim SONUC BASINA gelir, 423 sonra 209 cikti
            # jetonu). `total_cost_usd` ise BIRIKIMLIDIR (0,0068 -> 0,0103),
            # o yuzden maliyet `=` kalir. Tek sonuclu turda ikisi ayni.
            durum["jeton"] += int(
                (kullanim.get("input_tokens") or 0)
                + (kullanim.get("output_tokens") or 0)
                + (kullanim.get("cache_read_input_tokens") or 0)
                + (kullanim.get("cache_creation_input_tokens") or 0)
            )
            dokum_ekle(durum.setdefault("jeton_dokumu", {}), kullanim)
            for _mad, _mu in (mesaj.get("modelUsage") or {}).items():
                if isinstance(_mu, dict) and _mu.get("contextWindow"):
                    durum["baglam_siniri"] = int(_mu["contextWindow"])
                    baglam_siniri_ogren(durum.get("model") or _mad, _mu["contextWindow"])
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
