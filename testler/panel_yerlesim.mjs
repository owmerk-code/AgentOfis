// Panel YERLESIMININ saf islevlerini (DOM'suz) Node'da CALISTIRARAK sinar.
//
// Teknik panel_harita.mjs ile ayni: panel.js metin olarak okunur, islev
// govdeleri parantez eslestirmeyle ayiklanir, `new Function` ile
// degerlendirilir. DOM'a dokunulmaz.
//
// En onemli sinama bir DEGISMEZDIR: hangi girdi gelirse gelsin (bozuk
// saklanmis duzen, rastgele tasima dizisi) her pano duzende TAM BIR KEZ
// bulunur ve her sayi sonlu ve pozitiftir. Rakip v0.2.32'de tam bu
// yuzden "paneller kayboldu" hatasini yasadi.
//
// Cikti duman_panel.py icindir: "GECTI <ad>" / "KALDI <ad> -- <detay>".
// Konsol cp1254 -- cikti ASCII.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const burasi = path.dirname(fileURLToPath(import.meta.url));
const kaynak = readFileSync(path.join(burasi, "..", "web", "panel.js"), "utf8");

function eslesen(bas, ac, kapa) {
  const acilis = kaynak.indexOf(ac, bas);
  let derinlik = 0;
  for (let i = acilis; i < kaynak.length; i++) {
    if (kaynak[i] === ac) derinlik++;
    else if (kaynak[i] === kapa && --derinlik === 0) return kaynak.slice(bas, i + 1);
  }
  throw new Error(`kapanis bulunamadi (${ac}${kapa}) @${bas}`);
}
function islev(ad) {
  const bas = kaynak.indexOf(`function ${ad}(`);
  if (bas < 0) throw new Error(`islev bulunamadi: ${ad}`);
  return eslesen(bas, "{", "}");
}
function sabit(ad) {
  const bas = kaynak.indexOf(`const ${ad} = `);
  if (bas < 0) throw new Error(`sabit bulunamadi: ${ad}`);
  return eslesen(bas, "{", "}") + ";";
}

const ISLEVLER = ["yerlesimVarsayilan", "yerlesimOnar", "panoTasi",
                  "komsuPaylas", "birakmaYeri"];
const kod = [sabit("PANOLAR"), ...ISLEVLER.map(islev)].join("\n");
const Y = new Function(kod + `\nreturn { PANOLAR, ${ISLEVLER.join(", ")} };`)();
const HEPSI = Object.keys(Y.PANOLAR);

let gecen = 0, kalan = 0;
function sina(ad, kosul, detay = "") {
  if (kosul) { gecen++; console.log("GECTI " + ad); }
  else { kalan++; console.log("KALDI " + ad + (detay ? " -- " + detay : "")); }
}

// Degismez: her pano TAM BIR KEZ, her sayi sonlu > 0, bos yigin/sutun yok,
// secili kendi yigininda. Bozuksa sebebi doner (bos dize = saglam).
function bozukluk(y) {
  if (!y || !Array.isArray(y.sutunlar) || !y.sutunlar.length) return "sutun yok";
  const sayac = {};
  for (const s of y.sutunlar) {
    if (!(Number.isFinite(s.gen) && s.gen > 0)) return "gen bozuk: " + s.gen;
    if (typeof s.kapali !== "boolean") return "kapali boolean degil";
    if (!s.yiginlar.length) return "bos sutun";
    for (const g of s.yiginlar) {
      if (!(Number.isFinite(g.yuk) && g.yuk > 0)) return "yuk bozuk: " + g.yuk;
      if (!g.panolar.length) return "bos yigin";
      if (!g.panolar.includes(g.secili)) return "secili yiginda degil: " + g.secili;
      for (const p of g.panolar) sayac[p] = (sayac[p] || 0) + 1;
    }
  }
  for (const p of HEPSI) if (sayac[p] !== 1) return `${p} ${sayac[p] || 0} kez`;
  const fazla = Object.keys(sayac).filter((p) => !HEPSI.includes(p));
  if (fazla.length) return "bilinmeyen pano: " + fazla.join(",");
  return "";
}
const konum = (y, p) => {
  for (let i = 0; i < y.sutunlar.length; i++)
    for (let j = 0; j < y.sutunlar[i].yiginlar.length; j++)
      if (y.sutunlar[i].yiginlar[j].panolar.includes(p)) return [i, j];
  return null;
};
// Anahtar SIRASINDAN bagimsiz esitlik: ayni duzen farkli sirayla
// yazilmis olabilir (varsayilanda `secili` once yaziliyor).
const duz = (x) => Array.isArray(x) ? x.map(duz)
  : x && typeof x === "object"
    ? Object.fromEntries(Object.keys(x).sort().map((k) => [k, duz(x[k])])) : x;
