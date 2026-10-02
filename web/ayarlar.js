/* AYARLAR (02.10.2026) -- patronun ofis ayarlari TEK yerde.

   Kullanici: "ayarlara tiklayinca ne gorunecek, dogru durust sirala".
   Ayarlar ust cubukta, ayri panolarda ve yalniz komut satirinda daginikti.
   Bu ekran KURAL TASIMAZ: veri /api/ayarlar'dan (ofis/ayarlar.py), her
   degisiklik ayni uca yazilir; var olan uclar (efor, terminal kipi,
   bildirim, hesaplar, guncelleme, izin) aynen kullanilir.
   panel.js'in yardimcilarini kullanir: $, el, al, yolla, bildir, D. */

const AYAR_BOLUMLERI = [
  ["entegrasyon", "Entegrasyonlar"],
  ["takim", "Takımlar ve izinler"],
  ["modeller", "Hesaplar ve modeller"],
  ["calisma", "Çalışma"],
  ["bildirim", "Bildirimler"],
  ["guvenlik", "Onay ve güvenlik"],
  ["yedek", "Yedek ve sağlık"],
];
const AYAR = { bolum: "entegrasyon", veri: null };
try { AYAR.bolum = localStorage.getItem("agentofis.ayar.bolum") || AYAR.bolum; } catch (_) {}

function ayarlarAc(bolum) {
  if (bolum) AYAR.bolum = bolum;
  let p = $("#ayarlar-perde");
  if (!p) {
    p = el("div", "ayarlar-perde");
    p.id = "ayarlar-perde";
    p.onclick = (e) => { if (e.target === p) ayarlarKapat(); };
    document.body.append(p);
  }
  p.hidden = false;
  ayarlarCiz();
}
function ayarlarKapat() {
  const p = $("#ayarlar-perde");
  if (p) p.hidden = true;
  // Ust cubukta kalan gostergeler (motor rozetleri, hesap) tazelensin.
  try { yenile(); } catch (_) {}
}
document.addEventListener("keydown", (e) => {
  const p = $("#ayarlar-perde");
  if (e.key === "Escape" && p && !p.hidden) ayarlarKapat();
});

async function ayarlarCiz() {
  const p = $("#ayarlar-perde");
  const kutu = el("div", "ayarlar-kutu");
  const menu = el("nav", "ayarlar-menu");
  menu.append(el("div", "ayarlar-baslik", "Ayarlar"));
  for (const [k, ad] of AYAR_BOLUMLERI) {
    const b = el("button", "ayarlar-menu-oge" + (k === AYAR.bolum ? " secili" : ""), ad);
    b.onclick = () => {
      AYAR.bolum = k;
      try { localStorage.setItem("agentofis.ayar.bolum", k); } catch (_) {}
      ayarlarCiz();
    };
    menu.append(b);
  }
  const govde = el("section", "ayarlar-govde");
  const kapat = el("button", "ayarlar-kapat", "✕");
  kapat.title = "kapat (Esc)";
  kapat.onclick = ayarlarKapat;
  kutu.append(menu, govde, kapat);
  p.replaceChildren(kutu);
  govde.append(el("div", "bos-yazi", "yükleniyor…"));
  try { AYAR.veri = await al("/api/ayarlar"); }
  catch (e) { govde.replaceChildren(el("div", "form-ipucu uyari", "ayarlar okunamadı: " + e.message)); return; }
  govde.replaceChildren();
  const ad = (AYAR_BOLUMLERI.find((b) => b[0] === AYAR.bolum) || AYAR_BOLUMLERI[0]);
  govde.append(el("h2", "ayarlar-bolum-baslik", ad[1]));
  if ((AYAR.veri.hatalar || []).length)
    govde.append(el("div", "form-ipucu uyari", "Okunamayan: " + AYAR.veri.hatalar.join(" · ")));
  const ciz = { entegrasyon: ayarEntegrasyon, takim: ayarTakim, modeller: ayarModeller,
                calisma: ayarCalisma, bildirim: ayarBildirim, guvenlik: ayarGuvenlik,
                yedek: ayarYedek }[ad[0]];
  const taze = AYAR.taze; AYAR.taze = false;
  await ciz(govde, AYAR.veri, taze);
}

