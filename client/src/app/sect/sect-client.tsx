"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { POSTER_SCRIPT, startView, type NetworkHint, type StartView } from "@/lib/sect/content-start";
import { brushFont } from "./brush-font";
import { LoadingScreen } from "./loading-screen";

function Veil() {
  return <LoadingScreen progress={0} label="Loading the sect" />;
}

/** The flight's veil before its code is here: the graphics picker's and the sound prompt's places are kept. */
function FlightVeil() {
  return <LoadingScreen progress={0} label="Loading the sect" quality="reserve" sound="reserve" poster />;
}

// three.js and R3F live only in ./experience, which is reachable only through this dynamic import,
// so they are split into a chunk that loads on /sect alone (and not at all in the page view).
const SectExperience = dynamic(() => import("./experience/sect-experience"), { ssr: false, loading: FlightVeil });
const PageView = dynamic(() => import("./page-view"), { ssr: false, loading: Veil });

export function SectClient() {
  // Decided after mount (the server renders the veil either way): ?view=page, or a browser that asks
  // to save data, starts in the page view and never downloads the scene.
  const [start, setStart] = useState<StartView | null>(null);
  useEffect(() => {
    const net = (navigator as Navigator & { connection?: NetworkHint }).connection;
    setStart(startView(window.location.search, net));
  }, []);
  return (
    // The brush font's variable (brush-font.ts) is set here, so every overlay, reader and veil has it.
    <div className={`sect-root ${brushFont.variable}`}>
      {/* Before the first paint: the default start shows the poster still behind the veil at once
          (lib/sect/content-start.ts). Only the server's copy runs; the flight takes over the
          attribute once it is here. */}
      <script dangerouslySetInnerHTML={{ __html: POSTER_SCRIPT }} suppressHydrationWarning />
      {start === null ? <FlightVeil /> : start.view === "page" ? <PageView reason={start.reason} /> : <SectExperience />}
    </div>
  );
}
