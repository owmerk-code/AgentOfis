# -*- coding: utf-8 -*-
"""Gemini CLI adaptoru: `gemini -p ... --output-format stream-json`.

Yapi `claude.py`den alindi (Popen + okuyucu iplik + nabiz + surec agacini
kesme); degisen sey motorun SOZLUGUDUR, akisin sekli degil.

BAYRAKLAR TAHMIN DEGIL -- hepsi bu makinede `gemini 0.52.0` uzerinde
`--help` kosturularak ve gercek tur alinarak ogrenildi:

* `-p/--prompt` etkilesimsiz kip, `-o/--output-format {text,json,stream-json}`.
* `--approval-mode {default,auto_edit,yolo,plan}` -- **`plan` SALT
  OKUNURDUR**. `yazabilir=False` bununla uygulanir; brifingde rica
  edilen kural, kural degildir.
* `--session-id <UUID>` yeni oturumu BIZIM verdigimiz kimlikle baslatir,
  `-r/--resume` surdurur. Kimlik `oturum_id`de yasar.
* `--include-directories` ek klasorler.
* `-m/--model`.
* `--skip-trust` sart: OLCULDU, bayraksiz her tur `cikis 55` ile duser --
  "Gemini CLI is not running in a trusted directory". Ajanlar
  etkilesimsiz kosar; "interaktif modda guven" secenegi bizde yoktur.
  Guvenlik gevsetmesi degil: ajan zaten kendi klasorune bagli.
* TUR BASINA BUTCE TAVANI YOK -- `butce_destegi = False` ve butce
  verilirse tur HIC BASLAMADAN reddedilir. Para kontrolleri kapali
  kalarak basarisiz olur.
* ZAMAN ASIMI BAYRAGI YOK -- ama bu, uygulanamaz demek DEGILDIR:
  adaptor kendi surecini keser. Bir yetenegi "CLI'da bayrak yok" diye
  reddetmek, yapilabilecek bir isi yapmamaktir.

WINDOWS -- `.CMD` TUZAGI (olculdu): PATH'teki `gemini` bir npm
sarmalayicisidir (`gemini.CMD`) ve Python'dan dogrudan cagrilinca
`FileNotFoundError: [WinError 2]` verir. Yaninda `.exe` YOKTUR; gercek
giris noktasi `node <npm>/node_modules/@google/gemini-cli/bundle/gemini.js`
olarak olculdu ve calistigi dogrulandi. Ayni tuzak bu projede claude ve
codex'te de yasandi: cmd.exe, satir sonu tasiyan bir argumani komut
ayraci sayip SONRAKI BAYRAKLARI SESSIZCE DUSURUR.

MCP: `mcp_konusur = False`. Gemini MCP'yi kendi ayar dosyasindan yonetir
(`gemini mcp`, `--allowed-mcp-server-names`); bizim tur basina urettigimiz
`--mcp-config` esdegeri YOK. Yanlis bir `True`, koltugu MCP kanalini
secmeye ve METIN KOPRUSUNU KAPATMAYA iter -- ajan kanit ekleyemez ve is
hic kapanmaz. Bayragin isi, motorun NE YAPABILDIGINI dogru soylemektir.
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
from pathlib import Path
from typing import Iterator

from .tip import ortam_hazirla, Motor, MotorOlayi, MotorHatasi, MotorYokHatasi

_PENCERE_YOK = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_SON = object()

VARSAYILAN_ZAMAN_ASIMI = 1800.0
NABIZ_ARALIGI = 1.0

#: `yazabilir` -> `--approval-mode`. 'plan' salt okunurdur; 'yolo' butun
#: araclari otomatik onaylar (etkilesimsiz turda soru sorulamaz, cevap
#: verecek kimse yoktur -- soran arac sonsuza kadar bekler).
ONAY_YAZAR = "yolo"
ONAY_OKUR = "plan"

SISTEM_EKI_ORTAK = (
    "AgentOfis'te bir ajansin. Baglamin klasorundeki BRIFING.md dosyasidir; "
    "uzun bir iste savrulursan geri donup oku. "
    "Turkce yaz. "
    "Yalniz brifingdeki YAZMA ALANI icine yaz -- disina cikma; o alanlar "
    "baska ajanlara kilitli olabilir."
)

#: Gemini'nin `--append-system-prompt` karsiligi yoktur; sistem ekini
#: metnin basina BIZ koyariz. MCP konusmadigi icin kanit tek yoldan
#: gelir: METIN KOPRUSU.
KANIT_METIN = (
    "\n\n"
    "ISI BITIRINCE KANIT SATIRI YAZMAK ZORUNDASIN. Kanitsiz gorev "
    "kapanmaz. Son mesajinin sonuna, her kanit icin ayri satir olarak, "
    "TAM OLARAK su bicimde yaz:"
    "\n\n"
    "KANIT terminal: <kosturdugun komut> -> <ciktinin ozeti>\n"
    "KANIT dosya: <yol> -> <ne yaptin>"
    "\n\n"
    "Ciktiyi UYDURMA: yalnizca gercekten kosturdugun komutun gercek "
    "ciktisini yaz."
)


class GeminiMotoru(Motor):
    """`gemini` CLI'ini tur basina bir surec olarak kosturur."""

    ad = "gemini"
    #: Tur basina `--mcp-config` esdegeri yok (bkz. dosya basi).
    mcp_konusur = False
    #: Tur basina harcama tavani yok; butce verilirse REDDEDER.
    butce_destegi = False

    def __init__(self, *, calistirilabilir: str = "",
                 zaman_asimi: float = VARSAYILAN_ZAMAN_ASIMI) -> None:
        self.calistirilabilir = calistirilabilir or self._calistirilabilir_bul()
        self.zaman_asimi = zaman_asimi

    # -- kurulum -----------------------------------------------------------

    @staticmethod
    def _calistirilabilir_bul() -> list:
        """Sarmalayiciyi ATLAR, gercek giris noktasini dondurur.

        Doner: calistirilacak komut ONEKI (liste), orn.
        `["node", ".../bundle/gemini.js"]`.

        OLCULDU: `subprocess.run(["gemini", ...])` -> WinError 2. PATH'teki
        `gemini` bir npm sarmalayicisi; yaninda `.exe` yok. `.CMD` uzerinden
        kosmak cmd.exe'ye girmek demektir ve cmd.exe satir sonu tasiyan bir
        argumani komut ayraci sayip sonraki bayraklari SESSIZCE dusurur.
        Hata cikmaz: `rc=0`, akis normal gorunur, ama `--model` hic
        ulasmamis olur.
        """
        ozel = os.environ.get("OFIS_GEMINI_YOLU", "").strip()
        if ozel:
            y = Path(ozel)
            return ["node", str(y)] if y.suffix == ".js" else [str(y)]

        sarmalayici = shutil.which("gemini")
        adaylar = []
        if sarmalayici:
            npm = Path(sarmalayici).parent
            adaylar.append(npm / "node_modules" / "@google" / "gemini-cli"
                           / "bundle" / "gemini.js")
        adaylar.append(Path.home() / "AppData" / "Roaming" / "npm"
                       / "node_modules" / "@google" / "gemini-cli"
                       / "bundle" / "gemini.js")
        for aday in adaylar:
            if aday.exists():
                return ["node", str(aday)]
        return []

    def musait_mi(self) -> bool:
        """CLI kurulu MI ve ANAHTAR var mi -- ikisi ayri sart.

        Anahtarsiz tur baslar ve `cikis 41` ile duser ("Please set an Auth
        method..."). Jeton yakmaz ama zaman yakar ve orkestra bunu
        "ilerleme yok" diye okur: SEBEP GORUNMEZ. Musaitligi onceden
        olcmek, sebebi gorunur kilar.
        """
        if not self.calistirilabilir:
            return False
        if not shutil.which("node"):
            return False
        # ANAHTAR KASADA DA OLABILIR, yalniz ortamda degil.
        # Olculdu (21.09.2026): CLI kuruluydu (0.52.0), anahtar kasada
        # durdu ve bu islev yine False dondu -- yani dorduncu motor
        # `yetenek`te, `saglik`ta ve `ekip oner`de "kurulu degil"
        # gorunuyordu. `gorsel.py`de bir kez odenen KAPALI DONGUNUN
        # aynisi: `kabuk anahtar ekle` anahtari KASAYA yazar, kod
        # kasaya hic bakmazdi.
        from .. import gizli
        return bool(gizli.anahtar_oku("GEMINI_API_KEY")
                    or gizli.anahtar_oku("GOOGLE_GENAI_USE_VERTEXAI")
                    or gizli.anahtar_oku("GOOGLE_GENAI_USE_GCA"))

    # -- komut -------------------------------------------------------------

    def _komut_kur(self, *, oturum_id: str, model: str, yazabilir: bool,
                   ek_klasorler: tuple) -> list:
        komut = list(self.calistirilabilir)
        komut += ["--output-format", "stream-json", "--skip-trust"]
        # Yazma yasagi SUREC duzeyinde: 'plan' salt okunur kiptir.
        komut += ["--approval-mode", ONAY_YAZAR if yazabilir else ONAY_OKUR]
        if model:
            komut += ["-m", model]
        if oturum_id:
            komut += ["--session-id", oturum_id]
        for k in (ek_klasorler or ()):
            komut += ["--include-directories", str(k)]
        return komut

    def _arguman_dogrula(self, komut: list) -> None:
        """Satir sonlu argumani REDDEDER (`.CMD` sessiz bayrak dusurmesi).

        Brifing metni zaten `-p` yerine stdin'den gectigi icin bu durum
        normalde olusmaz; kapi, bir gun birinin metni arguman yapmasini
        engellemek icin duruyor. Bozulma SESSIZ oldugundan uyari yetmez.
        """
        ilk = str(komut[0]).lower()
        if not (ilk.endswith(".cmd") or ilk.endswith(".bat")):
            return
        for arguman in komut[1:]:
            if "\n" in str(arguman) or "\r" in str(arguman):
                raise MotorHatasi(
                    "Satir sonu tasiyan arguman `.CMD` uzerinden gecirilemez: "
                    "cmd.exe onu komut ayraci sayar ve SONRAKI BAYRAKLARI "
                    "sessizce dusurur. Metni stdin'den gecir.")

    # -- tur ---------------------------------------------------------------

    def tur_kos(self, metin: str, *, klasor: str, oturum_id: str = "",
                model: str = "", efor: str = "normal", yazabilir: bool = True,
                ek_klasorler: tuple = (), butce_usd: float = None,
                zaman_asimi: float = None, mcp_yapilandirma: str = "",
                izinli_araclar: tuple = (),
                ek_ortam: dict = None,
                izin_araci: str = "",
                kanal=None) -> Iterator[MotorOlayi]:
        # TUR ICI KANAL tasinamiyor (`-p` tek yonlu; ACP olculmedi, A1).
        # Sessizce yok saysaydik insan notunun ulastigini sanirdi.
        if kanal is not None:
            raise MotorHatasi(
                f"{self.ad} tur surerken not alamiyor; not bir sonraki "
                "turun basinda iletilmeli.")
        # IZIN KANCASI UYGULANAMIYOR -> KAPALI KALARAK REDDEDILIR.
        #
        # Sessizce yok saysaydik cagiran, riskli her cagrinin ofise
        # soruldugunu SANIRDI -- oysa hicbiri sorulmazdi. Para ve yayin
        # kontrolleri bu projede her zaman fail-closed olur (codex'in
        # butce tavanini reddetmesiyle ayni ilke).
        if izin_araci:
            raise MotorHatasi(
                f"{self.ad} izin kancasini uygulayamiyor "
                "(`--permission-prompt-tool` karsiligi yok); riskli "
                "cagrilar ofise sorulamazdi.")
        metin = (metin or "").strip()
        if not metin:
            raise MotorHatasi("Bos brifing kosturulamaz.")
        if not Path(klasor).is_dir():
            raise MotorHatasi(f"Calisma klasoru yok: {klasor}")

        # PARA KONTROLU KAPALI KALARAK BASARISIZ OLUR. Kullanici tavan
        # koydugunu sanip koymamis olmasin: faturayi gorene kadar
        # anlasilmaz.
        if butce_usd:
            raise MotorHatasi(
                "gemini tur basina butce tavani uygulayamaz (CLI'da boyle "
                "bir bayrak yok). Butceyi kaldir ya da bu isi butce "
                "destekleyen bir motora ver (claude).")

        # `mcp_yapilandirma` SESSIZCE yok sayilmaz: `mcp_konusur=False`
        # oldugu icin koltuk zaten gondermez. Yine de gelirse, kanit
        # kanalinin yanlis secildigini soyleyen bir cagri hatasidir.
        if mcp_yapilandirma:
            raise MotorHatasi(
                "gemini tur basina MCP yapilandirmasi alamaz "
                "(mcp_konusur=False). Kanit METIN KOPRUSUYLE toplanir; "
                "yapilandirma gonderen cagiran yanlis kanali secmis.")

        # `efor` ve `izinli_araclar`: gemini'de karsiligi YOK.
        # Sessizce yutmuyoruz -- olayla bildiriyoruz. Gorunmeyen bir
        # bosluk, sonra "neden efor uygulanmadi" sorusunu cevapsiz birakir.
        atlanan = []
        if efor and efor != "normal":
            atlanan.append(f"efor={efor}")
        if izinli_araclar:
            atlanan.append(f"izinli_araclar={len(izinli_araclar)} adet")

        if not self.calistirilabilir:
            yield MotorOlayi("bitti", "", {
                "basarili": False, "sebep": "motor_yok",
                "hata": "gemini CLI bulunamadi. `npm i -g @google/gemini-cli` "
                        "ya da OFIS_GEMINI_YOLU ile yolu ver."})
            return
        if not self.musait_mi():
            yield MotorOlayi("bitti", "", {
                "basarili": False, "sebep": "kimlik_yok",
                "hata": "GEMINI_API_KEY kurulu degil. "
                        "`python -m ofis.kabuk anahtar ekle GEMINI_API_KEY`"})
            return

        komut = self._komut_kur(oturum_id=oturum_id, model=model,
                                yazabilir=yazabilir, ek_klasorler=ek_klasorler)
        self._arguman_dogrula(komut)

        for a in atlanan:
            yield MotorOlayi("hata", f"gemini bunu uygulayamaz: {a}", {})

        # ANAHTAR ACIKCA GECIRILIR, gerisi ayiklanir. Ajan turu hesabin
        # butun anahtarlarini gormemeli (bkz. tip.SIR_ONEKLERI).
        # HESABIN kimligi de gecer ve adaptorun varsayilanini EZER:
        # `ek_ortam` hangi Gemini hesabiyla kosulacagini soyler
        # (baska bir `GEMINI_API_KEY`). Gecirmeseydik hesap tanimlanir
        # ama hicbir zaman kullanilmazdi -- "sessizce yok sayilan ayar".
        # KASA SON CARE OLARAK OKUNUR -- ve bu bir kapali dongunun
        # kapatilmasidir.
        #
        # OLCULDU (21.09.2026), ilk gercek gemini turunda: `musait_mi()`
        # kasayi okuyordu (bu bir kez duzeltilmisti) ve motor "kurulu"
        # gorunuyordu; ama TUR ORTAMI yalnizca `os.environ`dan
        # kuruluyordu. Anahtar kasada, ortamda degil -> gemini
        # "Please set an Auth method ... GEMINI_API_KEY" deyip cikis 41
        # ile oluyordu.
        #
        # Yani ucuncu kez ayni sekil: BIR YER kasayi okuyor, OTEKI
        # okumuyor; gosterge "hazir" diyor, is kosmuyor. Ayni tuzak once
        # `gorsel.py`de (uc uretici birden), sonra `motor/gemini.py`nin
        # `musait_mi`sinde cikti. Bu yuzden okuma tek yerde toplandi
        # (`gizli.anahtar_oku`) ve burada da O cagriliyor.
        #
        # SIRA: hesabin verdigi (`ek_ortam`) > ortam > kasa.
        # *Acikca verilen deger HER ZAMAN kazanir* -- rolun turu,
        # zincirin ilk basamagi, kota anahtari: ayni ilke.
        _ek = dict(ek_ortam or {})
        if "GEMINI_API_KEY" not in _ek and not os.environ.get("GEMINI_API_KEY"):
            from .. import gizli
            _kasa = gizli.anahtar_oku("GEMINI_API_KEY")
            if _kasa:
                _ek["GEMINI_API_KEY"] = _kasa
        ortam = ortam_hazirla(
            os.environ,
            ek=_ek,
            izinli=("GEMINI_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI",
                    "GOOGLE_GENAI_USE_GCA", "GOOGLE_APPLICATION_CREDENTIALS")
                   + tuple(_ek))

        tam_metin = SISTEM_EKI_ORTAK + KANIT_METIN + "\n\n---\n\n" + metin
        sinir = float(zaman_asimi or self.zaman_asimi)
        self._son_olcum = None
        self._son_model = ""
        basladi = time.monotonic()

        try:
            surec = subprocess.Popen(
                komut, cwd=klasor, env=ortam,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, encoding="utf-8",
                errors="replace", bufsize=1, creationflags=_PENCERE_YOK)
        except Exception as exc:
            yield MotorOlayi("bitti", "", {
                "basarili": False, "sebep": "surec", "hata": str(exc)})
            return

        kuyruk: queue.Queue = queue.Queue()

        def oku(akis, etiket):
            try:
                for satir in akis:
                    kuyruk.put((etiket, satir))
            finally:
                kuyruk.put((etiket, _SON))

        for akis, etiket in ((surec.stdout, "cikti"), (surec.stderr, "hata")):
            threading.Thread(target=oku, args=(akis, etiket), daemon=True).start()

        try:
            surec.stdin.write(tam_metin)
            surec.stdin.close()
        except Exception:
            pass

        yield MotorOlayi("basladi", " ".join(komut[:2]), {"komut": komut})

        biten = 0
        hata_metni = []
        parcalar = []
        son_nabiz = time.monotonic()
        zaman_asti = False

        while biten < 2:
            # ZAMAN ASIMI ADAPTORDE UYGULANIR. CLI'da bayrak yok ama bu,
            # yapilamaz demek degil: donmus bir tur kilidi de sonsuza
            # tutar ve panelde "calisiyor" gorunur -- en pahali yanilgi.
            if time.monotonic() - basladi > sinir:
                zaman_asti = True
                self._sureci_kes(surec)
                break
            try:
                etiket, veri = kuyruk.get(timeout=NABIZ_ARALIGI)
            except queue.Empty:
                simdi = time.monotonic()
                if simdi - son_nabiz >= NABIZ_ARALIGI:
                    son_nabiz = simdi
                    yield MotorOlayi("nabiz", "", {})
                continue
            if veri is _SON:
                biten += 1
                continue
            if etiket == "hata":
                hata_metni.append(veri)
                continue
            for olay in self._satiri_cevir(veri, parcalar):
                yield olay

        try:
            rc = surec.wait(timeout=10)
        except Exception:
            self._sureci_kes(surec)
            rc = -1

        if zaman_asti:
            yield MotorOlayi("bitti", "".join(parcalar), {
                "basarili": False, "sebep": "zaman_asimi",
                "zaman_asimi": True,
                "hata": f"Tur {sinir:.0f} saniyede bitmedi, surec kesildi."})
            return

        olcum = self._olcumu_ozetle(getattr(self, "_son_olcum", None))
        ham_hata = "".join(hata_metni)[:2000]
        limit = any(i in ham_hata.lower()
                    for i in ("quota", "rate limit", "resource_exhausted"))
        yield MotorOlayi("bitti", "".join(parcalar), {
            "basarili": rc == 0, "sebep": "" if rc == 0 else "cikis",
            "cikis": rc, "limit": limit, **olcum,
            "hata": "" if rc == 0 else ham_hata})

    # -- yardimcilar -------------------------------------------------------

    def _satiri_cevir(self, satir: str, parcalar: list):
        """`stream-json` satirini OFISIN olayina cevirir.

        BICIM TAHMIN DEGIL -- gercek bir tur kaydedilip olculdu
        (gemini 0.52.0, `--output-format stream-json`):

            {"type":"init","model":...,"session_id":...,"timestamp":...}
            {"type":"message","role":"assistant","content":"..."}
            {"type":"message","role":"assistant","content":"...","delta":"..."}
            {"type":"result","status":"success","stats":{...}}

        Ilk surumde bu bicim TAHMIN EDILMISTI ("assistant", "text",
        "session_started"...) ve tur basarili gorunup SIFIR metin
        uretiyordu -- cikti kayboluyor, kanit metin koprusunden hic
        gecmiyordu. Sessiz kayip: `basarili=True`, elde hicbir sey yok.

        `delta` onemli: ayni mesaj once tam `content` ile, sonra
        eklemelerle gelir. Ikisini de eklersek metin IKI KEZ birikir ve
        kanit metni bozulur -- bu projede cift kanit sorununu bir kez
        yasadik. Kural: delta varsa YALNIZ delta, yoksa content.
        """
        satir = satir.strip()
        if not satir:
            return
        try:
            d = json.loads(satir)
        except json.JSONDecodeError:
            parcalar.append(satir)
            yield MotorOlayi("metin", satir, {})
            return

        tur = str(d.get("type") or "")

        if tur == "init":
            kimlik = str(d.get("session_id") or "")
            if kimlik:
                yield MotorOlayi("oturum", kimlik, {"oturum_id": kimlik})
            self._son_model = str(d.get("model") or "")
            return

        if tur == "message":
            # ROL FILTRESI SART. OLCULDU: akis KULLANICI mesajini da
            # geri yolluyor; filtresiz aldigimizda "cevap" olarak
            # brifingin kendisi dondu. Kendi sorumuzu cevap sanmak,
            # kanit metnini de bozardi.
            if str(d.get("role") or "assistant") != "assistant":
                return
            # `delta` METIN DEGIL, BAYRAK. OLCULDU:
            #   role='user'      delta=None  content='Sadece OK yaz.'
            #   role='assistant' delta=True  content='OK'
            # Ilk surumde `delta`yi metin sandim ve cevap olarak 'True'
            # dondu. Alan adina bakip tipini VARSAYMAK, olcmemenin ucuz
            # gorunen halidir -- ve burada cikti tamamen bozuldu.
            # Metin her zaman `content`tedir; `delta` yalnizca parcanin
            # artimli olup olmadigini soyler.
            govde = str(d.get("content") or "")
            if govde:
                parcalar.append(govde)
                yield MotorOlayi("metin", govde, {})
            return

        if tur in ("tool_call", "tool_use", "tool"):
            yield MotorOlayi("arac", str(d.get("name") or "arac"), {"ham": d})
            return

        # OLCULDU: gercek akista `tool_result` var. Bunu "bilinmeyen tur"
        # olarak bildiren kural ISE YARADI -- yutsaydik arac sonuclari
        # sessizce kaybolurdu ve kimse fark etmezdi.
        if tur in ("tool_result", "tool_response"):
            yield MotorOlayi("arac_sonuc", str(d.get("name") or "")[:200],
                             {"ham": d})
            return

        if tur == "result":
            # `olcum` diye bir olay turu YOK -- sozlesme (tip.py) onu
            # reddetti ve HAKLI: olcum bir olay degil, turun SONUCUDUR.
            # Koltuk jetonu `bitti.ek`ten okur.
            self._son_olcum = d.get("stats") or {}
            if str(d.get("status") or "") not in ("success", ""):
                yield MotorOlayi("hata", f"gemini sonucu: {d.get('status')}",
                                 {"ham": d})
            return

        if tur == "error":
            yield MotorOlayi("hata", str(d.get("message") or "")[:400],
                             {"ham": d})
            return

        # TANIMADIGIMIZ TUR SESSIZCE ATILMAZ. Bilinmeyen bir olay turu,
        # yarin adaptoru guncellememiz gerektiginin isaretidir; yutarsak
        # o isareti hic gormeyiz.
        yield MotorOlayi("hata", f"gemini: bilinmeyen olay turu '{tur}'",
                         {"ham": d})

    def _olcumu_ozetle(self, ham) -> dict:
        """Gemini'nin `stats` blogundan jeton/model cikarir.

        Olcmedigimiz sey yonetilemez: maliyet gorunmezse "neden bu kadar
        tuttu" sorusu cevapsiz kalir. Gemini dolar vermez (kota tabanli),
        o yuzden `maliyet_usd` UYDURULMAZ -- yok diye 0.0 yazmak, olcum
        gibi gorunen bir tahmin olurdu.
        """
        if not isinstance(ham, dict):
            return {}
        # OLCULDU: `result.stats` duz alanlar tasiyor --
        #   total_tokens · input_tokens · output_tokens · duration_ms
        #   · tool_calls · models{<ad>: {...}}
        ozet = {}
        jeton = int(ham.get("total_tokens") or 0)
        if jeton:
            ozet["jeton"] = jeton
        model_ad = getattr(self, "_son_model", "") or ""
        if not model_ad:
            modeller = ham.get("models")
            if isinstance(modeller, dict) and modeller:
                model_ad = next(iter(modeller))
        if model_ad:
            ozet["model"] = model_ad
        if ham.get("duration_ms"):
            ozet["sure_ms"] = float(ham["duration_ms"])
        return ozet

    @staticmethod
    def _sureci_kes(surec) -> None:
        """Surec AGACINI keser. Cocuk surecler yetim kalmasin."""
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(surec.pid)],
                    capture_output=True, timeout=15,
                    creationflags=_PENCERE_YOK)
            else:
                surec.kill()
        except Exception:
            try:
                surec.kill()
            except Exception:
                pass
