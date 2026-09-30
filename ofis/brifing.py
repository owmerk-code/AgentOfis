# -*- coding: utf-8 -*-
"""Brifing: ajana verilen dort katmanli baglam.

Bu dosya, sistemin var olma sebebidir.

Olculmus problem: ajan taze bir surec olarak acilip tahtadan bir kart
cekerse, aldigi baglam o kartin icerigidir. Kart isi soyler; projeyi,
amaci, kimin ne yaptigini ve iki saat once alinan karari SOYLEMEZ. Ajan
isi kusursuz yapar, projeyi iskalar. Bir urun bu isabeti olcup yayinladi:
gorev-hedefli secimle bile yaklasik %25. Yani dortte uc bilinmiyor.

Cozum, kart yerine BRIFING:

  K1  ANAYASA      nadiren degisir -- ev kurallari + O AJANIN SICILI
  K2  KUNYE        haftada bir degisir -- proje amaci, kapsam disi, kisitlar
  K3  DURUM        HER DAGITIMDA YENIDEN URETILIR -- kim ne yapiyor, son kararlar
  K4  GOREV FISI   isin kendisi, NEDEN'i, ust hedefi, yazma alani, kabul olcutu

K3 kritik olandir. Elle yazilan durum ozeti bayatlar; bu katman veritabanindan
dagitim aninda uretildigi icin bayatlayamaz.

Brifing ayrica DISKE yazilir: uzun bir iste savrulan ajan kendi kendine
tekrar okuyabilsin. Baglam siserken dikkat bozulur ("context rot"); geri
donup bakilacak sabit bir metin bunu telafi eder.

NEREYE (30.09.2026 duzeltmesi): once ajanin klasorune `BRIFING.md`
yaziliyordu. "Ajanlar ortak kokte" kararindan beri o klasor HERKESIN
koku -- her tur ayni dosyayi eziyordu. Olculdu: gercek terminaldeki lider
kokteki BRIFING.md'yi (bilge'nin eski #33 isi) okudu, kendini bilge sandi
ve plani reddetti. Artik kopya ofis evinde AJAN BASINA durur
(`brifing_yolu`) ve yolu brifingin kendisinde yazar; koke hic yazilmaz.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from . import riskli, roller
from .roller import RolHatasi
from .db import simdi
from .postane import NOT_KURALI, gorev_notlari

#: Kaba jeton tahmini. Kesin olmasi gerekmiyor; amac brifing sisince
#: uyarabilmek. Turkce'de karakter/jeton orani ~3.
KARAKTER_BASINA_JETON = 3.0

#: Brifing bu esigi asarsa uyarilir: sisen baglam dikkati bozar.
JETON_UYARI_ESIGI = 6000


def _jeton(metin: str) -> int:
    return int(len(metin) / KARAKTER_BASINA_JETON)



def brifing_yolu(proje_id: str, ajan_ad: str) -> Path:
    """Ajanin brifing kopyasi: ofis evinde, proje ve AJAN basina (ortak
    kokte degil -- bkz. modul notu). Ad dosya adina uygun hale getirilir."""
    from .yollar import ofis_evi
    import re as _re
    ad = _re.sub(r"[^A-Za-z0-9._-]+", "-", str(ajan_ad or "ajan")) or "ajan"
    return ofis_evi() / "brifing" / str(proje_id) / f"{ad}.md"

class Brifing:
    def __init__(self, db, proje_id: str, kadro, tahta, bellek) -> None:
        self.db = db
        self.proje_id = proje_id
        self.kadro = kadro
        self.tahta = tahta
        self.bellek = bellek

    # -- katmanlar ---------------------------------------------------------

    def k1_anayasa(self, ajan_ad: str) -> str:
        """Kim oldugun, ev kurallari ve SANA OZEL dersler.

        Dersler kisiye ozeldir: 'Demir commit oncesi test kosmayi unutuyor'
        dersi herkese degil Demir'e yapisir. Sirket geneli kural, ilgisiz
        ajanin baglamini sisirir ve kimse ustune alinmaz.
        """
        ajan = self.kadro.ajan(ajan_ad)
        dersler = self.kadro.dersler(ajan_ad)

        satirlar = [
            "## K1 — ANAYASA",
            "",
            f"Sen **{ajan['ad']}**'sin. Meslegin: {ajan['meslek']}.",
        ]

        # ROL TANIMI BRIFINGE GIRER.
        #
        # Bu kurallar (dosya yazabilir mi, neyin kanit sayildigi, bu
        # rolde "bitti"nin ne demek oldugu) bugune kadar YALNIZCA KODDA
        # vardi: uygulaniyorlardi ama ajana hic soylenmiyorlardi.
        # Uygulanan ama soylenmeyen kural, ajanin ondan ogrenemedigi
        # kuraldir -- ajan neyin beklendigini tahmin etmek zorunda kalir
        # ve tahmin, bu projede defalarca yanlis is uretti.
        try:
            satirlar += ["", roller.brifing_blogu(ajan["meslek"])]
        except RolHatasi:
            # Kutuphane oncesi yazilmis, cozulemeyen bir meslek. Brifing
            # yine de uretilir -- eski bir kayit yuzunden ajanin isini
            # durdurmak, duzeltmekten pahalidir. Ama SESSIZ kalmaz.
            satirlar += [
                "",
                f"! Rolun ({ajan['meslek']}) kutuphanede TANIMLI DEGIL. "
                "Araclarin ve kanit beklentin varsayilana dusuyor; "
                "emin olmadigin sey icin lidere sor.",
            ]
        if ajan["lider_mi"]:
            satirlar += [
                "",
                "Sen bu kanadin **lidersin**. Sorumluluklarin:",
                "- Hedefi netlestir, isi adimlara bol, her adima sahip ve kabul olcutu yaz.",
                "- **Bolmeden once karar ver:** is gercekten bagimsiz kollara ayriliyor mu?",
                "  Ayrilmiyorsa BOLME, tek ajanda kostur. Coklu ajan ~15 kat jeton yakar ve",
                "  yalnizca genislik-oncelikli islerde kazanir. Karari ve GEREKCESINI yaz.",
                "- Iki acik gorev ayni dosyalara dokunamaz. Yazma alanlarini ayrik bol.",
                "- Sonucu alt goreve gore degil, **kullanicinin orijinal hedefine** gore incele.",
                "- Hatayi gorursen ajana soyle ve ders olarak yazdir; ayni hata tekrar ederse",
                "  ders sayaci artar ve o ajanin her brifinginde one cikar.",
            ]
        else:
            satirlar += [
                "",
                "Ev kurallari:",
                "- **Kanitsiz is bitmez.** Terminal ciktisi, diff ya da ekran goruntusu",
                "  eklemeden gorevi incelemeye veremezsin. 'Calisiyor' demek iddiadir.",
                "- **Yalnizca sana verilen yazma alaninda calis.** Disina cikman gerekiyorsa",
                "  once lidere sor; alan baskasinda kilitli olabilir.",
                "- **Takilirsan sor.** Tahmin etme. Lidere soru sormak ucuz, yanlis varsayimla",
                "  iki saat calismak pahalidir.",
                "- **Riskli adimda dur.** Para harcamak, disari yazmak, yayina almak, `push`",
                "  yapmak onay ister. Kod yazmak, test kosmak sormaz.",
            ]

        if dersler:
            satirlar += ["", "### Sana ozel — gecmiste duselen notlar"]
            for d in dersler:
                if d["tekrar"] > 1:
                    satirlar.append(f"- **({d['tekrar']}. kez)** {d['ders']}")
                else:
                    satirlar.append(f"- {d['ders']}")
        return "\n".join(satirlar)

    def k2_kunye(self, no: int = None) -> str:
        """Proje nedir. Haftada bir degisir, her brifingte tekrarlanir."""
        with self.db.baglanti() as conn:
            p = conn.execute(
                "SELECT * FROM proje WHERE id = ?", (self.proje_id,)
            ).fetchone()
        if not p:
            return "## K2 — KUNYE\n\n(proje kaydi yok)"

        satirlar = ["## K2 — PROJE KUNYESI", "", f"**Proje:** {p['ad']}"]
        if p["amac"]:
            satirlar += ["", f"**Amac:** {p['amac']}"]
        if p["basari_olcutu"]:
            satirlar += ["", f"**Basari olcutu:** {p['basari_olcutu']}"]
        if p["kapsam_disi"]:
            # Kapsam disi en cok atlanan alandir; ajan "faydali olayim" diye
            # istenmeyen isi yapar ve zaman yakar.
            satirlar += ["", f"**KAPSAM DISI (yapma):** {p['kapsam_disi']}"]
        if p["kisitlar"]:
            satirlar += ["", f"**Kisitlar:** {p['kisitlar']}"]
        if p["sozluk"]:
            satirlar += ["", f"**Sozluk:** {p['sozluk']}"]
        # OFIS KURALLARI -- KOSULSUZ. Olgu goreve gore secilir ve elenebilir;
        # kural, insanin "bu HER zaman bilinmeli" dedigi seydir.
        satirlar += self.kural_satirlari()

        # Gorev verildiyse olgular O ISE GORE secilir -- ama yalnizca
        # sisme esigi asilirsa (bkz. bellek.ilgili_olgular). Olculdu:
        # 300 olguda brifingin %98'i o ise gereksizdi ve 5773 jetona
        # cikmisti; 500 olguda esik asiliyordu.
        elenen = 0
        secim_yapildi = False
        if no is not None:
            g = self.tahta.gorev(no)
            anahtar = " ".join(str(g.get(alan) or "") for alan in
                               ("baslik", "govde", "neden", "ana_hedef",
                                "kabul_olcutu"))
            sonuc = self.bellek.ilgili_olgular(anahtar)
            olgular = sonuc["secilen"]
            elenen = sonuc["elenen"]
            secim_yapildi = sonuc["secim_yapildi"]
        else:
            olgular = self.bellek.gecerli_olgular()
        if olgular:
            satirlar += ["", "### Gecerli olgular", ""]
            for o in olgular:
                kaynak = f" _(kaynak: {o['kaynak']})_" if o["kaynak"] else ""
                # Bagla gelen olgu SOYLER: gorevle ortak kelimesi yok,
                # buraya baska bir bilginin `[[bagi]]` getirdi.
                bag = (f" _(bagla geldi: [[{o['bag']}]])_"
                       if o.get("bag") else "")
                satirlar.append(
                    f"- **{o['konu']}:** {o['icerik']}{kaynak}{bag}")
            satirlar.append("")
            satirlar.append(
                "_Bu liste yalnizca SU AN gecerli olgulari icerir. Eskimis bir bilgi "
                "hatirliyorsan, buradaki gecerlidir._"
            )
            if secim_yapildi:
                # Gizli eksiltme UYDURMANIN kapisini acar: ajan gorusunun
                # tam oldugunu sanirsa, olmayan bilgiyi tahmin eder.
                satirlar.append("")
                satirlar.append(
                    f"_Bu liste BU ISE GORE secildi; {elenen} olgu daha var. "
                    "Ihtiyacin olan bir bilgi burada yoksa UYDURMA -- "
                    "`durum` araciyla tamamini sor ya da lidere danis._"
                )
        return "\n".join(satirlar)

    def k3_durum(self, haric_ajan: str = "") -> str:
        """HER DAGITIMDA TAZE URETILIR. Bayatlayamaz, cunku sorgudur."""
        satirlar = ["## K3 — SU ANKI DURUM", ""]

        calisan = self.tahta.liste(durum="calisiyor")
        incelemede = self.tahta.liste(durum="inceleme")
        if calisan or incelemede:
            satirlar.append("**Su an kim ne yapiyor:**")
            for g in calisan:
                if g["sahip"] == haric_ajan:
                    continue
                alan = ", ".join(g["yazma_alani"]) or "—"
                satirlar.append(f"- `{g['sahip']}` → #{g['no']} {g['baslik']}  _(yazma alani: {alan})_")
            for g in incelemede:
                satirlar.append(f"- `{g['sahip']}` → #{g['no']} {g['baslik']}  _(incelemede)_")
        else:
            satirlar.append("Su an calisan baska ajan yok.")

        bekleyen = self.tahta.liste(durum="bekliyor")
        if bekleyen:
            satirlar += ["", "**Bagimliligi bekleyenler:**"]
            for g in bekleyen:
                blok = self.tahta.blokcular(g["no"])
                adlar = ", ".join(f"#{b['no']}" for b in blok) or "?"
                satirlar.append(f"- #{g['no']} {g['baslik']} — {adlar} bekliyor")

        kararlar = self.bellek.son_kararlar(8)
        if kararlar:
            satirlar += ["", "**Son kararlar** (en yenisi ustte):", ""]
            for k in kararlar:
                satirlar.append(f"- `{k['veren']}`: {k['karar']}")
                satirlar.append(f"  _gerekce: {k['gerekce']}_")
            satirlar.append("")
            satirlar.append(
                "_Bu kararlar baglayicidir. Biriyle celisen bir sey yapman gerekiyorsa "
                "once lidere sor._"
            )
        return "\n".join(satirlar)

    def kural_satirlari(self) -> list:
        """K2 ve lider istemleri icin kural blogu (bos ise hic yazilmaz)."""
        kurallar = self.bellek.kurallar()
        if not kurallar:
            return []
        return (["", "**OFIS KURALLARI (insan onayli -- HER iste gecerli):**"]
                + [f"- {k['metin']}" for k in kurallar])

    def kunye_ozeti(self) -> str:
        """LIDERIN gordugu kunye: amac, KAPSAM DISI, kisitlar, kurallar.

        OLCULDU (24.09.2026): lider triyajda, planlamada ve incelemede
        projenin kunyesini HIC gormuyordu -- `kapsam_disi` yalniz iscinin
        K2'sine giriyordu. Yani isi BOLEN ve INCELEYEN kisi "yapma" denen
        seyi bilmiyordu; kapsam disi bir kolu planlayip kapatabilirdi.
        Iscinin brifinginde yazili olmasi yetmez: karar verilen yerde
        yazili olmali (olcut sablonu ve baglayici envanteriyle ayni ders).

        Kisa tutulur: sozluk ve olgular burada YOK (triyaj olgulari zaten
        ayri veriyor), bu yalniz KARARI sinirlayan alanlar.
        """
        with self.db.baglanti() as conn:
            p = conn.execute("SELECT * FROM proje WHERE id = ?",
                             (self.proje_id,)).fetchone()
        if not p:
            return ""
        satirlar = ["## PROJE KUNYESI (kararini sinirlar)", ""]
        if p["amac"]:
            satirlar.append(f"- amac: {p['amac']}")
        if p["basari_olcutu"]:
            satirlar.append(f"- basari olcutu: {p['basari_olcutu']}")
        if p["kapsam_disi"]:
            satirlar.append(f"- KAPSAM DISI (yapilmaz, planlanmaz, "
                            f"kabul edilmez): {p['kapsam_disi']}")
        if p["kisitlar"]:
            satirlar.append(f"- kisitlar: {p['kisitlar']}")
        kurallar = self.kural_satirlari()
        if len(satirlar) == 2 and not kurallar:
            return ""
        return "\n".join(satirlar + kurallar)

    def _alan_satiri(self, yol: str) -> str:
        """Yazma alanini TURUYLE yazar -- uydurmadan.

        OLCULEN HATA (26.09.2026, deneme D05, codex isci): burada her alanin
        sonuna KOSULSUZ `/` ekleniyordu; `fiyatlar.csv` alani ajana
        `fiyatlar.csv/` diye, yani KLASOR olarak gosteriliyordu. Claude bunu
        gormezden geldi; codex (luna) kelimesi kelimesine uydu, `fiyatlar.csv`
        adinda KLASOR acip dosyayi icine yazdi -- iki kosuda iki. Hata ajanda
        degil brifingdeydi: yanlis bilgi veren brifing, yanlis is urettirir.

        Tur diskten OLCULUR; olculemiyorsa ada bakilir ve bu SOYLENIR.
        """
        ham = str(yol or "")
        ad = ham.rstrip("/\\")
        kok = self.tahta.kok_klasor()
        tam = (Path(kok) / ad) if kok and not Path(ad).is_absolute() else Path(ad)
        try:
            if tam.is_dir():
                return f"  - `{ad}/` (klasor -- icine yazabilirsin)"
            if tam.is_file():
                return f"  - `{ad}` (DOSYA -- bu dosyayi yaz, klasor ACMA)"
        except OSError:
            pass
        if ham.endswith(("/", "\\")):
            return f"  - `{ad}/` (klasor -- henuz yok, acabilirsin)"
        if Path(ad).suffix:
            return (f"  - `{ad}` (DOSYA -- henuz yok; bu ADLA bir dosya yaz, "
                    "klasor ACMA)")
        return (f"  - `{ad}` (henuz yok; dosya mi klasor mu adindan belli degil "
                "-- isin tanimina bak)")

    def k4_gorev(self, no: int, *, olcut: bool = True) -> str:
        """Isin kendisi -- ve nicin var oldugu.

        `olcut=False`: riskli eylem olcutu YAZILMAZ. Devam turu bunu
        boyle cagirir, cunku devam AYNI OTURUMDA kosar -- ajan olcutu
        zaten bu oturumun basinda okudu. Tekrarlamak her devam turuna
        ~700 karakter bindirirdi ve devam turu, butce kesintisinden
        sonra artik cok sik kosuyor.

        Ilk surumde bu bayrak yoktu ve `duman_koltuk` yakaladi:
        "devam metni tam brifingden cok daha kisa" sinamasi kaldi.
        """
        g = self.tahta.gorev(no)
        alan = ("\n".join(self._alan_satiri(y) for y in g["yazma_alani"])
                or "  - (belirtilmemis)")
        satirlar = [
            "## K4 — GOREVIN",
            "",
            f"### #{g['no']} — {g['baslik']}",
        ]
        if g["govde"]:
            satirlar += ["", g["govde"]]
        satirlar += [
            "",
            f"**Bu is nicin var:** {g['neden']}",
            "",
            f"**Bagli oldugu ust hedef:** {g['ana_hedef']}",
            "",
            f"**Bittigini nasil kanitlayacaksin:** {g['kabul_olcutu']}",
            "",
            "**Yazma alanin** — yalnizca buraya yazabilirsin:",
            alan,
        ]
        # PATRONUN NOTLARI isin tanimina EKTIR. Tur basinda (tam brifing,
        # devam, devir) her zaman gorunur: bir kez soylenip unutulan bir
        # yon duzeltmesi, sonraki turda eski yone donmek demektir.
        # Ulasmamis olanlar YENI diye isaretlenir -- ajan once onlara baksin.
        notlar = gorev_notlari(self.db, self.proje_id, g["id"])
        if notlar:
            satirlar += ["", f"**Patronun bu ise notlari** ({NOT_KURALI}):"]
            for n in notlar:
                zaman = str(n["olusturuldu"])[5:16].replace("T", " ")
                satirlar.append(f"  - [{zaman}]"
                                + ("" if n["okundu"] else " **YENI**")
                                + f" {n['govde']}")
        # TAKIMA BILDIRIM (29.09): ajan onemli anlari sohbete kendisi yazar.
        # 30.09: sohbet PATRONUN konusmasidir; "is bitti"yi lider rapor eder.
        satirlar += ["", "**Patrona bildirim:** `sohbete_yaz` YALNIZ patronun "
                         "gormesi gereken bir DOSYA (gorsel, pdf, video) ya da "
                         "seni durduran bir ENGEL icindir; 1-2 cumle. 'Is bitti', "
                         "ara durum, kanit ozeti YAZMA -- onu lider rapor eder. "
                         "Cevap bekleme. Patrona gorsel/pdf/video GOSTERMEK icin "
                         "ayni aracin `ekler` alanina dosya yolunu yaz. "
                         "Sohbet ofis icidir, disari cikmaz: ONAY GEREKMEZ. "
                         "`ekler/` klasoru HER ISTE SERBESTTIR (yazma alani gerekmez): patrona gosterilecek dosya oraya kaydedilir -- sayfa goruntusu icin `browser_take_screenshot` araci `filename: \"ekler/<ad>.png\"` ile -- ve `sohbete_yaz(ekler=[...])` ile gonderilir. Oradaki dosyayi SILME. "
                         "Soru icin `soru_sor`, onay icin `onay_iste`."]
        # PATRONUN IZINLERI her turda (devam dahil) soylenir: ajan izinli
        # bir eylem icin `onay_iste` cagirip bosuna durmasin.
        from .izin import brifing_blogu as izin_blogu
        iz = izin_blogu(self.db, self.proje_id, g["id"])
        if iz:
            satirlar += ["", iz]
        blok = self.tahta.blokcular(no)
        if blok:
            satirlar += ["", "**Seni bekleten isler:**"]
            for b in blok:
                satirlar.append(f"  - #{b['no']} {b['baslik']} ({b['durum']})")

        kanit = self.tahta.kanitlar(no)
        if kanit:
            satirlar += ["", "**Bu goreve daha once eklenmis kanitlar:**"]
            for k in kanit:
                satirlar.append(f"  - {k['tur']}: {k['baslik']} _({k['ekleyen']})_")

        # TARAYICI ARTIK HER ISTE (24.09.2026): alan bossa SERBEST,
        # doluysa o sitelere DARALTILMIS. Ajan ikisini ayirt etmeli --
        # serbestken "izinli siteler" listesi okumak onu kendi kendine
        # kisitlatir, daraltilmisken "serbest" demek yalan olurdu.
        alanlar = g.get("tarayici_alani") or []
        if olcut:
            satirlar += ["", riskli.brifing_blogu(
                True, serbest=not alanlar).rstrip()]
        if alanlar:
            # IZINLI SITELER SOYLENIR. Beyan edilmemis siteye gitmek artik
            # sert ret degil patrona SORU (tarayici_kapi); ajan bunu
            # bilmezse "erisemedim" deyip vazgecer ya da dolambacli yol
            # arar. Uygulanan ama soylenmeyen kural, ogrenilemeyen kuraldir.
            satirlar += [
                "",
                "**Izinli siteler:** " + ", ".join(alanlar) + ". Baska bir "
                "siteye GITMEN gerekirse `browser_navigate` ile git: ofis "
                "patrona sorar; onaylanirsa site bir SONRAKI turda acilir. "
                "O arada turu kanitlarinla bitir, dolambacli yol arama.",
            ]
            if not g.get("tarayici_yazma"):
                satirlar += [
                    "",
                    "**BU IS SALT OKUNUR:** tiklama/yazma araclari sana "
                    "HIC verilmedi (bilerek daraltildi). Gez, oku, ekran "
                    "goruntusu al. Tiklaman gerektigini dusunuyorsan "
                    "durma ve `soru_sor` ile lidere bildir.",
                ]

        satirlar += [
            "",
            "**Bitirince:** kanitini ekle (`ofis.kanit_ekle`), sonra isi incelemeye ver.",
            "**Takilirsan:** lidere sor (`ofis.soru_sor`) — tahmin etme.",
        ]
        if olcut:
            # OLGU KATMANI BESLENMIYORDU (olculdu, 24.09: gercek ofiste
            # 0 olgu). Kalici bilgiyi ogrenen ajandir; yazmazsa bir
            # sonraki ajan ayni seyi bastan arastirir.
            #
            # OLCULDU: rica bicimindeki ilk surume gercek haiku turu HIC
            # uymadi (ayar.txt'den portu okudu, rapora yazdi, bilgi_yaz'i
            # cagirmadi). DURUM ve KANIT satirlarinda odenen ders ucuncu
            # kez: kural bicimsiz verilmez -- TETIKLEYICI + sablon + ornek.
            satirlar += [
                "",
                "**BILGI YAZMAK -- tetikleyici olursa ZORUNLU.** Isin "
                "sirasinda bir dosyadan, komuttan ya da kaynaktan projeye "
                "dair bir DEGER ogrendiysen (port, surum, adres, fiyat, "
                "hesap adi, klasor yolu) ve bu deger bu isten sonra da "
                "gecerliyse `ofis.bilgi_yaz` ile yaz:",
                "",
                "    konu: kisa ad       icerik: deger (nereden ogrendin)",
                "",
                "Ornek: konu `veritabani surumu`, icerik `PostgreSQL 16 "
                "(docker-compose.yml)`. "
                "Ilgili bilgiye `[[konu]]` ile bagla. Gecici is notu YAZMA "
                "-- o DURUM satirina gider. Arac sende yoksa atla.",
            ]
        # DURUM NOTU -- yalniz tam brifingde (olcut ile ayni sebep: devam
        # AYNI oturumda kosar, ajan bunu zaten okudu). Kanal METINDIR,
        # arac degil: metin HER motorda akiyor, yani tek kanal ve yarin
        # eklenen motor da kendiliginden kapsanir.
        if olcut:
            # OLCULDU (23.09.2026): rica bicimindeki ilk surume gercek
            # haiku turu HIC uymadi (0 satir). KANIT satirinda bir kez
            # odenen ders: kural bicimsiz verilmez -- ZORUNLU + tam
            # sablon + ornek.
            satirlar += [
                "",
                "**DURUM SATIRI YAZMAK ZORUNDASIN.** Her dosyayi ya da "
                "adimi bitirdiginde VE turun sonunda, metnine ayri bir "
                "satir olarak TAM OLARAK su bicimde yaz:",
                "",
                "    DURUM: <ne bitti> | <sirada ne var>",
                "",
                "Ornek: `DURUM: cikti/bir.txt yazildi | sirada cikti/iki.txt`",
                "",
                "Sebep: tur senin elinde olmayan bir sebeple (kullanim "
                "limiti) kesilebilir ve isi BASKA bir model surdurur -- o "
                "model senin konusmani goremez, yalniz bu satiri gorur. "
                "En son satir gecerlidir.",
            ]
        return "\n".join(satirlar)

    # -- devir paketi ------------------------------------------------------

    #: Paketin tavani. Paket bir OZETTIR, transkript degil (Yasa 4):
    #: ajanin baglamini defterden aldigi yeri sisirmek, devrin kazancini
    #: baglam curumesiyle geri odemek olurdu.
    DEVIR_AZAMI_DOSYA = 25
    DEVIR_SON_SOZ_HARF = 900

    def devir_blogu(self, no: int, *, kesilen: dict = None) -> str:
        """"Bu is daha once basladi" blogu -- baska bir modelin KALDIGI
        YERDEN devam edebilmesi icin.

        OLCULEN BOSLUK (23.09.2026): nobet zinciri limitte isi sonraki
        motora devrediyordu ama yeni motor yarida kalan turda NE
        yapildigini hic gormuyordu. Oturum kimligi tasinamaz (o kimlik
        onceki motorun defterinde yasar) -- tasinabilecek olan DEFTERDIR.

        Uc kaynak, ucu de ayri etiketle -- olculen ile soylenen
        karismasin:

        * **Diskte OLCULEN degisiklik** (`degisim` tablosu + kesilen
          turun henuz yazilmamis farki). Ofisin olcumu, ajanin sozu degil.
        * **Durum notu** -- ajanin kendi `DURUM:` satiri. SOZDUR: dogrulanmadan
          guvenilmemeli ve blok bunu soyler.
        * **Son kanitlar** -- basliklari K4'te zaten var; burada icerigin
          ilk satirlari.

        `kesilen`: koltugun tur ORTASINDA devrederken verdigi taze olcum
        (`motor`, `model`, `son_soz`, `diskte`). Verilmezse yalnizca
        defter okunur.

        Gecmis YOKSA bos doner -- ilk kez baslayan ise "daha once
        basladi" demek, olmayan bir gecmisi uydurmak olurdu.
        """
        from . import degisim as _degisim
        g = self.tahta.gorev(no)
        kesilen = kesilen or {}

        # Disk: defterdekiler + kesilen turun taze farki, yol basina EN YENI.
        dosyalar = {}
        for k in reversed(_degisim.oku(self.db, self.proje_id,
                                       gorev_id=g["id"], limit=200)):
            dosyalar[k["yol"]] = k
        for k in (kesilen.get("diskte") or []):
            dosyalar[k["yol"]] = k

        with self.db.baglanti() as conn:
            not_ = conn.execute(
                "SELECT ajan_ad, govde, olusturuldu FROM olay WHERE proje_id = ?"
                " AND gorev_id = ? AND tur = 'durum_notu'"
                " ORDER BY olusturuldu DESC, rowid DESC LIMIT 1",
                (self.proje_id, g["id"]),
            ).fetchone()
        kanitlar = self.tahta.kanitlar(no)
        son_soz = (kesilen.get("son_soz") or "").strip()

        if not (dosyalar or not_ or kanitlar or son_soz):
            return ""

        s = ["## DEVIR — bu is DAHA ONCE BASLADI, sifirdan baslama", ""]
        if kesilen.get("motor"):
            s.append(
                f"Onceki tur **{kesilen['motor']}"
                + (f"/{kesilen['model']}" if kesilen.get("model") else "")
                + "** ile koşuyordu ve kullanim limitine takildi. Sen AYNI "
                "isi surduruyorsun; onceki modelin konusmasi sana "
                "tasinamadi, asagidakiler defterden.")
            s.append("")
        if dosyalar:
            s.append("**Diskte OLCULEN degisiklik** (ofisin olcumu, ajanin "
                     "sozu degil) — once bunlara bak:")
            sirali = sorted(dosyalar.values(), key=lambda k: k["yol"])
            for k in sirali[:self.DEVIR_AZAMI_DOSYA]:
                s.append(f"  - `{k['yol']}` {k['hal']} "
                         f"(+{int(k.get('eklenen') or 0)} "
                         f"-{int(k.get('silinen') or 0)})")
            if len(sirali) > self.DEVIR_AZAMI_DOSYA:
                s.append(f"  - ... ve {len(sirali) - self.DEVIR_AZAMI_DOSYA}"
                         " dosya daha")
            s.append("")
        if not_:
            s.append(f"**Son durum notu** ({not_['ajan_ad']}, "
                     f"{not_['olusturuldu']}) — ajanin SOZU, dosyalarla "
                     "dogrulamadan guvenme:")
            s.append(f"> {not_['govde'][:500]}")
            s.append("")
        if kanitlar:
            s.append("**Eklenmis son kanitlar** — TEKRAR EKLEME:")
            for k in kanitlar[-3:]:
                ilk = (k.get("icerik") or "").strip().splitlines()
                s.append(f"  - {k['tur']}: {k['baslik'][:120]}"
                         + (f" — {ilk[0][:160]}" if ilk else ""))
            s.append("")
        if son_soz:
            s.append("**Kesilen turun son sozu** (yarim kalmis olabilir):")
            s.append("> " + son_soz[-self.DEVIR_SON_SOZ_HARF:]
                     .replace(chr(10), chr(10) + "> "))
            s.append("")
        s.append("Once diskteki durumu dogrula, sonra YARIM KALANI tamamla. "
                 "Biten adimi tekrarlama.")
        return chr(10).join(s)

    # -- birlestirme -------------------------------------------------------

    def uret(self, no: int, ajan_ad: str, *, diske_yaz: bool = True,
             kesilen: dict = None) -> dict:
        """Dort katmani birlestir, kaydet, ajanin klasorune yaz.

        Kaydedilmesinin sebebi: bir is yanlis gittiginde "ajan ne biliyordu"
        sorusunun cevabi olmadan hata ayiklanamaz.
        """
        ajan = self.kadro.ajan(ajan_ad)
        parcalar = [
            self.k1_anayasa(ajan_ad),
            self.k2_kunye(no),
            self.k3_durum(haric_ajan=ajan_ad),
            self.k4_gorev(no),
        ]
        # Gecmisi olan is DEVIR paketini de tasir (bos ise hic eklenmez).
        devir = self.devir_blogu(no, kesilen=kesilen)
        if devir:
            parcalar.append(devir)
        hedef = brifing_yolu(self.proje_id, ajan_ad) if diske_yaz else None
        if hedef is not None:
            parcalar.append(
                "Bu brifingin kopyasi (YALNIZ SENIN; uzun iste savrulursan "
                f"geri donup oku): `{hedef}`. Proje kokunde BRIFING.md "
                "gorursen o SENIN degil, okuma.")
        metin = "\n\n---\n\n".join(parcalar)
        jeton = _jeton(metin)

        gorev = self.tahta.gorev(no)
        brifing_id = uuid.uuid4().hex
        with self.db.baglanti() as conn:
            conn.execute(
                "INSERT INTO brifing (id, gorev_id, ajan_ad, metin, jeton_tahmini, olusturuldu) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (brifing_id, gorev["id"], ajan_ad, metin, jeton, simdi()),
            )

        yazildi = ""
        if hedef is not None:
            try:
                hedef.parent.mkdir(parents=True, exist_ok=True)
                gecici = hedef.with_name(hedef.name + ".part")
                gecici.write_text(metin, encoding="utf-8")
                gecici.replace(hedef)
                yazildi = str(hedef)
            except OSError:
                # Diske yazamamak brifingi gecersiz kilmaz; ajan yine de
                # metni prompt olarak alir.
                yazildi = ""

        return {
            "id": brifing_id,
            "metin": metin,
            "jeton_tahmini": jeton,
            "sisme_uyarisi": jeton > JETON_UYARI_ESIGI,
            "dosya": yazildi,
        }

    def uyanis_metni(self, ajan_ad: str, son_gorulen_olay_id: int) -> str:
        """Devam eden oturuma verilecek kisa fark ozeti.

        Tam brifing yeniden verilmez: devam eden oturum zaten dolu. Yalnizca
        DEGISEN sey verilir -- baglami sismeden guncel tutmanin tek yolu bu.
        """
        olaylar = self.bellek.uyanis_ozeti(ajan_ad, son_gorulen_olay_id)
        if not olaylar:
            return ""
        satirlar = ["**Sen calisirken sunlar degisti:**", ""]
        for o in olaylar:
            satirlar.append(f"- [{o['tur']}] {o['govde']}")
        satirlar += [
            "",
            "_Devam etmeden once bunlarin isini etkileyip etkilemedigini dusun._",
        ]
        return "\n".join(satirlar)
