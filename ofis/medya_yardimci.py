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
  vokal    <girdi> <vokal_cikti> <muzik_cikti> --ffmpeg <ffmpeg.exe> --modeller <klasor>
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


# ------------------------------------------------------------------ vokal
#: MDX-Net (UVR, Kim_Vocal_2.onnx): spektrogram -> VOKAL spektrogrami. Kendi
#: STFT'miz numpy'la (torch YOK -- ayirma paketlerinin hepsi ~1 GB torch
#: istiyordu; onnxruntime ortamda zaten var). Parametreler modelin kendisi:
#: girdi [*, 4, 3072, 256] (olculdu), n_fft 7680, hop 1024, telafi 1.009.
MDX = {"n_fft": 7680, "hop": 1024, "dim_f": 3072, "dim_t": 256, "telafi": 1.009}
SR = 44100


def _pencere(n):
    import numpy as np
    return (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)).astype(np.float32)  # periyodik Hann


def _stft(x, p, w):
    """x [N, parca] -> [N/2, 4, dim_f, dim_t] (kanal x gercek/sanal)."""
    import numpy as np
    n_fft, hop, dim_t = p["n_fft"], p["hop"], p["dim_t"]
    xp = np.pad(x, ((0, 0), (n_fft // 2, n_fft // 2)), mode="reflect")
    idx = np.arange(dim_t)[:, None] * hop + np.arange(n_fft)[None, :]
    spek = np.fft.rfft(xp[:, idx] * w, axis=-1).transpose(0, 2, 1)       # [N, bins, t]
    ri = np.stack([spek.real, spek.imag], axis=1)                          # [N, 2, bins, t]
    ri = ri.reshape(-1, 4, ri.shape[2], dim_t)                             # [B, 4, bins, t]
    return ri[:, :, :p["dim_f"]].astype(np.float32)


def _istft(s, p, w, parca):
    import numpy as np
    n_fft, hop, dim_t = p["n_fft"], p["hop"], p["dim_t"]
    bins = n_fft // 2 + 1
    tam = np.zeros((s.shape[0], 4, bins, dim_t), np.float32)
    tam[:, :, :s.shape[2]] = s
    tam = tam.reshape(-1, 2, bins, dim_t)                                  # [N, 2, bins, t]
    c = (tam[:, 0] + 1j * tam[:, 1]).transpose(0, 2, 1)                    # [N, t, bins]
    kare = np.fft.irfft(c, n=n_fft, axis=-1).astype(np.float32) * w        # [N, t, n_fft]
    boy = parca + n_fft
    y = np.zeros((kare.shape[0], boy), np.float32)
    zarf = np.zeros(boy, np.float32)
    for t in range(dim_t):
        y[:, t * hop:t * hop + n_fft] += kare[:, t]
        zarf[t * hop:t * hop + n_fft] += w * w
    y /= np.where(zarf > 1e-8, zarf, 1.0)
    return y[:, n_fft // 2:n_fft // 2 + parca]


def vokal_ayir(a) -> dict:
    import numpy as np
    import onnxruntime as ort
    model = os.path.join(a.modeller, "mdx", "Kim_Vocal_2.onnx")
    if not os.path.isfile(model):
        raise FileNotFoundError(f"model yok: {model}")
    ham = subprocess.run([a.ffmpeg, "-v", "error", "-i", a.girdi, "-vn", "-f", "f32le", "-ac", "2",
                          "-ar", str(SR), "-"], capture_output=True, check=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    karisim = np.frombuffer(ham, np.float32).reshape(-1, 2).T.copy()          # [2, n]
    n = karisim.shape[1]
    if n < SR // 2:
        raise ValueError("ses cok kisa (en az 0,5 sn)")
    p = MDX
    w = _pencere(p["n_fft"])
    parca = p["hop"] * (p["dim_t"] - 1)
    kirp = p["n_fft"] // 2
    adim = parca - 2 * kirp
    dolgu = adim - n % adim
    kp = np.concatenate([np.zeros((2, kirp), np.float32), karisim,
                         np.zeros((2, dolgu + kirp), np.float32)], axis=1)
    s = ort.InferenceSession(model, providers=["CPUExecutionProvider"])
    giris = s.get_inputs()[0].name
    parcalar = []
    for i in range(0, n + dolgu, adim):
        spek = _stft(kp[:, i:i + parca], p, w)
        # Gurultu bastirma (UVR'in 'denoise'u): model(x) ve -model(-x) ortalamasi.
        tahmin = 0.5 * (s.run(None, {giris: spek})[0] - s.run(None, {giris: -spek})[0])
        dalga = _istft(tahmin, p, w, parca)                                    # [2, parca]
        parcalar.append(dalga[:, kirp:-kirp])
    vokal = np.concatenate(parcalar, axis=1)[:, :n] * p["telafi"]
    muzik = karisim - vokal

    def _yaz(x, yol):
        uz = os.path.splitext(yol)[1].lower()
        kod = {".wav": ["-c:a", "pcm_s16le"], ".mp3": ["-c:a", "libmp3lame", "-q:a", "2"]}.get(
            uz, ["-c:a", "aac", "-b:a", "192k"])
        subprocess.run([a.ffmpeg, "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2",
                        "-i", "-", *kod, yol], input=np.ascontiguousarray(x.T).astype(np.float32).tobytes(),
                       check=True, capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    _yaz(vokal, a.vokal)
    _yaz(muzik, a.muzik)

    def _db(x):
        return round(float(10 * np.log10(np.mean(x ** 2) + 1e-12)), 1)

    return {"vokal": a.vokal, "muzik": a.muzik, "sure": round(n / SR, 2),
            "vokal_db": _db(vokal), "muzik_db": _db(muzik), "karisim_db": _db(karisim)}


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
    a3 = alt.add_parser("vokal")
    a3.add_argument("girdi")
    a3.add_argument("vokal")
    a3.add_argument("muzik")
    a3.add_argument("--ffmpeg", required=True)
    a3.add_argument("--modeller", required=True)
    a = ap.parse_args(argv)
    try:
        sonuc = {"altyazi": altyazi, "arka_plan": arka_plan, "vokal": vokal_ayir}[a.komut](a)
        print(json.dumps({"tamam": True, **sonuc}, ensure_ascii=False))
        return 0
    except Exception as exc:                            # noqa: BLE001 -- cagirana JSON'la
        print(json.dumps({"tamam": False, "hata": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
