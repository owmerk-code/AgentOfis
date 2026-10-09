/* AgentOfis paneli — istemci.

   Panel karar VERMEZ, cekirdege sorar ve gosterir. Bir kural burada
   uygulaniyorsa yanlis yerdedir: CLI'dan girildiginde atlanabilir demektir.

   Ikinci kural: HAM VERI GOSTERILMEZ. Olay tablosu makine icin yazilir
   ("ise_alindi", "tur_ozeti"); insana Turkce cumle gosterilir. Ilk surumde
   ham olaylar dogrudan basildi ve panel okunamaz hale geldi. */

const D = {
  ofis: null, tahta: null, kanat: "",
  // YERLESIM: sutun -> yigin -> sekme (bkz. "yerlesim" bolumu).
  yerlesim: null, surukle: null,
  sonOlay: 0, olaylar: [], acikCekmece: null, panolar: {},
  // Ofis gorunumunde terminali acik olan ajan. Kat planinda sprite'a
  // tiklayinca dolar; kanat degisince veya ajan gorunmez olunca duser.
  secilenAjan: null,
  // OKUNUR KIP: arac gurultusu susar, ajanin SOZU kalir. Panel
  // geneli tek kip -- pano basina ayri kip, ayni ekranda iki farkli
  // okuma sozlesmesi demek olurdu.
  okunurKip: false,
  // KOD bolumu: diskte OLCULEN degisiklikler ve acilmis yamalar.
  // Fark `degisim` tablosunda yasar, bellekte degil -- Kod bolumunun
  // oturumlar arasi acik kalmasi bunun sonucu, bir arayuz numarasi degil.
  kod: null, kodAcik: {},
  // CANLI IZLEME: tur SURERKEN diskte olculen ara fark (/api/canli) ve
  // son cizilen halin imzasi -- degismeyen veri yeniden cizilmez (her
  // iki buckukta bir cizmek, okunan yamanin kaydirmasini sifirlardi).
  canli: null, canliImza: "",
  // BUYUTULMUS yigin ("sutun:yigin") -- GORUNUM hali, DUZENE YAZILMAZ.
  // Yazilsaydi panel bir sonraki acilista tek pano gibi acilir ve insan
  // oteki panolarin kayboldugunu sanirdi (rakibin v0.2.32'de yasadigi
  // "paneller kayboldu" hatasinin baska bir kapisi).
  buyuk: null,
  // Ajanin haritadaki SON yeri ve hangi kanadin haritasinda oldugu.
  // Yuruyus yalnizca yer GERCEKTEN degistiginde oynar -- rastgele gezinme
  // bilgi tasimaz, gecis tasir.
  konum: {}, konumKanat: null,
  // Yeniden kurulumdan hemen once YOLDA olanlarin anlik yeri ve kalan
  // yolu (bkz. yoldakileriOku). Kanat degisince bosalir.
  yolda: {},
  // Konumlarin ait oldugu KADRO (adlar). Kadro degisince masalar yeniden
  // dizilir -- eski konumlar tutulursa oturan ajanlar sahte bir yuruyus
  // yapardi; oysa hareket gercek bir olay olmali.
  konumKadro: null,
  // Her balonun son SECILEN hizasi. Tazelemede once o denenir; yoksa
  // olculen genislik bir pikselle oynadiginda balon her olayda sagdan
  // sola sicriyordu (olculdu).
  balonHiza: {},
};

const $  = (s) => document.querySelector(s);
const el = (etiket, sinif, metin) => {
  const d = document.createElement(etiket);
  if (sinif) d.className = sinif;
  if (metin !== undefined) d.textContent = metin;
  return d;
};
/* SAAT YEREL GOSTERILIR (01.10.2026, canli: patron 11:41'de "08:41" gordu).
   Defter UTC tutar (`db.simdi`); dilim bilgisi olan ISO ani tarayici yerel
   saate cevirir. Dilimsiz eski kayit oldugu gibi kesilir (uydurulmaz). */
const saat = (iso) => {
  const s = iso || "";
  if (!/[+-]\d\d:\d\d$|Z$/.test(s)) return s.slice(11, 16);
  const t = new Date(s);
  return isNaN(t) ? s.slice(11, 16)
    : t.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
};
const kes  = (m, n) => ((m || "").length > n ? m.slice(0, n) + "…" : (m || ""));

/* Odalar: anahtar, baslik, NE ANLAMA GELDIGI, haritadaki KISA ad.
   Aciklama surekli gorunur -- panel kendini anlatmali, kullanici
   ezberlememeli. Kisa ad bir kisaltma degil bir OLCUM sonucu: dar odanin
   plakasi (~90px) tam adi "İNCELEM…", "ONAY K…" diye kesiyordu; tam ad
   ve aciklama plakanin `title`inda duruyor. */
const ODALAR = [
  ["masa",        "MASALAR",        "şu an çalışıyor",            "MASALAR"],
  ["inceleme",    "İNCELEME ODASI", "lider kanıta bakıyor",       "İNCELEME"],
  ["bekleme",     "BEKLEME ODASI",  "soru sordu, cevap bekliyor", "BEKLEME"],
  ["onay_kapisi", "ONAY KAPISI",    "senin onayını bekliyor",     "ONAY"],
  ["mola",        "MOLA",           "boşta",                      "MOLA"],
];
const SUTUN_AD = {
  bekliyor: "BEKLİYOR", hazir: "HAZIR", calisiyor: "ÇALIŞIYOR",
  inceleme: "İNCELEME", bitti: "BİTTİ",
};

/* ─────────────── olayin insan hali ───────────────
   Her olay turu icin: okunur metin + onem rengi. Listede olmayan tur
   gunluge GIRMEZ; her satiri gostermek, hicbirini gostermemektir. */
const OLAY = {
  gorev_acildi:  (o) => ["görev açtı", o.govde, "dikkat"],
  sahiplenildi:  (o) => ["işi aldı", sagdanKes(o.govde), ""],
  kanit:         (o) => ["kanıt ekledi", sagdanKes(o.govde), "olumlu"],
  incelemede:    (o) => ["incelemeye verdi", sagdanKes(o.govde), "dikkat"],
  kapandi:       (o) => ["işi kapattı", sagdanKes(o.govde), "olumlu"],
  ret:           (o) => ["geri gönderdi", sagdanKes(o.govde), "kotu"],
  birakildi:     (o) => ["işi bıraktı", sagdanKes(o.govde), "kotu"],
  soru:          (o) => ["soru sordu", sagdanKes(o.govde), "bekleme"],
  cevap:         (o) => ["cevapladı", sagdanKes(o.govde), "bekleme"],
  onay_istendi:  (o) => ["onay istedi", sagdanKes(o.govde), "bekleme"],
  izin_verildi:  (o) => ["izin verildi", o.govde, "dikkat"],
  izinle_gecti:  (o) => ["izinle geçti (sorulmadı)", sagdanKes(o.govde), "dikkat"],
  izin_kaldirildi: (o) => ["izin kaldırıldı", o.govde, ""],
  onay_cevabi:   (o) => ["onay yanıtlandı", o.govde, "bekleme"],
  karar:         (o) => ["karar yazdı", sagdanKes(o.govde), ""],
  olgu:          (o) => ["bilgi eklendi", o.govde, ""],
  olgu_guncellendi: (o) => ["bilgi güncellendi", o.govde, "dikkat"],
  ders:          (o) => ["ders yazıldı", sagdanKes(o.govde), "dikkat"],
  ise_alindi:    (o) => ["işe alındı", ikinciParca(o.govde), ""],
  hata:          (o) => ["hata", o.govde, "kotu"],
  kabin_acildi:  (o) => ["tarayıcı açıldı", o.govde, ""],
  // MODEL / CLI GUNCELLEMESI (29.09.2026): otomatik modda her adim
  // gorunur -- fark edildi, deneme kosuyor, uygulandi/dustu, geri alindi.
  guncelleme_var:     (o) => ["güncelleme bulundu", o.govde, "dikkat"],
  guncelleme_basladi: (o) => ["güncelleme deneniyor", o.govde, "dikkat"],
  guncelleme_uygulandi: (o) => ["güncelleme uygulandı", o.govde, "olumlu"],
  guncelleme_dustu:   (o) => ["güncelleme düştü", o.govde, "kotu"],
  guncelleme_geri_alindi: (o) => ["güncelleme geri alındı", o.govde, "dikkat"],
  kabin_kapandi: (o) => ["tarayıcı kapatıldı", o.govde, ""],
  kabin_dustu:   (o) => ["tarayıcı kapandı", o.govde, "kotu"],
  izin:          (o) => ["izin reddedildi", o.govde, "kotu"],
  uyari:         (o) => ["uyarı", o.govde, "dikkat"],
  arka_kip:      (o) => ["arka planda", o.govde, ""],
  kanitsiz_tur:  (o) => ["iş sürüyor", o.govde, ""],
  onay_geldi:    (o) => ["onay geldi, sürüyor", o.govde, ""],
  brifing:       (o) => ["brifing okudu", o.govde, ""],
  rapor:         (o) => ["rapor verdi", raporTemiz(o.govde), ""],
  proje_acildi:  (o) => ["ofis açıldı", o.govde, ""],
  tur_ozeti:     (o) => ["tur bitti", turOzeti(o.govde), ""],
  // Ajanin kendi notu -- devir paketi bunu okur. SOZDUR, olcum degil.
  durum_notu:    (o) => ["durum notu", o.govde, ""],
  bilgi_onerisi: (o) => ["hafızaya önerdi", o.govde, ""],
  hafiza_onerisi: (o) => ["hafıza önerisi (senin sözün)", o.govde, "bekleme"],
  hafiza_onerisi_red: (o) => ["hafızaya yazılmadı", o.govde, ""],
  birlesti:      (o) => ["bilgiler birleştirildi", o.govde, ""],
  belge_yuklendi: (o) => ["belge yüklendi", o.govde, ""],
  tahmin:        (o) => ["ön tahmin", tahminMetni(o.govde), ""],
  oturum_tazelendi: (o) => ["oturum tazelendi", o.govde, "dikkat"],
  puan:          (o) => ["patron puanladı", o.govde, "dikkat"],
  tahmin_gercek: (o) => ["tahmin / gerçek", tahminMetni(o.govde), ""],
  belge_kaldirildi: (o) => ["belge kaldırıldı", o.govde, ""],
  hafiza_yok:    (o) => ["hafıza: yeni bilgi yok", "", ""],
  // Diskte OLCULEN degisiklik. "degisti" degil "diskte degisti" --
  // ajanin anlatisiyla karismasin diye.
  degisim:       (o) => ["diskte değişti", o.govde, "dikkat"],
  dosya_canli:   (o) => ["dosyaya yazıyor", sagdanKes(o.govde), ""],
  // Patronun CALISAN ajana notu ve notun ULASTIGI an. Ikisi ayri: yazilmak
  // ulasmak degildir (claude'da bir sonraki arac sinirinda ulasir).
  not:           (o) => ["patron not bıraktı", o.govde, "bekleme"],
  not_iletildi:  (o) => ["notu aldı", o.govde, "olumlu"],
  devral:        (o) => ["işi insana verdi (devral)", sagdanKes(o.govde), "dikkat"],
  devral_bitti:  (o) => ["iş ajana geri verildi", sagdanKes(o.govde), "olumlu"],
  devral_dokum:  (o) => ["terminal dökümü kaydedildi", "", ""],
  konsol_acildi: (o) => ["ofis dışı terminal açıldı", o.govde, ""],
  konsol_kapandi:(o) => ["ofis dışı terminal kapandı", o.govde, ""],
};

/* Olay govdesi cogu zaman "<ajan>: <sey>" ya da "#3 baslik -> ajan"
   bicimindedir; ajan adi zaten ayri sutunda gosteriliyor. Tekrari at --
   ilk surumde "demir demir ise alindi" yaziyordu. */
function sagdanKes(govde) {
  let m = (govde || "").replace(/\s+/g, " ").trim();
  m = m.replace(/\s*->\s*[a-z0-9-]+$/i, "");        // "... -> cinar"
  m = m.replace(/^([a-z0-9-]+):\s*/i, "");          // "cinar: ..."
  return m;
}
/* Rapor, ajanin ANLATISIDIR; kanit listesi degil. KANIT satirlari ayri
   kayitlar oldugu icin raporda tekrarlanmalari gurultu uretir. Tek yerde
   temizlenir ki pano, gunluk ve rapor sekmesi ayni seyi gostersin. */
function raporTemiz(govde) {
  return (govde || "").split(String.fromCharCode(10))
    .filter((l) => !/^\s*KANIT\s+\w+\s*:/i.test(l))
    // DURUM satiri devir icindir; ayri olay olarak zaten gorunur.
    .filter((l) => !/^\s*DURUM\s*:/i.test(l))
    .join(" ").replace(/\s+/g, " ").trim();
}

function ikinciParca(govde) {
  const m = (govde || "").match(/\(([^)]+)\)/);
  return m ? m[1] : sagdanKes(govde);
}
function turOzeti(govde) {
  try {
    const x = JSON.parse(govde);
    const j = x.jeton >= 1000 ? (x.jeton / 1000).toFixed(1) + "k" : x.jeton;
    return `${j} jeton` +
           (x.basarili ? "" : " · başarısız");
  } catch (e) { return ""; }
}
function olayOku(o) {
  const c = OLAY[o.tur];
  if (!c) return null;
  const [ne, ayrinti, onem] = c(o);
  return { kim: o.ajan_ad || "ofis", ne, ayrinti: ayrinti || "", onem: onem || "" };
}

/* ─────────────── veri ─────────────── */

async function al(yol, ayar) {
  const y = await fetch(yol, ayar);
  if (!y.ok) {
    // Sunucunun SEBEBI insana okunur verilir. Olculdu (24.09.2026): her
    // 400 hatasi eylem notunda ham JSON olarak (`{"detail": ...}`)
    // gorunuyordu -- sebep oradaydi ama okunmuyordu.
    let metin = await y.text();
    try { const j = JSON.parse(metin); if (j && j.detail) metin = String(j.detail); }
    catch (e) { /* JSON degilse metin oldugu gibi */ }
    throw new Error(metin);
  }
  return y.json();
}
const yolla = (yol, govde) => al(yol, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify(govde),
});

/* EYLEM SONUCU SOYLENIR. Panelde her insan eylemi bu sarmalayicidan
   gecer: basarida ne oldugu (ve halka SURDURULDU mu, surdurulmediyse
   NEDEN), hatada sunucunun sebebi yazilir. Yakalanmayan bir hata insana
   hicbir sey gostermez ve eylemin gittigini sandirir -- komut cubugunda
   bir kez odendi. */
function bildir(metin, tur) {
  // ÜSTTE BİLDİRİM (05.10.2026): alt çubuktaki not açık çekmece/pencere
  // altında kalıyordu; patron "Ekle'ye basıyorum eklemiyor" dedi — sebep
  // yazıyordu ama görünmüyordu. Her eylem sonucu üstte de gösterilir.
  if (metin) {
    let t = document.getElementById("ust-bildirim");
    if (!t) { t = el("div", "ust-bildirim"); t.id = "ust-bildirim"; document.body.append(t); }
    t.textContent = metin;
    t.className = "ust-bildirim gorun" + (tur ? " " + tur : "");
    clearTimeout(bildir._u);
    bildir._u = setTimeout(() => t.classList.remove("gorun"), tur === "kotu" ? 12000 : 5000);
  }
  const n = $("#eylem-notu");
  if (!n) return;
  n.textContent = metin || "";
  n.title = metin || "";
  n.className = "eylem-notu" + (tur ? " " + tur : "");
  clearTimeout(bildir._z);
  bildir._z = setTimeout(() => { n.textContent = ""; n.className = "eylem-notu"; },
                         tur === "kotu" ? 20000 : 12000);
}

/* ONIZLEME (06.10): pencere TIKLAMA aninda acilir (sonra acilan pencereyi
   tarayici engeller), adres sunucudan gelince yuklenir. */
async function onizlemeAc(no) {
  const w = window.open("about:blank", "_blank");
  try {
    const r = await yolla("/api/onizleme", { gorev: no });
    if (w) w.location = r.url; else window.open(r.url, "_blank");
  } catch (e) {
    if (w) w.close();
    bildir("önizleme açılamadı: " + (e.message || e), "kotu");
  }
}

async function eylem(yol, govde, basari) {
  try {
    const r = await yolla(yol, govde || {});
    let m = typeof basari === "function" ? basari(r) : (basari || "tamam");
    if (r && r.surduruldu === true) m += " — halka sürdürülüyor";
    else if (r && r.surduruldu === false && r.sebep && r.sebep !== "istenmedi")
      m += " — sürdürülmedi: " + r.sebep;
    bildir(m, "iyi");
    return r;
  } catch (e) {
    bildir(String(e.message || e).slice(0, 240), "kotu");
    return null;
  } finally {
    yenile();
  }
}

/* KOSU DURUMU. Panel `/api/lider-durum`u hic okumuyordu: lider ya da
   halka kosarken bunu soyleyen tek sey girdi kutusunun yer tutucusuydu. */
async function kosuDurumu() {
  const d = $("#komut-surdur");
  if (!d) return;
  try {
    const k = await al("/api/lider-durum");
    // KOSARKEN DUGME "DURDUR" OLUR: baslayan bir isi durdurmanin panelde
    // hicbir yolu yoktu. Durdurma YUMUSAK -- kosan tur biter, yenisi baslamaz.
    d.classList.toggle("kosuyor", !!k.calisiyor);
    d.dataset.kip = k.calisiyor ? "durdur" : "surdur";
    d.disabled = !!(k.calisiyor && k.dur);
    d.innerHTML = !k.calisiyor ? "&#9654; Sürdür"
                : k.dur ? "durduruluyor…" : "&#9632; Durdur";
    d.title = !k.calisiyor
      ? "Açık işleri kaldığı yerden sürdür (yeni hedef vermeden). Tur başına tavanlı."
      : "Ofis koşuyor: " + (k.mesaj || "?") +
        " — Durdur: koşan tur BİTİNCE yenisi başlamaz; kısmi kanıt korunur.";
    clearTimeout(kosuDurumu._z);
    if (k.calisiyor) kosuDurumu._z = setTimeout(kosuDurumu, 2000);
  } catch (e) { d.title = "koşu durumu okunamadı: " + e.message; }
}

async function yenile() {
  kosuDurumu();
  // OTOMATIK TARAYICI (02.10.2026): ajan tarayici gereken ise baslayinca
  // ofis kabini KENDISI acar; panel bunu burada gorur ve gosterir.
  kabinDurum().then((d) => {
    if (d && d.acik && !K.acik) { kabinGoster(d); kabinBagla(); }
  }).catch(() => {});
  await devralAl();
  D.ofis  = await al("/api/ofis");
  D.tahta = await al("/api/tahta" + (D.kanat ? "?kanat=" + D.kanat : ""));
  cizSerit(); cizGorunum(); cizBekleyenler(); cizSekme(); cizBaglam();
  cizKullanim();
  cizKod();
}

/* ─────────────── üst şerit ─────────────── */

function cizSerit() {
  const o = D.ofis;
  $("#proje-ad").textContent   = o.proje.ad;
  $("#proje-amac").textContent = o.proje.amac || "";

  const k = $("#kanatlar");
  k.innerHTML = "";
  const hepsi = el("button", "kanat-sekme" + (D.kanat ? "" : " secili"));
  hepsi.append(el("span", "kanat-ad", "TÜM OFİS"),
               el("span", "kanat-sayac", o.ajanlar.length + " ajan"));
  hepsi.onclick = () => { D.kanat = ""; yenile(); };
  k.append(hepsi);
  for (const kn of o.kanatlar) {
    const b = el("button", "kanat-sekme" + (D.kanat === kn.id ? " secili" : ""));
    b.style.setProperty("--kanat-renk", kn.renk);
    b.append(el("span", "kanat-ad", kn.ad),
             el("span", "kanat-sayac", kn.calisan + " / " + kn.gorev));
    b.title = `${kn.ad}: ${kn.calisan} iş çalışıyor, toplam ${kn.gorev} iş`;
    b.onclick = () => { D.kanat = kn.id; yenile(); };
    k.append(b);
  }
  // YONET (05.10.2026): secili takimin ajanlari, motorlari, modelleri.
  if (D.kanat) {
    const yon = el("button", "kanat-sekme kanat-yonet", "⚙ Yönet");
    yon.title = "Bu takımı yönet: ajan ekle/çıkar/taşı, motor ve model, lider, şablon";
    yon.onclick = () => organizasyonAc(D.kanat);
    k.append(yon);
  }
  // + TAKIM: yeni kanat. Kurulunca secilir ve ilk adim SOYLENIR (lider).
  const yeni = el("button", "kanat-sekme kanat-ekle", "+");
  yeni.title = "Yeni takım (kanat) kur — kendi ofisi, kadrosu ve lideri olur.";
  yeni.onclick = takimEkleAc;
  k.append(yeni);

  // TEK BICIM (01.10.2026): kendi bicimi "41335.3k jeton" yaziyordu.
  const jeton = jetonYaz(o.olcum.jeton);
  const oge = (deger, etiket, sinif) => {
    const d = el("div", "ray-oge" + (sinif ? " " + sinif : ""));
    d.append(el("b", null, String(deger)), el("span", null, etiket));
    return d;
  };
  const bekleyen = o.bekleyen_soru + o.bekleyen_onay;
  const r = $("#ray");
  r.innerHTML = "";
  r.append(oge(o.sayim.calisiyor, "çalışıyor"),
           oge(o.sayim.inceleme, "incelemede"));
  if (bekleyen) r.append(oge(bekleyen, "seni bekliyor", "bekliyor"));
  r.append(el("div", "ray-ayrac"), oge(jeton, "jeton"));

  // PARA GORUNUR OLMALI. Olculdu (21.09.2026): haftalik kapi
  // butcesinin $2,14'u harcanmisti, para kilidi kapaliydi, gorsel
  // kotasi doluydu -- ve panele bakan biri hicbirini goremiyordu.
  // Ofisin kendi kurali: *gorunmeyen butce, butce degildir.*
  // HESAPLARIN DOLULUGU (27.09.2026): abonelikte dolar yok; saglayicinin
  // KENDI yuzdesi gosterilir. Olculmeyen hesap cizilmez (uydurulmaz).
  const p = o.para || {};
  // HESAPLAR TEK DUGME (27.09.2026). Onceden hesap basina, pencere basina
  // cip vardi; kullanici: "ilerde baska hesaplar olacak, karmasik
  // olmasin." Artik hesap basina bir ince cubuk + yalniz SORUNU soyleyen
  // yazi; 2 hesapta da 10 hesapta da ayni yer. Tiklayinca hesap panosu.
  const hd = el("button", "hesap-hap");
  hd.type = "button";
  hd.onclick = hesapPanosuAc;
  r.append(hd);
  hesapDugmesiCiz(hd, D.hesaplar);
  hesaplariAl().then(t => hesapDugmesiCiz(hd, t)).catch(() => {});
  if (p.kilit_kapali) {
    const k = oge("KİLİTLİ", "para harcama");
    k.title = "Ücretli görsel/video üreticileri kapalı. Ajanlar da aşamaz. " +
              "Açmak: kabuk gorsel para ac";
    r.append(k);
  }

  const m = $("#motor-rozetleri");
  m.innerHTML = "";
  for (const [ad, acik] of Object.entries(o.motorlar)) {
    // SAHTE MOTOR patronun paneline ait degil (30.09, kullanici: "sahte
    // motor, sahte veri yerine gercek"); yalniz sinamalarda yasar.
    if (ad === "sahte") continue;
    // Uydurmaz: kurulu mu degil mi OLCULUR.
    const d = el("div", "motor-rozet" + (acik ? " acik" : ""));
    d.append(el("i"), el("span", null, ad));
    d.title = (acik ? ad + " bu makinede kurulu" : ad + " bulunamadı") +
              (ad === "sahte" ? "" : " — tıkla: neyi yapar, neyi yapamaz");
    if (ad !== "sahte") { d.style.cursor = "pointer"; d.onclick = () => motorKartiAc(ad); }
    m.append(d);
  }
}

/* DURUST MOTOR KARTI (E60). Motorlar esit degil ve bu GIZLENMEZ:
   her hucre motor matrisinin son OLCUMUNDEN gelir. Adaptorun "tasirim"
   iddiasi olcum degildir -- olculmemisse "ölçülmedi" yazar. "yok" kusur
   degil durust bildirim, "YALAN" kusurdur. */
const KART_DURUM = {
  var: ["✓", "iyi", "var"], yok: ["–", "sonuk", "yok"], bilgi: ["i", "sonuk", "bilgi"],
  YALAN: ["✗", "kotu", "YALAN"], KALDI: ["✗", "kotu", "kaldı"], hata: ["?", "uyari", "ölçüm düştü"],
  olculemedi: ["?", "uyari", "ölçülemedi"], olculmedi: ["?", "uyari", "ölçülmedi"],
  bayat: ["?", "uyari", "yeniden ölçülmeli"],
};
async function motorKartiAc(secili) {
  D.acikCekmece = { tur: "motor" };
  cekmeceAc(c => { cekBas(c, "MOTORLAR", "Motor kartı"); c.append(el("div", "bos-yazi", "ölçülüyor…")); });
  let r;
  try { r = await al("/api/motor_karti"); }
  catch (e) { return cekmeceAc(c => { cekBas(c, "MOTORLAR", "Motor kartı"); c.append(el("div", "bos-yazi", "okunamadı: " + e.message)); }); }
  if ((D.acikCekmece || {}).tur !== "motor") return;
  cekmeceAc(c => {
    cekBas(c, "MOTORLAR", "Motor kartı — neyi yapar, neyi yapamaz");
    c.append(el("div", "hp-not",
      "Her satır motor matrisinin GERÇEK ölçümünden gelir. “yok” kusur değildir, " +
      "motor dürüstçe yapamadığını söylüyor ve ofis o işi ona vermez. “ölçülmedi”: " +
      "adaptör iddia ediyor ama henüz sınanmadı (testler/matris.py)."));
    const kartlar = (r.kartlar || []).slice().sort((a, b) => (a.motor === secili ? -1 : b.motor === secili ? 1 : 0));
    for (const k of kartlar) {
      const b = el("div", "mk-kart" + (k.motor === secili ? " secili" : ""));
      const bas = el("div", "mk-bas");
      bas.append(el("b", null, k.motor));
      bas.append(el("span", "mk-rozet " + (k.kurulu ? "iyi" : "kotu"), k.kurulu ? "kullanılabilir" : "kullanılamıyor"));
      if (k.hukum) bas.append(el("span", "mk-rozet " + (k.hukum === "KABUL" ? "iyi" : "kotu"), "matris: " + k.hukum));
      b.append(bas);
      b.append(el("div", "mk-alt", k.olculdu
        ? `son ölçüm ${String(k.zaman || "").replace("T", " ")} · ${k.model || ""}`
        : "bu motor matristen hiç geçmedi — satırlar ölçüm değil"));
      if (k.durum_notu) b.append(el("div", "hp-sebep", k.durum_notu));
      const t = el("div", "mk-tablo");
      for (const h of k.hucreler) {
        const [imi, sinif, yazi] = KART_DURUM[h.durum] || ["?", "uyari", h.durum];
        const s = el("div", "mk-satir");
        s.title = `${h.ne}\n\n${h.not}`;
        s.append(el("span", "mk-imi " + sinif, imi), el("span", "mk-ad", h.ad_tr + (h.zorunlu ? " *" : "")),
                 el("span", "mk-durum " + sinif, yazi));
        t.append(s);
      }
      b.append(t);
      c.append(b);
    }
    c.append(el("div", "hp-not", "* zorunlu yetenek: eksikse motor deftere girmez."));
  });
}

/* ─────────────── ofis görünümü ─────────────── */

/* UC SUTUN AYNI ANDA CIZILIR.
   Onceden yalnizca secili sekme cizilirdi; simdi ucu de canli. Maliyet
   gercek (her tazelemede uc cizim) ama kazanc daha buyuk: ofisi
   izlerken terminalin aktigini ve tahtanin degistigini ayni anda
   goruyorsun. Izleme yuzeyinin butun degeri bu.

   Daraltilmis sutun CIZILMEZ -- gorunmeyen seyi cizmek bos is. */
function cizGorunum() {
  const ciz = { ofis: cizOfis, terminal: cizCanli, gorevler: cizTahta };
  // INSAN NOT YAZARKEN pano yeniden cizilmez (Hafiza'daki kuralin aynisi):
  // her canli olay terminali bastan cizer ve yarim not SILINIRDI.
  const odak = document.activeElement;
  const yaziyor = odak && odak.closest && odak.closest(".pano-not") && odak.value;
  const kok = { ofis: "#gorunum-ofis", terminal: "#gorunum-canli" };
  for (const p of Object.keys(ciz)) {
    if (!panoAcik(p)) continue;
    if (yaziyor && kok[p] && $(kok[p]) && $(kok[p]).contains(odak)) continue;
    ciz[p]();
  }
  sutunSayaclari();
}

/* Sutun basliklarindaki sayilar OLCULUR. Baslikta sayi olmasi,
   daraltilmis bir sutunun bile ne tasidigini soylemesini saglar --
   kapali bir panel "orada bir sey var mi" sorusunu cevapsiz
   birakmamali. */
function sutunSayaclari() {
  const o = D.ofis;
  if (!o) return;
  const ajanlar = o.ajanlar.filter((a) => !D.kanat || a.kanat_id === D.kanat);
  const calisan = ajanlar.filter((a) => a.oda === "masa").length;
  const izlenen = ajanlar.filter((a) => a.oda !== "mola").length;
  const acik = (D.tahta ? Object.entries(D.tahta) : [])
    .filter(([k]) => k !== "bitti")
    .reduce((n, [, v]) => n + v.length, 0);
  const yaz = (id, m) => { const e = $(id); if (e) e.textContent = m; };
  yaz("#sayac-ofis", `${calisan}/${ajanlar.length}`);
  yaz("#sayac-canli", izlenen ? String(izlenen) : "");
  yaz("#sayac-tahta", acik ? String(acik) : "");
}

/* ─────────────── canlı izle ───────────────
   Terminaller silinmedi, YERI verildi. Varsayilan gorunum sade kalir;
   izlemek isteyen buraya gelir. Molada olan ajan gosterilmez -- bos pano
   bilgi degil gurultudur. */
/* OKUNUR KIP -- "ajan ne SOYLEDI", "ajan ne YAPTI" degil.

   Iki ayri soru var ve tek akis ikisini birden kotu cevapliyor:
     - ayikliyorum  -> hangi araci cagirdi, izin dustu mu, kac jeton
     - takip ediyorum -> ne buldu, ne yazdi, neyi kanitladi

   Terminal kipi birinciyi cevaplar. Ikincisini cevaplamak icin arac
   gurultusu (arac · arac_sonuc · brifing · sahiplenildi · tur_ozeti)
   susturulur ve geriye ajanin SOZU kalir.

   Susturulanlar SILINMEZ, gizlenir: bir sey dagitiyorsa kaldirilmaz,
   yeri degistirilir. Anahtar geri cevrildiginde hepsi yerinde. */
const OKUNUR_TURLER = new Set([
  "cikti", "rapor", "kanit", "soru", "cevap", "onay_istendi",
  "hata", "izin", "ret", "ders", "not", "not_iletildi",
]);

/* TERMINAL GORUNUMU (28.09.2026). Kullanici: "ajanlar calisirken
   terminalleri normal terminal gibi gorunsun" (VS Code / PowerShell
   ekranlari). Ajanlar arka planda SESSIZ kipte kosmaya devam eder -- onay
   kapisi, kanit, limit devri, Durdur hep ona bagli; gosterim ise bir
   terminal oturumunun diliyle: `● Arac(ne)` / `  ⎿ sonuc`. Gercek,
   yazilabilir terminal "Devral"dadir. Hicbir sey UYDURULMAZ: defterde
   ne varsa o cizilir; komut bilinmiyorsa yalniz arac adi yazilir. */
function aracAdi(ad) {
  const m = /^mcp__(.+?)__(.+)$/.exec(ad || "");
  return m ? `${m[1].replace(/^claude_ai_/, "")}.${m[2]}` : (ad || "araç");
}

function terminalSatiri(o) {
  const g = o.govde || "";
  const s = el("div", "t-satir");
  const ekle = (sinif, metin) => { s.append(el("span", sinif, metin)); };
  switch (o.tur) {
    case "arac": {
      const i = g.indexOf("\n");
      const ad = i >= 0 ? g.slice(0, i) : g;
      const ne = i >= 0 ? g.slice(i + 1) : "";
      s.classList.add("t-arac");
      ekle("t-imi", "● ");
      ekle("t-ad", aracAdi(ad));
      if (ne) ekle("t-ne", "(" + kes(ne, 180) + ")");
      return s;
    }
    case "arac_sonuc": {
      const satirlar = g.split(/\r?\n/).filter((x) => x.trim()).slice(0, 4);
      if (!satirlar.length) return null;
      s.classList.add("t-sonuc");
      ekle("t-imi", "  ⎿ ");
      ekle(null, satirlar.map((x) => kes(x, 160)).join("\n     "));
      return s;
    }
    case "izin":
      s.classList.add("t-hata"); ekle("t-imi", "  ⎿ ✗ "); ekle(null, kes(g, 200)); return s;
    case "cikti": case "rapor": {
      // Ajanin SOZU: Claude Code'daki gibi beyaz nokta + metin; **kalin**
      // kalin cizilir, yildizlar gosterilmez. KANIT satirlari zaten ayri
      // kayit, burada tekrarlanmaz.
      const metin = raporTemiz(g).trim();
      if (!metin) return null;
      s.classList.add("t-metin");
      ekle("t-imi", "● ");
      const govde = el("span", "t-soz");
      kes(metin, 900).split(/(\*\*[^*\n]+\*\*)/).forEach((p) => {
        if (/^\*\*[^*]+\*\*$/.test(p)) govde.append(el("b", null, p.slice(2, -2)));
        else if (p) govde.append(document.createTextNode(p.replace(/^#{1,4} /gm, "")));
      });
      s.append(govde);
      return s;
    }
    case "kanit": s.classList.add("t-iyi"); ekle("t-imi", "✓ "); ekle(null, "kanıt: " + kes(g, 200)); return s;
    case "incelemede": case "kapandi":
      s.classList.add("t-iyi"); ekle("t-imi", "✓ "); ekle(null, (o.tur === "kapandi" ? "iş kapandı: " : "incelemeye verdi: ") + kes(g, 160)); return s;
    case "degisim": s.classList.add("t-diff"); ekle("t-imi", "± "); ekle(null, kes(g, 200)); return s;
    case "dosya_canli": s.classList.add("t-sonuk"); ekle("t-imi", "✎ "); ekle(null, kes(g, 200)); return s;
    case "hata": case "uyari": case "ret": case "ders":
      s.classList.add("t-hata"); ekle("t-imi", "✗ "); ekle(null, kes(g, 300)); return s;
    case "soru": case "onay_istendi": case "cevap": {
      s.classList.add("t-bekle"); ekle("t-imi", "? ");
      const govde = el("span");
      kes(g, 300).split(/(\*\*[^*\n]+\*\*)/).forEach((p) => {
        if (/^\*\*[^*]+\*\*$/.test(p)) govde.append(el("b", null, p.slice(2, -2)));
        else if (p) govde.append(document.createTextNode(p));
      });
      s.append(govde);
      return s;
    }
    case "not": case "not_iletildi":
      s.classList.add("t-bekle"); ekle("t-imi", "✉ "); ekle(null, kes(g, 300)); return s;
    case "tur_ozeti":
      s.classList.add("t-sonuk"); ekle(null, "✻ tur bitti · " + turOzeti(g)); return s;
    case "sahiplenildi":
      // Turun BASI: terminalde kullanicinin istemi gibi okunur.
      s.classList.add("t-istem"); ekle("t-imi", "> "); ekle(null, kes(g, 200)); return s;
    case "brifing":
      s.classList.add("t-sonuk"); ekle("t-imi", "  ⎿ "); ekle(null, kes(g, 200)); return s;
    default:
      return null;
  }
}

function panoSatiri(o) {
  const sinif = PANO_SINIF[o.tur];
  if (sinif === undefined) return null;
  if (D.okunurKip && !OKUNUR_TURLER.has(o.tur)) return null;
  // Terminal kipi (varsayilan): terminal oturumu diliyle ciz.
  if (!D.okunurKip) return terminalSatiri(o);
  const okunur = olayOku(o);
  const satir = el("div", sinif);
  // Okunur kipte ajanin kendi metni KESILMEZ: takip etmek icin
  // okunuyor, ayiklamak icin degil. Terminal kipinde kesilir cunku
  // orada aranan sey akisin sekli, cumlenin tamami degil.
  const uzun = D.okunurKip ? 4000 : 220;
  // Okunur kipte ajanin metninden KANIT satirlari CIKARILIR: onlar
  // zaten ayri birer kayit olarak listede duruyor ve iki kez okunmak
  // gurultudur. Kural mevcuttu (`raporTemiz`, "rapor anlatidir, kanit
  // listesi degil") ama `cikti`ya uygulanmiyordu -- kuralin yarisi.
  // Terminal kipinde ham birakilir: orada aranan sey ciktinin kendisi.
  const ham = D.okunurKip && o.tur === "cikti"
    ? raporTemiz(o.govde) : (o.govde || "").replace(/\s+/g, " ");
  if (D.okunurKip && o.tur === "cikti" && !ham.trim()) return null;
  satir.textContent = okunur
    ? `${okunur.ne}${okunur.ayrinti ? ": " + okunur.ayrinti : ""}`
    : kes(ham, uzun);
  return satir;
}

/* Jeton okunur hale: 1.407.411 -> "1.41M". Ham sayi insana bir sey
   soylemez; panelin kurali zaten "ham veri gosterilmez". */
function jetonYaz(n) {
  if (!n) return "0";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return Math.round(n / 1e3) + "k";
  return String(n);
}

/* KULLANIM KARTI -- panonun ustunde, jeton + API karsiligi.

   TEK KURAL BU KARTI DOGRU YAPAR: fiyatlanamayan tur SAHTE BIR $0
   olarak toplanmaz. `maliyet_usd = 0` OLCULMUS sifirdir; `null`
   OLCULEMEMISTIR. Ikisini ayni saymak, bilinmeyen maliyeti sifir ilan
   etmek olurdu -- *gorunmeyen butce, butce degildir.*

   Fiyatlanamayan tur varsa kart onu SAYAR ("2 tur fiyatsiz"); hicbiri
   fiyatlanamadiysa tutar yerine "fiyatsiz" yazar. */
function kullanimKarti(a) {
  const k = (a.sicil || {}).kullanim;
  if (!k) return null;
  const kart = el("div", "kullanim");
  const blok = (etiket, v) => {
    if (!v || !v.tur) return null;
    const b = el("div", "kullanim-blok");
    b.append(el("span", "kullanim-etiket", etiket));
    b.append(el("b", "kullanim-jeton", jetonYaz(v.jeton) + " jeton"));
    // 27.09.2026: abonelikte dolar gosterilmez -- olcu jeton ve
    // hesabin kendi yuzdesi (pano basligi). Dolar yalniz API hesabinda.
    b.append(el("span", "kullanim-alt", v.tur + " tur"));
    return b;
  };
  const no = (a.sicil.son_gorev || {}).no;
  const bu = no != null ? (k.ise_gore || {})[no] : null;
  const b1 = blok(no != null ? "#" + no : "bu iş", bu);
  const b2 = blok("tüm turlar", k.tum);
  if (b1) kart.append(b1);
  if (b2) kart.append(b2);
  return kart.children.length ? kart : null;
}

/* TEK PANO KURUCUSU -- iki gorunum de bunu cagirir.

   Neden tek: `cizOfis` ile `cizCanli` bir donem AYRI AYRI pano
   kuruyordu ve ikisi ayni seyi yapiyordu. Bu projede iki kopyadan biri
   duzeltilip oteki unutuldugu icin ALTI kez hata cikti; kopya daha
   buyumeden kapatildi.

   PANO ICI HER ZAMAN DOM'DA: ciktisi olmayan panoya `ic` eklenmezse
   canli akis GORUNMEYEN bir dugume yazar ve ajan kosarken pano bos
   kalir (bir kez odendi, 21.09). */
/* Bir pencerenin yuzdesi -- TEK bicim. Yenilenmis pencerenin bayat
   yuzdesi GOSTERILMEZ (kullanim.py kurali). */
function pencereYazi(w) {
  return w.yenilendi || w.kullanim == null ? "yenilendi"
       : `%${Math.round(w.kullanim * 100)}`;
}

/* Bu turu kosan HESABIN olculen penceresi. Hesap adi normallesir:
   ajanin kendi basamagi ("") ile ortuk hesap (motorun adi) ayni hesaptir. */
function hesapPenceresi(motor, hesap) {
  if (!motor) return null;
  const h = hesap && hesap !== motor ? hesap : "";
  return (D.pencereler || []).find(p => p.motor === motor && (p.hesap || "") === h) || null;
}
/* HANGI HESAP (08.10, B7): terminal basliginda ajanin HANGI aboneligiyle
   calistigi -- e-posta ve plan, hesap tablosundan (`/api/hesaplar`, tek
   kaynak). Bilinmiyorsa uydurulmaz: rozet yok. */
const PLAN_AD = { max: "Max", max5: "Max 5x", max20: "Max 20x", pro: "Pro", plus: "Plus",
                  pro200: "Pro", team: "Team", ultra: "Ultra" };
function hesapKaydi(motor, hesap) {
  if (!motor) return null;
  const hs = ((D.hesaplar || {}).hesaplar || [])
    .filter(r => r.motor === motor && r.durum !== "kapali");
  const h = hesap && hesap !== motor ? hesap : "";
  return hs.find(r => (r.hesap || "") === h || r.ad === hesap) || (h ? null : hs[0]) || null;
}
function hesapEtiketi(r) {
  if (!r) return "";
  const kim = r.eposta ? r.eposta.split("@")[0] : r.ad;
  const plan = r.plan ? (PLAN_AD[r.plan] || r.plan) : "";
  return kim + (plan ? " · " + plan : "");
}

/* BEKLEYEN SERIT (B6): `cizBekleyenler`in son okudugu kuyruktan (D.bekleyen). */
function bekleyenSeridi(a) {
  const b = D.bekleyen || {};
  const sorular = (b.sorular || []).filter((x) => x.gonderen === a.ad);
  const onaylar = (b.onaylar || []).filter((x) => x.isteyen === a.ad);
  if (!sorular.length && !onaylar.length) return null;
  const k = el("div", "pano-bekleyen");
  for (const q of sorular) {
    const sat = el("div", "pano-bekleyen-soru");
    sat.append(el("b", null, "? sana soruyor: "), document.createTextNode(q.govde));
    k.append(sat);
    const eylem_ = el("div", "istek-eylem");
    let secili = q.secim && q.secim.onerilen != null ? q.secim.onerilen : null;
    if (q.secim) {
      const sec = el("div", "secenekler");
      const dg = q.secim.secenekler.map((t, i) => {
        const d = el("button", "secenek" + (i === secili ? " secili" : ""),
                     t + (i === q.secim.onerilen ? "  ★" : ""));
        d.onclick = (e) => { e.stopPropagation(); secili = i;
          dg.forEach((x, j) => x.classList.toggle("secili", j === i)); };
        return d;
      });
      sec.append(...dg);
      k.append(sec);
    }
    const girdi = el("input");
    girdi.placeholder = q.secim ? "İstersen not ekle…" : "Cevabın…";
    girdi.onclick = (e) => e.stopPropagation();
    const gonder = (e) => {
      if (e) e.stopPropagation();
      const ek = girdi.value.trim();
      const metin = q.secim && secili != null ? q.secim.secenekler[secili] + (ek ? " — " + ek : "") : ek;
      if (!metin) return;
      eylem(`/api/soru/${q.id}/cevap`, { metin }, "cevap gönderildi");
    };
    const dug = el("button", "dugme olumlu", "Cevapla");
    dug.onclick = gonder;
    girdi.addEventListener("keydown", (e) => { if (e.key === "Enter") gonder(e); });
    eylem_.append(girdi, dug);
    k.append(eylem_);
  }
  for (const o of onaylar) {
    const sat = el("div", "pano-bekleyen-soru");
    sat.append(el("b", null, "⏸ onayını bekliyor: "), document.createTextNode(o.eylem),
               el("span", "dt-alt", "  — sağdaki “Senden bekleniyor” kartından onayla/reddet"));
    k.append(sat);
  }
  return k;
}

function panoKur(a, secenek) {
  const s = secenek || {};
  // TERMINAL KIPI (varsayilan): pano bastan sona bir terminal penceresi --
  // baslik cubugu, akis, istem kutusu, durum satiri. Okunur kip eski
  // kart duzenini korur (orada aranan sey okumak, terminal degil).
  const term = !D.okunurKip;
  const p = el("div", "pano" + (term ? " term" : "") + (s.sinif ? " " + s.sinif : ""));
  const bas = el("div", "pano-bas");
  // DURUM NOKTASI: canli mi gecmis mi. Rakipte de basligin ilk ogesi
  // bu ve isi ayni -- "bu pano su an akiyor mu" sorusu bir bakista
  // cevaplanmali, yoksa bayat bir cikti canli sanilir.
  const nokta = el("span", "pano-nokta" + (s.gecmis ? " sonuk" : ""));
  nokta.title = s.gecmis ? "son turun ciktisi -- su an akmiyor" : "canli";
  bas.append(nokta,
             el("span", "pano-ad", a.ad), el("span", "pano-meslek", a.meslek));
  if (a.gorev_no) bas.append(el("span", "pano-gorev", "#" + a.gorev_no));
  // MOTOR/MODEL ROZETI: hangi motorun hangi modeliyle kostugu basligin
  // bilgisidir. Olculmus kayittan gelir (`tur_ozeti`), ajanin
  // AYARINDAN degil -- zincir devrettiginde ayar YANLIS cevabi verir.
  const sonTur = (a.sicil || {}).son_tur || {};
  // ILK TUR (06.10, patron: "hangi model yazmiyor"): olcum ancak tur bitince
  // gelir; o zamana kadar ajanin AYARINDAKI model yazilir (ve oyle soylenir).
  // OKUNUR AD (09.10.2026, patron: "sonnet yaziyor hangi ai model belli degil"):
  // sunucu takma adi sabitlenen kimlige cevirip okunur ad verir (`model_ad`).
  const olculen = [sonTur.motor, sonTur.model_ad || sonTur.model].filter(Boolean).join(" ");
  const ayar = [a.motor, a.model_ad || a.model].filter(Boolean).join(" ");
  // AJANIN KENDI MODELI vs SON TUR (07.10.2026, patron: "lider neden fable
  // 5.1, tiklayinca opus 5.5 gorunuyor?"): son tur kapi modeline (hakem)
  // yukseltilmis inceleme ya da hesap zinciri devriyse rozet yalniz olculeni
  // yazinca ajanin modeli degismis sanildi. Ana rozet ajanin modeli; farkli
  // turda ikinci rozet "son tur: ..." ve sebebi.
  // 08.10.2026 (patron: "hem sonnet hem opus yaziyor terminalde?"): model
  // degistirilip yeni tur basladiginda "son tur: <eski model>" rozeti iki
  // model ayni anda calisiyormus gibi gorunuyordu. Ajan CALISIRKEN yalniz
  // simdiki model; bostayken farkliysa "onceki tur".
  const calisiyor = a.oda === "masa" || a.calisiyor;
  const farkli = !calisiyor && olculen && ayar
    && !modelAyni(a.motor, a.model, sonTur.motor, sonTur.model);
  const motorAd = farkli ? ayar : (olculen || ayar);
  if (motorAd) {
    const m = el("span", "pano-motor", motorAd.replace("claude-", ""));
    m.title = farkli ? "ajanın kendi motoru/modeli"
      : olculen ? "son turda ölçülen motor/model" : "ajanın ayarı (tur bitince ölçülen yazılır)";
    bas.append(m);
  }
  if (farkli) {
    const s2 = el("span", "pano-motor farkli", "önceki tur: " + olculen.replace("claude-", ""));
    s2.title = "Ajanın bir önceki turu başka modelle koştu: model sonradan değiştirilmiş ya da "
      + "hesap zinciri (limit) başka hesaba/motora devretmiş olabilir. Şu anki model soldaki.";
    bas.append(s2);
  }
  // BAGLAM (06.10, E34): ajanin aklinin ne kadari dolu. Olculmediyse YOK;
  // sinir bilinmiyorsa yalniz jeton. %80'de bir sonraki tur temiz oturumla
  // (devir paketiyle) baslar.
  const bg = sonTur.baglam;
  if (bg && bg.dolu) {
    const yuzde = bg.oran != null ? Math.round(bg.oran * 100) : null;
    const r = el("span", "pano-motor" + (yuzde != null && yuzde >= 80 ? " dolu" : ""),
                 yuzde != null ? `bağlam %${yuzde}` : `bağlam ${Math.round(bg.dolu / 1000)}b`);
    r.title = `son turda ${bg.dolu.toLocaleString("tr-TR")} jeton`
      + (bg.sinir ? ` / ${bg.sinir.toLocaleString("tr-TR")} sınır` : " (sınır bilinmiyor)")
      + ". %80'i geçince sonraki tur temiz oturumla, kaldığı yerden başlar.";
    bas.append(r);
  }
  // HESAP LIMITI: rakip her pano basliginda haftalik limiti gosteriyor.
  // Bizde olculuyor (saglayicinin kendi bildirimi) ama yalniz Hesap
  // sekmesindeydi. Olcum yoksa rozet YOK -- uydurulan bir yuzde,
  // yanlis gosteren gostergenin en sinsi turu olurdu.
  const hMotor = sonTur.motor || a.motor;
  const hSatir = hesapKaydi(hMotor, sonTur.motor ? sonTur.hesap : "");
  const pen = hesapPenceresi(sonTur.motor, sonTur.hesap);
  if (hSatir && !pen) {
    const hr = el("span", "pano-limit", hesapEtiketi(hSatir));
    hr.title = `${hSatir.saglayici || hMotor} hesabı: ${hSatir.eposta || hSatir.ad}` +
      (sonTur.motor ? " (son turda bununla çalıştı)" : " (ajanın motorunun ilk hesabı; tur bitince ölçülen yazılır)");
    bas.append(hr);
  }
  if (pen) {
    const parca = Object.entries(pen.pencereler)
      .map(([ad, w]) => `${ad} ${pencereYazi(w)}`);
    const dolu = Object.values(pen.pencereler)
      .some(w => w.kullanim != null && w.kullanim >= 0.8);
    // E63: HANGI HESAPTAN yedigi basta yazar -- iki codex hesabi varsa
    // yuzdeyi yanlis hesaba baglamak kolaydir.
    const hesapAd = hesapEtiketi(hSatir) || pen.hesap || pen.motor;
    const r = el("span", "pano-limit" + (dolu ? " dolu" : ""), `${hesapAd}: ${parca.join(" · ")}`);
    r.title = `${pen.motor}${pen.hesap ? "/" + pen.hesap : ""} hesabının TOPLAM kullanımı — ` +
      (pen.yas_dk == null ? "ölçüm yaşı bilinmiyor" : `${pen.yas_dk} dk önce ölçüldü`) +
      ` (${pen.kaynak || "sağlayıcı bildirimi"})`;
    bas.append(r);
  }
  if (s.gecmis) {
    const g = el("span", "pano-gecmis", "son tur");
    g.title = "Bu ajan su an kosmuyor; asagidaki cikti onceki turdan.";
    bas.append(g);
  } else {
    const odaAd = (ODALAR.find((o) => o[0] === a.oda) || [])[2] || "";
    bas.append(el("span", "pano-oda " + a.oda, odaAd));
  }
  // DEVRAL (E18): elinde is olan ajanin panosunda. Kosan tur varken
  // sunucu reddeder ve SEBEBINI soyler ("once Durdur").
  // Gercek terminal kipinde Devral YOK: insan terminale zaten yazabiliyor;
  // devral ikinci bir terminal acardi.
  if (!s.gecmis && a.gorev_no && !devralinmisMi(a.gorev_no) && !(D.tui || {})[a.ad]) {
    const dv = el("button", "pano-dugme devral-dugme", "⌨ Devral");
    dv.title = "Bu işi al: ajanın kendi oturumu gerçek bir terminalde açılır. " +
               "Ajan o sırada çalışmaz; işin bitince 'Ofise geri ver'.";
    dv.onclick = (e) => { e.stopPropagation(); devralBaslat(a.gorev_no); };
    bas.append(dv);
  }
  if (s.dugmeler) {
    bas.append(el("span", "pano-bosluk"));
    for (const [ad, islev] of s.dugmeler) {
      const d = el("button", "pano-dugme", ad);
      d.onclick = (e) => { e.stopPropagation(); islev(); };
      bas.append(d);
    }
  } else {
    bas.onclick = () => ajanAc(a.ad);
    bas.style.cursor = "pointer";
  }

  const ic = el("div", "pano-ic" + (D.okunurKip ? " okunur" : ""));
  let yazildi = 0;
  const kendi = D.olaylar.filter((o) => o.ajan_ad === a.ad).slice(-120);
  // `rapor`, turun sonunda akan `cikti` parcalarinin BIRLESMIS halidir
  // (koltuk: `"".join(tam_metin)`) -- yani ayni metin. Okunur kipte
  // ikisini birden gostermek, ayni cumleyi iki kez okutmak olurdu.
  //
  // Hangisi atilir sorusunun cevabi ZAMANA bagli: tur KOSARKEN henuz
  // rapor yoktur, yalnizca akis vardir. Raporu atsaydik canli okuma
  // calisir ama biten turda parcali metin kalirdi; akisi kosulsuz
  // atsaydik canli okuma BOS gorunurdu. Bu yuzden: raporu OLAN turun
  // akisi gizlenir, olmayanin akisi kalir.
  const sonRapor = D.okunurKip
    ? kendi.map((o, i) => (o.tur === "rapor" ? i : -1)).reduce((a2, b) => Math.max(a2, b), -1)
    : -1;
  kendi.forEach((o, i) => {
    if (sonRapor >= 0 && o.tur === "cikti" && i < sonRapor) return;
    const satir = panoSatiri(o);
    if (satir) { ic.append(satir); yazildi++; }
  });
  // UYDURMAZ -- ve BOSLUGUN SEBEBINI SOYLER. Okunur kipte sustugumuz
  // satirlar VAR ama gosterilmiyorsa, bos bir kutu "hicbir sey olmadi"
  // der; oysa olan sey suzgecin arkasinda. Yanlis gosteren bir gosterge,
  // gostergesizlikten kotudur.
  if (!yazildi) {
    const gizlenen = D.okunurKip
      ? kendi.filter((o) => PANO_SINIF[o.tur] !== undefined).length : 0;
    ic.append(el("div", "sonuk", gizlenen
      ? `— okunacak bir şey yok; ${gizlenen} araç/durum kaydı okunur kipte gizli —`
      : "— bu oturumda çıktı yok —"));
  }

  p.append(bas);
  // BEKLEYEN SORU TERMINALIN USTUNDE (08.10, B6): ajan sana soru sorduysa
  // soru ve cevap yeri (secenekliyse dugmeler) kendi panosunda; onay
  // bekliyorsa ne bekledigi ve nerede cevaplanacagi.
  const _bekleyen = bekleyenSeridi(a);
  if (_bekleyen) p.append(_bekleyen);
  if (!term) {
    p.append(ozetSatiri(a));
    const kart = kullanimKarti(a);
    if (kart) p.append(kart);
  }
  if (!s.gecmis && devralinmisMi(a.gorev_no)) {
    // Is INSANDA: akis yerine gercek terminal, not yerine "geri ver".
    p.classList.add("devralindi");
    p.append(terminalAlani(a.gorev_no), geriVerSatiri(a));
    D.panolar[a.ad] = ic;
    return p;
  }
  // GERCEK TERMINAL KIPI: ajan Claude/Codex'in KENDI terminalinde kosuyor.
  // Pano o terminalin ta kendisi; insan icine yazabilir. Akis satirlari
  // (ic) kaybolmaz, yalniz gosterilmez -- canli olaylar ona yazilmaya
  // devam eder, kip degisince geri gelir.
  const tu = !s.gecmis && (D.tui || {})[a.ad];
  if (tu) {
    // Ayri "gercek terminal" etiketi YOK (06.10, patron: gereksiz kalabalik);
    // terminalin kendisi zaten Claude/Codex'in terminali.
    p.classList.add("gercek-terminal");
    p.title = "Ajan Claude/Codex'in kendi terminalinde çalışıyor. İçine yazabilirsin; " +
              "riskli adımlar yine ofis kapısından geçer.";
    p.append(terminalAlani("t:" + tu.oturum, `/ws/tui/${encodeURIComponent(tu.oturum)}`,
                           "[ajanın terminali kapandı]"));
    if (a.gorev_no) p.append(notSatiri(a));
    if (term) p.append(durumSatiri(a));
    D.panolar[a.ad] = ic;
    return p;
  }
  p.append(ic);
  // YAZMA SATIRI yalniz elinde IS olan ajanda: not verilmis bir isin
  // yonunu duzeltir, is dagitmaz (yeni is lidere yazilir).
  if (!s.gecmis && a.gorev_no) p.append(notSatiri(a));
  // Terminal kipinde sicil (kilit, kanit, tur, jeton) DURUM SATIRINA iner:
  // bilgi kaybolmaz, yalniz akisin onunu kapatmaz.
  if (term) p.append(durumSatiri(a));
  D.panolar[a.ad] = ic;
  return p;
}

/* ─────────────── DEVRAL / OFİSE GERİ VER (E18) ───────────────
   Varsayilan izleme OKUNUR akistir; gercek terminal yalniz "Devral"
   denince acilir. Terminal ekrani (xterm.js, panelin icinde, internetten
   cekilmez) her yeniden cizimde KURULMAZ: bir kez kurulur, pano yeniden
   cizildikce ayni dugum TASINIR -- yoksa her olayda ekran silinirdi.
   Geri verirken insanin yaptigini OFIS olcer (sunucu: `ofis/devral.py`);
   panel bir sey iddia etmez, sunucunun cevabini soyler. */
function devralinmisMi(no) {
  return !!(no && (D.devral || {})[no]);
}

async function devralAl() {
  try {
    const r = await al("/api/devralinanlar");
    const m = {};
    for (const d of r.isler || []) m[d.no] = d;
    D.devral = m;
    D.devralPty = r.pty || "";
    // GERCEK TERMINAL KIPI: ajan adi -> canli terminali.
    const t = {};
    for (const x of r.tui || []) if (x.ajan) t[x.ajan] = x;
    D.tui = t;
  } catch (e) { /* olcum yoksa dugme yine sunucuya sorar */ }
}

async function devralBaslat(no) {
  const r = await eylem(`/api/gorev/${no}/devral`, { sutun: 120, satir: 32 },
    (r) => `#${r.no} sende — ${r.ajan}'in oturumu terminalde ` +
           (r.oturum ? "sürüyor" : "(yeni oturum)") +
           (r.olcum ? "" : " · DİKKAT: disk ölçülemedi"));
  if (r) { await devralAl(); cizCanli(); panoSec("terminal"); }
}

async function geriVer(no, not) {
  const r = await eylem(`/api/gorev/${no}/geri_ver`, { not_: not || "" },
    (r) => `#${r.no} ${r.ajan}'a geri verildi · terminal ${r.kapanis} · ` +
           (r.degisen && r.degisen.length ? `${r.degisen.length} dosya değişti (ölçüldü)`
                                          : (r.olcum_notu || "dosya değişmedi")) +
           (r.not_iletildi ? "" : " · DİKKAT: not ajana bırakılamadı"));
  if (r) terminalKapat(no);
  await devralAl();
  cizCanli();
}

/* KONSOL (28.09.2026): ofisten BAGIMSIZ, insanin kendi terminali --
   VS Code'daki terminal gibi. Klasor secilir (ofisin calisma kokunde
   ACILMAZ: orada ajanlar calisir ve yazma kilidi bu terminali goremez),
   PowerShell ya da Claude/Codex acilir. Birden cok konsol sekme olur.
   Pano yeniden cizilirken terminal dugumu TASINIR, yeniden kurulmaz:
   yazilan komut ve ekran kaybolmaz. */
async function cizKonsol() {
  const kap = $("#pano-konsol");
  if (!kap) return;
  let r;
  try { r = await al("/api/konsol"); }
  catch (e) { kap.textContent = ""; return kap.append(el("div", "form-ipucu uyari", "konsol okunamadı: " + e.message)); }
  D.konsollar = r.konsollar || [];
  const canli = D.konsollar.filter((k) => k.canli);
  if (D.konsolSecili && !D.konsollar.some((k) => k.kimlik === D.konsolSecili))
    D.konsolSecili = null;
  if (!D.konsolSecili && canli.length) D.konsolSecili = canli[canli.length - 1].kimlik;
  // Kapanmis sekmelerin terminalini birak.
  for (const a of Object.keys(D.term || {}))
    if (a.startsWith("k:") && !D.konsollar.some((k) => "k:" + k.kimlik === a))
      terminalKapat(a);

  const ust = el("div", "konsol-ust");
  for (const k of D.konsollar) {
    const s = el("button", "konsol-sekme" + (k.kimlik === D.konsolSecili ? " secili" : "")
                  + (k.canli ? "" : " kapali"));
    const kisa = (k.klasor || "").split(/[\\/]/).filter(Boolean).pop() || k.klasor;
    s.textContent = `${k.motor} · ${kisa}`;
    s.title = `${k.motor} — ${k.klasor}` + (k.canli ? "" : " (kapandı)");
    s.onclick = () => { D.konsolSecili = k.kimlik; cizKonsol(); };
    const x = el("span", "konsol-x", "×");
    x.title = "Bu terminali kapat";
    x.onclick = async (e) => {
      e.stopPropagation();
      try { await yolla(`/api/konsol/${k.kimlik}/kapat`, {}); }
      catch (err) { bildir("konsol kapatılamadı: " + err.message, "kotu"); }
      terminalKapat("k:" + k.kimlik);
      if (D.konsolSecili === k.kimlik) D.konsolSecili = null;
      cizKonsol();
    };
    s.append(x);
    ust.append(s);
  }
  const yeni = el("button", "konsol-sekme konsol-yeni", "+ terminal");
  yeni.onclick = () => { D.konsolForm = !D.konsolForm; cizKonsol(); };
  ust.append(yeni);

  const govde = el("div", "konsol-govde");
  if (r.pty && r.pty !== "hazir") {
    govde.append(el("div", "form-ipucu uyari", r.pty));
  } else if (D.konsolForm || !D.konsollar.length) {
    govde.append(konsolFormu(r.motorlar || ["powershell"], r.oneriler || []));
  } else if (D.konsolSecili) {
    govde.append(terminalAlani("k:" + D.konsolSecili, `/ws/konsol/${D.konsolSecili}`,
      "[terminal kapandı — sekmedeki × ile kaldırabilirsin]"));
  }
  // Terminal dugumu yerinden SOKULUR, yenisi kurulmaz (DOM tasima xterm'i bozmaz).
  kap.textContent = "";
  kap.append(ust, govde);
}

/* Konsol acma formu. Kullanici (28.09): "dosya yolunu yazip acmak
   yerine daha iyi bir cozum yok mu". Sonra: "gozat masaustunden
   secmeme izin vermeli, alttaki siralama hos degil, klasor acmadan
   terminali baslatamaz miyim". Bugunku hal:
   1. GOZAT -- Gezgin'in modern klasor penceresi, Masaustunden baslar.
   2. ONERILER -- kutuya yazinca tarayicinin oneri menusunde (liste yok).
   3. BOS birakmak -- sunucu kullanicinin ana klasorunde acar.
   Motor bir DUGMEDIR, acilir liste degil: klasor secildiyse tek tikla acar. */
function konsolFormu(motorlar, oneriler) {
  const f = el("form", "konsol-form");
  const secili = { yol: D.konsolSonKlasor || "" };
  const k = el("input", "konsol-yol");
  k.placeholder = "klasör (boş bırakırsan ana klasörde açılır)";
  k.value = secili.yol;
  k.spellcheck = false;
  const not = el("div", "form-ipucu");
  const isaretle = () => {
    for (const b of f.querySelectorAll(".konsol-oneri"))
      b.classList.toggle("secili", b.dataset.yol.toLowerCase() === k.value.trim().toLowerCase());
  };
  k.oninput = isaretle;
  const gz = el("button", "dugme", "Gözat…");
  gz.type = "button";
  gz.title = "Windows'un klasör seçme penceresini açar";
  gz.onclick = async () => {
    gz.disabled = true;
    not.classList.remove("uyari");
    not.textContent = "klasör penceresi açıldı — ekranında seç (görünmüyorsa görev çubuğuna bak)";
    try {
      const r = await yolla("/api/konsol/gozat", { baslangic: k.value.trim() });
      if (r.yol) { k.value = r.yol; isaretle(); not.textContent = "seçildi — şimdi ne açılacağını seç"; }
      else not.textContent = "vazgeçildi";
    } catch (err) { not.textContent = err.message; not.classList.add("uyari"); }
    gz.disabled = false;
  };
  const ust = el("div", "konsol-satir");
  ust.append(k, gz);
  f.append(ust);

  // Oneriler LISTE olarak cizilmez (kullanici: "alttaki siralama hos
  // degil") -- kutuya yazmaya baslayinca tarayicinin kendi oneri
  // menusunde cikar.
  if ((oneriler || []).length) {
    const dl = el("datalist");
    dl.id = "konsol-oneri-listesi";
    for (const o of oneriler) {
      const s = el("option");
      s.value = o.yol;
      dl.append(s);
    }
    k.setAttribute("list", dl.id);
    f.append(dl);
  }

  const adlar = { powershell: "PowerShell", claude: "Claude Code", codex: "Codex" };
  const dugmeler = el("div", "konsol-motorlar");
  const tumu = [];
  const ac = async (motor) => {
    // Klasor bos birakilabilir: sunucu kullanicinin ana klasorunde acar.
    const yol = k.value.trim();
    tumu.forEach((d) => { d.disabled = true; });
    not.classList.remove("uyari");
    not.textContent = "açılıyor…";
    try {
      const r = await yolla("/api/konsol", { klasor: yol, motor });
      D.konsolSonKlasor = yol;
      D.konsolSonMotor = motor;
      D.konsolSecili = r.kimlik;
      D.konsolForm = false;
      cizKonsol();
    } catch (err) {
      not.textContent = err.message;
      not.classList.add("uyari");
      tumu.forEach((d) => { d.disabled = false; });
    }
  };
  for (const ad of motorlar) {
    const d = el("button", "dugme konsol-motor" + (ad === (D.konsolSonMotor || motorlar[0]) ? " olumlu" : ""),
                 "▶ " + (adlar[ad] || ad));
    d.type = "button";
    d.onclick = () => ac(ad);
    tumu.push(d);
    dugmeler.append(d);
  }
  f.append(dugmeler, not);
  f.append(el("div", "form-ipucu sonuk",
    "Ofisten bağımsız: işin kaydına girmez (yalnız açıldı/kapandı yazılır). " +
    "Ofisin çalışma klasöründe açılmaz — bir işe elle girmek için o işi 'Devral'."));
  f.onsubmit = (e) => { e.preventDefault(); ac(D.konsolSonMotor || motorlar[0]); };
  setTimeout(isaretle, 0);
  return f;
}

function terminalKapat(no) {
  const x = (D.term || {})[no];
  if (!x) return;
  try { x.ws && x.ws.close(); } catch (e) { /* zaten kapali */ }
  try { x.ro && x.ro.disconnect(); } catch (e) { /* */ }
  try { x.term && x.term.dispose(); } catch (e) { /* */ }
  x.el.remove();
  delete D.term[no];
}

/* Gercek terminal alani. Devral (`no` = gorev no) ve Konsol (`anahtar`
   = "k:<kimlik>") AYNI yolu kullanir: iki kopya olsaydi biri duzeltilir
   oteki unutulurdu. */
function terminalAlani(no, wsYol, kapandiMetni) {
  wsYol = wsYol || `/ws/terminal/${no}`;
  kapandiMetni = kapandiMetni || "[terminal kapandı — 'Ofise geri ver' ile ajana dön]";
  D.term = D.term || {};
  if (D.term[no]) return D.term[no].el;
  const kutu = el("div", "pano-terminal");
  const x = { el: kutu, acildi: false };
  D.term[no] = x;
  if (typeof window.Terminal !== "function") {
    kutu.append(el("div", "sonuk", "— terminal bileşeni yüklenemedi (web/vendor/xterm) —"));
    return kutu;
  }
  const ac = () => {
    if (x.acildi || !kutu.isConnected) return;
    x.acildi = true;
    const term = new window.Terminal({
      fontSize: 13, cursorBlink: true, scrollback: 5000,
      fontFamily: "Cascadia Mono, Consolas, monospace",
      theme: { background: "#0d0f13", foreground: "#d7dde6" },
    });
    const fit = new window.FitAddon.FitAddon();
    term.loadAddon(fit);
    term.open(kutu);
    x.term = term;
    const ws = new WebSocket(`ws://${location.host}${wsYol}`);
    x.ws = ws;
    const boyut = () => {
      try { fit.fit(); } catch (e) { return; }
      if (ws.readyState === 1)
        ws.send(JSON.stringify({ tur: "boyut", sutun: term.cols, satir: term.rows }));
    };
    ws.onopen = boyut;
    ws.onmessage = (m) => {
      let v; try { v = JSON.parse(m.data); } catch (e) { return; }
      if (v.tur === "veri") term.write(v.govde || "");
      else if (v.tur === "kapandi") term.write("\r\n\x1b[33m" + kapandiMetni + "\x1b[0m\r\n");
      else if (v.tur === "hata") term.write("\r\n\x1b[31m" + (v.govde || "hata") + "\x1b[0m\r\n");
    };
    ws.onclose = () => { x.ws = null; };
    term.onData((d) => {
      if (ws.readyState === 1) ws.send(JSON.stringify({ tur: "girdi", govde: d }));
    });
    x.ro = new ResizeObserver(() => boyut());
    x.ro.observe(kutu);
    setTimeout(() => { boyut(); term.focus(); }, 50);
  };
  // Dugum DOM'a girince acilir (xterm olcu ister).
  x.bekle = setInterval(() => {
    if (kutu.isConnected) { clearInterval(x.bekle); ac(); }
  }, 60);
  return kutu;
}

function geriVerSatiri(a) {
  const f = el("form", "pano-not pano-devral");
  f.append(el("span", "devral-rozet", "SENDE"));
  const g = el("input");
  g.placeholder = `${a.ad}'a kısa not (isteğe bağlı) — değişen dosyaları ofis kendisi ölçer`;
  g.maxLength = 1000;
  const d = el("button", "dugme olumlu", "Ofise geri ver");
  d.type = "submit";
  d.title = "Terminal düzgün kapatılır; diskte ne değiştiği ölçülür ve " +
            "notunla birlikte ajana iletilir. Ajan kaldığı yerden sürer.";
  f.onsubmit = (e) => { e.preventDefault(); d.disabled = true; geriVer(a.gorev_no, g.value); };
  f.append(g, d);
  return f;
}

/* AJANA NOT (E17). Pano altindaki yazma satiri: "dur, sunu degistir".
   Not isin tanimina EKTIR. Motor tasiyorsa tur SURERKEN iletilir (claude:
   bir sonraki arac sinirinda, codex: hemen), tasimiyorsa bir sonraki
   turun basinda. Ulastigi an panoda "notu aldı" satiri olarak gorunur --
   gonderildi demek, ulasti demek DEGILDIR (panel uydurmaz). */
function notSatiri(a) {
  const f = el("form", "pano-not");
  if (!D.okunurKip) f.append(el("span", "t-istem-imi", ">"));
  const g = el("input");
  g.placeholder = `${a.ad}'a not (#${a.gorev_no}) — "dur, şunu değiştir" · Enter`;
  g.maxLength = 1000;
  g.title = "Not işin tanımına eklenir. Tur sürerken iletilebiliyorsa hemen, " +
    "iletilemiyorsa bir sonraki turun başında gider.";
  f.append(g);
  f.onsubmit = async (e) => {
    e.preventDefault();
    const metin = g.value.trim();
    if (!metin) return;
    g.disabled = true;
    const r = await eylem(`/api/ajan/${encodeURIComponent(a.ad)}/not`,
      { metin, gorev_no: a.gorev_no },
      (r) => r.tasir
        ? `not ${a.ad}'a yazıldı — tur sürüyorsa iletilecek; ulaşınca panoda "notu aldı" görünür`
        : `not kaydedildi — ${a.ad}'ın motoru (${r.motor}) tur sürerken almıyor; sonraki turun başında gider`);
    g.disabled = false;
    if (r) g.value = "";
  };
  return f;
}

/* TERMINAL SUTUNU -- ve OLCULMUS bir kusurun duzeltilmesi (22.09.2026).

   Kullanici: *"terminaller gelmiyor."* Hakliydi ve sebebi tek bir
   satirdi: panolar yalnizca `oda !== "mola"` olan ajanlar icin
   ciziliyordu. Yani ofis DINLENIRKEN sutun tamamen bos kaliyordu.

   Olculdu (gercek ofis, 22.09.2026):

       defterde cikti olayi : 17   (cinar 7 · bilge 7 · ege 3)
       ekranda cizilen pano :  0

   82 turluk gercek gecmis duruyordu ve ekran "izlenecek ajan yok"
   diyordu. Bu tam olarak panelin dondurulma sebebiydi: *dinlenen ofis
   ile hic kullanilmamis ofis birebir ayni gorunuyor.*

   DUZELTME UYDURMA DEGIL, GECMIS: kimse kosmuyorsa SON TURLAR
   gosterilir -- ve panonun basliginda acikca "son tur" yazar. Canli
   sanilmasin diye nokta soner, baslik isaretlenir. Bos bir kutu
   "hicbir sey olmadi" der; oysa olan sey defterde duruyor. */
function cizCanli() {
  const kap = $("#gorunum-canli");
  kap.innerHTML = "";
  D.panolar = {};
  const kanatta = D.ofis.ajanlar.filter(
    (a) => !D.kanat || a.kanat_id === D.kanat);
  const calisan = kanatta.filter((a) => a.oda !== "mola");

  // GECMIS: ciktisi olan ajanlar, EN SON olayina gore sirali.
  const sonIndeks = {};
  D.olaylar.forEach((o, i) => {
    if (o.ajan_ad && PANO_SINIF[o.tur] !== undefined) sonIndeks[o.ajan_ad] = i;
  });
  const gecmis = kanatta
    .filter((a) => sonIndeks[a.ad] !== undefined)
    .sort((x, y) => sonIndeks[y.ad] - sonIndeks[x.ad]);

  const gosterilecek = calisan.length ? calisan : gecmis;
  const gecmisMi = !calisan.length;

  if (!gosterilecek.length) {
    // Simdi gercekten bos: ne kosan var ne de defterde cikti.
    kap.append(el("div", "canli-bos",
      "Bu kanatta henüz hiç tur koşmamış — terminal geçmişi de yok."));
    return;
  }

  if (gecmisMi) {
    // BOSLUGUN SEBEBI SOYLENIR: canli sanilmasin.
    kap.append(el("div", "canli-not",
      "Şu an kimse çalışmıyor — aşağıdakiler SON TURLARIN çıktısı."));
  }

  const izgara = el("div", "canli-izle");
  for (const a of gosterilecek) izgara.append(panoKur(a, { gecmis: gecmisMi }));
  kap.append(izgara);
  // Her pano en son satirda acilsin.
  for (const ic of Object.values(D.panolar)) ic.scrollTop = ic.scrollHeight;
}

/* Canli akistan gelen olayi acik panoya YAZAR. Panel yeniden cizilmeden
   satir dusmesi onemli: izleme, tazelenmeyi beklemez. */
function panoyaAkit(o) {
  const ic = D.panolar[o.ajan_ad];
  if (!ic) return;
  // Suzgec CANLI akista da calisir. Yalnizca cizimde calissaydi,
  // okunur kipte gizlenmesi gereken satir canli gelince duserdi --
  // kip, tazelenene kadar yalan soylerdi.
  const satir = panoSatiri(o);
  if (!satir) return;
  const bos = ic.querySelector(".sonuk");
  if (bos && bos.textContent.startsWith("—")) bos.remove();
  // Ilk canli satir gelince pano ACILIR: "cikti yok" artik dogru degil.
  const pano = ic.closest(".pano");
  if (pano) pano.classList.remove("cikti-yok");
  satir.classList.add("yeni");
  ic.append(satir);
  while (ic.children.length > 400) ic.firstChild.remove();
  ic.scrollTop = ic.scrollHeight;
}

/* ─────────────── piksel ofis ───────────────

   ODA BIR GOSTERGEDIR, DEKOR DEGIL. Bu kural 18.09'dan beri yaziliydi ve
   piksel ofis tam bu yuzden UZUN SURE YAPILMADI: "sprite koyalim" demek
   ekrana suslu bir resim koymaktir, bilgi koymak degil.

   Burada her piksel bir olcume bagli:
     - ajanin YERI    -> `_oda` ile TURETILEN durum (saklanmaz)
     - balon          -> ajanin o an yaptigi is (`not`), UYDURULMAZ
     - asma kilit     -> gercek `yazma_kilidi` satirlari (Yasa 1 gorunur)
     - "yazamaz"      -> tur='kafa' (Yasa 5 gorunur)
   Olculemeyen hicbir sey cizilmez: notu olmayan ajanin balonu YOKTUR.

   Neden CSS/box-shadow ile cizildi: proje karari "derleme adimi yok".
   Bir resim dosyasi eklemek varlik yonetimi, surum ve onbellek demek;
   burada renk ajanin kanadindan, sac tohumu ADINDAN geliyor -- yani
   sprite ajanla birlikte KALICI. Ajan bir kimliktir. */

const FIGUR = [
  "..HHHH..",
  ".HHHHHH.",
  ".HSSSSH.",
  ".SESSES.",
  ".SSSSSS.",
  "..SSSS..",
  ".CCCCCC.",
  "CCCCCCCC",
  ".CC..CC.",
  ".KK..KK.",
];
const SACLAR = ["#3b2a1d", "#6b4423", "#22303b", "#4a2f3a", "#2f3b2a", "#5a3d1f"];
const TEN    = "#e8b98a";
const GOZ    = "#241f1b";
const AYAK   = "#2b2b31";

/* "#e0785a" -> "rgba(224,120,90,.07)". Kanadin kendi rengini zemine
   tasimak icin; sabit bir tema listesi tutsaydik kanat renkleriyle
   ayrisirdi ve ikisinden biri yalan soylerdi. */
function rgba(hex, a) {
  const h = String(hex || "").replace("#", "");
  const t = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = parseInt(t || "6ba3c7", 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

/* Ad -> her zaman ayni sac rengi. Rastgele secseydik her tazelemede
   ajanin yuzu degisirdi; kalici kimlik gorsel olarak da kalici olmali. */
function _tohum(ad) {
  let t = 0;
  for (const h of ad) t = (t * 31 + h.charCodeAt(0)) % 100000;
  return t;
}

/* Piksel cizici: harf haritasi -> box-shadow. Tek yerde durur cunku
   sahnede uc figur var (ajan, masa, ekran) ve ucu de ayni kurali
   kullanmali -- ayri ayri yazsaydik biri digerinden kayardi. */
function pikselCiz(figur, renk, p, sinif) {
  const golgeler = [];
  figur.forEach((satir, y) => {
    [...satir].forEach((c, x) => {
      if (c === "." || !renk[c]) return;
      golgeler.push(`${x * p}px ${y * p}px 0 ${renk[c]}`);
    });
  });
  const s = el("div", "sprite");
  s.style.width = p + "px";
  s.style.height = p + "px";
  s.style.boxShadow = golgeler.join(",");
  const kutu = el("div", sinif || "sprite-kutu");
  kutu.style.width = figur[0].length * p + "px";
  kutu.style.height = figur.length * p + "px";
  kutu.append(s);
  return kutu;
}

/* MASA + EKRAN. Sahne, ama BOS sahne degil: ekranin rengi ajanin
   halini tasiyor (calisan aydinlik, bekleyen mor, bosta sonuk).

   Mobilya bir DURUM IDDIASI degildir -- masa "su an sunu yapiyor"
   demez -- o yuzden kuralimizi ("oda bir gostergedir, dekor degil")
   cignemez. Kural, BILGIYMIS GIBI davranan dekoru yasaklar; ortamin
   kendisini degil. Ekranin rengi ise gercekten bilgi, ve olculen
   `oda`dan geliyor. */
const MASA = [
  "...EEEEEE.....",
  "...EssssE.....",
  "...EssssE.....",
  "...EEEEEE.....",
  ".....AA.......",
  "TTTTTTTTTTTTTT",
  "TTTTTTTTTTTTTT",
  ".B..........B.",
  ".B..........B.",
];
const MASA_RENK = {
  E: "#11161c",   // ekran cercevesi
  A: "#2b3038",   // ayak
  T: "#3a4150",   // tabla
  B: "#272d36",   // bacak
};
//: Ekran rengi = ajanin hali. Sonuk gri "bosta" demek.
const EKRAN_RENGI = {
  masa: "#7fd8a6", inceleme: "#e8c46a", bekleme: "#b6a8ee",
  onay_kapisi: "#e89a86", mola: "#232a34",
};

/* ── ODANIN KENDI MOBILYASI ──

   Kullanici rakiple yan yana koyup gosterdi (22.09.2026): onlarin her
   odasinda masa, monitor, bitki, dolap, kanepe var; bizimkinde HIC
   mobilya yoktu ve bos oda dort kez "bos" yaziyordu. Fark estetik
   degil YAPISAL: onlarin bos odasi hala bir ODA, bizimki bos bir
   KUTUYDU.

   Kuralin dogru okunusu zaten yaziliydi ama yarim uygulanmisti:
   *"oda bir gostergedir, dekor degil"* kurali BILGIYMIS GIBI davranan
   dekoru yasaklar -- ortamin kendisini degil. Masa bir durum iddiasi
   degildir; sahnedir. Bu ayrimi bir kez gorup yalnizca AJANIN masasini
   cizmisim, odanin kendisini bos birakmisim.

   MOBILYA ODAYA AITTIR, AJANA DEGIL: ajan yokken de durur. Bos odanin
   hala bir oda gibi gorunmesinin tek yolu bu.

   Ve "bos" yazisi KALKTI. Bilgi kaybi yok: sayac zaten basliktadir ve
   "0" der. Bos bir odaya ayrica "bos" yazmak, ekranin dortte birini
   ayni seyi tekrarlayan bir metne ayirmakti. */
const BITKI = [
  "..GGG..", ".GGGGG.", "GGGgGGG", ".GGGGG.", "..GGG..",
  "...S...", "...S...", "..PPP..", ".PPPPP.", ".PPPPP.",
];
const BITKI_RENK = { G: "#4e8c62", g: "#6fb583", S: "#3d5c46", P: "#8a5a3c" };

const DOLAP = [
  "DDDDDDDDDD", "D1.2.3.4.D", "D1.2.3.4.D", "DDDDDDDDDD",
  "D5.6.7...D", "D5.6.7...D", "DDDDDDDDDD", "D........D",
  "D..8888..D", "D..8888..D", "DDDDDDDDDD",
];
const DOLAP_RENK = {
  D: "#4a3f34", "1": "#c2705c", "2": "#6b8fb0", "3": "#c9a761",
  "4": "#7f9e77", "5": "#a07ab0", "6": "#c2705c", "7": "#6b8fb0",
  "8": "#3a4150",
};

const PANO = [
  "CCCCCCCCCCCC", "CwwwwwwwwwwC", "CwLLLwwwwwwC", "CwwwwwwLLwwC",
  "CwLLLLLwwwwC", "CwwwwwwwwwwC", "CCCCCCCCCCCC",
  ".....AA.....", ".....AA.....", "....AAAA....",
];
const PANO_RENK = { C: "#3a4150", w: "#cfd6e0", L: "#7c8798", A: "#2b3038" };

const KANEPE = [
  ".SSSSSSSSSSSS.", "SSssssssssssSS", "SSssssssssssSS",
  "SSssssssssssSS", ".SSSSSSSSSSSS.", "..A........A..", "..A........A..",
];
const KANEPE_RENK = { S: "#4b5468", s: "#606b82", A: "#2b3038" };

const SEBIL = [
  "..BBB..", ".BBBBB.", ".BbbbB.", ".BBBBB.",
  "..CCC..", ".CCCCC.", ".C...C.", ".C...C.", ".CCCCC.", ".CCCCC.",
];
const SEBIL_RENK = { B: "#6fa8c9", b: "#9fd0e6", C: "#c9cfd8" };

const KAPI = [
  "DDDDDDDDD", "DkkkkkkkD", "DkkkkkkkD", "DkkkkkkkD", "DkkkkkkkD",
  "DkkkkkkkD", "DkkkkkhkD", "DkkkkkkkD", "DkkkkkkkD", "DkkkkkkkD",
  "DkkkkkkkD", "DDDDDDDDD",
];
const KAPI_RENK = { D: "#4a3f34", k: "#5f5142", h: "#d8c27a" };

/* ── OFIS HARITASI (23.09.2026) ──

   Kullanici rakibin ekranini koydu: tek parca bir KAT PLANI -- ustte
   pencereli duvar, genis bir calisma salonu, altta renkli zeminli
   odalar, masasinda oturan karakterler. Bizimki basliklari olan KART
   IZGARASIYDI: bir pano, bir YER degil. Alti ajanin altisi "MOLA"
   kutusuna sikismis, masalarin basinda duruyordu.

   Yeni duzen tek bir harita ve YUZDE birimiyle kurulur -- sutun
   daraldikca olceklenir. Uc karar:

   1. HER AJANIN KALICI BIR MASASI VAR. Masa ajan yokken de durur;
      ekraninin rengi sahibinin halini gosterir (calisiyor yesil,
      bekliyor mor, bosta sonuk). Ofisin bos oldugunu anlatan sey
      duvar degil, basinda kimse olmayan masadir.
   2. ZEMIN RENGI ANLAM TASIR. Alt odalarin her biri kendi durumunun
      rengindedir ve kanattan kanada DEGISMEZ; salonun halisi ise
      kanadin KENDI renginden turetilir -- kanat degisince ofis
      degisir, ama bir odanin ne demek oldugu degismez.
   3. HAREKET GERCEK BIR OLAYDIR. Rakipte karakterler rastgele gezinir;
      hos durur ama hicbir sey soylemez. Burada ajan yalnizca DURUMU
      degisince yurur -- ve kapidan gecerek, duvarin icinden degil:
      moladan masasina (is aldi), masadan inceleme odasina (teslim
      etti), baska bir ajanin masasina (ONA SORU SORDU). */

/* Harita olculeri, YUZDE. `alt`: masalar salonunun altindaki odalar
   [anahtar, sol, genislik]. ODALAR'daki her masa-disi oda burada
   olmali -- olmazsa o haldeki ajan "mola"ya duser ve yanlis odada
   gorunur (duman_panel bunu sinar). */
const HARITA = {
  duvar: 8,
  ayrim: 55,
  alt: [
    ["inceleme",    0,  23],
    ["bekleme",     23, 23],
    ["onay_kapisi", 46, 22],
    ["mola",        68, 32],
  ],
};
//: Yuruyus hizi, haritanin yuzdesi / saniye. Salonun bir ucundan
//: otekine ~5 sn: gozun takip edebilecegi, bekletmeyecegi hiz.
const YURUME_HIZI = 20;

/* ODA RENKLERI -- durumun rengi. [zemin A, zemin B] (dama deseni).
   Parlak degil: zemin sahnedir, okunacak sey karakter ve balon. */
const ZEMIN = {
  inceleme:    ["#6a4f37", "#5f462f"],   // ahsap -- lider kanita bakiyor
  bekleme:     ["#3f3a5c", "#37324f"],   // mor -- cevap bekliyor
  onay_kapisi: ["#7d5249", "#70483f"],   // kil -- senin onayin
  mola:        ["#3b5552", "#334a47"],   // camgobegi -- bosta
};

const PENCERE = [
  "FFFFFFFFFFFFFF",
  "FbbbbbFbbbbbbF",
  "FbllbbFbbbbbbF",
  "FbbbbbFbbllbbF",
  "FFFFFFFFFFFFFF",
  "FbbbbbFbbbbbbF",
  "FbbbbbFbbbbbbF",
  "FFFFFFFFFFFFFF",
];
const PENCERE_RENK = { F: "#434b5b", b: "#29445f", l: "#4d7aa6" };

const SAAT = [".CCCC.", "CwwwwC", "CwwAwC", "CwAAwC", "CwwwwC", ".CCCC."];
const SAAT_RENK = { C: "#434b5b", w: "#d8dde6", A: "#2b3038" };

const KAHVE = [
  "MMMMMMM", "MkkkkkM", "MkRRkkM", "MkkkkkM",
  "MMMMMMM", "M.....M", "M..cc.M", "MMMMMMM",
];
const KAHVE_RENK = { M: "#2f3540", k: "#48505e", R: "#d9534f", c: "#e8e1d2" };

const YAZICI = [
  "..PPPPPP..", "PPPPPPPPPP", "PGGGGGGGGP",
  "PPPPPPPPPP", "P.wwwwww.P", "PPPPPPPPPP",
];
const YAZICI_RENK = { P: "#5a6272", G: "#2b3038", w: "#e8e8e8" };

/* Hangi odada ne var: [figur, renk, x%, y%] -- ODAYA gore yuzde, cizim
   ALT-ORTADAN tutturulur (esyanin tabani o noktada durur).

   Esleme TEMATIK: inceleme odasinda tahta, onay kapisinda kapi, molada
   kahve ve kanepe. Bunlar SAHNEDIR, bir durum IDDIA ETMEZLER -- durumu
   ajanin kendisi ve masasinin ekrani soyler.

   Masalar salonunun esyasi duvar boyunca durur; ortasi AJANLARIN
   masalarina ayrilmistir. Sol ust kose ODANIN PLAKASININ: oraya konan
   dolap plakanin altinda kaliyordu (olculdu). */
const MOBILYA = {
  masa:        [[YAZICI, YAZICI_RENK, 50, 14], [DOLAP, DOLAP_RENK, 85, 21],
                [BITKI, BITKI_RENK, 96, 22], [BITKI, BITKI_RENK, 3, 34]],
  inceleme:    [[PANO, PANO_RENK, 50, 40], [BITKI, BITKI_RENK, 88, 38]],
  bekleme:     [[KANEPE, KANEPE_RENK, 46, 40], [BITKI, BITKI_RENK, 89, 38]],
  onay_kapisi: [[KAPI, KAPI_RENK, 50, 40], [BITKI, BITKI_RENK, 13, 38]],
  mola:        [[KAHVE, KAHVE_RENK, 14, 36], [SEBIL, SEBIL_RENK, 33, 38],
                [KANEPE, KANEPE_RENK, 68, 40], [BITKI, BITKI_RENK, 93, 38]],
};

/* Bir esya: piksel cizim + yuzdeli konum. `pointer-events: none` (CSS)
   sart -- esya ajanin tiklama alanini calarsa "ajana tikla, terminali
   acilsin" yolu sessizce bozulur ve sebebi gorunmez. */
function esya(figur, renk, x, y) {
  const kutu = pikselCiz(figur, renk, 3, "hr-esya");
  kutu.style.left = x + "%";
  kutu.style.top = y + "%";
  return kutu;
}

/* "#e0785a" ile "#1b2029"u karistir. Salonun halisi kanadin KENDI
   renginden turer -- rastgele bir tema listesi tutsaydik kanat renkleriyle
   ayrisirdi ve ikisinden biri yalan soylerdi. */
function karistir(renk, zemin, oran) {
  const oku = (h) => {
    const t = String(h || "").replace("#", "");
    const u = t.length === 3 ? t.split("").map((c) => c + c).join("") : t;
    const n = parseInt(u || "000000", 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  };
  const a = oku(renk), b = oku(zemin);
  return "#" + a.map((v, i) => Math.round(v * (1 - oran) + b[i] * oran)
    .toString(16).padStart(2, "0")).join("");
}

/* TUM OFIS'in tek bir kanat rengi YOKTUR -- notr hali. Bir kez varsayilan
   renk verilmisti ve o renk pazarlamanin rengiyle ayniydi: iki farkli sey
   ayni gorunuyordu. */
function haliRengi(kanat) {
  if (!kanat || !kanat.renk) return ["#2c3442", "#303949"];
  return [karistir(kanat.renk, "#161a21", 0.66),
          karistir(kanat.renk, "#161a21", 0.60)];
}

function odaKutusu(anahtar) {
  if (anahtar === "masa")
    return { x: 0, y: HARITA.duvar, w: 100, h: HARITA.ayrim - HARITA.duvar };
  const k = HARITA.alt.find((a) => a[0] === anahtar) || HARITA.alt.at(-1);
  return { x: k[1], y: HARITA.ayrim, w: k[2], h: 100 - HARITA.ayrim };
}

/* Masa yerleri: her ajana SABIT bir masa. Sira ajanin adina gore: ayni
   kadroyla her cizimde AYNI yer cikar -- rastgele olsaydi ajan her
   tazelemede baska masada olurdu. Kadro degisince masalar yeniden
   dizilir; bu bir durum degisimi DEGILDIR, o yuzden kimse yurumez
   (bkz. cizOfis: kadro imzasi).

   Eksik sira ORTALANIR: 3 ajanlik bir kanatta masalar dort sutunluk
   izgarada sola yasli kaliyor, dorduncu sutun bos duruyordu (olculdu). */
function masaYerleri(n) {
  const kol = Math.max(1, Math.min(n, n <= 8 ? 4 : n <= 15 ? 5 : 6));
  const sira = Math.max(1, Math.ceil(n / kol));
  const r = odaKutusu("masa");
  return Array.from({ length: n }, (_, i) => {
    const s = Math.floor(i / kol);
    const bu = Math.min(kol, n - s * kol);        // bu siradaki masa sayisi
    return {
      x: ((i % kol) + 0.5 + (kol - bu) / 2) * 100 / kol,
      y: r.y + r.h * (0.42 + 0.50 * (s + 0.5) / sira),
    };
  });
}

/* Bir odada ayakta duranlarin yerleri. Oda doldukca SIKISIR, buyumez:
   gercek bir binada oda sabittir. Kimse gizlenmez -- sayi plakada. */
function odaYerleri(anahtar, n) {
  const r = odaKutusu(anahtar);
  const kol = Math.max(1, Math.min(n, Math.floor(r.w / 10.5)));
  const sira = Math.max(1, Math.ceil(n / kol));
  return Array.from({ length: n }, (_, i) => {
    const s = Math.floor(i / kol);
    const bu = Math.min(kol, n - s * kol);          // bu siradaki kisi
    return {
      x: r.x + r.w * (((i % kol) + 0.5) / bu),
      y: r.y + r.h * (sira === 1 ? 0.80 : 0.62 + 0.34 * s / (sira - 1)),
    };
  });
}

/* Kim nerede. Uc kaynak, hepsi OLCULEN `oda`dan:
   - masa   -> kendi masasinda OTURUR
   - bekleme + soru bir AJANA sorulduysa -> o ajanin YANINA gider
     (konusma gorunur olsun; soru insana ise bekleme odasinda)
   - digerleri -> kendi odasinda ayakta

   ZIYARETCI SORULANIN ODASINA KATILIR. Once sorulanin yanina sabit bir
   aralikla konuyordu ve olculdu (23.09.2026): iki kisilik inceleme
   odasinda ziyaretci ikinci kisinin TAM USTUNE dustu. Sorulan ayakta
   bir odadaysa ziyaretci o odanin yerlesimine, sorulanin hemen arkasina
   girer -- aralik odanin isi olur, kimse kimsenin ustune basmaz.
   Sorulan masasindaysa masanin yanina gider; masalar arasi bosluk
   bunun icin birakildi. */
function ajanKonumlari(ajanlar, masaYeri) {
  const konum = {};
  const odadakiler = {};
  const ziyaretci = [];
  const alan = new Set(HARITA.alt.map((a) => a[0]));
  // Haritada yeri olmayan bir oda gelirse "mola"ya duser -- ama bu bir
  // hata: duman_panel her odanin haritada yeri oldugunu sinar.
  const odasi = (a) => (alan.has(a.oda) ? a.oda : "mola");
  const adla = {};
  for (const a of ajanlar) adla[a.ad] = a;
  for (const a of ajanlar) {
    if (a.oda === "masa") {
      konum[a.ad] = { ...masaYeri[a.ad], oturuyor: true };
    } else if (a.oda === "bekleme" && a.kime && masaYeri[a.kime]) {
      ziyaretci.push(a);
    } else {
      (odadakiler[odasi(a)] = odadakiler[odasi(a)] || []).push(a);
    }
  }
  const masaya = [];
  for (const z of ziyaretci) {
    const h = adla[z.kime];
    const liste = h && odadakiler[odasi(h)];
    const i = liste ? liste.indexOf(h) : -1;
    if (i >= 0) liste.splice(i + 1, 0, z);   // sorulanin hemen arkasina
    else masaya.push(z);                     // sorulan masada (ya da o da ziyarette)
  }
  for (const [oda, liste] of Object.entries(odadakiler)) {
    const yer = odaYerleri(oda, liste.length);
    liste.forEach((a, i) => { konum[a.ad] = { ...yer[i], oturuyor: false }; });
  }
  const sayac = {};
  for (const z of masaya) {
    const h = masaYeri[z.kime];
    const k = (sayac[z.kime] = (sayac[z.kime] || 0) + 1);
    konum[z.ad] = { x: Math.min(95, Math.max(5, h.x + (k % 2 ? 7.5 : -7.5))),
                    y: Math.min(98, h.y + 3), oturuyor: false };
  }
  for (const z of ziyaretci) konum[z.ad].ziyaret = z.kime;
  return konum;
}

/* Yol: kapidan gecer, duvarin icinden DEGIL. Alt odalarin kapisi,
   salonla aralarindaki duvarin ortasinda. */
function kapiX(p) {
  const k = HARITA.alt.find((a) => p.x >= a[1] && p.x < a[1] + a[2]) ||
            HARITA.alt.at(-1);
  return k[1] + k[2] / 2;
}
function yolBul(a, b) {
  const ust = (p) => p.y < HARITA.ayrim;
  const yuk = HARITA.ayrim - 3, alt = HARITA.ayrim + 5;
  if (ust(a) && ust(b)) return [b];
  if (ust(a)) { const k = kapiX(b); return [{ x: k, y: yuk }, { x: k, y: alt }, b]; }
  if (ust(b)) { const k = kapiX(a); return [{ x: k, y: alt }, { x: k, y: yuk }, b]; }
  const ka = kapiX(a), kb = kapiX(b);
  if (ka === kb) return [b];
  return [{ x: ka, y: alt }, { x: ka, y: yuk },
          { x: kb, y: yuk }, { x: kb, y: alt }, b];
}

const hareketAzalt = () =>
  window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

/* Yuru: noktadan noktaya, her ayak mesafesine gore sure. Yuruyus
   bitince ajan hedefte OTURUR ya da DURUR. Hareket azaltma istenmisse
   isinlanir -- bilgi kaybolmaz, cunku yer zaten bilgiyi tasiyor.

   Kalan yol DUGUMUN USTUNDE durur (`_bacak` + `_kalan`): panel her
   olayda haritayi yeniden kurar ve yolda olan ajan kaldigi yerden
   devam etmeli (bkz. yoldakileriOku). */
function yuru(dugum, yol, son) {
  if (hareketAzalt()) {
    dugum.style.left = son.x + "%"; dugum.style.top = son.y + "%";
    dugum.classList.toggle("oturuyor", !!son.oturuyor);
    return;
  }
  dugum.classList.remove("oturuyor");
  dugum.classList.add("yuruyor");
  dugum._son = son;
  dugum._kalan = yol.slice();
  dugum._bacak = null;
  const adim = () => {
    if (!dugum.isConnected) return;       // cizim yenilendi: bu dugum oldu
    if (!dugum._kalan.length) {
      dugum._bacak = null;
      dugum.classList.remove("yuruyor");
      dugum.classList.toggle("oturuyor", !!son.oturuyor);
      dugum.style.zIndex = String(Math.round(son.y * 10));
      return;
    }
    const h = (dugum._bacak = dugum._kalan.shift());
    const x0 = parseFloat(dugum.style.left), y0 = parseFloat(dugum.style.top);
    const sure = Math.max(0.12, Math.hypot(h.x - x0, h.y - y0) / YURUME_HIZI);
    dugum.classList.toggle("sola", h.x < x0 - 0.3);
    dugum.style.transitionDuration = sure + "s";
    dugum.style.left = h.x + "%";
    dugum.style.top = h.y + "%";
    setTimeout(adim, sure * 1000);
  };
  // Iki kare bekle: tarayici once BASLANGIC konumunu boyamali, yoksa
  // gecis hic olmaz ve ajan isinlanir.
  requestAnimationFrame(() => requestAnimationFrame(adim));
}

/* YURUYUS KESILMESIN. Panel her olayda haritayi YENIDEN KURAR (sahiplenme,
   kanit, tur ozeti...). Yolda olan ajanin konumu o an bir CSS gecisinin
   icindedir; yeniden kurulumda okunmazsa ajan hedefine ISINLANIR -- ve
   yuruyus tam gorulmesi gereken anda (is basladi, soru soruldu) kesilir.
   Okunan: gecisin SU ANKI yeri (getComputedStyle gecis sirasinda ara
   degeri verir) + kalan yol + hedef. */
function yoldakileriOku(kap) {
  const yolda = {};
  const eski = kap.querySelector(".ofis-harita");
  if (!eski || !eski.clientWidth || !eski.clientHeight) return yolda;
  for (const d of eski.querySelectorAll(".hr-ajan.yuruyor")) {
    if (!d._son) continue;
    const s = getComputedStyle(d);
    yolda[d.dataset.ad] = {
      x: parseFloat(s.left) / eski.clientWidth * 100,
      y: parseFloat(s.top) / eski.clientHeight * 100,
      yol: [d._bacak, ...d._kalan].filter(Boolean),
      son: d._son,
    };
  }
  return yolda;
}

/* BALON CAKISMASI -- olculur, tahmin edilmez.
   Dar odada balonlar ust uste biniyordu (olculdu, 23.09.2026: inceleme
   odasinda uc balon birbirini ortuyordu). Ust uste binen metin, yanlis
   gosterenin en sinsi turudur: dogru gorunur, okunmaz.
   Balonlar ONEM sirasiyla yerlesir: secili ajan, onay, AJANIN AJANA
   sorusu, insana soru, calisan, inceleme. Yer kalmayanin balonu
   gizlenir ama bilgi KAYBOLMAZ: basinda "…" isareti kalir, uzerine
   gelince balon acilir, tiklayinca terminali. Haritadan tasan balon da
   gizlenir -- kirpilmis metin gostermektense isaret.

   Ajanlar arasi soru INSANA SORUDAN ONCE: olculdu, dar odalarda uc
   balon ayni satira fiziksel olarak sigmiyor ve biri feda ediliyor.
   Insana soru ve onay sag ustteki "SENDEN BEKLENIYOR" kuyrugunda tam
   metniyle zaten duruyor; ajanin ajana sordugu soru ise YALNIZCA
   haritada gorunur. Harita, baska yerde olmayani gostermeli. */
const BALON_ONCELIK = { onay_kapisi: 1, ziyaret: 2, bekleme: 3, masa: 4, inceleme: 5, mola: 6 };
const HIZALAR = ["", "sola-yasli", "saga-yasli"];
function balonlariYerlestir(h) {
  const cerceve = h.getBoundingClientRect();
  if (!cerceve.width) return;              // gorunmuyor: olculecek bir sey yok
  const ajanlar = [...h.querySelectorAll(".hr-ajan")];
  // Ajanin GOVDESI (sprite + ad) -- balon mutlak konumlu oldugu icin
  // ajanin kutusuna dahil degildir. Baskasinin adini ortmek de okunmazlik:
  // olculdu, alt siradakinin balonu ustteki "demir"i "der"e cevirdi.
  const govde = new Map(ajanlar.map((d) => [d, d.getBoundingClientRect()]));
  const kesisir = (r, s) => r.left < s.right + 2 && r.right > s.left - 2 &&
                            r.top < s.bottom + 2 && r.bottom > s.top - 2;
  const sira = ajanlar.filter((d) => d.querySelector(".balon"))
    .map((d) => [d.classList.contains("secili") ? 0
                 : BALON_ONCELIK[d.dataset.ziyaret ? "ziyaret" : d.dataset.oda] || 9, d]);
  sira.sort((p, q) => p[0] - q[0] || p[1].dataset.ad.localeCompare(q[1].dataset.ad, "tr"));
  const alinan = [];
  for (const [oncelik, d] of sira) {
    const b = d.querySelector(".balon");
    // Once kenara gore secilmis hiza (balonYap), sonra otekiler.
    const ilk = HIZALAR.find((c) => c && b.classList.contains(c)) || "";
    const onceki = D.balonHiza[d.dataset.ad];
    const denenecek = [...new Set([onceki, ilk, ...HIZALAR])].filter((c) => c !== undefined);
    const dene = (c) => {
      b.classList.remove("sola-yasli", "saga-yasli");
      if (c) b.classList.add(c);
      return b.getBoundingClientRect();
    };
    const uygun = (r, govdeye) =>
      r.top >= cerceve.top && r.left >= cerceve.left && r.right <= cerceve.right &&
      !alinan.some((s) => kesisir(r, s)) &&
      !(govdeye && ajanlar.some((o) => o !== d && kesisir(r, govde.get(o))));
    // Yer yoksa: yalnizca secili, onay ve soru balonu bir baskasinin
    // GOVDESINE binebilir; baska BALONA asla.
    let secilen = null;
    for (const govdeye of (oncelik <= 3 ? [true, false] : [true])) {
      for (const c of denenecek) {
        const r = dene(c);
        if (uygun(r, govdeye)) { secilen = r; D.balonHiza[d.dataset.ad] = c; break; }
      }
      if (secilen) break;
    }
    if (secilen) alinan.push(secilen);
    else { dene(ilk); d.classList.add("suskun"); }
  }
}

/* Harita DOM'a girdikten SONRA: once balonlar son yerlerinde olculur,
   sonra yuruyecek olanlar baslangica alinip yurutulur. Ikisi ayni gorev
   icinde oldugu icin tarayici arada BOYAMAZ -- hedefte bir an gorunup
   geri sicrayan ajan olmaz. */
function haritaCanlandir(h) {
  balonlariYerlestir(h);
  for (const { dugum, yol, hedef, bas } of h._yuruyus || []) {
    dugum.classList.remove("oturuyor");
    dugum.style.left = bas.x + "%";
    dugum.style.top = bas.y + "%";
    dugum.style.zIndex = String(Math.round(Math.max(bas.y, hedef.y) * 10) + 1);
    yuru(dugum, yol, hedef);
  }
}

/* Ajanin masasi -- sahibi yokken de durur. Ekranin rengi sahibinin
   HALIDIR (olculen `oda`dan), ad plakasi masanin altinda: kimin masasi
   oldugu sahibi uzaktayken de okunur. */
function masaCiz(a, yer) {
  const m = el("div", "hr-masa" + (a.oda === "masa" ? " dolu" : ""));
  m.dataset.oda = a.oda;
  m.style.left = yer.x + "%";
  m.style.top = yer.y + "%";
  m.style.zIndex = String(Math.round(yer.y * 10) + 2);
  m.append(pikselCiz(MASA, { ...MASA_RENK, s: EKRAN_RENGI[a.oda] || "#232a34" },
                     3, "masa-kutu"));
  const plaka = el("div", "hr-masa-ad", a.ad);
  m.append(plaka);
  return m;
}

/* Balon yalnizca SOYLENECEK bir sey varsa cizilir. Bos balon "bir sey
   yapiyor" izlenimi verirdi -- uydurmanin gorsel hali. Ziyaretcinin
   balonu KIME soruldugunu da soyler. */
function balonYap(a, yer) {
  const not = (a.not || "").trim();
  if (!not) return null;
  const b = el("div", "balon");
  let yazi = (a.gorev_no && !not.startsWith("#")) ? `#${a.gorev_no} ${not}` : not;
  if (yer && yer.ziyaret) yazi = `→ ${yer.ziyaret}: ${not}`;
  // Metin DOLGUSUZ bir ic ogede kirpilir. Olculdu (23.09.2026): kirpma
  // balonun kendisindeyken tasma DOLGU kutusunda kesiliyordu ve ucuncu
  // satirin ust yarisi alt dolguda gorunuyordu -- yarim satir,
  // kirpildigini soylemeyen bir kirpmadir.
  b.append(el("span", "balon-yazi", kes(yazi, 110)));
  b.title = yazi;
  // Kenardaki ajanin balonu haritadan TASMASIN: kirpilmis metin dogru
  // gorunur ama yanlis okunur (bir kez "#9" -> "9" oldu).
  if (yer && yer.x < 22) b.classList.add("sola-yasli");
  else if (yer && yer.x > 78) b.classList.add("saga-yasli");
  return b;
}

function haritaAjani(a, yer, kumas) {
  const d = el("div", "hr-ajan" + (D.secilenAjan === a.ad ? " secili" : ""));
  d.dataset.ad = a.ad;
  if (yer.ziyaret) d.dataset.ziyaret = yer.ziyaret;
  // HAREKET BIR BILGIDIR: oda sprite'a yazilir ki CSS ajanin HALINE gore
  // kipirdasin -- calisan nefes alir, bekleyen nabiz atar, moladaki DURUR.
  d.dataset.oda = a.oda;
  const balon = balonYap(a, yer);
  if (balon) d.append(balon);
  d.append(pikselCiz(FIGUR, karakterRenk(a, kumas), 3, "sprite-kutu"));
  const ad = el("div", "kat-ad");
  ad.append(el("span", "kat-ad-yazi", a.ad));
  // BIZE OZGU, rakipte YOK: yazma kilidi ofiste GORUNUR (Yasa 1).
  const kilit = (a.sicil && a.sicil.kilit) || [];
  if (kilit.length) {
    const k = el("span", "kat-kilit", "\u{1F512}");
    k.title = "Kilitli yol: " + kilit.join(" · ");
    ad.append(k);
  }
  if (a.tur === "kafa") {
    const y = el("span", "kat-yazamaz", "✎");
    y.title = "kafa ajan — yazan araci YOK (Yasa 5)";
    ad.append(y);
  }
  d.append(ad);
  d.title = `${a.ad} · ${a.meslek}` + (yer.ziyaret ? ` → ${yer.ziyaret}'e soru sordu` : "");
  d.onclick = (e) => {
    e.stopPropagation();
    D.secilenAjan = (D.secilenAjan === a.ad) ? null : a.ad;
    cizOfis();
  };
  return d;
}

/* Haritayi kur: duvar, odalar, duvarlar/kapilar, masalar, ajanlar.
   Derinlik: z-index = y -- onde duran (asagidaki) arkadakini orter,
   masanin arkasinda oturan ajani masa orter. */
function haritaKur(ajanlar, kanat) {
  const h = el("div", "ofis-harita");
  const [halA, halB] = haliRengi(kanat);
  h.style.setProperty("--hali-a", halA);
  h.style.setProperty("--hali-b", halB);

  const duvar = el("div", "hr-duvar");
  duvar.style.height = HARITA.duvar + "%";
  for (const x of [13, 33, 67, 87]) duvar.append(esya(PENCERE, PENCERE_RENK, x, 86));
  duvar.append(esya(SAAT, SAAT_RENK, 50, 76));
  h.append(duvar);

  const sayi = {};
  for (const a of ajanlar) sayi[a.oda] = (sayi[a.oda] || 0) + 1;
  for (const [anahtar, ad, aciklama, kisa] of ODALAR) {
    const r = odaKutusu(anahtar);
    const oda = el("div", "hr-oda");
    oda.dataset.oda = anahtar;
    oda.style.cssText = `left:${r.x}%;top:${r.y}%;width:${r.w}%;height:${r.h}%;`;
    if (ZEMIN[anahtar]) {
      oda.style.setProperty("--zemin-a", ZEMIN[anahtar][0]);
      oda.style.setProperty("--zemin-b", ZEMIN[anahtar][1]);
    }
    for (const [figur, renk, x, y] of MOBILYA[anahtar] || [])
      oda.append(esya(figur, renk, x, y));
    // ODANIN NE ANLAMA GELDIGI plakada ve title'da yazar: panel kendini
    // anlatmali, kullanici ezberlememeli. Sayi olculur; "0" da bir
    // bilgidir, "bos" diye ayrica yazilmaz.
    const plaka = el("div", "hr-plaka" + (sayi[anahtar] ? "" : " sifir"));
    plaka.append(el("span", "hr-plaka-ad", kisa || ad),
                 el("span", "hr-plaka-adet", String(sayi[anahtar] || 0)));
    if (anahtar === "masa") plaka.append(el("span", "hr-plaka-not", aciklama));
    plaka.title = `${ad} — ${aciklama}`;
    oda.append(plaka);
    h.append(oda);
  }

  // Salonla alt odalar arasindaki duvar -- her odanin ortasinda KAPI.
  const kapilar = HARITA.alt.map((a) => a[1] + a[2] / 2).sort((p, q) => p - q);
  let bas = 0;
  for (const k of [...kapilar, 200]) {
    const son = Math.min(100, k - 4);
    if (son > bas) {
      const w = el("div", "hr-duvar-yatay");
      w.style.cssText = `left:${bas}%;width:${son - bas}%;top:${HARITA.ayrim}%;`;
      h.append(w);
    }
    bas = k + 4;
  }
  for (const a of HARITA.alt.slice(1)) {
    const w = el("div", "hr-duvar-dikey");
    w.style.cssText = `left:${a[1]}%;top:${HARITA.ayrim}%;height:${100 - HARITA.ayrim}%;`;
    h.append(w);
  }

  // Masalar: kadro ADA gore dizilir -- ayni kadroyla her cizimde ayni yer.
  const sirali = [...ajanlar].sort((p, q) => p.ad.localeCompare(q.ad, "tr"));
  const yerler = masaYerleri(sirali.length);
  const masaYeri = {};
  sirali.forEach((a, i) => { masaYeri[a.ad] = yerler[i]; h.append(masaCiz(a, yerler[i])); });

  const konum = ajanKonumlari(ajanlar, masaYeri);
  const ayni = (p, q) => p && q && Math.abs(p.x - q.x) < 0.5 && Math.abs(p.y - q.y) < 0.5;
  h._yuruyus = [];
  for (const a of sirali) {
    const kn = D.ofis.kanatlar.find((x) => x.id === a.kanat_id);
    const hedef = konum[a.ad];
    const dugum = haritaAjani(a, hedef, (kn && kn.renk) || "#6ba3c7");
    // Once HEDEFTE cizilir: balonlar son yerlerine gore olculur
    // (balonlariYerlestir), yuruyecek olan sonra baslangica alinir.
    dugum.style.left = hedef.x + "%";
    dugum.style.top = hedef.y + "%";
    dugum.style.zIndex = String(Math.round(hedef.y * 10) + 1);
    dugum.classList.toggle("oturuyor", !!hedef.oturuyor);
    h.append(dugum);
    // YURUYUS: yalnizca YER DEGISINCE, kapidan gecerek. Yoldaysa kaldigi
    // yerden; hedefi degismediyse kalan yoldan devam eder.
    const yolda = D.yolda[a.ad];
    const once = yolda || D.konum[a.ad];
    if (once && !ayni(once, hedef)) {
      const yol = (yolda && ayni(yolda.son, hedef)) ? yolda.yol : yolBul(once, hedef);
      h._yuruyus.push({ dugum, yol, hedef, bas: once });
    }
    D.konum[a.ad] = { x: hedef.x, y: hedef.y };
  }
  return h;
}

/* OFIS GORUNUMU = AJAN PANOLARI, bos oda kartlari DEGIL.

   OLCULMUS TASARIM HATASI (21.09.2026): panele GERCEK veriyle
   bakildiginda ofis 9 is bitirmis, $14,84 harcamis, 40 karar
   uretmisti -- ve ana gorunum "bos . bos . bos . bos" diyordu.
   Ekranin %70'i bostu. Her ajanin altinda "is verilmedi" yaziyordu;
   `cinar` 8 is yapmisti.

   Yani DINLENEN bir ofis ile HIC KULLANILMAMIS bir ofis birebir ayni
   gorunuyordu -- ve bu kullanici zamanin cogunda gordugu ekran.

   Kok sebep: ana icerik olarak ODA konmustu. Oda bir soyutlamadir ve
   is yokken ici bostur. Rakibin ekrani canli duruyor cunku onun ana
   icerigi TERMINAL -- yani ISIN KENDISI.

   ODA BILGISI SILINMEDI, YERI DEGISTI: her panonun basliginda bir
   rozet. Kural zaten yaziliydi: *bir sey dagitiyorsa kaldirilmaz,
   yeri degistirilir.*

   Ve pano basligi bizim OLCEBILDIGIMIZ, rakipte OLMAYAN seyi tasir:
   yazma kilidi alani, kanit sayisi, turun maliyeti. Gucumuz vardi,
   ekranda yoktu. */

/* Terminalin alt durum satiri -- Claude Code'un status line'i gibi, tek
   satir. Icerik ozetSatiri + kullanimKarti ile AYNI olcum (ikinci bir
   hesap yok): yazma kilidi (Yasa 1) ve kanit sayisi burada da gorunur. */
function durumSatiri(a) {
  const s = a.sicil || {};
  const d = el("div", "t-durum");
  const parca = (metin, sinif, ipucu) => {
    const x = el("span", sinif || null, metin);
    if (ipucu) x.title = ipucu;
    d.append(x);
  };
  if (s.kilit && s.kilit.length)
    parca("\u{1F512} " + s.kilit.join(" · "), "t-kilit", "Bu ajan bu yolları KİLİTLİ tutuyor (yazma kilidi).");
  if (s.son_gorev) {
    parca(`#${s.son_gorev.no} ${s.son_gorev.durum}`, null, s.son_gorev.baslik);
    if (s.son_gorev.kanit) parca(`${s.son_gorev.kanit} kanıt`, "t-iyi");
  }
  if (s.tur) parca(`${s.tur} tur`);
  const t = s.son_tur;
  if (t && t.jeton) parca(`son ${jetonYaz(t.jeton)}`);
  const k = s.kullanim;
  if (k && k.tum && k.tum.jeton) parca(`toplam ${jetonYaz(k.tum.jeton)} jeton`);
  if (t && t.basarili === false) parca("son tur düştü", "t-hata");
  if (!d.children.length) parca("henüz iş yapmadı", "t-sonuk");
  return d;
}

function ozetSatiri(a) {
  const s = a.sicil || {};
  const p = el("div", "pano-ozet");
  const oge = (deger, etiket, sinif) => {
    const d = el("span", "ozet-oge" + (sinif ? " " + sinif : ""));
    d.append(el("b", null, String(deger)), el("i", null, etiket));
    return d;
  };
  // BIZE OZGU: yazma kilidi GORUNUR. Yasa 1'in ekrandaki hali.
  if (s.kilit && s.kilit.length) {
    const k = oge("\u{1F512}", s.kilit.join(" · "), "kilit");
    k.title = "Bu ajan su an bu yollari KILITLI tutuyor. " +
              "Cakisan bir talep reddedilir.";
    p.append(k);
  }
  if (s.son_gorev) {
    const g = oge("#" + s.son_gorev.no, s.son_gorev.baslik.slice(0, 38),
                  "is " + s.son_gorev.durum);
    g.title = s.son_gorev.baslik + "  (" + s.son_gorev.durum + ")";
    p.append(g);
    // KANIT SAYISI: kanit kapisinin ekrandaki hali.
    if (s.son_gorev.kanit) p.append(oge(s.son_gorev.kanit, "kanıt", "kanit"));
  }
  if (s.tur) p.append(oge(s.tur, "tur"));
  if (s.is) p.append(oge(s.is, "iş"));
  const t = s.son_tur;
  if (t) {
    if (t.jeton) p.append(oge(jetonYaz(t.jeton), "son tur jeton"));
    if (t.model) p.append(oge(t.model.replace("claude-", ""), "model"));
    // BASARISIZ TUR GIZLENMEZ. Olculdu: basarisiz turlar bir donem hic
    // kayda gecmiyordu ve toplam maliyet yaniltiyordu. Kacagin oldugu
    // yeri olcmemek, olcmemenin en pahali hali.
    if (t.basarili === false) p.append(oge("!", "son tur düştü", "dustu"));
  }
  if (!p.children.length)
    p.append(el("span", "ozet-oge sonuk", "henüz iş yapmadı"));
  return p;
}

function cizOfis() {
  const kap = $("#gorunum-ofis");
  // Yeniden kurmadan ONCE: yolda olanlarin su anki yeri.
  const yolda = yoldakileriOku(kap);
  kap.innerHTML = "";
  const ajanlar = D.ofis.ajanlar.filter((a) => !D.kanat || a.kanat_id === D.kanat);
  if (!ajanlar.length) {
    // BOS TAKIM bir sonraki adimi SOYLER: once lider (is dagitan o).
    const b = el("div", "canli-bos");
    b.append(el("div", null, D.kanat
      ? "Bu takımda henüz ajan yok. İlk iş: bir LİDER işe al — işi o dağıtır."
      : "Ofiste henüz ajan yok. İlk iş: bir LİDER işe al."));
    const d = el("button", "dugme olumlu", "+ ajan işe al");
    d.style.marginTop = "10px";
    d.onclick = ajanEkleAc;
    b.append(d);
    kap.append(b);
    return;
  }
  D.panolar = {};
  // Secili ajan bu kanatta yoksa secim DUSER -- yoksa kanat degisince
  // gorunmeyen bir ajanin terminali acik kalirdi.
  if (D.secilenAjan && !ajanlar.some((a) => a.ad === D.secilenAjan))
    D.secilenAjan = null;

  /* KANAT BASINA AYRI OFIS.
     Rakipte olculdu (21.09.2026): ust seritten kanat degistirince
     OFISIN KENDISI degisiyor. Bizde fark UYDURULMUYOR: salonun halisi
     kanadin KENDI renginden turetiliyor -- o rengi kullanici veriyor.
     Kanat degisince kadro, masalar ve hali birlikte degisir. */
  const seciliKanat = D.ofis.kanatlar.find((k) => k.id === D.kanat);
  // Kanat ya da kadro degisti: onceki konumlar bu haritada anlamsiz --
  // tasinirsa ajanlar baska bir ofisin (ya da eski dizilisin) masasindan
  // "yurur"; hareket gercek bir olay olmali, yeniden dizilis degil.
  const kadroImza = ajanlar.map((a) => a.ad).sort().join(",");
  if (D.konumKanat !== D.kanat || D.konumKadro !== kadroImza) {
    D.konum = {}; D.yolda = {}; D.konumKanat = D.kanat; D.konumKadro = kadroImza;
  } else D.yolda = yolda;
  const harita = haritaKur(ajanlar, seciliKanat);
  kap.append(harita);
  haritaCanlandir(harita);

  // "HQ CANLI" SERIDI -- hangi ofiste oldugunu SOYLER. Sayilar OLCULUR.
  const tema = seciliKanat ? seciliKanat.renk : "";
  const serit = el("div", "hq-serit");
  if (tema) serit.style.setProperty("--oda-tema", tema);
  const calisan = ajanlar.filter((a) => a.oda === "masa").length;
  serit.append(
    el("span", "hq-nokta"),
    el("span", "hq-ad", (seciliKanat ? seciliKanat.ad : "TÜM OFİS") + " HQ canlı"),
    el("span", "hq-alt",
       `${ajanlar.length} ajan · ${calisan} masada`));
  kap.append(serit);
  kap.append(kadroSeridi(ajanlar));

  // TIKLA -> TERMINAL. Ofis gorunumunden cikmadan ajanin kendi akisi.
  if (D.secilenAjan) kap.append(katTerminali(D.secilenAjan, ajanlar));
  else kap.append(el("div", "kat-ipucu",
    "Bir ajana tıkla — kendi terminali burada açılır."));

  cizYapilanlar(kap);
  for (const ic of Object.values(D.panolar)) ic.scrollTop = ic.scrollHeight;
}

/* KADRO SERIDI -- haritanin altinda isim cipleri. Rakipte var ve degeri
   belli: haritada kalabalikta ajani bulmak zor, cip her zaman ayni yerde.
   Nokta ODANIN rengi (durum OLCULUR, `panel._oda`); uzerine gelince kart
   "su an ne yapiyor" der, isi yoksa bunu SOYLER (uydurmaz). Tiklamak
   haritadaki sprite ile AYNI yolu kullanir -- ikinci bir secim mantigi
   yok. */
function kadroSeridi(ajanlar) {
  const s = el("div", "kadro-serit");
  for (const a of ajanlar) {
    const c = el("button", "kadro-cip" + (D.secilenAjan === a.ad ? " secili" : ""));
    c.append(el("span", "kadro-nokta oda-" + a.oda), el("span", null, a.ad));
    const kart = el("div", "kadro-kart");
    const odaAd = (ODALAR.find((o) => o[0] === a.oda) || [])[1] || a.oda;
    kart.append(el("b", null, a.ad), el("div", "kadro-kart-alt",
                `${a.meslek}${a.lider_mi ? " · lider" : ""} · ${odaAd}`));
    // Not gorev numarasini zaten tasiyorsa tekrar yazilmaz ("#2 — #2 ...").
    const onek = a.gorev_no && !String(a.not || "").includes("#" + a.gorev_no)
      ? `#${a.gorev_no} — ` : "";
    kart.append(el("div", "kadro-kart-is", a.not
      ? onek + a.not : "Şu an aktif bir işi yok."));
    kart.append(el("div", "kadro-kart-alt", `${a.motor}/${a.model || "varsayılan"}`
      + " · tıkla → terminali"));
    c.append(kart);
    c.onclick = () => {
      D.secilenAjan = (D.secilenAjan === a.ad) ? null : a.ad;
      cizOfis();
    };
    s.append(c);
  }
  return s;
}

/* Secili ajanin terminali -- ofis gorunumunun ICINDE.

   Neden cekmece degil: cekmece ofisi ORTER. Rakipte olculen sey
   "sprite'a tikla, ADIYLA anilan terminali acilsin" ve degeri tam
   burada: kimin nerede calistigini gorurken ciktisini da okuyorsun.

   PANO ICI HER ZAMAN DOM'DA (bir kez odendi): ciktisi olmayan panoya
   `ic` eklenmezse canli akis GORUNMEYEN bir dugume yazar ve ajan
   kosarken pano bos kalir. Bosken CSS ile kucultulur, ilk satirda acilir. */
function katTerminali(ad, ajanlar) {
  const a = ajanlar.find((x) => x.ad === ad);
  return panoKur(a, {
    sinif: "kat-terminal",
    dugmeler: [
      ["ayrıntı", () => ajanAc(a.ad)],
      ["kapat", () => { D.secilenAjan = null; cizOfis(); }],
    ],
  });
}

/* NE YAPILDI -- dinlenen ofis ile HIC KULLANILMAMIS ofis ayni gorunmesin.

   Olculmus tasarim hatasi (21.09.2026): ofis 9 is bitirmis, $14,84
   harcamis, 40 karar uretmisti ve ana gorunum bunlarin hicbirini
   gostermiyordu. Ajan panolari kisaldiginda alt yari bombos kaliyordu.

   Burada gosterilen sey ISIN KENDISI degil, ISIN KANITI: her kartta
   kac kanit dustugu ve hangi yollarin kilitlendigi yaziyor. Rakipte
   boyle bir sey YOK cunku kanit kapisi da yok. */
function cizYapilanlar(kap) {
  const bitti = (D.tahta && D.tahta.bitti) || [];
  if (!bitti.length) return;
  const b = el("section", "yapilanlar");
  const bas = el("div", "yapilanlar-bas");
  bas.append(el("span", null, "NE YAPILDI"),
             el("span", "sayi", String(bitti.length)));
  b.append(bas);
  const izgara = el("div", "yapilanlar-izgara");
  for (const g of bitti.slice().reverse()) {
    const k = el("button", "yapilan");
    k.append(el("span", "yapilan-no", "#" + g.no),
             el("span", "yapilan-ad", g.baslik));
    const alt = el("div", "yapilan-alt");
    if (g.sahip) alt.append(el("span", null, g.sahip));
    // KANIT SAYISI: kapinin ekrandaki hali. Kanitsiz is kapanmaz --
    // bu sayi, isin neden kapandiginin cevabidir.
    alt.append(el("span", "yapilan-kanit", g.kanit + " kanıt"));
    for (const y of (g.yazma_alani || []).slice(0, 2))
      alt.append(el("span", "yapilan-alan", y));
    k.append(alt);
    k.onclick = () => gorevAc(g.no);
    izgara.append(k);
  }
  b.append(izgara);
  kap.append(b);
}

/* ─────────────── KOD: diskte OLCULEN degisiklik ───────────────

   Bu bolum ajanin ANLATTIGINI degil ofisin OLCTUGUNU gosterir. Ayrimin
   bedeli olculdu (22.09.2026): gercek ofiste 16 `diff` KANITI vardi ve
   hepsi ajanin kendi anlatisiydi ("ONCEKI / COZUM / satir 68-73").
   Okunakli, hatta dogru -- ama bir dosyanin degistigini degil, ajanin
   degistirdigini SOYLEDIGINI kanitliyor.

   Terminalin ALTINDA duruyor, ayri bir sekmede degil: ustte ajanin
   sozu, altta diskin cevabi. Ikisi yan yana olmazsa aradaki fark --
   bakilmasi gereken tek sey -- bir tiklamanin arkasinda kalir. */
async function cizKod() {
  const kap = $("#gorunum-kod");
  if (!kap) return;
  // Sekme EKRANDA degilse olcum cekilmez; ekrandaysa (arka sekme bile)
  // sayac tazelenir -- bayat bir sayac yanlis gosteren gostergedir.
  if (!panoGorunur("kod")) return;
  try {
    [D.kod, D.canli] = await Promise.all([al("/api/degisim"),
                                          al("/api/canli")]);
  } catch (e) {
    kap.textContent = "";
    kap.append(el("div", "bos", "değişim ölçümü okunamadı"));
    return;
  }
  const hepsi = (D.kod.kayitlar || [])
    .filter((k) => !D.kanat || k.kanat_id === D.kanat);

  const sayac = $("#sayac-kod");
  const not = $("#kod-not");
  const disiSayi = hepsi.filter((k) => k.beyan_disi).length;
  if (sayac) sayac.textContent = hepsi.length ? String(hepsi.length) : "";
  // OLCULMEYEN YERLER SOYLENIR. Bos bir Kod bolumu gorup "ajan hicbir
  // sey yazmadi" diye okumak, yanlis gosteren gostergenin ta kendisi
  // olurdu -- dis klasorler (--klasor) hic olculmuyor.
  if (not) {
    const notlar = [...new Set(hepsi.map((k) => k.kapsam_notu).filter(Boolean))];
    not.textContent = disiSayi
      ? disiSayi + " dosya BEYAN DIŞI"
      : (notlar[0] || "");
    not.classList.toggle("kotu", !!disiSayi);
  }
  if (!panoAcik("kod")) return;       // arka sekme: govde cizilmez

  kap.textContent = "";
  // CANLI blok ustte: once "su an ne yaziliyor", sonra "neler yazildi".
  const cb = el("div", "kod-canli");
  cb.id = "kod-canli";
  kap.append(cb);
  D.canliImza = "";
  canliBlokCiz();
  if (!hepsi.length) {
    // UYDURMAZ: "degisiklik yok" ile "olculmedi" ayri seylerdir.
    if (!canliSuz().length)
      kap.append(el("div", "bos",
        D.kod.kok ? "bu kanatta ölçülmüş bir dosya değişikliği yok"
                  : "proje kökü tanımlı değil — değişim ölçülemiyor"));
    return;
  }
  kap.append(el("div", "kod-ara", "ÖLÇÜLEN · tur sonunda kesinleşen"));
  for (const k of hepsi) kap.append(kodSatiri(k));
}

/* ─────────────── CANLI IZLEME: tur surerken disk ───────────────

   Rakipte ajan bir dosyaya yazdikca dosya editorde kendiliginden
   aciliyor ("Izleniyor: Nova"). Bizde kaynak yine DISK: koltuk tur
   surerken iki saniyede bir ucuz bir tarama yapar (degisim.py,
   `CanliIzleyici`) ve olculen ara farki yazar. Ajanin sozu gecmez.

   EN SON dokunulan dosya kendiliginden ACIK durur -- insan kapattiysa
   o karara saygi gosterilir, bir sonraki tazelemede yeniden acilmaz.

   SALT OKUNUR, bilincli: panelden duzenleme, yazma kilidinin gormedigi
   ikinci bir yazar olurdu (Yasa 1). Rakipte "Kaydet" var; bizde yok. */
function canliSuz() {
  return ((D.canli && D.canli.kayitlar) || [])
    .filter((k) => !D.kanat || k.kanat_id === D.kanat);
}

function canliBlokCiz() {
  const cb = $("#kod-canli");
  if (!cb || !panoAcik("kod")) return;
  const liste = canliSuz();
  const imza = liste.map((k) => k.id + ":" + k.damga).join("|")
    + "|" + (D.kanat || "");
  if (imza === D.canliImza) return;
  D.canliImza = imza;
  cb.textContent = "";
  if (!liste.length) return;
  const ajanlar = [...new Set(liste.map((k) => k.ajan_ad).filter(Boolean))];
  const bas = el("div", "kod-canli-bas");
  bas.append(el("span", "kod-canli-nokta"),
             el("span", "kod-canli-ad", "İZLENİYOR: " + ajanlar.join(", ")),
             el("span", "kod-canli-not",
                "tur sürüyor · ara ölçüm · salt okunur"));
  bas.title = "Diskte ölçülen ARA fark (ajanın sözü değil). Tur bitince "
    + "silinir; yerini aşağıdaki kesin kayıt alır.";
  cb.append(bas);
  liste.forEach((k, i) => {
    const s = kodSatiri({ ...k, id: "c:" + k.id }, i === 0);
    s.classList.add("canli");
    cb.append(s);
  });
}

async function canliTazele() {
  if (!panoGorunur("kod")) return;
  try {
    D.canli = await al("/api/canli");
  } catch (e) {
    return;           // bir sonraki yoklama yeniden dener
  }
  canliBlokCiz();
}

/* Yoklama YALNIZ gerektiginde: Kod panosu ekrandaysa VE ya bir ajan
   masadaysa ya da ekranda hala canli satir varsa (tur bitti, satir
   kalkmali). Bos ofiste iki buckukta bir istek atmak bos is. */
function canliYoklamaKur() {
  setInterval(() => {
    const kosan = !!(D.ofis && D.ofis.ajanlar.some((a) => a.oda === "masa"));
    if (!kosan && !canliSuz().length) return;
    canliTazele();
  }, 2500);
}

function kodSatiri(k, acikVarsayilan = false) {
  const kutu = el("div", "kod-satir");
  kutu.dataset.hal = k.hal;
  if (k.beyan_disi) kutu.classList.add("beyan-disi");

  const ust = el("button", "kod-ust");
  ust.append(el("span", "kod-hal", k.hal));
  ust.append(el("span", "kod-yol", k.yol));
  if (k.gorev_no) ust.append(el("span", "kod-hal", "#" + k.gorev_no));
  if (k.ajan_ad) ust.append(el("span", "kod-hal", k.ajan_ad));
  // KILIT BIR BEYANDIR ve bu bayrak beyanin GERCEKLE uyusmadigini
  // soyluyor -- Yasa 1'in ekrandaki hali.
  if (k.beyan_disi) ust.append(el("span", "kod-bayrak", "BEYAN DIŞI"));
  // Paralel turda "kim yazdi" bilinmez: suclama yok, ama sessizlik de
  // yok. Olcemedigimize hukum vermeyiz.
  if (k.atif_belirsiz)
    ust.append(el("span", "kod-bayrak belirsiz", "atıf belirsiz"));
  if (k.olculemedi)
    ust.append(el("span", "kod-bayrak olculemedi", k.olculemedi));

  const sayi = el("span", "kod-sayi");
  if (k.eklenen) sayi.append(el("span", "art", "+" + k.eklenen + " "));
  if (k.silinen) sayi.append(el("span", "eks", "−" + k.silinen));
  ust.append(sayi);
  kutu.append(ust);

  const acikMi = () => D.kodAcik[k.id] ?? !!acikVarsayilan;
  if (acikMi() && k.yama) kutu.append(yamaYaz(k.yama));
  ust.onclick = () => {
    if (!k.yama) return;
    D.kodAcik[k.id] = !acikMi();
    const eski = kutu.querySelector(".kod-yama");
    if (eski) eski.remove(); else kutu.append(yamaYaz(k.yama));
  };
  if (!k.yama) ust.style.cursor = "default";
  return kutu;
}

/* Yamayi RENKLENDIR ama OLCUMU DEGISTIRME.

   SATIR SONU TUZAGI (olculdu, tarayicida): Windows'ta dosyalar CRLF
   yazilir, `splitlines(keepends=True)` `"\rn"` birakir, ve `<pre>`
   icinde o yalniz `\r` gorunur bir cop olarak durur.

   Iki kolay cozum de YANLIS:
     * Olcumde satir sonlarini normallestirmek -- o zaman bir dosyanin
       satir sonu GERCEKTEN degistiginde (CRLF -> LF, cogu zaman istemeden
       ve tum dosyayi kirletecek bicimde) fark HIC gorunmez.
     * Ekranda kosulsuz kirpmak -- yalnizca satir sonu degismis bir yama
       "-foo" ve "+foo" diye ayni gorunur, yani okuyana yalan soyler.

   Kural: CR varligi yamada KARISIKSA gorunur kilinir (gostermek gerekir,
   fark orada), tekduzeyse sessizce kirpilir (gurultu). */
function yamaYaz(yama) {
  const pre = el("pre", "kod-yama");
  const satirlar = String(yama).split("\n").filter((x) => x !== "");
  const icerik = satirlar.filter((x) => !x.startsWith("@@")
    && !x.startsWith("+++") && !x.startsWith("---"));
  const crli = icerik.filter((x) => x.endsWith("\r")).length;
  const karisik = crli > 0 && crli < icerik.length;

  for (const ham of satirlar) {
    const cr = ham.endsWith("\r");
    const satir = cr ? ham.slice(0, -1) : ham;
    let sinif = "";
    if (satir.startsWith("+") && !satir.startsWith("+++")) sinif = "y-art";
    else if (satir.startsWith("-") && !satir.startsWith("---")) sinif = "y-eks";
    else if (satir.startsWith("@@")) sinif = "y-bas";
    const p = el("span", sinif, satir + (karisik && cr ? "␍" : "")
                 + "\n");
    pre.append(p);
  }
  return pre;
}

/* ─────────────── KABIN: panelin ICINDE gercek tarayici ───────────────

   Kullanici: *"sistemden cikip chrome acip ugrasmak istemem."*

   `iframe` DEGIL ve bu OLCULDU: admin.shopify.com, mail.google.com,
   www.google.com hepsi `X-Frame-Options: SAMEORIGIN`. Bir sure bundan
   "ancak Tauri ile olur" sonucunu cikardim -- YANLISTI. ChatGPT'nin
   ajan tarayicisi da iframe kullanmaz: uzaktaki tarayicinin
   KARELERINI akitir, ve o yol bir web sayfasinda aciktir.

   Burada akan sey CDP screencast (olculdu: ilk kare 445 ms, kare
   ~16,8 KB), ve tiklama/tuslar geri tasiniyor -- yani IZLENMIYOR,
   KULLANILIYOR. */
const K = { soket: null, acik: false, kare: null, secKipi: false, ogeZaman: 0 };

async function kabinDurum() {
  try { return await al("/api/kabin"); } catch (e) { return { acik: false }; }
}

async function kabinAc(url) {
  // Giris karti bir ADRESLE acar; kabin zaten aciksa o adrese gider.
  if (url && K.acik) {
    panoSec("tarayici");
    kabinYolla({ tur: "git", url });
    return;
  }
  const et = $("#kabin-etiket");
  et.textContent = "açılıyor…";
  let d;
  try {
    // Chrome gibi Google ile acilir (02.10.2026, patron).
    d = await yolla("/api/kabin/ac", { url: url || "https://www.google.com/" });
  } catch (e) {
    // UYDURMAZ: acilmadiysa sebebi gorunur olur.
    et.textContent = "tarayıcı";
    $("#kabin-bos").textContent = "açılamadı: " + (e.message || e);
    // Hata GORUNMELI: pano, acilamadigini soylemek icin ekrana gelir.
    K.hata = true;
    yerlesimCiz(); panoSec("tarayici");
    return;
  }
  kabinGoster(d);
  panoSec("tarayici");
  kabinBagla();
}

function kabinGoster(d) {
  const onceki = panoGorunur("tarayici");
  K.acik = !!(d && d.acik);
  if (K.acik) K.hata = false;
  // Tarayici acilip kapaninca yerlesim YENIDEN kurulur: kapaliyken yer
  // kaplamaz, acilinca kendi yerine gelir.
  if (D.yerlesim && onceki !== panoGorunur("tarayici")) {
    yerlesimCiz(); gorunurleriCiz();
  }
  $("#kabin-anahtar").classList.toggle("acik", K.acik);
  $("#kabin-etiket").textContent = K.acik ? "tarayıcı açık" : "tarayıcı";
  const sk = $("#sayac-kabin");
  if (sk) sk.textContent = K.acik ? "açık" : "kapalı";
  if (!K.acik) {
    $("#kabin-kare").hidden = true;
    $("#kabin-bos").textContent = "tarayıcı kapalı";
  }
}

async function kabinKapat() {
  K.sekme = null; K.bilinenSekmeler = null;
  K.sekmeDegisiyor = true;
  if (K.soket) { try { K.soket.close(); } catch (e) {} K.soket = null; }
  try { kabinGoster(await yolla("/api/kabin/kapat", {})); }
  catch (e) { kabinGoster({ acik: false }); }
}

function kabinBagla() {
  if (K.soket) return;
  const s = new WebSocket(
    (location.protocol === "https:" ? "wss://" : "ws://")
    + location.host + "/ws/kabin"
    + (K.sekme ? "?sekme=" + encodeURIComponent(K.sekme) : ""));
  kabinSekmeleriCiz();
  K.soket = s;
  s.onmessage = (m) => {
    const v = JSON.parse(m.data);
    if (v.tur === "kare") {
      const img = $("#kabin-kare");
      img.hidden = false;
      $("#kabin-bos").textContent = "";
      img.src = "data:image/jpeg;base64," + v.govde;
    } else if (v.tur === "oge") {
      // Secim kipi kapandiktan sonra gelen GEC hover cevabi cizilmez:
      // secili ogenin cercevesini baska bir ogeye kaydirirdi.
      if (!v.kalici && !K.secKipi) return;
      if (!v.oge) {
        ogeVurgu(null);
        if (v.kalici) bildir("burada seçilecek bir öğe yok (boş alan)", "uyari");
        return;
      }
      ogeVurgu(v.oge.kutu, v.kalici);
      if (v.kalici) {
        D.secilenOge = v.oge;
        secKipiAyarla(false, true);
        ogeCipi();
        bildir("öğe seçildi — lidere yazacağın mesaja eklenecek", "iyi");
        $("#komut-girdi").focus();
      }
    } else if (v.tur === "adres") {
      // URL cubugu GERCEGI gosterir: yonlendirme olursa yazdigin
      // adres degil GIDILEN adres. Uydurmaz.
      K.sonAdres = v.govde || "";
      setTimeout(kabinSekmeleriCiz, 600);    // baslik / yeni sekme
      if (document.activeElement !== $("#kabin-adres"))
        $("#kabin-adres").value = K.sonAdres;
      // Sayfa degisti: cerceve artik baska bir yeri gosterirdi. Secilen
      // ogenin BILGISI kalir (cipte), cercevesi kalkar.
      ogeVurgu(null);
    } else if (v.tur === "hata") {
      $("#kabin-kare").hidden = true;
      $("#kabin-bos").textContent = v.govde;
    }
  };
  s.onclose = async () => {
    // ESKI SOKETIN GEC KAPANISI (02.10.2026 olculdu): sekme degisirken
    // eski soketin onclose'u YENI soketi siliyordu; adres cubugundan
    // giden komutlar tarayiciya hic ulasmiyordu. Yalniz KENDISI.
    if (K.soket !== s) return;
    K.soket = null;
    // DONMUS KARE, CANLI TARAYICI GIBI GORUNUR.
    //
    // Olculdu (22.09.2026): kabin Chrome'u kapandi, panel son kareyi
    // gostermeye devam etti ve ekranda hicbir sey degismedi -- yani
    // "tarayici acik" diyen bir gosterge, kapali bir tarayiciyi
    // gosteriyordu. Bu projenin karsi kuruldugu sinif.
    //
    // Kopunca DURUM YENIDEN SORULUR (varsayilmaz) ve kare kaldirilir.
    const d = await kabinDurum();
    kabinGoster(d);
    if (!d.acik) {
      $("#kabin-kare").hidden = true;
      $("#kabin-bos").textContent = "tarayıcı kapandı";
      kabinSekmeleriCiz();
    } else if (!K.sekmeDegisiyor) {
      // Izlenen SEKME kapandi (tarayici acik): kalan sekmeye gecilir.
      K.sekme = null;
      setTimeout(kabinBagla, 300);
    }
    K.sekmeDegisiyor = false;
  };
}

/* SEKMELER (02.10.2026, patron: "tarayicida sekme acma neden yok").
   Panel eskiden yalniz ILK sekmeyi akitiyordu; yeni sekmede acilan
   baglanti hic gorunmuyordu. Secili sekme `K.sekme`; gecmek = o sekmeye
   yeniden baglanmak. Liste sunucudan gelir (uydurulmaz). */
async function kabinSekmeleriCiz() {
  const kap = $("#kabin-sekmeler");
  if (!kap) return;
  if (!K.acik) { kap.innerHTML = ""; return; }
  let r;
  try { r = await al("/api/kabin/sekmeler"); } catch (e) { return; }
  // SIRA Chrome gibi: yeni sekme SAGA eklenir. Chrome'un listesi en
  // yeniyi basa koyuyor (olculdu); ilk gorulme sirasi tutulur.
  K.sekmeSira = K.sekmeSira || new Map();
  for (const t of [...(r.sekmeler || [])].reverse())
    if (!K.sekmeSira.has(t.id)) K.sekmeSira.set(t.id, K.sekmeSira.size);
  const liste = [...(r.sekmeler || [])].sort(
    (a, b) => K.sekmeSira.get(a.id) - K.sekmeSira.get(b.id));
  // SAYFANIN ACTIGI YENI SEKME: patron sayfaya tikladiktan hemen sonra
  // beliren sekmeye Chrome gibi gecilir (target=_blank baglanti).
  const onceki = K.bilinenSekmeler;
  K.bilinenSekmeler = new Set(liste.map((t) => t.id));
  if (onceki && Date.now() - (K.sonTik || 0) < 5000) {
    const yeni = liste.find((t) => !onceki.has(t.id));
    if (yeni && yeni.id !== K.sekme) { K.sonTik = 0; kabinSekmeSec(yeni.id); return; }
  }
  // Yeni secilen sekme Chrome'un listesine birkac yuz ms gec duser;
  // o arada secim GERI ALINMAZ (olculdu: "+" yeni sekmeyi acti ama
  // panel ilk sekmede kaldi).
  if (K.sekme && !K.bilinenSekmeler.has(K.sekme)
      && Date.now() - (K.sekmeSecildi || 0) > 4000) K.sekme = null;
  if (!K.sekme && liste.length) K.sekme = liste[0].id;
  kap.innerHTML = "";
  for (const t of liste) {
    const b = el("div", "kabin-sekme" + (t.id === K.sekme ? " secili" : ""));
    b.title = t.adres;
    b.append(el("span", null, t.baslik || t.adres || "yeni sekme"));
    const x = el("button", null, "✕");
    x.title = "Sekmeyi kapat";
    x.onclick = async (e) => {
      e.stopPropagation();
      try { await yolla("/api/kabin/sekme/" + encodeURIComponent(t.id) + "/kapat", {}); }
      catch (er) { return bildir("kapatılamadı: " + er.message, "uyari"); }
      if (t.id === K.sekme) kabinSekmeSec(null); else kabinSekmeleriCiz();
    };
    b.append(x);
    b.onclick = () => { if (t.id !== K.sekme) kabinSekmeSec(t.id); };
    kap.append(b);
  }
  const yeni = el("button", "kabin-sekme-yeni", "+");
  yeni.title = "Yeni sekme (Google)";
  yeni.onclick = async () => {
    let t;
    try { t = await yolla("/api/kabin/sekme", {}); }
    catch (er) { return bildir("sekme açılamadı: " + er.message, "uyari"); }
    kabinSekmeSec(t.id);
  };
  kap.append(yeni);
}

function kabinSekmeSec(kimlik) {
  K.sekme = kimlik;
  K.sekmeSecildi = Date.now();
  K.sonAdres = undefined;
  if (K.soket) {
    K.sekmeDegisiyor = true;
    try { K.soket.close(); } catch (e) {}
    K.soket = null;
  }
  kabinBagla();
}

const kabinYolla = (m) => {
  if (K.soket && K.soket.readyState === 1) K.soket.send(JSON.stringify(m));
};

/* Koordinat NORMALLESTIRILMIS gidiyor (0..1). Piksel gonderseydik
   panel yeniden boyutlandiginda tiklama kayardi ve sebebi gorunmezdi --
   "yanlis gosteren gosterge"nin girdi tarafi. */
function kabinNokta(e) {
  const r = $("#kabin-kare").getBoundingClientRect();
  return { x: (e.clientX - r.left) / (r.width || 1),
           y: (e.clientY - r.top) / (r.height || 1) };
}

/* OGE SECICI. Secim kipinde fare SAYFAYA GITMEZ: "Yayinla" dugmesini
   secmek onu basmak olmamali -- riskli eylem kapisinin insan tarafindaki
   deligi olurdu. Istemci yalniz iki sayi gonderir; sayfada kosan ifade
   sunucuda sabittir (`kabin.oge_ifadesi`). */
function secKipiAyarla(acik, cerceveKalsin) {
  K.secKipi = !!acik;
  $("#kabin-sec").classList.toggle("acik", K.secKipi);
  $("#gorunum-kabin").classList.toggle("sec-kipi", K.secKipi);
  if (!K.secKipi && !cerceveKalsin) ogeVurgu(null);
}

function ogeVurgu(kutu, secili) {
  const v = $("#kabin-vurgu"), img = $("#kabin-kare");
  if (!kutu || img.hidden || !(kutu.en > 0) || !(kutu.boy > 0)) {
    v.hidden = true; return;
  }
  v.hidden = false;
  v.classList.toggle("secili", !!secili);
  v.style.left = (img.offsetLeft + kutu.x * img.clientWidth) + "px";
  v.style.top = (img.offsetTop + kutu.y * img.clientHeight) + "px";
  v.style.width = (kutu.en * img.clientWidth) + "px";
  v.style.height = (kutu.boy * img.clientHeight) + "px";
}

/* Secili ogenin OZETI. Insan hangi ogeyi gonderdigini gormeli; tam
   secici ve sayfa `title`da. */
function ogeCipi() {
  const c = $("#komut-oge"), o = D.secilenOge;
  c.innerHTML = "";
  if (!o) { c.hidden = true; return; }
  const ad = `⌖ <${o.etiket}>` + (o.metin ? ` "${o.metin.slice(0, 40)}"` : "")
    + (o.essiz ? "" : " · tek değil");
  const s = el("span", "", ad);
  c.title = `${o.secici}\n${o.url || ""}` + (o.sorgu_atildi ? "\n(adresin sorgu kısmı atıldı)" : "");
  const x = el("button", "", "✕");
  x.title = "Seçimi kaldır";
  x.onclick = () => { D.secilenOge = null; ogeCipi(); ogeVurgu(null); };
  c.append(s, x);
  c.hidden = false;
}

/* ADRES CUBUGU Chrome gibi (02.10.2026, patron: "youtube deyince
   calismiyor"): adres gibi gorunen yazi acilir, oteki her sey ARANIR.
   Sema yoksa https varsayilir, http'ye DUSULMEZ (`tarayici.kaynak_normalle`
   ile ayni kural); yalniz yerel adres (localhost, 127.x, IP:port) http. */
function adresCoz(u) {
  u = (u || "").trim();
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(u) || /^(about|data|file):/i.test(u)) return u;
  const yerel = /^(localhost|127(?:\.\d+){3}|\[::1\]|(?:\d{1,3}\.){3}\d{1,3})(:\d+)?(\/.*)?$/i;
  if (yerel.test(u)) return "http://" + u;
  // Adres: bosluk yok, bir noktali ad ve gecerli bir uzanti (youtube.com,
  // a.b.co/yol). "youtube", "hava durumu", "3.5 kg" ARANIR.
  if (!/\s/.test(u) && /^[^/?#]+\.[a-z]{2,}(?::\d+)?(?:[/?#].*)?$/i.test(u))
    return "https://" + u;
  return "https://www.google.com/search?q=" + encodeURIComponent(u);
}

function kabinKur() {
  const img = $("#kabin-kare");
  const alan = $("#gorunum-kabin");

  img.onmousedown = (e) => {
    e.preventDefault();
    // IKI YERE BIRDEN YAZMA (02.10.2026, patron): preventDefault odagi
    // adres cubugunda BIRAKIYORDU; sayfaya tikladiktan sonra yazilanlar
    // adres cubuguna dusuyordu. Odak acikca birakilir: tuslar YALNIZ
    // sayfaya gider.
    if (document.activeElement && document.activeElement !== document.body)
      document.activeElement.blur();
    alan.classList.add("odakli");
    K.sonTik = Date.now();
    const p = kabinNokta(e);
    if (K.secKipi) {                 // SECIM: fare sayfaya GITMEZ
      kabinYolla({ tur: "oge", ...p, sec: true });
      return;
    }
    kabinYolla({ tur: "fare", alt: "bas", ...p, dugme: "left", dugmeler: 1, tik: 1 });
  };
  img.onmouseup = (e) => {
    if (K.secKipi) return;
    const p = kabinNokta(e);
    kabinYolla({ tur: "fare", alt: "birak", ...p, dugme: "left", dugmeler: 0, tik: 1 });
  };
  img.onmousemove = (e) => {
    if (!K.soket) return;
    const p = kabinNokta(e);
    if (K.secKipi) {
      // Hover sorgusu SEYRELTILIR: her piksel bir CDP cagrisi olmasin.
      const t = Date.now();
      if (t - K.ogeZaman < 90) return;
      K.ogeZaman = t;
      kabinYolla({ tur: "oge", ...p });
      return;
    }
    kabinYolla({ tur: "fare", alt: "hareket", ...p, dugmeler: e.buttons });
  };
  img.onwheel = (e) => {
    e.preventDefault();
    ogeVurgu(null);                  // kaydirinca cerceve bayatlar
    const p = kabinNokta(e);
    kabinYolla({ tur: "tekerlek", ...p, dx: e.deltaX, dy: e.deltaY });
  };
  img.oncontextmenu = (e) => e.preventDefault();

  // KLAVYE yalnizca kabin ODAKLIYKEN gider. Yoksa komut cubuguna
  // yazarken tuslar sessizce tarayiciya da duserdi -- iki yere birden
  // yazan bir girdi, en sinsi hata turu.
  document.addEventListener("keydown", (e) => {
    if (K.secKipi && e.key === "Escape") { secKipiAyarla(false); return; }
    if (!alan.classList.contains("odakli") || !K.acik) return;
    if (document.activeElement === $("#kabin-adres")) return;
    e.preventDefault();
    const basilabilir = e.key.length === 1 && !e.ctrlKey && !e.altKey;
    kabinYolla({ tur: "tus", alt: "bas", tus: e.key, kod: e.code,
                 kk: e.keyCode, metin: basilabilir ? e.key : "" });
  });
  document.addEventListener("keyup", (e) => {
    if (!alan.classList.contains("odakli") || !K.acik) return;
    if (document.activeElement === $("#kabin-adres")) return;
    kabinYolla({ tur: "tus", alt: "birak", tus: e.key, kod: e.code,
                 kk: e.keyCode });
  });
  document.addEventListener("mousedown", (e) => {
    if (!alan.contains(e.target)) alan.classList.remove("odakli");
  });

  // Adres cubuguna gecince sayfa tus ALMAZ (tek yer).
  // Chrome gibi: adres cubuguna girince yazinin TAMAMI secilir; yeni yazi
  // eskisinin onune eklenmez (02.10.2026 olculdu: "youtubeabout:blank").
  // Yazip vazgecince (Enter'siz cikis) cubuk GERCEK adrese doner.
  $("#kabin-adres").onblur = () => {
    if (K.sonAdres !== undefined) $("#kabin-adres").value = K.sonAdres;
  };
  $("#kabin-adres").onfocus = () => {
    alan.classList.remove("odakli");
    setTimeout(() => $("#kabin-adres").select(), 0);
  };
  $("#kabin-adres").onkeydown = (e) => {
    if (e.key !== "Enter") return;
    let u = $("#kabin-adres").value.trim();
    if (!u) return;
    kabinYolla({ tur: "git", url: adresCoz(u) });
    // Chrome gibi: Enter'dan sonra cubuk birakilir ve GIDILEN adresi gosterir.
    $("#kabin-adres").blur();
  };
  $("#kabin-geri").onclick = () => kabinYolla({ tur: "geri" });
  $("#kabin-yenile").onclick = () => kabinYolla({ tur: "yenile" });
  $("#kabin-kapat").onclick = kabinKapat;
  const izleCiz = (acik) => {
    const b = $("#kabin-izle"); if (!b) return;
    b.classList.toggle("acik", !!acik);
    b.textContent = acik ? "ajanlar: burada" : "ajanlar: kapalı";
  };
  al("/api/kabin/izle").then((r) => izleCiz(r.acik)).catch(() => {});
  // Sekme seridi tazelenir (yeni sekme, degisen baslik); pano gorunurken.
  setInterval(() => {
    if (K.acik && !document.hidden && panoGorunur("tarayici")) kabinSekmeleriCiz();
  }, 2500);
  $("#kabin-izle").onclick = async () => {
    const simdi = $("#kabin-izle").classList.contains("acik");
    try {
      const r = await yolla("/api/kabin/izle", { acik: !simdi });
      izleCiz(r.acik);
      bildir(r.acik ? "ajanlar kabinde: tarayıcılı iş burada canlı koşacak (kabin açıkken)"
                    : "ajanlar kendi görünmez tarayıcılarına döndü", "iyi");
    } catch (e) { bildir("ayarlanamadı: " + e.message, "uyari"); }
  };
  $("#kabin-sec").onclick = () => {
    if (!K.acik) return bildir("önce tarayıcıyı aç", "uyari");
    secKipiAyarla(!K.secKipi);
    if (K.secKipi) bildir("seçim kipi: bir öğeye tıkla (tıklama sayfaya gitmez) · Esc çık");
  };
  // ANAHTAR KAPATMAZ (24.09.2026). Acikken ayni dugmeye basmak
  // kabini KAPATIYORDU: kullanici "tarayiciya bakayim" diye bastiginda
  // tarayici gidiyordu ve "calismiyor" sandi. Acikken dugme panoyu one
  // getirir; kapatmak yalniz panonun kendi ✕ dugmesiyle.
  $("#kabin-anahtar").onclick = () => {
    if (!K.acik) return kabinAc();
    panoSec("tarayici");
    kabinBagla();
  };
}

function cizTahta() {
  const kap = $("#gorunum-tahta");
  kap.innerHTML = "";
  const izgara = el("div", "tahta");
  for (const [anahtar, ad] of Object.entries(SUTUN_AD)) {
    const kartlar = D.tahta[anahtar] || [];
    const s = el("div", "sutun");
    s.dataset.sutun = anahtar;
    const bas = el("div", "sutun-bas");
    bas.append(el("span", null, ad), el("b", null, String(kartlar.length)));
    const govde = el("div", "sutun-govde");
    for (const g of kartlar) {
      const k = el("div", "gorev-kart");
      k.append(el("div", "gorev-no", "#" + g.no),
               el("div", "gorev-baslik", g.baslik));
      const alt = el("div", "gorev-alt");
      if (g.sahip) alt.append(el("span", null, g.sahip));
      // BIZE OZGU: yazma alani kilidi kartta gorunur.
      if (g.kilitli && g.yazma_alani.length)
        alt.append(el("span", "kilit", "\u{1F512} " + g.yazma_alani.join(" ")));
      if (g.kanit) alt.append(el("span", "kanit-say", g.kanit + " kanıt"));
      if (g.blokci.length)
        alt.append(el("span", null, "#" + g.blokci.join(", #") + " bekliyor"));
      k.append(alt);
      k.onclick = () => gorevAc(g.no);
      govde.append(k);
    }
    s.append(bas, govde);
    izgara.append(s);
  }
  kap.append(izgara);
}

/* ─────────────── senden bekleniyor ─────────────── */

async function cizBekleyenler() {
  const kap = $("#bekleyen-bolum");
  const b = await al("/api/bekleyenler");
  // Terminal panolari ayni kuyrugu okur (B6: soru kendi terminalinin ustunde).
  const _onceki = JSON.stringify(((D.bekleyen || {}).sorular || []).map((x) => x.id))
                + JSON.stringify(((D.bekleyen || {}).onaylar || []).map((x) => x.id));
  D.bekleyen = b;
  if (_onceki !== JSON.stringify((b.sorular || []).map((x) => x.id))
                 + JSON.stringify((b.onaylar || []).map((x) => x.id))) {
    try { cizCanli(); } catch (_) {}
  }
  // SAGLIK BULGULARI DA BURAYA. Olculdu (21.09.2026): `saglik.py` 12
  // denetimle yazilmisti ve `panel.py` icinde adi bile gecmiyordu --
  // yani panelin cevapladigini soyledigi tek soru ("neye bakmam
  // gerekiyor?") icin yazilmis arac, panele HIC baglanmamisti.
  //
  // Yalnizca isi DURDURAN ve INSANA dusen bulgular gelir. "bilgi"
  // agirligindakiler buraya girseydi kuyruk gurultuye bogulur ve
  // insan ona bakmayi birakirdi -- her seye "sorun" diyen gosterge de
  // gostergesizlikten farksizdir.
  let sag = { bulgular: [] };
  try { sag = await al("/api/saglik"); } catch (e) { /* olculemedi */ }
  // Ekip ve guncelleme onerileri artik KART olarak ciziliyor (karar
  // panelden verilir); ayni seyi saglik bulgusu olarak da saymak, kuyrugu
  // IKI KEZ sayardi. Ayrim `kod` ile -- baslik metniyle degil.
  // `insan_kuyrugu` da: soru ve onaylar hemen asagida KART olarak duruyor;
  // bulgu olarak da saymak kuyruk sayacini sisiriyordu (olculdu, 23.09).
  const KARTLI = new Set(["ekip_onerisi", "guncelleme", "insan_kuyrugu"]);
  const bulgular = (sag.bulgular || [])
    .filter(x => (x.agirlik === "tikali" || x.agirlik === "insan")
                 && !KARTLI.has(x.kod));
  let on = { ekip: [], guncelleme: [], uygulanan: [] };
  try { on = await al("/api/oneriler"); } catch (e) { /* olculemedi */ }
  on.uygulanan = on.uygulanan || [];

  const adet = b.sorular.length + b.onaylar.length + bulgular.length
             + on.ekip.length + on.guncelleme.length + (on.hafiza || []).length;
  kap.innerHTML = "";

  const bas = el("div", "bekleyen-bas" + (adet ? "" : " sakin"));
  bas.append(el("span", null, "SENDEN BEKLENİYOR"));
  if (adet) bas.append(el("span", "sayi", String(adet)));
  kap.append(bas);
  // ONAY YORGUNLUGU OLCULUR (E80): bugun kac kez soruldu, kac adim senin
  // iznine dayanarak sorulmadan gecti. Cok soruluyorsa kartta "Bu projede hep".
  const sy = b.onay_sayaci;
  if (sy && (sy.bugun_soruldu || sy.bugun_izinle_gecti || sy.kalici_izin))
    kap.append(el("div", "sonuk",
      `bugün ${sy.bugun_soruldu} onay soruldu · ${sy.bugun_izinle_gecti} adım senin izninle sorulmadan geçti`
      + ` · ${sy.kalici_izin} kalıcı izin`));

  // OTOMATIK UYGULANAN GUNCELLEMELER: senden KARAR beklemez (sayaca
  // girmez) ama gorulene kadar durur -- sessizce degisen model olmasin.
  // Kartta ne oldugu, deneme sonucu ve GERI AL.
  for (const u of on.uygulanan) {
    const d = el("div", "istek guncelleme-bilgi");
    const ust = el("div", "istek-bas");
    ust.append(el("span", "istek-kim", u.veren === "insan" ? "ofis" : "OTOMATİK"),
               el("span", null, `güncelleme uygulandı · #${u.sira}`));
    const ne = u.ad ? `${u.ad} (${u.motor})` : u.motor + (u.tur === "cli" ? " CLI" : "");
    d.append(ust, el("div", "istek-govde", `${ne}: ${u.eski || "—"} → ${u.yeni}`));
    d.append(el("div", "istek-ayrinti",
      "Deneme turu geçti" + (u.deneme ? ` (cevap: ${u.deneme})` : "")
      + (u.tur === "cli"
         ? ". Beğenmezsen geri al: eski sürüm yeniden kurulur, bu sürüm bir daha kendiliğinden gelmez."
         : ". Eski model silinmedi; beğenmezsen geri al, bir daha kendiliğinden gelmez.")));
    const satir = el("div", "istek-eylem");
    const tamam = el("button", "dugme", "Tamam");
    const geri = el("button", "dugme olumsuz", "Geri al");
    tamam.onclick = () => eylem(`/api/guncelle/gecmis/${u.sira}/goruldu`, {},
                                `güncelleme #${u.sira} görüldü`);
    geri.onclick = () => eylem(`/api/guncelle/gecmis/${u.sira}/geri_al`,
                               { sebep: "panelden geri alindi" },
                               (r) => r.mesaj || `güncelleme #${u.sira} geri alındı`);
    satir.append(tamam, geri);
    d.append(satir);
    kap.append(d);
  }

  if (!adet) {
    kap.append(el("div", "bekleyen-yok", "Şu an senden beklenen bir şey yok."));
    ofisOnerileriCiz(kap, on);
    return;
  }

  // Once isi DURDURANLAR: agirlik sirasi `saglik.py`den gelir, panel
  // kendi sirasini icat etmez -- iki yerde tutulan sira kayar.
  for (const x of bulgular) {
    const d = el("div", "istek saglik " + x.agirlik);
    const ust = el("div", "istek-bas");
    ust.append(el("span", "istek-kim", x.agirlik === "tikali" ? "TIKALI" : "SENDE"),
               el("span", null, x.baslik));
    d.append(ust);
    if (x.ayrinti) d.append(el("div", "istek-govde", x.ayrinti));
    // CARE HER ZAMAN GOSTERILIR: teshis koyup care soylemeyen
    // gosterge, insani bir kez daha dusunmeye zorlar.
    if (x.care) d.append(el("div", "istek-ayrinti", "→ " + x.care));
    kap.append(d);
  }

  // EKIP ONERISI: kurmadan ONCE kadro gorunur (ad, rol, motor/model,
  // gerekce). Onizlemede gorunmeyen bir secim, onay alinmamis bir secimdir.
  for (const e of on.ekip) {
    const d = el("div", "istek onay");
    const ust = el("div", "istek-bas");
    ust.append(el("span", "istek-kim", e.oneren || "lider"),
               el("span", null, `ekip öneriyor · #${e.no}`));
    d.append(ust, el("div", "istek-govde", e.hedef));
    if (e.gerekce) d.append(el("div", "istek-ayrinti", e.gerekce));
    for (const u of e.uyeler) {
      const s = el("div", "oneri-uye");
      s.append(el("b", null, "+ " + u.ad), document.createTextNode(
        ` · ${u.rol} · ${u.motor}/${u.model || "(model yok!)"} · ${u.tur}`));
      if (u.gerekce) s.append(el("div", null, u.gerekce));
      if (u.uyari) s.append(el("div", "uyari", "! " + u.uyari));
      d.append(s);
    }
    const satir = el("div", "istek-eylem");
    const girdi = el("input");
    girdi.placeholder = "Ret gerekçesi (ret için zorunlu)";
    const kur = el("button", "dugme olumlu", "Kur ve işi başlat");
    kur.title = "Önerilen kadroyu işe al; bu öneriyi doğuran isteğin lidere geri gider ve iş başlar.";
    const yalniz = el("button", "dugme", "Yalnız kur");
    yalniz.title = "Kadroyu işe al ama işi başlatma (isteği sonra kendin yazarsın).";
    const red = el("button", "dugme olumsuz", "Reddet");
    const kurulan = (r) => `ekip #${e.no} kuruldu: ` + (r.alinan || []).map(x => x.ad).join(", ");
    kur.onclick = () => eylem(`/api/ekip/${e.no}/kur`, { baslat: true },
      (r) => kurulan(r) + (r.baslatildi ? " — istek lidere gitti, iş başlıyor"
                           : r.baslatilamadi ? ` — iş başlatılamadı: ${r.baslatilamadi}` : ""));
    yalniz.onclick = () => eylem(`/api/ekip/${e.no}/kur`, { baslat: false }, kurulan);
    red.onclick = () => {
      if (!girdi.value.trim()) {
        girdi.placeholder = "Gerekçe zorunlu — lider aynı öneriyi tekrar getirmesin";
        return girdi.focus();
      }
      eylem(`/api/ekip/${e.no}/red`, { sebep: girdi.value }, `ekip #${e.no} reddedildi`);
    };
    satir.append(girdi, kur, yalniz, red);
    d.append(satir);
    kap.append(d);
  }

  // HAFIZA ONERISI (06.10): sohbette soyledigin kalici bilgi. Lider onerir,
  // yazan SENSIN; alinti senin mesajindan aynen (ofis denetledi).
  for (const h of (on.hafiza || [])) {
    const d = el("div", "istek onay");
    const ust = el("div", "istek-bas");
    ust.append(el("span", "istek-kim", h.oneren || "lider"),
               el("span", null, "hafızaya yazayım mı?"));
    d.append(ust, el("div", "istek-govde", `${h.konu} → ${h.icerik}`));
    d.append(el("div", "istek-ayrinti", `senin sözün: «${h.alinti}»`
      + (h.simdiki ? ` · hafızada şu an: ${h.simdiki}` : "")));
    const satir = el("div", "istek-eylem");
    const yaz = el("button", "dugme olumlu", "Takıma yaz");
    yaz.title = "Bu takımın hafızasına: yalnız bu takımın ajanları görür.";
    const yazma = el("button", "dugme olumsuz", "Yazma");
    yaz.onclick = () => eylem(`/api/hafiza_onerisi/${h.id}`, { yaz: true }, `hafızaya yazıldı: ${h.konu}`);
    yazma.onclick = () => eylem(`/api/hafiza_onerisi/${h.id}`, { yaz: false }, "yazılmadı");
    // HERKESE (06.10): bilgi yalniz bu takimin degil, butun takimlarin.
    const herkese = el("button", "dugme", "Herkese yaz");
    herkese.title = "Ortak hafızaya: bütün takımların ajanları görür.";
    herkese.onclick = () => eylem(`/api/hafiza_onerisi/${h.id}`, { yaz: true, herkese: true },
                                  `ortak hafızaya yazıldı: ${h.konu}`);
    satir.append(yaz, herkese, yazma);
    d.append(satir);
    kap.append(d);
  }

  // GUNCELLEME: once DENEME TURU kosar; duserse eskisi kalir. Yeni aile
  // kendiliginden yerlesmez -- kademe insanin secimidir.
  for (const g of on.guncelleme) {
    const d = el("div", "istek onay");
    const ust = el("div", "istek-bas");
    ust.append(el("span", "istek-kim", "ofis"),
               el("span", null, `güncelleme · #${g.no}`));
    d.append(ust, el("div", "istek-govde", g.ozet));
    // Otomatik denendi ve DUSTU: neden sana dustugu gorunsun.
    if (g.otomatik_dustu)
      d.append(el("div", "istek-ayrinti", "Otomatik deneme düştü: " + g.otomatik_dustu));
    const ek = [];
    if (g.kademeler && g.kademeler.length) ek.push("kademe: " + g.kademeler.join(", "));
    if (g.ajanlar && g.ajanlar.length) ek.push("ajan: " + g.ajanlar.join(", "));
    if (g.tur === "cli") ek.push("bilgisayardaki BÜTÜN bu CLI kullanıcılarını etkiler");
    if (ek.length) d.append(el("div", "istek-ayrinti", ek.join(" · ")));
    const satir = el("div", "istek-eylem");
    const girdi = el("input");
    girdi.placeholder = "Ret gerekçesi (ret için zorunlu)";
    const kad = el("select");
    kad.title = "Yeni aile kendiliğinden yerleşmez: hangi kademeye?";
    for (const [v, t] of [["", "kademe (varsa)"], ["hizli", "hızlı"],
                          ["standart", "standart"], ["guclu", "güçlü"]])
      kad.append(Object.assign(el("option", null, t), { value: v }));
    const ver = el("button", "dugme olumlu", "Dene ve uygula");
    ver.title = "Önce kısa bir deneme turu koşar; düşerse eskisi kalır.";
    const red = el("button", "dugme olumsuz", "Reddet");
    ver.onclick = () => {
      bildir(`güncelleme #${g.no}: deneme turu koşuyor…`);
      eylem(`/api/guncelle/${g.no}/onayla`, { kademe: kad.value },
            (r) => (r.basarili ? "UYGULANDI: " : "UYGULANMADI: ") + (r.mesaj || ""));
    };
    red.onclick = () => {
      if (!girdi.value.trim()) {
        girdi.placeholder = "Gerekçe zorunlu";
        return girdi.focus();
      }
      eylem(`/api/guncelle/${g.no}/reddet`, { sebep: girdi.value },
            `güncelleme #${g.no} reddedildi`);
    };
    satir.append(girdi, kad, ver, red);
    d.append(satir);
    kap.append(d);
  }

  for (const a of b.onaylar) kap.append(onayKartiYap(a));

  // TOPLU KABUL (08.10, B1): onerilen secenegi olan sorularin hepsi tek
  // tikla onerilenle cevaplanir. Onay kartlari (para, silme, yayin) DAHIL DEGIL.
  const onerili = b.sorular.filter(s => s.secim && s.secim.onerilen != null);
  if (onerili.length) {
    const tk = el("div", "istek-eylem toplu-kabul");
    const dg = el("button", "dugme olumlu", `Önerilenlerin hepsini kabul et (${onerili.length})`);
    dg.title = "Ajanların önerdiği seçenekle cevaplar: " +
      onerili.map(s => `${s.gonderen}: ${s.secim.secenekler[s.secim.onerilen]}`).join(" · ") +
      ". Onay kartları (para, silme, yayın) bundan etkilenmez.";
    dg.onclick = () => eylem("/api/sorular/onerilenleri_kabul", {},
                             (r) => `${(r.cevaplanan || []).length} soru önerilenle cevaplandı`);
    tk.append(dg);
    kap.append(tk);
  }
  for (const s of b.sorular) kap.append(soruKartiYap(s));
  ofisOnerileriCiz(kap, on);
}

/* ONAY KARTI -- sagdaki kutu ve sohbet karti AYNI cizimi kullanir (09.10). */
function onayKartiYap(a) {
    // GIRIS ISTEGI: sifre ajana gecmez; insan kendisi girer, "yaptim" der.
    if (a.giris) {
      const g = a.giris;
      const o = el("div", "istek onay giris");
      const ust = el("div", "istek-bas");
      ust.append(el("span", "istek-kim", a.isteyen),
                 el("span", null, "giriş istiyor"),
                 el("span", "istek-risk", g.tur === "web" ? "SİTE" :
                    g.tur === "baglayici" ? "BAĞLAYICI" : "DİĞER"));
      if (a.gorev_no) ust.append(el("span", null, "#" + a.gorev_no));
      o.append(ust, el("div", "istek-govde", g.hizmet + (g.adres ? " — " + g.adres : "")),
               el("div", "istek-ayrinti", g.neden));
      // Talimat uzun: kuyruk kutusu sabit yukseklikte, dugmeler kesiliyordu
      // (tarayicida olculdu). Acilir; ilk kez gorenin okuyacagi yer.
      const ne = el("details", "istek-ayrinti giris-ne");
      ne.append(el("summary", null, "Ne yapacaksın? (şifreyi ajana yazma)"),
                el("div", null, g.talimat));
      o.append(ne);
      const satir = el("div", "istek-eylem");
      const girdi = el("input");
      girdi.placeholder = "Not (\u201cYapamam\u201d için zorunlu)";
      if (g.tur === "web" && g.adres) {
        const kab = el("button", "dugme", "Kabinde aç");
        kab.title = "Paylaşılan tarayıcıda giriş sayfasını açar; şifreyi SEN yazarsın.";
        kab.onclick = () => kabinAc(g.adres);
        satir.append(kab);
      }
      const ver = el("button", "dugme olumlu", "Giriş yaptım");
      ver.title = g.tur === "baglayici"
        ? "Ofis bağlandığını ÖLÇER; bağlı değilse kabul etmez."
        : "İş senin oturumunla sürer (paylaşılan kabinde).";
      const red = el("button", "dugme olumsuz", "Yapamam");
      ver.onclick = () => eylem(`/api/onay/${a.id}`,
        { onayla: true, not_: girdi.value, kapsam: "eylem" }, "giriş yapıldı — iş sürüyor");
      red.onclick = () => {
        if (!girdi.value.trim()) {
          girdi.placeholder = "Gerekçe zorunlu — ajan neden girilmediğini bilmeli";
          return girdi.focus();
        }
        eylem(`/api/onay/${a.id}`, { onayla: false, not_: girdi.value },
              "giriş yapılmadı — gerekçe ajana iletilecek");
      };
      satir.prepend(girdi);
      satir.append(ver, red);
      o.append(satir);
      return o;
    }
    const o = el("div", "istek onay");
    const ust = el("div", "istek-bas");
    ust.append(el("span", "istek-kim", a.isteyen),
               el("span", null, "onay istiyor"),
               el("span", "istek-risk", "RİSK: " + a.risk.toUpperCase()));
    o.append(ust, el("div", "istek-govde", a.eylem));
    if (a.ayrinti) o.append(el("div", "istek-ayrinti", a.ayrinti));
    // ONIZLEME (06.10, K14): yayindan ONCE isin sitesine bak.
    if (a.onizleme && a.gorev_no) {
      const oz = el("button", "dugme", "Önizlemeyi aç");
      oz.title = "İşin klasöründeki site bu bilgisayarda açılır (yayına almadan önce bak).";
      oz.onclick = () => onizlemeAc(a.gorev_no);
      const ozs = el("div", "istek-eylem"); ozs.append(oz); o.append(ozs);
    }
    const satir = el("div", "istek-eylem");
    const girdi = el("input");
    girdi.placeholder = "Not (ret için zorunlu)";
    // IKI KADEME: varsayilan DAR (bir kez). "Bu is boyunca" insanin ACIK
    // tercihi -- yoksa bir "evet" sessizce surekli yetkiye doner.
    const ver = el("button", "dugme olumlu", "Bir kez");
    ver.title = "Bu eylem BİR KEZ geçer; tekrar gerekirse yeniden sorulur.";
    const hep = el("button", "dugme", "Bu iş boyunca");
    hep.title = "Bu görev bitene kadar AYNI eylem bir daha sorulmaz.";
    const red = el("button", "dugme olumsuz", "Reddet");
    ver.onclick = () => eylem(`/api/onay/${a.id}`,
      { onayla: true, not_: girdi.value, kapsam: "eylem" }, "onaylandı (bir kez)");
    hep.onclick = () => eylem(`/api/onay/${a.id}`,
      { onayla: true, not_: girdi.value, kapsam: "is" }, "onaylandı (bu iş boyunca)");
    // UCUNCU KADEME (06.10, onay yorgunlugu): yalniz kalici izne donusebilen
    // kartta (kural sunucuda: izin.karttan_izin). Para/silme/sifre hic cikmaz.
    let proje = null;
    if (a.kalici && a.kalici.verilebilir) {
      proje = el("button", "dugme", "Bu projede hep");
      proje.title = `Bu projede "${a.kalici.desen}" bir daha SORULMAZ (kalıcı izin). Ayarlar > İzinler'den kaldırılır.`;
      proje.onclick = () => {
        if (!confirm(`Bu projede "${a.kalici.desen}" bundan sonra sana sorulmadan geçecek. Emin misin?`)) return;
        eylem(`/api/onay/${a.id}`, { onayla: true, not_: girdi.value, kapsam: "proje" },
              "onaylandı (bu projede hep — kalıcı izin yazıldı)");
      };
    }
    red.onclick = () => {
      if (!girdi.value.trim()) {
        girdi.placeholder = "Ret gerekçesi zorunlu — ajan neyi yapmayacağını bilmeli";
        return girdi.focus();
      }
      eylem(`/api/onay/${a.id}`, { onayla: false, not_: girdi.value },
            "reddedildi — gerekçe ajana iletilecek");
    };
    satir.append(girdi, ver, hep, ...(proje ? [proje] : []), red);
    o.append(satir);
    return o;
}

/* SORU KARTI -- sagdaki kutu ve sohbet karti AYNI cizimi kullanir (09.10). */
function soruKartiYap(s) {
    const o = el("div", "istek soru");
    const ust = el("div", "istek-bas");
    ust.append(el("span", "istek-kim", s.gonderen), el("span", null, "soruyor"));
    if (s.gorev_no) ust.append(el("span", null, "#" + s.gorev_no));
    o.append(ust, el("div", "istek-govde", s.govde));
    // SECENEKLI SORU (B1): secenekler dugme; onerilen hazir secili gelir.
    let secili = s.secim && s.secim.onerilen != null ? s.secim.onerilen : null;
    if (s.secim) {
      const sec = el("div", "secenekler");
      const dugmeler = s.secim.secenekler.map((t, i) => {
        const d = el("button", "secenek" + (i === secili ? " secili" : ""),
                     t + (i === s.secim.onerilen ? "  ★ önerilen" : ""));
        d.onclick = () => {
          secili = i;
          dugmeler.forEach((x, j) => x.classList.toggle("secili", j === i));
        };
        return d;
      });
      sec.append(...dugmeler);
      o.append(sec);
    }
    const satir = el("div", "istek-eylem");
    const girdi = el("input");
    girdi.placeholder = s.secim ? "İstersen not ekle (ya da kendi cevabını yaz)…" : "Cevabın…";
    const dg = el("button", "dugme olumlu", "Cevapla");
    const gonder = () => {
      const ek = girdi.value.trim();
      const metin = s.secim && secili != null
        ? s.secim.secenekler[secili] + (ek ? " — " + ek : "") : ek;
      if (!metin) return;
      eylem(`/api/soru/${s.id}/cevap`, { metin }, "cevap gönderildi");
    };
    dg.onclick = gonder;
    girdi.addEventListener("keydown", (e) => { if (e.key === "Enter") gonder(); });
    satir.append(girdi, dg);
    o.append(satir);
    return o;
}

/* OFISIN KENDI EKSIGI (06.10, K17): acil kartlarin ALTINDA -- karar bekler ama
   isi durdurmaz; onay ve sorular once gorunur. */
function ofisOnerileriCiz(kap, on) {
  // OFISIN KENDI EKSIGI (06.10, K17): olculmus tekrar eden sorun. Acil degil
  // (sayaca girmez) ama karar bekler: Onayla = duzeltilsin, Gereksiz = bir daha gelmez.
  for (const x of on.ofis || []) {
    const d = el("div", "istek guncelleme-bilgi");
    const ust = el("div", "istek-bas");
    ust.append(el("span", "istek-kim", "OFİSİN ÖNERİSİ"), el("span", null, x.baslik));
    d.append(ust, el("div", "istek-govde", x.oneri));
    if ((x.ornekler || []).length)
      d.append(el("div", "istek-ayrinti", "örnek: " + x.ornekler.map((o) => kes(o, 140)).join(" · ")));
    const satir = el("div", "istek-eylem");
    const ok = el("button", "dugme olumlu", "Onayla");
    ok.title = "Düzeltilsin: geliştirme listesine yazılır (ofis kendini kurmaz; düzeltmeyi insan kurar).";
    const yok = el("button", "dugme", "Gereksiz");
    yok.title = "Bu öneri bir daha gelmez.";
    ok.onclick = () => eylem(`/api/eksik/${x.anahtar}`, { karar: "onayla" }, "öneri onaylandı — geliştirme listesine yazıldı");
    yok.onclick = () => eylem(`/api/eksik/${x.anahtar}`, { karar: "gereksiz" }, "öneri kapatıldı");
    satir.append(ok, yok);
    d.append(satir);
    kap.append(d);
  }
}

/* ─────────────── sağ sekmeler ─────────────── */

/* UCUNCU SUTUNUN SEKMELERI: gorevler · raporlar · hafiza · kararlar ·
   hesap. Ayri sag kolon (360px) kaldirildi; icerik SILINMEDI, yeri
   degisti. Gorunurluk tek yerde karar verilir -- iki yerde verilseydi
   biri digerini ezerdi ve bos bir bolme "icerik yok" sanilirdi. */
async function cizSekme() {
  // Raporlar / Hafiza / Kararlar artik AYRI panolar: her biri kendi
  // kabina cizilir ve yalniz EKRANDAYSA cizilir.
  const ciz = { raporlar: cizRaporlar, hafiza: cizHafiza, kararlar: cizKararlar,
                yetenek: cizYetenek, sohbet: cizSohbet, denetim: cizDenetim,
                durum: cizDurum };
  // Konsol kendi kabini SILMEDEN cizer (terminal dugumu tasinir).
  if (panoAcik("konsol")) cizKonsol();
  for (const [p, f] of Object.entries(ciz)) {
    if (!panoAcik(p)) continue;
    const kap = $("#pano-" + p);
    // INSAN YAZARKEN PANO YENIDEN CIZILMEZ. Olculdu (24.09.2026): her
    // canli olay (kanit, karar, olgu...) bu panolari bastan ciziyor;
    // Hafiza'da bilgi yazan insanin yarim metni bir ajanin kanitiyla
    // SILINIYORDU. Cizim bir sonraki tazelemeye kalir -- veri kaybolmaz,
    // yazilan metin kaybolurdu.
    const odak = document.activeElement;
    if (odak && kap.contains(odak) && /^(INPUT|TEXTAREA)$/.test(odak.tagName)
        && odak.value) continue;
    if (medyaKullaniliyor(kap)) continue;
    if (p === "sohbet") { await sohbetiTazele(kap); continue; }
    kap.textContent = "";
    await f(kap);
  }
}

/* DURUM TABLOSU (08.10, B2 + B4): her isin GERCEK durumu (seni mi bekliyor,
   giris mi, kredi onayi mi, baska is mi, liderin incelemesi mi), son adimi;
   her ajanin ne yaptigi ve sirasi; lidere giden ama baslamamis istekler.
   Kural sunucuda (`ofis/durum_tablosu.py`); burada yalniz cizim. */
const DURUM_TUR = { sen: ["seni bekliyor", "dt-sen"], durdu: ["durdu", "dt-durdu"],
                    calisiyor: ["çalışıyor", "dt-calisiyor"], inceleme: ["incelemede", "dt-inceleme"],
                    bekliyor: ["bekliyor", "dt-bekliyor"], sirada: ["sırada", "dt-sirada"] };
function sureKisa(sn) {
  if (sn == null) return "";
  if (sn < 60) return `${sn} sn`;
  if (sn < 3600) return `${Math.round(sn / 60)} dk`;
  if (sn < 86400) return `${Math.round(sn / 3600)} sa`;
  return `${Math.round(sn / 86400)} gün`;
}
async function cizDurum(kap) {
  let r;
  try { r = await al("/api/durum"); }
  catch (e) { return kap.append(el("div", "form-ipucu uyari", "durum okunamadı: " + e.message)); }
  const oz = r.ozet || {};
  const ust = el("div", "dt-ozet");
  const parca = Object.entries(DURUM_TUR).filter(([t]) => oz[t])
    .map(([t, [ad, sinif]]) => el("span", "dt-rozet " + sinif, `${oz[t]} ${ad}`));
  if (!parca.length) ust.append(el("span", "bos-yazi", "Açık iş yok."));
  ust.append(...parca);
  kap.append(ust);

  kap.append(el("div", "dt-baslik", "İŞLER — şu an nerede"));
  for (const x of r.isler || []) {
    const [ad, sinif] = DURUM_TUR[x.tur] || [x.durum, ""];
    const d = el("div", "dt-is " + sinif);
    const bas = el("div", "dt-is-bas");
    bas.append(el("span", "dt-rozet " + sinif, ad), el("b", null, `#${x.no}`),
               el("span", "dt-is-ad", x.baslik));
    d.append(bas);
    d.append(el("div", "dt-nerede", x.nerede));
    const alt = [x.takim, x.sahip || "sahipsiz", x.model].filter(Boolean).join(" · ");
    const ek = [];
    if (x.son_adim) ek.push(`son adım: ${x.son_adim}` + (x.son_adim_yas_sn != null ? ` (${sureKisa(x.son_adim_yas_sn)} önce)` : ""));
    if (x.ret) ek.push(`${x.ret} kez geri döndü`);
    d.append(el("div", "dt-alt", alt + (ek.length ? " — " + ek.join(" · ") : "")));
    d.onclick = () => { try { gorevAc(x.no); } catch (_) {} };
    kap.append(d);
  }

  kap.append(el("div", "dt-baslik", "AJANLAR — kim ne yapıyor"));
  for (const a of r.ajanlar || []) {
    const sinif = { sen: "dt-sen", durdu: "dt-durdu", calisiyor: "dt-calisiyor",
                    inceleme: "dt-inceleme" }[a.hal] || "dt-bos";
    const d = el("div", "dt-ajan " + sinif);
    d.append(el("b", null, a.ad), el("span", "dt-alt", ` ${a.meslek}${a.lider ? " (lider)" : ""} · ${a.model}`));
    d.append(el("div", "dt-nerede", a.ne));
    if ((a.sirada || []).length) d.append(el("div", "dt-alt", "sırada: " + a.sirada.join(" · ")));
    kap.append(d);
  }

  await cizDeger(kap);
  if ((r.sira || []).length) {
    kap.append(el("div", "dt-baslik", "LİDERE GİDEN SIRA — henüz başlamadı"));
    for (const k of r.sira)
      kap.append(el("div", "dt-ajan dt-sirada",
        `${k.lider}: ${k.metin}` + (k.yas_sn != null ? ` (${sureKisa(k.yas_sn)} önce)` : "")));
  }
}

/* DEGER (08.10, B5): bu hafta ne uretildi, neye mal oldu -- olculmus kayittan. */
async function cizDeger(kap) {
  let v;
  try { v = await al("/api/deger?gun=7"); } catch (_) { return; }
  kap.append(el("div", "dt-baslik", "BU HAFTA — son 7 gün"));
  const k = el("div", "dt-ajan");
  const yuzde = v.ilk_seferde_oran != null ? ` (%${Math.round(v.ilk_seferde_oran * 100)})` : "";
  k.append(el("div", "dt-nerede",
    `${v.biten} iş bitti · ilk seferde geçen ${v.ilk_seferde}${yuzde} · geri dönen ${v.geri_donen} · iptal ${v.iptal}`));
  const ek = [];
  if (v.sure_dk_orta != null) ek.push(`bir iş ortalama ${v.sure_dk_orta < 60 ? v.sure_dk_orta + " dk" : (v.sure_dk_orta / 60).toFixed(1) + " sa"}`);
  if (v.puan_ort != null) ek.push(`teslim puanı ${String(v.puan_ort).replace(".", ",")}/5 (${v.puanli} iş)`);
  ek.push(`senden istenen: ${v.insana.soru} soru, ${v.insana.onay} onay`);
  k.append(el("div", "dt-alt", ek.join(" · ")));
  // Gunluk biten is: kucuk cubuklar (olculen sayi; 0 da yazilir).
  const enCok = Math.max(1, ...v.gunluk.map((g) => g.biten));
  const cub = el("div", "dg-cubuklar");
  for (const g of v.gunluk) {
    const c = el("div", "dg-cubuk");
    const i = el("i");
    i.style.height = `${Math.round((g.biten / enCok) * 28) + 2}px`;
    c.title = `${g.tarih}: ${g.biten} iş bitti`;
    c.append(i, el("span", null, g.gun));
    cub.append(c);
  }
  k.append(cub);
  kap.append(k);
  for (const h of v.harcama || []) {
    const r = hesapKaydi(h.motor, h.hesap);
    const pen = (v.pencereler || []).find((p) => p.motor === h.motor && (p.hesap || "") === (h.hesap || ""));
    const kota = pen ? Object.entries(pen.pencereler).filter(([, x]) => x != null)
      .map(([ad, x]) => `${({ "5s": "5 saat", "7g": "hafta", "7g_kapi": "Fable haftası" })[ad] || ad} %${Math.round(x * 100)}`).join(" · ") : "";
    const d = el("div", "dt-ajan");
    d.append(el("b", null, (r ? hesapEtiketi(r) : h.hesap || h.motor)),
             el("span", "dt-alt", ` ${h.motor}`));
    d.append(el("div", "dt-alt",
      `${h.tur} tur · ${jetonYaz(h.jeton)} jeton · ${h.sure_dk} dk çalıştı` + (kota ? ` — şu an ${kota}` : "")));
    kap.append(d);
  }
}

/* DENETIM (F3 / E27): "kim, neyi, hangi yetkiyle yapti". Sunucu yeni kayit
   tutmaz; olay + onay tablolarini tek listeye toplar. Burada yalniz suzgec
   ve okunur cizim var -- karar yok. */
const DENETIM_SINIF = { "": "hepsi", yetki: "yetki", kapi: "kapı", geri: "geri alma · yedek" };
async function cizDenetim(kap) {
  const secili = D.denetimSinif || "";
  let r;
  try { r = await al("/api/denetim?azami=200" + (secili ? "&sinif=" + secili : "")); }
  catch (e) { return kap.append(el("div", "form-ipucu uyari", "denetim okunamadı: " + e.message)); }
  const oz = r.ozet || {};
  const ust = el("div", "dn-ust");
  for (const [s, ad] of Object.entries(DENETIM_SINIF)) {
    const sayi = s ? (oz[s] || 0) : ((oz.yetki || 0) + (oz.kapi || 0) + (oz.geri || 0));
    const b = el("button", "dn-suz" + (s === secili ? " secili" : ""), `${ad} ${sayi}`);
    b.onclick = () => { D.denetimSinif = s; kap.textContent = ""; cizDenetim(kap); };
    ust.append(b);
  }
  kap.append(ust);
  kap.append(el("div", "hp-not",
    "Ofisin kendi kaydı: yetki açılışları (klasör, tarayıcı, bağlayıcı, terminal), " +
    "kapının kararları (sorulan, reddedilen, kullanılan onay, talimat şüphesi) ve " +
    "geri almalar. Yeni bir defter değil; olay ve onay kayıtlarının tek listesi."));
  const liste = el("div", "dn-liste");
  if (!(r.satirlar || []).length) liste.append(el("div", "bos-yazi", "bu süzgeçte kayıt yok"));
  for (const x of r.satirlar || []) {
    const s = el("div", "dn-satir " + x.sinif);
    const zaman = (x.zaman || "").replace("T", " ").slice(5, 16);
    s.append(el("span", "dn-zaman", zaman), el("span", "dn-kim", x.kim),
             el("span", "dn-ne", x.ne + (x.gorev_no ? ` · #${x.gorev_no}` : "")));
    if (x.yetki) s.append(el("span", "dn-yetki", x.yetki));
    const a = el("div", "dn-ayrinti", x.ayrinti || "");
    a.title = x.ayrinti || "";
    s.append(a);
    liste.append(s);
  }
  kap.append(liste);
}

/* YETENEK. Tarama CLI surumlerini alt surecle olcer (~0,7 sn, olculdu):
   her canli olayda kosturulamaz. Pano acilinca bir kez, sonra EN FAZLA
   dakikada bir; elle "yeniden olc" her zaman kosar. Bayat sonuc gosterilirse
   YASI yazilir -- bayat sayiyi canli sanmak, yanlis gosteren gosterge. */
const YTN_ARALIK_MS = 60000;
async function cizYetenek(kap, zorla, tam) {
  const simdi = Date.now();
  if (!zorla && D.yetenek && simdi - D.yetenek.an < YTN_ARALIK_MS)
    return yetenekYaz(kap, D.yetenek.veri, D.yetenek.an);
  if (!D.yetenek) kap.append(el("div", "bos-yazi", "ölçülüyor…"));
  try {
    const v = await al("/api/yetenek" + (tam ? "?tam=1" : ""));
    D.yetenek = { veri: v, an: Date.now() };
  } catch (e) {
    kap.textContent = "";
    return kap.append(el("div", "form-ipucu uyari", "yetenek ölçülemedi: " + e.message));
  }
  yetenekYaz(kap, D.yetenek.veri, D.yetenek.an);
}

function yetenekYaz(kap, v, an) {
  kap.textContent = "";
  const ust = el("div", "ytn-bas");
  const s = v.sayim || {};
  ust.append(el("span", null,
    `${s.hazir || 0} hazır · ${s.dar || 0} dar · ${s.yok || 0} yok · ${s.bilinmiyor || 0} bilinmiyor`),
    el("span", "sahip", `· ${Math.round((Date.now() - an) / 1000)} sn önce ölçüldü`));
  const yeniden = el("button", "dugme", "yeniden ölç");
  yeniden.onclick = () => cizYetenek(kap, true, false);
  const tam = el("button", "dugme", "bağlayıcılar dahil (~15 sn)");
  tam.title = "claude.ai bağlayıcılarını da ölçer (claude mcp list).";
  tam.onclick = () => { bildir("bağlayıcılar ölçülüyor…"); cizYetenek(kap, true, true); };
  ust.append(yeniden, tam);
  kap.append(ust);

  // PARA KILIDI: GOSTERILIR, panelden ACILMAZ. Kullanicinin kisiti
  // "sadece free"; tek tiklik bir dugme baska bir botun bakiyesini
  // yanlis tiklamaya acardi.
  const pk = el("div", "ytn-para");
  pk.append(el("b", null, v.para_kilidi ? "PARA KİLİDİ: KAPALI" : "PARA KİLİDİ: AÇIK"),
    document.createTextNode(v.para_kilidi
      ? " — ofis yalnız ücretsiz üretici kullanır; ücretli görsel/video koşmaz."
      : " — ücretli üreticiler koşabilir."),
    el("div", "form-ipucu",
      "Değiştirmek bir PARA kararıdır ve panelden yapılmaz: " +
      "`python -m ofis.kabuk gorsel para ac|kapat`"));
  kap.append(pk);

  const hesapDurum = Object.fromEntries((v.hesaplar || []).map(h => [h.ad, h]));
  for (const g of v.gruplar) {
    const gr = el("div", "ytn-grup");
    const b = el("div", "ytn-bas");
    // Sunucu ASCII ad verir ("Gorsel ureticileri"); buyuk harfe cevrilince
    // Turkcede "URETİCİLERİ" gibi bozuk okunur. Gorunen ad burada.
    const GRUP_AD = { "Komut satiri araclari": "Komut satırı araçları",
      "Anahtar kasasi": "Anahtar kasası", "Gorsel ureticileri": "Görsel üreticileri",
      "Video ureticileri": "Video üreticileri",
      "claude.ai baglayicilari": "claude.ai bağlayıcıları" };
    b.append(el("span", null, GRUP_AD[g.ad] || g.ad), el("span", "sahip",
      g.sahiplik === "ofis" ? "· ofis yönetir" : "· dışarıda — yalnız ölçülür"));
    gr.append(b);
    for (const r of g.satirlar) {
      const sat = el("div", "ytn-satir");
      sat.append(el("span", "ytn-nokta " + r.durum), el("span", null, r.ad),
                 el("span", "ytn-not", r.not || ""));
      const eylemYeri = el("span");
      if (g.ad === "Anahtar kasasi" && !r.ad.startsWith("(")) {
        const sil = el("button", "dugme olumsuz", "sil");
        sil.title = "Anahtarı kasadan siler. GERİ ALINMAZ.";
        sil.onclick = async () => {
          if (!confirm(`${r.ad} kasadan silinsin mi? Geri alınamaz; bu anahtarı kullanan üretici/motor çalışmaz hale gelir.`)) return;
          await eylem(`/api/anahtar/${encodeURIComponent(r.ad)}/sil`, {}, `${r.ad} silindi`);
          cizYetenek(kap, true, false);
        };
        eylemYeri.append(sil);
      }
      const h = g.ad === "Hesaplar" ? hesapDurum[r.ad] : null;
      if (h) {
        const t = el("button", "dugme" + (h.aktif ? " olumsuz" : " olumlu"),
                     h.aktif ? "zincirden çıkar" : "zincire al");
        t.title = h.aktif
          ? "Hesap nöbet zincirinden çıkar; kayıt ve geçmiş DURUR."
          : "Hesabı nöbet zincirine geri alır.";
        t.onclick = async () => {
          await eylem(`/api/hesap/${encodeURIComponent(h.ad)}/aktif`, { aktif: !h.aktif },
                      (x) => `${x.ad}: ${x.aktif ? "zincirde" : "zincir dışı"}`);
          cizYetenek(kap, true, false);
        };
        eylemYeri.append(t);
      }
      sat.append(eylemYeri);
      if (r.care) sat.append(el("div", "ytn-care", "→ " + r.care));
      gr.append(sat);
    }
    if (g.ad === "Anahtar kasasi") {
      // DEGER BIR KEZ GIDER, bir daha GELMEZ: alan parola turunde, cevapta
      // yalniz parmak izi var.
      const f = el("div", "ytn-form");
      const ad = el("input"); ad.placeholder = "ANAHTAR_ADI (ör. GEMINI_API_KEY)";
      const dg = el("input"); dg.type = "password"; dg.placeholder = "değer (bir daha gösterilmez)";
      dg.autocomplete = "new-password";
      const ek = el("button", "dugme olumlu", "ekle");
      ek.onclick = async () => {
        if (!ad.value.trim() || !dg.value.trim()) return bildir("ad ve değer zorunlu", "kotu");
        const r = await eylem("/api/anahtar", { ad: ad.value, deger: dg.value },
                              (x) => `${x.ad} kasaya yazıldı · parmak izi ${x.parmak_izi}`);
        dg.value = "";
        if (r) cizYetenek(kap, true, false);
      };
      f.append(ad, dg, ek);
      gr.append(f);
    }
    kap.append(gr);
  }
}

/* LIDER SOHBETI. Defterden okunur (`/api/sohbet`); cevap gelmemisse
   "dusunuyor" yazar ve kosu durumunu soyler -- bos bir cevap uydurmaz. */
/* TAKIM SOHBETI (29.09.2026). Rakipteki "Cekirdek takim sohbeti"nin
   karsiligi: lidere yazilanlar, `@ajan` sorulari/notlari/isleri, cevaplar,
   ajanlarin birbirine sorulari, raporlar ve hukumler TEK akista. Akis
   sunucuda defterden TURETILIR; burada yalniz cizim var, karar yok.
   - Metin KESILMEZ; uzun olan katlanir ve "Tamamini oku" acar (ilk surum
     600 harfte kesiyordu ve liderin cevabi yarida kaliyordu).
   - Is etiketi isin SU ANKI durumudur (defterden), mesajin yazildigi an
     degil.
   - "Terminalde goster" ajanin kendi akisini ofis panosunda acar. */
const TAKIM_KATLA_HARF = 700;
const TAKIM_TUR = { sohbet: "", soru: "soru", not: "not", cevap: "", rapor: "rapor",
                    is: "iş açıldı", kapandi: "kapandı", ret: "geri gönderildi",
                    onay: "onay istiyor", bildirim: "takıma yazdı",
                    sirada: "sırada", ozet: "dönüş raporu", iletilemedi: "İLETİLEMEDİ",
                    guncelleme: "güncelleme: iş sonradan bitti" };
const GOREV_DURUM = { bekliyor: "bekliyor", hazir: "sırada", calisiyor: "çalışıyor",
                      inceleme: "incelemede", bitti: "bitti", iptal: "iptal" };

/* `**kalin**` metni DOM dugumuyle kalinlastirir (innerHTML YOK: ajan
   metni sayfaya kod olarak giremez). Yalniz kalin; baska isaretleme yok. */
function kalinYaz(kap, metin) {
  const parca = String(metin || "").split("**");
  parca.forEach((p, i) => {
    if (!p) return;
    kap.append(i % 2 && i < parca.length - 1 ? el("b", null, p) : document.createTextNode(p));
  });
}

// Ajanin AYARI ile son turda OLCULEN ayni model mi? Ayar takma ad olabilir
// ("opus"), olcum tam kimlik ("claude-opus-5-5"): takma ad kimligin parcasiysa
// ayni sayilir. Motor farkliysa (zincir devri) farklidir.
function modelAyni(motorA, modelA, motorO, modelO) {
  if (motorA && motorO && motorA !== motorO) return false;
  const a = String(modelA || "").replace(/^claude-/, "").toLowerCase();
  const o = String(modelO || "").replace(/^claude-/, "").toLowerCase();
  if (!a || !o) return true;
  return o === a || o.startsWith(a + "-") || o.includes(a);
}

function sureYazi(sn) {
  if (sn < 60) return sn + " sn sürdü";
  const dk = Math.round(sn / 60);
  return dk < 60 ? dk + " dk sürdü" : Math.floor(dk / 60) + " sa " + (dk % 60) + " dk sürdü";
}

function takimBalonu(x, D_ajanlar) {
  const insan = x.kimden === "insan";
  const ajanMi = !insan && x.kimden !== "ofis";
  const b = el("div", "sohbet-balon " + (insan ? "insan" : "lider") + " tur-" + x.tur);
  const ust = el("div", "sohbet-ust");
  const kim = insan ? "sen" : x.kimden;
  ust.append(el("b", "sohbet-kim", kim));
  if (x.meslek && !insan) ust.append(el("span", "sohbet-meslek", " · " + x.meslek));
  if (x.kime) ust.append(el("span", null, " → " + (x.kime === "insan" ? "sen" : x.kime)));
  const tur = TAKIM_TUR[x.tur];
  if (tur) ust.append(el("span", "sohbet-tur", " · " + tur));
  ust.append(el("span", "sohbet-saat", " · " + saat(x.an)));
  b.append(ust);
  const yazi = el("span", "sohbet-yazi");
  kalinYaz(yazi, x.metin);
  b.append(yazi);
  // EKLER: gorsel kucuk resim (tiklayinca tam boy), digerleri baglanti.
  if ((x.ekler || []).length) {
    const kap = el("div", "sohbet-ekler");
    for (const y of x.ekler) {
      const ad = y.split("/").pop();
      const url = "/api/ek/" + encodeURIComponent(ad);
      const a = el("a", "sohbet-ek");
      a.href = url; a.target = "_blank"; a.rel = "noopener";
      if (/\.(png|jpe?g|gif|webp|bmp)$/i.test(ad)) {
        const im = el("img"); im.src = url; im.alt = ad; im.loading = "lazy";
        a.append(im);
      } else if (/\.(mp4|webm|mov|m4v)$/i.test(ad) || /\.(mp3|wav|ogg|m4a)$/i.test(ad)) {
        // VIDEO / SES balonda oynar; baglanti tam boy acar.
        const vid = /\.(mp4|webm|mov|m4v)$/i.test(ad);
        const m = el(vid ? "video" : "audio", "sohbet-ek-oynat");
        m.src = url; m.controls = true; m.preload = "metadata";
        m.title = y;
        kap.append(m);
        continue;
      } else a.textContent = "📄 " + ad.replace(/^\d{8}-\d{6}-/, "");
      a.title = y;
      kap.append(a);
    }
    b.append(kap);
  }
  const altlar = [];
  if (x.gorev_no) {
    const d = GOREV_DURUM[x.gorev_durum] || x.gorev_durum || "";
    const c = el("button", "sohbet-cip durum-" + (x.gorev_durum || "yok"),
                 `#${x.gorev_no}${d ? " " + d : ""}`);
    c.title = "işin ayrıntısı";
    c.onclick = () => gorevAc(x.gorev_no);
    altlar.push(c);
  }
  // NOTUN UC DURUMU: ulasti / is kapandi, ulasmayacak / incelemede.
  if (x.tur === "not") {
    const [s, t] = x.ulasti ? ["durum-bitti", "ulaştı"]
      : x.ulasmadi ? ["durum-kotu", "ulaşmadı — iş kapandı"]
      : x.incelemede ? ["durum-inceleme", "iş incelemede — lider görür"]
      : ["", "iletilecek"];
    const c = el("span", "sohbet-cip " + s, t);
    if (x.ulasmadi) c.title = "Ajan bu notu görmeden iş kapandı. Yeni bir iş için lidere yaz.";
    altlar.push(c);
  }
  // ILETILEMEDI (02.10.2026): dusen istek -- sebep, Tekrar dene, Kapat.
  if (x.tur === "iletilemedi") {
    if (x.sebep) b.append(el("div", "sohbet-sebep", "Sebep: " + x.sebep));
    const islem = async (yol, iyi) => {
      try { await yolla("/api/kuyruk/" + encodeURIComponent(x.id) + yol, {});
            bildir(iyi, "iyi"); }
      catch (e) { bildir(String(e.message || e).slice(0, 160), "uyari"); }
      yenile();
    };
    const td = el("button", "sohbet-cip", "Tekrar dene");
    td.title = "aynı mesajı yeniden sıraya koy";
    td.onclick = () => islem("/tekrar", "yeniden sıraya kondu");
    const kp = el("button", "sohbet-cip", "Kapat");
    kp.title = "bu uyarıyı kaldır";
    kp.onclick = () => islem("/kapat", "kaldırıldı");
    altlar.push(td, kp);
  }
  // SIRADAKI IS (01.10.2026): kac kisi onde ve iptal. Kosan is iptal
  // edilmez (Durdur) -- sunucu da reddeder; dugme yalniz bekleyende.
  // TESLIM SATIRI (02.10.2026; rakipte "Isimi bitirdim -- 6 dakika surdu ·
  // kontrol edildi · Duzeltme iste · Kabul et"). Liderin istege cevabinda.
  if (x.tur === "cevap" && x.istek && !(x.metin || "").startsWith("İLETİLEMEDİ")) {
    if (x.sure_sn != null) altlar.push(el("span", "sohbet-cip", "⏱ " + sureYazi(x.sure_sn)));
    const isler = x.isler || [];
    if (isler.length && isler.every((g) => g.durum === "bitti"))
      altlar.push(el("span", "sohbet-cip durum-bitti",
                     isler.length === 1 ? "kanıtla kontrol edildi" : `${isler.length} iş kanıtla kontrol edildi`));
    // Kabul/Duzeltme yalniz IS yapilmis teslimde (duz soru-cevapta anlamsiz).
    if (!isler.length) {}
    else if (x.kabul) altlar.push(el("span", "sohbet-cip durum-bitti", "✓ kabul ettin"));
    else {
      const kb = el("button", "sohbet-cip", "Kabul et");
      kb.title = "teslimi kabul et (karar günlüğüne yazılır)";
      kb.onclick = async () => {
        try { await yolla("/api/mesaj/" + encodeURIComponent(x.id) + "/kabul", {});
              bildir("kabul edildi", "iyi"); }
        catch (e) { bildir(String(e.message || e).slice(0, 160), "uyari"); }
        yenile();
      };
      altlar.push(kb);
    }
    const dz = el("button", "sohbet-cip", "Düzeltme iste");
    dz.title = "lidere bu teslim için düzeltme yaz";
    dz.onclick = () => {
      const g = $("#sohbet-girdi");
      if (!g) return;
      const ist = (x.isler || []).map((i) => "#" + i.no).join(" ");
      g.value = `Düzeltme${ist ? " (" + ist + ")" : ""}: `;
      g.focus(); g.setSelectionRange(g.value.length, g.value.length);
    };
    if (isler.length) altlar.push(dz);
  }
  if (x.tur === "sirada") {
    altlar.push(el("span", "sohbet-cip", `${x.sira_no}. sırada`));
    const ip = el("button", "sohbet-cip", "İptal");
    ip.title = "bu işi sıradan çıkar";
    ip.onclick = async () => {
      try { await yolla("/api/kuyruk/" + encodeURIComponent(x.id) + "/iptal", {});
            bildir("iş sıradan çıkarıldı", "iyi"); }
      catch (e) { bildir(String(e.message || e).slice(0, 160), "uyari"); }
      yenile();
    };
    altlar.push(ip);
  }
  if ((x.metin || "").length > TAKIM_KATLA_HARF) {
    b.classList.add("katli");
    const t = el("button", "sohbet-cip", "Tamamını oku");
    t.onclick = () => { const k = b.classList.toggle("katli");
                        t.textContent = k ? "Tamamını oku" : "Kısalt"; };
    altlar.push(t);
  }
  if (ajanMi && D_ajanlar.includes(x.kimden)) {
    const t = el("button", "sohbet-cip", "Terminalde göster");
    t.onclick = () => { D.secilenAjan = x.kimden; if (D.yerlesim) panoSec("ofis"); cizOfis(); };
    altlar.push(t);
  }
  if (altlar.length) { const a = el("div", "sohbet-altlar"); a.append(...altlar); b.append(a); }
  return b;
}

/* ISTEGIN ADIMLARI -- Claude Code'daki katli islem satirlari gibi.
   Basta tek satir: is surerken "bilge calisiyor · 0:40 -- <son durum>",
   bitince "▸ 12 islem · 2 mesaj". Tiklayinca ajan mesajlari acilir. */
D.acikAdim = D.acikAdim || new Set();
// Acik gorev metinleri yeniden cizimde KAPANMAZ (sohbet birkac sn'de bir
// cizilir; olculdu: kutu 4 sn sonra kayboluyordu). Metin bir kez cekilir.
D.acikMetin = D.acikMetin || new Set();
D.gorevMetni = D.gorevMetni || {};
function adimBlogu(x, cocuklar, adlar, kosuyor) {
  const d = x.istek_durum || {};
  const kap = el("div", "sohbet-adimlar" + (x.bekliyor ? " suruyor" : ""));
  const acik = D.acikAdim.has(x.id);
  const bas = el("button", "sohbet-adim-bas");
  const adimlar = d.adimlar || [];
  const verilen = d.isler || [];
  const acilir = cocuklar.length || adimlar.length || verilen.length;
  const ok = el("span", "sohbet-adim-ok", acilir ? (acik ? "▾" : "▸") : "·");
  bas.append(ok);
  if (x.bekliyor) {
    const kim = d.aktif ? d.aktif.sahip : (x.kime || "lider");
    const ne = d.aktif ? (d.aktif.durum === "inceleme" ? "inceleniyor" : "çalışıyor")
                       : (kosuyor ? "düşünüyor" : "sırada");
    bas.append(el("b", null, `${kim} ${ne}`));
    const sure = el("span", "sohbet-sure");
    sure.dataset.bas = (d.aktif && d.aktif.basladi) || x.an || "";
    bas.append(document.createTextNode(" · "), sure);
    if (d.son) bas.append(el("span", "sohbet-adim-son", " — " + d.son));
  } else {
    const parca = [];
    if (d.adim) parca.push(`${d.adim} işlem`);
    if (cocuklar.length) parca.push(`${cocuklar.length} mesaj`);
    if ((d.isler || []).length) parca.push(d.isler.map((i) => i.sahip).filter(Boolean)
      .filter((v, i, a) => a.indexOf(v) === i).join(", "));
    bas.append(el("span", null, parca.join(" · ") || "ayrıntı yok"));
  }
  kap.append(bas);
  const govde = el("div", "sohbet-adim-govde");
  govde.hidden = !acik;
  // VERILEN ISLER (02.10.2026; rakipte "Kamil Amca'ya giden gorev metni
  // [Kopyala]"): liderin ajana verdigi isin TAM metni, istenince.
  for (const g of verilen) {
    const s = el("div", "sohbet-verilen");
    s.append(el("span", "sohbet-adim-ajan", g.sahip || "—"),
             el("span", null, ` #${g.no} ${g.baslik || ""} · ${GOREV_DURUM[g.durum] || g.durum}`));
    const gm = el("button", "sohbet-cip", "Görev metni");
    gm.title = "liderin bu ajana verdiği işin tam metni";
    const goster = (metin) => {
      const kutu = el("div", "sohbet-gorev-metni");
      const kp = el("button", "sohbet-cip", "Kopyala");
      kp.onclick = async () => {
        try { await navigator.clipboard.writeText(metin); bildir("görev metni kopyalandı", "iyi"); }
        catch (_) { bildir("kopyalanamadı (tarayıcı izin vermedi)", "uyari"); }
      };
      const pre = el("pre"); pre.textContent = metin;
      kutu.append(kp, pre);
      s.append(kutu);
    };
    gm.onclick = async (e) => {
      e.stopPropagation();
      const var_ = s.querySelector(".sohbet-gorev-metni");
      if (var_) { D.acikMetin.delete(g.no); return var_.remove(); }
      try {
        if (!D.gorevMetni[g.no]) D.gorevMetni[g.no] = gorevMetni(await al("/api/gorev/" + g.no));
        D.acikMetin.add(g.no);
        goster(D.gorevMetni[g.no]);
      } catch (er) { bildir("görev okunamadı: " + er.message, "uyari"); }
    };
    s.append(gm);
    if (D.acikMetin.has(g.no) && D.gorevMetni[g.no]) goster(D.gorevMetni[g.no]);
    govde.append(s);
  }
  // Islem satirlari (Claude Code gibi): kim · ne · kisa ozet.
  if (adimlar.length) {
    const l = el("div", "sohbet-adim-liste");
    for (const a of adimlar) {
      const s = el("div", "sohbet-adim-satir");
      s.append(el("span", "sohbet-adim-ajan", a.ajan), el("b", null, " " + a.ad),
               el("span", "sohbet-adim-ozet", a.ozet ? " " + a.ozet : ""));
      l.append(s);
    }
    govde.append(l);
  }
  for (const c of cocuklar) govde.append(takimBalonu(c, adlar));
  kap.append(govde);
  bas.onclick = () => {
    if (!acilir) return;
    const ac = govde.hidden;
    govde.hidden = !ac; ok.textContent = ac ? "▾" : "▸";
    if (ac) D.acikAdim.add(x.id); else D.acikAdim.delete(x.id);
  };
  sureleriYaz();
  return kap;
}

// Ajana giden isin metni: ajanin brifingindeki isin tanimiyla AYNI alanlar.
function gorevMetni(g) {
  const p = [`#${g.no} ${g.baslik}`];
  if (g.sahip) p.push("Sahip: " + g.sahip);
  if (g.ana_hedef) p.push("Ana hedef: " + g.ana_hedef);
  if (g.neden) p.push("Neden: " + g.neden);
  if (g.govde) p.push("", g.govde);
  if (g.kabul_olcutu) p.push("", "Kabul ölçütü: " + g.kabul_olcutu);
  if ((g.yazma_alani || []).length) p.push("Yazma alanı: " + g.yazma_alani.join(", "));
  return p.join("\n");
}

function sureleriYaz() {
  for (const s of document.querySelectorAll(".sohbet-sure[data-bas]")) {
    const t = Date.parse(s.dataset.bas);
    if (!t) { s.textContent = ""; continue; }
    const sn = Math.max(0, Math.round((Date.now() - t) / 1000));
    s.textContent = sn < 60 ? `${sn} sn` : `${Math.floor(sn / 60)}:${String(sn % 60).padStart(2, "0")}`;
  }
}
setInterval(sureleriYaz, 1000);
// CANLI DURUM: bir istek surerken sohbet 3 sn'de bir tazelenir (son durum
// notu, calisan ajan). Cevap akarken akis izleyicisi zaten ciziyor.
/* VIDEO OYNARKEN PANO YENIDEN CIZILMEZ (08.10.2026, OLCULDU): sohbet her
   canli olayda bastan ciziliyordu; oynatilan video 1,5 sn icinde DOM'dan
   siliniyordu (patron: "videoyu acamiyorum, otomatik kapaniyor"). Oynayan,
   tam ekrandaki ya da son 30 sn icinde dokunulan medya varsa cizim bir
   sonraki tazelemeye kalir -- veri kaybolmaz, izlenen video kaybolurdu. */
/* SOHBET TITREMEZ, YUKARI KACMAZ (08.10.2026, patron: "panel surekli
   yenileniyor gibi, takim sohbeti yukari gidiyor"). Olculen sebep: her canli
   olayda pano SILINIP bastan ciziliyordu; silme aninda kaydirma 0'a dusuyor,
   tarayicinin kaydirma olayi da konumu "en ust" diye kaydediyordu. Artik:
   ekran disinda cizilir, DEGISMEDIYSE dokunulmaz, degistiyse tek hamlede
   yer degistirir ve kaydirma korunur. */
function sohbetKaydirmasi(kap) {
  kap.onscroll = () => {
    kap.dataset.altta = (kap.scrollHeight - kap.scrollTop - kap.clientHeight < 40) ? "1" : "0";
    kap.dataset.kaydir = String(kap.scrollTop);
  };
}
async function sohbetiTazele(kap) {
  const yeni = el("div");
  await cizSohbet(yeni);
  // Karsilastirma DOM'un metin dokumuyle (yazma degil OKUMA; XMLSerializer:
  // HTML yazan ozellik bu bolgede hic gecmesin -- guvenlik bekcisi).
  const html = new XMLSerializer().serializeToString(yeni);
  if (kap._sonHtml === html && kap.childNodes.length) return false;
  const altta = kap.dataset.altta !== "0";
  const kaydir = kap.scrollTop;
  kap._sonHtml = html;
  kap.replaceChildren(...yeni.childNodes);
  kap.scrollTop = altta ? kap.scrollHeight : kaydir;
  kap.dataset.kaydir = String(kap.scrollTop);
  sohbetKaydirmasi(kap);
  sureleriYaz();
  return true;
}

let _medyaDokunma = 0;
for (const olay of ["play", "pause", "seeking", "volumechange"])
  document.addEventListener(olay, (e) => {
    if (e.target && /^(VIDEO|AUDIO)$/.test(e.target.tagName)) _medyaDokunma = Date.now();
  }, true);
function medyaKullaniliyor(kap) {
  const fs = document.fullscreenElement;
  if (fs && kap.contains(fs)) return true;
  for (const m of kap.querySelectorAll("video, audio"))
    if (!m.paused && !m.ended) return true;
  return !!kap.querySelector("video, audio") && Date.now() - _medyaDokunma < 30000;
}

setInterval(async () => {
  const kap = $("#pano-sohbet");
  if (!kap || document.hidden || !panoAcik("sohbet") || _sohbetAkisZaman) return;
  if (!kap.querySelector(".kd-calisiyor, .kd-dusunuyor, .kd-karar, .kd-sirada")) return;
  if (medyaKullaniliyor(kap)) return;
  await sohbetiTazele(kap);
}, 3000);

// SUREN ISLER (02.10.2026; rakipte sohbetin altinda is basina "Durdur ·
// Duraklat · Iptal et" var). Ust cubuktaki Durdur BUTUN ofisi durdurur;
// burada tek is beklemeye alinir, oteki isler ve takimlar surer.
function surenIsler() {
  const satirlar = [];
  for (const d of ["calisiyor", "hazir", "bekliyor"])
    for (const g of (D.tahta && D.tahta[d]) || []) satirlar.push([d, g]);
  if (!satirlar.length) return null;
  const s = el("div", "suren-isler");
  s.append(el("b", "suren-baslik", "Süren işler"));
  for (const [d, g] of satirlar) {
    const r = el("div", "suren-is" + (g.duraklatildi ? " duraklatildi" : ""));
    // GERCEK DURUM (08.10, B2): tahtanin sutunu degil durum tablosunun
    // hukmu -- "calisiyor" sutunundaki is senin cevabini bekliyor olabilir.
    const gd = (D.durumIs || {})[g.no];
    const cip = el("span", "sohbet-cip " + (g.duraklatildi ? "durum-inceleme"
                : gd ? (DURUM_TUR[gd.tur] || ["", ""])[1] : "durum-" + d),
                g.duraklatildi ? "duraklatıldı"
                : gd ? (DURUM_TUR[gd.tur] || [GOREV_DURUM[d] || d])[0] : (GOREV_DURUM[d] || d));
    if (gd) cip.title = gd.nerede;
    r.append(el("span", "suren-sahip", g.sahip || "—"),
             el("span", "suren-ad", ` #${g.no} ${g.baslik}`), cip);
    const dk = el("button", "sohbet-cip", g.duraklatildi ? "Sürdür" : "Duraklat");
    dk.title = g.duraklatildi ? "aynı oturumdan devam eder"
      : "yalnız bu işi beklemeye alır (koşan turu keser); öteki işler sürer";
    dk.onclick = async () => {
      dk.disabled = true;
      try {
        await yolla(`/api/gorev/${g.no}/` + (g.duraklatildi ? "surdur" : "duraklat"), {});
        bildir(g.duraklatildi ? `#${g.no} sürüyor` : `#${g.no} duraklatıldı`, "iyi");
      } catch (e) { bildir(String(e.message || e).slice(0, 160), "uyari"); }
      yenile();
    };
    const ip = el("button", "sohbet-cip", "İptal et");
    ip.title = "işin ayrıntısını açar; iptal sebebi orada yazılır";
    ip.onclick = () => gorevAc(g.no);
    r.append(dk, ip);
    s.append(r);
  }
  return s;
}

/* ESKI sohbet cizimi (09.10.2026'ya dek): kartlara gecildi, bkz. cizSohbet. */
async function cizSohbetEski(kap) {
  let r;
  try { r = await al("/api/takim" + (D.kanat ? "?kanat=" + D.kanat : "")); }
  catch (e) { return kap.append(el("div", "form-ipucu uyari", "takım sohbeti okunamadı: " + e.message)); }
  const ogeler = r.ogeler || [];
  const adlar = ((D.ofis && D.ofis.ajanlar) || []).map((a) => a.ad);
  const bas = el("div", "takim-bas");
  const calisan = ((D.ofis && D.ofis.ajanlar) || []).filter((a) => a.oda === "masa").length;
  bas.append(el("b", null, "Takım sohbeti"),
             el("span", null, calisan ? ` · ${calisan} ajan çalışıyor` : " · kimse çalışmıyor"),
             el("span", "takim-ipucu", "@ad → ajana sor ya da not · @ad iş: … → işi ona ver · adres yoksa lidere"));
  kap.append(bas);
  if (!ogeler.length)
    return kap.append(el("div", "bos-yazi",
      "Takım sohbeti boş. Alttaki satıra yaz: adres yoksa lidere gider; " +
      "@ad ile bir ajana sorarsın (elinde iş varsa not olur), " +
      "@ad iş: … ile işi o ajana verirsin."));
  const kosuyor = (r.kosu && r.kosu.calisiyor) || (r.danisma && r.danisma.calisiyor);
  if (!kosuyor) gecicIpuclariniGeriAl();
  // TEK KONUSMA (02.10.2026, patron: "seninle konusur gibi"): bir istegin
  // ajan mesajlari ve adimlari o istegin ALTINDA katli toplanir; is
  // surerken tek satir canli durum. Senden bir sey bekleyen (onay, sana
  // soru) disarida kalir -- aranmasin.
  const istekler = new Set(ogeler.filter((x) => x.tur === "sohbet").map((x) => x.id));
  const cocuk = {};
  const ustler = [];
  for (const x of ogeler) {
    // ONAY KARTI disarida yalniz isi SURERKEN (08.10.2026, patron: "keremin
    // selinin gonderdikleri ne alaka"): kapanmis isin eski onaylari sohbetin
    // en altinda yigiliyordu; artik istegin katli adimlarinin icinde.
    const onayAcik = x.tur === "onay" && !["bitti", "iptal"].includes(x.gorev_durum || "");
    const disarida = x.tur === "sohbet" || x.tur === "cevap" || onayAcik
      || (x.bekliyor && x.kime === "insan");
    if (x.istek && istekler.has(x.istek) && !disarida) (cocuk[x.istek] = cocuk[x.istek] || []).push(x);
    else ustler.push(x);
  }
  for (const x of ustler) {
    kap.append(takimBalonu(x, adlar));
    // SIRA Claude Code gibi: once liderin (akan) cumlesi, ALTINDA adimlar.
    if (x.tur === "sohbet" && x.bekliyor && x.akis) {
      const l = el("div", "sohbet-balon lider akiyor");
      l.dataset.mesaj = x.id;
      const u = el("div", "sohbet-ust"); u.append(el("b", "sohbet-kim", x.kime));
      l.append(u);
      const y = el("span", "sohbet-yazi"); y.textContent = x.akis;
      l.append(y); kap.append(l);
    }
    if (x.tur === "sohbet" && (cocuk[x.id] || x.istek_durum || x.bekliyor))
      kap.append(adimBlogu(x, cocuk[x.id] || [], adlar, kosuyor));
    if (x.tur === "sohbet" && x.bekliyor) continue;   // yukarida cizildi
    // SANA SORULAN SORU (01.10.2026 canli): kime "insan" ise sira PATRONDA;
    // "cevap gelmedi (tur yarida kalmis olabilir)" yer tutucusu yanlisti --
    // ariza gibi gorunuyordu. Cevap yeri sagdaki "Senden bekleniyor"da.
    if (x.bekliyor && x.tur !== "not" && x.kime === "insan") {
      const l = el("div", "sohbet-balon lider bekliyor");
      l.append(el("span", "sohbet-yazi", "senin cevabını bekliyor — sağdaki “Senden bekleniyor” kutusundan cevapla"));
      kap.append(l);
      continue;
    }
    if (x.bekliyor && x.tur !== "not") {
      // Cevap henuz yok: yer tutucu. Liderin yazilmakta olan cevabi akar.
      const l = el("div", "sohbet-balon lider " + (x.akis ? "akiyor" : "bekliyor"));
      l.dataset.mesaj = x.id;
      const u = el("div", "sohbet-ust"); u.append(el("b", "sohbet-kim", x.kime));
      l.append(u);
      const y = el("span", "sohbet-yazi");
      y.textContent = x.akis || (kosuyor ? "düşünüyor…"
        : "cevap gelmedi (tur yarıda kalmış olabilir; günlükte 'hata' var mı bak).");
      l.append(y); kap.append(l);
    }
  }
  try {
    const dt = await al("/api/durum");
    D.durumIs = Object.fromEntries((dt.isler || []).map((x) => [x.no, x]));
  } catch (_) { D.durumIs = null; }       // olculemedi: tahtanin sutunu yazilir
  const _suren = surenIsler();
  if (_suren) kap.append(_suren);
  // KAYDIRMA KORUNUR: patron yukari kaydirmissa yeniden cizim onu
  // en alta firlatmaz (canli durum tazelemesi birkac saniyede bir cizer).
  if (kap.dataset.altta !== "0") kap.scrollTop = kap.scrollHeight;
  else kap.scrollTop = Number(kap.dataset.kaydir || 0);
  kap.onscroll = () => {
    kap.dataset.altta = (kap.scrollHeight - kap.scrollTop - kap.clientHeight < 40) ? "1" : "0";
    kap.dataset.kaydir = String(kap.scrollTop);
  };
  if (kosuyor) sohbetAkisIzle();
}

/* ─────────────── SOHBET KARTLARI (09.10.2026) ───────────────
   Patron: "verilen islerin yaniti karisik; ne is verdim, ne isi yapti hepsi
   birbirine girmis" -> secim A (tek akis, Claude Code / Codex gibi). HER ISTEK
   TEK KART: istek · tek durum satiri · (senden karar) · sonuc · dosyalar ·
   katli ayrinti. Ofisin ic notlari (dagitim, ret, kesinti, donus raporu)
   sohbete girmez; gunlukte ve kartin katli ayrintisinda durur. */
const SOHBET_KART_DURUM = {
  sirada: ["Sırada", "durum-bekliyor"], dusunuyor: ["Lider düşünüyor", "durum-calisiyor"],
  calisiyor: ["Çalışıyor", "durum-calisiyor"], karar: ["Senden karar bekliyor", "durum-bekleyen"],
  durdu: ["Durdu", "durum-inceleme"], bitti: ["Bitti", "durum-bitti"],
  iptal: ["İptal edildi", "durum-kotu"], iletilemedi: ["İletilemedi", "durum-kotu"],
  cevapsiz: ["Cevap gelmedi", "durum-kotu"],
};

function eklerKutusu(ekler) {
  const kap = el("div", "sohbet-ekler");
  for (const y of ekler || []) {
    const ad = y.split("/").pop();
    const url = "/api/ek/" + encodeURIComponent(ad);
    if (/\.(mp4|webm|mov|m4v|mp3|wav|ogg|m4a)$/i.test(ad)) {
      const vid = /\.(mp4|webm|mov|m4v)$/i.test(ad);
      const m = el(vid ? "video" : "audio", "sohbet-ek-oynat");
      m.src = url; m.controls = true; m.preload = "metadata"; m.title = y;
      kap.append(m); continue;
    }
    const a = el("a", "sohbet-ek");
    a.href = url; a.target = "_blank"; a.rel = "noopener"; a.title = y;
    if (/\.(png|jpe?g|gif|webp|bmp)$/i.test(ad)) {
      const im = el("img"); im.src = url; im.alt = ad; im.loading = "lazy"; a.append(im);
    } else a.textContent = "📄 " + ad.replace(/^\d{8}-\d{6}-/, "");
    kap.append(a);
  }
  return kap;
}

async function kartIslem(yol, govde, iyi) {
  try { await yolla(yol, govde || {}); bildir(iyi, "iyi"); }
  catch (e) { bildir(String(e.message || e).slice(0, 160), "uyari"); }
  yenile();
}

function kartCiz(k, adlar, bekleyen) {
  const kart = el("div", "kart kart-" + k.tip + " kd-" + (k.durum || ""));
  kart.dataset.kart = k.id;
  // 1) ISTEK (senin sozun)
  const ist = el("div", "kart-istek");
  const ust = el("div", "kart-ust");
  const kime = k.tip === "soru_sana" ? (k.kimden + " sana soruyor") : ("sen → " + (k.kime || "lider"));
  ust.append(el("b", null, kime), el("span", "sohbet-saat", " · " + saat(k.an)));
  ist.append(ust);
  const y = el("div", "kart-metin"); kalinYaz(y, k.metin); ist.append(y);
  if ((k.ekler || []).length) ist.append(eklerKutusu(k.ekler));
  kart.append(ist);
  // 2) TEK DURUM SATIRI
  const [ad, sinif] = SOHBET_KART_DURUM[k.durum] || [k.durum || "", ""];
  const ds = el("div", "kart-durum " + sinif);
  ds.append(el("span", "kart-nokta"), el("b", null, ad));
  const isler = k.isler || [];
  const kimler = isler.map((i) => i.sahip).filter(Boolean).filter((v, i, a) => a.indexOf(v) === i);
  if (k.canli) {
    const s = el("span", "sohbet-sure"); s.dataset.bas = k.canli.basladi || k.an || "";
    ds.append(document.createTextNode(" · " + (k.canli.kim || "") +
              (k.canli.ne === "inceleme" ? " (lider inceliyor)" : "") + " · "), s);
    if (k.canli.son) ds.append(el("span", "kart-son", " — " + k.canli.son));
  } else if (k.durum === "bitti" || k.durum === "iptal") {
    if (kimler.length) ds.append(document.createTextNode(" · " + kimler.join(", ")));
    if (k.sure_sn != null) ds.append(document.createTextNode(" · " + sureYazi(k.sure_sn)));
  } else if (k.durum === "sirada") {
    ds.append(document.createTextNode(` · ${k.sira_no}. sırada`));
  } else if (k.durum === "iletilemedi" && k.sebep) {
    ds.append(el("span", "kart-son", " — " + k.sebep));
  } else if (k.durum === "dusunuyor") {
    const s = el("span", "sohbet-sure"); s.dataset.bas = k.an || "";
    ds.append(document.createTextNode(" · "), s);
  }
  // durum satirinin dugmeleri
  const dug = el("span", "kart-dugmeler");
  const acikIsler = isler.filter((i) => !["bitti", "iptal"].includes(i.durum));
  if (k.durum === "sirada") {
    const b = el("button", "sohbet-cip", "İptal");
    b.onclick = () => kartIslem("/api/kuyruk/" + encodeURIComponent(k.id) + "/iptal", {}, "iş sıradan çıkarıldı");
    dug.append(b);
  }
  if (k.durum === "iletilemedi") {
    const b1 = el("button", "sohbet-cip", "Tekrar dene");
    b1.onclick = () => kartIslem("/api/kuyruk/" + encodeURIComponent(k.id) + "/tekrar", {}, "yeniden sıraya kondu");
    const b2 = el("button", "sohbet-cip", "Kapat");
    b2.onclick = () => kartIslem("/api/kuyruk/" + encodeURIComponent(k.id) + "/kapat", {}, "kaldırıldı");
    dug.append(b1, b2);
  }
  for (const i of acikIsler) {
    const tahta = ((D.tahta && Object.values(D.tahta).flat()) || []).find((g) => g.no === i.no) || {};
    const b = el("button", "sohbet-cip", (tahta.duraklatildi ? "Sürdür" : "Duraklat") + (acikIsler.length > 1 ? " #" + i.no : ""));
    b.onclick = () => kartIslem(`/api/gorev/${i.no}/` + (tahta.duraklatildi ? "surdur" : "duraklat"), {},
                                tahta.duraklatildi ? `#${i.no} sürüyor` : `#${i.no} duraklatıldı`);
    const ip = el("button", "sohbet-cip", "İptal" + (acikIsler.length > 1 ? " #" + i.no : ""));
    ip.title = "işin ayrıntısı açılır; iptal sebebi orada yazılır";
    ip.onclick = () => gorevAc(i.no);
    dug.append(b, ip);
  }
  if (dug.childNodes.length) ds.append(dug);
  kart.append(ds);
  // 3) SENDEN KARAR: bu istegin islerine bagli onay ve sorular KARTIN ICINDE
  const nolar = new Set(isler.map((i) => i.no));
  if (k.tip === "soru_sana") {
    const s = ((bekleyen && bekleyen.sorular) || []).find((x) => x.id === k.id);
    if (s) kart.append(soruKartiYap(s));
  } else if (bekleyen && nolar.size) {
    for (const a of bekleyen.onaylar || []) if (nolar.has(a.gorev_no)) kart.append(onayKartiYap(a));
    for (const s of bekleyen.sorular || []) if (nolar.has(s.gorev_no)) kart.append(soruKartiYap(s));
  }
  // 4) LIDERIN YAZILMAKTA OLAN CEVABI (dusunurken akar)
  if (k.durum === "dusunuyor" || (k.akis && !k.sonuc)) {
    const l = el("div", "sohbet-balon lider " + (k.akis ? "akiyor" : "bekliyor") + " kart-akis");
    l.dataset.mesaj = k.id;
    const yz = el("span", "sohbet-yazi"); yz.textContent = k.akis || "düşünüyor…";
    l.append(yz); kart.append(l);
  }
  // 5) SONUC + DOSYALAR
  if (k.sonuc) {
    const so = el("div", "kart-sonuc");
    const t = el("div", "kart-metin"); kalinYaz(t, k.sonuc); so.append(t);
    if (k.sonuc.length > TAKIM_KATLA_HARF) {
      so.classList.add("katli");
      const tk = el("button", "sohbet-cip", "Tamamını oku");
      tk.onclick = () => { const z = so.classList.toggle("katli"); tk.textContent = z ? "Tamamını oku" : "Kısalt"; };
      so.append(tk);
    }
    kart.append(so);
  }
  if ((k.sonuc_ekler || []).length) kart.append(eklerKutusu(k.sonuc_ekler));
  // 6) ALT: kabul / duzeltme / is cipleri
  const alt = el("div", "sohbet-altlar");
  if (k.durum === "bitti" && isler.length) {
    if (k.kabul) alt.append(el("span", "sohbet-cip durum-bitti", "✓ kabul ettin"));
    else {
      const kb = el("button", "sohbet-cip", "Kabul et");
      kb.title = "teslimi kabul et (karar günlüğüne yazılır)";
      kb.onclick = () => kartIslem("/api/mesaj/" + encodeURIComponent(k.id) + "/kabul", {}, "kabul edildi");
      alt.append(kb);
    }
    const dz = el("button", "sohbet-cip", "Düzeltme iste");
    dz.onclick = () => {
      const g = $("#sohbet-girdi"); if (!g) return;
      g.value = `Düzeltme (${isler.map((i) => "#" + i.no).join(" ")}): `;
      g.focus(); g.setSelectionRange(g.value.length, g.value.length);
    };
    alt.append(dz);
  }
  for (const i of isler) {
    const c = el("button", "sohbet-cip durum-" + i.durum, `#${i.no} ${GOREV_DURUM[i.durum] || i.durum}`);
    c.title = (i.baslik || "") + " — işin ayrıntısı";
    c.onclick = () => gorevAc(i.no);
    alt.append(c);
  }
  if (kimler.length && adlar.includes(kimler[0])) {
    const t = el("button", "sohbet-cip", "Terminalde göster");
    t.onclick = () => { D.secilenAjan = kimler[0]; if (D.yerlesim) panoSec("ofis"); cizOfis(); };
    alt.append(t);
  }
  if (alt.childNodes.length) kart.append(alt);
  // 7) KATLI AYRINTI: verilen isler, islem satirlari, ajanlarin mesajlari
  if (k.tip !== "sirada" && k.tip !== "iletilemedi" && k.tip !== "soru_sana"
      && (isler.length || (k.ayrinti || []).length || (k.adimlar || []).length)) {
    const sahte = { id: k.id, bekliyor: false,
                    istek_durum: { isler, adimlar: k.adimlar || [], adim: k.adim || 0 } };
    kart.append(adimBlogu(sahte, k.ayrinti || [], adlar, false));
  }
  return kart;
}

function kartSeridi(kartlar) {
  const say = { calisiyor: 0, karar: 0, durdu: 0, sirada: 0 };
  let ilk = {};
  for (const k of kartlar) {
    const d = k.durum === "dusunuyor" ? "calisiyor" : k.durum;
    if (d in say) { say[d]++; ilk[d] = ilk[d] || k.id; }
  }
  const ad = { calisiyor: "sürüyor", karar: "senden karar bekliyor", durdu: "durdu", sirada: "sırada" };
  const p = Object.keys(say).filter((d) => say[d]);
  if (!p.length) return null;
  const s = el("div", "kart-serit");
  for (const d of p) {
    const b = el("button", "sohbet-cip " + (SOHBET_KART_DURUM[d] || ["", ""])[1], `${say[d]} ${ad[d]}`);
    b.onclick = () => {
      const h = document.querySelector(`#pano-sohbet [data-kart="${CSS.escape(ilk[d])}"]`);
      if (h) h.scrollIntoView({ block: "center", behavior: "smooth" });
    };
    s.append(b);
  }
  return s;
}

async function cizSohbet(kap) {
  let r, bek = null;
  try { r = await al("/api/kartlar" + (D.kanat ? "?kanat=" + D.kanat : "")); }
  catch (e) { return kap.append(el("div", "form-ipucu uyari", "takım sohbeti okunamadı: " + e.message)); }
  try { bek = await al("/api/bekleyenler"); } catch (_) { bek = D.bekleyen || null; }
  const kartlar = r.kartlar || [];
  const adlar = ((D.ofis && D.ofis.ajanlar) || []).map((a) => a.ad);
  const bas = el("div", "takim-bas");
  bas.append(el("b", null, "Takım sohbeti"),
             el("span", "takim-ipucu", "yaz → lidere · @ad → ajana sor ya da not · @ad iş: … → işi ona ver"));
  kap.append(bas);
  const serit = kartSeridi(kartlar);
  if (serit) kap.append(serit);
  if (!kartlar.length)
    return kap.append(el("div", "bos-yazi",
      "Takım sohbeti boş. Alttaki satıra yaz: adres yoksa lidere gider; " +
      "@ad ile bir ajana sorarsın, @ad iş: … ile işi o ajana verirsin."));
  const kosuyor = (r.kosu && r.kosu.calisiyor) || (r.danisma && r.danisma.calisiyor);
  if (!kosuyor) gecicIpuclariniGeriAl();
  for (const k of kartlar) kap.append(kartCiz(k, adlar, bek));
  if (kap.dataset.altta !== "0") kap.scrollTop = kap.scrollHeight;
  else kap.scrollTop = Number(kap.dataset.kaydir || 0);
  kap.onscroll = () => {
    kap.dataset.altta = (kap.scrollHeight - kap.scrollTop - kap.clientHeight < 40) ? "1" : "0";
    kap.dataset.kaydir = String(kap.scrollTop);
  };
  sureleriYaz();
  if (kosuyor) sohbetAkisIzle();
}

function gecicIpuclariniGeriAl() {
  for (const g of document.querySelectorAll("[data-gecici='1']")) {
    g.placeholder = g.dataset.varsayilan || "";
    delete g.dataset.gecici;
  }
}

/* CEVAP YAZILIRKEN AKAR (29.09.2026). Lider kosarken yalniz AKAN metin
   yoklanir ve bekleyen balonun ICI degistirilir -- pano bastan cizilmez
   (kaydirma ve secim korunur). Akis kaydi kaybolunca (cevap deftere
   dustu) ya da kosu bitince sohbet bir kez tam cizilir. Metin sunucuda
   JSON'dan ayiklanmis gelir; burada yorum yok. */
let _sohbetAkisZaman = null;
function sohbetAkisIzle() {
  if (_sohbetAkisZaman) return;
  const tur = async () => {
    _sohbetAkisZaman = null;
    const kap = $("#pano-sohbet");
    if (!kap || !panoAcik("sohbet")) return;
    let r;
    try { r = await al("/api/sohbet/akis"); } catch (e) { return; }
    const akis = r.akis || {};
    let biten = false;
    for (const b of kap.querySelectorAll(".sohbet-balon.lider[data-mesaj]")) {
      const metin = akis[b.dataset.mesaj];
      const yazi = b.querySelector(".sohbet-yazi");
      if (metin) {
        if (yazi && yazi.textContent !== metin) {
          const altta = kap.scrollHeight - kap.scrollTop - kap.clientHeight < 40;
          yazi.textContent = metin;
          b.classList.remove("bekliyor"); b.classList.add("akiyor");
          if (altta) kap.scrollTop = kap.scrollHeight;
        }
      } else if (b.classList.contains("akiyor")) biten = true;
    }
    if (biten || !(r.kosu && r.kosu.calisiyor)) {
      if (medyaKullaniliyor(kap)) { _sohbetAkisZaman = setTimeout(tur, 2000); return; }
      await sohbetiTazele(kap); return;
    }
    _sohbetAkisZaman = setTimeout(tur, 400);
  };
  _sohbetAkisZaman = setTimeout(tur, 400);
}

async function cizRaporlar(kap) {
  const r = await al("/api/raporlar");
  if (!r.length) return kap.append(el("div", "bos-yazi", "Henüz rapor yok."));
  for (const x of r) {
    const o = el("div", "oge");
    const bas = el("div", "oge-bas");
    bas.append(el("span", null, x.ajan_ad),
               el("span", null, x.gorev_no ? "#" + x.gorev_no : ""),
               el("span", null, saat(x.olusturuldu)));
    o.append(bas, el("div", "oge-govde",
                     kes(raporTemiz(x.govde) || "(metin yok)", 320)));
    if (x.gorev_no) { o.style.cursor = "pointer";
                      o.onclick = () => gorevAc(x.gorev_no); }
    // RAPOR + KARARLARI (08.10, B3): bu iste verilen kararlar ve senden
    // bekleyen kararlar raporun altinda.
    if ((x.kararlar || []).length) {
      const kk = el("div", "rapor-kararlar");
      kk.append(el("div", "dt-alt", "bu işte verilen kararlar"));
      for (const k of x.kararlar)
        kk.append(el("div", "rapor-karar",
          `${k.veren === "insan" ? "sen" : k.veren}: ${kes(k.karar, 140)}` + (k.gerekce ? ` — ${kes(k.gerekce, 100)}` : "")));
      o.append(kk);
    }
    for (const b of x.bekleyen || []) {
      const kb = el("div", "rapor-bekleyen");
      kb.append(el("b", null, b.tur === "soru" ? "? senden karar bekliyor: " : "⏸ onayını bekliyor: "),
                document.createTextNode(kes(b.metin, 200)));
      if (b.tur === "soru") {
        const sat = el("div", "istek-eylem");
        let secili = b.secim && b.secim.onerilen != null ? b.secim.onerilen : null;
        if (b.secim) {
          const sec = el("div", "secenekler");
          const dg = b.secim.secenekler.map((t, i) => {
            const d = el("button", "secenek" + (i === secili ? " secili" : ""), t + (i === b.secim.onerilen ? "  ★" : ""));
            d.onclick = (e) => { e.stopPropagation(); secili = i; dg.forEach((z, j) => z.classList.toggle("secili", j === i)); };
            return d;
          });
          sec.append(...dg);
          kb.append(sec);
        }
        const girdi = el("input");
        girdi.placeholder = b.secim ? "İstersen not ekle…" : "Kararın…";
        girdi.onclick = (e) => e.stopPropagation();
        const dug = el("button", "dugme olumlu", "Cevapla");
        dug.onclick = (e) => {
          e.stopPropagation();
          const ek = girdi.value.trim();
          const metin = b.secim && secili != null ? b.secim.secenekler[secili] + (ek ? " — " + ek : "") : ek;
          if (metin) eylem(`/api/soru/${b.id}/cevap`, { metin }, "karar gönderildi");
        };
        sat.append(girdi, dug);
        kb.append(sat);
      } else {
        kb.append(el("span", "dt-alt", "  — sağdaki “Senden bekleniyor” kartından"));
      }
      o.append(kb);
    }
    kap.append(o);
  }
}

/* ─────────────── HAFIZA: bilgi · bag · kural ───────────────

   OLCULDU (24.09.2026): gercek ofiste OLGU SAYISI SIFIRDI -- bu pano
   "Henuz bilgi yok" diyordu ve bu dogruydu, cunku hafizayi besleyen tek
   bir yol yoktu. Artik uc kapi var: ajan (`bilgi_yaz`), kabuk (`bilgi
   ekle`) ve burasi.

   KURAL her brifinge KOSULSUZ girer; bilgi goreve gore SECILIR. Bir
   bilgiyi kurala yukseltmek "ilgiliyse" degil "her zaman" demek -- ve
   her turda odenir, o yuzden yuku (~jeton) basta yazar.

   CIZGE bir sus degil, SECIMIN HARITASI: kenarlar sunucuda, brifing
   seciminin izledigi `[[bag]]`larin ta kendisi. Bag yoksa cizge
   cizilmez ve NEDEN cizilmedigi yazilir. */
/* TAKIM KAPSAMI (06.10, patron: "her takim ayri"): "" = hepsi, "ortak" =
   yalniz ortak, takim kimligi = o takim + ortak. Ajanlar YALNIZ kendi
   takimini + ortagi gorur; panel hepsini gosterebilir. */
function hafizaKanatQ() { return "kanat=" + encodeURIComponent(D.hafizaKanat || ""); }
function hafizaYazimKanati() { return D.hafizaKanat || "ortak"; }
function kanatAnahtari(kid) { return kid ? kid : "ortak"; }

async function cizHafiza(kap) {
  const h = await al("/api/hafiza?" + hafizaKanatQ());
  D.hafiza = h;
  const ust = el("div", "hf-ust");
  // TAKIM SECICI: yalniz birden cok takim varsa anlamli.
  if ((h.kanatlar || []).length) {
    const sec = el("select", "hf-kanat");
    sec.title = "Hangi takımın hafızası? Ajanlar yalnız kendi takımının bilgisini ve ORTAK bilgiyi görür.";
    for (const [v, ad] of [["", "Bütün takımlar"], ["ortak", "Ortak (herkes)"],
                           ...h.kanatlar.map((k) => [k.id, k.ad])]) {
      const o = el("option", null, ad);
      o.value = v;
      if ((D.hafizaKanat || "") === v) o.selected = true;
      sec.append(o);
    }
    sec.onchange = () => { D.hafizaKanat = sec.value; cizSekme(); };
    ust.append(sec);
  }
  const kip = el("div", "hf-kip");
  for (const [k, ad] of [["liste", "Liste"], ["cizge", "Çizge"]]) {
    const b = el("button", "hf-kip-d" + ((D.hafizaKip || "liste") === k ? " secili" : ""), ad);
    b.onclick = () => { D.hafizaKip = k; cizSekme(); };
    kip.append(b);
  }
  ust.append(kip);
  // HAFIZADA ARA (03.10.2026): bilgi, ders, kural, karar -- kelimeyle.
  const ara = el("input", "ara-kutu hf-ara");
  ara.type = "search"; ara.placeholder = "hafızada ara…";
  ara.value = D.hafizaAra || "";
  const sonuc = el("div", "hf-ara-sonuc");
  let zaman = null;
  const aramaYap = async () => {
    D.hafizaAra = ara.value;
    if (!ara.value.trim()) { sonuc.replaceChildren(); return; }
    let r;
    try { r = await al("/api/hafiza/ara?q=" + encodeURIComponent(ara.value) + "&" + hafizaKanatQ()); }
    catch (e) { sonuc.replaceChildren(el("div", "hf-not", "aranamadı: " + e.message)); return; }
    sonuc.replaceChildren(el("div", "hf-bas", `ARAMA · ${r.sonuc.length} sonuç`));
    const TUR = { bilgi: "bilgi", ders: "ders", kural: "kural", karar: "karar" };
    const DUR = { eski: "eski sürüm", yanlis: "yanlış işaretli" };
    for (const x of r.sonuc) {
      const o = el("div", "oge" + (x.durum !== "gecerli" ? " eski" : ""));
      const b = el("div", "oge-bas");
      b.append(el("span", "hf-rozet", TUR[x.tur]), el("span", "hf-konu", " " + x.baslik));
      if (DUR[x.durum]) b.append(el("span", "hf-rozet", DUR[x.durum]));
      o.append(b, el("div", "oge-govde", x.metin));
      if (x.tur === "bilgi" && x.durum === "gecerli") {
        o.style.cursor = "pointer";
        o.onclick = () => { const h2 = [...document.querySelectorAll(".hf-bilgi")]
          .find((n) => n.querySelector(".hf-konu")?.textContent === x.baslik);
          if (h2) { h2.scrollIntoView({ block: "center" }); h2.classList.add("vurgu");
                    setTimeout(() => h2.classList.remove("vurgu"), 1400); } };
      }
      sonuc.append(o);
    }
    if (!r.sonuc.length) sonuc.append(el("div", "hf-not", "Bulunamadı."));
  };
  ara.oninput = () => { clearTimeout(zaman); zaman = setTimeout(aramaYap, 250); };
  ust.append(ara);
  kap.append(ust, sonuc);
  if (ara.value.trim()) aramaYap();

  kap.append(hafizaKurallar(h));
  kap.append(hafizaBilgiFormu());

  if ((D.hafizaKip || "liste") === "cizge") {
    kap.append(hafizaCizgeBolumu(h));
  } else {
    kap.append(hafizaBelgeler());
    if ((h.birlesim || []).length) kap.append(hafizaBirlesim(h));
    kap.append(hafizaBilgiler(h));
  }
  if (h.dersler && h.dersler.length) kap.append(hafizaDersler(h));
  if (h.eski.length) {
    const d = el("details", "hf-bolum");
    d.append(el("summary", "hf-bas", `DEVRİLMİŞ · ${h.eski.length} — ajanlara gitmiyor, geçmiş için duruyor`));
    for (const f of h.eski) {
      const o = el("div", "oge eski");
      const ob = el("div", "oge-bas", f.konu);
      if (f.yanlis) ob.append(el("span", "hf-rozet uyari", "yanlış: " + f.yanlis));
      o.append(ob, el("div", "oge-govde", f.icerik));
      d.append(o);
    }
    kap.append(d);
  }
}

function hafizaKurallar(h) {
  const b = el("div", "hf-bolum");
  const m = h.kural_maliyeti || {};
  const bas = el("div", "hf-bas", `OFİS KURALLARI · ${h.kurallar.length}`);
  if (h.kurallar.length) {
    const y = el("span", "hf-yuk" + (m.uyari ? " uyari" : ""),
                 `her brifinge ~${m.jeton_yaklasik} jeton`);
    y.title = "Kurallar görevle ilgisine bakılmadan HER ajanın HER turuna girer.";
    bas.append(y);
  }
  b.append(bas);
  if (!h.kurallar.length)
    b.append(el("div", "hf-not", "Kural yok. Bir bilgiyi ya da tekrarlayan bir dersi aşağıdan kurala yükseltebilirsin; kural görevle ilgisine bakılmadan her işe girer."));
  for (const k of h.kurallar) {
    const o = el("div", "hf-kural");
    // Kural bag IZLEMEZ (kosulsuz girer); `[[...]]` isareti burada
    // anlamsiz, yalniz ad kalir.
    o.append(el("span", "hf-kural-metin",
                String(k.metin).replace(/\[\[([^\[\]\n]+)\]\]/g, "$1")));
    o.append(el("span", "hf-rozet", k.kaynak_tur));
    const x = el("button", "hf-mini", "kaldır");
    x.title = "Kural silinmez, kaldırılır; sebep karar günlüğüne yazılır.";
    x.onclick = () => satirSor(o, "Kaldırma sebebi (zorunlu)", "kaldır", (sebep) =>
      eylem(`/api/kural/${encodeURIComponent(k.id)}/kaldir`, { sebep },
            "kural kaldırıldı"));
    o.append(x);
    o.title = `gerekçe: ${k.gerekce}`;
    b.append(o);
  }
  const ek = el("button", "hf-mini", "+ kural");
  ek.onclick = () => {
    const f = el("div", "hf-form");
    const mt = el("input"); mt.placeholder = "Kural (her işte geçerli olacak)";
    const gr = el("input"); gr.placeholder = "Gerekçe (zorunlu)";
    const ok = el("button", "dugme olumlu", "ekle");
    ok.onclick = async () => {
      if (!mt.value.trim() || !gr.value.trim()) return bildir("kural ve gerekçe zorunlu", "kotu");
      await eylem("/api/kural", { metin: mt.value, gerekce: gr.value, kanat: hafizaYazimKanati() }, "kural eklendi");
    };
    f.append(mt, gr, ok);
    ek.replaceWith(f);
    mt.focus();
  };
  b.append(ek);
  return b;
}

function hafizaBilgiFormu() {
  const f = el("div", "hf-form hf-bilgi-form");
  const konu = el("input"); konu.placeholder = "Konu (ör. iade süresi)";
  konu.maxLength = 80;
  const ic = el("input"); ic.placeholder = "Bilgi — başka konuya [[konu]] ile bağla";
  ic.maxLength = 600;
  const ok = el("button", "dugme olumlu", "+ bilgi");
  ok.title = "Senin yazdığın bilgiyi ajan sessizce değiştiremez.";
  ok.onclick = async () => {
    if (!konu.value.trim() || !ic.value.trim()) return bildir("konu ve bilgi zorunlu", "kotu");
    await eylem("/api/bilgi", { konu: konu.value, icerik: ic.value, kanat: hafizaYazimKanati() }, (r) =>
      r.durum === "ayni" ? `${r.konu}: zaten böyle — yeni sürüm açılmadı`
      : r.durum === "guncellendi" ? `${r.konu} güncellendi (eskisi geçmişte)`
      : `${r.konu} hafızaya yazıldı`);
  };
  f.append(konu, ic, ok);
  return f;
}

/* ON TAHMIN (06.10, E74): karneden; bilinmeyen "?" kalir, uydurulmaz. */
function tahminMetni(govde) {
  let t = {};
  try { t = JSON.parse(govde || "{}"); } catch (_) { return govde; }
  const sure = (s) => s == null ? "?" : (s < 90 ? `${Math.round(s)} sn` : `${Math.round(s / 60)} dk`);
  const bin = (j) => j == null ? "?" : `${Math.round(j / 1000)} bin`;
  if ("gercek_sure_sn" in t)
    return `süre ${sure(t.tahmin_sure_sn)} → ${sure(t.gercek_sure_sn)} · jeton ${bin(t.tahmin_jeton)} → ${bin(t.gercek_jeton)}`;
  if (!t.ornek) return "tahmin yok (karnede bu tür iş henüz yok)";
  return `~${sure(t.sure_sn)} · ~${bin(t.jeton)} jeton · `
    + (t.yuzde_5s != null ? `~%${t.yuzde_5s} ${t.motor || ""} 5 saatlik kota` : "kota yüzdesi bilinmiyor")
    + ` (${t.ornek} işten)`;
}

/* BELGELER (06.10, E77): yukledigin PDF/Word/Excel/metin parcalara bolunur;
   ajanlar ve lider sorulara KAYNAGIYLA (belge, sayfa/bolum) cevap verir. */
function hafizaBelgeler() {
  const b = el("div", "hf-bolum");
  const bas = el("div", "hf-bas", "BELGELER");
  b.append(bas);
  const liste = el("div");
  b.append(liste);
  const sec = el("input");
  sec.type = "file";
  sec.accept = ".pdf,.docx,.xlsx,.xlsm,.csv,.txt,.md";
  const yukle = el("button", "hf-mini", "belge yükle");
  yukle.title = "PDF, Word, Excel, CSV ya da metin. Taranmış (resim) PDF okunmaz.";
  yukle.onclick = () => sec.click();
  sec.onchange = async () => {
    const f = sec.files && sec.files[0];
    if (!f) return;
    const veri = await new Promise((ok) => {
      const r = new FileReader();
      r.onload = () => ok(String(r.result).split(",")[1] || "");
      r.readAsDataURL(f);
    });
    await eylem("/api/belge", { ad: f.name, veri, kanat: hafizaYazimKanati() },
                (r) => `${r.ad} yüklendi (${r.parca} parça)`);
  };
  b.append(el("div", "hf-eylem"));
  b.lastChild.append(yukle);
  (async () => {
    let j = { belgeler: [] };
    try { j = await al("/api/belgeler?" + hafizaKanatQ()); } catch (_) { /* olculemedi */ }
    bas.textContent = `BELGELER · ${j.belgeler.length}`;
    if (!j.belgeler.length)
      liste.append(el("div", "hf-not", "Belge yok. Yüklediğin belgeden ajanlar ve lider kaynak göstererek cevap verir."));
    for (const d of j.belgeler) {
      const o = el("div", "oge hf-bilgi");
      const ob = el("div", "oge-bas");
      ob.append(el("span", "hf-konu", d.ad), el("span", "hf-rozet", `${d.parca} parça`));
      const k = el("button", "hf-mini olumsuz", "kaldır");
      k.title = "Belge aramadan çıkar (dosya silinmez).";
      k.onclick = () => eylem(`/api/belge/${d.id}/kaldir`, {}, `${d.ad} kaldırıldı`);
      o.append(ob, k);
      liste.append(o);
    }
  })();
  return b;
}

/* AYNI BILGI IKI KONUDA (06.10, E32): ofis OLCER (ortak konu kelimesi +
   ortak deger), karar senin. Tuttugun konu kalir; oteki gecmise gider ve
   adi tuttuguna yonlenir (ajan eski adla yazsa da ayni yere duser). */
function hafizaBirlesim(h) {
  const b = el("div", "hf-bolum");
  b.append(el("div", "hf-bas", `AYNI BİLGİ OLABİLİR · ${h.birlesim.length}`));
  for (const x of h.birlesim) {
    const o = el("div", "oge hf-bilgi");
    o.append(el("div", "oge-govde", `${x.a}: ${x.a_icerik}`));
    o.append(el("div", "oge-govde", `${x.b}: ${x.b_icerik}`));
    o.append(el("div", "hf-not", x.sebep));
    const ey = el("div", "hf-eylem");
    const ta = el("button", "hf-mini", `"${x.a}" kalsın`);
    const tb = el("button", "hf-mini", `"${x.b}" kalsın`);
    ta.title = tb.title = "Tuttuğun konu kalır; öteki geçmişe gider ve adı tuttuğuna yönlenir.";
    ta.onclick = () => eylem("/api/hafiza/birlestir", { asil: x.a, takma: x.b, kanat: D.hafizaKanat || "" }, `birleştirildi: ${x.a}`);
    tb.onclick = () => eylem("/api/hafiza/birlestir", { asil: x.b, takma: x.a, kanat: D.hafizaKanat || "" }, `birleştirildi: ${x.b}`);
    ey.append(ta, tb);
    o.append(ey);
    b.append(o);
  }
  return b;
}

function hafizaBilgiler(h) {
  const b = el("div", "hf-bolum");
  const bas = el("div", "hf-bas", `BİLGİLER · ${h.gecerli.length}`);
  const ip = el("span", "hf-yuk",
    h.gecerli.length > h.secim_esigi ? "göreve göre seçiliyor" : "hepsi brifinge giriyor");
  ip.title = `${h.secim_esigi} bilgiye kadar hepsi her brifinge girer; üstünde göreve göre seçilir ve bağlar bir adım izlenir.`;
  bas.append(ip);
  b.append(bas);
  if (!h.gecerli.length) {
    b.append(el("div", "hf-not", "Henüz bilgi yok. Yukarıdan ekleyebilirsin; ajanlar da çalışırken öğrendikleri kalıcı bilgiyi buraya yazar."));
    return b;
  }
  for (const f of h.gecerli) {
    const o = el("div", "oge hf-bilgi");
    o.id = "hf-" + f.anahtar;
    const ob = el("div", "oge-bas");
    ob.append(el("span", "hf-konu", f.konu));
    ob.append(el("span", "hf-rozet", f.kaynak || "-"));
    // HANGI TAKIMIN: ajanlar yalniz kendi takimininkini + ortagi gorur.
    if ((D.hafiza.kanatlar || []).length > 1 || f.kanat_id)
      ob.append(el("span", "hf-rozet" + (f.kanat_id ? "" : " hf-ortak"), f.kanat_ad || "ortak"));
    if (f.surum > 1) ob.append(el("span", "hf-rozet", `${f.surum}. sürüm`));
    // GERI BAG: bu bilgiye baglanan bilgiler (rakipte "Bagli hafizalar").
    if ((f.geri || []).length) {
      const g = el("span", "hf-rozet hf-geri", `← ${f.geri.length} bağlı`);
      g.title = "Bu bilgiye bağlananlar: " + f.geri.join(", ");
      ob.append(g);
    }
    o.append(ob);
    o.append(hafizaIcerik(f));
    const ey = el("div", "hf-eylem");
    const dz = el("button", "hf-mini", "düzelt");
    dz.title = "Doğrusunu yaz: eskisi geçmişe gider; senin yazdığını ajan değiştiremez.";
    dz.onclick = () => {
      const [k, i] = document.querySelectorAll(".hf-bilgi-form input");
      if (!k || !i) return;
      k.value = f.konu; i.value = f.icerik;
      k.scrollIntoView({ block: "center" }); i.focus();
    };
    const yn = el("button", "hf-mini olumsuz", "yanlış");
    yn.title = "Bilgiyi kapat: ajanlara artık gitmez, ajan aynısını yeniden yazamaz. Geçmişte durur.";
    yn.onclick = () => satirSor(o, "Neden yanlış? (zorunlu)", "kapat",
      (sebep) => eylem("/api/hafiza/yanlis", { konu: f.konu, sebep, kanat: kanatAnahtari(f.kanat_id) }, `${f.konu} yanlış diye kapatıldı`));
    ey.append(dz, yn);
    if (f.surum > 1) {
      const gb = el("button", "hf-mini", "geçmiş");
      gb.onclick = () => hafizaGecmis(o, f.konu, gb, f.kanat_id);
      ey.append(gb);
    }
    const yk = el("button", "hf-mini", "kurala yükselt");
    yk.title = "Bu bilgi görevle ilgisine bakılmadan HER işe girer.";
    yk.onclick = () => satirSor(o, "Neden her işte geçerli olmalı? (zorunlu)", "yükselt",
      (gerekce) => eylem("/api/kural", { olgu: f.konu, gerekce, kanat: kanatAnahtari(f.kanat_id) }, "kurala yükseltildi"));
    ey.append(yk);
    o.append(ey);
    b.append(o);
  }
  return b;
}

/* Icerik metni + `[[bag]]` cipleri. Cip tiklaninca hedef bilgiye gidilir;
   KIRIK bag (henuz yazilmamis konu) kirmizi kesikli ve tiklaninca konu
   formu o adla dolar -- eksik bilgi bir davettir, hata degil. */
function hafizaIcerik(f) {
  const g = el("div", "oge-govde");
  const parca = String(f.icerik).split(/(\[\[[^\[\]\n]{1,80}\]\])/);
  const bl = f.baglar || [];
  for (const p of parca) {
    const m = p.match(/^\[\[(.+)\]\]$/);
    if (!m) { if (p) g.append(document.createTextNode(p)); continue; }
    // Bag SUNUCUNUN listesinden bulunur (ayni ayristirici): once birebir,
    // sonra harf buyuklugu farkiyla. Bulunamazsa uydurulmaz -- tiksiz cip.
    const ad = m[1].split(/\s+/).filter(Boolean).join(" ");
    const bag = bl.find((x) => x.konu === ad)
      || bl.find((x) => x.konu.toLocaleLowerCase("tr") === ad.toLocaleLowerCase("tr"))
      || { konu: ad, kirik: true, anahtar: "" };
    const c = el("button", "bag-cip" + (bag.kirik ? " kirik" : ""), bag.konu);
    c.title = bag.kirik ? "Bu konu henüz yazılmamış — tıkla, formu doldur"
                        : "Bağlı bilgiye git";
    c.onclick = () => {
      if (bag.kirik) {
        const k = document.querySelector(".hf-bilgi-form input");
        if (k) { k.value = bag.konu; k.nextSibling && k.nextSibling.focus(); }
        return;
      }
      const hedef = document.getElementById("hf-" + bag.anahtar);
      if (hedef) { hedef.scrollIntoView({ block: "center" }); hedef.classList.add("vurgu");
                   setTimeout(() => hedef.classList.remove("vurgu"), 1400); }
    };
    g.append(c);
  }
  return g;
}

async function hafizaGecmis(o, konu, dugme, kanatId) {
  const var_ = o.querySelector(".hf-gecmis");
  if (var_) { var_.remove(); return; }
  let r;
  try { r = await al("/api/hafiza/gecmis?konu=" + encodeURIComponent(konu)
                     + "&kanat=" + encodeURIComponent(kanatAnahtari(kanatId))); }
  catch (e) { return bildir("geçmiş okunamadı", "kotu"); }
  const k = el("div", "hf-gecmis");
  for (const x of r.gecmis) {
    const s = el("div", "hf-gecmis-satir" + (x.gecerli_bitis ? " eski" : ""));
    s.append(el("span", "hf-rozet", x.gecerli_bitis ? "devrildi" : "geçerli"),
             el("span", null, x.icerik),
             el("span", "hf-kaynak", `${x.kaynak || "-"} · ${String(x.gecerli_baslangic).slice(0, 16).replace("T", " ")}`));
    k.append(s);
  }
  o.append(k);
}

function hafizaDersler(h) {
  const d = el("details", "hf-bolum");
  const aday = h.dersler.filter((x) => x.aday).length;
  if (aday) d.open = true;
  d.append(el("summary", "hf-bas",
    `DERSLER · ${h.dersler.length}` + (aday ? ` · ${aday} kural adayı` : "")));
  d.append(el("div", "hf-not", "Ders o ajana özeldir. Tekrarlayan ders (aday) bir desendir; herkese açmak için kurala yükselt."));
  for (const x of h.dersler) {
    const o = el("div", "hf-ders" + (x.aday ? " aday" : ""));
    const metin = String(x.ders).split(/\s+/).join(" ");
    o.append(el("span", "hf-rozet", `${x.ajan_ad} ×${x.tekrar}`),
             el("span", "hf-ders-metin", metin));
    const yk = el("button", "hf-mini", "kurala yükselt");
    yk.onclick = () => satirSor(o, "Neden herkese açılmalı? (zorunlu)", "yükselt",
      (gerekce) => eylem("/api/kural", { ders_id: x.id, gerekce }, "ders kurala yükseltildi"));
    const yn = el("button", "hf-mini olumsuz", "yanlış");
    yn.title = "Dersi kaldır: o ajanın brifingine artık girmez, lider yeniden yazsa da geri gelmez.";
    yn.onclick = () => satirSor(o, "Neden yanlış? (zorunlu)", "kaldır",
      (sebep) => eylem("/api/hafiza/yanlis", { ders_id: x.id, sebep }, "ders kaldırıldı"));
    o.append(yk, yn);
    d.append(o);
  }
  return d;
}

/* Satir ici zorunlu metin, tarayicinin prompt diyalogu YERINE: o diyalog paneli
   dondurur ve gerekceyi bos gecmeyi kolaylastirir. */
function satirSor(yer, ipucu, etiket, islem) {
  const var_ = yer.querySelector(".hf-sor");
  if (var_) { var_.remove(); return; }
  const f = el("div", "hf-form hf-sor");
  const i = el("input"); i.placeholder = ipucu;
  const ok = el("button", "dugme olumlu", etiket);
  ok.onclick = async () => {
    if (!i.value.trim()) { i.placeholder = ipucu + " — boş geçilemez"; return i.focus(); }
    await islem(i.value);
  };
  i.onkeydown = (e) => { if (e.key === "Enter") ok.click(); if (e.key === "Escape") f.remove(); };
  f.append(i, ok);
  yer.append(f);
  i.focus();
}

/* CIZGE -- saf yerlesim (DOM'suz, Node'da sinanir): yalniz BAGA KATILAN
   bilgiler ve kirik hedefler cizilir. Bagsiz bilgiyi cizmek daire
   uzerinde anlamsiz noktalar demek olurdu; o yuzden sayisi ayrica
   soylenir. Yerlesim KARARLI: ayni girdi ayni resmi verir (konu adina
   gore sirali), tazelemede noktalar ziplamaz. */
function hafizaCizgesi(gecerli, en, boy, azami) {
  azami = azami || 60;
  const bilgi = {};
  for (const f of gecerli || []) bilgi[f.anahtar] = f;
  const kenarlar = [];
  const derece = {};
  for (const f of gecerli || []) {
    for (const b of f.baglar || []) {
      if (!b.anahtar || b.anahtar === f.anahtar) continue;
      const hedef = b.kirik ? "?" + b.anahtar : b.anahtar;
      kenarlar.push({ kaynak: f.anahtar, hedef, kirik: !!b.kirik });
      derece[f.anahtar] = (derece[f.anahtar] || 0) + 1;
      derece[hedef] = (derece[hedef] || 0) + 1;
      if (b.kirik && !bilgi[hedef]) bilgi[hedef] = { anahtar: hedef, konu: b.konu, kirik: true };
    }
  }
  let kimler = Object.keys(derece);
  let gizlenen = 0;
  if (kimler.length > azami) {
    kimler.sort((a, b) => derece[b] - derece[a] || (a < b ? -1 : 1));
    gizlenen = kimler.length - azami;
    kimler = kimler.slice(0, azami);
  }
  const ic = new Set(kimler);
  kimler.sort((a, b) => String(bilgi[a].konu).localeCompare(String(bilgi[b].konu), "tr"));
  const cx = en / 2, cy = boy / 2;
  const r = Math.max(20, Math.min(en, boy) / 2 - 48);
  const dugumler = kimler.map((k, i) => {
    const aci = -Math.PI / 2 + (2 * Math.PI * i) / Math.max(1, kimler.length);
    const f = bilgi[k];
    return { anahtar: k, konu: f.konu, kirik: !!f.kirik,
             kaynak: f.kaynak || "", surum: f.surum || 1, derece: derece[k],
             x: Math.round((cx + r * Math.cos(aci)) * 10) / 10,
             y: Math.round((cy + r * Math.sin(aci)) * 10) / 10 };
  });
  const yer = {};
  for (const d of dugumler) yer[d.anahtar] = d;
  return {
    dugumler,
    kenarlar: kenarlar.filter((k) => ic.has(k.kaynak) && ic.has(k.hedef))
      .map((k) => ({ ...k, x1: yer[k.kaynak].x, y1: yer[k.kaynak].y,
                     x2: yer[k.hedef].x, y2: yer[k.hedef].y })),
    bagsiz: (gecerli || []).filter((f) => !derece[f.anahtar]).length,
    gizlenen,
  };
}

function hafizaCizgeBolumu(h) {
  const b = el("div", "hf-bolum");
  const en = 420, boy = 340;
  const c = hafizaCizgesi(h.gecerli, en, boy);
  b.append(el("div", "hf-bas", `ÇİZGE · ${c.dugumler.length} bilgi · ${c.kenarlar.length} bağ`));
  if (!c.dugumler.length) {
    b.append(el("div", "hf-not",
      "Henüz bağ yok. Bir bilginin içine [[başka konu]] yazınca bağlanır; " +
      "bağlı bilgi, görevle ortak kelimesi olmasa da brifinge gelir " +
      "(ölçüldü: seçim devredeyken %83 → %100)."));
    return b;
  }
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${en} ${boy}`);
  svg.setAttribute("class", "hf-cizge");
  const defs = document.createElementNS(NS, "defs");
  defs.innerHTML = '<marker id="hf-ok" viewBox="0 0 8 8" refX="14" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8 z" class="hf-ok"/></marker>';
  svg.append(defs);
  const kenarG = document.createElementNS(NS, "g");
  for (const k of c.kenarlar) {
    const l = document.createElementNS(NS, "line");
    for (const [a, v] of [["x1", k.x1], ["y1", k.y1], ["x2", k.x2], ["y2", k.y2]]) l.setAttribute(a, v);
    l.setAttribute("class", "hf-kenar" + (k.kirik ? " kirik" : ""));
    l.setAttribute("marker-end", "url(#hf-ok)");
    l.dataset.kaynak = k.kaynak; l.dataset.hedef = k.hedef;
    kenarG.append(l);
  }
  svg.append(kenarG);
  const ayrinti = el("div", "hf-cizge-ayrinti");
  ayrinti.textContent = "Bir bilgiye tıkla: bağlı olduğu bilgiler parlar.";
  for (const d of c.dugumler) {
    const g = document.createElementNS(NS, "g");
    g.setAttribute("class", "hf-dugum" + (d.kirik ? " kirik" : "")
                   + (String(d.kaynak).startsWith("insan") ? " insan" : ""));
    g.setAttribute("transform", `translate(${d.x},${d.y})`);
    const ci = document.createElementNS(NS, "circle");
    ci.setAttribute("r", 6 + Math.min(4, d.surum - 1));
    const t = document.createElementNS(NS, "text");
    t.textContent = d.konu.length > 18 ? d.konu.slice(0, 17) + "…" : d.konu;
    t.setAttribute("y", -10);
    t.setAttribute("text-anchor", "middle");
    const tt = document.createElementNS(NS, "title");
    tt.textContent = d.kirik ? `${d.konu} — henüz yazılmamış` : d.konu;
    g.append(ci, t, tt);
    g.onclick = () => {
      svg.querySelectorAll(".hf-dugum").forEach((x) => x.classList.remove("secili", "komsu"));
      svg.querySelectorAll(".hf-kenar").forEach((x) => x.classList.remove("secili"));
      g.classList.add("secili");
      kenarG.querySelectorAll("line").forEach((l) => {
        if (l.dataset.kaynak === d.anahtar || l.dataset.hedef === d.anahtar) l.classList.add("secili");
      });
      const f = h.gecerli.find((x) => x.anahtar === d.anahtar);
      ayrinti.textContent = "";
      if (!f) {
        ayrinti.append(el("b", null, d.konu), document.createTextNode(" — bu konu henüz yazılmamış. Listeden ya da formdan ekleyebilirsin."));
        return;
      }
      ayrinti.append(el("b", null, f.konu), document.createTextNode(`  (${f.kaynak || "-"}${f.surum > 1 ? " · " + f.surum + ". sürüm" : ""})`));
      ayrinti.append(hafizaIcerik(f));
    };
    svg.append(g);
  }
  b.append(svg, ayrinti);
  const not = [];
  if (c.bagsiz) not.push(`${c.bagsiz} bilgi bağsız (çizgede yok, listede var)`);
  if (c.gizlenen) not.push(`${c.gizlenen} düğüm yer yüzünden gizlendi (en az bağlı olanlar)`);
  if (not.length) b.append(el("div", "hf-not", not.join(" · ")));
  return b;
}

async function cizKararlar(kap) {
  const k = await al("/api/kararlar");
  if (!k.length) return kap.append(el("div", "bos-yazi", "Henüz karar yok."));
  for (const x of k) {
    const o = el("div", "oge");
    const bas = el("div", "oge-bas");
    bas.append(el("span", null, x.veren), el("span", null, x.tur));
    o.append(bas, el("div", "oge-govde", x.karar),
             el("div", "oge-gerekce", x.gerekce));
    kap.append(o);
  }
}

/* ─────────────── hesaplar: ray dugmesi + pano ─────────────── */

// TEK KAYNAK: `/api/hesaplar`. Ray dugmesi ve pano ayni cevabi okur --
// iki ayri istek iki ayri ani gosterirdi.
async function hesaplariAl(taze) {
  const t = taze ? await yolla("/api/hesaplar/tazele", {}) : await al("/api/hesaplar");
  // Terminal basliklarindaki hesap rozeti (B7) bu tablodan: ilk geliste ya
  // da hesap/e-posta degisince panolar yeniden cizilir (yoksa ilk cizimde
  // tablo henuz yoktu ve rozet hic cikmiyordu -- olculdu).
  const imza = (x) => JSON.stringify(((x || {}).hesaplar || []).map((h) => [h.ad, h.eposta, h.plan, h.durum]));
  const degisti = imza(D.hesaplar) !== imza(t);
  D.hesaplar = t;
  if (degisti) { try { cizCanli(); } catch (_) {} }
  return t;
}

const HESAP_DURUM = {
  hazir: { sinif: "", yazi: "hazır" },
  dikkat: { sinif: "u", yazi: "dikkat" },
  dolu: { sinif: "k", yazi: "dolu" },
  kullanilamiyor: { sinif: "g", yazi: "kullanılamıyor" },
  olculmedi: { sinif: "g", yazi: "ölçülmedi" },
  kapali: { sinif: "g", yazi: "kapalı" },
};

// Cubuk rengi: rahat / dikkat / dolu. Olculmeyen gri, uydurulmaz.
function doluSinif(k) {
  if (k == null) return "g";
  return k >= 0.9 ? "k" : (k >= 0.75 ? "u" : "");
}

// Dolu pencerenin ne zaman acilacagi -- insanin bekledigi tek sayi.
// Birden cok pencere doluysa EN GEC acilan belirleyicidir.
function doluKalan(h, simdi) {
  const w = (h.pencereler || [])
    .filter(x => x.kullanim != null && x.kullanim >= 0.999 && x.yenilenme)
    .sort((a, b) => Date.parse(b.yenilenme) - Date.parse(a.yenilenme))[0];
  return w ? kalanSure(w.yenilenme, simdi) : "";
}

// Raydaki ozet YALNIZ SORUNU soyler; sorun yoksa "hepsi rahat".
function hesapOzetYazi(t, simdi) {
  const hs = (t.hesaplar || []).filter(h => h.durum !== "kapali");
  const dolu = hs.filter(h => h.durum === "dolu");
  const bozuk = hs.filter(h => h.durum === "kullanilamiyor");
  const dikkat = hs.filter(h => h.durum === "dikkat");
  if (dolu.length === 1 && !bozuk.length) {
    const k = doluKalan(dolu[0], simdi);
    return { sinif: "k", yazi: `${dolu[0].ad} dolu` + (k ? ` · ↻ ${k}` : "") };
  }
  const parca = [];
  if (dolu.length) parca.push(`${dolu.length} dolu`);
  if (bozuk.length) parca.push(bozuk.length === 1 ? `${bozuk[0].ad} kullanılamıyor`
                                                  : `${bozuk.length} kullanılamıyor`);
  if (parca.length) return { sinif: "k", yazi: parca.join(" · ") };
  if (dikkat.length) {
    const h = dikkat[0];
    return { sinif: "u", yazi: `${h.ad} %${Math.round((h.en_yuksek || 0) * 100)}` };
  }
  if (!hs.length) return { sinif: "", yazi: "hesap yok" };
  return { sinif: "", yazi: "hepsi rahat" };
}

function hesapDugmesiCiz(d, t) {
  d.innerHTML = "";
  if (!t) { d.append(el("span", "hap-yazi", "Hesaplar …")); return; }
  const hs = (t.hesaplar || []).filter(h => h.durum !== "kapali");
  const sira = el("span", "hap-cubuklar");
  for (const h of hs) {
    const c = el("i", "hap-cubuk " + ((HESAP_DURUM[h.durum] || {}).sinif || ""));
    c.title = `${h.ad} · ${(HESAP_DURUM[h.durum] || {}).yazi}` +
              (h.en_yuksek != null ? ` · en dolu pencere %${Math.round(h.en_yuksek * 100)}` : "");
    sira.append(c);
  }
  const oz = hesapOzetYazi(t);
  const yazi = el("span", "hap-yazi");
  yazi.append(el("span", null, `Hesaplar ${t.hazir}/${t.toplam} hazır`),
              el("small", oz.sinif ? "hap-" + oz.sinif : "", oz.yazi));
  d.append(sira, yazi);
  d.title = "Hesap limitleri — tıkla: her hesabın pencereleri, yenilenme zamanı, iş sırası";
}

function hesapPanosuAc() {
  D.acikCekmece = { tur: "hesaplar" };
  cizKullanim().then(() => {
    if ((D.acikCekmece || {}).tur === "hesaplar") hesapPanosuCiz($("#cekmece"), D.hesaplar);
  });
  cekmeceAc(c => hesapPanosuCiz(c, D.hesaplar));
  hesaplariAl().then(t => {
    if ((D.acikCekmece || {}).tur === "hesaplar") hesapPanosuCiz($("#cekmece"), t);
  }).catch(() => {});
}

function hesapPanosuCiz(c, t) {
  c.innerHTML = "";
  cekBas(c, "HESAPLAR", "Hesap limitleri");
  if (!t) { c.append(el("div", "bos-yazi", "ölçülüyor…")); return; }

  const ust = el("div", "hp-ust");
  ust.append(el("span", null, t.tazelendi_dk == null ? "sağlayıcıdan henüz canlı okunmadı"
                              : `sağlayıcıdan okundu · ${t.tazelendi_dk} dk önce`));
  const tz = el("button", "hp-tazele", "Şimdi tazele");
  tz.type = "button";
  tz.title = "Her hesabın limitini sağlayıcıdan şimdi okur. Kota harcamaz.";
  tz.onclick = async () => {
    tz.disabled = true; tz.textContent = "okunuyor…";
    try {
      const y = await hesaplariAl(true);
      hesapPanosuCiz(c, y);
      const hd = $(".hesap-hap"); if (hd) hesapDugmesiCiz(hd, y);
      if ((y.okunamadi || []).length)
        c.append(el("div", "hp-sebep", "okunamadı: " + y.okunamadi.join("; ")));
    } catch (e) {
      tz.disabled = false; tz.textContent = "Şimdi tazele";
      c.append(el("div", "hp-sebep", "tazelenemedi: " + e.message));
    }
  };
  ust.append(tz);
  c.append(ust);

  // IS SIRASI: zincirin KENDI karari (`zincir.pencereye_gore_sirala`).
  if ((t.sira || []).length) {
    const s = el("div", "hp-sira");
    s.append(el("span", "hp-etiket", "iş sırası şu an"));
    t.sira.forEach((x, i) => {
      if (i) s.append(el("span", "hp-ok", "→"));
      const a = el("span", "hp-adim" + (x.sonda ? " sonda" : ""),
                   x.ad + (x.sonda ? " (dolmak üzere, sonda)" : ""));
      if (x.sonda) a.title = "Eşiği geçti: ofis bu hesaba yeni tur vermeden önce " +
        "ötekileri dener. Silinmez; ötekiler de düşerse yine denenir.";
      s.append(a);
    });
    c.append(s);
  }

  // SAGLAYICIYA GORE; en acil grup ustte (sunucu aciliyet sirasiyla veriyor).
  const gruplar = new Map();
  for (const h of (t.hesaplar || [])) {
    if (!gruplar.has(h.saglayici)) gruplar.set(h.saglayici, []);
    gruplar.get(h.saglayici).push(h);
  }
  for (const [ad, hs] of gruplar) {
    c.append(el("div", "hp-grup", ad));
    for (const h of hs) c.append(hesapSatiri(h));
  }
  c.append(hesapTuketim(D.kullanim));
  c.append(el("div", "hp-not",
    "Yüzdeler hesabın TOPLAMIDIR, sağlayıcının kendi bildirimi (sen elle kullandıysan o da dahil). " +
    "Çubuktaki ince çizgi: ofisin o hesabı iş sırasının sonuna aldığı eşik. " +
    "Ölçülemeyen çizgili gri durur, uydurulmaz."));
}

// OFISIN TUKETTIGI: yalniz ofisin kendi turlari (hesabin toplami DEGIL).
// Olcum yoksa "olculmedi" der, sifir uydurmaz.
function hesapTuketim(k) {
  const b = el("div", "hp-tuketim");
  b.append(el("div", "hp-grup", "Ofisin tükettiği"));
  if (!k || k.hata || !k.oturum) {
    b.append(el("div", "hp-alt", k && k.hata ? k.hata : "henüz ölçülmedi"));
    return b;
  }
  const satir = (ad, p) => {
    const s = el("div", "hp-tk-satir");
    s.append(el("span", null, ad),
             el("b", null, `${p.tur} tur · ${Number(p.jeton).toLocaleString("tr")} jeton`));
    b.append(s);
  };
  satir(`son ${k.oturum_saat} saat`, k.oturum);
  satir("son 7 gün", k.hafta);
  b.append(el("div", "hp-alt", "Yalnız OFİSİN kendi turları; sen elle kullandıysan o burada yok."));
  return b;
}

function hesapSatiri(h) {
  const st = HESAP_DURUM[h.durum] || HESAP_DURUM.olculmedi;
  const satir = el("div", "hp-satir" + (h.durum === "kapali" ? " kapali" : ""));
  const kim = el("div", "hp-kim");
  const ad = el("div", "hp-ad");
  ad.append(el("span", null, h.ad), el("span", "hp-rozet " + (st.sinif || "iyi"), st.yazi));
  kim.append(ad);
  const alt = [h.eposta, h.plan, h.tur === "api" ? "API" : "abonelik"].filter(Boolean).join(" · ");
  if (alt) kim.append(el("div", "hp-alt", alt));
  if ((h.kullanan || []).length) kim.append(el("div", "hp-alt", "kullanan: " + h.kullanan.join(", ")));
  satir.append(kim);

  const pen = el("div", "hp-pencereler");
  if (!(h.pencereler || []).length) {
    const p = el("div", "hp-pen");
    const u = el("div", "hp-pen-ust");
    u.append(el("span", null, "limit"), el("b", null, "—"));
    p.append(u, el("div", "hp-cubuk bilinmez"),
             el("div", "hp-pen-alt", h.durum === "kapali" ? "" : "henüz ölçülmedi"));
    pen.append(p);
  }
  for (const w of (h.pencereler || [])) pen.append(pencereCubugu(w));
  satir.append(pen);
  if (h.sebep) satir.append(el("div", "hp-sebep", h.sebep));
  return satir;
}

function pencereCubugu(w) {
  const p = el("div", "hp-pen");
  const u = el("div", "hp-pen-ust");
  const sayi = w.dolar ? `$${Number(w.harcanan).toFixed(2)} / $${Number(w.sinir).toFixed(2)}`
             : (w.kullanim == null ? "yenilendi" : `%${Math.round(w.kullanim * 100)}`);
  u.append(el("span", null, w.etiket), el("b", null, sayi));
  const cb = el("div", "hp-cubuk " + (w.kullanim == null ? "bilinmez" : doluSinif(w.kullanim)));
  if (w.kullanim != null) {
    const i = el("i");
    i.style.width = Math.min(100, w.kullanim * 100) + "%";
    cb.append(i);
  }
  if (w.esik) {
    const e = el("span", "hp-esik");
    e.style.left = (w.esik * 100) + "%";
    e.title = w.ad === "7g_kapi"
      ? `%${Math.round(w.esik * 100)}: pahalı hakem yükseltmesi kapanır, iş durmaz`
      : `%${Math.round(w.esik * 100)}: ofis bu hesabı iş sırasının sonuna alır`;
    cb.append(e);
  }
  const a = el("div", "hp-pen-alt");
  const kalan = w.yenilenme ? kalanSure(w.yenilenme) : "";
  const zaman = w.yenilenme ? new Date(w.yenilenme).toLocaleString("tr",
    { weekday: "short", hour: "2-digit", minute: "2-digit" }) : "";
  a.append(el("span", null, w.kullanim == null && !w.dolar ? "pencere yenilendi, yeniden okunacak"
               : (kalan ? `↻ ${kalan} (${zaman})` : (zaman ? `↻ ${zaman}` : ""))),
           el("span", "hp-yas", w.dolar ? "ofisin sayımı"
               : (w.yas_dk == null ? "" : `${w.yas_dk} dk önce`)));
  p.append(u, cb, a);
  return p;
}

/* ─────────────── bağlam sağlığı ─────────────── */

// Yenilenmeye kalan sure, insanin okudugu bicimde: "1 sa 8 dk", "6 gün 4 sa".
// Gecmis an bos doner (pencere yenilenmistir; sunucu onu zaten ayri soyler).
function kalanSure(iso, simdi = Date.now()) {
  const dk = Math.round((Date.parse(iso) - simdi) / 60000);
  if (!(dk > 0)) return "";
  const g = Math.floor(dk / 1440), s = Math.floor((dk % 1440) / 60), d = dk % 60;
  if (g) return g + " gün" + (s ? " " + s + " sa" : "");
  if (s) return s + " sa" + (d ? " " + d + " dk" : "");
  return d + " dk";
}

// HESAPLAR ve KULLANIM.
//
// Kullanicinin istegi: "hangi hesap bagli, limitleri ne durumda, ne
// zaman yenilenecek." 22.09'da "limit OLCULEMIYOR" yaziyordu -- YANLISTI:
// saglayici her turda bildiriyor, ofis okuyup atiyordu (23.09.2026).
//
// IKI AYRI SAYI: pencere yuzdesi HESABIN TOPLAMIDIR (saglayicinin
// bildirimi, olcumun yasiyla); tur/jeton satirlari yalniz OFISIN
// kendi turlari. Yenilenmis pencerenin eski yuzdesi GOSTERILMEZ --
// bayat bir sayiyi canli sanmaya davet olurdu.
// 28.09: ayri "Hesap" panosu KALDIRILDI -- hesap listesi hesap panosunun
// (ray dugmesi) tekrariydi. Bu olcum artik ekrana kendi cizmez: pano
// basliklarindaki hesap rozetini besler ve "ofisin tukettigi" satirlari
// hesap panosunun altinda gosterilir (`hesapTuketim`).
async function cizKullanim() {
  let k;
  try { k = await al("/api/kullanim"); } catch (e) { return; }
  // Pano basliklari da ayni olcumu gosterir -- ayri bir istek degil,
  // ayni cevap (iki istek iki farkli ani gosterirdi).
  D.pencereler = k.pencereler || [];
  D.kullanim = k;
}

function cizBaglam() {
  const b = D.ofis.baglam;
  const kap = $("#baglam");
  kap.innerHTML = "";
  const bas = el("div", "baglam-bas");
  bas.append(el("span", null, "BAĞLAM SAĞLIĞI"),
             el("span", null, b.son_brifing_ajan || ""));
  const satir = el("div", "baglam-satir");
  const oge = (deger, etiket, sinif) => {
    const d = el("div", "baglam-oge" + (sinif ? " " + sinif : ""));
    d.append(el("b", null, String(deger)), el("span", null, etiket));
    return d;
  };
  satir.append(oge(b.son_brifing_jeton, "son brifing", b.sisme ? "dikkat" : ""),
               oge(b.gecerli_olgu, "geçerli bilgi"),
               oge(b.eski_olgu, "devrilmiş"),
               oge(b.karar, "karar"));
  kap.append(bas, satir);

  const cubuk = el("div", "baglam-cubuk" + (b.sisme ? " dikkat" : ""));
  const dolgu = el("i");
  dolgu.style.width = Math.min(100, (b.son_brifing_jeton / 6000) * 100) + "%";
  cubuk.append(dolgu);
  cubuk.title = `Brifing ${b.son_brifing_jeton} jeton · 6000 şişme eşiği`;
  kap.append(cubuk);
}

/* ─────────────── çekmece: ajan ve görev ─────────────── */

function cekmeceAc(doldur) {
  const c = $("#cekmece");
  c.innerHTML = "";
  c.classList.remove("genis");
  doldur(c);
  $("#perde").classList.remove("gizli");
}
const cekmeceKapat = () => {
  $("#perde").classList.add("gizli"); D.acikCekmece = null;
  // Organizasyon panosu açıksa, üstündeki çekmece kapanınca pano TAZELENİR
  // (Düzenle'de yapılan değişiklik panoda hemen görünsün).
  if (typeof ORG !== "undefined" && ORG.acik) organizasyonYenile();
};

function cekBas(kap, ust, baslik) {
  const bas = el("div", "cek-bas");
  const sol = el("div");
  sol.append(el("div", "cek-ust", ust), el("div", "cek-baslik", baslik));
  const kapat = el("button", "cek-kapat", "✕");
  kapat.onclick = cekmeceKapat;
  bas.append(sol, kapat);
  kap.append(bas);
}
function cekAlan(kap, etiket, deger) {
  if (!deger) return;
  const a = el("div", "cek-alan");
  a.append(el("div", "cek-etiket", etiket), el("div", "cek-deger", deger));
  kap.append(a);
}

const PANO_SINIF = {
  brifing: "brifing", sahiplenildi: "brifing", arac: "arac", arac_sonuc: "sonuk",
  cikti: "", rapor: "", kanit: "kanit", incelemede: "kanit", kapandi: "kanit",
  hata: "kotu", izin: "kotu", uyari: "kotu", ret: "kotu",
  soru: "bekleme", onay_istendi: "bekleme", cevap: "bekleme",
  tur_ozeti: "sonuk", ders: "kotu",
  not: "bekleme", not_iletildi: "kanit",
  degisim: "kanit", dosya_canli: "sonuk",
};

function ajanAc(ad) {
  const a = D.ofis.ajanlar.find((x) => x.ad === ad);
  if (!a) return;
  D.acikCekmece = { tur: "ajan", ad };
  cekmeceAc((c) => {
    const odaAd = (ODALAR.find((o) => o[0] === a.oda) || [])[1] || "";
    cekBas(c, `${a.meslek} · ${odaAd.toLowerCase()}`, a.ad);

    const et = el("div", "etiketler");
    if (a.lider_mi) et.append(el("span", "etiket lider", "LİDER"));
    if (a.tur === "kafa") et.append(el("span", "etiket yazamaz", "YAZAMAZ"));
    et.append(el("span", "etiket", "motor: " + a.motor),
              el("span", "etiket", "model: " + a.model),
              el("span", "etiket", "efor: " + a.efor));
    if (a.ders) et.append(el("span", "etiket ders", a.ders + " ders"));
    if (a.oturum_var) et.append(el("span", "etiket", "oturumu sürüyor"));
    c.append(et);

    if (a.not) cekAlan(c, "ŞU AN", (a.gorev_no ? `#${a.gorev_no} — ` : "") + a.not);

    c.append(el("div", "cek-etiket", "TERMİNAL"));
    const t = el("div", "cek-terminal");
    const kendi = D.olaylar.filter((o) => o.ajan_ad === ad &&
                                          PANO_SINIF[o.tur] !== undefined);
    if (!kendi.length) {
      t.append(el("div", "sonuk", "— bu ajandan henüz çıktı yok —"));
    } else {
      for (const o of kendi.slice(-160)) {
        const okunur = olayOku(o);
        const satir = el("div", PANO_SINIF[o.tur]);
        satir.textContent = okunur
          ? `${okunur.ne}${okunur.ayrinti ? ": " + okunur.ayrinti : ""}`
          : kes(o.govde.replace(/\s+/g, " "), 220);
        t.append(satir);
      }
    }
    c.append(t);
    t.scrollTop = t.scrollHeight;
    if (a.gorev_no) {
      const dg = el("button", "dugme", "Görevi aç →");
      dg.style.marginTop = "14px";
      dg.onclick = () => gorevAc(a.gorev_no);
      c.append(dg);
    }
    ajanaSor(c, a);
    ajanAyarlari(c, a);
  });
}

/* AJANA SOR: bilgi alisverisi, EMIR degil. Danisilan yazamaz, is acamaz;
   is vermek icin lidere yazilir. Cevap Sohbet panosuna duser. */
function ajanaSor(c, a) {
  c.append(el("div", "cek-etiket", `${a.ad.toUpperCase()}'A SOR`));
  const sat = el("div", "cek-eylem");
  const g = el("input");
  g.placeholder = `${a.ad}'a bir soru… (iş vermek için lidere yaz)`;
  const d = el("button", "dugme olumlu", "Sor");
  const gonder = async () => {
    if (!g.value.trim()) return g.focus();
    const r = await eylem("/api/ajana-sor", { ajan: a.ad, metin: g.value },
      (x) => `${x.ajan}'a soruldu — cevap Sohbet panosuna düşecek`);
    if (r) { g.value = ""; cekmeceKapat(); panoSec("sohbet"); }
  };
  d.onclick = gonder;
  g.addEventListener("keydown", (e) => { if (e.key === "Enter") gonder(); });
  sat.append(g, d);
  c.append(sat, el("div", "form-ipucu",
    "Salt okunur danışma: dosya yazamaz, iş açamaz. Tek tur, tavanlı."));
}

/* KADRO SECENEKLERI: sunucudan OLCULEREK gelir (motor kurulu mu, etkin
   kademe haritasi). Panel kendi listesini tutsaydi rol kutuphanesinden
   kayardi -- iki yerde tutulan her sey en az bir kez kayar. */
async function kadroSecenek() {
  if (!D.kadroSec) D.kadroSec = await al("/api/kadro/secenek");
  return D.kadroSec;
}

function secim(secenekler, secili) {
  const s = el("select");
  for (const [v, t, kapali] of secenekler) {
    const o = el("option", null, t);
    o.value = v;
    if (kapali) { o.disabled = true; }
    if (v === secili) o.selected = true;
    s.append(o);
  }
  return s;
}

function formAlan(kap, etiket, girdi, ipucu) {
  const a = el("div", "form-alan");
  a.append(el("label", null, etiket), girdi);
  if (ipucu) a.append(ipucu);
  kap.append(a);
  return a;
}

function rolSecimi(sec, secili) {
  // Kategoriye gore gruplu; her secenekte rolun NE IS yaptigi. Gorunmeyen
  // kutuphane kullanilmaz -- hangi adi sececegini bilmeyen serbest metne doner.
  const s = el("select");
  for (const k of sec.kategoriler) {
    const g = el("optgroup"); g.label = k;
    for (const r of sec.roller.filter(x => x.kategori === k)) {
      const o = el("option", null, `${r.baslik || r.ad} — ${kes(r.ozet, 60)}`);
      o.value = r.ad;
      if (r.ad === secili) o.selected = true;
      g.append(o);
    }
    s.append(g);
  }
  return s;
}

function motorSecimi(sec, secili) {
  // KURULU OLMAYAN MOTOR SECILEMEZ ve nedeni yazar: hic kosamayacak bir
  // ajan, onizlemede gorunmeyen bir tuzaktir.
  return secim(Object.entries(sec.motorlar)
    .filter(([m]) => m !== "sahte" || secili === "sahte")
    .map(([m, var_]) => [m, var_ ? m : `${m} (kurulu değil)`, !var_]), secili);
}

function modelIpucu(sec, rolAd, motor, ip) {
  const r = sec.roller.find(x => x.ad === rolAd);
  const m = r && (sec.kademe_harita[motor] || {})[r.kademe];
  ip.textContent = r
    ? `Boş bırakılırsa rolün kademesinden: ${r.kademe} → ${m || "(bu motorda kademe yok — hesabın varsayılanı, PAHALI olabilir)"}`
      + ` · tür: ${r.tur === "kafa" ? "kafa (dosya YAZAMAZ)" : "eller"}`
      + (r.uyari ? ` · ${r.uyari}` : "")
    : "";
  ip.className = "form-ipucu" + (r && !m ? " uyari" : "");
}

async function ajanAyarlari(c, a) {
  let sec;
  try { sec = await kadroSecenek(); }
  catch (e) { return c.append(el("div", "form-ipucu uyari", "kadro seçenekleri okunamadı: " + e.message)); }
  c.append(el("div", "cek-etiket", "AYARLAR"));
  const kutu = el("div");
  const rol = rolSecimi(sec, a.meslek);
  const motor = motorSecimi(sec, a.motor);
  const model = modelGirdisi(sec, a.motor, a.model || ""); model.placeholder = "rolün kademesinden";
  const efor = secim(sec.eforlar.map(e => [e, e]), a.efor);
  const ip = el("div", "form-ipucu");
  formAlan(kutu, "Rol", rol, el("div", "form-ipucu",
    "Rol değişince tür, araçlar ve kanıt beklentisi de değişir. Ad ve sicil kalır."));
  const sira = el("div", "form-sira");
  formAlan(sira, "Motor", motor); formAlan(sira, "Efor", efor);
  kutu.append(sira);
  formAlan(kutu, "Model", model, ip);
  kutu.append(model.liste);
  let karakter = a.karakter || "";
  const renk = ((D.ofis.kanatlar || []).find((k) => k.id === a.kanat_id) || {}).renk || "#6b7480";
  formAlan(kutu, "Karakter", karakterSecici(karakter, renk, (k) => { karakter = k; }));
  const tazele = () => modelIpucu(sec, rol.value, motor.value, ip);
  rol.onchange = tazele;
  motor.onchange = () => { model.motorYap(motor.value); tazele(); };
  model.motorYap(a.motor, a.model || "");
  tazele();
  const kaydet = el("button", "dugme olumlu", "Kaydet");
  kaydet.onclick = async () => {
    if (!model.kapiOnayi()) return;
    const r = await eylem(`/api/ajan/${a.ad}/ayar`, {
      meslek: rol.value, motor: motor.value, model: model.value, efor: efor.value, karakter },
      (r) => `${r.ad}: ${r.meslek} · ${r.tur} · ${r.motor}/${r.model || "varsayılan"} · ${r.efor}`);
    // ONCE TAZELE, SONRA AC: ajanAc listeden okur; tazelenmeden acilirsa
    // eski ayari gosterir (ya da yeni ajani hic bulamaz -- olculdu).
    if (r) { D.kadroSec = null; await yenile(); ajanAc(a.ad); }
  };
  const sat = el("div", "cek-eylem"); sat.append(kaydet);
  kutu.append(sat, el("div", "form-ipucu",
    "Yeni ayar bir SONRAKİ turda geçerli olur; süren tur başladığı motorla kalır."));
  c.append(kutu);
}

/* YENİ TAKIM (05.10.2026, patron: "şablona tıklıyorum çalışmıyor, istediğim
   gibi değil"). Tek akış: ad + renk → başlangıç (boş takım ya da şablon) →
   ajan listesi (ad, meslek, motor, model düzenlenir) → KUR. Takım ve
   ajanları TEK SEFERDE kurulur; kuran insan olduğu için ayrıca onay yok.
   Sorun varsa sunucu HİÇBİR ŞEY kurmaz ve sebep pencerenin içinde yazar. */
const AD_ADRES = (x) => String(x || "").toLocaleLowerCase("tr").replace(/ç/g, "c").replace(/ğ/g, "g")
  .replace(/ı/g, "i").replace(/ö/g, "o").replace(/ş/g, "s").replace(/ü/g, "u")
  .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

async function takimEkleAc() {
  let sec, sablonlar = [];
  D.kadroSec = null;
  try { sec = await kadroSecenek(); }
  catch (e) { return bildir("seçenekler okunamadı: " + e.message, "kotu"); }
  try { sablonlar = await al("/api/sablonlar"); } catch (e) { /* boş takım yine kurulur */ }
  cekmeceAc((c) => {
    c.classList.add("genis");
    cekBas(c, "organizasyon", "Yeni takım");
    const ad = el("input"); ad.placeholder = "ör. MAĞAZA, MOBİL, SAAS";
    const renk = el("input"); renk.type = "color";
    renk.value = ["#E0785A", "#6BA3C7", "#5FB98A", "#9B8BD0", "#D9A441"][(D.ofis.kanatlar || []).length % 5];
    const sira = el("div", "form-sira");
    formAlan(sira, "Takım adı", ad); formAlan(sira, "Renk", renk);
    c.append(sira);

    c.append(el("div", "cek-etiket", "BAŞLANGIÇ"));
    const kartlar = el("div", "sablon-liste");
    const kartDug = {};
    const kart = (anahtar, baslik, aciklama, roller) => {
      const b = el("button", "sablon-kart"); b.type = "button";
      b.append(el("div", "sablon-ad", baslik), el("div", "sablon-aciklama", aciklama));
      if (roller) b.append(el("div", "sablon-roller", roller));
      b.onclick = () => baslangic(anahtar);
      kartDug[anahtar] = b; kartlar.append(b);
    };
    kart("bos", "Boş takım", "Yalnız lider; ajanları sonra eklersin.");
    for (const s of sablonlar)
      kart(s.ad, s.baslik + (s.ozel ? " ★" : ""), s.aciklama,
           s.roller.map((r) => (sec.roller.find((x) => x.ad === r) || {}).baslik || r).join(" · "));
    c.append(kartlar);

    c.append(el("div", "cek-etiket", "AJANLAR"));
    const liste = el("div", "takim-liste");
    c.append(liste);
    const satirlar = [];
    const satirEkle = (u) => {
      const sat = el("div", "takim-satir");
      const adG = el("input"); adG.value = u.ad || ""; adG.placeholder = "ajan adı";
      const rol = rolSecimi(sec, u.rol);
      const kurulu = Object.entries(sec.motor_durum || {}).filter(([, d]) => d.kurulu).map(([m]) => m);
      const motor = secim(kurulu.map((m) => [m, MOTOR_ETIKET[m] || m]), u.motor || kurulu[0]);
      const model = modelGirdisi(sec, motor.value, u.model || "");
      motor.onchange = () => model.motorYap(motor.value);
      rol.onchange = () => {
        const k = (sec.katalog || {})[rol.value] || {};
        if (kurulu.includes(k.motor)) { motor.value = k.motor; model.motorYap(k.motor, k.model); }
        satirlar.forEach((x) => x.liderEtiket.hidden = x.rol.value !== "lider");
      };
      const lid = el("span", "org-lider", "LİDER");
      lid.hidden = u.rol !== "lider";
      const sil = el("button", "dugme kucuk", "✕"); sil.title = "Listeden çıkar";
      const kayit = { sat, adG, rol, motor, model, liderEtiket: lid };
      sil.onclick = () => { satirlar.splice(satirlar.indexOf(kayit), 1); sat.remove(); };
      const adKutu = el("div", "takim-ad"); adKutu.append(adG, lid);
      sat.append(adKutu, rol, motor, model, sil);
      satirlar.push(kayit); liste.append(sat);
    };
    let secilenSablon = "";
    const baslangic = async (anahtar) => {
      secilenSablon = anahtar;
      Object.entries(kartDug).forEach(([x, d]) => d.classList.toggle("secili", x === anahtar));
      try {
        const o = await al(`/api/sablon/${encodeURIComponent(anahtar)}/onizleme`);
        liste.innerHTML = ""; satirlar.length = 0;
        o.uyeler.forEach(satirEkle);
      } catch (e) { goster("Şablon okunamadı: " + e.message); }
    };
    const ekleDug = el("button", "dugme kucuk", "+ Meslek ekle");
    ekleDug.onclick = () => {
      const k = (sec.katalog || {}).arayuz || {};
      satirEkle({ ad: "", rol: "arayuz", motor: k.motor, model: k.model });
    };
    const ekleSat = el("div", "cek-eylem"); ekleSat.append(ekleDug); c.append(ekleSat);
    c.append(el("div", "form-ipucu",
      "Türkçe harf ve boşluk adreste çevrilir (Ömer Can → omer-can). Arşivdeki adlar kullanılamaz. " +
      "Motor ve model meslekten gelir; her satırda değiştirebilirsin."));

    const hata = el("div", "cek-hata gizli");
    function goster(m) { hata.textContent = m; hata.classList.remove("gizli"); hata.scrollIntoView({ block: "nearest" }); }
    const kur = el("button", "dugme olumlu", "Takımı kur");
    kur.onclick = async () => {
      hata.classList.add("gizli");
      if (!ad.value.trim()) { goster("Takım adı boş."); return ad.focus(); }
      if (!satirlar.length) return goster("Başlangıç seç: Boş takım ya da bir şablon.");
      const uyeler = satirlar.map((x) => ({ ad: AD_ADRES(x.adG.value), rol: x.rol.value,
                                            motor: x.motor.value, model: x.model.value }));
      const bos = uyeler.find((u) => !u.ad);
      if (bos) return goster("Her ajanın bir adı olmalı.");
      if (uyeler.filter((u) => u.rol === "lider").length !== 1)
        return goster("Takımda TAM bir lider olmalı.");
      for (const x of satirlar) if (!x.model.kapiOnayi()) return;
      kur.disabled = true; kur.textContent = "Kuruluyor…";
      try {
        const r = await yolla("/api/takim/kur", { ad: ad.value, renk: renk.value, uyeler,
                                                 sablon: secilenSablon });
        bildir(`${r.ad} takımı kuruldu: ${r.ajanlar.join(", ")}`, "iyi");
        D.kanat = r.id; D.kadroSec = null; await yenile(); organizasyonAc(r.id);
      } catch (e) {
        goster("Kurulmadı: " + String(e.message || e));
      } finally { kur.disabled = false; kur.textContent = "Takımı kur"; }
    };
    const vazgec = el("button", "dugme", "Vazgeç"); vazgec.onclick = cekmeceKapat;
    const sat = el("div", "cek-eylem"); sat.append(vazgec, kur);
    c.append(hata, sat);
    baslangic("bos");
  });
}

/* ─────────────── ORGANIZASYON (05.10.2026) ───────────────
   Patron: "her takımın Yönet kısmı olsun; motorları, modelleri, ajanları
   buradan yönetelim" + rakibin "Organizasyon — Şirket ağacı". İki görünüm
   (bütün şirket / tek takım) AYNI uçları kullanır. Kurallar kadro'da
   (açık işi olan taşınmaz, lider taşınmaz, ad geri dönmez); panel yalnız
   ona ulaşan kapı — sunucunun reddi olduğu gibi gösterilir. */

const MOTOR_ETIKET = { claude: "Claude Code", codex: "Codex", gemini: "Antigravity" };
const TENLER = ["#e8b98a", "#d29a6a", "#a8714a", "#7a4e33"];
/* 0 = takımın rengi (varsayılan); öteki kumaşlar karakter seçiminden. */
const KUMASLAR = ["", "#5a7fa8", "#7a5aa8", "#4f8a6a", "#a8584f", "#a8904f", "#3d4a5c", "#b0b8c4"];

/* Karakter "sac:ten:kumas" sıra numaraları; boşsa addan türetilir
   (eski davranış — kalıcı kimlik görsel olarak da kalıcı). */
function karakterRenk(a, kumas) {
  const k = String(a.karakter || "").split(":").map(Number);
  if (k.length === 3 && k.every((n) => Number.isInteger(n))) {
    return { H: SACLAR[k[0] % SACLAR.length], S: TENLER[k[1] % TENLER.length],
             E: GOZ, C: KUMASLAR[k[2] % KUMASLAR.length] || kumas, K: AYAK };
  }
  return { H: SACLAR[_tohum(a.ad || "") % SACLAR.length], S: TEN, E: GOZ, C: kumas, K: AYAK };
}

function karakterSecici(secili, renk, onSec) {
  const kap = el("div", "karakter-liste");
  const secenek = [];
  for (let i = 0; i < 18; i++) secenek.push(`${i % 6}:${Math.floor(i / 6) % 4}:${(i * 3) % 8}`);
  if (secili && !secenek.includes(secili)) secenek.unshift(secili);
  const dugmeler = [];
  const isaretle = (k) => dugmeler.forEach(([d, x]) => d.classList.toggle("secili", x === k));
  const oto = el("button", "karakter-kart", "otomatik");
  oto.type = "button"; oto.title = "Görünüş adından türetilir";
  oto.onclick = () => { isaretle(""); onSec(""); };
  dugmeler.push([oto, ""]); kap.append(oto);
  for (const k of secenek) {
    const d = el("button", "karakter-kart"); d.type = "button";
    d.append(pikselCiz(FIGUR, karakterRenk({ karakter: k }, renk), 3, "sprite-kutu"));
    d.onclick = () => { isaretle(k); onSec(k); };
    dugmeler.push([d, k]); kap.append(d);
  }
  isaretle(secili || "");
  return kap;
}

/* Model seçimi (05.10.2026, patron: "opus yazıyor ama hangi opus belli
   değil"): motorların KENDİ listelerinden GERÇEK adlarla seçim kutusu.
   Listede olmayan mevcut değer gizlenmez, "(şu anki)" diye eklenir. */
const modelAdi = (sec, id) => ((sec && sec.model_ad) || {})[id] || id || "varsayılan";

function modelGirdisi(sec, motor, deger) {
  const g = el("select");
  g.motorYap = (m, secili) => {
    g.innerHTML = "";
    const liste = ((sec.model_secenek || {})[m] || []);
    for (const x of liste) {
      const o = el("option", null, x.ad + (x.not ? `  —  ${x.not}` : ""));
      o.value = x.id; if (x.kapi) o.dataset.kapi = "1"; g.append(o);
    }
    if (secili && !liste.some((x) => x.id === secili)) {
      const o = el("option", null, `${secili} (şu anki)`); o.value = secili; g.prepend(o);
    }
    if (secili) g.value = secili;
  };
  /* Kapı modeli (Astra/Fable) seçilebilir ama bir kez sorulur. */
  g.kapiOnayi = () => {
    const o = g.selectedOptions && g.selectedOptions[0];
    return !(o && o.dataset.kapi) || confirm(
      `${o.textContent.split("  —  ")[0]} pahalı bir kapı modeli: her turda kullanılır ve ` +
      "limiti hızlı bitirir. Yine de bu ajana atansın mı?");
  };
  g.motorYap(motor, deger);
  g.liste = el("span");
  return g;
}

/* ORGANİZASYON PANOSU (05.10.2026, ikinci sürüm). Patron: "tasarım göze
   hitap etmiyor … güzel bir şey ortaya çıkar". Yan çekmece değil TAM EKRAN
   pano: takımlar renkli kartlar, ajanlar avatarlı kartlar (motor rengi,
   durum ışığı, gerçek model adı), düğmeler üstüne gelince; ajan sürüklenip
   başka takıma bırakılarak taşınır. Çekmeceler (Düzenle, Yeni ajan…) bu
   panonun ÜSTÜNDE açılır; kapanınca pano tazelenir. */

const MOTOR_RENK = { claude: "var(--turuncu)", codex: "var(--mavi)", gemini: "var(--yesil)" };
const ORG = { acik: false, odak: "", veri: null, sec: null };

/* PENCERE (05.10.2026, patron: "Murat gibi agent sisteminin İÇİNDE açılsın"):
   panel arkada karartılmış görünür; ✕, Esc, dışarı tıklama ve tarayıcının
   GERİ tuşu kapatır; "Tam sayfa" isteğe bağlı. */
function orgEkrani() {
  let e = document.getElementById("org-ekran");
  if (!e) {
    e = el("div", "org-ekran gizli"); e.id = "org-ekran";
    e.addEventListener("mousedown", (ev) => { if (ev.target === e) orgKapat(); });
    document.body.append(e);
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && ORG.acik && $("#perde").classList.contains("gizli")) orgKapat();
    });
    window.addEventListener("popstate", () => { if (ORG.acik) orgKapat(true); });
  }
  return e;
}
function orgKapat(geriTusuyla) {
  if (!ORG.acik) return;
  ORG.acik = false;
  orgEkrani().classList.add("gizli");
  if (!geriTusuyla && history.state && history.state.org) history.back();
}

async function organizasyonAc(odak) {
  ORG.odak = odak || "";
  D.kadroSec = null;
  try {
    [ORG.veri, ORG.sec] = await Promise.all([al("/api/organizasyon"), kadroSecenek()]);
  } catch (e) { return bildir("organizasyon okunamadı: " + e.message, "kotu"); }
  if (!ORG.acik) history.pushState({ org: 1 }, "");
  ORG.acik = true;
  $("#perde").classList.add("gizli"); D.acikCekmece = null;
  orgCiz();
}
const organizasyonYenile = () => organizasyonAc(ORG.odak);

function orgCiz() {
  const org = ORG.veri, sec = ORG.sec;
  const ekran = orgEkrani();
  ekran.innerHTML = "";
  ekran.classList.remove("gizli");
  ekran.classList.toggle("tam", !!ORG.tam);
  const e = el("div", "org-pencere");
  ekran.append(e);

  const bas = el("div", "org-bas");
  const sol = el("div", "org-bas-sol");
  const hepsi = org.kanatlar.flatMap((k) => k.ajanlar).concat(org.takimsiz);
  sol.append(el("div", "org-ust", "ORGANİZASYON"),
             el("div", "org-baslik", "Takım ve ajan yönetimi — ofisten ayrılmadan"),
             el("div", "org-alt", `${org.kanatlar.length} takım · ${hepsi.length} ajan` +
                (hepsi.some((a) => a.calisiyor) ? ` · ${hepsi.filter((a) => a.calisiyor).length} çalışıyor` : "")));
  // MOTOR DAĞILIMI: limit üç aboneliğe nasıl bölünüyor, tek bakışta.
  const say = {};
  hepsi.forEach((a) => { say[a.motor] = (say[a.motor] || 0) + 1; });
  const cubuk = el("div", "org-dagilim");
  for (const [m, n] of Object.entries(say)) {
    const p = el("div", "org-dagilim-parca");
    p.style.flex = n; p.style.background = MOTOR_RENK[m] || "var(--metin-3)";
    p.title = `${MOTOR_ETIKET[m] || m}: ${n} ajan`;
    cubuk.append(p);
  }
  const lejant = el("div", "org-lejant");
  for (const [m, n] of Object.entries(say)) {
    const l = el("span", "org-lejant-oge");
    const nokta = el("i"); nokta.style.background = MOTOR_RENK[m] || "var(--metin-3)";
    l.append(nokta, `${MOTOR_ETIKET[m] || m} ${n}`);
    lejant.append(l);
  }
  if (hepsi.length) sol.append(cubuk, lejant);
  const sag = el("div", "org-bas-sag");
  const katB = el("button", "org-dugme", "Meslek kataloğu");
  katB.onclick = katalogAc;
  const takB = el("button", "org-dugme ana", "+ Takım");
  takB.onclick = takimEkleAc;
  const tamB = el("button", "org-dugme", ORG.tam ? "Pencere" : "Tam sayfa");
  tamB.onclick = () => { ORG.tam = !ORG.tam; orgCiz(); };
  const kapB = el("button", "org-kapat", "✕"); kapB.title = "Kapat (Esc ya da Geri)";
  kapB.onclick = () => orgKapat();
  sag.append(katB, takB, tamB, kapB);
  bas.append(sol, sag);
  e.append(bas);

  const govde = el("div", "org-govde");
  if (!org.kanatlar.length) {
    const bos = el("div", "org-bos");
    bos.append(el("div", "org-bos-baslik", "Henüz takım yok"),
               el("div", "org-bos-metin",
                 "Bir takım kur: adını ver, şablondan bütün ekibi seç ya da ajanları tek tek ekle. " +
                 "Her ajan motorunu ve modelini mesleğinden alır."));
    const b = el("button", "org-dugme ana", "+ İlk takımı kur"); b.onclick = takimEkleAc;
    bos.append(b);
    govde.append(bos);
  }
  const izgara = el("div", "org-izgara");
  for (const k of org.kanatlar) izgara.append(orgTakim(k, org, sec));
  govde.append(izgara);
  if (org.takimsiz.length) {
    const t = el("div", "org-takim takimsiz");
    t.append(el("div", "org-takim-bas", "TAKIMSIZ AJANLAR — bir takıma sürükle"));
    const kartlar = el("div", "org-kartlar");
    org.takimsiz.forEach((a) => kartlar.append(orgKart(a, null, sec)));
    t.append(kartlar);
    govde.append(t);
  }
  if (org.arsiv.length) {
    const d = el("details", "org-arsiv");
    d.append(el("summary", null,
      `Arşiv · ${org.arsiv.length} ajan — çıkarılanlar; adları geri dönmez, geçmişleri okunur`));
    const kartlar = el("div", "org-kartlar");
    org.arsiv.forEach((a) => kartlar.append(orgKart(a, null, sec, true)));
    d.append(kartlar);
    govde.append(d);
  }
  e.append(govde);
  if (ORG.odak) {
    const h = e.querySelector(`[data-kanat="${ORG.odak}"]`);
    if (h) { h.classList.add("odak"); h.scrollIntoView({ block: "nearest" }); }
  }
}

function orgTakim(k, org, sec) {
  const kutu = el("div", "org-takim");
  kutu.dataset.kanat = k.id;
  kutu.style.setProperty("--kanat-renk", k.renk);
  const bas = el("div", "org-takim-bas");
  const ad = el("div", "org-takim-ad");
  const nokta = el("i", "org-takim-nokta");
  ad.append(nokta, el("span", null, k.ad));
  const calisan = k.ajanlar.filter((a) => a.calisiyor).length;
  const bilgi = el("div", "org-takim-bilgi" + (k.lider ? "" : " uyari"),
    (k.lider ? `lider ${k.lider}` : "lider yok") + ` · ${k.ajanlar.length} ajan` +
    (calisan ? ` · ${calisan} çalışıyor` : ""));
  const solB = el("div"); solB.append(ad, bilgi);
  const menu = el("details", "org-menu");
  menu.append(el("summary", null, "⋯"));
  const liste = el("div", "org-menu-liste");
  const oge = (metin, f, sinif) => {
    const b = el("button", "org-menu-oge" + (sinif ? " " + sinif : ""), metin);
    b.onclick = () => { menu.open = false; f(); };
    liste.append(b);
  };
  oge("Düzenle (ad, renk)", () => takimDuzenleAc(k));
  oge("Şablon olarak kaydet", () => sablonKaydetAc(k));
  oge("Takımı sil", () => takimSil(k), "tehlike");
  menu.append(liste);
  bas.append(solB, menu);
  kutu.append(bas);

  const kartlar = el("div", "org-kartlar");
  const sirali = [...k.ajanlar].sort((a, b) => (b.lider_mi - a.lider_mi));
  for (const a of sirali) kartlar.append(orgKart(a, k, sec));
  const ekle = el("button", "org-kart org-ekle");
  ekle.append(el("span", "org-ekle-arti", "+"),
              el("span", null, k.ajanlar.length ? "Ajan ekle" : "İlk ajan: lider"));
  ekle.onclick = () => ajanEkleAc(k.id);
  kartlar.append(ekle);
  kutu.append(kartlar);

  // SÜRÜKLE-BIRAK ile taşıma: kural sunucuda (açık işi olan, lider taşınmaz).
  kutu.addEventListener("dragover", (ev) => { ev.preventDefault(); kutu.classList.add("birak"); });
  kutu.addEventListener("dragleave", () => kutu.classList.remove("birak"));
  kutu.addEventListener("drop", async (ev) => {
    ev.preventDefault(); kutu.classList.remove("birak");
    const ad_ = ev.dataTransfer.getData("text/ajan");
    if (!ad_ || k.ajanlar.some((x) => x.ad === ad_)) return;
    if (await eylem(`/api/ajan/${encodeURIComponent(ad_)}/tasi`, { kanat: k.id },
                    `${ad_} → ${k.ad}`)) organizasyonYenile();
  });
  return kutu;
}

function orgKart(a, k, sec, arsiv) {
  const kart = el("div", "org-kart" + (a.lider_mi ? " lider" : "") + (arsiv ? " arsiv" : ""));
  kart.style.setProperty("--motor-renk", MOTOR_RENK[a.motor] || "var(--metin-3)");
  if (!arsiv) {
    kart.draggable = true;
    kart.addEventListener("dragstart", (ev) => ev.dataTransfer.setData("text/ajan", a.ad));
  }
  const avatar = el("div", "org-avatar");
  avatar.append(pikselCiz(FIGUR, karakterRenk(a, (k && k.renk) || "#6b7480"), 4, "org-sprite"));
  const durum = a.calisiyor ? ["calisiyor", "çalışıyor"]
              : a.acik_is ? ["acik", `${a.acik_is} açık iş`] : ["bos", "boşta"];
  if (!arsiv) {
    const isik = el("i", "org-isik " + durum[0]); isik.title = durum[1];
    avatar.append(isik);
  }
  const bilgi = el("div", "org-kart-bilgi");
  const ust = el("div", "org-kart-ust");
  ust.append(el("span", "org-kart-ad", a.ad));
  if (a.lider_mi) ust.append(el("span", "org-lider", "LİDER"));
  const md = (sec.motor_durum || {})[a.motor] || {};
  const motor = el("div", "org-kart-motor");
  const nokta = el("i"); motor.append(nokta, MOTOR_ETIKET[a.motor] || a.motor);
  if (md.notlar && md.notlar.length) motor.title = md.notlar.join(" · ");
  bilgi.append(ust, el("div", "org-kart-meslek", a.meslek_baslik), motor,
               el("div", "org-kart-model", modelAdi(sec, a.model) + (a.efor !== "normal" ? ` · ${a.efor}` : "")));
  kart.append(avatar, bilgi);
  if (!arsiv) {
    // Kartın "⋯" menüsü: yazıların üstüne binmez (05.10.2026 gözle denendi).
    const menu = el("details", "org-menu kart-menu");
    menu.append(el("summary", null, "⋯"));
    const e = el("div", "org-menu-liste");
    menu.append(e);
    const b = (metin, ipucu, f, sinif) => {
      const x = el("button", "org-menu-oge" + (sinif ? " " + sinif : ""), metin); x.title = ipucu;
      x.onclick = (ev) => { ev.stopPropagation(); menu.open = false; f(); }; e.append(x);
    };
    b("Düzenle", "Meslek, motor, model, efor, karakter", () => ajanAc(a.ad));
    b("Taşı", "Başka takıma — ya da kartı sürükle", () => tasiAc(a, ORG.veri));
    if (!a.lider_mi && k)
      b("Lider yap", `${k.ad} takımının lideri olsun`, async () => {
        if (await eylem(`/api/ajan/${encodeURIComponent(a.ad)}/lider`, {},
                        `${a.ad} artık ${k.ad} takımının lideri`)) organizasyonYenile();
      });
    b("Çıkar", "Arşive gider; adı geri dönmez", () => ajanCikar(a), "tehlike");
    kart.append(menu);
    kart.ondblclick = () => ajanAc(a.ad);
    kart.title = "Çift tıkla: düzenle · sürükle: başka takıma taşı";
  }
  return kart;
}

function tasiAc(a, org) {
  const hedefler = org.kanatlar.filter((k) => !k.ajanlar.some((x) => x.ad === a.ad));
  cekmeceAc((c) => {
    cekBas(c, "ajanı taşı", a.ad);
    if (!hedefler.length) { c.append(el("div", "form-ipucu", "Taşınacak başka takım yok.")); return; }
    const s = secim(hedefler.map((k) => [k.id, k.ad]), hedefler[0].id);
    formAlan(c, "Hedef takım", s, el("div", "form-ipucu",
      "Hafızası, dersleri ve oturumu onunla gider. Açık işi olan ajan ve takım lideri taşınamaz."));
    const t = el("button", "dugme olumlu", "Taşı");
    t.onclick = async () => {
      if (await eylem(`/api/ajan/${encodeURIComponent(a.ad)}/tasi`, { kanat: s.value },
                      `${a.ad} taşındı`)) organizasyonAc("");
    };
    const geri = el("button", "dugme", "Vazgeç"); geri.onclick = () => organizasyonAc("");
    const sat = el("div", "cek-eylem"); sat.append(t, geri); c.append(sat);
  });
}

async function ajanCikar(a) {
  if (!confirm(`${a.ad} takımdan çıkarılsın mı?\n\nArşive gider: adı geri dönmez, ` +
               "geçmişi ve dersleri okunur kalır. Açık işi varsa çıkarılamaz.")) return;
  if (await eylem(`/api/ajan/${encodeURIComponent(a.ad)}/cikar`, {}, `${a.ad} arşive alındı`))
    organizasyonYenile();
}

function takimDuzenleAc(k) {
  cekmeceAc((c) => {
    cekBas(c, "takımı düzenle", k.ad);
    const ad = el("input"); ad.value = k.ad;
    const renk = el("input"); renk.type = "color"; renk.value = k.renk;
    const sira = el("div", "form-sira");
    formAlan(sira, "Takım adı", ad); formAlan(sira, "Renk", renk);
    c.append(sira);
    // TAKIM KLASORU (06.10): takimin ajanlari bu klasorde calisir.
    const klasor = el("input"); klasor.value = k.klasor || "";
    klasor.placeholder = "boş = projenin klasörü";
    const ks = el("div", "form-sira"); formAlan(ks, "Klasör", klasor); c.append(ks);
    c.append(el("div", "hp-not", k.kendi_klasoru
      ? "Takımın kendi klasörü. Çalışan işi varken değiştirilemez."
      : "Takım şu an projenin klasörünü kullanıyor. Kendi klasörünü yazabilirsin."));
    // TAKIM KITI (06.10): her iste kendiliginden; yasak kelime teslimde taranir.
    const kit = k.kit || { bitti_tanimi: [], logo: "", renkler: "", ses_tonu: "", yasak: [] };
    const bt = el("textarea"); bt.rows = 3; bt.value = (kit.bitti_tanimi || []).join("\n");
    bt.placeholder = "her satır bir şart — örn. testler geçer · mobilde de çalışır";
    const bs = el("div", "form-sira"); formAlan(bs, "Bitti tanımı (her işte)", bt); c.append(bs);
    const ton = el("input"); ton.value = kit.ses_tonu || ""; ton.placeholder = "örn. samimi, siz diye hitap";
    const rk = el("input"); rk.value = kit.renkler || ""; rk.placeholder = "örn. #1F6FEB lacivert, #F5A623 turuncu";
    const lg = el("input"); lg.value = kit.logo || ""; lg.placeholder = "logo dosyasının yolu";
    const ys = el("input"); ys.value = (kit.yasak || []).join(", "); ys.placeholder = "virgülle: ucuz, bedava";
    const ms = el("div", "form-sira");
    formAlan(ms, "Ses tonu", ton); formAlan(ms, "Renkler", rk);
    c.append(ms);
    const ms2 = el("div", "form-sira");
    formAlan(ms2, "Logo", lg); formAlan(ms2, "Yasak kelimeler", ys);
    c.append(ms2);
    c.append(el("div", "hp-not", "Yasak kelime geçen teslimi lider geri gönderir: ofis işin dosyalarını ve kanıtlarını tarar."));
    const kaydet = el("button", "dugme olumlu", "Kaydet");
    kaydet.onclick = async () => {
      const govde = { ad: ad.value, renk: renk.value, bitti_tanimi: bt.value,
                      marka: { ses_tonu: ton.value, renkler: rk.value, logo: lg.value, yasak: ys.value } };
      if (klasor.value.trim() !== (k.klasor || "")) govde.klasor = klasor.value.trim();
      if (await eylem(`/api/kanat/${k.id}/duzenle`, govde,
                      (x) => `takım: ${x.ad}`)) organizasyonAc(k.id);
    };
    const geri = el("button", "dugme", "Vazgeç"); geri.onclick = () => organizasyonAc(k.id);
    const sat = el("div", "cek-eylem"); sat.append(kaydet, geri); c.append(sat);
  });
}

async function takimSil(k) {
  const n = k.ajanlar.length;
  if (!confirm(`${k.ad} takımı silinsin mi?\n\n` +
               (n ? `İçindeki ${n} ajan ARŞİVE alınır (adları geri dönmez, geçmişleri okunur). `
                  : "") +
               "Açık işi olan takım silinmez. Kapanmış işlerin kaydı durur.")) return;
  if (await eylem(`/api/kanat/${k.id}/sil`, { ajanlarla: true },
                  (x) => `takım silindi: ${x.silindi}`)) {
    if (D.kanat === k.id) D.kanat = "";
    organizasyonAc("");
  }
}

function sablonKaydetAc(k) {
  cekmeceAc((c) => {
    cekBas(c, "şablon olarak kaydet", k.ad);
    c.append(el("div", "form-ipucu",
      "Takımın bugünkü meslekleri (lider hariç) şablon olur. Yeni takım kurarken seçebilirsin; " +
      "motor ve model o gün meslek kataloğundan gelir."));
    const ad = el("input"); ad.value = k.ad.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const baslik = el("input"); baslik.value = k.ad;
    const aciklama = el("input"); aciklama.placeholder = "ne iş yapar (isteğe bağlı)";
    formAlan(c, "Şablon adı (küçük harf, tire)", ad);
    formAlan(c, "Başlık", baslik);
    formAlan(c, "Açıklama", aciklama);
    const kaydet = el("button", "dugme olumlu", "Kaydet");
    kaydet.onclick = async () => {
      if (await eylem("/api/sablon/kaydet",
          { kanat: k.id, ad: ad.value, baslik: baslik.value, aciklama: aciklama.value },
          (x) => `şablon kaydedildi: ${x.baslik} (${x.roller.join(", ")})`)) organizasyonAc(k.id);
    };
    const geri = el("button", "dugme", "Vazgeç"); geri.onclick = () => organizasyonAc(k.id);
    const sat = el("div", "cek-eylem"); sat.append(kaydet, geri); c.append(sat);
  });
}

async function katalogAc() {
  let kat, sec;
  D.kadroSec = null;
  try { [kat, sec] = await Promise.all([al("/api/katalog"), kadroSecenek()]); }
  catch (e) { return bildir("katalog okunamadı: " + e.message, "kotu"); }
  cekmeceAc((c) => {
    c.classList.add("genis");
    cekBas(c, "ayar · meslek kataloğu", "Hangi meslek hangi motor ve modelle çalışır");
    c.append(el("div", "form-ipucu",
      "Yeni işe alınan ajan motorunu ve modelini buradan alır. Mevcut ajanlar DEĞİŞMEZ — " +
      "onları Organizasyon'dan tek tek değiştir."));
    const geri = el("button", "dugme", "← Organizasyon"); geri.onclick = () => organizasyonAc("");
    const ust = el("div", "cek-eylem"); ust.append(geri); c.append(ust);
    const kurulu = Object.entries(sec.motor_durum || {}).filter(([, d]) => d.kurulu).map(([m]) => m);
    for (const kategori of sec.kategoriler) {
      c.append(el("div", "cek-etiket katalog-kategori", (sec.kategori_baslik[kategori] || kategori).toUpperCase()));
      for (const r of kat.filter((x) => x.kategori === kategori)) {
        const sat = el("div", "katalog-satir");
        const motor = secim(kurulu.map((m) => [m, MOTOR_ETIKET[m] || m]), r.motor);
        const model = modelGirdisi(sec, r.motor, r.model);
        motor.onchange = () => model.motorYap(motor.value);
        const kaydet = el("button", "dugme kucuk olumlu", "Kaydet");
        kaydet.onclick = async () => {
          if (!model.kapiOnayi()) return;
          if (await eylem("/api/katalog", { rol: r.rol, motor: motor.value, model: model.value },
                          (x) => `${r.baslik}: ${MOTOR_ETIKET[x.motor] || x.motor} · ${modelAdi(sec, x.model)}`)) katalogAc();
        };
        const ad = el("div", "katalog-ad", r.baslik);
        if (r.ayar) ad.append(el("span", "etiket", "değiştirildi"));
        sat.append(ad, motor, model, model.liste, kaydet);
        if (r.ayar) {
          const v = el("button", "dugme kucuk", "Varsayılan");
          v.title = `Varsayılan: ${MOTOR_ETIKET[r.varsayilan.motor] || r.varsayilan.motor} · ${modelAdi(sec, r.varsayilan.model)}`;
          v.onclick = async () => {
            if (await eylem("/api/katalog", { rol: r.rol, motor: "", model: "" },
                            `${r.baslik}: varsayılana döndü`)) katalogAc();
          };
          sat.append(v);
        }
        c.append(sat);
      }
    }
  });
}

/* YENİ AJAN (rakipteki "Yeni çalışan" penceresi): takım · ad · meslek
   (katalog) · karakter · AI motoru (dürüst durum) · model · efor.
   Meslek seçilince motor ve model KATALOGDAN gelir; insan değiştirebilir. */
async function ajanEkleAc(kanatId) {
  let sec;
  D.kadroSec = null;
  try { sec = await kadroSecenek(); }
  catch (e) { return bildir("kadro seçenekleri okunamadı: " + e.message, "kotu"); }
  let sablonlar = [];
  try { sablonlar = await al("/api/sablonlar"); } catch (e) { /* form yine açılır */ }
  if (typeof kanatId !== "string") kanatId = D.kanat || "";
  cekmeceAc((c) => {
    c.classList.add("genis");
    cekBas(c, "organizasyon", "Yeni ajan");
    if (!sec.kanatlar.length) {
      const u = el("div", "cek-uyari");
      u.append(el("b", null, "Henüz takımın yok. "),
               "Ajanlar bir takımda çalışır ve her takımın bir lideri olur — önce takımı kur.");
      const tk = el("button", "dugme olumlu", "+ Takım kur"); tk.onclick = takimEkleAc;
      u.append(tk);
      c.append(u);
    }
    const takim = secim([["", "takımsız"]].concat(sec.kanatlar.map((k) => [k.id, k.ad])), kanatId);
    const bosMu = () => !!takim.value && !D.ofis.ajanlar.some((x) => x.kanat_id === takim.value);
    formAlan(c, "Takım", takim);

    const ad = el("input"); ad.placeholder = "ajanın adı (ör. ayna, Ömer Can)";
    // AD → ADRES: sistem adı adres olarak kullanır (küçük harf, tire). Türkçe
    // harf ve boşluk kendiliğinden çevrilir; sonuç yazılır.
    const adresYap = (x) => x.toLocaleLowerCase("tr").replace(/ç/g, "c").replace(/ğ/g, "g")
      .replace(/ı/g, "i").replace(/ö/g, "o").replace(/ş/g, "s").replace(/ü/g, "u")
      .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    const adIpucu = el("div", "form-ipucu");
    const kullanilan = new Set((D.ofis.ajanlar || []).map((x) => x.ad));
    ad.oninput = () => {
      const a_ = adresYap(ad.value);
      adIpucu.className = "form-ipucu" + (kullanilan.has(a_) ? " uyari" : "");
      adIpucu.textContent = !ad.value.trim() ? ""
        : kullanilan.has(a_) ? `“${a_}” zaten kullanılıyor — başka ad seç.`
        : a_ !== ad.value.trim() ? `Adresi: ${a_}` : "";
    };
    formAlan(c, "Ajan adı", ad, adIpucu);
    c.append(el("div", "form-ipucu",
      "Ad bir kimliktir ve geri dönmez: sicil ve dersler bu adda birikir (arşivdeki adlar da kullanılamaz)."));

    let meslek = "", motor = "", karakter = "";
    const mesKap = el("div", "meslek-liste");
    const mesDug = {};
    const oneri = el("div", "form-ipucu");
    const model = modelGirdisi(sec, "", "");
    const efor = secim(sec.eforlar.map((e) => [e, e]), "normal");
    const lider = el("input"); lider.type = "checkbox";
    const motKap = el("div", "motor-liste");
    const motDug = {};
    const motorSec = (m, mdl) => {
      motor = m;
      Object.entries(motDug).forEach(([x, d]) => d.classList.toggle("secili", x === m));
      model.motorYap(m, mdl || "");
    };
    for (const [m, d] of Object.entries(sec.motor_durum || {})) {
      const b = el("button", "motor-kart" + (d.kurulu ? "" : " kapali")); b.type = "button";
      b.append(el("div", "motor-kart-ad", d.etiket || m),
               el("div", "motor-kart-durum durum-" + d.durum.replace(/\s+/g, "-"), d.durum));
      b.title = d.notlar && d.notlar.length ? d.notlar.join(" · ") : "eksik bilinen özellik yok";
      b.disabled = !d.kurulu;
      b.onclick = () => { motorSec(m, ""); oneri.textContent = "Motor elle seçildi; model boşsa mesleğin kademesinden."; };
      motDug[m] = b; motKap.append(b);
    }
    const meslekSec = (r) => {
      meslek = r;
      Object.entries(mesDug).forEach(([x, d]) => d.classList.toggle("secili", x === r));
      const k = (sec.katalog || {})[r] || {};
      const md = (sec.motor_durum || {})[k.motor] || {};
      const baslik = (sec.roller.find((x) => x.ad === r) || {}).baslik || r;
      if (md.kurulu) {
        motorSec(k.motor, k.model);
        oneri.textContent = `Meslekten önerildi: ${baslik} → ${MOTOR_ETIKET[k.motor] || k.motor} · ${modelAdi(sec, k.model)}`;
        oneri.className = "form-ipucu";
      } else {
        const ilk = Object.keys(motDug).find((x) => !motDug[x].disabled) || "";
        motorSec(ilk, "");
        oneri.textContent = `Katalogdaki motor (${k.motor || "?"}) kurulu değil; ${MOTOR_ETIKET[ilk] || ilk} seçildi.`;
        oneri.className = "form-ipucu uyari";
      }
      if (r === "lider" && bosMu()) lider.checked = true;
    };
    for (const kategori of sec.kategoriler) {
      mesKap.append(el("div", "meslek-kategori", (sec.kategori_baslik[kategori] || kategori).toUpperCase()));
      const izgara = el("div", "meslek-izgara");
      for (const r of sec.roller.filter((x) => x.kategori === kategori)) {
        const b = el("button", "meslek-kart"); b.type = "button";
        b.append(el("div", "meslek-kart-ad", r.baslik || r.ad), el("div", "meslek-kart-ozet", kes(r.ozet, 70)));
        if (r.uyari) b.title = r.uyari;
        b.onclick = () => meslekSec(r.ad);
        mesDug[r.ad] = b; izgara.append(b);
      }
      mesKap.append(izgara);
    }
    formAlan(c, "Meslek (katalog)", mesKap);
    const takimRengi = () => ((D.ofis.kanatlar || []).find((k) => k.id === takim.value) || {}).renk || "#6b7480";
    formAlan(c, "Karakter", karakterSecici("", takimRengi(), (k) => { karakter = k; }));
    formAlan(c, "AI motoru", motKap);
    const sira = el("div", "form-sira");
    formAlan(sira, "Model", model); sira.append(model.liste);
    formAlan(sira, "Efor", efor);
    c.append(sira, oneri);
    formAlan(c, "Bu takımın lideri", lider, el("div", "form-ipucu",
      "Takım başına TEK lider — ikinci lider reddedilir. Boş takımda ilk ajan lider olmalı."));
    meslekSec(bosMu() ? "lider" : "arayuz");
    takim.onchange = () => { if (bosMu()) { meslekSec("lider"); lider.checked = true; } };

    const hata = el("div", "cek-hata gizli");
    const goster = (m) => { hata.textContent = m; hata.classList.remove("gizli"); hata.scrollIntoView({ block: "nearest" }); };
    const ekle = el("button", "dugme olumlu", "Ekle");
    ekle.onclick = async () => {
      hata.classList.add("gizli");
      const adres = adresYap(ad.value);
      if (!adres) { goster("Ajan adı boş — bir ad yaz."); ad.scrollIntoView({ block: "center" }); return ad.focus(); }
      if (!meslek) return goster("Bir meslek seç.");
      if (!model.kapiOnayi()) return;
      ekle.disabled = true; ekle.textContent = "Ekleniyor…";
      try {
        const x = await yolla("/api/ajan", {
          ad: adres, meslek, motor, model: model.value, efor: efor.value,
          kanat: takim.value, lider: lider.checked, karakter });
        bildir(`${x.ad} eklendi: ${x.meslek} · ${MOTOR_ETIKET[x.motor] || x.motor} · ${modelAdi(sec, x.model)}`, "iyi");
        D.kadroSec = null; await yenile(); organizasyonAc(takim.value || "");
      } catch (e) {
        goster("Eklenmedi: " + String(e.message || e));
      } finally { ekle.disabled = false; ekle.textContent = "Ekle"; }
    };
    const vazgec = el("button", "dugme", "Vazgeç"); vazgec.onclick = cekmeceKapat;
    const sat = el("div", "cek-eylem"); sat.append(vazgec, ekle);
    c.append(hata, sat);
  });
}

async function gorevAc(no) {
  const g = await al("/api/gorev/" + no);
  D.acikCekmece = { tur: "gorev", no };
  cekmeceAc((c) => {
    cekBas(c, `#${g.no} · ${g.durum}` + (g.sahip ? ` · ${g.sahip}` : ""), g.baslik);
    cekAlan(c, "BU İŞ NİÇİN VAR", g.neden);
    cekAlan(c, "BAĞLI OLDUĞU ÜST HEDEF", g.ana_hedef);
    cekAlan(c, "KABUL ÖLÇÜTÜ", g.kabul_olcutu);
    cekAlan(c, "YAZMA ALANI (KİLİTLİ)", g.yazma_alani.join(" · ") || "—");
    // IZINLER: patronun sozunden cikan (ya da kalici) izinler GORUNUR ve
    // tek tikla kaldirilir. Ofis yanlis anladiysa insan hemen gorsun.
    c.append(el("div", "cek-etiket", "SORULMADAN GEÇECEKLER (senin iznin)"));
    if (!g.izinler || !g.izinler.length)
      c.append(el("div", "cek-deger",
        "Yok — riskli adımlar (push, deploy, silme, para) sana sorulur."));
    for (const iz of (g.izinler || [])) {
      const kk = el("div", "cek-eylem");
      const ne = iz.gorev_id ? `senin sözün: "${kes(iz.alinti, 90)}"`
                             : `kalıcı izin — ${kes(iz.gerekce, 90)}`;
      kk.append(el("span", "etiket", iz.desen), el("span", "sonuk", ne));
      const kb = el("button", "dugme olumsuz", "Kaldır");
      kb.title = "Bu eylem bundan sonra yine sana sorulur.";
      kb.onclick = async () => {
        const r = await eylem(`/api/izin/${iz.id}/kaldir`,
          { sebep: "panelden kaldırıldı" }, (r) => `izin kaldırıldı: ${r.desen}`);
        if (r) gorevAc(g.no);
      };
      kk.append(kb);
      c.append(kk);
    }
    if (g.izinler && g.izinler.length)
      c.append(el("div", "sonuk",
        "Para ve silme izinle açılmaz; her seferinde sorulur."));
    // TESLIM PUANI (06.10, E78): biten is 1-5. 3 ve alti gerekce ister; gerekce
    // ajanin dersi olur, puan karneye gider.
    if (g.durum === "bitti") {
      c.append(el("div", "cek-etiket", "PUANIN"));
      const ps = el("div", "cek-eylem");
      const gr = el("input");
      gr.placeholder = "gerekçe (3 ve altı için zorunlu — ajan ders alır)";
      if (g.puan) gr.value = g.puan.gerekce || "";
      for (let n = 1; n <= 5; n++) {
        const b = el("button", "dugme" + (g.puan && g.puan.puan === n ? " olumlu" : ""), String(n));
        b.title = n <= 3 ? "Gerekçe zorunlu; ajanın ders siciline girer." : "İşe yaradı.";
        b.onclick = async () => {
          if (n <= 3 && !gr.value.trim()) { gr.focus(); return bildir("3 ve altı için gerekçe yaz", "uyari"); }
          const r = await eylem(`/api/gorev/${g.no}/puan`, { puan: n, gerekce: gr.value },
                                (r) => `#${g.no}: ${r.puan}/5` + (r.ders ? " — ajana ders olarak yazıldı" : ""));
          if (r) gorevAc(g.no);
        };
        ps.append(b);
      }
      ps.append(gr);
      c.append(ps);
    }
    if (g.onizleme) {
      const ozs = el("div", "cek-eylem");
      const oz = el("button", "dugme", "Önizlemeyi aç");
      oz.title = "İşin klasöründeki site bu bilgisayarda açılır.";
      oz.onclick = () => onizlemeAc(g.no);
      ozs.append(oz); c.append(ozs);
    }
    // IS BASINA GIT KAYDI (06.10): projenin git deposunda bu isin kaydi.
    if (g.git_kaydi) {
      c.append(el("div", "cek-etiket", "GIT KAYDI"));
      const gs = el("div", "cek-eylem");
      gs.append(el("span", "etiket", g.git_kaydi.slice(0, 10)));
      const gb = el("button", "dugme olumsuz", "Bu işi geri al");
      gb.title = "git revert: işin değişikliklerini geri alan YENİ bir kayıt açar; geçmiş silinmez.";
      gb.onclick = async () => {
        if (!confirm(`#${g.no} işinin değişiklikleri geri alınsın mı?\n\nYeni bir git kaydı açılır, geçmiş silinmez.`)) return;
        const r = await eylem(`/api/gorev/${g.no}/git_geri_al`, {},
                              (r) => `#${g.no} geri alındı (${r.yeni_kayit.slice(0, 10)})`);
        if (r) gorevAc(g.no);
      };
      gs.append(gb);
      c.append(gs);
    }
    if (g.govde) cekAlan(c, "TARİF", g.govde);
    if (g.brifing)
      cekAlan(c, "BRİFİNG",
              `${g.brifing.ajan_ad} — ${g.brifing.jeton_tahmini} jeton`);

    c.append(el("div", "cek-etiket", `KANITLAR (${g.kanitlar.length})`));
    if (!g.kanitlar.length)
      c.append(el("div", "cek-deger", "Kanıt yok — bu iş kapanamaz."));
    for (const k of g.kanitlar) {
      const kk = el("div", "cek-kutu");
      const kb = el("div", "oge-bas");
      kb.append(el("span", "etiket", k.tur), el("span", null, k.baslik),
                el("span", null, k.ekleyen));
      kk.append(kb);
      if (k.icerik) kk.append(el("pre", null, k.icerik));
      c.append(kk);
    }
    if (g.rapor) {
      c.append(el("div", "cek-etiket", "SON RAPOR"));
      const kk = el("div", "cek-kutu");
      kk.append(el("pre", null, kes(g.rapor.govde, 1400)));
      c.append(kk);
    }
    // DEVRAL: calisan ya da hazir bekleyen iste (durdurulmus is dahil).
    if (devralinmisMi(g.no)) {
      c.append(el("div", "cek-etiket", "BU İŞ SENDE (terminalde)"));
      const sat = el("div", "cek-eylem");
      const nt = el("input");
      nt.placeholder = "Ajana kısa not (isteğe bağlı)";
      const gv = el("button", "dugme olumlu", "Ofise geri ver");
      gv.onclick = async () => { gv.disabled = true; await geriVer(g.no, nt.value); cekmeceKapat(); };
      sat.append(nt, gv);
      c.append(sat);
    } else if (["calisiyor", "hazir"].includes(g.durum)) {
      c.append(el("div", "cek-etiket", "DEVRAL"));
      const sat = el("div", "cek-eylem");
      const dv = el("button", "dugme", "⌨ Devral — ajanın oturumunu terminalde aç");
      dv.title = "Ajanın turu koşuyorsa önce Durdur. Ajan sen geri verene kadar çalışmaz.";
      dv.onclick = async () => { await devralBaslat(g.no); cekmeceKapat(); };
      sat.append(dv);
      if (D.devralPty && D.devralPty !== "hazir")
        sat.append(el("div", "sonuk", D.devralPty));
      c.append(sat);
    }
    // IPTAL: yalniz bitmemis iste. Sebep ZORUNLU; birakilan kilitler
    // sunucuda OLCULUR ve soylenir (iddia edilmez).
    if (!["bitti", "iptal"].includes(g.durum)) {
      c.append(el("div", "cek-etiket", "İŞİ DURDUR"));
      const sat = el("div", "cek-eylem");
      const sb = el("input");
      sb.placeholder = "İptal sebebi (zorunlu)";
      const ip = el("button", "dugme olumsuz", "İptal et");
      ip.title = "İşi iptal eder ve yazma kilitlerini bırakır. Geri alınmaz.";
      ip.onclick = async () => {
        if (!sb.value.trim()) {
          sb.placeholder = "Sebep zorunlu — 'bu iş neden yarım kaldı' cevapsız kalmasın";
          return sb.focus();
        }
        const r = await eylem(`/api/gorev/${g.no}/iptal`, { sebep: sb.value },
          (r) => `#${r.no} iptal edildi` +
                 (r.birakilan && r.birakilan.length ? " · kilit bırakıldı: " + r.birakilan.join(", ") : "") +
                 (r.kalan && r.kalan.length ? " · DİKKAT hâlâ kilitli: " + r.kalan.join(", ") : ""));
        if (r) cekmeceKapat();
      };
      sat.append(sb, ip);
      c.append(sat);
    }
  });
}

/* ─────────────── faaliyet: tek satır + günlük ─────────────── */

function gunlukSatiri(o) {
  const x = olayOku(o);
  if (!x) return null;
  const s = el("div", "gunluk-satir");
  s.dataset.onem = x.onem;
  s.append(el("div", "gunluk-saat", saat(o.olusturuldu)),
           el("div", "gunluk-kim", x.kim));
  const ne = el("div", "gunluk-ne");
  ne.textContent = x.ne + (x.ayrinti ? " — " + kes(x.ayrinti, 150) : "");
  s.append(ne);
  if (o.gorev_no) { s.style.cursor = "pointer";
                    s.onclick = () => gorevAc(o.gorev_no); }
  return s;
}

function faaliyetGoster(o) {
  const x = olayOku(o);
  if (!x) return;
  const m = $("#faaliyet-metin");
  m.innerHTML = "";
  m.append(el("b", null, x.kim), document.createTextNode(" " + x.ne +
           (x.ayrinti ? " — " + kes(x.ayrinti, 90) : "")));
}

function gunlugeEkle(o) {
  const satir = gunlukSatiri(o);
  if (!satir) return;
  const akis = $("#gunluk-akis");
  akis.append(satir);
  while (akis.children.length > 300) akis.firstChild.remove();
  if ($("#gunluk").classList.contains("gizli")) return;
  akis.scrollTop = akis.scrollHeight;
}

/* ─────────────── canlı akış ─────────────── */

// Panelin tazelenmesi gereken olaylar. Akan cikti (cikti/metin) buraya
// GIRMEZ: her jetonda paneli yeniden cizmek, paneli kullanilmaz yapar.
// "kabin": ofis tarayiciyi AJAN icin actiginda panel ANINDA gosterir (02.10.2026).
const TAZELE = new Set(["kabin_acildi", "kabin_kapandi", "kapandi", "sahiplenildi", "incelemede", "birakildi",
  "ret", "soru", "cevap", "onay_istendi", "onay_cevabi", "gorev_acildi",
  "kanit", "karar", "tur_ozeti", "olgu", "olgu_guncellendi", "ise_alindi",
  // Kural her brifinge girer: eklenince/kaldirilinca Hafiza o an tazelenmeli.
  "kural",
  // Tur bitince diskteki fark olculur; Kod bolumu o anda tazelenmeli.
  // Tazelemeseydik bolum bir sonraki yenilemeye kadar BAYAT kalirdi --
  // ve bayat bir olcum, olcum degildir.
  "degisim"]);

function baglan() {
  const kaynak = new EventSource("/api/akis?sonra=" + D.sonOlay);
  kaynak.onopen = () => $(".canli-nokta").classList.remove("kopuk");
  kaynak.onmessage = (m) => {
    const o = JSON.parse(m.data);
    D.sonOlay = o.id;
    D.olaylar.push(o);
    if (D.olaylar.length > 600) D.olaylar.shift();
    faaliyetGoster(o);
    gunlugeEkle(o);
    panoyaAkit(o);
    if (TAZELE.has(o.tur)) yenile();
    // Bir dosyaya ILK kez dokunuldu: yoklamayi beklemeden goster.
    else if (o.tur === "dosya_canli") canliTazele();
  };
  kaynak.onerror = () => {
    $(".canli-nokta").classList.add("kopuk");
    kaynak.close();
    setTimeout(baglan, 3000);
  };
}

/* ─────────────── yerleşim: sürükle · bırak · boyutlandır ───────────────

   Kullanici (23.09.2026): *"Muratify'da terminal, ofis, tarayici,
   hafiza, raporlar... her sey surukleyip yer degistirebiliyor,
   boyutlandirilabiliyor."* Rakibin urun sayfasi ve surum notlari
   okundu: dort yonde bolme, sekmeyi baska grubun govdesine birakma,
   bolucuyu surukleyerek boyutlandirma, grubu daraltma; v0.2.32'de
   bozuk duzen yuzunden "paneller kayboldu" hatasi yasanmis ve duzen
   acilista kendini ONARIR olmus.

   MODEL: sutun -> yigin -> sekme. Iki katman; rakibin sinirsiz dosema
   agaci DEGIL. Sinir bilinclidir: iki katman izleme yuzeyinin
   ihtiyacini karsiliyor ve her durum bir sayi dizisi gibi okunur.
   Gerekirse ic ice bolme sonra eklenir -- olcmeden karmasiklik yok.

   PANO ICERIGI YENIDEN CIZILMEZ, TASINIR: `#pano-depo`daki dugumler
   yerine konur. Terminal akisi, kaydirma konumu, kabin karesi kaybolmaz.

   DUZEN TARAYICIDA SAKLANIR (izleyicinin kendi tercihi, ofisin verisi
   degil) ve OKUNURKEN ONARILIR: bilinmeyen pano atilir, eksik pano
   eklenir, bozuk sayi varsayilana doner. Saklanan bir duzen asla bir
   panoyu KAYBETTIREMEZ -- rakibin yasadigi hata tam buydu. */

const PANOLAR = {
  ofis:     { ad: "Ofis",     sayac: "sayac-ofis" },
  terminal: { ad: "Terminal", sayac: "sayac-canli" },
  sohbet:   { ad: "Takım sohbeti", sayac: "" },
  konsol:   { ad: "Konsol",   sayac: "" },
  kod:      { ad: "Kod",      sayac: "sayac-kod" },
  tarayici: { ad: "Tarayıcı", sayac: "sayac-kabin" },
  gorevler: { ad: "Görevler", sayac: "sayac-tahta" },
  durum:    { ad: "Durum",    sayac: "" },
  raporlar: { ad: "Raporlar", sayac: "" },
  hafiza:   { ad: "Hafıza",   sayac: "" },
  kararlar: { ad: "Kararlar", sayac: "" },
  yetenek:  { ad: "Yetenek",  sayac: "" },
  denetim:  { ad: "Denetim",  sayac: "" },
};

/* Varsayilan, bugune kadarki sabit duzenin AYNISI: kullanicinin
   alistigi ekran sifirlamada geri gelir. */
function yerlesimVarsayilan() {
  return {
    surum: 1,
    sutunlar: [
      { gen: 1.0, kapali: false,
        yiginlar: [{ yuk: 1, panolar: ["ofis"], secili: "ofis" }] },
      { gen: 1.35, kapali: false,
        yiginlar: [{ yuk: 0.66, panolar: ["terminal", "konsol"], secili: "terminal" },
                   { yuk: 0.34, panolar: ["kod"], secili: "kod" }] },
      // TAKIM SOHBETI KENDI SUTUNUNDA, TAM BOY (29.09.2026, kullanici:
      // "takim sohbetinin altinda kod ne alaka, murat gibi degil"). Onceden
      // terminalle ayni sekme yiginindaydi ve altinda Kod duruyordu: sohbet
      // gorunmek icin sekme degistirmek istiyordu. Rakipte de ayri sutun.
      { gen: 1.0, kapali: false,
        yiginlar: [{ yuk: 1, panolar: ["sohbet"], secili: "sohbet" }] },
      { gen: 1.6, kapali: false,
        yiginlar: [{ yuk: 1, panolar: ["tarayici"], secili: "tarayici" }] },
      { gen: 0.8, kapali: false,
        yiginlar: [{ yuk: 1, secili: "gorevler",
                     panolar: ["gorevler", "durum", "raporlar", "hafiza", "kararlar",
                               "yetenek", "denetim"] }] },
    ],
  };
}

/* Saklanan (ya da tasinmis) duzeni GECERLI bir duzene cevirir.
   Asla atmaz, asla bir panoyu kaybettirmez. */
function yerlesimOnar(y) {
  const sayi = (v, vars) => (typeof v === "number" && isFinite(v) && v > 0 ? v : vars);
  const gorulen = new Set();
  const sutunlar = [];
  const kaynak = y && Array.isArray(y.sutunlar) ? y.sutunlar : [];
  for (const s of kaynak) {
    if (!s || !Array.isArray(s.yiginlar)) continue;
    const yiginlar = [];
    for (const g of s.yiginlar) {
      if (!g || !Array.isArray(g.panolar)) continue;
      // `gorulen` suzgecin ICINDE isaretlenir: ayni yigindaki tekrar da
      // (["ofis","ofis"]) duser -- disarida isaretlemek onu kaciriyordu.
      const panolar = g.panolar.filter((p) => {
        if (typeof p !== "string" || !Object.prototype.hasOwnProperty.call(PANOLAR, p)
            || gorulen.has(p)) return false;
        gorulen.add(p);
        return true;
      });
      if (!panolar.length) continue;
      yiginlar.push({ yuk: sayi(g.yuk, 1), panolar,
                      secili: panolar.includes(g.secili) ? g.secili : panolar[0] });
    }
    if (yiginlar.length)
      sutunlar.push({ gen: sayi(s.gen, 1), kapali: s.kapali === true, yiginlar });
  }
  if (!sutunlar.length) return yerlesimVarsayilan();
  // EKSIK PANO EKLENIR: yeni surumde gelen ya da bozulmada dusen pano
  // son yiginin sekmesi olarak geri gelir -- kaybolmaz.
  const son = sutunlar[sutunlar.length - 1].yiginlar;
  for (const p of Object.keys(PANOLAR))
    if (!gorulen.has(p)) son[son.length - 1].panolar.push(p);
  return { surum: 1, sutunlar };
}

/* Bir panoyu tasir. `hedef` = { sutun, yigin, yer }:
     sekme  -> o yiginin sekmesi olur
     ust/alt -> o yigini boler, yeni yigin ustte/altta
     sol/sag -> o sutunun yaninda YENI sutun
   Saf islev: yeni duzen doner, verileni degistirmez. Anlamsiz hareket
   (tek panolu yigini kendi kenarina birakmak) duzeni DEGISTIRMEZ. */
function panoTasi(y, pano, hedef) {
  const k = JSON.parse(JSON.stringify(yerlesimOnar(y)));
  const hs = k.sutunlar[hedef.sutun];
  const hy = hs && hs.yiginlar[hedef.yigin];
  if (!hs || (!hy && !["sol", "sag"].includes(hedef.yer)))
    return yerlesimOnar(y);
  let kaynakYigin = null;
  for (const s of k.sutunlar)
    for (const g of s.yiginlar)
      if (g.panolar.includes(pano)) kaynakYigin = g;
  if (!kaynakYigin) return yerlesimOnar(y);
  if (hedef.yer === "sekme") {
    if (hy === kaynakYigin) { hy.secili = pano; return yerlesimOnar(k); }
  }
  kaynakYigin.panolar = kaynakYigin.panolar.filter((p) => p !== pano);
  if (kaynakYigin.secili === pano) kaynakYigin.secili = kaynakYigin.panolar[0];
  const yeniYigin = { yuk: 1, panolar: [pano], secili: pano };
  if (hedef.yer === "sekme") {
    hy.panolar.push(pano); hy.secili = pano;
  } else if (hedef.yer === "ust" || hedef.yer === "alt") {
    if (!hy.panolar.length) return yerlesimOnar(y);       // kendi kenarina
    yeniYigin.yuk = hy.yuk / 2; hy.yuk = hy.yuk / 2;
    const i = hs.yiginlar.indexOf(hy);
    hs.yiginlar.splice(hedef.yer === "ust" ? i : i + 1, 0, yeniYigin);
  } else if (hedef.yer === "sol" || hedef.yer === "sag") {
    const bosaldi = hs.yiginlar.every((g) => !g.panolar.length);
    if (bosaldi) return yerlesimOnar(y);                   // tek panolu sutun
    const yeni = { gen: hs.gen / 2, kapali: false, yiginlar: [yeniYigin] };
    hs.gen = hs.gen / 2;
    const i = k.sutunlar.indexOf(hs);
    k.sutunlar.splice(hedef.yer === "sol" ? i : i + 1, 0, yeni);
  } else {
    return yerlesimOnar(y);
  }
  return yerlesimOnar(k);
}

/* Iki komsunun agirligini surukleme oranina gore paylastirir. Toplam
   KORUNUR (oteki sutunlar kipirdamaz); hicbiri toplamin `alt` payindan
   asagi inmez -- sifira ezilen bir pano, kaybolmus bir panodur.

   `alt` PIKSELDEN gelir (CSS alt siniri / iki komsunun toplam genisligi).
   Olculdu: yalniz %10 ile sinirlanirken sutun CSS'in 220px siniriyla
   durdu, yer OTEKI sutunlardan calindi ve saklanan agirlik ekrandaki
   genislikle ayristi -- bir sonraki cekiste bolucu sicrardi. Iki komsu
   alt siniri bile karsilayamiyorsa hic dokunulmaz. */
function komsuPaylas(a, b, oranA, alt = 0.1) {
  if (!(alt < 0.5)) return [a, b];
  // Olculen genislik 0 ise oran 0/0 = NaN: onceki deger KORUNUR (NaN
  // duzene yazilsa onarim 1'e cevirir ve oteki sutunlar sessizce kayardi).
  if (!Number.isFinite(oranA)) return [a, b];
  const t = a + b;
  const o = Math.min(1 - alt, Math.max(alt, oranA));
  return [t * o, t * (1 - o)];
}

/* Surukleme sirasinda imlecin bir yigin uzerindeki YERI: sekme cubugu,
   kenar serit (yeni sutun), ust/alt yari (bolme). */
function birakmaYeri(x, y, kutu, basYuksekligi) {
  if (y - kutu.top <= basYuksekligi) return "sekme";
  const gx = (x - kutu.left) / kutu.width;
  if (gx < 0.2) return "sol";
  if (gx > 0.8) return "sag";
  return (y - kutu.top - basYuksekligi) / (kutu.height - basYuksekligi) < 0.5
    ? "ust" : "alt";
}

/* panel.css ile AYNI sayilar (.sutun min-width, .yigin min-height):
   boyutlandirma bunlarin altina cekmez, yoksa CSS durdurur ve yer oteki
   panolardan calinir. */
const SUTUN_ALT_PX = 220, YIGIN_ALT_PX = 80;
// v2 (29.09.2026): varsayilan duzen degisti (takim sohbeti ayri sutun). v1
// anahtarinda saklanan eski duzen yeni varsayilani gizlerdi; anahtar
// degisince herkes yeni duzenle acilir, kendi duzenini yeniden kurabilir.
const YERLESIM_ANAHTARI = "agentofis.yerlesim.v2";
function yerlesimYukle() {
  try {
    const h = localStorage.getItem(YERLESIM_ANAHTARI);
    return yerlesimOnar(h ? JSON.parse(h) : null);
  } catch (e) { return yerlesimVarsayilan(); }
}
function yerlesimKaydet() {
  try { localStorage.setItem(YERLESIM_ANAHTARI, JSON.stringify(D.yerlesim)); }
  catch (e) { /* saklanamamak paneli bozmaz; bir sonraki acilis varsayilan */ }
}

/* Pano o an EKRANA konabilir mi. Tarayici kapaliyken yer kaplamaz --
   CDP yerel bir arka kapidir, varsayilan dar olmali. */
function panoGorunur(p) {
  return p !== "tarayici" || K.acik || K.hata;
}
/* Pano o an GORUNUYOR mu (secili sekme + daraltilmamis sutun). Cizim
   buna bakar: gorunmeyen seyi cizmek bos is. */
function panoAcik(p) {
  for (const s of D.yerlesim.sutunlar)
    for (const g of s.yiginlar)
      if (g.panolar.includes(p)) {
        const gorunen = g.panolar.filter(panoGorunur);
        const secili = gorunen.includes(g.secili) ? g.secili : gorunen[0];
        return !s.kapali && secili === p && panoGorunur(p);
      }
  return false;
}
function panoGovdesi(p) { return document.querySelector(`.pano-govde[data-pano="${p}"]`); }

function yerlesimCiz() {
  const kok = $("#sutunlar"), depo = $("#pano-depo");
  // Once her sey depoya: `textContent = ""` tasinmis dugumleri YOK ederdi.
  document.querySelectorAll(".pano-govde").forEach((g) => depo.append(g));
  depo.append($("#bekleyen-bolum"));
  kok.textContent = "";
  let oncekiSutun = null;
  D.yerlesim.sutunlar.forEach((s, i) => {
    const yiginlar = s.yiginlar
      .map((g, j) => ({ g, j, gorunen: g.panolar.filter(panoGorunur) }))
      .filter((x) => x.gorunen.length);
    if (!yiginlar.length) return;             // or. yalniz kapali tarayici
    if (oncekiSutun !== null && !s.kapali && !D.yerlesim.sutunlar[oncekiSutun].kapali)
      kok.append(ayirici("dikey", oncekiSutun, i));
    else if (oncekiSutun !== null)
      kok.append(el("div", "ayirici-bos"));
    oncekiSutun = i;
    const sut = el("section", "sutun" + (s.kapali ? " kapali" : ""));
    sut.dataset.sutun = i;
    sut.style.flex = s.kapali ? "0 0 150px" : `${s.gen} 1 0`;
    let oncekiYigin = null;
    yiginlar.forEach(({ g, j, gorunen }) => {
      if (oncekiYigin !== null && !s.kapali)
        sut.append(ayirici("yatay", i, oncekiYigin, j));
      oncekiYigin = j;
      const yig = el("div", "yigin");
      yig.dataset.sutun = i; yig.dataset.yigin = j;
      yig.style.flex = s.kapali ? "none" : `${g.yuk} 1 0`;
      const secili = gorunen.includes(g.secili) ? g.secili : gorunen[0];
      const bas = el("div", "sutun-bas yigin-bas");
      const sekmeler = el("div", "sekmeler");
      for (const p of gorunen) {
        const b = el("button", p === secili ? "secili" : "");
        b.dataset.pano = p;
        b.draggable = true;
        b.title = "Sürükle: başka yere taşı · tıkla: göster";
        b.append(document.createTextNode(PANOLAR[p].ad));
        if (PANOLAR[p].sayac) {
          const sy = el("span", "sutun-sayac");
          sy.id = PANOLAR[p].sayac;
          b.append(sy);
        }
        sekmeler.append(b);
      }
      bas.append(sekmeler);
      // BUYUT / BOL. Bolme yeni bir kural DEGIL: surukle-birakin kullandigi
      // ve Node'da sinanan `panoTasi`. Tek panolu yiginda bolmek anlamsiz
      // (panoTasi zaten degistirmez) -- dugme hic cizilmez.
      const buyukMu = D.buyuk === i + ":" + j;
      if (!s.kapali) {
        const ara = el("div", "yigin-arac");
        if (gorunen.length > 1) {
          for (const [yer, isaret, ne] of [["alt", "\u2B13", "alta böl"],
                                            ["sag", "\u25E8", "sağa yeni sütun"]]) {
            const d = el("button", "yigin-dugme", isaret);
            d.dataset.bol = yer;
            d.title = `${PANOLAR[secili].ad}: ${ne}`;
            ara.append(d);
          }
        }
        const bb = el("button", "yigin-dugme", buyukMu ? "\u2921" : "\u2922");
        bb.dataset.buyut = "1";
        bb.title = buyukMu ? "Küçült (Esc)" : "Büyüt: tüm alana yay (çift tık da olur)";
        ara.append(bb);
        bas.append(ara);
      }
      if (buyukMu) yig.classList.add("buyuk");
      if (oncekiYigin === yiginlar[0].j) {
        const kat = el("button", "sutun-kat");
        kat.dataset.katSutun = i;
        kat.title = s.kapali ? "Aç" : "Daralt";
        kat.innerHTML = s.kapali ? "&#43;" : "&#8211;";
        bas.append(kat);
      }
      yig.append(bas);
      if (gorunen.includes("gorevler")) yig.append($("#bekleyen-bolum"));
      const govde = el("div", "yigin-govde");
      for (const p of gorunen) {
        const pg = panoGovdesi(p);
        pg.hidden = p !== secili;
        govde.append(pg);
      }
      yig.append(govde);
      sut.append(yig);
    });
    kok.append(sut);
  });
  sutunSayaclari();
  const sk = $("#sayac-kabin");
  if (sk) sk.textContent = K.acik ? "açık" : "kapalı";
  // Buyutulen yigin artik yoksa (tasindi, kapandi) hal DUSER: olmayan
  // bir seyi buyutulmus saymak, dugmesi olmayan bir kipte kalmaktir.
  if (D.buyuk && !document.querySelector(".yigin.buyuk")) D.buyuk = null;
  buyukKonumla();
}

/* Buyutulen yigin CALISMA ALANININ tamamina yayilir: ust ray ve komut
   satiri gorunur kalir (insan neyin beklendigini ve lidere yazmayi
   kaybetmemeli). Alan olculur, sabit piksel yazilmaz. */
function buyukKonumla() {
  const y = document.querySelector(".yigin.buyuk");
  if (!y) return;
  const r = $("#sutunlar").getBoundingClientRect();
  Object.assign(y.style, { left: r.left + "px", top: r.top + "px",
                           width: r.width + "px", height: r.height + "px" });
}
window.addEventListener("resize", buyukKonumla);

function buyut(anahtar) {
  D.buyuk = D.buyuk === anahtar ? null : anahtar;
  yerlesimCiz();
  gorunurleriCiz();
}

function ayirici(yon, a, b, c) {
  const d = el("div", "ayirici-" + yon);
  d.dataset.yon = yon;
  d.dataset.a = a; d.dataset.b = b;
  if (c !== undefined) d.dataset.c = c;
  return d;
}

/* Gorunur panolari yeniden ciz -- yerlesim degisince. */
function gorunurleriCiz() {
  cizGorunum(); cizKod(); cizSekme();
}

function yerlesimUygula(yeni) {
  D.yerlesim = yerlesimOnar(yeni);
  yerlesimKaydet();
  yerlesimCiz();
  gorunurleriCiz();
}

/* ---- tikla: sekme sec, sutun daralt ---- */
$("#sutunlar").addEventListener("click", (e) => {
  const bol = e.target.closest("button[data-bol]");
  if (bol) {
    const yig = bol.closest(".yigin");
    const sec = yig.querySelector(".yigin-bas .sekmeler button.secili");
    if (!sec) return;
    D.buyuk = null;
    return yerlesimUygula(panoTasi(D.yerlesim, sec.dataset.pano,
      { sutun: +yig.dataset.sutun, yigin: +yig.dataset.yigin,
        yer: bol.dataset.bol }));
  }
  const bb = e.target.closest("button[data-buyut]");
  if (bb) {
    const yig = bb.closest(".yigin");
    return buyut(yig.dataset.sutun + ":" + yig.dataset.yigin);
  }
  const kat = e.target.closest("button[data-kat-sutun]");
  if (kat) {
    const k = JSON.parse(JSON.stringify(D.yerlesim));
    const s = k.sutunlar[+kat.dataset.katSutun];
    if (s) s.kapali = !s.kapali;
    return yerlesimUygula(k);
  }
  const b = e.target.closest(".yigin-bas button[data-pano]");
  if (!b) return;
  const yig = b.closest(".yigin");
  const k = JSON.parse(JSON.stringify(D.yerlesim));
  const g = k.sutunlar[+yig.dataset.sutun].yiginlar[+yig.dataset.yigin];
  g.secili = b.dataset.pano;
  yerlesimUygula(k);
});

/* Sekmeye CIFT TIK: o yigini buyut / kucult. */
$("#sutunlar").addEventListener("dblclick", (e) => {
  const b = e.target.closest(".yigin-bas button[data-pano]");
  if (!b) return;
  const yig = b.closest(".yigin");
  buyut(yig.dataset.sutun + ":" + yig.dataset.yigin);
});
/* Esc buyutmeyi kapatir -- ama yazi alanindan ya da odakli kabinden
   GELMIYORSA: orada Esc'in kendi isi var (form iptali, sayfaya tus). */
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || !D.buyuk) return;
  const a = document.activeElement;
  if (a && /^(INPUT|TEXTAREA)$/.test(a.tagName)) return;
  if (document.querySelector(".kabin-alan.odakli") || K.secKipi) return;
  buyut(D.buyuk);
});

/* ---- surukle-birak ---- */
$("#sutunlar").addEventListener("dragstart", (e) => {
  const b = e.target.closest(".yigin-bas button[data-pano]");
  if (!b) return;
  D.surukle = b.dataset.pano;
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", D.surukle);
  document.body.classList.add("surukleniyor");
});
function birakHedefi(e) {
  const yig = e.target.closest && e.target.closest(".yigin");
  if (!yig) return null;
  const kutu = yig.getBoundingClientRect();
  const bas = yig.querySelector(".yigin-bas");
  const yer = birakmaYeri(e.clientX, e.clientY, kutu, bas ? bas.offsetHeight : 32);
  return { sutun: +yig.dataset.sutun, yigin: +yig.dataset.yigin, yer, kutu,
           basY: bas ? bas.offsetHeight : 32 };
}
$("#sutunlar").addEventListener("dragover", (e) => {
  if (!D.surukle) return;
  const h = birakHedefi(e);
  const gos = $("#birak-gosterge");
  if (!h) { gos.hidden = true; return; }
  e.preventDefault();
  e.dataTransfer.dropEffect = "move";
  const k = h.kutu;
  const r = { sekme: [k.left, k.top, k.width, h.basY],
              sol:   [k.left, k.top, k.width * 0.3, k.height],
              sag:   [k.right - k.width * 0.3, k.top, k.width * 0.3, k.height],
              ust:   [k.left, k.top + h.basY, k.width, (k.height - h.basY) / 2],
              alt:   [k.left, k.top + h.basY + (k.height - h.basY) / 2, k.width,
                      (k.height - h.basY) / 2] }[h.yer];
  Object.assign(gos.style, { left: r[0] + "px", top: r[1] + "px",
                             width: r[2] + "px", height: r[3] + "px" });
  gos.hidden = false;
});
/* Surukleme durumu HER cikista temizlenir. `dragend` kaynak dugume
   atilir; birakinca yerlesim yeniden kuruldugu icin kaynak sekme DOM'dan
   cikmis olur ve olay `document`e ulasmayabilir. Temizlenmezse
   `surukleniyor` sinifi kalir ve butun pano govdeleri TIKLANAMAZ olur. */
function surukleBitir() {
  D.surukle = null;
  $("#birak-gosterge").hidden = true;
  document.body.classList.remove("surukleniyor");
}
$("#sutunlar").addEventListener("drop", (e) => {
  const p = D.surukle;
  const h = birakHedefi(e);
  surukleBitir();
  if (!p || !h) return;
  e.preventDefault();
  yerlesimUygula(panoTasi(D.yerlesim, p, h));
});
document.addEventListener("dragend", surukleBitir);

/* ---- boyutlandir: bolucuyu cek ---- */
$("#sutunlar").addEventListener("pointerdown", (e) => {
  const d = e.target.closest(".ayirici-dikey, .ayirici-yatay");
  if (!d) return;
  e.preventDefault();
  d.setPointerCapture(e.pointerId);
  const dikey = d.dataset.yon === "dikey";
  const onceki = d.previousElementSibling, sonraki = d.nextElementSibling;
  const ka = onceki.getBoundingClientRect(), kb = sonraki.getBoundingClientRect();
  const bas = dikey ? e.clientX : e.clientY;
  const uzA = dikey ? ka.width : ka.height, uzB = dikey ? kb.width : kb.height;
  const k = JSON.parse(JSON.stringify(D.yerlesim));
  const s = k.sutunlar;
  const [hedefA, hedefB, alan] = dikey
    ? [s[+d.dataset.a], s[+d.dataset.b], "gen"]
    : [s[+d.dataset.a].yiginlar[+d.dataset.b], s[+d.dataset.a].yiginlar[+d.dataset.c], "yuk"];
  const a0 = hedefA[alan], b0 = hedefB[alan];
  document.body.classList.add("boyutlaniyor");
  const hareket = (ev) => {
    const fark = (dikey ? ev.clientX : ev.clientY) - bas;
    const [a, b] = komsuPaylas(a0, b0, (uzA + fark) / (uzA + uzB),
                               Math.max(0.1, (dikey ? SUTUN_ALT_PX : YIGIN_ALT_PX) / (uzA + uzB)));
    hedefA[alan] = a; hedefB[alan] = b;
    onceki.style.flex = `${a} 1 0`; sonraki.style.flex = `${b} 1 0`;
  };
  const bitir = () => {
    d.removeEventListener("pointermove", hareket);
    d.removeEventListener("pointerup", bitir);
    d.removeEventListener("pointercancel", bitir);
    document.body.classList.remove("boyutlaniyor");
    // Boyut degisince harita balonlari yeniden OLCULMELI -- yerlesim
    // kurulusu yeniden yapilir.
    yerlesimUygula(k);
  };
  d.addEventListener("pointermove", hareket);
  d.addEventListener("pointerup", bitir);
  d.addEventListener("pointercancel", bitir);
});

$("#duzen-sifirla").onclick = () => yerlesimUygula(yerlesimVarsayilan());


/* Bir panoyu one getir (or. tarayici acilinca). */
function panoSec(p) {
  const k = JSON.parse(JSON.stringify(D.yerlesim));
  for (const s of k.sutunlar)
    for (const g of s.yiginlar)
      if (g.panolar.includes(p)) { g.secili = p; s.kapali = false; }
  yerlesimUygula(k);
}

/* ─────────────── kurulum ─────────────── */

/* SUTUN DARALTMA. Uc sutun 1600px'te sigar ama dar pencerede birbirini
   ezer; katlamak bunun cozumu. Rakipte de her panel basliginda ayni
   dugme var ve dogru bir fikir: ekrani kullanicinin o anki isine gore
   O ayarlar, biz varsayimla degil.

   Kapatilan sutun CIZILMEZ (bkz. cizGorunum) -- gorunmeyen seyi
   cizmek bos is; ama basliktaki SAYAC durur, yani kapali panel
   "orada bir sey var mi" sorusunu yine cevaplar. */
/* (Sutun daraltma artik yerlesimin parcasi: `kapali` duzende saklanir
   ve oturumlar arasi kalir -- bkz. "yerlesim" bolumu.) */
/* Kod bolumu ayri daraltilir: terminali izlerken diske bakmak
   istemeyen, yeri terminale birakabilmeli. Sutun daraltmasiyla ayni
   kural -- ekrani kullanici kendi isine gore ayarlar, biz varsayimla
   degil. */
/* (Kod artik ayri bir pano: sekme, yigin ya da sutun olarak yeri
   insanin. Ayri daraltma dugmesine gerek kalmadi.) */


$("#faaliyet-satir").onclick = () => {
  const g = $("#gunluk");
  g.classList.toggle("gizli");
  if (!g.classList.contains("gizli")) {
    const akis = $("#gunluk-akis");
    akis.scrollTop = akis.scrollHeight;
  }
};
$("#gunluk-kapat").onclick = (e) => {
  e.stopPropagation(); $("#gunluk").classList.add("gizli");
};
$("#perde").onclick = (e) => { if (e.target === $("#perde")) cekmeceKapat(); };
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!$("#perde").classList.contains("gizli")) cekmeceKapat();
  else $("#gunluk").classList.add("gizli");
});

/* GENEL KANAL onerisi: komut satirinin ustunde takim dugmeleri. Puani 0
   olan takim "onerilen" diye isaretlenmez -- uydurma bir "en uygun"
   gosterilmez. `metin` null ise satir kaldirilir. */
function takimOneriGoster(metin, oneriler, girdi, yer) {
  girdi = girdi || $("#komut-girdi");
  document.querySelectorAll(".takim-oneri").forEach((x) => x.remove());
  if (metin === null || metin === undefined) return;
  const kap = el("div", "takim-oneri");
  kap.id = "takim-oneri";
  kap.append(el("span", "takim-oneri-soru", "Birden çok takım var — hangisine gitsin?"));
  const enIyi = oneriler.length && oneriler[0].puan > 0 ? oneriler[0].kanat_id : null;
  for (const o of oneriler) {
    const b = el("button", "dugme" + (o.kanat_id === enIyi ? " olumlu" : ""),
                 o.ad + (o.kanat_id === enIyi ? " · önerilen" : ""));
    b.title = `lider: ${o.lider}` + (o.puan ? ` · eşleşen: ${o.sebep}` : " · eşleşme yok");
    b.onclick = async () => {
      kap.remove();
      try {
        await yolla("/api/lidere", { metin, kanat: o.kanat_id, oge: D.secilenOge || null });
        girdi.value = "";
        bildir(`mesaj ${o.ad} takımının liderine (${o.lider}) gitti`, "iyi");
        if (D.yerlesim) panoSec("sohbet");
      } catch (e) { bildir("gönderilemedi: " + (e.message || e), "kotu"); }
      yenile();
    };
    kap.append(b);
  }
  const vaz = el("button", "dugme", "vazgeç");
  vaz.onclick = () => kap.remove();
  kap.append(vaz);
  // Komut satirinin ICINE, onun ustunde SUZULUR: sayfayi itseydi komut
  // satiri ekranin altina kayardi (olculdu, 1920x900).
  (yer || document.querySelector(".komut")).append(kap);
}

/* Iki yazma yeri, TEK gonderici: alttaki komut satiri ve takim
   sohbeti panosunun kendi kutusu (29.09: kullanici "takim sohbetine
   yazamiyorum" demisti -- yazilan yer alttaki satirdi, pano degil).
   Ikisi ayni yonlendiriciden gecer; iki kopya olsaydi biri kayardi. */
/* EKLER (29.09): dosya secilince/yapistirilinca HEMEN yuklenir (proje
   kokunun `ekler/` klasoru), gonderilene kadar cip olarak bekler; mesaja
   `[ek] ekler/ad` satiri olarak eklenir. Kural sunucuda (`ofis/ekler.py`). */
D.ekler = D.ekler || [];
function ekCiplari() {
  const kap = $("#ek-ciplari");
  if (!kap) return;
  kap.textContent = "";
  for (const e of D.ekler) {
    const c = el("span", "ek-cip", (e.gorsel ? "🖼 " : "📄 ") + e.ad.replace(/^\d{8}-\d{6}-/, ""));
    const x = el("button", "ek-sil", "×");
    x.type = "button";
    x.title = "eki çıkar (dosya diskte kalır)";
    x.onclick = () => { D.ekler = D.ekler.filter((y) => y !== e); ekCiplari(); };
    c.append(x);
    kap.append(c);
  }
}
// BUYUK dosya (video/ses) AKISLA gider: govde dosyanin kendisi, sinir 2 GB
// (ekler.py). Kucuk dosya eskisi gibi base64 JSON.
async function ekAkisla(f) {
  const ad = f.name || ("ek-" + Date.now());
  bildir(`yükleniyor: ${ad} (${Math.round(f.size / 1048576)} MB)`, "bilgi");
  const r = await fetch("/api/ek_akis?ad=" + encodeURIComponent(ad) +
                        "&kanat=" + encodeURIComponent(D.kanat || ""),
                        { method: "POST", body: f });
  if (!r.ok) {
    let m = r.status + "";
    try { m = (await r.json()).detail || m; } catch (_) {}
    throw new Error(m);
  }
  return r.json();
}
async function ekYukle(dosyalar) {
  for (const f of dosyalar) {
    try {
      if (f.size > 15 * 1048576 || /^(video|audio)\//.test(f.type || "")) {
        const r = await ekAkisla(f);
        D.ekler.push(r);
        bildir(`eklendi: ${r.yol}`, "iyi");
        continue;
      }
      const veri = await new Promise((ok, hata) => {
        const r = new FileReader();
        r.onload = () => ok(String(r.result).split(",")[1] || "");
        r.onerror = () => hata(r.error);
        r.readAsDataURL(f);
      });
      const ad = f.name || ("ekran-" + Date.now() + ".png");
      const r = await yolla("/api/ek", { ad, veri });
      D.ekler.push(r);
      bildir(`eklendi: ${r.yol}`, "iyi");
    } catch (e) { bildir("eklenemedi: " + (e.message || e), "kotu"); }
  }
  ekCiplari();
}

async function komutGonder(girdi, oneriYeri) {
  girdi = (girdi && girdi.value !== undefined) ? girdi : $("#komut-girdi");
  let metin = girdi.value.trim();
  const ekVar = D.ekler.length > 0;
  if (!metin && !ekVar) return;
  if (ekVar) metin = (metin || "Ekteki dosyaya bak.") + "\n" +
    D.ekler.map((e) => "[ek] " + e.yol).join("\n");
  girdi.value = "";
  // SECILI KANAT gonderilir: ofiste birden fazla lider olabilir ve
  // yanlis kanada verilen hedef, yanlis kadroya yanlis isi verir.
  // Panelin ustunde sekme zaten duruyor; gondermemek, panelin
  // BILDIGI bir seyi cekirdekten saklamak olurdu.
  // RET SESSIZ OLMAZ. `al()` 200 disinda ISTISNA atar; yakalanmazsa
  // insan hicbir sey gormez ve mesajinin gittigini sanir -- tam da
  // kapatmaya calistigimiz hatanin bir baskasi.
  try {
    // Secili oge varsa GIDER; sunucu onu yeniden suzer ve lidere giden
    // bloğu kendisi kurar (`kabin.oge_metni`) -- metin tek yerde kurulur.
    const r = await yolla("/api/lidere",
      { metin, kanat: D.kanat || "", oge: D.secilenOge || null });
    if (D.secilenOge) {
      D.secilenOge = null; ogeCipi(); ogeVurgu(null);
      bildir(r && r.tarayici && r.tarayici.length
        ? `öğe eklendi · iş ${r.tarayici.join(", ")} kaynağına erişebilir`
          + (r.kabin ? " (paylaşılan kabin)" : " (kabin kapalı: ayrı tarayıcı)")
        : "öğe eklendi (sayfa bir web kaynağı değil, tarayıcı açılmadı)", "iyi");
    }
    if (r && r.yol === "oneri") {
      // GENEL KANAL: ofis secmez, ONERIR. Mesaj gitmedi; insan takimi
      // secince ayni istek o takimin kanadiyla yeniden gider.
      girdi.value = metin;
      takimOneriGoster(metin, r.oneriler || [], girdi, oneriYeri);
      return;
    }
    takimOneriGoster(null);
    if (ekVar) { D.ekler = []; ekCiplari(); }
    // GECICI IPUCU (01.10.2026, patronun ekrani): "Lider calisiyor..."
    // is bittikten sonra da kaliyordu. Ozgun ipucu saklanir; kosu bitince
    // `cizSohbet` onu geri koyar.
    if (!girdi.dataset.varsayilan) girdi.dataset.varsayilan = girdi.placeholder;
    girdi.dataset.gecici = "1";
    girdi.placeholder = r && r.yol === "not" ? `not ${r.alici}'a iletilecek`
      : r && r.yol === "soru" ? `${r.alici} düşünüyor…`
      : r && r.sirada ? `sıraya alındı (${r.sira}.) — önceki iş bitince başlar`
      : r && r.yol === "is" ? `iş ${r.atanan}'a veriliyor (planı ${r.alici} yazar)…`
      : "Lider çalışıyor…";
    // Cevap SOHBET panosuna duser; insan nereye bakacagini aramasin.
    if (D.yerlesim) panoSec("sohbet");
  } catch (e) {
    // yazdigini kaybetme -- ek satirlari cipte kaldigi icin metne yazilmaz
    girdi.value = metin.split("\n").filter((s) => !s.startsWith("[ek] ")).join("\n");
    girdi.placeholder = String(e.message || e).slice(0, 180);
  }
  yenile();
}
/* Okunur kip anahtari. Kip PANEL GENELIDIR: pano basina ayri kip,
   ayni ekranda iki farkli okuma sozlesmesi demek olurdu ve insan hangi
   panonun neyi sakladigini akilda tutmak zorunda kalirdi. */
function okunurAnahtar() {
  D.okunurKip = !D.okunurKip;
  $("#okunur-anahtar").classList.toggle("acik", D.okunurKip);
  $("#okunur-etiket").textContent = D.okunurKip ? "okunur kip" : "terminal kipi";
  cizGorunum();
}
$("#okunur-anahtar").onclick = okunurAnahtar;

/* MASAUSTU BILDIRIMI (01.10.2026). Ayar defterde (`bildirim`); panel
   yalniz gosterir ve degistirir. Sinama panelinde bildirim izleyicisi
   calismiyorsa dugme bunu SOYLER (acik gorunup sessiz kalmasin). */
async function bildirimDurumu(r) {
  try { r = r || await al("/api/bildirim"); } catch (e) { return; }
  const d = $("#bildirim-anahtar");
  d.classList.toggle("acik", !!(r.acik && r.panelde_calisiyor));
  $("#bildirim-etiket").textContent = !r.panelde_calisiyor ? "bildirim (bu panelde yok)"
    : r.acik ? "bildirim açık" : "bildirim kapalı";
  d.dataset.acik = r.acik ? "1" : "";
}
$("#bildirim-anahtar").onclick = async () => {
  try { bildirimDurumu(await yolla("/api/bildirim", { acik: !$("#bildirim-anahtar").dataset.acik })); }
  catch (e) { bildir(String(e.message || e).slice(0, 160), "uyari"); }
};
bildirimDurumu();

/* EFOR MODU. Panel karar vermez: secimi ayara yazar, kural sunucuda
   (`roller.tur_eforu`). Komut satirindan panelde dugmesi olmayan bir
   seviye secildiyse (orn. `dusuk`) hicbir dugme yalan yere secili
   gorunmez -- secilen seviye ayrica YAZILIR. */
async function cizEfor() {
  const kap = $("#efor-sec");
  if (!kap) return;
  let d;
  try { d = await al("/api/efor"); }
  catch (e) { kap.title = "efor modu okunamadi: " + e.message; return; }
  let tanindi = false;
  kap.querySelectorAll("button").forEach(b => {
    const s = b.dataset.mod === d.mod;
    b.classList.toggle("secili", s);
    if (s) tanindi = true;
  });
  kap.querySelector(".efor-diger")?.remove();
  if (!tanindi) {
    const not = document.createElement("span");
    not.className = "efor-diger";
    not.textContent = "sabit: " + d.mod;
    kap.appendChild(not);
  }
}

document.querySelectorAll("#efor-sec button").forEach(b => {
  b.onclick = async () => {
    try { await yolla("/api/efor", { mod: b.dataset.mod }); }
    catch (e) {
      // UYDURMAZ: degismediyse secim eski yerinde kalir ve sebep yazilir.
      await cizEfor();
      const not = document.createElement("span");
      not.className = "efor-diger";
      not.textContent = "değiştirilemedi";
      not.title = e.message || String(e);
      $("#efor-sec").appendChild(not);
      return;
    }
    cizEfor();
  };
});
cizEfor();

$("#komut-gonder").onclick = () => komutGonder();
{
  const f = $("#sohbet-yaz");
  if (f) f.onsubmit = (e) => {
    e.preventDefault();
    komutGonder($("#sohbet-girdi"), f).then(() => boyAyarla($("#sohbet-girdi")));
  };
  // COK SATIRLI ALAN: Enter gonderir, Shift+Enter yeni satir; alan
  // yazdikca buyur (tavani CSS'te).
  const sg = $("#sohbet-girdi");
  if (sg && f) {
    sg.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        f.requestSubmit();
      }
    });
    sg.addEventListener("input", () => boyAyarla(sg));
  }
  const sb = $("#sohbet-ses");
  if (sb && sg) sb.onclick = () => sesleYaz(sg, sb);
  // SURUKLE-BIRAK: sohbet panosunun uzerine birakilan dosya eklenir.
  const pano = document.querySelector('.pano-govde[data-pano="sohbet"]');
  const ip = $("#surukle-ipucu");
  if (pano && ip) {
    let derinlik = 0;
    const dosyaMi = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
    pano.addEventListener("dragenter", (e) => {
      if (!dosyaMi(e)) return;
      e.preventDefault(); derinlik++; ip.hidden = false;
    });
    pano.addEventListener("dragover", (e) => { if (dosyaMi(e)) e.preventDefault(); });
    pano.addEventListener("dragleave", () => {
      if (--derinlik <= 0) { derinlik = 0; ip.hidden = true; }
    });
    pano.addEventListener("drop", (e) => {
      if (!dosyaMi(e)) return;
      e.preventDefault(); derinlik = 0; ip.hidden = true;
      ekYukle([...e.dataTransfer.files]);
    });
  }
  const sec = $("#ek-sec"), dos = $("#ek-dosya");
  if (sec && dos) {
    sec.onclick = () => dos.click();
    dos.onchange = () => { ekYukle([...dos.files]); dos.value = ""; };
  }
  // Ekran goruntusu YAPISTIRMA: iki yazma yerinde de.
  for (const g of [$("#sohbet-girdi"), $("#komut-girdi")]) {
    if (!g) continue;
    g.addEventListener("paste", (e) => {
      const dosyalar = [...(e.clipboardData?.files || [])];
      if (dosyalar.length) { e.preventDefault(); ekYukle(dosyalar); }
    });
  }
}
$("#ajan-ekle").onclick = () => ajanEkleAc();
$("#org-ac").onclick = () => organizasyonAc("");

/* ARAMA. Sonuc cekmecede; gorevi olan sonuca tiklamak gorevi acar.
   Eslesen parca ISARETLENIR ama metin olarak -- innerHTML'e ham defter
   metni basmak, ajanin yazdigi bir etiketin panelde calismasi demekti. */
async function araAc(q) {
  let r;
  try { r = await al("/api/ara?q=" + encodeURIComponent(q)); }
  catch (e) { return bildir("arama yapılamadı: " + e.message, "kotu"); }
  cekmeceAc((c) => {
    cekBas(c, `arama · ${r.sonuclar.length} sonuç · ${r.kapsam}`, q);
    if (!r.sonuclar.length)
      return c.append(el("div", "bos-yazi", q.trim().length < 2
        ? "En az 2 harf yaz." : "Eşleşen kayıt yok."));
    const katla = (m) => (m || "").replace(/İ/g, "i").replace(/I/g, "i")
                                  .replace(/ı/g, "i").toLowerCase();
    for (const x of r.sonuclar) {
      const d = el("div", "ara-sonuc" + (x.gorev_no ? " acilir" : ""));
      const bas = el("div", "oge-bas");
      bas.append(el("span", "etiket", x.tur), el("span", null, x.baslik),
                 el("span", null, x.kim || ""), el("span", null, saat(x.zaman)));
      const g = el("div", "oge-govde");
      const i = katla(x.parca).indexOf(katla(q.trim()));
      if (i >= 0) {
        g.append(document.createTextNode(x.parca.slice(0, i)),
                 el("mark", null, x.parca.slice(i, i + q.trim().length)),
                 document.createTextNode(x.parca.slice(i + q.trim().length)));
      } else g.textContent = x.parca;
      d.append(bas, g);
      if (x.gorev_no) d.onclick = () => gorevAc(x.gorev_no);
      c.append(d);
    }
  });
}
$("#ara-kutu").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target.value.trim()) araAc(e.target.value);
});
$("#komut-surdur").onclick = () => ($("#komut-surdur").dataset.kip === "durdur"
  ? eylem("/api/durdur", {}, (r) => "durdurma istendi — " + r.not)
  : eylem("/api/devam", {},
      (r) => `halka sürdürülüyor · ${r.acik_is} açık iş`));
$("#komut-girdi").addEventListener("keydown",
  (e) => { if (e.key === "Enter") komutGonder(); });
/* SESLE YAZ (30.09): iki yazma yerinde de ayni islev. Soylenen kutuya
   YAZILIR, gonderilmez -- insan duzeltip gonderir (yanlis duyulmus bir
   "sil" dogrudan lidere gitmesin). Var olan metnin SONUNA eklenir.
   Tanima tarayicinin kendi hizmetidir (Chrome'da Google); ofis sesi
   kaydetmez. Desteklemeyen tarayicida SESSIZCE calisiyormus gibi yapmaz. */
function boyAyarla(g) {
  if (!g || g.tagName !== "TEXTAREA") return;
  g.style.height = "auto";
  g.style.height = Math.min(g.scrollHeight + 2, 160) + "px";
}
let _sesAcik = null;
function sesleYaz(girdi, dugme) {
  if (_sesAcik) { _sesAcik.stop(); return; }
  const T = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!T) {
    girdi.placeholder = "Bu tarayıcı ses tanımayı desteklemiyor (Chrome ya da Edge kullan).";
    return;
  }
  const t = new T();
  t.lang = "tr-TR";
  t.interimResults = true;
  t.continuous = true;
  const once = girdi.value ? girdi.value.trimEnd() + " " : "";
  let kesin = "";
  t.onresult = (e) => {
    let ara = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) kesin += r[0].transcript + " ";
      else ara += r[0].transcript;
    }
    girdi.value = (once + kesin + ara).trimStart();
    boyAyarla(girdi);
  };
  t.onerror = (e) => {
    girdi.placeholder = e.error === "not-allowed"
      ? "Mikrofon izni verilmedi (adres çubuğundaki simgeden izin ver)."
      : "Ses tanıma durdu: " + e.error;
  };
  t.onend = () => {
    _sesAcik = null;
    dugme.classList.remove("dinliyor");
    dugme.title = "Sesle yaz (Türkçe)";
    girdi.value = girdi.value.trimEnd();
    girdi.focus();
  };
  _sesAcik = t;
  dugme.classList.add("dinliyor");
  dugme.title = "Dinliyorum — bitirmek için tekrar bas";
  t.start();
}
$("#komut-ses").onclick = () => sesleYaz($("#komut-girdi"), $("#komut-ses"));

(async () => {
  // YERLESIM once kurulur: cizim fonksiyonlari panonun ekranda olup
  // olmadigina (`panoAcik`) bakar.
  D.yerlesim = yerlesimYukle();
  yerlesimCiz();
  // KABIN DUGMELERI HEMEN baglanir (02.10.2026 olculdu): eskiden butun
  // veri yuklendikten SONRA baglaniyordu; o birkac saniyede "tarayici"
  // dugmesine basmak HICBIR SEY yapmiyordu.
  kabinKur();
  await yenile();
  // HESAP LIMITLERI SUREKLI GUNCEL (27.09.2026): sunucu iki dakikada bir
  // saglayicidan okur; bos ofiste olay akmadigi icin ray kendiliginden
  // tazelenmezdi. Sekme gorunmuyorsa istek atilmaz.
  setInterval(() => { if (!document.hidden) yenile(); }, 60000);
  D.olaylar = await al("/api/olaylar?adet=300");
  const akis = $("#gunluk-akis");
  D.olaylar.forEach((o) => {
    D.sonOlay = Math.max(D.sonOlay, o.id);
    const s = gunlukSatiri(o);
    if (s) akis.append(s);
  });
  if (D.olaylar.length) faaliyetGoster(D.olaylar[D.olaylar.length - 1]);
  akis.scrollTop = akis.scrollHeight;

  // OLAYLAR YUKLENDIKTEN SONRA TEKRAR CIZ -- olculmus bir SIRALAMA
  // hatasi (22.09.2026).
  //
  // `yenile()` panolari cizer ama `D.olaylar` HENUZ BOSTUR: olay
  // defteri bir satir asagida cekiliyor. Yani terminal sutunu ilk
  // boyamada her zaman bos kaliyordu ve bir daha cizilmedigi icin
  // oyle KALIYORDU. Olculdu: defterde 249 ajanli olay, ekranda 0 pano;
  // elle `cizCanli()` cagrilinca 4 pano ve 187 satir geldi.
  //
  // Yalniz olaylara BAGLI gorunumler yeniden cizilir; `yenile()`yi
  // bastan cagirmak butun API'yi bir kez daha cekmek olurdu.
  cizCanli();
  cizOfis();

  baglan();
  canliYoklamaKur();
  // KABIN: dinleyiciler basta kuruldu; kabin ISTENMEDIKCE ACILMAZ.
  // Acilis durumu SORULUR, varsayilmaz -- panel yeniden acildiginda
  // disarida zaten acik bir kabin olabilir. (Patron bu arada actiysa
  // ikinci kez baglanilmaz.)
  if (!K.acik) {
    kabinGoster(await kabinDurum());
    if (K.acik) kabinBagla();
  }
})();
