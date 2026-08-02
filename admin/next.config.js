/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['@arco-design/web-react'],
  // 禁用静态页面收集，避免构建时预渲染 API 路由导致超时
  experimental: {
    workerThreads: false,
    cpus: 1,
  },
};

module.exports = nextConfig;
