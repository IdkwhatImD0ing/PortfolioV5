/**
 * The map's seals (map-view.tsx): one emblem per stop, drawn in a 40 x 40 box with brush-like round
 * strokes in the current colour (gold on an ink seal; ink on the gold seal of the current stop), and
 * the visitor's own mark, the sun and the moon (日月, as the sect's name begins) on a cinnabar seal.
 */
import type { ReactNode } from "react";
import type { AreaId } from "@/lib/sect/areas";

const OCTAGON = "M32 25 L25 32 L15 32 L8 25 L8 15 L15 8 L25 8 L32 15 Z";

/** The eight trigram bars of the formation's bagua, one per side of the octagon (broken bars split). */
function bagua(): ReactNode {
  const bars: ReactNode[] = [];
  for (let k = 0; k < 8; k++) {
    const a = ((22.5 + 45 * k + 22.5) * Math.PI) / 180;
    const cx = 20 + 9.6 * Math.cos(a);
    const cy = 20 + 9.6 * Math.sin(a);
    const tx = -Math.sin(a);
    const ty = Math.cos(a);
    const half = 2.6;
    const d =
      k % 2 === 0
        ? `M${(cx - tx * half).toFixed(2)} ${(cy - ty * half).toFixed(2)}L${(cx + tx * half).toFixed(2)} ${(cy + ty * half).toFixed(2)}`
        : `M${(cx - tx * half).toFixed(2)} ${(cy - ty * half).toFixed(2)}L${(cx - tx * 0.7).toFixed(2)} ${(cy - ty * 0.7).toFixed(2)}M${(cx + tx * 0.7).toFixed(2)} ${(cy + ty * 0.7).toFixed(2)}L${(cx + tx * half).toFixed(2)} ${(cy + ty * half).toFixed(2)}`;
    bars.push(<path key={k} d={d} />);
  }
  return bars;
}

