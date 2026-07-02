'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import clsx from 'clsx';
import { useSidebar } from '@/hooks/useSidebar';
import {
  LayoutDashboard,
  Layers,
  AlertTriangle,
  TrendingUp,
  Network,
  MessageSquare,
  Settings,
  User,
} from 'lucide-react';

const routes = [
  { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  { name: 'Assets', path: '/assets', icon: Layers },
  { name: 'Alerts', path: '/alerts', icon: AlertTriangle },
  { name: 'Predictions', path: '/predictions', icon: TrendingUp },
  { name: 'Knowledge Graph', path: '/knowledge', icon: Network },
  { name: 'Co-Pilot Chat', path: '/chat', icon: MessageSquare },
  { name: 'Settings', path: '/settings', icon: Settings },
  { name: 'Profile', path: '/profile', icon: User },
];

export function Sidebar() {
  const { isOpen } = useSidebar();
  const pathname = usePathname();

  return (
    <aside
      className={clsx(
        'h-screen border-r border-industrial-border bg-industrial-surface flex flex-col transition-all duration-300 shrink-0 select-none',
        isOpen ? 'w-64' : 'w-0 -translate-x-full lg:w-16 lg:translate-x-0'
      )}
    >
      <div className="h-14 flex items-center px-4 border-b border-industrial-border">
        {isOpen ? (
          <span className="text-sm font-semibold tracking-wide text-industrial-blue">OPERATIONAL SATELLITE</span>
        ) : (
          <div className="w-2 h-2 rounded-full bg-industrial-blue mx-auto" />
        )}
      </div>
      <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
        {routes.map((route) => {
          const Icon = route.icon;
          const isActive = pathname === route.path;
          return (
            <Link
              key={route.path}
              href={route.path}
              className={clsx(
                'flex items-center gap-3 px-3 py-2 rounded text-sm transition-all duration-150 group',
                isActive
                  ? 'bg-industrial-blue text-white font-medium'
                  : 'text-industrial-slate hover:bg-gray-800 hover:text-white'
              )}
            >
              <Icon
                className={clsx(
                  'w-5 h-5 shrink-0',
                  isActive ? 'text-white' : 'text-industrial-slate group-hover:text-white'
                )}
              />
              {isOpen && <span className="truncate">{route.name}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

export default Sidebar;
