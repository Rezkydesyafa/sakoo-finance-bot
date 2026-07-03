/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.BUILD_TARGET === 'android' ? 'export' : undefined,
  images: {
    unoptimized: true,
  }
};

export default nextConfig;
