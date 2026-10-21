import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { contentInventory, inventoryMarkdown } from "./content-inventory";

const DOC = path.resolve(__dirname, "../../../docs/sect-content-inventory.md");

describe("content inventory", () => {
  const items = contentInventory();

  it("numbers every entry once, in order", () => {
    items.forEach((e, i) => expect(e.id).toBe(`C-${String(i + 1).padStart(3, "0")}`));
  });

  it("says where every entry lives, and why when it is not carried", () => {
    for (const e of items) {
      expect(e.where.length, e.id).toBeGreaterThan(0);
      if (e.status === "dropped" || e.status === "adapted") expect(e.note?.length ?? e.where.length, e.id).toBeGreaterThan(0);
      if (e.status === "dropped") expect(e.note, `${e.id} needs a reason`).toBeTruthy();
    }
  });

  it("checks real content: carried entries in an area name their texts or links", () => {
    const checked = items.filter((e) => e.area && (e.status === "carried" || e.status === "adapted"));
    const empty = checked.filter((e) => !(e.texts?.length || e.urls?.length) && e.status === "carried");
    expect(empty.map((e) => e.id)).toEqual([]);
  });

  it("matches docs/sect-content-inventory.md", () => {
    const md = inventoryMarkdown();
    if (process.env.SECT_WRITE_INVENTORY === "1") writeFileSync(DOC, md + "\n", "utf8");
    expect(existsSync(DOC), "run with SECT_WRITE_INVENTORY=1 to write the doc").toBe(true);
    expect(readFileSync(DOC, "utf8").replace(/\r\n/g, "\n")).toBe(md + "\n");
  });
});
