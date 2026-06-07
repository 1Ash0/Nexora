'use client';

import React, { useState, useEffect } from 'react';
import { useResearchStore } from '../../store/research';

/**
 * DashboardShell Component
 * 
 * Provides the persistent terminal-style layout for the Nexora interface.
 * Implements: 
 * - Matrix-inspired technical telemetry
 * - Global scanline and flicker overlays
 * - Client-side only random initialization for hydration safety
 */
export function DashboardShell({ children }: { children: React.ReactNode }) {
  const status = useResearchStore((state) => state.status);
  const [mounted, setMounted] = useState(false);
  const [glitchText, setGlitchText] = useState('');
  const [memValue, setMemValue] = useState('0.0');

  useEffect(() => {
    setMounted(true);
    // Initialize random elements only on client
    const chars = '0123456789ABCDEF';
    const text = Array(4).fill(0).map(() => chars[Math.floor(Math.random() * chars.length)]).join('');
    setGlitchText(text);
    setMemValue((Math.random() * 10 + 42).toFixed(1));
  }, []);

  return (
    <div className="min-h-screen bg-void text-terminal-green font-mono selection:bg-terminal-green/30 flex flex-col relative overflow-hidden">
      {/* Matrix Background Effect */}
      <div className="fixed inset-0 pointer-events-none opacity-[0.03]">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_4px,3px_100%]" />
      </div>

      {/* Top Header/Telemetry */}
      <header className="border-b border-terminal-green/20 bg-void/80 backdrop-blur-md z-10 sticky top-0">
        <div className="max-w-[1800px] mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-lg font-bold tracking-tighter flex items-center gap-2 text-terminal-green">
              <span className="w-2 h-2 bg-terminal-green animate-pulse" />
              NEXORA_V1.1.2
            </h1>
            <div className="h-4 w-px bg-terminal-green/20" />
            <div className="flex gap-4 text-[10px] text-terminal-green/60 uppercase tracking-widest">
              <span className="flex items-center gap-1.5">
                <span className="opacity-40">[SYS]</span> 
                {mounted ? 'STABLE' : 'BOOTING'}
              </span>
              <span className="flex items-center gap-1.5">
                <span className="opacity-40">[MEM]</span> 
                {mounted ? `${memValue}GB/128GB` : '---'}
              </span>
              <span className="flex items-center gap-1.5">
                <span className="opacity-40">[LOC]</span> 
                {mounted ? 'US_EAST_1' : '---'}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2 px-3 py-1 bg-terminal-green/5 border border-terminal-green/10 rounded">
              <span className={`w-1.5 h-1.5 rounded-full ${
                status === 'idle' ? 'bg-terminal-green/20' :
                status === 'planning' || status === 'executing' || status === 'synthesizing' ? 'bg-terminal-green animate-pulse' :
                status === 'done' ? 'bg-indigo-500' : 
                status === 'error' || status === 'failed' ? 'bg-red-500' : 'bg-terminal-green/20'
              }`} />
              <span className="text-[10px] font-bold uppercase tracking-wider text-terminal-green">
                System_{status}
              </span>
            </div>
            <div className="text-[10px] opacity-40 font-bold text-terminal-green">
              TX_{mounted ? glitchText : '0000'}
            </div>
          </div>
        </div>
      </header>

      {/* Main Grid Content */}
      <main className="flex-1 max-w-[1800px] w-full mx-auto p-6 grid grid-rows-[1fr_auto] gap-6 relative z-0">
        {children}
      </main>

      {/* Footer System Telemetry */}
      <footer className="border-t border-terminal-green/10 bg-void/80 backdrop-blur-md px-6 h-10 flex items-center justify-between text-[10px] text-terminal-green/40 uppercase tracking-widest">
        <div className="flex gap-6">
          <span>SEC_MODE: ENCRYPTED</span>
          <span>LATENCY: {mounted ? `${(Math.random() * 20 + 10).toFixed(0)}MS` : '---'}</span>
        </div>
        <div className="flex gap-6">
          <span>FRAME_STABILITY: 100%</span>
          <span>BUILD: {mounted ? 'PRODUCTION_STABLE' : 'INITIALIZING'}</span>
        </div>
      </footer>

      {/* Global Terminal Overlay Effects */}
      <div className="fixed inset-0 pointer-events-none z-50 overflow-hidden">
        {/* CRT Scanline effect */}
        <div className="absolute inset-0 grayscale opacity-[0.02] mix-blend-overlay animate-scanline pointer-events-none" 
             style={{ background: 'linear-gradient(to bottom, transparent 50%, black 50%)', backgroundSize: '100% 4px' }} />
      </div>
    </div>
  );
}
