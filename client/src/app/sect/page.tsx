import type { Metadata } from "next";
import { PORTFOLIO } from "@/lib/portfolio-data";
import { SectClient } from "./sect-client";
import "./sect.css";

const TITLE = `${PORTFOLIO.name} · The Ming Sect`;
// The main page's share image (app/opengraph-image.tsx, twitter-image.tsx): setting openGraph here
// replaces the inherited one, images included, so they are named again.
const IMAGE = { width: 1200, height: 630, type: "image/png", alt: "Bill Zhang, voice-driven AI portfolio at art3m1s.me" };
const DESCRIPTION = PORTFOLIO.tagline;

// The real-time sect fly-through. Not linked from the main page, and kept out of search results.
export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  robots: { index: false, follow: false, nocache: true, googleBot: { index: false, follow: false } },
  alternates: { canonical: "/sect" },
  openGraph: {
    type: "website",
    url: "/sect",
    siteName: "Bill Zhang · art3m1s.me",
    title: TITLE,
    description: DESCRIPTION,
    images: [{ url: "/opengraph-image", ...IMAGE }],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
    images: [{ url: "/twitter-image", ...IMAGE }],
  },
};

export default function SectPage() {
  return <SectClient />;
}
