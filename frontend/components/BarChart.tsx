"use client";

import { useState } from "react";
import { niceTicks, formatCompact } from "@/lib/chart-utils";

export interface BarDatum {
  label: string;
  value: number;
}

export function BarChart({
  data,
  height = 220,
  valueSuffix = "",
}: {
  data: BarDatum[];
  height?: number;
  valueSuffix?: string;
}) {
  const [hovered, setHovered] = useState<number | null>(null);

  const width = 560;
  const padding = { top: 12, right: 12, bottom: 28, left: 40 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  const maxVal = Math.max(1, ...data.map((d) => d.value));
  const ticks = niceTicks(maxVal);
  const scaleMax = ticks[ticks.length - 1];

  const barSlot = plotW / data.length;
  const barWidth = Math.min(24, Math.max(2, barSlot - 8));
  const gap = 2;

  // Thin x-axis labels so they never overlap: figure out how many
  // ~10px-wide label slots fit and only draw every Nth one.
  const minLabelWidth = 26;
  const maxLabels = Math.max(1, Math.floor(plotW / minLabelWidth));
  const labelStep = Math.max(1, Math.ceil(data.length / maxLabels));

  // Truncate labels based on the room each one actually has, not a fixed
  // character count — two wide bars can show their full label.
  const approxCharPx = 5.5;
  const maxChars = Math.max(3, Math.floor((barSlot - 4) / approxCharPx));
  const fitLabel = (label: string) =>
    label.length > maxChars ? `${label.slice(0, maxChars - 1)}…` : label;

  const y = (v: number) => padding.top + plotH - (v / scaleMax) * plotH;

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label="Bar chart"
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

        {data.map((d, i) => {
          const slotX = padding.left + i * barSlot;
          const barX = slotX + (barSlot - barWidth) / 2;
          const barTop = y(d.value);
          const barH = padding.top + plotH - barTop;
          const isHovered = hovered === i;
          return (
            <g
              key={d.label}
              onPointerEnter={() => setHovered(i)}
              onPointerLeave={() => setHovered(null)}
              style={{ cursor: "pointer" }}
            >
              <rect
                x={slotX}
                y={padding.top}
                width={barSlot}
                height={plotH}
                fill="transparent"
              />
              <rect
                x={barX + gap / 2}
                y={barTop}
                width={Math.max(1, barWidth - gap)}
                height={Math.max(0, barH)}
                rx={4}
                fill="var(--series-1)"
                opacity={isHovered ? 0.75 : 1}
              />
              {i % labelStep === 0 && (
                <text
                  x={slotX + barSlot / 2}
                  y={padding.top + plotH + 16}
                  textAnchor="middle"
                  fontSize={10}
                  fill="var(--text-muted)"
                >
                  {fitLabel(d.label)}
                </text>
              )}
              {isHovered && (() => {
                const tooltipH = 22;
                const fitsAbove = barTop - tooltipH - 6 >= padding.top;
                const tooltipY = fitsAbove
                  ? barTop - tooltipH - 6
                  : barTop + 6;
                return (
                  <>
                    <rect
                      x={slotX + barSlot / 2 - 46}
                      y={tooltipY}
                      width={92}
                      height={tooltipH}
                      rx={4}
                      fill="var(--surface)"
                      stroke="var(--border)"
                    />
                    <text
                      x={slotX + barSlot / 2}
                      y={tooltipY + 15}
                      textAnchor="middle"
                      fontSize={11}
                      fontWeight={600}
                      fill="var(--text-primary)"
                    >
                      {d.label}: {formatCompact(d.value)}
                      {valueSuffix}
                    </text>
                  </>
                );
              })()}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
