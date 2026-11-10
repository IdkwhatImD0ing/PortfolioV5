/**
 * The soundtrack drawer's head: the title as the hero (Chinese with the seal, Latin in the serif),
 * quiet credits without "Not credited", and the owner's note only where there is one.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { songNote } from "@/lib/sect/song-notes";
import { SongHead } from "./karaoke-lyrics";

const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();

describe("SongHead", () => {
  it("writes a Chinese title with the seal beside it", () => {
    const html = renderToStaticMarkup(
      <SongHead track={{ title: "降临", show: "神印王座", artist: "Qi You (祁游)", language: "zh" }} note={songNote("arena")} />,
    );
    expect(html).toMatch(/<h2[^>]*sect-lyrics-title-zh/);
    expect(html).toContain('lang="zh"');
    expect(html).toContain("sect-seal");
    expect(text(html)).toContain("Qi You (祁游)");
    expect(text(html)).toContain("Sung in Chinese");
    expect(html).toContain('<dd lang="zh">神印王座</dd>');
  });

  it("writes a Latin title in the serif, with no seal", () => {
    const html = renderToStaticMarkup(
      <SongHead track={{ title: "Throne of Glory", show: "神印王座", artist: "Xian Ke", language: "en" }} note={songNote("mirror")} />,
    );
    expect(html).toMatch(/<h2 class="sect-lyrics-title">Throne of Glory<\/h2>/);
    expect(html).not.toContain("sect-seal");
    expect(text(html)).toContain("it’s better to let the glory go on without you and rest.");
  });

  it("leaves out an uncredited artist, and the note's place for an instrumental", () => {
    const html = renderToStaticMarkup(
      <SongHead track={{ title: "铁血丹心", show: "射雕英雄传 2017", artist: "Not credited", language: null }} note={songNote("gate")} />,
    );
    expect(html).not.toContain("Not credited");
    expect(html).not.toContain("Sung in");
    expect(html).not.toContain("sect-lyrics-note");
    expect(text(html)).toContain("Instrumental");
    // No note, so no brush rule to set one off.
    expect(html).not.toContain("sect-brushrule");
  });
});
