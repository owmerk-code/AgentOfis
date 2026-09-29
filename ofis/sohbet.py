# -*- coding: utf-8 -*-
"""Sohbet: liderin ON KAPISI. Insanin tek muhatabi burasidir.

Kullanicinin tarifi (19.09.2026): *"lider benim muhattabim, onunla
konusurum, ona soylerim; o ajanlari, ofisi yonetir, her seyi bilir,
takip eder, patrona raporu cikitiyi verir. Her konusmada calisan ajanlara
gorev dusup dusmedigine, ajana ihtiyac olup olmadigina LIDER karar
verecek. Tek basina verecegi bir cevapsa tek basina calisabilir."*

Bugune kadar eksik olan tam buydu. `kabuk hedef` her istegi ZORLA bir
goreve ceviriyordu: "iade suresi kac gun?" diye sorsan bile lider plan
yapmak, gorev acmak, isci kosturmak zorundaydi. Basit bir soru icin
butun makineyi calistirmak, jetonu da zamani da bosa yakar.

Dort yol, karari LIDERIN:

    CEVAP   Bilgi sorusu ya da karar sorusu. Lider kendi bilgisiyle
            cevaplar; hicbir gorev acilmaz, hicbir ajan uyandirilmaz.
    KENDI   Kucuk, tek parca is. Lider ustlenir. INCELEME INSANA DUSER
            (yapan inceleyemez -- bkz. lider.py).
    DAGIT   Gercekten bolunen ya da uzmanlik isteyen is. Kadroya dagitir,
            halka doner, sonunda TEK CIKTI ile geri gelir.
    KADRO   Is icin gereken ROL kadroda yok. Lider kadro ONERIR ve
            DURUR; is patron onaylayana kadar baslamaz (bkz. ekip.py).
            Bu yol olmadan `dagit` var olan kadroyu VARSAYIYORDU ve
            gereken rol yoksa is sessizce yarim kaliyordu.

Kararlar ve sebepleri:

* **Karar liderin, ama GEREKCESI kayda gecer.** "Neden bunun icin uc
  ajan kosturdun" ya da "neden bunu kendin yaptin" sorusunun cevabi alti
  ay sonra da durmali. Rakipte bildirilen hata bunun tersiydi: lider hic
  dagitmiyor, isi kendi iginde kosuyordu -- ve kimse fark etmiyordu.
  Iki ucu da kayittan anlasilir.

* **Lider TEMIZ oturumda triyaj yapar.** Konusma birikiminin tamami
  tasinmaz (Yasa 4: baglam curumesi). Tasinan sey: OFISIN SU ANKI HALI
  (taze sorgu) + son birkac konusma OZETI. Transkript degil ozet, cunku
  uzun bir gunun transkripti liderin dikkatini dagitir ve maliyeti her
  mesajda buyutur.

* **Tek cikti.** Is bittiginde lider, kapanan gorevleri ve KANITLARI
  okuyup insana tek bir cevap yazar. Parcalari insana yigmak, isi
  insana birlestirtmektir.

* **Sohbet `mesaj` tablosunda yasar.** Ayri bir tablo acmadik: insan ->
  lider zaten bir mesajdir ve postane onu tutuyor. Iki yerde tutmak,
  birinin bayatlamasi demektir.
"""

from __future__ import annotations

import threading
import time

from . import baglayici, gorsel, roller
from .motor import motor_ac
from .ekip import Ekip, EkipHatasi
from .klasor import klasorleri_dogrula, metinler
from .tarayici import kaynaklari_dogrula as tarayici_kaynaklari_dogrula
from .orkestra import Orkestra, OrkestraHatasi, _json_ayikla

#: Triyajda lidere gosterilecek son konusma sayisi. Az tutuluyor:
#: sohbetin tamami her mesajda tasinirsa maliyet dogrusal buyur ve
#: dikkat dagilir. Lider daha fazlasina ihtiyac duyarsa ofis durumu
#: zaten taze sorguyla onunde.
GECMIS_ADEDI = 6

#: Tek bir cevabin ustunde durulacak uzunluk. Daha uzunu sohbet degil
#: rapordur; rapor zaten is bitiminde ayrica uretilir.
CEVAP_SINIRI = 4000


class SohbetHatasi(RuntimeError):
    pass


