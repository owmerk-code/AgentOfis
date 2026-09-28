"""DENETIM KAYDI (F3 / E27) -- "kim, neyi, hangi yetkiyle yapti".

Ofis zaten her seyi yaziyor ama DAGINIK: onaylar `onay` tablosunda,
yetki genislemeleri (klasor, tarayici, baglayici, konsol, devral) ve kapi
kararlari `olay` tablosunda, yuzlerce "arac" ve "cikti" satiri arasinda.
Insan "gecen hafta ajana hangi klasoru actim, hangi onayi verdim, o onay
ne zaman kullanildi" sorusunu tek bakista cevaplayamiyordu.

Bu modul YENI BIR KAYIT TUTMAZ -- var olanlari tek listeye toplar. Ikinci
bir defter olsaydi ikisi ayrisirdi (bu projede kac kez odendi).

Uc sinif:
  * yetki  -- yetki GENISLEDI ya da degisti (kim, ne acildi, hangi ise)
  * kapi   -- ofisin kapisi bir karar verdi (soruldu, reddedildi, izin
              kullanildi, talimat suphesi, kaydedilen degisiklik)
  * geri   -- geri alma, iptal, durdurma, devir
Her satir: zaman · kim · ne · hangi is · hangi yetkiyle (onay/kapsam).
"""

from __future__ import annotations

#: olay turu -> (sinif, insan dilinde ne)
OLAYLAR = {
    # yetki
    "klasor_acildi": ("yetki", "ofis dışı klasör açıldı"),
    "tarayici_acildi": ("yetki", "tarayıcı açıldı"),
    "tarayici_alani": ("yetki", "tarayıcı alanı verildi"),
    "baglayici_istendi": ("yetki", "bağlayıcı istendi"),
    "baglayici_acildi": ("yetki", "bağlayıcı açıldı"),
    "konsol_acildi": ("yetki", "ofis dışı terminal açıldı"),
    "konsol_kapandi": ("yetki", "ofis dışı terminal kapandı"),
    "kabin_acildi": ("yetki", "paylaşılan tarayıcı (kabin) açıldı"),
    "kabin_kapandi": ("yetki", "kabin kapandı"),
    "kabin_dustu": ("yetki", "kabin kendiliğinden kapandı"),
    "devral": ("yetki", "iş insana devralındı"),
    "devral_bitti": ("yetki", "iş ajana geri verildi"),
    "hesap_eklendi": ("yetki", "hesap eklendi"),
    "ise_alindi": ("yetki", "ajan işe alındı"),
    "kanat_acildi": ("yetki", "takım kuruldu"),
    "kural": ("yetki", "ofis kuralı değişti"),
    "efor_modu": ("yetki", "efor modu değişti"),
    "efor_tavani": ("yetki", "efor tavanı değişti"),
    "kademe": ("yetki", "model kademesi değişti"),
    "yukseltme": ("yetki", "inceleme güçlü modele yükseltildi"),
    # kapi
    "onay_istendi": ("kapi", "onay istendi"),
    "arac_onay_bekliyor": ("kapi", "kapı durdurdu, onay bekliyor"),
    "tarayici_onay_bekliyor": ("kapi", "tarayıcı kapısı durdurdu"),
    "onay_cevabi": ("kapi", "onay cevaplandı"),
    "onay_kullanildi": ("kapi", "verilen onay kullanıldı"),
    "arac_degisikligi": ("kapi", "değişiklik yapıldı (sorulmadı, kaydedildi)"),
    "talimat_suphesi": ("kapi", "dış içerikte talimat şüphesi"),
    "izin": ("kapi", "araç izni reddedildi"),
    "bilgi_ret": ("kapi", "hafızaya yazma reddedildi"),
    # geri
    "geri_alindi": ("geri", "tur geri alındı"),
    "iptal": ("geri", "iş iptal edildi"),
    "ret": ("geri", "iş geri gönderildi"),
    "depo_gonderildi": ("geri", "yedek GitHub'a gönderildi"),
    "yedek_alindi": ("geri", "yedek alındı"),
}

SINIFLAR = ("yetki", "kapi", "geri")


