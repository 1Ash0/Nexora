'use client';

import React from 'react';

export const DotGrid: React.FC = () => {
  return (
    <div 
      className="fixed inset-0 opacity-[0.03] pointer-events-none z-[-1]"
      style={{
        backgroundImage: 'radial-gradient(circle, white 1px, transparent 1px)',
        backgroundSize: '24px 24px',
      }}
    />
  );
};
