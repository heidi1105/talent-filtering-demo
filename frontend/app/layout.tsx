import type { Metadata } from 'next'
import { DM_Sans, DM_Mono } from 'next/font/google'
import './globals.css'
import { AuthProvider } from '@/components/auth/AuthProvider'

const dmSans = DM_Sans({ subsets: ['latin'], variable: '--font-dm-sans' })
const dmMono = DM_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-dm-mono',
})

export const metadata: Metadata = {
  title: 'Talent Roster',
  description: 'Internal talent database',
  // Page-wide fallback so kprofiles.com photos (hotlink-blocked by Referer)
  // still load if a browser/proxy doesn't honor the per-<img> referrerPolicy
  // attribute — some mobile browsers and data-saver proxies re-request images
  // through their own layer and drop the element-level policy.
  referrer: 'no-referrer',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${dmSans.variable} ${dmMono.variable} bg-bg text-text font-sans`}>
        {/* AuthProvider is a 'use client' component — Next.js handles the
            server/client boundary automatically when a server component
            (this layout) imports and renders a client component. */}
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  )
}
