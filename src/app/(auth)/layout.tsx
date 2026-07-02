import React from 'react';
import { Container } from '@/components/ui/Container';

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-industrial-bg text-gray-100">
      <Container className="max-w-sm">
        <div className="w-full bg-industrial-surface border border-industrial-border p-8 rounded-lg shadow-xl">
          {children}
        </div>
      </Container>
    </div>
  );
}
