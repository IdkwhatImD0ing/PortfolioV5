/**
 * The icon on the voice orb's button (the sect's 传音符 talisman, dressed by sect.css under .sect-orb).
 *
 * The owner asked for "a more agentic icon than the microphone" (October 2026): something that reads
 * as a guide who goes and does things for you, not as a recording device. Three candidates are drawn
 * here beside the microphone, each made to read at the button's real size (26px on a 64px seal on
 * desktop, 21px on a 48px seal on phones, sect.css):
 *   crane     纸鹤传书: a folded paper crane, the messenger a cultivator sends off with a note. Flat
 *             gold planes with a lighter fold on the wing and body, tilted up as it takes off.
 *   disciple  the senior disciple: head and shoulders, a topknot, a robe crossed at the collar, and a
 *             sword's hilt over the shoulder.
 *   slip      a talisman slip with a spirit spark written on it in ink, and two sparks of jade qi
 *             round it.
 * ORB_ICON picks the one the button shows. It stays on the microphone until the owner picks.
 */
import type { ComponentType } from "react";

export type OrbIconId = "mic" | "crane" | "disciple" | "slip";

/** Every icon, in the order the preview sheet shows them. */
export const ORB_ICON_IDS: readonly OrbIconId[] = ["mic", "crane", "disciple", "slip"];

/** The icon the orb's button shows. */
export const ORB_ICON: OrbIconId = "mic";

/** The slip's writing: a dark jade, the shade of the talisman face's lower edge. */
const SLIP_INK = "#123a31";
/** Qi round the slip: the sect's jade. */
const QI = "var(--sect-jade, #8fe3c8)";

function Microphone() {
  return (
    <g fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="3" width="6" height="12" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0" />
      <line x1="12" y1="18" x2="12" y2="22" />
    </g>
  );
}

/** Facing left, into the page: neck and head, the raised wing, the body under it, the tail. */
function PaperCrane() {
  return (
    <g fill="currentColor" transform="rotate(-8 12 12) translate(0 .9)">
      <path d="M9.2 12.2 16.4 1 12.4 12.2z" />
      <path d="M12.4 12.2 16.4 1 15.1 12.2z" fillOpacity=".55" />
      <path d="M5.6 13.1h6.6l.6 7.1z" />
      <path d="M12.2 13.1h6.6l-6 7.1z" fillOpacity=".55" />
      <path d="M6.2 12.2 2.4 4.4 9 12.2z" />
      <path d="M2.6 3.6.4 7.6l3.4-1.8z" />
      <path d="M15.6 12.2 23.4 4 18.6 12.2z" fillOpacity=".8" />
    </g>
  );
}

/** The sword's hilt, then the head and topknot, then the robe's two lapels (crossed left over right). */
function SeniorDisciple() {
  return (
    <g fill="currentColor">
      <path d="M17 13 20.8 5.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M16.3 10.8l3.8 1.9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <circle cx="12" cy="11" r="3.8" />
      <circle cx="12" cy="6.1" r="1.75" />
      <path d="M3.4 22.2c.2-4.4 2.8-6.4 6-7l6 7z" />
      <path d="M14.6 15.2c3.2.6 5.8 2.6 6 7H16l-3.4-4z" />
    </g>
  );
}

/** The slip, leaning, with a spark and two lines of script in ink; two sparks of qi beside it. */
function TalismanSlip() {
  return (
    <g>
      <g transform="rotate(-12 12 12)">
        <path d="M8.2 1.4h7.6v21.2H8.2z" fill="currentColor" />
        <path d="M12 4.4l1.35 3.45L16.8 9.2l-3.45 1.35L12 14l-1.35-3.45L7.2 9.2l3.45-1.35z" fill={SLIP_INK} />
        <path
          d="M10.1 16.9h3.8M10.7 19.6h2.6"
          fill="none"
          stroke={SLIP_INK}
          strokeWidth="1.2"
          strokeLinecap="round"
        />
      </g>
      <path d="M20 1.6l.65 1.65 1.65.65-1.65.65L20 6.2l-.65-1.65-1.65-.65 1.65-.65z" style={{ fill: QI }} />
      <path d="M4.3 17.4l.45 1.15 1.15.45-1.15.45-.45 1.15-.45-1.15-1.15-.45 1.15-.45z" style={{ fill: QI }} />
    </g>
  );
}

const DRAWINGS: Record<OrbIconId, ComponentType> = {
  mic: Microphone,
  crane: PaperCrane,
  disciple: SeniorDisciple,
  slip: TalismanSlip,
};

/** The orb button's icon: decorative, since the button carries its own name. */
export function OrbIcon({ icon = ORB_ICON, className }: { icon?: OrbIconId; className?: string }) {
  const Drawing = DRAWINGS[icon];
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" data-orb-icon={icon} className={className}>
      <Drawing />
    </svg>
  );
}
