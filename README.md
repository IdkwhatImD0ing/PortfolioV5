<!--
  art3m1s.me · 日月神教 · the Sun Moon Divine Sect
  Bill Zhang's portfolio: a three.js fly-through of a floating xianxia sect, guided by a senior disciple.
  Author: Bill Zhang (@IdkwhatImD0ing)
-->

<a id="top"></a>

<p align="center">
  <a href="https://art3m1s.me"><picture><source media="(prefers-color-scheme: light)" srcset=".github/readme/seal-light.svg"/><img src=".github/readme/seal.svg" width="88" height="88" alt="The sect's seal: a sun held in a crescent moon, cut into a red stone seal"/></picture></a>
</p>

<h1 align="center">日月神教<br/><sub>The Sun Moon Divine Sect</sub></h1>

<p align="center">
  My portfolio site, <a href="https://art3m1s.me"><b>art3m1s.me</b></a>. You fly through a floating mountain sect, and a voice agent can show you around.
</p>

<p align="center">
  <a href="https://github.com/IdkwhatImD0ing/PortfolioV5/actions/workflows/test.yml"><img src="https://img.shields.io/github/actions/workflow/status/IdkwhatImD0ing/PortfolioV5/test.yml?branch=main&style=flat-square&label=tests&labelColor=0e0c14&color=c9a14f" alt="Tests"/></a>
</p>

<p align="center">
  <a href="https://art3m1s.me"><img src="client/public/og-image.jpg" width="100%" alt="The Mountain Gate on art3m1s.me: a red and teal gate with the 日月神教 (Sun Moon Divine Sect) plaque between a sun and a moon, the Heaven Sword and the Dragon Saber on either side, and floating peaks and a big moon behind."/></a>
</p>

<p align="center">
  <img src=".github/readme/brush-rule.svg" width="56%" alt=""/>
</p>

## 山门 · What this is

