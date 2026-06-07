'use client';

import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AgentEvent } from '../../lib/types';

interface AgentTerminalProps {
  events: AgentEvent[];
  className?: string;
}

const LogEntry = ({ event }: { event: AgentEvent }) => {
  const isError = event.status === 'failed';
  const isDone = event.status === 'done';
  const isExecuting = event.status === 'executing';
  
  const getIcon = () => {
    if (isError) return '!!';
    if (isDone) return '>>';
    if (isExecuting) return '..';
    return '--';
  };

  const getTextColor = () => {
    if (isError) return 'text-nexora-red';
    if (isDone) return 'text-nexora-green';
    if (isExecuting) return 'text-nexora-indigo';
    return 'text-nexora-text-muted';
  };

  const getAgentTag = () => {
    return event.agent.toUpperCase().substring(0, 4);
  };

  return (
    <motion.div
      initial={{ x: -16, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={`font-mono text-[11px] leading-5 py-0.5 border-l-2 pl-3 mb-1 border-opacity-20 ${
        isError ? 'border-nexora-red bg-nexora-red/5' : 
        isExecuting ? 'border-nexora-indigo bg-nexora-indigo/5' : 
        'border-nexora-border-subtle'
      }`}
    >
      <div className="flex gap-3">
        <span className={`opacity-40 tabular-nums shrink-0 text-[10px]`}>
          {new Date(event.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </span>
        <span className="text-nexora-text-muted shrink-0 opacity-60">[{getAgentTag()}]</span>
        <span className={`${getTextColor()} font-bold shrink-0`}>{getIcon()}</span>
        <span className="flex-1 break-all text-nexora-text-primary">
          {event.action.toUpperCase()}
        </span>
      </div>
      
      {event.payload && Object.keys(event.payload).length > 0 && (
        <div className="ml-10 mt-1 flex flex-wrap gap-x-4 gap-y-1 opacity-50 text-[10px] uppercase">
          {Object.entries(event.payload).slice(0, 3).map(([key, value]) => (
            <span key={key}>{key}: {String(value).substring(0, 20)}</span>
          ))}
          {(event.duration_ms ?? 0) > 0 && <span>DUR: {event.duration_ms}MS</span>}
        </div>
      )}
    </motion.div>
  );
};

export const AgentTerminal: React.FC<AgentTerminalProps> = ({ events, className = "" }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className={`flex flex-col h-full bg-nexora-surface-1 border border-nexora-border-subtle overflow-hidden terminal-surface corner-accent ${className}`}>
      {/* Terminal Header */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-nexora-surface-2 border-b border-nexora-border-subtle">
        <div className="flex items-center gap-2">
          <div className={`w-1.5 h-1.5 rounded-full status-dot ${events.length > 0 ? 'active' : 'neutral'}`} />
          <span className="text-[10px] font-bold tracking-widest text-nexora-text-secondary uppercase">
            AGENT_LOG_STREAM
          </span>
        </div>
        <div className="text-[9px] text-nexora-text-muted tabular-nums uppercase tracking-tighter">
          SECURE_ENCRYPTED_PATH
        </div>
      </div>

      {/* Log Container */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-3 scrollbar-none hover:scrollbar-thin scrollbar-thumb-nexora-border-mid scrollbar-track-transparent"
      >
        <AnimatePresence initial={false}>
          {events.length === 0 ? (
            <div className="h-full flex items-center justify-center text-nexora-text-muted text-[10px] uppercase tracking-widest animate-pulse">
              [ NO_ACTIVE_SESSION_DETECTED ]
            </div>
          ) : (
            events.map((event, idx) => (
              <LogEntry key={`${event.id}-${idx}`} event={event} />
            ))
          )}
        </AnimatePresence>
      </div>

      {/* Terminal Footer */}
      <div className="px-3 py-1 bg-nexora-black border-t border-nexora-border-subtle flex justify-between items-center">
        <div className="text-[9px] text-nexora-text-muted uppercase tabular-nums">
          TICKS: {events.length} | DEPTH: 100%
        </div>
        <div className="flex gap-2">
          <div className="w-1 h-3 bg-nexora-green animate-pulse" />
          <div className="w-1 h-3 bg-nexora-green/60 animate-pulse delay-75" />
          <div className="w-1 h-3 bg-nexora-green/30 animate-pulse delay-150" />
        </div>
      </div>
    </div>
  );
};
