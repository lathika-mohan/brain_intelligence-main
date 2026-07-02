import React from 'react';
import Link from 'next/link';
import Typography from '@/components/ui/Typography';

export default function NotFoundPage() {
  return (
    <div className="w-screen h-screen bg-industrial-bg flex flex-col items-center justify-center space-y-4 font-mono text-center px-4">
      <Typography variant="h3" className="text-industrial-blue font-bold tracking-tight">
        404 // NODE_NOT_FOUND
      </Typography>
      <Typography variant="body2" className="text-industrial-slate max-w-md">
        The requested system address space does not point to an active, registered platform execution layout.
      </Typography>
      <Link
        href="/dashboard"
        className="px-4 py-2 border border-industrial-blue text-industrial-blue text-xs rounded hover:bg-industrial-blue/10 transition-colors"
      >
        RETURN TO CENTRAL CONTROL HUB
      </Link>
    </div>
  );
}
