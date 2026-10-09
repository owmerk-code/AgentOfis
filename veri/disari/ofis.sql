BEGIN TRANSACTION;
CREATE TABLE ajan (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    kanat_id        TEXT REFERENCES kanat(id),
    ad              TEXT NOT NULL,              -- kebab-case, adres ve kimlik
    meslek          TEXT NOT NULL,              -- lider | backend | arayuz | test | arastirma | metin ...
    lider_mi        INTEGER NOT NULL DEFAULT 0,

    -- Motor katmani FISE TAKILIR: bugun 11 motor var, yarin baskalari olacak.
    -- Cekirdek motoru bilmez, sadece adaptor adini bilir.
    motor           TEXT NOT NULL DEFAULT 'claude',   -- claude | codex | opencode | api
    model           TEXT NOT NULL DEFAULT '',
    efor            TEXT NOT NULL DEFAULT 'normal',   -- dusuk | normal | yuksek

    -- 'eller' komut calistirir, dosya yazar (ajanik CLI sart).
    -- 'kafa' yalnizca dusunup metin uretir (ucuz API yeter).
    -- Bu ayrim maliyet icin degil SORUMLULUK icindir: kafa yazamaz.
    tur             TEXT NOT NULL DEFAULT 'eller',    -- eller | kafa

    klasor          TEXT NOT NULL DEFAULT '',   -- kendi calisma alani
    oturum_id       TEXT NOT NULL DEFAULT '',   -- motorun oturum kimligi (resume)
    faz             TEXT NOT NULL DEFAULT 'kuruluyor',  -- kuruluyor | aktif | basarisiz
    revizyon        INTEGER NOT NULL DEFAULT 1,
    olusturuldu     TEXT NOT NULL,
    guncellendi     TEXT NOT NULL, arsiv INTEGER NOT NULL DEFAULT 0, karakter TEXT NOT NULL DEFAULT '',
    UNIQUE (proje_id, ad)
);
INSERT INTO "ajan" VALUES('99a0808d801f4b32a5515ed6291ae78d','915d303e41ee4cb59fa908401d277926','7007669f4abc4c4386d77d1fa2606c19','arda','lider',1,'claude','opus','normal','eller','C:\Users\pc\Desktop\genel-agentofis','','kuruluyor',1,'2026-10-05T20:12:20+00:00','2026-10-05T20:12:20+00:00',0,'1:0:0');
CREATE TABLE ayar (
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    anahtar         TEXT NOT NULL,
    deger           TEXT NOT NULL DEFAULT '',
    guncellendi     TEXT NOT NULL,
    PRIMARY KEY (proje_id, anahtar)
);
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:takma_ad:opus','claude-opus-5-5','2026-09-22T23:02:36+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:takma_ad:sonnet','claude-sonnet-5-5','2026-09-28T22:15:42+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:takma_ad:haiku','claude-haiku-5-5','2026-10-08T04:18:52+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:bekleyen','[]','2026-10-08T14:31:25+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:son_kontrol','2026-10-08T14:31:25.522904+00:00','2026-10-08T14:31:25+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','efor_modu','normal','2026-09-24T02:07:37+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:cli:codex:0.156.0','onay','2026-09-23T00:13:11+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','kademe:codex:guclu','gpt-6.1-sol','2026-09-29T22:16:32+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:model:codex:gpt-5.6-sol->gpt-6-sol','onay','2026-09-23T00:21:41+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','kademe:codex:hizli','gpt-6-luna','2026-09-23T00:21:44+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:model:codex:gpt-5.6-luna->gpt-6-luna','onay','2026-09-23T00:21:44+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','kademe:codex:standart','gpt-6.1-sol','2026-09-29T22:16:32+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:cli:gemini:0.60.0','onay','2026-09-24T01:36:44+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','limit_canli_son','1791530411.4661348','2026-10-09T07:20:11+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','limit_canli:claude:','{"motor": "claude", "hesap": "", "olculdu": "2026-10-09T07:20:14+00:00", "limit_pencere": {"kaynak": "claude CLI (get_usage, tur yok)", "hal": "", "plan": "max", "pencereler": {"5s": {"kullanim": 0.12, "yenilenme": 1791545999}, "7g": {"kullanim": 0.21, "yenilenme": 1791946799}, "7g_kapi": {"kullanim": 0.0, "yenilenme": 1791946800}}}}','2026-10-09T07:20:14+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','limit_canli:codex:','{"motor": "codex", "hesap": "", "olculdu": "2026-10-09T07:20:17+00:00", "limit_pencere": {"kaynak": "codex app-server (account/rateLimits)", "hal": "", "plan": "plus", "pencereler": {"5s": {"kullanim": 0.0, "yenilenme": 1791548417}, "7g": {"kullanim": 0.03, "yenilenme": 1792015336}}}}','2026-10-09T07:20:17+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:cli:claude:2.1.284','otomatik','2026-09-28T22:15:11+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:gecmis','[{"tur": "cli", "motor": "claude", "paket": "@anthropic-ai/claude-code", "eski": "2.1.282", "yeni": "2.1.284", "anahtar": "cli:claude:2.1.284", "veren": "ofis", "deneme": "OK", "sira": 1, "zaman": "2026-09-28T22:15:11.610387+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "cli", "motor": "codex", "paket": "@openai/codex", "eski": "0.156.0", "yeni": "0.158.0", "anahtar": "cli:codex:0.158.0", "veren": "ofis", "deneme": "OK", "sira": 2, "zaman": "2026-09-28T22:15:29.639707+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "takma_ad", "motor": "claude", "ad": "sonnet", "eski": "claude-sonnet-5", "yeni": "claude-sonnet-5-5", "anahtar": "takma_ad:sonnet:claude-sonnet-5-5", "veren": "ofis", "deneme": "OK", "sira": 3, "zaman": "2026-09-28T22:15:43.569258+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "cli", "motor": "codex", "paket": "@openai/codex", "eski": "0.156.0", "yeni": "0.158.0", "anahtar": "cli:codex:0.158.0", "veren": "ofis", "deneme": "OK", "sira": 4, "zaman": "2026-09-28T22:15:47.019645+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "cli", "motor": "claude", "paket": "@anthropic-ai/claude-code", "eski": "2.1.284", "yeni": "2.1.285", "anahtar": "cli:claude:2.1.285", "veren": "ofis", "deneme": "OK", "sira": 5, "zaman": "2026-09-29T22:14:37.706093+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "cli", "motor": "codex", "paket": "@openai/codex", "eski": "0.158.0", "yeni": "0.159.1", "anahtar": "cli:codex:0.159.1", "veren": "ofis", "deneme": "OK", "sira": 6, "zaman": "2026-09-29T22:14:48.183813+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "model", "motor": "codex", "eski": "gpt-6-sol", "yeni": "gpt-6.1-sol", "eski_kademe": {"standart": "gpt-6-sol", "guclu": "gpt-6-sol"}, "ajanlar": ["cinar"], "anahtar": "model:codex:gpt-6-sol->gpt-6.1-sol", "veren": "ofis", "deneme": "OK", "sira": 7, "zaman": "2026-09-29T22:16:32.169169+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "cli", "motor": "codex", "paket": "@openai/codex", "eski": "0.159.1", "yeni": "0.159.2", "anahtar": "cli:codex:0.159.2", "veren": "ofis", "deneme": "OK", "sira": 8, "zaman": "2026-09-30T00:19:22.541637+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "cli", "motor": "codex", "paket": "@openai/codex", "eski": "0.159.2", "yeni": "0.159.3", "anahtar": "cli:codex:0.159.3", "veren": "ofis", "deneme": "OK", "sira": 9, "zaman": "2026-10-01T12:21:12.536851+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "cli", "motor": "claude", "paket": "@anthropic-ai/claude-code", "eski": "2.1.285", "yeni": "2.1.286", "anahtar": "cli:claude:2.1.286", "veren": "insan", "deneme": "OK", "sira": 10, "zaman": "2026-10-01T13:22:58.133009+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "cli", "motor": "claude", "paket": "@anthropic-ai/claude-code", "eski": "2.1.286", "yeni": "2.1.287", "anahtar": "cli:claude:2.1.287", "veren": "ofis", "deneme": "OK", "sira": 11, "zaman": "2026-10-01T18:28:27.369238+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "cli", "motor": "codex", "paket": "@openai/codex", "eski": "0.159.3", "yeni": "0.160.0", "anahtar": "cli:codex:0.160.0", "veren": "ofis", "deneme": "OK", "sira": 12, "zaman": "2026-10-01T21:09:54.666021+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "cli", "motor": "claude", "paket": "@anthropic-ai/claude-code", "eski": "2.1.287", "yeni": "2.1.289", "anahtar": "cli:claude:2.1.289", "veren": "insan", "deneme": "OK", "sira": 13, "zaman": "2026-10-05T12:27:19.912529+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "cli", "motor": "claude", "paket": "@anthropic-ai/claude-code", "eski": "2.1.287", "yeni": "2.1.289", "anahtar": "cli:claude:2.1.289", "veren": "insan", "deneme": "OK", "sira": 14, "zaman": "2026-10-05T12:27:43.835953+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "cli", "motor": "codex", "paket": "@openai/codex", "eski": "0.160.0", "yeni": "0.160.1", "anahtar": "cli:codex:0.160.1", "veren": "ofis", "deneme": "OK", "sira": 15, "zaman": "2026-10-05T19:30:05.126505+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "cli", "motor": "claude", "paket": "@anthropic-ai/claude-code", "eski": "2.1.289", "yeni": "2.1.291", "anahtar": "cli:claude:2.1.291", "veren": "ofis", "deneme": "OK", "sira": 16, "zaman": "2026-10-06T14:52:23.417639+00:00", "durum": "uygulandi", "goruldu": true}, {"tur": "takma_ad", "motor": "claude", "ad": "haiku", "eski": "claude-haiku-4-5-20251001", "yeni": "claude-haiku-5-5", "anahtar": "takma_ad:haiku:claude-haiku-5-5", "veren": "ofis", "deneme": "OK", "sira": 17, "zaman": "2026-10-08T04:18:52.895565+00:00", "durum": "uygulandi", "goruldu": true}]','2026-10-08T05:04:45+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:cli:codex:0.158.0','otomatik','2026-09-28T22:15:46+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:takma_ad:sonnet:claude-sonnet-5-5','otomatik','2026-09-28T22:15:42+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','terminal_kipi','gercek','2026-10-05T13:26:26+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','durdur_istegi','','2026-10-01T12:14:04+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:cli:claude:2.1.285','otomatik','2026-09-29T22:14:37+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:cli:codex:0.159.1','otomatik','2026-09-29T22:14:48+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:model:codex:gpt-6-sol->gpt-6.1-sol','otomatik','2026-09-29T22:16:32+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','kabin_izle','acik','2026-09-29T23:04:50+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:cli:codex:0.159.2','otomatik','2026-09-30T00:19:22+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:otomatik_dustu:cli:claude:2.1.286','2.1.286 denemeyi gecemedi, 2.1.285 surumune geri donuldu (olculen: 2.1.285). Sebep: GERCEK TERMINAL denemesi dustu: Brifing terminale yapistirildi ama GONDERILMEDI (oturum dosyasi buyumedi). Ekranin sonu: ──────────────────────────────────────────────────────────────────────────────────────────
Acce','2026-10-01T12:20:45+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:cli:codex:0.159.3','otomatik','2026-10-01T12:21:12+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:cli:claude:2.1.286','onay','2026-10-01T13:22:58+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:cli:claude:2.1.287','otomatik','2026-10-01T18:28:27+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:cli:codex:0.160.0','otomatik','2026-10-01T21:09:54+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:otomatik_dustu:cli:claude:2.1.289','2.1.289 denemeyi gecemedi, 2.1.287 surumune geri donuldu (olculen: 2.1.287). Sebep: GERCEK TERMINAL denemesi dustu: Brifing terminale yapistirildi ama GONDERILMEDI (oturum dosyasi buyumedi). Ekranin sonu: 
──────────────────────────────────────────────────────────────────────────────────────────────','2026-10-04T15:40:54+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:cli:claude:2.1.289','onay','2026-10-05T12:27:43+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','lider_terminal_kipi','gercek','2026-10-05T13:26:09+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:yeni_model:claude:claude-haiku-4-5-20251001','ret: gerek yok','2026-10-05T19:28:58+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:cli:codex:0.160.1','otomatik','2026-10-05T19:30:05+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:cli:claude:2.1.291','otomatik','2026-10-06T14:52:23+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:takma_ad:haiku:claude-haiku-5-5','otomatik','2026-10-08T04:18:52+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','guncelleme:karar:yeni_model:claude:claude-haiku-5-5','ret: gerek yok','2026-10-08T05:05:09+00:00');
INSERT INTO "ayar" VALUES('915d303e41ee4cb59fa908401d277926','limit_canli:gemini:','{"motor": "gemini", "hesap": "", "olculdu": "2026-10-09T07:20:21+00:00", "limit_pencere": {"kaynak": "agy /usage (tur yok)", "hal": "", "plan": "", "pencereler": {"7g": {"kullanim": 0.154, "yenilenme": 1791667766}, "5s": {"kullanim": 0.0, "yenilenme": 1791548421}}}}','2026-10-09T07:20:21+00:00');
CREATE TABLE belge (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    ad              TEXT NOT NULL,
    yol             TEXT NOT NULL,
    ozet            TEXT NOT NULL,
    tur             TEXT NOT NULL,
    boyut           INTEGER NOT NULL DEFAULT 0,
    parca           INTEGER NOT NULL DEFAULT 0,
    ekleyen         TEXT NOT NULL DEFAULT 'insan',
    olusturuldu     TEXT NOT NULL,
    kaldirildi      TEXT
, kanat_id TEXT NOT NULL DEFAULT '');
CREATE TABLE belge_parca (
    belge_id        TEXT NOT NULL REFERENCES belge(id),
    sira            INTEGER NOT NULL,
    yer             TEXT NOT NULL,
    metin           TEXT NOT NULL,
    PRIMARY KEY (belge_id, sira)
);
CREATE TABLE brifing (
    id              TEXT PRIMARY KEY,
    gorev_id        TEXT NOT NULL REFERENCES gorev(id),
    ajan_ad         TEXT NOT NULL,
    metin           TEXT NOT NULL,
    jeton_tahmini   INTEGER NOT NULL DEFAULT 0,
    olusturuldu     TEXT NOT NULL
);
CREATE TABLE canli_degisim (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL,
    gorev_id        TEXT NOT NULL,
    ajan_ad         TEXT NOT NULL DEFAULT '',
    yol             TEXT NOT NULL,
    hal             TEXT NOT NULL,
    beyan_disi      INTEGER NOT NULL DEFAULT 0,
    eklenen         INTEGER NOT NULL DEFAULT 0,
    silinen         INTEGER NOT NULL DEFAULT 0,
    yama            TEXT NOT NULL DEFAULT '',
    olculemedi      TEXT NOT NULL DEFAULT '',
    atif_belirsiz   INTEGER NOT NULL DEFAULT 0,
    guncellendi     TEXT NOT NULL,
    damga           INTEGER NOT NULL DEFAULT 0,
    UNIQUE (gorev_id, yol)
);
CREATE TABLE cihaz (
    id              TEXT PRIMARY KEY,
    ad              TEXT NOT NULL,
    anahtar_ozet    TEXT NOT NULL,
    olusturuldu     TEXT NOT NULL,
    son_gorulme     TEXT NOT NULL,
    push_abonelik   TEXT NOT NULL DEFAULT '',
    kaldirildi      TEXT
);
CREATE TABLE degisim (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL,
    gorev_id        TEXT,
    ajan_ad         TEXT NOT NULL DEFAULT '',
    yol             TEXT NOT NULL,              -- KOK-GORELI, '/' ayracli
    hal             TEXT NOT NULL,              -- eklendi | degisti | silindi
    beyan_disi      INTEGER NOT NULL DEFAULT 0,
    eklenen         INTEGER NOT NULL DEFAULT 0,
    silinen         INTEGER NOT NULL DEFAULT 0,
    yama            TEXT NOT NULL DEFAULT '',
    olculemedi      TEXT NOT NULL DEFAULT '',
    atif_belirsiz   INTEGER NOT NULL DEFAULT 0,
    olusturuldu     TEXT NOT NULL
);
CREATE TABLE ders (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    ajan_ad         TEXT NOT NULL,
    ders            TEXT NOT NULL,
    sebep_gorev_id  TEXT REFERENCES gorev(id),
    tekrar          INTEGER NOT NULL DEFAULT 1, -- kac kez ayni hata
    olusturuldu     TEXT NOT NULL,
    guncellendi     TEXT NOT NULL
, kaldirildi TEXT NOT NULL DEFAULT '');
CREATE TABLE ekip_onerisi (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    no              INTEGER NOT NULL,           -- insanin gordugu numara
    kanat_id        TEXT REFERENCES kanat(id),
    hedef           TEXT NOT NULL,              -- hangi istek bunu dogurdu
    gerekce         TEXT NOT NULL,              -- lider NICIN boyle onerdi
    uyeler          TEXT NOT NULL DEFAULT '[]', -- JSON: [{ad, rol, motor, model, gerekce}]
    oneren          TEXT NOT NULL DEFAULT '',   -- lider adi
    durum           TEXT NOT NULL DEFAULT 'bekliyor',  -- bekliyor | kuruldu | reddedildi
    sebep           TEXT NOT NULL DEFAULT '',   -- RET gerekcesi (zorunlu)
    olusturuldu     TEXT NOT NULL,
    karar_verildi   TEXT, patron_mesaji TEXT NOT NULL DEFAULT '',
    UNIQUE (proje_id, no)
);
CREATE TABLE gorev (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    kanat_id        TEXT REFERENCES kanat(id),
    no              INTEGER NOT NULL,           -- insan tarafindan okunan numara
    baslik          TEXT NOT NULL,
    govde           TEXT NOT NULL DEFAULT '',
    neden           TEXT NOT NULL,              -- bu is NICIN var
    ana_hedef       TEXT NOT NULL,              -- bagli oldugu ust hedef (senin cumlen)
    kabul_olcutu    TEXT NOT NULL,              -- bittigini nasil kanitlayacak
    yazma_alani     TEXT NOT NULL DEFAULT '[]', -- JSON dizi: ["api/", "db/"]
    sahip           TEXT NOT NULL DEFAULT '',   -- ajan.ad
    durum           TEXT NOT NULL DEFAULT 'bekliyor',
                    -- bekliyor | hazir | calisiyor | inceleme | bitti | iptal
    oncelik         TEXT NOT NULL DEFAULT 'normal',  -- dusuk | normal | yuksek
    revizyon        INTEGER NOT NULL DEFAULT 1,
    silindi         INTEGER NOT NULL DEFAULT 0, -- mezar tasi: gorunmez ama gecmis okunur
    olusturuldu     TEXT NOT NULL,
    guncellendi     TEXT NOT NULL, ek_klasorler TEXT NOT NULL DEFAULT '[]', zorluk TEXT NOT NULL DEFAULT '', zorluk_gerekce TEXT NOT NULL DEFAULT '', tarayici_alani TEXT NOT NULL DEFAULT '[]', baglayicilar TEXT NOT NULL DEFAULT '[]', tarayici_yazma INTEGER NOT NULL DEFAULT 0, tarayici_kabin INTEGER NOT NULL DEFAULT 0, kosan_surec TEXT NOT NULL DEFAULT '', istek_id TEXT NOT NULL DEFAULT '', duraklatildi TEXT NOT NULL DEFAULT '', motor_secimi TEXT NOT NULL DEFAULT '', patron_modeli TEXT NOT NULL DEFAULT '',
    UNIQUE (proje_id, no)
);
CREATE TABLE gorev_bagimlilik (
    gorev_id        TEXT NOT NULL REFERENCES gorev(id),
    bagli_oldugu    TEXT NOT NULL REFERENCES gorev(id),
    PRIMARY KEY (gorev_id, bagli_oldugu)
);
CREATE TABLE hafiza_onerisi (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    konu            TEXT NOT NULL,
    icerik          TEXT NOT NULL,
    alinti          TEXT NOT NULL,
    oneren          TEXT NOT NULL,
    durum           TEXT NOT NULL DEFAULT 'bekliyor',   -- bekliyor | yazildi | reddedildi
    olusturuldu     TEXT NOT NULL,
    cevaplandi      TEXT
, kanat_id TEXT NOT NULL DEFAULT '');
CREATE TABLE hesap (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    ad              TEXT NOT NULL,              -- 'claude-max', 'codex-is', 'api-1'
    motor           TEXT NOT NULL,              -- claude | codex | ...
    tur             TEXT NOT NULL DEFAULT 'abonelik',  -- abonelik | api
    plan            TEXT NOT NULL DEFAULT '',   -- max5 | max20 | plus | pro200 ...
    ortam           TEXT NOT NULL DEFAULT '{}', -- JSON: env; anahtar DEGIL referans
    sira            INTEGER NOT NULL DEFAULT 100,  -- nobet zincirindeki sira
    aktif           INTEGER NOT NULL DEFAULT 1, -- limit dolunca kapatilabilir
    not_            TEXT NOT NULL DEFAULT '',
    olusturuldu     TEXT NOT NULL,
    guncellendi     TEXT NOT NULL, aylik_sinir_usd REAL,
    UNIQUE (proje_id, ad)
);
INSERT INTO "hesap" VALUES('326f65fe07eb4e0bbbf4424314b5c1f9','915d303e41ee4cb59fa908401d277926','claude','claude','abonelik','max5','{}',10,1,'Claude Max 5x (bu makinenin oturumu)','2026-09-22T20:32:56+00:00','2026-09-22T20:32:56+00:00',NULL);
INSERT INTO "hesap" VALUES('2b20be28d5554962924bf2b24b01efac','915d303e41ee4cb59fa908401d277926','codex','codex','abonelik','plus','{}',20,1,'GPT Plus 1 - omerjob34 (ofisin kendi evi)','2026-09-22T20:32:56+00:00','2026-09-22T20:32:56+00:00',NULL);
INSERT INTO "hesap" VALUES('809249320dfe49bb8c8220f155df0b50','915d303e41ee4cb59fa908401d277926','codex2','codex','abonelik','plus','{"CODEX_HOME": "~/.agentofis/codex2"}',21,0,'GPT Plus 2 - trader bot hesabi, kullanici izin verdi 22.09.2026','2026-09-22T20:32:57+00:00','2026-09-28T22:25:00+00:00',NULL);
INSERT INTO "hesap" VALUES('4dc6b119d92b42028eba931bb40fd6f8','915d303e41ee4cb59fa908401d277926','gemini','gemini','abonelik','','{}',30,1,'Gemini (kasadaki anahtar)','2026-09-22T20:32:57+00:00','2026-10-08T03:52:09+00:00',NULL);
CREATE TABLE izin (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    gorev_id        TEXT REFERENCES gorev(id),
    sinif           TEXT NOT NULL,
    desen           TEXT NOT NULL,
    alinti          TEXT NOT NULL DEFAULT '',
    kaynak          TEXT NOT NULL,                  -- patron_sozu | insan
    gerekce         TEXT NOT NULL DEFAULT '',
    veren           TEXT NOT NULL,
    olusturuldu     TEXT NOT NULL,
    kaldirildi      TEXT,
    kaldirma_sebebi TEXT NOT NULL DEFAULT ''
);
CREATE TABLE kanat (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    ad              TEXT NOT NULL,
    onek            TEXT NOT NULL,              -- gorev numarasi oneki: UR, PZ, DS
    renk            TEXT NOT NULL DEFAULT '#E0785A',
    olusturuldu     TEXT NOT NULL, klasor TEXT NOT NULL DEFAULT '', kota_payi INTEGER NOT NULL DEFAULT 0, bitti_tanimi TEXT NOT NULL DEFAULT '', marka_kiti TEXT NOT NULL DEFAULT '', canli INTEGER NOT NULL DEFAULT 0,
    UNIQUE (proje_id, ad)
);
INSERT INTO "kanat" VALUES('7007669f4abc4c4386d77d1fa2606c19','915d303e41ee4cb59fa908401d277926','GENEL','GE','#e0785a','2026-10-05T20:12:20+00:00','C:\Users\pc\Desktop\genel-agentofis',0,'','{"logo": "", "renkler": "", "ses_tonu": "", "yasak": []}',0);
CREATE TABLE kanit (
    id              TEXT PRIMARY KEY,
    gorev_id        TEXT NOT NULL REFERENCES gorev(id),
    tur             TEXT NOT NULL,              -- terminal | diff | gorsel | dosya | baglanti
    baslik          TEXT NOT NULL,
    icerik          TEXT NOT NULL DEFAULT '',   -- kisa cikti ya da dosya yolu
    ekleyen         TEXT NOT NULL,
    olusturuldu     TEXT NOT NULL
);
CREATE TABLE karar (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    gorev_id        TEXT REFERENCES gorev(id),
    tur             TEXT NOT NULL DEFAULT 'genel',
                    -- genel | dagitim | ret | teknik | kapsam
    karar           TEXT NOT NULL,
    gerekce         TEXT NOT NULL,              -- bos birakilamaz
    veren           TEXT NOT NULL,              -- ajan.ad ya da 'insan'
    etkilenen_yollar TEXT NOT NULL DEFAULT '[]',
    olusturuldu     TEXT NOT NULL
, kanat_id TEXT NOT NULL DEFAULT '');
INSERT INTO "karar" VALUES('4a4a6839e30e4ee0b83e8fb92c485f41','915d303e41ee4cb59fa908401d277926',NULL,'guncelleme','`haiku` takma adi artik claude-haiku-5-5 (once claude-haiku-4-5-20251001). Onay: kabul et. Ret: kademeyi eskisine SABITLE.','OTOMATIK (ofis); deneme turu gecti (''OK''). `haiku` kullanan her ajan ve kademe artik claude-haiku-5-5.','ofis','[]','2026-10-08T04:18:52+00:00','');
INSERT INTO "karar" VALUES('e2bc06ecff204e02a08380431f6ec9d7','915d303e41ee4cb59fa908401d277926',NULL,'guncelleme','REDDEDILDI: claude: yeni model claude-haiku-5-5 (Haiku 5.5) -- hicbir kademede yok. Onaylarken HANGI kademeye girecegini sec.','gerek yok','insan','[]','2026-10-08T05:05:09+00:00','');
CREATE TABLE konu_takma (
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    takma_anahtar   TEXT NOT NULL,
    asil            TEXT NOT NULL,
    veren           TEXT NOT NULL,
    olusturuldu     TEXT NOT NULL,
    PRIMARY KEY (proje_id, takma_anahtar)
);
CREATE TABLE kural (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    metin           TEXT NOT NULL,
    kaynak_tur      TEXT NOT NULL DEFAULT 'insan',   -- insan | olgu | ders
    kaynak          TEXT NOT NULL DEFAULT '',
    gerekce         TEXT NOT NULL,
    veren           TEXT NOT NULL,
    olusturuldu     TEXT NOT NULL,
    kaldirildi      TEXT,
    kaldirma_sebebi TEXT NOT NULL DEFAULT ''
, kanat_id TEXT NOT NULL DEFAULT '');
CREATE TABLE kuyruk (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL,
    metin           TEXT NOT NULL,
    lider_ad        TEXT NOT NULL,
    atanan          TEXT NOT NULL DEFAULT '',
    tarayici_alani  TEXT NOT NULL DEFAULT '[]',
    kabin           INTEGER NOT NULL DEFAULT 0,
    kaynak          TEXT NOT NULL DEFAULT 'insan',
    durum           TEXT NOT NULL DEFAULT 'bekliyor',
    seri            TEXT NOT NULL DEFAULT '',
    kosan_surec     TEXT NOT NULL DEFAULT '',
    devam           INTEGER NOT NULL DEFAULT 0,
    gorev_sinir     INTEGER NOT NULL DEFAULT 0,
    not_            TEXT NOT NULL DEFAULT '',
    olusturuldu     TEXT NOT NULL,
    basladi         TEXT,
    bitti           TEXT
);
CREATE TABLE mesaj (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    gonderen        TEXT NOT NULL,
    alici           TEXT NOT NULL,              -- ajan.ad ya da 'insan'
    govde           TEXT NOT NULL,
    mod             TEXT NOT NULL DEFAULT 'sessiz',  -- sessiz | uyandiran | bekleyen
    gorev_id        TEXT REFERENCES gorev(id),
    cevap           TEXT NOT NULL DEFAULT '',
    cevaplandi      TEXT,
    okundu          INTEGER NOT NULL DEFAULT 0,
    olusturuldu     TEXT NOT NULL
, kabul TEXT NOT NULL DEFAULT '', kaynak TEXT NOT NULL DEFAULT '', secenekler TEXT NOT NULL DEFAULT '');
CREATE TABLE olay (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proje_id        TEXT NOT NULL,
    ajan_ad         TEXT NOT NULL DEFAULT '',
    gorev_id        TEXT,
    tur             TEXT NOT NULL,              -- gorev_acildi | sahiplenildi | cikti | kanit | kapandi ...
    govde           TEXT NOT NULL DEFAULT '',
    olusturuldu     TEXT NOT NULL
);
INSERT INTO "olay" VALUES(4533,'915d303e41ee4cb59fa908401d277926','insan',NULL,'sifirlandi','Defter sifirlama oncesi yedekten geri yuklendi (veri/ temizlenirken silinmisti); gecmis ve hafiza yeniden silindi, kadro/ayar/hesap korundu.','2026-10-08T01:12:45+00:00');
INSERT INTO "olay" VALUES(4534,'915d303e41ee4cb59fa908401d277926','',NULL,'guncelleme_var','`haiku` takma adi artik claude-haiku-5-5 (once claude-haiku-4-5-20251001). Onay: kabul et. Ret: kademeyi eskisine SABITLE.','2026-10-08T04:18:42+00:00');
INSERT INTO "olay" VALUES(4535,'915d303e41ee4cb59fa908401d277926','',NULL,'guncelleme_basladi','OTOMATIK: `haiku` takma adi artik claude-haiku-5-5 (once claude-haiku-4-5-20251001). Onay: kabul et. Ret: kademeyi eskisine SABITLE. -- deneme turu kosuyor','2026-10-08T04:18:42+00:00');
INSERT INTO "olay" VALUES(4536,'915d303e41ee4cb59fa908401d277926','',NULL,'tur_ozeti','{"jeton": 30187, "maliyet_usd": 0.003828825, "sure_ms": 10187.0, "model": "claude-haiku-5-5", "arac_sayisi": 0, "basarili": true, "jeton_dokumu": {"girdi": 2, "cikti": 148, "onbellek_okuma": 0, "onbellek_yazma": 30037, "onbellek_yazma_1sa": 0}, "baglam": {"dolu": 30042, "sinir": 1000000, "oran": 0.03}, "kip": null, "motor": "claude", "hesap": "", "yol": "guncelleme-deneme", "limit_pencere": {"kaynak": "claude CLI (rate_limit_event)", "hal": "allowed", "plan": "", "pencereler": {"5s": {"kullanim": 0.14, "yenilenme": 1791443400}, "7g": {"kullanim": 0.07, "yenilenme": 1791946800}}}}','2026-10-08T04:18:52+00:00');
INSERT INTO "olay" VALUES(4537,'915d303e41ee4cb59fa908401d277926','ofis',NULL,'karar','ofis: `haiku` takma adi artik claude-haiku-5-5 (once claude-haiku-4-5-20251001). Onay: kabul et. Ret: kademeyi eskisine SABITLE.','2026-10-08T04:18:52+00:00');
INSERT INTO "olay" VALUES(4538,'915d303e41ee4cb59fa908401d277926','',NULL,'guncelleme_uygulandi','#17 `haiku` claude-haiku-4-5-20251001 -> claude-haiku-5-5 (otomatik; deneme gecti)','2026-10-08T04:18:52+00:00');
INSERT INTO "olay" VALUES(4539,'915d303e41ee4cb59fa908401d277926','',NULL,'guncelleme_var','claude: yeni model claude-haiku-5-5 (Haiku 5.5) -- hicbir kademede yok. Onaylarken HANGI kademeye girecegini sec.','2026-10-08T04:18:55+00:00');
INSERT INTO "olay" VALUES(4540,'915d303e41ee4cb59fa908401d277926','insan',NULL,'karar','insan: REDDEDILDI: claude: yeni model claude-haiku-5-5 (Haiku 5.5) -- hicbir kademede yok. Onaylarken HANGI kademeye girecegini sec.','2026-10-08T05:05:09+00:00');
INSERT INTO "olay" VALUES(4541,'915d303e41ee4cb59fa908401d277926','',NULL,'kabin_dustu','Kabin Chrome''u kendiliginden kapandi (cikis 21). ine\connection_factory_impl.cc:484] ConnectionHandler failed with net error: -2
[17244:19288:1008/172044.209:ERROR:google_apis\gcm\engine\mcs_client.cc:750] Received close command, resetting connection.
--- kabin aciliyor 2026-10-08 17:33:58 kapi=9222
--- kabin aciliyor 2026-10-08 17:34:04 kapi=9222','2026-10-08T14:34:05+00:00');
INSERT INTO "olay" VALUES(4542,'915d303e41ee4cb59fa908401d277926','',NULL,'kabin_dustu','Kabin acilamadi: Tarayici profili baska bir Chrome''da acik (baska bir panelin tarayicisi ya da yeni kapanmis bir tarayici). O panelin tarayicisini kapat ya da biraz sonra yeniden dene. Ayrinti: Kabin Chrome''u acilirken kapandi (cikis 21). Son satirlar (C:\Users\pc\Desktop\AgentOfis\ev\kabin.log):
[17244:19288:1008/124543.189:ERROR:google_apis\gcm\engine\registration_request.cc:291] Registration response error message: QUOTA_EXCEEDED
[17244:19288:1008/142146.031:ERROR:google_apis\gcm\engine','2026-10-08T14:34:05+00:00');
INSERT INTO "olay" VALUES(4543,'915d303e41ee4cb59fa908401d277926','',NULL,'kabin_dustu','Kabin acilamadi: Tarayici profili baska bir Chrome''da acik (baska bir panelin tarayicisi ya da yeni kapanmis bir tarayici). O panelin tarayicisini kapat ya da biraz sonra yeniden dene. Ayrinti: Kabin Chrome''u acilirken kapandi (cikis 21). Son satirlar (C:\Users\pc\Desktop\AgentOfis\ev\kabin.log):
--- kabin aciliyor 2026-10-08 17:34:07 kapi=9222
--- kabin aciliyor 2026-10-08 17:34:08 kapi=9222
--- kabin aciliyor 2026-10-08 17:34:13 kapi=9222
--- kabin aciliyor 2026-10-08 17:34:14 kapi=9222','2026-10-08T14:34:14+00:00');
INSERT INTO "olay" VALUES(4544,'915d303e41ee4cb59fa908401d277926','',NULL,'kabin_dustu','Kabin acilamadi: Tarayici profili baska bir Chrome''da acik (baska bir panelin tarayicisi ya da yeni kapanmis bir tarayici). O panelin tarayicisini kapat ya da biraz sonra yeniden dene. Ayrinti: Kabin Chrome''u acilirken kapandi (cikis 21). Son satirlar (C:\Users\pc\Desktop\AgentOfis\ev\kabin.log):
--- kabin aciliyor 2026-10-08 17:34:07 kapi=9222
--- kabin aciliyor 2026-10-08 17:34:08 kapi=9222
--- kabin aciliyor 2026-10-08 17:34:13 kapi=9222
--- kabin aciliyor 2026-10-08 17:34:14 kapi=9222','2026-10-08T14:34:15+00:00');
INSERT INTO "olay" VALUES(4545,'915d303e41ee4cb59fa908401d277926','',NULL,'kabin_acildi','Kabin acildi (panel acti)','2026-10-08T14:35:14+00:00');
INSERT INTO "olay" VALUES(4546,'915d303e41ee4cb59fa908401d277926','',NULL,'kabin_kapandi','Kabin panelden kapatildi','2026-10-08T14:35:16+00:00');
INSERT INTO "olay" VALUES(4547,'915d303e41ee4cb59fa908401d277926','',NULL,'kabin_acildi','Kabin acildi (panel acti)','2026-10-08T14:38:00+00:00');
CREATE TABLE olgu (
    id                  TEXT PRIMARY KEY,
    proje_id            TEXT NOT NULL REFERENCES proje(id),
    konu                TEXT NOT NULL,          -- "iade suresi", "marka tonu"
    icerik              TEXT NOT NULL,
    kaynak              TEXT NOT NULL DEFAULT '',   -- kim/nereden
    gecerli_baslangic   TEXT NOT NULL,
    gecerli_bitis       TEXT,                   -- NULL = hala gecerli
    kaydedildi          TEXT NOT NULL,
    gecersiz_kilan      TEXT REFERENCES olgu(id)    -- hangi olgu bunu devirdi
, yanlis TEXT NOT NULL DEFAULT '', kanat_id TEXT NOT NULL DEFAULT '');
CREATE TABLE onay (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    gorev_id        TEXT REFERENCES gorev(id),
    isteyen         TEXT NOT NULL,
    eylem           TEXT NOT NULL,              -- insan diliyle ne yapacak
    ayrinti         TEXT NOT NULL DEFAULT '',   -- komut / istek govdesi
    risk            TEXT NOT NULL DEFAULT 'orta',   -- dusuk | orta | yuksek
    durum           TEXT NOT NULL DEFAULT 'bekliyor',  -- bekliyor | onaylandi | reddedildi
    cevap_notu      TEXT NOT NULL DEFAULT '',
    olusturuldu     TEXT NOT NULL,
    cevaplandi      TEXT
, kapsam TEXT NOT NULL DEFAULT 'eylem');
CREATE TABLE proje (
    id              TEXT PRIMARY KEY,
    ad              TEXT NOT NULL UNIQUE,
    amac            TEXT NOT NULL DEFAULT '',   -- ne yapiyoruz, kimin icin
    basari_olcutu   TEXT NOT NULL DEFAULT '',   -- bittigini nasil anlariz
    kapsam_disi     TEXT NOT NULL DEFAULT '',   -- ne YAPMIYORUZ (en cok atlanan alan)
    kisitlar        TEXT NOT NULL DEFAULT '',   -- teknik/marka kisitlari
    sozluk          TEXT NOT NULL DEFAULT '',   -- projeye ozel terimler
    kok_klasor      TEXT NOT NULL DEFAULT '',
    durum           TEXT NOT NULL DEFAULT 'acik',  -- acik | arsiv
    revizyon        INTEGER NOT NULL DEFAULT 1,
    olusturuldu     TEXT NOT NULL,
    guncellendi     TEXT NOT NULL
);
INSERT INTO "proje" VALUES('915d303e41ee4cb59fa908401d277926','Ofisim','Gunluk islerin buyuk kismini ajan ekibiyle yurutmek','Verilen hedef kanitla kapaniyor','','Yerel makine, Python 3.12, Turkce','','C:\Users\pc\Desktop\Ofisim','acik',1,'2026-09-18T17:01:47+00:00','2026-09-18T17:01:47+00:00');
CREATE TABLE teslim_puani (
    gorev_id        TEXT PRIMARY KEY REFERENCES gorev(id),
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    puan            INTEGER NOT NULL,
    gerekce         TEXT NOT NULL DEFAULT '',
    veren           TEXT NOT NULL DEFAULT 'insan',
    olusturuldu     TEXT NOT NULL
);
CREATE TABLE tur_anlik (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL,
    gorev_id        TEXT,
    ajan_ad         TEXT NOT NULL DEFAULT '',
    kok             TEXT NOT NULL,
    once            TEXT NOT NULL,
    sonra           TEXT NOT NULL,
    dosya           INTEGER NOT NULL DEFAULT 0,
    atif_belirsiz   INTEGER NOT NULL DEFAULT 0,
    not_            TEXT NOT NULL DEFAULT '',
    geri_alindi     TEXT NOT NULL DEFAULT '',
    olusturuldu     TEXT NOT NULL
);
CREATE TABLE yazma_kilidi (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL REFERENCES proje(id),
    yol_oneki       TEXT NOT NULL,              -- normalize edilmis: "api/orders"
    gorev_id        TEXT NOT NULL REFERENCES gorev(id),
    ajan_ad         TEXT NOT NULL,
    alindi          TEXT NOT NULL,
    -- Kira suresi: ajan olurse kilit sonsuza kadar kalmasin. Heartbeat
    -- gecmezse kilit dusar ve is yeniden sahiplenilebilir.
    son_nabiz       TEXT NOT NULL
);
CREATE TABLE zamanli (
    id              TEXT PRIMARY KEY,
    proje_id        TEXT NOT NULL,
    no              INTEGER NOT NULL,
    metin           TEXT NOT NULL,
    lider_ad        TEXT NOT NULL,
    kural           TEXT NOT NULL,
    sonraki         TEXT,
    etkin           INTEGER NOT NULL DEFAULT 1,
    son_calisma     TEXT,
    kaynak          TEXT NOT NULL DEFAULT 'insan',
    olusturuldu     TEXT NOT NULL
);
CREATE INDEX ix_kilit_yol ON yazma_kilidi (proje_id, yol_oneki);
CREATE INDEX ix_karar_proje ON karar (proje_id, olusturuldu DESC);
CREATE INDEX ix_olgu_konu ON olgu (proje_id, konu, gecerli_bitis);
CREATE INDEX ix_ders_ajan ON ders (proje_id, ajan_ad);
CREATE INDEX ix_mesaj_alici ON mesaj (proje_id, alici, okundu);
CREATE INDEX ix_olay_proje ON olay (proje_id, id DESC);
CREATE INDEX ix_degisim_proje
    ON degisim (proje_id, olusturuldu DESC);
CREATE INDEX ix_tur_anlik_proje
    ON tur_anlik (proje_id, olusturuldu DESC);
CREATE INDEX ix_kuyruk_durum ON kuyruk (proje_id, durum);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('olay',4547);
COMMIT;
PRAGMA user_version=2;
