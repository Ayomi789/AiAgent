import { useId } from "react";

interface Point {
  time: string;
  value: number;
}

export function BarChart({
  data,
  height = 168,
  color = "#3f6fb8",
  highlightIndex,
  unit = "",
}: {
  data: Point[];
  height?: number;
  color?: string;
  highlightIndex?: number;
  unit?: string;
}) {
  const width = 720;
  const padding = { top: 12, right: 8, bottom: 26, left: 38 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;
  const max = Math.max(...data.map((d) => d.value), 1);
  const step = chartW / data.length;
  const barW = Math.min(26, step * 0.52);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      style={{ height }}
      role="img"
      aria-label="Bar chart"
    >
      {[0, 0.25, 0.5, 0.75, 1].map((t) => {
        const y = padding.top + chartH - chartH * t;
        return (
          <g key={t}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={y}
              y2={y}
              stroke="#1e2227"
              strokeWidth={1}
            />
            <text
              x={padding.left - 8}
              y={y + 3}
              textAnchor="end"
              fontSize={9}
              fill="#4d555e"
              fontFamily="JetBrains Mono, monospace"
            >
              {Math.round(max * t)}
            </text>
          </g>
        );
      })}
      {data.map((d, i) => {
        const h = (d.value / max) * chartH;
        const x = padding.left + step * i + (step - barW) / 2;
        const y = padding.top + chartH - h;
        return (
          <g key={d.time}>
            <rect
              x={x}
              y={y}
              width={barW}
              height={Math.max(h, 1)}
              rx={2}
              fill={highlightIndex === i ? "#5b8fe0" : color}
              opacity={highlightIndex === i ? 1 : 0.82}
            >
              <title>{`${d.time} · ${d.value}${unit}`}</title>
            </rect>
            {i % 2 === 0 ? (
              <text
                x={x + barW / 2}
                y={height - 8}
                textAnchor="middle"
                fontSize={8.5}
                fill="#4d555e"
                fontFamily="JetBrains Mono, monospace"
              >
                {d.time}
              </text>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}

export function LineChart({
  data,
  height = 168,
  color = "#4c8dff",
  label,
  suffix = "",
}: {
  data: Point[];
  height?: number;
  color?: string;
  label?: string;
  suffix?: string;
}) {
  const width = 720;
  const padding = { top: 14, right: 10, bottom: 26, left: 38 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;
  const max = Math.max(...data.map((d) => d.value), 1);
  const stepX = chartW / Math.max(data.length - 1, 1);

  const points = data.map((d, i) => ({
    x: padding.left + stepX * i,
    y: padding.top + chartH - (d.value / max) * chartH,
  }));

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
  const areaPath = `${linePath} L${points[points.length - 1].x},${padding.top + chartH} L${
    points[0].x
  },${padding.top + chartH} Z`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      style={{ height }}
      role="img"
      aria-label={label ?? "Line chart"}
    >
      {[0, 0.25, 0.5, 0.75, 1].map((t) => {
        const y = padding.top + chartH - chartH * t;
        return (
          <g key={t}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={y}
              y2={y}
              stroke="#1e2227"
              strokeWidth={1}
            />
            <text
              x={padding.left - 8}
              y={y + 3}
              textAnchor="end"
              fontSize={9}
              fill="#4d555e"
              fontFamily="JetBrains Mono, monospace"
            >
              {Math.round(max * t)}
            </text>
          </g>
        );
      })}
      <path d={areaPath} fill={color} opacity={0.1} />
      <path d={linePath} fill="none" stroke={color} strokeWidth={1.8} strokeLinejoin="round" />
      {points.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={2.6} fill="#0b0d10" stroke={color} strokeWidth={1.5}>
          <title>{`${data[i].time} · ${data[i].value}${suffix}`}</title>
        </circle>
      ))}
      {data.map((d, i) =>
        i % 2 === 0 ? (
          <text
            key={d.time}
            x={points[i].x}
            y={height - 8}
            textAnchor="middle"
            fontSize={8.5}
            fill="#4d555e"
            fontFamily="JetBrains Mono, monospace"
          >
            {d.time}
          </text>
        ) : null,
      )}
    </svg>
  );
}

export function SeverityStack({
  segments,
  height = 10,
}: {
  segments: { label: string; value: number; color: string }[];
  height?: number;
}) {
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1;
  return (
    <div
      className="flex w-full overflow-hidden rounded-[3px] bg-app-750"
      style={{ height }}
      role="img"
      aria-label="Severity distribution"
    >
      {segments.map((s) => (
        <div
          key={s.label}
          title={`${s.label}: ${s.value}`}
          style={{
            width: `${(s.value / total) * 100}%`,
            backgroundColor: s.color,
            opacity: 0.9,
            transition: "width 300ms ease",
          }}
        />
      ))}
    </div>
  );
}

export function CoverageRow({
  label,
  value,
  detail,
  color = "#4c8dff",
}: {
  label: string;
  value: number;
  detail?: string;
  color?: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-[124px] shrink-0 text-[11px] text-muted truncate">{label}</div>
      <div className="relative h-[6px] flex-1 overflow-hidden rounded-[3px] bg-app-750">
        <div
          className="absolute inset-y-0 left-0 rounded-[3px] transition-[width] duration-500"
          style={{ width: `${value}%`, backgroundColor: color, opacity: 0.85 }}
        />
      </div>
      <div className="w-[38px] shrink-0 text-right font-mono text-[10.5px] text-ink-soft">
        {value}%
      </div>
      {detail ? (
        <div className="w-[72px] shrink-0 text-right font-mono text-[10px] text-faint">{detail}</div>
      ) : null}
    </div>
  );
}

export function Sparkline({
  values,
  color = "#4c8dff",
  width = 120,
  height = 32,
}: {
  values: number[];
  color?: string;
  width?: number;
  height?: number;
}) {
  const id = useId();
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const stepX = width / Math.max(values.length - 1, 1);
  const pts = values.map((v, i) => {
    const x = i * stepX;
    const y = height - 3 - ((v - min) / range) * (height - 6);
    return `${x},${y}`;
  });

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      <polyline
        points={pts.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        id={id}
      />
    </svg>
  );
}
