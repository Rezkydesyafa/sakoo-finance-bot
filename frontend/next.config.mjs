/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingRoot: process.cwd(),
  output: process.env.BUILD_TARGET === 'android' ? 'export' : undefined,
  images: {
    unoptimized: true,
  }
};

export default nextConfig;
