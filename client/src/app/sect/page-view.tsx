"use client";

/**
 * /sect as the one-page view only (?view=page, or when the browser asks to save data): every area's
 * content, the voice orb, and a link to the flight. No three.js and no scene download: when the page
 * view was chosen for the visitor, only the small manifest comes, for the size of what was skipped.
 */
import { useCallback, useEffect, useState } from "react";
import { commandTarget } from "@/lib/sect/content";
import { flightHref, skippedNote, type StartReason } from "@/lib/sect/content-start";
import { openingMegabytes } from "@/lib/sect/opening";
import { resolveAsset } from "@/lib/sect/parse";
import { parseSectParams, sectAssetBase } from "@/lib/sect/runtime";
import { ContentFallback, hotspotTarget, type ContentTarget } from "./content";
import { SectVoice, startTalk, useVoiceRouting } from "./experience/voice";

export default function PageView({ reason }: { reason: StartReason }) {
  const [view, setView] = useState<{ initial: ContentTarget | null; key: number }>(() => {
    const open = new URLSearchParams(window.location.search).get("open");
    return { initial: open ? hotspotTarget(open) : null, key: 0 };
  });

  // The voice agent and the orb's chips move this page, as they move the flight.
  useVoiceRouting((cmd) => {
    const t = commandTarget(cmd);
    if (t) setView((v) => ({ initial: t, key: v.key + 1 }));
  });

  const talk = useCallback(() => {
    if (!startTalk()) window.location.href = "/";
  }, []);

  // The size of the flight's first download, from the manifest (phones load the smaller textures).
  const [megabytes, setMegabytes] = useState<number | null>(null);
  useEffect(() => {
    if (reason === "asked") return;
    const ac = new AbortController();
    const base = sectAssetBase(parseSectParams(window.location.search).set, process.env.NEXT_PUBLIC_SECT_ASSET_BASE);
    const low = window.matchMedia("(pointer: coarse)").matches;
    fetch(resolveAsset(base, "manifest.json"), { signal: ac.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((raw: unknown) => setMegabytes(openingMegabytes(raw, low)))
      .catch(() => {});
    return () => ac.abort();
  }, [reason]);
  const why = skippedNote(reason, megabytes);

  const note = (
    <>
      {why ? `${why} ` : null}
      <a href={flightHref(window.location.search, window.location.hash)}>
        {reason === "asked" ? "See it as the 3D flight" : "Load the 3D flight anyway"}
      </a>
    </>
  );

  return (
    <>
      <ContentFallback key={view.key} initial={view.initial} onTalk={talk} note={note} />
      <SectVoice />
    </>
  );
}
