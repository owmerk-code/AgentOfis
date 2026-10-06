/* TELEFON SAYFASI (06.10.2026, Asama 3). Kural sunucuda: panelin giris kapisi
   (`telefon.py`) yalniz eslesmis cihaza ve izinli uclara izin verir. Bu sayfa
   panelin AYNI uclarini kullanir; yeni kural yazmaz. */
"use strict";
const $ = (s) => document.querySelector(s);

function el(etiket, sinif, metin) {
  const e = document.createElement(etiket);
  if (sinif) e.className = sinif;
  if (metin != null) e.textContent = metin;
  return e;
}

let bildiriZaman = null;
function bildir(metin) {
  const b = $("#bildiri");
  b.textContent = metin;
  b.classList.remove("gizli");
  clearTimeout(bildiriZaman);
  bildiriZaman = setTimeout(() => b.classList.add("gizli"), 3500);
}

async function al(yol, govde) {
  const ayar = govde === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(govde),
  };
  const r = await fetch(yol, { credentials: "same-origin", ...ayar });
  let j = null;
  try { j = await r.json(); } catch (_) { /* bos */ }
  if (!r.ok) throw new Error((j && j.detail) || `hata ${r.status}`);
  return j;
}

/* ---------------------------------------------------------------- eslestirme */
$("#eslestir-dugme").onclick = async () => {
  try {
    await al("/api/telefon/eslestir", { kod: $("#kod").value.trim().toUpperCase(), ad: $("#cihaz-ad").value.trim() });
    bildir("Telefon eşleşti.");
    basla();
  } catch (e) { bildir(e.message); }
};

/* ---------------------------------------------------------------- bekleyenler */
function onayKarti(a) {
  const k = el("div", "kart");
  k.append(el("div", "ust", `${a.isteyen} onay istiyor · `));
  k.firstChild.append(el("span", "risk", "risk: " + a.risk));
  k.append(el("div", "govde", a.eylem));
  const not = el("input");
  not.placeholder = "Not (ret için zorunlu)";
  const s = el("div", "satir");
  const ver = el("button", "iyi", "Bir kez onayla");
  const red = el("button", "tehlike", "Reddet");
  ver.onclick = () => eylem(`/api/onay/${a.id}`, { onayla: true, not_: not.value, kapsam: "eylem" }, "Onaylandı");
  red.onclick = () => {
    if (!not.value.trim()) { not.focus(); return bildir("Ret için kısa bir gerekçe yaz."); }
    eylem(`/api/onay/${a.id}`, { onayla: false, not_: not.value }, "Reddedildi");
  };
  s.append(ver, red);
  k.append(not, s);
  return k;
}

function soruKarti(q) {
  const k = el("div", "kart");
  k.append(el("div", "ust", `${q.gonderen} soruyor`), el("div", "govde", q.govde));
  const c = el("textarea");
  c.rows = 2;
  c.placeholder = "Cevabın";
  const b = el("button", "ana", "Cevapla");
  b.onclick = () => { if (c.value.trim()) eylem(`/api/soru/${q.id}/cevap`, { metin: c.value }, "Cevap gitti"); };
  k.append(c, b);
  return k;
}

function hafizaKarti(h) {
  const k = el("div", "kart");
  k.append(el("div", "ust", "hafızaya yazayım mı?"), el("div", "govde", `${h.konu} → ${h.icerik}`));
  const s = el("div", "satir");
  const y = el("button", "iyi", "Yaz");
  const n = el("button", null, "Yazma");
  y.onclick = () => eylem(`/api/hafiza_onerisi/${h.id}`, { yaz: true }, "Hafızaya yazıldı");
  n.onclick = () => eylem(`/api/hafiza_onerisi/${h.id}`, { yaz: false }, "Yazılmadı");
  s.append(y, n);
  k.append(s);
  return k;
}

async function eylem(yol, govde, basari) {
  try { await al(yol, govde); bildir(basari); } catch (e) { bildir(e.message); }
  yenile();
}

async function bekleyenleriCiz() {
  const [b, o] = await Promise.all([al("/api/bekleyenler"), al("/api/oneriler").catch(() => ({}))]);
  const kap = $("#bekleyenler");
  kap.innerHTML = "";
  const hafiza = (o && o.hafiza) || [];
  for (const a of b.onaylar || []) if (!a.giris) kap.append(onayKarti(a));
  for (const q of b.sorular || []) kap.append(soruKarti(q));
  for (const h of hafiza) kap.append(hafizaKarti(h));
  const n = (b.onaylar || []).filter((a) => !a.giris).length + (b.sorular || []).length + hafiza.length;
  $("#bekleyen-sayi").textContent = n ? String(n) : "";
  if (!n) kap.append(el("div", "soluk", "Senden beklenen bir şey yok."));
}

