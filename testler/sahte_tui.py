# -*- coding: utf-8 -*-
"""SAHTE ETKILESIMLI CLI -- gercek terminal kipinin sinamasi icin (jeton yok).

Gercek terminalde (ConPTY) kosar, klavyeden (msvcrt) okur ve bir oturum
dosyasina (JSONL) gercek CLI'lar gibi satir yazar:
  {"tur": "girdi", "metin": ...}      her gonderilen mesaj
  {"tur": "metin", "metin": ...}      ajanin sozu
  {"tur": "arac", "ad": "Bash", "ozet": ...}
  {"tur": "bitti"}                    tur sonu
Esc = turu kes ({"tur": "kesildi"} + bitti).

Davranis mesajdaki isaretlerden:
  YUTENTER  -> ilk Enter'i yutar (codex'in uzun yapistirma davranisi)
  YAVAS     -> tur 6 sn surer (not/durdur sinamasi)
  ASKIDA    -> tur hic bitmez (zaman asimi sinamasi)
Argumanlar: <oturum dosyasi>
"""
import json
import msvcrt
import sys
import time

DOSYA = sys.argv[1]
_yutuldu = False


def yaz(k):
    with open(DOSYA, "a", encoding="utf-8") as f:
        f.write(json.dumps(k, ensure_ascii=False) + "\n")


def mesaj_oku():
    global _yutuldu
    tampon = ""
    while True:
        ch = msvcrt.getwch()
        if ch == "\r":
            if "YUTENTER" in tampon and not _yutuldu:
                _yutuldu = True
                continue
            return tampon
        if ch == "\x1b":
            # yapistirma isaretlerini ([200~ / [201~) at
            dizi = ""
            while msvcrt.kbhit():
                dizi += msvcrt.getwch()
                if dizi.endswith("~"):
                    break
            continue
        tampon += ch


print("sahte-cli hazir >", flush=True)
while True:
    m = mesaj_oku()
    if m.strip() == "/exit":
        break
    yaz({"tur": "girdi", "metin": m})
    yaz({"tur": "metin", "metin": "isi aldim"})
    yaz({"tur": "arac", "ad": "Bash", "ozet": "echo tamam"})
    sure = 6 if "YAVAS" in m else (10 ** 6 if "ASKIDA" in m else 0.3)
    bas = time.time()
    kesildi = False
    while time.time() - bas < sure:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch == "\x1b" and not msvcrt.kbhit():
                kesildi = True
                break
            # tur surerken gelen not
            ek = ch
            while True:
                c = msvcrt.getwch()
                if c == "\r":
                    break
                ek += c
            yaz({"tur": "girdi", "metin": ek.replace("\x1b[200~", "").replace("\x1b[201~", "")})
        time.sleep(0.05)
    if kesildi:
        yaz({"tur": "kesildi"})
    yaz({"tur": "metin", "metin": "bitti"})
    yaz({"tur": "bitti"})
    print("tur bitti >", flush=True)
