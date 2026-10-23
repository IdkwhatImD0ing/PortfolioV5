/**
 * The small pieces of the sect's Chinese dress, shared by the overlays, the readers, the map and the
 * loading screens (their look is in sect.css): a name in the brush hand, the red seal stamped beside
 * it, and the ink ring that turns while something loads. The brush divider, the cloud corners and the
 * paper are plain CSS classes (.sect-brushstroke, .sect-brushrule, .sect-panel, .sect-paper).
 * No hooks, no three.js: the loading screen renders these before the 3D code is here.
 */
import { brushCovers } from "@/lib/sect/brush";

/**
 * A Chinese name in the brush hand (lib/sect/brush.ts), or in the serif when the brush font lacks a
 * character of it. `vertical` sets it in a column, top to bottom, as on a hanging scroll.
 */
export function BrushName({
  text,
  vertical = false,
  className,
  hidden,
}: {
  text: string;
  vertical?: boolean;
  className?: string;
  /** Decorative (the same name is written elsewhere for screen readers). */
  hidden?: boolean;
}) {
  const hand = brushCovers(text) ? "sect-brushname" : "sect-zh";
  return (
    <span lang="zh" aria-hidden={hidden || undefined} className={`${hand}${vertical ? " sect-brushname-v" : ""}${className ? ` ${className}` : ""}`}>
      {text}
    </span>
  );
}

/**
 * The sect's seal, stamped beside a name: 明 (the sun and the moon) cut in paper white out of a
 * cinnabar square, a little worn and set a touch askew, as a seal pressed by hand. Decorative.
 */
export function SealStamp({ text = "明", className }: { text?: string; className?: string }) {
  return (
    <svg viewBox="0 0 40 40" aria-hidden focusable="false" className={`sect-seal${className ? ` ${className}` : ""}`}>
      <path
        d="M3.6 3.2L12 2.7L20.4 3.1L29 2.6L36.8 3.5L37.2 12L36.9 20.6L37.4 29L36.5 36.8L28 37.3L19.6 36.9L11.2 37.4L3.1 36.6L2.7 28.2L3.2 19.6L2.6 11.4Z"
        fill="var(--sect-cinnabar, #b8412d)"
      />
      <path d="M6.7 6.6H33.3V33.4H6.7Z" fill="none" stroke="var(--sect-paper, #f5ecdc)" strokeOpacity="0.5" strokeWidth="1" />
      <text
        x="20"
        y="29.4"
        textAnchor="middle"
        fontSize="24"
        fill="var(--sect-paper, #f5ecdc)"
        className={brushCovers(text) ? "sect-brushname" : "sect-zh"}
      >
        {text}
      </text>
    </svg>
  );
}

/** A place's name in the brush hand with the seal after it, kept together when the line wraps. */
export function SealedName({ text, className }: { text: string; className?: string }) {
  return (
    <span className={`sect-sealedname${className ? ` ${className}` : ""}`}>
      <BrushName text={text} />
      <SealStamp />
    </span>
  );
}

/** The ink ring that turns while a place gathers itself (still with reduced motion). Decorative. */
export function InkRing({ className }: { className?: string }) {
  return <span aria-hidden className={`sect-enso${className ? ` ${className}` : ""}`} />;
}
