'use client';

import { useRef, useState, useCallback, useEffect, useMemo } from 'react';
import { CandleData } from '@/types/market';

interface ChartNavigatorProps {
  data: CandleData[];
  visibleRange: { from: number; to: number } | null;
  onRangeChange: (from: number, to: number) => void;
  onDragStateChange?: (isDragging: boolean) => void;
}

export function ChartNavigator({ data, visibleRange, onRangeChange, onDragStateChange }: ChartNavigatorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dragState, setDragState] = useState<{
    type: 'left' | 'right' | 'middle';
    startX: number;
    startRange: { from: number; to: number };
  } | null>(null);

  // Notify parent of drag state changes
  useEffect(() => {
    onDragStateChange?.(dragState !== null);
  }, [dragState, onDragStateChange]);

  // Calculate min/max prices for the mini chart
  const { minPrice, priceRange } = useMemo(() => {
    if (data.length === 0) return { minPrice: 0, maxPrice: 0, priceRange: 0 };
    let min = Infinity;
    let max = -Infinity;
    for (const candle of data) {
      if (candle.low < min) min = candle.low;
      if (candle.high > max) max = candle.high;
    }
    const padding = (max - min) * 0.1;
    return { minPrice: min - padding, maxPrice: max + padding, priceRange: max - min + padding * 2 };
  }, [data]);

  // Get selection bounds in percentages
  const selectionBounds = useMemo(() => {
    if (!visibleRange || data.length <= 1) {
      return { leftPercent: 0, rightPercent: 100 };
    }
    const leftPercent = (visibleRange.from / (data.length - 1)) * 100;
    const rightPercent = (visibleRange.to / (data.length - 1)) * 100;
    return { leftPercent, rightPercent };
  }, [visibleRange, data.length]);

  // Determine drag type based on click position
  const getDragType = useCallback((e: React.MouseEvent): 'left' | 'right' | 'middle' | null => {
    if (!containerRef.current || !visibleRange) return null;

    const rect = containerRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const width = rect.width;

    const leftEdgeX = (visibleRange.from / (data.length - 1)) * width;
    const rightEdgeX = (visibleRange.to / (data.length - 1)) * width;

    const handleWidth = 12; // Pixels for handle detection

    // Check if clicking on left handle
    if (Math.abs(clickX - leftEdgeX) <= handleWidth) {
      return 'left';
    }
    // Check if clicking on right handle
    if (Math.abs(clickX - rightEdgeX) <= handleWidth) {
      return 'right';
    }
    // Check if clicking inside selection
    if (clickX > leftEdgeX + handleWidth && clickX < rightEdgeX - handleWidth) {
      return 'middle';
    }

    return null;
  }, [visibleRange, data.length]);

  // Handle mouse down on the navigator
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!visibleRange) return;

    const dragType = getDragType(e);
    if (dragType) {
      e.preventDefault();
      setDragState({
        type: dragType,
        startX: e.clientX,
        startRange: { ...visibleRange },
      });
    }
  }, [visibleRange, getDragType]);

  // Handle mouse move during drag
  useEffect(() => {
    if (!dragState || !containerRef.current) return;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = containerRef.current!.getBoundingClientRect();
      const width = rect.width;
      const deltaX = e.clientX - dragState.startX;
      const deltaIndex = (deltaX / width) * (data.length - 1);

      const minRange = Math.max(10, Math.floor(data.length * 0.02));

      let newFrom = dragState.startRange.from;
      let newTo = dragState.startRange.to;

      if (dragState.type === 'left') {
        // Only move left edge, keep right fixed
        newFrom = dragState.startRange.from + deltaIndex;
        newFrom = Math.max(0, Math.min(newFrom, dragState.startRange.to - minRange));
        newTo = dragState.startRange.to; // Keep right fixed
      } else if (dragState.type === 'right') {
        // Only move right edge, keep left fixed
        newTo = dragState.startRange.to + deltaIndex;
        newTo = Math.min(data.length - 1, Math.max(newTo, dragState.startRange.from + minRange));
        newFrom = dragState.startRange.from; // Keep left fixed
      } else if (dragState.type === 'middle') {
        // Move both edges together
        const rangeSize = dragState.startRange.to - dragState.startRange.from;
        newFrom = dragState.startRange.from + deltaIndex;
        newTo = dragState.startRange.to + deltaIndex;

        // Clamp to bounds
        if (newFrom < 0) {
          newFrom = 0;
          newTo = rangeSize;
        }
        if (newTo > data.length - 1) {
          newTo = data.length - 1;
          newFrom = newTo - rangeSize;
        }
      }

      onRangeChange(Math.round(newFrom), Math.round(newTo));
    };

    const handleMouseUp = () => {
      setDragState(null);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [dragState, data.length, onRangeChange]);

  // Handle click on track to jump
  const handleTrackClick = useCallback((e: React.MouseEvent) => {
    if (!containerRef.current || !visibleRange || dragState) return;

    // Don't handle if we clicked on the selection area
    const dragType = getDragType(e);
    if (dragType) return;

    const rect = containerRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickIndex = (clickX / rect.width) * (data.length - 1);

    const rangeSize = visibleRange.to - visibleRange.from;
    const halfRange = rangeSize / 2;

    let newFrom = clickIndex - halfRange;
    let newTo = clickIndex + halfRange;

    // Clamp to bounds
    if (newFrom < 0) {
      newFrom = 0;
      newTo = rangeSize;
    }
    if (newTo > data.length - 1) {
      newTo = data.length - 1;
      newFrom = Math.max(0, newTo - rangeSize);
    }

    onRangeChange(Math.round(newFrom), Math.round(newTo));
  }, [visibleRange, data.length, getDragType, dragState, onRangeChange]);

  // Cursor style based on hover position
  const [cursorStyle, setCursorStyle] = useState<string>('pointer');
  const handleMouseMoveForCursor = useCallback((e: React.MouseEvent) => {
    if (dragState) return;
    const dragType = getDragType(e);
    if (dragType === 'left' || dragType === 'right') {
      setCursorStyle('ew-resize');
    } else if (dragType === 'middle') {
      setCursorStyle('grab');
    } else {
      setCursorStyle('pointer');
    }
  }, [getDragType, dragState]);

  if (data.length === 0) return null;

  return (
    <div className="w-full h-12 bg-[#0d0d0d] border-t border-[#1a1a1a] px-2 py-1">
      <div
        ref={containerRef}
        className="relative w-full h-full select-none"
        style={{ cursor: dragState ? (dragState.type === 'middle' ? 'grabbing' : 'ew-resize') : cursorStyle }}
        onMouseDown={handleMouseDown}
        onClick={handleTrackClick}
        onMouseMove={handleMouseMoveForCursor}
      >
        {/* Mini chart background */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none" preserveAspectRatio="none">
          {/* Price line */}
          <polyline
            fill="none"
            stroke="#3a3a3a"
            strokeWidth="1"
            points={data.map((candle, i) => {
              const x = (i / (data.length - 1)) * 100;
              const y = 100 - ((candle.close - minPrice) / priceRange) * 100;
              return `${x}%,${y}%`;
            }).join(' ')}
          />
          {/* Area fill */}
          <polygon
            fill="rgba(58, 58, 58, 0.3)"
            points={`0%,100% ${data.map((candle, i) => {
              const x = (i / (data.length - 1)) * 100;
              const y = 100 - ((candle.close - minPrice) / priceRange) * 100;
              return `${x}%,${y}%`;
            }).join(' ')} 100%,100%`}
          />
        </svg>

        {/* Selection overlay */}
        {visibleRange && (
          <>
            {/* Left dimmed area */}
            <div
              className="absolute top-0 bottom-0 left-0 bg-black/50 pointer-events-none"
              style={{ width: `${selectionBounds.leftPercent}%` }}
            />

            {/* Right dimmed area */}
            <div
              className="absolute top-0 bottom-0 right-0 bg-black/50 pointer-events-none"
              style={{ width: `${100 - selectionBounds.rightPercent}%` }}
            />

            {/* Selection box border */}
            <div
              className="absolute top-0 bottom-0 border-x-2 border-[#C59471]/70 pointer-events-none"
              style={{
                left: `${selectionBounds.leftPercent}%`,
                right: `${100 - selectionBounds.rightPercent}%`,
              }}
            >
              {/* Left handle indicator */}
              <div className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1/2 w-1 h-4 bg-[#C59471] rounded-full" />
              {/* Right handle indicator */}
              <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 w-1 h-4 bg-[#C59471] rounded-full" />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
