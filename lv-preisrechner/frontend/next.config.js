/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Self-hosting (Docker/Hetzner): Next.js erzeugt .next/standalone mit
  // minimal node_modules + server.js. Vercel ignoriert diesen Flag
  // transparent (eigener Build-Pipeline), also keine Kollision.
  // Siehe: https://nextjs.org/docs/app/api-reference/config/next-config-js/output
  output: "standalone",
  // Backend-URL:
  //   Local Dev: BACKEND_URL nicht gesetzt → http://127.0.0.1:8100
  //   Vercel:    BACKEND_URL = https://lv-preisrechner-backend.onrender.com
  async rewrites() {
    const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8100";
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
    ];
  },
  // Längere Response-Timeouts für PDF-Uploads (Vercel Serverless Cap: 60s/300s auf Pro)
  experimental: {
    proxyTimeout: 300_000, // 5 Minuten Proxy-Timeout für Vision-Calls
  },
};
module.exports = nextConfig;
