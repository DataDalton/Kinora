/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: require('path').join(__dirname, '../'),

  // React Compiler for automatic component memoization
  reactCompiler: true,

  // Turbopack configuration (now top-level in Next.js 16)
  turbopack: {
    rules: {},
  },

  // Partial Prerendering: combines static shell with streaming dynamic content
  cacheComponents: true,

  experimental: {
    // Enable Turbopack filesystem caching for faster compile times across restarts
    turbopackFileSystemCacheForDev: true,
    // Client router cache control
    staleTimes: {
      dynamic: 30,
      static: 180,
    },
    // Faster builds by optimizing barrel file imports
    optimizePackageImports: ['lucide-react'],
  },

  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'image.tmdb.org',
        pathname: '/t/p/**',
      },
      {
        protocol: 'https',
        hostname: 's4.anilist.co',
        pathname: '/file/**',
      },
    ],
    // Next.js 16 defaults: quality 75 for better performance
    // minimumCacheTTL defaults to 4 hours (14400 seconds)
    // dangerouslyAllowLocalIP defaults to false for security
  },

  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
