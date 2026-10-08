# -*- coding: utf-8 -*-
"""CANLI MASAUSTU DENEMESI (D1) -- GERCEK fare/klavye, YALNIZ patronun izniyle.

Sinama takimina GIRMEZ (adi duman_ degil): patronun masaustunu surer.
Kosmak icin: `python testler/canli_masaustu.py --evet` -- ve deneme boyunca
(~30 sn) fare ve klavyeye dokunulmaz; dokunulursa deneme DURUR.

Yaptigi: Not Defteri acar, yazi alanini Windows'un erisilebilirlik
katmanindan bulup tiklar, Turkce harfli iki satir yazar, yaziyi ayni
katmandan GERI OKUR (yazilan == okunan), Shift+Delete'i yalniz kapi
olcutuyle sinar (basmaz), Not Defteri'ni kaydetmeden kapatir. Ekran
goruntusu gecici klasore alinir ve silinir.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ofis import masaustu as M  # noqa: E402
from ofis.surec import PENCERE_YOK  # noqa: E402

if "--evet" not in sys.argv:
    print("Bu deneme MASAUSTUNU SURER. Patronun izniyle: --evet")
    sys.exit(2)

YAZI = "AgentOfis masaüstü denemesi: ğüşıöç ĞÜŞİÖÇ\nikinci satır 123"
sonuc, sure = [], {}


def adim(ad, kosul, not_=""):
    sonuc.append((ad, bool(kosul)))
    print(f"  [{'gecti' if kosul else 'KALDI'}] {ad} {not_}")


def dur_patron(ad):
    if M.patron_etkin_mi():
        print(f"\n!! PATRON fare/klavyeyi kullandi ({ad} oncesi) -- deneme DURDU.")
        raise SystemExit(3)


t0 = time.time()
for _ in range(30):
    if not M.patron_etkin_mi():
        break
    time.sleep(1)
else:
    print("Son 30 sn'de fare/klavye kullanildi; deneme baslamadi.")
    sys.exit(3)

once = {p["hwnd"] for p in M.pencereler(200)}
t = time.time()
pid = M.uygulama_ac("notepad")
pencere = None
for _ in range(40):
    time.sleep(0.25)
    yeni = [p for p in M.pencereler(200) if p["hwnd"] not in once
            and p["uygulama"].lower() == "notepad.exe"]
    if yeni:
        pencere = yeni[0]
        break
sure["ac"] = time.time() - t
adim("Not Defteri acildi ve penceresi bulundu", pencere is not None, str(pencere and pencere["baslik"]))
if not pencere:
    sys.exit(1)
try:
    dur_patron("one getirme")
    adim("pencere one geldi", M.pencere_one(pencere["hwnd"]))
    gk = Path(tempfile.mkdtemp(prefix="ofis-canli-masaustu-"))
    t = time.time()
    g = M.goruntu_al(gk / "ekran.png")
    sure["goruntu"] = time.time() - t
    adim("ekran goruntusu alindi", Path(g.yol).is_file() and g.genislik <= M.AZAMI_KENAR,
         f"{g.genislik}x{g.yukseklik} olcek {g.olcek:.3f}")
    t = time.time()
    ogeler = M.ogeler(pencere["hwnd"])
    sure["ogeler"] = time.time() - t
    alan = next((o for o in ogeler if o.get("tur") in ("Edit", "Document")), None)
    adim("ogeler okundu, yazi alani bulundu", alan is not None,
         f"{len(ogeler)} oge: " + ", ".join(f"{o.get('tur')}:{o.get('ad')!r}" for o in ogeler[:8]))
    if alan:
        k = alan["kutu"]
        ex, ey = (k[0] + k[2]) // 2, (k[1] + k[3]) // 2
        gx, gy = g.goruntuye(ex, ey)
        ex2, ey2 = g.ekrana(gx, gy)
        adim("goruntu<->ekran cevirisi tutarli (1 pikselin olcek kati icinde)",
             abs(ex2 - ex) <= g.olcek + 1 and abs(ey2 - ey) <= g.olcek + 1)
        t = time.time()
        nokta = M.oge_noktada(ex, ey) or {}
        sure["oge_noktada"] = time.time() - t
        adim("noktadaki oge = yazi alani (kapinin okuyacagi ad)", nokta.get("tur") in ("Edit", "Document"),
             str(nokta)[:160])
        dur_patron("tiklama")
        M.tikla(ex, ey)
        time.sleep(0.3)
        odak = M.odak_ogesi() or {}
        adim("tiklamadan sonra odak yazi alaninda", odak.get("tur") in ("Edit", "Document"), str(odak)[:120])
        dur_patron("yazma")
        t = time.time()
        M.yaz(YAZI)
        sure["yaz"] = time.time() - t
        time.sleep(0.4)
        okunan = M._ps(f"""
$k = $A::FromHandle([IntPtr]{int(pencere['hwnd'])})
$c = New-Object System.Windows.Automation.OrCondition(
  (New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, [System.Windows.Automation.ControlType]::Edit)),
  (New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, [System.Windows.Automation.ControlType]::Document)))
$e = $k.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $c)
$m = ''
try {{ $m = $e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value }} catch {{
  $m = $e.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern).DocumentRange.GetText(-1) }}
@{{ metin = $m }} | ConvertTo-Json -Compress
""")
        metin = ((okunan or {}).get("metin") or "").replace("\r\n", "\n").replace("\r", "\n")
        adim("yazilan = Windows'tan geri okunan (Turkce harfler dahil)", metin == YAZI, repr(metin[:80]))
        dur_patron("tus")
        M.tus("ctrl+a")
        M.tus("delete")
        time.sleep(0.3)
    from ofis import riskli as R
    adim("shift+delete kapida SILME (basilmadi, yalniz olcut)",
         R.masaustu_degerlendir("tus", tuslar="shift+delete")["sinif"] == "silme")
finally:
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, creationflags=PENCERE_YOK)
    try:
        import shutil
        shutil.rmtree(gk, ignore_errors=True)
    except NameError:
        pass
print("\nsureler (sn): " + ", ".join(f"{k} {v:.2f}" for k, v in sure.items()))
kalan = [a for a, ok in sonuc if not ok]
print(f"== {len(sonuc) - len(kalan)}/{len(sonuc)} gecti; toplam {time.time() - t0:.1f} sn ==")
sys.exit(1 if kalan else 0)
