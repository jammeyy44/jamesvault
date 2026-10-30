const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8080";

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
        ],
      },
    ];
  },
  images: { remotePatterns: [{ protocol: "https", hostname: "**" }] },
};

export default nextConfig;
