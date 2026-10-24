import { describe, expect, it } from "vitest";
import { isSectPath, personaForReferer, SECT_PERSONA } from "./persona";

describe("isSectPath", () => {
  it.each(["/", "/sect", "/sect/", "/sect/full/manifest.json"])("is the sect: %s", (path) => {
    expect(isSectPath(path)).toBe(true);
  });

  it.each(["", "/sectarian", "/api/sect", "/Sect", "/other"])("is not the sect: %j", (path) => {
    expect(isSectPath(path)).toBe(false);
  });
});

describe("personaForReferer", () => {
  it("asks for the sect persona from the home page, which is the sect, on any host", () => {
    for (const origin of ["https://art3m1s.me", "http://localhost:3000", "https://portfolio-v5-lake.vercel.app"]) {
      expect(personaForReferer(`${origin}/`), origin).toBe(SECT_PERSONA);
    }
    expect(personaForReferer("https://art3m1s.me/?view=page")).toBe(SECT_PERSONA);
    expect(personaForReferer("https://art3m1s.me/#project/dispatchai")).toBe(SECT_PERSONA);
  });

  it("asks for the sect persona from the sect's old address, query and hash or not", () => {
    expect(personaForReferer("https://portfolio-v5-lake.vercel.app/sect")).toBe(SECT_PERSONA);
    expect(personaForReferer("http://localhost:3000/sect?debug=1")).toBe(SECT_PERSONA);
    expect(personaForReferer("https://art3m1s.me/sect/#forge")).toBe(SECT_PERSONA);
  });

  it("asks for nothing from any other path", () => {
    expect(personaForReferer("https://art3m1s.me/sectarian")).toBeNull();
    expect(personaForReferer("https://art3m1s.me/other/page")).toBeNull();
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
