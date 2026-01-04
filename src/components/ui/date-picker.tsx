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
  onYearRangeSelect?: (year: number) => void;
}

export function DatePicker({
  date,
  onDateChange,
  minDate,
  maxDate,
  placeholder = 'Sélectionner',
  className,
  onYearRangeSelect,
}: DatePickerProps) {
  const [open, setOpen] = React.useState(false);

  // Calculate available years from minDate to maxDate
  const availableYears = React.useMemo(() => {
    if (!minDate || !maxDate) return [];
    const startYear = minDate.getFullYear();
    const endYear = maxDate.getFullYear();
    const years: number[] = [];
    for (let y = startYear; y <= endYear; y++) {
      years.push(y);
    }
    return years;
  }, [minDate, maxDate]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            'h-6 justify-between text-left font-mono text-[10px] !px-1.5 gap-1 cursor-pointer',
            'bg-gray-100 border-gray-300 hover:bg-gray-200 hover:border-gray-400',
            'dark:bg-[#252525] dark:border-[#3a3a3a] dark:hover:bg-[#303030] dark:hover:border-[#4a4a4a]',
            !date && 'text-gray-500',
            date && 'text-gray-700 dark:text-gray-300',
            className
          )}
        >
          {date ? format(date, 'dd/MM/yyyy', { locale: fr }) : placeholder}
          <CalendarIcon className="!h-3 !w-3 text-brand cursor-pointer" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-auto p-3 bg-white dark:bg-[#151515] border-gray-200 dark:border-[#2a2a2a]"
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
            caption_label: 'text-sm font-medium text-gray-700 dark:text-gray-300 [&>svg]:hidden transition-colors',
            dropdowns: 'flex gap-2 items-center',
            dropdown_root: 'group/dropdown relative border-none shadow-none cursor-pointer [&:hover>span]:text-brand',
            dropdown: 'absolute inset-0 opacity-0 cursor-pointer',
            nav: 'absolute top-0 left-0 right-0 h-7 flex items-center justify-between z-10 pointer-events-none',
            button_previous: 'h-6 w-6 bg-transparent hover:bg-gray-100 dark:hover:bg-[#252525] rounded p-0 flex items-center justify-center pointer-events-auto cursor-pointer',
            button_next: 'h-6 w-6 bg-transparent hover:bg-gray-100 dark:hover:bg-[#252525] rounded p-0 flex items-center justify-center pointer-events-auto cursor-pointer',
            table: 'w-full border-collapse',
            weekdays: 'flex',
            weekday: 'text-gray-500 rounded-md w-8 font-normal text-[0.8rem]',
            week: 'flex w-full mt-1',
            day: 'relative p-0 text-center text-sm focus-within:relative focus-within:z-20 h-8 w-8',
            day_button: cn(
              'h-8 w-8 p-0 font-normal rounded cursor-pointer',
              'hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-[#252525] dark:hover:text-white',
              'focus:bg-gray-100 focus:text-gray-900 dark:focus:bg-[#252525] dark:focus:text-white'
            ),
            selected: 'bg-brand text-[#0d0d0d] hover:bg-brand hover:text-[#0d0d0d]',
            today: 'bg-gray-100 text-gray-900 dark:bg-[#252525] dark:text-white',
            outside: 'text-gray-400 dark:text-gray-600 opacity-50',
            disabled: 'text-gray-300 dark:text-gray-700 opacity-30 cursor-not-allowed hover:bg-transparent',
            hidden: 'invisible',
          }}
        />
        {/* Year shortcuts */}
        {onYearRangeSelect && availableYears.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200 dark:border-[#2a2a2a]">
            <div
              className="grid h-7 bg-gray-100 dark:bg-[#252525] rounded-[2px] p-0.5"
              style={{ gridTemplateColumns: `repeat(${availableYears.length}, 1fr)` }}
            >
              {availableYears.map((year) => (
                <button
                  key={year}
                  onClick={() => {
                    onYearRangeSelect(year);
                    setOpen(false);
                  }}
                  className="flex items-center justify-center text-[10px] font-medium rounded-[2px] transition-all duration-200 cursor-pointer text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-[#303030]"
                >
                  {year}
                </button>
              ))}
            </div>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
