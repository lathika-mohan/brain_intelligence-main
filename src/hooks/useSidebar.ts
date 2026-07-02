'use client';

import { useContext } from 'react';
import { SidebarContext } from '@/contexts/SidebarContext';

export function useSidebar() {
  const context = useContext(SidebarContext);
  if (!context) {
    throw new Error('useSidebar must be instantiated within a valid SidebarProvider layout tree.');
  }
  return context;
}

// Backwards compatibility alias for components/contexts expecting useSidebarContext
export const useSidebarContext = useSidebar;
