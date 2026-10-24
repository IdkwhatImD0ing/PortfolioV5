/**
 * The inventory of everything the one-page portfolio showed or let a visitor do (the old page: the
 * src/app/page.tsx and section components the sect replaced as the home page, now archived), and
 * where each piece lives in the sect. It is the record that the move lost nothing. One source for
 * two checks:
 *   - content-completeness.test.tsx renders every reader and the one-page view and asserts that
 *     every `texts` and `urls` value of every carried entry is there;
 *   - content-inventory.test.ts checks docs/sect-content-inventory.md is inventoryMarkdown().
 * Regenerate the doc after changing this file:
 *   SECT_WRITE_INVENTORY=1 pnpm exec vitest run src/lib/sect/content-inventory.test.ts
 */
import { SUGGESTIONS } from "@/components/voice-orb/suggestions";
import {
  EDUCATION,
  EXPERIENCE,
  HACKATHONS,
  PERSONAL_FACTS,
  PORTFOLIO,
  PROJECTS,
  SKILLS_LINE,
} from "@/lib/portfolio-data";
import { AREAS, areaInfo, type AreaId } from "./areas";
import { FORGE_RING } from "./artifacts";
import {
  ABOUT_CARDS,
  ABOUT_HEAD,
  ARCH_FLOW,
  ARCH_HEAD,
  ARCH_SNIPPET,
  ARCH_STACK,
  EDUCATION_HEAD,
  EXPERIENCE_HEAD,
  FOOTER,
  HACKATHONS_HEAD,
  HACKATHON_STATS,
  HERO,
  HERO_CHIPS,
  PERSONAL_HEAD,
  PROJECTS_HEAD,
  PROJECT_FILTERS,
  PROJECT_YEARS,
  RESUME_GLANCE,
  RESUME_HEAD,
  RESUME_LINKS,
  RESUME_STATS,
  TOPBAR,
  VOICE_ORB,
  type Run,
} from "./content-copy";
import {
  SECTION_NAMES,
  areaSummary,
  hackathonTitle,
  heroChipTarget,
  projectMedia,
  skillGroups,
  stripTags,
} from "./content";

export type InventoryStatus =
  /** In the sect with the same content. */
  | "carried"
  /** In the sect with the same content, presented or operated differently (see note). */
  | "adapted"
  /** Belongs to the 3D page (src/app/sect/experience), not the content layer. */
  | "engine"
  /** Not in the sect (see note for why). */
  | "dropped";

export interface InventoryEntry {
  id: string;
  /** Old page's section or component. */
  section: string;
  what: string;
  status: InventoryStatus;
  /** Area whose reader shows it (and the one-page view's section). */
  area?: AreaId;
  /** Shown in this project's detail view (forge reader opened at project:<id>). */
  project?: string;
  /** Where it lives in the sect and how a visitor reaches it. */
  where: string;
  /** Strings that must appear in the rendered reader and the one-page view. */
  texts?: string[];
  /** href / src values that must appear. */
  urls?: string[];
  note?: string;
}

const runsText = (runs: Run[]) => runs.map((r) => r.t).join("");
const toEmbedLabel = (url: string) => /youtu/.test(url);

/** How a visitor gets to an area's reader (printed once per section in the doc). */
export function areaReach(area: AreaId): string {
  const s = areaSummary(area);
  const info = areaInfo(area);
  return `Scroll (or use the area rail) to the ${info.label} and press "${s.action}" on its panel; or Previous / Next from a neighbouring reader; or "${SECTION_NAMES[area]}" in the one-page view (#${info.sectionId}).`;
}

/** Where an entry lives: the area's reader, plus anything specific to the entry. */
function reach(area: AreaId, extra?: string): string {
  const base = `${areaInfo(area).label} reader.`;
  return extra ? `${base} ${extra}` : base;
}

