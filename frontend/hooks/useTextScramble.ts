'use client';

import { useEffect, useRef, useCallback } from 'react';

const CHARS = '!<>-_/[]{}—=+*^?#';

class Scrambler {
  private el: HTMLElement;
  private chars: string = CHARS;
  private frame: number = 0;
  private queue: Array<{ from: string; to: string; start: number; end: number; char?: string }> = [];
  private frameId: number = 0;
  private resolve: () => void = () => {};

  constructor(el: HTMLElement) {
    this.el = el;
    this.update = this.update.bind(this);
  }

  setText(newText: string): Promise<void> {
    const oldText = this.el.innerText;
    const length = Math.max(oldText.length, newText.length);
    const promise = new Promise<void>((resolve) => (this.resolve = resolve));
    
    this.queue = [];
    for (let i = 0; i < length; i++) {
      const from = oldText[i] || '';
      const to = newText[i] || '';
      const start = Math.floor(Math.random() * 40);
      const end = start + Math.floor(Math.random() * 40);
      this.queue.push({ from, to, start, end });
    }
    
    cancelAnimationFrame(this.frameId);
    this.frame = 0;
    this.update();
    return promise;
  }

  private update() {
    let output = '';
    let complete = 0;
    
    for (let i = 0, n = this.queue.length; i < n; i++) {
      let { from, to, start, end, char } = this.queue[i];
      
      if (this.frame >= end) {
        complete++;
        output += to;
      } else if (this.frame >= start) {
        if (!char || Math.random() < 0.28) {
          char = this.chars[Math.floor(Math.random() * this.chars.length)];
          this.queue[i].char = char;
        }
        output += `<span class="opacity-50 text-nexora-green">${char}</span>`;
      } else {
        output += from;
      }
    }
    
    this.el.innerHTML = output;
    
    if (complete === this.queue.length) {
      this.resolve();
    } else {
      this.frameId = requestAnimationFrame(this.update);
      this.frame++;
    }
  }
}

export function useTextScramble(text: string) {
  const elementRef = useRef<HTMLElement>(null);
  const scramblerRef = useRef<Scrambler | null>(null);

  useEffect(() => {
    if (elementRef.current && !scramblerRef.current) {
      scramblerRef.current = new Scrambler(elementRef.current);
    }
  }, []);

  useEffect(() => {
    if (scramblerRef.current) {
      scramblerRef.current.setText(text);
    }
  }, [text]);

  return elementRef;
}
