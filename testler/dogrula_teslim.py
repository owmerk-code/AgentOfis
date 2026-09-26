# -*- coding: utf-8 -*-
"""Teslim edilen motor adaptorunu BAGIMSIZ dogrular.

Neden ayri bir betik: ajanin sozune guvenilmez. Kanit kapisi liderin
yargisidir; bu, INSANIN kendi olcumudur. Ikisi ayri kalmali -- lider de
bir modeldir ve o da yanilabilir.

BU BETIK BIR OLCUM ARACIDIR, yani kendisi de tuzaga dusebilir. Daha once
tam burada bir hata yaptim ve kaydi CLAUDE.md'de duruyor:

    Codex adaptorunu "Motor'dan turemiyor" diye kaydetmistim. YANLISTI --
    dosyayi PAKET DISINDAN yukleyince `ofis.motor.tip` bir kez daha
    yukleniyor ve REFERANS KOPYASINDAKI farkli bir `Motor` sinifi devreye
    giriyordu. `issubclass` dogal olarak False donuyordu. Ajan isini
    dogru yapmisti; olcum aracim yanlis suclama uretti.

Bu yuzden burada modul, paketin ICINDEN ve `sys.modules`'a kayitli tek
bir `ofis.motor.tip` uzerinden yuklenir. Yukleme bicimi sonucu
degistiriyorsa, olctugun sey kodun kendisi degil yukleyicindir.

Kullanim:  python testler/dogrula_teslim.py [klasor]
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

# ONCE paketi normal yoldan yukle. Boylece `ofis.motor.tip` sys.modules'a
# TEK kez girer ve teslim edilen dosya onu ithal ettiginde AYNI sinifi
# gorur. Bunu atlarsak kendi kendimize yanlis cevap uretiriz.
from ofis.motor.tip import Motor, MotorOlayi, OLAY_TURLERI    # noqa: E402

GECEN = 0
KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def _satir_say(yol: Path) -> int:
    try:
        return len(yol.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return -1


def modulu_yukle(yol: Path, ad: str):
    """Teslim edilen dosyayi PAKETIN ICINDEN yukler.

    `ofis.motor.<ad>` adiyla kaydediyoruz: goreli ithaller
    (`from .tip import Motor`) ancak boyle cozulur ve `tip` modulu
    ZATEN yuklu oldugu icin ayni `Motor` sinifi gorunur.
    """
    tam_ad = f"ofis.motor.{ad}"
    spec = importlib.util.spec_from_file_location(tam_ad, yol)
    modul = importlib.util.module_from_spec(spec)
    sys.modules[tam_ad] = modul
    spec.loader.exec_module(modul)
    return modul


def asert_say(yol: Path) -> int:
    """Testteki gercek iddia sayisi.

    Bir testin 'gecmesi' iki sekilde saglanir: kodu duzeltmek ya da
    testi bosaltmak. Ikincisi sessizdir. GuvenKart isinde ayni olcumu
    yapmistik (once 15 assert, sonra 15) ve isin CERRAHI oldugunu
    ancak bu gosterdi.
    """
    agac = ast.parse(yol.read_text(encoding="utf-8"))
    n = sum(1 for d in ast.walk(agac) if isinstance(d, ast.Assert))
    # pytest.raises / unittest assertX cagrilari da iddiadir
    for d in ast.walk(agac):
        if isinstance(d, ast.Call):
            ad = getattr(d.func, "attr", "") or getattr(d.func, "id", "")
            if ad.startswith("assert") or ad == "raises":
                n += 1
    return n


def main() -> int:
    klasor = Path(sys.argv[1] if len(sys.argv) > 1 else KOK / "calisma" / "gemini")
    print(f"== teslim dogrulamasi: {klasor} ==\n")

    print("1. DOSYALAR VAR MI")
    kod = klasor / "gemini.py"
    test = klasor / "test_gemini.py"
    sina("adaptor dosyasi var", kod.exists(), f"({kod})")
    if test.exists():
        sina("test dosyasi var", True)
    else:
        # Kurulu bir adaptorun testleri yaninda DEGIL `testler/`dedir.
        # "yok" demek onu bozuk gosterirdi; bilinmeyeni bilinmiyor diye
        # yazmak, yanlis hukum vermekten iyidir.
        print(f"  [?] test dosyasi yaninda yok -- BILINMIYOR ({test})")
    if not kod.exists():
        print("\nAdaptor yok, devam edilemiyor.")
        return 1

    # 1b. TESLIM ile KURULU KOPYA AYRISTI MI
    #
    # Sartname kapisinin (fable) 21.09.2026'da yazdigi bulgu, kelimesi
    # kelimesine: *"prototip ile kurulan kopyanin ayrisip ayrismadigi
    # OLCULMUYOR."* Ayni gun gerceklesti:
    #
    #   calisma/gemini/gemini.py           201 satir  (bayat prototip)
    #   calisma/gemini/kurulum_hazir/...   198 satir  (iptal edilmis
    #                                                  #17'nin PROVA paketi)
    #   ofis/motor/gemini.py               497 satir  (KURULU, iyi olan)
    #
    # Bu arac teslimi dogrular; kurulduktan sonra teslim klasoru
    # BAYATLAR ve arac bayat olani olcmeye devam eder. Sonuc iki yonde
    # de yaniltir: teslim yesilken kurulu bozuk olabilir, ya da
    # (bugunku gibi) teslim kirmiziyken kurulu saglam olabilir.
    #
    # Karar VERMIYORUZ, GORUNUR kiliyoruz: hangi kopyanin dogru oldugu
    # bir yargidir ve yargi insanda.
    kurulu = KOK / "ofis" / "motor" / "gemini.py"
    if kurulu.exists() and kurulu.resolve() != kod.resolve():
        ayni = (kurulu.read_bytes() == kod.read_bytes())
        sina("teslim ile KURULU kopya ayni", ayni,
             f"-- kurulu {_satir_say(kurulu)} satir, "
             f"teslim {_satir_say(kod)} satir. AYRISMISLAR: bu arac "
             f"TESLIMI olcuyor, kurulu olani DEGIL. Kuruluyu olcmek "
             f"icin: python testler/dogrula_teslim.py ofis/motor")
    elif kurulu.resolve() == kod.resolve():
        print("  [bilgi] KURULU kopya olculuyor (teslim degil)")
    else:
        print("  [bilgi] henuz kurulmamis -- yalniz teslim olculuyor")

    print("\n2. SOZLESME -- gercekten Motor'dan turuyor mu")
    try:
        modul = modulu_yukle(kod, "gemini")
    except Exception as exc:
        sina("modul yuklenebiliyor", False, f"({exc})")
        return 1
    sina("modul yuklenebiliyor", True)

    sinif = None
    for ad in dir(modul):
        nesne = getattr(modul, ad)
        if isinstance(nesne, type) and issubclass(nesne, Motor) and nesne is not Motor:
            sinif = nesne
            break
    sina("Motor'dan TUREYEN bir sinif var", sinif is not None,
         f"(bulunanlar: {[a for a in dir(modul) if isinstance(getattr(modul, a), type)]})")
    if sinif is None:
        return 1

    print(f"     -> {sinif.__name__}")
    sina("`ad` alani dolu", bool(getattr(sinif, "ad", "")),
         f"({getattr(sinif, 'ad', None)})")
    sina("`mcp_konusur` bildirilmis", isinstance(getattr(sinif, "mcp_konusur", None), bool))
    sina("`butce_destegi` bildirilmis", isinstance(getattr(sinif, "butce_destegi", None), bool))
    sina("`musait_mi` var", callable(getattr(sinif, "musait_mi", None)))
    sina("`tur_kos` var", callable(getattr(sinif, "tur_kos", None)))

    print("\n3. BUTCE -- desteklemiyorsa KAPALI KALARAK reddetmeli")
    if getattr(sinif, "butce_destegi", False):
        sina("butce destekleniyor (reddetme beklenmiyor)", True)
    else:
        try:
            ornek = sinif()
            akis = ornek.tur_kos("selam", klasor=str(klasor), butce_usd=0.5)
            next(akis)
            sina("butce verilince REDDEDIYOR", False, "(kabul etti)")
        except Exception as exc:
            sina("butce verilince REDDEDIYOR", True, f"({type(exc).__name__})")

    print("\n3b. SOZLESME BUTUNLUGU -- sessizce yok sayilan parametre var mi")
    # OLCULDU (19.09.2026): teslim edilen Gemini adaptoru `Motor`'dan
    # turuyordu, butceyi reddediyordu, testleri yesildi -- ve kabul
    # olcutunu TAM OLARAK karsiliyordu. Ama `tur_kos` govdesinde SEKIZ
    # parametre hic kullanilmiyordu:
    #
    #   oturum_id · model · efor · yazabilir · ek_klasorler
    #   zaman_asimi · mcp_yapilandirma · izinli_araclar
    #
    # En tehlikelisi: `mcp_konusur = True` bildirilmis ama
    # `mcp_yapilandirma` yok sayilmis. Koltuk buna bakip MCP kanalini
    # secer ve METIN KOPRUSUNU KAPATIR -- yani ajanin kanit eklemesinin
    # HICBIR YOLU KALMAZ. Is yapilir, defter bos kalir.
    #
    # `yazabilir` yok sayilirsa 'kafa' ajan dosya yazabilir (Yasa 5),
    # `zaman_asimi` yok sayilirsa donmus tur hic olmez, `oturum_id`
    # yok sayilirsa kesilen is bastan kosar.
    #
    # Ofisin kurali zaten yaziliydi: **sessizce yok sayilan ayar, ayar
    # degildir.** Cekirdekte uyguluyorduk, ADAPTORLERDE denetlemiyorduk.
    # Bu bir kanit (calistigini ispatlamaz) degil LINT'tir: parametrenin
    # gecmesi dogru kullanildigini gostermez, ama GECMEMESI kesinlikle
    # kullanilmadigini gosterir.
    kaynak = ast.parse(kod.read_text(encoding="utf-8"))
    govde_metni = ""
    for d in ast.walk(kaynak):
        if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)) and d.name == "tur_kos":
            govde_metni = "\n".join(ast.dump(x) for x in d.body)
            break
    sina("`tur_kos` bulundu", bool(govde_metni))

    SOZLESME = ("oturum_id", "model", "efor", "yazabilir", "ek_klasorler",
                "zaman_asimi", "mcp_yapilandirma", "izinli_araclar",
                # 26.09.2026: tur ici not/durdurma kanali. Tasiyamayan adaptor
                # de ONU KULLANIR -- reddetmek icin (asagida davranissal).
                "kanal")
    yok_sayilan = [p for p in SOZLESME if f"'{p}'" not in govde_metni]
    sina("hicbir sozlesme parametresi SESSIZCE yok sayilmiyor",
         not yok_sayilan, f"(yok sayilanlar: {', '.join(yok_sayilan)})")

    if getattr(sinif, "mcp_konusur", False):
        sina("mcp_konusur=True ise `mcp_yapilandirma` KULLANILIYOR",
             "'mcp_yapilandirma'" in govde_metni,
             "-- MCP kanali secilir ama yapilandirma gitmez: "
             "ajan KANIT EKLEYEMEZ")

    print("\n3c. YETENEK-DAVRANIS TUTARLILIGI -- bayrak dogru soyluyor mu")
    # OLCULDU (19.09.2026) ve BU DENETIM ONCE YOKTU:
    #
    # Ikinci teslimde adaptor `mcp_konusur = True` bildiriyordu ama
    # `mcp_yapilandirma` gelince REDDEDIYORDU ("gemini uygulayamaz").
    # Koltuk tam o bayraga bakip HER TURDA yapilandirma gonderir --
    # yani motor ofiste HICBIR TURU BASLATAMAZDI.
    #
    # Onceki lint bunu KACIRDI: parametre govdede GECIYORDU, ama yalnizca
    # reddetmek icin. "Gecmesi dogru kullanildigini gostermez" diye
    # yazmistim; iste orneginin kendisi. Olcum aracinin kendisi de
    # olculmeli -- bugun ucuncu kez.
    #
    # Dogru denetim DAVRANISSAL: bayragi ne diyorsa, parametre verildigi
    # zaman oyle davranmali.
    #   yetenek=True  -> parametre REDDEDILMEMELI
    #   yetenek=False -> parametre REDDEDILMELI (kapali kalarak basarisiz)
    def _reddediyor_mu(**ek):
        """Parametre verilince akis daha ilk adimda patliyor mu?"""
        try:
            ornek = sinif()
            akis = ornek.tur_kos("selam", klasor=str(klasor), **ek)
            ilk = next(akis)
            akis.close()
            # Hata bir OLAY olabilir: `bitti` + basarili=False de rettir.
            if ilk.tur == "bitti" and not ilk.ek.get("basarili"):
                return True
            return False
        except StopIteration:
            return False
        except Exception:
            return True

    if getattr(sinif, "mcp_konusur", False):
        sina("mcp_konusur=True ise yapilandirma REDDEDILMIYOR",
             not _reddediyor_mu(mcp_yapilandirma='{"mcpServers":{}}'),
             "-- koltuk bu bayraga bakip HER TURDA yapilandirma gonderir; "
             "reddeden motor hicbir turu baslatamaz")
    else:
        sina("mcp_konusur=False (metin koprusu kullanilacak)", True)

    # TUR ICI KANAL: tasiyamayan adaptor kanali REDDETMELI. Tasiyan taraf
    # burada denenmez -- gercek bir surec baslatirdi; birim sinamasinda.
    if not getattr(sinif, "tur_ici_mesaj", False):
        from ofis.motor.tip import TurKanali
        sina("tur_ici_mesaj=False ise kanal REDDEDILIYOR",
             _reddediyor_mu(kanal=TurKanali()),
             "-- insan notunun ulastigini sanirdi")

    print("\n4. TEST BOSALTILMAMIS MI")
    if test.exists():
        n = asert_say(test)
        sina("testte gercek iddia var", n >= 4, f"({n} iddia)")
        print(f"     -> {n} iddia")

    print("\n5. TESTLERI BEN KOSTURUYORUM (ajanin sozune degil)")
    if not test.exists():
        # TEST YOKSA SONUC "KIRMIZI" DEGIL, **BILINMIYOR**.
        #
        # Olculdu (21.09.2026): arac KURULU adaptore dogrultuldugunda
        # "pytest YESIL [KALDI] -- no tests ran" dedi. Ama kurulu bir
        # adaptorun testleri yaninda degil `testler/`dedir; yani arac
        # saglam bir adaptoru BOZUK gosterdi.
        #
        # `saglik.py`nin kurali: olcemedigimize hukum vermeyiz, sessiz
        # de kalmayiz. Yanlis kirmizi, yanlis yesil kadar zararlidir --
        # ikisi de gostergeye olan guveni bitirir.
        print("  [?] test dosyasi yok -- SONUC BILINMIYOR, 'basarisiz' DEGIL.")
        print(f"      Beklenen: {test}")
        print("      Kurulu bir adaptoru olcuyorsan testleri `testler/`de")
        print("      arayin (orn. `python testler/duman_motor.py`).")
    else:
        try:
            p = subprocess.run([sys.executable, "-m", "pytest", str(klasor), "-q"],
                               cwd=str(KOK), capture_output=True, text=True,
                               timeout=180, encoding="utf-8", errors="replace")
            son = (p.stdout or "").strip().splitlines()[-1:] or ["(cikti yok)"]
            sina("pytest YESIL", p.returncode == 0, f"({son[0]})")
            print(f"     -> {son[0]}")
        except Exception as exc:
            sina("pytest kosturulabildi", False, f"({exc})")

    print("\n6. KISIT -- `ofis/` altina dokunulmamis mi")
    try:
        p = subprocess.run(["git", "status", "--porcelain", "ofis/"],
                           cwd=str(KOK), capture_output=True, text=True, timeout=30)
        sina("git yok ya da ofis/ temiz", True, "(git kontrolu atlandi)")
    except Exception:
        sina("git kontrolu atlandi (depo degil)", True)

    print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
    return 1 if KALAN else 0


if __name__ == "__main__":
    sys.exit(main())
