import { SectClient } from "./sect/sect-client";
import { SectSummary } from "./sect/summary";
import "./sect/sect.css";

// Without JavaScript there is no flight and no page view: the veil goes, and the portfolio as text
// (SectSummary) shows in its place.
const NO_SCRIPT_CSS =
  ".sect-root{display:none!important}.sect-summary{position:static;width:auto;height:auto;overflow:visible;clip-path:none;white-space:normal}";

/**
 * The home page is the sect: 日月神教, the Sun Moon Divine Sect, a real-time fly-through of the
 * portfolio (./sect). It was /sect until it replaced the one-page portfolio (archived); /sect now
 * redirects here (app/sect/route.ts). Title, description and share cards are the root layout's.
 */
export default function Home() {
  return (
    <>
      <SectClient />
      <SectSummary />
      <noscript dangerouslySetInnerHTML={{ __html: `<style>${NO_SCRIPT_CSS}</style>` }} />
    </>
  );
}
