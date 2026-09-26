# -*- coding: utf-8 -*-
"""CODEX APP-SERVER: onay kapisi, olay cevrimi, hata siniflari -- JETONSUZ.

Gercek codex KOSMAZ: app-server protokolunu (26.09.2026 semasi) konusan
SAHTE bir sunucu kurulur. Sunucu, adaptorun kendisine gonderdigi HER seyi
bir kayda yazar; sinamalar sonuca modelin sozune degil O KAYDA bakar.

Sinanan (olcumle kurulan kurallar, codex.py dosya basi):
1. Riskli komut ofisin kapisina (`mcpServer/tool/call` -> izin_sor) SORULUR,
   `decline` verilir ve kapinin GEREKCESI ajana `turn/steer` ile iletilir.
2. Zararsiz komut `accept` alir.
3. Ofisin kendi MCP araci (elicitation) `mcp__ofis__<arac>` adiyla sorulur;
   cevap `action` bicimindedir (olculdu: bicim yanlisken sunucu dusuyordu).
4. Kapi cevap veremezse KAPALI KALIR.
5. Tanimadigi istek CEVAPSIZ birakilmaz.
6. Kanca yokken gelen onay REDDEDILIR.
7. Limit / oturum hatalari YAPISAL koddan siniflanir.
8. Jeton, pencere, metin, oturum kimligi `bitti`ye ulasir.
9. Zaman asiminda `turn/interrupt` gonderilir.
10. `devam` -> `thread/resume`.
"""

from __future__ import annotations

import _temizlik  # noqa: F401 -- gecici klasorleri siler (E05); ILK ice aktarma

import json
import os
import sys
import tempfile
from pathlib import Path

ANA = Path(tempfile.mkdtemp(prefix="ofis-codexapp-"))
# Gercek codex evine ve olu oturum defterine DOKUNULMAZ.
os.environ["OFIS_CODEX_HOME"] = str(ANA / "ev")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ofis.motor import codex as CX          # noqa: E402

CX.OTURUM_DEFTERI = ANA / "codex_oturum.json"

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


