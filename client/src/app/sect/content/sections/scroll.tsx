"use client";

/** Jade Slip Pavilion (resume): the PDF preview and download, stats, at a glance, contact. */
import { PORTFOLIO } from "@/lib/portfolio-data";
import { RESUME_GLANCE, RESUME_HEAD, RESUME_LINKS, RESUME_STATS } from "@/lib/sect/content-copy";
import { itemDomId } from "@/lib/sect/content";
import { ExtLink, highlightProps, type BodyProps } from "../ui";

export function ScrollBody({ onHighlight }: BodyProps) {
  return (
    <div className="sc-body">
      <div className="sc-resume">
        <div id={itemDomId("resume")} tabIndex={-1} className="sc-resume-doc" {...highlightProps("resume", onHighlight)}>
          {/* The buttons sit above the preview: phones without an inline PDF viewer show an empty box. */}
          <div className="sc-resume-bar">
            <span className="sc-label">{RESUME_HEAD.fileLine}</span>
            <div className="sc-actions sc-actions-tight">
              <ExtLink href="/resume.pdf" className="sc-btn">
                <span aria-hidden>↗</span> {RESUME_HEAD.openTab}
              </ExtLink>
              <a href="/resume.pdf" download={RESUME_HEAD.downloadName} className="sc-btn sc-btn-gold">
                <span aria-hidden>↓</span> {RESUME_HEAD.download}
              </a>
            </div>
          </div>
          <div className="sc-resume-paper">
            <iframe src={RESUME_HEAD.previewSrc} title={RESUME_HEAD.previewTitle} loading="lazy" />
          </div>
        </div>

        <div className="sc-resume-side">
          <dl className="sc-stats sc-stats-2">
            {RESUME_STATS.map((s) => (
              <div key={s.k} className="sc-stat">
                <dt>{s.k}</dt>
                <dd>{s.v}</dd>
              </div>
            ))}
          </dl>

          <section className="sc-card" aria-labelledby="sc-resume-glance">
            <h4 id="sc-resume-glance" className="sc-label sc-label-gold">
              {RESUME_HEAD.glanceTitle}
            </h4>
            <ul className="sc-bullets sc-small">
              {RESUME_GLANCE.map((g) => (
                <li key={g.k}>
                  <strong className="sc-strong">{g.k}</strong> {g.v}
                </li>
              ))}
            </ul>
          </section>

          <section className="sc-card" aria-labelledby="sc-resume-contact">
            <h4 id="sc-resume-contact" className="sc-label sc-label-gold">
              {RESUME_HEAD.contactTitle}
            </h4>
            <ul className="sc-links">
              <li>
                <a href={`mailto:${PORTFOLIO.email}`} className="sc-linkrow">
                  {PORTFOLIO.email}
                </a>
              </li>
              {RESUME_LINKS.map((l) => (
                <li key={l.href}>
                  <ExtLink href={l.href} className="sc-linkrow">
                    {l.label}
                  </ExtLink>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