const esit = (a, b) => JSON.stringify(duz(a)) === JSON.stringify(duz(b));

// ------------------------------------------------------------- varsayilan
{
  const v = Y.yerlesimVarsayilan();
  sina("varsayilan duzen GECERLI (her pano bir kez)", !bozukluk(v), bozukluk(v));
  sina("varsayilan: ofis solda", esit(konum(v, "ofis"), [0, 0]));
  sina("varsayilan: kod terminalin ALTINDA ayni sutunda",
       esit(konum(v, "terminal"), [1, 0]) && esit(konum(v, "kod"), [1, 1]));
  sina("varsayilan: onarim onu DEGISTIRMEZ", esit(Y.yerlesimOnar(v), v));
  sina("varsayilan her cagride YENI nesne (paylasilan durum yok)",
       Y.yerlesimVarsayilan() !== Y.yerlesimVarsayilan());
}

// ----------------------------------------------------------------- onarim
{
  for (const [ad, girdi] of [["null", null], ["bos nesne", {}], ["dize", "abc"],
                             ["sayi", 5], ["sutunlar dizi degil", { sutunlar: 3 }],
                             ["bos sutunlar", { sutunlar: [] }]])
    sina(`onarim: ${ad} -> varsayilan`, esit(Y.yerlesimOnar(girdi), Y.yerlesimVarsayilan()));

  const r = Y.yerlesimOnar({ sutunlar: [
    { gen: "2", kapali: "evet", yiginlar: [
      { yuk: NaN, panolar: ["ofis", "uydurma", "ofis", 7], secili: "uydurma" },
      { yuk: -1, panolar: [] },
      null,
    ] },
    { gen: Infinity, yiginlar: [{ yuk: 0, panolar: ["terminal", "ofis"], secili: "ofis" }] },
    { gen: 1, yiginlar: [] },
    "cop",
  ] });
  sina("onarim sonucu GECERLI", !bozukluk(r), bozukluk(r));
  sina("onarim: bilinmeyen pano ATILIR",
       !JSON.stringify(r).includes("uydurma"));
  sina("onarim: tekrarlanan pano ILK yerinde kalir", esit(konum(r, "ofis"), [0, 0]));
  sina("onarim: bozuk sayi varsayilana doner (gen '2', Infinity, NaN, -1, 0)",
       r.sutunlar[0].gen === 1 && r.sutunlar[1].gen === 1 && r.sutunlar[0].yiginlar[0].yuk === 1);
  sina("onarim: kapali yalniz === true", r.sutunlar[0].kapali === false);
  sina("onarim: gecersiz secili -> ilk pano", r.sutunlar[0].yiginlar[0].secili === "ofis");
  sina("onarim: tekrari dusen yiginin secilisi DUZELIR",
       r.sutunlar[1].yiginlar[0].secili === "terminal");
  sina("onarim: bos yigin ve bos sutun ATILIR", r.sutunlar.length === 2);
  sina("onarim: EKSIK panolar son yigina eklenir (kaybolmaz)",
       HEPSI.filter((p) => !["ofis", "terminal"].includes(p))
         .every((p) => esit(konum(r, p), [1, 0])));
  sina("onarim girdiyi DEGISTIRMEZ", (() => {
    const g = { sutunlar: [{ gen: 1, yiginlar: [{ yuk: 1, panolar: ["ofis", "x"] }] }] };
    const once = JSON.stringify(g); Y.yerlesimOnar(g); return JSON.stringify(g) === once;
  })());

  // Rastgele bozuk girdi: degismez HER ZAMAN tutar.
  let tohum = 12345;
  const rnd = () => ((tohum = (tohum * 1103515245 + 12345) % 2147483648) / 2147483648);
  const sec = (d) => d[Math.floor(rnd() * d.length)];
  const cop = [null, undefined, NaN, -1, 0, "x", {}, [], Infinity, 2, 0.5, true];
  const adlar = [...HEPSI, "yok", "", "__proto__", "constructor", "toString"];
  let ilk = "";
  for (let n = 0; n < 2000 && !ilk; n++) {
    const sut = [];
    for (let i = 0; i < Math.floor(rnd() * 5); i++) {
      const yig = [];
      for (let j = 0; j < Math.floor(rnd() * 4); j++) {
        const pl = [];
        for (let k = 0; k < Math.floor(rnd() * 5); k++) pl.push(rnd() < 0.8 ? sec(adlar) : sec(cop));
        yig.push(rnd() < 0.9 ? { yuk: sec(cop), panolar: pl, secili: sec(adlar) } : sec(cop));
      }
      sut.push(rnd() < 0.9 ? { gen: sec(cop), kapali: sec(cop), yiginlar: yig } : sec(cop));
    }
    const b = bozukluk(Y.yerlesimOnar({ sutunlar: sut }));
    if (b) ilk = `#${n}: ${b}`;
  }
  sina("onarim: 2000 rastgele bozuk duzende hic pano KAYBOLMAZ", !ilk, ilk);
  sina("onarim: prototip adlari pano sayilmaz (__proto__, toString)",
       !bozukluk(Y.yerlesimOnar({ sutunlar: [{ yiginlar: [{ panolar: ["__proto__", "toString", "ofis"] }] }] })));
}

