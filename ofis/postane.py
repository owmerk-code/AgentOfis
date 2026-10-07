# -*- coding: utf-8 -*-
"""Postane: ajanlar arasi soru-cevap ve insan onayi.

Semada bastan beri duran ama bugune kadar kullanilmayan iki tablo:
`mesaj` ve `onay`. Ikisi de ayni bosluga bakiyor -- ajanin DURMASI gereken
anlar.

Neden onemli: Cognition'in acik sorunu "ajanlar arasi iletisim varsayilan
olarak calismiyor". Calismadiginda ajan susmaz; TAHMIN EDER. Yanlis
varsayimla emin adimlarla ilerler ve iki saat sonra atilacak is uretir.
Sorabilmek, bu yuzden bir konfor degil hata onleyicidir.

Iki bekleme turu, iki ayri sebep:

* **Soru** (`mesaj`, mod='bekleyen'): ajanin BILGISI eksik. Cevap gelince
  ayni oturumda kaldigi yerden devam eder -- bu yuzden kilit birakilmaz.
* **Onay** (`onay`): ajanin YETKISI eksik. Kod yazmak sormaz; para
  harcamak, disariya yazmak, yayina almak sorar. Tam otonomi istenmez:
  is yapan ajan sessizce yanlis yone sapabilir ve en pahali sapmalar
  geri alinamayanlardir.

Gorev durumu DEGISMEZ. Tahtada bes sutun vardir
(bekliyor/hazir/calisiyor/inceleme/bitti) ve "soru bekliyor" bunlardan
biri degildir -- gorev hala `calisiyor`dur, sahibi ve kilidi durur.
Bekleme, gorevin DURUMU degil TURETILEN bir hali: panelde ajan "bekleme
odasi"nda gorunur, tahtada karti yerinde kalir. Sutun acmak, ayni bilgiyi
iki yerde tutmak olurdu.
"""

from __future__ import annotations

import hashlib
import uuid

from .db import simdi
# Sadelestirmenin TEK gerceklestirmesi `riskli.py`de. Kendi kopyasini
# yazsaydik iki kapi ayni metni farkli sadelestirir ve ayni eylem iki
# ayri imza uretirdi.
from .riskli import sadelestir as _sadelestir


class PostaneHatasi(RuntimeError):
    pass


#: PATRONUN NOTU: insanin CALISAN bir ajana isi hakkinda yazdigi yonlendirme
#: ("dur, sunu degistir"). Soru degildir (cevap beklenmez, ajani durdurmaz)
#: ve lidere gonderilmez -- dogrudan o isin sahibine gider. `okundu=1`
#: notun ajana ULASTIGI andir (tur surerken ya da tur basinda); yazilmis
#: olmasi ulastigi anlamina gelmez.
NOT_MODU = "yonlendirme"

#: Notun isin ilk tanimiyla iliskisi -- TEK cumle, her yerde ayni. OLCULDU
#: (27.09, D14 codex): not isin metniyle celisti, ajan (dogru davranarak)
#: lidere sordu; liderin DANISMA turu notu hic gormedigi icin "notu
#: kullanma" dedi, ayni liderin INCELEMESI notu gordugu icin isi "not
#: uygulanmamis" diye geri gonderdi. Ayni lider iki kanalda iki resme
#: bakiyordu ve is tik sinirinda oldu. Kural dort yerde ayri cumleyle
#: yaziliydi (brifing, tur ici not, inceleme, danisma yoktu); tek sabit
#: hepsine ayni sozu soyletir.
#: Kapi kart actiktan sonra ajana soylenen tek cumle. OLCULDU (29.09,
#: gercek terminal): kapi karti actiktan sonra ajan bir de kendisi
#: `onay_iste` cagirdi -- patrona ayni is icin IKI kart dustu ve cevaplanmayan
#: ikinci kart isi incelemeye gecirmedi. Uc kapi da bu cumleyi kullanir.
KART_ACILDI = ("Onay karti patrona ZATEN dusuruldu: `onay_iste` CAGIRMA, "
               "ikinci kart ACMA.")

NOT_KURALI = ("Patronun notu isin ilk tanimindan YENIDIR ve onu DEGISTIRIR: "
              "ikisi celisirse NOT gecerlidir (is patronundur). Yalniz notun "
              "kendisi belirsizse ya da isi imkansiz kiliyorsa DUR ve "
              "`soru_sor` ile sor.")


