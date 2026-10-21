# Keeping the flyer and the sect consistent across AI video clips

Research done 2026-10-10 (web sources, no credits spent). Seedance and Higgsfield change fast:
re-check anything marked *unverified* before relying on it.

## The short version

Seedance 2.5 on Higgsfield can hold a character and a place steady across separate clips, as
long as every clip is given **the same references**, not just the previous clip's output.

The approach that fits this project:

1. **Camera and timing come from Blender.** Each generation gets its blocking clip as a
   reference video ("@Video 1: camera, timing and framing only").
2. **The flyer's look comes from one saved character.** Make a character sheet once (front,
   three-quarter, side, back), save it as a Higgsfield *Element* and attach it to every clip.
3. **Each place's look comes from one approved keyframe.** For each of the 11 areas, turn
   the Blender hero still into a finished painting-quality frame with an image model. Pick
   the best, save it as an Element, and attach it to every clip that shows that area.
4. **Seams:** give each clip the previous clip's last frame as its "opening state" reference,
   overlap clips by about half a second, and cross-fade them on the website.

## What Seedance 2.5 can take (verified, Sep 2026)

| | |
|---|---|
| Reference mode ("omni reference") | up to 30 images, 10 videos, 10 audio files (50 total); reference videos and audio up to 30 s total each |
| First/last-frame mode | 1–2 still images; **cannot be combined with reference images or videos** in the same generation |
| Prompt syntax | "@Image 1", "@Video 1", "@Audio 1"; saved Elements are pulled in with "@name" |
| Length | 4–30 s per generation; *Extend* continues a clip (nested up to ~60 s) |
| Resolution | 480p, 720p, 1080p (1080p on Plus plans and up) |
| Reference video rules | 2–30 s per clip, 24–60 fps, at least ~0.4 MP. The 1280×720 blocking clips qualify. |
| Fixing | *Seedance 2.5 Edit* fixes one region of a finished clip (480–720p), cheaper than re-rolling |

Sources: Higgsfield API docs (docs.higgsfield.ai/docs/models/seedance-2-5/reference-to-video),
BytePlus Seedance 2.5 tutorial (docs.byteplus.com/docs/ModelArk/2607688, updated Sep 2026),
Higgsfield help centre "How do I use Seedance" (updated Sep 9 2026).

**Known weaknesses:**
- Grey blocking shapes "inflate and morph": the camera path is followed closely, but
  geometry is not locked (Seadanse tests, Sep 16 2026).
- Readable text (plaques, stele glyphs, the scroll's calligraphy) comes out garbled. Add it on
  the website instead. The interactive plan already projects real text onto the scroll and
  tablets.
- Object counts (15 artifacts, 7 tablets) may drift. *Unverified, inferred from the
  morphing reports.*

## The flyer

- **Decided 2026-10-10:** the flyer is a fictional cultivator (not the user) in **purple robes**, so
  no Soul ID is needed. The notes on real faces below are kept for reference.
- **If the flyer were you:** Higgsfield's route is *Soul ID*. Upload 20–80 photos of yourself
  and train once (about 25 credits). It then appears as an Element in Seedance. Expect
  "clearly the same person", not pixel-identical. Seedance itself blocks direct uploads of
  real faces unless they're verified, so don't plan on just attaching a selfie. Whether
  Higgsfield's web app blocks a raw selfie is *unverified*.
- **Character sheet:** separate images per view are steadier than one collage. The chase
  camera sees the flyer mostly from behind, so the **back and rear three-quarter views
  matter most**. Popcorn (about 5 credits for a set of up to 8 consistent frames) can make
  the sheet.
- **One fixed description, word for word in every prompt**, for example: "a young cultivator
  in flowing deep violet hanfu with wide trailing sleeves, black hair in a topknot with
  a silver pin and silver ribbons, lilac sash ribbons, standing on a glowing jade flying
  sword with a cyan light trail".
- Re-attach the original sheet to every clip. Chaining only from the last output lets drift
  build up.

## The architecture

- Make one finished keyframe per area from the Blender hero still
  (`out/stills/hero_<area>.png`), using an image model's edit mode. fal's tests used Nano Banana
  Pro edit (about 2 credits per image); Seedream 5 Pro and GPT Image 2 are alternatives.
- Prompt pattern that held geometry in tests (fal, Jul 2026): *"Image 1 is the ONLY source of
  truth for geometry and composition. Repaint surfaces only."* Plus one fixed style
  paragraph reused word for word, with the palette as hex colours.
- Check each keyframe by overlaying it on the Blender frame at 50% opacity. The buildings
  should line up.
- None of Higgsfield's image models expose explicit depth or edge control (*medium
  confidence*). They follow the image and the instructions.
- In the video prompt, map keyframes to time ranges: "Use Video 1 only for camera, timing
  and framing. Image 2 defines the gate's design (0–5 s); Image 3 the mirror terrace (6–9 s)…"

## Restyling the whole blocking clip

- **Seedance 2.5 reference video:** keeps the camera path even when the text disagrees, but
  shapes morph. Prompt "Fully re-render Video 1 preserving camera, timing, framing."
- **Genjutsu Restyle** (Higgsfield): keeps motion and composition, 4–30 s, preset styles.
  Whether it can produce a photoreal look is *unverified*.
- Kling 3.0 Omni Edit and FLUX 3 Video Edit are also on Higgsfield's video-to-video page.

## Recommended pipeline for this project

1. **Blocking clips (free).** Re-cut the final chase render into 4 longer clips instead of
   8, which means fewer seams:
   - gate + mirror + forge, about 20 s
   - arena + mission + library, about 19 s
   - steles + scroll + formation, about 17 s
   - abode + summit, about 16 s

   That's 1280×720 at 24 fps, with the first frame of each clip showing its key elements.
2. **Flyer (about 30–45 credits).** Soul ID if it's you, then a character sheet with back
   views first, then save it as Element "flyer".
3. **Area keyframes (about 150–200 credits).** 4–8 edits per area, pick one each, save them
   as Elements ("gate", "forge"…), with one fixed style paragraph.
4. **Generate each clip in reference mode:**
   - @Video 1 = the blocking clip (camera only)
   - @flyer
   - the area keyframes mapped to time ranges
   - the previous clip's approved last frame (pulled with ffmpeg, unedited) as the opening state

   Don't describe camera moves in the text, because the reference video carries them.
5. **Drafts at 480p** (about 3 credits/s), finals at 720p (about 7 credits/s). Fix drift with
   Edit instead of re-rolling.
6. **Website:** overlap clips by about 0.5 s and cross-fade on scroll. Add all readable text
   as HTML.

**Rough credits for the 72 s:**
- 480p pass: about 216
- 720p pass: about 490
- 1080p pass: about 860

The total with two draft passes, 720p finals, about 30% re-rolls, keyframes and Soul ID is
**about 1,300 credits**, roughly 1.3 months of the $49 Plus plan (1,000 credits/month). With
1080p finals it's about 1,750.

**Unverified:**
- Whether a reference video raises the web price (the API also bills the input video's seconds).
- How the web app combines start/end frames with Elements.
- Whether the unlimited window covers the Blender plugin. Generations through MCP and the
  CLI always cost credits.

## Impact on the interactive plan

Seedance follows the blocking camera closely but morphs geometry. So the plan's alignment
steps are needed:
- the calibration page, where you drag hotspots onto the real objects at each hero moment
- the point-tracking pass
- the explore-only fallback

See `client/docs/interactive-flight-plan.md`, section 7.
