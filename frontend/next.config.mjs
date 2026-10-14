/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'upload.wikimedia.org',
      },
    ],
  },
  // The PPTX route reads reference/pptx_template.pptx from disk at request
  // time. Nothing imports it, so Vercel's dependency tracing can't see it and
  // would otherwise leave it out of the serverless bundle — the export then
  // 500s in production while working fine locally. Named file by file so the
  // rest of reference/ stays out of the bundle.
  experimental: {
    outputFileTracingIncludes: {
      '/export/pptx': ['./reference/pptx_template.pptx'],
    },
  },
}

export default nextConfig
