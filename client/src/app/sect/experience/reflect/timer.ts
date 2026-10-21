/**
 * GPU time of tagged spans (the reflection passes, or a whole frame) through
 * EXT_disjoint_timer_query_webgl2, for the debug probe (?debug=1) and inspection scripts. A span
 * is skipped when another time query is already running (the render driver's own), so the two
 * never collide; a disjoint drops what was in flight. Rolling means over the last `keep` samples.
 */
export class SpanTimer {
  private readonly ext: { TIME_ELAPSED_EXT: number; GPU_DISJOINT_EXT: number } | null;
  private readonly pending: { q: WebGLQuery; tag: string }[] = [];
  private active: { q: WebGLQuery; tag: string } | null = null;
  private readonly samples = new Map<string, number[]>();

  constructor(
    private readonly gl: WebGL2RenderingContext | null,
    private readonly keep = 60,
  ) {
    this.ext = gl ? (gl.getExtension("EXT_disjoint_timer_query_webgl2") as { TIME_ELAPSED_EXT: number; GPU_DISJOINT_EXT: number } | null) : null;
  }

  get available(): boolean {
    return this.ext !== null;
  }

  begin(tag: string): void {
    const { gl, ext } = this;
    if (!gl || !ext || this.active || this.pending.length > 8) return;
    if (gl.getQuery(ext.TIME_ELAPSED_EXT, gl.CURRENT_QUERY)) return;
    const q = gl.createQuery();
    if (!q) return;
    gl.beginQuery(ext.TIME_ELAPSED_EXT, q);
    this.active = { q, tag };
  }

  end(): void {
    const { gl, ext } = this;
    if (!gl || !ext || !this.active) return;
    gl.endQuery(ext.TIME_ELAPSED_EXT);
    this.pending.push(this.active);
    this.active = null;
  }

  poll(): void {
    const { gl, ext } = this;
    if (!gl || !ext || this.pending.length === 0) return;
    const disjoint = gl.getParameter(ext.GPU_DISJOINT_EXT) as boolean;
    while (this.pending.length > 0) {
      const p = this.pending[0];
      if (!disjoint && !gl.getQueryParameter(p.q, gl.QUERY_RESULT_AVAILABLE)) break;
      this.pending.shift();
      if (!disjoint) {
        const list = this.samples.get(p.tag) ?? [];
        list.push((gl.getQueryParameter(p.q, gl.QUERY_RESULT) as number) / 1e6);
        if (list.length > this.keep) list.shift();
        this.samples.set(p.tag, list);
      }
      gl.deleteQuery(p.q);
    }
  }

  /** Mean, median and count per tag (ms). */
  stats(): Record<string, { mean: number; median: number; n: number }> {
    const out: Record<string, { mean: number; median: number; n: number }> = {};
    for (const [tag, list] of this.samples) {
      if (list.length === 0) continue;
      const s = [...list].sort((a, b) => a - b);
      out[tag] = { mean: list.reduce((a, b) => a + b, 0) / list.length, median: s[Math.floor(s.length / 2)], n: list.length };
    }
    return out;
  }

  clear(): void {
    this.samples.clear();
  }

  dispose(): void {
    const { gl, ext } = this;
    if (!gl || !ext) return;
    if (this.active) {
      gl.endQuery(ext.TIME_ELAPSED_EXT);
      gl.deleteQuery(this.active.q);
      this.active = null;
    }
    for (const p of this.pending) gl.deleteQuery(p.q);
    this.pending.length = 0;
  }
}