/* -- kucuk yapi taslari -------------------------------------------------- */

async function ayarYaz(anahtar, deger, iyi) {
  try {
    AYAR.veri = await yolla("/api/ayarlar", { anahtar, deger });
    if (iyi) bildir(iyi, "iyi");
  } catch (e) { bildir(String(e.message || e).slice(0, 200), "kotu"); }
  ayarlarCiz();
}

function ayarSatir(kap, baslik, aciklama, kontrol) {
  const s = el("div", "ayar-satir");
  const sol = el("div", "ayar-sol");
  sol.append(el("div", "ayar-ad", baslik));
  if (aciklama) sol.append(el("div", "ayar-aciklama", aciklama));
  s.append(sol);
  if (kontrol) s.append(kontrol);
  kap.append(s);
  return s;
}

function ayarSecim(secenekler, secili, degisti) {
  const k = el("div", "efor-sec ayar-secim");
  for (const [deger, etiket] of secenekler) {
    const b = el("button", deger === secili ? "secili" : "", etiket);
    b.onclick = () => { if (deger !== secili) degisti(deger); };
    k.append(b);
  }
  return k;
}

function ayarAnahtar(acik, degisti, kilitli) {
  const b = el("button", "kip-anahtar" + (acik ? " acik" : ""));
  b.append(el("span", "kip-nokta"), el("span", null, acik ? "açık" : "kapalı"));
  if (kilitli) { b.disabled = true; b.title = kilitli; }
  else b.onclick = () => degisti(!acik);
  return b;
}

function ayarAltBaslik(kap, metin) { kap.append(el("h3", "ayar-alt-baslik", metin)); }

/* -- 1. Entegrasyonlar ve 2. Takimlar: ayrinti ayri adimda ---------------- */

const ENT_DURUM = {
  bagli: ["bağlı", "iyi"], giris_gerekli: ["giriş gerekli", "uyari"],
  hesapta_yok: ["hesapta yok", "soluk"], kurulu_degil: ["kurulu değil", "soluk"],
  sorunlu: ["bağlı · son çağrı düştü", "uyari"], olculemedi: ["ölçülemedi", "soluk"],
};

async function ayarEntegrasyon(kap, _v, taze) {
  const bas = el("div", "ent-bas");
  const not = el("span", "ayar-aciklama", "ölçülüyor…");
  const yb = el("button", "dugme", "Yeniden ölç (~20 sn)");
  yb.onclick = () => { AYAR.taze = true; ayarlarCiz(); };
  if (taze) { yb.disabled = true; yb.textContent = "ölçülüyor…"; }
  bas.append(not, yb);
  kap.append(bas);
  let r;
  try { r = await al("/api/entegrasyon" + (taze ? "?taze=1" : "")); }
  catch (e) { not.textContent = "ölçülemedi: " + e.message; not.classList.add("uyari"); return; }
  not.textContent = "Bağlantılar " + (r.olcum_zamani ? "ölçüldü: " + r.olcum_zamani.slice(0, 16).replace("T", " ")
    + " (UTC)" : "henüz ölçülmedi") + ". Girişi sen yaparsın; ofis yalnız ölçer ve gösterir.";
  const izgara = el("div", "ent-izgara");
  for (const k of r.kartlar) izgara.append(entegrasyonKarti(k));
  kap.append(izgara);
  ayarAnahtarlar(kap, r);
}

