'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

export interface SidebarContextType {
  // Core state - Enterprise API
  isOpen: boolean;
  isCollapsed: boolean;
  // Actions - full enterprise API (backwards compatible with existing IOB wiring)
  toggleSidebar: () => void;
  toggleCollapse: () => void;
  closeMobileSidebar: () => void;
  setIsOpen: (open: boolean) => void;
  // Simple API - for Global Shell Isolation spec
  toggle: () => void;
}

export const SidebarContext = createContext<SidebarContextType | undefined>(undefined);

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);

  // Global Shell Isolation: responsive auto-collapse at 1200px
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1200) {
        setIsOpen(false);
      } else {
        setIsOpen(true);
      }
      // Auto-collapse the desktop sidebar at tighter breakpoints too
      if (window.innerWidth < 1440 && window.innerWidth >= 1200) {
        // Optional: keep it open but allow user control
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const toggleSidebar = useCallback(() => {
    setIsOpen((prev) => !prev);
  }, []);

  const toggleCollapse = useCallback(() => {
    setIsCollapsed((prev) => !prev);
  }, []);

  const closeMobileSidebar = useCallback(() => {
    setIsOpen(false);
  }, []);

  // Simple API alias for spec compliance
  const toggle = toggleSidebar;

  const value: SidebarContextType = {
    isOpen,
    isCollapsed,
    toggleSidebar,
    toggleCollapse,
    closeMobileSidebar,
    setIsOpen,
    toggle,
  };

  return (
    <SidebarContext.Provider value={value}>
      {children}
    </SidebarContext.Provider>
  );
}

// Enterprise hook - use this in components
export const useSidebarContext = () => {
  const context = useContext(SidebarContext);
  if (context === undefined) {
    throw new Error('useSidebarContext must be used within a SidebarProvider');
  }
  return context;
};

// Convenience alias - matches @/hooks/useSidebar
export const useSidebar = useSidebarContext;

export default SidebarContext;
