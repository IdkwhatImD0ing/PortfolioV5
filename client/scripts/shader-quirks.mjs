// What does this browser's graphics path make of a few shader expressions GLSL leaves open? Each
// one is compiled into its own tiny program, fed its numbers as uniforms (so nothing is folded at
// compile time), drawn into a 1 x 1 float target and read back. docs/sect/render-probe.md has what
// the answers were on Windows and on a Mac, in Chrome and in WebKit.
//
//   node scripts/shader-quirks.mjs [--engine chromium|webkit] [--exe PATH] [--channel chrome] [--angle metal]
import { createRequire } from "node:module";

function arg(name, dflt) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1] : dflt;
}

async function loadPlaywright() {
  const at = process.env.PLAYWRIGHT_CORE;
  if (at) return createRequire(import.meta.url)(at);
  return import("playwright-core").then((m) => m.default ?? m);
}

const engine = arg("engine", "chromium");
const angle = arg("angle", "");
const exe = arg("exe", "");
const channel = arg("channel", "");

// The frame grade's tone curve as the page had it (lib/sect/glsl.ts lookFrameGradeGlsl), and with
// its bases kept off zero. u: (0, 1, k, p). v: (1.3, 0.99999994, 1.0000001, 0.5).
const CURVE = `
float curve( float v, float p, float k ) {
  float x = clamp( v, 0.0, 1.0 );
  return x < p ? p * pow( x / p, k ) : 1.0 - ( 1.0 - p ) * pow( ( 1.0 - x ) / ( 1.0 - p ), k );
}
float curveFloored( float v, float p, float k ) {
  float x = clamp( v, 0.0, 1.0 );
  return x < p ? p * pow( max( x / p, 1e-6 ), k ) : 1.0 - ( 1.0 - p ) * pow( max( ( 1.0 - x ) / ( 1.0 - p ), 1e-6 ), k );
}
float gradeChannel( float c, float p, float k ) {
  float cv = pow( min( c, 1.0 ), 0.45454545 );
  float cc = pow( curve( cv, p, k ), 2.2 );
  return mix( cc, c, step( 1.0, c ) );
}
float gradeChannelFixed( float c, float p, float k ) {
  float cv = pow( clamp( c, 1e-6, 1.0 ), 0.45454545 );
  float cc = pow( curveFloored( cv, p, k ), 2.2 );
  return c >= 1.0 ? c : cc;
}
`;

const TESTS = [
  ["pow( 0, k ), k a uniform", "pow( u.x, u.z )", "0"],
  ["pow( 0, 4.0 )", "pow( u.x, 4.0 )", "0"],
  ["pow( 0, 0.4545 )", "pow( u.x, 0.45454545 )", "0"],
  ["pow( 1, 0.4545 )", "pow( u.y, 0.45454545 )", "1"],
  ["pow( min( 1.3, 1 ), 0.4545 )", "pow( min( v.x, 1.0 ), 0.45454545 )", "1"],
  ["pow( 0.99999994, 0.4545 )", "pow( v.y, 0.45454545 )", "just under 1"],
  ["1 - clamp( pow( 1, 0.4545 ), 0, 1 )", "1.0 - clamp( pow( min( v.x, 1.0 ), 0.45454545 ), 0.0, 1.0 )", "0"],
  ["pow( ( 1 - 1 ) / ( 1 - p ), k )", "pow( ( 1.0 - u.y ) / ( 1.0 - u.w ), u.z )", "0"],
  ["the curve at 1", "curve( u.y, u.w, u.z )", "1"],
  ["the curve at pow( min( 1.3, 1 ), 0.4545 )", "curve( pow( min( v.x, 1.0 ), 0.45454545 ), u.w, u.z )", "1"],
  ["the grade of a channel at 1.3 (as it was)", "gradeChannel( v.x, u.w, u.z )", "1.3"],
  ["the grade of a channel at 1.0 (as it was)", "gradeChannel( u.y, u.w, u.z )", "1"],
  ["the grade of a channel at 0.5 (as it was)", "gradeChannel( v.w, u.w, u.z )", "a number near 0.5"],
  ["the grade of a channel at 0 (as it was)", "gradeChannel( u.x, u.w, u.z )", "0"],
  ["the grade of a channel at 1.3 (fixed)", "gradeChannelFixed( v.x, u.w, u.z )", "1.3"],
  ["the grade of a channel at 1.0 (fixed)", "gradeChannelFixed( u.y, u.w, u.z )", "1"],
  ["the grade of a channel at 0.5 (fixed)", "gradeChannelFixed( v.w, u.w, u.z )", "the same number near 0.5"],
  ["the grade of a channel at 0 (fixed)", "gradeChannelFixed( u.x, u.w, u.z )", "0"],
  ["mix( NaN, 1.3, 1.0 )", "mix( sqrt( u.x - 1.0 ), v.x, u.y )", "NaN by the book"],
  ["pow( -0.0000001, 4.0 )", "pow( u.x - 1e-7, 4.0 )", "undefined in GLSL"],
  ["pow( -0.0000001, k ), k a uniform", "pow( u.x - 1e-7, u.z )", "undefined in GLSL"],
  ["pow( 1 - 1.0000001, 5.0 )", "pow( 1.0 - v.z, 5.0 )", "undefined in GLSL"],
  ["clamp( NaN, 0, 1 )", "clamp( sqrt( u.x - 1.0 ), 0.0, 1.0 )", "undefined in GLSL"],
  ["max( NaN, 0 )", "max( sqrt( u.x - 1.0 ), 0.0 )", "undefined in GLSL"],
  ["min( NaN, 1 )", "min( sqrt( u.x - 1.0 ), 1.0 )", "undefined in GLSL"],
  ["0 * ( 1 / 0 )", "u.x * ( u.y / u.x )", "NaN by the book"],
];