/* ---------------------------------------------------------------- isler */
const DURUM_AD = { calisiyor: "çalışıyor", inceleme: "incelemede", hazir: "sırada", bekliyor: "bekliyor", bitti: "bitti" };
async function isleriCiz() {
  const t = await al("/api/tahta");
  const kap = $("#isler");
  kap.innerHTML = "";
  const sira = ["calisiyor", "inceleme", "hazir", "bekliyor"];
  let n = 0;
  for (const d of sira) for (const g of t[d] || []) {
    n++;
    const s = el("div", "is");
    s.append(el("div", null, `#${g.no} ${g.baslik}` + (g.sahip ? ` · ${g.sahip}` : "")),
             el("div", "d", DURUM_AD[d] + (g.duraklatildi ? " · durdu" : "")));
    kap.append(s);
  }
  const biten = (t.bitti || []).slice(-3).reverse();
  for (const g of biten) {
    const s = el("div", "is");
    s.append(el("div", "soluk", `#${g.no} ${g.baslik}`), el("div", "d", "bitti"));
    kap.append(s);
  }
  if (!n && !biten.length) kap.append(el("div", "soluk", "İş yok."));
  $("#durum").textContent = n ? `${n} açık iş` : "boşta";
}

/* ---------------------------------------------------------------- lidere yaz */
let foto = null;
$("#foto").onchange = () => {
  foto = $("#foto").files[0] || null;
  $("#foto-ad").textContent = foto ? foto.name || "fotoğraf" : "";
};

async function gonder(kanat) {
  let metin = $("#mesaj").value.trim();
  if (!metin && !foto) return;
  try {
    if (foto) {
      const veri = await new Promise((ok, hata) => {
        const r = new FileReader();
        r.onload = () => ok(String(r.result).split(",")[1] || "");
        r.onerror = () => hata(r.error);
        r.readAsDataURL(foto);
      });
      const ek = await al("/api/ek", { ad: foto.name || `telefon-${Date.now()}.jpg`, veri });
      metin = (metin || "Ekteki fotoğrafa bak.") + "\n[ek] " + ek.yol;
    }
    const r = await al("/api/lidere", { metin, kanat: kanat || "" });
    if (r && r.yol === "oneri") {
      // Birden cok takim: ofis secmez, ONERIR; patron secer.
      const k = $("#takim-sec");
      k.innerHTML = "";
      k.append(el("div", "soluk", "Hangi takıma gitsin?"));
      for (const o of r.oneriler || []) {
        const b = el("button", null, o.ad || o.kanat_ad || o.kisaltma || "takım");
        b.onclick = () => { k.innerHTML = ""; gonder(o.kanat_id || o.id); };
        k.append(b);
      }
      return;
    }
    $("#mesaj").value = "";
    foto = null; $("#foto").value = ""; $("#foto-ad").textContent = "";
    bildir("Lidere gitti.");
  } catch (e) { bildir(e.message); }
  yenile();
}
$("#gonder").onclick = () => gonder("");

/* ---------------------------------------------------------------- durdur */
$("#durdur").onclick = async () => {
  if (!confirm("Bütün çalışan işler durdurulsun mu? Yarım kalan iş Sürdür ile kaldığı yerden devam eder.")) return;
  try { await al("/api/durdur", {}); bildir("Durduruluyor."); } catch (e) { bildir(e.message); }
  yenile();
};

/* ---------------------------------------------------------------- bildirim */
function anahtarCevir(b64) {
  const dolgu = "=".repeat((4 - (b64.length % 4)) % 4);
  const ham = atob((b64 + dolgu).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...ham].map((c) => c.charCodeAt(0)));
}

$("#bildirim-ac").onclick = async () => {
  try {
    if (!("serviceWorker" in navigator) || !("PushManager" in window))
      throw new Error("Bu tarayıcı bildirim desteklemiyor (iPhone'da önce 'Ana Ekrana Ekle').");
    const izin = await Notification.requestPermission();
    if (izin !== "granted") throw new Error("Bildirim izni verilmedi.");
    const kayit = await navigator.serviceWorker.register("/sw.js");
    const d = await al("/api/telefon/durum");
    const abonelik = await kayit.pushManager.subscribe({
      userVisibleOnly: true, applicationServerKey: anahtarCevir(d.vapid),
    });
    await al("/api/telefon/abone", { abonelik: abonelik.toJSON() });
    bildir("Bildirimler açık.");
    $("#bildirim-dene").classList.remove("gizli");
  } catch (e) { bildir(e.message); }
};
$("#bildirim-dene").onclick = async () => {
  try {
    const r = await al("/api/telefon/dene", {});
    bildir(r.gonderildi ? "Deneme bildirimi gönderildi." : ("Gönderilemedi: " + (r.hata || "abonelik yok")));
  } catch (e) { bildir(e.message); }
};

/* ---------------------------------------------------------------- dongu */
async function yenile() {
  try { await Promise.all([bekleyenleriCiz(), isleriCiz()]); }
  catch (e) { if (/eşleşmemiş|eslesmemis|401/.test(e.message)) basla(); }
}

async function basla() {
  let d = {};
  try { d = await al("/api/telefon/durum"); } catch (_) { /* ag yok */ }
  const eslesmis = !!d.eslesmis;
  $("#eslestir").classList.toggle("gizli", eslesmis);
  $("#ana").classList.toggle("gizli", !eslesmis);
  if (eslesmis) yenile();
}

basla();
setInterval(() => { if (!document.hidden && !$("#ana").classList.contains("gizli")) yenile(); }, 10000);
