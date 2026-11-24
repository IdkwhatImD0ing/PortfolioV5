// Opens the sect at given camera frames in one browser and graphics backend, saves a screenshot of
// each view, and reads the scene's HDR buffer back as floats to count pixels that are not real
// numbers (NaN or Inf: they show as black), negative, or whose alpha is out of range.
//
// It exists to compare machines the owner cannot sit at: the same views on a Windows PC (D3D11) and
// on a Mac (Metal), in Chrome and in WebKit. See docs/sect/render-probe.md.
//
// Read-only and silent: the site is muted, and every request that is not a same-origin static file
// is blocked (no backend wake-up, no Pusher, no analytics).
//
//   node scripts/render-probe.mjs --base https://art3m1s.me --frames 93,516 --out out
//
// Options:
//   --base URL          the site to open (default https://art3m1s.me)
//   --engine NAME       chromium (default) or webkit
//   --exe PATH          the browser to launch (chromium only; default: Playwright's own)
//   --channel NAME      a Playwright channel instead, e.g. chrome
//   --angle NAME        chromium's ANGLE backend: d3d11, gl, vulkan, metal, swiftshader (default: the browser's own)
//   --tier NAME         high, mid or low (default: none, the page's own pick for this machine)
//   --frames A,B,C      camera frames (default: the eleven stops)
//   --extra QUERY       more query, e.g. "far=1" or "far=0&live=0"
//   --label NAME        the files' prefix (default: the engine, the backend and the tier)
//   --assets ORIGIN     fetch the Git LFS files (scene packs, live-light maps) from this origin instead
//                       of --base: a build whose baked files are LFS pointers borrows production's
//   --width, --height, --dsf   the window (default 1600 x 900 at 1x)
//   --wait MS           settle time after the page says it is ready (default 8000)
//   --ready MS          how long to wait for the page to say it is ready (default 180000); after two
//                       views in a row that never get there, the run stops
//   --yaw DEG, --pitch DEG   turn the view from the flight's own (free look; left is positive)
//   --ladder N          step the quality ladder down N times first (the page's own debug hook,
//                       window.__sectLadder.down()): what a slow machine ends up drawing
//   --yaws A,B,C        several turns per frame instead of --yaw, a picture each
//   --ladders A,B,C     several ladder depths per frame instead of --ladder. The page loads once per
//                       frame and is stepped down between them; a depth that changes nothing (the
//                       ladder's bottom was reached) is skipped. "0,1,2,3,4,5,6,7,8,9,10,11,12" is
//                       every state of any tier
//   --hud 0             leave the debug panel out of the pictures (what it says is in the JSON)
//   --jpeg Q            save pictures as JPEG at quality Q instead of PNG (a sweep is hundreds)
//   --headed            show the window
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const STOPS = [93, 217, 352, 516, 619, 772, 974, 1103, 1208, 1380, 1647];

function arg(name, dflt) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1] : dflt;
}

async function loadPlaywright() {
  // PLAYWRIGHT_CORE: the folder of a playwright-core installed somewhere else (a global one).
  const at = process.env.PLAYWRIGHT_CORE;
  if (at) return createRequire(import.meta.url)(at);
  return import("playwright-core").then((m) => m.default ?? m);
}

const base = arg("base", "https://art3m1s.me").replace(/\/+$/, "");
const engine = arg("engine", "chromium");
const angle = arg("angle", "");
const tier = arg("tier", "");
const frames = arg("frames", STOPS.join(",")).split(",").map(Number).filter(Number.isFinite);
const extra = arg("extra", "");
const out = arg("out", "render-probe-out");
const assets = arg("assets", "").replace(/\/+$/, "");
const width = Number(arg("width", "1600"));
const height = Number(arg("height", "900"));
const dsf = Number(arg("dsf", "1"));
const waitMs = Number(arg("wait", "8000"));
const readyMs = Number(arg("ready", "180000"));
const yaw = Number(arg("yaw", "0"));
const pitch = Number(arg("pitch", "0"));
const ladder = Number(arg("ladder", "0"));
const numbers = (s) => s.split(",").map(Number).filter(Number.isFinite);
const yawList = arg("yaws", "") ? numbers(arg("yaws", "")) : [yaw];
const ladderList = (arg("ladders", "") ? numbers(arg("ladders", "")) : [ladder]).sort((a, b) => a - b);
const many = yawList.length > 1 || ladderList.length > 1;
const hud = arg("hud", "1") !== "0";
const jpeg = Number(arg("jpeg", "0"));
const exe = arg("exe", "");
const channel = arg("channel", "");
const headed = process.argv.includes("--headed");
const slug = (s) => s.replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "");
const label = arg("label", [engine, angle || "default", tier || "auto", extra ? slug(extra) : ""].filter(Boolean).join("-"));

