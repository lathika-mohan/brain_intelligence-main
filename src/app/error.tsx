'use client';

import React, { useEffect } from 'react';
import Typography from '@/components/ui/Typography';

export default function RootErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('System Thread Exception Stack:', error);
  }, [error]);

  return (
    <div className="p-8 bg-red-950/20 border border-red-900 rounded-lg max-w-3xl mx-auto my-12 font-mono space-y-4">
      <Typography variant="h5" className="text-red-400 font-bold">
        CORE RENDER THREAD ABORTED
      </Typography>
      <div className="p-3 bg-black/40 rounded border border-red-950 text-xs text-red-400 overflow-x-auto">
        {error.message || 'Unknown Structural Boundary Exception.'}
      </div>
      <button
        onClick={() => reset()}
        className="px-4 py-2 bg-red-900 text-white text-xs font-semibold rounded hover:bg-red-800 transition-colors"
      >
        RE-INITIALIZE RENDER THREAD
      </button>
    </div>
  );
}