export function contentInventory(): InventoryEntry[] {
  const out: InventoryEntry[] = [];
  const add = (e: Omit<InventoryEntry, "id">) => {
    out.push({ id: `C-${String(out.length + 1).padStart(3, "0")}`, ...e });
  };

  // ---- page shell -------------------------------------------------------------------------------
  const shell = "Page shell (layout.tsx, page.tsx)";
  add({
    section: shell,
    what: "Document title and description, Open Graph and Twitter cards",
    status: "adapted",
    where: `The root layout (src/app/layout.tsx) sets the site's title ("${PORTFOLIO.name} · Sun Moon Divine Sect"), description, Open Graph and Twitter cards; the share image is a frame of the Mountain Gate (public/og-image.jpg). While a reader is open the tab names its section. The description's facts (Pinterest, 36 wins, talk to it) are in the gate reader.`,
    note: "Same person and facts, worded for the sect. The sect is the indexed home page; under the flight the server renders the whole portfolio as text (app/sect/summary.tsx) for crawlers and for visitors without JavaScript.",
  });
  add({
    section: shell,
    what: "JSON-LD Person record (Software Engineer II at Pinterest; alumni of USC and UC Santa Cruz; knows AI, ML, conversational AI, voice agents)",
    status: "carried",
    where: "The root layout's application/ld+json block, now also linking GitHub, LinkedIn and Devpost (sameAs). The same facts are visible in the Mission Hall (role) and Scripture Pavilion (schools).",
  });
  add({
    section: shell,
    what: "Favicons, web manifest, theme colour",
    status: "carried",
    where: "The root layout's, as before.",
  });
  add({
    section: "Top bar",
    what: `Name pill "${TOPBAR.name}"`,
    status: "carried",
    area: "gate",
    texts: [TOPBAR.name],
    where: reach("gate", "In the intro line; also the one-page view's title."),
  });
  add({
    section: "Top bar",
    what: `San Francisco clock "${TOPBAR.cityPrefix} · HH:MM" (America/Los_Angeles, 24 h)`,
    status: "carried",
    area: "gate",
    texts: [`${TOPBAR.cityPrefix} ·`],
    where: reach("gate"),
  });
  add({
    section: "Scroll progress bar",
    what: "Thin bar at the top showing how far down the page you are",
    status: "engine",
    where: "The 3D page's area rail shows where you are in the flight.",
  });
  add({
    section: "Custom cursor, background stage, speech waveform",
    what: "Decorative cursor ring, gradient backdrop, animated waveform beside the hero eyebrow",
    status: "dropped",
    where: "Not in the sect.",
    note: "Decoration only. The 3D scene is the backdrop and the sect uses the normal cursor.",
  });
  add({
    section: "Backend warm-up",
    what: "Pings the voice backend on load so a call starts fast",
    status: "engine",
    where: "Only matters when the 3D page offers a voice call (onTalk).",
  });
  add({
    section: "Hash landing and deep links",
    what: "Landing on /#section or /#project/<id> keeps the target in view",
    status: "adapted",
    where: "parseContentHash() reads #<section id>, #<area id> and #project/<id>, in any letter case; a project id outside the 15 opens the forge reader, which loads it from the archive or says it couldn't find it, and a malformed hash is ignored. The 3D page flies there and opens the reader; the one-page view (also /?view=page) jumps there.",
    note: "On the old page, opening a project pushes #project/<id>, so Back closes it and the address can be shared. In the sect that history handling belongs to the 3D page (sect-experience.tsx); the reader reports a project opened or closed inside it through onItemChange for that.",
  });

  // ---- hero -------------------------------------------------------------------------------------
  const hero = "Hero (#hero)";
  add({
    section: hero,
    what: `Eyebrow "${HERO.eyebrow}"`,
    status: "dropped",
    where: "Not in the sect.",
    note: "Cut to keep the gate reader short.",
  });
  add({
    section: hero,
    what: `Headline "${runsText(HERO.heading)}"`,
    status: "dropped",
    where: "Not in the sect.",
    note: "Cut to keep the gate reader short.",
  });
  add({
    section: hero,
    what: "Intro paragraph (I'm Bill Zhang ... ask it something.)",
    status: "adapted",
    area: "gate",
    texts: [runsText(HERO.intro).replace(/ This page is one of those builds\..*$/, "")],
    where: reach("gate"),
    note: "The last two sentences are left out.",
  });
  add({
    section: hero,
    what: `Tagline "${PORTFOLIO.tagline}" (portfolio data)`,
    status: "carried",
    area: "gate",
    texts: [PORTFOLIO.tagline],
    where: reach("gate", "Also on the gate's summary panel."),
  });
  add({
    section: hero,
    what: `"${HERO.viewResume}" button (jumps to the resume)`,
    status: "carried",
    area: "gate",
    texts: [HERO.viewResume],
    where: reach("gate", "The button goes to the Jade Slip Pavilion reader."),
  });
  add({
    section: hero,
    what: `"${HERO.downloadPdf} ${HERO.pdfSize}" (downloads /resume.pdf as ${RESUME_HEAD.downloadName})`,
    status: "carried",
    area: "gate",
    texts: [HERO.downloadPdf, HERO.pdfSize],
    urls: ["/resume.pdf"],
    where: reach("gate", "Also on the Jade Slip Pavilion panel and reader."),
  });
  for (const chip of HERO_CHIPS) {
    const t = heroChipTarget(chip);
    add({
      section: hero,
      what: `Question chip "${chip}" (moves to ${SECTION_NAMES[t.area]}${t.filter ? `, filtered by ${t.filter}` : ""})`,
      status: "carried",
      area: "gate",
      texts: [chip],
      where: reach("gate", `A question chip; it goes to the ${areaInfo(t.area).label}.`),
    });
  }

  // ---- voice orb ----------------------------------------------------------------------------------
  const orb = "Voice orb (components/voice-orb)";
  add({
    section: orb,
    what: `Orb button "${VOICE_ORB.button}" and pill "${VOICE_ORB.pill}"`,
    status: "engine",
    where: 'The 3D page passes onTalk; the content shows "Ask a senior disciple" on the gate and summit panels, in the gate reader, in the contact reader, and on the moon hotspot. Without onTalk they are left out. The orb (components/voice-orb) is dressed by sect.css as a 传音符 (a sound-transmission talisman): a jade seal stamped 音, "Ask a senior disciple" on hover and keyboard focus, glowing while it listens and speaks; its pill shows on the intro screen only, because at the stops it covered the scene\'s own objects.',
  });
  add({
    section: orb,
    what: "Voice call panel: Retell call, status lines, transcript, text chat mode, end call",
    status: "engine",
    where: "Runs through onTalk on the 3D page. The content layer has no call UI of its own, but keeps the orb usable over its modals: the reader and the one-page view never pull focus out of the orb, a reader the agent opens mid-reply leaves the caret in the chat box, and Tab goes from a modal's last control to the orb.",
  });
  add({
    section: orb,
    what: `Panel title "${VOICE_ORB.panelTitle}"`,
    status: "engine",
    where: "The voice orb in the sect shows it in its own panel.",
  });
  for (const s of SUGGESTIONS) {
    add({
      section: orb,
      what: `Suggestion "${s.you}" with reply "${s.ai}"`,
      status: "engine",
      where:
        "The voice orb in the sect lists it in its own panel. The gate's Sword Monoliths view also lists the question, without the reply.",
    });
  }

  // ---- about ----------------------------------------------------------------------------------------
  const about = "About (#about)";
  add({
    section: about,
    what: `Eyebrow "${ABOUT_HEAD.eyebrow}" and heading "${runsText(ABOUT_HEAD.heading)}"`,
    status: "dropped",
    where: "Not in the sect.",
    note: "The reader's title already says About.",
  });
  add({
    section: about,
    what: "Sticky cards that stack as you scroll",
    status: "adapted",
    area: "mirror",
    where: reach("mirror"),
    note: "The four cards become a plain list in the same order.",
  });
  for (const c of ABOUT_CARDS) {
    add({
      section: about,
      what: `Card ${c.num}: "${c.title}" and its paragraph`,
      status: "adapted",
      area: "mirror",
      texts: [c.title, c.body],
      where: reach("mirror", "Clicking the bronze mirror (hotspot mirror) opens it too."),
      note: `The "${c.num}" label is left out.`,
    });
  }

  // ---- projects -------------------------------------------------------------------------------------
  const proj = "Projects (#projects)";
  add({
    section: proj,
    what: `Eyebrow "${PROJECTS_HEAD.eyebrow} · <count>" (6 STANDOUTS, or matches/15 when filtered) and heading "${runsText(PROJECTS_HEAD.heading)}"`,
    status: "dropped",
    where: "Not in the sect.",
    note: "The reader's title already says Projects.",
  });
  add({
    section: proj,
    what: `"${PROJECTS_HEAD.galleryLabel}" and "${PROJECTS_HEAD.galleryHint}"`,
    status: "dropped",
    where: "Not in the sect.",
    note: "Cut: the filters explain themselves.",
  });
  add({
    section: proj,
    what: `Phone hint "${PROJECTS_HEAD.mobileHint}" and the "SCROLL ↓ drives gallery →" footer`,
    status: "dropped",
    where: "Not in the sect.",
    note: "They describe the phone carousel and the scroll-driven rail, which the reader replaces with a grid of cards.",
  });
  add({
    section: proj,
    what: `Filters: ${PROJECT_FILTERS.map((f) => f.label).join(", ")}, and year toggles ${PROJECT_YEARS.join(", ")}`,
    status: "adapted",
    area: "forge",
    texts: [...PROJECT_FILTERS.map((f) => f.label), ...PROJECT_YEARS.map(String)],
    where: reach("forge", "Filter buttons sit above the cards; the orb suggestion \"Show me only the voice AI projects.\" opens the forge filtered."),
    note: `Same filters and rules as the old page (a year narrows, picking a filter clears the year). Two filters are added: "On the ring", the default, lists the ${FORGE_RING.length} prize winners whose artifacts circle the cauldron, biggest win first; "All ${PROJECTS.length}" lists every project. "Standouts" still shows the old page's six hand-picked projects in their order.`,
  });
  add({
    section: proj,
    what: 'Match count ("6/15 standouts", "n/15 match")',
    status: "adapted",
    area: "forge",
    texts: [`/${PROJECTS.length} on the ring`],
    where: reach("forge", "Announced politely to screen readers when it changes."),
    note: `The default view counts the ring's winners ("${FORGE_RING.length}/${PROJECTS.length} on the ring"); a filter shows "n/${PROJECTS.length} match" and Standouts "6/${PROJECTS.length} standouts", as on the old page.`,
  });
  add({
    section: proj,
    what: `Project cards: poster, award badge, /id, "${PROJECTS_HEAD.deepDive}", name, summary, #tags, year`,
    status: "adapted",
    area: "forge",
    texts: PROJECTS.flatMap((p) => [p.name, p.summary, `/${p.id}`]),
    urls: PROJECTS.flatMap((p) => (p.poster ? [p.poster] : [])),
    where: reach("forge", "Hovering a card lights its artifact in the scene."),
    note: `A grid instead of the horizontal scroll rail and the phone carousel with dots. The "${PROJECTS_HEAD.deepDive}" label is left out; the whole card opens.`,
  });
  add({
    section: proj,
    what: "Project detail view: eyebrow (award or Project · year), name, summary, demo video / image / placeholder, The story, Role, Stack, Year, ID, Tags, demo / live / GitHub links, voice tip, close with Esc",
    status: "adapted",
    area: "forge",
    project: "dispatchai",
    texts: [PROJECTS_HEAD.story, PROJECTS_HEAD.role, PROJECTS_HEAD.stack, PROJECTS_HEAD.year, PROJECTS_HEAD.id, PROJECTS_HEAD.tags, PROJECTS_HEAD.source, PROJECTS_HEAD.liveProject],
    where: "Inside the forge reader: press a project's name or card, click its artifact in the scene (hotspot project:<id>), or pick it in the map's list of places. Esc or \"Back\" goes back to the list; arrows step to the previous/next project.",
    note: "Shown in the reader sheet instead of a second modal. YouTube demos load when you press Play (the 3D scene already uses the GPU), and a \"Watch on YouTube\" link is always there. The voice tip is left out, and the eyebrow shows only an award (the Year row has the year).",
  });
  add({
    section: proj,
    what: "Projects outside the 15 that the voice agent can open (Pinecone corpus, lazy-loaded)",
    status: "carried",
    where: 'Forge reader, when a deep link (#project/<id>, ?open=project:<id>) or a voice command names one: the detail loads from the same corpus, like the old page. An id that is not there either shows "Couldn\'t find project".',
  });
  add({
    section: proj,
    what: 'Voice feedback lines ("Filtering by voice.", "Focusing on X.", "Opening X.")',
    status: "dropped",
    where: "Not in the sect.",
    note: "They echo voice commands. The filter state and match count show the same result.",
  });
  for (const p of PROJECTS) {
    const { demoLink } = projectMedia(p);
    add({
      section: proj,
      what: `Project ${p.name} (${p.id}): ${[
        "summary",
        "story",
        p.role && "role",
        p.stack && `${p.stack.length} stack items`,
        p.award && `award "${p.award}"`,
        p.year && `year ${p.year}`,
        `tags ${p.tags.map((t) => `#${t}`).join(" ")}`,
        p.github && "GitHub link",
        demoLink && (toEmbedLabel(demoLink) ? "demo video" : "demo media link"),
        p.projectUrl && "live project link",
        p.poster && "poster",
      ]
        .filter(Boolean)
        .join(", ")}`,
      status: "carried",
      area: "forge",
      project: p.id,
      texts: [
        p.name,
        p.summary,
        p.long ?? p.summary,
        ...(p.role ? [p.role] : []),
        ...(p.stack ?? []),
        ...(p.award ? [`★ ${p.award}`] : []),
        ...(p.year ? [String(p.year)] : []),
        ...p.tags.map((t) => `#${t}`),
        `/${p.id}`,
      ],
      urls: [p.github, demoLink, p.projectUrl, p.poster].filter((u): u is string => Boolean(u)),
      where: `Forge reader, ${p.name} detail: click its artifact (hotspot project:${p.id}), its card in the forge reader, or the map's list of places. Deep link #project/${p.id} in the one-page view.`,
    });
  }

  // ---- hackathons ------------------------------------------------------------------------------------
  const hack = "Hackathons (#hackathons)";
  add({
    section: hack,
    what: `Eyebrow "${HACKATHONS_HEAD.eyebrowPrefix} · ${HACKATHONS.length} ${HACKATHONS_HEAD.eyebrowSuffix}", heading "${runsText(HACKATHONS_HEAD.heading)}" and intro`,
    status: "dropped",
    where: "Not in the sect.",
    note: "The panel and the stat tiles carry the numbers.",
  });
  add({
    section: hack,
    what: "Two scrolling marquee rows (first 18, last 18)",
    status: "adapted",
    area: "arena",
    where: reach("arena"),
    note: "One list of all 36 banners in the same order. Nothing moves, so nothing has to be caught. The reader also shows each win's project (a field of the data the marquee leaves out), with a link to it in the forge when it is one of the 15.",
  });
  for (const s of HACKATHON_STATS) {
    const n = s.n === "count" ? String(HACKATHONS.length) : s.n;
    add({ section: hack, what: `Stat "${n}" ${s.l}`, status: "carried", area: "arena", texts: [n, s.l], where: reach("arena") });
  }
  HACKATHONS.forEach((h, i) => {
    add({
      section: hack,
      what: `Hackathon ${i + 1}: ${hackathonTitle(i)}, ${h.project}, ${h.prize}`,
      status: "carried",
      area: "arena",
      texts: [h.name, ...(h.year ? [String(h.year)] : []), h.project, `★ ${h.prize}`],
      where: reach("arena", `Its banner is hotspot hackathon:${i}.`),
    });
  });

  // ---- experience ---------------------------------------------------------------------------------------
  const exp = "Experience (#experience)";
  add({
    section: exp,
    what: `Eyebrow "${EXPERIENCE_HEAD.eyebrow}" and heading "${runsText(EXPERIENCE_HEAD.heading)}"`,
    status: "dropped",
    where: "Not in the sect.",
    note: "The reader's title already says Experience.",
  });
  add({
    section: exp,
    what: "Timeline spine that draws in on scroll",
    status: "dropped",
    where: "Not in the sect.",
    note: "Decoration. The roles keep their order.",
  });
  EXPERIENCE.forEach((r, i) => {
    add({
      section: exp,
      what: `Role ${i + 1}: ${r.role}, ${r.where} (${r.when})`,
      status: "carried",
      area: "mission",
      texts: [r.when, r.role, r.where, ...r.bullets, ...(r.badge ? [r.badge] : [])],
      urls: r.link ? [r.link] : [],
      where: reach("mission", `Its jade tablet is hotspot role:${i}.`),
    });
  });

  // ---- education ------------------------------------------------------------------------------------------
  const edu = "Education (#education)";
  add({
    section: edu,
    what: `Eyebrow "${EDUCATION_HEAD.eyebrow}" and heading "${runsText(EDUCATION_HEAD.heading)}"`,
    status: "dropped",
    where: "Not in the sect.",
    note: "The reader's title already says Education.",
  });
  add({
    section: edu,
    what: `Flip cards and the hint "${EDUCATION_HEAD.hint}"`,
    status: "adapted",
    area: "library",
    where: reach("library"),
    note: "Both faces of each card are shown at once, so nothing hides behind a flip and the hint is not needed.",
  });
  EDUCATION.forEach((e, i) => {
    add({
      section: edu,
      what: `School ${i + 1}: ${e.full} (front: logo, number, name, degree, dates; back: notes)`,
      status: "adapted",
      area: "library",
      texts: [e.full, e.degree, e.when, e.detail],
      urls: [e.logo],
      where: reach("library", `Its lit pagoda floor is hotspot school:${i}.`),
      note: "The card number and the NOTES label are left out.",
    });
  });

  // ---- skills ----------------------------------------------------------------------------------------------
  const skills = "Skills (#skills)";
  add({
    section: skills,
    what: "The skills sentence, with its four tagged phrases set in the accent style",
    status: "carried",
    area: "steles",
    texts: SKILLS_LINE.map((w) => w.w),
    where: reach("steles", "The master stele is hotspot steles."),
  });
  add({
    section: skills,
    what: "Word-by-word light-up as you scroll",
    status: "adapted",
    area: "steles",
    texts: skillGroups().map((g) => g.label),
    where: reach(
        "steles",
        "Each of the five stele rows (hotspots skills:0 to skills:4) carries one phrase; hovering or focusing a row lights its words in the sentence.",
      ),
    note: "The phrase groups are the sentence's own key phrases: \"voice-first\" and the four tagged phrases.",
  });

  // ---- resume -----------------------------------------------------------------------------------------------
  const res = "Resume (#resume)";
  add({
    section: res,
    what: `Eyebrow "${RESUME_HEAD.eyebrow}", heading "${runsText(RESUME_HEAD.heading)}" and intro`,
    status: "dropped",
    where: "Not in the sect.",
    note: "The panel and the file line say what it is.",
  });
  add({
    section: res,
    what: "Inline PDF preview of /resume.pdf",
    status: "carried",
    area: "scroll",
    texts: [],
    urls: [RESUME_HEAD.previewSrc],
    where: reach("scroll", "Clicking the giant jade scroll (hotspot resume) opens the reader at the preview."),
  });
  add({
    section: res,
    what: `File line "${RESUME_HEAD.fileLine}"`,
    status: "carried",
    area: "scroll",
    texts: [RESUME_HEAD.fileLine],
    where: reach("scroll"),
  });
  add({
    section: res,
    what: `"${RESUME_HEAD.openTab}" and "${RESUME_HEAD.download}" (${RESUME_HEAD.downloadName})`,
    status: "carried",
    area: "scroll",
    texts: [RESUME_HEAD.openTab, RESUME_HEAD.download],
    urls: ["/resume.pdf"],
    where: reach(
      "scroll",
      "Placed above the preview (phones without a PDF viewer show an empty box). The Jade Slip Pavilion panel has its own Download PDF button.",
    ),
  });
  for (const s of RESUME_STATS) {
    add({ section: res, what: `Stat "${s.v}" ${s.k}`, status: "carried", area: "scroll", texts: [s.v, s.k], where: reach("scroll") });
  }
  for (const g of RESUME_GLANCE) {
    add({
      section: res,
      what: `At a glance: ${g.k} ${g.v}`,
      status: "carried",
      area: "scroll",
      texts: [RESUME_HEAD.glanceTitle, g.k, g.v],
      where: reach("scroll"),
    });
  }
  add({
    section: res,
    what: `Get in touch: ${PORTFOLIO.email}, ${RESUME_LINKS.map((l) => l.label).join(", ")}`,
    status: "carried",
    area: "scroll",
    texts: [RESUME_HEAD.contactTitle, PORTFOLIO.email, ...RESUME_LINKS.map((l) => l.label)],
    urls: [`mailto:${PORTFOLIO.email}`, ...RESUME_LINKS.map((l) => l.href)],
    where: reach("scroll"),
  });
  add({
    section: res,
    what: `Voice tip ${RESUME_HEAD.voiceTipText}`,
    status: "dropped",
    where: "Not in the sect.",
    note: "Cut to keep the reader short.",
  });

  // ---- architecture -----------------------------------------------------------------------------------------
  const arch = "Architecture (#architecture)";
  add({
    section: arch,
    what: `Eyebrow "${ARCH_HEAD.eyebrow}", heading "${runsText(ARCH_HEAD.heading)}" and intro`,
    status: "adapted",
    area: "formation",
    texts: [ARCH_HEAD.intro],
    where: reach("formation"),
    note: "The eyebrow and heading are left out; the reader's title names the section.",
  });
  ARCH_FLOW.forEach((f, i) => {
    add({
      section: arch,
      what: `Flow step ${f.k}: ${f.title}`,
      status: "carried",
      area: "formation",
      texts: [f.k, f.title, f.body],
      where: reach("formation", `Its array-flag pillar is hotspot arch:${i}.`),
    });
  });
  for (const s of ARCH_STACK) {
    add({
      section: arch,
      what: `Stack group ${s.group}: ${s.items.join(", ")}`,
      status: "carried",
      area: "formation",
      texts: [s.group, ...s.items],
      where: reach("formation", "The stack is pillar hotspot arch:6."),
    });
  }
  add({
    section: arch,
    what: "Code snippet (navigation metadata → VoiceBus → scroll), syntax highlighted",
    status: "carried",
    area: "formation",
    texts: [ARCH_SNIPPET],
    where: reach("formation", "The code is pillar hotspot arch:7."),
  });

  // ---- personal -------------------------------------------------------------------------------------------------
  const per = "Personal (#personal)";
  add({
    section: per,
    what: `Eyebrow "${PERSONAL_HEAD.eyebrow}" and heading "${runsText(PERSONAL_HEAD.heading)}"`,
    status: "dropped",
    where: "Not in the sect.",
    note: "The reader's title already says Off the clock.",
  });
  add({
    section: per,
    what: "Watermark lines behind the section",
    status: "dropped",
    where: "Not in the sect.",
    note: "Decoration.",
  });
  add({
    section: per,
    what: `Photo (${PERSONAL_HEAD.photo}, alt "${PERSONAL_HEAD.photoAlt}") with caption "${PERSONAL_HEAD.photoCaption}"`,
    status: "carried",
    area: "abode",
    texts: [PERSONAL_HEAD.photoCaption],
    urls: [PERSONAL_HEAD.photo],
    where: reach("abode", "The moon gate (hotspot abode) opens the reader."),
  });
  // The object each fact's hotspot is, in PERSONAL_FACTS order (blender/xianxia-sect/sect/export_web.py ABODE_FACTS).
  // Round 34 made the 笑傲江湖 duet's qin table the drums-and-piano fact's object (the wind chimes before it).
  const factObjects = ["waterfall", "peach tree", "cliff inscription", "qin table of the 笑傲江湖 duet", "tea table", "crane", "koi pool"];
  PERSONAL_FACTS.forEach((f, i) => {
    const obj = factObjects[i];
    add({
      section: per,
      what: `Fact ${i + 1}: ${stripTags(f.line)}`,
      status: "carried",
      area: "abode",
      texts: [stripTags(f.line)],
      where: reach("abode", obj ? `Its object in the abode is the ${obj} (hotspot fact:${i}).` : `Its object in the abode is hotspot fact:${i}.`),
    });
  });
  add({
    section: per,
    what: `Tip "${PERSONAL_HEAD.tipLead} ${PERSONAL_HEAD.tipQuote}"`,
    status: "dropped",
    where: "Not in the sect.",
    note: "The Ask a senior disciple button does the same.",
  });

  // ---- footer ----------------------------------------------------------------------------------------------------
  const foot = "Footer / contact";
  add({
    section: foot,
    what: `Eyebrow "${FOOTER.eyebrow}", heading "${runsText(FOOTER.heading)} ${FOOTER.heading2}" and "${FOOTER.body}"`,
    status: "dropped",
    where: "Not in the sect.",
    note: "The reader's title already says Contact; the email and the talk button follow.",
  });
  add({
    section: foot,
    what: `Direct: email ${PORTFOLIO.email}`,
    status: "carried",
    area: "summit",
    texts: [FOOTER.direct, PORTFOLIO.email],
    urls: [`mailto:${PORTFOLIO.email}`],
    where: reach("summit", "The summit panel also has an Email button."),
  });
  add({
    section: foot,
    what: `Direct: "${FOOTER.tapOrb}"`,
    status: "carried",
    area: "summit",
    texts: [FOOTER.tapOrb],
    where: reach(
        "summit",
        "Starts a call through onTalk (left out without it). Clicking the moon (hotspot moon) does the same on the 3D page.",
      ),
  });
  for (const [label, href] of [
    ["GitHub", PORTFOLIO.github],
    ["LinkedIn", PORTFOLIO.linkedin],
    ["Devpost", PORTFOLIO.devpost],
  ] as const) {
    add({
      section: foot,
      what: `Elsewhere: ${label} (${href})`,
      status: "carried",
      area: "summit",
      texts: [FOOTER.elsewhere, label],
      urls: [href],
      where: reach("summit"),
    });
  }
  for (const l of FOOTER.indexLinks) {
    add({
      section: foot,
      what: `Index: ${l.label} (jumps to #${l.section})`,
      status: "dropped",
      where: "Not in the sect.",
      note: "The reader's Previous / Next and the map (its seals and its list of places) already move between areas.",
    });
  }
  add({
    section: foot,
    what: `"${FOOTER.copyright}"`,
    status: "carried",
    area: "summit",
    texts: [FOOTER.copyright],
    where: reach("summit"),
  });
  add({
    section: foot,
    what: `Location "${PORTFOLIO.location}" (portfolio data; the old page shows it only as "SF" in the top bar)`,
    status: "carried",
    area: "summit",
    texts: [PORTFOLIO.location],
    where: reach("summit"),
  });

  // ---- files ----------------------------------------------------------------------------------------------------
  const files = "Public files";
  add({
    section: files,
    what: "/resume.pdf (preview, open in new tab, download)",
    status: "carried",
    area: "scroll",
    urls: ["/resume.pdf"],
    where: "Jade Slip Pavilion panel and reader; gate reader (Download PDF).",
  });
  add({
    section: files,
    what: `Project posters (${PROJECTS.filter((p) => p.poster).length} in /project-posters/)`,
    status: "carried",
    area: "forge",
    urls: PROJECTS.flatMap((p) => (p.poster ? [p.poster] : [])),
    where: "Forge reader cards and the detail view's video cover.",
  });
  add({
    section: files,
    what: `School logos (${EDUCATION.map((e) => e.logo).join(", ")})`,
    status: "carried",
    area: "library",
    urls: EDUCATION.map((e) => e.logo),
    where: "Scripture Pavilion reader.",
  });
  add({
    section: files,
    what: "github.svg, linkedin.svg, devpost.svg, rocket.png, llms.txt, data.json",
    status: "dropped",
    where: "Not in the sect.",
    note: "The old page did not use them either.",
  });

  return out;
}

