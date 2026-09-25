// web/panel.js icindeki SAF islevleri (DOM'suz) sinar.
// panel.js bir tarayici dosyasi oldugu icin import edilmez: metin olarak
// okunur, ilgili islev govdeleri parantez-eslestirme ile ayiklanir ve
// `new Function` ile degerlendirilir. DOM'a dokunulmaz.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const PANEL_JS = "C:\\Users\\pc\\Desktop\\AgentOfis\\web\\panel.js";
const kaynak = readFileSync(PANEL_JS, "utf8");

// "function ad(" gecen noktadan baslayip esleşen kapanis suslu parantezine
// kadar olan tam islev metnini ayiklar.
function islevAyikla(ad) {
  const imza = `function ${ad}(`;
  const bas = kaynak.indexOf(imza);
  if (bas === -1) throw new Error(`islev bulunamadi: ${ad}`);
  const acilis = kaynak.indexOf("{", bas);
  let derinlik = 0;
  for (let i = acilis; i < kaynak.length; i++) {
    if (kaynak[i] === "{") derinlik++;
    else if (kaynak[i] === "}") {
      derinlik--;
      if (derinlik === 0) return kaynak.slice(bas, i + 1);
    }
  }
  throw new Error(`kapanis parantezi bulunamadi: ${ad}`);
}

function islevKur(ad) {
  const govde = islevAyikla(ad);
  // govde: "function ad(...) {...}" -- degerini dondurup cagirilabilir
  // yapmak icin bir ifade baglamina sariyoruz.
  return new Function(`return (${govde});`)();
}

const jetonYaz = islevKur("jetonYaz");
const sagdanKes = islevKur("sagdanKes");
const raporTemiz = islevKur("raporTemiz");
const turOzeti = islevKur("turOzeti");

let gecen = 0, kalan = 0;
const basarisizlar = [];

function esit(ad, gercek, beklenen) {
  const g = JSON.stringify(gercek);
  const b = JSON.stringify(beklenen);
  if (g === b) {
    gecen++;
  } else {
    kalan++;
    basarisizlar.push(`${ad}: beklenen ${b}, gelen ${g}`);
  }
}

// jetonYaz
esit("jetonYaz(1407411)", jetonYaz(1407411), "1.41M");
esit("jetonYaz(142571)", jetonYaz(142571), "143k");
esit("jetonYaz(0)", jetonYaz(0), "0");

// raporTemiz: KANIT ile baslayan satirlari atar, kalanlari korur
{
  const govde = [
    "ilk satir kalir",
    "KANIT terminal: node test.mjs calisti",
    "ikinci satir kalir",
    "  KANIT diff: dosya degisti  ",
  ].join(String.fromCharCode(10));
  const sonuc = raporTemiz(govde);
  esit("raporTemiz KANIT satirlarini atar", sonuc, "ilk satir kalir ikinci satir kalir");
}

// sagdanKes
esit("sagdanKes('cinar: x -> cinar')", sagdanKes("cinar: x -> cinar"), "x");

// turOzeti: bozuk JSON'da bos string doner, patlamaz
esit("turOzeti(bozuk JSON)", turOzeti("{ bozuk"), "");

console.log(`gecen: ${gecen}  kalan: ${kalan}`);
if (kalan > 0) {
  for (const b of basarisizlar) console.error("KALAN -> " + b);
  process.exitCode = 1;
}