This repo is my portfolio, live at **[art3m1s.me](https://art3m1s.me)**.

The home page is a flight through 日月神教, a sect on mountain peaks that float above the clouds. Scroll and the camera climbs from the gate to the summit, with one part of the portfolio at each of the eleven stops. You can drag to look around, or press <kbd>M</kbd> for the map and jump to any stop. If you just want the info, **Read as page** shows everything as one plain page without the 3D.

You can also talk to it. Press the talisman button at the bottom right (or click the moon at the summit) and a voice agent answers, by voice or by text. On the sect site it plays a senior disciple. Ask it about my work and it finds the right project and flies you to that stop.

I'm a big Jin Yong fan. 日月神教 is the Sun Moon Divine Sect from his novel *The Smiling, Proud Wanderer*, and art3m1s is Artemis, goddess of the moon, which is why there's a moon everywhere. 19 items from his novels are hidden along the way.

The site went live on October 24, 2026. The previous site still runs at [v4.art3m1s.me](https://v4.art3m1s.me).

## 十一处 · The eleven stops

The camera stops at each of these, in order.

| # | Stop | Portfolio section | What you'll find |
|:-:|---|---|---|
| 1 | 山门 Mountain Gate | Welcome | A five-bay gate with the 日月神教 plaque, guarded by the Heaven Sword and the Dragon Saber |
| 2 | 心镜台 Heart-Mirror Terrace | About | A giant bronze mirror above a still pond. On Medium and High quality, both show live reflections |
| 3 | 炼器峰 Artifact Forge Peak | Projects | A cauldron circled by 11 prize-winning projects, each forged into a magic artifact |
| 4 | 论剑台 Sword-Discussion Arena | Hackathons | A floating duelling ring lined with banners, with a black iron sword driven through it |
| 5 | 任务殿 Mission Hall | Experience | A wall of seven white-jade boards, one for each role |
| 6 | 藏经阁 Scripture Pavilion | Education | A seven-storey pagoda with one glowing floor per school and scrolls circling it |
| 7 | 碑林 Stele Forest | Skills | Rows of glowing stone tablets, one colour per skill area |
| 8 | 玉简阁 Jade Slip Pavilion | Resume | A small pavilion with a jade slip, and the Sword Tomb nearby |
| 9 | 护宗大阵 Grand Sect-Protecting Formation | How this site works | Eight carved pillars with holy-fire braziers around a bronze armillary sphere. Each pillar explains one part of how the site works |
| 10 | 洞府 Cave Abode | Off the clock | A cliff home with a waterfall, a koi pool and a tea pavilion |
| 11 | 望月台 Moon-Gazing Terrace | Contact | The summit under a giant moon. Click the moon to talk to the voice agent |

## 法器 · The stack

| Layer | Tech | Why |
|---|---|---|
| Site | Next.js 15 (App Router), React 19, TypeScript 5, Tailwind v4 | One page that renders the sect, plus the portfolio as text under it for search engines and no-JS browsers |
| 3D | three.js, React Three Fiber, drei, postprocessing, three-mesh-bvh | The fly-through, clicking things in the scene, and the glow |
| Scene build | Blender 5.2 Python, Cycles on a rented cloud GPU, glTF Transform with meshopt, WebP, Git LFS | Every stop is built in Python, with the lighting baked once and loaded in small files |
| Voice and chat | Retell (voice calls), FastAPI, OpenAI Agents SDK, Pusher (page moves and captions) | A streaming agent that can move the page while it talks |
| Search | Pinecone with `text-embedding-3-large` | Finds a project from a description of what it does |
| Hosting | Vercel (site), Docker on Cloud Run (backend) | A push to `main` ships the site |
| Watching it | Vercel Analytics and Speed Insights, [FireTrace](https://tracing.art3m1s.me) | Real-visitor performance, and one trace per agent run |
| Tests | Vitest, pytest, GitHub Actions | CI runs both suites on every push to `main` |

## 宗门图 · Map of the repo

| Folder | What lives there |
|---|---|
| [`client/`](client) | The Next.js site. The fly-through is `src/app/sect/`, its tested logic is `src/lib/sect/`, the talisman is `src/components/voice-orb/`, and the packed scene is `public/sect/full/` |
| [`server/`](server) | FastAPI: the voice WebSocket, text chat, the agent, its navigation and search tools, the guardrail and the two personas |
| [`pinecone/`](pinecone) | A one-shot script: `data.json`, then embeddings, then the Pinecone index |
| [`blender/xianxia-sect/`](blender/xianxia-sect) | Blender Python for every stop (`sect/`), the bake and export scripts, and [`spec.md`](blender/xianxia-sect/spec.md), the scene's contract |
| [`blender/xianxia-sect/tools/`](blender/xianxia-sect/tools) | The packer `sect_pack.py`, the remote Blender runner `rblender.py`, and small data fixes |
| [`docs/`](docs/README.md) | Every doc: the design-decisions log, the scene, the voice agent, deploy, music and research |
| [`browserless/`](browserless) | Deploy script for a separate headless-browser service |
| [`.github/`](.github) | CI workflows and the images in this README |
| [`Makefile`](Makefile) | Install everything, run the server, site and tunnel together, run all tests |

## 入门 · Run it locally

### The site

The fly-through only needs the client.

```bash
git lfs install          # the scene files live in Git LFS
git clone https://github.com/IdkwhatImD0ing/PortfolioV5.git
cd PortfolioV5/client
pnpm install
pnpm dev                 # then open http://localhost:3000
```

Add `?tier=low`, `?tier=mid` or `?tier=high` to force a quality tier, or `?view=page` to read the sect as one plain page. If you cloned before installing Git LFS, run `git lfs pull` to fetch the scene files.

### The voice and text agent

The agent needs the server, a public address so Retell can reach it, and the keys below. Install once, then run each of the last three lines in its own terminal, from the repo root.

```bash
make install-deps                                # uv, pnpm and ngrok, then each app's packages
cd server && uv run uvicorn main:app --reload    # the server, on :8000
ngrok http 8000                                  # a public URL for Retell to reach the server
cd client && pnpm dev                            # the site, on :3000
```

These are the variable names only. Don't commit the real values.

```bash
# server/.env
RETELL_API_KEY=...
OPENAI_API_KEY=...
PINECONE_API_KEY=...
FIRETRACE_API_KEY=...            # optional: records every agent run
PUSHER_SECRET=...                # voice page moves and live captions (server/README.md, "Voice events")

# client/.env.local (see client/.env.local.example)
RETELLAI_API_KEY=...             # server-side only, used by the create-web-call proxy
NEXT_PUBLIC_RETELL_AGENT_ID=...
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=...          # optional: backend URL for warm-up and text chat
```

### The search index

```bash
cd pinecone
python load_data.py      # embeds data.json and uploads it to the Pinecone index
```

It needs `OPENAI_API_KEY` and `PINECONE_API_KEY`, and it writes to the live index, so run it only when the project data changes. See [`docs/voice/pinecone/`](docs/voice/pinecone/README.md).

### The scene

You don't need Blender to run the site: the packed scene is already in `client/public/sect/full/`. To rebuild it, the scripts in `blender/xianxia-sect/sect/` run in Blender 5.2 in background mode (`blender --background --python <script> -- <args>`). The light bake needs a big GPU, so it runs on a rented cloud machine. Start with [`spec.md`](blender/xianxia-sect/spec.md) and [`api_look.md`](blender/xianxia-sect/docs/api_look.md), which shows how to render a preview of any module.

### Tests

```bash
cd client && pnpm lint && pnpm typecheck && pnpm test
cd server && uv run pytest tests/ -m "not integration"   # what CI runs
```

<p align="center">
  <img src=".github/readme/brush-rule.svg" width="56%" alt=""/>
</p>

## 炼器 · How the scene is built

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#15101b','primaryTextColor':'#f5ecdc','primaryBorderColor':'#c9a14f','lineColor':'#c9a14f','secondaryColor':'#2c2233','tertiaryColor':'#0e0c14','fontFamily':'Georgia, serif'}}}%%
flowchart TB
  A["Blender Python<br/>every stop built by code"] --> B["Cycles light bake<br/>on a rented cloud GPU"]
  B --> C["sect_pack.py<br/>glTF, meshopt, WebP, gzip"]
  C --> D[("Per-stop files<br/>in Git LFS")]
  D --> E["three.js in the browser<br/>streams stops as you fly"]
  E --> F["Live layers<br/>reflections, banners, water,<br/>clouds, birds, qi motes"]
```

1. The whole sect is Python that runs inside Blender: one module per stop, plus shared libraries for buildings, props, trees, rock and water. That is about 70,000 lines, not counting one-off patch scripts. A few free photo textures and two CC BY models, the Divine Condor and the gate's guardian lions, come from outside (see [Credits](#鸣谢--credits)).
2. Cycles, Blender's path tracer, bakes the lighting into textures on a rented RTX 5090. A development bake takes about an hour and a half, and the browser only reads the result.
3. [`sect_pack.py`](blender/xianxia-sect/tools/sect_pack.py) packs each stop into its own glTF files and checks every file before installing it. There are about 60 files, close to 200 MB in all: a full set, plus a lighter set for phones. A visitor downloads only one set, a few stops at a time.
4. three.js shows the baked light and adds live layers on top: real reflections in the Heart-Mirror and its pond, banners that wave, flowing water, drifting clouds, birds, cranes, glowing qi motes and peach petals.
5. The loading screen picks Low, Medium or High quality from your device, and you can change it. If frames run slow, it steps down. On a desktop, the stop you're at and two on each side stay at full detail.

Every design choice behind this, with its date and reason, is in the [decisions log](docs/decisions/README.md).

## 传音 · The voice agent

The voice agent is where this portfolio started. As the senior disciple, it never says it's an AI.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#15101b','primaryTextColor':'#f5ecdc','primaryBorderColor':'#c9a14f','lineColor':'#c9a14f','secondaryColor':'#2c2233','tertiaryColor':'#0e0c14','fontFamily':'Georgia, serif'}}}%%
flowchart TB
  U(["Visitor<br/>presses the talisman"]) --> R{{"Retell<br/>voice call"}}
  R --> WS(["FastAPI<br/>WebSocket"])
  WS --> A[["Agents SDK<br/>the senior disciple"]]
  A <--> P[("Pinecone<br/>project search")]
  A --> PU{{"Pusher<br/>page moves, captions"}}
  PU --> B["Browser<br/>ink fast-travel to the stop"]
```

- The agent can move the page. It calls tools like `display_project`, the server sends each call as a small navigation message on the call's Pusher channel, and the browser flies you to that stop and opens the reader.
- Search works by meaning. Every project is embedded in Pinecone, so if you ask "what did you build for emergency dispatch?" it finds DispatchAI even though you never said its name.
- A small classifier checks each question while the main model starts answering. If it flags the question, the answer is cancelled and swapped for a polite refusal. Normal questions don't wait for the check.
- The sect gets the senior disciple. Anything that doesn't ask for a persona gets the classic one (me, in first person), so the old site still works on the same server.
- The server also renders the whole portfolio as plain text under the flight, so search engines, LLMs and browsers without JavaScript can read it. JSON-LD and [`/llms.txt`](https://art3m1s.me/llms.txt) describe the site too.

## 出山 · Deploy and roll back

- **Site.** A push to `main` deploys art3m1s.me on Vercel. The Vercel project needs Git LFS turned on, or visitors get pointer files instead of the scene. To roll back, promote the last good deployment in Vercel, then revert the commit.
- **Backend.** One Cloud Run service serves every site. Ship a new revision with no traffic and a tag, test it at the tag's URL, then move the traffic. Keep the previous revision: rolling back means sending the traffic back to it.
- **Voice agent.** Published Retell agent versions are never overwritten or deleted. A change is a new version or a new agent.

The details are in [`docs/deploy/`](docs/deploy/README.md). There are no secrets in this repo.

## 藏经阁 · The docs

| Read this | To learn |
|---|---|
| [The index](docs/README.md) | Every doc, one line each |
| [Design decisions](docs/decisions/README.md) | Why the site is built this way, one dated entry per decision |
| [The scene](docs/README.md#the-scene-blenderxianxia-sect) | The web pipeline, the walking-route audit, asset research, the Jin Yong references |
| [The voice agent](docs/voice/README.md) | The backend, its endpoints, the agent, the guardrail, search |
| [Deploy and roll back](docs/deploy/README.md) | Shipping and undoing each part |
| [Music](docs/music/sect-themes/README.md) | How each stop's music was made |

<p align="center">
  <img src=".github/readme/brush-rule.svg" width="56%" alt=""/>
</p>

## 画卷 · Gallery

<table>
  <tr>
    <td width="50%"><img src=".github/readme/mirror.jpg" alt="Heart-Mirror Terrace: a round bronze mirror on a marble dais, reflected in a still pond beside a teal-roofed pavilion"/></td>
    <td width="50%"><img src=".github/readme/arena.jpg" alt="Sword-Discussion Arena with its info panel open: Hackathons, 36 wins during college"/></td>
  </tr>
  <tr>
    <td><sub>心镜台 Heart-Mirror Terrace. The still pond reflects the bronze mirror.</sub></td>
    <td><sub>论剑台 Sword-Discussion Arena, with its panel open. "Open" shows all 36 wins.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src=".github/readme/library.jpg" alt="Scripture Pavilion: a red seven-storey pagoda with scrolls drifting around it and a half-ice floating island at top left"/></td>
    <td width="50%"><img src=".github/readme/summit.jpg" alt="Moon-Gazing Terrace: a white-roofed round pavilion under a giant full moon, a dark condor on a rock to the left"/></td>
  </tr>
  <tr>
    <td><sub>藏经阁 Scripture Pavilion. Scrolls circle the pagoda. The ice island at top left is Ice-Fire Island.</sub></td>
    <td><sub>望月台 Moon-Gazing Terrace, the end of the flight. The Divine Condor sits on the rock at left.</sub></td>
  </tr>
</table>

<p align="center">
  <img src=".github/readme/map.jpg" alt="日月神教全图, the map of the sect: an ink-wash painting on a hanging scroll, with a seal on each of the 11 stops joined by a dotted route" width="100%"/>
  <br/>
  <sub>日月神教全图, the map of the sect (press <kbd>M</kbd>). Pick a seal and the camera fast-travels there.</sub>
</p>

## 彩蛋 · Jin Yong easter eggs

19 objects from Jin Yong's novels are hidden along the flight. Hover one (or tap it on a phone) to see what it is.

| Stop | Items | From |
|---|---|---|
| Mountain Gate | 倚天劍 Heaven-Reliant Sword · 屠龍刀 Dragon-Slaying Saber · 日月 Sun and Moon | *Heaven Sword and Dragon Saber* · the sect's name, from *The Smiling, Proud Wanderer* |
| Heart-Mirror Terrace | 玉簫 Huang Yaoshi's Jade Flute · 思過崖 Cliff of Reflection | *Legend of the Condor Heroes* · *The Smiling, Proud Wanderer* |
| Artifact Forge Peak | 金銀銅鐵鉛五輪 Five Metal Wheels | *Return of the Condor Heroes* |
| Sword-Discussion Arena | 玄鐵重劍 Black Iron Heavy Sword · 華山論劍 the seats of the Five Greats | *Return of the Condor Heroes* · *Legend of the Condor Heroes* |
| Mission Hall | 天罡北斗陣 Big Dipper Formation | *Legend of the Condor Heroes* |
| Scripture Pavilion | 冰火島 Ice-Fire Island | *Heaven Sword and Dragon Saber* |
| Stele Forest | 聖火令 the Ming Sect's Holy Flame Tablets · 獨孤九劍 Nine Swords of Dugu | *Heaven Sword and Dragon Saber* · *The Smiling, Proud Wanderer* |
| Jade Slip Pavilion | 劍塚 Sword Tomb | *Return of the Condor Heroes* |
| Grand Formation | 五行旗 the Ming Sect's Five Element Banners · 聖火 the Ming Sect's Holy Flame | *Heaven Sword and Dragon Saber* |
| Cave Abode | 笑傲江湖 Qu Yang and Liu Zhengfeng's duet | *The Smiling, Proud Wanderer* |
| Moon-Gazing Terrace | 神鵰 Divine Condor · 金鈴索 Golden Bell Rope · 綠竹巷 Green Bamboo Lane | *Return of the Condor Heroes* · *The Smiling, Proud Wanderer* |

The stele rows carry martial-arts manuals from the novels too, and each role tablet in the Mission Hall takes one star of the Big Dipper. The research behind them is in [`docs/scene/jin-yong-references.md`](docs/scene/jin-yong-references.md).

## 法宝 · Featured projects

Four of my projects. All four won prizes, and each one circles the cauldron at the forge stop.

- [DispatchAI](https://github.com/IdkwhatImD0ing/DispatchAI)
- [TalkTuahBank](https://github.com/aurelisajuan/TalkTuahBank)
- [SlugLoop](https://github.com/IdkwhatImD0ing/SlugLoop)
- [AdaptEd](https://github.com/IdkwhatImD0ing/AdaptEd)

## 鸣谢 · Credits

- **Divine Condor** model: "Dark Vulture" by [Pigcraft](https://sketchfab.com/s8819296) on Sketchfab, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), reduced and re-textured.
- **Guardian lions**: "Stone Big Lion 01" by [Game industry veteran](https://sketchfab.com/zhengzhangxun) on Sketchfab, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), reduced, re-textured and adapted (the male is mirrored, with an embroidered ball in place of the cub).
- **Photo textures** from [Poly Haven](https://polyhaven.com) and [ambientCG](https://ambientcg.com). Pine twig texture: "Pine Tree 01" by Rob Tuytel and Rico Cilliers. Mist flipbooks by Thomas Iché (Unity Labs), via the Brackeys VFX Bundle. Waterfall texture by Martin Vorel (LibreShot). All CC0.
- The full list is in [`blender/xianxia-sect/assets/CREDITS.md`](blender/xianxia-sect/assets/CREDITS.md).
- The sect, its treasures and its martial arts come from the novels of **Jin Yong** (金庸).

## 传书 · Connect

<p align="center">
  <a href="https://art3m1s.me"><b>art3m1s.me</b></a> ·
  <a href="https://www.linkedin.com/in/bill-zhang1/">LinkedIn</a> ·
  <a href="https://github.com/IdkwhatImD0ing">GitHub</a> ·
  <a href="https://devpost.com/IdkwhatImD0ing">Devpost (36 hackathon wins)</a> ·
  <a href="mailto:billzhangsc@gmail.com">Email</a>
</p>

<p align="center">
  <img src=".github/readme/brush-rule.svg" width="56%" alt=""/>
</p>

<p align="center">
  <a href="#top">回到山门 · Back to the gate</a>
</p>
