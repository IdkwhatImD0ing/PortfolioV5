import { describe, expect, it } from "vitest";
import { isSectPath, personaForReferer, SECT_PERSONA, SECT_REFERRER } from "./persona";

describe("isSectPath", () => {
  it.each(["/sect", "/sect/", "/sect/full/manifest.json"])("is the sect: %s", (path) => {
    expect(isSectPath(path)).toBe(true);
  });

  it.each(["/", "", "/sectarian", "/api/sect", "/Sect"])("is not the sect: %j", (path) => {
    expect(isSectPath(path)).toBe(false);
  });
});

describe("personaForReferer", () => {
  it("asks for the sect persona from the /sect page, query and hash or not", () => {
    expect(personaForReferer("https://portfolio-v5-lake.vercel.app/sect")).toBe(SECT_PERSONA);
    expect(personaForReferer("http://localhost:3000/sect?debug=1")).toBe(SECT_PERSONA);
    expect(personaForReferer("https://art3m1s.me/sect/#forge")).toBe(SECT_PERSONA);
  });

  it("asks for the sect persona from the address the sect's orb names, on any host", () => {
    // fetch() sends a same-origin `referrer` path as the full URL.
    for (const origin of ["https://art3m1s.me", "http://localhost:3000", "https://portfolio-v5-25hr.vercel.app"]) {
      expect(personaForReferer(new URL(SECT_REFERRER, origin).href), origin).toBe(SECT_PERSONA);
    }
  });

  it("asks for nothing from the root path or anywhere else", () => {
    expect(personaForReferer("https://art3m1s.me/")).toBeNull();
    expect(personaForReferer("https://art3m1s.me/#projects")).toBeNull();
    expect(personaForReferer("https://art3m1s.me/sectarian")).toBeNull();
  });

  it("asks for nothing without a usable Referer", () => {
    expect(personaForReferer(null)).toBeNull();
    expect(personaForReferer(undefined)).toBeNull();
    expect(personaForReferer("")).toBeNull();
    expect(personaForReferer("not a url")).toBeNull();
  });

  it("is the backend's name for the persona", () => {
    // server/personas.py MING_SECT; the backend treats any other value as classic.
    expect(SECT_PERSONA).toBe("ming-sect");
  });
});
