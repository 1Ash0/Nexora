'use client';

import React from 'react';
import Link from 'next/link';
import { ResearchStage } from '../lib/types';

interface NexoraShellProps {
  children: React.ReactNode;
  sessionId?: string;
  query?: string;
  stage?: ResearchStage;
  onInterrupt?: () => void;
}

const STAGE_STEPS: { key: ResearchStage; label: string }[] = [
  { key: 'planning',     label: 'Plan'       },
  { key: 'executing',    label: 'Research'   },
  { key: 'analyzing',    label: 'Analyze'    },
  { key: 'synthesizing', label: 'Synthesize' },
  { key: 'done',         label: 'Done'       },
];

const STAGE_ORDER: Record<ResearchStage, number> = {
  idle: -1, planning: 0, executing: 1, analyzing: 2, synthesizing: 3, done: 4, error: 99,
};

function StagePipeline({ stage }: { stage: ResearchStage }) {
  const current = STAGE_ORDER[stage] ?? -1;
  return (
    <div className="hidden md:flex items-center gap-1">
      {STAGE_STEPS.map(({ key, label }, i) => {
        const idx    = STAGE_ORDER[key];
        const done   = idx < current;
        const active = idx === current;
        return (
          <React.Fragment key={key}>
            {i > 0 && (
              <div className="w-4 h-px mx-0.5" style={{ background: done ? 'rgba(16,232,160,0.4)' : 'rgba(255,255,255,0.07)' }} />
            )}
            <div
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium transition-all"
              style={
                active
                  ? { background: 'rgba(16,232,160,0.10)', border: '1px solid rgba(16,232,160,0.25)', color: '#10E8A0' }
                  : done
                    ? { color: 'rgba(16,232,160,0.50)' }
                    : { color: '#4D5B7A', opacity: 0.6 }
              }
            >
              {active && <span className="w-1.5 h-1.5 rounded-full bg-[#10E8A0] animate-[pulse-dot_2s_ease-in-out_infinite]" />}
              {done && (
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              )}
              {label}
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}

export function NexoraShell({ children, sessionId, query, stage = 'idle', onInterrupt }: NexoraShellProps) {
  const hasSession = !!sessionId;
  const isLive = hasSession && stage !== 'idle' && stage !== 'done' && stage !== 'error';

  return (
    <div className="bg-[#070A12] min-h-screen flex flex-col overflow-hidden text-[#EEF2FF]" style={{ fontFamily: 'var(--font-inter)' }}>
      {/* Header */}
      <header className="h-12 shrink-0 border-b border-white/[0.05] bg-[rgba(7,10,18,0.90)] backdrop-blur-md sticky top-0 z-50 flex items-center px-5 gap-4">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 group shrink-0">
          <div className="w-6 h-6 rounded-md bg-[#10E8A0] flex items-center justify-center shadow-[0_0_12px_rgba(16,232,160,0.35)] group-hover:shadow-[0_0_18px_rgba(16,232,160,0.50)] transition-shadow">
            <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
              <path d="M8 2L14 5V11L8 14L2 11V5L8 2Z" stroke="#040C16" strokeWidth="1.5" strokeLinejoin="round"/>
              <circle cx="8" cy="8" r="2" fill="#040C16"/>
            </svg>
          </div>
          <span className="text-[14px] font-bold tracking-tight text-[#EEF2FF] group-hover:text-[#10E8A0] transition-colors" style={{ fontFamily: 'var(--font-syne)' }}>
            Nexora
          </span>
        </Link>

        {hasSession && (
          <>
            <div className="w-px h-4 bg-white/[0.07] shrink-0" />
            {query && (
              <span className="text-[12px] text-[#9BA3BE] truncate max-w-[260px] hidden lg:block">
                {query}
              </span>
            )}
            <div className="flex-1" />
            <StagePipeline stage={stage} />
            <div className="w-px h-4 bg-white/[0.07] shrink-0 ml-2" />
            <span className="text-[10px] font-mono text-[#4D5B7A] shrink-0">
              {sessionId.slice(0, 8)}
            </span>
            {isLive && (
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10E8A0] animate-[pulse-dot_2s_ease-in-out_infinite]" />
                <span className="text-[10px] font-mono text-[#10E8A0]">Live</span>
              </div>
            )}
            {onInterrupt && isLive && (
              <button
                onClick={onInterrupt}
                className="shrink-0 px-3 py-1 text-[11px] rounded border border-[rgba(255,64,64,0.25)] text-[#FF4040]/70 hover:bg-[rgba(255,64,64,0.08)] hover:text-[#FF4040] transition-all"
              >
                Abort
              </button>
            )}
          </>
        )}
        {!hasSession && <div className="flex-1" />}
      </header>

      {/* Content */}
      <main className="flex-1 overflow-hidden relative">{children}</main>
    </div>
  );
}
