// Hafiza CIZGESININ saf yerlesimini (DOM'suz) Node'da CALISTIRARAK sinar.
//
// Teknik panel_harita.mjs ile ayni: panel.js metin olarak okunur, islev
// govdesi parantez eslestirmeyle ayiklanir, `new Function` ile
// degerlendirilir.
//
// Cizge SECIMIN HARITASIDIR: kenarlar sunucudan (`baglar`) gelir ve
// burada yalniz yerlestirilir. Sinanan: yalniz baga katilan bilgi
// cizilir, kirik hedef hayalet dugum olur, yerlesim KARARLIDIR (ayni
// girdi ayni resim), sinir asilinca en az bagli olan gizlenir ve SAYISI
// soylenir, her kenarin iki ucu da cizilmis bir dugumdur.
//
// Cikti duman_panel.py icindir: "GECTI <ad>" / "KALDI <ad> -- <detay>".

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const burasi = path.dirname(fileURLToPath(import.meta.url));
const kaynak = readFileSync(path.join(burasi, "..", "web", "panel.js"), "utf8");

function islev(ad) {
  const bas = kaynak.indexOf(`function ${ad}(`);
  if (bas < 0) throw new Error(`islev bulunamadi: ${ad}`);
  const acilis = kaynak.indexOf("{", bas);
  let derinlik = 0;
  for (let i = acilis; i < kaynak.length; i++) {
    if (kaynak[i] === "{") derinlik++;
    else if (kaynak[i] === "}" && --derinlik === 0) return kaynak.slice(bas, i + 1);
  }
  throw new Error("kapanis yok: " + ad);
}
const hafizaCizgesi = new Function(islev("hafizaCizgesi") + "\nreturn hafizaCizgesi;")();

let gecen = 0, kalan = 0;
function sina(ad, kosul, detay = "") {
  if (kosul) { gecen++; console.log("GECTI " + ad); }
  else { kalan++; console.log("KALDI " + ad + (detay ? " -- " + detay : "")); }
}

const b = (konu, anahtar, kirik = false) => ({ konu, anahtar, kirik });
const bilgi = (konu, baglar = [], kaynak = "insan") =>
  ({ konu, anahtar: konu.toLowerCase(), kaynak, surum: 1, baglar });

// Bag yok -> cizge bos, bagsiz sayisi soylenir.
let c = hafizaCizgesi([bilgi("a"), bilgi("b")], 420, 340);
sina("bag yokken dugum YOK", c.dugumler.length === 0 && c.kenarlar.length === 0);
sina("  bagsiz bilgi SAYILIYOR", c.bagsiz === 2, String(c.bagsiz));

// Basit bag + kirik bag.
const girdi = [
  bilgi("kargo bedeli", [b("lojistik", "lojistik")]),
  bilgi("lojistik", [b("depo", "depo", true)]),
  bilgi("tek basina"),
];
c = hafizaCizgesi(girdi, 420, 340);
const adlar = c.dugumler.map((d) => d.anahtar).sort();
sina("yalniz baga katilanlar cizildi", JSON.stringify(adlar) ===
     JSON.stringify(["?depo", "kargo bedeli", "lojistik"]), JSON.stringify(adlar));
sina("kirik hedef HAYALET dugum", c.dugumler.some((d) => d.anahtar === "?depo" && d.kirik));
sina("kirik kenar isaretli", c.kenarlar.some((k) => k.hedef === "?depo" && k.kirik));
sina("bagsiz bilgi 1", c.bagsiz === 1, String(c.bagsiz));
const yer = Object.fromEntries(c.dugumler.map((d) => [d.anahtar, d]));
sina("her kenarin iki ucu da CIZILMIS dugum",
     c.kenarlar.every((k) => yer[k.kaynak] && yer[k.hedef]
       && k.x1 === yer[k.kaynak].x && k.y2 === yer[k.hedef].y));
sina("dugumler cercevenin ICINDE",
     c.dugumler.every((d) => d.x >= 0 && d.x <= 420 && d.y >= 0 && d.y <= 340));

// Kendine bag cizilmez.
c = hafizaCizgesi([bilgi("x", [b("x", "x")])], 420, 340);
sina("kendine bag cizilmiyor", c.kenarlar.length === 0 && c.dugumler.length === 0);

// KARARLILIK: sira degisse de ayni resim.
const r1 = JSON.stringify(hafizaCizgesi(girdi, 420, 340).dugumler);
const r2 = JSON.stringify(hafizaCizgesi([...girdi].reverse(), 420, 340).dugumler);
sina("yerlesim KARARLI (girdi sirasi degismez)", r1 === r2);

// SINIR: yildiz -- merkez her seye bagli. Sinir 5 iken en az bagli
// yapraklar gizlenir, merkez kalir; gizlenen SAYILIR.
const yapraklar = Array.from({ length: 10 }, (_, i) => bilgi("y" + i));
const merkez = bilgi("merkez", yapraklar.map((y) => b(y.konu, y.anahtar)));
c = hafizaCizgesi([merkez, ...yapraklar], 420, 340, 5);
sina("sinir asilinca en fazla 5 dugum", c.dugumler.length === 5, String(c.dugumler.length));
sina("  en cok bagli (merkez) KALDI", c.dugumler.some((d) => d.anahtar === "merkez"));
sina("  gizlenen SAYILIYOR", c.gizlenen === 6, String(c.gizlenen));
sina("  gizlenene giden kenar CIZILMIYOR",
     c.kenarlar.every((k) => c.dugumler.some((d) => d.anahtar === k.hedef)));

console.log(`SONUC ${gecen} gecti ${kalan} kaldi`);
