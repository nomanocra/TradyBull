'use client';

import { ReactNode } from 'react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface GroupButtonOption {
  value: string;
  label: string;
  icon?: ReactNode;
  description?: string;
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
      className={`inline-flex flex-wrap gap-0.5 bg-gray-100 dark:bg-[#252525] rounded-md p-0.5 ${className}`}
    >
      {options.map((option) => {
        const isActive = option.value === value;
        const button = (
          <button
            key={option.value}
            onClick={() => onChange(option.value)}
            className={`
              flex items-center justify-center gap-1.5 px-2.5 h-6 text-[10px] font-medium rounded-md
              transition-all duration-200 cursor-pointer whitespace-nowrap
              ${isActive
                ? 'bg-brand text-white dark:text-[#0d0d0d] shadow-sm'
                : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
              }
            `}
          >
            {option.icon}
            {option.label}
          </button>
        );

        if (option.description) {
          return (
            <Tooltip key={option.value}>
              <TooltipTrigger asChild>{button}</TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[250px]">
                {option.description}
              </TooltipContent>
            </Tooltip>
          );
        }

        return button;
      })}
    </div>
  );
}