fs.mkdirSync(out, { recursive: true });
const origin = new URL(base).origin;
const pw = await loadPlaywright();

const launch = { headless: !headed };
if (engine === "chromium") {
  launch.args = ["--mute-audio", "--ignore-gpu-blocklist", "--enable-gpu"];
  if (angle) launch.args.push(`--use-angle=${angle}`);
  if (angle === "swiftshader") launch.args.push("--enable-unsafe-swiftshader");
  if (angle === "vulkan") launch.args.push("--enable-features=Vulkan");
  if (exe) launch.executablePath = exe;
  if (channel) launch.channel = channel;
}
const browser = await pw[engine].launch(launch);
const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: dsf });
// Muted before the page's first script (client/CLAUDE.md: nobody at the machine should hear it).
await context.addInitScript(() => {
  try {
    localStorage.setItem("sect.music.muted", "1");
  } catch {}
});
let blocked = 0;
await context.route("**/*", async (route) => {
  const u = new URL(route.request().url());
  // Vercel's analytics scripts are same-origin (/_vercel/insights): a probe is not a visitor.
  if (u.origin !== origin || u.pathname.startsWith("/api/") || u.pathname.startsWith("/_vercel/")) {
    blocked++;
    return route.abort();
  }
  // Only what Git LFS holds (.gitattributes): the scene packs and the live-light maps. The JSON beside
  // them is in git, so a branch's own manifest and tables are the ones tested.
  if (assets && (/^\/sect\/.+\.glb\.gz$/i.test(u.pathname) || /^\/sect\/[^/]+\/live\/.+\.webp$/i.test(u.pathname))) {
    try {
      const res = await route.fetch({ url: `${assets}${u.pathname}${u.search}` });
      return route.fulfill({ response: res });
    } catch {
      return route.abort();
    }
  }
  return route.continue();
});

/** In the page: wraps the renderer's setRenderTarget so the composer's buffers are known. */
function watchTargets() {
  const gl = window.__sect.gl;
  if (gl.__probe) return;
  const seen = new Set();
  const orig = gl.setRenderTarget.bind(gl);
  gl.setRenderTarget = (rt, ...rest) => {
    if (rt) seen.add(rt);
    return orig(rt, ...rest);
  };
  gl.__probe = seen;
}

/** In the page: turns the view (lib/sect/free-look.ts) and keeps the canvas drawing for a while. */
function turnView([yawDeg, pitchDeg]) {
  const s = window.__sect.store;
  s.look.recenter = null;
  s.look.yaw = (yawDeg * Math.PI) / 180;
  s.look.pitch = (pitchDeg * Math.PI) / 180;
  s.wakeUntil = performance.now() + 4000;
}

