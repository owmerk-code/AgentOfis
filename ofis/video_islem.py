# -*- coding: utf-8 -*-
"""VIDEO DUZENLEME -- hazir bir videoyu ajanin anlayip kesmesi (08.10.2026).

Patron: *"Flow'dan cikan videoyu ya da sohbette verdigim hazir videoyu
istedigime gore edit, montaj, sahne, ses birlestirme yapabilmeli."*

`video_kurgula` (Remotion) PLANDAN video cizer; ama hazir bir videoyla
calismanin ilk adimi onu ANLAMAKTIR: nerede kesme var, hangi sahne ne
gosteriyor, nerede konusma susuyor. Ajan videoyu izleyemez -- kare
panosuna bakar. Bu modul o adimlari verir; hepsi yerel ffmpeg, KREDI
HARCAMAZ, cikti OLCULUR (yanlis gosteren gosterge olmasin diye her
sonuc ffprobe'la yeniden okunur).

* `sahneler`  -- kesme noktalari (ffmpeg sahne skoru) + her sahnenin
  ortasindan zaman damgali kare panosu.
* `kes`       -- bas-son araligini yeni dosyaya (yeniden kodlayarak: kare
  dogru, ses senkronlu; `-c copy` anahtar kareye kayar).
* `ses_ayir`  -- sesi ayri dosyaya (muzik/seslendirme yeniden kullanimi).
* `sessizlik_kes` -- konusmali videoda sessiz bosluklari atar (auto-editor
  yaklasimi, ffmpeg silencedetect ile; ek paket yok).

Birlestirme, hiz, yazi, gecis, muzik, seslendirme, logo: `video_kurgula`.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import time
from pathlib import Path

from .kurgu import KurguHatasi, _pencere_yok, arac, olc

VIDEO_UZANTI = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}
SES_UZANTI = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
#: Kare panosunda en cok kac sahne (fazlasi esit aralikla secilir).
PANO_AZAMI = 24
PANO_EN = 320
#: Paylasima hazir H.264 (Instagram/Meta kabul eder; bt709 + yuv420p).
KODLA = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
KODLA_SESSIZ = [k for k in KODLA if k not in ("-c:a", "aac", "-b:a", "192k")] + ["-an"]


def _calistir(argv: list, zaman_asimi: float = 900) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, capture_output=True, timeout=zaman_asimi,
                              creationflags=_pencere_yok())
    except subprocess.TimeoutExpired:
        raise KurguHatasi(f"zaman asimi ({int(zaman_asimi)} sn)")


def _girdi(yol, uzantilar=VIDEO_UZANTI) -> Path:
    p = Path(yol)
    if not p.is_file():
        raise KurguHatasi(f"dosya yok: {p}")
    if p.suffix.lower() not in uzantilar:
        raise KurguHatasi(f"'{p.name}' turu desteklenmiyor ({', '.join(sorted(uzantilar))}).")
    return p


def _hata(r) -> str:
    return (r.stderr or b"").decode("utf-8", "replace").strip()[-400:]


# ----------------------------------------------------------------- sahneler
def kesimleri_bul(video, esik: float = 0.3) -> list:
    """Sahne degisimlerinin zamanlari (sn). ffmpeg `scene` skoru 0-1."""
    r = _calistir([arac("ffmpeg"), "-hide_banner", "-nostats", "-i", str(video),
                   "-vf", f"select='gt(scene,{esik})',showinfo", "-an", "-f", "null", "-"])
    zamanlar = []
    for s in (r.stderr or b"").decode("utf-8", "replace").splitlines():
        m = re.search(r"pts_time:([0-9.]+)", s)
        if "Parsed_showinfo" in s and m:
            zamanlar.append(round(float(m.group(1)), 2))
    return sorted(set(zamanlar))


def sahneler(girdi, pano, *, esik: float = 0.3) -> dict:
    """Videoyu sahnelere boler, her sahneden bir kare panoya koyar."""
    from PIL import Image, ImageDraw
    girdi = _girdi(girdi)
    if not 0.05 <= float(esik) <= 0.9:
        raise KurguHatasi("esik 0.05-0.9 olmali (dusuk = daha cok kesim).")
    o = olc(girdi)
    sure = float(o.get("sure") or 0)
    if sure <= 0:
        raise KurguHatasi("videonun suresi okunamadi.")
    kesim = [t for t in kesimleri_bul(girdi, esik) if 0.2 < t < sure - 0.2]
    sinirlar = [0.0] + kesim + [sure]
    liste = [{"no": i + 1, "bas": round(a, 2), "son": round(b, 2), "sure": round(b - a, 2)}
             for i, (a, b) in enumerate(zip(sinirlar, sinirlar[1:])) if b - a > 0.05]
    secilen = liste
    if len(liste) > PANO_AZAMI:
        adim = len(liste) / PANO_AZAMI
        secilen = [liste[int(i * adim)] for i in range(PANO_AZAMI)]
    kareler = []
    with tempfile.TemporaryDirectory(prefix="ofis-sahne-") as gec:
        for s in secilen:
            t = (s["bas"] + s["son"]) / 2
            y = Path(gec) / f"k{s['no']}.jpg"
            _calistir([arac("ffmpeg"), "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(girdi),
                       "-frames:v", "1", "-vf", f"scale={PANO_EN}:-2", "-q:v", "3", str(y)], 60)
            kareler.append((s, Image.open(y).convert("RGB").copy() if y.is_file() else None))
    sutun = min(6, max(1, len(kareler)))
    boy = max((k.height for _, k in kareler if k is not None), default=PANO_EN * 9 // 16)
    satir = (len(kareler) + sutun - 1) // sutun
    sayfa = Image.new("RGB", (PANO_EN * sutun, (boy + 26) * satir), (24, 24, 24))
    ciz = ImageDraw.Draw(sayfa)
    for i, (s, k) in enumerate(kareler):
        x, y = (i % sutun) * PANO_EN, (i // sutun) * (boy + 26)
        if k is None:
            ciz.text((x + 10, y + boy // 2), "okunamadi", fill=(255, 255, 255))
        else:
            sayfa.paste(k, (x, y))
        ciz.text((x + 6, y + boy + 6), f"#{s['no']}  {s['bas']:.1f}-{s['son']:.1f} sn",
                 fill=(235, 235, 235))
    pano = Path(pano)
    pano.parent.mkdir(parents=True, exist_ok=True)
    sayfa.save(pano, quality=88)
    return {"sure": round(sure, 2), "sahneler": liste, "pano": str(pano),
            "panoda": len(kareler), "olcum": o}


# ----------------------------------------------------------------- kes
def kes(girdi, cikti, *, bas: float, son: float) -> dict:
    """[bas, son] araligi yeni dosyaya; cikti OLCULUR (sure tutuyor mu)."""
    girdi = _girdi(girdi)
    o = olc(girdi)
    sure = float(o.get("sure") or 0)
    bas, son = float(bas), float(son)
    if not (0 <= bas < son):
        raise KurguHatasi("bas >= 0 ve son > bas olmali (saniye).")
    if sure and bas >= sure:
        raise KurguHatasi(f"bas ({bas}) videonun suresinden ({sure}) buyuk.")
    son = min(son, sure) if sure else son
    cikti = Path(cikti).with_suffix(".mp4")
    cikti.parent.mkdir(parents=True, exist_ok=True)
    r = _calistir([arac("ffmpeg"), "-v", "error", "-y", "-ss", f"{bas:.3f}", "-to", f"{son:.3f}",
                   "-i", str(girdi), *(KODLA if o.get("ses") else KODLA_SESSIZ),
                   str(cikti)])
    if r.returncode != 0 or not cikti.is_file():
        raise KurguHatasi(f"kesilemedi: {_hata(r)}")
    oc = olc(cikti)
    beklenen = son - bas
    if abs(float(oc.get("sure") or 0) - beklenen) > 0.5:
        raise KurguHatasi(f"kesilen sure tutmadi: {oc.get('sure')} sn (beklenen {beklenen:.2f}).")
    return {"cikti": str(cikti), "bas": bas, "son": son, "olcum": oc}


# ----------------------------------------------------------------- ses
def ses_ayir(girdi, cikti) -> dict:
    girdi = _girdi(girdi)
    if not olc(girdi).get("ses"):
        raise KurguHatasi("videoda SES yok; ayrilacak bir sey yok.")
    cikti = Path(cikti)
    uz = cikti.suffix.lower() if cikti.suffix.lower() in (".wav", ".mp3", ".m4a") else ".m4a"
    cikti = cikti.with_suffix(uz)
    cikti.parent.mkdir(parents=True, exist_ok=True)
    kod = {".wav": ["-c:a", "pcm_s16le"], ".mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
           ".m4a": ["-c:a", "aac", "-b:a", "192k"]}[uz]
    r = _calistir([arac("ffmpeg"), "-v", "error", "-y", "-i", str(girdi), "-vn", *kod, str(cikti)])
    if r.returncode != 0 or not cikti.is_file():
        raise KurguHatasi(f"ses ayrilamadi: {_hata(r)}")
    return {"cikti": str(cikti), "olcum": olc(cikti)}


def sessizlikleri_bul(girdi, *, esik_db: float = -35, en_az: float = 0.6) -> list:
    """[(bas, son), ...] sessiz araliklar (ffmpeg silencedetect)."""
    r = _calistir([arac("ffmpeg"), "-hide_banner", "-nostats", "-i", str(girdi), "-vn",
                   "-af", f"silencedetect=noise={esik_db}dB:d={en_az}", "-f", "null", "-"])
    metin = (r.stderr or b"").decode("utf-8", "replace")
    baslar = [float(x) for x in re.findall(r"silence_start: (-?[0-9.]+)", metin)]
    sonlar = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", metin)]
    araliklar = []
    for i, b in enumerate(baslar):
        araliklar.append((max(0.0, b), sonlar[i] if i < len(sonlar) else None))
    return araliklar


def sessizlik_kes(girdi, cikti, *, esik_db: float = -35, en_az: float = 0.6,
                  pay: float = 0.15) -> dict:
    """Sessiz bosluklari atar; konusmanin basina/sonuna `pay` sn birakir."""
    girdi = _girdi(girdi)
    o = olc(girdi)
    if not o.get("ses"):
        raise KurguHatasi("videoda SES yok; sessizlik olculemez.")
    sure = float(o.get("sure") or 0)
    sessiz = sessizlikleri_bul(girdi, esik_db=esik_db, en_az=en_az)
    tut, imlec = [], 0.0
    for b, s in sessiz:
        s = sure if s is None else s
        bitis = min(sure, b + pay)
        if bitis - imlec > 0.05:
            tut.append((imlec, bitis))
        imlec = max(imlec, s - pay)
    if sure - imlec > 0.05:
        tut.append((imlec, sure))
    atilan = round(sure - sum(b - a for a, b in tut), 2)
    if not sessiz or atilan < 0.3:
        return {"cikti": None, "atilan_sn": max(0.0, atilan), "araliklar": tut,
                "not": "kayda deger sessizlik yok; video degistirilmedi."}
    if not tut:
        raise KurguHatasi("videonun tamami sessiz gorunuyor; esik_db'yi dusur (orn. -45).")
    secim = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in tut)
    cikti = Path(cikti).with_suffix(".mp4")
    cikti.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(f"[0:v]select='{secim}',setpts=N/FRAME_RATE/TB[v];"
                f"[0:a]aselect='{secim}',asetpts=N/SR/TB[a]")
        betik = f.name
    try:
        r = _calistir([arac("ffmpeg"), "-v", "error", "-y", "-i", str(girdi),
                       # ffmpeg 8+: `-filter_complex_script` KALDIRILDI (olculdu,
                       # 9.0.2 "Unrecognized option"); dosyadan okuma `-/secenek`.
                       "-/filter_complex", betik, "-map", "[v]", "-map", "[a]",
                       *KODLA, str(cikti)])
    finally:
        Path(betik).unlink(missing_ok=True)
    if r.returncode != 0 or not cikti.is_file():
        raise KurguHatasi(f"sessizlik kesilemedi: {_hata(r)}")
    oc = olc(cikti)
    return {"cikti": str(cikti), "atilan_sn": atilan, "parca": len(tut),
            "araliklar": [(round(a, 2), round(b, 2)) for a, b in tut], "olcum": oc,
            "sure_once": round(sure, 2), "sure_sonra": oc.get("sure")}


# ----------------------------------------------------------------- ara kare
#: RIFE (github.com/nihui/rife-ncnn-vulkan, v4.6): iki kare arasina YAPAY ZEKAYLA
#: kare uretir. Flow/Veo klibi 24 kare/sn; 0,5x agir cekimde saniyede 12 farkli
#: kare kalir ve goruntu TAKILIR. Ara kareyle 48/96 kare/sn -> akici agir cekim.
def _rife() -> Path:
    import os
    from .yollar import OFIS_EVI
    p = Path(os.environ.get("OFIS_RIFE") or (OFIS_EVI / "araclar" / "rife" / "rife-ncnn-vulkan.exe"))
    if not p.is_file() or not (p.parent / "rife-v4.6" / "flownet.bin").is_file():
        raise KurguHatasi(f"RIFE kurulu degil ({p}).")
    return p


def kare_ara(girdi, cikti, *, carpan: int = 2) -> dict:
    """Kare sayisini `carpan` kat artirir (sure AYNI, kare/sn x carpan)."""
    from PIL import Image, ImageStat
    girdi = _girdi(girdi)
    if int(carpan) not in (2, 4):
        raise KurguHatasi("carpan 2 ya da 4 olmali.")
    carpan = int(carpan)
    o = olc(girdi)
    fps = float(o.get("fps") or 0)
    if not fps:
        raise KurguHatasi("videonun kare hizi okunamadi.")
    if fps * carpan > 240:
        raise KurguHatasi(f"{fps:g} x {carpan} kare/sn cok yuksek (en cok 240).")
    cikti = Path(cikti).with_suffix(".mp4")
    cikti.parent.mkdir(parents=True, exist_ok=True)
    bas = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="ofis-rife-") as gec:
        gir, cik = Path(gec) / "gir", Path(gec) / "cik"
        gir.mkdir()
        cik.mkdir()
        r = _calistir([arac("ffmpeg"), "-v", "error", "-i", str(girdi), "-fps_mode", "passthrough",
                       str(gir / "%08d.png")])
        n = len(list(gir.glob("*.png")))
        if r.returncode != 0 or n < 2:
            raise KurguHatasi(f"kareler cikarilamadi: {_hata(r)}")
        rife = _rife()
        r = _calistir([str(rife), "-i", str(gir), "-o", str(cik), "-n", str(n * carpan),
                       "-m", str(rife.parent / "rife-v4.6")], max(600, n * 3))
        cikan = sorted(cik.glob("*.png"))
        if r.returncode != 0 or len(cikan) < n * carpan - carpan:
            raise KurguHatasi(f"RIFE basarisiz (cikis {r.returncode}, {len(cikan)}/{n * carpan} kare): "
                              f"{_hata(r)}")
        # SIYAH CIKTI TUZAGI (Real-ESRGAN'da olculdu: cikis 0, kareler siyah):
        # kaynakla ayni yerden bir kare parlaklikla karsilastirilir.
        with Image.open(sorted(gir.glob("*.png"))[n // 2]) as a, Image.open(cikan[len(cikan) // 2]) as b:
            pa = sum(ImageStat.Stat(a.convert("L")).mean)
            pb = sum(ImageStat.Stat(b.convert("L")).mean)
        if pa > 8 and pb < pa * 0.3:
            raise KurguHatasi(f"RIFE ciktisi KARANLIK/SIYAH (kaynak {pa:.0f}, cikti {pb:.0f}); kullanilmadi.")
        yeni_fps = fps * carpan
        sesli = bool(o.get("ses"))
        r = _calistir([arac("ffmpeg"), "-v", "error", "-y", "-framerate", f"{yeni_fps:g}",
                       "-i", str(cik / "%08d.png"), *(["-i", str(girdi), "-map", "0:v", "-map", "1:a",
                                                       "-shortest"] if sesli else []),
                       *(KODLA if sesli else KODLA_SESSIZ), str(cikti)])
    if r.returncode != 0 or not cikti.is_file():
        raise KurguHatasi(f"video yeniden kurulamadi: {_hata(r)}")
    oc = olc(cikti)
    return {"cikti": str(cikti), "fps_once": fps, "fps_sonra": oc.get("fps"),
            "sure_once": o.get("sure"), "sure_sonra": oc.get("sure"),
            "sure_sn": round(time.monotonic() - bas, 1), "olcum": oc}
