# Black holes in the mist, and the render probe

Added 2026-11-18, rewritten 2026-11-20 once the cause was found.

## What the owner saw

2026-11-18: "I was testing this on my macbook, and i seemed to see back spots in various background
clouds and stuff? But its not seeable on my pc".

2026-11-20: "Wait now I see the black parts on my windows machine as well", with a screenshot: the
mirror terrace, the view turned right over the valley, crisp black shapes in the mist where the
forest should be.

## The cause: the quality ladder stopped drawing the trees

When frames run long the page steps its quality down (the ladder, `degradeQuality` in
`client/src/lib/sect/runtime.ts`). Its second-to-last step, after "the other areas as stand-ins",
stopped drawing every tree card. On High the crown shells were tied to that step too, so every far
forest went.

The ground under the forests is baked nearly black: in the bake the trees stand over it. Without
the trees it shows as black holes, with the mist's wisps drawn over them.

A MacBook reaches the bottom of the ladder because High is too much for it. The PC reaches it when
something else has the GPU, a game for one. Then the ladder climbs back and the trees return, so
it comes and goes.

The owner's screenshot carries the other signs of that state: jagged edges on the stairs (no MSAA,
three-quarter render scale) and no trees on the far cliff top.

### How it was found

Two days went to a wrong theory first (the next section). The screenshot settled it:

1. Its black shapes are crisp. The first theory predicts blocks spread over a third of the frame.
2. Its place was found by turning the view at each stop: the mirror terrace, turned right.
3. At that place the scene's raw numbers are clean in every direction, on High and on Medium. So
   the black is not drawn wrong. Something is missing.
4. What is missing there is the forest. Stepping the ladder down by hand
   (`window.__sectLadder.down()` with `?debug=1`) shows it: at "stand-ins" the valley has its
   forest, at "stand-ins, no cards" it is a dark void.

### The fix

The step is gone. The ladder now ends: render scale, stand-ins, 30 fps. The trees are never a step.

What the step bought, measured at four stops at the bottom of the ladder: 11 percent of the draw
calls left by then (16 to 19 of about 160) and 18 to 23 percent of the triangles (0.44 to 0.61
million of about 2.6 million). The step before it, stand-ins, takes 45 to 66 percent of the draw
calls on its own.

`runtime.test.ts` walks every tier to the bottom and fails if a step takes the trees again.

Checked in the browser on a build of this branch: stepped to the bottom at the mirror terrace and
turned as in the owner's screenshot, the valley keeps its forest, and the quality line reads
"stand-ins, 30 fps cap". The live site at the same step reads "stand-ins, no cards, 30 fps cap" and
shows the void.

### What is left

- The ground under the forests is still nearly black. With the baked cards (Medium, and High once
  the ladder has taken the shells off) it shows as dark gaps between tree clumps where the trees
  stand apart. A bake round, or a tint on that ground in the page, would close it.
- Why the PC went down the ladder that day was not measured. If it happens with nothing else using
  the GPU, the ladder's own judgement is the next thing to look at. `?debug=1` shows the quality
  line.

## The first theory: a Mac's pow

Before the screenshot the only fact was "a Mac shows it and the PC does not", so the search was for
what a Mac's graphics path does differently. One real difference came out of it, and its guards
stay in. It is not what the owner saw, and it has not been seen on a Mac.

The page's shaders are GLSL. The browser translates them: on Windows to D3D11, on a Mac to Metal,
in Chrome and Safari alike. `pow( x, y )` has no defined answer for x below zero. On Windows the
translator writes `pow( x, 2.0 )` and other small whole exponents as multiplications, so a base of
-0.0000001 does no harm. On a Mac pow is `exp2( y * log2( x ) )`, and a negative base gives NaN
("not a number"). A base goes a hair under zero where `1.0 - dot( a, b )` is taken of two unit
vectors that line up: the dot rounds to 1.0000001.

What one NaN pixel does, measured on the PC by forcing NaN onto the far tree crowns at the arena:
103,024 NaN pixels (7 percent of the frame) left 1,187,672 of 1,265,920 pixels black (94 percent).
A NaN pixel is black, cloud drawn over it stays black, and bloom's mip chain spreads it into a
block.

