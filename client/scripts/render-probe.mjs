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
      let cyan = 0, magenta = 0, yellow = 0, red = 0, black = 0, full = 0;
      for (let i = 0; i < px.length; i += 4) {
        const r = px[i], g = px[i + 1], b = px[i + 2];
        if (r < 30 && g > 200 && b > 200) cyan++;
        else if (g < 30 && r > 200 && b > 200) magenta++;
        else if (b < 30 && r > 200 && g > 200) yellow++;
        else if (r > 200 && g < 30 && b < 30) red++;
        if (r < 4 && g < 4 && b < 4) black++;
        if (r === 255) full++;
        if (g === 255) full++;
        if (b === 255) full++;
      }
      done({ w, h, crushed: cyan + magenta + yellow + red, cyan, magenta, yellow, red, black, full, readError: ctx.getError() });
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
  try {
    await page.goto(r.url, { waitUntil: "domcontentloaded", timeout: 120000 });
    await page.waitForSelector("body[data-sect-ready]", { state: "attached", timeout: readyMs });
    await page.waitForFunction(() => !!window.__sect?.gl, null, { timeout: 60000 });
    await page.evaluate(watchTargets);
    await page.waitForTimeout(waitMs);
    for (let i = 0; i < ladder; i++) {
      await page.evaluate(() => window.__sectLadder?.down());
      await page.waitForTimeout(1500);
    }
    if (yaw !== 0 || pitch !== 0 || ladder > 0) {
      // Twice: the first frames after a turn or a step may still be loading what came into view.
      for (let i = 0; i < 2; i++) {
        await page.evaluate(turnView, [yaw, pitch]);
        await page.waitForTimeout(1500);
      }
    }
    r.info = await page.evaluate(readInfo);
    r.buffers = await page.evaluate(readBuffers);
    r.canvas = await page.evaluate(readCanvas);
    r.shot = `${label}-f${frame}.png`;
    await page.screenshot({ path: path.join(out, r.shot) });
    failedInARow = 0;
  } catch (e) {
    failedInARow++;
    r.error = String(e).slice(0, 600);
    try {
      r.shot = `${label}-f${frame}-error.png`;
      await page.screenshot({ path: path.join(out, r.shot) });
    } catch {}
  }
  r.logs = logs.slice(0, 40);
  results.push(r);
  const b = r.buffers?.[0];
  console.log(
    [
      label,
      `f${frame}`,
      r.error ? `ERROR ${r.error.slice(0, 160)}` : "",
      r.info ? `${r.info.renderer.slice(0, 60)} | ${r.info.quality}` : "",
      b ? `nan ${b.nan} inf ${b.inf} neg ${b.neg} zero ${b.zero} alpha>1 ${b.aHigh} max ${b.max.toFixed(2)}` : "no buffer (no post pass on this tier)",
      r.canvas ? (r.canvas.error ? `canvas: ${r.canvas.error}` : `canvas crushed ${r.canvas.crushed} black ${r.canvas.black} at-255 ${r.canvas.full}`) : "",
      r.logs.length ? `logs ${r.logs.length}` : "",
    ]
      .filter(Boolean)
      .join("  "),
  );
  await page.close();
}
await browser.close();
fs.writeFileSync(path.join(out, `${label}.json`), JSON.stringify({ label, base, blocked, results }, null, 1));
