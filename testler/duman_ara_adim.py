# -*- coding: utf-8 -*-
"""BITEN KOL BEKLEMEZ (11.10.2026). Olculdu (08.10 Brave gosterisinin
defteri): gorsel ajaninin turu 09:23'te bitti, isi incelemeye dustu; ayni
halka adimindaki video ajaninin Flow turu 09:37'ye kadar surdu, inceleme
09:38'de koştu -- 15 dk sirada. Adim kollarin HEPSINI bekliyordu.

Sinanan (jeton yakmaz; koltuk ve lider sahte, sureler gercek):
  1. uzun tur surerken biten is HEMEN incelenir; reddedilirse ayni adimda
     yeniden koşar ve uzun tur bitmeden kapanir
  2. ara adim deftere yazilir (`ara_adim`)
  3. MUTASYON: ara adim kapatilinca (eski davranis) inceleme uzun turu
     bekler -- test bunu yakalar
  4. dusen (hata) is ayni adimda yeniden DENENMEZ
  5. hep geri donen is bir adimda en cok ARA_ADIM_TUR_SINIRI kez koşar
  6. turunu bitirip isi acik birakan ajan ayni adimda yeniden koşmaz
"""
from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler; ILK ice aktarma

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ofis import Ofis, Veritabani  # noqa: E402
from ofis import orkestra as O  # noqa: E402

GECEN = KALAN = 0


