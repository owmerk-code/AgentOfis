# -*- coding: utf-8 -*-
"""YEREL MEDYA ARACLARI (07.10.2026; patron: "gerekli araclari kuracagiz",
kurulum onayi ayni gun). Yerelde kosar: KREDI, PARA, KOTA HARCAMAZ.

  * gorsel_buyut -- Real-ESRGAN ncnn (ekran karti, Vulkan), gercekci model
    `realesrgan-x4plus` (`ev/araclar/realesrgan`).
  * altyazi      -- faster-whisper large-v3-turbo (islemci, int8).
  * arka_plan    -- rembg: `birefnet-general-lite` (ince kenar, varsayilan)
    ya da `isnet-general-use` (hizli).
Whisper ve rembg ofisin evindeki AYRI Python ortaminda (`ev/araclar/medya-py`,
cagri `medya_yardimci.py` uzerinden): sistem Python'una kurulsaydi numpy/numba
yukselirdi (olculdu; patronun baska programlari ortak ortami kullaniyor).

OLCULENLER (07.10, GTX 1050 Ti / i7-7700K):
  * Real-ESRGAN varsayilan parca boyunda (0 = oto) ve 256'da cikti TAMAMEN
    SIYAH: `vkQueueSubmit failed -4`, ama cikis kodu 0 ve dosya yazildi.
    Parca 128 sabit ve cikti siyah mi OLCULUR -- sessiz bozuk cikti teslim
    edilmez (sistem saglikli gorunurken yanlis calisma sinifi).
  * x4plus 720x1280 kare ~54 sn. VIDEO icin yerel buyutme YOK: hizli model
    (`realesr-animevideov3`, ~2,2 sn/kare) teni MUMLASTIRIYOR (ayni karede
    gozle karsilastirildi), gercekci model 10 sn'lik klipte ~3,5 saat.
    Video icin Flow'un "1080p Yükseltilmiş"i (kredi kapisi) ya da kurgunun
    olceklemesi.
  * Whisper: 8 sn klip ~15 sn. Patronun Flow klibinde Turkce replik dogru,
    marka adi yanlis yazildi ("semubeyleyi") -> replik verilirse YAZIM
    replikten, ZAMAN Whisper'dan; uyum dusukse "ses repligi yanlis
    soyluyor olabilir" (Flow sesinin denetimi de olur).
  * rembg 720x1280: isnet ~2,6 sn, birefnet-lite ~18 sn.
"""

from __future__ import annotations

import difflib
import json
import re
import subprocess
import time
from pathlib import Path

from .yollar import OFIS_EVI

ARACLAR = OFIS_EVI / "araclar"
MEDYA_PY = ARACLAR / "medya-py" / "Scripts" / "python.exe"
ESRGAN = ARACLAR / "realesrgan" / "realesrgan-ncnn-vulkan.exe"
MODELLER = ARACLAR / "modeller"
YARDIMCI = Path(__file__).resolve().parent / "medya_yardimci.py"
#: OLCULDU: 0 (oto) ve 256 siyah cikti verdi; 128 dogru.
PARCA = 128
GORSEL_UZANTI = {".png", ".jpg", ".jpeg", ".webp"}
#: Satir basina en cok kelime (Reels altyazisi; ekran yazisi kurali 6-7).
SATIR_KELIME = 6
#: Bu oranin altinda duyulan replikle beklenen ayrisir: uyari.
UYUM_ESIGI = 0.6
ARKA_PLAN_MODELLERI = ("birefnet-general-lite", "isnet-general-use", "birefnet-general", "u2net")


class MedyaHatasi(ValueError):
    pass


def _pencere_yok() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def hazir_mi() -> dict:
    """Hangi arac kurulu -- ajanin ve liderin gordugu durum (olculur, varsayilmaz)."""
    return {"gorsel_buyut": ESRGAN.is_file() and (ESRGAN.parent / "models" / "realesrgan-x4plus.bin").is_file(),
            "altyazi": MEDYA_PY.is_file() and (MODELLER / "whisper").is_dir(),
            "arka_plan": MEDYA_PY.is_file()}


