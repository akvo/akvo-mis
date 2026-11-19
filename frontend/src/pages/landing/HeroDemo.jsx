import { useState } from "react";
import PropTypes from "prop-types";
import colors from "../../lib/theme";

// Build the area + line path for a small sparkline-style chart from a list
// of values. Pure geometry, no chart library — the dashboard is an
// illustrative product shot, not a real visualisation.
const buildChart = (values, width, height, pad) => {
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const stepX = (width - pad * 2) / (values.length - 1);
  const points = values.map((value, i) => {
    const x = pad + i * stepX;
    const y = height - pad - ((value - min) / span) * (height - pad * 2);
    return [x, y];
  });
  const line = points
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`)
    .join(" ");
  const first = points[0];
  const last = points[points.length - 1];
  const area = `${line} L${last[0].toFixed(1)} ${
    height - pad
  } L${first[0].toFixed(1)} ${height - pad} Z`;
  return { line, area, last };
};

const CHART_W = 460;
const CHART_H = 150;
const CHART_PAD = 12;

const HeroDemo = ({ demo }) => {
  const [active, setActive] = useState(0);
  const sector = demo.sectors[active];
  const { line, area, last } = buildChart(
    sector.trend,
    CHART_W,
    CHART_H,
    CHART_PAD
  );

  return (
    <div className="w-full rounded-2xl border border-white/10 bg-brand-ink p-5 shadow-2xl shadow-black/30">
      {/* Status row */}
      <div className="flex items-center gap-2">
        <span
          className="h-2.5 w-2.5 rounded-full bg-brand-bright"
          aria-hidden="true"
        />
        <span className="font-mono text-sm text-white">{demo.brandLabel}</span>
        <span className="font-mono text-sm text-white/40">
          · {demo.liveLabel}
        </span>
        <span className="flex-1" />
        <span className="rounded-full border border-brand-bright/50 px-3 py-1 text-xs font-semibold text-brand-bright">
          {demo.syncedLabel}
        </span>
      </div>

      {/* Sector tabs */}
      <div className="mt-4 flex flex-wrap gap-2">
        {demo.sectors.map((s, i) => (
          <button
            key={s.name}
            type="button"
            aria-pressed={i === active}
            onClick={() => setActive(i)}
            className={
              i === active
                ? "rounded-full bg-brand px-3 py-1.5 text-xs font-semibold text-white"
                : "rounded-full border border-white/15 px-3 py-1.5 text-xs font-semibold text-white/70 transition-colors hover:border-white/40 hover:text-white"
            }
          >
            {s.name}
          </button>
        ))}
      </div>

      {/* Stat tiles + map placeholder */}
      <div className="mt-4 grid grid-cols-3 gap-3">
        <div className="col-span-1 flex flex-col gap-3">
          <div className="rounded-xl bg-white/5 p-3">
            <p className="font-mono text-[11px] uppercase tracking-wide text-white/40">
              {sector.metricLabel}
            </p>
            <p className="mt-1 font-title text-2xl font-bold text-white">
              {sector.metricValue}
            </p>
            <p className="mt-1 text-xs font-semibold text-brand-bright">
              ↗ {sector.metricNote}
            </p>
          </div>
          <div className="rounded-xl bg-white/5 p-3">
            <p className="font-mono text-[11px] uppercase tracking-wide text-white/40">
              {sector.rateLabel}
            </p>
            <p className="mt-1 font-title text-2xl font-bold text-white">
              {sector.rateValue}
            </p>
            <p className="mt-1 text-xs font-semibold text-brand-bright">
              {sector.rateNote}
            </p>
          </div>
        </div>
        <div className="col-span-2 flex items-end rounded-xl border border-white/10 bg-gradient-to-br from-brand-bright/15 to-transparent p-3">
          <span className="font-mono text-xs text-white/50">
            {sector.mapNote}
          </span>
        </div>
      </div>

      {/* Chart */}
      <div className="mt-3 rounded-xl bg-white/5 p-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs text-white/60">
            {demo.chartTitle}
          </span>
          <span className="font-mono text-xs text-brand-bright">
            {demo.chartNote}
          </span>
        </div>
        <svg
          viewBox={`0 0 ${CHART_W} ${CHART_H}`}
          className="mt-2 h-28 w-full"
          preserveAspectRatio="none"
          role="img"
          aria-label={`${demo.chartTitle}: ${sector.name}`}
        >
          <defs>
            <linearGradient id="heroDemoFill" x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="0%"
                stopColor={colors.brandChart}
                stopOpacity="0.45"
              />
              <stop
                offset="100%"
                stopColor={colors.brandChart}
                stopOpacity="0"
              />
            </linearGradient>
          </defs>
          <path d={area} fill="url(#heroDemoFill)" />
          <path
            d={line}
            fill="none"
            stroke={colors.brandBright}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx={last[0]} cy={last[1]} r="5" fill={colors.brandBright} />
        </svg>
      </div>

      {/* Caption */}
      <div className="mt-3 flex items-center gap-2">
        <span className="rounded-md bg-white/10 px-2 py-0.5 font-mono text-[11px] text-white/50">
          {demo.demoBadge}
        </span>
        <span className="text-xs text-white/50">{demo.caption}</span>
      </div>
    </div>
  );
};

HeroDemo.propTypes = {
  demo: PropTypes.shape({
    brandLabel: PropTypes.string,
    liveLabel: PropTypes.string,
    syncedLabel: PropTypes.string,
    demoBadge: PropTypes.string,
    caption: PropTypes.string,
    chartTitle: PropTypes.string,
    chartNote: PropTypes.string,
    mobileAlt: PropTypes.string,
    flipLabel: PropTypes.string,
    sectors: PropTypes.arrayOf(PropTypes.object),
  }).isRequired,
};

export default HeroDemo;
