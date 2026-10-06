"""DEVRAL / OFISE GERI VER -- insan bir ajanin isini alir, sonra geri verir.

PLAN E18. Rakipte ajan panosu hep gercek bir terminaldir ve insan istedigi
an icine yazar; bizde varsayilan gorunum OKUNUR akistir (ne yapti, hangi
kaniti ekledi, diskte ne degisti) ve gercek terminal yalnizca "Devral"
denince acilir. Izlemek icin okunur akis, el atmak icin gercek terminal.

OLCULENLER (28.09.2026, ConPTY, bos gecici klasor):

* Ofisin ARKA PLANDA baslattigi oturum `claude --resume <id>` ve
  `codex resume <id>` ile terminalde acildi ve onceki konusmayi GORDU.
* Ama insanin terminalde yazdigi Claude'un oturum dosyasina YAZILMADI
  (terminal duzgun kapatildiginda bile). Yani "ofise geri ver"i CLI'in
  ic dosyasina dayandirmak, insanin yaptigini ajana ULASTIRMAMAK olurdu.

Bu yuzden DEVIR OFISIN KENDI KAYDIYLA yapilir -- motordan bagimsiz:

1. **Devral:** is insanin olur; halka ona DOKUNMAZ (`devralinmis`),
   koltuk reddeder. Yazma kilidi ajanda KALIR (kira duser diye korunur):
   baska bir ajan araya giremez. Diskin anlik goruntusu ve golge depo
   ALINIR -- insanin degisikligi de olculur ve geri alinabilir.
2. **Terminal:** ajanin kendi oturumu, ajanin kendi klasorunde, hesabin
   kendi kimligiyle (`Motor.etkilesimli_komut`). Komutlari insan onaylar;
   klavyenin basinda o var.
3. **Ofise geri ver:** terminal DUZGUN kapatilir; diskte ne degistigi
   OLCULUR ve "insan" adina yazilir; ekranin dokumu deftere gecer; insanin
   notu + degisen dosyalar ajana PATRONUN NOTU olarak gider
   (`postane.not_birak` -- `NOT_KURALI`: not isin tanimindan yenidir).
   Ajan bir sonraki turda kaldigi yerden surer ve bunu gorur.

Kosan bir TUR devralinamaz: once Durdur. Ayni anda iki yazar olurdu
(Yasa 1) -- ajanin turu ve insanin terminali ayni dosyalara yazabilirdi.
"""

from __future__ import annotations

import json
import subprocess

from . import degisim, geri_al, terminal
from .db import simdi
from .motor import motor_ac, MotorHatasi

ONEK = "devral:"

#: Bir turun "kosuyor" sayilmasi icin kilit nabzinin tazeligi (sn).
#: Koltuk saniyede bir nabiz atar; donmus bir surec nabiz atmaz.
KOSUYOR_NABIZ_SN = 30


class DevralHatasi(RuntimeError):
    pass


# ------------------------------------------------------------- sorgular
def devralinmis(db, proje_id: str, gorev_id: str) -> dict | None:
    """Is insanda mi? Kayit DEFTERDE: panel yeniden baslasa da is
    kendiliginden ajana donmez (insanin elindeki is sessizce elinden
    alinmamali)."""
    ham = db.ayar_oku(proje_id, ONEK + str(gorev_id), "")
    if not ham:
        return None
    try:
        return json.loads(ham)
    except ValueError:
        return {"bozuk": ham}


def devralinanlar(db, proje_id: str) -> list:
    with db.baglanti() as c:
        rows = c.execute(
            "SELECT anahtar, deger FROM ayar WHERE proje_id = ? "
            "AND anahtar LIKE ? AND deger != ''",
            (proje_id, ONEK + "%")).fetchall()
    sonuc = []
    for r in rows:
        try:
            d = json.loads(r["deger"])
        except ValueError:
            continue
        d["gorev_id"] = r["anahtar"][len(ONEK):]
        t = terminal.al(d["gorev_id"])
        d["terminal_acik"] = bool(t and t["terminal"].canli())
        sonuc.append(d)
    return sonuc


