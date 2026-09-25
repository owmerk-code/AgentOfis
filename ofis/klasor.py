# -*- coding: utf-8 -*-
"""Ofisin disina acilan klasorlerin TEK kapisi.

Ajanlar normalde `--restricted` ile kendi klasorlerine hapsedilir. Bu
dogru varsayilan: ajan turu tekrarlanabilir olmali ve insanin kisisel
dosyalari isin icine karismamali.

Ama kullanici isini masaustundeki bir klasorde tutuyor ve olculdu ki
lidere o klasoru soylemenin hicbir yolu yoktu -- lider `--restricted`
sinirinin disini goremiyor, "bulamiyorum" diyordu.

Bu modul o deligi ACAR ama kurala baglar. Uc kural, ucu de bu projede
ODENMIS bir bedelden geliyor:

1. **MUTLAK yol.** Hayalet veritabani dersi: MCP sunucusu AYRI bir
   surecte ve BASKA bir calisma klasorunde kosar; oraya giden her
   goreli yol baska bir yere cozulur ve kimse fark etmez. Surec
   sinirini gecen her sey mutlak olmali.

2. **VAR OLDUGU OLCULUR.** Yanlis yazilmis bir klasor adi sessiz bir
   olum sebebidir: `--add-dir` onu kabul eder, ajan orayi goremez ve
   "dosya yok" der. Ajanin haksiz yere sucland... tam olarak bu sinifta
   bir hata daha yasadik (inceleyici bos klasorde kostu, isi reddetti).
   Yoksa ANINDA reddedilir.

3. **KAYDA GECER.** Klasor acmak bir yetki genisletmesidir. "Hangi
   klasor hangi ise, kimin istegiyle acildi" sorusu alti ay sonra da
   cevaplanabilmeli. Cagiran taraf bunu olaya yazar.

Bir sey BILEREK yapilmiyor: kalici "ofis genelinde acik klasor" listesi
yok. Boyle bir liste bir kez doldurulur ve bir daha bakilmaz; her is
kendi acikligini kendi tasir.
"""

from pathlib import Path

#: Bir klasorun ACILMASI reddedilir: cok genis ya da sistemin kendisi.
#: Genis aciklik, `--restricted` kilidini dekora cevirir -- surucu kokunu
#: acmak, hic kisitlamamakla aynidir.
YASAK_ADLAR = ("windows", "system32", "program files", "program files (x86)",
               "programdata", "appdata", "$recycle.bin")


class KlasorHatasi(Exception):
    """Acilmak istenen klasor kabul edilmedi."""


def klasor_dogrula(ham: str) -> Path:
    """Tek bir klasoru mutlaklastirir ve kabul edilebilir mi diye OLCER.

    Donus mutlak `Path`. Kabul edilmezse `KlasorHatasi` -- sessizce
    atlamak, kullanicinin actigini sandigi bir kapinin kapali kalmasi
    demektir ve bunu ancak ajan "bulamadim" dedigin de anlardi.
    """
    metin = (ham or "").strip().strip('"').strip("'")
    if not metin:
        raise KlasorHatasi("Bos klasor yolu verildi.")

    yol = Path(metin).expanduser()
    try:
        yol = yol.resolve()
    except OSError as exc:
        raise KlasorHatasi(f"Yol cozulemedi: {metin} ({exc})") from None

    if not yol.exists():
        raise KlasorHatasi(
            f"Klasor YOK: {yol}\n"
            "Yanlis yazilmis bir yol sessizce calisiyormus gibi gorunur: "
            "ajan orayi goremez ve 'dosya bulamadim' der. Yolu kontrol et."
        )
    if not yol.is_dir():
        raise KlasorHatasi(
            f"Bu bir klasor degil, dosya: {yol}\n"
            "Dosyanin bulundugu klasoru ver; ajan icinden okur."
        )
    if yol.parent == yol:
        raise KlasorHatasi(
            f"Surucu kokunu acamam: {yol}\n"
            "Butun diski acmak, kisitlamayi tamamen kaldirmakla aynidir. "
            "Isin gercekten gectigi klasoru ver."
        )
    if yol.name.lower() in YASAK_ADLAR:
        raise KlasorHatasi(
            f"Sistem klasoru acilamaz: {yol}\n"
            "Ajanin isi burada olamaz; olsaydi bile bedeli kabul edilemez."
        )
    return yol


def klasorleri_dogrula(hamlar) -> list:
    """Coklu hali. Sirayi ve benzersizligi korur.

    Sirayi korumak onemli: ilk klasor, insanin 'asil' isaret ettigidir
    ve brifingde once yazilir.
    """
    sonuc = []
    for ham in (hamlar or ()):
        yol = klasor_dogrula(ham)
        if yol not in sonuc:
            sonuc.append(yol)
    return sonuc


def metinler(yollar) -> list:
    """Mutlak yollari metne cevirir -- veritabanina ve CLI'a giden bicim."""
    return [str(y) for y in (yollar or ())]
