/**
 * The portfolio's copy that is not in portfolio-data: headings, cards, chips and labels the sect's
 * readers show. It was copied verbatim from the one-page portfolio's section components, which the
 * sect replaced (they are archived, out of the repo); this file is now its only home, so edit the
 * wording here.
 *
 * Each block names the component it came from. JSX text is stored with its entities decoded
 * (&apos; -> ') and its whitespace collapsed, the way it rendered.
 */

/** A run of text; `em` marks the serif accent word (the old page's gradient word), `b` the bold words. */
export interface Run {
  t: string;
  em?: boolean;
  b?: boolean;
}

// ---- src/components/sections/hero.tsx -------------------------------------------------------
export const HERO = {
  eyebrow: "VOICE-DRIVEN PORTFOLIO · 2026",
  heading: [{ t: "Ask me " }, { t: "anything.", em: true }] as Run[],
  intro: [
    { t: "I'm " },
    { t: "Bill Zhang", b: true },
    {
      t: ". By day I build LLM agents at Pinterest. By night I build software you can talk to, which is how I ended up with 36 hackathon wins. This page is one of those builds. Go on, ask it something.",
    },
  ] as Run[],
  viewResume: "View resume",
  downloadPdf: "Download PDF",
  pdfSize: "113 KB",
};

/** The five question chips under the hero intro (hero.tsx HERO_CHIPS). */
export const HERO_CHIPS = [
  "Who is Bill?",
  "What voice AI projects has he built?",
  "Show me the hackathon wins.",
  "What does he do for fun?",
  "Take me to his projects.",
];

// ---- src/components/topbar.tsx --------------------------------------------------------------
export const TOPBAR = {
  name: "Bill Zhang",
  cityPrefix: "SF",
  timeZone: "America/Los_Angeles",
};

// ---- src/components/voice-orb/index.tsx (the floating orb and its panel) ---------------------
// In the sect the orb is the 传音符 talisman and a senior disciple answers through it: none of the
// agent's labels say "AI" (the owner's wish, October 2026).
export const VOICE_ORB = {
  pill: "Ask a senior disciple · or scroll",
  button: "Ask a senior disciple by voice",
  panel: "Speak with a senior disciple",
  panelTitle: "Ask anything.",
};

// ---- src/components/sections/about.tsx ------------------------------------------------------
export const ABOUT_HEAD = {
  eyebrow: "ABOUT",
  heading: [{ t: "A builder who " }, { t: "listens", em: true }, { t: " first." }] as Run[],
};

export const ABOUT_CARDS = [
  {
    num: "01 / WHO",
    title: "Most of my work is failure handling.",
    body: "Latency, interrupted sentences, tool calls that half-fail, a model that answers the wrong question with total confidence. At Scale AI I shipped a multi-agent system that works through up to 20K denied claims a week, and owned the eval framework that moved audit accuracy from 64% to 88%. Almost all of that came out of the failure cases.",
  },
  {
    num: "02 / WHAT",
    title: "Software you can talk to.",
    body: "A 911 console that triages live calls, a whole bank that runs inside a phone call, a food-rescue network that dispatches by voice, game tape you can question mid-replay. Several of them need nothing but a phone. No app, no internet.",
  },
  {
    num: "03 / HOW",
    title: "One idea, end to end, in 36 hours.",
    body: "At a hackathon I pick one idea and make it actually work. Dispatch AI was a phone line, a fine-tuned triage model, and a dispatcher screen. It won the $25K SkyDeck grand prize at Berkeley against 900+ people, plus a separate $25K investment from AIC.",
  },
  {
    num: "04 / WHY",
    title: "Talking is the interface of the future.",
    body: "Most people can speak several times faster than they type, with a fraction of the effort. And while you talk, your hands are free for whatever else you were doing. That is why this site listens instead of making you click, and why TalkTuahBank handles balances, transfers, and bill pay by voice alone. No app, no data plan.",
  },
];

// ---- src/components/sections/projects/* ----------------------------------------------------
export const PROJECTS_HEAD = {
  eyebrow: "PROJECTS",
  heading: [{ t: "Things I " }, { t: "shipped.", em: true }] as Run[],
  galleryLabel: "Curated gallery",
  galleryHint: "Ask by voice for any project, or filter the archive.",
  mobileHint: "Swipe the cards, ask by voice, or filter the archive.",
  deepDive: "↗ deep dive",
  story: "The story",
  role: "Role",
  stack: "Stack",
  year: "Year",
  id: "ID",
  tags: "Tags",
  demoMedia: "View demo media",
  liveProject: "Live project",
  source: "Source on GitHub",
  voiceTip: "Voice tip",
  noMedia: "Demo media not available. Check the project links.",
};

