// ─────────────────────────────────────────────────────────────
// app.js — App composition, responsive layout
// ─────────────────────────────────────────────────────────────
const { useState: useS, useEffect: useE, useRef: useR } = React;

function App() {
  const [regions, setRegions] = useS(window.PLACEHOLDER_REGIONS);
  const [meta, setMeta] = useS({});
  const [wti, setWti] = useS({ price: 71.2, dir: 'down', change: -1.4 });
  const [regionId, setRegionId] = useS('ca');
  const [sheet, setSheet] = useS(null);       // 'location' | 'context' | null
  const [precise, setPrecise] = useS(false);
  const [locating, setLocating] = useS(false);
  const [refreshing, setRefreshing] = useS(false);
  const [toast, setToast] = useS('');
  const [loading, setLoading] = useS(true);
  const [menuOpen, setMenuOpen] = useS(false);
  const toastTimer = useR(null);

  const motion = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Load data and detect region on mount
  useE(() => {
    async function init() {
      const [dataResult, detectedId] = await Promise.all([
        window.loadData(),
        window.detectRegionFromIP(),
      ]);
      setRegions(dataResult.regions);
      setMeta(dataResult.meta);
      if (dataResult.wti) setWti(dataResult.wti);
      if (detectedId) {
        const found = dataResult.regions.find((r) => r.id === detectedId);
        if (found) setRegionId(detectedId);
      }
      setLoading(false);
    }
    init();
  }, []);

  // Close menu when clicking outside
  const menuRef = useR(null);
  useE(() => {
    if (!menuOpen) return;
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  // Keep the browser toolbar tint in sync with the active verdict. Safari tints
  // its top toolbar from <meta name="theme-color">; a static dark value left a
  // visible seam against the amber page. Use the verdict's solid tone color.
  useE(() => {
    const r = regions.find((x) => x.id === regionId) || regions[0];
    const tone = r && window.PALETTES.classic.tone[r.verdict];
    if (!tone) return;
    const tag = document.querySelector('meta[name="theme-color"]');
    if (tag) tag.setAttribute('content', tone);
  }, [regionId, regions]);

  const region = regions.find((r) => r.id === regionId) || regions[0];
  if (!region) return null;
  const theme = window.getTheme(region.verdict);
  const vinfo = window.VERDICTS[region.verdict];
  const animKey = regionId + '-' + region.verdict;

  const deltaStr = window.formatDelta(region.weekDelta, region.weekDeltaDir).label;
  const chipLabel = locating ? 'Locating…' : (precise ? `${region.city}, ${region.abbr}` : region.state);
  const updatedStr = window.formatRelativeTime(meta.pricesUpdatedAt) || '—';

  function flash(msg) {
    setToast(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(''), 2200);
  }
  function pickRegion(id) { setRegionId(id); setPrecise(false); setSheet(null); setMenuOpen(false); }
  function useExact() {
    if (locating) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      () => { setLocating(false); setPrecise(true); flash('Now using your exact location'); },
      () => { setLocating(false); flash('Location unavailable — using region avg'); }
    );
  }
  function refresh() {
    if (refreshing) return;
    setRefreshing(true);
    window.loadData().then((result) => {
      setRegions(result.regions);
      setMeta(result.meta);
      if (result.wti) setWti(result.wti);
      setRefreshing(false);
      flash('Prices refreshed');
    });
  }
  function openTab(url) { window.open(url, '_blank', 'noopener'); }
  function gbRegionSearchUrl() {
    return `https://www.gasbuddy.com/home?search=${encodeURIComponent(region.city + ', ' + region.abbr)}&fuel=1`;
  }
  function gbCoordsSearchUrl(lat, lng) {
    return `https://www.gasbuddy.com/home?search=${lat},${lng}&fuel=1`;
  }
  function openGasBuddy() {
    const low = region.lowStation;
    // Prompt for precise location so we can land the user on the most relevant
    // result. When granted: deep-link to the known cheapest station if the
    // backend found one, otherwise center GasBuddy on the user's exact coords.
    // When denied/unavailable: deep-link if we have it, else a region search.
    if (navigator.geolocation) {
      flash('Finding the cheapest station near you…');
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setPrecise(true);
          if (low && low.url) {
            flash(`Cheapest: ${low.name || 'station'}${low.price ? ` · $${low.price}/${region.unit}` : ''}`);
            openTab(low.url);
          } else {
            openTab(gbCoordsSearchUrl(pos.coords.latitude, pos.coords.longitude));
          }
        },
        () => {
          if (low && low.url) { flash(`Cheapest: ${low.name || 'station'}`); openTab(low.url); }
          else openTab(gbRegionSearchUrl());
        },
        { timeout: 6000, maximumAge: 600000 }
      );
      return;
    }
    if (low && low.url) { flash(`Cheapest: ${low.name || 'station'}`); openTab(low.url); }
    else { flash('Opening GasBuddy…'); openTab(gbRegionSearchUrl()); }
  }

  // Dynamic GasBuddy button hint: surface the cheapest known station when we have it.
  const gbLow = region.lowStation;
  const gbHint = gbLow && gbLow.price
    ? `Cheapest nearby: $${gbLow.price}/${region.unit}${gbLow.name ? ` · ${gbLow.name}` : ''}`
    : 'Tap to find the cheapest stations near you';

  if (loading) return <window.LoadingScreen />;

  const S = window.SOURCES;

  // Chip & icon buttons (shared between mobile and desktop topbar)
  const chipBtn = (
    <div className="chip-wrap" ref={menuRef}>
      <button className="chip" onClick={() => { setMenuOpen((v) => !v); setSheet(null); }}
        style={{ background: theme.chipBg, borderColor: theme.chipBorder, color: theme.text }}>
        <span className={'pin' + (precise ? ' filled' : '')}
          style={{ borderColor: theme.text, background: precise ? theme.accent : 'transparent' }} />
        <span className={locating ? 'chip-pulse' : ''}>{chipLabel}</span>
        <span style={{ opacity: 0.55, fontSize: 12 }}>▾</span>
      </button>
      <window.LocationSheet open={menuOpen} onClose={() => setMenuOpen(false)}
        onSelect={pickRegion} current={regionId} theme={theme} paletteKey="classic" variant="dropdown"
        regions={regions} />
    </div>
  );

  const iconBtns = (
    <>
      {!precise && (
        <button className="icon-btn" onClick={useExact} aria-label="Use my exact location"
          style={{ background: theme.chipBg, borderColor: theme.chipBorder, color: theme.text }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3.2" /><circle cx="12" cy="12" r="8" opacity="0.5" />
            <line x1="12" y1="1.5" x2="12" y2="4.5" /><line x1="12" y1="19.5" x2="12" y2="22.5" />
            <line x1="1.5" y1="12" x2="4.5" y2="12" /><line x1="19.5" y1="12" x2="22.5" y2="12" />
          </svg>
        </button>
      )}
      <button className="icon-btn" onClick={refresh} aria-label="Refresh prices"
        style={{ background: theme.chipBg, borderColor: theme.chipBorder, color: theme.text }}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          className={refreshing ? 'spin' : ''}>
          <path d="M21 12a9 9 0 1 1-2.64-6.36" /><polyline points="21 3 21 9 15 9" />
        </svg>
      </button>
    </>
  );

  // Context rail content (right column on desktop)
  const contextRailContent = (
    <aside className="context-rail" key={'rail-' + animKey}>
      <div className="rail-card" style={{ background: theme.cardBg, borderColor: theme.cardBorder }}>
        <div className="sup-head">
          <span className="sup-label" style={{ color: theme.textSoft }}>Best day to fill</span>
          <span className="advice" style={{ color: theme.accent }}>{window.bestDayLabel(region.bestDayIdx)}</span>
        </div>
        <window.DayStrip bestDayIdx={region.bestDayIdx} theme={theme} />
      </div>

      <div className="rail-card" style={{ background: theme.cardBg, borderColor: theme.cardBorder }}>
        <div className="sup-head">
          <span className="sup-label" style={{ color: theme.textSoft }}>2-week trend</span>
          <span className="delta" style={{ color: theme.textSoft }}>{deltaStr} · ${window.formatPrice(region.price, region.unit)} avg</span>
        </div>
        <window.Sparkline values={region.trend} accent={theme.accent} stroke={theme.word} motion={motion} animKey={animKey} />
        <div style={{ textAlign: 'right', marginTop: 6 }}><window.SrcLink src={S.price} theme={theme} /></div>
      </div>

      <div className="rail-card" style={{ background: theme.cardBg, borderColor: theme.cardBorder }}>
        <window.ContextContent region={region} wti={wti} theme={theme} />
      </div>
    </aside>
  );

  return (
    <div className={'app-root' + (motion ? '' : ' no-motion')}
      style={{ '--display-font': "'Bricolage Grotesque'" }}>
      <window.WashBackground wash={theme.wash} motion={motion} />
      <div className="grain" />

      <div className="site-wrap">
        {/* Top bar */}
        <header className="topbar">
          <div className="topbar-left">
            <h1 className="brand" style={{ color: theme.text }}>
              <a href="/" style={{ color: theme.text, textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '9px' }}>
                <span className="brand-logo" style={{ borderColor: theme.accent, color: theme.accent }}>$</span>
                Should&nbsp;I&nbsp;Get&nbsp;Gas?
              </a>
            </h1>
            {chipBtn}
          </div>
          <div className="topbar-right">
            <span className="d-updated" style={{ color: theme.textSoft }}>
              {updatedStr ? `Updated ${updatedStr}` : ''}
            </span>
            {iconBtns}
          </div>
        </header>

        {/* Main layout — becomes two-column grid on desktop via CSS */}
        <main className="main-content" key={animKey}>
          {/* Hero column */}
          <section className="hero">
            <div className="eyebrow reveal-item" style={{ color: theme.accent, animationDelay: '.04s' }}>
              Today · {region.state}
            </div>

            <window.GasPriceDisplay
              price={region.price}
              priceLow={region.priceLow}
              weekDelta={region.weekDelta}
              weekDeltaDir={region.weekDeltaDir}
              precise={precise}
              city={region.city}
              abbr={region.abbr}
              state={region.state}
              unit={region.unit}
              theme={theme}
              animKey={animKey}
              priceSource={region.priceSource}
            />

            <div className="verdict-word reveal-item word-reveal"
              style={{ color: theme.word, animationDelay: '.15s' }}>
              {vinfo.label}
            </div>
            <div className="verdict-desc">
              <div className="tagline reveal-item" style={{ color: theme.textSoft, animationDelay: '.24s' }}>
                {vinfo.tagline}
              </div>
              <p className="why reveal-item" style={{ color: theme.text, animationDelay: '.32s' }}>
                {region.why}
              </p>
            </div>

            {/* Desktop: GasBuddy action below why text */}
            <div className="hero-actions reveal-item" style={{ animationDelay: '.4s' }}>
              <button className="gb-btn" onClick={openGasBuddy}
                style={{ borderColor: theme.accent, color: theme.text }}>
                <span>{gbLow ? 'Go to cheapest station' : 'Find stations on GasBuddy'}</span>
                <span className="gb-btn-arrow" style={{ color: theme.accent }}>→</span>
              </button>
              <span className="gb-hint" style={{ color: theme.textSoft }}>
                {gbHint}
              </span>
            </div>
          </section>

          {/* Support cards — visible on mobile, hidden on desktop */}
          <div className="support-cards reveal-item" style={{ animationDelay: '.44s' }}>
            <div className="support-card" style={{ background: theme.cardBg, borderColor: theme.cardBorder }}>
              <div className="sup-head">
                <span className="sup-label" style={{ color: theme.textSoft }}>Best day to fill</span>
                <span className="advice" style={{ color: theme.accent }}>{window.bestDayLabel(region.bestDayIdx)}</span>
              </div>
              <window.DayStrip bestDayIdx={region.bestDayIdx} theme={theme} />
            </div>

            <div className="support-card" style={{ background: theme.cardBg, borderColor: theme.cardBorder }}>
              <div className="sup-head">
                <span className="sup-label" style={{ color: theme.textSoft }}>2-week trend</span>
                <span className="delta" style={{ color: theme.textSoft }}>{deltaStr}</span>
              </div>
              <window.Sparkline values={region.trend} accent={theme.accent} stroke={theme.word} motion={motion} animKey={animKey} />
            </div>

            <button className="ctx-link" onClick={() => setSheet('context')}
              style={{ color: theme.textSoft }}>
              What's driving this <span style={{ color: theme.accent }}>→</span>
            </button>

            <button className="gb-btn" onClick={openGasBuddy}
              style={{ borderColor: theme.accent, color: theme.text }}>
              <span>{gbLow ? 'Go to cheapest station' : 'Find stations on GasBuddy'}</span>
              <span className="gb-btn-arrow" style={{ color: theme.accent }}>→</span>
            </button>
            <div className="mobile-attribution" style={{ color: theme.textSoft }}>
              Prices via EIA · AI analysis updated daily ·{' '}
              <a href="data/data.json" style={{ color: theme.accent, textDecoration: 'none' }}>raw data ↗</a>
            </div>
          </div>

          {/* Context rail — hidden on mobile, two-column right on desktop */}
          {contextRailContent}
        </main>

        <footer className="site-footer" style={{ color: theme.textSoft }}>
          Prices via EIA · AI analysis updated daily ·{' '}
          <a href="data/data.json" style={{ color: theme.accent, textDecoration: 'none' }}>raw data ↗</a>
        </footer>
      </div>

      {/* Mobile sheets */}
      <window.ContextSheet open={sheet === 'context'} onClose={() => setSheet(null)}
        region={region} wti={wti} theme={theme} />
      <window.Toast msg={toast} />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
