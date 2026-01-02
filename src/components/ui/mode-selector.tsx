'use client';

import * as React from 'react';
import { ChevronDown, Check, LucideIcon } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

export interface ModeOption {
  value: string;
  label: string;
  description: string;
  icon: LucideIcon;
}

interface ModeSelectorProps {
  options: ModeOption[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export function ModeSelector({ options, value, onChange, className }: ModeSelectorProps) {
  const [open, setOpen] = React.useState(false);
  const selectedOption = options.find((opt) => opt.value === value) || options[0];

  const handleSelect = (optionValue: string) => {
    onChange(optionValue);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          className={cn(
            'flex w-full items-center gap-2 px-2 py-1.5 bg-background dark:bg-muted/50 border border-border hover:bg-muted transition-colors text-left rounded-[2px]',
            className
          )}
        >
          <div className="flex h-5 w-5 items-center justify-center bg-brand/20 text-brand rounded-[2px]">
            <selectedOption.icon size={12} />
          </div>
          <span className="flex-1 text-xs font-medium text-foreground">
            {selectedOption.label}
          </span>
          <ChevronDown
            size={12}
            className={cn(
              'text-muted-foreground transition-transform',
              open && 'rotate-180'
            )}
          />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        sideOffset={4}
        className="w-[var(--radix-popover-trigger-width)] p-1 rounded-[2px] border-border"
      >
        {options.map((option) => {
          const isSelected = option.value === value;
          const Icon = option.icon;
          return (
            <button
              key={option.value}
              onClick={() => handleSelect(option.value)}
              className={cn(
                'flex w-full items-center gap-2.5 px-2 py-2 text-left transition-colors rounded-[2px]',
                isSelected
                  ? 'bg-brand/10 text-foreground'
                  : 'hover:bg-muted text-muted-foreground hover:text-foreground'
              )}
            >
              <div
                className={cn(
                  'flex h-7 w-7 items-center justify-center rounded-[2px]',
                  isSelected ? 'bg-brand/20 text-brand' : 'bg-muted text-muted-foreground'
                )}
              >
                <Icon size={16} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium">{option.label}</div>
                <div className="text-[10px] text-muted-foreground truncate">
                  {option.description}
                </div>
              </div>
              {isSelected && (
                <Check size={12} className="text-brand flex-shrink-0" />
              )}
            </button>
          );
        })}
      </PopoverContent>
    </Popover>
  );
}
