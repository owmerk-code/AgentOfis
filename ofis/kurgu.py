# -*- coding: utf-8 -*-
"""VIDEO KURGU + OLCUM (06.10.2026, Asama 5; patron karari).

Yapay zeka videosu Google Flow'da (gomulu tarayici, patronun hesabi) uretilir;
ajan kliplerini/gorsellerini bu modulle PAYLASMAYA HAZIR videoya cevirir:
Instagram bicimi (9:16 Reels/hikaye, 4:5 ve 1:1 gonderi, 16:9), yazi,
altyazi, gecis, muzik, kapanis karti.

Neden ajan Remotion kodu YAZMIYOR: tek, sinanmis bir sablon (`medya/remotion`)
bir PLAN (JSON) ile doldurulur. Ajanin isi plani yazmak; cizim, bicim ve
olcum ofisin. Her iste ayni guvenilir yol (kural yapi, rica degil).

OLCUM ofisin, ajanin sozu degil (`denetle`): ffprobe ile boyut, sure, kare
hizi, kodlayici, renk bicimi, ses var mi; siyah kare ve sessizlik taramasi;
kare ozeti (kontak sayfasi) ve kapak. Lider incelemede bunu kanit olarak
gorur; patron kareleri gorur.

Araclar ofisin evinde (`ev/araclar/ffmpeg`, sisteme kurulmaz). Remotion
kodun yaninda (`medya/remotion`, bagimliliklari `npm install` ile).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from .yollar import OFIS_EVI, OFIS_KODU

REMOTION_KOK = OFIS_KODU / "medya" / "remotion"
BICIMLER = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080), "16:9": (1920, 1080)}
VIDEO_UZANTI = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
GORSEL_UZANTI = {".png", ".jpg", ".jpeg", ".webp"}
SES_UZANTI = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
AZAMI_SAHNE_SN = 60
AZAMI_TOPLAM_SN = 180          # Instagram Reels siniri (3 dk)


class KurguHatasi(ValueError):
    pass


# --------------------------------------------------------------- araclar
def ffmpeg_klasoru() -> Path:
    return Path(os.environ.get("OFIS_FFMPEG_KLASORU") or (OFIS_EVI / "araclar" / "ffmpeg" / "bin"))


def arac(ad: str) -> str:
    """ffmpeg/ffprobe yolu: once ofisin evi, sonra sistem PATH'i."""
    p = ffmpeg_klasoru() / f"{ad}.exe"
    if p.is_file():
        return str(p)
    q = shutil.which(ad)
    if q:
        return q
    raise KurguHatasi(f"{ad} bulunamadi (ev/araclar/ffmpeg/bin ya da PATH).")


def yola_ekle() -> None:
    """Ofisin ffmpeg'i ajan turlarina da gorunsun (alt surecler PATH'i miras alir)."""
    k = ffmpeg_klasoru()
    if k.is_dir() and str(k).lower() not in os.environ.get("PATH", "").lower():
        os.environ["PATH"] = str(k) + os.pathsep + os.environ.get("PATH", "")


def hazir_mi() -> dict:
    """Kurgu araclari kurulu mu (saglik / ayarlar icin)."""
    durum = {"ffmpeg": False, "remotion": False}
    try:
        arac("ffmpeg")
        arac("ffprobe")
        durum["ffmpeg"] = True
    except KurguHatasi:
        pass
    durum["remotion"] = (REMOTION_KOK / "node_modules" / "@remotion" / "cli" / "remotion-cli.js").is_file()
    return durum


