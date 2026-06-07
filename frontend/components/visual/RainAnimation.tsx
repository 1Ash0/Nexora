'use client';

import React, { useRef, useEffect } from 'react';
import { NEXORA_TOKENS } from '../../lib/design-tokens';

const CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ!<>-_/[]{}—=+*^?#';

export const RainAnimation: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    // Rain character objects
    const charCount = 300;
    const chars: { x: number; y: number; char: string; speed: number; highlight: boolean }[] = [];

    const createChar = () => ({
      x: Math.random() * width,
      y: Math.random() * -height,
      char: CHARS[Math.floor(Math.random() * CHARS.length)],
      speed: 1 + Math.random() * 3,
      highlight: Math.random() < 0.05 // 5% chance of being green glow as per user directive
    });

    for (let i = 0; i < charCount; i++) {
      chars.push(createChar());
    }

    const draw = () => {
      // Clear with slight trail effect
      ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
      ctx.fillRect(0, 0, width, height);

      ctx.font = `14px ${NEXORA_TOKENS.typography.mono}`;

      chars.forEach((c) => {
        if (c.highlight) {
          ctx.fillStyle = NEXORA_TOKENS.colors.green;
          ctx.shadowBlur = 10;
          ctx.shadowColor = NEXORA_TOKENS.colors.green;
          ctx.fillText(c.char, c.x, c.y);
          // Scale effect simulation via font size
          ctx.font = `18px ${NEXORA_TOKENS.typography.mono}`;
          ctx.fillText(c.char, c.x, c.y);
          ctx.font = `14px ${NEXORA_TOKENS.typography.mono}`;
          ctx.shadowBlur = 0;
        } else {
          ctx.fillStyle = 'rgba(255, 255, 255, 0.05)'; // Muted white for background
          ctx.fillText(c.char, c.x, c.y);
        }

        c.y += c.speed;
        
        // Randomly update character while falling
        if (Math.random() < 0.02) {
          c.char = CHARS[Math.floor(Math.random() * CHARS.length)];
        }

        if (c.y > height) {
          c.y = -20;
          c.x = Math.random() * width;
        }
      });

      requestAnimationFrame(draw);
    };

    const handleResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };

    window.addEventListener('resize', handleResize);
    draw();

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      style={{ background: 'black' }}
    />
  );
};
