import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const apiProxyUrl = process.env.API_PROXY_URL || "https://gscheme-production.up.railway.app/api";

    return [
      {
        source: "/backend-api/:path*",
        destination: `${apiProxyUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
