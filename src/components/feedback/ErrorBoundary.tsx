'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import Typography from '@/components/ui/Typography';

interface Props {
  children?: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Critical Platform Runtime Interception:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="p-6 m-4 bg-red-950/20 border border-red-900 rounded-md text-red-200 font-mono space-y-2">
          <Typography variant="h6" className="text-red-400 font-bold">
            CRITICAL ENGINE INTERRUPTION
          </Typography>
          <p className="text-xs max-w-2xl overflow-x-auto">
            {this.state.error?.toString() || 'Execution context mapping failure.'}
          </p>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
