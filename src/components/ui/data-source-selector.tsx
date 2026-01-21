'use client';

import { useEffect, useRef, useState } from 'react';
import { Database } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useDataSources, DataSource } from '@/hooks/useDataSources';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface DataSourceSelectorProps {
  value: string;
  onChange: (source: string) => void;
  className?: string;
}

export function DataSourceSelector({ value, onChange, className }: DataSourceSelectorProps) {
  const { dataSources, isLoading } = useDataSources();
  const hasSyncedRef = useRef(false);
  const [selectOpen, setSelectOpen] = useState(false);

  const formatSourceLabel = (source: DataSource) => {
    const name = source.source === 'firstrate' ? 'FirstRate' : 'yFinance';
    return `${name} (${source.years_coverage}y)`;
  };

  const formatSourceDescription = (source: DataSource) => {
    return `${source.start_date} to ${source.end_date} - ${source.count.toLocaleString()} candles`;
  };

  // Determine effective value
  const valueExists = dataSources.some(s => s.source === value);
  const effectiveValue = valueExists ? value : (dataSources[0]?.source || value);
  const currentSource = dataSources.find(s => s.source === effectiveValue);

  // Sync effective value to parent only once when sources load and value doesn't exist
  useEffect(() => {
    if (!isLoading && dataSources.length > 0 && !valueExists && !hasSyncedRef.current) {
      hasSyncedRef.current = true;
      onChange(dataSources[0].source);
    }
  }, [isLoading, dataSources, valueExists, onChange]);

  // Reset sync flag when value changes externally
  useEffect(() => {
    if (valueExists) {
      hasSyncedRef.current = false;
    }
  }, [value, valueExists]);

  if (isLoading || dataSources.length === 0) {
    return null;
  }

  return (
    <div className={className}>
      <Tooltip open={selectOpen ? false : undefined}>
        <TooltipTrigger asChild>
          <div className="flex items-center gap-1">
            <Database className="h-3 w-3 text-muted-foreground" />
            <Select value={effectiveValue} onValueChange={onChange} open={selectOpen} onOpenChange={setSelectOpen}>
              <SelectTrigger className="!h-6 w-auto text-[10px] border-none bg-transparent shadow-none hover:bg-muted/50 focus:ring-0 px-1.5 gap-0.5 [&_svg]:size-3">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {dataSources.map((source) => (
                  <SelectItem
                    key={source.source}
                    value={source.source}
                    className="text-xs"
                  >
                    {formatSourceLabel(source)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="text-xs">
          {currentSource ? formatSourceDescription(currentSource) : 'Select data source'}
        </TooltipContent>
      </Tooltip>
    </div>
  );
}