/** In the page: what the page says about itself and the machine. */
function readInfo() {
  const s = window.__sect;
  const i = s.info();
  const ctx = s.gl.getContext();
  const dbg = ctx.getExtension("WEBGL_debug_renderer_info");
  return {
    renderer: String(dbg ? ctx.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : ctx.getParameter(ctx.RENDERER)),
    userAgent: navigator.userAgent,
    calls: i.calls,
    triangles: i.triangles,
    farTris: i.farTris,
    drawnTris: i.drawnTris,
    chunks: (i.stream?.resident ?? []).map((c) => `${c.id}${c.far ? "^" : c.drawn ? "*" : ""}${c.ready ? "" : "~"}`).join(" "),
    failed: i.stream?.failed ?? [],
    deviceMemory: navigator.deviceMemory,
    cores: navigator.hardwareConcurrency,
    dpr: window.devicePixelRatio,
    canvas: [ctx.drawingBufferWidth, ctx.drawingBufferHeight],
    quality: document.body.innerText.match(/quality\s+(.+)/)?.[1] ?? "",
    scale: document.body.innerText.match(/dpr\s+(.+)/)?.[1] ?? "",
    fps: document.body.innerText.match(/fps\s+(.+)/)?.[1] ?? "",
    maxSamples: ctx.getParameter(ctx.MAX_SAMPLES),
    glError: ctx.getError(),
  };
}

/** In the page: the composer's HDR buffers read back as floats, and what is wrong in them. */
function readBuffers() {
  const gl = window.__sect.gl;
  const ctx = gl.getContext();
  const list = [];
  for (const rt of gl.__probe ?? []) {
    if ((rt.texture?.name ?? "") !== "EffectComposer.Buffer") continue;
    const fbo = gl.properties.get(rt).__webglFramebuffer;
    if (!fbo) continue;
    const w = rt.width;
    const h = rt.height;
    const prev = ctx.getParameter(ctx.READ_FRAMEBUFFER_BINDING);
    ctx.bindFramebuffer(ctx.READ_FRAMEBUFFER, fbo);
    const px = new Float32Array(w * h * 4);
    ctx.readPixels(0, 0, w, h, ctx.RGBA, ctx.FLOAT, px);
    const err = ctx.getError();
    ctx.bindFramebuffer(ctx.READ_FRAMEBUFFER, prev);
    let nan = 0, inf = 0, neg = 0, zero = 0, aLow = 0, aHigh = 0, aNot1 = 0, max = 0;
    const where = [];
    let x0 = w, y0 = h, x1 = -1, y1 = -1;
    for (let i = 0; i < px.length; i += 4) {
      const r = px[i], g = px[i + 1], b = px[i + 2], a = px[i + 3];
      const bad = Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b) || Number.isNaN(a);
      const big = !bad && !(Number.isFinite(r) && Number.isFinite(g) && Number.isFinite(b) && Number.isFinite(a));
      if (bad) nan++;
      if (big) inf++;
      if (bad || big) {
        const p = i / 4;
        const x = p % w;
        const y = h - 1 - Math.floor(p / w);
        if (where.length < 40) where.push([x, y]);
        x0 = Math.min(x0, x);
        y0 = Math.min(y0, y);
        x1 = Math.max(x1, x);
        y1 = Math.max(y1, y);
        continue;
      }
      if (r < -1e-3 || g < -1e-3 || b < -1e-3) neg++;
      if (r === 0 && g === 0 && b === 0) zero++;
      if (a < -1e-3) aLow++;
      if (a > 1.001) aHigh++;
      if (Math.abs(a - 1) > 1e-3) aNot1++;
      const m = Math.max(r, g, b);
      if (m > max) max = m;
    }
    list.push({ w, h, samples: rt.samples, readError: err, nan, inf, neg, zero, aLow, aHigh, aNot1, max, box: x1 >= 0 ? [x0, y0, x1, y1] : null, where });
  }
  return list;
}

/**
 * In the page: the canvas's own pixels, read with readPixels right after the frame's last draw
 * (the drawing buffer is only valid until the browser shows it). Counts the pixels where one
 * channel is near 0 while the others are bright, as `crushed`: a screenshot can show such patches
 * that the canvas does not have, when the browser converts colour spaces on the way to the file
 * and lets a channel run past 255 (seen in WebKit on a Mac runner, 2026-11-20). `full` is the
 * count of channels at 255.
 *
 * `dark` counts the pixels whose brightest channel is under 24, and `grid` is the share of such
 * pixels in each cell of a 32 by 18 grid, top row first, in hundredths. Two machines' grids for the
 * same view say where one draws dark and the other does not, without anyone looking at a picture.
 */