def _calistir(argv, *, zaman_asimi: float, cwd=None) -> subprocess.CompletedProcess:
    from .surec import PENCERE_YOK
    from .motor.tip import SurecKafesi
    s = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=PENCERE_YOK)
    kafes = SurecKafesi(s)      # Remotion basliksiz Chrome acar: zaman asiminda hepsi biter
    try:
        cikti, hata = s.communicate(timeout=zaman_asimi)
    except subprocess.TimeoutExpired:
        kafes.kapat()
        s.kill()
        cikti, hata = s.communicate()
        raise KurguHatasi(f"zaman asimi ({int(zaman_asimi)} sn)")
    finally:
        try:
            kafes.kapat()
        except Exception:                    # noqa: BLE001
            pass
    return subprocess.CompletedProcess(argv, s.returncode, cikti, hata)


# --------------------------------------------------------------- plan
def _icinde(yol: Path, kok: Path) -> bool:
    try:
        yol.resolve().relative_to(kok.resolve())
        return True
    except ValueError:
        return False


def _dosya(kok: Path, ham: str, uzantilar: set, ne: str) -> Path:
    p = Path(str(ham or "").strip())
    if not str(p):
        raise KurguHatasi(f"{ne}: dosya yolu bos.")
    if not p.is_absolute():
        p = kok / p
    if not _icinde(p, kok):
        raise KurguHatasi(f"{ne}: '{ham}' isin klasorunun DISINDA; once klasore indir/kopyala.")
    if not p.is_file():
        raise KurguHatasi(f"{ne}: '{ham}' bulunamadi.")
    if p.suffix.lower() not in uzantilar:
        raise KurguHatasi(f"{ne}: '{p.name}' turu desteklenmiyor ({', '.join(sorted(uzantilar))}).")
    return p


def plan_dogrula(plan: dict, kok) -> dict:
    """Plani denetler; dosyalari MUTLAK yola cevirir. Hata mesaji ne yapilacagini soyler."""
    if not isinstance(plan, dict):
        raise KurguHatasi("Plan bir sozluk (JSON nesnesi) olmali.")
    kok = Path(kok)
    bicim = plan.get("bicim") or "9:16"
    if bicim not in BICIMLER:
        raise KurguHatasi(f"bicim {bicim!r} gecersiz; 9:16 (reels/hikaye), 4:5 ya da 1:1 (gonderi), 16:9.")
    sahneler = plan.get("sahneler")
    if not isinstance(sahneler, list) or not sahneler:
        raise KurguHatasi("En az bir sahne gerekli (sahneler: [...]).")
    if len(sahneler) > 40:
        raise KurguHatasi("En fazla 40 sahne.")
    gecis = plan.get("gecis") or "solma"
    if gecis not in ("solma", "kesme"):
        raise KurguHatasi("gecis 'solma' ya da 'kesme' olmali.")
    gs = float(plan.get("gecis_sure") if plan.get("gecis_sure") is not None else 0.4)
    if gecis == "solma" and not 0.1 <= gs <= 1.5:
        raise KurguHatasi("gecis_sure 0.1-1.5 sn olmali.")
    temiz = []
    toplam = 0.0
    for i, s in enumerate(sahneler, 1):
        if not isinstance(s, dict):
            raise KurguHatasi(f"sahne {i} bir nesne olmali.")
        tur = s.get("tur")
        if tur not in ("video", "gorsel", "renk"):
            raise KurguHatasi(f"sahne {i}: tur 'video', 'gorsel' ya da 'renk' olmali.")
        try:
            sure = float(s.get("sure"))
        except (TypeError, ValueError):
            raise KurguHatasi(f"sahne {i}: sure (saniye) gerekli.")
        if not 0.3 <= sure <= AZAMI_SAHNE_SN:
            raise KurguHatasi(f"sahne {i}: sure 0.3-{AZAMI_SAHNE_SN} sn olmali.")
        if gecis == "solma" and sure <= gs:
            raise KurguHatasi(f"sahne {i}: sure ({sure}) gecis suresinden ({gs}) uzun olmali.")
        y = dict(s, sure=sure)
        if tur == "video":
            y["dosya"] = str(_dosya(kok, s.get("dosya"), VIDEO_UZANTI, f"sahne {i}"))
        elif tur == "gorsel":
            y["dosya"] = str(_dosya(kok, s.get("dosya"), GORSEL_UZANTI, f"sahne {i}"))
        if y.get("yazi") is not None:
            y["yazi"] = str(y["yazi"])[:200]
        temiz.append(y)
        toplam += sure
    out = dict(plan, bicim=bicim, gecis=gecis, gecis_sure=gs, sahneler=temiz,
               fps=int(plan.get("fps") or 30))
    if out["fps"] not in (24, 25, 30, 60):
        raise KurguHatasi("fps 24, 25, 30 ya da 60 olmali.")
    if plan.get("muzik"):
        out["muzik"] = str(_dosya(kok, plan["muzik"], SES_UZANTI, "muzik"))
    sk = plan.get("son_kart")
    if sk:
        if not isinstance(sk, dict) or not str(sk.get("metin") or "").strip():
            raise KurguHatasi("son_kart {metin, alt_metin?, sure} olmali.")
        out["son_kart"] = dict(sk, sure=float(sk.get("sure") or 2.0))
        toplam += out["son_kart"]["sure"]
    if toplam > AZAMI_TOPLAM_SN:
        raise KurguHatasi(f"Toplam sure {toplam:.0f} sn; en fazla {AZAMI_TOPLAM_SN} sn.")
    for a in plan.get("altyazi") or []:
        if not isinstance(a, dict) or float(a.get("son", 0)) <= float(a.get("bas", 0)):
            raise KurguHatasi("altyazi satiri {bas, son, metin} ve son > bas olmali.")
    return out


