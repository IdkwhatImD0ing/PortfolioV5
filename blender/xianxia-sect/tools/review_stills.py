"""Round 60's blind review kit for rock stills (docs/scene/rock-r60.md, its decision rule). PC only, with PIL and
numpy; no Blender. It turns the stills preview_r59.py brings back (<renders>/r59_<tag>_<shot>.png) into folders of
unlabelled pictures for review agents, and scores the agents' JSON answers against the rule.

The lead's steps, from blender/xianxia-sect:

1. Prepare, once the stills (7 tags x 18 shots) and the box logs (the '| tee' files) are on the PC:

       python -P tools/review_stills.py prepare out/tmp/r60/renders --out <kit> --before before \
           --tags mtn8,mtn8hc,mtn12,big3,big3soft --placebo p830 --seed <n> --logs out/tmp/r60/logs

   It prints the counted set, the brightness table and the time table, and writes:
       <kit>/lead/KEY_do_not_show.json      which crop and side is which tag, the tables, the windows
       <kit>/lead/summary.txt               what it printed
       <kit>/lead/crops/<shot>__<tag>.png   the labelled 1:1 crops, for the lead's own look
       <kit>/lead/windows/<shot>.jpg        before at half size: changed pixels tinted red, the crop window in yellow
       <kit>/stage1/r1/, <kit>/stage1/r2/   one folder per stage 1 reviewer
   Nothing in a reviewer folder names a tag: crops are a.png, b.png ... in folders s01, s02 ... in a shuffled order
   per reviewer, and every picture is written fresh, without Blender's PNG text (its 'File' entry names the .blend).
   Reviewer folders hold plain copies of the files under lead/, written in letter (or A, B) order, so their dates
   follow the random letters and sides. Hard links would save disk, but their link count marks before (place()).

2. Start two fresh reviewers, one per stage 1 folder. Give each only its folder's path and this brief: follow
   README.txt in the folder, and do not open anything outside it. Each one saves answers.json in its folder (or
   returns the JSON; save that as answers.json in its folder).

3. Score stage 1:

       python -P tools/review_stills.py score <kit> <kit>/stage1/r1 <kit>/stage1/r2

   It prints each tag's mean rank, today's score, the noise, the bar, who advances and the stage 2 queue.

4. Build stage 2 for the first candidate of the queue:

       python -P tools/review_stills.py pairs <kit> --candidate <tag>

   It prints the candidate's neutral id cN and writes <kit>/stage2/cN/r1, r2 and r3 (r3 is only for a third
   reviewer), the stills without PNG text under <kit>/lead/full/cN/ and the key <kit>/lead/KEY_stage2_cN.json.
   Every counted shot is one pair, plus 4 hidden placebo pairs.

5. Start two different fresh reviewers on stage2/cN/r1 and stage2/cN/r2, as in step 2. Then:

       python -P tools/review_stills.py score <kit> <kit>/stage2/cN/r1 <kit>/stage2/cN/r2

   It prints items (a) to (g) of the rule, and (h) for big3 and big3soft (the lead's rule 5: those ship only if they
   win both the close and the far set), each PASS or FAIL, and one VERDICT line:
   - PASS or FAIL.
   - REPLACE: a reviewer picked a side on 3 or 4 of the 4 placebo pairs. Move that answers.json out of the folder
     (to <kit>/lead/answers/, say), start a fresh reviewer on the same folder and score again, giving the moved file
     first and then the folder: score <kit> <moved file> <kit>/stage2/cN/r1 <kit>/stage2/cN/r2.
   - INCONCLUSIVE: the replacement picked sides too. Nothing is baked.
   - NEED THIRD: the two split on (a). Start a fresh reviewer on stage2/cN/r3 and score again with all three.
   If it fails and the queue has a second candidate, go back to step 4 with that one.

The score command takes answers files, or reviewer folders (it reads answers.json there). Each answers file names
its folder in "kit" (the template fills it in). It writes its result to <kit>/lead/score_stage1.json or
score_stage2_cN.json as well. Exit code 2 means bad input: the message lists every problem, so a reviewer can be
asked to fix its file.

Answer formats (README.txt in each folder says the same to the reviewer):
    stage 1: {"kit": "stage1/r1", "shots": {"s01": {"rank": ["c", "a", ...], "tells": {"a": ["crack_web"], ...}}}}
             rank: every letter of the folder once, best first (reads most like real cliff rock at this size).
    stage 2: {"kit": "stage2/c1/r1", "pairs": {"p01": {"pick": "A", "tells_A": [], "tells_B": ["repeat"]}}}
             pick: "A", "B" or "same".
    Tell ids: crack_web, repeat, plaster, ink_lines, wrong_light, masonry, tilted_grain, green_stripes.

The rule as scored here (every number is a constant below, fixed before any still is seen):
- A pixel changed when any channel moves more than 8 of 255 against before. The real variants' masks are unioned
  (the placebo's is not), and one 800 x 450 window per shot goes where the union is densest (the one nearest the
  frame's centre when several tie). A shot counts when 10 % or more of that window changed. Close and far sets are
  CLOSE_SET and FAR_SET.
- Stage 1: ranks are averaged over every reviewer and counted shot. Today = the mean of before's and the placebo's
  mean ranks; noise = the gap between them. A real variant advances when today minus its mean rank is at least
  max(0.75, 2 x noise). The queue is the best, then the second only if it is within 0.5 of the best. Equal means
  are ordered by fewer crack_web ticks, then fewer other ticks, then TIE_ORDER.
- Stage 2, N counted pairs: (a) each reviewer gives the candidate at least ceil(0.6 N) wins and at least 2.5 times
  as many wins as losses ('same' is neither). (b) None of KEY_CLOSE is lost with both reviewers. (c) On the far set
  each reviewer gives at least as many wins as losses, and 'repeat' is ticked on the candidate by both reviewers in
  at most 1 far shot where no reviewer ticked it on before. (d) crack_web ticks on the candidate, summed over the
  reviewers, are at most half of before's. (e) No other tell is ticked on the candidate by both reviewers in 3 or
  more shots where no reviewer ticked it on before. (f) On every counted close shot, the candidate's mean linear
  luminance over the shot's changed pixels (the union mask above, so every still of a shot is measured on the same
  pixels) is within max(5 %, |the placebo's deviation over those pixels| + 2 %) of before's. (g) Render seconds on
  KEY_CLOSE add up to at most 1.3 times before's, from the logs' 'PREVIEW wrote ... N s' lines (or from the PNGs'
  RenderTime when the logs lack one of the six numbers; one source per gate). (h) big3 and big3soft only: each
  reviewer gives more wins than losses on the close set and on the far set.
  With a third reviewer (only when the two split on (a)), (a) to (c) and (h) need two of the three reviewers, and
  'both' in (c) to (e) means two of three.
  A reviewer who picks a side on 3 or more of 4 placebo pairs is replaced once (with fewer placebo pairs present:
  on at least three quarters of them, rounded up).

Test: python -P tools/test_review_stills.py (synthetic stills, a few seconds).
"""
import argparse
import glob
import json
import math
import os
import random
import re
import shutil
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

PREFIX = "r59"                 # preview_r59.py writes <out>/r59_<tag>_<shot>.png
SHOTS = ("abode_1380", "abode_1380_close", "library_772", "library_772_close", "steles_974", "steles_974_close",
         "mirror_217", "mirror_217_close", "forge_352", "forge_352_close", "arena_516", "arena_516_close",
         "mission_619", "mission_619_close", "gate_93", "scroll_1103", "formation_1208", "summit_1647")