function readCanvas() {
  return new Promise((resolve) => {
    const s = window.__sect;
    const gl = s.gl;
    const ctx = gl.getContext();
    const orig = gl.render;
    const done = (v) => {
      gl.render = orig;
      resolve(v);
    };
    const timer = setTimeout(() => done({ error: "no frame was drawn to the canvas" }), 5000);
    gl.render = function (...args) {
      const out = orig.apply(this, args);
      if (gl.getRenderTarget() !== null) return out;
      clearTimeout(timer);
      const w = ctx.drawingBufferWidth;
      const h = ctx.drawingBufferHeight;
      const px = new Uint8Array(w * h * 4);
      ctx.readPixels(0, 0, w, h, ctx.RGBA, ctx.UNSIGNED_BYTE, px);
      const COLS = 32, ROWS = 18;
      const cellDark = new Uint32Array(COLS * ROWS);
      const cellAll = new Uint32Array(COLS * ROWS);
      let cyan = 0, magenta = 0, yellow = 0, red = 0, black = 0, full = 0, dark = 0, sum = 0;
      for (let y = 0; y < h; y++) {
        // readPixels starts at the bottom row.
        const row = Math.min(ROWS - 1, Math.floor(((h - 1 - y) * ROWS) / h)) * COLS;
        for (let x = 0; x < w; x++) {
          const i = (y * w + x) * 4;
          const r = px[i], g = px[i + 1], b = px[i + 2];
          if (r < 30 && g > 200 && b > 200) cyan++;
          else if (g < 30 && r > 200 && b > 200) magenta++;
          else if (b < 30 && r > 200 && g > 200) yellow++;
          else if (r > 200 && g < 30 && b < 30) red++;
          if (r < 4 && g < 4 && b < 4) black++;
          if (r === 255) full++;
          if (g === 255) full++;
          if (b === 255) full++;
          const cell = row + Math.min(COLS - 1, Math.floor((x * COLS) / w));
          cellAll[cell]++;
          sum += r + g + b;
          if (r < 24 && g < 24 && b < 24) {
            dark++;
            cellDark[cell]++;
          }
        }
      }
      const grid = Array.from(cellDark, (n, i) => Math.round((100 * n) / Math.max(1, cellAll[i])));
      done({ w, h, crushed: cyan + magenta + yellow + red, cyan, magenta, yellow, red, black, full, dark, mean: sum / (3 * w * h), cols: COLS, rows: ROWS, grid, readError: ctx.getError() });
      return out;
    };
    s.store.wakeUntil = performance.now() + 3000;
  });
}