# --------------------------------------------------------------- olcum
def olc(video) -> dict:
    """ffprobe ile videonun OLCULEN ozellikleri."""
    r = subprocess.run([arac("ffprobe"), "-v", "error", "-print_format", "json",
                        "-show_streams", "-show_format", str(video)],
                       capture_output=True, timeout=60, creationflags=_pencere_yok())
    if r.returncode != 0:
        raise KurguHatasi(f"video okunamadi: {r.stderr.decode('utf-8', 'replace')[:200]}")
    v = json.loads(r.stdout.decode("utf-8", "replace") or "{}")
    vs = [s for s in v.get("streams", []) if s.get("codec_type") == "video"]
    ss = [s for s in v.get("streams", []) if s.get("codec_type") == "audio"]
    o = {"boyut_bayt": int(v.get("format", {}).get("size") or 0),
         "sure": round(float(v.get("format", {}).get("duration") or 0), 2),
         "ses": bool(ss), "ses_kodlayici": ss[0].get("codec_name") if ss else None}
    if vs:
        s = vs[0]
        try:
            pay, payda = (s.get("r_frame_rate") or "0/1").split("/")
            fps = round(float(pay) / float(payda), 2) if float(payda) else 0
        except (ValueError, ZeroDivisionError):
            fps = 0
        o.update({"genislik": s.get("width"), "yukseklik": s.get("height"), "fps": fps,
                  "kodlayici": s.get("codec_name"), "renk_bicimi": s.get("pix_fmt")})
    return o


def _pencere_yok():
    from .surec import PENCERE_YOK
    return PENCERE_YOK


def _tara(video, filtre: str, anahtar: str) -> list:
    r = subprocess.run([arac("ffmpeg"), "-hide_banner", "-nostats", "-i", str(video),
                        *filtre.split(" "), "-f", "null", "-"],
                       capture_output=True, timeout=300, creationflags=_pencere_yok())
    metin = r.stderr.decode("utf-8", "replace")
    return [s for s in metin.splitlines() if anahtar in s]


