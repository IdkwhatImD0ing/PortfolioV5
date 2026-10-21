"use client";

/** Cave Abode (personal) and Moon-Gazing Summit (footer / contact). */
import Image from "next/image";
import { PERSONAL_FACTS, PORTFOLIO } from "@/lib/portfolio-data";
import { FOOTER, PERSONAL_HEAD } from "@/lib/sect/content-copy";
import { AREAS } from "@/lib/sect/areas";
import { SECTION_NAMES, factRuns, itemDomId, itemIndex, shortFact, stripTags } from "@/lib/sect/content";
import { DetailFrame, OpenTitle, openCardProps, spotNames, useItemDetail, type ItemDetail } from "../detail";
import { ExtLink, TalkButton, highlightProps, type BodyProps } from "../ui";

/** A personal fact with its bold words. */
function FactText({ line }: { line: string }) {
  return (
    <>
      {factRuns(line).map((r, j) =>
        r.b ? (
          <b key={j} className="sc-strong">
            {r.t}
          </b>
        ) : (
          <span key={j}>{r.t}</span>
        ),
      )}
    </>
  );
}

function Portrait({ onHighlight, small = false }: { onHighlight?: (id: string | null) => void; small?: boolean }) {
  return (
    <figure className={small ? "sc-portrait sc-portrait-sm" : "sc-portrait"} {...highlightProps("abode", onHighlight)}>
      <div className="sc-portrait-img">
        <Image src={PERSONAL_HEAD.photo} alt={PERSONAL_HEAD.photoAlt} fill sizes="(max-width: 640px) 92vw, 340px" className="sc-cover" />
      </div>
      {!small && <figcaption className="sc-label">{PERSONAL_HEAD.photoCaption}</figcaption>}
    </figure>
  );
}

const abodeItem = (it: string) => itemIndex(it, "fact") !== null || it === "abode-cranes";

/** PERSONAL_FACTS index of the crane on the abode's lawn (export_web.py ABODE_FACTS "Crane"). */
const CRANE_FACT = 5;

