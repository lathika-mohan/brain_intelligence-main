'use client';

import { useEffect } from 'react';
import { useTheme as useMuiTheme } from '@mui/material/styles';
import { useLocalStorage } from './useLocalStorage';

export type Theme = 'dark' | 'light' | 'high-contrast';

export function useTheme() {
  const muiTheme = useMuiTheme();
  const [themeMode, setThemeMode] = useLocalStorage<Theme>('iob_theme', 'dark');

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const root = document.documentElement;
    root.setAttribute('data-theme', themeMode);
    if (themeMode === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [themeMode]);

  const toggleTheme = () => {
    setThemeMode((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  return {
    // Section 9 core architectural base hooks contract
    theme: muiTheme,
    isDark: muiTheme?.palette?.mode === 'dark' || themeMode === 'dark',
    // Legacy integration wiring & backwards compatibility
    themeMode,
    setTheme: setThemeMode,
    toggleTheme,
  };
}
