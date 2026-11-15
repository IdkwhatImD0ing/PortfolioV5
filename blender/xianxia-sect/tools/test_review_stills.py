"""Offline test of tools/review_stills.py (round 60's blind review kit) on synthetic stills. No Blender. Run on the PC
with

    python -P E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect/tools/test_review_stills.py

(-P, not -I: numpy lives in the user site on this PC). It builds small stills (192 x 108, a 96 x 54 window) for the
18 shots in a temporary folder, runs prepare, pairs and score on them, and deletes the folder. Prints
'test_review_stills ok' when every check passes; it takes a few seconds.
"""
import contextlib
import io
import json
import math
import os
import shutil
import sys
import tempfile
import time

import numpy as np
from PIL import Image, PngImagePlugin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_stills as RS  # noqa: E402

W, H = 192, 108
WIN = (96, 54)
REAL = ("mtn8", "big3", "mtn12")
PLACEBO = "p830"
TAGS = ("before", PLACEBO) + REAL
RENDER_TIME = dict(before="00:04.00", mtn8="00:04.80", big3="00:05.60", mtn12="00:04.40", p830="00:04.00")
SMALL = ("scroll_1103", "summit_1647")     # changed only on 10 x 10 pixels: not counted
PROOF = "steles_974_close"                  # the placebo moves brightness a lot here: (f)'s bar widens
BOX = "/E:/Github/PortfolioV5/blender/xianxia-sect/out/tmp/r60/renders/"


def lin(c):
    return ((c / 255.0 + 0.055) / 1.055) ** 2.4


def checker(h, w, lo, hi):
    yy, xx = np.mgrid[0:h, 0:w]
    return np.where((yy + xx) % 2 == 0, lo, hi).astype(np.uint8)


def rect_of(i, shot):
    """The rock box a shot's variants change: (x0, y0, x1, y1)."""
    if shot in SMALL:
        return 150, 80, 160, 90
    if shot == "gate_93":
        return 20, 30, 60, 50
    x0, y0 = 10 + (i * 37) % 120, 8 + (i * 23) % 70
    return x0, y0, x0 + 60, y0 + 30