# -- CEVAP YAZILIRKEN AKAR ---------------------------------------------------
#
# OLCULDU (29.09.2026): liderin "naber"e cevabi Opus'ta 9-27 sn suruyor ve
# panel bu sure boyunca yalnizca "dusunuyor" diyordu. Modeli kucultmek
# lideri zayiflatirdi; bekleyisi kisaltmanin tek yolu cevabi YAZILIRKEN
# gostermek.
#
# Iki tuzak, ikisi de bilincli karsilandi:
#
# 1. Triyaj cevabi JSON'un ICINDE (`{"karar", "gerekce", "cevap", ...}`).
#    Ham parcalari basmak patrona makine metni gosterirdi. Akista yalniz
#    `cevap` alani (kacislari cozulmus, yarimsa yarim) gosterilir; karar
#    `cevap` degilse yolun kendisi ve gerekcesi.
# 2. Akis DEFTERE YAZILMAZ, surecin BELLEGINDE yasar. Ilk surum onu tek
#    bir `ayar` kaydinda tutuyordu. OLCULDU: defter yazimi bosta ~9 ms
#    (WAL + synchronous=FULL, her islemde fsync), ama makine yuk altindayken
#    100-150 ms'ye cikti ve akis defter kilidini tuttugu icin cevabi HIZLI
#    gostermek icin eklenen sey lider turunu YAVASLATABILIYORDU. Bellekte
#    maliyeti yok. Bedeli yazili: kabuktan baslayan `konus` panelde AKMAZ
#    (ayri surec); panelden yazilan her mesaj akar. Cevabin kendisi yine
#    deftere duser -- akis yalniz bekleyis suresinin gorunur hali.
#
# 3. En fazla ~3 kez/sn guncellenir: her parcada yarim JSON'u yeniden
#    ayiklamak uzun cevapta karesel buyurdu.

AKIS_ARALIK_SN = 0.3

#: `{(proje_id, mesaj_id): metin}` -- su an yazilmakta olan cevaplar.
_AKISLAR: dict = {}
_AKIS_KILIDI = threading.Lock()


def _bellege_yaz(proje_id: str, mesaj_id: str, metin) -> None:
    with _AKIS_KILIDI:
        if metin is None:
            _AKISLAR.pop((proje_id, mesaj_id), None)
        else:
            _AKISLAR[(proje_id, mesaj_id)] = metin

_KARAR_ETIKET = {"kendi": "kendim yapıyorum", "dagit": "ekibe dağıtıyorum",
                 "kadro": "kadro öneriyorum", "cevap": "cevaplıyorum"}


def _kismi_alan(metin: str, alan: str):
    """JSON metnindeki `"alan": "..."` degerini, YARIM olsa bile coz.

    Doner `(deger, kapandi)`; alan hic baslamadiysa `(None, False)`.
    Yarim bir kacis (`\\` ya da `\\u00`) sonda kalirsa o parca beklenir,
    uydurulmaz.
    """
    import re
    m = re.search(r'"' + re.escape(alan) + r'"\s*:\s*"', metin)
    if not m:
        return None, False
    i, cikti = m.end(), []
    kacis = {"n": "\n", "t": "\t", "r": "", '"': '"', "\\": "\\",
             "/": "/", "b": "", "f": ""}
    while i < len(metin):
        c = metin[i]
        if c == '"':
            return "".join(cikti), True
        if c == "\\":
            if i + 1 >= len(metin):
                break
            k = metin[i + 1]
            if k == "u":
                hex_ = metin[i + 2:i + 6]
                if len(hex_) < 4:
                    break
                try:
                    cikti.append(chr(int(hex_, 16)))
                except ValueError:
                    pass
                i += 6
                continue
            cikti.append(kacis.get(k, k))
            i += 2
            continue
        cikti.append(c)
        i += 1
    return "".join(cikti), False


def akis_metni(ham: str, kip: str = "json") -> str:
    """Liderin YARIM ciktisindan patrona gosterilecek metin.

    `kip="duz"`: rapor turu, metin oldugu gibi. `kip="json"`: triyaj.
    Gosterilecek bir sey yoksa bos doner (panel "dusunuyor" der).
    """
    import re
    ham = ham or ""
    if kip == "duz":
        return ham.strip()
    m = re.search(r'\{\s*"karar"', ham)
    if not m:
        yalin = ham.strip()
        # JSON gelmek uzere olabilir (cit ya da suslu parantez): o zaman
        # henuz gosterilecek bir sey yok. Duz metinse -- lider bicime
        # uymadiysa -- oldugu gibi akar; triyaj da onu cevap sayacak.
        if not yalin or yalin.startswith(("{", "`")):
            return ""
        return yalin
    govde = ham[m.start():]
    karar, kapandi = _kismi_alan(govde, "karar")
    if not kapandi:
        return ""
    if karar == "cevap":
        cevap, _ = _kismi_alan(govde, "cevap")
        return (cevap or "").strip()
    gerekce, _ = _kismi_alan(govde, "gerekce")
    bas = _KARAR_ETIKET.get(karar, karar)
    return (bas + (" — " + gerekce.strip() if gerekce else "")).strip()


