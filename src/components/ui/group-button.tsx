'use client';

import { ReactNode } from 'react';

interface GroupButtonOption {
  value: string;
  label: string;
  icon?: ReactNode;
}

interface GroupButtonProps {
  options: GroupButtonOption[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export function GroupButton({ options, value, onChange, className = '' }: GroupButtonProps) {
  return (
    <div
      className={`grid h-7 bg-[#1a1a1a] rounded-none p-0.5 ${className}`}
      style={{ gridTemplateColumns: `repeat(${options.length}, 1fr)` }}
    >
      {options.map((option) => {
        const isActive = option.value === value;
        return (
          <button
            key={option.value}
            onClick={() => onChange(option.value)}
            className={`
              flex items-center justify-center gap-1.5 text-[10px] font-medium rounded-none
              transition-all duration-200 cursor-pointer
              ${isActive
                ? 'bg-[#C59471] text-[#0d0d0d] shadow-sm'
                : 'text-gray-500 hover:text-gray-300'
              }
            `}
          >
            {option.icon}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