function entegrasyonKarti(k) {
  const c = el("div", "ent-kart");
  const ust = el("div", "ent-ust");
  const [yazi, sinif] = ENT_DURUM[k.durum] || [k.durum, "soluk"];
  ust.append(el("b", "ent-ad", k.ad), el("span", "ent-durum " + sinif, yazi));
  c.append(ust, el("div", "ent-alt", `${k.kategori} · ${k.kaynak}`));
  if (k.ayrinti) c.append(el("div", "ent-ayrinti", k.ayrinti));
  c.append(el("div", "ent-risk", k.risk));
  const dug = el("div", "ent-dugmeler");
  const yer = el("div", "ent-yonerge");
  const yonerge = (baslik, adimlar) => {
    if (!yer.hidden && yer.dataset.ne === baslik) { yer.hidden = true; return; }
    yer.dataset.ne = baslik; yer.hidden = false; yer.replaceChildren(el("b", null, baslik));
    for (const a of adimlar) yer.append(a);
  };
  const komutSatiri = (komut) => {
    const s = el("div", "ent-komut");
    const code = el("code", null, komut);
    const kp = el("button", "sohbet-cip", "Kopyala");
    kp.onclick = async () => {
      try { await navigator.clipboard.writeText(komut); bildir("komut kopyalandı", "iyi"); }
      catch (_) { bildir("kopyalanamadı (tarayıcı izin vermedi)", "uyari"); }
    };
    const ko = el("button", "sohbet-cip", "Konsolu aç");
    ko.title = "panelin konsolunda PowerShell açar; komutu yapıştırıp çalıştırırsın";
    ko.onclick = async () => {
      try {
        const r = await yolla("/api/konsol", { klasor: "", motor: "powershell" });
        D.konsolSecili = r.kimlik; D.konsolForm = false;
        ayarlarKapat(); panoSec("konsol"); cizKonsol();
      } catch (e) { bildir("konsol açılamadı: " + e.message, "kotu"); }
    };
    s.append(code, kp, ko);
    return s;
  };
  if (k.durum !== "bagli") {
    const b = el("button", "dugme olumlu", "Bağla");
    b.onclick = () => {
      const adim = [];
      if (k.bagla.url) {
        const a = el("a", null, "claude.ai bağlayıcı sayfası");
        a.href = k.bagla.url; a.target = "_blank"; a.rel = "noopener";
        const s = el("div", "ent-adim"); s.append("1) Hesabında yoksa ekle: ", a);
        adim.push(s);
        adim.push(el("div", "ent-adim", "2) Ofisin kullandığı Claude CLI'a giriş (tarayıcı açılır, sen onaylarsın):"));
      } else adim.push(el("div", "ent-adim", "Terminalde çalıştır (giriş tarayıcıda açılır, sen onaylarsın):"));
      adim.push(komutSatiri(k.bagla.komut));
      adim.push(el("div", "ent-adim soluk", "Bitince 'Yeniden ölç'e bas; durum ölçülmeden 'bağlı' yazmaz."));
      yonerge("Bağla", adim);
    };
    dug.append(b);
  } else {
    const kb = el("button", "dugme", "Kopar");
    kb.onclick = () => yonerge("Kopar", [
      el("div", "ent-adim", "Bu bağlantının girişini silmek için terminalde çalıştır:"),
      komutSatiri(k.kopar.komut),
      el("div", "ent-adim soluk", "Ofis kendisi koparmaz; giriş ve çıkış senin elinde."),
    ]);
    dug.append(kb);
  }
  yer.hidden = true;
  c.append(dug, yer);
  return c;
}

