'use client';

import { useRef, useEffect, useCallback, useState, memo } from 'react';
import { CandleData } from '@/types/market';

interface ChartNavigatorProps {
  data: CandleData[];
  totalBars: number;
  visibleFrom: number;
  visibleTo: number;
  onRangeChange: (from: number, to: number) => void;
  minVisibleBars?: number;
  maxVisibleBars?: number;
}

type DragType = 'none' | 'left' | 'right' | 'window';

function ChartNavigatorComponent({
  data,
  totalBars,
  visibleFrom,
  visibleTo,
  onRangeChange,
  minVisibleBars = 50,
  maxVisibleBars = 10000,
}: ChartNavigatorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [dragType, setDragType] = useState<DragType>('none');
  const [dragStartX, setDragStartX] = useState(0);
  const [dragStartFrom, setDragStartFrom] = useState(0);
  const [dragStartTo, setDragStartTo] = useState(0);

  const HEIGHT = 40;
  const HANDLE_WIDTH = 8;

  // Get container width
  const getContainerWidth = useCallback(() => {
    return containerRef.current?.clientWidth ?? 0;
  }, []);

  // Convert bar index to pixel position
  const barToPixel = useCallback((bar: number) => {
    const width = getContainerWidth();
    if (totalBars <= 0 || width <= 0) return 0;
    return (bar / totalBars) * width;
  }, [getContainerWidth, totalBars]);

  // Convert pixel position to bar index
  const pixelToBar = useCallback((pixel: number) => {
    const width = getContainerWidth();
    if (width <= 0) return 0;
    return (pixel / width) * totalBars;
  }, [getContainerWidth, totalBars]);

  // Draw miniature chart
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || data.length === 0) return;

    const width = container.clientWidth;
    const height = HEIGHT;

    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Background
    ctx.fillStyle = '#141414';
    ctx.fillRect(0, 0, width, height);

    // Find price range
    let minPrice = Infinity;
    let maxPrice = -Infinity;
    for (const candle of data) {
      minPrice = Math.min(minPrice, candle.low);
      maxPrice = Math.max(maxPrice, candle.high);
    }
    const priceRange = maxPrice - minPrice || 1;

    // Draw line
    ctx.beginPath();
    ctx.strokeStyle = '#4b5563';
    ctx.lineWidth = 1;

    const padding = 4;
    const chartHeight = height - padding * 2;

    for (let i = 0; i < data.length; i++) {
      const x = (i / Math.max(data.length - 1, 1)) * width;
      const y = padding + chartHeight - ((data[i].close - minPrice) / priceRange) * chartHeight;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }, [data]);

  // Handle mouse down
  const handleMouseDown = useCallback((e: React.MouseEvent, type: DragType) => {
    e.preventDefault();
    e.stopPropagation();
    setDragType(type);
    setDragStartX(e.clientX);
    setDragStartFrom(visibleFrom);
    setDragStartTo(visibleTo);
  }, [visibleFrom, visibleTo]);

  // Handle mouse move
  useEffect(() => {
    if (dragType === 'none') return;

    const handleMouseMove = (e: MouseEvent) => {
      const deltaPixels = e.clientX - dragStartX;
      const deltaBars = pixelToBar(deltaPixels);

      let newFrom = dragStartFrom;
      let newTo = dragStartTo;

      if (dragType === 'left') {
        // newTo stays fixed at dragStartTo
        newFrom = Math.max(0, dragStartFrom + deltaBars);
        newFrom = Math.min(newFrom, newTo - minVisibleBars);  // Can't go past min size
        newFrom = Math.max(newFrom, newTo - maxVisibleBars);  // Can't exceed max size
      } else if (dragType === 'right') {
        newTo = Math.min(totalBars, dragStartTo + deltaBars);
        newTo = Math.max(newTo, newFrom + minVisibleBars);    // Can't go past min size
        newTo = Math.min(newTo, newFrom + maxVisibleBars);    // Can't exceed max size
      } else if (dragType === 'window') {
        const windowSize = dragStartTo - dragStartFrom;
        newFrom = dragStartFrom + deltaBars;
        newTo = dragStartTo + deltaBars;

        if (newFrom < 0) {
          newFrom = 0;
          newTo = windowSize;
        }
        if (newTo > totalBars) {
          newTo = totalBars;
          newFrom = totalBars - windowSize;
        }
      }

      onRangeChange(Math.round(newFrom), Math.round(newTo));
    };

    const handleMouseUp = () => {
      setDragType('none');
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [dragType, dragStartX, dragStartFrom, dragStartTo, pixelToBar, totalBars, onRangeChange, minVisibleBars, maxVisibleBars]);

  // Cursor style
  useEffect(() => {
    if (dragType === 'left' || dragType === 'right') {
      document.body.style.cursor = 'ew-resize';
    } else if (dragType === 'window') {
      document.body.style.cursor = 'grabbing';
    } else {
      document.body.style.cursor = '';
    }
    return () => { document.body.style.cursor = ''; };
  }, [dragType]);

  if (data.length === 0 || totalBars === 0) return null;

  // Calculate positions (clamped to valid range)
  const clampedFrom = Math.max(0, Math.min(visibleFrom, totalBars));
  const clampedTo = Math.max(0, Math.min(visibleTo, totalBars));

  const leftPx = barToPixel(clampedFrom);
  const rightPx = barToPixel(clampedTo);
  const widthPx = Math.max(rightPx - leftPx, HANDLE_WIDTH * 2);

  const isDragging = dragType !== 'none';

  return (
    <div
      ref={containerRef}
      className="relative w-full bg-[#141414] border-t border-[#2a2a2a] group"
      style={{ height: HEIGHT }}
    >
      {/* Canvas */}
      <canvas ref={canvasRef} className="absolute top-0 left-0" />

      {/* Left dimmed area */}
      <div
        className="absolute top-0 bottom-0 left-0 bg-black/40 pointer-events-none"
        style={{ width: leftPx }}
      />

      {/* Right dimmed area */}
      <div
        className="absolute top-0 bottom-0 bg-black/40 pointer-events-none"
        style={{ left: rightPx, right: 0 }}
      />

      {/* Window */}
      <div
        className="absolute top-0 bottom-0"
        style={{ left: leftPx, width: widthPx }}
      >
        {/* Border lines - top, bottom (visible on hover or dragging) */}
        <div className={`absolute top-0 left-0 right-0 h-[2px] bg-[#C59471] transition-opacity duration-300 ease-in-out ${isDragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} />
        <div className={`absolute bottom-0 left-0 right-0 h-[2px] bg-[#C59471] transition-opacity duration-300 ease-in-out ${isDragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} />
        {/* Vertical lines - always visible */}
        <div className="absolute top-0 bottom-0 left-0 w-[1px] bg-[#C59471]/30" />

        {/* Left handle (visible on hover or dragging) */}
        <div
          className={`absolute top-1/2 -translate-y-1/2 left-0 w-[8px] h-[20px] bg-[#2a2a2a] hover:bg-[#3a3a3a] rounded-sm cursor-ew-resize flex items-center justify-center gap-[1px] border border-[#C59471] transition-opacity duration-300 ease-in-out ${isDragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
          style={{ marginLeft: -3 }}
          onMouseDown={(e) => handleMouseDown(e, 'left')}
        >
          <div className="w-[1px] h-2.5 bg-[#C59471]/60 rounded-full" />
          <div className="w-[1px] h-2.5 bg-[#C59471]/60 rounded-full" />
        </div>

        {/* Center area */}
        <div
          className="absolute top-0 bottom-0 left-0 right-0 cursor-grab active:cursor-grabbing"
          onMouseDown={(e) => handleMouseDown(e, 'window')}
        />

        {/* Right border line - always visible */}
        <div className="absolute top-0 bottom-0 right-0 w-[1px] bg-[#C59471]/30" />

        {/* Right handle (visible on hover or dragging) */}
        <div
          className={`absolute top-1/2 -translate-y-1/2 right-0 w-[8px] h-[20px] bg-[#2a2a2a] hover:bg-[#3a3a3a] rounded-sm cursor-ew-resize flex items-center justify-center gap-[1px] border border-[#C59471] transition-opacity duration-300 ease-in-out ${isDragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
          style={{ marginRight: -3 }}
          onMouseDown={(e) => handleMouseDown(e, 'right')}
        >
          <div className="w-[1px] h-2.5 bg-[#C59471]/60 rounded-full" />
          <div className="w-[1px] h-2.5 bg-[#C59471]/60 rounded-full" />
        </div>
      </div>

    </div>
  );
}

export const ChartNavigator = memo(ChartNavigatorComponent);