const STATUS_WORD: Record<InventoryStatus, string> = {
  carried: "carried",
  adapted: "adapted",
  engine: "3D page",
  dropped: "not carried",
};

/** docs/sect-content-inventory.md, generated from contentInventory(). */
export function inventoryMarkdown(): string {
  const items = contentInventory();
  const sections: string[] = [];
  for (const e of items) if (!sections.includes(e.section)) sections.push(e.section);
  const count = (s: InventoryStatus) => items.filter((e) => e.status === s).length;
  const lines: string[] = [];
  lines.push("# Sect content inventory");
  lines.push("");
  lines.push(
    "Generated from `src/lib/sect/content-inventory.ts`. Do not edit by hand; after changing that file run `SECT_WRITE_INVENTORY=1 pnpm exec vitest run src/lib/sect/content-inventory.test.ts`.",
  );
  lines.push("");
  lines.push(
    "Every piece of content and every interaction on the old page (the one-page portfolio that was `src/app/page.tsx` until the sect replaced it as the home page; archived), and where it lives in the sect. `src/app/sect/content/content-completeness.test.tsx` renders every area reader and the one-page view and fails if any text or link below marked carried or adapted is missing.",
  );
  lines.push("");
  lines.push("## How a visitor reaches content in the sect");
  lines.push("");
  lines.push(
    "1. Fly: scroll (or use the area rail) through the eleven areas. The camera holds at each one and its summary panel appears. The panel's button opens the reader for that area.",
  );
  lines.push("2. Click a thing in the scene (an artifact, a banner, a tablet...). The reader opens at that item. The map's list of places (the Map button, or M) does the same.");
  lines.push("3. Inside a reader, Previous / Next go to the neighbouring areas, and links inside the content (hero chips, a win's \"Open project\") jump across areas.");
  lines.push("4. Read as one page: every reader's content on one scrolling page with a menu of the eleven areas. It is also what a browser without WebGL gets. It opens at `#<section id>` or `#project/<id>`.");
  lines.push("");
  lines.push("| Area | Place | Old page's section |");
  lines.push("| --- | --- | --- |");
  for (const a of AREAS) lines.push(`| ${a.id} | ${a.label} (${a.zh}) | ${SECTION_NAMES[a.id]} (#${a.sectionId}) |`);
  lines.push("");
  lines.push(
    `${items.length} entries: ${count("carried")} carried, ${count("adapted")} adapted (same content, different presentation), ${count("engine")} handled by the 3D page, ${count("dropped")} not carried (each with its reason).`,
  );
  lines.push("");
  const end = (t: string) => (/[.!?]["”)]?$/.test(t) ? t : `${t}.`);
  for (const s of sections) {
    const group = items.filter((e) => e.section === s);
    lines.push(`## ${s} (${group.length})`);
    lines.push("");
    const areas = group.map((e) => e.area).filter((a): a is AreaId => Boolean(a));
    const tally = (a: AreaId) => areas.filter((x) => x === a).length;
    const main = [...areas].sort((a, b) => tally(b) - tally(a))[0];
    if (main) {
      lines.push(`Reader: ${areaInfo(main).label} (${areaInfo(main).zh}). ${areaReach(main)}`);
      lines.push("");
    }
    for (const e of group) {
      const box = e.status === "dropped" ? "[ ]" : "[x]";
      lines.push(`- ${box} **${e.id}** ${end(e.what)} *${STATUS_WORD[e.status]}.* ${end(e.where)}${e.note ? ` ${end(e.note)}` : ""}`);
    }
    lines.push("");
  }
  return lines.join("\n");
}
