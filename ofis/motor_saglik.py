# -*- coding: utf-8 -*-
"""MOTOR SAGLIK HAFIZASI (E16) -- "anahtar var != calisiyor", her motorda TEK desen.

## Neden

Bir motorun CLI'i kurulu ve giris dosyasi duruyor olabilir; yine de tek
satir is yapamayabilir:

* OLCULDU (25.09.2026, codex): `auth.json` duruyordu, sunucu her istege
  `401 token_revoked` donuyordu. `musait_mi` HAZIR diyordu; `cinar` tek
  satir is yapamiyordu ve ofiste bunu soyleyen hicbir sey yoktu.
* Claude'da ayni kor nokta TAMAMEN aciktir (27.09.2026'ya kadar):
  `musait_mi` yalniz programin kurulu oldugunu soruyordu. CLI akista
  hesap sorununu ayri bir alanla bildiriyor (assistant mesajinin `error`
  alani; semasi CLI'in kendi kodundan okundu: `authentication_failed` ·
  `oauth_org_not_allowed` · `account_on_hold` · `verification_required` ·
  `billing_error` ...) ama adaptor bu alani hic okumuyordu -- dusen oturum
  siradan bir "basarisiz tur" gibi gorunuyor ve HATIRLANMIYORDU.

Codex'e ozel yazilmis bir hafiza vardi (`codex_oturum.json`); Claude'a
ikinci bir kopya yazmak, bu projede alti kez odenen "iki kopyadan biri
duzeltilir, oteki unutulur" deseninin davetiyesiydi. Hafiza artik TEK:
motor adi + kimlik anahtari ile tutulur.

## Kural

* **Olcmek pahaliysa HATIRLANIR.** Oturumun sunucuda olup olmadigini
  olcmek bir tur kosmaktir (kotadan yer). Gercek bir tur hesap hatasi
  aldiginda kaydedilir. Olcmek BEDAVAYSA olculur: Claude'un yerel girisi
  `claude auth status` ile (0,4-0,5 sn, jeton yok) -- o is adaptorde.
* **Kayit KENDILIGINDEN duser.** Kayit, kimligin O ANKI parmak izini
  tutar (giris dosyasinin damgasi ya da anahtarin ozeti). Kullanici
  yeniden giris yapinca parmak izi degisir ve kayit gecersiz olur --
  unutulabilecek bir "temizle" adimi yok.
* **Yazamamak isi DURDURMAZ.** Hafiza bir kolaylik, bir kapi degil.
* **Anahtar yazilmaz**, yalniz ozeti (parmak izi) -- defter kasa degildir.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .yollar import OFIS_EVI

#: Tek defter -- proje kokunun DISINDA (kota ve baglayici hafizasiyla ayni
#: kok). Motor evlerinin ICINE yazilmaz: ev motorun kendi dizinidir ve
#: kullanicinin `~/.codex`i bir hesap olarak tanimlanirsa oraya yazmak onun
#: salt-okunur kuralini cigner.
DEFTER = OFIS_EVI / "motor_saglik.json"

#: Claude CLI'in hesap sorunu kategorileri (assistant `error` alani).
#: Hepsi INSAN eylemi ister -- beklemek ise yaramaz; bu yuzden limit gibi
#: devredilip unutulmaz, hatirlanir. `rate_limit` BURADA DEGIL: o bir
#: kaynak tukenmesidir ve pencere olcumuyle (`kullanim.son_pencereler`)
#: yonetilir; `overloaded`/`server_error` gecicidir.
HESAP_SORUNLARI = {
    "authentication_failed": "oturum kapanmis ya da gecersiz (giris gerekli)",
    "oauth_org_not_allowed": "kurulus bu girise izin vermiyor",
    "account_on_hold": "hesap ASKIDA",
    "verification_required": "hesap dogrulamasi gerekiyor",
    "billing_error": "odeme / abonelik sorunu",
    "token_revoked": "oturum sunucuda kapatilmis (401 token_revoked)",
}


def parmak_izi_dosya(yol) -> str:
    """Giris dosyasinin damgasi; yoksa 'yok'. Yeniden giris damgayi degistirir."""
    try:
        return "dosya:" + str(Path(yol).expanduser().stat().st_mtime_ns)
    except OSError:
        return "dosya:yok"


def parmak_izi_anahtar(deger: str) -> str:
    """Anahtarin OZETI -- deger defterde durmaz."""
    return "anahtar:" + hashlib.sha256(str(deger).encode("utf-8")).hexdigest()[:16]


def _oku(defter) -> dict:
    try:
        d = json.loads(Path(defter).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _anahtar(motor: str, kimlik: str) -> str:
    return f"{motor}:{str(kimlik).lower()}"


def olu_yaz(motor: str, kimlik: str, parmak_izi: str, kategori: str, *,
            defter=None) -> None:
    """Bu kimligin hesabi SU AN kullanilamiyor -- gercek bir turda olculdu."""
    defter = Path(defter or DEFTER)
    try:
        d = _oku(defter)
        d[_anahtar(motor, kimlik)] = {"parmak_izi": parmak_izi,
                                       "kategori": kategori, "an": time.time()}
        from .dosya import atomik_yaz
        atomik_yaz(defter, json.dumps(d, ensure_ascii=False))
    except OSError:
        pass


def olu_kaydi(motor: str, kimlik: str, parmak_izi: str, *, defter=None):
    """Gecerli kayit (sozluk) ya da None. Parmak izi degistiyse kayit DUSER."""
    k = _oku(defter or DEFTER).get(_anahtar(motor, kimlik))
    if not isinstance(k, dict) or k.get("parmak_izi") != parmak_izi:
        return None
    return k


def kategori_metni(kategori: str) -> str:
    return HESAP_SORUNLARI.get(kategori, kategori or "hesap sorunu")


def kayit_metni(motor: str, kayit: dict, care: str) -> str:
    """Insana: ne oldu, ne zaman olculdu, ne yapilmali."""
    dk = max(0, round((time.time() - float(kayit.get("an") or 0)) / 60))
    return (f"{motor} hesabi kullanilamiyor: {kategori_metni(kayit.get('kategori', ''))} "
            f"(gercek bir turda olculdu, {dk} dk once). {care} "
            "Giris yapilinca bu kayit kendiliginden duser.")


#: Pencere bu orana ulastiysa hesap DOLU sayilir. Esik degil OLCUM: saglayici
#: %100 bildirdiyse is kosamaz; altini "dolmak uzere" zincir zaten yonetir
#: (`zincir.pencereye_gore_sirala`).
DOLU_ORANI = 1.0


def dolu_hesaplar(db, proje_id: str, *, simdi_=None) -> list:
    """Olculen pencerelerden DOLU olanlar -- saglayicinin kendi bildirimi.

    Yenilenmis pencere sayilmaz (`son_pencereler` yuzdesini zaten None
    yapar). Olcumun yasi tasinir: sayi yalniz ofis o hesapla tur kostukca
    tazelenir.
    """
    from . import kullanim
    out = []
    for p in kullanim.son_pencereler(db, proje_id, simdi_=simdi_):
        for ad, pen in (p.get("pencereler") or {}).items():
            k = pen.get("kullanim")
            if k is None or k < DOLU_ORANI:
                continue
            out.append({"motor": p["motor"], "hesap": p["hesap"], "pencere": ad,
                        "yenilenme": pen["yenilenme"],
                        "kalan_saat": pen["kalan_saat"], "yas_dk": p.get("yas_dk")})
    return out
