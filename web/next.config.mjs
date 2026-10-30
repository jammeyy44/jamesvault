const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8080";

// Everything the site loads comes from its own origin (API and uploads are proxied through it). Inline scripts/styles are
// needed by Next.js itself; blob:/data: cover chat attachment previews and inline icons.
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'" + (process.env.NODE_ENV === "production" ? "" : " 'unsafe-eval'"),
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "media-src 'self' blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  // The browser only ever talks to this origin; Flask stays private behind the proxy,
  // which keeps session cookies first-party and makes CORS unnecessary.
  async redirects() {
    return [
      { source: "/promotions", destination: "/bonus-zone", permanent: false },
      { source: "/tournaments", destination: "/bonus-zone", permanent: false },
      { source: "/tournaments/:slug", destination: "/bonus-zone", permanent: false },
    ];
  },
  async rewrites() {
    return [
      { source: "/api/v1/:path*", destination: `${BACKEND_URL}/api/v1/:path*` },
      { source: "/uploads/:path*", destination: `${BACKEND_URL}/uploads/:path*` }, // uploaded game thumbnails
    ];
  },
  async headers() {
    return [
      {
        // Site artwork never changes under the same name (replace an image by giving it a new file name): cache it for a year.
        source: "/images/:path*",
        headers: [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }],
      },
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
          { key: "Content-Security-Policy", value: CSP },
        ],
      },
    ];
  },
  images: { remotePatterns: [] }, // next/image is not used; no remote host may be fetched by the optimizer
};

export default nextConfig;
