# -*- coding: utf-8 -*-
"""EKIP ONERISI -- lider ONERIR, insan ONAYLAR, ofis ISE ALIR.

Kullanicinin sorusu suydu: *"konusarak baslarsam lider anlayip takimi
kurma onerisi verecek mi?"*

Bugune kadar cevap hayirdi. `konus` uc yol taniyordu -- `cevap`,
`kendi`, `dagit` -- ve `dagit` **var olan kadroyu varsayiyordu**. Kadroda
gereken rol yoksa lider ya yanlis ajana veriyor ya is yarim kaliyordu.
Bu, olctugumuz bir hata sinifinin aynisi: lider **goremedigi bir
gerceğe gore** plan yapiyor (ilk gercek iste yazma alanini var olmayan
`calisma/demir` diye yazmisti).

Rakipte de yok: rehberli turlari `1 Sirket kurulumu -> 2 Calisan
tasarimi -> 3 Gorev & plan`. Takimi insan kuruyor, lider ancak 3.
adimda giriyor.

## Uc kural

1. **Lider ONERIR, insan ONAYLAR.** Kadro kurmak bir YETKI
   GENISLETMESIDIR; lider senin limitini harcayacak bir kadroyu kendi
   kuramaz. Ayni kural klasorde de var: *yetki insandan gelir, dagitim
   liderden.*

2. **UYDURMAZ.** Yalniz `roller.ROLLER`'deki rollerden ve
   `musait_motorlar()`un GERCEKTEN gordugu motorlardan secer. Kutuphane
   olmadan "oneri" zaten uydurma olurdu -- bu yuzden once kutuphane
   yazildi.

3. **Oneri bir KARARDIR** ve gerekcesiyle karar gunlugune yazilir.
   "Bu ajan neden ise alinmis" sorusu alti ay sonra da cevaplanmali.
   Ret de bir karardir ve SEBEBI zorunludur -- gerekcesiz ret, liderin
   ayni oneriyi baska bicimde tekrar getirmesi demektir.

## Kapi REDDEDER ve lidere SEBEBINI soyler

Plan kapisinin aynisi: sessizce duzeltmek, liderin yanlis ogrenmesidir.
**Ret ogretir.**
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from . import roller
from .db import simdi
from .kadro import KadroHatasi
from .motor import motor_ac, musait_motorlar
from .motor.tip import MotorHatasi
from .roller import RolHatasi

#: Bir oneride en fazla kac ajan. Sinir keyfi degil: coklu ajan ~15 kat
#: jeton yakar (Yasa 2) ve kalabalik bir kadro, bos duran koltuk
#: demektir. Lider daha fazlasina ihtiyac duyuyorsa ikinci bir oneri
#: getirir -- ve o da ayrica onaylanir.
AZAMI_UYE = 6

#: Liderin cevabindan JSON ayiklama. Serbest metin ayristirmak modelin o
#: gunku uslubuna bagimli olur; bicim zorunlu olunca ya gelir ya gelmez,
#: ikisi de kayittir.
from .orkestra import Orkestra, _json_ayikla  # noqa: E402


class EkipHatasi(RuntimeError):
    pass


class Ekip:
    def __init__(self, ofis, *, motor_fabrikasi=motor_ac) -> None:
        self.ofis = ofis
        self.db = ofis.db
        self.proje_id = ofis.proje_id
        self.motor_fabrikasi = motor_fabrikasi
        # KENDI Orkestra'sini kurar, ofisinkini KULLANMAZ.
        #
        # Ilk surumde `self.orkestra._lideri_kostur(...)` cagiriyordu
        # ve verilen `motor_fabrikasi` HICBIR YERE ULASMIYORDU -- ofisin
        # orkestrasi kendi (varsayilan) fabrikasiyla kosuyordu.
        # "Sessizce yok sayilan ayar, ayar degildir": ayni hata bu
        # projede bir kez daha cikmisti (orkestra fabrikayi koltuga
        # gecirmiyordu) ve yine bir test yakaladi.
        self.orkestra = Orkestra(ofis, motor_fabrikasi=motor_fabrikasi)

    # -- 1. liderin gordugu istek ------------------------------------------

    def oneri_metni(self, hedef: str, kanat_id, hata: str = "") -> str:
        """Lidere verilen kadro istegi.

        Kutuphane ve MUSAIT motorlar ACIKCA verilir. Vermeseydik lider
        tahmin ederdi -- ve tahmin, bu projede defalarca var olmayan bir
        seye gore plan uretti.
        """
        mevcut = self.ofis.kadro.liste()
        satir = [
            "# ISTEK",
            "",
            hedef,
            "",
            "---",
            "",
            "# SEN",
            "",
            "Bu ofisin lidersin. Patron yukaridaki isi istiyor ve mevcut",
            "kadronun yetmedigini dusunuyorsun. **Kadro ONERECEKSIN.**",
            "",
            "Kadro kurmak patronun yetkisidir: sen onerirsin, O onaylar.",
            "Onerdigin her ajan onun limitinden harcayacak.",
            "",
            "# SU ANKI KADRO",
            "",
        ]
        if mevcut:
            for a in mevcut:
                etiket = "LIDER" if a["lider_mi"] else a["tur"]
                satir.append(
                    f"- {a['ad']} · {a['meslek']} · {etiket} · "
                    f"{a['motor']}/{a['model'] or '(model yok)'}")
        else:
            satir.append("- (kadro bos)")

        satir += [
            "",
            "**Zaten kadroda olan bir rolu TEKRAR onerme.** Var olan ajan",
            "o isi yapabiliyorsa yeni ajan acmak bos koltuk uretir.",
            "",
            "# ROL KUTUPHANESI -- yalniz BURADAN secebilirsin",
            "",
        ]
        for kat in roller.kategoriler():
            satir.append(f"**{kat}**")
            for r in roller.ROLLER.values():
                if r.kategori != kat:
                    continue
                ek = "  ! " + r.uyari.split(".")[0] if r.uyari else ""
                satir.append(f"- `{r.ad}` — {r.ozet}{ek}")
            satir.append("")

        musait = [m for m, var in musait_motorlar().items() if var and m != "sahte"]
        satir += [
            "# MUSAIT MOTORLAR -- yalniz BUNLARI kullanabilirsin",
            "",
            f"{', '.join(musait) if musait else '(hicbiri kurulu degil)'}",
            "",
            "Model yazma: rolun kademesi motora gore dogru modeli secer.",
            "Farkli bir model istiyorsan gerekcesini `gerekce` alanina yaz.",
            "",
            "# KARARIN",
            "",
            f"En fazla {AZAMI_UYE} ajan oner. Her ajan icin NEDEN gerektigini",
            "yaz -- gerekcesiz bir ajan, bos duran bir koltuktur.",
            "",
            "Ad kurallari: kucuk harf, Turkce karakter yok, tek kelime",
            "(ornek: selin, kerem, aras). Kadroda olan bir adi TEKRAR",
            "kullanamazsin -- ad geri donmez.",
            "",
            "# CIKTI BICIMI",
            "",
            "Yalnizca su JSON'u ver, baska hicbir sey yazma:",
            "",
            "```json",
            "{",
            '  "gerekce": "kadro NICIN boyle -- bir iki cumle",',
            '  "uyeler": [',
            '    {"ad": "selin", "rol": "arayuz", "motor": "claude",',
            '     "gerekce": "ekran isi var, kadroda arayuz rolu yok"}',
            "  ]",
            "}",
            "```",
        ]
        if hata:
            satir += [
                "",
                "# ONCEKI ONERIN REDDEDILDI",
                "",
                hata,
                "",
                "Duzelt ve yeniden ver.",
            ]
        return "\n".join(satir)

    # -- 2. kapilar ---------------------------------------------------------

    def oneriyi_dogrula(self, oneri) -> str:
        """Oneri kabul edilebilir mi. Bos donerse gecerli.

        Hic reddetmeyen kapi, kapi degildir. Buradaki her ret bir
        SESSIZ OLUMU onluyor: tanimsiz rol -> araclari hic verilmemis
        ajan; kurulu olmayan motor -> hic kosamayacak ajan; tekrar eden
        ad -> gecmisi okunamaz hale gelen sicil.
        """
        if not isinstance(oneri, dict):
            return "Cikti JSON nesnesi degil."
        if not (oneri.get("gerekce") or "").strip():
            return ("`gerekce` bos. Kadro kurmak patronun limitini harcar; "
                    "neden bu kadro gerektigini yazmadan onay isteyemezsin.")
        uyeler = oneri.get("uyeler")
        if not isinstance(uyeler, list) or not uyeler:
            return "`uyeler` bos ya da liste degil. En az bir ajan oner."
        if len(uyeler) > AZAMI_UYE:
            return (f"{len(uyeler)} ajan onerdin, en fazla {AZAMI_UYE} olabilir. "
                    "Kalabalik kadro bos koltuk demektir; gerekiyorsa ikinci "
                    "bir oneri getir.")

        musait = {m for m, var in musait_motorlar().items() if var}
        mevcut_adlar = {a["ad"] for a in self.ofis.kadro.liste()}
        gorulen = set()

        for i, u in enumerate(uyeler):
            yer = f"{i + 1}. uye"
            if not isinstance(u, dict):
                return f"{yer}: nesne degil."
            ad = (u.get("ad") or "").strip().lower()
            if not ad:
                return f"{yer}: `ad` bos."
            if ad in mevcut_adlar:
                return (f"{yer}: '{ad}' adi zaten kadroda. Ad geri donmez -- "
                        "gecmis okunabilir kalsin diye. Baska bir ad sec.")
            if ad in gorulen:
                return f"{yer}: '{ad}' adini iki kez onerdin."
            gorulen.add(ad)

            try:
                roller.coz(u.get("rol") or "")
            except RolHatasi as exc:
                return f"{yer} ('{ad}'): {str(exc).splitlines()[0]} " \
                       f"Gecerli roller: {', '.join(sorted(roller.ROLLER))}"

            motor = (u.get("motor") or "claude").strip()
            if motor not in musait:
                return (f"{yer} ('{ad}'): '{motor}' motoru KURULU DEGIL. "
                        f"Musait: {', '.join(sorted(musait))}")
            if not (u.get("gerekce") or "").strip():
                return (f"{yer} ('{ad}'): `gerekce` bos. Gerekcesiz bir ajan, "
                        "bos duran bir koltuktur.")
        return ""

    # -- 3. oneriyi uret ----------------------------------------------------

    def oner(self, hedef: str, *, lider_ad: str = "", kanat_id: str = None,
             butce_usd: float = None, zaman_asimi: float = None,
             deneme: int = 2) -> dict:
        """Lideri kadro onermeye iter, kapilardan gecirir, SAKLAR.

        Saklamak sart: `oner` ile `kur` arasinda insan dusunur. Oneri
        diskte durmazsa "onayla" diyecek bir sey kalmaz.
        """
        hedef = (hedef or "").strip()
        if not hedef:
            raise EkipHatasi("Bos istek icin kadro onerilemez.")

        lider = self.orkestra._lider_sec(lider_ad, kanat_id)
        kanat_id = kanat_id if kanat_id is not None else lider["kanat_id"]

        hata = ""
        for sira in range(max(1, deneme)):
            metin = self.oneri_metni(hedef, kanat_id, hata)
            try:
                ham = self.orkestra._lideri_kostur(
                    lider, metin, butce_usd, zaman_asimi)
            except Exception as exc:
                raise EkipHatasi(f"Lider kadro oneremedi: {exc}") from exc
            oneri = _json_ayikla(ham)
            hata = self.oneriyi_dogrula(oneri)
            if not hata:
                break
            # Ret OGRETIR: lider neyi yanlis yaptigini gorur.
            self.db.olay_yaz(
                self.proje_id, "uyari",
                f"Ekip onerisi reddedildi ({sira + 1}. deneme): {hata}",
                ajan_ad=lider["ad"])
        else:
            raise EkipHatasi(
                f"Lider gecerli bir kadro oneremedi. Son sebep: {hata}")

        return self._sakla(hedef, oneri, lider["ad"], kanat_id)

    def sablondan(self, sablon_ad: str, *, kanat_id: str = None) -> dict:
        """SABLONDAN oneri: lider CAGRILMAZ, jeton yanmaz, sonuc kararli.

        Yeni bir yol degil: uretilen sey siradan bir ekip onerisidir ve
        AYNI kapidan (`oneriyi_dogrula`) gecer, ayni onizlemeyle gosterilir,
        ayni `kur`/`reddet` ile karara baglanir. Kurmak yine INSANIN karari.
        """
        from . import sablon as _s
        if kanat_id is None:
            with self.db.baglanti() as conn:
                kanatlar = [dict(r) for r in conn.execute(
                    "SELECT id FROM kanat WHERE proje_id = ?",
                    (self.proje_id,)).fetchall()]
            if len(kanatlar) > 1:
                raise EkipHatasi(
                    "Birden cok takim var; sablonun hangi takima kurulacagini "
                    "sec (kanat). Yanlis takima kurulan kadro yanlis lidere baglanir.")
            kanat_id = kanatlar[0]["id"] if kanatlar else None
        kadro = self.ofis.kadro.liste()
        lider_var = any(a["lider_mi"] and a["kanat_id"] == kanat_id
                        for a in kadro)
        try:
            oneri = _s.oneri_uret(sablon_ad, [a["ad"] for a in kadro],
                                  lider_var=lider_var)
        except _s.SablonHatasi as exc:
            raise EkipHatasi(str(exc)) from exc
        hata = self.oneriyi_dogrula(oneri)
        if hata:
            raise EkipHatasi(f"Sablon onerisi kapidan gecmedi: {hata}")
        s = _s.SABLONLAR[sablon_ad.strip().lower()]
        return self._sakla(f"Sablon: {s.baslik}", oneri, f"sablon:{s.ad}",
                           kanat_id)

    def _sakla(self, hedef: str, oneri: dict, oneren: str, kanat_id) -> dict:
        # Model bos birakildiysa rolun kademesinden doldurulur -- ise
        # alma aninda degil SIMDI, cunku insan onizlemede hangi modelin
        # kosacagini GORMELI. Onizlemede gorunmeyen bir secim, onay
        # alinmamis bir secimdir.
        uyeler = []
        for u in oneri["uyeler"]:
            rol_ad = roller.coz(u["rol"])
            r = roller.ROLLER[rol_ad]
            motor = (u.get("motor") or "claude").strip()
            uyeler.append({
                "ad": u["ad"].strip().lower(),
                "rol": rol_ad,
                "tur": r.tur,
                "motor": motor,
                "model": (u.get("model") or "").strip()
                         or roller.model_sec(
                             motor, r.kademe,
                             roller.kademe_haritasi(self.db, self.proje_id)),
                "gerekce": u["gerekce"].strip(),
                "uyari": r.uyari,
            })

        with self.db.baglanti() as conn:
            son = conn.execute(
                "SELECT COALESCE(MAX(no), 0) AS n FROM ekip_onerisi "
                "WHERE proje_id = ?", (self.proje_id,)).fetchone()["n"]
            no = int(son) + 1
            conn.execute(
                "INSERT INTO ekip_onerisi (id, proje_id, no, kanat_id, hedef, "
                "gerekce, uyeler, oneren, durum, olusturuldu) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'bekliyor', ?)",
                (uuid.uuid4().hex, self.proje_id, no, kanat_id, hedef,
                 oneri["gerekce"].strip(),
                 json.dumps(uyeler, ensure_ascii=False), oneren, simdi()))

        self.db.olay_yaz(
            self.proje_id, "ekip_onerildi",
            f"#{no}: {len(uyeler)} ajan onerildi ({', '.join(u['ad'] for u in uyeler)})",
            ajan_ad=oneren)
        return self.oneri(no)

    # -- 4. okuma -----------------------------------------------------------

    def oneri(self, no: int) -> dict:
        with self.db.baglanti() as conn:
            row = conn.execute(
                "SELECT * FROM ekip_onerisi WHERE proje_id = ? AND no = ?",
                (self.proje_id, int(no))).fetchone()
        if not row:
            raise EkipHatasi(f"Ekip onerisi bulunamadi: #{no}")
        d = dict(row)
        d["uyeler"] = json.loads(d["uyeler"] or "[]")
        return d

    def bekleyenler(self) -> list:
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT * FROM ekip_onerisi WHERE proje_id = ? AND "
                "durum = 'bekliyor' ORDER BY no", (self.proje_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["uyeler"] = json.loads(d["uyeler"] or "[]")
            out.append(d)
        return out

    # -- 5. insanin karari --------------------------------------------------

    def kur(self, no: int, *, klasor: str = "") -> list:
        """ONAYLANDI: onerilen kadroyu gercekten ise alir.

        Ise alma `kadro.ise_al`tan gecer -- yani rol kapisi, ad kapisi
        ve tek-lider kapisi burada da uygulanir. Ayri bir yol acsaydik
        kurallar iki yerde olurdu ve biri otekinden kayardi (bu projede
        tam bu yuzden bes kez hata cikti).
        """
        o = self.oneri(no)
        if o["durum"] != "bekliyor":
            raise EkipHatasi(
                f"#{no} zaten '{o['durum']}'. Karar bir kez verilir.")
        if not o["uyeler"]:
            raise EkipHatasi(f"#{no} bos.")
        # KLASOR VERILMEDIYSE ORTAK KOK. Olculdu (24.09.2026): panelin
        # "Kur" dugmesi `kur(no)`u klasorsuz cagiriyordu ve ajanlar BOS
        # klasorle ise aliniyordu; koltuk bos klasorde isi "calisma klasoru
        # tanimli degil" diye reddeder. Yani panelden kurulan ekip HIC
        # calisamazdi. Kural tek yerde: `Ofis.kok_klasoru` (karar 18.09).
        if not klasor:
            klasor = self.ofis.kok_klasoru()
            Path(klasor).mkdir(parents=True, exist_ok=True)

        alinan = []
        for u in o["uyeler"]:
            try:
                # `lider` rolu GERCEK lider olur: onceden `lider_mi`
                # gecirilmiyordu ve lidersiz bir takima kurulan "lider"
                # yalniz bir etiket olarak kaliyordu -- orkestra onu
                # lider saymaz, is dagitilmazdi. Tek-lider kapisi
                # `ise_al`da; ikinci lider yine REDDEDILIR.
                alinan.append(self.ofis.kadro.ise_al(
                    u["ad"], u["rol"], motor=u["motor"], model=u["model"],
                    kanat_id=o["kanat_id"], klasor=klasor,
                    lider_mi=(u["rol"] == "lider")))
            except (KadroHatasi, RolHatasi) as exc:
                # Yarim kurulmus kadro, kurulmamis kadrodan KOTUDUR:
                # tahtada var gorunur, calismaz. Ne kuruldugunu acikca
                # soyleyip duruyoruz.
                raise EkipHatasi(
                    f"#{no} kurulurken '{u['ad']}' ise alinamadi: {exc}\n"
                    f"Once alinanlar: {', '.join(a['ad'] for a in alinan) or '(yok)'}\n"
                    "Oneri BEKLIYOR olarak duruyor; duzeltip yeniden kur."
                ) from exc

        with self.db.baglanti() as conn:
            conn.execute(
                "UPDATE ekip_onerisi SET durum = 'kuruldu', karar_verildi = ? "
                "WHERE proje_id = ? AND no = ?", (simdi(), self.proje_id, no))

        # Oneri bir KARARDIR. "Bu ajan neden ise alinmis" sorusu alti ay
        # sonra da cevaplanabilmeli.
        self.ofis.bellek.karar_yaz(
            f"Kadroya {len(alinan)} ajan eklendi: "
            f"{', '.join(f'{a['ad']} ({a['meslek']})' for a in alinan)}.",
            f"Istek: {o['hedef']}\nLiderin gerekcesi: {o['gerekce']}",
            "insan", tur="kadro")
        self.db.olay_yaz(
            self.proje_id, "ekip_kuruldu",
            f"#{no}: {', '.join(a['ad'] for a in alinan)}", ajan_ad="insan")
        return alinan

    def reddet(self, no: int, sebep: str) -> dict:
        """REDDEDILDI. Sebep ZORUNLU.

        Gerekcesiz ret, liderin ayni oneriyi baska bicimde tekrar
        getirmesi demektir -- `onay_cevapla`daki kuralin aynisi.
        """
        sebep = (sebep or "").strip()
        if not sebep:
            raise EkipHatasi(
                "Ret gerekcesi zorunlu. Lider neyin kabul edilmedigini "
                "ogrenmezse ayni oneriyi baska bicimde tekrar getirir.")
        o = self.oneri(no)
        if o["durum"] != "bekliyor":
            raise EkipHatasi(f"#{no} zaten '{o['durum']}'.")
        with self.db.baglanti() as conn:
            conn.execute(
                "UPDATE ekip_onerisi SET durum = 'reddedildi', sebep = ?, "
                "karar_verildi = ? WHERE proje_id = ? AND no = ?",
                (sebep, simdi(), self.proje_id, no))
        self.ofis.bellek.karar_yaz(
            f"Ekip onerisi #{no} reddedildi.", sebep, "insan", tur="kadro")
        self.db.olay_yaz(self.proje_id, "ekip_reddedildi",
                         f"#{no}: {sebep[:120]}", ajan_ad="insan")
        return self.oneri(no)

    # -- 6. insana gosterim -------------------------------------------------

    def onizleme(self, no: int) -> str:
        """Kurmadan ONCE gosterilen hali.

        Onizlemenin butun degeri, kararin UYGULANMADAN once gorunmesinde.
        Rakipte bildirilen hata bunun tersiydi: *"lider gorevi
        dagitmiyor, kendi icinde kosuyordu"* -- ve kimse gormuyordu.
        """
        o = self.oneri(no)
        satir = [
            f"EKIP ONERISI #{o['no']}   [{o['durum']}]",
            f"  istek   : {o['hedef']}",
            f"  oneren  : {o['oneren']}",
            "",
            f"  gerekce : {o['gerekce']}",
            "",
            "  ONERILEN (henuz KURULMADI):",
        ]
        motorlar = set()
        for u in o["uyeler"]:
            motorlar.add(u["motor"])
            satir.append(
                f"    + {u['ad']:<10}{u['rol']:<13}{u['motor']}/"
                f"{u['model'] or '(model yok!)':<16} {u['tur']}")
            satir.append(f"        {u['gerekce']}")
            if u.get("uyari"):
                satir.append(f"        ! {u['uyari']}")
        satir += [
            "",
            f"  {len(o['uyeler'])} ajan · {len(motorlar)} motor "
            f"({', '.join(sorted(motorlar))})",
        ]
        if o["durum"] == "bekliyor":
            satir += [
                "",
                f"  kur    :  python -m ofis.kabuk ekip kur {o['no']}",
                f"  reddet :  python -m ofis.kabuk ekip red {o['no']} "
                f"--sebep \"...\"",
            ]
        elif o["durum"] == "reddedildi":
            satir += ["", f"  ret sebebi: {o['sebep']}"]
        return "\n".join(satir)
