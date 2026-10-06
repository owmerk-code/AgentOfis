import React from "react";
import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {Audio} from "@remotion/media";
import {TransitionSeries, linearTiming} from "@remotion/transitions";
import {fade} from "@remotion/transitions/fade";

/* AGENTOFIS KURGU SABLONU (06.10.2026, Asama 5).
   Tek genel bilesen: ajan bir PLAN yazar (sahneler, yazilar, gecis, muzik,
   altyazi, kapanis karti); ofis (ofis/kurgu.py) plani dogrular, dosyalari
   bir is klasorune kopyalar ve bunu cizdirir. Ajan Remotion kodu yazmaz:
   her iste ayni, sinanmis yol (kural yapi, rica degil). */

export type Bicim = "9:16" | "4:5" | "1:1" | "16:9";

export type Sahne = {
  tur: "video" | "gorsel" | "renk";
  dosya?: string;          // public klasorune gore (ofis kopyalar)
  renk?: string;           // tur=renk icin arka plan
  sure: number;            // saniye
  kirp_bas?: number;       // video: bastan kac saniye atlanir
  ses?: boolean;           // video: klibin kendi sesi (Flow/Veo) duyulsun mu
  yazi?: string;
  yazi_konum?: "ust" | "orta" | "alt";
  hareket?: "yakinlas" | "uzaklas" | "yok";   // gorsel: yavas kamera
};

export type Plan = {
  bicim: Bicim;
  fps?: number;
  sahneler: Sahne[];
  gecis?: "kesme" | "solma";
  gecis_sure?: number;
  muzik?: string | null;
  muzik_ses?: number;
  klip_ses?: number;
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

const SahneCiz: React.FC<{s: Sahne; plan: Plan; uzunluk: number}> = ({s, plan, uzunluk}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const sesVar = s.ses ?? !plan.muzik;
  let icerik: React.ReactNode = null;
  if (s.tur === "video" && s.dosya) {
    icerik = (
      <OffthreadVideo
        src={staticFile(s.dosya)}
        trimBefore={s.kirp_bas ? kare(s.kirp_bas, fps) : undefined}
        muted={!sesVar}
        volume={plan.klip_ses ?? 1}
        style={{width: "100%", height: "100%", objectFit: "cover"}}
      />
    );
  } else if (s.tur === "gorsel" && s.dosya) {
    const h = s.hareket ?? "yakinlas";
    const olcek = h === "yok" ? 1
      : interpolate(frame, [0, uzunluk], h === "yakinlas" ? [1, 1.1] : [1.1, 1],
                    {extrapolateRight: "clamp"});
    icerik = (
      <Img src={staticFile(s.dosya)}
           style={{width: "100%", height: "100%", objectFit: "cover", transform: `scale(${olcek})`}} />
    );
  }
  return (
    <AbsoluteFill style={{backgroundColor: s.renk || "#000000", overflow: "hidden"}}>
      {icerik}
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
      ogeler.push(<TransitionSeries.Transition key={`g${i}`} presentation={fade()}
                    timing={linearTiming({durationInFrames: g})} />);
  });
  if (plan.son_kart)
    ogeler.push(
      <TransitionSeries.Sequence key="son" durationInFrames={kare(plan.son_kart.sure, fps)}>
        <SonKart plan={plan} />
      </TransitionSeries.Sequence>);
  // Muzik sonda 1 sn'de kisilir (kesik bitis kulaga hata gibi gelir).
  const mses = (plan.muzik_ses ?? 0.8) * interpolate(
    frame, [durationInFrames - fps, durationInFrames], [1, 0],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  return (
    <AbsoluteFill style={{backgroundColor: "#000000"}}>
      <TransitionSeries>{ogeler}</TransitionSeries>
      <Altyazi plan={plan} />
      {plan.muzik ? <Audio src={staticFile(plan.muzik)} volume={mses} loop /> : null}
    </AbsoluteFill>
  );
};
