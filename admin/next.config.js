/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['@arco-design/web-react'],
  experimental: {
    workerThreads: false,
    cpus: 1,
  },
  serverActions: {
    bodySizeLimit: '200mb',
  },
};

module.exports = nextConfig;
