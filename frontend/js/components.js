// ─────────────────────────────────────────────────────────────
// components.js — presentational & interactive UI pieces
// ─────────────────────────────────────────────────────────────
const { useState, useEffect, useRef } = React;

// Cross-fading full-screen colour wash
function WashBackground({ wash, motion }) {
  const [layers, setLayers] = useState([{ id: 0, wash }]);
  const prev = useRef(wash);
  const nid = useRef(1);
  useEffect(() => {
    if (wash === prev.current) return;
    prev.current = wash;
    if (!motion) { setLayers([{ id: nid.current++, wash }]); return; }
    setLayers((ls) => [...ls, { id: nid.current++, wash }]);
  }, [wash, motion]);
  return (
    <div className="wash-root">
      {layers.map((l, i) => (
        <div key={l.id} className="wash-layer"
          style={{ backgroundImage: l.wash, animation: i > 0 && motion ? 'washIn .55s ease forwards' : 'none' }}
          onAnimationEnd={() => { if (i > 0) setLayers((cur) => cur.slice(-1)); }} />
      ))}
    </div>
  );
}

// Glanceable gas price display — hero widget
function GasPriceDisplay({ price, priceLow, weekDelta, precise, city, abbr, state, unit, theme, animKey }) {
  const isUp = weekDelta >= 0;
  const priceUnit = unit || 'gal';
  const absChange = Math.abs(weekDelta * 100).toFixed(0);
  const displayPrice = precise && priceLow ? priceLow : price;
  const priceLabel = precise && priceLow ? `lowest nearby · ${city}` : `avg · ${state}`;

  return (
    <div className="price-display reveal-item" style={{ animationDelay: '.08s' }} key={animKey}>
      <div className="price-row">
        <div className="price-number" style={{ color: theme.word }}>
          ${displayPrice.toFixed(2)}
        </div>
        <span className="price-delta-badge" style={{ color: theme.accent }}>
          {isUp ? '↑' : '↓'}&thinsp;{isUp ? '+' : '−'}{absChange}¢
        </span>
      </div>
      <div className="price-label" style={{ color: theme.textSoft }}>
        {priceLabel}
        <span className="price-unit-inline">&thinsp;/{priceUnit}</span>
      </div>
    </div>
  );
}

