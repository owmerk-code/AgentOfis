# -*- coding: utf-8 -*-
"""Bellek: uc ayri torba, tek torba degil.

* **Olgu bellegi** (bu dosya) -- ne dogru, VE NE ZAMANDAN NE ZAMANA KADAR.
* **Olay bellegi** (`db.olay`) -- ne oldu.
* **Yordam bellegi** (`kadro.ders` + skill dosyalari) -- nasil yapilir.

Neden cift-zamanli:

Bir olgunun DUNYADA ne zaman dogru oldugu ile BIZIM ne zaman ogrendigimiz
ayri seylerdir. "Iade suresi 14 gun" olgusu Mart'ta 30 gune ciktiysa, duz
bir bellek iki olguyu da esit dogrulukta getirir ve ajan yanlis olani
kullanir -- sessizce, kimse fark etmeden musteriye yanlis sure soylenir.

Cozum: her olgu `gecerli_baslangic` ve `gecerli_bitis` tasir. Yeni olgu ayni
konuya yazildiginda eskisi otomatik KAPANIR (`gecerli_bitis` dolar) ama
SILINMEZ. Boylece:

  - brifinge yalnizca gecerli olgular girer,
  - "eskiden ne kadardi" sorusu hala cevaplanabilir,
  - bir kararin hangi bilgiyle alindigi geriye donuk anlasilir.

Zep/Graphiti'nin zamansal testlerde 22 puan one gecmesinin sebebi bu; biz
ayni fikri SQLite uzerinde kendimiz tutuyoruz -- dis bagimlilik yok.
"""

from __future__ import annotations

import json
import re
import uuid

from .db import simdi



#: Bu sayinin ALTINDA hicbir secim yapilmaz -- hepsi brifinge girer.
#: Sebep olculdu: kucuk ofiste secim, kazanc getirmeden RISK ekler.
#: Eksik bilgi gurultuden PAHALIDIR: gereksiz olgu jeton yakar, eksik
#: olgu yanlis is urettirir (MAST'in %41,8'lik belirtim hata kumesi).
OLGU_SECIM_ESIGI = 40

#: Secim devreye girdiginde brifinge en fazla kac olgu konur.
AZAMI_OLGU = 40

#: Skorlamaya katilmayan, her metinde gecen kelimeler.
DURAK_KELIMELER = frozenset("""
ve veya ile icin gibi ama fakat ancak cunku yani hem her bir bu su o
olan olarak olsun olmali var yok daha cok az en de da mi mu ki ise
uzere gore kadar sonra once simdi yeni eski tum butun bazi kendi
""".split())


def _sadelestir(metin: str) -> str:
    """Turkce harfleri ASCII'ye indirger ve kucultur.

    Skorlama icin yeter: amac dilbilgisi degil ORTAK KELIME saymak.
    """
    cevrim = str.maketrans("abcdefghijklmnopqrstuvwxyz\u00e7\u011f\u0131\u0130\u00f6\u015f\u00fc"
                           "\u00c7\u011e\u00d6\u015e\u00dc",
                           "abcdefghijklmnopqrstuvwxyzcgiiosucgosu")
    return (metin or "").lower().translate(cevrim)


def _kelimeler(metin: str) -> set:
    temiz = "".join(c if c.isalnum() else " " for c in _sadelestir(metin))
    return {k for k in temiz.split()
            if len(k) >= 4 and k not in DURAK_KELIMELER}


def _ortak(a: set, b: set) -> int:
    """Kac kelime ortak. ONEK eslesmesi sayilir.

    Turkce eklemeli bir dil: "iade" ile "iadesi", "kargo" ile "kargonun"
    ayni seyi soyler. Tam eslesme arasak, gereken olgu ELENIRDI --
    ve eksik bilgi gurultuden pahalidir.
    """
    sayi = 0
    for x in a:
        for y in b:
            if x == y or x.startswith(y[:4]) or y.startswith(x[:4]):
                sayi += 1
                break
    return sayi


