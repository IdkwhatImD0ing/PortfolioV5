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
const TITLE = `${PORTFOLIO.name} · Sun Moon Divine Cult`;
const DESCRIPTION = `${PORTFOLIO.name} builds LLM agents at Pinterest and has won ${HACKATHONS.length} hackathons. His portfolio is a 3D flight through 日月神教, the Sun Moon Divine Cult, with a voice guide you can talk to.`;
const SHARE_TEXT = "LLM agents at Pinterest. A portfolio you fly through, and talk to.";
// A frame of the flight at the Mountain Gate, 1200x630 (public/og-image.jpg).
const IMAGE = {
  url: "/og-image.jpg",
  width: 1200,
  height: 630,
  type: "image/jpeg",
  alt: "The Mountain Gate of 日月神教, the Sun Moon Divine Cult, Bill Zhang's portfolio at art3m1s.me",
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
    "Sun Moon Divine Cult",
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
  icons: {
    icon: [
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/icon.ico", rel: "icon" },
    ],
    shortcut: "/icon.ico",
    apple: "/apple-touch-icon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning style={{ colorScheme: "dark" }}>
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${instrumentSerif.variable}`}
      >
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "Person",
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
              url: "https://art3m1s.me",
              sameAs: [PORTFOLIO.github, PORTFOLIO.linkedin, PORTFOLIO.devpost],
              knowsAbout: [
                "Artificial Intelligence",
                "Machine Learning",
                "Conversational AI",
                "Voice Agents",
              ],
            }),
          }}
        />
        {children}
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
