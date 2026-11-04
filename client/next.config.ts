import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        // A 3D asset fetched as <file>?v=<fingerprint> (the manifest's `rev`, see fetchUrl in lib/sect/parse.ts)
        // never changes under that URL: a changed file gets a new fingerprint. So the browser and the CDN may
        // keep it for a year. Without `v` (manifest.json above all) the default stays: check every time.
        source: "/sect/:path*",
        has: [{ type: "query", key: "v" }],
        headers: [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }],
      },
    ];
  },
};

export default nextConfig;
