"use client";

/**
 * Artifact Forge Peak (projects): the winners on the ring first, every project under "All", the
 * main page's filters and a detail view.
 */
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { PROJECTS, findProject, type Project } from "@/lib/portfolio-data";
import { loadFallbackProject } from "@/lib/project-fallback";
import { onRing, projectAward } from "@/lib/sect/artifacts";
import { PROJECTS_HEAD, PROJECT_YEARS } from "@/lib/sect/content-copy";
import {
  FORGE_FILTERS,
  STANDOUT_IDS,
  filterProjects,
  itemDomId,
  parseFilter,
  projectMedia,
  thingLore,
} from "@/lib/sect/content";
import { withJsApi } from "@/lib/sect/youtube";
import { ExtLink, highlightProps, type BodyProps } from "../ui";
import { useVideoWatch } from "../video-watch";

/** "project:dispatchai" -> "dispatchai" (resolved through aliases), or the raw id for archived ones. */
function projectIdOf(item: string | null): string | null {
  if (!item || !item.startsWith("project:")) return null;
  const raw = item.slice("project:".length);
  return findProject(raw)?.id ?? (raw || null);
}

/** The Forge Hall opens the forge at its altar: the hand-picked standouts. */
const HALL = "forge-hall";

export function ForgeBody({ item, filter: filterArg, version = 0, onHighlight, onNestedChange, onItemChange }: BodyProps) {
  const filterProp = filterArg ?? (item === HALL ? "all" : undefined);
  const initial = parseFilter(filterProp);
  const [filter, setFilter] = useState(initial.filter);
  const [year, setYear] = useState<number | null>(initial.year);
  const [openId, setOpenId] = useState<string | null>(() => projectIdOf(item));
  const [archived, setArchived] = useState<Project | null>(null);
  const [missing, setMissing] = useState<string | null>(null);
  const [seen, setSeen] = useState({ item, filterProp, version });
  const returnTo = useRef<string | null>(null);
  const focusOpened = useRef(false);
  const backBtn = useRef<HTMLButtonElement>(null);

  // A new target from the engine (another artifact clicked, a voice command) replaces the view.
  if (seen.item !== item || seen.filterProp !== filterProp || seen.version !== version) {
    const again = seen.version !== version;
    if (seen.filterProp !== filterProp || (again && filterProp !== undefined)) {
      const f = parseFilter(filterProp);
      setFilter(f.filter);
      setYear(f.year);
    }
    if (seen.item !== item || again) setOpenId(projectIdOf(item));
    setSeen({ item, filterProp, version });
  }

  const known = openId ? findProject(openId) : undefined;
  const open = known ?? (archived && archived.id === openId ? archived : null);

  // Projects outside the curated 15 (the voice agent can name any project in its corpus).
  useEffect(() => {
    if (!openId || findProject(openId)) return;
    let cancelled = false;
    loadFallbackProject(openId).then((p) => {
      if (cancelled) return;
      if (p) setArchived(p);
      else {
        setMissing(openId);
        setOpenId(null);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [openId]);

  const back = () => {
    returnTo.current = openId;
    setOpenId(null);
  };
  const backRef = useRef(back);
  backRef.current = back;

  // Report the project shown (after the first render), so the page can keep the URL in step.
  const reported = useRef(openId);
  const itemChangeRef = useRef(onItemChange);
  itemChangeRef.current = onItemChange;
  useEffect(() => {
    if (reported.current === openId) return;
    reported.current = openId;
    itemChangeRef.current?.(openId ? `project:${openId}` : null);
  }, [openId]);

  // Escape inside the detail steps back to the list first.
  useEffect(() => {
    onNestedChange?.(open ? () => backRef.current() : null);
  }, [open, onNestedChange]);
  useEffect(() => () => onNestedChange?.(null), [onNestedChange]);

  // After leaving a detail, focus goes back to that project's card (or the list heading).
  useEffect(() => {
    if (open || !returnTo.current) return;
    const id = returnTo.current;
    returnTo.current = null;
    const card = document.getElementById(itemDomId(`project:${id}`));
    const btn = card?.querySelector<HTMLElement>("button");
    (btn ?? document.getElementById("sc-forge-list"))?.focus();
  }, [open]);

  // Opening a project from the list (or stepping to the next one) shows the detail from its top
  // and moves focus to its name.
  const openFromList = (id: string) => {
    focusOpened.current = true;
    setOpenId(id);
  };
  useEffect(() => {
    if (!open || !focusOpened.current) return;
    focusOpened.current = false;
    backBtn.current?.scrollIntoView({ block: "start" });
    document.getElementById(itemDomId(`project:${open.id}`))?.focus({ preventScroll: true });
  }, [open]);

  const list = filterProjects(filter, year);
  const pick = (key: string) => {
    setFilter(key);
    setYear(null);
  };
  const pickYear = (y: number) => setYear((cur) => (cur === y ? null : y));
  const curated = filter === "all" && !year;

  if (open) {
    const inList = list.findIndex((p) => p.id === open.id);
    const ring = inList >= 0 ? list : PROJECTS;
    const at = ring.findIndex((p) => p.id === open.id);
    const prev = at > 0 ? ring[at - 1] : null;
    const next = at >= 0 && at < ring.length - 1 ? ring[at + 1] : null;
    return (
      <div className="sc-body">
        <button ref={backBtn} type="button" className="sc-back" onClick={back}>
          <span aria-hidden>←</span> Back
        </button>
        <ProjectDetail project={open} />
        <nav aria-label="Other projects" className="sc-pager">
          {prev ? (
            <button type="button" className="sc-btn" onClick={() => openFromList(prev.id)}>
              <span aria-hidden>←</span> {prev.name}
            </button>
          ) : (
            <span />
          )}
          {next && (
            <button type="button" className="sc-btn" onClick={() => openFromList(next.id)}>
              {next.name} <span aria-hidden>→</span>
            </button>
          )}
        </nav>
      </div>
    );
  }

  const ringView = filter === "ring" && !year;
  // The ring's view also lists, after the winners, the projects that are not on the ring.
  const offRing = ringView ? PROJECTS.filter((p) => !onRing(p.id)) : [];
  const countText = curated
    ? `${list.length}/${PROJECTS.length} standouts`
    : ringView
      ? `${list.length}/${PROJECTS.length} on the ring`
      : `${list.length}/${PROJECTS.length} match`;

  return (
    <div className="sc-body">
      {item === HALL && (
        <div id={itemDomId(HALL)} tabIndex={-1} data-sc-top="" className="sc-hall">
          <h4 className="sc-label sc-label-gold">{thingLore(HALL)?.name}</h4>
        </div>
      )}
      {missing && (
        <p className="sc-note" role="status">
          Couldn&apos;t find project &ldquo;{missing}&rdquo;.
        </p>
      )}
      <div className="sc-filters" role="group" aria-label="Filter projects">
        {FORGE_FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            aria-pressed={filter === f.key}
            className="sc-filter"
            onClick={() => pick(f.key)}
          >
            {f.label}
          </button>
        ))}
        {PROJECT_YEARS.map((y) => (
          <button key={y} type="button" aria-pressed={year === y} className="sc-filter" onClick={() => pickYear(y)}>
            {y}
          </button>
        ))}
      </div>
      <p className="sc-count" aria-live="polite">
        {countText}
      </p>
      <ul id="sc-forge-list" tabIndex={-1} className="sc-grid sc-projects" aria-label="Projects">
        {list.map((p) => (
          <ProjectCard
            key={p.id}
            project={p}
            standout={STANDOUT_IDS.includes(p.id)}
            onOpen={() => openFromList(p.id)}
            onHighlight={onHighlight}
          />
        ))}
      </ul>
      {list.length === 0 && <p className="sc-note">No project matches this filter.</p>}
      {ringView && offRing.length > 0 && (
        <section aria-labelledby="sc-forge-more" className="sc-forge-more">
          <h4 id="sc-forge-more" className="sc-label">
            More projects
          </h4>
          <ul className="sc-grid sc-projects" aria-label="More projects">
            {offRing.map((p) => (
              <ProjectCard
                key={p.id}
                project={p}
                standout={STANDOUT_IDS.includes(p.id)}
                onOpen={() => openFromList(p.id)}
                onHighlight={onHighlight}
              />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function ProjectCard({
  project: p,
  standout,
  onOpen,
  onHighlight,
}: {
  project: Project;
  standout: boolean;
  onOpen: () => void;
  onHighlight?: (id: string | null) => void;
}) {
  const hid = `project:${p.id}`;
  const award = projectAward(p.id);
  return (
    <li id={itemDomId(hid)} tabIndex={-1} className="sc-card sc-proj" onClick={onOpen} {...highlightProps(hid, onHighlight)}>
      <div className="sc-proj-media">
        {p.poster ? (
          <Image src={p.poster} alt={`${p.name} demo still`} fill sizes="(max-width: 640px) 92vw, 300px" className="sc-cover" />
        ) : (
          <span aria-hidden className="sc-proj-blank">
            /{p.id}
          </span>
        )}
        {award && <span className="sc-award">★ {award}</span>}
        {p.poster && <span className="sc-proj-id">/{p.id}</span>}
      </div>
      <div className="sc-proj-text">
        <h4 className="sc-h4">
          <button
            type="button"
            className="sc-proj-open"
            onClick={(e) => {
              e.stopPropagation();
              onOpen();
            }}
          >
            {p.name}
          </button>
        </h4>
        <p className="sc-text sc-small">{p.summary}</p>
        <ul className="sc-tags" aria-label="Tags">
          {p.tags.map((t) => (
            <li key={t}>#{t}</li>
          ))}
          {!!p.year && <li className="sc-tag-year">{p.year}</li>}
          {standout && <li className="sc-tag-standout">Standout</li>}
        </ul>
      </div>
    </li>
  );
}

function DemoMedia({ project: p }: { project: Project }) {
  const { embed, image } = projectMedia(p);
  const [play, setPlay] = useState(false);
  if (embed && play) return <DemoVideo src={`${embed}&autoplay=1`} title={`${p.name} demo video`} />;
  if (embed) {
    // The player loads only when asked: the 3D scene is already using the GPU.
    return (
      <button type="button" className="sc-media-play" onClick={() => setPlay(true)}>
        {p.poster && <Image src={p.poster} alt="" fill sizes="(max-width: 640px) 100vw, 860px" className="sc-cover" />}
        <span className="sc-play-badge">
          <span aria-hidden>▶</span> Play demo
        </span>
      </button>
    );
  }
  if (image) {
    // A Devpost gallery still on a CDN, shown as is (like the main page's detail view).
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={image} alt={p.name} className="sc-cover" loading="lazy" />;
  }
  if (p.poster) {
    return <Image src={p.poster} alt={`${p.name} demo still`} fill sizes="(max-width: 640px) 100vw, 860px" className="sc-cover" />;
  }
  return (
    <div className="sc-media-empty">
      <span className="sc-media-id">/{p.id}</span>
      <span className="sc-note">{PROJECTS_HEAD.noMedia}</span>
    </div>
  );
}

/**
 * The YouTube player. It reports its state to the page (enablejsapi, this origin), so the sect's music
 * steps aside while it plays (../video-watch.ts).
 */
function DemoVideo({ src, title }: { src: string; title: string }) {
  const ref = useRef<HTMLIFrameElement>(null);
  const [url] = useState(() => withJsApi(src, typeof window === "undefined" ? null : window.location.origin));
  useVideoWatch(ref);
  return (
    <iframe
      ref={ref}
      src={url}
      title={title}
      allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture"
      allowFullScreen
      className="sc-media-frame"
    />
  );
}

function ProjectDetail({ project: p }: { project: Project }) {
  const { demoLink, embed, image } = projectMedia(p);
  const hid = `project:${p.id}`;
  const award = projectAward(p.id);
  return (
    <article className="sc-detail" aria-labelledby={itemDomId(hid)}>
      {award && (
        <p className="sc-eyebrow">
          <span aria-hidden className="sc-diamond" />★ {award}
        </p>
      )}
      <h3 id={itemDomId(hid)} tabIndex={-1} data-sc-top="" className="sc-h3">
        {p.name}
      </h3>
      <p className="sc-intro">{p.summary}</p>

      <div className="sc-media">
        <DemoMedia key={p.id} project={p} />
      </div>

      <div className="sc-detail-grid">
        <div>
          <h4 className="sc-label">{PROJECTS_HEAD.story}</h4>
          <p className="sc-text">{p.long || p.summary}</p>
          {p.role && (
            <div className="sc-row">
              <span className="sc-label">{PROJECTS_HEAD.role}</span>
              <span className="sc-text">{p.role}</span>
            </div>
          )}
          {p.stack && (
            <div className="sc-row">
              <span className="sc-label">{PROJECTS_HEAD.stack}</span>
              <ul className="sc-pills" aria-label="Stack">
                {p.stack.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div className="sc-detail-side">
          {image && p.poster && (
            <figure className="sc-poster">
              <div className="sc-poster-img">
                <Image src={p.poster} alt={`${p.name} demo still`} fill sizes="(max-width: 860px) 92vw, 320px" className="sc-cover" />
              </div>
            </figure>
          )}
          <dl className="sc-facts">
            {!!p.year && (
              <>
                <dt>{PROJECTS_HEAD.year}</dt>
                <dd>{p.year}</dd>
              </>
            )}
            <dt>{PROJECTS_HEAD.id}</dt>
            <dd>/{p.id}</dd>
            <dt>{PROJECTS_HEAD.tags}</dt>
            <dd>
              <ul className="sc-tags">
                {p.tags.map((t) => (
                  <li key={t}>#{t}</li>
                ))}
              </ul>
            </dd>
          </dl>
          <ul className="sc-links">
            {demoLink && embed && (
              <li>
                <ExtLink href={demoLink} className="sc-linkrow">
                  <span aria-hidden className="sc-linkicon">
                    ▶
                  </span>
                  Watch on YouTube
                </ExtLink>
              </li>
            )}
            {demoLink && !embed && (
              <li>
                <ExtLink href={demoLink} className="sc-linkrow">
                  <span aria-hidden className="sc-linkicon">
                    ▶
                  </span>
                  {PROJECTS_HEAD.demoMedia}
                </ExtLink>
              </li>
            )}
            {p.projectUrl && (
              <li>
                <ExtLink href={p.projectUrl} className="sc-linkrow">
                  <span aria-hidden className="sc-linkicon">
                    ↗
                  </span>
                  {PROJECTS_HEAD.liveProject}
                </ExtLink>
              </li>
            )}
            {p.github && (
              <li>
                <ExtLink href={p.github} className="sc-linkrow">
                  <span aria-hidden className="sc-linkicon">
                    {"</>"}
                  </span>
                  {PROJECTS_HEAD.source}
                </ExtLink>
              </li>
            )}
          </ul>
        </div>
      </div>
    </article>
  );
}