def _yardimci(argv: list, zaman_asimi: float) -> dict:
    if not MEDYA_PY.is_file():
        raise MedyaHatasi(f"Medya ortami kurulu degil ({MEDYA_PY}).")
    try:
        p = subprocess.run([str(MEDYA_PY), str(YARDIMCI), *argv], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=zaman_asimi,
                           creationflags=_pencere_yok())
    except subprocess.TimeoutExpired:
        raise MedyaHatasi(f"Medya araci {int(zaman_asimi)} sn'de bitmedi.")
    satir = (p.stdout or "").strip().splitlines()
    try:
        d = json.loads(satir[-1]) if satir else {}
    except ValueError:
        d = {}
    if not d.get("tamam"):
        raise MedyaHatasi(d.get("hata") or (p.stderr or "").strip()[-400:] or "medya araci cevap vermedi")
    return d


# ------------------------------------------------------------------ gorsel
def _esrgan_komut() -> list:
    """Real-ESRGAN cagrisi (sinama sahte bir komutla degistirir)."""
    return [str(ESRGAN)]


def _siyah_mi(yol: Path) -> bool:
    from PIL import Image, ImageStat
    with Image.open(yol) as im:
        orta = ImageStat.Stat(im.convert("RGB")).mean
    return max(orta) < 2.0


def gorsel_buyut(girdi, cikti, *, olcek: int = 2, en: int = 0) -> dict:
    """Gorseli yapay zekayla buyutur (x4 uretir, `olcek`e ya da `en` genislige
    indirir). Cikti siyahsa HATA (olculmus sessiz bozulma)."""
    from PIL import Image
    girdi, cikti = Path(girdi), Path(cikti)
    if girdi.suffix.lower() not in GORSEL_UZANTI:
        raise MedyaHatasi("Yalniz gorsel buyutulur (png/jpg/webp). Video: Flow'un 1080p "
                          "Yükseltilmiş secenegi ya da kurgunun olceklemesi.")
    if not hazir_mi()["gorsel_buyut"]:
        raise MedyaHatasi("Real-ESRGAN kurulu degil.")
    if olcek not in (2, 3, 4):
        raise MedyaHatasi("olcek 2, 3 ya da 4 olmali.")
    gecici = cikti.with_name(cikti.stem + ".x4-gecici.png")
    t = time.time()
    p = subprocess.run(_esrgan_komut() + ["-i", str(girdi), "-o", str(gecici), "-n", "realesrgan-x4plus",
                                          "-t", str(PARCA), "-m", str(ESRGAN.parent / "models")],
                       capture_output=True, text=True, timeout=900, creationflags=_pencere_yok())
    try:
        if not gecici.is_file():
            raise MedyaHatasi("Real-ESRGAN cikti yazmadi: " + (p.stderr or "")[-300:])
        if _siyah_mi(gecici):
            raise MedyaHatasi("Real-ESRGAN cikti SIYAH (ekran karti hatasi; "
                              + ("vkQueueSubmit" if "vkQueue" in (p.stderr or "") else "sebep bilinmiyor")
                              + "). Teslim edilmedi.")
        with Image.open(girdi) as k:
            kaynak = k.size
        with Image.open(gecici) as im:
            im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
            hedef_en = int(en) if en else kaynak[0] * olcek
            hedef = (hedef_en, round(im.height * hedef_en / im.width))
            if hedef != im.size:
                im = im.resize(hedef, Image.LANCZOS)
            cikti.parent.mkdir(parents=True, exist_ok=True)
            if cikti.suffix.lower() in (".jpg", ".jpeg"):
                im.convert("RGB").save(cikti, quality=95)
            else:
                im.save(cikti)
            boyut = im.size
    finally:
        gecici.unlink(missing_ok=True)
    return {"cikti": str(cikti), "kaynak_boyut": list(kaynak), "boyut": list(boyut),
            "sure_sn": round(time.time() - t, 1)}