function ayarAnahtarlar(kap, r) {
  ayarAltBaslik(kap, "API anahtarları (ofisin kasası)");
  kap.append(el("div", "ayar-aciklama",
    "Anahtarın kendisi hiçbir yerde gösterilmez; yalnız adı ve kısa parmak izi. Ajanlar anahtarı ortam değişkeni olarak alır, metinde görmez."));
  if (r.kasa_hatasi) kap.append(el("div", "form-ipucu uyari", r.kasa_hatasi));
  if (!r.anahtarlar.length) kap.append(el("div", "bos-yazi", "Kasada anahtar yok."));
  for (const a of r.anahtarlar) {
    const sil = el("button", "dugme olumsuz", "sil");
    sil.onclick = async () => {
      if (!confirm(`${a.ad} kasadan silinsin mi? Geri alınamaz.`)) return;
      try { await yolla(`/api/entegrasyon/anahtar/${encodeURIComponent(a.ad)}/sil`, {}); bildir("silindi", "iyi"); }
      catch (e) { bildir(String(e.message || e), "kotu"); }
      ayarlarCiz();
    };
    ayarSatir(kap, a.ad, "parmak izi: " + a.parmak_izi, sil);
  }
  const k = el("div", "ayar-kontrol");
  const ad = el("input", "ayar-girdi kisa-ad"); ad.placeholder = "AD (ör. OPENROUTER_API_KEY)";
  const deger = el("input", "ayar-girdi"); deger.type = "password"; deger.placeholder = "değer";
  deger.autocomplete = "off";
  const ekle = el("button", "dugme olumlu", "ekle");
  ekle.onclick = async () => {
    try { const x = await yolla("/api/entegrasyon/anahtar", { ad: ad.value, deger: deger.value });
          deger.value = ""; bildir(`${x.ad} eklendi (parmak izi ${x.parmak_izi})`, "iyi"); }
    catch (e) { deger.value = ""; bildir(String(e.message || e), "kotu"); }
    ayarlarCiz();
  };
  k.append(ad, deger, ekle);
  ayarSatir(kap, "Yeni anahtar", "", k);
}

async function ayarTakim(kap, v) {
  kap.append(el("div", "ayar-aciklama",
    "İşaretlediğin bağlayıcıyı o takımın lideri işe kendisi verebilir; sana ayrıca sorulmaz. " +
    "İşaretlemediğin bağlayıcı o takımın işine verilmez (ajan gerekirse senden ister). " +
    "Bağlayıcının içindeki riskli adım (yayına alma, gönderme, silme, para) her durumda sorulur."));
  let ent = { kartlar: [] };
  try { ent = await al("/api/entegrasyon"); } catch (_) {}
  const baglar = ent.kartlar.filter((k) => k.kaynak === "claude.ai bağlayıcısı" && k.durum !== "hesapta_yok");
  for (const t of v.takimlar) {
    ayarAltBaslik(kap, t.ad);
    ayarSatir(kap, "Lider", "", el("span", "ayar-deger", t.lider || "lider yok"));
    ayarSatir(kap, "Ajanlar", "",
      el("span", "ayar-deger uzun", t.ajanlar.map((a) => `${a.ad} (${a.meslek}, ${a.motor})`).join(" · ") || "—"));
    const kutu = el("div", "takim-izin");
    const secili = new Set(t.izinli);
    for (const b of baglar) {
      const et = el("label", "takim-izin-oge");
      const cb = el("input"); cb.type = "checkbox"; cb.checked = secili.has(b.ad);
      cb.onchange = () => {
        if (cb.checked) secili.add(b.ad); else secili.delete(b.ad);
        ayarYaz("takim_izni", { kanat_id: t.id, adlar: [...secili] },
                `${t.ad}: ${b.ad} ${cb.checked ? "izinli" : "izinsiz"}`);
      };
      et.append(cb, document.createTextNode(" " + b.ad));
      if (b.durum !== "bagli") et.append(el("span", "ent-alt", " (" + (ENT_DURUM[b.durum] || [b.durum])[0] + ")"));
      kutu.append(et);
    }
    // Olcumde gorunmeyen eski izinler de gorunur (sessizce kaybolmasin).
    for (const ad of t.izinli.filter((a) => !baglar.some((b) => b.ad === a)))
      kutu.append(el("span", "takim-izin-oge uyari", ad + " (ölçümde yok)"));
    ayarSatir(kap, "Bağlayıcı izni", baglar.length ? "" : "bağlayıcı ölçülemedi", kutu);
  }
  ayarAltBaslik(kap, "Klasörler");
  kap.append(el("div", "ayar-aciklama",
    "Her ajan kendi klasöründe çalışır. Ofis dışı bir klasör İŞ BAŞINA verilir ve kayda geçer; " +
    "ofis geneli kalıcı açık klasör listesi bilerek yok (unutulan açık kapı riskini sıfırlar)."));
  for (const t of v.takimlar)
    for (const a of t.ajanlar)
      ayarSatir(kap, `${a.ad} · ${t.ad}`, "", el("span", "ayar-deger uzun", a.klasor || "—"));
}

