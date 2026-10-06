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
sina("3 dk siniri", red({"sahneler": [dict(v, sure=60)] * 4}, "en fazla 180"))
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
r2 = K.kurgula(dict(plan, bicim="1:1", muzik=None, son_kart=None), d, "reels deneme")
o2 = r2["olcum"]
sina("1:1 = 1080x1080, ayni adla ikinci cizim USTUNE YAZMAZ",
     (o2.get("genislik"), o2.get("yukseklik")) == (1080, 1080) and r2["video"] != r["video"], str(o2))

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

print("\n5. motor ayarlari")
from ofis.motor.codex import CodexMotoru as CodexMotor  # noqa: E402
satir = CodexMotor._mcp_ayarlari(json.dumps({"mcpServers": {"ofis": {"command": "python", "args": ["x"]}}}))
sina("codex: ofis araclarinin zaman asimi uzun (video cizimi kesilmesin)",
     any("tool_timeout_sec=900" in x for x in satir), str(satir))
K.yola_ekle()
sina("ffmpeg ajan turlarinin PATH'inde", str(K.ffmpeg_klasoru()).lower() in os.environ["PATH"].lower())

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