SAHTE = r'''
import json, os, sys, time, threading
KILIT = threading.Lock()
sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")
SEN = json.load(open(os.environ["SAHTE_SENARYO"], encoding="utf-8"))
KAYIT = open(os.environ["SAHTE_KAYIT"], "a", encoding="utf-8")
T, U = "thr-1", "tur-1"
adim = [0]
bekle = [None]
def yaz(m):
    with KILIT:
        sys.stdout.write(json.dumps(m, ensure_ascii=False) + "\n"); sys.stdout.flush()
def kaydet(m):
    with KILIT:
        KAYIT.write(json.dumps(m, ensure_ascii=False) + "\n"); KAYIT.flush()
def mcp_durumlari():
    # AYRI iplikte: sunucu beklerken istemcinin ERKEN gonderdigi istek de
    # okunup kaydedilsin -- yoksa sira her zaman "dogru" gorunur (mutasyon
    # bunu gosterdi: bekleme kaldirilinca sinama ates ETMEDI).
    for ad, durum, bekle_sn in SEN.get("mcp", []):
        time.sleep(bekle_sn)
        kaydet({"_sahte": f"{ad}:{durum}"})
        yaz({"jsonrpc": "2.0", "method": "mcpServer/startupStatus/updated",
             "params": {"threadId": T, "name": ad, "status": durum,
                        "failureReason": "sahte cokme" if durum == "failed" else None}})
def ilerle():
    adimlar = SEN.get("adimlar", [])
    while bekle[0] is None and adim[0] < len(adimlar):
        a = adimlar[adim[0]]; adim[0] += 1
        if "istek" in a:
            kid = "s%d" % adim[0]
            yaz({"jsonrpc": "2.0", "id": kid, "method": a["istek"],
                 "params": dict(a.get("params") or {}, threadId=T, turnId=U)})
            bekle[0] = kid
        elif "bildirim" in a:
            yaz({"jsonrpc": "2.0", "method": a["bildirim"], "params": a.get("params") or {}})
        elif "bitir" in a:
            yaz({"jsonrpc": "2.0", "method": "turn/completed",
                 "params": {"threadId": T, "turn": {"id": U, "status": a["bitir"],
                                                    "error": a.get("hata")}}})
        elif "asili" in a:
            return
while True:
    satir = sys.stdin.readline()
    if not satir:
        break
    m = json.loads(satir); kaydet(m)
    meth, mid = m.get("method"), m.get("id")
    if meth is None:
        if mid == bekle[0]:
            bekle[0] = None; ilerle()
        continue
    if meth == "initialize":
        yaz({"jsonrpc": "2.0", "id": mid, "result": {}})
    elif meth in ("thread/start", "thread/resume"):
        yaz({"jsonrpc": "2.0", "id": mid,
             "result": {"thread": {"id": m["params"].get("threadId") or T}, "model": "sahte-model"}})
        threading.Thread(target=mcp_durumlari, daemon=True).start()
    elif meth == "turn/start":
        yaz({"jsonrpc": "2.0", "id": mid, "result": {"turn": {"id": U, "status": "inProgress"}}})
        yaz({"jsonrpc": "2.0", "method": "turn/started", "params": {"threadId": T, "turn": {"id": U}}})
        ilerle()
    elif meth == "mcpServer/tool/call":
        g = (m["params"].get("arguments") or {})
        if SEN.get("kapi_bozuk"):
            yaz({"jsonrpc": "2.0", "id": mid, "error": {"code": -1, "message": "kapi coktu"}})
            continue
        komut = str((g.get("input") or {}).get("command") or "")
        riskli = "Remove-Item" in komut or "rm " in komut or g.get("tool_name") == "izin_genisletme"
        karar = ({"behavior": "deny", "message": "ONAY ISTENDI -- SIMDI DUR. Sinif: SILME"}
                 if riskli else {"behavior": "allow", "updatedInput": g.get("input")})
        yaz({"jsonrpc": "2.0", "id": mid,
             "result": {"content": [{"type": "text", "text": json.dumps(karar)}]}})
    elif meth in ("turn/steer",):
        if SEN.get("steer_red"):
            yaz({"jsonrpc": "2.0", "id": mid,
                 "error": {"code": -32600, "message": "no active turn"}})
        else:
            yaz({"jsonrpc": "2.0", "id": mid, "result": {"turnId": U}})
        if SEN.get("steer_sonra_bitir"):
            yaz({"jsonrpc": "2.0", "method": "turn/completed",
                 "params": {"threadId": T, "turn": {"id": U, "status": "completed"}}})
    elif meth == "turn/interrupt":
        yaz({"jsonrpc": "2.0", "id": mid, "result": {}})
        yaz({"jsonrpc": "2.0", "method": "turn/completed",
             "params": {"threadId": T, "turn": {"id": U, "status": "interrupted"}}})
    elif mid is not None:
        yaz({"jsonrpc": "2.0", "id": mid, "result": {}})
'''

sahte_py = ANA / "sahte_app.py"
sahte_py.write_text(SAHTE, encoding="utf-8")
sahte_cmd = ANA / "sahte_codex.cmd"
sahte_cmd.write_text(f'@"{sys.executable}" "{sahte_py}" %*\r\n', encoding="utf-8")
klasor = ANA / "is"
klasor.mkdir()

KOMUT_RM = '"C:\\\\x\\\\powershell.exe" -NoProfile -Command \'Remove-Item a.txt\''
KOMUT_SET = "Set-Content a.txt merhaba"


