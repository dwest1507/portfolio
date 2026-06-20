import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { Analytics } from '@vercel/analytics/react'
import Header from '@/components/layout/Header'
import Footer from '@/components/layout/Footer'
import AmbientBackground from '@/components/layout/ScanlineOverlay'
import ChatbotWidget from '@/components/chatbot/ChatbotWidget'
import './globals.css'

const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin'],
  display: 'swap',
})

export const metadata: Metadata = {
  metadataBase: new URL('https://davidwest.dev'),
  title: 'David West — AI Engineer',
  description:
    'AI Engineer with 5+ years of experience building intelligent systems. View projects and ask my AI assistant about my qualifications.',
  openGraph: {
    title: 'David West — AI Engineer',
    description:
      'AI Engineer with 5+ years of experience building intelligent systems. View projects and ask my AI assistant about my qualifications.',
    type: 'website',
    images: ['/og-image.png'],
  },
  twitter: {
    card: 'summary_large_image',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="flex min-h-screen flex-col">
        <AmbientBackground />
        <Header />
        <main className="relative z-10 flex-1">{children}</main>
        <Footer />
        <ChatbotWidget />
        <Analytics />
      </body>
    </html>
  )
}