class AkisYazici:
    """Tek mesajin akisini BELLEGE seyrek yazan cagrilabilir.

    Orkestra her parcada cagirir; `None` = yeni basamak, bastan (devredilen
    turun yarim metni yenisine yapismasin). `sabit` onceki bolumdur
    (orn. triyajin cevabi) ve rapor akarken ustunde durur.
    """

    def __init__(self, db, proje_id: str, mesaj_id: str) -> None:
        self._saat = time.monotonic
        self.proje_id, self.mesaj_id = proje_id, str(mesaj_id)
        self.kip, self.ham, self.sabit = "json", "", ""
        self._son_an, self._son_metin = 0.0, None

    def yeni_bolum(self, kip: str, sabit: str = "") -> None:
        self.kip, self.ham, self.sabit = kip, "", sabit or ""

    def not_yaz(self, metin: str) -> None:
        """Iki tur arasindaki durum ("ekip calisiyor...") -- hemen yazilir."""
        self.sabit, self.ham = metin, ""
        self._yaz(zorla=True)

    def __call__(self, parca) -> None:
        if parca is None:
            self.ham = ""
        else:
            self.ham += parca
        self._yaz()

    def _metin(self) -> str:
        akan = akis_metni(self.ham, self.kip)
        if self.sabit and akan:
            return self.sabit + "\n\n" + akan
        return self.sabit or akan

    def _yaz(self, zorla: bool = False) -> None:
        an = self._saat()
        if not zorla and an - self._son_an < AKIS_ARALIK_SN:
            return
        metin = self._metin()[:CEVAP_SINIRI]
        if metin == self._son_metin:
            return
        self._son_an, self._son_metin = an, metin
        _bellege_yaz(self.proje_id, self.mesaj_id, metin)

    def bitir(self) -> None:
        _bellege_yaz(self.proje_id, self.mesaj_id, None)


def akislar(db, proje_id: str) -> dict:
    """Su an akan butun cevaplar: `{mesaj_id: metin}` (bu surecte)."""
    with _AKIS_KILIDI:
        return {m: v for (p, m), v in _AKISLAR.items() if p == proje_id}


