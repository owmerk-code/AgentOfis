import assert from "node:assert/strict";
import { tohumluRng, yuruyusOlustur } from "../ofis_yurume/hareket.mjs";

const alan = { x: 0, y: 0, w: 100, h: 55 };
const masa = { x: 46, y: 25 };
const engeller = [{ x: 41, y: 20, w: 10, h: 10 }];
const ayar = { konum: { x: 20, y: 40 }, masa, alan, engeller,
               hiz: 8, pay: 2, bekleme: [0.3, 0.7], rng: tohumluRng(31) };
const ajan = yuruyusOlustur(ayar);
const iz = [ajan.oku().konum];
for (let i = 1; i <= 3; i++) iz.push(ajan.tick(1).konum);

for (const [i, p] of iz.entries()) {
  console.log(`boşta t=${i}: (${p.x.toFixed(3)}, ${p.y.toFixed(3)})`);
  assert.ok(p.x >= alan.x && p.x <= alan.x + alan.w);
  assert.ok(p.y >= alan.y && p.y <= alan.y + alan.h);
  assert.ok(p.x < engeller[0].x || p.x > engeller[0].x + engeller[0].w ||
            p.y < engeller[0].y || p.y > engeller[0].y + engeller[0].h);
}
assert.equal(new Set(iz.map((p) => `${p.x},${p.y}`)).size, 4);

const ayniTohum = yuruyusOlustur({ ...ayar, rng: tohumluRng(31) });
for (let i = 1; i <= 3; i++)
  assert.deepEqual(ayniTohum.tick(1).konum, iz[i]);
console.log("ok: boşta hareket ve sabit tohum");

ajan.durumAyarla("çalışıyor");
assert.deepEqual(ajan.oku().hedef, masa);
for (let i = 0; i < 20; i++) ajan.tick(1);
assert.deepEqual(ajan.oku().konum, masa);
console.log(`çalışıyor: (${ajan.oku().konum.x}, ${ajan.oku().konum.y})`);
for (let i = 0; i < 5; i++) assert.deepEqual(ajan.tick(1).konum, masa);
console.log("ok: masaya vardı ve çalışırken sabit kaldı");

ajan.durumAyarla("boşta");
const once = ajan.oku().konum;
ajan.tick(1);
assert.notDeepEqual(ajan.oku().konum, once);
console.log("ok: iş bitince dolaşma yeniden başladı");

assert.throws(() => ajan.tick(-1), /zaman/);
assert.throws(() => ajan.durumAyarla("bilinmiyor"), /durum/);
console.log("passed: ofis yürüyüşü");