// 2-week trend sparkline
function Sparkline({ values, accent, motion, animKey }) {
  const W = 320, H = 60, pad = 4;
  const min = Math.min(...values), max = Math.max(...values);
  const span = (max - min) || 1;
  const pts = values.map((v, i) => {
    const x = pad + (W - 2 * pad) * (i / (values.length - 1));
    const y = pad + (H - 2 * pad) * (1 - (v - min) / span);
    return [x, y];
  });
  const line = pts.map((p) => p.join(',')).join(' ');
  const area = `M${pts[0][0]},${H} L` + line.replace(/ /g, ' L') + ` L${pts[pts.length-1][0]},${H} Z`;
  const last = pts[pts.length - 1];
  const gid = 'spark-' + animKey;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="spark" style={{ height: H }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={accent} stopOpacity="0.32" />
          <stop offset="100%" stopColor={accent} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`} className={motion ? 'spark-area-in' : ''} />
      <polyline points={line} fill="none" stroke={accent} strokeWidth="2.5"
        strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke"
        className={motion ? 'spark-draw' : ''} />
      <circle cx={last[0]} cy={last[1]} r="3.4" fill={accent}
        className={motion ? 'spark-dot-in' : ''} />
    </svg>
  );
}

// 7-day strip with today tick + best-day ring
function DayStrip({ bestDayIdx, theme }) {
  return (
    <div className="daystrip">
      {window.DAYS.map((d, i) => {
        const isBest = i === bestDayIdx;
        const isToday = i === window.TODAY_IDX;
        return (
          <div key={i} className="day-col">
            <div className="day-cell" style={{
              color: isBest ? theme.onAccent : theme.textSoft,
              background: isBest ? theme.accent : 'transparent',
              border: isBest ? `2px solid ${theme.accent}` : `1.5px solid ${theme.cardBorder}`,
              fontWeight: isBest ? 700 : 500,
            }}>{d}</div>
            <div className="day-tick" style={{ background: isToday ? theme.textSoft : 'transparent' }} />
          </div>
        );
      })}
    </div>
  );
}

// Horizontal price-component meter
function BarMeter({ label, pct, accent, theme }) {
  return (
    <div className="meter-row">
      <div className="meter-top">
        <span style={{ color: theme.text }}>{label}</span>
        <span style={{ color: theme.textSoft }}>{pct}%</span>
      </div>
      <div className="meter-track" style={{ background: theme.cardBorder }}>
        <div className="meter-fill" style={{ width: pct + '%', background: accent }} />
      </div>
    </div>
  );
}

// Source attribution link
function SrcLink({ src, theme }) {
  return (
    <a className="src-link" href={src.url} target="_blank" rel="noopener"
      style={{ color: theme.accent }} onClick={(e) => e.stopPropagation()}>
      {src.label} ↗
    </a>
  );
}

// News carousel with pill selector
function NewsCarousel({ items, theme }) {
  const [idx, setIdx] = useState(0);
  const trackRef = useRef(null);
  const onScroll = () => {
    const el = trackRef.current; if (!el) return;
    setIdx(Math.round(el.scrollLeft / el.clientWidth));
  };
  const go = (i) => {
    const el = trackRef.current; if (!el) return;
    el.scrollTo({ left: i * el.clientWidth, behavior: 'smooth' });
    setIdx(i);
  };
  return (
    <div className="news-wrap">
      <div className="news-pills">
        {items.map((n, i) => (
          <button key={i} className={'news-pill' + (i === idx ? ' active' : '')} onClick={() => go(i)}
            style={{
              background: i === idx ? theme.accent : 'transparent',
              color: i === idx ? theme.onAccent : theme.textSoft,
              borderColor: i === idx ? theme.accent : theme.cardBorder,
            }}>{n.source}</button>
        ))}
      </div>
      <div className="news-track" ref={trackRef} onScroll={onScroll}>
        {items.map((n, i) => (
          <div className="news-card" key={i}
            style={{ background: theme.dark ? 'rgba(127,127,127,0.14)' : 'rgba(0,0,0,0.05)' }}>
            <div className="news-head">{n.headline}</div>
            <a className="news-src" href={n.url} target="_blank" rel="noopener"
              style={{ color: theme.accent }} onClick={(e) => e.stopPropagation()}>
              Read at {n.source} ↗
            </a>
          </div>
        ))}
      </div>
      <div className="news-dots">
        {items.map((_, i) => (
          <span key={i} className="news-dot" onClick={() => go(i)}
            style={{ background: i === idx ? theme.accent : theme.cardBorder, width: i === idx ? 18 : 6 }} />
        ))}
      </div>
    </div>
  );
}

// Generic bottom sheet (mobile)
function Sheet({ open, onClose, theme, children, title }) {
  return (
    <div className={'sheet-overlay' + (open ? ' open' : '')} onClick={onClose}>
      <div className={'sheet' + (open ? ' open' : '')}
        style={{ background: 'rgba(18,18,22,0.88)', color: '#fff' }}
        onClick={(e) => e.stopPropagation()}>
        <div className="sheet-grab" style={{ background: 'rgba(255,255,255,0.28)' }} />
        {title && <div className="sheet-title">{title}</div>}
        {children}
      </div>
    </div>
  );
}

// Location picker sheet (mobile) / dropdown (desktop)
function LocationSheet({ open, onClose, onSelect, current, theme, paletteKey, variant = 'sheet', regions }) {
  const [q, setQ] = useState('');
  useEffect(() => { if (!open) setQ(''); }, [open]);
  const source = regions || window.PLACEHOLDER_REGIONS;
  const list = source.filter((r) =>
    r.state.toLowerCase().includes(q.toLowerCase()) ||
    r.abbr.toLowerCase().includes(q.toLowerCase())
  );
  const tone = (r) => window.PALETTES[paletteKey || 'classic'].tone[r.verdict];

  const items = (
    <div className="loc-list">
      {list.map((r) => (
        <button key={r.id} className="loc-item" onClick={() => onSelect(r.id)}
          style={{ borderColor: r.id === current ? tone(r) : 'transparent' }}>
          <span className="loc-dot" style={{ background: tone(r) }} />
          <span className="loc-name">{r.state}</span>
          <span className="loc-price">${r.price.toFixed(2)}{r.unit === 'L' ? '/L' : ''}</span>
          <span className="loc-verdict" style={{ color: tone(r) }}>{window.VERDICTS[r.verdict].label}</span>
        </button>
      ))}
      {list.length === 0 && <div className="loc-empty">No match found.</div>}
    </div>
  );

  if (variant === 'dropdown') {
    if (!open) return null;
    return (
      <div className="loc-dropdown"
        style={{ background: 'rgba(22,22,28,0.97)', borderColor: theme.cardBorder, color: '#fff' }}>
        <input className="loc-search" placeholder="Search states…" value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ background: 'rgba(255,255,255,0.08)', color: '#fff', outline: 'none', borderRadius: 10, padding: '8px 12px', fontFamily: 'inherit', fontSize: 14, marginBottom: 6, border: 0 }} />
        {items}
      </div>
    );
  }

  return (
    <Sheet open={open} onClose={onClose} theme={theme} title="Choose your region">
      <input className="loc-search" placeholder="Search states…" value={q}
        onChange={(e) => setQ(e.target.value)}
        style={{ background: 'rgba(255,255,255,0.1)', color: '#fff' }} />
      {items}
    </Sheet>
  );
}

// Context / what's-driving-this content (used in both sheet + rail)
function ContextContent({ region, wti, theme }) {
  if (!region) return null;
  const b = region.breakdown;
  const S = window.SOURCES;
  const wtiPrice = (wti && wti.price) || 71.2;
  const wtiDir   = (wti && wti.dir) || region.wtiDir || 'flat';
  return (
    <>
      <div className="ctx-grid">
        <div className="ctx-stat" style={{ background: 'rgba(255,255,255,0.07)' }}>
          <div className="ctx-k">WTI crude</div>
          <div className="ctx-v" style={{ color: theme.text }}>
            ${wtiPrice.toFixed(2)}
            <span style={{ color: theme.accent, fontSize: 15, marginLeft: 4 }}>
              {wtiDir === 'down' ? '▼' : wtiDir === 'up' ? '▲' : '—'}
            </span>
          </div>
          <SrcLink src={S.crude} theme={theme} />
        </div>
        <div className="ctx-stat" style={{ background: 'rgba(255,255,255,0.07)' }}>
          <div className="ctx-k">Regional avg</div>
          <div className="ctx-v" style={{ color: theme.text }}>${region.price.toFixed(2)}</div>
          <SrcLink src={S.price} theme={theme} />
        </div>
      </div>

      <div className="ctx-k" style={{ marginBottom: 8, color: theme.textSoft }}>In the news</div>
      <NewsCarousel items={region.news} theme={theme} />

      <div className="breakdown-head">
        <span className="ctx-k" style={{ color: theme.textSoft }}>Price breakdown</span>
        <SrcLink src={S.breakdown} theme={theme} />
      </div>
      <BarMeter label="Crude oil" pct={b.crude} accent={theme.accent} theme={theme} />
      <BarMeter label="Refining" pct={b.refining} accent={theme.accent} theme={theme} />
      <BarMeter label="Taxes" pct={b.taxes} accent={theme.accent} theme={theme} />
      <BarMeter label="Distribution" pct={b.dist} accent={theme.accent} theme={theme} />
      <div className="ctx-foot">Data via EIA · updated periodically</div>
    </>
  );
}

// Context bottom sheet (mobile)
function ContextSheet({ open, onClose, region, wti, theme }) {
  if (!region) return null;
  return (
    <Sheet open={open} onClose={onClose} theme={theme} title="What's driving today's price">
      <ContextContent region={region} wti={wti} theme={theme} />
    </Sheet>
  );
}

// Toast notification
function Toast({ msg }) {
  return <div className={'toast' + (msg ? ' show' : '')}>{msg}</div>;
}

// Loading screen
function LoadingScreen() {
  return (
    <div className="loading-screen">
      <div className="loading-dots">
        <div className="loading-dot" />
        <div className="loading-dot" />
        <div className="loading-dot" />
      </div>
    </div>
  );
}

Object.assign(window, {
  WashBackground, GasPriceDisplay, Sparkline, DayStrip, BarMeter, SrcLink,
  NewsCarousel, Sheet, LocationSheet, ContextContent, ContextSheet, Toast, LoadingScreen,
});
