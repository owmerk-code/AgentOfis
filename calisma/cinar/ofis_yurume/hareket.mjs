// Harita birimleri yuzdelik koordinattir. Bu modul DOM ve zamanlayici kullanmaz.
export function tohumluRng(tohum) {
  let durum = tohum >>> 0;
  return () => ((durum = (1664525 * durum + 1013904223) >>> 0) / 2 ** 32);
}

function noktaGecerli(p, alan, engeller, pay) {
  if (p.x < alan.x + pay || p.x > alan.x + alan.w - pay ||
      p.y < alan.y + pay || p.y > alan.y + alan.h - pay) return false;
  return engeller.every((e) =>
    p.x < e.x - pay || p.x > e.x + e.w + pay ||
    p.y < e.y - pay || p.y > e.y + e.h + pay);
}

function yolAcik(a, b, alan, engeller, pay) {
  if (b.x < alan.x + pay || b.x > alan.x + alan.w - pay ||
      b.y < alan.y + pay || b.y > alan.y + alan.h - pay) return false;
  return engeller.every((e) => {
    const sol = e.x - pay, sag = e.x + e.w + pay;
    const ust = e.y - pay, alt = e.y + e.h + pay;
    // Masa basindan kalkisa izin ver; hedefe giderken diger engelleri kesme.
    if (a.x >= sol && a.x <= sag && a.y >= ust && a.y <= alt) return true;
    let giris = 0, cikis = 1;
    for (const [bas, fark, min, max] of
      [[a.x, b.x - a.x, sol, sag], [a.y, b.y - a.y, ust, alt]]) {
      if (Math.abs(fark) < 1e-12) {
        if (bas < min || bas > max) return true;
      } else {
        const t1 = (min - bas) / fark, t2 = (max - bas) / fark;
        giris = Math.max(giris, Math.min(t1, t2));
        cikis = Math.min(cikis, Math.max(t1, t2));
      }
    }
    return giris > cikis;
  });
}

export function yuruyusOlustur({ konum, masa, alan, engeller = [],
                                hiz = 20, pay = 1, rng = Math.random,
                                bekleme = [0.4, 1.2] }) {
  if (!konum || !masa || !alan || !Number.isFinite(hiz) || hiz <= 0 ||
      !Number.isFinite(pay) || pay < 0 ||
      !Number.isFinite(bekleme[0]) || !Number.isFinite(bekleme[1]) ||
      bekleme[0] < 0 || bekleme[1] < bekleme[0])
    throw new Error("gecersiz yuruyus ayari");

  const s = { konum: { ...konum }, masa: { ...masa },
              durum: "boşta", hedef: null, bekle: 0 };
  const rastgele = () => {
    const r = rng();
    if (!Number.isFinite(r) || r < 0 || r >= 1) throw new Error("RNG [0,1) donmeli");
    return r;
  };
  const hedefSec = () => {
    for (let i = 0; i < 200; i++) {
      const p = { x: alan.x + pay + rastgele() * (alan.w - 2 * pay),
                  y: alan.y + pay + rastgele() * (alan.h - 2 * pay) };
      if (Math.hypot(p.x - s.konum.x, p.y - s.konum.y) > 0.5 &&
          noktaGecerli(p, alan, engeller, pay) &&
          yolAcik(s.konum, p, alan, engeller, pay)) return p;
    }
    // Engeller alani doldurduysa rastgele sonsuz donguye girmesin.
    return null;
  };

  return {
    durumAyarla(durum) {
      if (durum !== "boşta" && durum !== "çalışıyor") throw new Error("gecersiz durum");
      if (s.durum === durum) return;
      s.durum = durum;
      s.hedef = durum === "çalışıyor" ? { ...s.masa } : null;
      s.bekle = 0;
    },
    tick(dt) {
      if (!Number.isFinite(dt) || dt < 0) throw new Error("gecersiz zaman adimi");
      let kalan = dt;
      for (let tur = 0; kalan > 0 && tur < 1000; tur++) {
        if (s.durum === "boşta" && s.bekle > 0) {
          const sure = Math.min(kalan, s.bekle);
          kalan -= sure;
          s.bekle -= sure;
          if (s.bekle > 1e-9) break;
          s.bekle = 0;
        }
        if (!s.hedef) s.hedef = s.durum === "çalışıyor" ? { ...s.masa } : hedefSec();
        if (!s.hedef) break;
        const mesafe = Math.hypot(s.hedef.x - s.konum.x, s.hedef.y - s.konum.y);
        const adim = Math.min(mesafe, hiz * kalan);
        if (mesafe > 0) {
          s.konum.x += (s.hedef.x - s.konum.x) * adim / mesafe;
          s.konum.y += (s.hedef.y - s.konum.y) * adim / mesafe;
        }
        kalan -= adim / hiz;
        if (adim + 1e-9 < mesafe) break;
        s.konum = { ...s.hedef };
        s.hedef = null;
        if (s.durum === "çalışıyor") break;
        s.bekle = bekleme[0] + rastgele() * (bekleme[1] - bekleme[0]);
      }
      return this.oku();
    },
    oku() {
      return { konum: { ...s.konum }, masa: { ...s.masa }, durum: s.durum,
               hedef: s.hedef && { ...s.hedef }, bekle: s.bekle };
    },
  };
}
