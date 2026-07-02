'use client';

import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { SidebarProvider } from '@/contexts/SidebarContext';
import { TelemetryProvider } from '@/contexts/TelemetryContext';

// Enterprise Industrial Operating Brain - Dark Theme
const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#007ACC', // Industrial Blue
    },
    secondary: {
      main: '#64748B', // Slate
    },
    background: {
      default: '#0B0F19', // Dark Gray
      paper: '#111827',
    },
    divider: '#1F2937',
  },
  typography: {
    fontFamily: 'var(--font-inter), Inter, system-ui, sans-serif',
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: '#0B0F19',
          color: '#F3F4F6',
          margin: 0,
          padding: 0,
          minHeight: '100vh',
        },
        '*': {
          scrollbarWidth: 'thin',
          scrollbarColor: '#1F2937 #0B0F19',
        },
        '*::-webkit-scrollbar': {
          width: '8px',
          height: '8px',
        },
        '*::-webkit-scrollbar-track': {
          background: '#0B0F19',
        },
        '*::-webkit-scrollbar-thumb': {
          backgroundColor: '#1F2937',
          borderRadius: '4px',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: '4px',
          fontWeight: 500,
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#111827',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: '#111827',
          borderRight: '1px solid #1F2937',
        },
      },
    },
  },
});

export function GlobalProviders({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            retry: 1,
            staleTime: 5 * 60 * 1000, // 5 minutes
            gcTime: 10 * 60 * 1000, // 10 minutes
          },
          mutations: {
            retry: 0,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={darkTheme}>
        <CssBaseline />
        <TelemetryProvider>
          <SidebarProvider>
            {children}
          </SidebarProvider>
        </TelemetryProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default GlobalProviders;
