// Ofis haritasinin SAF islevlerini (DOM'suz) Node'da CALISTIRARAK sinar.
//
// Teknik ofisin kendisinden: #23 (bilge) `calisma/cinar/test_panel_js.mjs`.
// panel.js bir tarayici dosyasidir, import edilmez: metin olarak okunur,
// islev ve sabit govdeleri parantez eslestirmeyle ayiklanir ve tek bir
// kapsamda `new Function` ile degerlendirilir. DOM'a dokunulmaz.
//
// Neden metne bakmak yetmiyor: harita konum, yol ve ziyaretci yerlesimi
// URETIR -- bunlarin dogrulugu ancak islev kosturulunca gorunur. Iki
// kusur tam boyle bulundu (23.09.2026): ziyaretci sorulanin yanina sabit
// aralikla konuyor ve ikinci kisinin TAM USTUNE dusuyordu; uc masalik
// kanatta masalar sola yasli kaliyordu.
//
// Cikti duman_panel.py icindir: her satir "GECTI <ad>" ya da
// "KALDI <ad> -- <detay>". Konsol cp1254 -- ciktı ASCII.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const burasi = path.dirname(fileURLToPath(import.meta.url));
const kaynak = readFileSync(path.join(burasi, "..", "web", "panel.js"), "utf8");

// `bas`tan baslayip ilk acilan parantezin ESINE kadar olan metin.
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
  const ilk = kaynak[kaynak.indexOf("=", bas) + 2];
  return eslesen(bas, ilk, ilk === "{" ? "}" : "]") + ";";
}

const ISLEVLER = ["odaKutusu", "masaYerleri", "odaYerleri", "ajanKonumlari",
                  "kapiX", "yolBul", "karistir", "haliRengi"];
const kod = [sabit("HARITA"), sabit("ODALAR"), ...ISLEVLER.map(islev)].join("\n");
const H = new Function(kod + `\nreturn { HARITA, ODALAR, ${ISLEVLER.join(", ")} };`)();

let gecen = 0, kalan = 0;
function sina(ad, kosul, detay = "") {
  if (kosul) { gecen++; console.log("GECTI " + ad); }
  else { kalan++; console.log("KALDI " + ad + (detay ? " -- " + detay : "")); }
}
const icinde = (p, r, pay = 0.01) =>
  p.x >= r.x - pay && p.x <= r.x + r.w + pay && p.y >= r.y - pay && p.y <= r.y + r.h + pay;
const uzaklik = (p, q) => Math.hypot(p.x - q.x, p.y - q.y);

// ---------------------------------------------------------------- odalar
const alt = H.HARITA.alt;
{
  let bas = 0, bosluk = [];
  for (const [ad, sol, gen] of alt) { if (Math.abs(sol - bas) > 1e-9) bosluk.push(ad); bas = sol + gen; }
  sina("alt odalar BITISIK (bosluk/binme yok)", bosluk.length === 0, bosluk.join(","));
  sina("alt odalar tam genislik (0..100)", Math.abs(bas - 100) < 1e-9, String(bas));
  const haritada = new Set(alt.map((a) => a[0]));
  const eksik = H.ODALAR.map((o) => o[0]).filter((k) => k !== "masa" && !haritada.has(k));
  sina("her masa-disi odanin haritada YERI var", eksik.length === 0, eksik.join(","));
  const kisasiz = H.ODALAR.filter((o) => !o[3]).map((o) => o[0]);
  sina("her odanin haritada KISA adi var", kisasiz.length === 0, kisasiz.join(","));
}

