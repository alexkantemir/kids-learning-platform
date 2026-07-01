import { ReactNode } from 'react';
import { clsx } from 'clsx';

interface ButtonProps {
  children: ReactNode;
  onClick?: () => void;
  type?: 'button' | 'submit';
  variant?: 'primary' | 'secondary' | 'success' | 'ghost';
  size?: 'sm' | 'md' | 'lg' | 'xl';
  disabled?: boolean;
  className?: string;
  fullWidth?: boolean;
}

const variants = {
  primary: 'bg-purple-600 hover:bg-purple-700 text-white shadow-lg hover:shadow-purple-300',
  secondary: 'bg-blue-500 hover:bg-blue-600 text-white shadow-lg',
  success: 'bg-green-500 hover:bg-green-600 text-white shadow-lg',
  ghost: 'bg-white hover:bg-gray-50 text-gray-700 border-2 border-gray-200',
};

const sizes = {
  sm: 'px-4 py-2 text-sm rounded-xl',
  md: 'px-6 py-3 text-base rounded-2xl',
  lg: 'px-8 py-4 text-lg rounded-2xl',
  xl: 'px-10 py-5 text-xl rounded-3xl',
};

export function Button({
  children, onClick, type = 'button', variant = 'primary',
  size = 'md', disabled, className, fullWidth,
}: ButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        'font-bold transition-all duration-200 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed',
        variants[variant],
        sizes[size],
        fullWidth && 'w-full',
        className
      )}
    >
      {children}
    </button>
  );
}