CLOSE_SET = ("abode_1380", "abode_1380_close", "steles_974_close", "mirror_217", "mirror_217_close",
             "library_772_close", "forge_352_close", "mission_619_close", "arena_516_close")
FAR_SET = ("forge_352", "library_772", "steles_974", "gate_93", "mission_619", "arena_516", "scroll_1103",
           "formation_1208", "summit_1647")
KEY_CLOSE = ("abode_1380_close", "steles_974_close", "mirror_217_close")     # items (b) and (g)
PLACEBO_PAIR_SHOTS = ("abode_1380_close", "steles_974_close", "mirror_217_close", "library_772_close")
WINDOW = (800, 450)            # the crop, 1:1
DIFF = 8                       # a pixel changed when any channel moves more than this (of 255)
COUNT_SHARE = 0.10             # a shot counts when this share of its window changed
ADVANCE_MIN = 0.75             # stage 1: beat today's mean rank by max(ADVANCE_MIN, ADVANCE_NOISE x noise)
ADVANCE_NOISE = 2.0
SECOND_WITHIN = 0.5            # the second candidate goes to stage 2 only within this of the best mean rank
WIN_SHARE = 0.6                # (a)
WIN_LOSS = 2.5                 # (a)
REPEAT_FAR_MAX = 1             # (c)
CRACK_SHARE = 0.5              # (d)
OTHER_TELL_MAX = 2             # (e): fails at 3 shots
BRIGHT_MIN = 0.05              # (f)
BRIGHT_PAD = 0.02              # (f)
TIME_MAX = 1.3                 # (g)
PLACEBO_PICK_SHARE = 0.75      # a reviewer who picks a side on this share of the placebo pairs (3 of 4) is replaced
BOTH_SETS_TAGS = ("big3", "big3soft")    # (h), the lead's rule 5
TIE_ORDER = ("big3soft", "big3", "mtn8", "mtn12", "mtn8hc")
STAGE1_REVIEWERS = 2
STAGE2_REVIEWERS = ("r1", "r2", "r3")    # r2 sees r1's sides flipped; r3 is only for a third reviewer
TELLS = (
    ("crack_web", "crack web of any cell size (dried mud, crazy paving, flagstones, crackle, polygon net, the same "
                  "small pattern printed all over)"),
    ("repeat", "repeat, grid or wallpaper"),
    ("plaster", "plaster, smear or blur"),
    ("ink_lines", "drawn ink lines"),
    ("wrong_light", "light from the wrong side, or painted shading"),
    ("masonry", "masonry"),
    ("tilted_grain", "tilted grain"),
    ("green_stripes", "green stripes"),
)
TELL_IDS = tuple(t for t, _d in TELLS)
KEY_FILE = "KEY_do_not_show.json"
EPS = 1e-9

_LIN = np.array([c / 255.0 / 12.92 if c / 255.0 <= 0.04045 else ((c / 255.0 + 0.055) / 1.055) ** 2.4
                 for c in range(256)], np.float32)
_W709 = np.array([0.2126, 0.7152, 0.0722], np.float32)


class KitError(Exception):
    """Bad input: the message and every problem found."""

    def __init__(self, msg, problems=()):
        super().__init__(msg)
        self.problems = list(problems)


class Out:
    """Prints a line (unless quiet) and keeps it for the summary file."""

    def __init__(self, quiet):
        self.quiet, self.lines = quiet, []

    def __call__(self, s=""):
        self.lines.append(s)
        if not self.quiet:
            print(s, flush=True)


# ---------------------------------------------------------------------------------------------------- pictures

def still_path(renders, prefix, tag, shot):
    return os.path.join(renders, "%s_%s_%s.png" % (prefix, tag, shot))


def load_still(path):
    """(RGB uint8 array, the PNG's text and other info)."""
    with Image.open(path) as im:
        im.load()
        info = dict(im.info)
        arr = np.array(im.convert("RGB"), dtype=np.uint8)
    return arr, info


def save_png(arr, path):
    """A fresh PNG from pixels only: no text, no EXIF, nothing the source carried."""
    Image.fromarray(np.ascontiguousarray(arr)).save(path, format="PNG", compress_level=3)


def place(src, dst):
    """A reviewer's copy of a picture under lead/: a plain copy, written when the folder is built (a, b, c ... or A
    then B), so its date follows the random letters and sides. Not a hard link: a link shares the file's link count,
    and before's crop is linked into more folders than any other tag's (every pair, and twice on the placebo shots),
    so 'ls -l' would point at it."""
    shutil.copyfile(src, dst)


def lin_lum(rgb):
    """Linear luminance (Rec. 709) of an sRGB uint8 picture."""
    return _LIN[rgb] @ _W709


def change_mask(a, b, diff=DIFF):
    """True where any channel of a moves more than diff against b."""
    return (np.abs(a.astype(np.int16) - b.astype(np.int16)) > diff).any(axis=-1)


def densest_window(mask, w, h):
    """(x0, y0, x1, y1, changed pixels) of the w x h window holding the most of mask; among equal ones the nearest
    the frame's centre. The window shrinks to the frame if the frame is smaller."""
    H, W = mask.shape
    w, h = min(w, W), min(h, H)
    s = np.zeros((H + 1, W + 1), np.int64)
    s[1:, 1:] = mask.astype(np.int64).cumsum(0).cumsum(1)
    sums = s[h:, w:] - s[:-h, w:] - s[h:, :-w] + s[:-h, :-w]
    best = int(sums.max())
    ys, xs = np.nonzero(sums == best)
    i = int(np.argmin((ys - (H - h) / 2.0) ** 2 + (xs - (W - w) / 2.0) ** 2))
    x0, y0 = int(xs[i]), int(ys[i])
    return x0, y0, x0 + w, y0 + h, best


def brightness(lum_tag, lum_before, mask):
    """(mean linear luminance of the tag's still over mask, before's over mask, the tag's deviation); (None, None,
    0.0) for an empty mask."""
    if not mask.any():
        return None, None, 0.0
    lt, lb = float(lum_tag[mask].mean()), float(lum_before[mask].mean())
    return lt, lb, (lt / lb - 1.0) if lb > 0 else 0.0


