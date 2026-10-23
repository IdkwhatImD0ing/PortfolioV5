import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { PORTFOLIO, PROJECTS } from "@/lib/portfolio-data";
import { SUMMARY_ID } from "@/lib/sect/content-start";

// next/font only works inside Next's compiler; here the brush font is a plain class name.
vi.mock("./brush-font", () => ({ brushFont: { variable: "font-brush-test" } }));

const { SectSummary } = await import("./summary");

describe("SectSummary", () => {
  const html = renderToStaticMarkup(<SectSummary />);

  it("is one block the page can hide and make inert by id", () => {
    expect(html.startsWith(`<div id="${SUMMARY_ID}" class="sect-summary `)).toBe(true);
    expect(html).not.toContain("<script");
  });

  it("has one h1, the owner's name, and the sect's name", () => {
    expect(html.match(/<h1/g)).toHaveLength(1);
    expect(html).toContain(`<h1>${PORTFOLIO.name}</h1>`);
    expect(html).toContain("Sun Moon Divine Cult");
  });

  it("carries every project and the ways to get in touch as real links", () => {
    for (const p of PROJECTS) expect(html, p.name).toContain(p.name.replace(/&/g, "&amp;"));
    expect(html).toContain(`href="mailto:${PORTFOLIO.email}"`);
    expect(html).toContain('href="/resume.pdf"');
    expect(html).toContain(`href="${PORTFOLIO.linkedin}"`);
  });
});
