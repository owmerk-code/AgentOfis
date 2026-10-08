import React from "react";
import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {Audio} from "@remotion/media";
import {TransitionSeries, linearTiming} from "@remotion/transitions";
import {fade} from "@remotion/transitions/fade";
import {slide} from "@remotion/transitions/slide";
import {wipe} from "@remotion/transitions/wipe";

/* AGENTOFIS KURGU SABLONU (06.10.2026, Asama 5).
   Tek genel bilesen: ajan bir PLAN yazar (sahneler, yazilar, gecis, muzik,
   altyazi, kapanis karti); ofis (ofis/kurgu.py) plani dogrular, dosyalari
   bir is klasorune kopyalar ve bunu cizdirir. Ajan Remotion kodu yazmaz:
   her iste ayni, sinanmis yol (kural yapi, rica degil).

   08.10.2026 (patron: "edit, montaj, sahne, ses birlestirme"): sahnede hiz,
   yerlesim (kapla / bulanik dolgu / sigdir) ve odak, renk filtresi; planda
   seslendirme/efekt izleri (sesler[]) ve konusurken muzigin kisilmasi,
   muzigin baslangici, yeni gecisler (kayma, silme, yukari), logo. */

export type Bicim = "9:16" | "4:5" | "1:1" | "16:9";

export type Sahne = {
  tur: "video" | "gorsel" | "renk";
  dosya?: string;          // public klasorune gore (ofis kopyalar)
  renk?: string;           // tur=renk icin arka plan
  sure: number;            // saniye (CIKTIDAKI sure)
  kirp_bas?: number;       // video: bastan kac saniye atlanir
  ses?: boolean;           // video: klibin kendi sesi (Flow/Veo) duyulsun mu
  hiz?: number;            // video: 0.25-4 (0.5 = agir cekim)
  yerlesim?: "kapla" | "bulanik" | "sigdir";  // orani tutmayan kaynak icin
  odak?: string;           // kapla'da kirpma merkezi: orta|sol|sag|ust|alt ya da "30% 50%"
  filtre?: "yok" | "sicak" | "soguk" | "siyah_beyaz" | "canli" | "sinematik";
  yazi?: string;
  yazi_konum?: "ust" | "orta" | "alt";
  hareket?: "yakinlas" | "uzaklas" | "yok";   // gorsel: yavas kamera
};

export type SesIzi = {
  dosya: string;           // seslendirme / efekt
  bas: number;             // videonun kacinci saniyesinde baslar
  sure: number;            // ofis olcer (ffprobe); kirp_bas sonrasi kalan
  ses?: number;            // 0-2 (varsayilan 1)
  kirp_bas?: number;
};

export type Logo = {
  dosya: string;
  konum?: "sag_ust" | "sol_ust" | "sag_alt" | "sol_alt" | "orta_ust" | "orta_alt";
  boyut?: number;          // ekran genisliginin orani (0.18)
  saydamlik?: number;      // 0-1 (0.9)
};

export type Plan = {
  bicim: Bicim;
  fps?: number;
  sahneler: Sahne[];
  gecis?: "kesme" | "solma" | "kayma" | "silme" | "yukari";
  gecis_sure?: number;
  muzik?: string | null;
  muzik_ses?: number;
  muzik_bas?: number;      // muzik dosyasinin kacinci saniyesinden
  muzik_alcalt?: number;   // ses izi calarken muzigin carpani (0.3)
  klip_ses?: number;
  sesler?: SesIzi[];
  logo?: Logo | null;
  altyazi?: {bas: number; son: number; metin: string}[];
  son_kart?: {metin: string; alt_metin?: string; sure: number; renk?: string} | null;
  yazi_renk?: string;
  yazi_tipi?: string;
};

export const boyut = (b: Bicim) =>
  b === "4:5" ? {width: 1080, height: 1350}
  : b === "1:1" ? {width: 1080, height: 1080}
  : b === "16:9" ? {width: 1920, height: 1080}
  : {width: 1080, height: 1920};

