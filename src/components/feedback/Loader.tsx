'use client';

import React from 'react';
import CircularProgress from '@mui/material/CircularProgress';

export interface LoaderProps {
  /** Optional status copy for route-level or panel-level loading states. */
  text?: string;
  /** Maintains compatibility with existing imports that passed a Loader size. */
  size?: 'sm' | 'md' | 'lg';
}

const loaderSizeMap: Record<NonNullable<LoaderProps['size']>, number> = {
  sm: 24,
  md: 32,
  lg: 40,
};

export default function Loader({
  text = 'POLLING PLATFORM EDGE DATASTREAM...',
  size = 'md',
}: LoaderProps) {
  return (
    <div className="w-full h-48 flex items-center justify-center bg-transparent">
      <div className="flex flex-col items-center gap-3">
        <CircularProgress
          size={loaderSizeMap[size]}
          thickness={4.5}
          className="text-industrial-blue"
        />
        <span className="text-xs font-mono tracking-widest text-industrial-slate animate-pulse text-center">
          {text}
        </span>
      </div>
    </div>
  );
}

export { Loader };
