'use client';

import React, { useState, useEffect, useRef } from 'react';

interface TextScrambleProps {
  text: string;
  duration?: number; // in frames (as per DESIGN.md: 40)
  className?: string;
  as?: React.ElementType;
}

const CHARS = '!<>-_/[]{}—=+*^?#';

export const TextScramble: React.FC<TextScrambleProps> = ({ 
  text, 
  duration = 40, 
  className = "",
  as: Component = "span" 
}) => {
  const [displayText, setDisplayText] = useState(text);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const _frameRef = useRef(0);
  const animationRef = useRef<number | null>(null);

  useEffect(() => {
    let frame = 0;
    const targetText = text;
    const length = targetText.length;
    
    const scramble = () => {
      frame++;
      
      const nextText = targetText.split('').map((char, index) => {
        if (char === ' ') return ' ';
        
        // Progress for this specific character
        const charProgress = (frame / duration) * length;
        
        if (index < charProgress) {
          return char;
        }
        
        return CHARS[Math.floor(Math.random() * CHARS.length)];
      }).join('');

      setDisplayText(nextText);

      if (frame < duration) {
        animationRef.current = requestAnimationFrame(scramble);
      } else {
        setDisplayText(targetText);
      }
    };

    animationRef.current = requestAnimationFrame(scramble);

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [text, duration]);

  return (
    <Component className={className}>
      {displayText}
    </Component>
  );
};
