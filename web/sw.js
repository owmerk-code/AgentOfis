/* Telefon bildirimi (Web Push). Icerik ofisin `telefon.gonder`inden gelir. */
self.addEventListener("push", (olay) => {
  let v = {};
  try { v = olay.data ? olay.data.json() : {}; } catch (_) { v = { govde: olay.data && olay.data.text() }; }
  olay.waitUntil(self.registration.showNotification(v.baslik || "AgentOfis", {
    body: v.govde || "", data: { adres: v.adres || "/telefon" }, tag: "agentofis", renotify: true,
  }));
});

self.addEventListener("notificationclick", (olay) => {
  olay.notification.close();
  const adres = (olay.notification.data && olay.notification.data.adres) || "/telefon";
  olay.waitUntil(clients.matchAll({ type: "window", includeUncontrolled: true }).then((liste) => {
    for (const c of liste) if (c.url.includes("/telefon")) return c.focus();
    return clients.openWindow(adres);
  }));
});
