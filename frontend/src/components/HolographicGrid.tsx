'use client';

import { useEffect, useRef } from 'react';

export default function HolographicGrid() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    let animationFrame: number;
    let time = 0;

    const drawGrid = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const gridSize = 50;
      const lineWidth = 1;
      time += 0.008;

      ctx.save();

      // Draw diagonal grid lines
      for (let i = -canvas.height; i < canvas.width + canvas.height; i += gridSize) {
        const shimmer = Math.sin(time + i * 0.01) * 0.3 + 0.7;
        const gradient = ctx.createLinearGradient(
          i,
          0,
          i + 100,
          canvas.height
        );

        gradient.addColorStop(0, `rgba(64, 64, 64, ${0.15 * shimmer})`);
        gradient.addColorStop(0.5, `rgba(59, 130, 246, ${0.35 * shimmer})`);
        gradient.addColorStop(1, `rgba(64, 64, 64, ${0.1 * shimmer})`);

        ctx.strokeStyle = gradient;
        ctx.lineWidth = lineWidth;
        ctx.beginPath();
        ctx.moveTo(i, 0);
        ctx.lineTo(i - canvas.height, canvas.height);
        ctx.stroke();
      }

      // Draw horizontal grid lines
      for (let i = 0; i < canvas.height; i += gridSize) {
        const shimmer = Math.sin(time * 0.8 + i * 0.02) * 0.3 + 0.7;
        const gradient = ctx.createLinearGradient(0, i, canvas.width, i);

        gradient.addColorStop(0, `rgba(64, 64, 64, ${0.1 * shimmer})`);
        gradient.addColorStop(0.5, `rgba(59, 130, 246, ${0.25 * shimmer})`);
        gradient.addColorStop(1, `rgba(64, 64, 64, ${0.05 * shimmer})`);

        ctx.strokeStyle = gradient;
        ctx.lineWidth = lineWidth;
        ctx.beginPath();
        ctx.moveTo(0, i);
        ctx.lineTo(canvas.width, i);
        ctx.stroke();
      }

      ctx.restore();

      animationFrame = requestAnimationFrame(drawGrid);
    };

    drawGrid();

    const handleResize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationFrame);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
      <canvas
        ref={canvasRef}
        className="absolute inset-0 opacity-50"
      />
  );
}
