'use client';

import React from 'react';
import { Container as MuiContainer, ContainerProps as MuiContainerProps } from '@mui/material';

export type ContainerProps = MuiContainerProps;

export function Container({ children, ...props }: ContainerProps) {
  return <MuiContainer {...props}>{children}</MuiContainer>;
}

export default Container;
