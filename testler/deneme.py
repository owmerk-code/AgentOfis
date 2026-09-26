# -*- coding: utf-8 -*-
"""DENEME SETI kosturucu (PLAN §4-T4, §5, E01).

    python testler/deneme.py --hizli                 # hizli set, gercek motor
    python testler/deneme.py --is D01 --is D05       # secili isler
    python testler/deneme.py --hizli --kuru          # $0: dogrulayicilari sina

Her is BOS bir gecici ofiste kosar: kendi defteri, kendi proje koku, kendi
golge deposu. Gercek ofise, kasaya, kabin profiline DOKUNMAZ. Lider isi
dagitmaz; gorev dogrudan tahtaya acilir ve halka (isci -> lider incelemesi)
doner. Bolme karari ayri bir iste (D11) sinanir.

**Kuru kip** motor yerine isin iki sahte davranisini kosturur: `kuru_iyi`
dogrulayici GECTI demeli, `kuru_kotu` KALDI demeli. Ikisi de tutmazsa
sorun islerde degil DOGRULAYICIDADIR -- ve gercek kosunun sonucu
anlamsizdir.

Rapor: `testler/rapor/deneme-<zaman>.json` ve `.md`.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import argparse
import datetime as _dt
import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
for akis in (sys.stdout, sys.stderr):
    try:
        akis.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from ofis import Ofis, Veritabani                   # noqa: E402
from ofis.motor import motor_ac                     # noqa: E402
from ofis.motor.sahte import SahteMotor             # noqa: E402
from ofis.orkestra import Orkestra                  # noqa: E402
import deneme_isler as ISL                          # noqa: E402
import deneme_isler_tam as ISL_TAM                  # noqa: E402

#: Tek katalog: hizli + tam. Iki ayri liste ayrisirdi.
ISL.ISLER.update(ISL_TAM.ISLER)

RAPOR = Path(__file__).resolve().parent / "rapor"


class KuruMotor(SahteMotor):
    """Kuru kip: lider incelemesinde KAPAT der, isci turunda isin sahte
    davranisini (iyi ya da kotu) diske uygular."""

    def __init__(self, davranis, kok, ofis, bag, **ayar):
        super().__init__(**ayar)
        self.davranis, self.kok, self.ofis, self.bag = davranis, kok, ofis, bag

    def tur_kos(self, metin, **ayar):
        if "KARAR:" in metin:
            self.cevap = "Kanitlar olcutu karsiliyor.\nKARAR: kapat"
        else:
            self.cevap = self.davranis(self.kok, self.ofis, self.bag)
        return super().tur_kos(metin, **ayar)


def _gorev(tanim, bag) -> dict:
    g = tanim["gorev"]
    return dict(g(bag) if callable(g) else g)


def _kullaniciya_ac(klasor: Path) -> None:
    """Gecici klasoru, gercek `calisma/` gibi KULLANICIYA MIRAS gecen izinle acar.

    OLCULDU (26.09.2026, deneme seti codex isciyle): Python'un `mkdtemp`i
    Windows'ta yalniz `OWNER RIGHTS`e izin veren siki bir klasor aciyor.
    Codex'in sandbox'i dosyayi KENDI kullanicisiyla olusturur -- dosyanin
    sahibi o olur ve `pc` icin HICBIR izin kalmaz: dogrulayici D05'te
    `fiyatlar.csv`yi okuyamadi (Permission denied) ve klasorler
    silinemedi. Gercek `calisma/` Masaustunden `pc:(OI)(CI)F` miras aliyor;
    orada sorun YOK (olculdu). Sahne gercegi taklit etmeli -- yoksa
    deneme, gercekte olmayan bir hatayi olcer ve gercekte olani kacirir.
    """
    if os.name != "nt":
        return
    import subprocess
    kim = os.environ.get("USERNAME") or ""
    if kim:
        subprocess.run(["icacls", str(klasor), "/grant", f"{kim}:(OI)(CI)F"],
                       capture_output=True)


def is_kos(no: str, *, kip: str, motor: str, model: str, lider_model: str,
           tur_tavani: float, azami_tik: int, sakla: bool = False) -> dict:
    tanim = ISL.ISLER[no]
    sonuc = {"no": no, "ad": tanim["ad"], "kip": kip, "motor": motor,
             "model": model if kip == "gercek" else "", "olcutler": []}
    if tanim.get("destek_yok"):
        sonuc.update(durum="destek_yok", neden=tanim["destek_yok"])
        return sonuc

    ana = Path(tempfile.mkdtemp(prefix=f"ofis-deneme-{no}-"))
    _kullaniciya_ac(ana)
    kok = ana / "calisma"
    kok.mkdir()
    bag: dict = {}
    t0 = time.time()
    try:
        tanim["fikstur"](kok, bag)
        hedef_kipi = tanim.get("mod") == "hedef"
        g = {} if hedef_kipi else _gorev(tanim, bag)
        rol = tanim.get("rol") if hedef_kipi else g.pop("rol")
        db = Veritabani(ana / "o.sqlite3")
        ofis = Ofis.proje_ac(db, f"Deneme {no}", amac="deneme seti",
                             basari_olcutu="dogrulayici gecer", kok_klasor=str(kok))
        kanat = ofis.kanat_ac("DENEME", "DN")
        # Insan yerine davranan kancalar (D14 not birakir, D17 durdurur)
        # ofise buradan ulasir -- fikstur ofisten ONCE kurulur.
        bag["ofis"] = ofis
        iscler = ["isci"] + [f"isci{i}" for i in range(2, tanim.get("isci_sayisi", 1) + 1)]
        gercek = kip == "gercek"
        ofis.kadro.ise_al("lale", "lider", lider_mi=True, kanat_id=kanat,
                          klasor=str(kok), motor="claude" if gercek else "sahte",
                          model=lider_model if gercek else "")
        for ad in iscler:
            isci_motor = tanim.get("isci_motor") or (motor if gercek else "sahte")
            ofis.kadro.ise_al(ad, rol, klasor=str(kok), motor=isci_motor,
                              model=model if (gercek and isci_motor == motor) else "",
                              kanat_id=kanat)
        if gercek:
            fabrika = motor_ac
        else:
            davranis = tanim["kuru_iyi" if kip == "kuru_iyi" else "kuru_kotu"]

            def fabrika(ad, **a):
                return KuruMotor(davranis, kok, ofis, bag)
        if tanim.get("fabrika_sar"):
            fabrika = tanim["fabrika_sar"](fabrika, bag, kok)

        ork = Orkestra(ofis, motor_fabrikasi=fabrika)
        if hedef_kipi and gercek:
            # Bolme karari LIDERIN: hedef verilir, plan onun.
            ork.hedef_ver(tanim["hedef"], kanat_id=kanat, butce_usd=tur_tavani,
                          zaman_asimi=900)
        elif hedef_kipi:
            # Kuru kipte lider yok: plan elle kurulur (dogrulayici sinanir).
            tanim["kuru_gorevler"](ofis, kanat)
        else:
            ofis.tahta.gorev_ac(g.pop("baslik"), neden="deneme seti",
                                kanat_id=kanat, **g)

        def halka():
            adimlar = list(ork.kos(azami_tik=azami_tik, butce_usd=tur_tavani,
                                   zaman_asimi=900,
                                   paralel=max(1, len(iscler))))
            bag["paralel_en"] = max([bag.get("paralel_en", 1)] + [
                len(a.get("baslatilan") or []) for a in adimlar])
            return adimlar

        adimlar = halka()
        # DURDUR -> SURDUR (D17): insan durdurdu, halka durdu; kosturucu
        # insan yerine "Surdur"e basar (istek kalkar, halka yeniden doner).
        if tanim.get("durdur_sonra_surdur"):
            from ofis.koltuk import durdurma_temizle
            bag["ilk_halka"] = (adimlar[-1] if adimlar else {}).get("sebep", "")
            durdurma_temizle(ofis.db, ofis.proje_id)
            adimlar += halka()
        # INSAN CEVABI (D12): ajan insana sorduysa kosturucu insan yerine
        # cevaplar ve halkayi BIR KEZ daha dondurur.
        if tanim.get("insan_cevabi"):
            bekleyen = ofis.postane.insan_bekleyenler()
            for m in bekleyen:
                ofis.postane.cevapla(m["id"], tanim["insan_cevabi"])
            bag["soruldu"] = len(bekleyen)
            if bekleyen:
                adimlar += halka()
        son = adimlar[-1] if adimlar else {}
        sonuc["halka"] = son.get("sebep", "")
        sonuc["olcutler"] = [
            {"olcut": o, "gecti": bool(gc), "not": n}
            for o, gc, n in tanim["dogrula"](kok, ofis, bag)]
        sonuc["durum"] = ("gecti" if sonuc["olcutler"]
                          and all(o["gecti"] for o in sonuc["olcutler"])
                          else "kaldi")
        sonuc.update(_olcumler(ofis))
    except Exception as exc:            # noqa: BLE001 -- bir is digerini durdurmasin
        sonuc["durum"] = "hata"
        sonuc["hata"] = f"{exc.__class__.__name__}: {exc}"
        sonuc["iz"] = traceback.format_exc()[-1500:]
    finally:
        bag.pop("ofis", None)
        if tanim.get("kapat") and bag:
            try:
                tanim["kapat"](bag)
            except Exception:           # noqa: BLE001
                pass
    sonuc["sure_sn"] = round(time.time() - t0, 1)
    if sakla and sonuc.get("durum") in ("kaldi", "hata"):
        # Kalan isin defteri ve klasoru incelenmek uzere BIRAKILIR (silme
        # listesinden cikarilir) ve yeri soylenir.
        _temizlik._ACILAN[:] = [y for y in _temizlik._ACILAN if Path(y) != ana]
        sonuc["saklandi"] = str(ana)
    return sonuc


def _olcumler(ofis) -> dict:
    with ofis.db.baglanti() as c:
        turlar = [json.loads(r["govde"] or "{}") for r in c.execute(
            "SELECT govde FROM olay WHERE proje_id=? AND tur='tur_ozeti'",
            (ofis.proje_id,))]
        kanit = c.execute("SELECT count(*) FROM kanit k JOIN gorev g ON "
                          "g.id=k.gorev_id WHERE g.proje_id=?",
                          (ofis.proje_id,)).fetchone()[0]
        onay = c.execute("SELECT count(*) FROM onay WHERE proje_id=?",
                         (ofis.proje_id,)).fetchone()[0]
        soru = c.execute("SELECT count(*) FROM mesaj WHERE proje_id=? AND "
                         "alici='insan'", (ofis.proje_id,)).fetchone()[0]
        # KAPI mi durdurdu, ajan kendisi mi sordu? Ikisi ayri olcumdur:
        # kapisi hic atesslemeyen bir gecis, kapinin calistigini kanitlamaz.
        kapi = [r["govde"][:120] for r in c.execute(
            "SELECT govde FROM olay WHERE proje_id=? AND tur='izin' "
            "ORDER BY rowid", (ofis.proje_id,))]
        # Insana dusen HER istek metniyle raporlanir: sayi tek basina "iki
        # kart" ile "bir kart"i ayirt etmez (onay yorgunlugu, E80).
        istekler = [f"onay: {r['eylem'][:120]}" for r in c.execute(
            "SELECT eylem FROM onay WHERE proje_id=? ORDER BY rowid",
            (ofis.proje_id,))] + [f"soru: {r['govde'][:120]}" for r in c.execute(
            "SELECT govde FROM mesaj WHERE proje_id=? AND alici='insan' "
            "ORDER BY rowid", (ofis.proje_id,))]
    fiyatli = [t["maliyet_usd"] for t in turlar
               if isinstance(t.get("maliyet_usd"), (int, float))]
    return {"tur": len(turlar),
            "jeton": sum(int(t.get("jeton") or 0) for t in turlar),
            # Olculemeyen maliyet SIFIR sayilmaz (kullanim.py kurali).
            "maliyet_usd": round(sum(fiyatli), 4) if fiyatli else None,
            "fiyatsiz_tur": len(turlar) - len(fiyatli),
            "kanit": kanit, "insana_soru": onay + soru, "istekler": istekler,
            "kapi_durdurdu": len(kapi), "kapi_olaylari": kapi}


def rapor_yaz(sonuclar: list, ayar: dict) -> Path:
    RAPOR.mkdir(exist_ok=True)
    zaman = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    ad = f"deneme-{zaman}-{ayar['kip']}"
    (RAPOR / f"{ad}.json").write_text(json.dumps(
        {"zaman": zaman, "ayar": ayar, "sonuclar": sonuclar},
        ensure_ascii=False, indent=1), encoding="utf-8")
    satir = [f"# Deneme seti — {zaman} — {ayar['kip']}", "",
             f"motor: {ayar['motor']} · model: {ayar['model']} · lider: "
             f"{ayar['lider_model']} · tur tavani: ${ayar['tur_tavani']}", "",
             "| No | Is | Durum | Tur | Jeton | Maliyet | Kanit | Insana soru | Sure |",
             "|---|---|---|---|---|---|---|---|---|"]
    for s in sonuclar:
        m = s.get("maliyet_usd")
        satir.append(
            f"| {s['no']} | {s['ad']} | **{s['durum']}** | {s.get('tur', '-')} | "
            f"{s.get('jeton', '-')} | "
            f"{'fiyatsiz' if m is None and s.get('tur') else ('-' if m is None else f'${m}')} | "
            f"{s.get('kanit', '-')} | {s.get('insana_soru', '-')} | {s.get('sure_sn', '-')} sn |")
    satir.append("")
    for s in sonuclar:
        satir.append(f"## {s['no']} — {s['durum']}")
        if s.get("neden"):
            satir.append(s["neden"])
        if s.get("hata"):
            satir.append(f"HATA: {s['hata']}")
        if s.get("halka"):
            satir.append(f"halka: {s['halka']}")
        for o in s["olcutler"]:
            satir.append(f"- [{'x' if o['gecti'] else ' '}] {o['olcut']}"
                         + (f" — {o['not']}" if o["not"] else ""))
        for i in s.get("istekler") or []:
            satir.append(f"  - insana: {i}")
        if "kapi_durdurdu" in s:
            satir.append(f"  - kapi durdurdu: {s['kapi_durdurdu']} kez"
                         + "".join(f" | {k}" for k in s.get("kapi_olaylari") or []))
        satir.append("")
    (RAPOR / f"{ad}.md").write_text("\n".join(satir), encoding="utf-8")
    return RAPOR / f"{ad}.md"


def main() -> int:
    a = argparse.ArgumentParser(description="AgentOfis deneme seti")
    a.add_argument("--hizli", action="store_true")
    a.add_argument("--hepsi", action="store_true")
    a.add_argument("--is", dest="isler", action="append", default=[])
    a.add_argument("--kuru", action="store_true",
                   help="$0: dogrulayicilari iyi/kotu sahte davranisla sina")
    a.add_argument("--motor", default="claude")
    a.add_argument("--model", default="haiku")
    a.add_argument("--lider-model", default="sonnet")
    a.add_argument("--tur-tavani", type=float, default=0.60)
    a.add_argument("--azami-tik", type=int, default=4)
    a.add_argument("--rapor-yok", action="store_true")
    a.add_argument("--sakla", action="store_true",
                   help="kalan isin gecici klasorunu ve defterini incelemek icin birak")
    ar = a.parse_args()

    if ar.isler:
        secim = ar.isler
    elif ar.hepsi:
        secim = list(ISL.ISLER)
    else:
        secim = [n for n, t in ISL.ISLER.items() if t["set"] == "hizli"]
    bilinmeyen = [n for n in secim if n not in ISL.ISLER]
    if bilinmeyen:
        print("Bilinmeyen is:", ", ".join(bilinmeyen), "· gecerli:",
              ", ".join(ISL.ISLER))
        return 2

    kipler = ["kuru_iyi", "kuru_kotu"] if ar.kuru else ["gercek"]
    sonuclar, bozuk = [], 0
    for no in secim:
        for kip in kipler:
            s = is_kos(no, kip=kip, motor=ar.motor, model=ar.model,
                       lider_model=ar.lider_model, tur_tavani=ar.tur_tavani,
                       azami_tik=ar.azami_tik, sakla=ar.sakla)
            sonuclar.append(s)
            beklenen = {"kuru_iyi": "gecti", "kuru_kotu": "kaldi"}.get(kip)
            isaret = ""
            if beklenen and s["durum"] not in (beklenen, "destek_yok"):
                bozuk += 1
                isaret = f"   <-- DOGRULAYICI BOZUK (beklenen {beklenen})"
            print(f"{no} {kip:9s} {s['durum']:10s} tur={s.get('tur', '-')} "
                  f"jeton={s.get('jeton', '-')} maliyet={s.get('maliyet_usd')} "
                  f"{s.get('sure_sn')}sn{isaret}")
            for o in s["olcutler"]:
                if not o["gecti"]:
                    print(f"      - {o['olcut']}: {o['not'][:160]}")
            if s.get("hata"):
                print("      HATA:", s["hata"])
            if s.get("saklandi"):
                print("      SAKLANDI:", s["saklandi"])
    if not ar.rapor_yok:
        yol = rapor_yaz(sonuclar, {"kip": "kuru" if ar.kuru else "gercek",
                                   "motor": ar.motor, "model": ar.model,
                                   "lider_model": ar.lider_model,
                                   "tur_tavani": ar.tur_tavani})
        print("\nrapor:", yol)
    if ar.kuru:
        print(f"\nDOGRULAYICI: {'SAGLAM' if not bozuk else f'{bozuk} BOZUK'}")
        return 1 if bozuk else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