// ---------------------------------------------------------------- masalar
{
  const salon = H.odaKutusu("masa");
  let tasan = [], dar = [], ortasiz = [];
  for (let n = 1; n <= 20; n++) {
    const y = H.masaYerleri(n);
    if (y.some((p) => !icinde(p, salon))) tasan.push(n);
    // Ayni siradaki komsu masalar arasi en az bir masa+bosluk (yuzde).
    const siralar = {};
    for (const p of y) (siralar[p.y.toFixed(3)] = siralar[p.y.toFixed(3)] || []).push(p.x);
    for (const xs of Object.values(siralar)) {
      xs.sort((a, b) => a - b);
      for (let i = 1; i < xs.length; i++) if (xs[i] - xs[i - 1] < 100 / 6 - 1e-6) dar.push(n);
      // Her sira ORTALI: ilk ve son masa kenara esit uzaklikta.
      if (Math.abs(xs[0] - (100 - xs[xs.length - 1])) > 1e-6) ortasiz.push(n);
    }
  }
  sina("masalar salonun ICINDE (n=1..20)", tasan.length === 0, tasan.join(","));
  sina("ayni siradaki masalar SIKISMIYOR", dar.length === 0, [...new Set(dar)].join(","));
  sina("eksik sira ORTALANIYOR (3 masa sola yasli kalmiyor)", ortasiz.length === 0,
       [...new Set(ortasiz)].join(","));
  const uc = H.masaYerleri(3).map((p) => +p.x.toFixed(1));
  sina("3 masa tam genislige yayiliyor", JSON.stringify(uc) === "[16.7,50,83.3]", JSON.stringify(uc));
}

// ---------------------------------------------------------------- oda ici
{
  let tasan = [];
  for (const [oda] of alt) for (let n = 1; n <= 8; n++)
    if (H.odaYerleri(oda, n).some((p) => !icinde(p, H.odaKutusu(oda)))) tasan.push(`${oda}:${n}`);
  sina("ayaktakiler kendi odasinin ICINDE", tasan.length === 0, tasan.join(","));
}

// ---------------------------------------------------------------- kim nerede
const a = (ad, oda, kime = "") => ({ ad, oda, kime });
function yerlestir(ajanlar) {
  const sirali = [...ajanlar].sort((p, q) => p.ad.localeCompare(q.ad, "tr"));
  const yerler = H.masaYerleri(sirali.length);
  const masaYeri = {};
  sirali.forEach((x, i) => { masaYeri[x.ad] = yerler[i]; });
  return { masaYeri, konum: H.ajanKonumlari(ajanlar, masaYeri) };
}
{
  // Olculen sahne (ornek ofis, 23.09.2026): ziyaretci sorulanin odasina.
  const ajanlar = [a("demir", "inceleme"), a("cinar", "inceleme"),
                   a("yaprak", "bekleme", "demir"), a("bilge", "bekleme", "insan"),
                   a("kaya", "onay_kapisi", "insan"), a("deniz", "masa"),
                   a("ruzgar", "mola")];
  const { masaYeri, konum } = yerlestir(ajanlar);
  sina("calisan ajan KENDI masasinda oturuyor",
       konum.deniz.oturuyor === true && uzaklik(konum.deniz, masaYeri.deniz) < 1e-9);
  sina("ajana soru soran ZIYARETCI olarak isaretli", konum.yaprak.ziyaret === "demir");
  sina("ziyaretci sorulanin ODASINDA (ayakta sorulan)",
       icinde(konum.yaprak, H.odaKutusu("inceleme")), JSON.stringify(konum.yaprak));
  // Olculen kusur: ziyaretci ikinci kisinin TAM USTUNE dusuyordu.
  // Olcut GORSEL ortusme: bir ajan (sprite + ad) haritanin ~%7 eni,
  // ~%10 boyu. Once "en yakin >= %5" yazmistim -- eski kusurlu yerlesimde
  // o cift TAM 5.0 cikiyor ve sinama GECIYORDU; esik kusuru yakalamiyordu.
  const adlar = Object.keys(konum);
  const binen = [];
  for (let i = 0; i < adlar.length; i++) for (let j = i + 1; j < adlar.length; j++) {
    const p = konum[adlar[i]], q = konum[adlar[j]];
    if (Math.abs(p.x - q.x) < 7 && Math.abs(p.y - q.y) < 10)
      binen.push(`${adlar[i]}/${adlar[j]} dx=${Math.abs(p.x - q.x).toFixed(1)} dy=${Math.abs(p.y - q.y).toFixed(1)}`);
  }
  sina("kimse kimsenin USTUNE dusmuyor", binen.length === 0, binen.join(" | "));
  sina("insana soru soran BEKLEME odasinda",
       icinde(konum.bilge, H.odaKutusu("bekleme")) && !konum.bilge.ziyaret);
  sina("onay bekleyen ONAY odasinda", icinde(konum.kaya, H.odaKutusu("onay_kapisi")));
  sina("bostaki MOLA odasinda", icinde(konum.ruzgar, H.odaKutusu("mola")));
}
{
  // Sorulan MASASINDA: ziyaretci masanin yanina gider, masaya oturmaz.
  const { masaYeri, konum } = yerlestir([a("ada", "masa"), a("can", "bekleme", "ada")]);
  sina("masadakine soran masanin YANINDA durur",
       konum.can.oturuyor === false && Math.abs(konum.can.x - masaYeri.ada.x) <= 10 &&
       konum.can.ziyaret === "ada", JSON.stringify(konum.can));
  // Haritada olmayana (baska kanat) soran: bekleme odasi -- uydurmaz.
  const b = yerlestir([a("ada", "masa"), a("can", "bekleme", "yabanci")]).konum;
  sina("haritada olmayana soran BEKLEME odasinda", icinde(b.can, H.odaKutusu("bekleme")) && !b.can.ziyaret);
  // Bilinmeyen oda: mola'ya duser (haritada yeri olmayan hal).
  const c = yerlestir([a("ada", "uzay")]).konum;
  sina("bilinmeyen hal MOLA'ya dusuyor", icinde(c.ada, H.odaKutusu("mola")));
}

