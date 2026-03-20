import type { Metadata } from 'next'
import { Orbitron, JetBrains_Mono } from 'next/font/google'
import { Analytics } from '@vercel/analytics/react'
import Header from '@/components/layout/Header'
import Footer from '@/components/layout/Footer'
import ScanlineOverlay from '@/components/layout/ScanlineOverlay'
import ChatbotWidget from '@/components/chatbot/ChatbotWidget'
import './globals.css'

const orbitron = Orbitron({
  variable: '--font-orbitron',
  subsets: ['latin'],
  weight: ['400', '500', '600', '700', '800', '900'],
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  variable: '--font-jetbrains-mono',
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700'],
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
    <html lang="en" className={`${orbitron.variable} ${jetbrainsMono.variable}`}>
      <body className="flex min-h-screen flex-col">
        <ScanlineOverlay />
        <Header />
        <main className="relative z-10 flex-1">{children}</main>
        <Footer />
        <ChatbotWidget />
        <Analytics />
      </body>
    </html>
  )
}
