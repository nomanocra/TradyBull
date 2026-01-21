'use client';

import { useEffect, useRef } from 'react';
import { Database } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useDataSources, DataSource } from '@/hooks/useDataSources';

interface DataSourceSelectorProps {
  value: string;
  onChange: (source: string) => void;
  className?: string;
}

export function DataSourceSelector({ value, onChange, className }: DataSourceSelectorProps) {
  const { dataSources, isLoading } = useDataSources();
  const hasSyncedRef = useRef(false);

  const formatSourceLabel = (source: DataSource) => {
    const name = source.source === 'firstrate' ? 'FirstRate' : 'yFinance';
    return `${name} (${source.years_coverage}y)`;
  };

  // Determine effective value
  const valueExists = dataSources.some(s => s.source === value);
  const effectiveValue = valueExists ? value : (dataSources[0]?.source || value);

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
      <div className="flex items-center gap-1">
        <Database className="h-3 w-3 text-muted-foreground" />
        <Select value={effectiveValue} onValueChange={onChange}>
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
    </div>
  );
}