def _son_sahip(db, proje_id: str, gorev: dict) -> str:
    if gorev.get("sahip"):
        return gorev["sahip"]
    with db.baglanti() as c:
        row = c.execute(
            "SELECT ajan_ad FROM olay WHERE proje_id = ? AND gorev_id = ? "
            "AND tur = 'sahiplenildi' AND ajan_ad != '' "
            "ORDER BY rowid DESC LIMIT 1", (proje_id, gorev["id"])).fetchone()
    return row["ajan_ad"] if row else ""


def _bu_isin_oturumu(db, proje_id: str, ajan: dict, gorev: dict) -> str:
    """Ajanin oturumu BU ise mi ait? Degilse bos: baska bir isin
    konusmasini bu isin terminalinde acmak yanlis baglam olurdu
    (`koltuk._devam_mi` ile ayni olcut)."""
    if not ajan.get("oturum_id"):
        return ""
    with db.baglanti() as c:
        row = c.execute(
            "SELECT gorev_id FROM olay WHERE proje_id = ? AND tur = 'oturum' "
            "AND ajan_ad = ? ORDER BY rowid DESC LIMIT 1",
            (proje_id, ajan["ad"])).fetchone()
    return ajan["oturum_id"] if row and row["gorev_id"] == gorev["id"] else ""


def tur_kosuyor_mu(db, proje_id: str, gorev_id: str) -> bool:
    """Bu isin bir turu SU AN kosuyor mu -- olay defterinden + kilit nabzi.

    `basladi` son `tur_ozeti`nden yeniyse tur acik demektir; ama cokmus
    bir surec `tur_ozeti` yazamaz, o yuzden kilidin nabzi da taze olmali.
    """
    from .tahta import _yas_saniye
    with db.baglanti() as c:
        bas = c.execute(
            "SELECT COALESCE(MAX(rowid),0) FROM olay WHERE proje_id=? AND "
            "gorev_id=? AND tur='basladi'", (proje_id, gorev_id)).fetchone()[0]
        son = c.execute(
            "SELECT COALESCE(MAX(rowid),0) FROM olay WHERE proje_id=? AND "
            "gorev_id=? AND tur IN ('tur_ozeti','birakildi','incelemede')",
            (proje_id, gorev_id)).fetchone()[0]
        nabiz = c.execute(
            "SELECT son_nabiz FROM yazma_kilidi WHERE proje_id=? AND gorev_id=?",
            (proje_id, gorev_id)).fetchall()
    if bas <= son:
        return False
    return any(_yas_saniye(n["son_nabiz"]) < KOSUYOR_NABIZ_SN for n in nabiz)


