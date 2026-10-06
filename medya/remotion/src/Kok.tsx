import React from "react";
import {CalculateMetadataFunction, Composition} from "remotion";
import {Kurgu, Plan, boyut, toplamKare} from "./Kurgu";

/* Varsayilan plan yalniz Studio onizlemesi icin; gercek plan `--props` ile
   gelir (ofis/kurgu.py). Sure ve boyut PLANDAN hesaplanir. */
const ornek: Plan = {
  bicim: "9:16",
  fps: 30,
  sahneler: [{tur: "renk", renk: "#222222", sure: 2, yazi: "Örnek sahne"}],
  gecis: "solma",
  gecis_sure: 0.4,
};

const olcu: CalculateMetadataFunction<Plan> = ({props}) => {
  const {width, height} = boyut(props.bicim);
  const fps = props.fps || 30;
  return {durationInFrames: Math.max(1, toplamKare(props, fps)), fps, width, height};
};

export const Kok: React.FC = () => (
  <Composition
    id="Kurgu"
    component={Kurgu}
    defaultProps={ornek}
    calculateMetadata={olcu}
    durationInFrames={60}
    fps={30}
    width={1080}
    height={1920}
  />
);
