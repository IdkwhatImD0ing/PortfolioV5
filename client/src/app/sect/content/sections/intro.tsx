"use client";

/** Mountain Gate (hero) and Heart-Mirror Terrace (about). */
import { SUGGESTIONS } from "@/components/voice-orb/suggestions";
import { PORTFOLIO } from "@/lib/portfolio-data";
import { ABOUT_CARDS, HERO, RESUME_HEAD, TOPBAR } from "@/lib/sect/content-copy";
import { HERO_CHIP_TARGETS, commandTarget, itemDomId, type ContentTarget } from "@/lib/sect/content";
import { MIRROR_CARD_THINGS, mirrorCardIndex } from "@/lib/sect/explore";
import { DetailFrame, OpenTitle, openCardProps, spotNames, useItemDetail, type ItemDetail } from "../detail";
import { Runs, TalkButton, highlightProps, useSfTime, type BodyProps } from "../ui";

/** The hero's question chips: each goes to the place in the sect that answers it. */
function QuestionChips({ onGo }: { onGo: (t: ContentTarget) => void }) {
  return (
    <ul className="sc-chips">
      {HERO_CHIP_TARGETS.map(({ chip, target }) => (
        <li key={chip}>
          <button type="button" className="sc-chip" onClick={() => onGo(target)}>
            <span aria-hidden className="sc-quote">
              &ldquo;
            </span>
            <span>{chip}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

/** The voice orb's starter suggestions, each moving you to its answer. */
function OrbSuggestions({ onGo }: { onGo: (t: ContentTarget) => void }) {
  return (
    <ul className="sc-chips">
      {SUGGESTIONS.map((s) => {
        const target = commandTarget(s.cmd);
        return (
          <li key={s.you}>
            <button type="button" className="sc-chip" disabled={!target} onClick={() => target && onGo(target)}>
              <span aria-hidden className="sc-quote">
                &ldquo;
              </span>
              <span>{s.you}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

const gateItem = (it: string) => it === "gate-lions" || it === "gate-swords";

/** The hero intro without its last two sentences ("This page is one of those builds. Go on, ask it something."). */
const INTRO = HERO.intro.map((r) => ({ ...r, t: r.t.replace(/ This page is one of those builds\..*$/, "") }));

export function GateBody(props: BodyProps) {
  const { onNavigate, onTalk, onHighlight } = props;
  const time = useSfTime(TOPBAR.timeZone);
  const d = useItemDetail("gate", gateItem, props);
  if (d.openItem) return <GateThingView d={d} id={d.openItem} onTalk={onTalk} />;
  return (
    <div className="sc-body">
      <div className="sc-head">
        <p className="sc-intro">
          <Runs runs={INTRO} />
        </p>
      </div>

      <p className="sc-meta">
        <span>
          {TOPBAR.cityPrefix} · <time>{time}</time>
        </span>
      </p>
      <p className="sc-tagline" {...highlightProps("gate", onHighlight)}>
        {PORTFOLIO.tagline}
      </p>

      <div className="sc-actions">
        <TalkButton onTalk={onTalk} label="Talk to the portfolio" />
        <button type="button" className="sc-btn" onClick={() => onNavigate({ area: "scroll", item: null })}>
          {HERO.viewResume}
        </button>
        <a href="/resume.pdf" download={RESUME_HEAD.downloadName} type="application/pdf" className="sc-btn">
          {HERO.downloadPdf}
          <span className="sc-btn-note">{HERO.pdfSize}</span>
        </a>
      </div>

      <section id={itemDomId("gate-lions")} tabIndex={-1} className="sc-block" {...highlightProps("gate-lions", onHighlight)}>
        <QuestionChips onGo={onNavigate} />
      </section>
    </div>
  );
}

function GateThingView({ d, id, onTalk }: { d: ItemDetail; id: string; onTalk?: () => void }) {
  const lions = id === "gate-lions";
  return (
    <DetailFrame d={d} item={id} title={spotNames(id).name}>
      {lions ? (
        <div className="sc-related">
          <QuestionChips onGo={d.go} />
        </div>
      ) : (
        <div className="sc-related">
          <div className="sc-actions">
            <TalkButton onTalk={onTalk} label="Talk to the portfolio" />
          </div>
          <OrbSuggestions onGo={d.go} />
        </div>
      )}
    </DetailFrame>
  );
}

const mirrorItem = (it: string) => mirrorCardIndex(it) >= 0;

export function MirrorBody(props: BodyProps) {
  const { onHighlight } = props;
  const d = useItemDetail("mirror", mirrorItem, props);
  if (d.openItem) return <ReflectionView d={d} id={d.openItem} />;
  return (
    <div className="sc-body">
      <ol className="sc-list sc-about">
        {ABOUT_CARDS.map((c, i) => {
          const thing = MIRROR_CARD_THINGS[i];
          return (
            <li
              key={c.num}
              id={thing ? itemDomId(thing) : undefined}
              tabIndex={thing ? -1 : undefined}
              className="sc-card"
              {...(thing ? openCardProps(d, thing) : {})}
              {...highlightProps(thing ?? "mirror", onHighlight)}
            >
              <h4 className="sc-h4 sc-h4-lg">
                {thing ? (
                  <OpenTitle d={d} id={thing}>
                    {c.title}
                  </OpenTitle>
                ) : (
                  c.title
                )}
              </h4>
              <p className="sc-text">{c.body}</p>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function ReflectionView({ d, id }: { d: ItemDetail; id: string }) {
  const c = ABOUT_CARDS[mirrorCardIndex(id)];
  return (
    <DetailFrame
      d={d}
      item={id}
      title={c.title}
      labelOf={(x) => ABOUT_CARDS[mirrorCardIndex(x)]?.title ?? x}
    >
      <p className="sc-intro">{c.body}</p>
    </DetailFrame>
  );
}
