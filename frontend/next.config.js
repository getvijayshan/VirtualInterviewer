/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // When API_PROXY_TARGET is set (e.g. http://<vm-ip>), /api/* is forwarded to
  // the backend server-side. Set NEXT_PUBLIC_API_BASE_URL=/api so an HTTPS
  // frontend (Vercel) can reach a plain-HTTP API without mixed-content or CORS.
  async rewrites() {
    const target = process.env.API_PROXY_TARGET;
    if (!target) return [];
    return [{ source: "/api/:path*", destination: `${target.replace(/\/$/, "")}/:path*` }];
  },
};

module.exports = nextConfig;
