import { SUMMARY_ID } from "@/lib/sect/content-start";
import { portfolioSummary } from "@/lib/sect/summary";
import { brushFont } from "./brush-font";
import { BrushName } from "./ornaments";

/**
 * The whole portfolio as plain text, rendered on the server under the flight (lib/sect/summary.ts):
 * crawlers and language models read it in the HTML, and visitors without JavaScript get it as the
 * page (the <noscript> rule in app/page.tsx). While the page's scripts run it stays out of sight and
 * sect-client.tsx makes it inert, so the flight and its own readers are what anyone sees or tabs to.
 * A server component: none of it is in the page's scripts.
 */
export function SectSummary() {
  const s = portfolioSummary();
  return (
    <div id={SUMMARY_ID} className={`sect-summary ${brushFont.variable}`}>
      <div className="sect-summary-page">
        <header>
          <p className="sect-summary-brand">
            <BrushName text="日月神教" even={0.1} className="sect-summary-seal" />
            <span>Sun Moon Divine Sect</span>
          </p>
          <h1>{s.name}</h1>
          <p className="sect-summary-tagline">{s.tagline}</p>
          <p>{s.intro}</p>
          <p className="sect-summary-note">
            This site is a 3D flight through 日月神教, the Sun Moon Divine Sect, where a senior disciple of the sect guides you.
            Both need JavaScript, so here is the whole portfolio as text.
          </p>
        </header>
        {s.sections.map((sec) => (
          <section key={sec.area} aria-labelledby={`${SUMMARY_ID}-${sec.area}`}>
            <h2 id={`${SUMMARY_ID}-${sec.area}`}>
              {sec.heading}{" "}
              <span className="sect-summary-place">
                {sec.place} <span lang="zh">{sec.zh}</span>
              </span>
            </h2>
            {sec.intro && <p>{sec.intro}</p>}
            {sec.items.length > 0 && (
              <ul>
                {sec.items.map((it, i) => (
                  <li key={i}>
                    <h3>{it.title}</h3>
                    {it.meta && <p className="sect-summary-meta">{it.meta}</p>}
                    {it.lines.map((l, j) => (
                      <p key={j}>{l}</p>
                    ))}
                    {it.links && it.links.length > 0 && (
                      <p className="sect-summary-links">
                        {it.links.map((l) => (
                          <a key={l.href} href={l.href}>
                            {l.label}
                          </a>
                        ))}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}