# ---------------------------------------------------------------------------
# BILGI, BAG, KURAL (24.09.2026)
# ---------------------------------------------------------------------------
#
# OLCULDU: gercek ofiste OLGU SAYISI SIFIRDI. `olgu_yaz`i uretimde cagiran
# TEK BIR YOL yoktu -- MCP araci yok, kabuk komutu yok, lider yolu yok.
# Hafiza isabeti %100 olculmustu, ama SENTETIK veriyle; gercek kullanimda
# olgu katmani hic beslenmiyordu. Sistem saglikli gorunurken yanlis
# calisiyordu: brifingin K2'si her turda "gecerli olgular" basligini hic
# basmadi ve bunu kimse fark etmedi.

#: `[[konu]]` bagi -- bir olgu baska bir konuya isaret eder. Brifing
#: secimi bagi BIR ADIM izler (bkz. `ilgili_olgular`).
BAG_DESENI = re.compile(r"\[\[([^\[\]\n]{1,80})\]\]")

#: Bag ile secimin USTUNE eklenebilecek en fazla olgu. Bag bir genisletme
#: kapisidir; sinirsiz olsa bir zincir butun hafizayi brifinge cekerdi.
AZAMI_BAG_OLGU = 8

#: Bilgi bir OLGUDUR, rapor degil. Uzun metin brifingi sisirir ve her
#: turda yeniden odenir.
AZAMI_KONU_HARF = 80
AZAMI_BILGI_HARF = 600

#: Insanin yazdigi bilginin kaynagi. Ajan bunu SESSIZCE devremez.
KAYNAK_INSAN = "insan"

#: Ajana donen ret (riskli.koruma_asma eslesince). Neden + care birlikte.
HAFIZA_REDDI = (
    "HAFIZA KAPISI: bu yazi ofisin bir korumasini (onay, izin, kanca, kapi) "
    "asmayi ya da etrafindan dolanmayi anlatiyor. Ajan bunu hafizaya YAZAMAZ: "
    "hafiza her brifinge girer ve boyle bir yol butun ofise ogretilmis olur. "
    "Patron bunu gordu. Bir koruma isini gercekten engelliyorsa `soru_sor` "
    "ile patrona sor; korumayi asma.")

#: Kurallar HER brifinge girer; toplam bunu asarsa panel uyarir.
KURAL_UYARI_HARF = 1500
AZAMI_KURAL_HARF = 400

#: Bir dersin kural ADAYI olmasi icin kac kez tekrarlanmis olmasi gerekir.
#: Birinci ret siradandir, ikincisi bir DESENDIR (ret sayacinin ve kapi
#: modeli esiginin ayni mantigi).
KURAL_ADAY_TEKRAR = 2


def konu_anahtari(konu: str) -> str:
    """Iki konu adi ayni konu mu? Harf buyuklugu ve Turkce harf farki
    yeni bir konu ACMAZ: "Iade suresi" ile "iade süresi" ayri iki konu
    olsaydi ikisi de gecerli kalir ve brifinge celisen iki bilgi girerdi
    -- cift-zamanli bellegin onlemek icin var oldugu hata."""
    return " ".join(_sadelestir(konu).split())


def baglar(icerik: str) -> list:
    """Icerikteki `[[konu]]` baglari, sirayla ve tekrarsiz."""
    goren, sonuc = set(), []
    for m in BAG_DESENI.finditer(icerik or ""):
        k = " ".join(m.group(1).split())
        a = konu_anahtari(k)
        if k and a not in goren:
            goren.add(a)
            sonuc.append(k)
    return sonuc


class BellekHatasi(RuntimeError):
    pass