/* -- 3. Hesaplar ve modeller ----------------------------------------------- */

const KADEME_AD = { hizli: "hızlı", standart: "standart", guclu: "güçlü" };

async function ayarModeller(kap, v) {
  ayarAltBaslik(kap, "Hesaplar ve kota");
  const h = el("div", "ayar-hesap");
  kap.append(h);
  try {
    const t = D.hesaplar || await hesaplariAl(false);
    hesapPanosuCiz(h, t);
    h.querySelector(".cek-bas")?.remove();
  } catch (e) { h.append(el("div", "form-ipucu uyari", "hesaplar okunamadı: " + e.message)); }

  ayarAltBaslik(kap, "Hangi işte hangi model");
  kap.append(el("div", "ayar-aciklama",
    "Lider her işe zorluk verir; kolay iş hızlı, zor iş güçlü kademeyle koşar. Boş bırakılamaz; kapı modelleri (fable) hiçbir kademeye konmaz."));
  const m = v.modeller;
  for (const [motor, kademeler] of Object.entries(m.kademe)) {
    for (const kd of m.kademeler) {
      const giris = el("input", "ayar-girdi");
      giris.value = kademeler[kd] || "";
      const kaydet = el("button", "dugme", "kaydet");
      kaydet.onclick = () => ayarYaz("kademe", { motor, kademe: kd, model: giris.value },
                                     `${motor} ${KADEME_AD[kd]} → ${giris.value}`);
      const k = el("div", "ayar-kontrol"); k.append(giris, kaydet);
      ayarSatir(kap, `${motor} · ${KADEME_AD[kd] || kd}`, "", k);
    }
  }

  ayarAltBaslik(kap, "Hesabı önceden sıraya al");
  ayarSatir(kap, "Önceden geçiş",
    "Hesabın penceresi dolmak üzereyken yeni iş o hesapta başlamaz, sıradaki hesaba geçer (iş yarıda kesilmesin).",
    ayarAnahtar(m.onceden_gecis, (a) => ayarYaz("onceden_gecis", a)));
  const ROL = { isci: "işçi", lider: "lider" };
  const PEN = { "5s": "5 saatlik", "7g": "haftalık" };
  for (const [rol, esik] of Object.entries(m.esikler)) {
    for (const [pen, deger] of Object.entries(esik)) {
      const g = el("input", "ayar-girdi kisa");
      g.type = "number"; g.min = 50; g.max = 100; g.value = Math.round(deger * 100);
      const kaydet = el("button", "dugme", "kaydet");
      kaydet.onclick = () => ayarYaz("esik", { rol, pencere: pen, deger: Number(g.value) / 100 },
                                     `${ROL[rol]} ${PEN[pen]} eşiği %${g.value}`);
      const k = el("div", "ayar-kontrol"); k.append(g, el("span", null, "%"), kaydet);
      ayarSatir(kap, `${ROL[rol]} · ${PEN[pen]} pencere`, "", k);
    }
  }

  ayarAltBaslik(kap, "Güncelleme");
  ayarSatir(kap, "Otomatik güncelleme",
    "Aynı ailenin yeni modeli ve CLI sürümü deneme turu geçerse kendiliğinden uygulanır; yeni aile ve kapı modeli sana sorulur.",
    ayarAnahtar(m.guncelleme_otomatik, (a) => ayarYaz("guncelleme_otomatik", a)));
  for (const g of m.guncelleme_gecmis || []) {
    const ne = [g.tur, g.motor, g.eski && g.yeni ? `${g.eski} → ${g.yeni}` : (g.yeni || g.anahtar || "")]
      .filter(Boolean).join(" · ");
    let kontrol = el("span", "ayar-deger", g.durum || "");
    if (g.durum === "uygulandi") {
      kontrol = el("button", "dugme", "geri al");
      kontrol.onclick = async () => {
        try { await yolla(`/api/guncelle/gecmis/${g.sira}/geri_al`, {}); bildir("geri alındı", "iyi"); }
        catch (e) { bildir(String(e.message || e).slice(0, 200), "kotu"); }
        ayarlarCiz();
      };
    }
    ayarSatir(kap, ne || "güncelleme", (g.zaman || "").slice(0, 16).replace("T", " "), kontrol);
  }
}