def kos(ad: str, adimlar: list, **kw):
    """Senaryoyu kosturur; (olaylar, bitti.ek, kayittaki mesajlar) doner."""
    senaryo = ANA / f"{ad}.json"
    kayit = ANA / f"{ad}.kayit.jsonl"
    senaryo.write_text(json.dumps({"adimlar": adimlar,
                                   "kapi_bozuk": kw.pop("kapi_bozuk", False),
                                   "steer_red": kw.pop("steer_red", False),
                                   "steer_sonra_bitir": kw.pop("steer_sonra_bitir", False),
                                   "mcp": kw.pop("mcp_durum", [])}),
                       encoding="utf-8")
    os.environ["SAHTE_SENARYO"] = str(senaryo)
    os.environ["SAHTE_KAYIT"] = str(kayit)
    m = CX.CodexMotoru(calistirilabilir=str(sahte_cmd), kip="app-server")
    kw.setdefault("izin_araci", "mcp__ofis__izin_sor")
    kw.setdefault("zaman_asimi", 30)
    olaylar = list(m.tur_kos("gorev metni", klasor=str(klasor), efor="dusuk", **kw))
    gelen = ([json.loads(s) for s in kayit.read_text(encoding="utf-8").splitlines()]
             if kayit.exists() else [])
    return olaylar, olaylar[-1].ek, gelen


def cevap(gelen: list, kid: str):
    for g in gelen:
        if g.get("id") == kid and "method" not in g:
            return g
    return None


def istekler(gelen: list, yontem: str) -> list:
    return [g for g in gelen if g.get("method") == yontem]


