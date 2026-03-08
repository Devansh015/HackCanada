import type { Metadata } from 'next'
import './globals.css'
import { ProfileProvider } from '@/context/ProfileContext'

export const metadata: Metadata = {
  title: 'Cortex | Neural Intelligence',
  description: 'A living neural network visualization powered by advanced AI',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="antialiased">
        <ProfileProvider>
          {children}
        </ProfileProvider>
      </body>
    </html>
  )
}