class Bellek:
    def __init__(self, db, proje_id: str) -> None:
        self.db = db
        self.proje_id = proje_id

    # -- olgular -----------------------------------------------------------

    def olgu_yaz(self, konu: str, icerik: str, *, kaynak: str = "",
                 gecerli_baslangic: str = None) -> dict:
        """Yeni olgu yazar ve AYNI KONUDAKI gecerli olguyu kapatir.

        Kapatma otomatiktir cunku elle yapilirsa unutulur; unutulan eski olgu
        da brifinge girip yeni olguyla celisir. Ajan iki celiskili bilgiyi
        gorunce hangisine guvenecegini bilemez ve genelde yanlis olani secer.
        """
        konu = (konu or "").strip()
        icerik = (icerik or "").strip()
        if not konu or not icerik:
            raise BellekHatasi("Olgunun konusu ve icerigi bos olamaz.")

        an = simdi()
        baslangic = gecerli_baslangic or an
        yeni_id = uuid.uuid4().hex

        with self.db.baglanti() as conn:
            eski = conn.execute(
                "SELECT id, icerik FROM olgu WHERE proje_id = ? AND konu = ? "
                "AND gecerli_bitis IS NULL",
                (self.proje_id, konu),
            ).fetchall()

            conn.execute(
                "INSERT INTO olgu (id, proje_id, konu, icerik, kaynak, "
                "gecerli_baslangic, gecerli_bitis, kaydedildi, gecersiz_kilan) "
                "VALUES (?, ?, ?, ?, ?, ?, NULL, ?, NULL)",
                (yeni_id, self.proje_id, konu, icerik, kaynak, baslangic, an),
            )

            for row in eski:
                conn.execute(
                    "UPDATE olgu SET gecerli_bitis = ?, gecersiz_kilan = ? WHERE id = ?",
                    (baslangic, yeni_id, row["id"]),
                )

        if eski:
            self.db.olay_yaz(
                self.proje_id, "olgu_guncellendi",
                f"{konu}: '{eski[0]['icerik']}' -> '{icerik}'",
            )
        else:
            self.db.olay_yaz(self.proje_id, "olgu", f"{konu}: {icerik}")
        return {"id": yeni_id, "konu": konu, "icerik": icerik}

    def gecerli_olgular(self, konular=None) -> list:
        """Su an dogru olan olgular. Brifing yalnizca bunlari gorur."""
        with self.db.baglanti() as conn:
            if konular:
                isaret = ",".join("?" for _ in konular)
                rows = conn.execute(
                    f"SELECT konu, icerik, kaynak, gecerli_baslangic FROM olgu "
                    f"WHERE proje_id = ? AND gecerli_bitis IS NULL AND konu IN ({isaret}) "
                    f"ORDER BY konu",
                    (self.proje_id, *konular),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT konu, icerik, kaynak, gecerli_baslangic FROM olgu "
                    "WHERE proje_id = ? AND gecerli_bitis IS NULL ORDER BY konu",
                    (self.proje_id,),
                ).fetchall()
        return [dict(r) for r in rows]


    def ilgili_olgular(self, gorev_metni: str, *, esik: int = None,
                       azami: int = None) -> dict:
        """Goreve gore secilmis olgular.

        Donen sozluk: `secilen` · `elenen` (sayi) · `secim_yapildi`.

        Karar: **esigin altinda HICBIR SEY kesilmez.** Kucuk ofiste secim
        kazanc getirmeden risk ekler; gereken bir olguyu elemek, ajanin
        bilmedigi bir seyle calismasi demektir.

        Esik asilinca goreve gore siralanir. Ama secim yapildigi
        BRIFINGDE SOYLENIR (bkz. brifing.k2_kunye) -- ajan gorusunun
        kismi oldugunu bilmeli ve gerekirse `durum` araciyla tamamini
        sorabilmeli. Gizli eksiltme, uydurmanin kapisini acar.
        """
        esik = OLGU_SECIM_ESIGI if esik is None else esik
        azami = AZAMI_OLGU if azami is None else azami
        hepsi = self.gecerli_olgular()
        if len(hepsi) <= esik:
            return {"secilen": hepsi, "elenen": 0, "secim_yapildi": False}

        anahtar = _kelimeler(gorev_metni)
        puanli = []
        for o in hepsi:
            kelimeler = _kelimeler(o["konu"] + " " + o["icerik"])
            puanli.append((_ortak(kelimeler, anahtar), o))
        # Yuksek puan once; esitlikte konu adina gore kararli sirala ki
        # ayni girdi ayni ciktiyi versin.
        puanli.sort(key=lambda p: (-p[0], p[1]["konu"]))

        # Sifir puanli olgu -- goreve deyen tek kelimesi bile yok -- KESILIR.
        # Bu guvenli, cunku KALICI kurallar olgu degil PROJE alanidir
        # (amac · basari_olcutu · kapsam_disi · kisitlar · sozluk) ve
        # K2'de kosulsuz duruyor. Dogrulandi.
        ilgili = [o for puan, o in puanli if puan > 0][:azami]
        if ilgili:
            secilen = ilgili
        else:
            # Hicbiri deymiyorsa NE ILGILI OLDUGUNU BILMIYORUZ demektir.
            # O zaman bilmedigimizi biliyormus gibi davranmayiz: en
            # yakinlari koyariz ve brifing secim yapildigini soyler.
            secilen = [o for puan, o in puanli[:azami]]

        # BAG BIR ADIM IZLENIR. Olculmus kayip (19.09.2026): gereken olgu
        # gorevle HIC ortak kelime tasimiyorsa eleniyordu ("lojistik
        # anlasmasi" vs "kargo ekrani"). Kelime bunu cozemez; ama bilgiyi
        # yazan kisi iki konunun iliskili oldugunu BILIYORDU. `[[konu]]`
        # o bilgiyi tasir. Tek adim ve sinirli: zincir izlenseydi bir bag
        # agi butun hafizayi brifinge cekerdi.
        dizin = {konu_anahtari(o["konu"]): o for o in hepsi}
        secili = {konu_anahtari(o["konu"]) for o in secilen}
        eklenen = []
        for o in list(secilen):
            for b in baglar(o["icerik"]):
                a = konu_anahtari(b)
                if (a in dizin and a not in secili
                        and len(eklenen) < AZAMI_BAG_OLGU):
                    secili.add(a)
                    eklenen.append(dict(dizin[a], bag=o["konu"]))
        secilen = secilen + eklenen
        return {"secilen": secilen, "elenen": len(hepsi) - len(secilen),
                "secim_yapildi": True, "bag_ile": len(eklenen)}

    # -- bilgi: olgu katmaninin GIRIS kapisi -------------------------------

    def _konu_bul(self, konu: str) -> str:
        """Ayni konu daha once yazildiysa ONUN yazilisi doner."""
        a = konu_anahtari(konu)
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT DISTINCT konu FROM olgu WHERE proje_id = ?",
                (self.proje_id,)).fetchall()
        for r in rows:
            if konu_anahtari(r["konu"]) == a:
                return r["konu"]
        return ""

    def bilgi_ekle(self, konu: str, icerik: str, *, yazan: str,
                   gorev_no: int = None) -> dict:
        """Olgu katmaninin TEK giris kapisi: ajan, panel, kabuk.

        Uc kural, ucu de bir hata sinifina karsi:

        * **Insanin yazdigini ajan SESSIZCE devremez.** Bir ajan ayni
          konuya farkli bir sey yazarsa ret alir ve `soru_sor`a
          yonlendirilir. Devirebilseydi yanlis bir cikarim, insanin
          soyledigini brifinglerden sessizce silerdi -- ve eski olgu
          gecmiste dursa bile kimse ona bakmaz.
        * **Ayni icerik yeni surum ACMAZ.** Iki ajan ayni seyi yazarsa
          gecmis anlamsiz surumlerle dolar ve "ne zaman degisti"
          sorusunun cevabi gurultuye gomulur.
        * **Konu adi normallesir** (`konu_anahtari`): "Iade suresi" ile
          "iade süresi" ayni konudur.
        """
        konu = " ".join((konu or "").split())
        icerik = (icerik or "").strip()
        if not konu or not icerik:
            raise BellekHatasi("Bilginin konusu ve icerigi bos olamaz.")
        if len(konu) > AZAMI_KONU_HARF:
            raise BellekHatasi(
                f"Konu en fazla {AZAMI_KONU_HARF} harf olabilir -- konu bir "
                "ad, cumle degil (ornek: 'iade suresi').")
        if len(icerik) > AZAMI_BILGI_HARF:
            raise BellekHatasi(
                f"Bilgi en fazla {AZAMI_BILGI_HARF} harf olabilir. Bilgi bir "
                "OLGUDUR, rapor degil; her brifinge girer ve her turda "
                "yeniden odenir. Uzun metin icin dosya yaz ve buraya yolunu "
                "koy.")
        yazan = (yazan or "").strip()
        if not yazan:
            raise BellekHatasi("Bilgiyi kimin yazdigi bos olamaz.")
        if yazan != KAYNAK_INSAN:
            self.koruma_kapisi(yazan, "bilgi", f"{konu}: {icerik}")
        konu = self._konu_bul(konu) or konu
        simdiki = [o for o in self.gecerli_olgular([konu])]
        mevcut = simdiki[0] if simdiki else None
        if mevcut and mevcut["icerik"].strip() == icerik:
            return {"konu": konu, "icerik": icerik, "durum": "ayni",
                    "kaynak": mevcut["kaynak"]}
        if (yazan != KAYNAK_INSAN and mevcut
                and str(mevcut["kaynak"] or "").startswith(KAYNAK_INSAN)):
            raise BellekHatasi(
                f"'{konu}' bilgisini INSAN yazdi ({mevcut['icerik'][:120]}). "
                "Ajan insanin yazdigi bilgiyi sessizce devremez. Farkli bir "
                "sey gorduysen `soru_sor` ile insana sor; o degistirir.")
        if yazan == KAYNAK_INSAN:
            kaynak = KAYNAK_INSAN
        else:
            kaynak = f"ajan:{yazan}" + (f" #{gorev_no}" if gorev_no else "")
        r = self.olgu_yaz(konu, icerik, kaynak=kaynak)
        r["durum"] = "guncellendi" if mevcut else "yeni"
        r["kaynak"] = kaynak
        return r

    def koruma_kapisi(self, yazan: str, tur: str, metin: str) -> None:
        """Ajanin/liderin hafiza yazisi korumayi asmayi anlatiyorsa DURUR.

        Sessiz ret degil: `hafiza_reddi` olayi takim sohbetine ve masaustu
        bildirimine duser -- bir ajanin korumayi asmaya calistigini
        patron BILMELI (rakipte lider bunu yazdi ve kimse gormedi).
        """
        from .riskli import koruma_asma
        bulunan = koruma_asma(metin)
        if not bulunan:
            return
        self.db.olay_yaz(
            self.proje_id, "hafiza_reddi",
            f"{yazan} hafizaya {tur} yazmak istedi; ofis DURDURDU (korumayi "
            f"asmayi anlatiyor: '{bulunan}'). Yazi: {' '.join(metin.split())[:300]}",
            ajan_ad=yazan)
        raise BellekHatasi(HAFIZA_REDDI)

    # -- kurallar: HER isde gecerli, INSAN onayli --------------------------

    def kurallar(self, *, hepsi: bool = False) -> list:
        """Gecerli kurallar (eklenme sirasiyla). `hepsi`: kaldirilanlar da."""
        kosul = "" if hepsi else " AND kaldirildi IS NULL"
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT * FROM kural WHERE proje_id = ?" + kosul
                + " ORDER BY olusturuldu, rowid", (self.proje_id,)).fetchall()
        return [dict(r) for r in rows]

    def kural_ekle(self, metin: str, gerekce: str, *,
                   veren: str = KAYNAK_INSAN, kaynak_tur: str = "insan",
                   kaynak: str = "") -> dict:
        """Kural HER brifinge girer -- yani bir politika karari ve her
        turun jetonundan odenir.

        YALNIZ INSANDAN gelir. Lider ya da ajan kural koyabilseydi
        kendi urettigi bir cikarimi butun ofise dayatirdi; yetki
        insandan gelir, dagitim liderden (klasor ve kadro kurallariyla
        ayni ilke). Gerekce ZORUNLU ve karar gunlugune yazilir.
        """
        metin = " ".join((metin or "").split())
        gerekce = (gerekce or "").strip()
        if veren != KAYNAK_INSAN:
            raise BellekHatasi(
                "Kural yalniz INSANDAN gelir. Ajan ya da lider bir kurali "
                "ONEREBILIR ama koyamaz: kural her ajanin her brifingine "
                "girer ve bu bir politika kararidir.")
        if not metin:
            raise BellekHatasi("Bos kural yazilamaz.")
        if len(metin) > AZAMI_KURAL_HARF:
            raise BellekHatasi(
                f"Kural en fazla {AZAMI_KURAL_HARF} harf olabilir; HER "
                "brifinge girer.")
        if not gerekce:
            raise BellekHatasi(
                "Gerekce zorunlu. Kural her ise girer; neden konuldugu "
                "bilinmezse kaldirilmasi gereken gun de bilinmez.")
        a = konu_anahtari(metin)
        if any(konu_anahtari(k["metin"]) == a for k in self.kurallar()):
            raise BellekHatasi("Bu kural zaten gecerli.")
        kid = uuid.uuid4().hex
        with self.db.baglanti() as conn:
            conn.execute(
                "INSERT INTO kural (id, proje_id, metin, kaynak_tur, kaynak,"
                " gerekce, veren, olusturuldu) VALUES (?,?,?,?,?,?,?,?)",
                (kid, self.proje_id, metin, kaynak_tur, str(kaynak or ""),
                 gerekce, veren, simdi()))
        self.karar_yaz(f"Kural eklendi: {metin}", gerekce, veren,
                       tur="kapsam")
        self.db.olay_yaz(self.proje_id, "kural", f"eklendi: {metin}")
        return {"id": kid, "metin": metin, "kaynak_tur": kaynak_tur}

    def olgudan_kural(self, konu: str, gerekce: str, *,
                      veren: str = KAYNAK_INSAN) -> dict:
        """Gecerli bir bilgiyi KURALA yukseltir.

        Olgu goreve gore SECILIR ve gorevle ortak kelimesi yoksa elenir;
        kural her ise KOSULSUZ girer. Yukseltmenin anlami tam budur: bu
        bilgi "ilgiliyse" degil "her zaman" bilinmeli.
        """
        k = self._konu_bul(konu)
        liste = self.gecerli_olgular([k]) if k else []
        if not liste:
            raise BellekHatasi(f"Gecerli bir '{konu}' bilgisi yok.")
        olgu = liste[0]
        return self.kural_ekle(f"{olgu['konu']}: {olgu['icerik']}", gerekce,
                               veren=veren, kaynak_tur="olgu",
                               kaynak=olgu["konu"])

    def _kimlik_coz(self, tablo: str, onek: str) -> str:
        """Kisa kimlik (liste 8 hane gosterir) BENZERSIZSE kabul edilir.

        Benzersiz degilse REDDEDILIR: iki kaydin ilkini secmek, insanin
        kastetmedigi bir kurali kaldirmak olurdu.
        """
        onek = (onek or "").strip()
        if not onek:
            raise BellekHatasi("Kimlik bos.")
        with self.db.baglanti() as conn:
            rows = conn.execute(
                f"SELECT id FROM {tablo} WHERE proje_id = ? AND id LIKE ?",
                (self.proje_id, onek.replace("%", "") + "%")).fetchall()
        if len(rows) > 1:
            raise BellekHatasi(f"'{onek}' birden cok kayda uyuyor; daha uzun yaz.")
        return rows[0]["id"] if rows else onek

    def dersten_kural(self, ders_id: str, gerekce: str, *,
                      veren: str = KAYNAK_INSAN) -> dict:
        """Bir ajanin TEKRARLAYAN dersini butun ofisin kuralina yukseltir.

        Ders kisiye ozeldir (o ajanin brifingine girer). Ayni hata tekrar
        ediyorsa -- ya da baska ajanlar da ayni tuzaga dusebilecekse --
        insan onu herkese acar.
        """
        ders_id = self._kimlik_coz("ders", ders_id)
        with self.db.baglanti() as conn:
            d = conn.execute("SELECT * FROM ders WHERE id = ? AND proje_id = ?",
                             (ders_id, self.proje_id)).fetchone()
        if not d:
            raise BellekHatasi(f"Ders bulunamadi: {ders_id}")
        return self.kural_ekle(" ".join(d["ders"].split()), gerekce, veren=veren,
                               kaynak_tur="ders", kaynak=d["id"])

    def kural_kaldir(self, kural_id: str, sebep: str, *,
                     veren: str = KAYNAK_INSAN) -> dict:
        """Kural SILINMEZ, kaldirilir: ne zaman, neden -- gecmis okunur."""
        sebep = (sebep or "").strip()
        if veren != KAYNAK_INSAN:
            raise BellekHatasi("Kurali yalniz insan kaldirabilir.")
        if not sebep:
            raise BellekHatasi("Kaldirma sebebi zorunlu.")
        kural_id = self._kimlik_coz("kural", kural_id)
        with self.db.baglanti() as conn:
            k = conn.execute(
                "SELECT * FROM kural WHERE id = ? AND proje_id = ? AND "
                "kaldirildi IS NULL", (kural_id, self.proje_id)).fetchone()
            if not k:
                raise BellekHatasi(f"Gecerli bir kural bulunamadi: {kural_id}")
            conn.execute("UPDATE kural SET kaldirildi = ?, kaldirma_sebebi = ?"
                         " WHERE id = ?", (simdi(), sebep, kural_id))
        self.karar_yaz(f"Kural kaldirildi: {k['metin']}", sebep, veren,
                       tur="kapsam")
        self.db.olay_yaz(self.proje_id, "kural", f"kaldirildi: {k['metin']}")
        return {"id": kural_id, "metin": k["metin"]}

    def kural_adaylari(self) -> list:
        """Kurala yukseltilmeye ADAY dersler -- OLCULEN bir sinyal.

        Tekrari `KURAL_ADAY_TEKRAR`a ulasan ders: ayni ajan ayni hatayi
        yapmaya devam ediyor. Model tahmini degil sayac; sayacin degeri
        yalnizca gercek deseni saymasindadir. Karari insan verir.
        """
        gecerli = {konu_anahtari(k["metin"]) for k in self.kurallar()}
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT id, ajan_ad, ders, tekrar, guncellendi FROM ders "
                "WHERE proje_id = ? AND tekrar >= ? "
                "ORDER BY tekrar DESC, guncellendi DESC",
                (self.proje_id, KURAL_ADAY_TEKRAR)).fetchall()
        return [dict(r) for r in rows
                if konu_anahtari(r["ders"]) not in gecerli]

    def kural_maliyeti(self) -> dict:
        """Kurallarin her brifinge ekledigi yuk -- gorunmeyen maliyet,
        maliyet degildir."""
        k = self.kurallar()
        harf = sum(len(x["metin"]) + 4 for x in k)
        return {"adet": len(k), "harf": harf, "jeton_yaklasik": harf // 4,
                "uyari": harf > KURAL_UYARI_HARF}

    def konu_gecmisi(self, konu: str) -> list:
        """Bir konunun tum gecmisi -- 'eskiden ne kadardi' sorusu icin."""
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT icerik, kaynak, gecerli_baslangic, gecerli_bitis, kaydedildi "
                "FROM olgu WHERE proje_id = ? AND konu = ? ORDER BY gecerli_baslangic DESC",
                (self.proje_id, konu),
            ).fetchall()
        return [dict(r) for r in rows]

    # -- kararlar ----------------------------------------------------------

    def karar_yaz(self, karar: str, gerekce: str, veren: str, *,
                  tur: str = "genel", gorev_id: str = None,
                  etkilenen_yollar=None, denetle: bool = False) -> dict:
        """Gerekce ZORUNLUDUR.

        Gerekcesiz karar, alti ay sonra 'bunu neden boyle yapmistik' sorusuna
        cevap vermez ve ekip ayni tartismayi bastan yapar. Fan-out karari da
        buraya yazilir: lider bolerse de bolmezse de nedenini birakir.
        """
        karar = (karar or "").strip()
        gerekce = (gerekce or "").strip()
        if not karar:
            raise BellekHatasi("Bos karar yazilamaz.")
        if not gerekce:
            raise BellekHatasi(
                "Gerekce zorunlu. Gerekcesiz karar, sonradan sorgulanamaz "
                "ve ekip ayni tartismayi bastan yapar."
            )
        # `denetle`: metni MODEL yazdiysa (ajanin karar_yaz araci). Ofisin
        # kendi kararlari ve patron sozunu alintilayanlar denetlenmez.
        if denetle and veren != KAYNAK_INSAN:
            self.koruma_kapisi(veren, "karar", f"{karar} -- {gerekce}")
        karar_id = uuid.uuid4().hex
        with self.db.baglanti() as conn:
            conn.execute(
                "INSERT INTO karar (id, proje_id, gorev_id, tur, karar, gerekce, "
                "veren, etkilenen_yollar, olusturuldu) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (karar_id, self.proje_id, gorev_id, tur, karar, gerekce, veren,
                 json.dumps(etkilenen_yollar or [], ensure_ascii=False), simdi()),
            )
        self.db.olay_yaz(self.proje_id, "karar", f"{veren}: {karar}",
                         ajan_ad=veren, gorev_id=gorev_id)
        return {"id": karar_id, "karar": karar, "gerekce": gerekce}

    def son_kararlar(self, adet: int = 10) -> list:
        """Brifingin 3. katmani buradan beslenir -- her dagitimda TAZE uretilir.

        Elle yazilan durum ozeti bayatlar; bu sorgu bayatlamaz.

        Siralama `rowid` ile BERABERLIK BOZAR. Zaman damgasi saniye
        cozunurluklu (db.simdi); ayni saniyeye dusen iki karar yalnizca
        zamana gore siralandiginda EKLENME sirasiyla, yani en eskisi ustte
        gelir. Brifing bu listeyi "en yenisi ustte" ve "baglayicidir" diye
        sunar -- yani devrilmis bir karar, gecerliymis gibi okunur. Olculdu:
        ayni saniyede yazilan uc karar ters sirada dondu.
        """
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT karar, gerekce, veren, tur, olusturuldu FROM karar "
                "WHERE proje_id = ? ORDER BY olusturuldu DESC, rowid DESC LIMIT ?",
                (self.proje_id, adet),
            ).fetchall()
        return [dict(r) for r in rows]

    # -- uyanis ozeti ------------------------------------------------------

    def uyanis_ozeti(self, ajan_ad: str, son_gorulen_olay_id: int) -> list:
        """Devam eden oturumun baglami ESKIDIR.

        Ajan uzun bir isin ortasinda kaldiysa, o calisirken dunya degismis
        olabilir: baska bir ajan karar almis, gorev iptal olmus, olgu
        guncellenmis olabilir. Devam etmeden once bunlari gormezse, gecersiz
        bir varsayimla saatlerce emin adimlarla yanlis is uretir.
        """
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT id, ajan_ad, tur, govde, olusturuldu FROM olay "
                "WHERE proje_id = ? AND id > ? AND ajan_ad != ? "
                "AND tur IN ('karar', 'olgu', 'olgu_guncellendi', 'kural', "
                "'kapandi', 'iptal', 'ret') "
                "ORDER BY id",
                (self.proje_id, son_gorulen_olay_id, ajan_ad),
            ).fetchall()
        return [dict(r) for r in rows]

    def son_olay_id(self) -> int:
        with self.db.baglanti() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(id), 0) AS n FROM olay WHERE proje_id = ?",
                (self.proje_id,),
            ).fetchone()
        return int(row["n"])
