'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { ResearchTask } from '../lib/types';

const STATUS_CONFIG: Record<string, { label: string; dotClass: string; textColor: string; bg: string; border: string }> = {
  pending: { label: 'Queued',  dotClass: 'bg-[#4D5B7A] opacity-40',                              textColor: '#4D5B7A',  bg: '',                         border: 'border-white/[0.06]' },
  running: { label: 'Running', dotClass: 'bg-[#10E8A0] animate-[pulse-dot_2s_ease-in-out_infinite]', textColor: '#10E8A0', bg: 'bg-[rgba(16,232,160,0.06)]', border: 'border-[rgba(16,232,160,0.22)]' },
  done:    { label: 'Done',    dotClass: 'bg-[#10E8A0]',                                           textColor: '#10E8A0',  bg: 'bg-[rgba(16,232,160,0.04)]', border: 'border-[rgba(16,232,160,0.15)]' },
  failed:  { label: 'Failed',  dotClass: 'bg-[#FF4040]',                                           textColor: '#FF4040',  bg: 'bg-[rgba(255,64,64,0.06)]',  border: 'border-[rgba(255,64,64,0.22)]' },
};

export const TasksPanel: React.FC<{ tasks: ResearchTask[] }> = ({ tasks }) => {
  if (tasks.length === 0) {
    return (
      <div className="h-full flex items-center justify-center bg-[#0D1120]">
        <p className="text-[#4D5B7A] text-[12px] animate-pulse">Awaiting plan…</p>
      </div>
    );
  }

  const done  = tasks.filter(t => t.status === 'done').length;
  const total = tasks.length;
  const pct   = total > 0 ? (done / total) * 100 : 0;

  return (
    <div className="h-full flex flex-col bg-[#0D1120]">
      {/* Progress header */}
      <div className="px-4 py-3 border-b border-white/[0.05] shrink-0">
        <div className="flex justify-between items-center text-[11px] mb-2">
          <span className="text-[#4D5B7A] font-mono tracking-wider">Progress</span>
          <span className="font-mono text-[#9BA3BE] tabular-nums">{done}/{total}</span>
        </div>
        <div className="h-[3px] bg-white/[0.05] rounded-full overflow-hidden">
          <motion.div
            className="h-full rounded-full"
            style={{ background: 'linear-gradient(90deg, #10E8A0, #7C5CFC)' }}
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.6, ease: [0.16,1,0.3,1] }}
          />
        </div>
      </div>

      {/* Tasks */}
      <div className="flex-1 overflow-y-auto px-3 py-2.5 space-y-2" style={{ scrollbarWidth: 'thin' }}>
        {tasks.map((task, i) => {
          const cfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
          return (
            <motion.div
              key={task.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: i * 0.05 }}
              className={`rounded-lg border px-3 py-2.5 transition-all ${cfg.bg} ${cfg.border}`}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${cfg.dotClass}`} />
                <span className="text-[10px] font-medium font-mono" style={{ color: cfg.textColor }}>{cfg.label}</span>
                <span className="ml-auto text-[9px] font-mono text-[#4D5B7A]/60">#{i + 1}</span>
              </div>
              <p className="text-[13px] text-[#C0CAEC] leading-snug">{task.description}</p>
              {task.result && (
                <p className="mt-2 text-[11px] text-[#4D5B7A] leading-snug line-clamp-2 pl-3 border-l-2 border-white/[0.06]">
                  {task.result}
                </p>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};
