"use client";

/** Stele Forest of Techniques (skills) and the Grand Sect-Protecting Formation (architecture). */
import { useState } from "react";
import { SKILLS_LINE } from "@/lib/portfolio-data";
import { highlightJs } from "@/lib/highlight";
import { ARCH_FLOW, ARCH_HEAD, ARCH_SNIPPET, ARCH_STACK } from "@/lib/sect/content-copy";
import { formationItems, itemDomId, itemIndex, skillGroups } from "@/lib/sect/content";
import { skillEvidence, stackSteps } from "@/lib/sect/explore";
import { DetailFrame, OpenTitle, RelatedList, openCardProps, useItemDetail, type ItemDetail } from "../detail";
import { highlightProps, type BodyProps } from "../ui";

// ---- steles -----------------------------------------------------------------------------------

const stelesItem = (it: string) => itemIndex(it, "skills") !== null;

/** The skills sentence with some of its words lit. */
function SkillsLine({ lit, id, onHighlight }: { lit: number[]; id?: string; onHighlight?: (id: string | null) => void }) {
  return (
    <p id={id} tabIndex={id ? -1 : undefined} className="sc-skills-line" {...highlightProps(id ? "steles" : null, onHighlight)}>
      {SKILLS_LINE.map((w, i) => (
        <span key={i} className={[w.tag ? "sc-em" : "", lit.includes(i) ? "sc-lit" : ""].filter(Boolean).join(" ") || undefined}>
          {w.w}{" "}
        </span>
      ))}
    </p>
  );
}