# ------------------------------------------------------------- devral
def devral(ofis, no: int, *, fabrika=motor_ac, sutun: int = 120,
           satir: int = 32) -> dict:
    """Isi insana verir ve ajanin oturumunu gercek bir terminalde acar."""
    db, pid = ofis.db, ofis.proje_id
    gorev = ofis.tahta.gorev(no)
    if gorev["durum"] not in ("calisiyor", "hazir"):
        raise DevralHatasi(
            f"#{no} '{gorev['durum']}' durumunda -- yalniz calisan ya da "
            "hazir bekleyen is devralinir.")
    if devralinmis(db, pid, gorev["id"]):
        raise DevralHatasi(f"#{no} zaten sende (devralinmis).")
    ajan_ad = _son_sahip(db, pid, gorev)
    if not ajan_ad:
        raise DevralHatasi(
            f"#{no} henuz hicbir ajana gitmedi -- devralinacak bir ajan "
            "oturumu yok. Isi bir ajana verdikten sonra devral.")
    if tur_kosuyor_mu(db, pid, gorev["id"]):
        raise DevralHatasi(
            f"#{no} icin {ajan_ad}'in turu SU AN kosuyor. Once 'Durdur' -- "
            "ajanin turu ile senin terminalin ayni dosyalara ayni anda "
            "yazabilirdi (Yasa 1).")
    ajan = ofis.kadro.ajan(ajan_ad)
    try:
        motor = fabrika(ajan["motor"])
    except MotorHatasi as exc:
        raise DevralHatasi(f"{ajan_ad}'in motoru acilamadi: {exc}") from exc
    oturum = _bu_isin_oturumu(db, pid, ajan, gorev)
    komut = motor.etkilesimli_komut(oturum_id=oturum,
                                    klasor=ajan.get("klasor") or "",
                                    model=ajan.get("model") or "")
    if not komut:
        raise DevralHatasi(
            f"'{ajan['motor']}' motoru devralinamiyor (terminalde acma yolu "
            "bildirmiyor).")
    durum = terminal.pty_durumu()
    if durum:
        raise DevralHatasi(durum)

    # KILIT: is birakilmissa (kaynak tukendi, durduruldu) yeniden alinir --
    # insan KILITSIZ calismasin (Yasa 1). Kilit ajan adina tutulur; ajan
    # geri aldiginda ayni kilitle surer.
    if gorev["durum"] == "hazir":
        try:
            ofis.tahta.sahiplen(no, ajan_ad, gorev["revizyon"])
        except Exception as exc:          # noqa: BLE001 -- sebebi insana
            raise DevralHatasi(f"#{no} kilidi alinamadi: {exc}") from exc
        gorev = ofis.tahta.gorev(no)

    # OLCUM: insanin yaptigi da olculur ve geri alinabilir.
    kok = ofis.tahta.gorev_koku(gorev)
    once_anlik, golge_once = None, ""
    if kok:
        try:
            once_anlik = degisim.anlik(kok, degisim.ofis_dosyalari(db.yol))
        except OSError:
            once_anlik = None
        if once_anlik is not None:
            try:
                golge_once = geri_al.Golge(
                    kok, degisim.ofis_dosyalari(db.yol)).anlik(f"once devral #{no}")
            except (geri_al.GeriAlHatasi, OSError, subprocess.SubprocessError):
                golge_once = ""

    try:
        t = terminal.Terminal(komut["argv"], klasor=ajan.get("klasor") or kok,
                              ortam=komut.get("ortam"),
                              kapat_girdisi=komut.get("kapat", ""),
                              sutun=sutun, satir=satir)
    except terminal.TerminalHatasi as exc:
        raise DevralHatasi(str(exc)) from exc
    terminal.kaydet(gorev["id"], t, once_anlik=once_anlik,
                    golge_once=golge_once, kok=kok)
    kayit = {"no": no, "ajan": ajan_ad, "motor": ajan["motor"],
             "oturum": oturum, "basladi": simdi()}
    db.ayar_yaz(pid, ONEK + gorev["id"], json.dumps(kayit, ensure_ascii=False))
    db.olay_yaz(pid, "devral",
                f"#{no} insan devraldi ({ajan_ad} · {ajan['motor']}"
                + (" · oturum surdu" if oturum else " · yeni oturum") + ")",
                ajan_ad=ajan_ad, gorev_id=gorev["id"])
    return {**kayit, "gorev_id": gorev["id"],
            "olcum": once_anlik is not None, "kafes": t.kafes.kuruldu}