def denetle(video, bicim: str = "") -> dict:
    """Paylasmaya hazir mi? Doner: {olcum, sorunlar, uyarilar, kareler, kapak}.

    SORUN = paylasilamaz (yanlis boyut/oran, video yok, bozuk); UYARI =
    patronun bilmesi gereken (sessiz video, uzun siyah ekran, buyuk dosya).
    """
    video = Path(video)
    o = olc(video)
    sorun, uyari = [], []
    if not o.get("genislik"):
        sorun.append("videoda goruntu akisi YOK")
    elif bicim in BICIMLER:
        g, y = BICIMLER[bicim]
        if abs(o["genislik"] / o["yukseklik"] - g / y) > 0.01:
            sorun.append(f"oran {o['genislik']}x{o['yukseklik']}, istenen {bicim}")
        elif o["genislik"] < g * 0.66:
            uyari.append(f"cozunurluk dusuk ({o['genislik']}x{o['yukseklik']}; onerilen {g}x{y})")
    if o.get("sure", 0) <= 0:
        sorun.append("sure 0")
    elif o["sure"] > AZAMI_TOPLAM_SN:
        sorun.append(f"sure {o['sure']} sn > {AZAMI_TOPLAM_SN} sn (Instagram Reels siniri)")
    if o.get("kodlayici") and o["kodlayici"] != "h264":
        uyari.append(f"kodlayici {o['kodlayici']} (Instagram icin en guvenlisi H.264)")
    if o.get("renk_bicimi") and o["renk_bicimi"] not in ("yuv420p",):
        uyari.append(f"renk bicimi {o['renk_bicimi']} (en guvenlisi yuv420p)")
    if not o["ses"]:
        uyari.append("videoda SES yok (Instagram'da muzik eklenebilir)")
    if o.get("fps") and not 23 <= o["fps"] <= 61:
        uyari.append(f"kare hizi {o['fps']}")
    if o["boyut_bayt"] > 250 * 1024 * 1024:
        uyari.append(f"dosya buyuk ({o['boyut_bayt'] // (1024 * 1024)} MB)")
    try:
        siyah = _tara(video, "-vf blackdetect=d=1.0:pix_th=0.02", "black_start")
        if siyah:
            uyari.append(f"{len(siyah)} yerde 1 sn'den uzun SIYAH ekran")
        if o["ses"]:
            sessiz = _tara(video, "-af silencedetect=n=-50dB:d=" + str(max(1.0, o["sure"] * 0.9)),
                           "silence_start")
            if sessiz:
                uyari.append("ses akisi var ama neredeyse TAMAMEN sessiz")
    except (subprocess.SubprocessError, OSError) as exc:
        uyari.append(f"siyah/sessizlik taramasi yapilamadi: {exc}")
    kareler = video.with_name(video.stem + "-kareler.jpg")
    kapak = video.with_name(video.stem + "-kapak.jpg")
    try:
        sure = max(o.get("sure") or 0.1, 0.1)
        # Esit aralikla 6 kare: ilk kare + her `adim` saniyede bir (pencereli
        # secim kare hizina denk gelmeyince bos karo birakiyordu -- olculdu).
        adim = sure / 6.0
        r = subprocess.run([arac("ffmpeg"), "-v", "error", "-y", "-i", str(video), "-vf",
                            f"select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,{adim:.3f})'"
                            + ",scale=300:-2,tile=6x1", "-frames:v", "1", "-fps_mode", "vfr",
                            str(kareler)], capture_output=True, timeout=120,
                           creationflags=_pencere_yok())
        if r.returncode != 0 or not kareler.is_file():
            uyari.append("kare ozeti cikarilamadi")
            kareler = None
        r = subprocess.run([arac("ffmpeg"), "-v", "error", "-y", "-ss", f"{min(1.0, sure / 3):.2f}",
                            "-i", str(video), "-frames:v", "1", "-q:v", "2", str(kapak)],
                           capture_output=True, timeout=60, creationflags=_pencere_yok())
        if r.returncode != 0 or not kapak.is_file():
            kapak = None
    except (subprocess.SubprocessError, OSError):
        kareler = kapak = None
    return {"olcum": o, "sorunlar": sorun, "uyarilar": uyari,
            "kareler": str(kareler) if kareler else "", "kapak": str(kapak) if kapak else ""}


