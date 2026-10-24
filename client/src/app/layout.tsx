import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import { HACKATHONS, PORTFOLIO } from "@/lib/portfolio-data";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  weight: "400",
  style: ["normal", "italic"],
  subsets: ["latin"],
});

export const viewport: Viewport = {
  // The sect's ink (app/sect/sect.css --sect-ink), as in public/manifest.json.
  themeColor: "#0e0c14",
};

// The site is one page, the sect (app/page.tsx), so its title, description and share cards are here.
// The English name after the last "·" is the one the voice persona uses too (server/tests/test_personas.py).
const TITLE = `${PORTFOLIO.name} · Sun Moon Divine Sect`;
const DESCRIPTION = `${PORTFOLIO.name} builds LLM agents at Pinterest and has won ${HACKATHONS.length} hackathons. His portfolio is a 3D flight through 日月神教, the Sun Moon Divine Sect, where a senior disciple guides you through his work.`;
const SHARE_TEXT = "LLM agents at Pinterest. A portfolio you fly through, with a senior disciple of the sect as your guide.";
// A frame of the flight at the Mountain Gate, 1200x630 (public/og-image.jpg).
const IMAGE = {
  url: "/og-image.jpg",
  width: 1200,
  height: 630,
  type: "image/jpeg",
  alt: "The Mountain Gate of 日月神教, the Sun Moon Divine Sect, Bill Zhang's portfolio at art3m1s.me",
};

export const metadata: Metadata = {
  metadataBase: new URL("https://art3m1s.me"),
  manifest: "/manifest.json",
  title: TITLE,
  description: DESCRIPTION,
  keywords: [
    "AI Engineer",
    "Bill Zhang",
    "Portfolio",
    "Voice AI",
    "Conversational AI",
    "LLM agents",
    "Retell",
    "Hackathon",
    "three.js",
    "Sun Moon Divine Sect",
    "日月神教",
  ],
  authors: [{ name: PORTFOLIO.name }],
  creator: PORTFOLIO.name,
  robots: { index: true, follow: true },
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: "/",
    siteName: "Bill Zhang · art3m1s.me",
    title: TITLE,
    description: SHARE_TEXT,
    images: [IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: SHARE_TEXT,
    images: [IMAGE],
  },
  // The sect's seal: a sun cradled in a crescent moon, 日月, on cinnabar (public/favicon.svg; the PNGs
  // and the .ico are drawn from the same SVGs by scripts/make-icons.mjs).
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/icon.ico", sizes: "16x16 32x32 48x48" },
    ],
    shortcut: "/icon.ico",
    apple: { url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
  },
};

const SITE = "https://art3m1s.me";

/** Who the site is about, and the site itself (the sect), for search engines. */
const JSON_LD = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Person",
      "@id": `${SITE}/#bill`,
      name: PORTFOLIO.name,
      description: PORTFOLIO.tagline,
      jobTitle: "Software Engineer II",
      worksFor: {
        "@type": "Organization",
        name: "Pinterest",
      },
      alumniOf: [
        {
          "@type": "EducationalOrganization",
          name: "University of Southern California",
        },
        {
          "@type": "EducationalOrganization",
          name: "University of California, Santa Cruz",
        },
      ],
      url: SITE,
      sameAs: [PORTFOLIO.github, PORTFOLIO.linkedin, PORTFOLIO.devpost],
      knowsAbout: ["Artificial Intelligence", "Machine Learning", "Conversational AI", "Voice Agents"],
    },
    {
      "@type": "WebSite",
      "@id": `${SITE}/#site`,
      url: SITE,
      name: TITLE,
      alternateName: ["日月神教", "Sun Moon Divine Sect", "art3m1s.me"],
      description: DESCRIPTION,
      inLanguage: "en",
      author: { "@id": `${SITE}/#bill` },
      about: { "@id": `${SITE}/#bill` },
    },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning style={{ colorScheme: "dark" }}>
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${instrumentSerif.variable}`}
      >
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }} />
        {children}
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
