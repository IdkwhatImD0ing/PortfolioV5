# Sect content inventory

Generated from `client/src/lib/sect/content-inventory.ts`. Do not edit by hand; after changing that file, run `SECT_WRITE_INVENTORY=1 pnpm exec vitest run src/lib/sect/content-inventory.test.ts` in `client/`. Paths below are relative to `client/`.

Every piece of content and every interaction on the old page (the one-page portfolio that was `src/app/page.tsx` until the sect replaced it as the home page; archived), and where it lives in the sect. `src/app/sect/content/content-completeness.test.tsx` renders every area reader and the one-page view and fails if any text or link below marked carried or adapted is missing.

## How a visitor reaches content in the sect

1. Fly: scroll (or use the area rail) through the eleven areas. The camera holds at each one and its summary panel appears. The panel's button opens the reader for that area.
2. Click a thing in the scene (an artifact, a banner, a tablet...). The reader opens at that item. The map's list of places (the Map button, or M) does the same.
3. Inside a reader, Previous / Next go to the neighbouring areas, and links inside the content (hero chips, a win's "Open project") jump across areas.
4. Read as one page: every reader's content on one scrolling page with a menu of the eleven areas. It is also what a browser without WebGL gets. It opens at `#<section id>` or `#project/<id>`.

| Area | Place | Old page's section |
| --- | --- | --- |
| gate | Mountain Gate (山门) | Welcome (#hero) |
| mirror | Heart-Mirror Terrace (心镜台) | About (#about) |
| forge | Artifact Forge Peak (炼器峰) | Projects (#projects) |
| arena | Sword-Discussion Arena (论剑台) | Hackathons (#hackathons) |
| mission | Mission Hall (任务殿) | Experience (#experience) |
| library | Scripture Pavilion (藏经阁) | Education (#education) |
| steles | Stele Forest (碑林) | Skills (#skills) |
| scroll | Jade Slip Pavilion (玉简阁) | Resume (#resume) |
| formation | Grand Sect-Protecting Formation (护宗大阵) | How this site works (#architecture) |
| abode | Cave Abode (洞府) | Off the clock (#personal) |
| summit | Moon-Gazing Terrace (望月台) | Contact (#footer) |

166 entries: 117 carried, 19 adapted (same content, different presentation), 8 handled by the 3D page, 22 not carried (each with its reason).

## Page shell (layout.tsx, page.tsx) (3)

- [x] **C-001** Document title and description, Open Graph and Twitter cards. *adapted.* The root layout (src/app/layout.tsx) sets the site's title ("Bill Zhang · Sun Moon Divine Sect"), description, Open Graph and Twitter cards; the share image is a frame of the Mountain Gate (public/og-image.jpg). While a reader is open the tab names its section. The description's facts (Pinterest, 36 wins, talk to it) are in the gate reader. Same person and facts, worded for the sect. The sect is the indexed home page; under the flight the server renders the whole portfolio as text (app/sect/summary.tsx) for crawlers and for visitors without JavaScript.
- [x] **C-002** JSON-LD Person record (Software Engineer II at Pinterest; alumni of USC and UC Santa Cruz; knows AI, ML, conversational AI, voice agents). *carried.* The root layout's application/ld+json block, now also linking GitHub, LinkedIn and Devpost (sameAs). The same facts are visible in the Mission Hall (role) and Scripture Pavilion (schools).
- [x] **C-003** Favicons, web manifest, theme colour. *carried.* The root layout's, as before.

## Top bar (2)

Reader: Mountain Gate (山门). Scroll (or use the area rail) to the Mountain Gate and press "Open" on its panel; or Previous / Next from a neighbouring reader; or "Welcome" in the one-page view (#hero).

- [x] **C-004** Name pill "Bill Zhang". *carried.* Mountain Gate reader. In the intro line; also the one-page view's title.
- [x] **C-005** San Francisco clock "SF · HH:MM" (America/Los_Angeles, 24 h). *carried.* Mountain Gate reader.

## Scroll progress bar (1)

- [x] **C-006** Thin bar at the top showing how far down the page you are. *3D page.* The 3D page's area rail shows where you are in the flight.

## Custom cursor, background stage, speech waveform (1)

- [ ] **C-007** Decorative cursor ring, gradient backdrop, animated waveform beside the hero eyebrow. *not carried.* Not in the sect. Decoration only. The 3D scene is the backdrop and the sect uses the normal cursor.

## Backend warm-up (1)

- [x] **C-008** Pings the voice backend on load so a call starts fast. *3D page.* Only matters when the 3D page offers a voice call (onTalk).

## Hash landing and deep links (1)

- [x] **C-009** Landing on /#section or /#project/<id> keeps the target in view. *adapted.* parseContentHash() reads #<section id>, #<area id> and #project/<id>, in any letter case; a project id outside the 15 opens the forge reader, which loads it from the archive or says it couldn't find it, and a malformed hash is ignored. The 3D page flies there and opens the reader; the one-page view (also /?view=page) jumps there. On the old page, opening a project pushes #project/<id>, so Back closes it and the address can be shared. In the sect that history handling belongs to the 3D page (sect-experience.tsx); the reader reports a project opened or closed inside it through onItemChange for that.

## Hero (#hero) (11)

Reader: Mountain Gate (山门). Scroll (or use the area rail) to the Mountain Gate and press "Open" on its panel; or Previous / Next from a neighbouring reader; or "Welcome" in the one-page view (#hero).

- [ ] **C-010** Eyebrow "VOICE-DRIVEN PORTFOLIO · 2026". *not carried.* Not in the sect. Cut to keep the gate reader short.
- [ ] **C-011** Headline "Ask me anything." *not carried.* Not in the sect. Cut to keep the gate reader short.
- [x] **C-012** Intro paragraph (I'm Bill Zhang ... ask it something.) *adapted.* Mountain Gate reader. The last two sentences are left out.
- [x] **C-013** Tagline "AI engineer" (portfolio data). *carried.* Mountain Gate reader. Also on the gate's summary panel.
- [x] **C-014** "View resume" button (jumps to the resume). *carried.* Mountain Gate reader. The button goes to the Jade Slip Pavilion reader.
- [x] **C-015** "Download PDF 113 KB" (downloads /resume.pdf as Bill-Zhang-Resume.pdf). *carried.* Mountain Gate reader. Also on the Jade Slip Pavilion panel and reader.
- [x] **C-016** Question chip "Who is Bill?" (moves to About). *carried.* Mountain Gate reader. A question chip; it goes to the Heart-Mirror Terrace.
- [x] **C-017** Question chip "What voice AI projects has he built?" (moves to Projects, filtered by voice). *carried.* Mountain Gate reader. A question chip; it goes to the Artifact Forge Peak.
- [x] **C-018** Question chip "Show me the hackathon wins." (moves to Hackathons). *carried.* Mountain Gate reader. A question chip; it goes to the Sword-Discussion Arena.
- [x] **C-019** Question chip "What does he do for fun?" (moves to Off the clock). *carried.* Mountain Gate reader. A question chip; it goes to the Cave Abode.
- [x] **C-020** Question chip "Take me to his projects." (moves to Projects). *carried.* Mountain Gate reader. A question chip; it goes to the Artifact Forge Peak.

## Voice orb (components/voice-orb) (6)

- [x] **C-021** Orb button "Ask a senior disciple by voice" and pill "Ask a senior disciple · or scroll". *3D page.* The 3D page passes onTalk; the content shows "Ask a senior disciple" on the gate and summit panels, in the gate reader, in the contact reader, and on the moon hotspot. Without onTalk they are left out. The orb (components/voice-orb) is dressed by sect.css as a 传音符 (a sound-transmission talisman): a jade seal stamped 音, "Ask a senior disciple" on hover and keyboard focus, glowing while it listens and speaks; its pill shows on the intro screen only, because at the stops it covered the scene's own objects.
- [x] **C-022** Voice call panel: Retell call, status lines, transcript, text chat mode, end call. *3D page.* Runs through onTalk on the 3D page. The content layer has no call UI of its own, but keeps the orb usable over its modals: the reader and the one-page view never pull focus out of the orb, a reader the agent opens mid-reply leaves the caret in the chat box, and Tab goes from a modal's last control to the orb.
- [x] **C-023** Panel title "Ask anything." *3D page.* The voice orb in the sect shows it in its own panel.
- [x] **C-024** Suggestion "Show me only the voice AI projects." with reply "Filtering by voice + AI." *3D page.* The voice orb in the sect lists it in its own panel. The gate's Sword Monoliths view also lists the question, without the reply.
- [x] **C-025** Suggestion "Highlight SentinelAI." with reply "Focusing SentinelAI." *3D page.* The voice orb in the sect lists it in its own panel. The gate's Sword Monoliths view also lists the question, without the reply.
- [x] **C-026** Suggestion "Tell me more about Dispatch AI." with reply "Opening Dispatch AI deep-dive." *3D page.* The voice orb in the sect lists it in its own panel. The gate's Sword Monoliths view also lists the question, without the reply.

## About (#about) (6)

Reader: Heart-Mirror Terrace (心镜台). Scroll (or use the area rail) to the Heart-Mirror Terrace and press "Open" on its panel; or Previous / Next from a neighbouring reader; or "About" in the one-page view (#about).

- [ ] **C-027** Eyebrow "ABOUT" and heading "A builder who listens first." *not carried.* Not in the sect. The reader's title already says About.
- [x] **C-028** Sticky cards that stack as you scroll. *adapted.* Heart-Mirror Terrace reader. The four cards become a plain list in the same order.
- [x] **C-029** Card 01 / WHO: "Most of my work is failure handling." and its paragraph. *adapted.* Heart-Mirror Terrace reader. Clicking the bronze mirror (hotspot mirror) opens it too. The "01 / WHO" label is left out.
- [x] **C-030** Card 02 / WHAT: "Software you can talk to." and its paragraph. *adapted.* Heart-Mirror Terrace reader. Clicking the bronze mirror (hotspot mirror) opens it too. The "02 / WHAT" label is left out.
- [x] **C-031** Card 03 / HOW: "One idea, end to end, in 36 hours." and its paragraph. *adapted.* Heart-Mirror Terrace reader. Clicking the bronze mirror (hotspot mirror) opens it too. The "03 / HOW" label is left out.
- [x] **C-032** Card 04 / WHY: "Talking is the interface of the future." and its paragraph. *adapted.* Heart-Mirror Terrace reader. Clicking the bronze mirror (hotspot mirror) opens it too. The "04 / WHY" label is left out.

## Projects (#projects) (24)

Reader: Artifact Forge Peak (炼器峰). Scroll (or use the area rail) to the Artifact Forge Peak and press "Open" on its panel; or Previous / Next from a neighbouring reader; or "Projects" in the one-page view (#projects).

- [ ] **C-033** Eyebrow "PROJECTS · <count>" (6 STANDOUTS, or matches/15 when filtered) and heading "Things I shipped." *not carried.* Not in the sect. The reader's title already says Projects.
- [ ] **C-034** "Curated gallery" and "Ask by voice for any project, or filter the archive." *not carried.* Not in the sect. Cut: the filters explain themselves.
- [ ] **C-035** Phone hint "Swipe the cards, ask by voice, or filter the archive." and the "SCROLL ↓ drives gallery →" footer. *not carried.* Not in the sect. They describe the phone carousel and the scroll-driven rail, which the reader replaces with a grid of cards.
- [x] **C-036** Filters: Standouts, Voice, AI, Fintech, Safety, Education, 3D, Winners, and year toggles 2025, 2024. *adapted.* Artifact Forge Peak reader. Filter buttons sit above the cards; the orb suggestion "Show me only the voice AI projects." opens the forge filtered. Same filters and rules as the old page (a year narrows, picking a filter clears the year). Two filters are added: "On the ring", the default, lists the 11 prize winners whose artifacts circle the cauldron, biggest win first; "All 15" lists every project. "Standouts" still shows the old page's six hand-picked projects in their order.
- [x] **C-037** Match count ("6/15 standouts", "n/15 match"). *adapted.* Artifact Forge Peak reader. Announced politely to screen readers when it changes. The default view counts the ring's winners ("11/15 on the ring"); a filter shows "n/15 match" and Standouts "6/15 standouts", as on the old page.
- [x] **C-038** Project cards: poster, award badge, /id, "↗ deep dive", name, summary, #tags, year. *adapted.* Artifact Forge Peak reader. Hovering a card lights its artifact in the scene. A grid instead of the horizontal scroll rail and the phone carousel with dots. The "↗ deep dive" label is left out; the whole card opens.
- [x] **C-039** Project detail view: eyebrow (award or Project · year), name, summary, demo video / image / placeholder, The story, Role, Stack, Year, ID, Tags, demo / live / GitHub links, voice tip, close with Esc. *adapted.* Inside the forge reader: press a project's name or card, click its artifact in the scene (hotspot project:<id>), or pick it in the map's list of places. Esc or "Back" goes back to the list; arrows step to the previous/next project. Shown in the reader sheet instead of a second modal. YouTube demos load when you press Play (the 3D scene already uses the GPU), and a "Watch on YouTube" link is always there. The voice tip is left out, and the eyebrow shows only an award (the Year row has the year).
- [x] **C-040** Projects outside the 15 that the voice agent can open (Pinecone corpus, lazy-loaded). *carried.* Forge reader, when a deep link (#project/<id>, ?open=project:<id>) or a voice command names one: the detail loads from the same corpus, like the old page. An id that is not there either shows "Couldn't find project".
- [ ] **C-041** Voice feedback lines ("Filtering by voice.", "Focusing on X.", "Opening X."). *not carried.* Not in the sect. They echo voice commands. The filter state and match count show the same result.
- [x] **C-042** Project SentinelAI (sentinelai): summary, story, role, 8 stack items, year 2025, tags #ai #voice #safety, GitHub link, demo video, poster. *carried.* Forge reader, SentinelAI detail: click its artifact (hotspot project:sentinelai), its card in the forge reader, or the map's list of places. Deep link #project/sentinelai in the one-page view.
- [x] **C-043** Project CourtVision (courtvision): summary, story, role, 6 stack items, year 2025, tags #ai #voice #3d, GitHub link, demo media link, poster. *carried.* Forge reader, CourtVision detail: click its artifact (hotspot project:courtvision), its card in the forge reader, or the map's list of places. Deep link #project/courtvision in the one-page view.
- [x] **C-044** Project Dispatch AI (dispatchai): summary, story, role, 6 stack items, award "Grand Prize, UC Berkeley AI Hackathon 2024", year 2024, tags #ai #voice #safety #winner, GitHub link, demo video, live project link, poster. *carried.* Forge reader, Dispatch AI detail: click its artifact (hotspot project:dispatchai), its card in the forge reader, or the map's list of places. Deep link #project/dispatchai in the one-page view.
- [x] **C-045** Project TalkTuahBank (talktuahbank): summary, story, role, 6 stack items, award "Grand + Goldman Sachs, HackUTD 2024", year 2024, tags #voice #fintech #ai #winner, GitHub link, demo video, live project link, poster. *carried.* Forge reader, TalkTuahBank detail: click its artifact (hotspot project:talktuahbank), its card in the forge reader, or the map's list of places. Deep link #project/talktuahbank in the one-page view.
- [x] **C-046** Project AdaptEd (adapted): summary, story, role, 6 stack items, award "Google Challenge, LA Hacks 2024", year 2024, tags #ai #voice #education #winner, GitHub link, demo video, poster. *carried.* Forge reader, AdaptEd detail: click its artifact (hotspot project:adapted), its card in the forge reader, or the map's list of places. Deep link #project/adapted in the one-page view.
- [x] **C-047** Project SlugLoop (slugloop): summary, story, role, 7 stack items, award "MLH GitHub, CruzHacks 2023", year 2023, tags #transit #social-good #winner, GitHub link, demo video, live project link, poster. *carried.* Forge reader, SlugLoop detail: click its artifact (hotspot project:slugloop), its card in the forge reader, or the map's list of places. Deep link #project/slugloop in the one-page view.
- [x] **C-048** Project Vocalyze (vocalyze): summary, story, role, 4 stack items, award "Letta + Finance, HackMerced X", year 2025, tags #voice #fintech #ai #winner, GitHub link, demo video, poster. *carried.* Forge reader, Vocalyze detail: click its artifact (hotspot project:vocalyze), its card in the forge reader, or the map's list of places. Deep link #project/vocalyze in the one-page view.
- [x] **C-049** Project SoundSearch (soundsearch): summary, story, role, 4 stack items, award "NLX Overall, AI ATL 2024", year 2024, tags #voice #ai #accessibility #winner, GitHub link, demo video, live project link, poster. *carried.* Forge reader, SoundSearch detail: click its artifact (hotspot project:soundsearch), its card in the forge reader, or the map's list of places. Deep link #project/soundsearch in the one-page view.
- [x] **C-050** Project SwarmAid (swarmaid): summary, story, role, 5 stack items, award "2nd Place, Hack Dearborn 2024", year 2024, tags #ai #social-good #winner, GitHub link, demo video, poster. *carried.* Forge reader, SwarmAid detail: click its artifact (hotspot project:swarmaid), its card in the forge reader, or the map's list of places. Deep link #project/swarmaid in the one-page view.
- [x] **C-051** Project SecWay (secway): summary, story, role, 4 stack items, year 2025, tags #ai #security, GitHub link, demo video, poster. *carried.* Forge reader, SecWay detail: click its artifact (hotspot project:secway), its card in the forge reader, or the map's list of places. Deep link #project/secway in the one-page view.
- [x] **C-052** Project SlugMeditate (slugmeditate): summary, story, role, 5 stack items, year 2025, tags #ai #3d, GitHub link, demo media link, poster. *carried.* Forge reader, SlugMeditate detail: click its artifact (hotspot project:slugmeditate), its card in the forge reader, or the map's list of places. Deep link #project/slugmeditate in the one-page view.
- [x] **C-053** Project TalkTuahDuck (talktuahduck): summary, story, role, 5 stack items, year 2025, tags #ai #voice #education, GitHub link, demo video, poster. *carried.* Forge reader, TalkTuahDuck detail: click its artifact (hotspot project:talktuahduck), its card in the forge reader, or the map's list of places. Deep link #project/talktuahduck in the one-page view.
- [x] **C-054** Project TeamFood Tactics (tft): summary, story, role, 5 stack items, award "Sustainability, SpartaHack X", year 2025, tags #voice #ai #winner, GitHub link, demo media link, poster. *carried.* Forge reader, TeamFood Tactics detail: click its artifact (hotspot project:tft), its card in the forge reader, or the map's list of places. Deep link #project/tft in the one-page view.
- [x] **C-055** Project SplatNFT (splatnft): summary, story, role, 5 stack items, award "SolanaU, SoCal Tech Week", year 2024, tags #3d #web3 #winner, GitHub link, demo media link, live project link, poster. *carried.* Forge reader, SplatNFT detail: click its artifact (hotspot project:splatnft), its card in the forge reader, or the map's list of places. Deep link #project/splatnft in the one-page view.
- [x] **C-056** Project InstaRizz (instarizz): summary, story, role, 5 stack items, year 2024, tags #ai #wearable, GitHub link, demo video, poster. *carried.* Forge reader, InstaRizz detail: click its artifact (hotspot project:instarizz), its card in the forge reader, or the map's list of places. Deep link #project/instarizz in the one-page view.

## Hackathons (#hackathons) (42)

Reader: Sword-Discussion Arena (论剑台). Scroll (or use the area rail) to the Sword-Discussion Arena and press "Open" on its panel; or Previous / Next from a neighbouring reader; or "Hackathons" in the one-page view (#hackathons).

- [ ] **C-057** Eyebrow "HACKATHONS · 36 WINS", heading "Thirty-six wins." and intro. *not carried.* Not in the sect. The panel and the stat tiles carry the numbers.
- [x] **C-058** Two scrolling marquee rows (first 18, last 18). *adapted.* Sword-Discussion Arena reader. One list of all 36 banners in the same order. Nothing moves, so nothing has to be caught. The reader also shows each win's project (a field of the data the marquee leaves out), with a link to it in the forge when it is one of the 15.
- [x] **C-059** Stat "36" Hackathons won. *carried.* Sword-Discussion Arena reader.
- [x] **C-060** Stat "$74k" Largest prize. *carried.* Sword-Discussion Arena reader.
- [x] **C-061** Stat "$150k+" Prizes won. *carried.* Sword-Discussion Arena reader.
- [x] **C-062** Stat "17" Colleges visited. *carried.* Sword-Discussion Arena reader.
- [x] **C-063** Hackathon 1: Berkeley AI Hackathon 2024, DispatchAI, Grand Prize · $25k SkyDeck. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:0.
- [x] **C-064** Hackathon 2: HackUTD 2024, TalkTuahBank, Grand Prize + Goldman Sachs. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:1.
- [x] **C-065** Hackathon 3: HackDavis 2025, SentinelAI, Best AI/ML Hack. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:2.
- [x] **C-066** Hackathon 4: VTHacks 2024, linguify, Best Startup Hack. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:3.
- [x] **C-067** Hackathon 5: YaleHacks 2024, Tidbits, 1st Place. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:4.
- [x] **C-068** Hackathon 6: LAHacks 2024, AdaptED, Google Challenge. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:5.
- [x] **C-069** Hackathon 7: AIATL 2023, WebWeaver, Most Innovative Startup. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:6.
- [x] **C-070** Hackathon 8: AIATL 2024, SoundSearch, NLX Overall. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:7.
- [x] **C-071** Hackathon 9: HackMerced 2025, Vocalyze, Letta AI + Finance. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:8.
- [x] **C-072** Hackathon 10: SpartaHacks 2025, Team Food Tactics, Sustainability. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:9.
- [x] **C-073** Hackathon 11: CruzHacks 2025, SlugMeditate, Niantic WebXR. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:10.
- [x] **C-074** Hackathon 12: SoCalTechWeek 2024, SplatNFT, Solana University. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:11.
- [x] **C-075** Hackathon 13: HackMerced 2024, PyPointer, Letta + Finance. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:12.
- [x] **C-076** Hackathon 14: DiamondHacks 2024, ABSeas, Captain's Classroom. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:13.
- [x] **C-077** Hackathon 15: IrvineHacks 2024, XPlore, Best Travel Hack. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:14.
- [x] **C-078** Hackathon 16: HackDearborn 2024, SwarmAID, 2nd Place. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:15.
- [x] **C-079** Hackathon 17: Uncommon Hacks 2024, Mad Lyrics, Programmatic Art. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:16.
- [x] **C-080** Hackathon 18: HackDavis 2024, Doggo AI, Best Intel Dev Cloud. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:17.
- [x] **C-081** Hackathon 19: QWER Hacks 2024, Talking Terry, Best Google Cloud. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:18.
- [x] **C-082** Hackathon 20: CruzHacks 2023, SlugLoop, MLH GitHub. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:19.
- [x] **C-083** Hackathon 21: CruzHacks 2022, Covinet, QB3 @ UCSC. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:20.
- [x] **C-084** Hackathon 22: SBHacks 2023, GitPT, Student Life Hack. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:21.
- [x] **C-085** Hackathon 23: HackDavis 2023, IntelliConverse, Best MongoDB Atlas. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:22.
- [x] **C-086** Hackathon 24: CitrusHacks 2023, MonkeySign, New Frontiers. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:23.
- [x] **C-087** Hackathon 25: ACMHacks 2023, Assistance, Best Global Solution. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:24.
- [x] **C-088** Hackathon 26: Hackrithmitic 2023, PaddyPlantPrognosis, Best Data Science. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:25.
- [x] **C-089** Hackathon 27: AI Hacks 2022, Progno D, 1st Overall. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:26.
- [x] **C-090** Hackathon 28: WildHacks 2022, Wonder, 2nd Overall. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:27.
- [x] **C-091** Hackathon 29: Hacks for Hackers 2023, Architect, 3rd Overall. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:28.
- [x] **C-092** Hackathon 30: Opportunity Hacks 2022, Volunteer Hub, 3rd Place. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:29.
- [x] **C-093** Hackathon 31: Web3Apps 2023, Fundraiser, Microsoft Cloud + Circle. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:30.
- [x] **C-094** Hackathon 32: Planet Unity 2023, Sink or Swim, Top 10. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:31.
- [x] **C-095** Hackathon 33: GraceHacks 2022, Pool Party, Best Mobile. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:32.
- [x] **C-096** Hackathon 34: PeddieHacks 2022, Remote Trainer, Innovation Prize (HS). *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:33.
- [x] **C-097** Hackathon 35: Funathon 2022, Tetris Duels, Participation Prize. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:34.
- [x] **C-098** Hackathon 36: FullyHacks 2024, Tank, 1st Place. *carried.* Sword-Discussion Arena reader. Its banner is hotspot hackathon:35.

## Experience (#experience) (9)

Reader: Mission Hall (任务殿). Scroll (or use the area rail) to the Mission Hall and press "Open" on its panel; or Previous / Next from a neighbouring reader; or "Experience" in the one-page view (#experience).

- [ ] **C-099** Eyebrow "EXPERIENCE" and heading "A short, productive career." *not carried.* Not in the sect. The reader's title already says Experience.
- [ ] **C-100** Timeline spine that draws in on scroll. *not carried.* Not in the sect. Decoration. The roles keep their order.
- [x] **C-101** Role 1: Software Engineer II, Pinterest · San Francisco (Jul 2026 — Now). *carried.* Mission Hall reader. Its jade tablet is hotspot role:0.
- [x] **C-102** Role 2: Applied AI Engineer (Forward-Deployed), Scale AI · San Francisco (Jun 2025 — Jul 2026). *carried.* Mission Hall reader. Its jade tablet is hotspot role:1.
- [x] **C-103** Role 3: AI Engineer, RingCentral · Remote (Jun 2023 — Jun 2025). *carried.* Mission Hall reader. Its jade tablet is hotspot role:2.
- [x] **C-104** Role 4: Co-founder + CFO, Dispatch AI · Remote (Jun 2024 — Dec 2024). *carried.* Mission Hall reader. Its jade tablet is hotspot role:3.
- [x] **C-105** Role 5: Founder, SlugLoop · Santa Cruz (Feb 2023 — Jun 2024). *carried.* Mission Hall reader. Its jade tablet is hotspot role:4.
- [x] **C-106** Role 6: CS Instructor + Teaching Assistant, X-Camp Academy · San Jose (Jun 2022 — Dec 2023). *carried.* Mission Hall reader. Its jade tablet is hotspot role:5.
- [x] **C-107** Role 7: Hackathon Mainstay, 36 wins across the hackathon circuit (2023 — 2025+). *carried.* Mission Hall reader. Its jade tablet is hotspot role:6.

## Education (#education) (5)

Reader: Scripture Pavilion (藏经阁). Scroll (or use the area rail) to the Scripture Pavilion and press "Open" on its panel; or Previous / Next from a neighbouring reader; or "Education" in the one-page view (#education).

- [ ] **C-108** Eyebrow "EDUCATION" and heading "Three schools, one path." *not carried.* Not in the sect. The reader's title already says Education.
- [x] **C-109** Flip cards and the hint "Click a card to flip it." *adapted.* Scripture Pavilion reader. Both faces of each card are shown at once, so nothing hides behind a flip and the hint is not needed.
- [x] **C-110** School 1: University of Southern California (front: logo, number, name, degree, dates; back: notes). *adapted.* Scripture Pavilion reader. Its lit pagoda floor is hotspot school:0. The card number and the NOTES label are left out.
- [x] **C-111** School 2: UC Santa Cruz (front: logo, number, name, degree, dates; back: notes). *adapted.* Scripture Pavilion reader. Its lit pagoda floor is hotspot school:1. The card number and the NOTES label are left out.
- [x] **C-112** School 3: Lynbrook High School (front: logo, number, name, degree, dates; back: notes). *adapted.* Scripture Pavilion reader. Its lit pagoda floor is hotspot school:2. The card number and the NOTES label are left out.

## Skills (#skills) (2)

Reader: Stele Forest (碑林). Scroll (or use the area rail) to the Stele Forest and press "Open" on its panel; or Previous / Next from a neighbouring reader; or "Skills" in the one-page view (#skills).

- [x] **C-113** The skills sentence, with its four tagged phrases set in the accent style. *carried.* Stele Forest reader. The master stele is hotspot steles.
- [x] **C-114** Word-by-word light-up as you scroll. *adapted.* Stele Forest reader. Each of the five stele rows (hotspots skills:0 to skills:4) carries one phrase; hovering or focusing a row lights its words in the sentence. The phrase groups are the sentence's own key phrases: "voice-first" and the four tagged phrases.

## Resume (#resume) (14)

Reader: Jade Slip Pavilion (玉简阁). Scroll (or use the area rail) to the Jade Slip Pavilion and press "Open" on its panel; or Previous / Next from a neighbouring reader; or "Resume" in the one-page view (#resume).

- [ ] **C-115** Eyebrow "RESUME · ONE-PAGER", heading "The printable version." and intro. *not carried.* Not in the sect. The panel and the file line say what it is.
- [x] **C-116** Inline PDF preview of /resume.pdf. *carried.* Jade Slip Pavilion reader. Clicking the giant jade scroll (hotspot resume) opens the reader at the preview.
- [x] **C-117** File line "resume.pdf · last updated September 12, 2026". *carried.* Jade Slip Pavilion reader.
- [x] **C-118** "Open in new tab" and "Download PDF" (Bill-Zhang-Resume.pdf). *carried.* Jade Slip Pavilion reader. Placed above the preview (phones without a PDF viewer show an empty box). The Jade Slip Pavilion panel has its own Download PDF button.
- [x] **C-119** Stat "5+" Years building. *carried.* Jade Slip Pavilion reader.
- [x] **C-120** Stat "36" Hackathon wins. *carried.* Jade Slip Pavilion reader.
- [x] **C-121** Stat "9" Voice apps shipped. *carried.* Jade Slip Pavilion reader.
- [x] **C-122** Stat "$150k+" Prizes won. *carried.* Jade Slip Pavilion reader.
- [x] **C-123** At a glance: AI engineer: voice-first agents, multimodal pipelines, real-time inference. *carried.* Jade Slip Pavilion reader.
- [x] **C-124** At a glance: Pinterest: LLM agent systems, RAG, production guardrails. Previously Scale AI. *carried.* Jade Slip Pavilion reader.
- [x] **C-125** At a glance: USC: M.S. Computer Science, AI specialization. *carried.* Jade Slip Pavilion reader.
- [x] **C-126** At a glance: Stack: TypeScript / Python / Rust, Next.js, Retell, Twilio, Mistral, Llama. *carried.* Jade Slip Pavilion reader.
- [x] **C-127** Get in touch: billzhangsc@gmail.com, github.com/IdkwhatImD0ing, linkedin.com/in/bill-zhang1. *carried.* Jade Slip Pavilion reader.
- [ ] **C-128** Voice tip “Send me your resume.” → opens the download. *not carried.* Not in the sect. Cut to keep the reader short.

## Architecture (#architecture) (12)

Reader: Grand Sect-Protecting Formation (护宗大阵). Scroll (or use the area rail) to the Grand Sect-Protecting Formation and press "Open" on its panel; or Previous / Next from a neighbouring reader; or "How this site works" in the one-page view (#architecture).

- [x] **C-129** Eyebrow "HOW THIS SITE WORKS", heading "A portfolio that talks back." and intro. *adapted.* Grand Sect-Protecting Formation reader. The eyebrow and heading are left out; the reader's title names the section.
- [x] **C-130** Flow step 01: Mic input. *carried.* Grand Sect-Protecting Formation reader. Its array-flag pillar is hotspot arch:0.
- [x] **C-131** Flow step 02: LLM agent. *carried.* Grand Sect-Protecting Formation reader. Its array-flag pillar is hotspot arch:1.
- [x] **C-132** Flow step 03: Tool calls. *carried.* Grand Sect-Protecting Formation reader. Its array-flag pillar is hotspot arch:2.
- [x] **C-133** Flow step 04: VoiceBus. *carried.* Grand Sect-Protecting Formation reader. Its array-flag pillar is hotspot arch:3.
- [x] **C-134** Flow step 05: Sections react. *carried.* Grand Sect-Protecting Formation reader. Its array-flag pillar is hotspot arch:4.
- [x] **C-135** Flow step 06: Voice reply. *carried.* Grand Sect-Protecting Formation reader. Its array-flag pillar is hotspot arch:5.
- [x] **C-136** Stack group Voice: Retell AI (call runtime, WebRTC), Deepgram speech-to-text, ElevenLabs text-to-speech. *carried.* Grand Sect-Protecting Formation reader. The stack is pillar hotspot arch:6.
- [x] **C-137** Stack group Brain: GPT-5.6 Terra (the agent), GPT-5.6 Luna (guardrail + call summary), OpenAI Agents SDK, nine tools, Site-grounded system prompt. *carried.* Grand Sect-Protecting Formation reader. The stack is pillar hotspot arch:6.
- [x] **C-138** Stack group Frame: Next.js + React 19, Three.js + React Three Fiber + GLSL, A sect modelled and baked in Blender. *carried.* Grand Sect-Protecting Formation reader. The stack is pillar hotspot arch:6.
- [x] **C-139** Stack group State: VoiceBus pub-sub, URL-driven section anchors, Per-section local React state. *carried.* Grand Sect-Protecting Formation reader. The stack is pillar hotspot arch:6.
- [x] **C-140** Code snippet (navigation metadata → VoiceBus → scroll), syntax highlighted. *carried.* Grand Sect-Protecting Formation reader. The code is pillar hotspot arch:7.

## Personal (#personal) (11)

Reader: Cave Abode (洞府). Scroll (or use the area rail) to the Cave Abode and press "Open" on its panel; or Previous / Next from a neighbouring reader; or "Off the clock" in the one-page view (#personal).

- [ ] **C-141** Eyebrow "OFF THE CLOCK" and heading "A few true things." *not carried.* Not in the sect. The reader's title already says Off the clock.
- [ ] **C-142** Watermark lines behind the section. *not carried.* Not in the sect. Decoration.
- [x] **C-143** Photo (/profile-joshua-tree.webp, alt "Bill Zhang") with caption "SHOT · 2025 · LA". *carried.* Cave Abode reader. The moon gate (hotspot abode) opens the reader.
- [x] **C-144** Fact 1: Finished a 4-year CS degree in 2.5 years. *carried.* Cave Abode reader. Its object in the abode is the waterfall (hotspot fact:0).
- [x] **C-145** Fact 2: Won my first hackathon at 17. *carried.* Cave Abode reader. Its object in the abode is the peach tree (hotspot fact:1).
- [x] **C-146** Fact 3: Speaks Mandarin and English; building agents in both. *carried.* Cave Abode reader. Its object in the abode is the cliff inscription (hotspot fact:2).
- [x] **C-147** Fact 4: Plays drums and piano when the laptop is closed. *carried.* Cave Abode reader. Its object in the abode is the qin table of the 笑傲江湖 duet (hotspot fact:3).
- [x] **C-148** Fact 5: Still chasing the best bowl of noodles in San Francisco. *carried.* Cave Abode reader. Its object in the abode is the tea table (hotspot fact:4).
- [x] **C-149** Fact 6: Convinced everyone gets a personal Jarvis eventually: an AI you just talk to, in real time. Building toward it. *carried.* Cave Abode reader. Its object in the abode is the crane (hotspot fact:5).
- [x] **C-150** Fact 7: Would rather talk to software than tap through it. Hence this site. *carried.* Cave Abode reader. Its object in the abode is the koi pool (hotspot fact:6).
- [ ] **C-151** Tip "Try asking the orb: “What does Bill do for fun?”". *not carried.* Not in the sect. The Ask a senior disciple button does the same.

## Footer / contact (11)

Reader: Moon-Gazing Terrace (望月台). Scroll (or use the area rail) to the Moon-Gazing Terrace and press "Open" on its panel; or Previous / Next from a neighbouring reader; or "Contact" in the one-page view (#footer).

- [ ] **C-152** Eyebrow "CONTACT", heading "Let's talk. (Literally.)" and "Tap the talisman and a senior disciple of the sect will answer. Or, if you're old-school, send a normal email. I read every one." *not carried.* Not in the sect. The reader's title already says Contact; the email and the talk button follow.
- [x] **C-153** Direct: email billzhangsc@gmail.com. *carried.* Moon-Gazing Terrace reader. The summit panel also has an Email button.
- [x] **C-154** Direct: "Ask a senior disciple". *carried.* Moon-Gazing Terrace reader. Starts a call through onTalk (left out without it). Clicking the moon (hotspot moon) does the same on the 3D page.
- [x] **C-155** Elsewhere: GitHub (https://github.com/IdkwhatImD0ing). *carried.* Moon-Gazing Terrace reader.
- [x] **C-156** Elsewhere: LinkedIn (https://www.linkedin.com/in/bill-zhang1/). *carried.* Moon-Gazing Terrace reader.
- [x] **C-157** Elsewhere: Devpost (https://devpost.com/IdkwhatImD0ing). *carried.* Moon-Gazing Terrace reader.
- [ ] **C-158** Index: Projects (jumps to #projects). *not carried.* Not in the sect. The reader's Previous / Next and the map (its seals and its list of places) already move between areas.
- [ ] **C-159** Index: Hackathons (jumps to #hackathons). *not carried.* Not in the sect. The reader's Previous / Next and the map (its seals and its list of places) already move between areas.
- [ ] **C-160** Index: Experience (jumps to #experience). *not carried.* Not in the sect. The reader's Previous / Next and the map (its seals and its list of places) already move between areas.
- [x] **C-161** "© 2026 BILL ZHANG". *carried.* Moon-Gazing Terrace reader.
- [x] **C-162** Location "San Francisco, CA" (portfolio data; the old page shows it only as "SF" in the top bar). *carried.* Moon-Gazing Terrace reader.

## Public files (4)

Reader: Jade Slip Pavilion (玉简阁). Scroll (or use the area rail) to the Jade Slip Pavilion and press "Open" on its panel; or Previous / Next from a neighbouring reader; or "Resume" in the one-page view (#resume).

- [x] **C-163** /resume.pdf (preview, open in new tab, download). *carried.* Jade Slip Pavilion panel and reader; gate reader (Download PDF).
- [x] **C-164** Project posters (15 in /project-posters/). *carried.* Forge reader cards and the detail view's video cover.
- [x] **C-165** School logos (/usc.png, /ucsc.png, /lynbrook.png). *carried.* Scripture Pavilion reader.
- [ ] **C-166** github.svg, linkedin.svg, devpost.svg, rocket.png, llms.txt, data.json. *not carried.* Not in the sect. The old page did not use them either.

