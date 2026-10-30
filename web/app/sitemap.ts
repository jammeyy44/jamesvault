import type { MetadataRoute } from "next";
import { brand } from "@/lib/brand";

const PUBLIC = ["", "/games", "/bonus-zone", "/refer", "/support", "/legal/terms", "/legal/privacy", "/legal/responsible-gaming"];

export default function sitemap(): MetadataRoute.Sitemap {
  return PUBLIC.map((p) => ({ url: `${brand.siteUrl}${p}`, changeFrequency: "weekly", priority: p === "" ? 1 : 0.7 }));
}
