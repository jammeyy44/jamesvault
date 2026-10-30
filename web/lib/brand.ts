/**
 * Central brand settings. Rename the product or tweak the palette here (and in tailwind.config.ts).
 * The backend can also override name/tagline/support email through GET /api/v1/site/config.
 */
export const brand = {
  name: "stakesweep.net",
  tagline: "Your next winning moment starts here.",
  description:
    "stakesweep.net is a premium gaming destination with a curated game lobby, instant bonus rewards and dedicated player support.",
  siteUrl: process.env.NEXT_PUBLIC_SITE_URL || "https://stakesweep.net",
  colors: {
    page: "#0B0E17",
    ink: "#FFFFFF",
    primary: "#38BDF8",
    electric: "#00D2FF",
    violet: "#7C3AED",
    soft: "#141A29",
    line: "#1E2638",
    muted: "#94A3B8",
    success: "#36D98A",
  },
  gradient: "linear-gradient(135deg, #7C3AED 0%, #4F46E5 100%)",
} as const;

export const navLinks = [
  { href: "/", label: "Home" },
  { href: "/games", label: "Games" },
  { href: "/bonus-zone", label: "Bonus Zone" },
  { href: "/refer", label: "Refer a Friend" },
] as const;
