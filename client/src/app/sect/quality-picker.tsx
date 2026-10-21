"use client";

/**
 * The graphics picker: Low, Medium or High, with the tier the device probe chose marked
 * "Recommended". On the loading screen (a row of three cells under the progress bar) and in the
 * overlay's graphics popover (a column). No three.js here: the loading screen renders it before the
 * 3D chunk has downloaded.
 *
 * Native radios in a fieldset: Tab lands on the checked one, the arrow keys move and pick, and
 * screen readers hear a radio group named "Graphics". The inputs are visually hidden; each whole
 * cell is the label, so a tap anywhere on it picks (52 px tall on the loading screen, 44 px in the
 * popover). The ring for keyboard focus is drawn on the cell (.sect-seg in sect.css).
 */
import { useEffect, useId, useRef } from "react";
import { TIER_LABELS, TIER_ORDER, type Tier } from "@/lib/sect/runtime";

/** Under the picker while the checked tier is above the recommended one. */
export const QUALITY_HINT = "May run slowly on this device.";

export interface QualityPickerProps {
  /** The checked tier. */
  tier: Tier;
  /** The device probe's tier (tagged "Recommended"). */
  recommended: Tier;
  onPick: (tier: Tier) => void;
  /** "row": three cells (the loading screen). "column": three rows (the overlay's popover). */
  layout?: "row" | "column";
  /** The radios' group name (two pickers on the page at once must not share one). */
  name?: string;
  /** Focus the checked radio once mounted (the focus was in the other picker, which went away). */
  autoFocus?: boolean;
}

/**
 * The loading screen's picker takes this much height, whatever it shows; QualityPickerSpace keeps
 * it before the picker can mount, so the centred column never jumps.
 */
const ROW_BOX = "mt-7 h-[6.5rem] w-full [@media(max-height:30rem)]:mt-4";

function Diamond({ on }: { on: boolean }) {
  return (
    <span
      aria-hidden
      className={`block h-2.5 w-2.5 shrink-0 rotate-45 border border-[var(--sect-gold)] shadow-[0_0_0_1px_rgba(14,12,20,0.6)] ${on ? "bg-[var(--sect-gold)]" : "bg-[rgba(14,12,20,0.62)]"}`}
    />
  );
}

export function QualityPicker({ tier, recommended, onPick, layout = "row", name = "sect-quality", autoFocus = false }: QualityPickerProps) {
  const hintId = useId();
  const checkedRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (autoFocus) checkedRef.current?.focus({ preventScroll: true });
    // Once, on mount: later picks keep the focus where the visitor put it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const above = TIER_ORDER.indexOf(tier) > TIER_ORDER.indexOf(recommended);
  const row = layout === "row";

  const cells = TIER_ORDER.map((t, i) => {
    const on = t === tier;
    const look = on
      ? "bg-[rgba(233,199,126,0.12)] text-[var(--sect-paper)] shadow-[inset_0_0_0_1px_var(--sect-gold)]"
      : "text-[var(--sect-paper-soft)] hover:text-[var(--sect-paper)] hover:shadow-[inset_0_0_0_1px_rgba(233,199,126,0.6)]";
    const tag =
      t === recommended ? (
        <>
          <span className="sr-only">, </span>
          Recommended
        </>
      ) : null;
    return (
      <label
        key={t}
        className={`sect-seg relative flex cursor-pointer select-none transition-[color,background-color,box-shadow] duration-150 motion-reduce:transition-none ${look} ${
          row
            ? `h-[3.25rem] items-center justify-center px-1 pb-2 ${i > 0 ? "border-l border-[var(--sect-gold-soft)]" : ""}`
            : "min-h-11 items-center gap-3 rounded-[2px] px-3"
        }`}
      >
        <input
          ref={on ? checkedRef : undefined}
          type="radio"
          name={name}
          value={t}
          checked={on}
          onChange={() => onPick(t)}
          aria-describedby={hintId}
          className="sr-only"
        />
        {row ? (
          <>
            <span className="flex items-center gap-2 text-[0.72rem] uppercase leading-none tracking-[0.2em]">
              <Diamond on={on} />
              {TIER_LABELS[t]}
            </span>
            {/* Hung under the label, so all three labels sit on one line near the cells' middle. */}
            {tag && (
              <span className="absolute inset-x-0 top-[calc(50%+0.4rem)] whitespace-nowrap text-[0.66rem] normal-case leading-3 tracking-[0.06em] text-[var(--sect-gold)]">
                {tag}
              </span>
            )}
          </>
        ) : (
          <>
            <Diamond on={on} />
            <span className="flex-1 text-left text-[0.72rem] uppercase tracking-[0.2em]">{TIER_LABELS[t]}</span>
            {tag && <span className="text-[0.66rem] tracking-[0.06em] text-[var(--sect-gold)]">{tag}</span>}
          </>
        )}
      </label>
    );
  });

  const fieldset = (
    // On the loading screen it fades in over its kept place (sect.css) when the flight's code arrives.
    <fieldset data-sect-picker className={`m-0 min-w-0 border-0 p-0 ${row ? "sect-fade-in" : ""}`}>
      <legend
        className={
          row
            ? "float-left mb-2 w-full p-0 pl-[0.3em] text-center text-[0.62rem] uppercase leading-4 tracking-[0.3em] text-[var(--sect-gold)]"
            : "mb-1.5 px-1 text-[0.62rem] uppercase leading-4 tracking-[0.3em] text-[var(--sect-gold)]"
        }
      >
        Graphics
      </legend>
      <div
        className={
          row ? "clear-both grid grid-cols-3 rounded-[2px] border border-[var(--sect-gold-soft)]" : "flex flex-col gap-1"
        }
      >
        {cells}
      </div>
      {/* On the loading screen its row is always there (empty when nothing needs saying), so the
          centred column never moves; the popover just grows. */}
      <p
        id={hintId}
        className={`text-[0.75rem] leading-[1.125rem] text-[var(--sect-paper-soft)] ${row ? "mt-2 min-h-[1.125rem] text-center" : above ? "mt-2 px-1" : "hidden"}`}
      >
        {above ? QUALITY_HINT : ""}
      </p>
    </fieldset>
  );
  return row ? <div className={ROW_BOX}>{fieldset}</div> : fieldset;
}

/** The loading screen's picker's place, kept empty before it can mount (no inputs, not announced). */
export function QualityPickerSpace() {
  return <div aria-hidden className={ROW_BOX} />;
}