const results = [];
let failedInARow = 0;
for (const frame of frames) {
  if (failedInARow >= 2) {
    console.log(`${label}  stopping: two views in a row never became ready`);
    break;
  }
  const page = await context.newPage();
  const logs = [];
  page.on("console", (m) => {
    const t = m.text();
    if (/Clock: This module/.test(t)) return;
    if (/Failed to load resource/.test(t)) return; // the response listener below names the URL
    if (m.type() === "error" || m.type() === "warning" || /WebGL|GL_|shader|\[sect\]/i.test(t)) logs.push(`${m.type()}: ${t.slice(0, 400)}`);
  });
  page.on("pageerror", (e) => logs.push(`pageerror: ${String(e).slice(0, 400)}`));
  page.on("response", (res) => {
    if (res.status() >= 400) logs.push(`http ${res.status()}: ${res.url().slice(0, 200)}`);
  });
  const query = ["debug=1", "ui=0", tier ? `tier=${tier}` : "", `frame=${frame}`, extra].filter(Boolean).join("&");
  const r = { label, engine, angle, tier, frame, url: `${base}/?${query}` };
  const say = (v) => {
    const b = v.buffers?.[0];
    console.log(
      [
        label,
        many ? `f${frame} L${v.ladder} y${v.yaw}` : `f${frame}`,
        v.error ? `ERROR ${v.error.slice(0, 160)}` : "",
        v.info ? `${v.info.renderer.slice(0, 60)} | ${v.info.quality} | dpr ${v.info.scale}` : "",
        b ? `nan ${b.nan} inf ${b.inf} neg ${b.neg} zero ${b.zero} alpha>1 ${b.aHigh} max ${b.max.toFixed(2)}` : "no buffer (no post pass on this tier)",
        v.canvas ? (v.canvas.error ? `canvas: ${v.canvas.error}` : `canvas crushed ${v.canvas.crushed} black ${v.canvas.black} dark ${v.canvas.dark} at-255 ${v.canvas.full}`) : "",
        v.logs?.length ? `logs ${v.logs.length}` : "",
      ]
        .filter(Boolean)
        .join("  "),
    );
  };
  let last = null;
  try {
    await page.goto(r.url, { waitUntil: "domcontentloaded", timeout: 120000 });
    await page.waitForSelector("body[data-sect-ready]", { state: "attached", timeout: readyMs });
    await page.waitForFunction(() => !!window.__sect?.gl, null, { timeout: 60000 });
    await page.evaluate(watchTargets);
    await page.waitForTimeout(waitMs);
    if (!hud) await page.addStyleTag({ content: "[data-sect-hud]{opacity:0!important}" });
    let stepped = 0;
    let state = "";
    for (const depth of ladderList) {
      for (; stepped < depth; stepped++) {
        await page.evaluate(() => window.__sectLadder?.down());
        await page.waitForTimeout(1500);
      }
      // The ladder's bottom: a deeper step that changes nothing is the same picture again.
      const now = await page.evaluate(() => {
        const t = document.body.innerText;
        return `${t.match(/quality\s+(.+)/)?.[1] ?? ""} | ${t.match(/dpr\s+(.+)/)?.[1] ?? ""}`;
      });
      if (many && depth > ladderList[0] && now === state) continue;
      state = now;
      for (const turn of yawList) {
        const v = { ...r, ladder: depth, yaw: turn, pitch };
        if (turn !== 0 || pitch !== 0 || depth > 0 || many) {
          // Twice: the first frames after a turn or a step may still be loading what came into view.
          for (let i = 0; i < 2; i++) {
            await page.evaluate(turnView, [turn, pitch]);
            await page.waitForTimeout(1500);
          }
          // An area the turn brought into the window: wait for it, but not for the background fill.
          await page
            .waitForFunction(
              () => {
                const st = window.__sect.info().stream;
                if (!st) return true;
                return !st.resident.some((c) => !c.ready) && !st.loading.some((id) => !st.filling.includes(id));
              },
              null,
              { timeout: 15000 },
            )
            .catch(() => {});
          await page.evaluate(turnView, [turn, pitch]);
          await page.waitForTimeout(400);
        }
        v.info = await page.evaluate(readInfo);
        v.buffers = await page.evaluate(readBuffers);
        v.canvas = await page.evaluate(readCanvas);
        v.shot = `${label}-f${frame}${many ? `-L${depth}-y${turn}` : ""}.${jpeg ? "jpg" : "png"}`;
        await page.screenshot({ path: path.join(out, v.shot), ...(jpeg ? { type: "jpeg", quality: jpeg } : {}) });
        results.push(v);
        last = v;
        say(v);
      }
    }
    failedInARow = 0;
  } catch (e) {
    failedInARow++;
    const v = { ...r, error: String(e).slice(0, 600) };
    try {
      v.shot = `${label}-f${frame}-error.png`;
      await page.screenshot({ path: path.join(out, v.shot) });
    } catch {}
    results.push(v);
    last = v;
    say(v);
  }
  // One page per frame: its console lines go on the frame's last view.
  if (last) last.logs = logs.slice(0, 40);
  if (last?.logs.length) console.log(`${label}  f${frame}  logs ${last.logs.length}: ${last.logs[0].slice(0, 160)}`);
  await page.close();
  // A sweep takes a long time: what is done so far is on disk.
  fs.writeFileSync(path.join(out, `${label}.json`), JSON.stringify({ label, base, blocked, results }, null, 1));
}
await browser.close();
fs.writeFileSync(path.join(out, `${label}.json`), JSON.stringify({ label, base, blocked, results }, null, 1));
