# -*- coding: utf-8 -*-
"""CANLI GOSTERI BULGULARI (06.10.2026). Jeton yakmaz.

Patronun ofisinin kopyasinda canli gosteri uc hatayi yakaladi; sinamalar
gormemisti:
  1. Lider kadro onerdi, patron "Kur" dedi -- is BASLAMADI (asil istek
     sirada "bitti" diye kapanmisti). Artik oneriyi doguran patron mesaji
     AYNEN lidere doner ("Kur ve isi baslat"); "Yalniz kur" baslatmaz;
     sablondan kurulan takim baslatilmaz.
  2. Takim kokundeki `.ofis/ekler/` dosyasi sohbete "gizli" diye
     gonderilmedi (denetim projenin ekler klasorune bakiyordu).
  3. Liderin medya blogu "video uretimi MUMKUN DEGIL, IS ACMA" diyordu;
     lider Flow ile yapilabilecek videoyu reddetti. Flow artik uretici.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, ekler as E, kuyruk as Q  # noqa: E402

GECEN = KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


d = Path(tempfile.mkdtemp(prefix="ofis-gosteri-bulgu-"))
kok = d / "proje"
kok.mkdir()
db = Veritabani(d / "o.sqlite3")
ofis = Ofis.proje_ac(db, "Bulgu", amac="a", basari_olcutu="b", kok_klasor=str(kok))
KA = ofis.kanat_ac("GENEL", "GN")
ofis.takim_klasoru_ayarla(KA, str(d / "takim"))
ofis.kadro.ise_al("arda", "lider", kanat_id=KA, lider_mi=True, motor="sahte",
                  klasor=ofis.kok_klasoru(KA))

print("1. kadro sonrasi is SURER")
MESAJ = "Belle icin 9:16 urun klibi uret ve bana gonder."
o1 = ofis.ekip._sakla("urun klibi", {"gerekce": "video rolu yok",
                                     "uyeler": [{"ad": "deniz", "rol": "video", "gerekce": "Flow"}]},
                      "arda", KA, patron_mesaji=MESAJ)
o2 = ofis.ekip._sakla("ikinci", {"gerekce": "metin rolu yok",
                                 "uyeler": [{"ad": "mert", "rol": "metin", "gerekce": "yazi"}]},
                      "arda", KA, patron_mesaji="baska istek")
o3 = ofis.ekip._sakla("Sablon: icerik", {"gerekce": "sablon",
                                         "uyeler": [{"ad": "ece", "rol": "tasarim", "gerekce": "g"}]},
                      "sablon:icerik", KA)
sina("kurulmamis oneri devam ettirilmez", ofis.ekip.devam_mesaji(o1["no"]) is None)
from fastapi.testclient import TestClient  # noqa: E402
from ofis import panel as _panel  # noqa: E402
_basladi = []
_panel._kuyrugu_baslat = lambda *a, **k: _basladi.append(a) or True   # sinamada motor kosmaz
ist = TestClient(_panel.olustur(db.yol))
r = ist.post(f"/api/ekip/{o1['no']}/kur", json={"baslat": True})
bek = Q.bekleyenler(ofis)
sina("'Kur ve isi baslat': kadro kuruldu", r.status_code == 200 and ofis.kadro.ajan("deniz")["ad"] == "deniz",
     r.text[:200])
sina("  patron mesaji AYNEN lidere sirada", r.json().get("baslatildi") is True
     and any(k["metin"] == MESAJ and k["lider_ad"] == "arda" and k["kaynak"] == "ekip" for k in bek),
     str([(k["metin"][:30], k["kaynak"]) for k in bek]))
sina("  sira BASLATILDI", len(_basladi) == 1)
# SOHBETTE IKINCI KEZ "sen" YAZILMAZ (07.10.2026, patron: "Kur'dan sonra ayni
# mesaji neden bir daha sohbete atiyor?"). Sira isi sohbetten GERCEKTEN gecer
# (triyaj sahte: cevap); lidere giden metin AYNEN, gorunen ofis notu.
from ofis import takim as _takim  # noqa: E402
_ek = next(k for k in bek if k["kaynak"] == "ekip")
_soh = ofis.sohbet
_soh._triyaj = lambda *a, **kw: {"karar": "cevap", "cevap": "Ise basliyorum.", "gerekce": "s"}
list(_soh.konus(_ek["metin"], lider_ad="arda", kaynak="ekip"))
with db.baglanti() as _c:
    _m = dict(_c.execute("SELECT govde, gonderen, kaynak FROM mesaj ORDER BY rowid DESC LIMIT 1").fetchone())
sina("  lidere giden mesaj AYNEN (patronun sozu degismez), kaynak 'ekip'",
     _m["govde"] == MESAJ and _m["gonderen"] == "insan" and _m["kaynak"] == "ekip", str(_m))
_og = [x for x in _takim.akis(ofis) if x["tur"] in ("sohbet", "cevap")]
sina("  sohbette 'sen' balonu DEGIL ofis notu",
     _og and _og[-2]["kimden"] == "ofis" and _og[-2]["metin"].startswith("Kadro kuruldu, iş başlıyor"),
     str([(x["kimden"], x["metin"][:40]) for x in _og]))
sina("  liderin cevabi yine patrona", _og and _og[-1]["kimden"] == "arda" and _og[-1]["kime"] == "insan")
_ap = ist.get("/api/sohbet").json()["mesajlar"]
sina("  eski sohbet gorunumu de ayni", _ap and _ap[-1]["govde"].startswith("Kadro kuruldu"), str(_ap[-1:])[:200])
import inspect as _insp  # noqa: E402
sina("  panelin sira iscisi kaynagi sohbete tasiyor",
     'kaynak=("ekip" if k.get("kaynak") == "ekip" else "")' in _insp.getsource(_panel._kuyrugu_kostur))
r = ist.post(f"/api/ekip/{o2['no']}/kur", json={"baslat": False})
sina("'Yalniz kur': is baslatilmaz", r.status_code == 200 and r.json().get("baslatildi") is False
     and not any(k["metin"] == "baska istek" for k in Q.bekleyenler(ofis)))
r = ist.post(f"/api/ekip/{o3['no']}/kur", json={})
sina("sablondan kurulan takim istek olmadigi icin baslatilmaz", r.status_code == 200
     and r.json().get("baslatildi") is False)

print("\n1b. kadro onerisinde motor/model KATALOGDAN")
from ofis import roller  # noqa: E402
from ofis.motor import musait_motorlar  # noqa: E402
metin = ofis.ekip.oneri_metni("video isi", KA)
sina("onerinin ornek JSON'unda motor YOK (lider kopyaliyordu)", '"motor": "claude"' not in metin)
sina("lidere meslek katalogu gosteriliyor", "- video:" in metin and "MOTOR VE MODEL YAZMA" in metin, metin[-900:])
_km = roller.meslek_motoru("video", db, ofis.proje_id, musait_motorlar())
o4 = ofis.ekip._sakla("v", {"gerekce": "g", "uyeler": [{"ad": "nil", "rol": "video", "gerekce": "g"}]},
                      "arda", KA)
sina("motor/model yazilmazsa KATALOG kullanilir, uyari yok",
     (o4["uyeler"][0]["motor"], o4["uyeler"][0]["model"]) == (_km[0], _km[1])
     and "KATALOG DISI" not in (o4["uyeler"][0].get("uyari") or ""), str(o4["uyeler"][0]))
o5 = ofis.ekip._sakla("v", {"gerekce": "g", "uyeler": [{"ad": "nur", "rol": "video", "gerekce": "g",
                                                         "motor": _km[0], "model": "baska-model"}]},
                      "arda", KA)
sina("katalog disi model kartta GORUNUR", "KATALOG DISI" in (o5["uyeler"][0].get("uyari") or ""),
     str(o5["uyeler"][0].get("uyari")))

print("\n2. takim kokundeki ek sohbete GIDER")
def _paylas(y):
    try:
        return E.paylas(ofis, y, ajan_ad="deniz")
    except E.EkHatasi as exc:        # coken sinama kalandan kotudur: KALDI yazilir
        return f"HATA: {exc}"


e = E.kaydet(ofis, "klip.mp4", b"x" * 100, ajan_ad="deniz", kanat_id=KA)
yol = _paylas(e["yol"])
sina("takimin .ofis/ekler dosyasi paylasildi (gizli sayilmadi)", yol == e["yol"], f"{yol} / {e['yol']}")
sina("  dosya takimin kokunde", (Path(ofis.kok_klasoru(KA)) / e["yol"]).is_file())
(Path(ofis.kok_klasoru(KA)) / "is").mkdir()
(Path(ofis.kok_klasoru(KA)) / "is" / "kapak.jpg").write_bytes(b"y" * 50)
yol2 = _paylas("is/kapak.jpg")
sina("yazma alanindaki dosya TAKIMIN eklerine kopyalanir",
     (Path(ofis.kok_klasoru(KA)) / yol2).is_file(), yol2)
(Path(ofis.kok_klasoru(KA)) / ".env").write_text("GIZLI=1", encoding="utf-8")
try:
    E.paylas(ofis, ".env", ajan_ad="deniz")
    sina("baska gizli dosya yine REDDEDILIR", False)
except E.EkHatasi:
    sina("baska gizli dosya yine REDDEDILIR", True)

print("\n2b. teslim dosyasi liderin SON RAPORUNDA da durur")
g = ofis.tahta.gorev_ac("klip", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=KA)
g = ofis.tahta.sahiplen(g["no"], "deniz", g["revizyon"])
db.olay_yaz(ofis.proje_id, "ajan_sohbet",
            "Klip hazir.\n[ek] .ofis/ekler/a-klip.mp4\n[ek] .ofis/ekler/a-klip-kareler.jpg\n"
            "[ek] .ofis/ekler/a-kapak.png", ajan_ad="deniz", gorev_id=g["id"])
for _ad in ("a-klip.mp4", "a-klip-kareler.jpg", "a-kapak.png"):
    (Path(ofis.kok_klasoru(KA)) / ".ofis" / "ekler" / _ad).write_bytes(b"z" * 20)
te = E.teslim_ekleri(ofis, [g["id"]])
sina("teslim: video ve kapak var, kare ozeti YOK",
     te == [".ofis/ekler/a-klip.mp4", ".ofis/ekler/a-kapak.png"], str(te))
ofis.tahta.kanit_ekle(g["no"], "dosya", "klip", ".ofis/ekler/a-klip.mp4", "deniz")
g = ofis.tahta.gorev(g["no"])
ofis.tahta.kapat(g["no"], g["revizyon"], kapatan="arda")
db.olay_yaz(ofis.proje_id, "rapor_taslak", "Klibin hazir; 9:16, 8 sn.", ajan_ad="arda", gorev_id=g["id"])
rapor = ofis.sohbet._taslaktan_rapor({"gorevler": [{"no": g["no"]}]}, "klip yap")
sina("liderin raporu videoyu kendisi TASIYOR (ajan once gondermis olsa da)",
     "[ek] .ofis/ekler/a-klip.mp4" in rapor and "[ek] .ofis/ekler/a-kapak.png" in rapor
     and "kareler" not in rapor and "gonderilemedi" not in rapor.lower(), rapor[-300:])
css = (Path(__file__).resolve().parent.parent / "web" / "panel.css").read_text(encoding="utf-8")
sina("raporda video BUYUK oynatici", ".sohbet-balon.tur-cevap .sohbet-ek-oynat" in css)

print("\n3. liderin medya blogu Flow'u uretici sayar")
from ofis import gorsel as G  # noqa: E402
from ofis import kabin  # noqa: E402
blok = G.lider_blogu()
prof = Path(kabin.profil_yolu())
sina("profil BOSKEN Flow 'kullanilabilir' denmez", "flow" in blok and "BOS" in blok, blok[-600:])
(prof / "Default").mkdir(parents=True, exist_ok=True)
blok = G.lider_blogu()
sina("girisli profilde Flow KULLANILABILIR", "flow        KULLANILABILIR" in blok)
sina("  'otomatik uretim MUMKUN DEGIL' DENMEZ", "MUMKUN DEGIL" not in blok)
sina("  Flow'un para kilidine TAKILMADIGI soyleniyor", "TAKILMAZ" in blok)
sina("  kurgu araci satiri var", "video_kurgula" in blok)

print("\n9. ajanin kendi modeli ile son turun modeli ayri (07.10 patron: 'fable mi opus mu?')")
_js = (Path(__file__).resolve().parent.parent / "web" / "panel.js").read_text(encoding="utf-8")
# 08.10 (patron: "hem sonnet hem opus yaziyor terminalde?"): ajan CALISIRKEN
# ikinci rozet YOK; bostayken farkliysa "onceki tur:".
sina("farkli turda ikinci rozet 'onceki tur:'; ajan calisirken gosterilmez",
     "\"önceki tur: \"" in _js and "const farkli = !calisiyor &&" in _js
     and "function modelAyni(" in _js and "\"son tur: \" + olculen" not in _js)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