/* GUVENLI ALAN: Instagram'in dugmeleri/aciklamasi ekranin ustunu, altini ve
   (dikeyde) sagini kapatir; yazi oraya dusmesin. Oranlar ekranin yuzdesi. */
const guvenli = (b: Bicim) =>
  b === "9:16" ? {ust: 0.14, alt: 0.3, sol: 0.07, sag: 0.13}
  : b === "4:5" ? {ust: 0.08, alt: 0.1, sol: 0.07, sag: 0.07}
  : {ust: 0.07, alt: 0.07, sol: 0.07, sag: 0.07};

const kare = (sn: number, fps: number) => Math.max(1, Math.round(sn * fps));

const parcalar = (p: Plan) => {
  const s: {sure: number}[] = [...p.sahneler];
  if (p.son_kart) s.push({sure: p.son_kart.sure});
  return s;
};

export const gecisKare = (p: Plan, fps: number) =>
  p.gecis === "kesme" ? 0 : kare(p.gecis_sure ?? 0.4, fps);

export const toplamKare = (p: Plan, fps: number) => {
  const ps = parcalar(p);
  const g = gecisKare(p, fps);
  return ps.reduce((t, x) => t + kare(x.sure, fps), 0) - g * Math.max(0, ps.length - 1);
};

const ODAK: Record<string, string> = {
  orta: "50% 50%", sol: "0% 50%", sag: "100% 50%", ust: "50% 0%", alt: "50% 100%",
};
const odakCss = (o?: string) => (o ? ODAK[o] || o : "50% 50%");

const FILTRE: Record<string, string> = {
  yok: "none",
  sicak: "sepia(0.18) saturate(1.12) brightness(1.03)",
  soguk: "saturate(0.95) hue-rotate(-8deg) brightness(1.02)",
  siyah_beyaz: "grayscale(1) contrast(1.08)",
  canli: "saturate(1.3) contrast(1.06)",
  sinematik: "contrast(1.12) saturate(0.9) brightness(0.97)",
};

const sunum = (p: Plan) =>
  p.gecis === "kayma" ? slide({direction: "from-right"})
  : p.gecis === "yukari" ? slide({direction: "from-bottom"})
  : p.gecis === "silme" ? wipe({direction: "from-left"})
  : fade();

const Yazi: React.FC<{metin: string; konum: string; plan: Plan; buyuk?: boolean}> = ({
  metin, konum, plan, buyuk,
}) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const g = guvenli(plan.bicim);
  const gorun = interpolate(frame, [0, fps * 0.35], [0, 1], {extrapolateRight: "clamp"});
  const kay = interpolate(frame, [0, fps * 0.35], [height * 0.015, 0], {extrapolateRight: "clamp"});
  const dikey: React.CSSProperties =
    konum === "ust" ? {top: height * g.ust}
    : konum === "orta" ? {top: 0, bottom: 0, display: "flex", alignItems: "center"}
    : {bottom: height * g.alt};
  return (
    <div style={{position: "absolute", left: width * g.sol, right: width * g.sag, ...dikey}}>
      <div style={{
        width: "100%", textAlign: "center", color: plan.yazi_renk || "#FFFFFF",
        fontFamily: plan.yazi_tipi || "'Segoe UI', Arial, sans-serif", fontWeight: 700,
        fontSize: width * (buyuk ? 0.08 : 0.062), lineHeight: 1.18,
        textShadow: "0 2px 18px rgba(0,0,0,0.65), 0 1px 3px rgba(0,0,0,0.8)",
        opacity: gorun, transform: `translateY(${kay}px)`, whiteSpace: "pre-wrap",
      }}>
        {metin}
      </div>
    </div>
  );
};

/* Kaynagi cerceveye yerlestirir. BULANIK: orani tutmayan kaynak (16:9 klip
   9:16 videoda) kirpilmadan ortada, arkasi ayni goruntunun bulanik buyugu
   -- profesyonel dikey kurgunun standart cozumu. */