try:
    # ------------------------------------------------------------ 0
    print("\n0. YALITIM")
    sina("codex evi gecici", CX.CodexMotoru._ev_bul().startswith(str(ANA)))
    sina("olu oturum defteri gecici", str(CX.OTURUM_DEFTERI).startswith(str(ANA)))

    # ------------------------------------------------------------ 1
    print("\n1. RISKLI KOMUT: kapiya sorulur, reddedilir, GEREKCE ajana gider")
    ol, ek, gelen = kos("rm", [
        {"istek": "item/commandExecution/requestApproval", "params": {"command": KOMUT_RM}},
        {"bildirim": "item/completed", "params": {"item": {"type": "agentMessage", "text": "durdum"}}},
        {"bitir": "completed"}])
    sorular = istekler(gelen, "mcpServer/tool/call")
    sina("kapiya SORULDU (mcpServer/tool/call)", len(sorular) == 1, str(len(sorular)))
    arg = (sorular[0]["params"] if sorular else {})
    sina("kapi = ofis/izin_sor", arg.get("server") == "ofis" and arg.get("tool") == "izin_sor")
    sina("kapiya Bash + komut gitti",
         (arg.get("arguments") or {}).get("tool_name") == "Bash"
         and "Remove-Item" in str((arg.get("arguments") or {}).get("input")))
    c = cevap(gelen, "s1")
    sina("codex'e `decline` verildi", (c or {}).get("result") == {"decision": "decline"}, str(c))
    steer = istekler(gelen, "turn/steer")
    sina("GEREKCE ajana steer ile gitti",
         len(steer) == 1 and "OFIS KAPISI" in json.dumps(steer[0], ensure_ascii=False)
         and "SIMDI DUR" in json.dumps(steer[0], ensure_ascii=False), str(steer)[:200])
    sina("steer DOGRU tura (expectedTurnId)",
         bool(steer) and steer[0]["params"].get("expectedTurnId") == "tur-1")
    sina("izin olayi yazildi", any(o.tur == "izin" and "Bash" in o.govde for o in ol))
    sina("tur yine BASARILI kapandi", ek.get("basarili") is True, str(ek)[:200])

    # ------------------------------------------------------------ 2
    print("\n2. ZARARSIZ KOMUT: accept, steer YOK")
    ol, ek, gelen = kos("set", [
        {"istek": "item/commandExecution/requestApproval", "params": {"command": KOMUT_SET}},
        {"bitir": "completed"}])
    sina("accept verildi", (cevap(gelen, "s1") or {}).get("result") == {"decision": "accept"})
    sina("steer GONDERILMEDI", not istekler(gelen, "turn/steer"))
    sina("izin olayi YOK", not any(o.tur == "izin" for o in ol))

    # ------------------------------------------------------------ 3
    print("\n3. OFISIN KENDI MCP ARACI (elicitation): dogru ad, dogru bicim")
    ol, ek, gelen = kos("mcp", [
        {"istek": "mcpServer/elicitation/request", "params": {
            "serverName": "ofis", "mode": "form",
            "message": 'Allow the ofis MCP server to run tool "kanit_ekle"?',
            "_meta": {"codex_approval_kind": "mcp_tool_call",
                      "tool_params": {"tur": "terminal", "baslik": "x"}}}},
        {"bitir": "completed"}])
    arg = (istekler(gelen, "mcpServer/tool/call") or [{}])[0].get("params") or {}
    sina("kapiya `mcp__ofis__kanit_ekle` adiyla soruldu",
         (arg.get("arguments") or {}).get("tool_name") == "mcp__ofis__kanit_ekle", str(arg)[:200])
    sina("parametreler kapiya gitti",
         ((arg.get("arguments") or {}).get("input") or {}).get("baslik") == "x")
    sina("cevap `action: accept` bicimde",
         ((cevap(gelen, "s1") or {}).get("result") or {}).get("action") == "accept")
    ol, ek, gelen = kos("mcp_adsiz", [
        {"istek": "mcpServer/elicitation/request", "params": {
            "serverName": "ofis", "message": "anlasilmaz", "_meta": {}}},
        {"bitir": "completed"}])
    arg = (istekler(gelen, "mcpServer/tool/call") or [{}])[0].get("params") or {}
    sina("ADI cikarilamayan istek kapiya TANINMAYAN adla gider (kapi sorar)",
         str((arg.get("arguments") or {}).get("tool_name", "")).startswith("mcp_istegi__"))

    # ------------------------------------------------------------ 4
    print("\n4. KAPI COKERSE KAPALI KALIR")
    ol, ek, gelen = kos("bozuk", [
        {"istek": "item/commandExecution/requestApproval", "params": {"command": KOMUT_SET}},
        {"bitir": "completed"}], kapi_bozuk=True)
    sina("zararsiz komut bile DECLINE", (cevap(gelen, "s1") or {}).get("result") == {"decision": "decline"})
    sina("sebep ajana soylendi (steer)", len(istekler(gelen, "turn/steer")) == 1)

    # ------------------------------------------------------------ 5
    print("\n5. TANINMAYAN ISTEK CEVAPSIZ KALMAZ")
    ol, ek, gelen = kos("bilinmeyen", [
        {"istek": "item/tool/requestUserInput", "params": {"questions": []}},
        {"bitir": "completed"}])
    c = cevap(gelen, "s1") or {}
    sina("hata ile cevaplandi", (c.get("error") or {}).get("code") == CX.DESTEKSIZ_ISTEK_KODU, str(c))
    sina("kapiya SORULMADI (onay degil)", not istekler(gelen, "mcpServer/tool/call"))

    # ------------------------------------------------------------ 6
    print("\n6. KANCA YOKKEN GELEN ONAY REDDEDILIR")
    ol, ek, gelen = kos("kancasiz", [
        {"istek": "item/commandExecution/requestApproval", "params": {"command": KOMUT_SET}},
        {"bitir": "completed"}], izin_araci="")
    sina("decline", (cevap(gelen, "s1") or {}).get("result") == {"decision": "decline"})
    ts = istekler(gelen, "thread/start")
    sina("kancasiz politika `never`", bool(ts) and ts[0]["params"].get("approvalPolicy") == "never")
    ol, ek, gelen = kos("kancali_politika", [{"bitir": "completed"}])
    ts = istekler(gelen, "thread/start")
    sina("kancali politika `untrusted`",
         bool(ts) and ts[0]["params"].get("approvalPolicy") == "untrusted")
    sina("sandbox workspace-write (yazabilir)",
         bool(ts) and ts[0]["params"].get("sandbox") == "workspace-write")
    ol, ek, gelen = kos("kafa", [{"bitir": "completed"}], yazabilir=False)
    ts = istekler(gelen, "thread/start")
    sina("yazamaz -> sandbox read-only",
         bool(ts) and ts[0]["params"].get("sandbox") == "read-only")

    # ------------------------------------------------------------ 7
    print("\n7. HATA SINIFLARI YAPISAL KODDAN")
    ol, ek, gelen = kos("limit", [{"bitir": "failed", "hata": {
        "message": "bir sey oldu", "codexErrorInfo": "usageLimitExceeded"}}])
    sina("usageLimitExceeded -> limit", ek.get("limit") is True and ek.get("basarili") is False)
    sina("limit olayi var", any(o.tur == "limit" for o in ol))
    ol, ek, gelen = kos("oturum", [{"bitir": "failed", "hata": {
        "message": "x", "codexErrorInfo": "unauthorized"}}])
    sina("unauthorized -> oturum_kapandi (limit DEGIL)",
         ek.get("sebep") == "oturum_kapandi" and ek.get("limit") is False, str(ek.get("sebep")))
    sina("olu oturum KAYDEDILDI (gecici defter)", CX.OTURUM_DEFTERI.exists())
    ol, ek, gelen = kos("tekrar", [
        {"bildirim": "error", "params": {"error": {"message": "gecici", "codexErrorInfo": "usageLimitExceeded"},
                                         "willRetry": True}},
        {"bitir": "completed"}])
    sina("willRetry hatasi turu DUSURMEZ", ek.get("basarili") is True and ek.get("limit") is False)

    # ------------------------------------------------------------ 8
    print("\n8. OLCUMLER bitti'ye ULASIR")
    ol, ek, gelen = kos("olcum", [
        {"bildirim": "item/started", "params": {"item": {"type": "commandExecution", "id": "c1",
                                                         "command": "ls"}}},
        {"bildirim": "item/completed", "params": {"item": {"type": "commandExecution", "id": "c1",
                                                           "exitCode": 0, "aggregatedOutput": "a.txt"}}},
        {"bildirim": "thread/tokenUsage/updated", "params": {"tokenUsage": {"total": {
            "inputTokens": 100, "outputTokens": 10, "cachedInputTokens": 40}}}},
        {"bildirim": "account/rateLimits/updated", "params": {"rateLimits": {
            "primary": {"usedPercent": 20, "windowDurationMins": 300, "resetsAt": 1790397644},
            "secondary": {"usedPercent": 42, "windowDurationMins": 10080, "resetsAt": 1790717703},
            "planType": "plus"}}},
        {"bildirim": "item/completed", "params": {"item": {"type": "agentMessage", "text": "BITTI"}}},
        {"bitir": "completed"}])
    sina("oturum kimligi (thread)", ek.get("oturum_id") == "thr-1")
    sina("model (sunucunun bildirdigi)", ek.get("model") == "sahte-model")
    sina("jeton exec ile AYNI formul (girdi+cikti+onbellek)", ek.get("jeton") == 150, str(ek.get("jeton")))
    p = ek.get("limit_pencere") or {}
    sina("pencere tur SURERKEN geldi (app-server kaynagi)",
         "app-server" in str(p.get("kaynak")) and (p.get("pencereler") or {}).get("5s", {}).get("kullanim") == 0.2,
         str(p)[:200])
    sina("arac sayildi", ek.get("arac_sayisi") == 1)
    sina("arac + arac_sonuc olaylari", any(o.tur == "arac" for o in ol) and any(o.tur == "arac_sonuc" for o in ol))
    sina("metin -> basarili cevap", ek.get("basarili") is True and ol[-1].govde == "BITTI")
    sina("maliyet OLCULEMEDI (None), 0.0 degil", ek.get("maliyet_usd") is None)
    tsi = istekler(gelen, "turn/start")
    sina("efor turn/start'a gitti (dusuk -> low)", bool(tsi) and tsi[0]["params"].get("effort") == "low")

    # ------------------------------------------------------------ 9
    print("\n9. ZAMAN ASIMI: interrupt gonderilir")
    ol, ek, gelen = kos("asili", [{"asili": True}], zaman_asimi=4)
    sina("zaman_asimi bildirildi", ek.get("zaman_asimi") is True and ek.get("basarili") is False)
    sina("turn/interrupt GONDERILDI", len(istekler(gelen, "turn/interrupt")) == 1)

    # ------------------------------------------------------------ 10
    print("\n10. DEVAM -> thread/resume")
    ol, ek, gelen = kos("devam", [{"bitir": "completed"}],
                        oturum_id="11111111-1111-1111-1111-111111111111")
    rs = istekler(gelen, "thread/resume")
    sina("thread/resume kullanildi", len(rs) == 1 and not istekler(gelen, "thread/start"))
    sina("dogru kimlikle", bool(rs) and rs[0]["params"].get("threadId") == "11111111-1111-1111-1111-111111111111")

    # ------------------------------------------------------------ 11
    print("\n11. HER SUNUCU ISTEGI CEVAPLANDI (hicbiri asili kalmadi)")
    for ad, adimlar in (("hepsi", [
            {"istek": "item/commandExecution/requestApproval", "params": {"command": KOMUT_SET}},
            {"istek": "item/fileChange/requestApproval", "params": {}},
            {"istek": "item/permissions/requestApproval", "params": {"permissions": {"network": {"enabled": True}}}},
            {"istek": "account/chatgptAuthTokens/refresh", "params": {}},
            {"bitir": "completed"}]),):
        ol, ek, gelen = kos(ad, adimlar)
        sina("dort istegin dordu de cevaplandi",
             all(cevap(gelen, f"s{i}") for i in (1, 2, 3, 4)))
        sina("dosya yazimi (Write) serbest: accept",
             (cevap(gelen, "s2") or {}).get("result") == {"decision": "accept"})
        sina("izin genisletme kapiya soruldu ve REDDEDILDI (bos izin)",
             (cevap(gelen, "s3") or {}).get("result") == {"permissions": {}}, str(cevap(gelen, "s3")))
        sina("tur bitti", ek.get("basarili") is True)

    # ------------------------------------------------------------ 11b
    print("\n11b. TUR, MCP HAZIR OLMADAN BASLAMAZ (olculmus yaris)")
    MCP = json.dumps({"mcpServers": {"ofis": {"command": "python", "args": ["x.py"]}}})

    def sira(gelen, isaret):
        adlar = [g.get("_sahte") or g.get("method") for g in gelen]
        return (adlar.index(isaret) if isaret in adlar else -1,
                adlar.index("turn/start") if "turn/start" in adlar else -1)
    ol, ek, gelen = kos("mcp_hazir", [{"bitir": "completed"}], mcp_yapilandirma=MCP,
                        mcp_durum=[["ofis", "starting", 0], ["ofis", "ready", 1.5]])
    hazir_i, tur_i = sira(gelen, "ofis:ready")
    sina("turn/start, 'ready'den SONRA", 0 <= hazir_i < tur_i, f"ready={hazir_i} tur={tur_i}")
    sina("tur basarili", ek.get("basarili") is True)
    ol, ek, gelen = kos("mcp_dustu", [{"bitir": "completed"}], mcp_yapilandirma=MCP,
                        mcp_durum=[["ofis", "starting", 0], ["ofis", "failed", 0.5]])
    sina("dusen sunucu GORUNUR (hata olayi)",
         any(o.tur == "hata" and (o.ek or {}).get("sebep") == "mcp_acilamadi" for o in ol))
    sina("dusen sunucuya ragmen tur basladi", bool(istekler(gelen, "turn/start")))
    eski_sn = CX.MCP_HAZIR_SN
    CX.MCP_HAZIR_SN = 2.0
    try:
        ol, ek, gelen = kos("mcp_sessiz", [{"bitir": "completed"}], mcp_yapilandirma=MCP,
                            mcp_durum=[["ofis", "starting", 0]])
    finally:
        CX.MCP_HAZIR_SN = eski_sn
    sina("hic hazir olmayan sunucu: sure dolunca tur BASLADI",
         bool(istekler(gelen, "turn/start")) and ek.get("basarili") is True)
    sina("gecikme GORUNUR (hata olayi)",
         any(o.tur == "hata" and (o.ek or {}).get("sebep") == "mcp_gecikti" for o in ol))
    ol, ek, gelen = kos("mcpsiz", [{"bitir": "completed"}])
    sina("MCP yoksa beklemeden baslar", ek.get("basarili") is True)

    # ------------------------------------------------------------ 11c
    print("\n11c. TUR ICI KANAL (E17): not steer ile, durdurma interrupt ile")
    from ofis.motor.tip import TurKanali
    kn = TurKanali()
    kn.gonder("n1", "PATRONUN NOTU: b.txt de yaz")   # tur BASLAMADAN once kanalda
    ol, ek, gelen = kos("kanal_not", [{"asili": True}], kanal=kn,
                        steer_sonra_bitir=True)
    st = istekler(gelen, "turn/steer")
    adlar = [g.get("method") for g in gelen]
    sina("not turn/steer ile GITTI", len(st) == 1
         and "b.txt" in json.dumps(st[0], ensure_ascii=False), str(st)[:160])
    sina("steer tur BASLADIKTAN sonra (turn/start'tan once degil)",
         "turn/start" in adlar and "turn/steer" in adlar
         and adlar.index("turn/start") < adlar.index("turn/steer"))
    sina("steer dogru tura (expectedTurnId)",
         bool(st) and st[0]["params"].get("expectedTurnId") == "tur-1")
    mes = [o for o in ol if o.tur == "mesaj"]
    sina("kabul edilen steer -> 'mesaj' olayi (ulasti)",
         len(mes) == 1 and mes[0].ek.get("kimlik") == "n1", str([o.tur for o in ol]))
    sina("tur basarili bitti", ek.get("basarili") is True)

    kn = TurKanali()
    kn.gonder("n2", "reddedilecek not")
    ol, ek, gelen = kos("kanal_red", [{"asili": True}], kanal=kn, steer_red=True,
                        zaman_asimi=4)
    sina("REDDEDILEN steer ulasti SAYILMAZ", not any(o.tur == "mesaj" for o in ol))

    kn = TurKanali()
    kn.durdur()
    ol, ek, gelen = kos("kanal_dur", [{"asili": True}], kanal=kn)
    sina("durdurma turn/interrupt GONDERDI", len(istekler(gelen, "turn/interrupt")) == 1)
    sina("durdurulan tur: basarisiz, sebep 'durduruldu' (zaman asimi DEGIL)",
         ek.get("basarili") is False and ek.get("sebep") == "durduruldu"
         and ek.get("zaman_asimi") is False, str(ek)[:160])
    sina("durdurma GORUNUR (hata olayi)",
         any(o.tur == "hata" and (o.ek or {}).get("sebep") == "durduruldu" for o in ol))

    # ------------------------------------------------------------ 12
    print("\n12. SOZLESME: exec kipi kancayi reddeder, bozuk kanca adi reddedilir")
    try:
        list(CX.CodexMotoru(calistirilabilir=str(sahte_cmd), kip="exec").tur_kos(
            "x", klasor=str(klasor), izin_araci="mcp__ofis__izin_sor"))
        sina("exec kipi kancayi REDDEDIYOR", False, "-- kabul etti")
    except CX.MotorHatasi as exc:
        sina("exec kipi kancayi REDDEDIYOR", "kanca" in str(exc).lower())
    try:
        list(CX.CodexMotoru(calistirilabilir=str(sahte_cmd)).tur_kos(
            "x", klasor=str(klasor), izin_araci="izin_sor"))
        sina("bozuk kanca adi REDDEDILIYOR", False, "-- kabul etti")
    except CX.MotorHatasi as exc:
        sina("bozuk kanca adi REDDEDILIYOR", "mcp__" in str(exc))
    k = CX.CodexMotoru(calistirilabilir="codex")._app_komutu(
        ek_klasorler=("C:/a",), mcp_yapilandirma="")
    sina("app komutu --strict-config tasiyor", "--strict-config" in k and k[1] == "app-server")
    sina("ek klasor yazilabilir kok olarak", any("writable_roots" in x for x in k))
finally:
    import shutil
    shutil.rmtree(ANA, ignore_errors=True)

print(f"\n== sonuc: {GECEN} gecti, {KALAN} kaldi ==")
sys.exit(1 if KALAN else 0)
