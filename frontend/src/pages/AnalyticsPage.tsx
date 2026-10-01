import { useEffect, useState } from 'react';
import { AnalyticsSummary, getAnalytics } from '../api/client';

// ── Colour palette ──────────────────────────────────────────────────
const REL_COLORS: Record<string, string> = {
  corroborates: '#10b981',
  contradicts: '#ef4444',
  reconciles: '#f59e0b',
  unrelated: '#9ca3af',
};

const ENTITY_COLORS = [
  '#3b82f6', '#8b5cf6', '#10b981', '#f59e0b',
  '#ef4444', '#06b6d4', '#ec4899', '#84cc16',
];

// ── Mini bar chart (horizontal) ────────────────────────────────────
function HBar({
  items,
  colorFn,
  maxWidth = 260,
}: {
  items: { label: string; value: number; color?: string }[];
  colorFn?: (label: string, i: number) => string;
  maxWidth?: number;
}) {
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="hbar-chart">
      {items.map((item, i) => {
        const color = item.color ?? colorFn?.(item.label, i) ?? '#3b82f6';
        const pct = (item.value / max) * 100;
        return (
          <div key={item.label} className="hbar-row">
            <span className="hbar-label" title={item.label}>
              {item.label.length > 22 ? item.label.slice(0, 20) + '…' : item.label}
            </span>
            <div className="hbar-track">
              <div
                className="hbar-fill"
                style={{ width: `${pct}%`, background: color }}
              />
            </div>
            <span className="hbar-value">{item.value}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Donut / pie chart via SVG ───────────────────────────────────────
function DonutChart({
  slices,
  size = 140,
}: {
  slices: { label: string; value: number; color: string }[];
  size?: number;
}) {
  const total = slices.reduce((s, sl) => s + sl.value, 0);
  if (total === 0) return <div className="empty-state">No data</div>;

  const r = 50;
  const cx = 70;
  const cy = 70;
  let cumAngle = -Math.PI / 2;

  const paths = slices
    .filter((sl) => sl.value > 0)
    .map((sl) => {
      const angle = (sl.value / total) * 2 * Math.PI;
      const x1 = cx + r * Math.cos(cumAngle);
      const y1 = cy + r * Math.sin(cumAngle);
      cumAngle += angle;
      const x2 = cx + r * Math.cos(cumAngle);
      const y2 = cy + r * Math.sin(cumAngle);
      const large = angle > Math.PI ? 1 : 0;
      return { sl, d: `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${large},1 ${x2},${y2} Z` };
    });

  return (
    <div className="donut-wrap">
      <svg width={size} height={size} viewBox="0 0 140 140">
        {paths.map(({ sl, d }) => (
          <path key={sl.label} d={d} fill={sl.color} stroke="#fff" strokeWidth={1.5}>
            <title>{sl.label}: {sl.value}</title>
          </path>
        ))}
        {/* inner hole */}
        <circle cx={cx} cy={cy} r={28} fill="#fff" />
        <text x={cx} y={cy - 4} textAnchor="middle" fontSize="12" fontWeight="700" fill="#111">
          {total}
        </text>
        <text x={cx} y={cy + 10} textAnchor="middle" fontSize="8" fill="#9ca3af">
          total
        </text>
      </svg>
      <div className="donut-legend">
        {slices.filter((sl) => sl.value > 0).map((sl) => (
          <div key={sl.label} className="donut-legend-item">
            <span className="donut-dot" style={{ background: sl.color }} />
            <span>{sl.label}</span>
            <span className="donut-count">{sl.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Stat card ───────────────────────────────────────────────────────
function StatCard({
  label,
  value,
  sub,
  color = '#3b82f6',
}: {
  label: string;
  value: number | string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="stat-card">
      <div className="stat-value" style={{ color }}>{value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────
function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    getAnalytics()
      .then(setData)
      .catch(() => setError('Unable to load analytics.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="empty-state">Loading analytics…</div>;
  if (error) return <div className="page-message page-error">{error}</div>;
  if (!data) return null;

  const { totals } = data;
  const reviewPct = totals.facts > 0
    ? Math.round((totals.needs_review / totals.facts) * 100)
    : 0;

  return (
    <section className="analytics-page">
      <div className="page-heading">
        <span className="eyebrow">System overview</span>
        <h2>Analytics</h2>
        <p>A snapshot of everything extracted and analysed across your documents.</p>
      </div>

      {/* ── Summary cards ── */}
      <div className="stat-grid">
        <StatCard label="Documents" value={totals.documents} color="#3b82f6" />
        <StatCard label="Total facts" value={totals.facts} color="#8b5cf6" />
        <StatCard label="Entities" value={totals.entities} color="#10b981" />
        <StatCard label="Relationships" value={totals.relationships} color="#f59e0b" />
        <StatCard
          label="Need review"
          value={totals.needs_review}
          sub={`${reviewPct}% of facts`}
          color={totals.needs_review > 0 ? '#ef4444' : '#10b981'}
        />
      </div>

      {/* ── Row 1: Facts per doc + Relationship breakdown ── */}
      <div className="analytics-row">
        <div className="analytics-card">
          <h3>Facts per document</h3>
          <HBar
            items={data.facts_per_document.map((d) => ({
              label: d.filename.replace(/^document:[a-f0-9]+_/, '').replace('.pdf', ''),
              value: d.fact_count,
            }))}
            colorFn={(_, i) => ENTITY_COLORS[i % ENTITY_COLORS.length]}
          />
        </div>

        <div className="analytics-card">
          <h3>Relationship types</h3>
          <DonutChart
            slices={data.relationship_breakdown.map((r) => ({
              label: r.type.charAt(0).toUpperCase() + r.type.slice(1),
              value: r.count,
              color: REL_COLORS[r.type.toLowerCase()] ?? '#9ca3af',
            }))}
          />
        </div>
      </div>

      {/* ── Row 2: Confidence distribution + Entity types ── */}
      <div className="analytics-row">
        <div className="analytics-card">
          <h3>Confidence distribution</h3>
          <HBar
            items={data.confidence_distribution.map((b) => ({
              label: b.label,
              value: b.count,
            }))}
            colorFn={(label) => {
              if (label.startsWith('80')) return '#10b981';
              if (label.startsWith('60')) return '#3b82f6';
              if (label.startsWith('40')) return '#f59e0b';
              return '#ef4444';
            }}
          />
        </div>

        <div className="analytics-card">
          <h3>Entity types</h3>
          <DonutChart
            slices={data.entity_type_breakdown.map((e, i) => ({
              label: e.type.charAt(0).toUpperCase() + e.type.slice(1),
              value: e.count,
              color: ENTITY_COLORS[i % ENTITY_COLORS.length],
            }))}
          />
        </div>
      </div>

      {/* ── Row 3: Top attributes + Top entities ── */}
      <div className="analytics-row">
        <div className="analytics-card">
          <h3>Top 10 attributes</h3>
          <HBar
            items={data.top_attributes.map((a) => ({
              label: a.attribute,
              value: a.count,
            }))}
            colorFn={(_, i) => ENTITY_COLORS[i % ENTITY_COLORS.length]}
          />
        </div>

        <div className="analytics-card">
          <h3>Top 10 entities by facts</h3>
          <HBar
            items={data.top_entities.map((e, i) => ({
              label: e.canonical_name,
              value: e.count,
              color: ENTITY_COLORS[i % ENTITY_COLORS.length],
            }))}
          />
        </div>
      </div>
    </section>
  );
}

export default AnalyticsPage;
