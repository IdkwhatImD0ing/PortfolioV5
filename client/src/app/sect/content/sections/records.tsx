"use client";

/** Sword-Discussion Arena (hackathons), Mission Hall (experience), Scripture Pavilion (education). */
import Image from "next/image";
import { useState } from "react";
import { EDUCATION, EXPERIENCE, HACKATHONS, PORTFOLIO } from "@/lib/portfolio-data";
import { HACKATHON_STATS } from "@/lib/sect/content-copy";
import { company, hackathonProject, itemDomId, itemIndex } from "@/lib/sect/content";
import { roleTimeline, topPrizes } from "@/lib/sect/explore";
import { DetailFrame, OpenTitle, RelatedList, openCardProps, spotNames, useItemDetail, type ItemDetail } from "../detail";
import { ExtLink, highlightProps, type BodyProps } from "../ui";

// ---- arena ------------------------------------------------------------------------------------

const arenaItem = (it: string) => itemIndex(it, "hackathon") !== null || it === "arena-judges";

function HackathonStats() {
  return (
    <dl className="sc-stats">
      {HACKATHON_STATS.map((s) => (
        <div key={s.l} className="sc-stat">
          <dt>{s.l}</dt>
          <dd>{s.n === "count" ? HACKATHONS.length : s.n}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ArenaBody(props: BodyProps) {
  const { onNavigate, onHighlight } = props;
  const d = useItemDetail("arena", arenaItem, props);
  if (d.openItem === "arena-judges") return <JudgesView d={d} />;
  if (d.openItem) return <HackathonView d={d} i={itemIndex(d.openItem, "hackathon")!} />;
  return (
    <div className="sc-body">
      <HackathonStats />
      <ol className="sc-banners">
        {HACKATHONS.map((h, i) => {
          const hid = `hackathon:${i}`;
          const project = hackathonProject(i);
          return (
            <li
              key={hid}
              id={itemDomId(hid)}
              tabIndex={-1}
              className="sc-banner"
              {...openCardProps(d, hid)}
              {...highlightProps(hid, onHighlight)}
            >
              <span className="sc-banner-no" aria-hidden>
                {String(i + 1).padStart(2, "0")}
              </span>
              <div className="sc-banner-text">
                <h5 className="sc-banner-name">
                  <OpenTitle d={d} id={hid}>
                    {h.name}
                    {h.year && <span className="sc-banner-year"> {h.year}</span>}
                  </OpenTitle>
                </h5>
                <p className="sc-prize">★ {h.prize}</p>
                <p className="sc-text sc-small">
                  <span className="sc-label-inline">Project</span> {h.project}
                </p>
                {project && (
                  <button
                    type="button"
                    className="sc-textbtn"
                    onClick={() => onNavigate({ area: "forge", item: `project:${project.id}` })}
                  >
                    Open project <span aria-hidden>→</span>
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function HackathonView({ d, i }: { d: ItemDetail; i: number }) {
  const h = HACKATHONS[i];
  const project = hackathonProject(i);
  const hid = `hackathon:${i}`;
  return (
    <DetailFrame
      d={d}
      item={hid}
      title={
        <>
          {h.name}
          {h.year && <span className="sc-h3-year"> {h.year}</span>}
        </>
      }
    >
      <p className="sc-prize sc-prize-lg">★ {h.prize}</p>
      {project ? (
        <div className="sc-feature">
          {project.poster && (
            <div className="sc-feature-img">
              <Image src={project.poster} alt={`${project.name} demo still`} fill sizes="(max-width: 640px) 92vw, 260px" className="sc-cover" />
            </div>
          )}
          <div className="sc-feature-text">
            <h4 className="sc-h4 sc-h4-lg">{project.name}</h4>
            <p className="sc-text sc-small">{project.summary}</p>
            <button type="button" className="sc-btn sc-btn-gold" onClick={() => d.go({ area: "forge", item: `project:${project.id}` })}>
              Open project <span aria-hidden>→</span>
            </button>
          </div>
        </div>
      ) : (
        <p className="sc-text">
          <span className="sc-label-inline">Project</span> {h.project}
        </p>
      )}
      <p>
        <ExtLink href={PORTFOLIO.devpost} className="sc-textbtn">
          Every win on Devpost <span aria-hidden>↗</span>
        </ExtLink>
      </p>
    </DetailFrame>
  );
}

function JudgesView({ d }: { d: ItemDetail }) {
  return (
    <DetailFrame d={d} item="arena-judges" title={spotNames("arena-judges").name}>
      <RelatedList title="Top prizes" items={topPrizes()} onGo={d.go} />
    </DetailFrame>
  );
}

// ---- mission hall -----------------------------------------------------------------------------

/** The company of a role, when its "where" names one ("Pinterest · San Francisco"), else null. */
function companyOf(where: string): string | null {
  return where.includes("·") ? company(where) : null;
}

const missionItem = (it: string) => itemIndex(it, "role") !== null || it === "mission-bell";

export function MissionBody(props: BodyProps) {
  const { onHighlight } = props;
  const d = useItemDetail("mission", missionItem, props);
  if (d.openItem === "mission-bell") return <BellView d={d} />;
  if (d.openItem) return <RoleView d={d} i={itemIndex(d.openItem, "role")!} />;
  return (
    <div className="sc-body">
      <ol className="sc-list sc-timeline">
        {EXPERIENCE.map((r, i) => {
          const hid = `role:${i}`;
          return (
            <li
              key={hid}
              id={itemDomId(hid)}
              tabIndex={-1}
              className="sc-card sc-role"
              {...openCardProps(d, hid)}
              {...highlightProps(hid, onHighlight)}
            >
              <p className="sc-kicker">{r.when}</p>
              <h4 className="sc-h4 sc-h4-lg">
                <OpenTitle d={d} id={hid}>
                  {r.role}
                </OpenTitle>
              </h4>
              <p className="sc-where">
                {r.link ? (
                  <ExtLink href={r.link} className="sc-inline-link">
                    {r.where} <span aria-hidden>↗</span>
                  </ExtLink>
                ) : (
                  r.where
                )}
              </p>
              <ul className="sc-bullets">
                {r.bullets.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
              {r.badge && (
                <span className="sc-badge">
                  <span aria-hidden className="sc-dot" />
                  {r.badge}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** Every role on one time axis; each row opens its role. */
function RoleTimeline({ d }: { d: ItemDetail }) {
  const [now] = useState(() => new Date());
  const t = roleTimeline(now);
  const years: number[] = [];
  for (let y = t.from; y < t.to; y++) years.push(y);
  return (
    <div className="sc-gantt">
      <ol className="sc-gantt-rows">
        {t.rows.map((row, i) => {
          const r = EXPERIENCE[i];
          return (
            <li key={row.item}>
              <button type="button" className="sc-gantt-row" onClick={() => d.open(row.item)}>
                <span className="sc-gantt-name">
                  {r.role}
                  {companyOf(r.where) && <span className="sc-gantt-co"> · {companyOf(r.where)}</span>}
                </span>
                <span className="sc-gantt-track" aria-hidden>
                  <span
                    className={row.open ? "sc-gantt-bar sc-gantt-open" : "sc-gantt-bar"}
                    style={{ left: `${row.left * 100}%`, width: `${row.width * 100}%` }}
                  />
                </span>
                <span className="sc-sr">{r.when}</span>
              </button>
            </li>
          );
        })}
      </ol>
      <div className="sc-gantt-axis" aria-hidden>
        <span className="sc-gantt-ticks">
          {years.map((y) => (
            <span key={y} style={{ left: `${((y - t.from) / (t.to - t.from)) * 100}%` }}>
              {y}
            </span>
          ))}
        </span>
      </div>
    </div>
  );
}

function RoleView({ d, i }: { d: ItemDetail; i: number }) {
  const r = EXPERIENCE[i];
  const hid = `role:${i}`;
  return (
    <DetailFrame
      d={d}
      item={hid}
      eyebrow={r.when}
      title={r.role}
      labelOf={(id) => {
        const x = EXPERIENCE[itemIndex(id, "role") ?? 0];
        const co = companyOf(x.where);
        return co ? `${x.role} · ${co}` : x.role;
      }}
    >
      <p className="sc-where sc-where-lg">
        {r.link ? (
          <ExtLink href={r.link} className="sc-inline-link">
            {r.where} <span aria-hidden>↗</span>
          </ExtLink>
        ) : (
          r.where
        )}
        {r.badge && (
          <span className="sc-badge">
            <span aria-hidden className="sc-dot" />
            {r.badge}
          </span>
        )}
      </p>
      <div className="sc-objectives">
        <ol>
          {r.bullets.map((b, j) => (
            <li key={b}>
              <span aria-hidden className="sc-objective-no">
                {String(j + 1).padStart(2, "0")}
              </span>
              <span className="sc-text">{b}</span>
            </li>
          ))}
        </ol>
      </div>
    </DetailFrame>
  );
}

function BellView({ d }: { d: ItemDetail }) {
  const now = EXPERIENCE.findIndex((r) => r.badge) >= 0 ? EXPERIENCE.findIndex((r) => r.badge) : 0;
  const r = EXPERIENCE[now];
  return (
    <DetailFrame d={d} item="mission-bell" title={spotNames("mission-bell").name}>
      <div className="sc-card sc-role">
        <p className="sc-kicker">{r.when}</p>
        <h4 className="sc-h4 sc-h4-lg">{r.role}</h4>
        <p className="sc-where">{r.where}</p>
        <button type="button" className="sc-btn sc-btn-gold sc-self-start" onClick={() => d.open(`role:${now}`)}>
          Open <span aria-hidden>→</span>
        </button>
      </div>
      <RoleTimeline d={d} />
    </DetailFrame>
  );
}

// ---- scripture pavilion -----------------------------------------------------------------------

const libraryItem = (it: string) => itemIndex(it, "school") !== null || it === "library-pond";

export function LibraryBody(props: BodyProps) {
  const { onHighlight } = props;
  const d = useItemDetail("library", libraryItem, props);
  if (d.openItem === "library-pond") return <PondView d={d} />;
  if (d.openItem) return <SchoolView d={d} i={itemIndex(d.openItem, "school")!} />;
  return (
    <div className="sc-body">
      <ol className="sc-grid sc-schools">
        {EDUCATION.map((e, i) => {
          const hid = `school:${i}`;
          return (
            <li
              key={hid}
              id={itemDomId(hid)}
              tabIndex={-1}
              className="sc-card sc-school"
              {...openCardProps(d, hid)}
              {...highlightProps(hid, onHighlight)}
            >
              <div className="sc-logo">
                <Image src={e.logo} alt={`${e.school} logo`} width={64} height={64} unoptimized />
              </div>
              <h4 className="sc-h4 sc-h4-lg">
                <OpenTitle d={d} id={hid}>
                  {e.full}
                </OpenTitle>
              </h4>
              <p className="sc-accent">{e.degree}</p>
              <p className="sc-muted">{e.when}</p>
              <div className="sc-notes">
                <p className="sc-text">{e.detail}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function SchoolView({ d, i }: { d: ItemDetail; i: number }) {
  const e = EDUCATION[i];
  return (
    <DetailFrame
      d={d}
      item={`school:${i}`}
      title={e.full}
      labelOf={(id) => EDUCATION[itemIndex(id, "school") ?? 0].full}
    >
      <div className="sc-school-head">
        <div className="sc-logo sc-logo-lg">
          <Image src={e.logo} alt={`${e.school} logo`} width={112} height={112} unoptimized />
        </div>
        <div>
          <p className="sc-accent sc-accent-lg">{e.degree}</p>
          <p className="sc-muted">{e.when}</p>
        </div>
      </div>
      <div className="sc-notes">
        <p className="sc-intro">{e.detail}</p>
      </div>
    </DetailFrame>
  );
}

function PondView({ d }: { d: ItemDetail }) {
  // The climb, bottom to top: the ground floor first.
  const climb = EDUCATION.map((e, i) => ({ e, i })).reverse();
  return (
    <DetailFrame d={d} item="library-pond" title={spotNames("library-pond").name}>
      <div className="sc-related">
        <ol className="sc-climb">
          {climb.map(({ e, i }) => (
            <li key={e.school}>
              <button type="button" className="sc-related-row" onClick={() => d.open(`school:${i}`)}>
                <span className="sc-related-title">{e.full}</span>
                <span className="sc-related-note">
                  {e.degree} · {e.when}
                </span>
                <span aria-hidden className="sc-related-arrow">
                  →
                </span>
              </button>
            </li>
          ))}
        </ol>
      </div>
    </DetailFrame>
  );
}