// ----------------------------------------------------------------- tasima
{
  const v = Y.yerlesimVarsayilan();
  const once = JSON.stringify(v);

  const a = Y.panoTasi(v, "kod", { sutun: 0, yigin: 0, yer: "sekme" });
  sina("sekme: kod ofisin yigininda sekme olur ve SECILI",
       esit(konum(a, "kod"), [0, 0]) && a.sutunlar[0].yiginlar[0].secili === "kod", bozukluk(a));
  sina("sekme: terminal sutunu tek yigina iner", a.sutunlar[1].yiginlar.length === 1);

  const b = Y.panoTasi(v, "hesap", { sutun: 0, yigin: 0, yer: "ust" });
  sina("ust: hesap ofisin USTUNE yeni yigin",
       esit(konum(b, "hesap"), [0, 0]) && esit(konum(b, "ofis"), [0, 1]), bozukluk(b));
  sina("ust: bolunen yigin yuku ikiye paylasilir (toplam korunur)",
       Math.abs(b.sutunlar[0].yiginlar[0].yuk + b.sutunlar[0].yiginlar[1].yuk - 1) < 1e-9);

  const c = Y.panoTasi(v, "hesap", { sutun: 0, yigin: 0, yer: "alt" });
  sina("alt: hesap ofisin ALTINA", esit(konum(c, "hesap"), [0, 1]));

  const d = Y.panoTasi(v, "kod", { sutun: 0, yigin: 0, yer: "sol" });
  sina("sol: kod EN SOLDA yeni sutun", esit(konum(d, "kod"), [0, 0]) &&
       d.sutunlar.length === v.sutunlar.length + 1, bozukluk(d));
  sina("sol: bolunen sutun genisligi paylasilir",
       Math.abs(d.sutunlar[0].gen + d.sutunlar[1].gen - v.sutunlar[0].gen) < 1e-9);

  const e = Y.panoTasi(v, "raporlar", { sutun: 3, yigin: 0, yer: "sag" });
  sina("sag: raporlar EN SAGDA yeni sutun", esit(konum(e, "raporlar"), [4, 0]));

  const f = Y.panoTasi(v, "ofis", { sutun: 3, yigin: 0, yer: "sekme" });
  sina("sutunun SON panosu gidince sutun kalkar",
       f.sutunlar.length === v.sutunlar.length - 1 && esit(konum(f, "ofis"), [2, 0]), bozukluk(f));

  const g = Y.panoTasi(v, "raporlar", { sutun: 3, yigin: 0, yer: "sekme" });
  sina("ayni yigina sekme: yalniz secili degisir",
       g.sutunlar[3].yiginlar[0].secili === "raporlar" &&
       esit(g.sutunlar[3].yiginlar[0].panolar, v.sutunlar[3].yiginlar[0].panolar));

  const h = Y.panoTasi(v, "raporlar", { sutun: 3, yigin: 0, yer: "alt" });
  sina("cok panolu yigini KENDI icinde bolmek calisir",
       esit(konum(h, "raporlar"), [3, 1]) && esit(konum(h, "gorevler"), [3, 0]), bozukluk(h));

  // Anlamsiz hareketler duzeni DEGISTIRMEZ.
  for (const [ad, pano, hedef] of [
    ["tek panolu yigin kendi ustune", "ofis", { sutun: 0, yigin: 0, yer: "ust" }],
    ["tek panolu yigin kendi altina", "ofis", { sutun: 0, yigin: 0, yer: "alt" }],
    ["tek panolu sutun kendi soluna", "ofis", { sutun: 0, yigin: 0, yer: "sol" }],
    ["tek panolu sutun kendi sagina", "ofis", { sutun: 0, yigin: 0, yer: "sag" }],
    ["bilinmeyen pano", "uydurma", { sutun: 0, yigin: 0, yer: "sekme" }],
    ["olmayan sutun", "kod", { sutun: 99, yigin: 0, yer: "sekme" }],
    ["olmayan yigin", "kod", { sutun: 0, yigin: 99, yer: "ust" }],
    ["bilinmeyen yer", "kod", { sutun: 0, yigin: 0, yer: "capraz" }],
  ]) sina(`degismez hareket: ${ad}`, esit(Y.panoTasi(v, pano, hedef), v));

  sina("tasima girdiyi DEGISTIRMEZ", JSON.stringify(v) === once);

  // Rastgele tasima dizisi: degismez her adimda tutar.
  let tohum = 777;
  const rnd = () => ((tohum = (tohum * 1103515245 + 12345) % 2147483648) / 2147483648);
  const YERLER = ["sekme", "ust", "alt", "sol", "sag"];
  let y = Y.yerlesimVarsayilan(), ilk = "", enCok = 0;
  for (let n = 0; n < 5000 && !ilk; n++) {
    const i = Math.floor(rnd() * (y.sutunlar.length + 1));
    const j = Math.floor(rnd() * 4);
    y = Y.panoTasi(y, HEPSI[Math.floor(rnd() * HEPSI.length)],
                   { sutun: i, yigin: j, yer: YERLER[Math.floor(rnd() * 5)] });
    const bz = bozukluk(y);
    if (bz) ilk = `adim ${n}: ${bz}`;
    enCok = Math.max(enCok, y.sutunlar.length);
  }
  sina("5000 rastgele tasimada hic pano KAYBOLMAZ, hic sayi bozulmaz", !ilk, ilk);
  sina("rastgele tasima gercekten yeni sutun uretti (sahne sinira ulasti)",
       enCok > v.sutunlar.length, "en cok " + enCok);
}

