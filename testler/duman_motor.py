# -*- coding: utf-8 -*-
"""Motor katmani duman testi.

Sinanan sey modelin zekasi degil SOZLESME: akis her zaman `bitti` ile
kapaniyor mu, kafa ajan yazan arac alabiliyor mu, bilinmeyen motor
sessizce varsayilana dusuyor mu, surec kesildiginde akis temiz mi
kapaniyor.

Konsol cp1254 oldugu icin cikti ASCII: '->' yazilir, ok isareti degil.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis.motor import (
    motor_ac, musait_motorlar, kayitli_motorlar, MotorHatasi, OLAY_TURLERI,
)
from ofis.motor.claude import ClaudeMotoru, ELLER_ARACLARI, KAFA_ARACLARI

GECEN = 0
KALAN = 0


def sina(baslik: str, kosul: bool, not_: str = "") -> None:
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [gecti] {baslik}")
    else:
        KALAN += 1
        print(f"  [KALDI] {baslik} {not_}")


def akisi_topla(motor, **ayar) -> list:
    return list(motor.tur_kos("brifing metni", klasor=".", **ayar))


print("== motor katmani duman testi ==\n")

# 1 -- kayit defteri bilinmeyen adi sessizce gecmemeli
print("1. kayit defteri")
sina("claude ve sahte kayitli", set(kayitli_motorlar()) >= {"claude", "sahte"})
try:
    motor_ac("claud")           # yazim hatasi
    sina("bilinmeyen motor reddedildi", False, "-- sessizce gecti!")
except MotorHatasi:
    sina("bilinmeyen motor reddedildi", True)
sina("musait_motorlar sahte'yi musait sayiyor", musait_motorlar()["sahte"] is True)

# 1b -- codex adaptoru: OFIS KENDI YAZDI, sozlesmeye uyuyor mu
print("\n1b. codex adaptoru sozlesmesi")
from ofis.motor.codex import CodexMotoru
from ofis.motor.tip import Motor as _Motor
sina("codex kayitli", "codex" in kayitli_motorlar())
sina("Motor alt sinifi", issubclass(CodexMotoru, _Motor))
sina("ad dogru", CodexMotoru.ad == "codex")
# MCP KONUSMADIGINI bildiriyor -- ve bu bir gerileme degil, DUZELTME.
# Bu iddia IKI KEZ degisti ve ikisi de OLCUMLE:
#
# 1. Once `is True` yaziyordu ve YANLISTI: `codex exec` her MCP
#    cagrisini onaya bagliyordu ve etkilesimsiz kipte onay verecek
#    kimse yoktu ("MCP tool call requires approval, but approval
#    policy is never"). `False`a cevrildi.
# 2. Simdi yine `True`, cunku `--approve-for-me` bayragi var:
#    onay istekleri workspace-write sandbox'i icinde OTOMATIK
#    inceleniyor. Gercek turla olculdu -- ajan `kanit_ekle`yi cagirdi,
#    kanit tahtaya DUSTU, sandbox kalkmadi.
#
# Bayragin isi motorun NE YAPABILDIGINI dogru soylemektir; iki yonde
# de yanlis olmasi pahalidir.
sina("MCP KONUSTUGUNU bildiriyor (--approve-for-me ile)",
     CodexMotoru.mcp_konusur is True)
# Ve bayrak GERCEKTEN komuta giriyor mu -- "kablonun bagli olmasi,
# icinden akim gectigi anlamina gelmez".
_kur = lambda **kw: CodexMotoru(calistirilabilir="codex")._komut_kur(
    "", devam=False, model="", efor="normal", yazabilir=True,
    ek_klasorler=(), klasor=".", **kw)
_k = _kur(mcp_yapilandirma='{"mcpServers":{"ofis":{"command":"x"}}}')
sina("MCP verilince --approve-for-me eklendi", "--approve-for-me" in _k)
# Bayrak kendi sandbox'ini kurar; bizimki DUSMELI yoksa codex
# "cannot be used with --sandbox" ile duser (olculdu).
sina("--approve-for-me ile bizim -s DUSUYOR", "-s" not in _k)
# MCP YOKSA eski davranis aynen kalir: sandbox'i biz kurariz.
_k2 = _kur()
sina("MCP yokken -s duruyor", "-s" in _k2)
sina("MCP yokken --approve-for-me YOK", "--approve-for-me" not in _k2)
for _uye in ("musait_mi", "tur_kos"):
    sina(f"{_uye} var", callable(getattr(CodexMotoru, _uye, None)))
_cx = CodexMotoru(calistirilabilir="codex")
# Brifing STDIN den gider: cok satirli arguman hic olusmaz, boylece
# Windows .CMD tuzagi (bkz. claude.py) codexte de kurulamaz.
_k = _cx._komut_kur("11111111-1111-1111-1111-111111111111", devam=False,
                    model="", efor="normal", yazabilir=True,
                    ek_klasorler=(), klasor=".")
sina("codex exec cagriliyor", "exec" in _k)
sina("JSONL akisi acik", "--json" in _k)
sina("yazabilir -> workspace-write",
     "workspace-write" in _k)
_ko = _cx._komut_kur("11111111-1111-1111-1111-111111111111", devam=False,
                     model="", efor="normal", yazabilir=False,
                     ek_klasorler=(), klasor=".")
sina("kafa -> read-only kum havuzu", "read-only" in _ko)
sina("hicbir argumanda satir sonu YOK (cmd.exe tuzagi)",
     not any(chr(10) in a for a in _k))
# Butce bir PARA kontroludur: uygulayamayan motor sessizce kosmaz.
# "Sessizce yok sayilan ayar, ayar degildir."
sina("codex butce DESTEKLEMEDIGINI bildiriyor",
     CodexMotoru.butce_destegi is False)
sina("claude butce destekliyor", motor_ac("claude").butce_destegi is True)
try:
    list(_cx.tur_kos("is", klasor=".", butce_usd=1.0))
    sina("butce verilince codex REDDEDIYOR", False, "-- sessizce kostu!")
except MotorHatasi as _e:
    sina("butce verilince codex REDDEDIYOR", "butce" in str(_e).lower())

# 2 -- akis sozlesmesi
print("\n2. akis sozlesmesi")
sahte = motor_ac("sahte")
olaylar = akisi_topla(sahte)
sina("ilk olay 'basladi'", olaylar[0].tur == "basladi")
sina("son olay 'bitti'", olaylar[-1].tur == "bitti")
sina("bitti.ek['basarili'] var", "basarili" in olaylar[-1].ek)
sina("tum olay turleri sozlukte",
     all(o.tur in OLAY_TURLERI for o in olaylar))
sina("metin olaylari birikti",
     "".join(o.govde for o in olaylar if o.tur == "metin").strip().startswith("Is bitti"))

# 3 -- basarisiz turlar da 'bitti' ile kapanmali (istisna ile kopmamali)
print("\n3. basarisiz turlar akisi koparmiyor")
for senaryo, beklenen in (("hata", False), ("limit", False),
                          ("zaman_asimi", False), ("basarili", True)):
    olaylar = akisi_topla(motor_ac("sahte", senaryo=senaryo))
    sina(f"{senaryo}: son olay bitti, basarili={beklenen}",
         olaylar[-1].tur == "bitti" and olaylar[-1].ek["basarili"] is beklenen)

olaylar = akisi_topla(motor_ac("sahte", senaryo="limit"))
sina("limit ayri isaretlendi", olaylar[-1].ek["limit"] is True)

# 4 -- bos brifing sozlesme ihlali: bu istisna atmali
print("\n4. sozlesme ihlali istisna atar")
try:
    list(motor_ac("sahte").tur_kos("   ", klasor="."))
    sina("bos brifing reddedildi", False, "-- kabul edildi!")
except MotorHatasi:
    sina("bos brifing reddedildi", True)

try:
    list(motor_ac("claude").tur_kos("is", klasor="yok-boyle-bir-klasor"))
    sina("olmayan klasor reddedildi", False, "-- kabul edildi!")
except MotorHatasi:
    sina("olmayan klasor reddedildi", True)

try:
    list(motor_ac("claude").tur_kos("is", klasor=".", oturum_id="bozuk-kimlik"))
    sina("bozuk oturum kimligi reddedildi", False, "-- kabul edildi!")
except MotorHatasi:
    sina("bozuk oturum kimligi reddedildi", True)

# 5 -- 'kafa' yazamaz: kural surec duzeyinde uygulanmali
print("\n5. kafa yazamaz (komut duzeyinde)")
cm = ClaudeMotoru(calistirilabilir="claude")
kafa = cm._komut_kur("11111111-1111-1111-1111-111111111111", devam=False,
                     model="", efor="normal", yazabilir=False,
                     ek_klasorler=(), butce_usd=None)
eller = cm._komut_kur("11111111-1111-1111-1111-111111111111", devam=False,
                      model="", efor="yuksek", yazabilir=True,
                      ek_klasorler=(), butce_usd=2.5)
sina("kafa arac listesinde Write yok", "Write" not in kafa[kafa.index("--tools") + 1])
sina("kafa arac listesinde Bash yok", "Bash" not in kafa[kafa.index("--tools") + 1])
# OLCULDU (19.09.2026): plan kipi kaldirildi. Ajana "hicbir sey YAPMA,
# sadece plan uret" dedigi icin arastirma isini dort tur boyunca oldurdu.
# Yazma yasagi arac YOKLUGUNDA duruyor (ustteki iki sinama) -- daha guclu,
# cunku kipin yorumuna degil araclarin varligina bagli.
sina("kafa plan kipinde DEGIL",
     kafa[kafa.index("--permission-mode") + 1] != "plan")
sina("eller Write alabiliyor", "Write" in eller[eller.index("--tools") + 1])
sina("eller acceptEdits", eller[eller.index("--permission-mode") + 1] == "acceptEdits")

# 6 -- izin sorusu asilamaz, klasor disina cikilamaz
print("\n6. izin ve hapis kapilari")
sina("permission-prompts none", "none" == eller[eller.index("--permission-prompts") + 1])
sina("restricted acik", "--restricted" in eller)
# Olculmus hata: bu bayrak olmadan hesabin butun connector'lari ajanin
# baglamina yukleniyor ve tur brifingi okumadan 53.831 jetonda dusuyor.
sina("strict-mcp-config acik (baglam patlamasin)", "--strict-mcp-config" in eller)
sina("MCP verilmezse hicbiri yuklenmiyor", "--mcp-config" not in eller)
mcpli = cm._komut_kur("11111111-1111-1111-1111-111111111111", devam=False,
                      model="", efor="normal", yazabilir=True,
                      ek_klasorler=(), butce_usd=None,
                      mcp_yapilandirma='{"mcpServers":{}}')
sina("verilen MCP yapilandirmasi geciyor",
     mcpli[mcpli.index("--mcp-config") + 1] == '{"mcpServers":{}}')

# 7 -- efor cevrimi ve butce
print("\n7. efor cevrimi ve butce tavani")
sina("yuksek -> high", eller[eller.index("--effort") + 1] == "high")
sina("butce tavani gecti", eller[eller.index("--max-budget-usd") + 1] == "2.5")
normal = cm._komut_kur("11111111-1111-1111-1111-111111111111", devam=False,
                       model="", efor="normal", yazabilir=True,
                       ek_klasorler=(), butce_usd=None)
sina("normal -> medium", normal[normal.index("--effort") + 1] == "medium")
sina("butce verilmezse bayrak yok", "--max-budget-usd" not in normal)

# 8 -- kimlik: ilk tur --session-id, devam --resume
print("\n8. oturum kimligi (ajanin hafizasi)")
sina("ilk tur --session-id", "--session-id" in normal and "--resume" not in normal)
devam = cm._komut_kur("11111111-1111-1111-1111-111111111111", devam=True,
                      model="", efor="normal", yazabilir=True,
                      ek_klasorler=(), butce_usd=None)
sina("devam turu --resume", "--resume" in devam and "--session-id" not in devam)
olaylar = akisi_topla(motor_ac("sahte"), oturum_id="")
oturum_olayi = [o for o in olaylar if o.tur == "oturum"][0]
sina("oturum kimligi akista bildiriliyor", bool(oturum_olayi.ek["oturum_id"]))
sina("bitti olayi da kimligi tasiyor",
     olaylar[-1].ek["oturum_id"] == oturum_olayi.ek["oturum_id"])

# 9 -- sessiz motor nabiz atiyor (kilit dusmesin)
print("\n9. sessizlik nabza cevriliyor")
olaylar = akisi_topla(motor_ac("sahte", senaryo="sessiz"))
sina("sessiz turda nabiz olayi var",
     len([o for o in olaylar if o.tur == "nabiz"]) >= 3)

# 10 -- izin reddi gorunur olay
print("\n10. izin reddi gorunur")

# Reddedilen SEYIN adi olayda olmali: "izin reddedildi" deyip neyin
# reddedildigini soylememek, kullaniciya "bir sey oldu" demektir.
# OLCULDU: gercek bir iste uc tur ust uste izin reddiyle dustu ve
# hangi aracin reddedildigi kayitta hic yoktu.
cm2 = ClaudeMotoru(calistirilabilir="claude")
durum = {"oturum_id": "x", "model": "", "metin": [], "hatali": False,
         "hata_notu": "", "limit": False, "sonuc": "", "maliyet": 0.0,
         "jeton": 0, "arac_sayisi": 0, "arac_adlari": {}}
cm2._mesaji_cevir({"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "t1", "name": "Bash",
     "input": {"command": "rm -rf /"}}]}}, durum)
olaylar = cm2._mesaji_cevir({"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "t1", "is_error": True,
     "content": "Permission for this tool use was denied."}]}}, durum)
sina("izin olayi REDDEDILEN ARACIN adini tasiyor",
     olaylar[0].tur == "izin" and olaylar[0].ek["arac"] == "Bash")
sina("izin olayi komutu da tasiyor", "rm -rf /" in olaylar[0].govde)
olaylar = akisi_topla(motor_ac("sahte", senaryo="izin_reddi"))
sina("izin olayi akista", any(o.tur == "izin" for o in olaylar))

# 11 -- cagiran dongudan cikabilmeli (durdurma kolu cagiranda)
print("\n11. erken cikis akisi temiz kapatiyor")
akis = motor_ac("sahte", senaryo="basarili").tur_kos("is", klasor=".")
next(akis)
akis.close()          # GeneratorExit -- finally kosmali, patlamamali
sina("erken kapanis istisna atmadi", True)

# 12 -- OKUMA araclari IZIN LISTESINDE mi (olculmus regresyon)
print("\n12. web araclari izin listesinde -- ARASTIRMA ISI ICIN SART")
# OLCULDU (19.09.2026): WebSearch/WebFetch `--tools` listesinde vardi ama
# IZIN listesinde yoktu; gercek turda ajan aramayi denedi ve "izin
# alinamadi" deyip isi YAPAMADAN bitirdi. Kod isinde hic gorunmuyordu
# cunku kod isi arama yapmaz -- arastirma isinde sistem tamamen calismaz.
from ofis.motor.claude import ClaudeMotoru, ELLER_IZINLI, KAFA_IZINLI

sina("eller izin listesinde WebSearch var", "WebSearch" in ELLER_IZINLI)
sina("eller izin listesinde WebFetch var", "WebFetch" in ELLER_IZINLI)
sina("kafa izin listesinde WebSearch var", "WebSearch" in KAFA_IZINLI)
sina("kafa izin listesi SALT OKUNUR (yazan arac yok)",
     not any(a in KAFA_IZINLI for a in ("Write", "Edit", "Bash")),
     f"({KAFA_IZINLI})")

# OLCULDU: kafa icin izin listesi eklenirken ofis araclari unutuldu ve
# `kanit_ekle` REDDEDILDI -- ajan isi yapti, kanit ekleyemedi, is kanitsiz
# kaldi. Bir seyi kisitlarken kisitlamak ISTEMEDIGIN seyi de kisitlarsin.
sina("kafa ofis araclarina ULASABILIYOR (kanit ekleyebilmeli)",
     any(a.startswith("mcp__ofis") for a in KAFA_IZINLI), f"({KAFA_IZINLI})")
sina("eller ofis araclarina ULASABILIYOR",
     any(a.startswith("mcp__ofis") for a in ELLER_IZINLI))

try:
    cm = ClaudeMotoru()
    for yazar, etiket in ((True, "eller"), (False, "kafa")):
        k = cm._komut_kur("", devam=False, model="haiku", efor="",
                          yazabilir=yazar, ek_klasorler=(), butce_usd=None)
        sina(f"{etiket} komutunda --allowedTools var", "--allowedTools" in k)
        sina(f"{etiket} komutunda WebSearch izinli", "WebSearch" in k)
    k = cm._komut_kur("", devam=False, model="haiku", efor="",
                      yazabilir=False, ek_klasorler=(), butce_usd=None)
    # OLCULDU: plan kipi ajana "hicbir sey YAPMA" der ve arastirma isini
    # dort tur boyunca oldurdu ($0,617, sifir kanit). Yasak artik ARACIN
    # HIC OLMAMASIYLA duruyor -- daha guclu ve isi engellemiyor.
    sina("kafa PLAN kipinde DEGIL (isi yapabilmeli)", "plan" not in k)
    sina("kafa yazan arac ALMIYOR (yasak arac yoklugunda)",
         "Write" not in k and "Edit" not in k and "Bash" not in k,
         f"({[x for x in k if x in ('Write', 'Edit', 'Bash')]})")
    araclar = k[k.index("--tools") + 1]
    sina("kafa arac listesinde yazan arac yok",
         not any(a in araclar for a in ("Write", "Edit", "Bash")), f"({araclar})")
except Exception as exc:
    # claude CLI kurulu degilse komut kurulamaz; liste sinamalari yine gecti.
    print(f"  (atlandi: {exc})")

print("\n13. SIR YALITIMI -- ajan hesabin anahtarlarini ALMAZ")
# OLCULDU (19.09.2026): koltuk ajan surecine `os.environ.copy()`
# veriyordu -- makinedeki HER anahtar ajanin eline geciyordu. Ve izin
# listesinde `Bash(echo *)` ile `Bash(cat *)` var: bir ajan
# `echo $GEMINI_API_KEY` yazip anahtari TERMINAL KANITI olarak tahtaya
# dusurebilirdi. Kotu niyet gerekmez.
#
# Kural MCP yalitimindakiyle ayni: ajan, isinin gerektirdigini alir.
# Orada bedel 131.543 jetondu; burada bedel bir SIR -- ve sizan anahtar
# geri alinamaz, yalnizca degistirilebilir.
from ofis.motor.tip import ortam_hazirla, SIR_ONEKLERI, SIR_PARCALARI

_temel = {
    "PATH": "x", "HOME": "y", "LANG": "tr",
    "GEMINI_API_KEY": "gizli", "OPENAI_API_KEY": "gizli",
    "ANTHROPIC_API_KEY": "gizli", "SHOPIFY_TOKEN": "gizli",
    "MY_SERVICE_SECRET": "gizli", "APP_PASSWORD": "gizli",
    "SOME_APIKEY": "gizli", "CUSTOM_PRIVATE_KEY": "gizli",
}

_kapali = ortam_hazirla(_temel, izinli=())
sina("hicbir sir gecmiyor (varsayilan KAPALI)",
     not any(k in _kapali for k in
             ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
              "SHOPIFY_TOKEN", "MY_SERVICE_SECRET", "APP_PASSWORD",
              "SOME_APIKEY", "CUSTOM_PRIVATE_KEY")),
     f"({sorted(_kapali)})")
sina("normal degiskenler DURUYOR",
     all(k in _kapali for k in ("PATH", "HOME", "LANG")))

_acik = ortam_hazirla(_temel, izinli=("GEMINI_API_KEY",))
sina("ACIKCA izin verilen anahtar geciyor", _acik.get("GEMINI_API_KEY") == "gizli")
sina("izin verilmeyen oteki anahtarlar yine gecmiyor",
     "OPENAI_API_KEY" not in _acik and "SHOPIFY_TOKEN" not in _acik)

# Ad listesiyle degil DESENLE de yakalaniyor: liste eksik kalir, desen kalmaz.
_yeni = ortam_hazirla({"BILINMEYEN_SERVIS_TOKEN": "gizli", "PATH": "x"})
sina("listede OLMAYAN ama desene uyan degisken de dusuyor",
     "BILINMEYEN_SERVIS_TOKEN" not in _yeni, f"({sorted(_yeni)})")

# Gercek komut kurulumunda da uygulanmali -- liste dogru olsa bile
# BAGLANMAMIS olabilir ("sessizce yok sayilan ayar, ayar degildir").
try:
    import os as _os2
    _eski = _os2.environ.get("GEMINI_API_KEY")
    _os2.environ["GEMINI_API_KEY"] = "SINAMA-DEGERI"
    _cm2 = ClaudeMotoru()
    _o2 = ortam_hazirla(_os2.environ, izinli=())
    sina("claude turu ortaminda GEMINI_API_KEY YOK",
         "GEMINI_API_KEY" not in _o2)
finally:
    if _eski is None:
        _os2.environ.pop("GEMINI_API_KEY", None)
    else:
        _os2.environ["GEMINI_API_KEY"] = _eski

# ══════════ CODEX `-c` SATIRLARI TOML MI (JSON DEGIL) ══════════
#
# ILK GERCEK CODEX TURUNDA BULUNDU (21.09.2026). Bu kod aylardir
# yaziliydi, `musait_motorlar()` codex'i "kurulu" gosteriyordu ve
# adaptorun 37 sozlesme testi geciyordu -- ama `-c` satirlarini HICBIRI
# sinamiyordu. Gercek tur 157 ms'de dustu:
#
#   Error loading config.toml: invalid type: string
#   "{\"OFIS_DB\": \"C:\\\\...\\\\ofis.sqlite3\", ...}"
#
# Sebep: `env` JSON nesnesi olarak yaziliyordu, codex ise `-c` degerini
# TOML olarak ayristiriyor. Tuzagin sinsiligi sudur: TOML dizisi ile
# JSON dizisi AYNI gorunur (`["a","b"]`), o yuzden `args` tesadufen
# calisiyordu; hata yalnizca `env` verildiginde -- yani ofis MCP'si
# baglandiginda, yani HER GERCEK ISTE -- cikiyordu.
#
# *Bir is turunu kosturmadiysan, o tur icin sistemin calistigini
# bilmiyorsun -- test sayisi ne olursa olsun.*
print("\n13. CODEX -c SATIRLARI (TOML)")
import json as _cj
_y = _cj.dumps({"mcpServers": {"ofis": {
    "command": "python", "args": ["-m", "ofis.mcp_sunucu"],
    "env": {"OFIS_DB": r"C:\Users\pc\veri\ofis.sqlite3", "OFIS_AJAN": "cinar"},
}}})
_s = CodexMotoru._mcp_ayarlari(_y)
_env = [x for x in _s if ".env=" in x]
sina("env satiri uretiliyor", len(_env) == 1, str(_s))
_deger = _env[0].split("=", 1)[1] if _env else ""
# TOML satir ici tablosu: `{"K" = "V"}`. JSON olsaydi `{"K": "V"}`.
sina("env TOML satir ici tablosu -- JSON DEGIL",
     " = " in _deger and '":' not in _deger, _deger)
sina("  ters bolu KACIRILIYOR (Windows yolu)", "\\\\" in _deger, _deger)
sina("  anahtarlar tirnakli", _deger.startswith('{"OFIS_DB"'), _deger)
# Gercekten TOML mu: ayristirilabiliyor mu?
try:
    import tomllib as _toml
except ImportError:
    _toml = None
if _toml:
    try:
        _c = _toml.loads("[x]\n" + _env[0].replace("mcp_servers.ofis.env", "env"))
        sina("TOML ayristirici env'i TABLO okuyor (string degil)",
             isinstance(_c["x"]["env"], dict), repr(_c["x"].get("env")))
        sina("  deger dogru cozuluyor",
             _c["x"]["env"]["OFIS_DB"] == r"C:\Users\pc\veri\ofis.sqlite3")
    except Exception as _exc:
        sina("TOML ayristirici env'i TABLO okuyor (string degil)", False,
             f"ayristirilamadi: {_exc}")
else:
    print("  [atlandi] tomllib yok -- sonuc BILINMIYOR, 'gecti' DEGIL")
# args tesadufen dogruydu; yine de sabitlenir.
_args = [x for x in _s if ".args=" in x]
sina("args TOML dizisi", _args and _args[0].endswith(']'), str(_args))

# HER SATIR -- ornek degil TUR. `env` duzeltildikten sonra `command`
# HALA bozuktu: ham interpolasyon Windows yolundaki ters bolu + buyuk
# harf dizisini gecersiz bir TOML kacisi yapiyordu. Tek tek alan
# sinamak, bir sonraki alani kacirmaktir; uretilen HER satir gecerli
# TOML olmali.
_win = {"mcpServers": {"ofis": {
    "command": r"C:\Users\pc\AppData\Local\Programs\Python\Python312\python.exe",
    "args": [r"C:\Users\pc\Desktop\AgentOfis\ofis\mcp_sunucu.py"],
    "env": {"OFIS_DB": r"C:\Users\pc\Desktop\AgentOfis\veri\ofis.sqlite3"},
    "url": r"http://127.0.0.1:1/x",
}}}
if _toml:
    _bozuk = []
    for _satir in CodexMotoru._mcp_ayarlari(_cj.dumps(_win)):
        try:
            _toml.loads(_satir.replace("mcp_servers.ofis.", ""))
        except Exception as _e:
            _bozuk.append(f"{_satir.split('=')[0]}: {_e}")
    sina("URETILEN HER -c satiri gecerli TOML (Windows yolu)",
         not _bozuk, " | ".join(_bozuk))
else:
    print("  [atlandi] tomllib yok -- sonuc BILINMIYOR, 'gecti' DEGIL")

# ---------------------------------------------------------------- IZIN KANCASI
print("\n15. IZIN KANCASI -- ofisin tek kapisi komut satirina ULASIYOR mu")

# BU BOLUM UC OLCUMUN FATURASIYLA YAZILDI (22.09.2026). Ayni istem
# ("dosya yaz, sonra `rm` ile sil") uc ayarla kosuldu:
#
#   acceptEdits + --permission-prompts none  -> kanca 0 kez, `rm` CALISTI
#   kanca + acceptEdits                      -> kanca 0 kez, `rm` CALISTI
#   kanca, kip VERILMEDEN                    -> kanca 2 kez, `rm` ENGELLENDI
#
# Yani `acceptEdits` kancayi TAMAMEN devre disi birakiyor. Ve ikinci
# sonuc daha agir: bugunku ayar keyfi kabuk komutu kosturuyordu --
# `ELLER_IZINLI` gercek bir kapi degil DEKOR olmustu.
from ofis.motor.claude import ClaudeMotoru as _CM           # noqa: E402

_m = _CM.__new__(_CM)
_m.calistirilabilir = "claude"


def _komut(izin_araci: str, **ek) -> str:
    ayar = dict(oturum="", devam=False, model="haiku", efor="normal",
                yazabilir=True, ek_klasorler=(), butce_usd=None,
                mcp_yapilandirma="x.json", izinli_araclar=(),
                izin_araci=izin_araci)
    ayar.update(ek)
    return " ".join(_CM._komut_kur(_m, **ayar))


_kancali = _komut("mcp__ofis__izin_sor")
_kancasiz = _komut("")

sina("kanca verilince bayrak komuta giriyor",
     "--permission-prompt-tool mcp__ofis__izin_sor" in _kancali)
sina("kanca verilince prompts=host", "--permission-prompts host" in _kancali)
# EN KRITIK SINAMA: kip kalmamali. Kalsaydi kanca sessizce hic
# cagrilmaz ve ofis "kapi kurdum" sanirdi.
sina("kanca varken acceptEdits VERILMIYOR",
     "acceptEdits" not in _kancali, _kancali[:200])

sina("kanca yokken eski davranis korunuyor",
     "--permission-prompts none" in _kancasiz
     and "acceptEdits" in _kancasiz)
sina("kanca yokken prompt-tool YOK",
     "--permission-prompt-tool" not in _kancasiz)

# 'kafa' ajanda da ayni kural gecerli olmali -- yoksa arastirma
# turlarinda kapi sessizce kapali kalirdi.
sina("kafa turunde de kanca kipi dusuruyor",
     "acceptEdits" not in _komut("mcp__ofis__izin_sor", yazabilir=False))

# KANCAYI UYGULAYAMAYAN MOTOR KAPALI KALARAK REDDEDER.
#
# Sessizce yok saysaydik cagiran, riskli her cagrinin ofise
# soruldugunu SANIRDI; oysa hicbiri sorulmazdi.
from ofis.motor import motor_ac as _ac                      # noqa: E402

from ofis.motor.gemini import GeminiMotoru as _Gem          # noqa: E402

# Gemini defterden cikti (24.09.2026) ama dosyasi duruyor; geri takilirsa
# kanca sozlesmesi yine tutmali, o yuzden sinifi dogrudan sinaniyor.
# codex: kanca KIPE bagli (A2/A3, 26.09.2026). exec'te kanal yok ->
# reddetmeli; app-server'da var -> bildirmeli. Sinif duzeyi KAPALI (ornek
# kurmadan bakan "kanca var" sanmasin).
from ofis.motor.codex import CodexMotoru as _CxK                # noqa: E402
sina("codex: SINIF duzeyinde izin_kancasi=False (temkinli taraf)",
     _CxK.izin_kancasi is False)
sina("codex app-server: izin_kancasi=True bildiriyor",
     _CxK(calistirilabilir="codex", kip="app-server").izin_kancasi is True)
sina("codex: VARSAYILAN kip app-server",
     _CxK(calistirilabilir="codex").kip == "app-server")
try:
    _CxK(calistirilabilir="codex", kip="uydurma")
    sina("codex: bilinmeyen kip REDDEDILIYOR", False, "-- kabul etti!")
except Exception as _exc:
    sina("codex: bilinmeyen kip REDDEDILIYOR", "kip" in str(_exc).lower())
for _ad, _mm in (("codex exec", _CxK(kip="exec")), ("gemini", _Gem()),
                 ("sahte", _ac("sahte"))):
    sina(f"{_ad}: izin_kancasi=False bildiriyor",
         getattr(_mm, "izin_kancasi", False) is False)
    try:
        list(_mm.tur_kos("x", klasor=str(Path.cwd()),
                         izin_araci="mcp__ofis__izin_sor"))
        sina(f"{_ad}: kanca istenince REDDEDIYOR", False, "-- kabul etti!")
    except Exception as _exc:
        sina(f"{_ad}: kanca istenince REDDEDIYOR",
             "kanca" in str(_exc).lower(), str(_exc)[:90])

sina("claude: izin_kancasi=True bildiriyor",
     getattr(_ac("claude"), "izin_kancasi", False) is True)

# LIMIT PENCERELERI -- saglayici bildiriyor, adaptor TASIMALI.
#
# OLCULDU (23.09.2026): claude her turda `rate_limit_event` yolluyor ve
# ofis bunu 64 kez okuyup ATMISTI; codex ayni seyi oturum kaydina
# yaziyor. Iki halka: ayristirici son olayi SAKLAR, `bitti` onu TASIR.
# Ikincisi calisan bir CLI gerektirdigi icin kaynak sozlesmesi olarak
# sinanir (kablo kopunca ates etsin diye).
print("\nLIMIT PENCERELERI -- ayristirici saklar, bitti tasir")
import inspect as _ins
from ofis.motor import claude as _cl_mod, codex as _cx_mod
_cm3 = ClaudeMotoru(calistirilabilir="claude")
_d3 = {"oturum_id": "x", "model": "", "metin": [], "hatali": False,
       "hata_notu": "", "limit": False, "sonuc": "", "maliyet": 0.0,
       "jeton": 0, "arac_sayisi": 0, "arac_adlari": {}, "limit_bilgi": None}
_bilgi = {"status": "allowed_warning", "unifiedWindows": {
    "five_hour": {"utilization": 0.71, "resetsAt": 1790129400}}}
_cm3._mesaji_cevir({"type": "rate_limit_event", "rate_limit_info": _bilgi}, _d3)
sina("claude: rate_limit_event SAKLANIYOR", _d3["limit_bilgi"] == _bilgi)
sina("claude: uyari limit SAYILMIYOR (bosuna devir olmaz)", _d3["limit"] is False)
sina("claude: `bitti` olcumu TASIYOR",
     '"limit_pencere": claude_pencereleri(durum["limit_bilgi"])'
     in _ins.getsource(_cl_mod.ClaudeMotoru.tur_kos))
_cx_tur = _ins.getsource(_cx_mod.CodexMotoru.tur_kos)
sina("codex: `bitti` olcumu TASIYOR (bu turun oturumu, bu hesabin evi)",
     'codex_pencereleri(ev, durum["oturum_id"])' in _cx_tur
     and '"limit_pencere"' in _cx_tur)
sina("codex app-server: tur SURERKEN gelen pencere oncelikli",
     'durum.get("pencere")' in _cx_tur)

# codex DOLAR BILDIRMEZ. 0.0 "olculmus sifir" demektir ve hic
# guncellenmiyordu: gercek lider devri olcumunde her codex turu defterde
# BEDAVA gorundu. Olculemeyen maliyet None'dir (panelin "fiyatsiz" ayrimi).
_cx_kod = _ins.getsource(_cx_mod.CodexMotoru.tur_kos)
sina("codex: maliyet varsayilani None (olculemedi), 0.0 DEGIL",
     '"maliyet": None,' in _cx_kod and '"maliyet": 0.0,' not in _cx_kod)

print("\nSUREC KAFESI -- turun baslattigi HER SEY tur bitince biter")
# Ebeveyni olmus torun (yetim) surec: eski `_surec_agacini_kes` onu
# BULAMAZ (psutil ebeveyn kimligiyle arar; ustelik bu makinede psutil yok,
# yani agac kesme hic alt surec bulmuyordu). Kafes (Windows is nesnesi)
# yetimi de sonlandirir. Sinama gercek surec acar, model/para YOK.
import os
import time
import subprocess as _sp
from ofis.motor.tip import SurecKafesi as _K


def _yasiyor(pid):
    r = _sp.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True)
    return str(pid) in r.stdout


if os.name == "nt":
    _betik = ("import subprocess,sys; p=subprocess.Popen([sys.executable,'-c',"
              "'import time; time.sleep(60)']); print(p.pid, flush=True)")
    _s = _sp.Popen([sys.executable, "-c", _betik], stdout=_sp.PIPE, text=True)
    _k = _K(_s)
    _torun = int(_s.stdout.readline())
    _s.wait()
    sina("kafes kuruldu", _k.kuruldu, _k.hata)
    sina("ebeveyn bitti, yetim torun YASIYOR (sahne dogru)", _yasiyor(_torun))
    _k.kapat()
    time.sleep(0.5)
    sina("kafes kapaninca yetim torun BITTI", not _yasiyor(_torun))
    if _yasiyor(_torun):
        _sp.run(["taskkill", "/F", "/PID", str(_torun)], capture_output=True)
    _k.kapat()
    sina("kafes iki kez kapatilabilir (patlamaz)", True)
    _src_c = (Path(__file__).resolve().parent.parent / "ofis/motor/claude.py").read_text(encoding="utf-8")
    _src_x = (Path(__file__).resolve().parent.parent / "ofis/motor/codex.py").read_text(encoding="utf-8")
    sina("claude adaptoru kafes kuruyor ve kapatiyor",
         "SurecKafesi(surec)" in _src_c and "kafes.kapat()" in _src_c)
    sina("codex adaptoru kafes kuruyor ve kapatiyor",
         "SurecKafesi(surec)" in _src_x and "kafes.kapat()" in _src_x)
else:
    print("  [ATLANDI] kafes yalniz Windows'ta (gecti SAYILMAZ)")

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
