# -*- coding: utf-8 -*-
"""MEDYA YARDIMCISI -- ofisin evindeki AYRI Python ortaminda (`ev/araclar/medya-py`)
kosar; ofisin geri kalanini ICE AKTARMAZ. `ofis/medya_arac.py` bunu alt surec
olarak cagirir ve JSON cevabini okur.

Neden ayri ortam (07.10.2026, OLCULDU): faster-whisper + rembg sistem
Python'una kurulsaydi numpy 2.2 -> 2.5 ve numba/llvmlite yukselirdi; patronun
baska programlari (calisan bir sunucu dahil) ayni ortami kullaniyor.

Komutlar (cikti: stdout'ta TEK JSON satiri):
  altyazi  <video/ses> --ffmpeg <ffmpeg.exe> --modeller <klasor> [--model large-v3-turbo]
  arka_plan <girdi> <cikti> --modeller <klasor> [--model birefnet-general-lite]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def _ses(yol: str, ffmpeg: str):
    """Sesi ffmpeg ile 16 kHz tek kanal cozer. OLCULDU: faster-whisper 1.2.1'in
    kendi cozucusu `av` 19 ile patliyor (`metadata_errors`); ffmpeg ofiste zaten var."""
    import numpy as np
    ham = subprocess.run([ffmpeg, "-v", "error", "-i", yol, "-vn", "-f", "s16le", "-ac", "1",
                          "-ar", "16000", "-"], capture_output=True, check=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    return np.frombuffer(ham, np.int16).astype(np.float32) / 32768.0


def altyazi(a) -> dict:
    from faster_whisper import WhisperModel
    m = WhisperModel(a.model, device="cpu", compute_type="int8",
                     download_root=os.path.join(a.modeller, "whisper"))
    ses = _ses(a.girdi, a.ffmpeg)
    if not len(ses):
        return {"kelimeler": [], "satirlar": [], "sure": 0.0}
    parcalar, bilgi = m.transcribe(ses, language=a.dil or None, word_timestamps=True,
                                   vad_filter=True)
    kelimeler, satirlar = [], []
    for p in parcalar:
        satirlar.append({"bas": round(p.start, 2), "son": round(p.end, 2), "metin": p.text.strip()})
        for w in p.words or []:
            kelimeler.append({"k": w.word.strip(), "bas": round(w.start, 2), "son": round(w.end, 2)})
    return {"kelimeler": kelimeler, "satirlar": satirlar, "dil": bilgi.language,
            "sure": round(len(ses) / 16000, 2)}


def arka_plan(a) -> dict:
    os.environ["U2NET_HOME"] = os.path.join(a.modeller, "rembg")
    from PIL import Image
    from rembg import new_session, remove
    im = Image.open(a.girdi)
    cikti = remove(im, session=new_session(a.model))
    cikti.save(a.cikti)
    alfa = cikti.getchannel("A")
    hist = alfa.histogram()
    on = sum(hist[129:]) / max(1, alfa.width * alfa.height)
    return {"cikti": a.cikti, "boyut": list(cikti.size), "on_plan_orani": round(on, 4)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    alt = ap.add_subparsers(dest="komut", required=True)
    a1 = alt.add_parser("altyazi")
    a1.add_argument("girdi")
    a1.add_argument("--ffmpeg", required=True)
    a1.add_argument("--modeller", required=True)
    a1.add_argument("--model", default="large-v3-turbo")
    a1.add_argument("--dil", default="tr")
    a2 = alt.add_parser("arka_plan")
    a2.add_argument("girdi")
    a2.add_argument("cikti")
    a2.add_argument("--modeller", required=True)
    a2.add_argument("--model", default="birefnet-general-lite")
    a = ap.parse_args(argv)
    try:
        sonuc = altyazi(a) if a.komut == "altyazi" else arka_plan(a)
        print(json.dumps({"tamam": True, **sonuc}, ensure_ascii=False))
        return 0
    except Exception as exc:                            # noqa: BLE001 -- cagirana JSON'la
        print(json.dumps({"tamam": False, "hata": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
