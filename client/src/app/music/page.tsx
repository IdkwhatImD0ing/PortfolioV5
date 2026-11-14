import type { Metadata } from "next";
import { brushFont } from "../sect/brush-font";
import { MusicPlayer } from "./music-player";
import "../sect/sect.css";
import "./music.css";

const TITLE = "Music · Bill Zhang";
const DESCRIPTION = "The songs that play across Bill Zhang’s portfolio, with their lyrics in Chinese and English.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: "/music" },
  // The root layout's share image (the Mountain Gate): a page's own openGraph replaces the layout's whole.
  openGraph: { type: "website", url: "/music", siteName: "Bill Zhang · art3m1s.me", title: TITLE, description: DESCRIPTION, images: ["/og-image.jpg"] },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION, images: ["/og-image.jpg"] },
};

/**
 * /music: the soundtrack as a player of its own, with each song's whole lyrics
 * (docs/music/music-page.md). The page is the client's (./music-player.tsx): the song list comes
 * from the backend, and nothing plays before a press.
 */
export default function MusicPage() {
  return (
    <>
      <MusicPlayer fontClass={brushFont.variable} />
      <noscript>
        <p style={{ padding: "1.5rem", color: "#f5ecdc" }}>The player needs JavaScript.</p>
      </noscript>
    </>
  );
}
