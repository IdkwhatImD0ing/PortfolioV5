# Research

Background research for the portfolio site and its voice agent. Nothing here is
loaded by the site or the server. It is kept so that later changes to site copy,
agent prompts or the voice stack can be checked against what was found before.

The JSON files are raw web-search and extract results (Parallel API). Each one
holds a list of pages with their URL, title and quoted excerpts.

## Files

| File | What it is |
|---|---|
| `fact-audit/fact-audit-general-claims.json` | Sources for general statistics the site quotes (for example 911 staffing, World Bank Findex, active-recall studies). |
| `fact-audit/fact-audit-personal.json` | Search results about the owner's own profiles. Many hits are other people with the same name. Two data-broker results were removed before the first commit. |
| `fact-audit/fact-audit-projects.json` | Devpost and hackathon pages that back up project and award claims (part 1). |
| `fact-audit/fact-audit-projects-2.json` | Same, part 2. One lead-generation result with a third party's contact details was removed before the first commit. |
| `devpost/devpost-award-verification.json` | Hackathon pages used to confirm specific awards. |
| `devpost/devpost-known-voice-projects.json` | Devpost pages of the owner's voice projects (AdaptEd, Vocalyze, SoundSearch, Dispatch AI and others). |
| `devpost/devpost-profile-voice-extract.json` | The owner's Devpost profile, extracted to list voice projects. |
| `voice-platforms/retell-vs-elevenlabs-agents.md` | April 2026 comparison of Retell AI and ElevenLabs Agents for this voice agent, including how hard a move would be. |
| `voice-platforms/retell-vs-elevenlabs-agents.json` | The raw research run behind that report, with per-field reasoning and sources. |
| `visual-audit-2026-09.md` | Design audit of the live site (art3m1s.me), September 24-25, 2026, with ranked fixes. |
| `guardrail-handoff.md` | Notes from the `server/guardrail.py` evaluation: traps hit, known weaknesses, open decisions. Its branch and PR #19 refer to the old PortfolioV4 repo. |

The fact-audit, devpost and voice-platform files were carried over from
PortfolioV4 (file dates May 23, 2026). They used to sit at the repo root.

## Research kept elsewhere

These stay where they are because tools or docs link to them by path.

- `blender/xianxia-sect/docs/`: asset, web and AI-video research for the /sect
  fly-through, the Jin Yong references and the architecture audit.
  `tools/rblender.py` uploads this folder to the render box.
- `blender/xianxia-sect/out/seedance_prompts.md`: the Seedance video prompt
  plan, linked from `client/docs/interactive-flight-plan.md`.
- `music/sect-themes/`: the Suno prompts for each area's music.