const Kaynak: React.FC<{s: Sahne; plan: Plan; olcek: number}> = ({s, plan, olcek}) => {
  const {fps} = useVideoConfig();
  const yer = s.yerlesim || "kapla";
  const filtre = FILTRE[s.filtre || "yok"] || "none";
  const ciz = (fit: "cover" | "contain", ek: React.CSSProperties, sessiz: boolean) => {
    const stil: React.CSSProperties = {
      width: "100%", height: "100%", objectFit: fit,
      objectPosition: fit === "cover" ? odakCss(s.odak) : "50% 50%", ...ek,
    };
    if (s.tur === "video") {
      const sesVar = (s.ses ?? !plan.muzik) && !sessiz;
      return (
        <OffthreadVideo
          src={staticFile(s.dosya!)}
          trimBefore={s.kirp_bas ? kare(s.kirp_bas, fps) : undefined}
          playbackRate={s.hiz ?? 1}
          muted={!sesVar}
          volume={plan.klip_ses ?? 1}
          style={stil}
        />
      );
    }
    return <Img src={staticFile(s.dosya!)} style={stil} />;
  };
  const hareket = {transform: `scale(${olcek})`, filter: filtre};
  if (yer === "kapla") return ciz("cover", hareket, false);
  return (
    <AbsoluteFill>
      {yer === "bulanik" ? (
        <AbsoluteFill style={{transform: "scale(1.15)", filter: `blur(40px) brightness(0.7) ${filtre === "none" ? "" : filtre}`}}>
          {ciz("cover", {}, true)}
        </AbsoluteFill>
      ) : null}
      <AbsoluteFill>{ciz("contain", hareket, false)}</AbsoluteFill>
    </AbsoluteFill>
  );
};

const SahneCiz: React.FC<{s: Sahne; plan: Plan; uzunluk: number}> = ({s, plan, uzunluk}) => {
  const frame = useCurrentFrame();
  let olcek = 1;
  if (s.tur === "gorsel") {
    const h = s.hareket ?? "yakinlas";
    olcek = h === "yok" ? 1
      : interpolate(frame, [0, uzunluk], h === "yakinlas" ? [1, 1.1] : [1.1, 1],
                    {extrapolateRight: "clamp"});
  }
  return (
    <AbsoluteFill style={{backgroundColor: s.renk || "#000000", overflow: "hidden"}}>
      {(s.tur === "video" || s.tur === "gorsel") && s.dosya ? <Kaynak s={s} plan={plan} olcek={olcek} /> : null}
      {s.yazi ? <Yazi metin={s.yazi} konum={s.yazi_konum || "alt"} plan={plan} /> : null}
    </AbsoluteFill>
  );
};

