'use client';

import * as React from 'react';
import { CalendarIcon } from 'lucide-react';
import { format } from 'date-fns';
import { fr } from 'date-fns/locale';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

interface DatePickerProps {
  date: Date | undefined;
  onDateChange: (date: Date | undefined) => void;
  minDate?: Date;
  maxDate?: Date;
  placeholder?: string;
  className?: string;
}

export function DatePicker({
  date,
  onDateChange,
  minDate,
  maxDate,
  placeholder = 'Sélectionner',
  className,
}: DatePickerProps) {
  const [open, setOpen] = React.useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            'h-6 justify-between text-left font-mono text-[10px] !px-1.5 gap-1 cursor-pointer',
            'bg-[#1a1a1a] border-[#2a2a2a] hover:bg-[#252525] hover:border-[#3a3a3a]',
            !date && 'text-gray-500',
            date && 'text-gray-300',
            className
          )}
        >
          {date ? format(date, 'dd/MM/yyyy', { locale: fr }) : placeholder}
          <CalendarIcon className="!h-3 !w-3 text-[#C59471] cursor-pointer" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-auto p-3 bg-[#151515] border-[#2a2a2a]"
        align="start"
      >
        <Calendar
          mode="single"
          selected={date}
          onSelect={(newDate) => {
            onDateChange(newDate);
            setOpen(false);
          }}
          disabled={(day) => {
            if (minDate && day < minDate) return true;
            if (maxDate && day > maxDate) return true;
            return false;
          }}
          defaultMonth={date || minDate}
          startMonth={minDate}
          endMonth={maxDate}
          captionLayout="dropdown"
          locale={fr}
          className="bg-transparent p-0"
          classNames={{
            months: 'flex flex-col relative',
            month: 'space-y-2',
            month_caption: 'flex justify-center items-center h-7 relative',
            caption_label: 'text-sm font-medium text-gray-300 [&>svg]:hidden transition-colors',
            dropdowns: 'flex gap-2 items-center',
            dropdown_root: 'group/dropdown relative border-none shadow-none cursor-pointer [&:hover>span]:text-[#C59471]',
            dropdown: 'absolute inset-0 opacity-0 cursor-pointer',
            nav: 'absolute top-0 left-0 right-0 h-7 flex items-center justify-between z-10 pointer-events-none',
            button_previous: 'h-6 w-6 bg-transparent hover:bg-[#252525] rounded p-0 flex items-center justify-center pointer-events-auto cursor-pointer',
            button_next: 'h-6 w-6 bg-transparent hover:bg-[#252525] rounded p-0 flex items-center justify-center pointer-events-auto cursor-pointer',
            table: 'w-full border-collapse',
            weekdays: 'flex',
            weekday: 'text-gray-500 rounded-md w-8 font-normal text-[0.8rem]',
            week: 'flex w-full mt-1',
            day: 'relative p-0 text-center text-sm focus-within:relative focus-within:z-20 h-8 w-8',
            day_button: cn(
              'h-8 w-8 p-0 font-normal rounded cursor-pointer',
              'hover:bg-[#252525] hover:text-white',
              'focus:bg-[#252525] focus:text-white'
            ),
            selected: 'bg-[#C59471] text-[#0d0d0d] hover:bg-[#C59471] hover:text-[#0d0d0d]',
            today: 'bg-[#252525] text-white',
            outside: 'text-gray-600 opacity-50',
            disabled: 'text-gray-700 opacity-30 cursor-not-allowed hover:bg-transparent',
            hidden: 'invisible',
          }}
        />
      </PopoverContent>
    </Popover>
  );
}
