# -*- coding: utf-8 -*-
"""YEREL MEDYA ARACLARI (07.10.2026, `ofis/medya_arac.py`). Jeton, kredi
yakmaz; GERCEK modelleri kosturmaz (Whisper cevabi ve Real-ESRGAN sahte,
mantik gercek). Gercek araclarla olcum gunlukte (patronun iki Flow klibi:
uyum %100 ve %83, marka adi dogru; buyutme 73 sn; arka plan 26 sn).

Sinanan:
  * altyazi: replik varsa YAZIM replikten zaman sesten; bitisik yazim
    ("Semu Belle"/"Semubelle") eslesmis sayilir; fazladan duyulan kelime
    atlanir; duyulmayan kelime araya yerlesir; yanlis replik -> UYARI;
    satirlar noktalama ve 6 kelimede bolunur, ust uste binmez; SRT bicimi.
  * gorsel_buyut: ekran karti SIYAH cikti verirse (07.10 olculdu, cikis
    kodu 0!) TESLIM EDILMEZ; dogru ciktiyi hedef genislige indirir; video
    reddedilir.
  * arka_plan: on plan ~0 ya da ~1 ise uyari.
  * kurulu degilse SOYLER (cokmez); MCP araci klasor disini reddeder,
    kaniti otomatik yazar.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici ev; ILK ice aktarma

import sys
import tempfile
from pathlib import Path

KOD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOD))

from PIL import Image  # noqa: E402

from ofis import Ofis, Veritabani, medya_arac as M  # noqa: E402
from ofis import mcp_sunucu as S  # noqa: E402

GECEN = KALAN = 0
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def k(w, b, s):
    return {"k": w, "bas": b, "son": s}


# Patronun Flow klibinden (07.10) Whisper'in GERCEK cevabinin bicimi
HAM = {"kelimeler": [k("Bir", 0.0, 0.3), k("kez", 0.3, 0.55), k("dene", 0.55, 0.8), k("ya.", 0.8, 1.0),
                     k("Nasıl", 1.14, 1.5), k("hissettirdiğini", 1.5, 2.3), k("görürsün.", 2.3, 2.8),
                     k("Ben", 4.04, 4.4), k("bırakamıyorum.", 4.4, 5.54), k("Semubelle.", 6.32, 7.08)],
       "satirlar": [{"bas": 0, "son": 2.8, "metin": "Bir kez dene ya. Nasıl hissettirdiğini görürsün."},
                    {"bas": 4.04, "son": 5.54, "metin": "Ben bırakamıyorum."},
                    {"bas": 6.32, "son": 7.08, "metin": "Semubelle."}], "sure": 8.0}
REPLIK = "Bir kez dene — nasıl hissettirdiğini görürsün. Ben bırakamıyorum. Semu Belle."

print("1. altyazi: replige hizalama")
d = tempfile.mkdtemp(prefix="ofis-medya-")
srt = Path(d) / "a.srt"
a = M.altyazi("yok.mp4", replik=REPLIK, srt=srt, ham=HAM)
sina("uyum %100 (bitisik 'Semubelle' = 'Semu Belle', fazladan 'ya' atlandi)", a["uyum"] == 1.0, str(a["uyum"]))
sina("uyari yok", a["uyari"] == "", a["uyari"])
metinler = [s["metin"] for s in a["satirlar"]]
sina("marka adi REPLIKTEKI gibi yazildi", metinler[-1] == "Semu Belle.", str(metinler))
sina("satirlar noktalamada bolundu, tire satir sonu (kendisi yazilmaz)",
     metinler == ["Bir kez dene", "nasıl hissettirdiğini görürsün.", "Ben bırakamıyorum.", "Semu Belle."],
     str(metinler))
sina("zaman SESTEN (Ben bırakamıyorum 4,04-5,54)",
     a["satirlar"][2]["bas"] == 4.04 and a["satirlar"][2]["son"] == 5.54, str(a["satirlar"][2]))
sina("satirlar ust uste binmiyor", all(a["satirlar"][i]["son"] <= a["satirlar"][i + 1]["bas"]
                                       for i in range(len(a["satirlar"]) - 1)))
sina("SRT yazildi ve bicimi dogru", srt.is_file() and "00:00:04,040 --> 00:00:05,540\nBen bırakamıyorum."
     in srt.read_text(encoding="utf-8"), srt.read_text(encoding="utf-8")[:200] if srt.is_file() else "")
y = M.altyazi("yok.mp4", replik="Yeni sezon kampanyası başladı, hemen sipariş verin.", ham=HAM)
sina("yanlis replik: uyum dusuk ve UYARI (ses repligi yanlis soyluyor olabilir)",
     y["uyum"] is not None and y["uyum"] < M.UYUM_ESIGI and "YANLIS" in y["uyari"], str(y["uyum"]))
e = M.hizala([k("Bir", 0.0, 0.3), k("dene.", 2.0, 2.4)], "Bir kez dene.", 3.0)
sina("duyulmayan kelime komsularinin ARASINA yerlesir",
     e["kelimeler"][1]["bas"] >= 0.3 and e["kelimeler"][1]["son"] <= 2.0 and e["uyum"] < 1, str(e))
r = M.altyazi("yok.mp4", ham=HAM)
sina("replik yoksa duyulan yazilir", r["uyum"] is None and r["satirlar"] and "Semubelle." in r["satirlar"][-1]["metin"])
uzun = [k(f"k{i}", i * 0.5, i * 0.5 + 0.4) for i in range(14)]
sina("en cok 6 kelimelik satirlar", all(len(s["metin"].split()) <= 6 for s in M.satirla(uzun)))
sina("bos seste uyari", "konusma" in M.altyazi("x", ham={"kelimeler": [], "satirlar": []})["uyari"])

print("\n2. kurulu degilse SOYLER")
sina("gecici evde araclar kurulu degil (gercek eve bakilmiyor)",
     not any(M.hazir_mi().values()) and str(M.ARACLAR).startswith(str(Path(tempfile.gettempdir()))),
     f"{M.hazir_mi()} {M.ARACLAR}")
for ad, cagri in (("altyazi", lambda: M.altyazi("x.mp4")),
                  ("gorsel_buyut", lambda: M.gorsel_buyut(Path(d) / "x.png", Path(d) / "y.png")),
                  ("arka_plan", lambda: M.arka_plan(Path(d) / "x.png", Path(d) / "y.png")),
                  ("vokal_ayir", lambda: M.vokal_ayir(Path(d) / "x.mp4", Path(d) / "v.wav", Path(d) / "m.wav"))):
    try:
        cagri()
        sina(f"{ad}: kurulu degilken hata soyledi", False)
    except M.MedyaHatasi as exc:
        sina(f"{ad}: kurulu degilken hata soyledi ({str(exc)[:40]})", True)

print("\n3. gorsel_buyut: SIYAH cikti teslim edilmez")
sahte = Path(d) / "sahte_esrgan.py"
sahte.write_text(
    "import sys\nfrom PIL import Image\na=sys.argv\ni=a[a.index('-i')+1]; o=a[a.index('-o')+1]\n"
    "im=Image.open(i)\nim=im.resize((im.width*4, im.height*4))\n"
    "if 'SIYAH' in i: im=Image.new('RGB', im.size, (0,0,0)); sys.stderr.write('vkQueueSubmit failed -4')\n"
    "im.save(o)\n", encoding="utf-8")
M._esrgan_komut = lambda: [sys.executable, str(sahte)]
_hazir = M.hazir_mi
M.hazir_mi = lambda: {"gorsel_buyut": True, "altyazi": False, "arka_plan": False}
Image.new("RGB", (72, 128), (180, 120, 90)).save(Path(d) / "urun.png")
Image.new("RGB", (72, 128), (180, 120, 90)).save(Path(d) / "SIYAH.png")
try:
    M.gorsel_buyut(Path(d) / "SIYAH.png", Path(d) / "siyah_cikti.png")
    sina("siyah cikti REDDEDILDI", False)
except M.MedyaHatasi as exc:
    sina("siyah cikti REDDEDILDI (sebep soylendi)", "SIYAH" in str(exc) and "vkQueueSubmit" in str(exc), str(exc))
sina("  reddedilen cikti diske birakilmadi", not (Path(d) / "siyah_cikti.png").exists()
     and not list(Path(d).glob("*gecici*")))
b = M.gorsel_buyut(Path(d) / "urun.png", Path(d) / "urun_buyuk.jpg", en=108)
sina("dogru cikti hedef genislige indirildi (oran korundu)", b["boyut"] == [108, 192], str(b))
b2 = M.gorsel_buyut(Path(d) / "urun.png", Path(d) / "urun_x3.png", olcek=3)
sina("olcek 3", b2["boyut"] == [216, 384], str(b2))
try:
    M.gorsel_buyut(Path(d) / "klip.mp4", Path(d) / "k.mp4")
    sina("video REDDEDILDI", False)
except M.MedyaHatasi as exc:
    sina("video REDDEDILDI (Flow'un buyutmesi soylenir)", "Flow" in str(exc), str(exc))
M.hazir_mi = _hazir

print("\n4. arka_plan: ayirma tutmazsa uyari")
_y = M._yardimci
for oran, bekle in ((0.0, "bos"), (1.0, "silinmedi"), (0.7, "")):
    M._yardimci = lambda argv, z, o=oran: {"tamam": True, "boyut": [72, 128], "on_plan_orani": o}
    r = M.arka_plan(Path(d) / "urun.png", Path(d) / "urun_arkasiz.jpg")
    sina(f"on plan %{int(oran * 100)}: " + (f"uyari ({bekle})" if bekle else "uyari yok"),
         (bekle in r["uyari"]) if bekle else r["uyari"] == "", r["uyari"])
sina("saydamlik icin cikti PNG'ye cevrildi", r["cikti"].endswith(".png"))

print("\n4b. vokal_ayir: bos iz UYARIR")
_hz = M.hazir_mi
M.hazir_mi = lambda: {"vokal_ayir": True}
from ofis import kurgu as _K  # noqa: E402
_arac, _K.arac = _K.arac, (lambda ad: ad)  # sahte yardimci ffmpeg cagirmaz
for vdb, mdb, bekle in ((-60, -14, "VOKAL yok"), (-15, -60, "MUZIK yok"), (-20, -16, "")):
    M._yardimci = lambda argv, z, v=vdb, m=mdb: {"tamam": True, "sure": 3.0, "vokal_db": v,
                                                "muzik_db": m, "karisim_db": -14}
    r = M.vokal_ayir(Path(d) / "klip.mp4", Path(d) / "v.wav", Path(d) / "m.wav")
    sina(f"vokal {vdb} / muzik {mdb} dB: " + (f"uyari ({bekle})" if bekle else "uyari yok"),
         (bekle in r["uyari"]) if bekle else r["uyari"] == "", r["uyari"])
try:
    M.vokal_ayir(Path(d) / "klip.mp4", Path(d) / "v.txt", Path(d) / "m.wav")
    sina("vokal_ayir: ses disi cikti REDDEDILDI", False)
except M.MedyaHatasi:
    sina("vokal_ayir: ses disi cikti REDDEDILDI", True)
M.hazir_mi, M._yardimci, _K.arac = _hz, _y, _arac

print("\n5. MCP araci")
o = Ofis.proje_ac(Veritabani(Path(d) / "o.sqlite3"), "Medya", amac="a", basari_olcutu="b", kok_klasor=d)
o.kadro.ise_al("vera", "video", motor="sahte")
g = o.tahta.gorev_ac("Reels", neden="s", ana_hedef="s", kabul_olcutu="y", yazma_alani=["x"], sahip="vera")


class _Oturum:
    ofis = o
    gorev_no = g["no"]
    ajan_ad = "vera"

    def gorev(self):
        return o.tahta.gorev(g["no"])


ot = _Oturum()
sina("klasor disi dosya REDDEDILIR", "disinda" in S.arac_medya_isle(ot, {"islem": "altyazi", "dosya": "C:/Windows/win.ini"}))
sina("bilinmeyen islem", "olmali" in S.arac_medya_isle(ot, {"islem": "uydur", "dosya": "urun.png"}))
M._yardimci = lambda argv, z: {"tamam": True, "boyut": [72, 128], "on_plan_orani": 0.6}
cev = S.arac_medya_isle(ot, {"islem": "arka_plan", "dosya": "urun.png"})
sina("arka_plan: olcum cevapta, cikti .ofis/ekler'de", "on plan %60" in cev and ".ofis/ekler/urun-arkasiz.png" in cev, cev)
_alt = M.altyazi
M.altyazi = lambda p, replik="", srt=None: _alt(p, replik=replik, srt=srt, ham=HAM)
(Path(d) / "klip.mp4").write_bytes(b"x")
cev = S.arac_medya_isle(ot, {"islem": "altyazi", "dosya": "klip.mp4", "replik": REPLIK})
sina("altyazi: video_kurgula bicimi + uyum + srt", '"metin": "Semu Belle."' in cev and "uyum %100" in cev
     and "klip.srt" in cev, cev[:300])
with o.db.baglanti() as c:
    kn = [r[0] for r in c.execute("SELECT baslik FROM kanit")]
sina("kanit OTOMATIK yazildi (iki islem)", sum(1 for x in kn if x.startswith("medya:")) == 2, str(kn))
M._yardimci, M.altyazi = _y, _alt

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