A five-reviewer audit of the shader code, each finding challenged by a second reviewer, left 12 of
21 findings standing as plausible and none proven. The likeliest: the reflections' sky
(`sectEnvSky` in `materials.ts`), where `pow( sunSide, 4.0 )` goes under zero for a reflection
straight away from the sun.

The guards:

1. Every such pow has a floor: the two skies' `sunSide`, the crowns' `facing`, the wet rock's
   Fresnel, the hover highlight, the grade's lift, the finish's toe, the contact shade's tint, the
   sparks' and embers' life. The reflections' sky holds the ray's height to 1 before `asin`.
2. The fog chunk swaps a colour that is not a number for the haze's colour (`fogChunks` in
   `glsl.ts`), before the multisample resolve and before bloom.
3. Bloom's threshold drops a texel that is not a number (`glowPrefilter` in `post/atmos.ts`).
4. The hue clip caps its input under the half-float buffer's largest number, and the finish's
   sharpening ignores a neighbour that is not a number.

The test for "not a number" reads the float's bits (`nonFiniteGlsl` in `glsl.ts`): Metal builds
shaders with fast maths, which may drop `x != x` or `isnan( x )`. `POW_BASE_NOTE` in `glsl.ts` holds
the reason in the code, and `nan-guards.test.ts` fails if a guard goes missing.

On the PC the guards change nothing: before against after at all eleven stops, High and Medium, the
pixels that differ by more than 40 levels are 0.3 to 4.2 percent, and two runs of the same build
differ by 0.3 to 3.4 percent (flags, fire, the forge's orbiting artifacts).

## The render probe

`client/scripts/render-probe.mjs` opens the sect at given camera frames in one browser and saves,
for each view:

- a screenshot;
- the HDR frame read back as floats: how many pixels are NaN or Inf (and where the first 40 are),
  negative, exactly zero, or carry an alpha over 1;
- what the page says about itself: the GPU, the quality line, the places held, far triangles;
- console errors and failed requests.

It mutes the site and blocks every request that is not a same-origin static file (the backend,
Pusher, Vercel's analytics). It needs `?debug=1`, which the page has in production too.

```bash
# the live site on this machine's default graphics path
PLAYWRIGHT_CORE=<a playwright-core folder> node scripts/render-probe.mjs --base https://art3m1s.me --tier high --out out

# a local build whose baked files are Git LFS pointers: borrow production's
node scripts/render-probe.mjs --base http://localhost:3000 --assets https://art3m1s.me --tier high --out out

# what a slow machine ends up drawing at the mirror terrace, looking over the valley
node scripts/render-probe.mjs --frames 205 --yaw -40 --pitch -12 --ladder 10 --width 1226 --height 945 --out out
```

`--engine webkit` runs Safari's engine, `--angle metal|d3d11|vulkan` picks Chrome's backend,
`--extra "far=0&lux=0"` adds switches, `--frames 93,516` picks views (default: the eleven stops),
`--yaw` and `--pitch` turn the view, `--ladder N` steps the quality down N times first.

`client/scripts/render-compare.mjs` compares two sets of those screenshots view by view: pixels
near black in one and not in the other, pixels much darker, and a diff picture of each.

```bash
node scripts/render-compare.mjs --a pc --alabel pc-high --b mac --blabel live-chrome-high --out diff
```

What the probe taught about itself: views along the flight at the stops are not enough. This bug
needed a turned view and a quality state the page only reaches when frames run long. Check both.

### On a Mac nobody owns

`.github/workflows/mac-render-probe.yml` runs the probe on one of GitHub's Mac machines (Apple
silicon, Metal): the live site in one job, this branch built on the runner in another (its baked
files borrowed from the live site). It uploads the screenshots and counts. Start it by hand from
the Actions tab, or push to the branch named in the file. The repo is public, so the Mac minutes
are free.

The runner's GPU is a virtual one over real Apple hardware. It runs Metal and Apple's shader
compiler, which is where the pow difference lives, but it is not the owner's MacBook, and its
frame times say nothing about a real one's ladder.