def gorev_notlari(db, proje_id: str, gorev_id: str) -> list:
    """Bir isin BUTUN patron notlari, yazilis sirasiyla.

    TEK sorgu: brifing (isin tanimina ek), koltuk (iletilecekler) ve lider
    incelemesi (hangi not ulasti, hangisi ulasmadi) ayni yerden okur. Uc
    ayri sorgu olsaydi biri `okundu`yu, oteki sirayi farkli yorumlardi.
    """
    with db.baglanti() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, alici, govde, okundu, olusturuldu FROM mesaj "
            "WHERE proje_id = ? AND gorev_id = ? AND mod = ? "
            "ORDER BY olusturuldu, rowid",
            (proje_id, gorev_id, NOT_MODU)).fetchall()]


class Postane:
    def __init__(self, ofis) -> None:
        self.ofis = ofis
        self.db = ofis.db
        self.proje_id = ofis.proje_id

    # -- patronun notlari ----------------------------------------------------

    def not_birak(self, alici: str, govde: str, *, gorev_no=None) -> dict:
        """Insanin CALISAN bir ajana notu. Is aciklamasina EK sayilir.

        Not bir ISE baglidir, ajana degil: ajan baska ise gecince bu isin
        notu onu izlememeli. Is verilmezse ajanin elindeki is bulunur;
        elinde is yoksa not REDDEDILIR -- yeni bir is, lidere yazilir
        (lider insanin tek muhatabidir; not, zaten verilmis bir isin
        yonunu duzeltir, is DAGITMAZ).
        """
        govde = (govde or "").strip()
        if not govde:
            raise PostaneHatasi("Bos not birakilamaz.")
        if alici == "insan":
            raise PostaneHatasi("Not bir AJANA yazilir.")
        try:
            self.ofis.kadro.ajan(alici)
        except Exception:
            adlar = ", ".join(a["ad"] for a in self.ofis.kadro.liste())
            raise PostaneHatasi(f"'{alici}' diye biri yok. Ajanlar: {adlar}")
        if gorev_no is None:
            with self.db.baglanti() as conn:
                row = conn.execute(
                    "SELECT no FROM gorev WHERE proje_id = ? AND sahip = ? "
                    "AND durum IN ('calisiyor', 'inceleme') AND silindi = 0 "
                    "ORDER BY guncellendi DESC, rowid DESC LIMIT 1",
                    (self.proje_id, alici)).fetchone()
            if not row:
                raise PostaneHatasi(
                    f"{alici} su an bir is uzerinde degil; not ancak VERILMIS "
                    "bir isin yonunu duzeltir. Yeni is icin lidere yaz.")
            gorev_no = row["no"]
        gorev = self.ofis.tahta.gorev(gorev_no)
        if gorev["durum"] in ("bitti", "iptal"):
            raise PostaneHatasi(
                f"#{gorev_no} {gorev['durum']}: kapanmis bir ise not yazilmaz. "
                "Devam gerekiyorsa lidere yaz.")
        if (gorev.get("sahip") or "") != alici:
            raise PostaneHatasi(
                f"#{gorev_no} {alici}'in isi degil (sahibi: "
                f"{gorev.get('sahip') or 'yok'}). Not isin SAHIBINE yazilir.")
        mesaj_id = uuid.uuid4().hex
        with self.db.baglanti() as conn:
            conn.execute(
                "INSERT INTO mesaj (id, proje_id, gonderen, alici, govde, mod, "
                "gorev_id, cevap, cevaplandi, okundu, olusturuldu) "
                "VALUES (?, ?, 'insan', ?, ?, ?, ?, '', NULL, 0, ?)",
                (mesaj_id, self.proje_id, alici, govde, NOT_MODU,
                 gorev["id"], simdi()),
            )
        self.db.olay_yaz(self.proje_id, "not",
                         f"insan -> {alici} (#{gorev_no}): {govde[:200]}",
                         ajan_ad=alici, gorev_id=gorev["id"])
        return {"id": mesaj_id, "alici": alici, "govde": govde,
                "gorev_no": gorev_no}

    def bekleyen_notlar(self, alici: str, *, gorev_no) -> list:
        """Bu ise yazilmis, ajana HENUZ ulasmamis notlar."""
        gorev = self.ofis.tahta.gorev(gorev_no)
        return [n for n in gorev_notlari(self.db, self.proje_id, gorev["id"])
                if n["alici"] == alici and not n["okundu"]]

    def not_iletildi(self, mesaj_id: str, *, yol: str) -> bool:
        """Notun ajana ULASTIGI an. Iki kez isaretlenmez (ilk yol kalir).

        `yol`: 'tur_ici' (motor tur surerken aldi) ya da 'tur_basinda'
        (bir sonraki turun istemine girdi). Ikisi ayri yazilir: insan notun
        ne zaman etkili oldugunu bilmeli.
        """
        with self.db.baglanti() as conn:
            row = conn.execute(
                "SELECT m.alici, m.govde, m.gorev_id, g.no AS gorev_no "
                "FROM mesaj m LEFT JOIN gorev g ON g.id = m.gorev_id "
                "WHERE m.id = ? AND m.proje_id = ? AND m.mod = ? AND m.okundu = 0",
                (mesaj_id, self.proje_id, NOT_MODU)).fetchone()
            if not row:
                return False
            conn.execute("UPDATE mesaj SET okundu = 1 WHERE id = ?", (mesaj_id,))
        ne = "tur SURERKEN" if yol == "tur_ici" else "tur BASINDA"
        self.db.olay_yaz(self.proje_id, "not_iletildi",
                         f"{row['alici']} notu aldi ({ne}, #{row['gorev_no']}): "
                         f"{row['govde'][:160]}",
                         ajan_ad=row["alici"], gorev_id=row["gorev_id"])
        return True

    # -- sorular -----------------------------------------------------------

    def soru_sor(self, gonderen: str, alici: str, govde: str, *,
                 gorev_no=None, mod: str = "bekleyen", kaynak: str = "") -> dict:
        govde = (govde or "").strip()
        if not govde:
            raise PostaneHatasi("Bos soru sorulamaz.")
        if mod not in ("sessiz", "uyandiran", "bekleyen"):
            raise PostaneHatasi(f"Bilinmeyen mesaj modu: {mod}")
        # Alici DOGRULANIR. Var olmayan bir ada yazilan soru hicbir zaman
        # teslim edilemez ve kuyrukta sonsuza kadar durur -- soran ajan da
        # sonsuza kadar bekler. Yanlis yazilmis bir ad, sessiz bir olum
        # sebebidir; burada gurultuyle reddedilir.
        if alici != "insan":
            try:
                self.ofis.kadro.ajan(alici)
            except Exception:
                adlar = ", ".join(a["ad"] for a in self.ofis.kadro.liste())
                raise PostaneHatasi(
                    f"'{alici}' diye biri yok. Alici 'insan' ya da su "
                    f"ajanlardan biri olmali: {adlar}")
        gorev_id = None
        if gorev_no is not None:
            gorev_id = self.ofis.tahta.gorev(gorev_no)["id"]
        mesaj_id = uuid.uuid4().hex
        with self.db.baglanti() as conn:
            conn.execute(
                "INSERT INTO mesaj (id, proje_id, gonderen, alici, govde, mod, "
                "gorev_id, cevap, cevaplandi, okundu, olusturuldu, kaynak) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, '', NULL, 0, ?, ?)",
                (mesaj_id, self.proje_id, gonderen, alici, govde, mod,
                 gorev_id, simdi(), kaynak or ""),
            )
        self.db.olay_yaz(self.proje_id, "soru",
                         f"{gonderen} -> {alici}: {govde[:200]}",
                         ajan_ad=gonderen, gorev_id=gorev_id)
        return {"id": mesaj_id, "alici": alici, "govde": govde, "mod": mod}

    def cevapla(self, mesaj_id: str, cevap: str, *, cevaplayan: str = "insan") -> dict:
        cevap = (cevap or "").strip()
        if not cevap:
            raise PostaneHatasi(
                "Bos cevap, cevap degildir. Ajan hala bekliyor olur ve "
                "bekledigini kimse fark etmez."
            )
        with self.db.baglanti() as conn:
            row = conn.execute(
                "SELECT * FROM mesaj WHERE id = ? AND proje_id = ?",
                (mesaj_id, self.proje_id),
            ).fetchone()
            if not row:
                raise PostaneHatasi(f"Mesaj bulunamadi: {mesaj_id}")
            conn.execute(
                "UPDATE mesaj SET cevap = ?, cevaplandi = ?, okundu = 1 WHERE id = ?",
                (cevap, simdi(), mesaj_id),
            )
        self.db.olay_yaz(self.proje_id, "cevap",
                         f"{cevaplayan} -> {row['gonderen']}: {cevap[:200]}",
                         ajan_ad=cevaplayan, gorev_id=row["gorev_id"])
        return {"id": mesaj_id, "cevap": cevap}

    def bekleyen_sorular(self, alici: str = None, *, soran: str = None) -> list:
        """Cevabi gelmemis, ajani DURDURAN sorular."""
        sorgu = ("SELECT m.*, g.no AS gorev_no FROM mesaj m "
                 "LEFT JOIN gorev g ON g.id = m.gorev_id "
                 "WHERE m.proje_id = ? AND m.mod = 'bekleyen' "
                 "AND m.cevaplandi IS NULL")
        degerler = [self.proje_id]
        if alici:
            sorgu += " AND m.alici = ?"
            degerler.append(alici)
        if soran:
            sorgu += " AND m.gonderen = ?"
            degerler.append(soran)
        sorgu += " ORDER BY m.olusturuldu, m.rowid"
        with self.db.baglanti() as conn:
            return [dict(r) for r in conn.execute(sorgu, degerler).fetchall()]

    def insan_bekleyenler(self) -> list:
        """Yalnizca INSANA yonelmis bekleyen sorular.

        `bekleyen_sorular()` her aliciyi dondurur; insanin eylem kuyrugu
        ise yalnizca ona dusen isi gostermelidir. Ayrilmadan once panel ve
        kabuk, bir ajana sorulmus soruyu insana gosteriyordu -- insan,
        liderin cevaplamasi gereken seyi cevapliyordu. Yanlis gosteren bir
        gosterge, gostergesizlikten kotudur.
        """
        return [m for m in self.bekleyen_sorular() if m["alici"] == "insan"]

    def ajana_bekleyenler(self) -> list:
        """Bir AJANA yonelmis, henuz teslim edilmemis sorular."""
        return [m for m in self.bekleyen_sorular() if m["alici"] != "insan"]

    def insana_yonlendir(self, mesaj_id: str, sebep: str) -> dict:
        """Ajanin cevaplayamadigi soruyu insana YUKSELTIR.

        Cevaplanamayan soru sessizce birakilamaz: soran ajan onu bekliyor
        ve cevap gelmezse sonsuza kadar duracak. Sebep GOVDEYE yazilir --
        insan, kendisine neden bu sorunun dustugunu bilmeli, yoksa
        baglamsiz bir soruya baglamsiz bir cevap verir.
        """
        sebep = (sebep or "").strip()
        if not sebep:
            raise PostaneHatasi(
                "Yukseltme sebebi zorunlu. Sebepsiz yukselen soru, insana "
                "neden kendisine dustugunu soylemez.")
        with self.db.baglanti() as conn:
            satir = conn.execute(
                "SELECT * FROM mesaj WHERE id = ? AND proje_id = ?",
                (mesaj_id, self.proje_id)).fetchone()
            if satir is None:
                raise PostaneHatasi(f"Mesaj bulunamadi: {mesaj_id}")
            if satir["cevaplandi"]:
                raise PostaneHatasi("Cevaplanmis soru yukseltilemez.")
            eski_alici = satir["alici"]
            if eski_alici == "insan":
                return dict(satir)
            govde = (satir["govde"] + chr(10) * 2
                     + f"[YUKSELDI -- '{eski_alici}' cevaplayamadi: {sebep}]")
            conn.execute("UPDATE mesaj SET alici = 'insan', govde = ? "
                         "WHERE id = ?", (govde, mesaj_id))
        self.db.olay_yaz(
            self.proje_id, "uyari",
            f"Soru insana yukseldi ('{eski_alici}' cevaplayamadi): {sebep}",
            ajan_ad=satir["gonderen"], gorev_id=satir["gorev_id"])
        return {"id": mesaj_id, "alici": "insan", "govde": govde,
                "eski_alici": eski_alici, "sebep": sebep}

    def cevaplar(self, soran: str, *, gorev_no=None) -> list:
        """Ajanin sordugu ve CEVAPLANMIS sorular -- devam turunda verilir."""
        sorgu = ("SELECT m.*, g.no AS gorev_no FROM mesaj m "
                 "LEFT JOIN gorev g ON g.id = m.gorev_id "
                 "WHERE m.proje_id = ? AND m.gonderen = ? "
                 "AND m.cevaplandi IS NOT NULL")
        degerler = [self.proje_id, soran]
        if gorev_no is not None:
            sorgu += " AND g.no = ?"
            degerler.append(int(gorev_no))
        sorgu += " ORDER BY m.olusturuldu, m.rowid"
        with self.db.baglanti() as conn:
            return [dict(r) for r in conn.execute(sorgu, degerler).fetchall()]

    # -- onaylar -----------------------------------------------------------

    def cevaplanan_onaylar(self, isteyen: str, *, gorev_no=None) -> list:
        """Ajanin istedigi ve CEVAPLANMIS onaylar -- devam turunda verilir.

        `cevaplar()`in onay tarafi. Bu ikisi ofisin iki ayri bekleme
        sebebidir (*"soru_sor -> BILGISI eksik, onay_iste -> YETKISI
        eksik"*) ve devam metni uzun sure yalnizca ilkini veriyordu.

        OLCULDU (22.09.2026, gercek tur): insan onayi verdi, ajan bir
        sonraki turda bunu HIC ogrenmedi ve eylemi tekrar denemedi.
        Yalnizca durduran bir kapi isi kalici olarak oldurur -- "onay"
        diye bir sey yoktur, yalnizca yasak vardir.

        Ayni desen bu projede defalarca cikti: iki paralel kavramdan
        biri baglanir, oteki unutulur.
        """
        sorgu = ("SELECT o.*, g.no AS gorev_no FROM onay o "
                 "LEFT JOIN gorev g ON g.id = o.gorev_id "
                 "WHERE o.proje_id = ? AND o.isteyen = ? "
                 "AND o.durum != 'bekliyor'")
        degerler = [self.proje_id, isteyen]
        if gorev_no is not None:
            sorgu += " AND g.no = ?"
            degerler.append(int(gorev_no))
        sorgu += " ORDER BY o.olusturuldu, o.rowid"
        with self.db.baglanti() as conn:
            return [dict(r) for r in conn.execute(sorgu, degerler).fetchall()]

    # -- KAPI TARAFI: imza, arama, tuketme ---------------------------------
    #
    # Bu uc parca TEK YERDE durur. Iki kapi var (tarayici vekili ve
    # CLI izin kancasi) ve ikisi de ayni soruyu soruyor: *"bu eylem
    # icin verilmis bir onay var mi?"* Ayri ayri yazsaydik biri
    # duzeltilir, oteki unutulurdu -- bu projede tam boyle alti hata
    # cikti.

    @staticmethod
    def imza(bulgu: dict) -> str:
        """Bir riskli eylemin turlar arasi SABIT kimligi.

        Icine yalniz DEGISMEYEN sey girer: sinif, arac ve eylemin
        insan okunur adi (dugme yazisi ya da arac adi).

        DISARIDA BIRAKILANLAR olculerek belirlendi: Playwright'in
        `ref`i her anlik goruntude yenilenir, ve sayfa adresi vekil o
        tur icinde henuz bir sonuc gormediyse bostur. Ikisi de imzaya
        girince onay ikinci turda TANINMIYORDU.
        """
        ham = "|".join((
            str(bulgu.get("sinif") or ""),
            str(bulgu.get("arac") or ""),
            _sadelestir(bulgu.get("element") or bulgu.get("hedef") or ""),
        ))
        return hashlib.sha1(ham.encode("utf-8")).hexdigest()[:16]

    def onay_ara(self, isteyen: str, imza: str, *, gorev_no=None) -> list:
        """Ayni imzali onaylar, en yenisi basta."""
        sorgu = ("SELECT o.*, g.no AS gorev_no FROM onay o "
                 "LEFT JOIN gorev g ON g.id = o.gorev_id "
                 "WHERE o.proje_id = ? AND o.isteyen = ? "
                 "AND o.ayrinti LIKE ?")
        degerler = [self.proje_id, isteyen, f"%IMZA:{imza}%"]
        if gorev_no is not None:
            sorgu += " AND g.no = ?"
            degerler.append(int(gorev_no))
        sorgu += " ORDER BY o.olusturuldu DESC, o.rowid DESC"
        with self.db.baglanti() as conn:
            return [dict(r) for r in conn.execute(sorgu, degerler).fetchall()]

    def onay_kullanildi_mi(self, onay_id: str) -> bool:
        with self.db.baglanti() as conn:
            return bool(conn.execute(
                "SELECT 1 FROM olay WHERE proje_id = ? AND tur = "
                "'onay_kullanildi' AND govde LIKE ?",
                (self.proje_id, onay_id + "%")).fetchone())

    def onay_kullan(self, onay_id: str, *, ajan_ad: str, ne: str,
                    gorev_id=None) -> None:
        """Onayi TUKETIR.

        Tuketmeseydik tek bir "evet" o eylem icin SUREKLI yetki
        olurdu: insan "bu urunu yayinla" der, ajan her urunu
        yayinlardi. Kapsami `is` olan onay bunun istisnasi ve o karar
        insanin acik tercihidir.
        """
        self.db.olay_yaz(self.proje_id, "onay_kullanildi",
                         f"{onay_id} | {ne}"[:400],
                         ajan_ad=ajan_ad, gorev_id=gorev_id)

    def onay_iste(self, isteyen: str, eylem: str, *, ayrinti: str = "",
                  risk: str = "orta", gorev_no=None) -> dict:
        eylem = (eylem or "").strip()
        if not eylem:
            raise PostaneHatasi("Onay istenen eylem bos olamaz.")
        if risk not in ("dusuk", "orta", "yuksek"):
            raise PostaneHatasi(f"Bilinmeyen risk: {risk}")
        gorev_id = None
        if gorev_no is not None:
            gorev_id = self.ofis.tahta.gorev(gorev_no)["id"]
        onay_id = uuid.uuid4().hex
        with self.db.baglanti() as conn:
            conn.execute(
                "INSERT INTO onay (id, proje_id, gorev_id, isteyen, eylem, "
                "ayrinti, risk, durum, cevap_notu, olusturuldu, cevaplandi) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'bekliyor', '', ?, NULL)",
                (onay_id, self.proje_id, gorev_id, isteyen, eylem,
                 ayrinti, risk, simdi()),
            )
        self.db.olay_yaz(self.proje_id, "onay_istendi",
                         f"{isteyen}: {eylem[:200]} (risk: {risk})",
                         ajan_ad=isteyen, gorev_id=gorev_id)
        return {"id": onay_id, "eylem": eylem, "risk": risk, "durum": "bekliyor"}

    def onay_cevapla(self, onay_id: str, *, onayla: bool, not_: str = "",
                     cevaplayan: str = "insan", kapsam: str = "eylem") -> dict:
        """Reddin gerekcesi zorunludur -- ajan neden olmadigini bilmeli.

        Gerekcesiz ret, ajanin ayni seyi baska bicimde tekrar denemesine
        yol acar; yasak olanin NE oldugunu ogrenmemistir.

        `kapsam`:
          * `eylem` (varsayilan) -- BIR KEZ gecer, sonra tukenir.
          * `is`    -- bu gorev boyunca ayni eylem bir daha sorulmaz.
          * `proje` -- BU PROJEDE HEP (06.10.2026, onay yorgunlugu E80):
            karttan KALICI izin yazilir (`izin.karttan_izin`; para, silme,
            sifre, masaustu asla). Izin Ayarlar'da gorunur ve kaldirilir.

        Varsayilan DAR olan. Genis kapsam insanin ACIK tercihidir;
        varsayilan yapsaydik bir "evet" sessizce surekli yetkiye
        donusurdu. Reddederken kapsam anlamsiz: ret her halde ogretir.
        """
        if kapsam not in ("eylem", "is", "proje"):
            raise PostaneHatasi(
                f"Bilinmeyen kapsam: {kapsam!r}. 'eylem', 'is' ya da 'proje'.")
        if not onayla and not (not_ or "").strip():
            raise PostaneHatasi(
                "Ret gerekcesi zorunlu. Gerekcesiz ret, ajanin ayni seyi "
                "baska bicimde tekrar denemesiyle sonuclanir."
            )
        with self.db.baglanti() as conn:
            row = conn.execute(
                "SELECT * FROM onay WHERE id = ? AND proje_id = ?",
                (onay_id, self.proje_id),
            ).fetchone()
            if not row:
                raise PostaneHatasi(f"Onay bulunamadi: {onay_id}")
            if row["durum"] != "bekliyor":
                raise PostaneHatasi(
                    f"Bu istek zaten '{row['durum']}'. Onay bir kez verilir."
                )
            durum = "onaylandi" if onayla else "reddedildi"
            if onayla and kapsam == "proje":
                # Once IZIN yazilir: verilemiyorsa kart da DEGISMEZ (yarim
                # kalan "onaylandi ama izin yok" durumu olmaz).
                from ofis import izin as _izin
                k = _izin.karttan_izin(dict(row))
                if not k["verilebilir"]:
                    raise PostaneHatasi("Bu projede hep izni verilemez: " + k["sebep"])
                try:
                    _izin.tanimla(
                        self.db, self.proje_id, desen=k["desen"], sinif=k["sinif"],
                        veren=cevaplayan, kaynak="insan",
                        gerekce=(not_ or "").strip()
                        or f"onay kartindan 'Bu projede hep': {row['eylem'][:80]}")
                except _izin.IzinHatasi as exc:
                    raise PostaneHatasi(str(exc))
            conn.execute(
                "UPDATE onay SET durum = ?, cevap_notu = ?, cevaplandi = ?, "
                "kapsam = ? WHERE id = ?",
                (durum, not_, simdi(), kapsam if onayla else "eylem",
                 onay_id),
            )
        # KAPSAM DA KAYDA GECER. Gostermeyen cikti, sessizce genisleyen
        # bir yetkiyi fark ettirmez.
        kapsam_notu = {"is": " [BU IS BOYUNCA]", "proje": " [BU PROJEDE HEP]"}.get(
            kapsam, "") if onayla else ""
        self.db.olay_yaz(
            self.proje_id, "onay_cevabi",
            f"{row['eylem'][:120]} -> {durum}{kapsam_notu}. {not_}".strip(),
            ajan_ad=cevaplayan, gorev_id=row["gorev_id"])
        return {"id": onay_id, "durum": durum, "not": not_,
                "kapsam": kapsam if onayla else "eylem"}

    def bekleyen_onaylar(self, isteyen: str = None) -> list:
        sorgu = ("SELECT o.*, g.no AS gorev_no FROM onay o "
                 "LEFT JOIN gorev g ON g.id = o.gorev_id "
                 "WHERE o.proje_id = ? AND o.durum = 'bekliyor'")
        degerler = [self.proje_id]
        if isteyen:
            sorgu += " AND o.isteyen = ?"
            degerler.append(isteyen)
        sorgu += " ORDER BY o.olusturuldu, o.rowid"
        with self.db.baglanti() as conn:
            return [dict(r) for r in conn.execute(sorgu, degerler).fetchall()]

    # -- turetilmis hal ----------------------------------------------------

    def bekliyor_mu(self, ajan_ad: str) -> dict:
        """Ajan bir seyi mi bekliyor? Panelin 'oda'sini bu belirler.

        Gorev durumu degismedigi icin (bkz. dosya basi) bu bilgi TURETILIR.
        Tek kaynak: soru ve onay tablolari.
        """
        sorular = self.bekleyen_sorular(soran=ajan_ad)
        onaylar = self.bekleyen_onaylar(isteyen=ajan_ad)
        # `kime`: soru KIME soruldu. Panel ofis gorunumunde soran ajani
        # sorulanin masasina YURUTUR -- hareket gercek bir konusmayi
        # gostersin diye. Bu alan olmadan ajan yalnizca "bekleme odasi"na
        # gidebilirdi ve "lidere mi sordu, sana mi" ayrimi ekranda
        # kaybolurdu. Onayin alicisi her zaman insandir.
        if sorular:
            return {"bekliyor": True, "tur": "soru",
                    "aciklama": sorular[0]["govde"][:300], "adet": len(sorular),
                    "kime": sorular[0].get("alici") or ""}
        if onaylar:
            return {"bekliyor": True, "tur": "onay",
                    "aciklama": onaylar[0]["eylem"][:300], "adet": len(onaylar),
                    "kime": "insan"}
        return {"bekliyor": False, "tur": "", "aciklama": "", "adet": 0,
                "kime": ""}
