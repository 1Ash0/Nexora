import { create } from 'zustand';
import {
  AgentEvent,
  ResearchTask,
  ResearchSource,
  GraphNode,
  GraphEdge,
  Contradiction,
  SynthesisMetadata,
  BackendEvent,
  ResearchState,
  ResearchStage,
} from '../lib/types';

interface ResearchActions {
  processBackendEvent: (raw: BackendEvent) => void;
  startSession: (query: string) => Promise<void>;
  interrupt: (reason?: string) => Promise<void>;
  resume: (feedback?: string, action?: string) => Promise<void>;
  reset: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080/api/v1';

function stageFromStatus(status: string, action: string): ResearchStage {
  const a = action.toLowerCase();
  if (a.includes('plan') || status === 'thinking') return 'planning';
  if (a.includes('execut') || a.includes('task') || a.includes('search')) return 'executing';
  if (a.includes('contradict') || a.includes('critic') || a.includes('analyz')) return 'analyzing';
  if (a.includes('synth')) return 'synthesizing';
  return 'executing';
}

const initialState: ResearchState = {
  sessionId: '',
  query: '',
  depth: 'standard',
  stage: 'idle',
  status: 'idle',
  events: [],
  tasks: [],
  sources: [],
  nodes: [],
  edges: [],
  contradictions: [],
  synthesis: '',
  metadata: null,
  refinedQuery: '',
  followUpQuestions: [],
  orderedSources: [],
  isHITLOpen: false,
  hitlReason: '',
  hitlSummary: '',
  startedAt: null,
  completedAt: null,
};

export const useResearchStore = create<ResearchState & ResearchActions>((set, get) => ({
  ...initialState,

  processBackendEvent: (raw: BackendEvent) => {
    const type = raw.type || 'agent_step';
    const payload = raw.payload || {};

    if (type === 'refined_query') {
      set({ refinedQuery: (payload.refined_query as string) || '' });
      return;
    }

    if (type === 'synthesis_complete') {
      const report = (payload.report as string) || '';
      const meta = (payload.metadata as SynthesisMetadata) || null;
      const fup = (payload.follow_up_questions as string[]) || (meta as Record<string,unknown>)?.follow_up_questions as string[] || [];
      const orderedSources = (payload.ordered_sources as { url: string; title: string }[]) || [];
      const now = Date.now();
      set({
        synthesis: report,
        stage: 'done',
        status: 'done',
        metadata: meta,
        followUpQuestions: fup,
        orderedSources,
        completedAt: now,
      });
      // Persist to session history in localStorage
      try {
        const state = get();
        const cs = meta?.confidence_summary ?? '';
        const confidence = /high/i.test(cs) ? 0.85 : /medium/i.test(cs) ? 0.65 : 0.45;
        const record = {
          id: state.sessionId || `s_${now}`,
          query: state.query || '',
          completedAt: now,
          wordCount: (meta as Record<string,unknown>)?.word_count as number ?? 0,
          sourceCount: (meta as Record<string,unknown>)?.source_count as number ?? 0,
          confidence,
          synthesisPreview: report.replace(/^#+\s+/gm, '').slice(0, 160) + '…',
        };
        const raw = localStorage.getItem('nexora_session_history');
        const history = raw ? JSON.parse(raw) : [];
        const updated = [record, ...history.filter((r: {id:string}) => r.id !== record.id)].slice(0, 20);
        localStorage.setItem('nexora_session_history', JSON.stringify(updated));
      } catch {}
      return;
    }

    if (type === 'done') {
      // Final sentinel — nothing to render, just ensure stage stays 'done'
      set((s) => ({ stage: s.stage === 'done' ? 'done' : s.stage }));
      return;
    }

    if (type === 'error') {
      set({ stage: 'error', status: 'error', hitlSummary: raw.action });
      return;
    }

    if (type === 'task_update') {
      const taskData = payload.task as { id: string; description: string; status: string; result?: string };
      if (taskData) {
        set((state) => {
          const existing = state.tasks.find((t) => t.id === taskData.id);
          if (existing) {
            return {
              tasks: state.tasks.map((t) =>
                t.id === taskData.id ? { ...t, status: taskData.status as ResearchTask['status'], result: taskData.result } : t
              ),
            };
          }
          return {
            tasks: [...state.tasks, {
              id: taskData.id,
              description: taskData.description,
              status: taskData.status as ResearchTask['status'],
              result: taskData.result,
            }],
          };
        });
      }
      // Also log as agent event
    }

    if (type === 'sources_found') {
      const newSources = (payload.sources as ResearchSource[]) || [];
      set((state) => {
        const existingUrls = new Set(state.sources.map((s) => s.url));
        const added = newSources.filter((s) => !existingUrls.has(s.url));
        return { sources: [...state.sources, ...added] };
      });
    }

    // Always add to event log
    if (type !== 'heartbeat') {
      const event: AgentEvent = {
        id: `${raw.id ?? Date.now()}-${Math.random()}`,
        agent: raw.agent,
        action: raw.action,
        status: raw.status as AgentEvent['status'],
        timestamp: raw.timestamp || new Date().toISOString(),
        payload: payload,
      };

      set((state) => {
        const newStage = state.stage === 'done' ? 'done' : stageFromStatus(raw.status, raw.action);
        return {
          events: [...state.events, event],
          stage: newStage,
          status: raw.status as AgentEvent['status'],
        };
      });
    }
  },

  startSession: async (query: string) => {
    const depth = get().depth || 'standard';
    set({ ...initialState, query, depth, stage: 'planning', startedAt: Date.now() });
    try {
      const res = await fetch(`${API_BASE}/research/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, depth }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      set({ sessionId: data.session_id });
    } catch (err) {
      set({ stage: 'error', status: 'error', hitlSummary: (err as Error).message });
      throw err;
    }
  },

  interrupt: async (reason = 'USER_ABORTED') => {
    const { sessionId } = get();
    if (!sessionId) return;
    await fetch(`${API_BASE}/research/interrupt/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    }).catch(() => {});
  },

  resume: async (feedback = '', action = 'continue') => {
    const { sessionId } = get();
    if (!sessionId) return;
    set({ isHITLOpen: false });
    await fetch(`${API_BASE}/research/resume/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feedback, action }),
    }).catch(() => {});
  },

  reset: () => set(initialState),
}));