// --------------------------------------------------------- boyut paylasimi
{
  const [a, b] = Y.komsuPaylas(1.1, 1.62, 0.3);
  sina("paylasim toplami KORUR", Math.abs(a + b - 2.72) < 1e-9);
  sina("paylasim orani uygular", Math.abs(a / (a + b) - 0.3) < 1e-9);
  const [c, d] = Y.komsuPaylas(1, 1, -5);
  sina("paylasim alt sinir %10 (pano sifira ezilmez)", Math.abs(c - 0.2) < 1e-9 && Math.abs(d - 1.8) < 1e-9);
  const [e2, f] = Y.komsuPaylas(1, 1, 7);
  sina("paylasim ust sinir %90", Math.abs(e2 - 1.8) < 1e-9 && Math.abs(f - 0.2) < 1e-9);
  // Iki komsunun olculen genisligi 0 ise oran 0/0 = NaN olur (or. gizli
  // pencere). NaN duzene yazilirsa onarim onu 1'e cevirir ve oteki
  // sutunlar sessizce kayar -- paylasim ONCEKI degeri korumali.
  // Piksel alt siniri: 440px'lik iki komsuda 220px alt sinir = %50 --
  // ikisi de alt sinirda, hic kipirdamaz; %30'da oran ona gore kisilir.
  const [p1, p2] = Y.komsuPaylas(1, 1, 0.05, 0.3);
  sina("paylasim PIKSEL alt sinirina uyar (oteki sutundan yer calinmaz)",
       Math.abs(p1 - 0.6) < 1e-9 && Math.abs(p2 - 1.4) < 1e-9, `${p1},${p2}`);
  const [p3, p4] = Y.komsuPaylas(1, 3, 0.9, 0.5);
  sina("paylasim: alt sinir karsilanamiyorsa DOKUNMAZ", p3 === 1 && p4 === 3, `${p3},${p4}`);
  const [g, h] = Y.komsuPaylas(1.1, 1.62, NaN);
  sina("paylasim: gecersiz oran (NaN) degerleri KORUR", g === 1.1 && h === 1.62, `${g},${h}`);
}

// ---------------------------------------------------------- birakma yeri
{
  const k = { left: 100, top: 50, width: 400, height: 332 };
  const Y0 = (x, y) => Y.birakmaYeri(x, y, k, 32);
  sina("baslik cubugu -> sekme", Y0(300, 60) === "sekme");
  sina("sol kenar serit -> sol", Y0(110, 200) === "sol");
  sina("sag kenar serit -> sag", Y0(490, 200) === "sag");
  sina("govdenin ust yarisi -> ust", Y0(300, 150) === "ust");
  sina("govdenin alt yarisi -> alt", Y0(300, 300) === "alt");
  sina("baslik kenar seritten ONCE gelir (sekmeye birakmak her yerden)",
       Y0(105, 60) === "sekme");
}

console.log(`SONUC ${gecen} gecti ${kalan} kaldi`);
process.exit(kalan ? 1 : 0);