class Sohbet:
    def __init__(self, ofis, *, motor_fabrikasi=motor_ac, zincir=None) -> None:
        self.ofis = ofis
        self.db = ofis.db
        self.proje_id = ofis.proje_id
        self.motor_fabrikasi = motor_fabrikasi
        self.orkestra = Orkestra(ofis, motor_fabrikasi=motor_fabrikasi,
                                 zincir=zincir)
        # Ekip de KENDI fabrikasiyla kurulur, `ofis.ekip` KULLANILMAZ.
        #
        # Ilk surumde ofisin kendi Ekip'i cagriliyordu ve Sohbet'e
        # verilen motor fabrikasi oraya HIC ULASMIYORDU -- kadro onerisi
        # sessizce varsayilan motorla kosuyordu. Ayni hata bu oturumda
        # UCUNCU kez cikti (orkestra->koltuk, ekip->orkestra, simdi
        # sohbet->ekip) ve ucunu de test yakaladi.
        #
        # Desen belli: bir parca fabrika aliyorsa, cagirdigi HER
        # parcaya onu gecirmek zorunda. "Sessizce yok sayilan ayar,
        # ayar degildir."
        self.ekip = Ekip(ofis, motor_fabrikasi=motor_fabrikasi)

    # -- liderin gordugu ---------------------------------------------------

    def ofis_ozeti(self) -> str:
        """Liderin SU ANKI ofis goruntusu -- her mesajda TAZE uretilir.

        Elle tutulan bir ozet bayatlar; bu sorgudur, bayatlayamaz.
        Liderin "her seyi bilir, takip eder" olmasi buradan gelir.
        """
        satirlar = []
        # KUNYE ONCE: patronun mesajini "kapsam disi" bilmeden triyaj
        # etmek, yapilmayacak bir isi dagitmanin en kisa yolu.
        kunye = self.ofis.brifing.kunye_ozeti()
        if kunye:
            satirlar += [kunye, ""]
        kadro = self.ofis.kadro.liste()
        isciler = [a for a in kadro if not a["lider_mi"]]
        if isciler:
            satirlar.append("### Kadron")
            for a in isciler:
                yetki = ("YAZAMAZ (dusunur, metin uretir)"
                         if a["tur"] == "kafa" else "dosya yazar, komut kosturur")
                hal = self.ofis.postane.bekliyor_mu(a["ad"])
                kendi = [g for g in self.ofis.tahta.liste()
                         if g["sahip"] == a["ad"]
                         and g["durum"] in ("calisiyor", "inceleme")]
                durum = (f"BEKLIYOR ({hal['tur']})" if hal["bekliyor"]
                         else (f"#{kendi[0]['no']} {kendi[0]['baslik']}"
                               if kendi else "bosta"))
                satirlar.append(f"- **{a['ad']}** ({a['meslek']}, {a['model'] or 'varsayilan'}) "
                                f"— {yetki} — {durum}")

        acik = [g for g in self.ofis.tahta.liste()
                if g["durum"] in ("bekliyor", "hazir", "calisiyor", "inceleme")]
        satirlar.append("")
        if acik:
            satirlar.append("### Acik isler")
            for g in acik:
                kanit = len(self.ofis.tahta.kanitlar(g["no"]))
                satirlar.append(f"- #{g['no']} [{g['durum']}] {g['baslik']} "
                                f"— {g['sahip'] or 'atanmadi'} — {kanit} kanit")
        else:
            satirlar.append("### Acik is yok.")

        bekleyen = (self.ofis.postane.insan_bekleyenler()
                    + self.ofis.postane.bekleyen_onaylar())
        if bekleyen:
            satirlar += ["", "### INSANDAN BEKLENENLER (is ilerlemiyor)"]
            for b in self.ofis.postane.insan_bekleyenler():
                satirlar.append(f"- {b['gonderen']} soruyor: {b['govde'][:160]}")
            for b in self.ofis.postane.bekleyen_onaylar():
                satirlar.append(f"- {b['isteyen']} onay istiyor: {b['eylem'][:160]}")

        olgular = self.ofis.bellek.gecerli_olgular()
        if olgular:
            satirlar += ["", "### Gecerli bilgiler"]
            for o in olgular[:25]:
                satirlar.append(f"- {o['konu']}: {o['icerik']}")
            if len(olgular) > 25:
                satirlar.append(f"- _(+{len(olgular) - 25} bilgi daha)_")

        kararlar = self.ofis.bellek.son_kararlar(6)
        if kararlar:
            satirlar += ["", "### Son kararlar (BAGLAYICI)"]
            for k in kararlar:
                satirlar.append(f"- {k['veren']}: {k['karar']}")
        return "\n".join(satirlar)

    def gecmis(self, adet: int = GECMIS_ADEDI) -> list:
        """Son konusmalar. Transkript degil OZET malzemesi."""
        with self.db.baglanti() as conn:
            rows = conn.execute(
                "SELECT govde, cevap, olusturuldu FROM mesaj "
                "WHERE proje_id = ? AND gonderen = 'insan' "
                # Patronun AJANA notu liderle konusma degildir; gecmise
                # girseydi lider onu kendisine soylenmis sanirdi.
                "AND mod != 'yonlendirme' "
                "ORDER BY olusturuldu DESC, rowid DESC LIMIT ?",
                (self.proje_id, int(adet)),
            ).fetchall()
        return [dict(r) for r in rows][::-1]

    def triyaj_metni(self, mesaj: str, *, ek_klasorler=()) -> str:
        satirlar = [
            "# PATRONUN MESAJI",
            "",
            mesaj,
            "",
            "---",
            "",
            "# SEN",
            "",
            "Bu ofisin lidersin. Patronun tek muhatabi sensin: o sana",
            "soyler, sen ofisi yonetirsin ve sonucu ona sen verirsin.",
            "",
            "# OFISIN SU ANKI HALI",
            "",
            self.ofis_ozeti(),
            "",
            # BAGLAYICI ENVANTERI TRIYAJDA DA GEREKIYOR.
            #
            # Kullanici sordu: *"ajan farkedebilecek mi bagli mi degil
            # mi, soracak mi?"* -- lider envanteri gormeden hayirdi.
            # Patron "magazadaki siparislere bakalim" dediginde lider
            # ya uydurur, ya sessizce basarisiz bir is acar. Ucuncu ve
            # dogru yol: BAGLI DEGIL diyip hangi komutun calistirilmasi
            # gerektigini soylemek -- ama bunun icin GORMESI gerek.
            baglayici.lider_blogu(),
            "",
            # ROL KUTUPHANESI TRIYAJDA GEREKIYOR -- dorduncu yol icin.
            #
            # Olculdu (21.09.2026): `kadro` yolu iki gercek kosuda da
            # HIC atesmedi. Is tam bir dokuman isiydi, kadroda
            # `dokuman` YOKTU, kutuphanede VARDI -- lider isi `bilge`ye
            # (arastirma) verdi. Cunku triyaj metni `kadro` yolunu
            # anlatiyor ama onerebilecegi rollerin listesini HIC
            # vermiyordu; `roller` bu modulde ice aktarilmamisti bile.
            #
            # Baglayici envanteriyle ayni sinif: gormeden karar vermek
            # tahmindir. Ve uydurma rol adi zaten `Ekip` tarafindan
            # reddedilir -- yani liste olmadan yol pratikte kapaliydi.
            roller.lider_blogu(
                [a["meslek"] for a in self.ofis.kadro.liste()]),
            "",
            # MEDYA YETENEGI TRIYAJDA GEREKIYOR.
            #
            # Olculdu (21.09.2026): lider medya hakkinda HICBIR SEY
            # gormuyordu -- ne para kilidini, ne kotayi. Patron
            # "kapak gorseli yapalim" dediginde lider ya is acip
            # ortada patlayacak, ya yapabilecegini varsayacakti.
            #
            # Baglayici ve rol envanterleriyle ayni sinif: gormeden
            # karar vermek tahmindir. Ve blok yalnizca "yapilamaz"
            # demiyor -- insan koprusunu (`gorsel_iste`) da soyluyor,
            # cunku genelde dogru cevap odur.
            gorsel.lider_blogu(),
        ]

        ekler = list(ek_klasorler or ())
        if ekler:
            # Klasor triyajda da acik: patron "su klasorde ne var"
            # diye sorabilmeli ve liderin bunun icin is acmasi
            # gerekmemeli. Tur salt okunur, yani bakmak guvenli.
            satirlar += [
                "",
                "# PATRONUN ACTIGI KLASOR",
                "",
                "Su klasore SIMDI erisebiliyorsun (salt okunur):",
                "",
            ] + [f"- `{e}`" for e in ekler] + [
                "",
                "Icerigi hakkinda soru soruluyorsa once BAK, sonra cevapla.",
                "Bakmadan icerigi hakkinda bir sey soyleme.",
            ]

        gecmis = self.gecmis()
        if gecmis:
            satirlar += ["", "# SON KONUSMALAR", ""]
            for g in gecmis:
                satirlar.append(f"- patron: {g['govde'][:200]}")
                if g["cevap"]:
                    satirlar.append(f"  sen: {g['cevap'][:200]}")

        satirlar += [
            "",
            "---",
            "",
            "# KARARIN",
            "",
            "Bu mesaj icin **ajana ihtiyac var mi?** Dort yoldan birini sec:",
            "",
            "**cevap** — Bilgi ya da karar sorusu. Kendi bilginle cevapla.",
            "  Hicbir gorev acilmaz, hicbir ajan uyandirilmaz. Basit bir",
            "  soru icin butun makineyi calistirmak jetonu da zamani da",
            "  bosa yakar. Patron 'ne durumdayiz', 'su neydi', 'sence' diye",
            "  soruyorsa yol budur.",
            "",
            "**kendi** — Kucuk, tek parca, bolunmeyen is. Sen ustlenirsin.",
            "  Dikkat: YAPAN INCELEYEMEZ. Bu isi sen yaparsan incelemeyi",
            "  patron yapacak. Emin degilsen dagit.",
            "",
            "**dagit** — Gercekten bolunen ya da uzmanlik isteyen is.",
            "  Kadroya dagitirsin, sonunda TEK CIKTI ile patrona donersin.",
            "",
            "**kadro** — Is icin gereken ROL kadroda YOK. Once kadro",
            "  onerirsin; patron onaylayinca is baslar. Var olan bir ajana",
            "  yapamayacagi isi vermek, isi yarim birakmanin en sessiz",
            "  yoludur. Yeni bir rol gerekmiyorsa bu yolu SECME.",
            "",
            "Bolmek varsayilan DEGILDIR: coklu ajan ~15 KAT jeton yakar ve",
            "yalnizca is gercekten bagimsiz kollara ayriliyorsa kazandirir.",
            "Ama HER SEYI KENDIN YAPMAK da yanlistir -- kadron bunun icin var.",
            "",
            "# CIKTI BICIMI",
            "",
            "Yalnizca su JSON'u ver, baska hicbir sey yazma:",
            "",
            "```json",
            "{",
            '  "karar": "cevap",',
            '  "gerekce": "NEDEN bu yolu sectin -- zorunlu",',
            '  "cevap": "karar=cevap ise patrona yazacagin metin",',
            '  "hedef": "karar=kendi, dagit ya da kadro ise isin tek cumlelik hedefi"',
            "}",
            "```",
            "",
            "Kurallar:",
            "- `gerekce` bos olamaz. Ajan kosturmamak da bir karardir.",
            "- `karar=cevap` ise `cevap` dolu olmali; Turkce ve net yaz.",
            "- `karar=kendi`, `dagit` ya da `kadro` ise `hedef` dolu olmali.",
            "- `karar=kadro` yalnizca kadroda OLMAYAN bir rol gerektiginde.",
            "  Kadroyu SEN kuramazsin -- onerirsin, patron onaylar.",
            "- Bilmedigin bir seyi UYDURMA. Bilmiyorsan `cevap` ile soyle,",
            "  ya da ogrenmek icin `dagit` ile arastirma isi ac.",
        ]
        return "\n".join(satirlar)

    # -- ana akis ----------------------------------------------------------

    def konus(self, mesaj: str, **ayarlar):
        """Patronun mesajini alir, lideri karar verdirir, sonucu akitir.

        Akan sozlukler: `{tur, govde, ek}`. Turler:
        `triyaj` · `cevap` · `plan` · `tik` · `rapor` · `bitti`.

        Liderin cevabi YAZILIRKEN de deftere akar (`AkisYazici`); cevap
        dusunce -- ya da tur hangi sebeple biterse bitsin -- akis kaydi
        silinir. Bitmis bir mesajin yarim metni panelde asili kalmaz.
        """
        self._akis = None
        try:
            yield from self._konus(mesaj, **ayarlar)
        finally:
            if self._akis is not None:
                self._akis.bitir()
                self._akis = None

    def _konus(self, mesaj: str, *, lider_ad: str = "", butce_usd=None,
               zaman_asimi=None, azami_tik: int = 8, paralel: int = 3,
               izinli_araclar: tuple = (), ek_klasorler=None,
               tarayici_alani=None, tarayici_kabini: str = ""):
        mesaj = (mesaj or "").strip()
        if not mesaj:
            raise SohbetHatasi("Bos mesaj gonderilemez.")

        # Var olmayan klasor ANINDA reddedilir -- yanlis yazilmis bir yol
        # sessizce calisiyormus gibi gorunur ve ajan "bulamadim" der.
        ekler = metinler(klasorleri_dogrula(ek_klasorler))

        lider = self.orkestra._lider_sec(lider_ad, None)
        kayit = self.ofis.postane.soru_sor("insan", lider["ad"], mesaj,
                                           mod="uyandiran")
        self._akis = AkisYazici(self.db, self.proje_id, kayit["id"])

        if ekler:
            # OLCULDU: klasor acilisi yalnizca GOREV acilinca kayda
            # geciyordu. Ama lider `cevap` yolunda gorev acmaz -- klasor
            # yine de acilmisti ve hicbir yerde gorunmuyordu. Yetkinin
            # yarisi kayitli, yarisi gorunmez olmaz.
            self.ofis.db.olay_yaz(
                self.ofis.proje_id, "klasor_acildi",
                "Patron mesaji icin ofis disi klasor: " + " · ".join(ekler),
                ajan_ad="insan")

        # TARAYICI ALANI da klasor gibi: yetki INSANDAN gelir (panelde
        # kabinde oge secmek bir isaret etmedir) ve acilis kayda gecer --
        # `cevap` yolunda gorev acilmasa bile.
        web = tarayici_kaynaklari_dogrula(tarayici_alani or [])
        if web:
            self.ofis.db.olay_yaz(
                self.ofis.proje_id, "tarayici_alani",
                "Patron mesaji icin tarayici: " + " · ".join(web)
                + (" (PAYLASILAN kabin)" if tarayici_kabini else ""),
                ajan_ad="insan")

        karar = self._triyaj(lider, mesaj, butce_usd, zaman_asimi,
                             ek_klasorler=ekler)
        yield {"tur": "triyaj", "govde": karar["karar"],
               "ek": {"gerekce": karar.get("gerekce", ""),
                      "hedef": karar.get("hedef", "")}}

        # Karar bir KARARDIR: ajan kosturmamak da dahil, gerekcesiyle yazilir.
        self.ofis.bellek.karar_yaz(
            f"Patron mesaji '{mesaj[:80]}' icin yol: {karar['karar']}.",
            karar.get("gerekce") or "(gerekce verilmedi)",
            lider["ad"], tur="dagitim")

        if karar["karar"] == "cevap":
            cevap = (karar.get("cevap") or "").strip()[:CEVAP_SINIRI]
            if not cevap:
                cevap = "(Lider cevap metni vermedi.)"
            self.ofis.postane.cevapla(kayit["id"], cevap,
                                      cevaplayan=lider["ad"])
            yield {"tur": "cevap", "govde": cevap, "ek": {}}

            # Lider cevap verdi diye OFIS UYUMAZ.
            #
            # OLCULDU (19.09.2026): lider mukerrer istegi dogru yakaladi
            # ("#5 zaten cinar'da calisiyor, tekrar dagitmak jeton
            # israfi") ve *"tamamlaninca sana sunacagim"* dedi. Ama
            # `cevap` yolu halkayi dondurmuyordu: hicbir sey o isi
            # ilerletmeyecekti. Lider dogru soyledi, sistem yalanci
            # cikardi -- saglikli gorunup yanlis calisan hal.
            #
            # Bu yuzden cevap yolundan sonra da ACIK IS varsa halka
            # doner. "Lider ofisi yonetir, takip eder" demek, acik isle
            # bosta duran bir ofis olmamasi demektir.
            if self._acik_is_var():
                self._akis.not_yaz(cevap + "\n\n(açık iş var — ekip çalışıyor, "
                                   "bitince rapor buraya eklenecek)")
                self._akis.yeni_bolum("duz", sabit=cevap)
                yield {"tur": "surduruluyor", "govde":
                       "Acik is var, halka donuyor.", "ek": {}}
                for adim in self.orkestra.kos(
                        azami_tik=azami_tik, butce_usd=butce_usd,
                        zaman_asimi=zaman_asimi, paralel=paralel,
                        izinli_araclar=izinli_araclar,
                        tarayici_kabini=tarayici_kabini):
                    yield {"tur": "tik", "govde": adim.get("sebep", ""),
                           "ek": adim}
                    if adim.get("bitti"):
                        break
                rapor = self._rapor(lider, mesaj, {"gorevler": self._acik_ve_yeni()},
                                    butce_usd, zaman_asimi)
                self.ofis.postane.cevapla(kayit["id"],
                                          cevap + chr(10) * 2 + rapor,
                                          cevaplayan=lider["ad"])
                yield {"tur": "rapor", "govde": rapor, "ek": {}}

            yield {"tur": "bitti", "govde": "", "ek": {"yol": "cevap"}}
            return

        hedef = (karar.get("hedef") or mesaj).strip()

        if karar["karar"] == "kadro":
            # KADRO YETMIYOR. Lider oneri getirir ve BURADA DURUR.
            #
            # Is baslamaz: kadro kurmak patronun limitini harcar ve bu
            # bir YETKI GENISLETMESIDIR. Ayni kural klasorde de var --
            # yetki insandan gelir, dagitim liderden.
            #
            # Onay gelince is `kabuk ekip kur <no>` ile baslar; orasi
            # `konus`u yeniden cagirmaz, cunku patron onaylarken isi de
            # baslatmak isteyip istemedigine kendi karar verir.
            try:
                oneri = self.ekip.oner(
                    hedef, lider_ad=lider["ad"], butce_usd=butce_usd,
                    zaman_asimi=zaman_asimi)
            except EkipHatasi as exc:
                not_ = f"Kadro onerisi alinamadi: {exc}"
                self.ofis.postane.cevapla(kayit["id"], not_,
                                          cevaplayan=lider["ad"])
                yield {"tur": "cevap", "govde": not_, "ek": {"hata": True}}
                yield {"tur": "bitti", "govde": "", "ek": {"yol": "kadro"}}
                return

            onizleme = self.ekip.onizleme(oneri["no"])
            self.ofis.postane.cevapla(kayit["id"], onizleme,
                                      cevaplayan=lider["ad"])
            yield {"tur": "ekip_onerisi", "govde": onizleme,
                   "ek": {"no": oneri["no"], "uyeler": oneri["uyeler"],
                          "gerekce": oneri["gerekce"]}}
            yield {"tur": "bitti", "govde": "", "ek": {"yol": "kadro"}}
            return

        try:
            plan = self.orkestra.hedef_ver(
                hedef, lider_ad=lider["ad"], butce_usd=butce_usd,
                zaman_asimi=zaman_asimi, ek_klasorler=ekler,
                tarayici_alani=web or None,
                tarayici_kabin=bool(web and tarayici_kabini))
        except OrkestraHatasi as exc:
            not_ = f"Plan alinamadi: {exc}"
            self.ofis.postane.cevapla(kayit["id"], not_, cevaplayan=lider["ad"])
            yield {"tur": "cevap", "govde": not_, "ek": {"hata": True}}
            yield {"tur": "bitti", "govde": "", "ek": {"yol": "plan_hatasi"}}
            return

        self._akis.not_yaz(_KARAR_ETIKET.get(karar["karar"], karar["karar"])
                           + " — ekip çalışıyor; bitince rapor buraya düşer. ("
                           + ", ".join(f"#{g['no']} {g['sahip'] or '-'}"
                                       for g in plan["gorevler"]) + ")")
        self._akis.yeni_bolum("duz")
        yield {"tur": "plan", "govde": plan["gerekce"],
               "ek": {"bol": plan["bol"],
                      "gorevler": [{"no": g["no"], "baslik": g["baslik"],
                                    "sahip": g["sahip"]}
                                   for g in plan["gorevler"]]}}

        for adim in self.orkestra.kos(azami_tik=azami_tik, butce_usd=butce_usd,
                                      zaman_asimi=zaman_asimi, paralel=paralel,
                                      izinli_araclar=izinli_araclar,
                                      tarayici_kabini=tarayici_kabini):
            yield {"tur": "tik", "govde": adim.get("sebep", ""), "ek": adim}
            if adim.get("bitti"):
                son_adim = adim
                break

        rapor = self._rapor(lider, mesaj, plan, butce_usd, zaman_asimi)
        self.ofis.postane.cevapla(kayit["id"], rapor, cevaplayan=lider["ad"])
        yield {"tur": "rapor", "govde": rapor, "ek": {}}
        yield {"tur": "bitti", "govde": "", "ek": {"yol": karar["karar"]}}

    def _acik_is_var(self) -> bool:
        """Kosulabilecek acik is var mi? (Bekleyen degil, ILERLEYEBILIR.)"""
        return bool(self._acik_ve_yeni())

    def _acik_ve_yeni(self) -> list:
        return [g for g in self.ofis.tahta.liste()
                if g["durum"] in ("hazir", "calisiyor", "inceleme")]

    # -- ic isleyis --------------------------------------------------------

    def _triyaj(self, lider: dict, mesaj: str, butce_usd, zaman_asimi,
                ek_klasorler=()) -> dict:
        metin = self.triyaj_metni(mesaj, ek_klasorler=ek_klasorler)
        ham = self._lideri_kostur(lider, metin, butce_usd, zaman_asimi,
                                  ek_klasorler=ek_klasorler,
                                  akis=getattr(self, "_akis", None))
        karar = _json_ayikla(ham)
        if not isinstance(karar, dict) or karar.get("karar") not in (
                "cevap", "kendi", "dagit", "kadro"):
            # Bicim tutmadiysa UYDURMA: en guvenli yol, isi ajanlara
            # vermek degil PATRONA DONMEKTIR. Yanlis yorumlanmis bir
            # mesajla is acmak, olmayan bir isi baslatir.
            return {"karar": "cevap",
                    "gerekce": "Lider gecerli bir karar bicimi vermedi.",
                    "cevap": (ham or "").strip()[:CEVAP_SINIRI]
                             or "(Lider bir sey yazmadi.)"}
        return karar

    def _rapor(self, lider: dict, mesaj: str, plan: dict,
               butce_usd, zaman_asimi) -> str:
        """TEK CIKTI: kapanan isleri ve KANITLARI okuyup patrona tek cevap.

        Parcalari insana yigmak, isi insana birlestirtmektir. Rapor,
        yapilan isin INCELENMESI degildir -- inceleme zaten kanit kapisinda
        yapildi; bu yalnizca anlatmadir.
        """
        satirlar = ["# PATRONUN ISTEGI", "", mesaj, "", "# SONUC", ""]
        for g0 in plan["gorevler"]:
            g = self.ofis.tahta.gorev(g0["no"])
            satirlar.append(f"## #{g['no']} {g['baslik']} — {g['durum']}")
            satirlar.append(f"- sahip: {g['sahip'] or '-'}")
            satirlar.append(f"- kabul olcutu: {g['kabul_olcutu']}")
            for k in self.ofis.tahta.kanitlar(g["no"]):
                satirlar.append(f"- KANIT [{k['tur']}] {k['baslik']}: "
                                f"{(k['icerik'] or '')[:200]}")
            satirlar.append("")

        bekleyen = (self.ofis.postane.insan_bekleyenler()
                    + self.ofis.postane.bekleyen_onaylar())
        if bekleyen:
            satirlar.append("# SANA DUSEN (is bunlar olmadan ilerlemiyor)")
            for b in self.ofis.postane.insan_bekleyenler():
                satirlar.append(f"- {b['gonderen']} soruyor: {b['govde']}")
            for b in self.ofis.postane.bekleyen_onaylar():
                satirlar.append(f"- {b['isteyen']} onay istiyor: {b['eylem']}")
            satirlar.append("")

        satirlar += [
            "---",
            "",
            "Yukaridakileri patrona **tek bir cevap** olarak yaz.",
            "",
            "- Turkce, kisa, net. Madde madde yazabilirsin.",
            "- Ne ISTENDI, ne YAPILDI, KANITI ne -- bu ucu gecir.",
            "- Kapanmayan ya da beklemede kalan is varsa ACIKCA soyle.",
            "- KANIT UYDURMA: yukarida yazmayan bir sonucu yazma.",
            "- Ic isleyisi (gorev numarasi, kilit, revizyon) anlatma;",
            "  patron sonucu ister, defteri degil.",
        ]
        ham = self._lideri_kostur(lider, "\n".join(satirlar),
                                  butce_usd, zaman_asimi,
                                  akis=getattr(self, "_akis", None))
        metin = (ham or "").strip()[:CEVAP_SINIRI] or "(Lider rapor yazmadi.)"
        return metin + self._gercek_durum(plan)

    def _gercek_durum(self, plan: dict) -> str:
        """Raporun sonuna HESAPLANAN gercegi ekler.

        OLCULDU (19.09.2026): lider raporu *"tamamlandi... Bekleyen is
        yok"* dedi -- oysa is hala INCELEMEDEYDI ve kapanmamisti. Rapor
        talimatinda "kapanmayan is varsa ACIKCA soyle" yaziyordu; model
        uymadi.

        Cozum talimati sertlestirmek DEGIL. Ofisin ZATEN BILDIGI bir
        olguyu modelden istemek, uydurmaya kapi acmaktir. Bu satirlar
        tahtadan okunur, model onlara dokunamaz ve abartamaz.

        Ayni ilke panelde de var: "motor rozetleri olculur, bos terminal
        'cikti yok' der". Ofis uydurmaz -- anlatan model olsa bile
        SAYILAR ofisten gelir.
        """
        satirlar = []
        acik = []
        for g0 in plan.get("gorevler") or []:
            try:
                g = self.ofis.tahta.gorev(g0["no"])
            except Exception:
                continue
            kanit = len(self.ofis.tahta.kanitlar(g["no"]))
            if g["durum"] not in ("bitti", "iptal"):
                acik.append((g, kanit))
            satirlar.append(f"- #{g['no']} {g['baslik']}: **{g['durum']}** "
                            f"({kanit} kanit)")

        bekleyen = (self.ofis.postane.insan_bekleyenler()
                    + self.ofis.postane.bekleyen_onaylar())
        if not satirlar and not bekleyen:
            return ""

        parca = [chr(10) * 2, "---", "", "**Defterden (ofis yazdi, lider degil):**", ""]
        parca += satirlar
        if acik:
            parca.append("")
            parca.append(
                f"**{len(acik)} is HENUZ KAPANMADI.** Kapanmayan is, "
                "yapilmamis is degildir ama BITMIS de degildir -- kanit "
                "kapisi ondan gecmedi.")
        if bekleyen:
            parca.append("")
            parca.append(f"**{len(bekleyen)} istek SENI bekliyor.** "
                         "`python -m ofis.kabuk bekleyen`")
        return chr(10).join(parca)

    def _lideri_kostur(self, lider: dict, metin: str, butce_usd,
                       zaman_asimi, ek_klasorler=(), akis=None) -> str:
        """Lideri TEMIZ oturumda, YAZMA YETKISI VERMEDEN kosturur.

        Kosumu Orkestra ile PAYLASIR, kopyalamaz. Iki ayri kopya olsaydi
        biri duzeltilip oteki unutulurdu -- bu projede tam bu yuzden iki
        kez ayni hata cikti (motor listesi, kanit sayaci). Triyaj ve rapor
        birer YARGI isidir; yazma acik olsaydi lider "madem buradayim,
        sunu da duzeltivereyim" diyebilir ve is tahtaya hic girmeden,
        kanitsiz ve incelenmeden yapilmis olurdu.
        """
        try:
            return self.orkestra._lideri_kostur(
                lider, metin, butce_usd, zaman_asimi,
                ek_klasorler=ek_klasorler, akis=akis)
        except OrkestraHatasi as exc:
            raise SohbetHatasi(str(exc)) from exc
