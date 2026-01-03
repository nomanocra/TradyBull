'use client';

import { Skeleton } from '@/components/ui/skeleton';

export function BacktestingPageSkeleton() {
  return (
    <div className="h-full w-full bg-background flex flex-col overflow-hidden">
      {/* Header skeleton */}
      <header className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-card">
        {/* Strategy name - Left */}
        <div className="flex-1 flex items-center gap-2">
          <Skeleton className="h-4 w-32" />
        </div>

        {/* Symbol and price - Center */}
        <div className="flex items-center gap-2">
          <Skeleton className="h-4 w-10" />
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-4 w-14" />
        </div>

        {/* Data info - Right */}
        <div className="flex-1 flex items-center justify-end gap-3">
          <div className="flex items-center gap-2">
            <Skeleton className="h-4 w-8" />
            <Skeleton className="h-8 w-24" />
          </div>
          <div className="flex items-center gap-2">
            <Skeleton className="h-4 w-6" />
            <Skeleton className="h-8 w-24" />
          </div>
          <Skeleton className="h-4 w-20" />
          <div className="w-1.5 h-1.5 rounded-full bg-yellow-500 animate-pulse" />
        </div>
      </header>

      {/* KPI Tiles skeleton */}
      <div className="px-2 pt-2">
        <div className="flex gap-2 flex-wrap">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="bg-card rounded px-2.5 py-1.5 min-w-0">
              <Skeleton className="h-3 w-16 mb-1" />
              <Skeleton className="h-5 w-12" />
            </div>
          ))}
        </div>
      </div>

      {/* Chart skeleton */}
      <div className="flex-1 p-2 bg-background min-h-0">
        <div className="h-full w-full rounded-md overflow-hidden border border-border bg-card">
          {/* Chart header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-border">
            <Skeleton className="h-4 w-28" />
            <div className="flex gap-2">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-16" />
            </div>
          </div>

          {/* Chart area */}
          <div className="relative flex-1 p-4" style={{ height: 'calc(100% - 40px)' }}>
            {/* Y-axis skeleton */}
            <div className="absolute right-0 top-4 bottom-4 w-12 flex flex-col justify-between items-end pr-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-3 w-10" />
              ))}
            </div>

            {/* Chart bars skeleton */}
            <div className="h-full mr-14 flex items-end gap-0.5 pb-6">
              {Array.from({ length: 80 }).map((_, i) => (
                <Skeleton
                  key={i}
                  className="flex-1"
                  style={{ height: `${30 + Math.sin(i * 0.2) * 25 + Math.random() * 25}%` }}
                />
              ))}
            </div>

            {/* X-axis skeleton */}
            <div className="absolute bottom-0 left-4 right-14 flex justify-between">
              {Array.from({ length: 10 }).map((_, i) => (
                <Skeleton key={i} className="h-3 w-12" />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