def ozet_metni(d: dict) -> str:
    """Kanit ve sohbet icin tek bakista olcum."""
    o = d["olcum"]
    s = (f"{o.get('genislik')}x{o.get('yukseklik')} · {o.get('sure')} sn · {o.get('fps')} fps · "
         f"{o.get('kodlayici')}/{o.get('renk_bicimi')} · ses: {'var' if o['ses'] else 'YOK'} · "
         f"{round(o['boyut_bayt'] / 1048576, 1)} MB")
    if d["sorunlar"]:
        s += "\nSORUN: " + "; ".join(d["sorunlar"])
    if d["uyarilar"]:
        s += "\nuyari: " + "; ".join(d["uyarilar"])
    return s


# --------------------------------------------------------------- cizim
def kurgula(plan: dict, kok, ad: str) -> dict:
    """Plani videoya cizer ve olcer. Cikti `kok/.ofis/ekler/<ad>.mp4`.

    Dosyalar is klasorune (`.ofis/kurgu/<kimlik>/public`) kopyalanir:
    Remotion yalniz kendi public klasorunu gorur ve kaynak dosyalara dokunmaz.
    """
    durum = hazir_mi()
    if not all(durum.values()):
        eksik = [k for k, v in durum.items() if not v]
        raise KurguHatasi(f"Kurgu araclari kurulu degil: {', '.join(eksik)}.")
    kok = Path(kok).resolve()
    p = plan_dogrula(plan, kok)
    ad = Path(str(ad or "video")).stem[:60].strip() or "video"
    ad = "".join(c if c.isalnum() or c in "-_" else "-" for c in ad)
    is_klasoru = kok / ".ofis" / "kurgu" / f"{ad}-{uuid.uuid4().hex[:8]}"
    public = is_klasoru / "public"
    public.mkdir(parents=True, exist_ok=True)
    cizilecek = json.loads(json.dumps(p))
    for i, s in enumerate(cizilecek["sahneler"]):
        if s.get("dosya"):
            kaynak = Path(s["dosya"])
            hedef = public / f"s{i}{kaynak.suffix.lower()}"
            shutil.copy2(kaynak, hedef)
            s["dosya"] = hedef.name
    if cizilecek.get("muzik"):
        kaynak = Path(cizilecek["muzik"])
        hedef = public / f"muzik{kaynak.suffix.lower()}"
        shutil.copy2(kaynak, hedef)
        cizilecek["muzik"] = hedef.name
    plan_yolu = is_klasoru / "plan.json"
    plan_yolu.write_text(json.dumps(cizilecek, ensure_ascii=False, indent=1), encoding="utf-8")
    cikti_klasoru = kok / ".ofis" / "ekler"
    cikti_klasoru.mkdir(parents=True, exist_ok=True)
    cikti = cikti_klasoru / f"{ad}.mp4"
    if cikti.exists():
        cikti = cikti_klasoru / f"{ad}-{uuid.uuid4().hex[:6]}.mp4"
    sure = sum(s["sure"] for s in p["sahneler"]) + (p.get("son_kart") or {}).get("sure", 0)
    argv = [shutil.which("node") or "node",
            str(REMOTION_KOK / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"),
            "render", "src/index.ts", "Kurgu", str(cikti), f"--props={plan_yolu}",
            f"--public-dir={public}", "--codec=h264", "--color-space=bt709", "--log=error"]
    r = _calistir(argv, cwd=str(REMOTION_KOK), zaman_asimi=max(300, sure * 40))
    if r.returncode != 0 or not cikti.is_file():
        hata = (r.stderr or b"").decode("utf-8", "replace").strip()[-600:]
        raise KurguHatasi(f"Cizim basarisiz (cikis {r.returncode}): {hata}")
    d = denetle(cikti, p["bicim"])
    d.update({"video": str(cikti), "plan": str(plan_yolu), "bicim": p["bicim"]})
    return d
