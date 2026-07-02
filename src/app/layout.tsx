import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';
import { GlobalProviders } from '@/providers/GlobalProviders';
import '@/styles/globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Industrial Operating Brain (IOB)',
  description: 'Enterprise Industry 5.0 Intelligent Monitoring Platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body id="__next_root">
        <AppRouterCacheProvider options={{ enableCssLayer: true }}>
          <GlobalProviders>
            {children}
          </GlobalProviders>
        </AppRouterCacheProvider>
      </body>
    </html>
  );
}