/* -- 4. Calisma -------------------------------------------------------------- */

async function ayarCalisma(kap, v) {
  const c = v.calisma;
  const KIP = [["arka", "arka plan"], ["gercek", "gerçek terminal"]];
  const kipYaz = async (yol, kip) => {
    try { await yolla(yol, { kip }); } catch (e) { bildir(String(e.message || e), "kotu"); }
    ayarlarCiz(); try { cizKip(); } catch (_) {}
  };
  ayarSatir(kap, "Ajanların terminali",
    "Gerçek: Claude/Codex kendi terminalinde çalışır, panoda canlı görünür, içine yazabilirsin. Sonraki turlardan itibaren geçerli. Riskli adım iki kipte de sorulur.",
    ayarSecim(KIP, c.ajan_kipi, (k) => kipYaz("/api/terminal_kipi", k)));
  ayarSatir(kap, "Liderin terminali",
    "Liderin turları (planlama, inceleme, rapor). Arka plan daha hızlı ölçüldü; tavan gereken tur her durumda arkada koşar.",
    ayarSecim(KIP, c.lider_kipi, (k) => ayarYaz("lider_kipi", k)));
  const EFOR = { zorluk: "zorluğa göre", dusuk: "hepsi low", normal: "hepsi medium",
                 yuksek: "hepsi high", cok_yuksek: "hepsi xhigh" };
  ayarSatir(kap, "Efor",
    "Ajanlar ne kadar derin düşünsün. 'Zorluğa göre': lider her işe kolay/orta/zor/çok zor der, efor ona göre seçilir.",
    ayarSecim(c.efor_modlari.map((m) => [m, EFOR[m] || m]), c.efor, async (m) => {
      try { await yolla("/api/efor", { mod: m }); } catch (e) { bildir(String(e.message || e), "kotu"); }
      ayarlarCiz(); try { cizEfor(); } catch (_) {}
    }));
  ayarSatir(kap, "Gömülü tarayıcıyı ajanlar kendiliğinden kullansın",
    "Açıkken tarayıcı gereken iş panelin tarayıcısında canlı koşar (girdiğin hesaplarla); riskli tıklama yine sana sorulur.",
    ayarAnahtar(c.kabin_izle, (a) => ayarYaz("kabin_izle", a)));
}

/* -- 5. Bildirimler ------------------------------------------------------------ */

async function ayarBildirim(kap, v) {
  const b = v.bildirim;
  ayarSatir(kap, "Masaüstü bildirimi",
    b.panelde_calisiyor ? "Windows bildirimi gelir." : "Bu panelde bildirim izleyicisi çalışmıyor (sınama paneli).",
    ayarAnahtar(b.acik, async (a) => {
      try { await yolla("/api/bildirim", { acik: a }); } catch (e) { bildir(String(e.message || e), "kotu"); }
      ayarlarCiz(); try { bildirimDurumu(); } catch (_) {}
    }));
  ayarAltBaslik(kap, "Hangi olaylarda");
  for (const t of b.turler)
    ayarSatir(kap, t.etiket, t.kapatilabilir ? "" : "kapatılamaz — iş seni bekler, bildirim gelmezse sessizce durur",
              ayarAnahtar(t.acik, (a) => ayarYaz("bildirim_turu", { tur: t.anahtar, acik: a }),
                          t.kapatilabilir ? "" : "kapatılamaz"));
}

/* -- 6. Onay ve guvenlik ------------------------------------------------------- */