# ------------------------------------------------------------- geri ver
def geri_ver(ofis, no: int, *, not_: str = "") -> dict:
    """Terminali kapatir, insanin yaptigini OLCER ve ajana iletir."""
    db, pid = ofis.db, ofis.proje_id
    gorev = ofis.tahta.gorev(no)
    kayit = devralinmis(db, pid, gorev["id"])
    if not kayit:
        raise DevralHatasi(f"#{no} sende degil (devralinmamis).")
    ajan_ad = kayit.get("ajan") or _son_sahip(db, pid, gorev)
    acik = terminal.cikar(gorev["id"]) or {}
    t = acik.get("terminal")
    kapanis, dokum = "terminal yoktu", ""
    if t:
        dokum = t.dokum()
        kapanis = t.kapat()

    # OLCUM -- anlik goruntu terminal ile ayni surecte tutulur; panel
    # arada yeniden basladiysa YOKTUR ve bu SOYLENIR ("degismedi" denmez).
    degisen, olcum_notu = [], ""
    once = acik.get("once_anlik")
    kok = acik.get("kok") or ofis.tahta.gorev_koku(ofis.tahta.gorev(no))
    if once is not None and kok:
        try:
            sonra = degisim.anlik(kok, degisim.ofis_dosyalari(db.yol))
            kayitlar = degisim.karsilastir(once, sonra,
                                           beyan=gorev.get("yazma_alani") or ())
            if kayitlar:
                degisim.yaz(db, pid, gorev["id"], "insan", kayitlar)
                degisen = [k["yol"] for k in kayitlar]
                if acik.get("golge_once"):
                    try:
                        g = geri_al.Golge(kok, degisim.ofis_dosyalari(db.yol))
                        geri_al.kaydet(db, pid, gorev["id"], "insan", kok,
                                       acik["golge_once"],
                                       g.anlik(f"sonra devral #{no}"),
                                       len(kayitlar), not_="devral")
                    except (geri_al.GeriAlHatasi, OSError,
                            subprocess.SubprocessError):
                        olcum_notu = "geri alma kaydi yazilamadi"
        except OSError as exc:
            olcum_notu = f"fark olculemedi: {exc}"
    else:
        olcum_notu = ("fark OLCULEMEDI (panel arada yeniden basladi; "
                      "degisiklik yok DEMEK DEGILDIR)")

    if dokum:
        db.olay_yaz(pid, "devral_dokum", dokum[-3000:], ajan_ad=ajan_ad,
                    gorev_id=gorev["id"])

    # AJANA GIDEN NOT -- tek kanal: patronun notu (NOT_KURALI).
    parcalar = ["Patron bu isi DEVRALDI, terminalde calisti ve sana geri verdi."]
    if (not_ or "").strip():
        parcalar.append("Notu: " + not_.strip())
    if degisen:
        parcalar.append("Diskte degistirdigi dosyalar (ofisin olcumu): "
                        + ", ".join(degisen[:30])
                        + (f" (+{len(degisen) - 30})" if len(degisen) > 30 else "")
                        + ". Kaldigin yerden surdurmeden once bu dosyalara bak.")
    elif olcum_notu:
        parcalar.append(olcum_notu + " -- dosyalari kendin kontrol et.")
    else:
        parcalar.append("Diskte bir dosya degistirmedi.")
    metin = " ".join(parcalar)
    ulasti = True
    try:
        ofis.postane.not_birak(ajan_ad, metin, gorev_no=no)
    except Exception:                      # noqa: BLE001 -- kayit yine dussun
        ulasti = False
        db.olay_yaz(pid, "uyari", f"#{no} devir notu ajana birakilamadi: {metin}",
                    ajan_ad=ajan_ad, gorev_id=gorev["id"])

    db.ayar_yaz(pid, ONEK + gorev["id"], "")
    db.olay_yaz(pid, "devral_bitti",
                f"#{no} ofise geri verildi -- terminal {kapanis}; "
                + (f"{len(degisen)} dosya degisti" if degisen else (olcum_notu or "dosya degismedi")),
                ajan_ad=ajan_ad, gorev_id=gorev["id"])
    return {"no": no, "ajan": ajan_ad, "kapanis": kapanis,
            "degisen": degisen, "olcum_notu": olcum_notu,
            "not_iletildi": ulasti}