def window_preview(before, union, box, path):
    v = before.astype(np.float32)
    v[union] = v[union] * 0.45 + np.array([255.0, 40.0, 40.0], np.float32) * 0.55
    im = Image.fromarray(np.clip(v, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = box
    for k in range(3):
        d.rectangle([x0 - k, y0 - k, x1 - 1 + k, y1 - 1 + k], outline=(255, 230, 0))
    im = im.resize((max(1, im.width // 2), max(1, im.height // 2)), Image.Resampling.BILINEAR)
    im.save(path, quality=85)


# ---------------------------------------------------------------------------------------------------- render times

WROTE_RE = re.compile(r"PREVIEW wrote (\S+\.png)")
SECS_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?) s\s*$")
RUN_RE = re.compile(r"PREVIEW cycles device")


def split_name(base, prefix, shots):
    """(tag, shot) of '<prefix>_<tag>_<shot>.png', or None."""
    if not (base.startswith(prefix + "_") and base.endswith(".png")):
        return None
    stem = base[len(prefix) + 1:-4]
    for s in sorted(shots, key=len, reverse=True):
        if stem.endswith("_" + s) and len(stem) > len(s) + 1:
            return stem[:-(len(s) + 1)], s
    return None


def log_files(spec):
    """The log files a --logs value names (folders: their *.log and *.txt), oldest first."""
    files = []
    for part in [p for p in (spec or "").split(",") if p.strip()]:
        part = part.strip()
        if os.path.isdir(part):
            files += glob.glob(os.path.join(part, "*.log")) + glob.glob(os.path.join(part, "*.txt"))
        elif os.path.isfile(part):
            files.append(part)
        else:
            raise KitError("--logs: no such file or folder: %s" % part)
    return sorted(set(files), key=lambda p: (os.path.getmtime(p), p))


def parse_logs(paths, prefix, shots):
    """{(tag, shot): {sec, file, first}} from 'PREVIEW wrote <path> ... <N> s' lines; a later line for the same still
    wins (a retried run). 'first' marks a run's first still, which carries the GPU's warm-up."""
    got, dups = {}, []
    for p in paths:
        first = True
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\r\n")
                if RUN_RE.search(line):
                    first = True
                    continue
                m = WROTE_RE.search(line)
                if not m:
                    continue
                was_first, first = first, False
                sec = SECS_RE.search(line)
                name = split_name(re.split(r"[\\/]", m.group(1))[-1], prefix, shots)
                if name is None or sec is None:
                    continue
                if name in got:
                    dups.append("%s_%s" % name)
                got[name] = dict(sec=float(sec.group(1)), file=os.path.basename(p), first=was_first)
    return got, dups


def hms_seconds(s):
    """Blender's 'MM:SS.cc' or 'HH:MM:SS.cc' as seconds (None if not that)."""
    try:
        vals = [float(p) for p in str(s).strip().split(":")]
    except ValueError:
        return None
    sec = 0.0
    for v in vals:
        sec = sec * 60.0 + v
    return sec


# ---------------------------------------------------------------------------------------------------- prepare

STAGE1_README = """Rock review: ranking ({kit})

You are reviewing renders of a 3D scene, blind: you do not know how any picture was made. Only this folder is part
of the review. Do not open, list or search anything outside it.

Each folder s01 to s{last:02d} holds {n} crops of one view: {letters}. They are the same view rendered with different
rock materials. Each crop is {w} x {h} pixels, cut 1:1 from a 1600 x 900 still (one image pixel per screen pixel,
the size the page shows). The letters are in a random order, different in every folder.

For each folder:
1. Look at every crop at full size. Judge only the rock.
2. Rank all {n} crops by which reads more like real cliff rock at this size, best first. No ties: when two look the
   same to you, still give them an order.
3. For each crop, list every tell below that you see on it. An empty list means you see none.

Tells (write the id):
{tells}

Answer: answers_template.json has every folder and letter. Fill it in and save it as answers.json in this folder.
If you cannot write files, return the filled JSON as your final answer. "rank" lists every letter of the folder
once, best first. "tells" maps each letter to a list of tell ids. For example:
  "s01": {{"rank": [{example}], "tells": {{"a": ["crack_web"], "b": [], ...}}}}
Keep "kit": "{kit}" as it is.
"""

STAGE2_README = """Rock review: pairs ({kit})

You are reviewing renders of a 3D scene, blind: you do not know how either side was made. Only this folder is part
of the review. Do not open, list or search anything outside it.

Each folder p01 to p{last:02d} holds one view rendered two ways, A and B:
  A_full.png, B_full.png   the whole still, {fw} x {fh} pixels
  A_crop.png, B_crop.png   a {w} x {h} crop of the same part of each still, 1:1 (one image pixel per screen pixel,
                           the size the page shows); answers_template.json gives the crop's box in the still
Which side is A is random in every folder.

For each folder:
1. Look at both full stills and both crops at full size. Judge only the rock.
2. Answer which reads more like real cliff rock at the page's size: "A", "B" or "same". Say "same" when you see no
   difference that matters, or have no preference.
3. List every tell below that you see on A and on B. An empty list means you see none.

Tells (write the id):
{tells}

Answer: answers_template.json has every folder. Fill it in and save it as answers.json in this folder. If you cannot
write files, return the filled JSON as your final answer. For example:
  "p01": {{"pick": "B", "tells_A": ["crack_web", "repeat"], "tells_B": []}}
Keep "kit": "{kit}" as it is.
"""


def tells_text():
    return "\n".join("  %-14s %s" % (t, d) for t, d in TELLS)


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=1)
        fh.write("\n")


def parse_window(s):
    m = re.fullmatch(r"\s*(\d+)\s*[xX]\s*(\d+)\s*", s or "")
    if not m or int(m.group(1)) < 1 or int(m.group(2)) < 1:
        raise KitError("--window must be WxH, e.g. 800x450")
    return int(m.group(1)), int(m.group(2))


def shot_set(shot):
    return "close" if shot in CLOSE_SET else ("far" if shot in FAR_SET else "other")


def fmt_pct(x):
    return "%+.1f %%" % (100.0 * x)


def time_gate(times, tag, before, shots=KEY_CLOSE):
    """(source, tag's seconds, before's seconds, ratio) over shots, one source for all six numbers; source None when
    neither source has them all."""
    for src in ("log", "png"):
        vals = [(times.get(t, {}).get(s) or {}).get(src) for t in (tag, before) for s in shots]
        if all(v is not None for v in vals):
            a, b = sum(vals[:len(shots)]), sum(vals[len(shots):])
            return src, a, b, (a / b if b > 0 else float("inf"))
    return None, None, None, None


def cmd_prepare(a, say):
    renders, out = os.path.abspath(a.renders), os.path.abspath(a.out)
    real = [t.strip() for t in a.tags.split(",") if t.strip()]
    before, placebo = a.before.strip(), (a.placebo or "").strip() or None
    tags = [before] + ([placebo] if placebo else []) + real
    if not real:
        raise KitError("--tags names no real variant")
    if len(set(tags)) != len(tags):
        raise KitError("a tag is named twice: %s" % tags)
    if len(tags) > 26:
        raise KitError("more than 26 tags")
    shots_req = [s.strip() for s in a.shots.split(",") if s.strip()] if a.shots else list(SHOTS)
    ww, wh = parse_window(a.window)
    if not os.path.isdir(renders):
        raise KitError("no renders folder %s" % renders)
    lead = os.path.join(out, "lead")
    if os.path.exists(os.path.join(lead, KEY_FILE)):
        if not a.force:
            raise KitError("%s already holds a kit (use --force to build it again)" % out)
        for sub in ("lead", "stage1", "stage2"):
            if os.path.isdir(os.path.join(out, sub)):
                shutil.rmtree(os.path.join(out, sub))
    for sub in ("crops", "windows"):
        os.makedirs(os.path.join(lead, sub), exist_ok=True)

    present, missing = [], {}
    for s in shots_req:
        miss = [t for t in tags if not os.path.isfile(still_path(renders, a.prefix, t, s))]
        if miss:
            missing[s] = miss
        else:
            present.append(s)
    if not present:
        raise KitError("no shot has a still for every tag in %s" % renders, ["%s: missing %s" % (s, m)
                                                                             for s, m in missing.items()])
    say("review_stills prepare: %d shots with every tag, tags %s (before %s, placebo %s), seed %d" % (
        len(present), real, before, placebo, a.seed))
    for s, m in missing.items():
        say("WARN %s left out: no still for %s" % (s, m))

    shots, bright, times = {}, {t: {} for t in tags if t != before}, {t: {} for t in tags}
    for i, s in enumerate(present, 1):
        imgs, infos = {}, {}
        for t in tags:
            imgs[t], infos[t] = load_still(still_path(renders, a.prefix, t, s))
            times[t][s] = dict(log=None, log_first=None, png=hms_seconds(infos[t].get("RenderTime"))
                               if infos[t].get("RenderTime") is not None else None)
        size = imgs[before].shape
        bad = [t for t in tags if imgs[t].shape != size]
        if bad:
            raise KitError("%s: %s differ in size from before %s" % (s, bad, size[1::-1]))
        lb = lin_lum(imgs[before])
        masks = {t: change_mask(imgs[t], imgs[before]) for t in tags if t != before}
        union = np.zeros(size[:2], bool)
        for t in real:
            union |= masks[t]
        x0, y0, x1, y1, n = densest_window(union, ww, wh)
        share = n / float((x1 - x0) * (y1 - y0))
        counted = share >= COUNT_SHARE - EPS
        shots[s] = dict(window=[x0, y0, x1, y1], window_share=share, union_share=float(union.mean()),
                        counted=bool(counted), set=shot_set(s), size=[size[1], size[0]])
        # written in a shuffled order (the lead's files; reviewers get copies, dated when their folder is built)
        for t in random.Random("%d|save|%s" % (a.seed, s)).sample(tags, len(tags)):
            save_png(imgs[t][y0:y1, x0:x1], os.path.join(lead, "crops", "%s__%s.png" % (s, t)))
        for t in tags:
            if t != before:
                lt = lin_lum(imgs[t])
                lum, lum_b, dev = brightness(lt, lb, union)
                _l, _b, dev_own = brightness(lt, lb, masks[t])
                bright[t][s] = dict(dev=dev, lum=lum, lum_before=lum_b, region=float(union.mean()),
                                    changed=float(masks[t].mean()), dev_own=dev_own)
        window_preview(imgs[before], union, (x0, y0, x1, y1), os.path.join(lead, "windows", "%s.jpg" % s))
        say("  [%2d/%d] %-18s %-5s window %4d,%-4d changed %5.1f %% of it -> %s" % (
            i, len(present), s, shots[s]["set"], x0, y0, 100.0 * share, "counted" if counted else "not counted"))

    logs = log_files(a.logs)
    got, dups = parse_logs(logs, a.prefix, shots_req)
    for (t, s), v in got.items():
        if t in times and s in times[t]:
            times[t][s]["log"], times[t][s]["log_first"] = v["sec"], v["first"]

    counted = [s for s in present if shots[s]["counted"]]
    stage1 = {}
    for r in range(1, a.reviewers + 1):
        rid = "r%d" % r
        rng = random.Random("%d|stage1|%s" % (a.seed, rid))
        order = counted[:]
        rng.shuffle(order)
        d = os.path.join(out, "stage1", rid)
        os.makedirs(d, exist_ok=True)
        folders = {}
        for j, s in enumerate(order, 1):
            fid = "s%02d" % j
            mix = tags[:]
            rng.shuffle(mix)
            letters = {chr(97 + k): t for k, t in enumerate(mix)}
            os.makedirs(os.path.join(d, fid), exist_ok=True)
            for letter in sorted(letters):
                place(os.path.join(lead, "crops", "%s__%s.png" % (s, letters[letter])),
                      os.path.join(d, fid, letter + ".png"))
            folders[fid] = dict(shot=s, letters=letters)
        stage1[rid] = folders
        kit = "stage1/%s" % rid
        lets = [chr(97 + k) for k in range(len(tags))]
        write_text(os.path.join(d, "README.txt"), STAGE1_README.format(
            kit=kit, last=len(order), n=len(tags), letters=", ".join(x + ".png" for x in lets), w=ww, h=wh,
            tells=tells_text(), example=", ".join('"%s"' % x for x in lets[2:] + lets[:2])))
        write_json(os.path.join(d, "answers_template.json"), dict(
            kit=kit, tell_ids=list(TELL_IDS),
            shots={fid: dict(rank=[], tells={x: [] for x in lets}) for fid in sorted(folders)}))

    key = dict(version=1, made=time.strftime("%Y-%m-%d %H:%M:%S"), renders=renders, prefix=a.prefix, before=before,
               placebo=placebo, real=real, tags=tags, seed=a.seed, window=[ww, wh], shots=shots, missing=missing,
               bright=bright, times=times, logs=[os.path.abspath(p) for p in logs], log_duplicates=dups,
               stage1=stage1, rule=rule_constants())
    write_json(os.path.join(lead, KEY_FILE), key)

    say("")
    report_sets(key, say)
    report_bright(key, say)
    report_times(key, say)
    say("")
    if not counted:
        say("No counted shot: stage 1 has nothing to judge. By the rule: no bake.")
    else:
        say("Stage 1 folders (one per reviewer): %s" % ", ".join(
            os.path.join(out, "stage1", rid) for rid in sorted(stage1)))
        say("Next: start one fresh reviewer per folder, then: python -P tools/review_stills.py score %s %s" % (
            out, " ".join(os.path.join(out, "stage1", rid) for rid in sorted(stage1))))
    write_text(os.path.join(lead, "summary.txt"), "\n".join(say.lines) + "\n")
    return key


def rule_constants():
    return dict(diff=DIFF, count_share=COUNT_SHARE, advance_min=ADVANCE_MIN, advance_noise=ADVANCE_NOISE,
                second_within=SECOND_WITHIN, win_share=WIN_SHARE, win_loss=WIN_LOSS, repeat_far_max=REPEAT_FAR_MAX,
                crack_share=CRACK_SHARE, other_tell_max=OTHER_TELL_MAX, bright_min=BRIGHT_MIN, bright_pad=BRIGHT_PAD,
                time_max=TIME_MAX, placebo_pick_share=PLACEBO_PICK_SHARE, both_sets_tags=list(BOTH_SETS_TAGS),
                key_close=list(KEY_CLOSE), placebo_pair_shots=list(PLACEBO_PAIR_SHOTS), close_set=list(CLOSE_SET),
                far_set=list(FAR_SET), tells=list(TELL_IDS))


def report_sets(key, say):
    shots = key["shots"]
    close = [s for s in shots if shots[s]["counted"] and shots[s]["set"] == "close"]
    far = [s for s in shots if shots[s]["counted"] and shots[s]["set"] == "far"]
    other = [s for s in shots if shots[s]["counted"] and shots[s]["set"] == "other"]
    say("Counted set: %d of %d shots (10 %% or more of the window changed)." % (
        len(close) + len(far) + len(other), len(shots)))
    say("  close (%d): %s" % (len(close), ", ".join(close) or "none"))
    say("  far   (%d): %s" % (len(far), ", ".join(far) or "none"))
    if other:
        say("  other (%d): %s" % (len(other), ", ".join(other)))
    left = [s for s in shots if not shots[s]["counted"]]
    say("  not counted: %s" % (", ".join("%s (%.1f %%)" % (s, 100.0 * shots[s]["window_share"]) for s in left)
                               or "none"))


def bright_tol(key, shot):
    p = key["placebo"]
    dev_p = key["bright"][p][shot]["dev"] if p else 0.0
    return max(BRIGHT_MIN, abs(dev_p) + BRIGHT_PAD), dev_p


def report_bright(key, say):
    shots = key["shots"]
    close = [s for s in shots if shots[s]["counted"] and shots[s]["set"] == "close"]
    say("")
    say("Brightness, gate (f): each still's mean linear luminance over the shot's changed pixels (the union of the "
        "real variants' masks) against before's over the same pixels; the bar is max(5 %, |placebo| + 2 %). "
        "Counted close shots:")
    if not close:
        say("  none")
        return
    cols = [t for t in key["tags"] if t != key["before"]]
    say("  %-18s %8s " % ("shot", "bar") + " ".join("%10s" % t[:10] for t in cols))
    for s in close:
        tol, _dev_p = bright_tol(key, s)
        cells = []
        for t in cols:
            b = key["bright"][t][s]
            mark = "" if t == key["placebo"] or abs(b["dev"]) <= tol + EPS else "!"
            cells.append("%10s" % (fmt_pct(b["dev"]) + mark))
        say("  %-18s %8s " % (s, "%.1f %%" % (100 * tol)) + " ".join(cells))
    say("  ('!' = over the bar. The key also holds each still's deviation over its own changed pixels, dev_own.)")


def report_times(key, say):
    say("")
    say("Render seconds, gate (g): %s added up, against before's (at most %.1f times):" % (
        " + ".join(KEY_CLOSE), TIME_MAX))
    for t in key["real"] + ([key["placebo"]] if key["placebo"] else []):
        src, a, b, r = time_gate(key["times"], t, key["before"])
        if src is None:
            say("  %-10s no complete data (the logs and the PNGs lack one of the six numbers)" % t)
        else:
            say("  %-10s %6.1f s against %6.1f s: %.2f times (%s)%s" % (
                t, a, b, r, "logs" if src == "log" else "PNG RenderTime", "  OVER" if r > TIME_MAX + EPS else ""))
    firsts = sorted({"%s_%s" % (t, s) for t, v in key["times"].items() for s, x in v.items()
                     if s in KEY_CLOSE and x.get("log_first")})
    if firsts:
        say("  WARN a run's first still (GPU warm-up) is in the gate: %s" % ", ".join(firsts))
    if key.get("log_duplicates"):
        say("  logs rendered these again (the last line counts): %s" % ", ".join(sorted(set(key["log_duplicates"]))))
    if not key.get("logs"):
        say("  (no logs given: seconds from the PNGs' RenderTime)")


# ---------------------------------------------------------------------------------------------------- pairs

def load_key(kit):
    path = os.path.join(kit, "lead", KEY_FILE)
    if not os.path.isfile(path):
        raise KitError("no kit at %s (run prepare first)" % kit)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def stage2_keys(kit):
    out = {}
    for p in sorted(glob.glob(os.path.join(kit, "lead", "KEY_stage2_*.json"))):
        with open(p, encoding="utf-8") as fh:
            k = json.load(fh)
        out[k["cid"]] = k
    return out


def full_still(kit, key, cid, shot, tag):
    """The still without its PNG text, made once per stage 2 candidate under lead/full/<cid>/ (per candidate, so
    before's files are not older than the candidate's in a later candidate's folders)."""
    d = os.path.join(kit, "lead", "full", cid)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "%s__%s.png" % (shot, tag))
    if not os.path.isfile(p):
        arr, _info = load_still(still_path(key["renders"], key["prefix"], tag, shot))
        save_png(arr, p)
    return p


def cmd_pairs(a, say):
    kit = os.path.abspath(a.kit)
    key = load_key(kit)
    cand, before, placebo = a.candidate.strip(), key["before"], key["placebo"]
    if cand not in key["real"]:
        raise KitError("%s is not a real variant of this kit (%s)" % (cand, key["real"]))
    have = stage2_keys(kit)
    old = [cid for cid, k in have.items() if k["candidate"] == cand]
    if old and not a.force:
        raise KitError("%s already has stage 2 folders as %s (use --force to build them again)" % (cand, old[0]))
    cid = old[0] if old else "c%d" % (len(have) + 1)
    root = os.path.join(kit, "stage2", cid)
    for d in (root, os.path.join(kit, "lead", "full", cid)):
        if os.path.isdir(d):
            shutil.rmtree(d)
    counted = [s for s in key["shots"] if key["shots"][s]["counted"]]
    if not counted:
        raise KitError("no counted shot: nothing to pair")
    pairs = [("real", s, cand) for s in counted]
    if placebo:
        pairs += [("placebo", s, placebo) for s in PLACEBO_PAIR_SHOTS if s in key["shots"]]
    nplac = sum(1 for p in pairs if p[0] == "placebo")
    need = sorted({(s, t) for _k, s, other in pairs for t in (other, before)})
    for s, t in random.Random("%d|stage2|%s|save" % (key["seed"], cid)).sample(need, len(need)):
        full_still(kit, key, cid, s, t)     # made in a shuffled order (reviewers get copies)
    side_rng = random.Random("%d|stage2|%s|%s|sides" % (key["seed"], cid, cand))
    sides = [side_rng.random() < 0.5 for _p in pairs]        # True: the tested tag on A, for r1
    reviewers = {}
    for rid in STAGE2_REVIEWERS:
        rng = random.Random("%d|stage2|%s|%s|%s" % (key["seed"], cid, cand, rid))
        own = [rng.random() < 0.5 for _p in pairs]
        order = list(range(len(pairs)))
        rng.shuffle(order)
        d = os.path.join(root, rid)
        os.makedirs(d, exist_ok=True)
        folders = {}
        for j, pi in enumerate(order, 1):
            kind, s, other = pairs[pi]
            on_a = sides[pi] if rid == "r1" else (not sides[pi] if rid == "r2" else own[pi])
            ta, tb = (other, before) if on_a else (before, other)
            fid = "p%02d" % j
            fd = os.path.join(d, fid)
            os.makedirs(fd, exist_ok=True)
            for side, t in (("A", ta), ("B", tb)):
                place(full_still(kit, key, cid, s, t), os.path.join(fd, side + "_full.png"))
                place(os.path.join(kit, "lead", "crops", "%s__%s.png" % (s, t)), os.path.join(fd, side + "_crop.png"))
            folders[fid] = dict(shot=s, kind=kind, A=ta, B=tb)
        reviewers[rid] = folders
        kid = "stage2/%s/%s" % (cid, rid)
        ww, wh = key["window"]
        fw, fh = key["shots"][counted[0]]["size"]
        write_text(os.path.join(d, "README.txt"), STAGE2_README.format(
            kit=kid, last=len(pairs), fw=fw, fh=fh, w=ww, h=wh, tells=tells_text()))
        write_json(os.path.join(d, "answers_template.json"), dict(
            kit=kid, tell_ids=list(TELL_IDS),
            pairs={fid: dict(crop_box=key["shots"][f["shot"]]["window"], pick="", tells_A=[], tells_B=[])
                   for fid, f in sorted(folders.items())}))
    k2 = dict(version=1, made=time.strftime("%Y-%m-%d %H:%M:%S"), cid=cid, candidate=cand, counted=counted,
              placebo_pairs=nplac, reviewers=reviewers)
    write_json(os.path.join(kit, "lead", "KEY_stage2_%s.json" % cid), k2)
    say("review_stills pairs: %s is %s. %d counted pairs and %d hidden placebo pairs per reviewer." % (
        cand, cid, len(counted), nplac))
    if placebo and nplac < len(PLACEBO_PAIR_SHOTS):
        say("WARN only %d placebo pairs: some placebo shots have no stills" % nplac)
    for rid in STAGE2_REVIEWERS:
        say("  %s%s" % (os.path.join(root, rid), "   (only for a third reviewer)" if rid == "r3" else ""))
    say("Next: start fresh reviewers on r1 and r2, then: python -P tools/review_stills.py score %s %s %s" % (
        kit, os.path.join(root, "r1"), os.path.join(root, "r2")))
    return k2


# ---------------------------------------------------------------------------------------------------- answers

def norm_tell(x):
    return str(x).strip().lower().replace("-", "_").replace(" ", "_")


def read_answers(kit, spec):
    """(path, data, kit id) of an answers file or a reviewer folder's answers.json."""
    path = os.path.join(spec, "answers.json") if os.path.isdir(spec) else spec
    if not os.path.isfile(path):
        raise KitError("no answers file %s" % path)
    try:
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except ValueError as e:
        raise KitError("%s is not JSON: %s" % (path, e))
    if not isinstance(data, dict):
        raise KitError("%s: the answers must be a JSON object" % path)
    kid = data.get("kit")
    try:
        rel = os.path.relpath(os.path.dirname(os.path.abspath(path)), kit).replace("\\", "/")
    except ValueError:      # another drive
        rel = ""
    if not rel.startswith("stage"):
        rel = ""
    if not kid:
        kid = rel
    if not kid:
        raise KitError("%s: no \"kit\" entry, and it is not inside a reviewer folder" % path)
    kid = str(kid).strip("/")
    if rel and kid != rel:      # a reviewer copied another folder's id: its answers would score the wrong key
        raise KitError("%s sits in %s but its \"kit\" says %s" % (path, rel, kid))
    return path, data, kid


def check_tells(where, value, problems):
    if not isinstance(value, list):
        problems.append("%s: tells must be a list" % where)
        return []
    out = []
    for x in value:
        t = norm_tell(x)
        if t not in TELL_IDS:
            problems.append("%s: unknown tell %r (ids: %s)" % (where, x, ", ".join(TELL_IDS)))
        else:
            out.append(t)
    return sorted(set(out))


def check_stage1(path, data, folders):
    """{fid: (rank letters, {letter: tells})} and the problems."""
    problems, out = [], {}
    shots = data.get("shots")
    if not isinstance(shots, dict):
        return {}, ["%s: no \"shots\" object" % path]
    for fid in sorted(set(shots) - set(folders)):
        problems.append("%s: unknown folder %s" % (path, fid))
    for fid, f in sorted(folders.items()):
        ans = shots.get(fid)
        letters = sorted(f["letters"])
        if not isinstance(ans, dict):
            problems.append("%s %s: missing" % (path, fid))
            continue
        rank = [str(x).strip().lower() for x in ans.get("rank") or []]
        if sorted(rank) != letters:
            problems.append("%s %s: rank must list each of %s once, got %s" % (path, fid, letters, ans.get("rank")))
        tells_in = ans.get("tells") or {}
        if not isinstance(tells_in, dict):
            problems.append("%s %s: tells must map letters to lists" % (path, fid))
            tells_in = {}
        tells = {}
        for x, v in tells_in.items():
            x = str(x).strip().lower()
            if x not in letters:
                problems.append("%s %s: tells for unknown letter %r" % (path, fid, x))
                continue
            tells[x] = check_tells("%s %s %s" % (path, fid, x), v, problems)
        out[fid] = (rank, tells)
    return out, problems


def check_stage2(path, data, folders):
    """{fid: (pick 'A'|'B'|'same', tells A, tells B)} and the problems."""
    problems, out = [], {}
    pairs = data.get("pairs")
    if not isinstance(pairs, dict):
        return {}, ["%s: no \"pairs\" object" % path]
    for fid in sorted(set(pairs) - set(folders)):
        problems.append("%s: unknown folder %s" % (path, fid))
    for fid in sorted(folders):
        ans = pairs.get(fid)
        if not isinstance(ans, dict):
            problems.append("%s %s: missing" % (path, fid))
            continue
        pick = str(ans.get("pick", "")).strip()
        pick = {"a": "A", "b": "B", "same": "same"}.get(pick.lower())
        if pick is None:
            problems.append("%s %s: pick must be \"A\", \"B\" or \"same\", got %r" % (path, fid, ans.get("pick")))
        ta = check_tells("%s %s tells_A" % (path, fid), ans.get("tells_A") or [], problems)
        tb = check_tells("%s %s tells_B" % (path, fid), ans.get("tells_B") or [], problems)
        out[fid] = (pick, ta, tb)
    return out, problems


# ---------------------------------------------------------------------------------------------------- score

def cmd_score(a, say):
    kit = os.path.abspath(a.kit)
    key = load_key(kit)
    entries = [read_answers(kit, p) for p in a.answers]
    stages = sorted({kid.split("/")[0] for _p, _d, kid in entries})
    if stages == ["stage1"]:
        return score_stage1(kit, key, entries, say)
    if stages == ["stage2"]:
        cids = sorted({kid.split("/")[1] if kid.count("/") >= 2 else "" for _p, _d, kid in entries})
        if len(cids) != 1 or not cids[0]:
            raise KitError("score one stage 2 candidate at a time; got %s" % [k for _p, _d, k in entries])
        have = stage2_keys(kit)
        if cids[0] not in have:
            raise KitError("no stage 2 key for %s (run pairs first)" % cids[0])
        return score_stage2(kit, key, have[cids[0]], entries, say)
    raise KitError("answers must all be stage 1 or all one stage 2 candidate; got %s" % [k for _p, _d, k in entries])


def tie_rank(tag):
    return (TIE_ORDER.index(tag) if tag in TIE_ORDER else len(TIE_ORDER), tag)


def score_stage1(kit, key, entries, say):
    s1, problems, answers = key["stage1"], [], {}
    for path, data, kid in entries:
        parts = kid.split("/")
        rid = parts[1] if len(parts) == 2 else ""
        if rid not in s1:
            problems.append("%s: no stage 1 folder %s" % (path, kid))
            continue
        if rid in answers:
            problems.append("%s: a second answers file for %s" % (path, kid))
            continue
        got, probs = check_stage1(path, data, s1[rid])
        problems += probs
        answers[rid] = got
    for rid in sorted(set(s1) - set(answers)):
        problems.append("no answers for stage1/%s: the rule needs every stage 1 reviewer" % rid)
    if problems:
        raise KitError("stage 1 answers have problems", problems)
    tags, real, before, placebo = key["tags"], key["real"], key["before"], key["placebo"]
    ranks = {t: [] for t in tags}
    per = {rid: {t: [] for t in tags} for rid in answers}
    crack = {t: 0 for t in tags}
    other = {t: 0 for t in tags}
    for rid, got in sorted(answers.items()):
        for fid, (rank, tells) in got.items():
            letters = s1[rid][fid]["letters"]
            for pos, x in enumerate(rank, 1):
                ranks[letters[x]].append(pos)
                per[rid][letters[x]].append(pos)
            for x, ids in tells.items():
                for i in ids:
                    if i == "crack_web":
                        crack[letters[x]] += 1
                    else:
                        other[letters[x]] += 1
    mean = {t: float(np.mean(v)) if v else float("nan") for t, v in ranks.items()}
    today = (mean[before] + mean[placebo]) / 2.0 if placebo else mean[before]
    noise = abs(mean[before] - mean[placebo]) if placebo else 0.0
    bar = max(ADVANCE_MIN, ADVANCE_NOISE * noise)
    nshots = len(next(iter(s1.values()))) if s1 else 0
    say("STAGE 1: %d reviewers (%s), %d counted shots, %d versions per shot" % (
        len(answers), ", ".join(sorted(answers)), nshots, len(tags)))
    say("  %-10s %9s " % ("tag", "mean rank") + " ".join("%6s" % rid for rid in sorted(answers))
        + "  %11s %11s" % ("crack ticks", "other ticks"))
    for t in sorted(tags, key=lambda t: (mean[t], tie_rank(t))):
        role = " (before)" if t == before else (" (placebo)" if t == placebo else "")
        say("  %-10s %9.2f " % (t, mean[t]) + " ".join("%6.2f" % float(np.mean(per[rid][t])) for rid in sorted(per))
            + "  %11d %11d%s" % (crack[t], other[t], role))
    say("Today %.2f (%s); noise %.2f; bar max(%.2f, %.1f x noise) = %.2f" % (
        today, "mean of before %.2f and %s %.2f" % (mean[before], placebo, mean[placebo]) if placebo
        else "before alone: no placebo", noise, ADVANCE_MIN, ADVANCE_NOISE, bar))
    adv = [t for t in real if today - mean[t] >= bar - EPS]
    adv.sort(key=lambda t: (mean[t], crack[t], other[t], tie_rank(t)))
    for t in real:
        say("  %-10s beats today by %+.2f: %s" % (t, today - mean[t], "ADVANCES" if t in adv else "does not advance"))
    queue = adv[:1] + [t for t in adv[1:2] if mean[t] - mean[adv[0]] <= SECOND_WITHIN + EPS]
    if not adv:
        say("VERDICT stage 1: nothing advances. By the rule: stop, no bake.")
    else:
        rest = [t for t in adv if t not in queue]
        say("VERDICT stage 1: queue %s%s" % (
            queue[0], (", then %s only if %s fails stage 2" % (queue[1], queue[0])) if len(queue) > 1 else ""))
        if rest:
            say("  advanced but more than %.1f behind the best, so not sent: %s" % (SECOND_WITHIN, ", ".join(rest)))
        say("Next: python -P tools/review_stills.py pairs %s --candidate %s" % (kit, queue[0]))
    res = dict(stage=1, reviewers=sorted(answers), mean=mean, per_reviewer={r: {t: float(np.mean(v)) for t, v in
                                                                               p.items()} for r, p in per.items()},
               crack=crack, other=other, today=today, noise=noise, bar=bar, advanced=adv, queue=queue)
    write_json(os.path.join(kit, "lead", "score_stage1.json"), res)
    return res


def placebo_limit(k):
    return max(1, int(math.ceil(PLACEBO_PICK_SHARE * k - EPS))) if k else None


def reviewer_view(folders, got, cand):
    """Per counted shot: (outcome 'W'|'L'|'S', tells on the candidate, tells on before); and placebo picks."""
    shots, picks = {}, 0
    for fid, f in folders.items():
        pick, ta, tb = got[fid]
        if f["kind"] == "placebo":
            picks += pick in ("A", "B")
            continue
        c_side = "A" if f["A"] == cand else "B"
        outcome = "S" if pick == "same" else ("W" if pick == c_side else "L")
        shots[f["shot"]] = (outcome, set(ta if c_side == "A" else tb), set(tb if c_side == "A" else ta))
    return shots, picks


def wl(view, shots):
    w = sum(1 for s in shots if view[s][0] == "W")
    l_ = sum(1 for s in shots if view[s][0] == "L")
    return w, l_


def score_stage2(kit, key, k2, entries, say):
    cid, cand, before, placebo = k2["cid"], k2["candidate"], key["before"], key["placebo"]
    folders_all, problems, files = k2["reviewers"], [], {}
    for path, data, kid in entries:
        parts = kid.split("/")
        rid = parts[2] if len(parts) == 3 else ""
        if rid not in folders_all:
            problems.append("%s: no stage 2 folder %s" % (path, kid))
            continue
        got, probs = check_stage2(path, data, folders_all[rid])
        problems += probs
        files.setdefault(rid, []).append((path, got))
    for rid in ("r1", "r2"):
        if rid not in files:
            problems.append("no answers for stage2/%s/%s: the rule needs r1 and r2" % (cid, rid))
    if problems:
        raise KitError("stage 2 answers have problems", problems)

    nplac, counted = k2["placebo_pairs"], k2["counted"]
    limit = placebo_limit(nplac)
    say("STAGE 2: %s = %s against %s, %d counted pairs, %d hidden placebo pairs (%s)" % (
        cid, cand, before, len(counted), nplac, placebo))
    eff, status = {}, {}
    for rid, lst in sorted(files.items()):
        if len(lst) > 2:
            raise KitError("more than two answers files for stage2/%s/%s (the first and one replacement)" % (cid, rid))
        views = [reviewer_view(folders_all[rid], got, cand) for _p, got in lst]
        for (p, _g), (_v, picks) in zip(lst, views):
            say("  placebo: %s (%s) picked a side on %d of %d" % (rid, os.path.basename(p), picks, nplac))
        noisy = [limit is not None and picks >= limit for _v, picks in views]
        if not noisy[0]:
            if len(lst) > 1:
                raise KitError("stage2/%s/%s: a second answers file, but the first passed the placebo check" % (
                    cid, rid))
            eff[rid] = views[0][0]
        elif len(lst) == 1:
            status[rid] = "REPLACE"
        elif noisy[1]:
            status[rid] = "INCONCLUSIVE"
        else:
            eff[rid] = views[1][0]
            say("  %s: replaced once; the replacement passed the placebo check" % rid)
    res = dict(stage=2, cid=cid, candidate=cand, counted=counted, items={}, verdict=None)

    def done(verdict, why):
        res["verdict"], res["why"] = verdict, why
        say("VERDICT %s (%s): %s%s" % (cand, cid, verdict, (": " + why) if why else ""))
        write_json(os.path.join(kit, "lead", "score_stage2_%s.json" % cid), res)
        return res

    main_two = ("r1", "r2")
    if any(status.get(r) == "INCONCLUSIVE" for r in main_two):
        return done("INCONCLUSIVE", "a replacement also picked sides on the placebo pairs; nothing is baked")
    if any(status.get(r) == "REPLACE" for r in main_two):
        return done("REPLACE", "replace %s once with a fresh reviewer on the same folder" % ", ".join(
            r for r in main_two if status.get(r) == "REPLACE"))

    n = len(counted)
    need_w = int(math.ceil(WIN_SHARE * n - EPS))

    def a_ok(view):
        w, l_ = wl(view, counted)
        return w >= need_w and w >= WIN_LOSS * l_ - EPS

    use = ["r1", "r2"]
    if a_ok(eff["r1"]) != a_ok(eff["r2"]):
        if "r3" not in files:
            return done("NEED THIRD", "r1 and r2 split on (a): start a fresh reviewer on stage2/%s/r3" % cid)
        if status.get("r3") == "INCONCLUSIVE":
            return done("INCONCLUSIVE", "r3's replacement also picked sides on the placebo pairs; nothing is baked")
        if status.get("r3") == "REPLACE":
            return done("REPLACE", "replace r3 once with a fresh reviewer on the same folder")
        use = ["r1", "r2", "r3"]
    elif "r3" in files:
        say("  r1 and r2 agree on (a): r3's answers are not used")
    need = 2
    who = "both reviewers" if len(use) == 2 else "two of three reviewers"
    views = {r: eff[r] for r in use}
    close = [s for s in counted if key["shots"][s]["set"] == "close"]
    far = [s for s in counted if key["shots"][s]["set"] == "far"]

    say("  %-4s %5s %6s %5s %10s %10s" % ("", "wins", "losses", "same", "close W-L", "far W-L"))
    for r in use:
        w, l_ = wl(views[r], counted)
        cw, cl = wl(views[r], close)
        fw, fl = wl(views[r], far)
        say("  %-4s %5d %6d %5d %10s %10s" % (r, w, l_, n - w - l_, "%d-%d" % (cw, cl), "%d-%d" % (fw, fl)))

    items = res["items"]

    def item(name, ok, text):
        items[name] = dict(ok=bool(ok), text=text)
        say("(%s) %s  %s" % (name, "PASS" if ok else "FAIL", text))

    # (a)
    parts, oks = [], 0
    for r in use:
        w, l_ = wl(views[r], counted)
        ok = a_ok(views[r])
        oks += ok
        parts.append("%s %d wins, %d losses %s" % (r, w, l_, "ok" if ok else "short"))
    item("a", n > 0 and oks >= need, "need %d wins of %d and wins >= %.1f x losses, from %s: %s" % (
        need_w, n, WIN_LOSS, who, "; ".join(parts)))
    # (b)
    lost = []
    for s in KEY_CLOSE:
        if s in counted and sum(1 for r in use if views[r][s][0] == "L") >= need:
            lost.append(s)
    judged = [s for s in KEY_CLOSE if s in counted]
    item("b", not lost, "lost with %s: %s (judged: %s)" % (who, ", ".join(lost) or "none", ", ".join(judged) or "none"))
    # (c)
    far_ok = sum(1 for r in use if wl(views[r], far)[0] >= wl(views[r], far)[1])
    rep = [s for s in far if sum(1 for r in use if "repeat" in views[r][s][1]) >= need
           and not any("repeat" in views[r][s][2] for r in use)]
    item("c", far_ok >= need and len(rep) <= REPEAT_FAR_MAX,
         "far set (%d shots): wins >= losses with %d reviewers (need %d); new 'repeat' from %s in %d shots (max %d)%s"
         % (len(far), far_ok, need, who, len(rep), REPEAT_FAR_MAX, (": " + ", ".join(rep)) if rep else ""))
    # (d)
    c_crack = sum(1 for r in use for s in counted if "crack_web" in views[r][s][1])
    b_crack = sum(1 for r in use for s in counted if "crack_web" in views[r][s][2])
    item("d", c_crack <= CRACK_SHARE * b_crack + EPS, "crack_web ticks: %d on it, %d on before (max %.1f)" % (
        c_crack, b_crack, CRACK_SHARE * b_crack))
    # (e)
    new = {}
    for t in TELL_IDS:
        if t == "crack_web":
            continue
        hit = [s for s in counted if sum(1 for r in use if t in views[r][s][1]) >= need
               and not any(t in views[r][s][2] for r in use)]
        if hit:
            new[t] = hit
    over = {t: v for t, v in new.items() if len(v) > OTHER_TELL_MAX}
    item("e", not over, "new tells from %s, shots per tell (fails at %d): %s" % (
        who, OTHER_TELL_MAX + 1, ", ".join("%s %d" % (t, len(v)) for t, v in sorted(new.items())) or "none"))
    # (f)
    rows, bad = [], []
    for s in close:
        tol, dev_p = bright_tol(key, s)
        dev = key["bright"][cand][s]["dev"]
        rows.append("%s %s (bar %.1f %%)" % (s, fmt_pct(dev), 100 * tol))
        if abs(dev) > tol + EPS:
            bad.append(s)
    item("f", not bad, "counted close shots: %s%s" % ("; ".join(rows) or "none",
                                                       ("; over: " + ", ".join(bad)) if bad else ""))
    # (g)
    src, ta, tb, ratio = time_gate(key["times"], cand, before)
    if src is None:
        item("g", False, "no complete render seconds for %s and %s on %s" % (cand, before, ", ".join(KEY_CLOSE)))
    else:
        item("g", ratio <= TIME_MAX + EPS, "%.1f s against %.1f s: %.2f times (max %.1f; from %s)" % (
            ta, tb, ratio, TIME_MAX, "the logs" if src == "log" else "the PNGs' RenderTime"))
    # (h)
    if cand in BOTH_SETS_TAGS:
        txt = []
        ok = True
        for name, ss in (("close", close), ("far", far)):
            k = sum(1 for r in use if wl(views[r], ss)[0] > wl(views[r], ss)[1])
            ok = ok and bool(ss) and k >= need
            txt.append("%s (%d shots): more wins than losses with %d reviewers" % (name, len(ss), k))
        item("h", ok, "the lead's rule 5 for %s, need %s on each set: %s" % (cand, who, "; ".join(txt)))
    failed = [k for k, v in items.items() if not v["ok"]]
    return done("FAIL" if failed else "PASS", ("failed " + ", ".join("(%s)" % k for k in failed)) if failed else
                "next is the bake check")


# ---------------------------------------------------------------------------------------------------- main

def parser():
    ap = argparse.ArgumentParser(prog="review_stills.py", description="Round 60's blind review kit for rock stills.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare", help="masks, windows, crops, stage 1 folders, key and tables")
    p.add_argument("renders", help="folder of <prefix>_<tag>_<shot>.png stills")
    p.add_argument("--out", required=True, help="the kit's folder")
    p.add_argument("--before", default="before")
    p.add_argument("--tags", required=True, help="the real variants, comma-separated")
    p.add_argument("--placebo", default="", help="the placebo tag (p830)")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--logs", default="", help="box log folder(s) or files, comma-separated")
    p.add_argument("--prefix", default=PREFIX)
    p.add_argument("--shots", default="", help="comma-separated; default all 18")
    p.add_argument("--window", default="%dx%d" % WINDOW, help="crop size WxH (tests use a small one)")
    p.add_argument("--reviewers", type=int, default=STAGE1_REVIEWERS, help="stage 1 folders")
    p.add_argument("--force", action="store_true", help="build again over an existing kit")
    q = sub.add_parser("pairs", help="stage 2 folders for one candidate")
    q.add_argument("kit")
    q.add_argument("--candidate", required=True)
    q.add_argument("--force", action="store_true")
    s = sub.add_parser("score", help="score reviewers' answers (files or reviewer folders)")
    s.add_argument("kit")
    s.add_argument("answers", nargs="+")
    return ap


def run(argv, quiet=False):
    """Run one command; returns its result. Raises KitError on bad input."""
    a = parser().parse_args(argv)
    say = Out(quiet)
    return dict(prepare=cmd_prepare, pairs=cmd_pairs, score=cmd_score)[a.cmd](a, say)


def main(argv=None):
    try:
        run(sys.argv[1:] if argv is None else argv)
    except KitError as e:
        print("review_stills: %s" % e, file=sys.stderr)
        for p in e.problems:
            print("  - %s" % p, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