/** filter-bar.tsx FILTERS, in order. */
export const PROJECT_FILTERS = [
  { key: "all", label: "Standouts" },
  { key: "voice", label: "Voice" },
  { key: "ai", label: "AI" },
  { key: "fintech", label: "Fintech" },
  { key: "safety", label: "Safety" },
  { key: "education", label: "Education" },
  { key: "3d", label: "3D" },
  { key: "winner", label: "Winners" },
] as const;

/** filter-bar.tsx year buttons. */
export const PROJECT_YEARS = [2025, 2024] as const;

// ---- src/components/sections/hackathons/hackathons-section.tsx ------------------------------
export const HACKATHONS_HEAD = {
  /** Rendered as `HACKATHONS · ${HACKATHONS.length} WINS`. */
  eyebrowPrefix: "HACKATHONS",
  eyebrowSuffix: "WINS",
  heading: [{ t: "Thirty-six " }, { t: "wins.", em: true }] as Run[],
  intro:
    "Every one of these was a weekend: build it, demo it, win over the judges. All during college. $150k+ in prizes.",
};

/** The four stat tiles under the marquee. The first value is HACKATHONS.length on the page. */
export const HACKATHON_STATS = [
  { n: "count", l: "Hackathons won" },
  { n: "$74k", l: "Largest prize" },
  { n: "$150k+", l: "Prizes won" },
  { n: "17", l: "Colleges visited" },
];

// ---- src/components/sections/experience/experience-section.tsx ------------------------------
export const EXPERIENCE_HEAD = {
  eyebrow: "EXPERIENCE",
  heading: [{ t: "A short, " }, { t: "productive", em: true }, { t: " career." }] as Run[],
};

// ---- src/components/sections/education.tsx -------------------------------------------------
export const EDUCATION_HEAD = {
  eyebrow: "EDUCATION",
  heading: [{ t: "Three schools, " }, { t: "one path.", em: true }] as Run[],
  hint: "Click a card to flip it.",
  notes: "NOTES",
};

// ---- src/components/sections/resume.tsx ----------------------------------------------------
export const RESUME_HEAD = {
  eyebrow: "RESUME · ONE-PAGER",
  heading: [{ t: "The " }, { t: "printable", em: true }, { t: " version." }] as Run[],
  intro:
    "Same information, one page, no talking required. Read it below or take the PDF; both match what the rest of this site says.",
  fileLine: "resume.pdf · last updated September 12, 2026",
  previewSrc: "/resume.pdf#toolbar=0&navpanes=0&view=FitH",
  previewTitle: "Bill Zhang Resume",
  openTab: "Open in new tab",
  download: "Download PDF",
  downloadName: "Bill-Zhang-Resume.pdf",
  glanceTitle: "At a glance",
  contactTitle: "Get in touch",
  voiceTip: "Voice tip",
  voiceTipText: "“Send me your resume.” → opens the download.",
};

export const RESUME_STATS = [
  { k: "Years building", v: "5+" },
  { k: "Hackathon wins", v: "36" },
  { k: "Voice apps shipped", v: "9" },
  { k: "Prizes won", v: "$150k+" },
];

export const RESUME_GLANCE = [
  { k: "AI engineer:", v: "voice-first agents, multimodal pipelines, real-time inference." },
  { k: "Pinterest:", v: "LLM agent systems, RAG, production guardrails. Previously Scale AI." },
  { k: "USC:", v: "M.S. Computer Science, AI specialization." },
  { k: "Stack:", v: "TypeScript / Python / Rust, Next.js, Retell, Twilio, Mistral, Llama." },
];

/** The "Get in touch" links on the resume section (the email is PORTFOLIO.email). */
export const RESUME_LINKS = [
  { label: "github.com/IdkwhatImD0ing", href: "https://github.com/IdkwhatImD0ing" },
  { label: "linkedin.com/in/bill-zhang1", href: "https://www.linkedin.com/in/bill-zhang1/" },
];