async function ayarGuvenlik(kap, v) {
  const g = v.guvenlik;
  ayarAltBaslik(kap, "Verdiğin kalıcı izinler");
  if (!g.kalici_izinler.length) kap.append(el("div", "bos-yazi", "Kalıcı izin yok. (Patronun sözü izni iş başına; kalıcı izin yalnız senden: kabuk izin)"));
  for (const i of g.kalici_izinler) {
    const k = el("div", "ayar-kontrol");
    const sb = el("input", "ayar-girdi"); sb.placeholder = "kaldırma sebebi (zorunlu)";
    const kb = el("button", "dugme olumsuz", "kaldır");
    kb.onclick = async () => {
      if (!sb.value.trim()) return sb.focus();
      try { await yolla(`/api/izin/${i.id}/kaldir`, { sebep: sb.value }); bildir("izin kaldırıldı", "iyi"); }
      catch (e) { bildir(String(e.message || e).slice(0, 200), "kotu"); }
      ayarlarCiz();
    };
    k.append(sb, kb);
    ayarSatir(kap, i.desen, `${i.veren || ""} · ${(i.olusturuldu || "").slice(0, 10)}`, k);
  }
  ayarAltBaslik(kap, "Her zaman sorulanlar");
  kap.append(el("div", "ayar-aciklama", "Bunlar izinle de açılmaz; her seferinde sana sorulur."));
  // Sunucunun etiketleri ASCII BUYUK harf (ret metinleri icin); burada
  // okunur Turkce ad. Bilinmeyen sinif sunucudaki adla yine GORUNUR.
  const SINIF_AD = { para: "Para harcama", silme: "Geri alınamaz silme", kimlik: "Şifre / kimlik",
    suphe: "Sayfada gizli talimat görüldükten sonraki eylem", belirsiz: "Riskli sayfada onay",
    kod: "Sayfayı değiştiren kod", bilinmiyor: "Tanınmayan araç",
    masaustu: "Senin masaüstün ve kendi tarayıcın" };
  for (const [k, ad] of Object.entries(g.her_zaman_sorulur))
    ayarSatir(kap, SINIF_AD[k] || ad, "", el("span", "ayar-deger", "her zaman sorulur"));
  ayarAltBaslik(kap, "Para");
  ayarSatir(kap, "Para kilidi",
    g.para_kilitli ? "Ücretli üreticiler kapalı; ajanlar da aşamaz. Açmak bilinçli bir karar: yalnız komut satırından (kabuk gorsel para ac)."
                   : "DİKKAT: ücretli üreticiler AÇIK.",
    el("span", "ayar-deger" + (g.para_kilitli ? "" : " uyari"), g.para_kilitli ? "kilitli (sadece ücretsiz)" : "açık"));
  ayarAltBaslik(kap, "Hafıza kapısının durdurdukları");
  if (!g.hafiza_reddi.length) kap.append(el("div", "bos-yazi", "Durdurulan yazı yok."));
  for (const r of g.hafiza_reddi)
    ayarSatir(kap, r.kim || "?", (r.an || "").slice(0, 16).replace("T", " "), el("span", "ayar-deger uzun", r.metin));
}

/* -- 7. Yedek ve saglik ----------------------------------------------------------- */

async function ayarYedek(kap, v) {
  const y = v.yedek;
  const saat = y.son_saat;
  ayarSatir(kap, "Son yedek",
    y.son ? `${y.son.slice(0, 16).replace("T", " ")} (${saat < 1 ? "1 saatten az" : Math.round(saat) + " saat"} önce)` : "hiç alınmamış",
    (() => { const b = el("button", "dugme", "Şimdi yedekle");
             b.onclick = async () => { b.disabled = true;
               try { await yolla("/api/ayarlar/yedek", {}); bildir("yedek alınıyor — bitince günlükte görünür", "iyi"); }
               catch (e) { bildir(String(e.message || e), "kotu"); } };
             return b; })());
  ayarSatir(kap, "Ek yedek yerleri (Drive vb.)", "",
    el("span", "ayar-deger", (y.hedefler || []).join(" · ") || "yok"));
  if (y.github)
    ayarSatir(kap, "Gizli GitHub yedeği", y.github.uzak,
      el("span", "ayar-deger", y.github.son ? "son: " + y.github.son.slice(0, 16).replace("T", " ") : "hiç gönderilmemiş"));
  ayarAltBaslik(kap, "Bu ofis neyi yapabilir");
  const d = el("div"); kap.append(d);
  await cizYetenek(d);
}