export function AbodeBody(props: BodyProps) {
  const { onHighlight, onTalk } = props;
  const d = useItemDetail("abode", abodeItem, props);
  if (d.openItem === "abode-cranes") return <CranesView d={d} />;
  if (d.openItem) return <FactView d={d} i={itemIndex(d.openItem, "fact")!} />;
  return (
    <div className="sc-body">
      <div className="sc-abode">
        <Portrait onHighlight={onHighlight} />
        <div>
          <ul className="sc-list sc-facts-list">
            {PERSONAL_FACTS.map((f, i) => {
              const hid = `fact:${i}`;
              return (
                <li key={hid} id={itemDomId(hid)} tabIndex={-1} className="sc-card sc-fact" {...openCardProps(d, hid)} {...highlightProps(hid, onHighlight)}>
                  <span aria-hidden className="sc-fact-icon">
                    {f.icon}
                  </span>
                  <span className="sc-text">
                    <OpenTitle d={d} id={hid}>
                      <FactText line={f.line} />
                    </OpenTitle>
                  </span>
                </li>
              );
            })}
          </ul>
          {onTalk && (
            <div className="sc-actions">
              <TalkButton onTalk={onTalk} label="Ask the portfolio" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FactView({ d, i }: { d: ItemDetail; i: number }) {
  const f = PERSONAL_FACTS[i];
  return (
    <DetailFrame
      d={d}
      item={`fact:${i}`}
      title={<span className="sc-fact-title">{shortFact(f.line)}</span>}
      labelOf={(id) => shortFact(PERSONAL_FACTS[itemIndex(id, "fact") ?? 0].line)}
    >
      <div className="sc-abode sc-abode-item">
        <Portrait small />
        {stripTags(f.line).replace(/\.$/, "") !== shortFact(f.line) && (
          <div className="sc-fact-big">
            <span aria-hidden className="sc-fact-icon">
              {f.icon}
            </span>
            <p className="sc-intro">
              <FactText line={f.line} />
            </p>
          </div>
        )}
      </div>
    </DetailFrame>
  );
}

/** The pair circling over the abode, and the way to the crane that stayed on the lawn. */
function CranesView({ d }: { d: ItemDetail }) {
  const id = "abode-cranes";
  return (
    <DetailFrame d={d} item={id} title={spotNames(id).name}>
      <div className="sc-related">
        <div className="sc-actions">
          <button type="button" className="sc-btn" onClick={() => d.go({ area: "abode", item: `fact:${CRANE_FACT}` })}>
            {shortFact(PERSONAL_FACTS[CRANE_FACT].line)} <span aria-hidden>→</span>
          </button>
        </div>
      </div>
    </DetailFrame>
  );
}

const summitItem = (it: string) => it === "summit-arch" || it === "summit-cranes";

export function SummitBody(props: BodyProps) {
  const { onTalk, onHighlight } = props;
  const d = useItemDetail("summit", summitItem, props);
  if (d.openItem === "summit-cranes") return <MoonCranesView d={d} onTalk={onTalk} />;
  if (d.openItem) return <ArchView d={d} />;
  const social = [
    { label: "GitHub", href: PORTFOLIO.github },
    { label: "LinkedIn", href: PORTFOLIO.linkedin },
    { label: "Devpost", href: PORTFOLIO.devpost },
  ];
  return (
    <div className="sc-body">
      <div className="sc-grid sc-contact">
        <section aria-labelledby="sc-contact-direct">
          <h4 id="sc-contact-direct" className="sc-label">
            {FOOTER.direct}
          </h4>
          <ul className="sc-links">
            <li>
              <a href={`mailto:${PORTFOLIO.email}`} className="sc-linkrow">
                {PORTFOLIO.email} <span aria-hidden>↗</span>
              </a>
            </li>
            <li {...highlightProps("moon", onHighlight)}>
              <TalkButton id={itemDomId("moon")} onTalk={onTalk} label={FOOTER.tapOrb} className="sc-linkrow sc-linkrow-btn" />
            </li>
          </ul>
        </section>
        <section aria-labelledby="sc-contact-elsewhere">
          <h4 id="sc-contact-elsewhere" className="sc-label">
            {FOOTER.elsewhere}
          </h4>
          <ul className="sc-links">
            {social.map((s) => (
              <li key={s.label}>
                <ExtLink href={s.href} className="sc-linkrow">
                  {s.label} <span aria-hidden>↗</span>
                </ExtLink>
              </li>
            ))}
          </ul>
        </section>
      </div>
      <p className="sc-label sc-copyright">
        {FOOTER.copyright}
        <span aria-hidden> · </span>
        <span>{PORTFOLIO.location}</span>
      </p>
    </div>
  );
}

/** The two cranes flying for the moon, and the way to say hello. */
function MoonCranesView({ d, onTalk }: { d: ItemDetail; onTalk?: () => void }) {
  const id = "summit-cranes";
  return (
    <DetailFrame d={d} item={id} title={spotNames(id).name}>
      <div className="sc-related">
        <ul className="sc-links">
          <li>
            <a href={`mailto:${PORTFOLIO.email}`} className="sc-linkrow">
              {PORTFOLIO.email} <span aria-hidden>↗</span>
            </a>
          </li>
        </ul>
        {onTalk && (
          <div className="sc-actions">
            <TalkButton onTalk={onTalk} label={FOOTER.tapOrb} />
          </div>
        )}
      </div>
    </DetailFrame>
  );
}

/** Every path in the sect from the top of the climb: each area and its section. */
function ArchView({ d }: { d: ItemDetail }) {
  return (
    <DetailFrame d={d} item="summit-arch" title={spotNames("summit-arch").name}>
      <div className="sc-related">
        <ol className="sc-related-list">
          {AREAS.map((a, i) => (
            <li key={a.id}>
              <button type="button" className="sc-related-row" onClick={() => d.go({ area: a.id, item: null })}>
                <span className="sc-related-place">{String(i + 1).padStart(2, "0")}</span>
                <span className="sc-related-title">{a.label}</span>
                <span className="sc-related-note">{SECTION_NAMES[a.id]}</span>
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
