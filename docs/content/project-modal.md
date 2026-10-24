# Project Modal Data

> Moved here from `client/docs/` on 2026-10-24, when every doc moved into `docs/`. File paths inside it are relative to `client/`.

Project cards and modals are driven by `src/lib/portfolio-data.ts`.

- Use each project's GitHub README as the source of truth for `summary`, `long`, `stack`, and external links.
- Put YouTube demos in `videoUrl`. The modal always prefers `videoUrl` and renders it as an embedded iframe.
- Put generated card stills in `poster`. Posters live in `public/project-posters/` and are rendered in the horizontal project cards.
- Keep `demo` for non-YouTube media, such as Devpost gallery images or static preview assets.
- Keep `projectUrl` for live sites, Devpost pages, or project walkthrough pages that are not the primary video.

The project view in the sect's forge reader (`src/app/sect/content/sections/forge.tsx`, with `projectMedia()` in `src/lib/sect/content.ts`) falls back from YouTube embed to image preview to a branded placeholder. (The one-page portfolio's modal it was modelled on was archived when the sect became the home page.)
When a YouTube embed is rendered, do not show a duplicate "Watch on YouTube" action; reserve the demo-media action for non-embedded demos.

The project rail defaults to a curated six-project set of awarded projects. The full `PROJECTS` array should still include the broader archive because voice commands, filters, and direct project opens can surface non-curated projects on demand.

Only put a project in the `winner` tag or show an `award` badge when the award is publicly verified or owner-confirmed. Unverified hackathon recognitions should stay as normal project context, not award labels.
