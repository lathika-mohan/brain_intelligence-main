'use client';

import React from 'react';
import clsx from 'clsx';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function Card({ className, children, ...props }: CardProps) {
  return (
    <div
      className={clsx('bg-industrial-surface border border-industrial-border rounded-md p-4 shadow-md', className)}
      {...props}
    >
      {children}
    </div>
  );
}

export default Card;
