# -*- coding: utf-8 -*-
"""VIDEO KURGU + OLCUM (06.10.2026, Asama 5). GERCEK ffmpeg ve GERCEK Remotion
cizimi; jeton ve kredi yakmaz (klipler ffmpeg ile uretilir).

Sinanan: plan kapisi (gecersiz bicim, bos sahne, klasor disi / olmayan /
yanlis turde dosya, gecisten kisa sahne, 3 dk siniri); cizim (9:16 ve 1:1,
boyut, sure = sahneler - gecisler, H.264 + yuv420p, ses), kapak ve kare
ozeti; olcum (yanlis oran SORUN, sessiz video ve siyah ekran UYARI); ajan
araclari (`video_kurgula` kaniti otomatik yazar, plan metin JSON olabilir,
hata kanit yazmaz; `video_denetle` klasor disini reddeder); codex arac zaman
asimi; ffmpeg ajan PATH'inde.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

KOD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOD))
# Araclar ofisin GERCEK evinde (yalniz OKUNUR); sinamanin evi gecici.
os.environ.setdefault("OFIS_FFMPEG_KLASORU", str(KOD / "ev" / "araclar" / "ffmpeg" / "bin"))
os.environ.setdefault("OFIS_RIFE", str(KOD / "ev" / "araclar" / "rife" / "rife-ncnn-vulkan.exe"))

from ofis import Ofis, Veritabani, kurgu as K, mcp_sunucu as M  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


durum = K.hazir_mi()
sina("kurgu araclari kurulu (ffmpeg + remotion)", all(durum.values()), str(durum))
if not all(durum.values()):
    print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
    sys.exit(1)

d = Path(tempfile.mkdtemp(prefix="ofis-kurgu-"))
F = K.arac("ffmpeg")


def uret(ad, *arg):
    subprocess.run([F, "-v", "error", "-y", *arg, str(d / ad)], check=True, capture_output=True)


uret("dikey.mp4", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=3",
     "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
     "-c:a", "aac", "-shortest")
uret("yatay.mp4", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=2",
     "-c:v", "libx264", "-pix_fmt", "yuv420p")
uret("siyah.mp4", "-f", "lavfi", "-i", "color=c=black:size=1080x1920:rate=30:duration=3",
     "-c:v", "libx264", "-pix_fmt", "yuv420p")
uret("urun.png", "-f", "lavfi", "-i", "testsrc=size=1200x1200:rate=1", "-frames:v", "1")
uret("muzik.mp3", "-f", "lavfi", "-i", "sine=frequency=220:duration=10", "-c:a", "libmp3lame")
(d / "not.txt").write_text("x", encoding="utf-8")
disari = Path(tempfile.mkdtemp(prefix="ofis-kurgu-disari-"))
(disari / "d.mp4").write_bytes((d / "yatay.mp4").read_bytes())

print("\n1. plan kapisi")


def red(plan, parca):
    try:
        K.plan_dogrula(plan, d)
        return False
    except K.KurguHatasi as exc:
        return parca in str(exc)


v = {"tur": "video", "dosya": "dikey.mp4", "sure": 2}
sina("gecersiz bicim", red({"bicim": "3:2", "sahneler": [v]}, "bicim"))
sina("bos sahne listesi", red({"sahneler": []}, "En az bir sahne"))
sina("klasor DISI dosya", red({"sahneler": [dict(v, dosya=str(disari / "d.mp4"))]}, "DISINDA"))
sina("olmayan dosya", red({"sahneler": [dict(v, dosya="yok.mp4")]}, "bulunamadi"))
sina("yanlis tur (video yerine metin)", red({"sahneler": [dict(v, dosya="not.txt")]}, "desteklenmiyor"))
sina("gecisten kisa sahne", red({"sahneler": [dict(v, sure=0.3)], "gecis_sure": 0.5}, "gecis suresinden"))
sina("3 dk siniri", red({"sahneler": [{"tur": "renk", "sure": 60}] * 4}, "en fazla 180"))
# 08.10.2026: duzenleme alanlari (hiz, yerlesim, odak, filtre, sesler, logo, gecis).
sina("klip YETMIYORSA (sure x hiz > klip) once soylenir -- sonu siyah kalmaz",
     red({"sahneler": [dict(v, sure=2.5, hiz=2)]}, "klip"))
sina("  agir cekim klibe sigiyor: kabul",
     K.plan_dogrula({"sahneler": [dict(v, sure=4, hiz=0.5)]}, d)["sahneler"][0]["hiz"] == 0.5)
sina("hiz yalniz video sahnesinde", red({"sahneler": [{"tur": "renk", "sure": 1, "hiz": 2}]}, "yalniz video"))
sina("gecersiz yerlesim / filtre / odak reddedilir",
     red({"sahneler": [dict(v, yerlesim="genis")]}, "yerlesim")
     and red({"sahneler": [dict(v, filtre="neon")]}, "filtre")
     and red({"sahneler": [dict(v, odak="kenar")]}, "odak"))
sina("yeni gecisler kabul (kayma, silme, yukari)",
     all(K.plan_dogrula({"gecis": x, "sahneler": [v]}, d)["gecis"] == x for x in ("kayma", "silme", "yukari")))
_sp = K.plan_dogrula({"sahneler": [dict(v, sure=3)], "sesler": [{"dosya": "muzik.mp3", "bas": 1}]}, d)
sina("ses izinin suresi OLCULUR ve videonun sonunda kirpilir",
     abs(_sp["sesler"][0]["sure"] - 2.0) < 0.05, str(_sp["sesler"]))
sina("video bittikten sonra baslayan ses izi reddedilir",
     red({"sahneler": [v], "sesler": [{"dosya": "muzik.mp3", "bas": 5}]}, "sonra"))
sina("logo boyutu sinirli, konum listeden",
     red({"sahneler": [v], "logo": {"dosya": "urun.png", "boyut": 0.9}}, "logo boyut")
     and red({"sahneler": [v], "logo": {"dosya": "urun.png", "konum": "kose"}}, "logo konumu"))
sina("gecerli plan gecer, dosya mutlak yola doner",
     Path(K.plan_dogrula({"sahneler": [v]}, d)["sahneler"][0]["dosya"]).is_absolute())

print("\n2. cizim (gercek Remotion)")
plan = {"bicim": "9:16", "gecis": "solma", "gecis_sure": 0.5,
        "sahneler": [dict(v, sure=3, yazi="Yeni sezon", yazi_konum="ust"),
                     {"tur": "gorsel", "dosya": "urun.png", "sure": 2, "yazi": "Işıltılı", "hareket": "yakinlas"}],
        "muzik": "muzik.mp3", "altyazi": [{"bas": 0, "son": 2, "metin": "İğde ve amber"}],
        "son_kart": {"metin": "Marka", "alt_metin": "site.com", "sure": 2}}
r = K.kurgula(plan, d, "reels deneme")
o = r["olcum"]
sina("9:16 = 1080x1920", (o.get("genislik"), o.get("yukseklik")) == (1080, 1920), str(o))
sina("sure = 3 + 2 + 2 - 2 gecis (6 sn)", abs(o["sure"] - 6.0) < 0.15, str(o["sure"]))
sina("H.264 + yuv420p (Instagram'in en guvenlisi)", o.get("kodlayici") == "h264" and o.get("renk_bicimi") == "yuv420p")
sina("ses var (muzik)", o["ses"])
sina("sorun yok", r["sorunlar"] == [], str(r["sorunlar"]))
sina("cikti .ofis/ekler altinda", Path(r["video"]).parent == (d / ".ofis" / "ekler").resolve())
sina("kapak ve kare ozeti cikti", Path(r["kapak"]).is_file() and Path(r["kareler"]).is_file())


def _kutu_parlakliklari(yol):
    from PIL import Image, ImageStat
    with Image.open(yol) as im:
        en = im.width // 6
        return [max(ImageStat.Stat(im.crop((i * en, 0, (i + 1) * en, im.height)).convert("RGB")).mean)
                for i in range(6)]


# 07.10 canli: gercek Remotion ciktisinda kare ozetinin son kutusu SIYAHTI
# (video siyahla bitmiyordu -- olculdu). Son kart (#111) koyu: esik 5.
# DURUST NOT: eski secim filtresi hatayi YALNIZ o gercek final videosunda
# uretti (elle olculdu: kutular 189/184/175/161/90/0); bu ve asagidaki yapay
# sicrama sinamasi eski kodla da geciyor -- genel bekci, eski hatanin kaniti degil.
_kp = _kutu_parlakliklari(r["kareler"]) if r.get("kareler") else []
sina("gercek Remotion ciktisinda 6 kutu da dolu (bos/siyah kutu yok)",
     len(_kp) == 6 and min(_kp) > 5, str([round(x, 1) for x in _kp]))
r2 = K.kurgula(dict(plan, bicim="1:1", muzik=None, son_kart=None), d, "reels deneme")
o2 = r2["olcum"]
sina("1:1 = 1080x1080, ayni adla ikinci cizim USTUNE YAZMAZ",
     (o2.get("genislik"), o2.get("yukseklik")) == (1080, 1080) and r2["video"] != r["video"], str(o2))

print("\n2b. DUZENLEME cizimi: yatay klip dikeyde BULANIK dolgu, agir cekim, filtre,")
print("    kayma gecisi, logo, seslendirme izi ve altinda muzigin KISILMASI (gercek Remotion)")
uret("ses.mp3", "-f", "lavfi", "-i", "sine=frequency=880:duration=1.5", "-c:a", "libmp3lame")
_dp = {"bicim": "9:16", "gecis": "kayma", "gecis_sure": 0.3,
       "sahneler": [{"tur": "video", "dosya": "yatay.mp4", "sure": 3, "hiz": 0.5,
                     "yerlesim": "bulanik", "filtre": "sinematik"},
                    {"tur": "video", "dosya": "yatay.mp4", "sure": 2, "yerlesim": "sigdir"}],
       "muzik": "muzik.mp3", "muzik_ses": 1, "muzik_alcalt": 0.2,
       "sesler": [{"dosya": "ses.mp3", "bas": 0.5, "ses": 1}],
       "logo": {"dosya": "urun.png", "konum": "sag_ust", "boyut": 0.15}}
_dr = K.kurgula(_dp, d, "duzenleme")
_do = _dr["olcum"]
sina("duzenleme cizimi 1080x1920, sure 3 + 2 - 0.3", (_do.get("genislik"), _do.get("yukseklik")) == (1080, 1920)
     and abs(_do["sure"] - 4.7) < 0.15, str(_do))


def _ust_parlaklik(video, t):
    from PIL import Image, ImageStat
    k = d / f"kare-{t}.png"
    subprocess.run([F, "-v", "error", "-y", "-ss", str(t), "-i", str(video), "-frames:v", "1", str(k)],
                   capture_output=True)
    with Image.open(k) as im:
        return max(ImageStat.Stat(im.crop((0, int(im.height * 0.25), im.width,
                                           int(im.height * 0.3))).convert("RGB")).mean)


_bul, _sig = _ust_parlaklik(_dr["video"], 1.5), _ust_parlaklik(_dr["video"], 4.2)
sina("BULANIK dolgu: yatay klibin ustu bos/siyah DEGIL; sigdir'da siyah",
     _bul > 25 and _sig < 8, f"bulanik={_bul:.1f} sigdir={_sig:.1f}")


def _bas_db(video, bas, sure):
    r = subprocess.run([F, "-hide_banner", "-nostats", "-ss", str(bas), "-t", str(sure), "-i", str(video),
                        "-af", "lowpass=f=300,volumedetect", "-vn", "-f", "null", "-"], capture_output=True)
    import re as _re
    m = _re.search(r"mean_volume: (-?[0-9.]+) dB", r.stderr.decode("utf-8", "replace"))
    return float(m.group(1)) if m else 0.0


_ic, _dis = _bas_db(_dr["video"], 0.9, 0.7), _bas_db(_dr["video"], 2.6, 0.7)
sina("seslendirme calarken muzik KISILIYOR (olculdu, ~-14 dB beklenir)",
     _dis - _ic > 8, f"ses izi icinde {_ic} dB, disinda {_dis} dB")

print("\n3. olcum")
dy = K.denetle(d / "yatay.mp4", "9:16")
sina("yanlis oran SORUN", any("oran" in s for s in dy["sorunlar"]), str(dy["sorunlar"]))
sina("sessiz video UYARI", any("SES yok" in u for u in dy["uyarilar"]), str(dy["uyarilar"]))
ds = K.denetle(d / "siyah.mp4", "9:16")
sina("uzun siyah ekran UYARI", any("SIYAH" in u for u in ds["uyarilar"]), str(ds["uyarilar"]))
sina("ozet metni olcumu tasiyor", "1080x1920" in K.ozet_metni(r) and "ses: var" in K.ozet_metni(r))

print("\n4. ajan araclari")
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Kurgu", amac="a", basari_olcutu="b", kok_klasor=str(d))
KA = ofis.kanat_ac("ICERIK", "IC")
ofis.kadro.ise_al("lale", "lider", kanat_id=KA, lider_mi=True, motor="sahte", klasor=str(d))
ofis.kadro.ise_al("ece", "video", kanat_id=KA, motor="sahte", klasor=str(d))
g = ofis.tahta.gorev_ac("reels", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KA)
g = ofis.tahta.sahiplen(g["no"], "ece", g["revizyon"])


class _Oturum:
    def __init__(self):
        self.ofis, self.ajan_ad, self.gorev_no, self.proje_id = ofis, "ece", g["no"], ofis.proje_id

    def ajan(self):
        return ofis.kadro.ajan("ece")

    def gorev(self):
        return ofis.tahta.gorev(g["no"])


kucuk = {"bicim": "4:5", "sahneler": [{"tur": "renk", "renk": "#334455", "sure": 1.5, "yazi": "Deneme"}]}
cevap = M.arac_video_kurgula(_Oturum(), {"plan": json.dumps(kucuk), "ad": "gonderi"})
kan = ofis.tahta.kanitlar(g["no"])
sina("video_kurgula: VIDEO HAZIR (plan metin JSON da olur)", cevap.startswith("VIDEO HAZIR") and "1080x1350" in cevap,
     cevap[:300])
sina("  kanit OTOMATIK yazildi (ofisin olcumu)", len(kan) == 1 and kan[0]["tur"] == "dosya" and "1080x1350" in kan[0]["icerik"])
sina("  yol isin klasorune goreli", ".ofis/ekler/gonderi.mp4" in cevap)
cevap = M.arac_video_kurgula(_Oturum(), {"plan": {"bicim": "9:16", "sahneler": []}})
sina("hatali plan HATA doner, kanit YAZILMAZ", cevap.startswith("HATA") and len(ofis.tahta.kanitlar(g["no"])) == 1)
cevap = M.arac_video_denetle(_Oturum(), {"dosya": str(disari / "d.mp4")})
sina("video_denetle klasor disini reddeder", cevap.startswith("HATA") and "disinda" in cevap)
cevap = M.arac_video_denetle(_Oturum(), {"dosya": "dikey.mp4", "bicim": "9:16"})
sina("video_denetle olcer ve kanit yazar", "OLCUM" in cevap and len(ofis.tahta.kanitlar(g["no"])) == 2, cevap[:200])

# 08.10.2026: hazir video duzenleme (medya_isle -> ofis/video_islem.py), gercek ffmpeg.
uret("konusma.mp4", "-f", "lavfi", "-i", "color=c=red:s=640x360:d=3:r=30",
     "-f", "lavfi", "-i", "color=c=white:s=640x360:d=3:r=30",
     "-f", "lavfi", "-i", "sine=f=440:d=2", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=2",
     "-f", "lavfi", "-i", "sine=f=660:d=2",
     "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v];[2:a]aresample=44100[a2];"
     "[4:a]aresample=44100[a4];[a2][3:a][a4]concat=n=3:v=0:a=1[a]",
     "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac")
cevap = M.arac_medya_isle(_Oturum(), {"islem": "sahneler", "dosya": "konusma.mp4"})
sina("medya_isle sahneler: 2 sahne, kesim 3. sn'de, kare panosu yazildi",
     "2 sahne" in cevap and "3.00-6.00" in cevap
     and (d / ".ofis" / "ekler" / "konusma-sahneler.jpg").is_file(), cevap[:300])
cevap = M.arac_medya_isle(_Oturum(), {"islem": "kes", "dosya": "konusma.mp4", "bas": 1, "son": 4})
sina("medya_isle kes: 3 sn, kanit yazildi", "-> 3.0 sn" in cevap and "Kanit OTOMATIK" in cevap, cevap[:200])
cevap = M.arac_medya_isle(_Oturum(), {"islem": "ses_ayir", "dosya": "konusma.mp4"})
sina("medya_isle ses_ayir: ses dosyasi", "SES AYRILDI" in cevap
     and (d / ".ofis" / "ekler" / "konusma-ses.m4a").is_file(), cevap[:200])
cevap = M.arac_medya_isle(_Oturum(), {"islem": "sessizlik_kes", "dosya": "konusma.mp4"})
sina("medya_isle sessizlik_kes: 6 sn -> ~4.3 sn (2 sn sessizlik, kenar payi kalir)",
     "SESSIZLIK ATILDI" in cevap and "6.0 ->" in cevap, cevap[:200])
cevap = M.arac_medya_isle(_Oturum(), {"islem": "sessizlik_kes", "dosya": "yatay.mp4"})
sina("sesi OLMAYAN videoda sessizlik kesme acik HATA", cevap.startswith("HATA") and "SES yok" in cevap,
     cevap[:160])
# RIFE ara kare (gercek, kucuk klip): kare/sn iki kat, sure ayni, siyah degil.
from ofis import video_islem as _VI  # noqa: E402
try:
    _VI._rife()
    _rife_var = True
except K.KurguHatasi:
    _rife_var = False
if _rife_var:
    uret("akici.mp4", "-f", "lavfi", "-i", "testsrc2=size=320x568:rate=24:duration=1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p")
    cevap = M.arac_medya_isle(_Oturum(), {"islem": "kare_ara", "dosya": "akici.mp4", "carpan": 2})
    sina("medya_isle kare_ara (RIFE): 24 -> 48 kare/sn, sure ayni",
         "24 -> 48 kare/sn" in cevap and "sure 1.0 -> 1.0" in cevap, cevap[:220])
else:
    print("  [ATLANDI] RIFE kurulu degil (ev/araclar/rife)")
# VOKAL AYIRMA (gercek MDX-Net, gercek medya ortami; salt okunur kullanim):
# calisiyor mu, vokal + muzik = karisim mi (fark yontemi), sure ayni mi.
from ofis import medya_arac as _MA  # noqa: E402
_MA.MEDYA_PY = KOD / "ev" / "araclar" / "medya-py" / "Scripts" / "python.exe"
_MA.MODELLER = KOD / "ev" / "araclar" / "modeller"
if _MA.hazir_mi()["vokal_ayir"]:
    cevap = M.arac_medya_isle(_Oturum(), {"islem": "vokal_ayir", "dosya": "konusma.mp4"})
    sina("medya_isle vokal_ayir (gercek model): iki iz, sure ayni",
         "VOKAL / MUZIK AYRILDI" in cevap and "6.0 sn ses" in cevap, cevap[:300])
    import numpy as _np  # noqa: E402

    def _pcm(yol):
        ham = subprocess.run([F, "-v", "error", "-i", str(yol), "-f", "f32le", "-ac", "2", "-ar", "44100", "-"],
                             capture_output=True).stdout
        return _np.frombuffer(ham, _np.float32)

    _ek = d / ".ofis" / "ekler"
    _v, _m, _k = _pcm(_ek / "konusma-vokal.wav"), _pcm(_ek / "konusma-muzik.wav"), _pcm(d / "konusma.mp4")
    _n = min(len(_v), len(_m), len(_k))
    _hata = float(_np.abs(_v[:_n] + _m[:_n] - _k[:_n]).max()) if _n else 9.0
    sina("  vokal + muzik = karisim (kayip yok; 16 bit yuvarlama payi)", _n > 0 and _hata < 0.002, str(_hata))
else:
    print("  [ATLANDI] vokal ayirma modeli kurulu degil")
# YAZI URUNE BINIYOR MU (08.10 canli: yazilar alta tasindi, kutuya/siseye bindi; lider
# kacirdi). Gercek rembg: altta parlak "urun", ustu bos.
if _MA.hazir_mi()["arka_plan"]:
    from PIL import Image as _Im, ImageDraw as _Id  # noqa: E402
    _urun = _Im.new("RGB", (1080, 1920), (8, 8, 10))
    _Id.Draw(_urun).rounded_rectangle((330, 1050, 750, 1800), 40, fill=(222, 180, 90))
    _urun.save(d / "urun-sahne.png")
    uret("urun-sahne.mp4", "-loop", "1", "-i", str(d / "urun-sahne.png"), "-t", "3", "-r", "30",
         "-c:v", "libx264", "-pix_fmt", "yuv420p")
    _pl = {"bicim": "9:16", "gecis": "kesme", "sahneler": [
        {"tur": "video", "dosya": "urun-sahne.mp4", "sure": 3, "yazi": "Cesur olanlar fark edilir.",
         "yazi_konum": "alt"}]}
    _u1 = K.yazi_carpismasi(d / "urun-sahne.mp4", _pl)
    _pl["sahneler"][0]["yazi_konum"] = "ust"
    _u2 = K.yazi_carpismasi(d / "urun-sahne.mp4", _pl)
    sina("yazi urunun ustunde: UYARI; bos alanda: uyari YOK",
         len(_u1) == 1 and "URUNUN USTUNE" in _u1[0] and _u2 == [], f"{_u1} / {_u2}")
else:
    print("  [ATLANDI] arka plan araci (rembg) kurulu degil")
cevap = M.arac_medya_isle(_Oturum(), {"islem": "kare_ara", "dosya": "konusma.mp4", "carpan": 3})
sina("kare_ara carpani 2|4 disi HATA", cevap.startswith("HATA") and "carpan" in cevap, cevap[:120])
cevap = M.arac_medya_isle(_Oturum(), {"islem": "kes", "dosya": "konusma.mp4", "bas": 4, "son": 2})
sina("ters aralik HATA, dosya uretilmez", cevap.startswith("HATA"), cevap[:160])

print("\n5. motor ayarlari")
from ofis.motor.codex import CodexMotoru as CodexMotor  # noqa: E402
satir = CodexMotor._mcp_ayarlari(json.dumps({"mcpServers": {"ofis": {"command": "python", "args": ["x"]}}}))
sina("codex: ofis araclarinin zaman asimi uzun (video cizimi kesilmesin)",
     any("tool_timeout_sec=900" in x for x in satir), str(satir))
K.yola_ekle()
sina("ffmpeg ajan turlarinin PATH'inde", str(K.ffmpeg_klasoru()).lower() in os.environ["PATH"].lower())

print("\nKARE OZETI zaman damgasi sicramasinda bos (siyah) kutu birakmaz (07.10 canli)")
# Remotion ciktisinda 2,5 sn'de zaman damgasi sicradi; eski secim filtresi kaydi
# ve son kutu SIYAH cizildi -- video siyahla bitiyormus gibi gorundu (olcum: yok).
_sv = d / "sicrama.mp4"
subprocess.run([K.arac("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i",
                "testsrc2=size=360x640:rate=24:duration=15", "-vf",
                "setpts='if(gte(N\\,60)\\,PTS+0.4/TB\\,PTS)'", "-pix_fmt", "yuv420p", str(_sv)],
               capture_output=True, timeout=120)
_od = K.denetle(_sv)
from PIL import Image, ImageStat  # noqa: E402
_kut = []
if _od.get("kareler"):
    with Image.open(_od["kareler"]) as _im:
        _en = _im.width // 6
        _kut = [max(ImageStat.Stat(_im.crop((i * _en, 0, (i + 1) * _en, _im.height)).convert("RGB")).mean)
                for i in range(6)]
sina("6 kutunun HEPSI dolu (siyah kutu yok)", len(_kut) == 6 and min(_kut) > 20, str([round(x) for x in _kut]))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
