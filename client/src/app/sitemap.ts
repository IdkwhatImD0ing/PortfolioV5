import { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: "https://art3m1s.me",
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 1,
    },
    // The soundtrack's own page (app/music).
    {
      url: "https://art3m1s.me/music",
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.5,
    },
  ];
}
