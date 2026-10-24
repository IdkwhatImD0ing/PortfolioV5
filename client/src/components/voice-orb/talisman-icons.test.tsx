/**
 * The orb button's icon and its candidates (talisman-icons.tsx): the microphone stays until the owner
 * picks, and every icon is a decorative 24-unit SVG so the button keeps its own accessible name.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ORB_ICON, ORB_ICON_IDS, OrbIcon, type OrbIconId } from "./talisman-icons";

// JSX in this folder's tests: its tsconfig.json turns it on for Vitest, as the sect's experience/ does.
const draw = (icon?: OrbIconId, className?: string) => renderToStaticMarkup(<OrbIcon icon={icon} className={className} />);

describe("OrbIcon", () => {
  it("shows the talisman slip, the owner's pick", () => {
    expect(ORB_ICON).toBe("slip");
    expect(draw()).toContain('data-orb-icon="slip"');
  });

  it("draws every icon as a hidden 24-unit SVG, each one different", () => {
    const drawn = new Set<string>();
    for (const id of ORB_ICON_IDS) {
      const svg = draw(id, "w-[22px]");
      expect(svg).toContain('viewBox="0 0 24 24"');
      expect(svg).toContain('aria-hidden="true"');
      expect(svg).toContain('focusable="false"');
      expect(svg).toContain('class="w-[22px]"');
      // Nothing in it is read out or named: no title, no text.
      expect(svg).not.toMatch(/<title|<text/);
      drawn.add(svg.replace(/data-orb-icon="[^"]*"/, ""));
    }
    expect(drawn.size).toBe(ORB_ICON_IDS.length);
    expect(new Set(ORB_ICON_IDS)).toEqual(new Set(["mic", "crane", "disciple", "slip"]));
  });

  it("colours the drawings from the button's text colour, the slip's ink and qi aside", () => {
    for (const id of ORB_ICON_IDS) {
      const svg = draw(id);
      expect(svg).toContain("currentColor");
    }
    expect(draw("slip")).toContain("var(--sect-jade");
  });
});
