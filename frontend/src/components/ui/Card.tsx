import { ReactNode, KeyboardEvent } from 'react';
import { clsx } from 'clsx';

interface CardProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  hover?: boolean;
}

export function Card({ children, className, onClick, hover }: CardProps) {
  const isInteractive = !!(onClick || hover);

  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (onClick && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onClick();
    }
  }

  return (
    <div
      onClick={onClick}
      onKeyDown={onClick ? handleKeyDown : undefined}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      className={clsx(
        'bg-white rounded-3xl shadow-md p-6',
        isInteractive && 'cursor-pointer hover:shadow-xl hover:-translate-y-1 transition-all duration-200',
        onClick && 'focus:outline-none focus:ring-2 focus:ring-purple-400',
        className
      )}
    >
      {children}
    </div>
  );
}
