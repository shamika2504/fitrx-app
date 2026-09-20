"use client";

import { useRef, useState } from "react";
import { niceTicks, formatCompact } from "@/lib/chart-utils";

export interface LineDatum {
  x: string;
  value: number;
}

export function LineChart({
  data,
  height = 220,
}: {
  data: LineDatum[];
  height?: number;
}) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const width = 560;
  const padding = { top: 12, right: 16, bottom: 28, left: 40 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  if (data.length === 0) {
    return (
      <div className="flex h-[220px] items-center justify-center text-sm text-[var(--text-muted)]">
        No data
      </div>
    );
  }

  const maxVal = Math.max(1, ...data.map((d) => d.value));
  const ticks = niceTicks(maxVal);
  const scaleMax = ticks[ticks.length - 1];

  const stepX = data.length > 1 ? plotW / (data.length - 1) : 0;
  const x = (i: number) => padding.left + i * stepX;
  const y = (v: number) => padding.top + plotH - (v / scaleMax) * plotH;

  const linePath = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(d.value)}`)
    .join(" ");
  const areaPath = `${linePath} L ${x(data.length - 1)} ${padding.top + plotH} L ${x(0)} ${padding.top + plotH} Z`;

  function handleMove(e: React.PointerEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const scale = width / rect.width;
    const px = (e.clientX - rect.left) * scale;
    const rel = (px - padding.left) / (stepX || 1);
    const idx = Math.max(0, Math.min(data.length - 1, Math.round(rel)));
    setHoverIdx(idx);
  }

  const last = data[data.length - 1];

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        className="w-full touch-none"
        role="img"
        aria-label="Line chart"
        onPointerMove={handleMove}
        onPointerLeave={() => setHoverIdx(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={y(t)}
              y2={y(t)}
              stroke="var(--gridline)"
              strokeWidth={1}
            />
            <text
              x={padding.left - 8}
              y={y(t)}
              textAnchor="end"
              dominantBaseline="middle"
              fontSize={10}
              fill="var(--text-muted)"
            >
              {formatCompact(t)}
            </text>
          </g>
        ))}
        <line
          x1={padding.left}
          x2={width - padding.right}
          y1={padding.top + plotH}
          y2={padding.top + plotH}
          stroke="var(--axis)"
          strokeWidth={1}
        />

        <path d={areaPath} fill="var(--series-1)" opacity={0.1} />
        <path
          d={linePath}
          fill="none"
          stroke="var(--series-1)"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* end marker */}
        <circle cx={x(data.length - 1)} cy={y(last.value)} r={5} fill="var(--surface)" />
        <circle cx={x(data.length - 1)} cy={y(last.value)} r={4} fill="var(--series-1)" />
        <text
          x={x(data.length - 1)}
          y={y(last.value) - 10}
          textAnchor="end"
          fontSize={11}
          fontWeight={600}
          fill="var(--text-primary)"
        >
          {formatCompact(last.value)}
        </text>

        {/* x-axis labels: first and last only */}
        <text x={x(0)} y={height - 8} fontSize={10} fill="var(--text-muted)" textAnchor="start">
          {data[0].x}
        </text>
        <text
          x={x(data.length - 1)}
          y={height - 8}
          fontSize={10}
          fill="var(--text-muted)"
          textAnchor="end"
        >
          {last.x}
        </text>

        {hoverIdx !== null && (
          <g>
            <line
              x1={x(hoverIdx)}
              x2={x(hoverIdx)}
              y1={padding.top}
              y2={padding.top + plotH}
              stroke="var(--axis)"
              strokeWidth={1}
            />
            <circle
              cx={x(hoverIdx)}
              cy={y(data[hoverIdx].value)}
              r={4}
              fill="var(--series-1)"
              stroke="var(--surface)"
              strokeWidth={2}
            />
          </g>
        )}
      </svg>

      {hoverIdx !== null && (
        <div
          className="pointer-events-none absolute top-0 -translate-x-1/2 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs shadow-sm"
          style={{
            left: `${(x(hoverIdx) / width) * 100}%`,
          }}
        >
          <div className="font-semibold text-[var(--text-primary)]">
            {formatCompact(data[hoverIdx].value)}
          </div>
          <div className="text-[var(--text-muted)]">{data[hoverIdx].x}</div>
        </div>
      )}
    </div>
  );
}
