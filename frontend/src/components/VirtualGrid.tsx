'use client';

import { useVirtualizer } from '@tanstack/react-virtual';
import { useRef, useEffect, useState, useCallback } from 'react';

interface VirtualGridProps<T> {
  items: T[];
  renderItem: (item: T, index: number) => React.ReactNode;
  itemHeight: number;
  gap?: number;
  className?: string;
  minColumns?: number;
  maxColumns?: number;
}

// Breakpoint configuration for responsive column counts
interface BreakpointConfig {
  minWidth: number;
  columns: number;
}

const defaultBreakpoints: BreakpointConfig[] = [
  { minWidth: 1280, columns: 6 },
  { minWidth: 1024, columns: 5 },
  { minWidth: 768, columns: 4 },
  { minWidth: 640, columns: 3 },
  { minWidth: 0, columns: 2 },
];

// Calculate column count based on container width
function getColumnCount(width: number, minColumns: number, maxColumns: number): number {
  for (const breakpoint of defaultBreakpoints) {
    if (width >= breakpoint.minWidth) {
      return Math.min(Math.max(breakpoint.columns, minColumns), maxColumns);
    }
  }
  return minColumns;
}

export function VirtualGrid<T>({
  items,
  renderItem,
  itemHeight,
  gap = 16,
  className = '',
  minColumns = 2,
  maxColumns = 6,
}: VirtualGridProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null);
  const [columns, setColumns] = useState(5);

  // Update column count when container resizes
  const updateColumns = useCallback(() => {
    if (parentRef.current) {
      const width = parentRef.current.offsetWidth;
      const newColumns = getColumnCount(width, minColumns, maxColumns);
      setColumns(newColumns);
    }
  }, [minColumns, maxColumns]);

  useEffect(() => {
    updateColumns();

    const resizeObserver = new ResizeObserver(() => {
      updateColumns();
    });

    if (parentRef.current) {
      resizeObserver.observe(parentRef.current);
    }

    return () => {
      resizeObserver.disconnect();
    };
  }, [updateColumns]);

  const rowCount = Math.ceil(items.length / columns);

  const virtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => parentRef.current,
    estimateSize: () => itemHeight + gap,
    overscan: 3,
  });

  const virtualRows = virtualizer.getVirtualItems();

  if (items.length === 0) {
    return null;
  }

  return (
    <div
      ref={parentRef}
      className={`overflow-auto ${className}`}
      style={{ height: '100%' }}
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualRows.map((virtualRow) => {
          const startIndex = virtualRow.index * columns;
          const rowItems = items.slice(startIndex, startIndex + columns);

          return (
            <div
              key={virtualRow.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: `${virtualRow.size - gap}px`,
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <div
                className="grid"
                style={{
                  gridTemplateColumns: `repeat(${columns}, 1fr)`,
                  gap: `${gap}px`,
                }}
              >
                {rowItems.map((item, i) => (
                  <div key={startIndex + i}>
                    {renderItem(item, startIndex + i)}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Window-based virtualization for full-page scrolling
interface WindowVirtualGridProps<T> {
  items: T[];
  renderItem: (item: T, index: number) => React.ReactNode;
  itemHeight: number;
  gap?: number;
  className?: string;
  minColumns?: number;
  maxColumns?: number;
}

export function WindowVirtualGrid<T>({
  items,
  renderItem,
  itemHeight,
  gap = 16,
  className = '',
  minColumns = 2,
  maxColumns = 6,
}: WindowVirtualGridProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [columns, setColumns] = useState(5);

  // Update column count when container resizes
  const updateColumns = useCallback(() => {
    if (containerRef.current) {
      const width = containerRef.current.offsetWidth;
      const newColumns = getColumnCount(width, minColumns, maxColumns);
      setColumns(newColumns);
    }
  }, [minColumns, maxColumns]);

  useEffect(() => {
    updateColumns();

    const resizeObserver = new ResizeObserver(() => {
      updateColumns();
    });

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      resizeObserver.disconnect();
    };
  }, [updateColumns]);

  const rowCount = Math.ceil(items.length / columns);

  const virtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () =>
      typeof window !== 'undefined' ? (window as unknown as Element) : null,
    estimateSize: () => itemHeight + gap,
    overscan: 5,
  });

  const virtualRows = virtualizer.getVirtualItems();

  if (items.length === 0) {
    return null;
  }

  return (
    <div ref={containerRef} className={className}>
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualRows.map((virtualRow) => {
          const startIndex = virtualRow.index * columns;
          const rowItems = items.slice(startIndex, startIndex + columns);

          return (
            <div
              key={virtualRow.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: `${virtualRow.size - gap}px`,
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <div
                className="grid"
                style={{
                  gridTemplateColumns: `repeat(${columns}, 1fr)`,
                  gap: `${gap}px`,
                }}
              >
                {rowItems.map((item, i) => (
                  <div key={startIndex + i}>
                    {renderItem(item, startIndex + i)}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default VirtualGrid;
