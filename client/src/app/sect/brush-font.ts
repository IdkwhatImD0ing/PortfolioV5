import localFont from "next/font/local";

/**
 * The brush hand for the places' Chinese names (lib/sect/brush.ts): Ma Shan Zheng, SIL Open Font
 * License 1.1 (assets/OFL-MaShanZheng.txt), cut down to the 35 characters the page writes in it
 * (about 16 KB). Preloaded on /sect only. Until it is in, or where it fails, the serif CJK stack
 * draws the names: each character is a full em square in both, so nothing moves when it swaps.
 */
export const brushFont = localFont({
  src: "./assets/sect-brush.woff2",
  variable: "--font-sect-brush",
  display: "swap",
  preload: true,
  // Its metrics are a CJK em box; an Arial-based fallback would size the serif wrongly.
  adjustFontFallback: false,
  fallback: ["Noto Serif SC", "Source Han Serif SC", "Songti SC", "STSong", "SimSun", "serif"],
});
