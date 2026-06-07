'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { ResearchSource } from '../lib/types';

function getDomain(url: string): string {
  try { return new URL(url).hostname.replace('www.', ''); }
  catch { return url.slice(0, 30); }
}

export const SourcesPanel: React.FC<{ sources: ResearchSource[] }> = ({ sources }) => {
  if (sources.length === 0) {
    return (
      <div className="h-full flex items-center justify-center bg-[#0D1120]">
        <p className="text-[#4D5B7A] text-[12px] animate-pulse">Searching the web…</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-[#0D1120]">
      <div className="px-4 py-2.5 border-b border-white/[0.05] shrink-0 flex items-center justify-between">
        <span className="text-[11px] font-mono text-[#4D5B7A] tracking-wider">Sources indexed</span>
        <span className="text-[11px] font-mono text-[#10E8A0] tabular-nums">{sources.length}</span>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2.5 space-y-1.5" style={{ scrollbarWidth: 'thin' }}>
        {sources.map((src, i) => {
          const domain = getDomain(src.url);
          const hue    = domain.split('').reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
          return (
            <motion.a
              key={src.url + i}
              href={src.url}
              target="_blank"
              rel="noopener noreferrer"
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.18, delay: i * 0.04 }}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12] hover:bg-white/[0.04] transition-all group"
            >
              <div
                className="w-7 h-7 rounded-lg shrink-0 flex items-center justify-center text-[11px] font-bold uppercase"
                style={{
                  background: `hsla(${hue},50%,30%,0.4)`,
                  border: `1px solid hsla(${hue},50%,50%,0.25)`,
                  color: `hsla(${hue},55%,65%,0.9)`,
                }}
              >
                {domain.charAt(0)}
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-[12px] text-[#9BA3BE] group-hover:text-[#EEF2FF] transition-colors truncate leading-snug">
                  {src.title || domain}
                </p>
                <p className="text-[10px] font-mono text-[#4D5B7A] truncate mt-0.5">{domain}</p>
                {src.snippet && (
                  <p className="text-[11px] text-[#4D5B7A]/70 mt-1 leading-snug line-clamp-1">{src.snippet}</p>
                )}
              </div>

              <svg className="w-3.5 h-3.5 text-[#4D5B7A] group-hover:text-[#9BA3BE] transition-colors shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" />
              </svg>
            </motion.a>
          );
        })}
      </div>
    </div>
  );
};
