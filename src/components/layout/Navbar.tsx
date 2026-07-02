'use client';

import React from 'react';
import { Menu } from 'lucide-react';
import { useSidebar } from '@/hooks/useSidebar';
import Logo from '@/components/ui/Logo';

export function Navbar() {
  const { toggle } = useSidebar();

  return (
    <header className="h-14 border-b border-industrial-border bg-industrial-surface px-4 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-4">
        <button
          onClick={toggle}
          className="p-1.5 text-industrial-slate hover:text-white hover:bg-gray-800 rounded transition-colors"
          aria-label="Toggle Sidebar Navigation"
        >
          <Menu className="w-5 h-5" />
        </button>
        <Logo />
      </div>
      <div className="flex items-center gap-3">
        <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
        <span className="text-xs font-mono text-industrial-slate">NODE_01_SYNCHRONIZED</span>
      </div>
    </header>
  );
}

export default Navbar;
