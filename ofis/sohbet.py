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

import re
import threading
import time

from . import baglayici, gorsel, roller
from .motor import motor_ac
from .ekip import Ekip, EkipHatasi
from .klasor import klasorleri_dogrula, metinler
from .tarayici import kaynaklari_dogrula as tarayici_kaynaklari_dogrula
from .orkestra import Orkestra, OrkestraHatasi, _json_ayikla
from .lider import ARAC_SUSKUNLUGU

#: Triyajda lidere gosterilecek son konusma sayisi. Az tutuluyor:
#: sohbetin tamami her mesajda tasinirsa maliyet dogrusal buyur ve
#: dikkat dagilir. Lider daha fazlasina ihtiyac duyarsa ofis durumu
#: zaten taze sorguyla onunde.
GECMIS_ADEDI = 6

#: Tek bir cevabin ustunde durulacak uzunluk. Daha uzunu sohbet degil
#: rapordur; rapor zaten is bitiminde ayrica uretilir.
CEVAP_SINIRI = 4000
#: Liderin aracsiz triyajinda "bakamiyorum" demesi (bkz. `_konus`). Bilgi
#: eksikligi ("bilmiyorum") DEGIL, ARAC eksikligi kalibi: acamiyorum,
#: bakamiyorum, erisemiyorum, dogrulayamiyorum, goremiyorum, alamiyorum.
#: 01.10: gecmis zaman ("yazamadim") ve YAZMA fiilleri de (gercek set G05,
#: claude: lider CSV'yi okuyup hesapladi ama "rapor.md'yi yazamadim" dedi).
YAPAMAM_CEVABI = re.compile(
    r"(?:a[cç]|bak|eri[sş]|do[gğ]rula|g[oö]r|al|kontrol ed|[cç]al[iı][sş]t[iı]r"
    r"|yaz|olu[sş]tur|kayded|g[oö]nder|y[uü]kle|indir|d[uü]zenle|d[uü]zelt)"
    r"(?:a|e|ya|ye)m(?:[iı]yorum|ad[iı]m|ed[iı]m)"
    # 01.10 (G08, codex): "yazma izni yok ... gorevi yeniden baslatin"
    r"|(?:yazma |dosya |arac )?izn?[iı] yok|yetkim yok|yeniden ba[sş]lat[iı]n", re.I)

#: "ANLATTI, YAPMADI" KORUMASI (03.10.2026, gercek set G05, claude, tek tur
#: triyaj): "satislar.csv'deki ciroyu bul; rapor.md dosyasina YAZ, sonucu bana
#: da soyle" -> lider CSV'yi okudu, sonucu `cevap` ile soyledi; rapor.md HIC
#: yazilmadi. Istemde "anlatma, yaptir" kurali VARDI (30.09 G04'te de ayni
#: sinif). Rica ile duran kural, kural degildir: mesaj YAZMA istiyor ve adi
#: gecen dosya projede YOKSA cevap patrona gitmez, is ajana verilir.
YAZMA_FIILI = re.compile(
    r"\b(?:yaz|olu[sş]tur|kaydet|haz[iı]rla|[cç][iı]kar|d[uü]zenle|ekle|g[uü]ncelle"
    r"|d[uü]zelt|kur|yap)", re.I)
DOSYA_ADI = re.compile(
    r"(?<![\w/\\.-])((?:[\w.-]+[/\\])*[\w-]+\.(?:md|txt|html?|css|js|ts|tsx|jsx|py|json"
    r"|csv|xlsx?|docx?|pdf|pptx?|png|jpe?g|svg|yml|yaml|toml|ini|sql|sh|bat|ps1))\b", re.I)


def yazilacak_dosyalar(mesaj: str, kok) -> list:
    """Mesajin YAZILMASINI istedigi ve projede henuz OLMAYAN dosyalar.

    Yazma fiili yoksa bos doner (soru: "rapor.md nerede?" cevap yoludur).
    Var olan dosya sayilmaz: "satislar.csv'yi oku" girdi dosyasidir.
    """
    from pathlib import Path as _P
    if not mesaj or not YAZMA_FIILI.search(mesaj):
        return []
    kok = _P(str(kok or "")).expanduser() if kok else None
    eksik = []
    for ad in dict.fromkeys(m.group(1) for m in DOSYA_ADI.finditer(mesaj)):
        if kok is None or not (kok / ad).exists():
            eksik.append(ad)
    return eksik


def _hazir_plan(karar: dict):
    """Triyajdaki plan (tek tur). IZINLER ust duzeye yazildiysa plana tasinir.

    OLCULDU (03.10.2026, gercek set G14, karma, iki kosu): lider gerekcede
    "gonderme adimi patronun acik izni" yazdi ama izin plana girmedi -- tek
    turda plan ic ice bir alan; `izinler` cevabin USTUNE yazilinca ofis
    gormuyordu ve form gonderilmeden is patrona soruldu. Tasinan izin yine
    ayni kapidan (patronun sozune karsi alinti) gecer.
    """
    plan = karar.get("plan") if isinstance(karar.get("plan"), dict) else None
    if plan is None:
        return None
    ust = karar.get("izinler")
    if ust and not plan.get("izinler"):
        plan = dict(plan, izinler=ust)
    return plan


def _zaman_blogu(ofis) -> str:
    from datetime import datetime
    from . import zamanlayici as _z
    an = datetime.now().astimezone()
    satir = [f"# ZAMAN\n\nSimdi (patronun yerel saati): {an:%Y-%m-%d %H:%M}, "
             f"{_z.GUNLER[an.weekday()]}."]
    blok = _z.triyaj_blogu(ofis)
    if blok:
        satir += ["", blok]
    return "\n".join(satir)


