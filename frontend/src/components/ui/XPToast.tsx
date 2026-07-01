'use client';
import { useState, useEffect } from 'react';

interface XPToastProps {
  points?: number;
  onComplete?: () => void;
}

export function XPToast({ points = 10, onComplete }: XPToastProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      onComplete?.();
    }, 1500);
    return () => clearTimeout(timer);
  }, [onComplete]);

  if (!visible) return null;

  return <div className="xp-toast">+{points} XP</div>;
}