// ---------------------------------------------------------------- yol
{
  // Yol DUVARIN ICINDEN gecmez: salon/alt oda sinirini yalnizca bir
  // KAPIDAN, dik olarak gecer.
  const ayrim = H.HARITA.ayrim;
  const kapilar = alt.map(([, sol, gen]) => sol + gen / 2);
  const noktalar = [{ x: 12.5, y: 33.6 }, { x: 87.5, y: 45.4 }, ...alt.map(([oda]) => {
    const r = H.odaKutusu(oda); return { x: r.x + r.w / 2, y: r.y + r.h * 0.8 };
  })];
  let kotu = [];
  for (const p of noktalar) for (const q of noktalar) {
    if (p === q) continue;
    const yol = [p, ...H.yolBul(p, q)];
    const son = yol[yol.length - 1];
    if (uzaklik(son, q) > 1e-9) kotu.push("hedefe varmiyor");
    for (let i = 1; i < yol.length; i++) {
      const u = yol[i - 1], v = yol[i];
      const gecer = (u.y < ayrim) !== (v.y < ayrim);
      if (gecer && !(Math.abs(u.x - v.x) < 1e-9 && kapilar.some((k) => Math.abs(k - u.x) < 1e-9)))
        kotu.push(`${JSON.stringify(u)}->${JSON.stringify(v)}`);
      // Alt odalar arasi DOGRUDAN gecis yok: iki farkli alt odanin
      // icindeki noktalar arasinda yatay adim, duvari keser.
      if (u.y >= ayrim && v.y >= ayrim && H.kapiX(u) !== H.kapiX(v))
        kotu.push(`alt-alt ${JSON.stringify(u)}->${JSON.stringify(v)}`);
    }
  }
  sina("yol duvardan DEGIL kapidan geciyor", kotu.length === 0, kotu.slice(0, 3).join(" | "));
}

// ---------------------------------------------------------------- hali
{
  const notr = H.haliRengi(null);
  const mavi = H.haliRengi({ renk: "#6BA3C7" });
  const kirmizi = H.haliRengi({ renk: "#E0785A" });
  const hex = (h) => /^#[0-9a-f]{6}$/i.test(h);
  sina("hali rengi gecerli renk", [...notr, ...mavi, ...kirmizi].every(hex));
  sina("kanat halisi KANADIN renginden (farkli kanat, farkli hali)",
       mavi[0] !== kirmizi[0] && mavi[0] !== notr[0]);
  sina("TUM OFIS notr (bir kanadin rengini ODUNC almaz)",
       !["#6ba3c7", "#e0785a"].includes(notr[0].toLowerCase()));
}

console.log(`SONUC ${gecen} ${kalan}`);
if (kalan) process.exitCode = 1;