const SonKart: React.FC<{plan: Plan}> = ({plan}) => {
  const k = plan.son_kart!;
  const {height} = useVideoConfig();
  return (
    <AbsoluteFill style={{backgroundColor: k.renk || "#111111"}}>
      <Yazi metin={k.metin} konum="orta" plan={plan} buyuk />
      {k.alt_metin ? (
        <div style={{position: "absolute", left: 0, right: 0, top: height * 0.58}}>
          <Yazi metin={k.alt_metin} konum="ust" plan={{...plan, bicim: "1:1"}} />
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

const LogoCiz: React.FC<{plan: Plan}> = ({plan}) => {
  const {width, height} = useVideoConfig();
  const l = plan.logo!;
  const g = guvenli(plan.bicim);
  const k = l.konum || "sag_ust";
  const genislik = width * (l.boyut ?? 0.18);
  const stil: React.CSSProperties = {position: "absolute", width: genislik, opacity: l.saydamlik ?? 0.9};
  if (k.endsWith("ust")) stil.top = height * g.ust * 0.6; else stil.bottom = height * g.alt * 0.75;
  if (k.startsWith("sol")) stil.left = width * g.sol;
  else if (k.startsWith("sag")) stil.right = width * g.sag;
  else stil.left = (width - genislik) / 2;
  return <Img src={staticFile(l.dosya)} style={stil} />;
};

const Altyazi: React.FC<{plan: Plan}> = ({plan}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const sn = frame / fps;
  const a = (plan.altyazi || []).find((x) => sn >= x.bas && sn < x.son);
  if (!a) return null;
  const g = guvenli(plan.bicim);
  return (
    <div style={{position: "absolute", left: width * g.sol, right: width * g.sag,
                 bottom: height * (g.alt - 0.06), textAlign: "center"}}>
      <span style={{
        backgroundColor: "rgba(0,0,0,0.62)", color: "#FFFFFF", padding: "0.18em 0.45em",
        borderRadius: 10, fontSize: width * 0.042, fontWeight: 600, lineHeight: 1.5,
        fontFamily: plan.yazi_tipi || "'Segoe UI', Arial, sans-serif",
        boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone",
      }}>{a.metin}</span>
    </div>
  );
};

/* Ses izi calarken muzik `muzik_alcalt` carpanina iner; 0,3 sn'de yumusak
   gecer (ani kesik kulaga hata gibi gelir). */
export const muzikCarpani = (p: Plan, sn: number) => {
  const alt = p.muzik_alcalt ?? 0.3;
  const yum = 0.3;
  let c = 1;
  for (const s of p.sesler || []) {
    const b = s.bas, e = s.bas + s.sure;
    let v = 1;
    if (sn >= b && sn <= e) v = alt;
    else if (sn > b - yum && sn < b) v = 1 - (1 - alt) * (sn - (b - yum)) / yum;
    else if (sn > e && sn < e + yum) v = alt + (1 - alt) * (sn - e) / yum;
    c = Math.min(c, v);
  }
  return c;
};

export const Kurgu: React.FC<Plan> = (plan) => {
  const {fps, durationInFrames} = useVideoConfig();
  const frame = useCurrentFrame();
  const g = gecisKare(plan, fps);
  const ps = parcalar(plan);
  const ogeler: React.ReactNode[] = [];
  plan.sahneler.forEach((s, i) => {
    const uz = kare(s.sure, fps);
    ogeler.push(
      <TransitionSeries.Sequence key={`s${i}`} durationInFrames={uz}>
        <SahneCiz s={s} plan={plan} uzunluk={uz} />
      </TransitionSeries.Sequence>);
    if (g > 0 && i < ps.length - 1)
      ogeler.push(<TransitionSeries.Transition key={`g${i}`} presentation={sunum(plan)}
                    timing={linearTiming({durationInFrames: g})} />);
  });
  if (plan.son_kart)
    ogeler.push(
      <TransitionSeries.Sequence key="son" durationInFrames={kare(plan.son_kart.sure, fps)}>
        <SonKart plan={plan} />
      </TransitionSeries.Sequence>);
  const sonKartBas = plan.son_kart ? durationInFrames - kare(plan.son_kart.sure, fps) : durationInFrames;
  // Muzik sonda 1 sn'de kisilir (kesik bitis kulaga hata gibi gelir).
  const mses = (plan.muzik_ses ?? 0.8) * muzikCarpani(plan, frame / fps) * interpolate(
    frame, [durationInFrames - fps, durationInFrames], [1, 0],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  return (
    <AbsoluteFill style={{backgroundColor: "#000000"}}>
      <TransitionSeries>{ogeler}</TransitionSeries>
      {plan.logo && frame < sonKartBas ? <LogoCiz plan={plan} /> : null}
      <Altyazi plan={plan} />
      {plan.muzik ? (
        <Audio src={staticFile(plan.muzik)} volume={mses} loop
               trimBefore={plan.muzik_bas ? kare(plan.muzik_bas, fps) : undefined} />
      ) : null}
      {(plan.sesler || []).map((s, i) => (
        <Sequence key={`ses${i}`} from={kare(s.bas, fps)} durationInFrames={kare(s.sure, fps)}>
          <Audio src={staticFile(s.dosya)} volume={s.ses ?? 1}
                 trimBefore={s.kirp_bas ? kare(s.kirp_bas, fps) : undefined} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