def kayit(ofis, *, sinif: str = "", ajan: str = "", gorev_no: int = None,
          azami: int = 300) -> list:
    """Denetim satirlari, EN YENI once. Olaylar + onay tablosu birlesik."""
    turler = [t for t, (s, _) in OLAYLAR.items() if not sinif or s == sinif]
    satirlar = []
    with ofis.db.baglanti() as c:
        gid = None
        if gorev_no is not None:
            r = c.execute("SELECT id FROM gorev WHERE proje_id=? AND no=?",
                          (ofis.proje_id, int(gorev_no))).fetchone()
            gid = r["id"] if r else "-"
        if turler:
            q = ("SELECT o.rowid AS sira, o.tur, o.govde, o.ajan_ad, o.olusturuldu, "
                 "g.no AS gorev_no FROM olay o LEFT JOIN gorev g ON g.id = o.gorev_id "
                 f"WHERE o.proje_id=? AND o.tur IN ({','.join('?' * len(turler))})")
            p = [ofis.proje_id, *turler]
            if ajan:
                q += " AND o.ajan_ad=?"
                p.append(ajan)
            if gid:
                q += " AND o.gorev_id=?"
                p.append(gid)
            q += " ORDER BY o.rowid DESC LIMIT ?"
            p.append(azami)
            for r in c.execute(q, p):
                s, ne = OLAYLAR[r["tur"]]
                satirlar.append({
                    "zaman": r["olusturuldu"], "sinif": s, "tur": r["tur"], "ne": ne,
                    # Konsol ve Devral INSANIN eylemidir; olay ajansiz yazilir.
                    "kim": r["ajan_ad"] or ("insan" if r["tur"].startswith(("konsol_", "devral"))
                                            else "ofis"),
                    "gorev_no": r["gorev_no"],
                    "ayrinti": (r["govde"] or "")[:400], "_sira": (r["olusturuldu"], r["sira"]),
                })
        # ONAY TABLOSU: istek + (varsa) karar tek satirda -- "hangi yetkiyle".
        if not sinif or sinif == "kapi":
            q = ("SELECT n.*, g.no AS gorev_no FROM onay n LEFT JOIN gorev g ON g.id = n.gorev_id "
                 "WHERE n.proje_id=?")
            p = [ofis.proje_id]
            if ajan:
                q += " AND n.isteyen=?"
                p.append(ajan)
            if gid:
                q += " AND n.gorev_id=?"
                p.append(gid)
            q += " ORDER BY n.rowid DESC LIMIT ?"
            p.append(azami)
            for r in c.execute(q, p):
                karar = {"bekliyor": "BEKLİYOR", "onaylandi": "ONAYLANDI",
                         "reddedildi": "REDDEDİLDİ"}.get(r["durum"], r["durum"])
                kapsam = (r["kapsam"] or "eylem")
                satirlar.append({
                    "zaman": r["cevaplandi"] or r["olusturuldu"], "sinif": "kapi",
                    "tur": "onay", "ne": f"onay {karar}",
                    "kim": r["isteyen"], "gorev_no": r["gorev_no"],
                    "ayrinti": (r["eylem"] or "")[:200]
                               + (f" — patron: {r['cevap_notu']}" if r["cevap_notu"] else ""),
                    "yetki": ("" if r["durum"] != "onaylandi" else
                              ("bu iş boyunca" if kapsam == "is" else "bir kez")),
                    "risk": r["risk"], "_sira": (r["cevaplandi"] or r["olusturuldu"], 0),
                })
    satirlar.sort(key=lambda x: x["_sira"], reverse=True)
    for x in satirlar:
        x.pop("_sira", None)
    return satirlar[:azami]


def ozet(satirlar: list) -> dict:
    """Sinif basina sayi + bekleyen onay sayisi (panel basligi icin)."""
    say = {s: 0 for s in SINIFLAR}
    for x in satirlar:
        say[x["sinif"]] = say.get(x["sinif"], 0) + 1
    say["bekleyen_onay"] = sum(1 for x in satirlar if x["tur"] == "onay" and "BEKL" in x["ne"])
    return say