def _zamanla(ofis, karar: dict, lider_ad: str, mesaj: str) -> str:
    """`karar=zamanla` -> kaydet ya da iptal et; cevabi OFIS kurar.

    Lider zamani YAPI olarak verir, ofis dogrular. Cevap metni de ofisten:
    "her gun 09:00, ilki yarin 09:00" defterdeki gercek kayittir -- liderin
    serbest cumlesi kayitla celisebilirdi (soyledigi saat ile kaydedilen).
    """
    from . import zamanlayici as _z
    zaman = karar.get("zaman") or {}
    try:
        if isinstance(zaman, dict) and zaman.get("tur") == "iptal":
            r = _z.iptal(ofis, zaman.get("no"))
            return f"Tamam, Z{r['no']} iptal edildi: «{r['metin'][:100]}». Artık çalışmayacak."
        z = _z.ekle(ofis, (karar.get("hedef") or mesaj).strip(), lider_ad, zaman)
    except _z.ZamanHatasi as exc:
        return (f"Zamanı kaydedemedim: {exc} Ne zaman yapılsın? Örnek: 'her gün 09:00'da', "
                "'pazartesi ve perşembe 14:00'te', 'yarın 10:30'da bir kez', 'her 30 dakikada'.")
    return (f"Tamam, zamanladım (Z{z['no']}): {_z.insan_metni(z['kural'])} — «{z['metin'][:120]}». "
            f"İlk çalışma: {_z.an_metni(z['sonraki'])}. Vakti gelince sıraya girer, sonucu buraya "
            "yazarım. İptal için 'Z" + str(z['no']) + "'yi iptal et' demen yeter.")


#: Lider de sohbete dosya gonderir (30.09): satiri ofis `ekler/`e tasir.
EK_KURALI = ("Patrona bir DOSYA gostermek istersen (gorsel, pdf, video; "
             "orn. bir ajanin urettigi), cevabina AYRI SATIRDA `[ek] <proje "
             "kokune gore yol>` yaz; ofis onu sohbete ekler. Var olmayan "
             "dosya UYDURMA.")


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

#: Patrona akan satirin basi. 30.09.2026: once "kendim yapiyorum — <GEREKCE>"
#: akiyordu; kullanici "niye boyle cevap veriyor" dedi -- gerekce ("bolunmez,
#: ~15 kat jeton, yapan inceleyemez") liderin ic muhasebesi, patrona degil
#: karar gunlugune yazilir (zaten yaziliyor). Patron NE yapilacagini gorur:
#: `hedef`. Hedef JSON'da gerekceden SONRA geldigi icin o gelene kadar
#: yalniz etiket akar.
_KARAR_ETIKET = {"kendi": "Bu işi ben yapıyorum",
                 "dagit": "Bu işi ekibe dağıtıyorum",
                 "kadro": "Bu iş için kadroya yeni bir ajan öneriyorum",
                 "cevap": "Cevaplıyorum",
                 "zamanla": "Bunu zamanlıyorum"}


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
    hedef, _ = _kismi_alan(govde, "hedef")
    bas = _KARAR_ETIKET.get(karar, karar)
    return (bas + (": " + hedef.strip() if hedef and hedef.strip() else "…")).strip()


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


