# -*- coding: utf-8 -*-
"""EKLER duman testi -- sohbete dosya/gorsel (29.09.2026), jeton yakmadan.

Sinananlar:
  1. Ad temizleme (Turkce harf, yol parcasi, bos ad).
  2. Kaydet: kokun `ekler/` klasoru, benzersiz ad, boyut siniri, bos dosya
     reddi, `.part` artigi kalmaz, olay yazilir.
  3. Okuma: klasor disi / yol parcali / olmayan ad REDDEDILIR.
  4. Ayiklama: `[ek] ekler/ad` satirlari mesajdan cikar.
  5. Panel: yukle (base64), bozuk veri 400, cok buyuk 400, oku 200/404.
  6. Takim akisi: balonda metin temiz, ekler ayri alan.
  7. Sohbet: lider hedefi yeniden yazsa bile ek yolu ISE tasinir.
  8. Disk olcumu `ekler/`i saymaz; `.gitignore` onu GitHub'a gondermez.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis import Ofis, Veritabani, ekler, takim  # noqa: E402
from ofis.motor.sahte import SahteMotor  # noqa: E402
from ofis.sohbet import Sohbet  # noqa: E402

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


def hata(islev, *a, **k) -> str:
    try:
        islev(*a, **k)
    except Exception as exc:                     # noqa: BLE001
        return str(exc) or type(exc).__name__
    return ""


_KOK = Path(tempfile.mkdtemp(prefix="ofis-ekler-"))
db_yolu = _KOK / "o.sqlite3"
db = Veritabani(db_yolu)
ofis = Ofis.proje_ac(db, "Ekler", amac="a", basari_olcutu="b", kok_klasor=str(_KOK))
kn = ofis.kanat_ac("A", "A")
ofis.kadro.ise_al("demir", "lider", kanat_id=kn, lider_mi=True, motor="sahte", klasor=str(_KOK))
ofis.kadro.ise_al("cinar", "backend", kanat_id=kn, motor="sahte", klasor=str(_KOK))

print("\n-- 1. ad temizleme --")
sina("Turkce harf sadelesir", ekler.ad_temizle("Ekran Görüntüsü (1).png") == "Ekran-Goruntusu-1-.png"
     or ekler.ad_temizle("Ekran Görüntüsü (1).png").startswith("Ekran-Goruntusu"),
     ekler.ad_temizle("Ekran Görüntüsü (1).png"))
sina("yol parcasi atilir", ekler.ad_temizle("..\\..\\windows\\x.ini") == "x.ini",
     ekler.ad_temizle("..\\..\\windows\\x.ini"))
sina("bos ad -> 'ek'", ekler.ad_temizle("") == "ek")

print("\n-- 2. kaydet --")
r = ekler.kaydet(ofis, "rapor.pdf", b"%PDF-1 deneme")
sina("kokun GIZLI .ofis/ekler/ klasorune yazildi (01.10 ayrim)",
     (_KOK / r["yol"]).is_file() and r["yol"].startswith(".ofis/ekler/"), r["yol"])
r2 = ekler.kaydet(ofis, "rapor.pdf", b"ikinci")
sina("ayni ad ustune YAZMAZ (benzersiz)", r2["yol"] != r["yol"] and
     (_KOK / r["yol"]).read_bytes() == b"%PDF-1 deneme")
sina("gorsel bayragi", ekler.kaydet(ofis, "a.PNG", b"x")["gorsel"] is True)
sina("bos dosya reddedilir", "Bos" in hata(ekler.kaydet, ofis, "b.txt", b""))
sina("sinirdan buyuk reddedilir",
     "buyuk" in hata(ekler.kaydet, ofis, "c.bin", b"0" * (ekler.AZAMI_BAYT + 1)))
sina(".part artigi yok", not list((_KOK / ".ofis" / "ekler").glob("*.part")))
sina("kokte ofise ait gorunur ekler/ klasoru YOK", not (_KOK / "ekler").exists())
with db.baglanti() as c:
    sina("ek_eklendi olayi", c.execute("SELECT COUNT(*) FROM olay WHERE tur='ek_eklendi'").fetchone()[0] == 3)

print("\n-- 3. okuma kapisi --")
sina("var olan ek okunur", ekler.dosya(ofis, r["ad"]).is_file())
(_KOK / "gizli.txt").write_text("sir", encoding="utf-8")
sina("klasor disi (..) reddedilir", bool(hata(ekler.dosya, ofis, "../gizli.txt")))
sina("yol parcali ad reddedilir", bool(hata(ekler.dosya, ofis, "alt/x.txt")))
sina("olmayan ek reddedilir", bool(hata(ekler.dosya, ofis, "yok.txt")))

print("\n-- 4. ayiklama --")
m, y = ekler.ayikla("buna bak\n[ek] ekler/a.png\n[ek] ekler/b.pdf")
sina("satirlar cikti", m == "buna bak" and y == ["ekler/a.png", "ekler/b.pdf"], f"{m!r} {y}")
sina("sahte ek satiri (yol kacisi) taninmaz",
     ekler.ayikla("[ek] ekler/../gizli.txt")[1] == [])
_m3, _y3 = ekler.ayikla("yeni\n[ek] .ofis/ekler/a.png")
sina("yeni bicim satiri (.ofis/ekler) da ayiklanir", _m3 == "yeni" and _y3 == [".ofis/ekler/a.png"], str(_y3))

print("\n-- 5. panel --")
try:
    from fastapi.testclient import TestClient
    from ofis.panel import olustur
    ist = TestClient(olustur(db_yolu))
    yan = ist.post("/api/ek", json={"ad": "ekran.png",
                                    "veri": base64.b64encode(b"\x89PNG deneme").decode()})
    sina("yukleme 200", yan.status_code == 200, yan.text[:120])
    ad = yan.json().get("ad", "")
    sina("okuma 200 ve icerik ayni", ist.get(f"/api/ek/{ad}").content == b"\x89PNG deneme")
    sina("bozuk veri 400", ist.post("/api/ek", json={"ad": "x", "veri": "!!!"}).status_code == 400)
    sina("cok buyuk 400", ist.post("/api/ek", json={
        "ad": "x", "veri": "A" * (ekler.AZAMI_BAYT * 4 // 3 + 100)}).status_code == 400)
    sina("yol kacisi 404", ist.get("/api/ek/..%2Fgizli.txt").status_code == 404)

    # BUYUK EK AKISLA (08.10.2026): video base64'suz, ham govdeyle; sinir ada gore.
    _vid = b"\x00\x00\x00\x18ftypmp42" + os.urandom(3 * 1024 * 1024)
    _y = ist.post("/api/ek_akis?ad=klip%201.mp4", content=_vid)
    sina("akisli video eki 200", _y.status_code == 200, _y.text[:160])
    _j = _y.json() if _y.status_code == 200 else {}
    sina("  icerik birebir, medya isaretli",
         ist.get(f"/api/ek/{_j.get('ad', 'x')}").content == _vid and _j.get("medya") is True)
    sina("  yarim (.part) dosya kalmadi",
         not list(ekler.klasor(ofis).glob("*.part")))
    sina("video siniri 2 GB, oteki 20 MB",
         ekler.sinir("a.MP4") == ekler.MEDYA_AZAMI_BAYT and ekler.sinir("a.pdf") == ekler.AZAMI_BAYT)
    _sin = ekler.MEDYA_AZAMI_BAYT
    ekler.MEDYA_AZAMI_BAYT = 1024 * 1024
    _b = ist.post("/api/ek_akis?ad=buyuk.mp4", content=b"x" * (2 * 1024 * 1024))
    ekler.MEDYA_AZAMI_BAYT = _sin
    sina("sinirdan buyuk akis 400 ve yarim dosya SILINDI",
         _b.status_code == 400 and not list(ekler.klasor(ofis).glob("*.part"))
         and not list(ekler.klasor(ofis).glob("*buyuk.mp4")), _b.text[:120])
    sina("akisla gelen pdf 20 MB sinirina tabi",
         ist.post("/api/ek_akis?ad=b.pdf", content=b"x" * (ekler.AZAMI_BAYT + 10)).status_code == 400)
    sina("bos akis 400", ist.post("/api/ek_akis?ad=bos.mp4", content=b"").status_code == 400)
    # Ajanin buyuk videoyu paylasmasi: bellege okumadan kopya, 20 MB'a takilmaz.
    _pv = Path(ofis.kok_klasoru(None)) / "cikti" / "reels.mp4"
    _pv.parent.mkdir(parents=True, exist_ok=True)
    _pv.write_bytes(b"v" * (ekler.AZAMI_BAYT + 1024))
    try:
        _py = ekler.paylas(ofis, "cikti/reels.mp4", ajan_ad="")
        sina("ajan 20 MB'tan buyuk videoyu paylasabiliyor",
             (Path(ofis.kok_klasoru(None)) / _py).stat().st_size == ekler.AZAMI_BAYT + 1024, _py)
    except ekler.EkHatasi as exc:
        sina("ajan 20 MB'tan buyuk videoyu paylasabiliyor", False, str(exc))
except ImportError as exc:
    print(f"  [ATLANDI] fastapi yok: {exc}")

print("\n-- 6. takim akisi --")
ofis.postane.soru_sor("insan", "demir", "sayfa bozuk\n[ek] ekler/" + r["ad"], mod="uyandiran")
x = [o for o in takim.akis(ofis) if o["kimden"] == "insan"][-1]
sina("balon metni temiz", x["metin"] == "sayfa bozuk", repr(x["metin"]))
sina("ek ayri alanda", x["ekler"] == ["ekler/" + r["ad"]], str(x["ekler"]))

print("\n-- 7. sohbet: ek ise tasinir --")
KOL = [{"baslik": "Duzelt", "sahip": "cinar", "neden": "hata", "kabul_olcutu": "k",
        "govde": "duzelt", "yazma_alani": ["a.txt"]}]


class Lider(SahteMotor):
    def tur_kos(self, metin, **ayar):
        if "# PATRONUN MESAJI" in metin:
            self.cevap = "```json\n" + json.dumps({"karar": "dagit", "gerekce": "is",
                                                   "hedef": "Sayfayi duzelt"}) + "\n```"
        elif '"kollar"' in metin:
            self.cevap = "```json\n" + json.dumps({"bol": False, "gerekce": "tek",
                                                   "kollar": KOL}) + "\n```"
        else:
            self.cevap = "tamam"
        return super().tur_kos(metin, **ayar)


s = Sohbet(ofis, motor_fabrikasi=lambda ad, **k: Lider(cevap=""))
list(s.konus("sayfa bozuk, ekrana bak\n[ek] ekler/" + r["ad"], azami_tik=0))
g = ofis.tahta.liste()[-1]
sina("lider hedefi yeniden yazdi ama ek yolu ISE tasindi",
     ("ekler/" + r["ad"]) in (g.get("ana_hedef") or ""), (g.get("ana_hedef") or "")[:200])

print("\n-- 9. ajan/lider dosya gonderir (paylas, 30.09) --")
(_KOK / "rapor").mkdir(exist_ok=True)
(_KOK / "rapor" / "sonuc.pdf").write_bytes(b"%PDF sonuc")
y1 = ekler.paylas(ofis, "rapor/sonuc.pdf", ajan_ad="cinar")
sina("kokteki dosya .ofis/ekler/'e KOPYALANDI, asli yerinde",
     y1.startswith(".ofis/ekler/") and (_KOK / y1).read_bytes() == b"%PDF sonuc"
     and (_KOK / "rapor" / "sonuc.pdf").is_file(), y1)
sina("mutlak yol (kok icinde) da kabul", ekler.paylas(ofis, str(_KOK / "rapor" / "sonuc.pdf")).startswith(".ofis/ekler/"))
sina("zaten .ofis/ekler/'deki dosya KOPYALANMAZ (gizli ama ofisin eki)", ekler.paylas(ofis, y1) == y1)
(_KOK / ".ofis" / "sir.txt").write_text("x", encoding="utf-8")
sina("  .ofis/ altindaki BASKA gizli dosya reddedilir", "gizli" in hata(ekler.paylas, ofis, ".ofis/sir.txt"))
sina("kok disi reddedilir", "disinda" in hata(ekler.paylas, ofis, "../gizli.txt"))
(_KOK / ".env").write_text("SIR=1", encoding="utf-8")
sina("gizli dosya (.env) reddedilir", "gizli" in hata(ekler.paylas, ofis, ".env"))
sina("olmayan dosya reddedilir", "bulunamadi" in hata(ekler.paylas, ofis, "yok.pdf"))
m2, h2 = ekler.metni_hazirla(ofis, "Rapor hazir.\n[ek] rapor/sonuc.pdf\n[ek] yok.png", ajan_ad="demir")
_, y2 = ekler.ayikla(m2)
sina("liderin [ek] satiri ekler/'e cevrildi", len(y2) == 1 and (_KOK / y2[0]).is_file(), m2)
sina("gonderilemeyen ek SESSIZ dusmez (sebep yazili)",
     "ek gonderilemedi" in m2 and len(h2) == 1, m2)
from ofis.mcp_sunucu import Oturum, arac_sohbete_yaz  # noqa: E402
_o = Oturum(); _o.db_yolu = str(db_yolu); _o.proje_id = ofis.proje_id; _o.ajan_ad = "cinar"
sina("6'dan fazla ek reddedilir",
     arac_sohbete_yaz(_o, {"metin": "x", "ekler": ["a"] * 6}).startswith("HATA"))
sina("yalniz ek (metinsiz) kabul",
     "yazildi" in arac_sohbete_yaz(_o, {"metin": "", "ekler": ["rapor/sonuc.pdf"]}))


class EkliLider(SahteMotor):
    def tur_kos(self, metin, **ayar):
        if "# PATRONUN MESAJI" not in metin:
            self.cevap = "Rapor."
            return super().tur_kos(metin, **ayar)
        self.cevap = "```json\n" + json.dumps({
            "karar": "cevap", "gerekce": "soru",
            "cevap": "Iste rapor:\n[ek] rapor/sonuc.pdf"}) + "\n```"
        return super().tur_kos(metin, **ayar)


list(Sohbet(ofis, motor_fabrikasi=lambda ad, **k: EkliLider(cevap="")).konus("raporu goster"))
_l = [o for o in takim.akis(ofis) if o["kimden"] == "demir"][-1]
sina("liderin cevabindaki dosya balonda ek olarak", len(_l["ekler"]) == 1
     and _l["metin"].startswith("Iste rapor:") and "[ek]" not in _l["metin"], repr(_l))

print("\n-- 9b. lider incelemesi sohbete GONDERILENI goruyor (30.09, G01) --")
from ofis.lider import Lider  # noqa: E402
_gi = ofis.tahta.gorev_ac("Goruntu gonder", neden="n", ana_hedef="h", kabul_olcutu="sohbete gitti",
                          govde="g", yazma_alani=["rapor/"], kanat_id=kn, sahip="cinar")
ofis.db.olay_yaz(ofis.proje_id, "ajan_sohbet", "goruntu\n[ek] " + y1, ajan_ad="cinar",
                 gorev_id=_gi["id"])
_im = Lider(ofis).inceleme_metni(_gi["no"])
sina("inceleme metninde patrona gonderilen ek var",
     "GONDERILENLER" in _im and y1 in _im, _im[-300:])

print("\n-- 9b2. bolunmus hedefin kolu yalniz KENDI olcutuyle incelenir (01.10, G08) --")
_k1 = ofis.tahta.gorev_ac("Sehirler", neden="n", ana_hedef="sehirler ve renkler", kabul_olcutu="5 sehir",
                          govde="g", yazma_alani=["s.md"], kanat_id=kn)
_k2 = ofis.tahta.gorev_ac("Renkler", neden="n", ana_hedef="sehirler ve renkler", kabul_olcutu="5 renk",
                          govde="g", yazma_alani=["r.md"], kanat_id=kn)
_km = Lider(ofis).inceleme_metni(_k1["no"])
sina("inceleme kardes kolu gosteriyor ve 'bu koldan isteme' diyor",
     "BIR KOLUDUR" in _km and "Renkler" in _km and "ISTEME" in _km, _km[:300])
sina("tek isli hedefte kardes bolumu YOK",
     "BIR KOLUDUR" not in Lider(ofis).inceleme_metni(_gi["no"]))

_kp = ofis.tahta.gorev_ac("Oyun", neden="n", ana_hedef="yilan oyunu", kabul_olcutu="oynanis goruntusu",
                          govde="g", yazma_alani=["oyun/"], kanat_id=kn)
ofis.db.olay_yaz(ofis.proje_id, "patron_sozu", "yilan oyunu yap", ajan_ad="insan", gorev_id=_kp["id"])
_kpm = Lider(ofis).inceleme_metni(_kp["no"])
sina("inceleme patronun KENDI sozunu ve 'istemedigi bicim ret sebebi degil' kuralini tasiyor (G07)",
     "Patronun KENDI sozu" in _kpm and "yilan oyunu yap" in _kpm and "RET SEBEBI" in _kpm)

print("\n-- 9c. kanitta gecen ama sohbete GITMEMIS ek olculur (30.09, G01) --")
_gg = ofis.tahta.gorev_ac("Goruntu", neden="n", ana_hedef="h", kabul_olcutu="k",
                          govde="g", yazma_alani=["x/"], kanat_id=kn, sahip="cinar")
(_KOK / ".ofis" / "ekler" / "menu.png").write_bytes(b"\x89PNG" + b"0" * 2000)
# Kanit ESKI yazimla ("ekler/menu.png") -- ajan aliskanligi; ofis onu .ofis/ekler'e esler.
ofis.tahta.kanit_ekle(_gg["no"], "gorsel", "menu goruntusu", "ekler/menu.png kaydedildi",
                      ekleyen="cinar")
ofis.tahta.kanit_ekle(_gg["no"], "dosya", "olmayan", "ekler/yok.png", ekleyen="cinar")
sina("gitmemis ek bulundu (diskte olmayan sayilmadi)",
     ekler.gonderilmemisler(ofis, [_gg["id"]]) == [".ofis/ekler/menu.png"],
     str(ekler.gonderilmemisler(ofis, [_gg["id"]])))
ofis.db.olay_yaz(ofis.proje_id, "ajan_sohbet", "ekte\n[ek] .ofis/ekler/menu.png", ajan_ad="cinar",
                 gorev_id=_gg["id"])
sina("sohbete gidince listeden cikti", ekler.gonderilmemisler(ofis, [_gg["id"]]) == [])
# gorsel_uret dosyayi YAZMA ALANINA koyar (ekler/ degil): kanit icerigi yoldur.
(_KOK / "logo").mkdir(exist_ok=True)
(_KOK / "logo" / "logo.png").write_bytes(b"\x89PNG" + b"1" * 2000)
ofis.tahta.kanit_ekle(_gg["no"], "gorsel", "logo", "logo/logo.png", ekleyen="cinar")
sina("yazma alanindaki GORSEL kanit da gitmemis sayilir",
     ekler.gonderilmemisler(ofis, [_gg["id"]]) == ["logo/logo.png"],
     str(ekler.gonderilmemisler(ofis, [_gg["id"]])))
_kopya = ekler.paylas(ofis, "logo/logo.png", ajan_ad="cinar")
ofis.db.olay_yaz(ofis.proje_id, "ajan_sohbet", "logo\n[ek] " + _kopya, ajan_ad="cinar",
                 gorev_id=_gg["id"])
(_KOK / "toplanti.docx").write_bytes(b"PK" + b"0" * 2000)
(_KOK / "app.py").write_text("print(1)", encoding="utf-8")
ofis.tahta.kanit_ekle(_gg["no"], "dosya", "belge", "toplanti.docx yazildi; app.py de guncellendi",
                      ekleyen="cinar")
_gm_ = ekler.gonderilmemisler(ofis, [_gg["id"]])
sina("kokteki Word belgesi de gitmemis sayilir (G17), kod dosyasi SAYILMAZ",
     "toplanti.docx" in _gm_ and "app.py" not in _gm_, str(_gm_))
ofis.db.olay_yaz(ofis.proje_id, "ajan_sohbet", "belge\n[ek] " + ekler.paylas(ofis, "toplanti.docx"),
                 ajan_ad="cinar", gorev_id=_gg["id"])
sina("zaman damgali kopyasi gidince listeden cikti",
     ekler.gonderilmemisler(ofis, [_gg["id"]]) == [], str(ekler.gonderilmemisler(ofis, [_gg["id"]])))
# 01.10 (patronun ofis kopyasi): karalama/ ara urunu patrona gitmez.
(_KOK / ".ofis" / "karalama").mkdir(parents=True, exist_ok=True)
(_KOK / ".ofis" / "karalama" / "arka-plan.png").write_bytes(b"\x89PNG" + b"0" * 500)
ofis.tahta.kanit_ekle(_gg["no"], "dosya", "ara", "arka plan .ofis/karalama/arka-plan.png uretildi",
                      ekleyen="cinar")
sina("karalama/ ara urunu gitmemis SAYILMAZ (patrona eklenmez)",
     ekler.gonderilmemisler(ofis, [_gg["id"]]) == [], str(ekler.gonderilmemisler(ofis, [_gg["id"]])))

print("\n-- 10. Codex gercek terminal: ret dedektoru (30.09) --")
from ofis.motor.codex import tui_ret_mi  # noqa: E402
sina("brifing okumasi (icinde 'ONAY ISTENDI' gecen) RET SAYILMAZ",
     not tui_ret_mi("Script completed\nOutput:\n... ONAY ISTENDI -- SIMDI DUR ... OFIS KAPISI ..."))
sina("kancanin olculmus reddi RET",
     tui_ret_mi("Script error:\nCommand blocked by PreToolUse hook: ONAY ISTENDI -- SIMDI DUR."))
sina("hatali ofis araci (vekil) reddi RET",
     tui_ret_mi('{"content":[{"type":"text","text":"ONAY ISTENDI"}],"isError":true}'))

print("\n-- 9d. patronun eki ISI YAPAN TAKIMIN klasorune gelir (08.10 canli) --")
_tk = _KOK / "takim-B"
_kb = ofis.kanat_ac("B", "B")
ofis.takim_klasoru_ayarla(_kb, str(_tk))
_e = ekler.kaydet(ofis, "kutu-on.jpg", b"jpg-veri")          # Tum ofis: proje koku
sina("sahne: ek proje kokunde, takimin klasorunde YOK",
     (Path(ofis.kok_klasoru(None)) / _e["yol"]).is_file()
     and not (ekler.klasor(ofis, _kb) / _e["ad"]).exists())
_kop = ekler.takima_getir(ofis, "bunlarla yap" + chr(10) + "[ek] " + _e["yol"], _kb)
sina("istek takima gidince ek takimin .ofis/ekler'ine KOPYALANDI (ayni ad)",
     _kop == [_e["ad"]] and (ekler.klasor(ofis, _kb) / _e["ad"]).read_bytes() == b"jpg-veri", str(_kop))
sina("ikinci cagri bir sey yapmaz", ekler.takima_getir(ofis, "[ek] " + _e["yol"], _kb) == [])
sina("var olmayan ek sessizce atlanir (uydurulmaz)",
     ekler.takima_getir(ofis, "[ek] .ofis/ekler/yok.jpg", _kb) == [])

print("\n-- 8. olcum ve yedek disi --")
from ofis import degisim  # noqa: E402
sina("disk olcumu .ofis/ klasorunu saymaz; 'ekler' ADI artik atlanmaz (patronun klasoru olabilir)",
     ".ofis" in degisim.ATLANAN_KLASOR and "ekler" not in degisim.ATLANAN_KLASOR
     and "karalama" not in degisim.ATLANAN_KLASOR)
kok = Path(__file__).resolve().parent.parent
r = subprocess.run(["git", "check-ignore", "-q", "calisma/ekler/x.png"], cwd=kok)
sina(".gitignore calisma/ekler/'i GitHub'dan dislar", r.returncode == 0)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