export function StelesBody(props: BodyProps) {
  const { onHighlight } = props;
  const d = useItemDetail("steles", stelesItem, props);
  const groups = skillGroups();
  const [lit, setLit] = useState<number | null>(null);
  if (d.openItem) return <SkillView d={d} g={itemIndex(d.openItem, "skills")!} />;
  const litWords = lit === null ? [] : groups[lit].words;
  const hl = (id: string, g: number | null) => ({
    onMouseEnter: () => {
      setLit(g);
      onHighlight?.(id);
    },
    onMouseLeave: () => {
      setLit(null);
      onHighlight?.(null);
    },
    onFocus: () => {
      setLit(g);
      onHighlight?.(id);
    },
    onBlur: () => {
      setLit(null);
      onHighlight?.(null);
    },
  });
  return (
    <div className="sc-body">
      <SkillsLine lit={litWords} id={itemDomId("steles")} onHighlight={onHighlight} />
      <ol className="sc-list sc-stele-rows">
        {groups.map((g) => {
          const hid = `skills:${g.index}`;
          return (
            <li key={hid} id={itemDomId(hid)} tabIndex={-1} className="sc-card sc-stele" {...openCardProps(d, hid)} {...hl(hid, g.index)}>
              <span className="sc-stele-word">
                <OpenTitle d={d} id={hid}>
                  {g.label}
                </OpenTitle>
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function SkillView({ d, g }: { d: ItemDetail; g: number }) {
  const group = skillGroups()[g];
  const evidence = skillEvidence(g, 3);
  return (
    <DetailFrame
      d={d}
      item={`skills:${g}`}
      title={group.label.charAt(0).toUpperCase() + group.label.slice(1)}
    >
      <RelatedList title="In the work" items={evidence} onGo={d.go} />
    </DetailFrame>
  );
}

// ---- formation --------------------------------------------------------------------------------

const TOKEN_CLASS: Record<string, string> = {
  "text-muted italic": "sc-tok-comment",
  "text-cyan": "sc-tok-string",
  "text-magenta": "sc-tok-keyword",
  "text-accent": "sc-tok-call",
  "text-primary": "sc-tok-type",
  "text-ink": "sc-tok-ident",
  "text-ink-soft": "sc-tok-punct",
};

const SNIPPET_TOKENS = highlightJs(ARCH_SNIPPET);

function Snippet() {
  return (
    <pre className="sc-code" tabIndex={0} aria-label="Navigation code snippet">
      <code>
        {SNIPPET_TOKENS.map((t, i) => (
          <span key={i} className={TOKEN_CLASS[t.cls] || undefined}>
            {t.text}
          </span>
        ))}
      </code>
    </pre>
  );
}

const formationItem = (it: string) => itemIndex(it, "arch") !== null;
const STACK_ITEM = "arch:6";
const CODE_ITEM = "arch:7";
/** Flow steps the code snippet carries out: the tool call, the bus, the sections. */
const CODE_STEPS = [2, 3, 4];

export function FormationBody(props: BodyProps) {
  const { onHighlight } = props;
  const d = useItemDetail("formation", formationItem, props);
  if (d.openItem === STACK_ITEM) return <StackView d={d} />;
  if (d.openItem === CODE_ITEM) return <CodeView d={d} />;
  if (d.openItem) return <StepView d={d} i={itemIndex(d.openItem, "arch")!} />;
  return (
    <div className="sc-body">
      <div className="sc-head">
        <p className="sc-intro">{ARCH_HEAD.intro}</p>
      </div>
      <ol className="sc-grid sc-flow">
        {ARCH_FLOW.map((f, i) => {
          const hid = `arch:${i}`;
          return (
            <li key={f.k} id={itemDomId(hid)} tabIndex={-1} className="sc-card sc-step" {...openCardProps(d, hid)} {...highlightProps(hid, onHighlight)}>
              <span className="sc-step-k">{f.k}</span>
              <h4 className="sc-h4">
                <OpenTitle d={d} id={hid}>
                  {f.title}
                </OpenTitle>
              </h4>
              <p className="sc-text sc-small">{f.body}</p>
            </li>
          );
        })}
      </ol>
      <div className="sc-arch-split">
        <section id={itemDomId(STACK_ITEM)} tabIndex={-1} aria-labelledby="sc-arch-stack" {...highlightProps(STACK_ITEM, onHighlight)}>
          <h4 id="sc-arch-stack" className="sc-label sc-list-title">
            <OpenTitle d={d} id={STACK_ITEM}>
              Stack
            </OpenTitle>
          </h4>
          <StackGrid />
        </section>
        <section id={itemDomId(CODE_ITEM)} tabIndex={-1} aria-labelledby="sc-arch-code" {...highlightProps(CODE_ITEM, onHighlight)}>
          <h4 id="sc-arch-code" className="sc-label sc-list-title">
            <OpenTitle d={d} id={CODE_ITEM}>
              Code
            </OpenTitle>
          </h4>
          <Snippet />
        </section>
      </div>
    </div>
  );
}

function StackGrid({ d }: { d?: ItemDetail }) {
  return (
    <div className="sc-grid sc-stack">
      {ARCH_STACK.map((s) => (
        <div key={s.group} className="sc-card">
          <h5 className="sc-label sc-label-gold">{s.group}</h5>
          <ul className="sc-bullets sc-small">
            {s.items.map((it) => (
              <li key={it}>{it}</li>
            ))}
          </ul>
          {d && (
            <ul className="sc-chips sc-chips-sm" aria-label={`Steps ${s.group} powers`}>
              {stackSteps(s.group).map((i) => (
                <li key={i}>
                  <button type="button" className="sc-chip" onClick={() => d.open(`arch:${i}`)}>
                    {ARCH_FLOW[i].k} {ARCH_FLOW[i].title}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

/** The six steps in a row, the ones given lit; each opens its pillar. */
function FlowChain({ d, lit }: { d: ItemDetail; lit: number[] }) {
  return (
    <ol className="sc-chain" aria-label="The flow, voice to page">
      {ARCH_FLOW.map((f, i) => (
        <li key={f.k}>
          <button type="button" className="sc-chain-step" aria-current={lit.includes(i) ? "step" : undefined} onClick={() => d.open(`arch:${i}`)}>
            <span className="sc-step-k">{f.k}</span>
            <span>{f.title}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}

const pillarLabel = (id: string) => formationItems()[itemIndex(id, "arch") ?? 0].title;

function StepView({ d, i }: { d: ItemDetail; i: number }) {
  const f = ARCH_FLOW[i];
  return (
    <DetailFrame
      d={d}
      item={`arch:${i}`}
      title={f.title}
      labelOf={pillarLabel}
    >
      <p className="sc-intro">{f.body}</p>
      <FlowChain d={d} lit={[i]} />
      {i === 4 && (
        <p className="sc-note">On this 3D page the camera flies to the place the agent names, and the place opens.</p>
      )}
      {i === 3 && <Snippet />}
    </DetailFrame>
  );
}

function StackView({ d }: { d: ItemDetail }) {
  return (
    <DetailFrame d={d} item={STACK_ITEM} title="Stack" labelOf={pillarLabel}>
      <StackGrid d={d} />
    </DetailFrame>
  );
}

function CodeView({ d }: { d: ItemDetail }) {
  return (
    <DetailFrame d={d} item={CODE_ITEM} title="Code" labelOf={pillarLabel}>
      <Snippet />
      <FlowChain d={d} lit={CODE_STEPS} />
    </DetailFrame>
  );
}