def durum_yazisi(g: dict) -> str:
    """Liderin gordugu is durumu. DURAKLATILAN is ayrica soylenir.

    OLCULDU (02.10.2026, sinama paneli): patron calisan isi duraklatti, is
    `hazir`a dondu; lider raporunda *"is hazir diye isaretlenmis ama dosya
    yok, bitmis sayilmaz"* yazdi -- patronun kendi istegini ariza sandi.
    """
    if g.get("duraklatildi"):
        return f"{g['durum']} -- PATRON DURAKLATTI (Surdur'e basinca devam eder; ariza degil)"
    return g["durum"]


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

    def ofis_ozeti(self, kanat_id=None) -> str:
        """Liderin SU ANKI ofis goruntusu -- her mesajda TAZE uretilir.

        Elle tutulan bir ozet bayatlar; bu sorgudur, bayatlayamaz.
        Liderin "her seyi bilir, takip eder" olmasi buradan gelir.
        """
        satirlar = []
        # KUNYE ONCE: patronun mesajini "kapsam disi" bilmeden triyaj
        # etmek, yapilmayacak bir isi dagitmanin en kisa yolu.
        # TAKIM GOZU (06.10.2026): lider yalniz kendi takiminin (+ ortak)
        # hafizasini gorur. Takimsiz cagri (eski yol) yalniz ORTAGI gorur.
        bel = self.ofis.bellek.kapsam(kanat_id or "")
        kunye = self.ofis.brifing.kunye_ozeti(kanat_id or "")
        if kunye:
            satirlar += [kunye, ""]
        kadro = self.ofis.kadro.liste()
        # COK TAKIM (01.10.2026): lider KENDI takimini gorur; obur takimlar
        # sonda tek satirla anilir (karismasin, ama varliklarini bilsin).
        takim = (lambda g: self.orkestra.takimin_isi(g, kanat_id))
        takimdaki = {a["ad"] for a in kadro if not kanat_id or a["kanat_id"] == kanat_id}
        isciler = [a for a in kadro if not a["lider_mi"] and a["ad"] in takimdaki]
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
                if g["durum"] in ("bekliyor", "hazir", "calisiyor", "inceleme")
                and takim(g)]
        satirlar.append("")
        if acik:
            satirlar.append("### Acik isler")
            for g in acik:
                kanit = len(self.ofis.tahta.kanitlar(g["no"]))
                satirlar.append(f"- #{g['no']} [{durum_yazisi(g)}] {g['baslik']} "
                                f"— {g['sahip'] or 'atanmadi'} — {kanit} kanit")
        else:
            satirlar.append("### Acik is yok.")
        # KAPANAN / IPTAL EDILEN ISLER (01.10.2026 OLCULDU): lider 30.09'da
        # "#37 kapandi" dedi; is sonra dort kez IPTAL edildi, rapor dosyasi
        # hic yazilmadi. Lider sohbet gecmisinden kendi eski sozunu okuyup
        # "#37 raporu hazir bekliyor" demeyi 4 sohbet boyunca surdurdu.
        # Ozet yalniz ACIK isleri gosteriyordu; DEFTERIN hukmu lidere hic
        # ulasmiyordu.
        _son = [g for g in self.ofis.tahta.liste() if g["durum"] in ("bitti", "iptal")
                and takim(g)]
        _son.sort(key=lambda g: g.get("guncellendi") or "", reverse=True)
        if _son:
            satirlar += ["", "### Son kapanan / iptal edilen isler (DEFTER -- sohbet "
                         "gecmisinde baska bir sey yaziyorsa DEFTER dogrudur)"]
            for g in _son[:8]:
                if g["durum"] == "iptal":
                    satirlar.append(f"- #{g['no']} IPTAL EDILDI -- sonucu YOK, "
                                    f"patrona 'hazir' diye sunma: {g['baslik']}")
                else:
                    kanit = len(self.ofis.tahta.kanitlar(g["no"]))
                    satirlar.append(f"- #{g['no']} bitti ({kanit} kanit): {g['baslik']}")

        sorular = [b for b in self.ofis.postane.insan_bekleyenler() if b["gonderen"] in takimdaki]
        onaylar = [b for b in self.ofis.postane.bekleyen_onaylar() if b["isteyen"] in takimdaki]
        if sorular or onaylar:
            satirlar += ["", "### INSANDAN BEKLENENLER (is ilerlemiyor)"]
            for b in sorular:
                satirlar.append(f"- {b['gonderen']} soruyor: {b['govde'][:160]}")
            for b in onaylar:
                satirlar.append(f"- {b['isteyen']} onay istiyor: {b['eylem'][:160]}")

        olgular = bel.gecerli_olgular()
        if olgular:
            satirlar += ["", "### Gecerli bilgiler"]
            for o in olgular[:25]:
                satirlar.append(f"- {o['konu']}: {o['icerik']}")
            if len(olgular) > 25:
                satirlar.append(f"- _(+{len(olgular) - 25} bilgi daha)_")

        kararlar = bel.son_kararlar(6)
        if kararlar:
            satirlar += ["", "### Son kararlar (BAGLAYICI)"]
            for k in kararlar:
                satirlar.append(f"- {k['veren']}: {k['karar']}")
        if kanat_id:
            with self.ofis.db.baglanti() as c:
                obur = c.execute("SELECT id, ad FROM kanat WHERE proje_id = ? AND id != ? "
                                 "ORDER BY ad", (self.ofis.proje_id, kanat_id)).fetchall()
            if obur:
                satirlar += ["", "### Obur takimlar (SENIN DEGIL -- islerine karisma, "
                             "isleri o takimin lideri yurutur)"]
                for k in obur:
                    n = sum(1 for g in self.ofis.tahta.liste(k["id"])
                            if g["durum"] in ("bekliyor", "hazir", "calisiyor", "inceleme"))
                    satirlar.append(f"- {k['ad']}: {n} acik is")
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

    def triyaj_metni(self, mesaj: str, *, ek_klasorler=(), kanat_id=None,
                     plan_bolumu: bool = True) -> str:
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
            self.ofis_ozeti(kanat_id),
            "",
            # ZAMAN (01.10.2026, F5/4): "yarin 10:30" demek icin lider
            # bugunun tarihini ve gununu GORMELI -- yoksa uydurur.
            _zaman_blogu(self.ofis),
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

        # BELGELER (06.10.2026, E77): patron "iade politikamiz ne diyor"
        # diye sorabilmeli; lider belgeden KAYNAGIYLA cevaplar.
        from .belge import kaynakli_blok
        _belge = kaynakli_blok(self.db, self.proje_id, mesaj,
                               baslik="PATRONUN BELGELERI", kanat=kanat_id or "")
        if _belge:
            satirlar += ["", _belge.replace("## ", "# ", 1)]

        gecmis = self.gecmis()
        if gecmis:
            satirlar += ["", "# SON KONUSMALAR", ""]
            for g in gecmis:
                satirlar.append(f"- patron: {g['govde'][:200]}")
                if g["cevap"]:
                    satirlar.append(f"  sen: {g['cevap'][:200]}")

        # AJANLARIN ELINDEKILER (30.09.2026). OLCULDU, iki motorda da:
        # "example.com'u ac, ekran goruntusu at" -> lider 'cevap' yolunu
        # secip "bu oturumda acamiyorum, sen at" dedi; is hic acilmadi.
        # Lider KENDI araçsiz triyaj turunu ofisin siniri sandi. Plan
        # isteminde bu bolum vardi, triyajda yoktu.
        satirlar += [
            "",
            "# AJANLARININ ELINDEKILER",
            "",
            "Senin bu turun aracsiz; AJANLARIN degil. Ajanlar terminaldeki "
            "Claude Code / Codex gibi calisir: TARAYICIYLA siteye gider, "
            "tiklar, form doldurur, sayfanin ekran goruntusunu alir ve "
            "sohbete gonderir; kod yazar, komut kosturur, dosya/gorsel "
            "uretir, arastirir. Bunlardan birini gerektiren mesaja "
            "'yapamam / sen yap' diye CEVAP VERME -- `kendi` ya da `dagit` sec.",
            # 30.09 olculdu (gercek set G04, claude): "testler kirmizi,
            # hatayi duzelt" -> lider `cevap` secip hatanin nerede oldugunu
            # ve nasil duzeltilecegini ANLATTI; dosyaya dokunulmadi.
            "Patron bir seyin YAPILMASINI istiyorsa (duzelt, yaz, yap, ac, "
            "gonder, kur, degistir) NASIL yapilacagini anlatma -- YAPTIR. "
            "`cevap` yalniz soru, bilgi ve sohbet icindir.",
        ]

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
            "**zamanla** — Patron isin ILERIDE ya da TEKRAR TEKRAR yapilmasini",
            "  istiyor ('her sabah 9'da', 'pazartesi 14:00'te', 'yarin 10:30'da',",
            "  'her 30 dakikada'), ya da kayitli bir zamanli isi iptal ettiriyor.",
            "  Isi SIMDI yapma; ofis kaydeder, vakti gelince sana getirir.",
            "  `zaman` alanini YAPI olarak ver (asagida). Saati uydurma: patron",
            "  saat soylemediyse `cevap` ile sor.",
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
            '  "hedef": "karar=kendi, dagit ya da kadro ise isin tek cumlelik hedefi",',
            '  "plan": "karar=kendi ya da dagit ise ZORUNLU -- asagidaki PLAN bolumundeki JSON"',
            "}",
            "```",
            "",
            # 06.10.2026 (E31): patronun sohbette soyledigi KALICI bilgi
            # hicbir yere yazilmiyordu. Lider ONERIR; patron "Yaz" der.
            "ISTEGE BAGLI `bilgi` alani (her kararda): patron BU MESAJDA "
            "projeye ya da kendine dair KALICI bir bilgi SOYLEDIYSE (fiyat, "
            "adres, sure, hesap adi, bir TERCIHI -- 'iade suresi 30 gun', "
            "'raporlari hep Excel isterim') en fazla 3 oneri: "
            '`"bilgi": [{"konu": "kisa ad", "icerik": "deger", "alinti": '
            '"patronun mesajindan KELIMESI KELIMESINE parca"}]`. '
            "Soru, istek ya da gecici sey bilgi DEGILDIR; yoksa alani yazma. "
            "Ofis patrona 'hafizaya yazayim mi' diye sorar.",
            "",
            "karar=zamanla ise `hedef` = vakti gelince yapilacak is (patronun",
            "sozuyle, zaman ifadesi CIKARILMIS), ve `zaman` su bicimlerden biri:",
            '`{"tur": "gunluk", "saat": "09:00"}` · '
            '`{"tur": "haftalik", "saat": "14:00", "gunler": [0, 3]}` (0=pazartesi .. 6=pazar) · '
            '`{"tur": "bir_kez", "tarih": "2026-10-02", "saat": "10:30"}` · '
            '`{"tur": "aralik", "dakika": 30}` (en az 15). '
            'Iptal icin: `{"tur": "iptal", "no": 2}` (ZAMANLANMIS ISLER listesindeki Z numarasi).',
            "",
            "Kurallar:",
            "- `gerekce` bos olamaz. Ajan kosturmamak da bir karardir.",
            "- `karar=cevap` ise `cevap` dolu olmali; Turkce ve net yaz.",
            # 05.10.2026, patron: "ortada hicbir sey yokken neden bu kadar uzun
            # cevap yazdi" -- "naber"e baglayicilari, para kilidini, ofis
            # durumunu saydi. Ozeti GORMEK onu SAYMAK icin degil.
            "- `cevap` KISA olsun: selamlasma ve kucuk sohbete 1-2 cumle. Patron",
            "  sormadikca baglayici, para kilidi, kadro ya da ofis durumu SAYMA;",
            "  ayrintiyi ancak patron isterse ya da isin icin gerekliyse yaz.",
            "- `karar=kendi`, `dagit` ya da `kadro` ise `hedef` dolu olmali.",
            "- `karar=kendi` ya da `dagit` ise `plan` dolu olmali (ayni cevapta;",
            "  ayri bir planlama turu YOK). Oteki kararlarda `plan` yazma.",
            "- `karar=kadro` yalnizca kadroda OLMAYAN bir rol gerektiginde.",
            "  Kadroyu SEN kuramazsin -- onerirsin, patron onaylar.",
            "- Bilmedigin bir seyi UYDURMA. Bilmiyorsan `cevap` ile soyle,",
            "  ya da ogrenmek icin `dagit` ile arastirma isi ac.",
            "- " + EK_KURALI,
        ]
        if plan_bolumu:
            # TEK TUR (03.10.2026, "ofis carpani" olcumu): triyaj ve plan
            # ayri turdu; liderin her turu ~12-24 bin jetonluk on eki 1
            # saatlik onbellege bastan yaziyor (Claude Code'un davranisi,
            # duz `claude -p`de de olculdu). Plan ayni cevapta gelir; ayni
            # kapilardan gecer, gecmezse eski yola (plan turu) duser.
            satirlar += [
                "",
                "---",
                "",
                "# PLAN (yalniz karar=kendi ya da dagit ise)",
                "",
                self.orkestra.plan_metni(
                    "Patronun mesaji (en ustte). `hedef` alanina yazdigin cumle.",
                    kanat_id, ek_klasorler=ek_klasorler, patron_sozu=mesaj,
                    ic_ice=True),
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
               tarayici_alani=None, tarayici_kabini: str = "",
               atanan: str = "", kaynak: str = "", ara_ver=None):
        # ARA VER (09.10.2026, F1 canli: doviz istegi, kargo isi 2 saat donerken
        # SIRADA BEKLEDI -- sira, onceki istegin isi BITMEDEN sonrakine
        # gecmiyordu). `ara_ver()` True donerse halka her adimdan sonra birakilir:
        # isler kapanmaz, sonraki istegin halkasi HEPSINI birlikte surdurur;
        # bu istegin ozeti isler bitince ofisin modelsiz cevabiyla gelir
        # (`kuyruk.askida_kalanlari_kapat`).
        self._ara_ver = ara_ver
        mesaj = (mesaj or "").strip()
        if not mesaj:
            raise SohbetHatasi("Bos mesaj gonderilemez.")

        # Var olmayan klasor ANINDA reddedilir -- yanlis yazilmis bir yol
        # sessizce calisiyormus gibi gorunur ve ajan "bulamadim" der.
        ekler = metinler(klasorleri_dogrula(ek_klasorler))

        lider = self.orkestra._lider_sec(lider_ad, None)
        # Patronun eki ISI YAPACAK takimin klasorunde olsun (08.10.2026).
        from . import ekler as _ek
        _ek.takima_getir(self.ofis, mesaj, lider.get("kanat_id"))
        atanan = (atanan or "").strip()
        if atanan:
            # TAKIM SOHBETI: `@ad is: ...`. Is yine LIDERIN planindan
            # gecer (olcut, yazma alani, kanit kapisi); yalniz KIMIN
            # yapacagi patronun. Ajan var mi, isci mi -- burada olculur,
            # plan kapisina kalmasin (orada her deneme bir lider turu).
            try:
                hedef_ajan = self.ofis.kadro.ajan(atanan)
            except Exception:
                adlar = ", ".join(a["ad"] for a in self.ofis.kadro.liste())
                raise SohbetHatasi(f"'{atanan}' diye bir ajan yok. Ajanlar: {adlar}")
            if hedef_ajan["lider_mi"]:
                raise SohbetHatasi(
                    f"{atanan} lider: lider is DAGITIR ve inceler, isi isci yapar. "
                    "Isi lidere dogrudan yaz (@ olmadan).")
            if hedef_ajan["kanat_id"] != lider["kanat_id"]:
                raise SohbetHatasi(
                    f"{atanan} bu liderin takiminda degil; isi kendi takiminin "
                    "liderine ver.")
        kayit = self.ofis.postane.soru_sor(
            "insan", lider["ad"],
            (f"@{atanan} is: {mesaj}" if atanan else mesaj), mod="uyandiran",
            kaynak=kaynak)
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

        if atanan:
            # Triyaj SORULMAZ: patron bunun bir IS oldugunu ve kimin
            # yapacagini soyledi. Bir lider turu (9-27 sn) kazanilir ve
            # "cevap" yoluna dusup isin hic acilmamasi riski kalkar.
            karar = {"karar": "dagit",
                     "gerekce": f"Patron isi takim sohbetinde dogrudan "
                                f"@{atanan}'a verdi.",
                     "hedef": mesaj}
        else:
            karar = self._triyaj(lider, mesaj, butce_usd, zaman_asimi,
                                 ek_klasorler=ekler)
        # "BAKAMIYORUM" CEVABI PATRONA GITMEZ -- YAPI, RICA DEGIL (30.09.2026).
        # Olculdu (gercek set G09, codex, araliki): "sayfadaki fiyat ne?" ->
        # lider `cevap` secip "bu turda sayfayi acip dogrulayamiyorum" dedi;
        # istemde "yapamam deme, dagit" kurali VARDI. Liderin triyaj turu
        # aracsizdir, ajanlarinki degil: ofis cevabi patrona gondermek
        # yerine isi bir ajana verir ve bunu kayda gecirir.
        if (karar.get("karar") == "cevap"
                and YAPAMAM_CEVABI.search(karar.get("cevap") or "")):
            self.ofis.db.olay_yaz(
                self.ofis.proje_id, "uyari",
                "Lider 'bakamiyorum/acamiyorum' diye cevapladi; ofis cevabi "
                "patrona gondermedi, isi ajana verdi.", ajan_ad=lider["ad"])
            karar = {**karar, "karar": "dagit", "hedef": mesaj,
                     "gerekce": (karar.get("gerekce") or "")
                     + " [ofis: aracsiz triyaj 'yapamam' dedi -> ajana verildi]"}
        if karar.get("karar") == "cevap":
            _eksik = yazilacak_dosyalar(
                mesaj, self.ofis.tahta.kok_klasor(lider.get("kanat_id") or None).strip())
            if _eksik:
                self.ofis.db.olay_yaz(
                    self.ofis.proje_id, "uyari",
                    "Lider yazilmasi istenen dosyayi yazdirmadan cevapladi ("
                    + ", ".join(_eksik) + "); ofis cevabi patrona gondermedi, "
                    "isi ajana verdi.", ajan_ad=lider["ad"])
                karar = {**karar, "karar": "dagit", "hedef": mesaj,
                         "gerekce": (karar.get("gerekce") or "")
                         + " [ofis: istenen dosya yazilmadi -> ajana verildi]"}
        yield {"tur": "triyaj", "govde": karar["karar"],
               "ek": {"gerekce": karar.get("gerekce", ""),
                      "hedef": karar.get("hedef", "")}}
        # HAFIZA ONERISI (06.10.2026, E31): patronun soyledigi kalici bilgi
        # kart olur; kapi (alinti, uzunluk, koruma) bellekte. Patlamasi
        # sohbeti durdurmaz -- oneri bir kolaylik, kapi degil.
        if karar.get("bilgi"):
            try:
                self.ofis.bellek.kapsam(lider.get("kanat_id") or "").sohbet_onerileri(
                    karar.get("bilgi"), mesaj, oneren=lider["ad"])
            except Exception as exc:          # noqa: BLE001
                self.ofis.db.olay_yaz(self.ofis.proje_id, "uyari",
                                      f"Hafiza onerisi islenemedi: {exc}",
                                      ajan_ad=lider["ad"])

        # Karar bir KARARDIR: ajan kosturmamak da dahil, gerekcesiyle yazilir.
        self.ofis.bellek.karar_yaz(
            f"Patron mesaji '{mesaj[:80]}' icin yol: {karar['karar']}.",
            karar.get("gerekce") or "(gerekce verilmedi)",
            lider["ad"], tur="dagitim", kanat_id=lider.get("kanat_id") or "")

        if karar["karar"] == "cevap":
            cevap = (karar.get("cevap") or "").strip()[:CEVAP_SINIRI]
            if not cevap:
                cevap = "(Lider cevap metni vermedi.)"
            cevap = self._ekleri_hazirla(cevap, lider["ad"])
            cevap += self._bayat_hatirlatma(lider.get("kanat_id"))
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
            if self._acik_is_var(lider.get("kanat_id")):
                self._akis.not_yaz(cevap + "\n\n(açık iş var — ekip çalışıyor, "
                                   "bitince rapor buraya eklenecek)")
                self._akis.yeni_bolum("duz", sabit=cevap)
                yield {"tur": "surduruluyor", "govde":
                       "Acik is var, halka donuyor.", "ek": {}}
                ara = False
                for adim in self.orkestra.kos(
                        azami_tik=azami_tik, butce_usd=butce_usd,
                        zaman_asimi=zaman_asimi, paralel=paralel,
                        izinli_araclar=izinli_araclar,
                        tarayici_kabini=tarayici_kabini,
                        kanat_id=lider.get("kanat_id")):
                    yield {"tur": "tik", "govde": adim.get("sebep", ""),
                           "ek": adim}
                    if adim.get("bitti"):
                        break
                    if self._ara_var_mi():
                        ara = True
                        break
                if ara:
                    self.ofis.postane.cevapla(kayit["id"], cevap, cevaplayan=lider["ad"])
                    yield {"tur": "ara", "govde": "Sirada yeni istek var; isler suruyor.", "ek": {}}
                    yield {"tur": "bitti", "govde": "", "ek": {"yol": "cevap", "ara": True}}
                    return
                rapor = self._rapor(lider, mesaj,
                                    {"gorevler": self._acik_ve_yeni(lider.get("kanat_id"))},
                                    butce_usd, zaman_asimi)
                self.ofis.postane.cevapla(kayit["id"],
                                          cevap + chr(10) * 2 + rapor,
                                          cevaplayan=lider["ad"])
                yield {"tur": "rapor", "govde": rapor, "ek": {}}

            yield {"tur": "bitti", "govde": "", "ek": {"yol": "cevap"}}
            return

        if karar["karar"] == "zamanla":
            cevap = _zamanla(self.ofis, karar, lider["ad"], mesaj)
            self.ofis.postane.cevapla(kayit["id"], cevap, cevaplayan=lider["ad"])
            yield {"tur": "cevap", "govde": cevap, "ek": {}}
            yield {"tur": "bitti", "govde": "", "ek": {"yol": "zamanla"}}
            return

        hedef = (karar.get("hedef") or mesaj).strip()
        # EKLER ise TASINIR: lider hedefi yeniden yazarken dosya satirlarini
        # dusurebilir; isi yapacak ajan dosyanin yerini bilmeli.
        from .ekler import ajan_notu, ayikla
        _, _yollar = ayikla(mesaj)
        if _yollar and not all(y in hedef for y in _yollar):
            hedef += "\n\n" + ajan_notu(_yollar)

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
                    zaman_asimi=zaman_asimi, patron_mesaji=mesaj)
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

        _hp = _hazir_plan(karar)
        if _hp is not None and karar.get("izinler") and _hp.get("izinler") is karar.get("izinler"):
            self.ofis.db.olay_yaz(self.ofis.proje_id, "uyari",
                                  "Lider izinleri planin DISINA yazdi; ofis plana tasidi "
                                  "(gecerliligi patronun sozune karsi yine olculur).",
                                  ajan_ad=lider["ad"])
        try:
            plan = self.orkestra.hedef_ver(
                hedef, lider_ad=lider["ad"], butce_usd=butce_usd,
                zaman_asimi=zaman_asimi, ek_klasorler=ekler,
                tarayici_alani=web or None,
                tarayici_kabin=bool(web and tarayici_kabini),
                atanan=atanan, patron_sozu=mesaj,
                # Plan yalniz kendi/dagit yoluna gelir (oteki yollar yukarida
                # dondu); gecersizse plan turu ret metniyle kosar.
                hazir_plan=_hp)
        except OrkestraHatasi as exc:
            plan = None
            not_ = f"Plan alinamadi: {exc}"
            self.ofis.postane.cevapla(kayit["id"], not_, cevaplayan=lider["ad"])
            yield {"tur": "cevap", "govde": not_, "ek": {"hata": True}}
            yield {"tur": "bitti", "govde": "", "ek": {"yol": "plan_hatasi"}}
            return
        # ISLER ISTEGE BAGLANIR: sohbet adimlari bu mesajin altinda toplar.
        try:
            with self.ofis.db.baglanti() as _c:
                for _g in plan.get("gorevler") or []:
                    _c.execute("UPDATE gorev SET istek_id = ? WHERE proje_id = ? AND no = ?",
                               (kayit["id"], self.ofis.proje_id, _g["no"]))
        except Exception:                # noqa: BLE001 -- gosterim icin; is durmaz
            pass

        # ON TAHMIN (06.10.2026, E74): karneden sure / jeton / kota yuzdesi;
        # bilinmiyorsa BILINMIYOR der. Tahmin deftere, kapanista gercekle yan yana.
        _tahmin_satiri = ""
        try:
            from . import tahmin as _tahmin
            _parca = []
            for g in plan["gorevler"]:
                _a = self.ofis.kadro.ajan(g["sahip"]) if g.get("sahip") else None
                if not _a:
                    continue
                _gg = self.ofis.tahta.gorev(g["no"])
                _t = _tahmin.tahmin(self.db, self.proje_id, meslek=_a.get("meslek") or "",
                                    zorluk=_gg.get("zorluk") or "", motor=_a.get("motor") or "")
                _tahmin.kaydet(self.db, self.proje_id, _gg, _t, _a.get("motor") or "")
                _parca.append(f"#{g['no']}: {_tahmin.metin(_t, _a.get('motor') or '')}")
            if _parca:
                _tahmin_satiri = "\nTahmin: " + " | ".join(_parca)
        except Exception as exc:          # noqa: BLE001 -- tahmin isi durdurmaz
            self.ofis.db.olay_yaz(self.ofis.proje_id, "uyari", f"Tahmin yapilamadi: {exc}")
        self._akis.not_yaz(_KARAR_ETIKET.get(karar["karar"], karar["karar"])
                           + " — ekip çalışıyor; bitince rapor buraya düşer. ("
                           + ", ".join(f"#{g['no']} {g['sahip'] or '-'}"
                                       for g in plan["gorevler"]) + ")"
                           + _tahmin_satiri
                           + ("\nSorulmadan geçecek (senin sözün): "
                              + ", ".join(plan.get("izinler") or [])
                              if plan.get("izinler") else ""))
        self._akis.yeni_bolum("duz")
        yield {"tur": "plan", "govde": plan["gerekce"],
               "ek": {"bol": plan["bol"], "izinler": plan.get("izinler") or [],
                      "gorevler": [{"no": g["no"], "baslik": g["baslik"],
                                    "sahip": g["sahip"]}
                                   for g in plan["gorevler"]]}}

        for adim in self.orkestra.kos(azami_tik=azami_tik, butce_usd=butce_usd,
                                      zaman_asimi=zaman_asimi, paralel=paralel,
                                      izinli_araclar=izinli_araclar,
                                      tarayici_kabini=tarayici_kabini,
                                      kanat_id=lider.get("kanat_id")):
            yield {"tur": "tik", "govde": adim.get("sebep", ""), "ek": adim}
            if adim.get("bitti"):
                son_adim = adim
                break
            if self._ara_var_mi():
                # Istek CEVAPSIZ kalir: isler bitince ofisin ozetiyle kapanir.
                self.ofis.db.olay_yaz(self.ofis.proje_id, "uyari",
                                      "Sirada yeni istek var: halka ona birakildi; bu istegin "
                                      "isleri birlikte suruyor, bitince ozet duser.",
                                      ajan_ad="ofis")
                yield {"tur": "ara", "govde": "Sirada yeni istek var; isler suruyor.", "ek": {}}
                yield {"tur": "bitti", "govde": "", "ek": {"yol": karar["karar"], "ara": True}}
                return

        rapor = self._rapor(lider, mesaj, plan, butce_usd, zaman_asimi)
        self.ofis.postane.cevapla(kayit["id"], rapor, cevaplayan=lider["ad"])
        yield {"tur": "rapor", "govde": rapor, "ek": {}}
        yield {"tur": "bitti", "govde": "", "ek": {"yol": karar["karar"]}}

    def _ara_var_mi(self) -> bool:
        f = getattr(self, "_ara_ver", None)
        try:
            return bool(f and f())
        except Exception:                         # noqa: BLE001 -- olcum halkayi durdurmaz
            return False

    def _acik_is_var(self, kanat_id=None) -> bool:
        """Kosulabilecek acik is var mi? (Bekleyen degil, ILERLEYEBILIR.)"""
        return bool(self._acik_ve_yeni(kanat_id))

    def _acik_ve_yeni(self, kanat_id=None) -> list:
        # Bayat is (bkz. Orkestra.BAYAT_SN) halkayi DONDURMEZ: patron sohbet
        # etti diye unutulmus is kendiliginden baslamaz.
        return [g for g in self.ofis.tahta.liste()
                if g["durum"] in ("hazir", "calisiyor", "inceleme")
                and self.orkestra.takimin_isi(g, kanat_id)
                and not self.orkestra.bayat_mi(g)]

    def _bayat_hatirlatma(self, kanat_id=None) -> str:
        """Bayat isleri patrona BIR KEZ soyler (her sohbette tekrar etmez)."""
        bayat = [g for g in self.ofis.tahta.liste(durum="hazir")
                 if self.orkestra.takimin_isi(g, kanat_id) and self.orkestra.bayat_mi(g)]
        with self.ofis.db.baglanti() as c:
            soylenen = {r["gorev_id"] for r in c.execute(
                "SELECT gorev_id FROM olay WHERE proje_id = ? AND tur = 'bayat_hatirlatildi'",
                (self.ofis.proje_id,)).fetchall()}
        yeni = [g for g in bayat if g["id"] not in soylenen]
        if not yeni:
            return ""
        for g in yeni:
            self.ofis.db.olay_yaz(self.ofis.proje_id, "bayat_hatirlatildi",
                                  f"#{g['no']} bekliyor, kendiliginden baslatilmadi",
                                  ajan_ad="ofis", gorev_id=g["id"])
        satirlar = "\n".join(f"- #{g['no']} {g['baslik'][:80]}" for g in yeni)
        return ("\n\nNot: uzun süredir bekleyen iş var; kendiliğinden "
                "BAŞLATMADIM:\n" + satirlar
                + "\nSürdürmek için 'Sürdür'e bas, istemiyorsan iptal et.")

    # -- ic isleyis --------------------------------------------------------

    def _triyaj(self, lider: dict, mesaj: str, butce_usd, zaman_asimi,
                ek_klasorler=()) -> dict:
        metin = self.triyaj_metni(mesaj, ek_klasorler=ek_klasorler,
                                  kanat_id=lider.get("kanat_id"))
        ham = self._lideri_kostur(lider, metin, butce_usd, zaman_asimi,
                                  ek_klasorler=ek_klasorler,
                                  akis=getattr(self, "_akis", None))
        karar = _json_ayikla(ham)
        if not isinstance(karar, dict) or karar.get("karar") not in (
                "cevap", "kendi", "dagit", "kadro", "zamanla"):
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
        kisa = self._taslaktan_rapor(plan, mesaj)
        if kisa:
            return kisa + self._gercek_durum(plan)

        satirlar = ["# PATRONUN ISTEGI", "", mesaj, "", "# SONUC", ""]
        for g0 in plan["gorevler"]:
            g = self.ofis.tahta.gorev(g0["no"])
            satirlar.append(f"## #{g['no']} {g['baslik']} — {durum_yazisi(g)}")
            satirlar.append(f"- sahip: {g['sahip'] or '-'}")
            satirlar.append(f"- kabul olcutu: {g['kabul_olcutu']}")
            for k in self.ofis.tahta.kanitlar(g["no"]):
                satirlar.append(f"- KANIT [{k['tur']}] {k['baslik']}: "
                                f"{(k['icerik'] or '')[:200]}")
            satirlar.append("")

        from .ekler import gonderilmemisler
        try:
            _gitmemis = gonderilmemisler(self.ofis, [
                self.ofis.tahta.gorev(g0["no"])["id"] for g0 in plan["gorevler"]],
                ek_metinler=(mesaj,))
        except Exception:                        # noqa: BLE001 -- rapor yine yazilir
            _gitmemis = []
        # TESLIM RAPORDA (06.10.2026 gosteri): ajanlarin sohbete gonderdigi
        # teslim dosyalari da raporda tekrar yer alir -- patron raporu okur.
        try:
            from .ekler import teslim_ekleri as _teslim
            _teslimler = _teslim(self.ofis, [self.ofis.tahta.gorev(g0["no"])["id"]
                                             for g0 in plan["gorevler"]])
        except Exception:                        # noqa: BLE001
            _teslimler = []
        if _teslimler:
            satirlar += ["# TESLIM DOSYALARI (ajanlar gonderdi; raporunda AYRI SATIRDA "
                         "`[ek] <yol>` olarak MUTLAKA tekrar ver -- patron raporu okur)", ""]
            satirlar += [f"- {y}" for y in _teslimler]
            satirlar.append("")
        if _gitmemis:
            satirlar += ["# PATRONA HENUZ GITMEMIS DOSYALAR (ofisin olcumu)", ""]
            satirlar += [f"- {y}" for y in _gitmemis]
            satirlar += ["", "Patronun gormesi gerekiyorsa raporuna AYRI SATIRDA "
                             "`[ek] <yol>` olarak ekle.", ""]

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
            # SADE CEVAP (02.10.2026, patron: "burada seninle konusur gibi").
            # "Ne istendi / Ne yapildi" BASLIKLI rapor kalibi sohbette uzun ve
            # yapay duruyordu.
            "- Claude Code'un is bitince yazdigi gibi: ILK CUMLE SONUC; gerekirse",
            "  en fazla 3-4 kisa madde; dosya/baglanti varsa adi. 'Ne istendi',",
            "  'Ne yapildi', 'Kanit' gibi BASLIK yazma; istenen seyi tekrar anlatma.",
            "- Kapanmayan ya da beklemede kalan is varsa ACIKCA soyle.",
            "- KANIT UYDURMA: yukarida yazmayan bir sonucu yazma.",
            "- BASLIK ya da ara cumle YAZMA ('Patrona rapor', 'Once bakiyorum');",
            "  ilk cumle SONUC olsun. 'KANIT' / 'DURUM:' satiri yazma.",
            "- Ic isleyisi (gorev numarasi, kilit, revizyon) anlatma;",
            "  patron sonucu ister, defteri degil.",
            "- " + ARAC_SUSKUNLUGU,
            "- " + EK_KURALI,
        ]
        ham = self._lideri_kostur(lider, "\n".join(satirlar),
                                  butce_usd, zaman_asimi,
                                  akis=getattr(self, "_akis", None))
        metin = (ham or "").strip()[:CEVAP_SINIRI] or "(Lider rapor yazmadi.)"
        # TESLIM GARANTISI (yapi, rica degil): lider teslim satirini yazmasa da
        # ofis ekler -- patron raporu okur (06.10.2026 gosteri).
        _eksik = [y for y in _teslimler if y not in metin]
        if _eksik:
            from .ekler import satirlar as _ek_satirlari
            metin += "\n\n" + _ek_satirlari(_eksik)
        return self._ekleri_hazirla(metin, lider["ad"]) + self._gercek_durum(plan)

    def _taslaktan_rapor(self, plan: dict, mesaj: str = "") -> str:
        """Tek isli planda, isi KAPATAN incelemenin `PATRONA:` taslagi rapor
        olur -- ayri rapor turu kosmaz (bkz. `lider._hukmu_uygula`).

        Kosullar dar: tek is, bitti, taslak var, patronu bekleyen bir sey
        yok. Aksi halde bos doner ve eski yol (liderin rapor turu) isler.
        Sohbete gitmemis kanit dosyasi (`ekler.gonderilmemisler`) OFISCE
        eklenir: lider turu yok, onu ekleyecek kimse yok.
        """
        gorevler = plan.get("gorevler") or []
        if len(gorevler) != 1:
            return ""
        try:
            g = self.ofis.tahta.gorev(gorevler[0]["no"])
        except Exception:                        # noqa: BLE001
            return ""
        if g["durum"] != "bitti":
            return ""
        if self.ofis.postane.insan_bekleyenler() or self.ofis.postane.bekleyen_onaylar():
            return ""
        with self.ofis.db.baglanti() as c:
            r = c.execute("SELECT govde, ajan_ad FROM olay WHERE proje_id = ? AND gorev_id = ? "
                          "AND tur = 'rapor_taslak' ORDER BY rowid DESC LIMIT 1",
                          (self.ofis.proje_id, g["id"])).fetchone()
        if not r or not (r["govde"] or "").strip():
            return ""
        metin = r["govde"].strip()
        from .ekler import gonderilmemisler, satirlar as ek_satirlari, teslim_ekleri
        try:
            gitmemis = gonderilmemisler(self.ofis, [g["id"]], ek_metinler=(metin, mesaj))
        except Exception:                        # noqa: BLE001
            gitmemis = []
        # TESLIM RAPORDA (06.10.2026 gosteri): ajanin once gonderdigi video/
        # gorsel de son raporda tekrar durur -- patron raporu okur.
        try:
            gitmemis = [y for y in teslim_ekleri(self.ofis, [g["id"]]) if y not in metin] + gitmemis
        except Exception:                        # noqa: BLE001
            pass
        if gitmemis:
            metin += "\n\n" + ek_satirlari(gitmemis)
        return self._ekleri_hazirla(metin[:CEVAP_SINIRI], r["ajan_ad"] or "")

    def _ekleri_hazirla(self, metin: str, lider_ad: str) -> str:
        """Liderin `[ek] <yol>` satirlari -> sohbette gorunen ek (kural
        `ekler.metni_hazirla`da). Lider salt okunurdur, dosyayi kendisi
        `ekler/`e tasiyamaz; ofis tasir."""
        from .ekler import metni_hazirla
        # DEFTER SATIRLARI PATRONA GITMEZ (30.09.2026). Olculdu (gercek set
        # G01, iki motor): rapor "KANIT terminal: `Get-ChildItem ...` -> ..."
        # satiriyla geldi -- motorun sistem eki her tura "KANIT satiri yaz"
        # der, aracsiz lider turu da onu alir. Bu satirlar ajanin DEFTER
        # kaydidir (kanit kapisi okur); sohbette gurultudur. Kesin bicim
        # silinir, sade "Kanit: ..." cumlesine dokunulmaz.
        metin = re.sub(r"(?m)^[ \t]*(?:KANIT[ \t]+\S+[ \t]*:|DURUM:).*(?:\r?\n|$)", "", metin)
        metin = re.sub(r"\n{3,}", "\n\n", metin).strip()
        try:
            metin, hatalar = metni_hazirla(self.ofis, metin, ajan_ad=lider_ad)
        except Exception as exc:          # noqa: BLE001 -- cevap kaybolmasin
            self.ofis.db.olay_yaz(self.ofis.proje_id, "uyari",
                                  f"Liderin ekleri islenemedi: {exc}",
                                  ajan_ad=lider_ad)
            return metin
        for h in hatalar:
            self.ofis.db.olay_yaz(self.ofis.proje_id, "uyari",
                                  f"Liderin eki gonderilemedi: {h}",
                                  ajan_ad=lider_ad)
        return metin

    def _gosterilen_durum(self, g: dict, durum_adi: dict) -> str:
        """Raporda bir isin durum yazisi. Pano ile AYNI olcum ve ayni oncelik:
        onay/soru bekleyen -> 'seni bekliyor', duraklatilmis -> 'patron
        duraklatti', `calisiyor` ama OFIS TUR KOSTURMUYORSA -> 'durdu --
        Surdur'e bas'. Olcum `durum_tablosu.tur_olcumu` (kaynagi orada yazar);
        olculemezse eskisi gibi 'calisiyor'."""
        from . import durum_tablosu
        if g["durum"] in ("calisiyor", "inceleme", "hazir", "bekliyor"):
            if (any(o.get("gorev_no") == g["no"] for o in self.ofis.postane.bekleyen_onaylar())
                    or any(s.get("gorev_no") == g["no"] and s.get("alici") == "insan"
                           for s in self.ofis.postane.bekleyen_sorular())):
                return "seni bekliyor"
        if g.get("duraklatildi"):
            return "patron duraklattı"
        if g["durum"] == "calisiyor" and durum_tablosu.tur_kosuyor_mu(self.ofis, g) is False:
            return durum_tablosu.DURDU_METNI
        return durum_adi.get(g["durum"], g["durum"])

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
            satirlar.append(f"- #{g['no']} {g['baslik']}: **{durum_yazisi(g)}** "
                            f"({kanit} kanit)")

        bekleyen = (self.ofis.postane.insan_bekleyenler()
                    + self.ofis.postane.bekleyen_onaylar())
        # 30.09.2026: her sey kapandiysa HICBIR SEY eklenmez. Once her
        # raporun sonuna "Defterden (ofis yazdi...)" + is listesi + kanit
        # sayisi ekleniyordu; kullanici sohbeti "profesyonel degil" buldu.
        # Blogun gorevi LIDERIN ABARTISINI duzeltmekti -- duzeltilecek bir
        # sey yoksa yazmak gurultudur. Kalan: sade, tek satir, jargonsuz.
        if not acik and not bekleyen:
            return ""
        durum_adi = {"bekliyor": "sırada", "hazir": "sırada",
                     "calisiyor": "çalışıyor", "inceleme": "incelemede",
                     "engelli": "takıldı"}
        parca = [chr(10) * 2, "---", ""]
        if acik:
            parca.append(
                f"**Not (ofisin kaydı):** {len(acik)} iş henüz bitmedi — "
                + "; ".join(f"#{g['no']} {g['baslik']} "
                            f"({self._gosterilen_durum(g, durum_adi)})"
                            for g, _ in acik) + ".")
        if bekleyen:
            parca.append(f"**{len(bekleyen)} karar seni bekliyor** "
                         "(Senden bekleniyor bölümünde).")
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
