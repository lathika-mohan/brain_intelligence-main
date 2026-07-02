'use client';

import React from 'react';
import { Button as MuiButton, ButtonProps as MuiButtonProps } from '@mui/material';
import clsx from 'clsx';

export type ButtonProps = MuiButtonProps;

export function Button({ className, children, ...props }: ButtonProps) {
  return (
    <MuiButton className={clsx('font-medium shadow-sm', className)} {...props}>
      {children}
    </MuiButton>
  );
}

export default Button;
