---
name: sync-nav-contract
description: Add, rename, or remove a voice-navigation destination by editing all sides of the wire contract in sync (server/navigation.py, server/llm.py, client/src/lib/voice-bus.ts, client/src/lib/sect/areas.ts). Use when the agent needs to navigate to a new section/stop, or when a navigable destination changes.
disable-model-invocation: true
---

# Sync the voice → navigation wire contract

The voice agent navigates the site by emitting tool calls that become navigation
metadata, which the browser turns into flights to a stop of the sect (the site's
only page, `/`). That contract spans
**four files in two languages**, and type checking cannot catch drift between
them — so adding a destination by editing only one side silently breaks navigation
at runtime. This skill walks the full edit so every side stays in sync.

Ask the user (or infer from their request) what they want:
- **Add** a new navigable destination, **rename** an existing `page` value, or
  **remove** one.
- The human name of the section and which of the sect's stops presents it.

## The four sources of truth

1. **`server/llm.py`** — the `@tool` function the agent calls (e.g.
   `display_architecture_page`) and its registration in `prepare_functions()`.
   The tool's docstring is what the LLM uses to decide when to navigate there.
2. **`server/navigation.py`** — `_PAGE_TOOLS` maps the tool name → a `page`
   string. `NAVIGATION_PAGES` is derived from it (plus `"project"`). `display_project`
   is special-cased (it carries a `project_id` arg) — don't add it to `_PAGE_TOOLS`.
3. **`client/src/lib/voice-bus.ts`** — `NavigationMeta["page"]` is the union
   of accepted `page` values, and `PAGE_TO_SECTION` maps each `page` → a section
   name. Both must include the new value.
4. **`client/src/lib/sect/areas.ts`** — `AREAS` gives each stop of the sect a
   `sectionId`; the `PAGE_TO_SECTION` value must be one of them, or the
   navigation flies nowhere. The sect's place list in `server/prompts_sect.py`
   names the tool for each stop (a server test checks it).

> Note: `navigation.py`'s docstring still says `PAGE_TO_SECTION` lives in
> `voice-orb.tsx`. It moved to `voice-bus.ts`. Trust the code, not that comment.

## Procedure to ADD a destination

Read all four files first, then edit them together (use a tool name like
`display_<thing>_page`, a `page` value like `<thing>`, and a section name that
is a stop's `sectionId` in `areas.ts`):

1. **`server/llm.py`** — add an `@tool def display_<thing>_page() -> str:` with a
   clear docstring describing *when* the agent should navigate there, returning a
   short confirmation string. Add the function to the list in `prepare_functions()`.
2. **`server/navigation.py`** — add `"display_<thing>_page": "<thing>"` to
   `_PAGE_TOOLS`. (`NAVIGATION_PAGES` updates automatically.)
3. **`client/src/lib/voice-bus.ts`** — add `"<thing>"` to the
   `NavigationMeta["page"]` union **and** a `"<thing>": "<section-id>"` entry to
   `PAGE_TO_SECTION`. TypeScript's `Record<NonNullable<...>, string>` will fail to
   compile if you add to the union but forget the map — that's the safety net.
4. **`client/src/lib/sect/areas.ts`** — make sure a stop's `sectionId` is
   `<section-id>` (a new stop is a Blender and camera change too: see
   `blender/xianxia-sect/spec.md`), and add the tool to that stop's line in
   `server/prompts_sect.py`.

## Procedure to RENAME or REMOVE

Apply the same change across all four files. For a rename, update the `page`
string in `_PAGE_TOOLS`, the union + `PAGE_TO_SECTION` key in `voice-bus.ts`, and
the stop's `sectionId` in `areas.ts` together (the tool name in `llm.py` can stay or change
— keep it consistent with `_PAGE_TOOLS`'s key). For a removal, delete the tool,
its `prepare_functions()` entry, the `_PAGE_TOOLS` row, the union member, the
`PAGE_TO_SECTION` entry, and the tool from the sect prompt's place list.

## Verify

After editing, confirm the contract holds:

```bash
# Backend parity (server/ — uses uv)
uv run pytest tests/ -k "navigation or nav" -v --tb=short

# Frontend: the union/Record mismatch is a compile error, and voice-bus has tests
cd client && pnpm exec vitest run src/lib/voice-bus.test.ts && pnpm typecheck
```

Then hand off to the `navigation-contract-reviewer` subagent for a final
cross-file drift check. If the change affects what the agent *says* when it
navigates, also skim `server/prompts.py` for stale references to the old page set.
