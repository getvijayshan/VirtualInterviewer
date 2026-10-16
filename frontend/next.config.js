/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Self-contained server bundle (.next/standalone) so the VM only needs the
  // Node runtime — it is built on the CI runner and copied over.
  output: "standalone",
  // Optional: forward /api/* to another backend (e.g. a hosted frontend talking
  // to a plain-HTTP API). On the VM, Nginx does this instead.
  async rewrites() {
    const target = process.env.API_PROXY_TARGET;
    if (!target) return [];
    return [{ source: "/api/:path*", destination: `${target.replace(/\/$/, "")}/:path*` }];
  },
};

module.exports = nextConfig;