/** In the page: runs every test and returns its float and its bits. */
function run([tests, curve]) {
  const canvas = document.createElement("canvas");
  const gl = canvas.getContext("webgl2");
  if (!gl) return { error: "no WebGL 2" };
  const float = gl.getExtension("EXT_color_buffer_float");
  const dbg = gl.getExtension("WEBGL_debug_renderer_info");
  const renderer = String(dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
  if (!float) return { error: "no float render target", renderer };
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texStorage2D(gl.TEXTURE_2D, 1, gl.RGBA32F, 1, 1);
  const fbo = gl.createFramebuffer();
  gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
  gl.viewport(0, 0, 1, 1);
  const vs = gl.createShader(gl.VERTEX_SHADER);
  gl.shaderSource(vs, "#version 300 es\nvoid main(){ vec2 p = vec2( float( ( gl_VertexID << 1 ) & 2 ), float( gl_VertexID & 2 ) ); gl_Position = vec4( p * 2.0 - 1.0, 0.0, 1.0 ); }");
  gl.compileShader(vs);
  const out = [];
  const px = new Float32Array(4);
  const bits = new Uint32Array(px.buffer);
  for (const [name, expr, expected] of tests) {
    const fs = gl.createShader(gl.FRAGMENT_SHADER);
    gl.shaderSource(fs, `#version 300 es\nprecision highp float;\nuniform vec4 u;\nuniform vec4 v;\nout vec4 o;\n${curve}\nvoid main(){ o = vec4( ${expr}, 0.0, 0.0, 1.0 ); }`);
    gl.compileShader(fs);
    const prog = gl.createProgram();
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      out.push({ name, expected, error: (gl.getShaderInfoLog(fs) || gl.getProgramInfoLog(prog) || "link failed").slice(0, 200) });
      continue;
    }
    gl.useProgram(prog);
    // k 1.12 and p 0.42: a contrast and a pivot of the kind the journey sets.
    gl.uniform4f(gl.getUniformLocation(prog, "u"), 0, 1, 1.12, 0.42);
    gl.uniform4f(gl.getUniformLocation(prog, "v"), 1.3, 0.99999994, 1.0000001, 0.5);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.FLOAT, px);
    const x = px[0];
    out.push({ name, expected, value: Number.isNaN(x) ? "NaN" : Number.isFinite(x) ? String(x) : x > 0 ? "+Inf" : "-Inf", bits: bits[0].toString(16).padStart(8, "0") });
  }
  return { renderer, userAgent: navigator.userAgent, out };
}

const pw = await loadPlaywright();
const launch = { headless: true };
if (engine === "chromium") {
  launch.args = ["--ignore-gpu-blocklist", "--enable-gpu"];
  if (angle) launch.args.push(`--use-angle=${angle}`);
  if (exe) launch.executablePath = exe;
  if (channel) launch.channel = channel;
}
const browser = await pw[engine].launch(launch);
const page = await browser.newPage();
await page.goto("about:blank");
const r = await page.evaluate(run, [TESTS, CURVE]);
await browser.close();
console.log(`engine: ${engine}${angle ? ` (${angle})` : ""}`);
console.log(`gpu: ${r.renderer ?? "?"}`);
console.log(`browser: ${(r.userAgent ?? "").replace(/^Mozilla\/5\.0 /, "")}`);
if (r.error) {
  console.log(`could not run: ${r.error}`);
  process.exit(1);
}
const wide = Math.max(...r.out.map((t) => t.name.length));
for (const t of r.out) console.log(`${t.name.padEnd(wide)}  ${t.error ? `ERROR ${t.error}` : `${t.value.padEnd(14)} (bits ${t.bits})`}   expected: ${t.expected}`);