// ---- src/components/sections/architecture.tsx ----------------------------------------------
export const ARCH_HEAD = {
  eyebrow: "HOW THIS SITE WORKS",
  heading: [{ t: "A portfolio that " }, { t: "talks back.", em: true }] as Run[],
  intro:
    "Ask about a project and the agent looks it up, describes it, and opens it on the page. Retell carries the audio, Deepgram hears you, GPT-5.6 Terra thinks, ElevenLabs talks back. A Python backend runs the agent and tells the browser where to fly.",
};

export const ARCH_FLOW = [
  {
    k: "01",
    title: "Mic input",
    body: "Browser mic → Retell client SDK over WebRTC. Deepgram transcribes the stream as you speak.",
  },
  {
    k: "02",
    title: "LLM agent",
    body: "Retell hands the transcript to a FastAPI backend, where a GPT-5.6 Terra agent (OpenAI Agents SDK) runs with this site's content in context, nine registered tools, and a jailbreak guardrail in front.",
  },
  {
    k: "03",
    title: "Tool calls",
    body: "Agent emits structured tool calls: display_project(id), display_resume_page(), search_projects(query, ...), and six more.",
  },
  {
    k: "04",
    title: "VoiceBus",
    body: "navigation.py turns each display_* call into a navigation metadata event; the browser converts it to a bus command. No prop drilling, no router. The sect listens.",
  },
  {
    k: "05",
    title: "Sections react",
    body: "The sect turns each command into one of its eleven stops and flies there, then opens the section or project it names.",
  },
  {
    k: "06",
    title: "Voice reply",
    body: "The reply streams back through Retell into an ElevenLabs voice while the flight is still landing, so the answer and the view arrive together.",
  },
];

export const ARCH_STACK = [
  {
    group: "Voice",
    items: ["Retell AI (call runtime, WebRTC)", "Deepgram speech-to-text", "ElevenLabs text-to-speech"],
  },
  {
    group: "Brain",
    items: [
      "GPT-5.6 Terra (the agent)",
      "GPT-5.6 Luna (guardrail + call summary)",
      "OpenAI Agents SDK, nine tools",
      "Site-grounded system prompt",
    ],
  },
  { group: "Frame", items: ["Next.js + React 19", "Three.js + React Three Fiber + GLSL", "A sect modelled and baked in Blender"] },
  {
    group: "State",
    items: ["VoiceBus pub-sub", "URL-driven section anchors", "Per-section local React state"],
  },
];

export const ARCH_SNIPPET = `// server: navigation.py turns a display_* tool call into
// { type: "navigation", page: "project", project_id: "dispatchai" }

// browser: metadata event → bus command
client.on("metadata", ({ metadata }) => {
  const cmd = metaToNavigationAction(metadata);
  if (cmd) VoiceBus.emit(cmd);
});

// the sect listens on the same bus and flies there
VoiceBus.on((cmd) => {
  const target = commandTarget(cmd); // { area: "forge", item: "project:dispatchai" }
  if (target) navigate(target);
});`;

// ---- src/components/sections/personal/personal-section.tsx ---------------------------------
export const PERSONAL_HEAD = {
  eyebrow: "OFF THE CLOCK",
  heading: [{ t: "A few " }, { t: "true things.", em: true }] as Run[],
  /** The three faint watermark lines behind the section. */
  decor: ["off the clock · off the clock · off the clock", "drums · piano · good noodles", "made in san francisco"],
  photo: "/profile-joshua-tree.webp",
  photoAlt: "Bill Zhang",
  photoCaption: "SHOT · 2025 · LA",
  tipLead: "Try asking the orb:",
  tipQuote: "“What does Bill do for fun?”",
};

// ---- src/components/sections/personal/footer.tsx -------------------------------------------
export const FOOTER = {
  eyebrow: "CONTACT",
  heading: [{ t: "Let's " }, { t: "talk.", em: true }] as Run[],
  heading2: "(Literally.)",
  body: "Tap the talisman and a senior disciple of the sect will answer. Or, if you're old-school, send a normal email. I read every one.",
  direct: "Direct",
  tapOrb: "Ask a senior disciple",
  elsewhere: "Elsewhere",
  index: "Index",
  /** The footer's Index column: label and main-page section id. */
  indexLinks: [
    { label: "Projects", section: "projects" },
    { label: "Hackathons", section: "hackathons" },
    { label: "Experience", section: "experience" },
  ],
  copyright: "© 2026 BILL ZHANG",
};