def sina(baslik, kosul, not_=""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


O.ARA_ADIM_YOKLAMA_SN = 0.2
UZUN_SN = 2.5


def sahne(ad):
    d = Path(tempfile.mkdtemp(prefix=f"ofis-ara-adim-{ad}-"))
    o = Ofis.proje_ac(Veritabani(d / "o.sqlite3"), "Ara", amac="a", basari_olcutu="b", kok_klasor=str(d))
    k = o.kanat_ac("ANA", "AN")
    o.kadro.ise_al("ada", "lider", lider_mi=True, kanat_id=k, motor="sahte", klasor=str(d))
    o.kadro.ise_al("uzun", "video", kanat_id=k, motor="sahte", klasor=str(d))
    o.kadro.ise_al("kisa", "tasarim", kanat_id=k, motor="sahte", klasor=str(d))
    gu = o.tahta.gorev_ac("video isi", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=k,
                          yazma_alani=["video/"])
    gk = o.tahta.gorev_ac("gorsel isi", neden="n", ana_hedef="h", kabul_olcutu="k", kanat_id=k,
                          yazma_alani=["gorsel/"])
    o.tahta.sahiplen(gu["no"], "uzun", o.tahta.gorev(gu["no"])["revizyon"])
    o.tahta.sahiplen(gk["no"], "kisa", o.tahta.gorev(gk["no"])["revizyon"])
    return o, gu["no"], gk["no"]


def sahte_koltuk(o, iz, *, dusur=()):
    """Tur: uzun ajan UZUN_SN, kisa 0.2 sn; bitince kanit + incelemeye."""
    def kos(no, ajan, **_):
        iz.append(("bas", no, ajan, time.monotonic()))
        if no in dusur:
            raise RuntimeError("sahte dusus")
        time.sleep(UZUN_SN if ajan == "uzun" else 0.2)
        g = o.tahta.gorev(no)
        o.tahta.kanit_ekle(no, "dosya", "yapildi", "x.txt", ajan)
        o.tahta.incelemeye_ver(no, o.tahta.gorev(no)["revizyon"])
        iz.append(("son", no, ajan, time.monotonic()))
        return {"durum": g["durum"]}
    return kos


def sahte_lider(o, iz, kararlar):
    """kararlar: no -> ['ret', 'kapat', ...] (sirayla)."""
    def incele(no, **_):
        h = (kararlar.get(no) or ["kapat"]).pop(0) if kararlar.get(no) else "kapat"
        g = o.tahta.gorev(no)
        if h == "ret":
            o.tahta.geri_gonder(no, g["revizyon"], gerekce="eksik", gonderen="ada")
        else:
            o.tahta.kapat(no, g["revizyon"], kapatan="ada")
        iz.append(("incele", no, h, time.monotonic()))
        return {"hukum": "kabul" if h == "kapat" else "ret", "gerekce": "sahte", "gorev_no": no, "ders": False}
    return incele


def an(iz, tur, no, sira=0):
    x = [e[3] for e in iz if e[0] == tur and e[1] == no]
    return x[sira] if len(x) > sira else None


print("1. uzun tur surerken biten is incelenir, reddedilir, yeniden koşar, kapanir")
o, nu, nk = sahne("bir")
ork = o.orkestra
iz = []
ork.koltuk.kos = sahte_koltuk(o, iz)
ork.lider.incele = sahte_lider(o, iz, {nk: ["ret", "kapat"]})
t0 = time.monotonic()
oz = ork.tik(paralel=3)
uzun_son = an(iz, "son", nu)
ilk_inceleme = an(iz, "incele", nk, 0)
sina("kisa isin ILK incelemesi uzun tur bitmeden", ilk_inceleme is not None and ilk_inceleme < uzun_son,
     str(iz))
sina("  reddedilen is AYNI adimda yeniden koştu (2 tur)",
     sum(1 for e in iz if e[0] == "bas" and e[1] == nk) == 2, str(iz))
sina("  ikinci inceleme de uzun tur bitmeden ve is KAPANDI",
     (an(iz, "incele", nk, 1) or 1e9) < uzun_son and o.tahta.gorev(nk)["durum"] == "bitti",
     str((iz, o.tahta.gorev(nk)["durum"])))
sina("  uzun is bir kez koştu, ayni ajana iki tur verilmedi",
     sum(1 for e in iz if e[0] == "bas" and e[1] == nu) == 1)
_ilk_bas = min(e[3] for e in iz if e[0] == "bas")
_son = max(e[3] for e in iz)
sina("  turlar uzun turdan fazla surmedi (yeniden tur paralel)", _son - _ilk_bas < UZUN_SN + 1.0,
     f"ilk tur basi -> son olay {_son - _ilk_bas:.1f} sn; adim toplam {time.monotonic() - t0:.1f} sn")
with o.db.baglanti() as c:
    _aa = c.execute("SELECT govde FROM olay WHERE tur = 'ara_adim'").fetchall()
sina("2. ara adim deftere yazildi", len(_aa) == 1 and f"#{nk}" in _aa[0][0] and f"#{nu}" in _aa[0][0],
     str([r[0] for r in _aa]))
sina("  ozette iki inceleme + uc baslatma", len(oz["incelenen"]) == 2 and len(oz["baslatilan"]) == 3,
     str((len(oz["incelenen"]), len(oz["baslatilan"]))))

print("\n3. MUTASYON: ara adim kapali (eski davranis) -> inceleme uzun turu BEKLER")
o, nu, nk = sahne("mut")
ork = o.orkestra
iz = []
ork.koltuk.kos = sahte_koltuk(o, iz)
ork.lider.incele = sahte_lider(o, iz, {nk: ["kapat"]})
_asil = ork._inceleme_ve_danisma


def _eski(ozet, kanat_id, **kw):
    if kw.get("haric_no"):
        return None          # ara adimda hicbir sey yapma
    return _asil(ozet, kanat_id, **kw)


ork._inceleme_ve_danisma = _eski
ork.tik(paralel=3)
sina("eski davranista kisa is bu adimda HIC incelenmedi (test farki yakaliyor)",
     an(iz, "incele", nk) is None, str(iz))

print("\n4. dusen is ayni adimda yeniden denenmez")
o, nu, nk = sahne("dus")
ork = o.orkestra
iz = []
ork.koltuk.kos = sahte_koltuk(o, iz, dusur={nk})
ork.lider.incele = sahte_lider(o, iz, {})
ork.tik(paralel=3)
sina("dusen is bir kez denendi", sum(1 for e in iz if e[0] == "bas" and e[1] == nk) == 1, str(iz))

print("\n5. hep geri donen is bir adimda en cok ARA_ADIM_TUR_SINIRI kez")
o, nu, nk = sahne("sinir")
ork = o.orkestra
iz = []
ork.koltuk.kos = sahte_koltuk(o, iz)
ork.lider.incele = sahte_lider(o, iz, {nk: ["ret"] * 20})
ork.tik(paralel=3)
_n = sum(1 for e in iz if e[0] == "bas" and e[1] == nk)
sina(f"kisa is {O.ARA_ADIM_TUR_SINIRI} kez koştu", _n == O.ARA_ADIM_TUR_SINIRI, str(_n))

print("\n6. turunu bitirip isi ACIK birakan ajan ayni adimda yeniden KOSMAZ (eskisi gibi sonraki adim)")
o, nu, nk = sahne("acik")
ork = o.orkestra
iz = []
_kos = sahte_koltuk(o, iz)


def _acik_birak(no, ajan, **kw):
    if ajan == "kisa":
        iz.append(("bas", no, ajan, time.monotonic()))
        time.sleep(0.2)
        return {"durum": "calisiyor"}      # incelemeye vermedi, is acik
    return _kos(no, ajan, **kw)


ork.koltuk.kos = _acik_birak
ork.lider.incele = sahte_lider(o, iz, {})
ork.tik(paralel=3)
_n = sum(1 for e in iz if e[0] == "bas" and e[1] == nk)
sina("acik kalan is bu adimda bir kez koştu (11.10: panel senaryosu halkasi bitmiyordu)", _n == 1, str(_n))

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
