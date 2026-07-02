import React from 'react';
import Loader from '@/components/feedback/Loader';

export default function GlobalLoadingPage() {
  return (
    <div className="w-screen h-screen bg-industrial-bg flex items-center justify-center">
      <Loader />
    </div>
  );
}
