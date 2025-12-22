'use client';

import { useRef, useEffect, useCallback, useState, memo } from 'react';
import { CandleData } from '@/types/market';

// Theme-aware navigator colors
const navigatorColors = {
  dark: {
    background: '#141414',
    line: '#4b5563',
    dimmed: 'rgba(0, 0, 0, 0.4)',
  },
  light: {
    background: '#f9fafb',
    line: '#9ca3af',
    dimmed: 'rgba(0, 0, 0, 0.15)',
  },
};

// Hook to detect theme changes
function useTheme() {
  const [isDark, setIsDark] = useState(true);

  useEffect(() => {
    setIsDark(document.documentElement.classList.contains('dark'));

    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
          setIsDark(document.documentElement.classList.contains('dark'));
        }
      });
    });

    observer.observe(document.documentElement, { attributes: true });
    return () => observer.disconnect();
  }, []);

  return isDark;
}

interface ChartNavigatorProps {
  data: CandleData[];
  totalBars: number;
  visibleFrom: number;
  visibleTo: number;
  onRangeChange: (from: number, to: number) => void;
  onReset?: () => void;
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
  onReset,
  minVisibleBars = 50,
  maxVisibleBars = 10000,
}: ChartNavigatorProps) {
  const isDark = useTheme();
  const colors = navigatorColors[isDark ? 'dark' : 'light'];

  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [dragType, setDragType] = useState<DragType>('none');
  const [dragStartX, setDragStartX] = useState(0);
  const [dragStartFrom, setDragStartFrom] = useState(0);
  const [dragStartTo, setDragStartTo] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);

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

  // Stable reference to data for the drawing effect
  const dataRef = useRef(data);
  dataRef.current = data;

  // Draw miniature chart - use stable dependencies to avoid size change warnings
  const dataLength = data.length;
  const firstTime = data[0]?.time;
  const lastTime = data[dataLength - 1]?.time;

  // Track container width for resize - triggers redraw
  const [containerWidth, setContainerWidth] = useState(0);

  // ResizeObserver to track container width changes
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Try to get width, retry if 0
    const trySetWidth = () => {
      const width = container.clientWidth;
      if (width > 0) {
        setContainerWidth(width);
        return true;
      }
      return false;
    };

    // Try immediately, then after RAF, then after timeout
    if (!trySetWidth()) {
      requestAnimationFrame(() => {
        if (!trySetWidth()) {
          setTimeout(trySetWidth, 50);
        }
      });
    }

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const width = entry.contentRect.width;
        if (width > 0) {
          setContainerWidth(width);
        }
      }
    });

    resizeObserver.observe(container);

    return () => resizeObserver.disconnect();
  }, []);

  // Draw canvas function
  const drawCanvas = useCallback((width: number) => {
    const canvas = canvasRef.current;
    const currentData = dataRef.current;
    if (!canvas || currentData.length === 0 || width === 0) return;

    const height = HEIGHT;

    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Background
    ctx.fillStyle = colors.background;
    ctx.fillRect(0, 0, width, height);

    // Find price range
    let minPrice = Infinity;
    let maxPrice = -Infinity;
    for (const candle of currentData) {
      minPrice = Math.min(minPrice, candle.low);
      maxPrice = Math.max(maxPrice, candle.high);
    }
    const priceRange = maxPrice - minPrice || 1;

    // Draw line
    ctx.beginPath();
    ctx.strokeStyle = colors.line;
    ctx.lineWidth = 1;

    const padding = 4;
    const chartHeight = height - padding * 2;

    for (let i = 0; i < currentData.length; i++) {
      const x = (i / Math.max(currentData.length - 1, 1)) * width;
      const y = padding + chartHeight - ((currentData[i].close - minPrice) / priceRange) * chartHeight;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }, [colors]);

  // Trigger draw on data change, resize, or theme change
  useEffect(() => {
    if (containerWidth > 0) {
      drawCanvas(containerWidth);
      requestAnimationFrame(() => drawCanvas(containerWidth));
      const timeoutId = setTimeout(() => drawCanvas(containerWidth), 100);
      return () => clearTimeout(timeoutId);
    }
  }, [drawCanvas, dataLength, firstTime, lastTime, containerWidth]);

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

  // Handle double click to reset (must be before early return)
  const handleDoubleClick = useCallback(() => {
    if (onReset) {
      setIsAnimating(true);
      // Wait for transition class to be applied before changing values
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          onReset();
          setTimeout(() => setIsAnimating(false), 300);
        });
      });
    }
  }, [onReset]);

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
      className="relative w-full bg-card border-t border-border group"
      style={{ height: HEIGHT }}
      onDoubleClick={handleDoubleClick}
    >
      {/* Canvas */}
      <canvas ref={canvasRef} className="absolute top-0 left-0" />

      {/* Left dimmed area */}
      <div
        className={`absolute top-0 bottom-0 left-0 pointer-events-none ${isAnimating ? 'transition-all duration-300 ease-out' : ''}`}
        style={{ width: leftPx, backgroundColor: colors.dimmed }}
      />

      {/* Right dimmed area */}
      <div
        className={`absolute top-0 bottom-0 pointer-events-none ${isAnimating ? 'transition-all duration-300 ease-out' : ''}`}
        style={{ left: rightPx, right: 0, backgroundColor: colors.dimmed }}
      />

      {/* Window */}
      <div
        className={`absolute top-0 bottom-0 ${isAnimating ? 'transition-all duration-300 ease-out' : ''}`}
        style={{ left: leftPx, width: widthPx }}
      >
        {/* Border lines - top, bottom (visible on hover or dragging) */}
        <div className={`absolute top-0 left-0 right-0 h-[2px] bg-brand transition-opacity duration-300 ease-in-out ${isDragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} />
        <div className={`absolute bottom-0 left-0 right-0 h-[2px] bg-brand transition-opacity duration-300 ease-in-out ${isDragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} />
        {/* Vertical lines - always visible */}
        <div className="absolute top-0 bottom-0 left-0 w-[1px] bg-brand/30" />

        {/* Left handle (visible on hover or dragging) */}
        <div
          className={`absolute top-1/2 -translate-y-1/2 left-0 w-[8px] h-[20px] bg-muted hover:bg-muted-foreground/30 rounded-sm cursor-ew-resize flex items-center justify-center gap-[1px] border border-brand transition-opacity duration-300 ease-in-out ${isDragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
          style={{ marginLeft: -3 }}
          onMouseDown={(e) => handleMouseDown(e, 'left')}
        >
          <div className="w-[1px] h-2.5 bg-brand/60 rounded-full" />
          <div className="w-[1px] h-2.5 bg-brand/60 rounded-full" />
        </div>

        {/* Center area */}
        <div
          className="absolute top-0 bottom-0 left-0 right-0 cursor-grab active:cursor-grabbing"
          onMouseDown={(e) => handleMouseDown(e, 'window')}
        />

        {/* Right border line - always visible */}
        <div className="absolute top-0 bottom-0 right-0 w-[1px] bg-brand/30" />

        {/* Right handle (visible on hover or dragging) */}
        <div
          className={`absolute top-1/2 -translate-y-1/2 right-0 w-[8px] h-[20px] bg-muted hover:bg-muted-foreground/30 rounded-sm cursor-ew-resize flex items-center justify-center gap-[1px] border border-brand transition-opacity duration-300 ease-in-out ${isDragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
          style={{ marginRight: -3 }}
          onMouseDown={(e) => handleMouseDown(e, 'right')}
        >
          <div className="w-[1px] h-2.5 bg-brand/60 rounded-full" />
          <div className="w-[1px] h-2.5 bg-brand/60 rounded-full" />
        </div>
      </div>

    </div>
  );
}

export const ChartNavigator = memo(ChartNavigatorComponent);