# ----------------------------------------------------------------- altyazi
def _sade(k: str) -> str:
    k = (k or "").replace("İ", "i").replace("I", "ı").lower()
    return re.sub(r"[^\w]", "", k)


def _sozcukler(metin: str) -> list:
    return [s for s in re.split(r"\s+", (metin or "").strip()) if s]


def hizala(kelimeler: list, replik: str, sure: float = 0.0) -> dict:
    """Beklenen REPLIGIN kelimelerine Whisper'in zamanlarini verir.

    Yazim replikten gelir (marka adi dogru), zaman duyulandan. Eslesmeyen
    replik kelimesi komsularinin arasina yerlestirilir. Donus: kelime
    zamanlari + `uyum` (replik kelimelerinin duyulanla eslesen orani)."""
    rep = []
    for s in _sozcukler(replik):
        if not _sade(s) and rep:
            rep[-1] += " " + s                  # tek basina tire/isaret: onceki kelimeye (satir sonu)
        elif _sade(s):
            rep.append(s)
    if not rep:
        return {"kelimeler": [], "uyum": None}
    duyulan = [_sade(w.get("k", "")) for w in kelimeler]
    beklenen = [_sade(w) for w in rep]
    zaman = [None] * len(rep)
    eslesen = 0
    sm = difflib.SequenceMatcher(a=beklenen, b=duyulan, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                w = kelimeler[j1 + k]
                zaman[i1 + k] = (float(w["bas"]), float(w["son"]))
            eslesen += i2 - i1
        elif tag == "replace":
            # Duyulan araligin zamanini beklenen kelimelere paylastir. Bitisik
            # yazim ("Semu Belle" / "Semubelle") ayni harflerse ESLESMIS sayilir.
            bas, son = float(kelimeler[j1]["bas"]), float(kelimeler[j2 - 1]["son"])
            adim = max(0.0, son - bas) / (i2 - i1)
            for k in range(i2 - i1):
                zaman[i1 + k] = (round(bas + adim * k, 2), round(bas + adim * (k + 1), 2))
            if "".join(beklenen[i1:i2]) == "".join(duyulan[j1:j2]):
                eslesen += i2 - i1
    # Hic duyulmayanlari araya dagit (onceki son .. sonraki bas).
    son_zaman = max([z[1] for z in zaman if z] + [float(sure or 0)] + [0.0])
    i = 0
    while i < len(rep):
        if zaman[i] is not None:
            i += 1
            continue
        j = i
        while j < len(rep) and zaman[j] is None:
            j += 1
        bas = zaman[i - 1][1] if i > 0 else (zaman[j][0] if j < len(rep) else 0.0)
        bitis = zaman[j][0] if j < len(rep) else max(son_zaman, bas + 0.4 * (j - i))
        adim = max(0.0, bitis - bas) / (j - i)
        for k in range(i, j):
            zaman[k] = (round(bas + adim * (k - i), 2), round(bas + adim * (k - i + 1), 2))
        i = j
    return {"kelimeler": [{"k": rep[i], "bas": zaman[i][0], "son": zaman[i][1]} for i in range(len(rep))],
            "uyum": round(eslesen / len(rep), 3)}


def satirla(kelimeler: list, azami: int = SATIR_KELIME) -> list:
    """Kelimeleri altyazi satirlarina boler: cumle sonu (. ! ? …) ya da tire
    ya da `azami` kelimede. Satir {bas, son, metin} (video_kurgula bicimi)."""
    satirlar, eldeki = [], []
    for w in kelimeler:
        eldeki.append(w)
        bitti = re.search(r"[.!?…:]$|[—–]$", w["k"]) or len(eldeki) >= azami
        if bitti:
            satirlar.append(eldeki)
            eldeki = []
    if eldeki:
        satirlar.append(eldeki)
    out = []
    for s in satirlar:
        metin = re.sub(r"\s*[—–]$", "", " ".join(w["k"] for w in s)).strip()
        if metin:
            out.append({"bas": round(float(s[0]["bas"]), 2), "son": round(float(s[-1]["son"]), 2),
                        "metin": metin})
    # Ust uste binme olmasin, cok kisa satir okunur kalsin (en az 0,8 sn).
    for i, s in enumerate(out):
        sonraki = out[i + 1]["bas"] if i + 1 < len(out) else None
        s["son"] = max(s["son"], s["bas"] + 0.8)
        if sonraki is not None:
            s["son"] = min(s["son"], sonraki)
    return out


def srt_metni(satirlar: list) -> str:
    def _z(t):
        ms = int(round(float(t) * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    return "\n".join(f"{i}\n{_z(s['bas'])} --> {_z(s['son'])}\n{s['metin']}\n"
                     for i, s in enumerate(satirlar, 1))


def altyazi(girdi, *, replik: str = "", srt=None, ham: dict = None) -> dict:
    """Videonun/sesin Turkce altyazisi. `replik` verilirse yazim replikten,
    zaman duyulandan; duyulan replikten cok ayrisirsa UYARI. `ham` sinama
    icin (Whisper'in cevabi)."""
    if ham is None:
        if not hazir_mi()["altyazi"]:
            raise MedyaHatasi("Altyazi araci (Whisper) kurulu degil.")
        from . import kurgu
        ham = _yardimci(["altyazi", str(girdi), "--ffmpeg", kurgu.arac("ffmpeg"),
                         "--modeller", str(MODELLER)], 600)
    duyulan = " ".join(s.get("metin", "") for s in ham.get("satirlar") or []).strip()
    uyari, uyum = "", None
    if replik.strip():
        h = hizala(ham.get("kelimeler") or [], replik, ham.get("sure") or 0.0)
        kelimeler, uyum = h["kelimeler"], h["uyum"]
        if uyum is not None and uyum < UYUM_ESIGI:
            uyari = (f"SES REPLIGI YANLIS SOYLUYOR OLABILIR (uyum %{round(uyum * 100)}): "
                     f"beklenen \"{replik.strip()}\", duyulan \"{duyulan}\". Klibi dinle; "
                     "gerekiyorsa yeniden uret.")
    else:
        kelimeler = ham.get("kelimeler") or []
    if not kelimeler:
        uyari = uyari or "Seste konusma bulunamadi."
    satirlar = satirla(kelimeler)
    if srt:
        Path(srt).parent.mkdir(parents=True, exist_ok=True)
        Path(srt).write_text(srt_metni(satirlar), encoding="utf-8")
    return {"satirlar": satirlar, "duyulan": duyulan, "uyum": uyum, "uyari": uyari,
            "srt": str(srt) if srt else ""}


# --------------------------------------------------------------- arka plan
def arka_plan(girdi, cikti, *, model: str = "birefnet-general-lite") -> dict:
    """Arka plani siler (saydam PNG). On plan orani olculur: ~0 ya da ~1 ise
    ayirma TUTMAMISTIR -- uyari."""
    girdi, cikti = Path(girdi), Path(cikti)
    if girdi.suffix.lower() not in GORSEL_UZANTI:
        raise MedyaHatasi("Yalniz gorselin arka plani silinir (png/jpg/webp).")
    if model not in ARKA_PLAN_MODELLERI:
        raise MedyaHatasi(f"model {', '.join(ARKA_PLAN_MODELLERI)} olmali.")
    if cikti.suffix.lower() != ".png":
        cikti = cikti.with_suffix(".png")           # saydamlik yalniz PNG'de
    cikti.parent.mkdir(parents=True, exist_ok=True)
    t = time.time()
    d = _yardimci(["arka_plan", str(girdi), str(cikti), "--modeller", str(MODELLER),
                   "--model", model], 600)
    oran = float(d.get("on_plan_orani") or 0)
    uyari = ""
    if oran < 0.01:
        uyari = "Ayirma TUTMADI: on plan neredeyse bos."
    elif oran > 0.99:
        uyari = "Ayirma TUTMADI: arka plan silinmedi."
    return {"cikti": str(cikti), "boyut": d.get("boyut"), "on_plan_orani": oran, "uyari": uyari,
            "model": model, "sure_sn": round(time.time() - t, 1)}