def make_stills(d):
    """Synthetic stills for every tag and shot; returns {shot: rock box}."""
    boxes = {}
    for i, shot in enumerate(RS.SHOTS):
        rng = np.random.default_rng(1000 + i)
        base = rng.uniform(60, 200, size=(H // 6 + 1, W // 6 + 1, 3))
        base = np.kron(base, np.ones((6, 6, 1)))[:H, :W].astype(np.uint8)
        x0, y0, x1, y1 = boxes[shot] = rect_of(i, shot)
        base[y0:y1, x0:x1] = 120
        imgs = {t: base.copy() for t in TAGS}
        h, w = y1 - y0, x1 - x0
        if shot == "gate_93":
            # +8 everywhere does not count as a change, +9 on the box does
            imgs["mtn8"] = (base.astype(np.int16) + 8).astype(np.uint8)
            imgs["mtn8"][y0:y1, x0:x1] = 129
        else:
            for t in ("mtn8", "mtn12"):
                imgs[t][y0:y1, x0:x1] = checker(h, w, 100, 140)[..., None]
            imgs["big3"][y0:y1, x0:x1] = checker(h, w, 90, 150)[..., None]
            if shot == PROOF:
                imgs[PLACEBO][y0:y1, x0:x1] = checker(h, w, 90, 150)[..., None]
            else:       # the placebo changes the left half of the box only
                imgs[PLACEBO][y0:y1, x0:x0 + w // 2] = checker(h, w // 2, 110, 130)[..., None]
        for t in TAGS:
            info = PngImagePlugin.PngInfo()
            info.add_text("File", "/E:/Github/PortfolioV5/blender/xianxia-sect/out/r60_%s.blend" % t)
            info.add_text("RenderTime", RENDER_TIME[t])
            Image.fromarray(imgs[t]).save(os.path.join(d, "r59_%s_%s.png" % (t, shot)), pnginfo=info)
    return boxes


def make_logs(d):
    """Box logs: before's first try stopped after two stills; its retry, then mtn8 and big3. mtn12 has none."""
    os.makedirs(d)

    def lines(tag, secs, shots=RS.SHOTS, first=70.0):
        out = ["Blender 5.2.2", "PREVIEW cycles device OPTIX ['NVIDIA GeForce RTX 5090'] samples 64",
               "PREVIEW close boxes from %stargets.json ['abode_1380']" % BOX]
        for k, s in enumerate(shots):
            info = ("rock point 89.7 m off (nearest the frame's centre); lens 50 mm, 30.1 m to the box's centre"
                    if s.endswith("_close") else "site framing (0.0, 0.0, 0)")
            out.append("PREVIEW wrote %sr59_%s_%s.png frame 1380 %s relief none %.1f s" % (
                BOX, tag, s, info, first if k == 0 else secs))
        return out

    files = [("1_before_try.log", lines("before", 9.0, RS.SHOTS[:2])),
             ("2_before.log", lines("before", 4.0)), ("3_mtn8.log", lines("mtn8", 4.8)),
             ("4_big3.log", lines("big3", 5.6))]
    now = time.time()
    for k, (name, ls) in enumerate(files):
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write("\r\n".join(ls) + "\r\n")        # tee on Windows can leave CRLF
        os.utime(p, (now - 100 + k, now - 100 + k))


def check(cond, what):
    if not cond:
        raise AssertionError(what)


def read_rgb(path):
    with Image.open(path) as im:
        return np.array(im.convert("RGB"))


def check_readme(path):
    """A reviewer's README names no tag and no role."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read().lower()
    for word in TAGS + ("placebo", "today", "candidate", "variant"):
        check(word not in text, "%s names %r" % (path, word))


def expect_error(argv, what):
    try:
        RS.run(argv, quiet=True)
    except RS.KitError as e:
        return e
    raise AssertionError("no KitError: " + what)


# ---------------------------------------------------------------------------------------------------- unit checks

def test_units():
    a = np.zeros((1, 3, 3), np.uint8)
    b = a.copy()
    b[0, 1, 2] = 8
    b[0, 2, 0] = 9
    check(RS.change_mask(b, a).tolist() == [[False, False, True]], "a change of 8 is not a change, 9 is")
    m = np.zeros((100, 200), bool)
    m[60:90, 150:190] = True
    x0, y0, x1, y1, n = RS.densest_window(m, 80, 45)
    check(n == 30 * 40 and x0 <= 150 and x1 >= 190 and y0 <= 60 and y1 >= 90, "window covers the change")
    check(RS.densest_window(np.zeros((100, 200), bool), 80, 46)[:4] == (60, 27, 140, 73), "empty: centred window")
    check(RS.densest_window(m, 400, 400)[:4] == (0, 0, 200, 100), "a window larger than the frame shrinks to it")
    check(abs(RS.hms_seconds("00:04.42") - 4.42) < 1e-9 and abs(RS.hms_seconds("01:02:03.50") - 3723.5) < 1e-9,
          "Blender's render time")
    check(RS.split_name("r59_after2_abode_1380.png", "r59", RS.SHOTS) == ("after2", "abode_1380"), "split name")
    check(RS.split_name("r59_after2_abode_1380_close.png", "r59", RS.SHOTS) == ("after2", "abode_1380_close"),
          "split name, close")
    check(RS.split_name("r59_abode_1380.png", "r59", RS.SHOTS) is None, "a still without a tag is skipped")


# ---------------------------------------------------------------------------------------------------- prepare

def test_prepare(tmp, renders, boxes, logs):
    kit = os.path.join(tmp, "kit")
    argv = ["prepare", renders, "--out", kit, "--before", "before", "--tags", ",".join(REAL), "--placebo", PLACEBO,
            "--seed", "60", "--logs", logs, "--window", "%dx%d" % WIN]
    key = RS.run(argv, quiet=True)
    shots = key["shots"]
    counted = [s for s in RS.SHOTS if shots[s]["counted"]]
    check(counted == [s for s in RS.SHOTS if s not in SMALL], "counted set: %s" % counted)
    for s in RS.SHOTS:
        x0, y0, x1, y1 = shots[s]["window"]
        bx0, by0, bx1, by1 = boxes[s]
        check(x1 - x0 == WIN[0] and y1 - y0 == WIN[1], "window size")
        check(x0 <= bx0 and y0 <= by0 and x1 >= bx1 and y1 >= by1, "%s: the window holds the change" % s)
    check(abs(shots["gate_93"]["window_share"] - 800.0 / (WIN[0] * WIN[1])) < 1e-9, "gate_93: +8 does not count")
    check(abs(shots["gate_93"]["union_share"] - 800.0 / (W * H)) < 1e-9, "gate_93: only the +9 box changed")
    # brightness over the shot's changed pixels (the union: the box), and over each still's own
    dev_m = (lin(100) + lin(140)) / 2 / lin(120) - 1
    dev_b = (lin(90) + lin(150)) / 2 / lin(120) - 1
    dev_p = (lin(110) + lin(130)) / 2 / lin(120) - 1
    br = key["bright"]
    check(abs(br["mtn8"]["abode_1380_close"]["dev"] - dev_m) < 1e-4, "mtn8 brightness %s" % br["mtn8"])
    check(abs(br["big3"]["mirror_217"]["dev"] - dev_b) < 1e-4, "big3 brightness")
    check(abs(br[PLACEBO]["mirror_217"]["dev"] - dev_p / 2) < 1e-4, "placebo over the box: half of it changed")
    check(abs(br[PLACEBO]["mirror_217"]["dev_own"] - dev_p) < 1e-4, "placebo over its own changed pixels")
    check(abs(br[PLACEBO][PROOF]["dev"] - dev_b) < 1e-4, "placebo brightness at %s" % PROOF)
    check(abs(br["mtn8"]["abode_1380_close"]["changed"] - 1800.0 / (W * H)) < 1e-9, "changed share")
    check(abs(br[PLACEBO]["mirror_217"]["changed"] - 900.0 / (W * H)) < 1e-9, "the placebo's own changed share")
    check(br["mtn12"]["gate_93"]["dev"] == 0.0 and br["mtn12"]["gate_93"]["dev_own"] == 0.0
          and br["mtn12"]["gate_93"]["changed"] == 0.0, "unchanged still: no deviation")
    # times: the retry's line wins, the run's first still is marked, mtn12 falls back to the PNGs
    t = key["times"]
    check(t["before"]["abode_1380_close"]["log"] == 4.0, "the retried still's last line wins")
    check(t["before"]["abode_1380"]["log_first"] is True and t["before"]["abode_1380_close"]["log_first"] is False,
          "the run's first still is marked")
    check("before_abode_1380_close" in key["log_duplicates"], "duplicates listed")
    check(t["mtn12"]["mirror_217_close"]["log"] is None and abs(t["mtn12"]["mirror_217_close"]["png"] - 4.4) < 1e-9,
          "PNG RenderTime read")
    check(RS.time_gate(t, "mtn8", "before")[0] == "log" and abs(RS.time_gate(t, "mtn8", "before")[3] - 1.2) < 1e-9,
          "time gate from the logs")
    check(RS.time_gate(t, "mtn12", "before")[0] == "png" and abs(RS.time_gate(t, "mtn12", "before")[3] - 1.1) < 1e-9,
          "time gate from the PNGs when a log lacks one")
    # stage 1 folders
    s1 = key["stage1"]
    check(sorted(s1) == ["r1", "r2"], "two stage 1 folders")
    for rid, folders in s1.items():
        check(sorted(f["shot"] for f in folders.values()) == sorted(counted), "%s: one folder per counted shot" % rid)
        for fid, f in folders.items():
            d = os.path.join(kit, "stage1", rid, fid)
            check(sorted(os.listdir(d)) == ["%s.png" % c for c in "abcde"], "five crops a to e")
            check(sorted(f["letters"].values()) == sorted(TAGS), "every tag once")
            for letter, tag in f["letters"].items():
                with Image.open(os.path.join(d, letter + ".png")) as im:
                    im.load()
                    check("File" not in im.info and "RenderTime" not in im.info, "no PNG text on a crop")
                    crop = np.asarray(im.convert("RGB"))
                x0, y0, x1, y1 = key["shots"][f["shot"]]["window"]
                src = read_rgb(os.path.join(renders, "r59_%s_%s.png" % (tag, f["shot"])))
                check(np.array_equal(crop, src[y0:y1, x0:x1]), "the crop is 1:1 and is the mapped tag")
        check(os.path.isfile(os.path.join(kit, "stage1", rid, "README.txt")), "README")
        with open(os.path.join(kit, "stage1", rid, "answers_template.json"), encoding="utf-8") as fh:
            tpl = json.load(fh)
        check(tpl["kit"] == "stage1/" + rid and sorted(tpl["shots"]) == sorted(folders), "template")
    check([s1["r1"][k] for k in sorted(s1["r1"])] != [s1["r2"][k] for k in sorted(s1["r2"])],
          "the two reviewers get different shuffles")
    oldest = []
    for fid, f in s1["r1"].items():
        d = os.path.join(kit, "stage1", "r1", fid)
        first = min(f["letters"], key=lambda x: os.stat(os.path.join(d, x + ".png")).st_mtime_ns)
        oldest.append(f["letters"][first])
    check(oldest.count("before") < len(oldest) and len(set(oldest)) > 1, "file dates do not mark before: %s" % oldest)
    check_readme(os.path.join(kit, "stage1", "r1", "README.txt"))
    # same seed, same kit; another seed, another shuffle; no overwrite without --force
    key2 = RS.run(["prepare", renders, "--out", os.path.join(tmp, "kit2")] + argv[4:], quiet=True)
    check(key2["stage1"] == key["stage1"], "the seed fixes the shuffles")
    argv3 = list(argv)
    argv3[argv3.index("--seed") + 1] = "61"
    key3 = RS.run(["prepare", renders, "--out", os.path.join(tmp, "kit3")] + argv3[4:], quiet=True)
    check(key3["stage1"] != key["stage1"], "another seed, another shuffle")
    expect_error(argv, "a second prepare into the same kit")
    shutil.rmtree(os.path.join(tmp, "kit2"))
    shutil.rmtree(os.path.join(tmp, "kit3"))
    return kit, key


# ---------------------------------------------------------------------------------------------------- stage 1

def stage1_answers(key, rid, order, tells=None):
    shots = {}
    for fid, f in key["stage1"][rid].items():
        inv = {t: x for x, t in f["letters"].items()}
        shots[fid] = dict(rank=[inv[t] for t in order],
                          tells={inv[t]: list((tells or {}).get(t, [])) for t in f["letters"].values()})
    return {"kit": "stage1/" + rid, "shots": shots}


def write(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return path


def test_stage1(kit, key, ans):
    def score(o1, o2, t1=None, t2=None):
        p1 = write(os.path.join(ans, "s1_r1.json"), stage1_answers(key, "r1", o1, t1))
        p2 = write(os.path.join(ans, "s1_r2.json"), stage1_answers(key, "r2", o2, t2))
        return RS.run(["score", kit, p1, p2], quiet=True)

    r = score(["mtn8", "mtn12", "before", PLACEBO, "big3"], ["mtn12", "mtn8", PLACEBO, "before", "big3"])
    check(r["mean"]["mtn8"] == 1.5 and r["mean"]["mtn12"] == 1.5 and r["mean"]["big3"] == 5.0, "mean ranks")
    check(r["today"] == 3.5 and r["noise"] == 0.0 and r["bar"] == 0.75, "today, noise, bar")
    check(r["advanced"] == ["mtn8", "mtn12"] and r["queue"] == ["mtn8", "mtn12"], "tie order: mtn8 before mtn12")
    r = score(["mtn8", "mtn12", "before", PLACEBO, "big3"], ["mtn12", "mtn8", PLACEBO, "before", "big3"],
              t1={"mtn8": ["crack_web"]})
    check(r["queue"] == ["mtn12", "mtn8"], "equal means: fewer crack_web ticks first")
    r = score(["mtn8", "before", "mtn12", "big3", PLACEBO], ["mtn8", "before", "mtn12", "big3", PLACEBO])
    check(r["noise"] == 3.0 and r["bar"] == 6.0 and r["advanced"] == [], "a noisy placebo raises the bar")
    r = score(["mtn8", "mtn12", "before", PLACEBO, "big3"], ["mtn8", "mtn12", PLACEBO, "before", "big3"])
    check(r["noise"] == 0.0 and r["advanced"] == ["mtn8", "mtn12"] and r["queue"] == ["mtn8"],
          "the second is 1.0 behind: not queued")
    r = score(["mtn8", "mtn12", "before", PLACEBO, "big3"], ["mtn8", "mtn12", "before", PLACEBO, "big3"])
    check(r["noise"] == 1.0 and r["bar"] == 2.0 and r["advanced"] == ["mtn8"], "bar 2 x noise: mtn12 drops out")
    r = score(["before", PLACEBO, "mtn8", "mtn12", "big3"], ["before", PLACEBO, "mtn8", "mtn12", "big3"])
    check(r["advanced"] == [] and r["queue"] == [], "nothing beats today")
    # a reviewer folder's answers.json, without a "kit" entry
    data = stage1_answers(key, "r1", ["mtn8", "mtn12", "before", PLACEBO, "big3"])
    del data["kit"]
    write(os.path.join(kit, "stage1", "r1", "answers.json"), data)
    p2 = write(os.path.join(ans, "s1_r2.json"), stage1_answers(key, "r2", ["mtn8", "mtn12", "before", PLACEBO,
                                                                           "big3"]))
    r = RS.run(["score", kit, os.path.join(kit, "stage1", "r1"), p2], quiet=True)
    check(r["reviewers"] == ["r1", "r2"], "a folder is read as its answers.json")
    os.remove(os.path.join(kit, "stage1", "r1", "answers.json"))
    # one reviewer is not enough; an answers.json whose "kit" names another folder is refused
    expect_error(["score", kit, p2], "stage 1 scored with one reviewer")
    write(os.path.join(kit, "stage1", "r2", "answers.json"),
          stage1_answers(key, "r1", ["mtn8", "mtn12", "before", PLACEBO, "big3"]))
    e = expect_error(["score", kit, os.path.join(kit, "stage1", "r2"), p2], "r2's folder holds r1's answers")
    check("its \"kit\" says stage1/r1" in str(e), "the mismatch is named: %s" % e)
    os.remove(os.path.join(kit, "stage1", "r2", "answers.json"))
    # bad answers: a missing letter, an unknown tell, both listed
    bad = stage1_answers(key, "r1", ["mtn8", "mtn12", "before", PLACEBO, "big3"])
    fid = sorted(bad["shots"])[0]
    bad["shots"][fid]["rank"] = bad["shots"][fid]["rank"][:4]
    bad["shots"][fid]["tells"]["a"] = ["mud"]
    e = expect_error(["score", kit, write(os.path.join(ans, "bad.json"), bad), p2], "bad stage 1 answers")
    check(len(e.problems) == 2, "both problems listed: %s" % e.problems)
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        code = RS.main(["score", kit, os.path.join(ans, "bad.json"), p2])
    check(code == 2 and "unknown tell" in err.getvalue(), "the command line exits 2 on bad answers")


# ---------------------------------------------------------------------------------------------------- stage 2

def test_pairs(kit, key):
    k2 = RS.run(["pairs", kit, "--candidate", "mtn8"], quiet=True)
    counted = [s for s in RS.SHOTS if key["shots"][s]["counted"]]
    check(k2["cid"] == "c1" and k2["counted"] == counted and k2["placebo_pairs"] == 4, "pairs: ids and counts")
    sides = {}
    for rid in RS.STAGE2_REVIEWERS:
        folders = k2["reviewers"][rid]
        check(len(folders) == len(counted) + 4, "%s: every counted shot and 4 placebo pairs" % rid)
        plac = sorted(f["shot"] for f in folders.values() if f["kind"] == "placebo")
        check(plac == sorted(RS.PLACEBO_PAIR_SHOTS), "placebo pairs on the four close shots")
        for fid, f in folders.items():
            check({f["A"], f["B"]} == {"before", "mtn8" if f["kind"] == "real" else PLACEBO}, "pair tags")
            sides.setdefault((f["shot"], f["kind"]), {})[rid] = f["A"] == "before"
            d = os.path.join(kit, "stage2", "c1", rid, fid)
            check(sorted(os.listdir(d)) == ["A_crop.png", "A_full.png", "B_crop.png", "B_full.png"], "pair files")
            check(all(os.stat(os.path.join(d, x)).st_nlink == 1 for x in os.listdir(d)),
                  "copies, not hard links: a link count would mark before")
        with Image.open(os.path.join(kit, "stage2", "c1", rid, "p01", "A_full.png")) as im:
            im.load()
            check(im.size == (W, H) and "File" not in im.info and "RenderTime" not in im.info,
                  "full stills carry no PNG text")
        check_readme(os.path.join(kit, "stage2", "c1", rid, "README.txt"))
    check(all(v["r1"] != v["r2"] for v in sides.values()), "r2 sees every pair's sides flipped")
    check(any(v["r1"] != v["r3"] for v in sides.values()), "r3 has its own sides")
    orders = [[(f["shot"], f["kind"]) for _k, f in sorted(k2["reviewers"][rid].items())] for rid in ("r1", "r2")]
    check(orders[0] != orders[1], "each reviewer has its own order")
    expect_error(["pairs", kit, "--candidate", "mtn8"], "pairs twice without --force")
    expect_error(["pairs", kit, "--candidate", "before"], "before is not a candidate")
    return k2, RS.run(["pairs", kit, "--candidate", "big3"], quiet=True), \
        RS.run(["pairs", kit, "--candidate", "mtn12"], quiet=True)


def stage2_answers(k2, rid, policy):
    """policy(shot, kind) -> (outcome for the tested side 'W' | 'L' | 'S', its tells, before's tells)."""
    pairs = {}
    for fid, f in k2["reviewers"][rid].items():
        tested = "A" if f["A"] != "before" else "B"
        other = "B" if tested == "A" else "A"
        out, tc, tb = policy(f["shot"], f["kind"])
        pairs[fid] = {"pick": "same" if out == "S" else (tested if out == "W" else other),
                      "tells_" + tested: list(tc), "tells_" + other: list(tb)}
    return {"kit": "stage2/%s/%s" % (k2["cid"], rid), "pairs": pairs}


def win_all(shot, kind):
    return ("W", [], []) if kind == "real" else ("S", [], [])


def test_stage2(kit, key, ans, k_m, k_b, k_12):
    n = [0]

    def score(k2, *runs):
        paths = []
        for rid, pol in runs:
            n[0] += 1
            paths.append(write(os.path.join(ans, "s2_%d_%s_%s.json" % (n[0], k2["cid"], rid)),
                               stage2_answers(k2, rid, pol)))
        return RS.run(["score", kit] + paths, quiet=True)

    def fails(r):
        return sorted(k for k, v in r["items"].items() if not v["ok"])

    counted = k_m["counted"]
    far = [s for s in counted if s in RS.FAR_SET]
    check(len(counted) == 16 and len(far) == 7, "16 counted pairs, 7 far")
    r = score(k_m, ("r1", win_all), ("r2", win_all))
    check(r["verdict"] == "PASS" and sorted(r["items"]) == list("abcdefg") and not fails(r), "mtn8 passes: %s" % r)

    def wins_on(shots):
        return lambda s, kind: ("W" if s in shots else "S", [], []) if kind == "real" else ("S", [], [])

    need = int(math.ceil(0.6 * 16))
    r = score(k_m, ("r1", wins_on(counted[:need - 1])), ("r2", wins_on(counted[:need - 1])))
    check(r["verdict"] == "FAIL" and fails(r) == ["a"], "(a): one win short: %s" % fails(r))
    # a split on (a) asks for a third reviewer; with r3 two of three decide
    r = score(k_m, ("r1", win_all), ("r2", wins_on(counted[:8])))
    check(r["verdict"] == "NEED THIRD", "split on (a)")
    r = score(k_m, ("r1", win_all), ("r2", wins_on(counted[:8])), ("r3", win_all))
    check(r["verdict"] == "PASS" and r["items"]["a"]["ok"], "two of three pass (a)")
    # the placebo check: replace once, then inconclusive

    def picks_placebo(shot, kind):
        return ("W", [], []) if kind == "real" else ("L", [], [])

    r = score(k_m, ("r1", picks_placebo), ("r2", win_all))
    check(r["verdict"] == "REPLACE", "a reviewer who picks sides on the placebo pairs is replaced")
    r = score(k_m, ("r1", picks_placebo), ("r1", win_all), ("r2", win_all))
    check(r["verdict"] == "PASS", "the replacement passes")
    r = score(k_m, ("r1", picks_placebo), ("r1", picks_placebo), ("r2", win_all))
    check(r["verdict"] == "INCONCLUSIVE", "the replacement picks sides too")

    def two_of_four(shot, kind):
        return ("W", [], []) if kind == "real" or shot in RS.PLACEBO_PAIR_SHOTS[:2] else ("S", [], [])

    r = score(k_m, ("r1", two_of_four), ("r2", win_all))
    check(r["verdict"] == "PASS", "2 of 4 placebo picks is allowed")
    # (b): a key close shot lost with both
    lose_abode = lambda s, kind: ("L" if s == "abode_1380_close" else "W", [], []) if kind == "real" else ("S", [], [])  # noqa: E731,E501
    r = score(k_m, ("r1", lose_abode), ("r2", lose_abode))
    check(fails(r) == ["b"], "(b) %s" % fails(r))
    r = score(k_m, ("r1", lose_abode), ("r2", win_all))
    check(not fails(r), "(b) lost with one reviewer only is allowed")
    # (c): far losses; new repeats on far shots

    def lose_far(shot, kind):
        return ("L" if shot in far[:4] else "W", [], []) if kind == "real" else ("S", [], [])

    r = score(k_m, ("r1", lose_far), ("r2", lose_far))
    check(fails(r) == ["c"], "(c) far losses %s" % fails(r))

    def repeats(on_before):
        def pol(shot, kind):
            if kind != "real":
                return "S", [], []
            rep = ["repeat"] if shot in far[:2] else []
            return "W", rep, (rep if shot in on_before else [])
        return pol

    r = score(k_m, ("r1", repeats(())), ("r2", repeats(())))
    check(fails(r) == ["c"], "(c) new repeat on 2 far shots %s" % fails(r))
    r = score(k_m, ("r1", repeats((far[0],))), ("r2", repeats(())))
    check(not fails(r), "(c) a repeat before has too does not count")
    # (d): crack_web ticks against before's

    def cracks(n_c, n_b):
        def pol(shot, kind):
            if kind != "real":
                return "S", [], []
            i = counted.index(shot)
            return "W", (["crack_web"] if i < n_c else []), (["crack_web"] if i < n_b else [])
        return pol

    r = score(k_m, ("r1", cracks(3, 2)), ("r2", cracks(0, 2)))
    check(fails(r) == ["d"], "(d) 3 against 4 %s" % fails(r))
    r = score(k_m, ("r1", cracks(2, 2)), ("r2", cracks(0, 2)))
    check(not fails(r), "(d) 2 against 4")
    # (e): another tell new on 3 shots with both

    def plaster(k):
        return lambda s, kind: ("W", ["plaster"] if counted.index(s) < k else [], []) if kind == "real" \
            else ("S", [], [])

    r = score(k_m, ("r1", plaster(3)), ("r2", plaster(3)))
    check(fails(r) == ["e"], "(e) %s" % fails(r))
    r = score(k_m, ("r1", plaster(2)), ("r2", plaster(3)))
    check(not fails(r), "(e) 2 shots with both")
    # big3: brighter than the bar (except where the placebo widens it), slower, and the lead's rule 5
    r = score(k_b, ("r1", win_all), ("r2", win_all))
    check(fails(r) == ["f", "g"] and "h" in r["items"], "big3: (f) and (g) fail, (h) is scored: %s" % fails(r))
    check(PROOF not in r["items"]["f"]["text"].split("over: ")[1], "(f): the placebo's own deviation widens the bar")
    check("1.40 times" in r["items"]["g"]["text"], "(g) ratio from the logs")
    lose_all_far = lambda s, kind: ("L" if s in far else "W", [], []) if kind == "real" else ("S", [], [])  # noqa: E731,E501
    r = score(k_b, ("r1", lose_all_far), ("r2", lose_all_far))
    check("h" in fails(r) and "c" in fails(r), "(h): big3 must win the far set too")
    r = score(k_12, ("r1", win_all), ("r2", win_all))
    check(r["verdict"] == "PASS" and "PNGs" in r["items"]["g"]["text"], "mtn12: (g) from the PNGs, passes")
    # answers for two candidates at once are refused
    p1 = write(os.path.join(ans, "x1.json"), stage2_answers(k_m, "r1", win_all))
    p2 = write(os.path.join(ans, "x2.json"), stage2_answers(k_b, "r2", win_all))
    expect_error(["score", kit, p1, p2], "two candidates in one score")
    bad = stage2_answers(k_m, "r2", win_all)
    bad["pairs"]["p01"]["pick"] = "left"
    expect_error(["score", kit, p1, write(os.path.join(ans, "x3.json"), bad)], "a bad pick")


def main():
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="test_review_stills_")
    try:
        renders = os.path.join(tmp, "renders")
        os.makedirs(renders)
        ans = os.path.join(tmp, "answers")
        os.makedirs(ans)
        boxes = make_stills(renders)
        logs = os.path.join(tmp, "logs")
        make_logs(logs)
        test_units()
        kit, key = test_prepare(tmp, renders, boxes, logs)
        test_stage1(kit, key, ans)
        k_m, k_b, k_12 = test_pairs(kit, key)
        test_stage2(kit, key, ans, k_m, k_b, k_12)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("test_review_stills ok (%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