/** Each stop's emblem (inside an <svg viewBox="0 0 40 40">). */
export const EMBLEMS: Record<AreaId, ReactNode> = {
  // The mountain gate: a three-bay paifang, the middle roof highest, with its name board.
  gate: (
    <>
      <path d="M11 11.8C14.5 12.4 17.4 11 20 8.6C22.6 11 25.5 12.4 29 11.8L27.8 14H12.2Z" fill="currentColor" stroke="none" />
      <path d="M5 16.6C7.4 17 9.4 16 10.8 14.6C11.6 15.6 12.6 16.2 13.6 16.4L13 18H6Z" fill="currentColor" stroke="none" />
      <path d="M35 16.6C32.6 17 30.6 16 29.2 14.6C28.4 15.6 27.4 16.2 26.4 16.4L27 18H34Z" fill="currentColor" stroke="none" />
      <path d="M14.2 14V31M25.8 14V31M7.6 18V31M32.4 18V31M12.6 19.4H27.4" />
      <path d="M17.6 14.6H22.4V17.4H17.6Z" strokeWidth="1.2" />
      <path d="M12.6 31.4H15.8M24.2 31.4H27.4M6.4 31.4H8.8M31.2 31.4H33.6" strokeWidth="1.5" />
    </>
  ),
  // The Heart-Mirror Terrace: a round bronze mirror on a lotus stand.
  mirror: (
    <>
      <circle cx="20" cy="16.4" r="9" />
      <circle cx="20" cy="16.4" r="5.9" strokeWidth="1" strokeDasharray="1.5 1.6" />
      <circle cx="20" cy="16.4" r="1.7" fill="currentColor" stroke="none" />
      <path d="M14.4 12.2A7 7 0 0 1 17.8 9.6" strokeWidth="1.2" opacity="0.85" />
      <path d="M20 25.4V27.4" />
      <path d="M13.4 31.6C14.2 28.8 16.9 27.4 20 27.4C23.1 27.4 25.8 28.8 26.6 31.6Z" fill="currentColor" stroke="none" />
    </>
  ),
  // The forge: a flame over a ding cauldron.
  forge: (
    <>
      <path
        d="M20 6.4C23.8 10 24.8 13.2 22.8 15.8C22.6 14 21.8 13 20.7 12.3C21.1 14.3 19.9 15.6 18.6 16.2C16.3 14.6 16.1 11.4 20 6.4Z"
        fill="currentColor"
        stroke="none"
      />
      <path d="M10.6 19.2H29.4M11.6 19.2C11.6 25 15 28.2 20 28.2C25 28.2 28.4 25 28.4 19.2" />
      <path d="M12.8 19.2V16.2H16V19.2M24 19.2V16.2H27.2V19.2" strokeWidth="1.5" />
      <path d="M13.6 22.6H26.4" strokeWidth="1.1" opacity="0.85" />
      <path d="M15.2 27.2L14 31.6M24.8 27.2L26 31.6M20 28.2V31.6" />
    </>
  ),
  // The arena: two crossed swords.
  arena: (
    <>
      <path d="M13.4 26.6L29.6 10.4M10.2 29.8L13.4 26.6M11.6 23.4L16.6 28.4" />
      <path d="M26.6 26.6L10.4 10.4M29.8 29.8L26.6 26.6M28.4 23.4L23.4 28.4" />
      <circle cx="9.4" cy="30.6" r="1.2" fill="currentColor" stroke="none" />
      <circle cx="30.6" cy="30.6" r="1.2" fill="currentColor" stroke="none" />
    </>
  ),
  // The Mission Hall: a temple bell.
  mission: (
    <>
      <path d="M17.4 10.6Q20 7.6 22.6 10.6" />
      <path d="M13.6 26C13.6 17.8 15.6 11 20 11C24.4 11 26.4 17.8 26.4 26Z" />
      <path d="M11.4 26.4H28.6M15.2 17.6H24.8" />
      <path d="M15 21.6H25" strokeWidth="1" opacity="0.8" />
      <circle cx="20" cy="29.4" r="1.7" fill="currentColor" stroke="none" />
    </>
  ),
  // The Scripture Pavilion: a three-roofed pagoda.
  library: (
    <>
      <path d="M20 5.6V9.4" />
      <path d="M13.2 13C16.4 12.4 18.4 11.2 20 9.4C21.6 11.2 23.6 12.4 26.8 13L25.8 14.2H14.2Z" fill="currentColor" stroke="none" />
      <path d="M11 19.2C15 18.6 17.8 17.2 20 15.4C22.2 17.2 25 18.6 29 19.2L28 20.4H12Z" fill="currentColor" stroke="none" />
      <path d="M8.6 25.6C13.6 25 17.4 23.4 20 21.4C22.6 23.4 26.4 25 31.4 25.6L30.4 26.8H9.6Z" fill="currentColor" stroke="none" />
      <path d="M16.4 14.2V15.8M23.6 14.2V15.8M14.4 20.4V22.4M25.6 20.4V22.4M12.4 26.8V31.2M27.6 26.8V31.2M9.4 31.4H30.6" />
      <path d="M18.2 31.2V28.6H21.8V31.2" strokeWidth="1.2" />
    </>
  ),
  // The Stele Forest: an inscribed stele under its carved crown, smaller ones either side.
  steles: (
    <>
      <path d="M6.6 30V21C6.6 18.6 10.6 18.6 10.6 21V30M29.4 30V21C29.4 18.6 33.4 18.6 33.4 21V30" strokeWidth="1.3" opacity="0.8" />
      <path d="M13.6 14.8C13.6 8.4 26.4 8.4 26.4 14.8Z" fill="currentColor" stroke="none" />
      <path d="M15 14.8V30M25 14.8V30" />
      <path d="M18 17.4V19.8M18 21.6V24M18 25.8V27.6M22 17.4V19.8M22 21.6V24M22 25.8V27.6" strokeWidth="1.3" />
      <path d="M5.4 30.6H34.6M13.4 30.6V28.8H26.6V30.6" strokeWidth="1.5" />
    </>
  ),
  // The Jade Slip Pavilion: a book of slips bound with cords, its end rolled up, a tassel hanging.
  scroll: (
    <>
      <path d="M8.6 11.4H11.4V28.6H8.6ZM12.8 10.6H15.6V29.4H12.8ZM17 11.4H19.8V28.6H17ZM21.2 10.6H24V29.4H21.2Z" strokeWidth="1.4" />
      <circle cx="29" cy="20" r="5.4" strokeWidth="1.6" />
      <path d="M29 20.2m-1.9 0a1.9 1.9 0 1 1 1.9 1.9" strokeWidth="1.3" />
      <path d="M7.4 16C14 15.2 19.4 16.6 25.4 15.8M7.4 24.4C14 23.6 19.4 25 25.4 24.2" strokeWidth="1.4" />
      <path d="M7.4 24.4L5.4 28.4" strokeWidth="1.3" />
      <path d="M5.4 28.4L4.2 31.4H6.6Z" fill="currentColor" stroke="none" />
    </>
  ),
  // The Grand Formation: the bagua round the taiji.
  formation: (
    <>
      <path d={OCTAGON} strokeWidth="1.4" />
      <g strokeWidth="1.5">{bagua()}</g>
      <circle cx="20" cy="20" r="4.6" strokeWidth="1.3" />
      <path d="M20 15.4A2.3 2.3 0 0 1 20 20A2.3 2.3 0 0 0 20 24.6A4.6 4.6 0 0 1 20 15.4Z" fill="currentColor" stroke="none" />
    </>
  ),
  // The Cave Abode: a moon gate in a wall under the mountain.
  abode: (
    <>
      <path d="M6.6 17.4L13.6 9.6L17.6 13.2L22.8 7.4L33.4 17.4" strokeWidth="1.5" />
      <path d="M7.4 20.2L9 18.6H31L32.6 20.2" />
      <path d="M9.4 20.2V31M30.6 20.2V31M7.4 31.2H32.6" />
      <path d="M15.2 31A6.4 6.4 0 1 1 24.8 31" />
    </>
  ),
  // The Moon-Gazing Terrace: the crescent moon over the terrace.
  summit: (
    <>
      <path d="M19.14 7.5A8.5 8.5 0 1 0 26.9 19.14A7 7 0 0 1 19.14 7.5Z" fill="currentColor" stroke="none" />
      <path d="M10.6 31.4H29.4M12.8 31.4V27.6H27.2V31.4M11.6 27.6H28.4" strokeWidth="1.5" />
    </>
  ),
};

/** One stop's emblem as an SVG (decorative: the button around it carries the name). */
export function Emblem({ id, className }: { id: AreaId; className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      aria-hidden
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {EMBLEMS[id]}
    </svg>
  );
}

/** The visitor's mark: 日月, the sun beside the moon, in paper on a cinnabar seal. */
export function HereGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" aria-hidden className={className}>
      <circle cx="20" cy="20" r="15" fill="var(--sect-cinnabar)" stroke="var(--sect-gold)" strokeWidth="1.6" />
      <circle cx="20" cy="20" r="12.2" fill="none" stroke="var(--sect-paper)" strokeWidth="0.7" opacity="0.55" />
      <circle cx="14.4" cy="20" r="3.5" fill="var(--sect-paper)" />
      <path d="M24.73 15.01A5 5 0 1 0 29.12 21.91A4.1 4.1 0 1 1 24.73 15.01Z" fill="var(--sect-paper)" />
    </svg>
  );
}
