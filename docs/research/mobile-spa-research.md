# Mobile SPA Research: iOS Safari & WebKit Best Practices
**Generated:** 2026-06-07  
**Target platform:** iOS 16+ (iOS 18 current as of this writing)  
**Project:** shouldigetgas — zero-build React 18 SPA

---

## Table of Contents

- [Part 1: iOS Safari & WebKit Quirks](#part-1-ios-safari--webkit-quirks)
- [Part 2: Progressive Web App (PWA) Requirements](#part-2-progressive-web-app-pwa-requirements)
- [Part 3: Cross-Browser SPA Best Practices](#part-3-cross-browser-spa-best-practices)
- [Part 4: Performance on Mobile](#part-4-performance-on-mobile)
- [Part 5: iOS-Specific Issues & Workarounds](#part-5-ios-specific-issues--workarounds)
- [Priority Summary](#priority-summary)
- [Sources](#sources)

---

## Part 1: iOS Safari & WebKit Quirks

### 1. `100dvh` / `100vh` — Dynamic Viewport Height

**What it is:**  
The `dvh` (dynamic viewport height) unit accounts for iOS Safari's collapsing/expanding browser toolbar. Classic `100vh` locks to the *initial* viewport height (with the toolbar visible), so content can be taller than the screen once the toolbar collapses. `100dvh` tracks the viewport dynamically.

**iOS version applicability:**  
- iOS 15.4+: `100dvh` fully supported (Safari 15.4 shipped in March 2022)  
- iOS 14 and below: No `dvh` support — falls back to the unit being ignored; `100vh` is the only option  
- iOS 18: Stable, works as expected

**How it applies to shouldigetgas:**  
`styles.css` mobile media query (`max-width: 899px`) correctly uses the fallback-then-override pattern:
```css
html, body { height: 100dvh }
.site-wrap { height: 100vh; height: 100dvh }
```
The cascade ensures `100vh` is used when `100dvh` is unknown (iOS < 15.4). This is correct and no change is needed for modern targets. For iOS 14 support, an `@supports` guard makes intent clearer:
```css
.site-wrap {
  height: 100vh; /* fallback for iOS < 15.4 */
}
@supports (height: 100dvh) {
  .site-wrap { height: 100dvh; }
}
```

**Recommendation:** Current approach is correct. No change required if iOS 15.4+ is the minimum target (≈95%+ of active iOS devices as of 2026).

**Sources:**  
- https://medium.com/@tharunbalaji110/understanding-mobile-viewport-units-a-complete-guide-to-svh-lvh-and-dvh-0c905d96e21a  
- https://caniuse.com/viewport-unit-variants

---

### 2. `env(safe-area-inset-*)` and `viewport-fit=cover`

**What it is:**  
The `env()` CSS function reads device-provided environment variables for safe area insets (notch, Dynamic Island, home indicator). Crucially, `env(safe-area-inset-*)` values are **all 0px unless `viewport-fit=cover` is declared in the viewport meta tag**. Without that declaration, Safari letterboxes content and considers everything "safe" — making the env() calls a no-op.

**iOS version applicability:**  
- iOS 11.0+: `env()` and `viewport-fit` supported (Safari 11)  
- iOS 11.0–11.2: Used `constant()` syntax (see §7 below)  
- iOS 18: Dynamic Island inset is ~54px top on iPhone 16 Pro, ~50px on iPhone 15 Pro

**How it applies to shouldigetgas:**  
`styles.css` uses safe area insets in multiple places:
```css
.site-wrap {
  padding: env(safe-area-inset-top, 0px) 0 0;  /* top inset */
}
.sheet {
  padding: 12px 20px calc(28px + env(safe-area-inset-bottom, 0px));  /* bottom inset */
}
```

**However**, `index.html`'s current viewport meta tag is:
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
```
`viewport-fit=cover` is **missing**. This means all `env()` calls resolve to `0px` — the notch and Dynamic Island insets are not honoured. Content is letterboxed on notched iPhones rather than extending edge-to-edge.

**Recommendation:**  
Add `viewport-fit=cover` to `index.html`:
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
```
Always include fallback values in `env()` calls (already done — e.g., `env(safe-area-inset-top, 0px)`) so non-notched devices work correctly.

**Sources:**  
- https://css-tricks.com/the-notch-and-css/  
- https://mohammadshehadeh.com/css/safe-area-insets/  
- https://webkit.org/blog/7929/designing-websites-for-iphone-x/

---

### 3. `100vh` / `position: fixed` with iOS Address Bar

**What it is:**  
A longstanding iOS Safari bug: when the address bar auto-hides as the user scrolls, `position: fixed` elements are repainted relative to the *initial* viewport, not the collapsed one. This can cause fixed overlays to appear partially behind the toolbar or jump during scrolling.

**iOS version applicability:**  
- iOS 6 through iOS 18: Persists in various forms  
- Most noticeable on iOS 13–16; iOS 17+ is improved but not fully fixed

**How it applies to shouldigetgas:**  
`.sheet-overlay { position: fixed; inset: 0; }` and `.toast { position: fixed; }` use fixed positioning. The sheet covers the full screen, which is the most vulnerable pattern. If a keyboard also opens while the sheet is visible, the overlay may jump.

**Recommendation:**  
1. `100dvh` (already used) mitigates most of this for the outer container.  
2. For `.sheet-overlay`, consider using `position: fixed; inset: 0; height: 100%; height: 100dvh;` to ensure full coverage.  
3. Test specifically on a physical iPhone 14/15 in portrait with address bar visible, then scroll — verify the overlay does not gap at top or bottom.  
4. If the Visual Viewport API is available, compensate with JS (see §16 in Part 5).

---

### 4. `position: sticky` in Flex/Scroll Containers

**What it is:**  
`position: sticky` fails silently on iOS Safari when the scrolling ancestor is a **flex or grid container with `overflow: hidden` or `overflow: auto`**, or when a parent has `overflow` other than `visible` on any axis. The element simply doesn't stick.

**iOS version applicability:**  
All iOS versions including iOS 18. The root cause is the spec: sticky only works relative to its scroll container, and flex overflow changes what that container is.

**How it applies to shouldigetgas:**  
`.topbar` in `styles.css`:
```css
.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
}
```
Its parent is `.site-wrap`, which on mobile uses:
```css
.site-wrap {
  overflow: hidden;       /* ← This breaks position: sticky */
  height: 100dvh;
}
```
`overflow: hidden` on `.site-wrap` **prevents `.topbar` from sticking** on iOS. The topbar will scroll away with content.

**Recommendation:**  
Remove `overflow: hidden` from `.site-wrap` (or the intermediate scrollable parent). Instead, control overflow at the element level that actually scrolls. If `.main-content` is the scroll container, set `overflow-y: auto` on it and use `overflow: clip` (non-scrollable) rather than `hidden` on `.site-wrap`:
```css
.site-wrap {
  overflow: clip; /* doesn't create a scroll container; preserves sticky */
}
.main-content {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}
```
Test on a real iOS device — this is a hard-to-catch issue in browser DevTools.

**Sources:**  
- https://www.w3.org/TR/css-position-3/#sticky-pos  
- https://css-tricks.com/position-sticky-and-table-headers/

---

### 5. Input Font-Size Auto-Zoom (< 16px Threshold)

**What it is:**  
iOS Safari auto-zooms into any `<input>`, `<textarea>`, or `<select>` with `font-size` below 16px when focused, to aid readability. This creates a jarring viewport zoom that is difficult to suppress without sacrificing accessibility.

**iOS version applicability:**  
All iOS versions. Still present in iOS 18.

**How it applies to shouldigetgas:**  
`styles.css` defines `.loc-search` (the location search input inside the bottom sheet) with:
```css
.loc-search {
  font-size: 15px;  /* ← 1px below the 16px threshold; WILL trigger auto-zoom */
}
```
When users tap the search input on iOS, the entire viewport zooms in unexpectedly.

**Recommendation:**  
Increase to `font-size: 16px`:
```css
.loc-search {
  font-size: 16px;
}
```
This is the single most impactful fix for the location sheet UX on iOS. Do NOT use `maximum-scale=1` in the viewport meta to suppress zoom — that permanently disables pinch-to-zoom and is an accessibility violation.

**Sources:**  
- https://css-tricks.com/16px-or-larger-text-prevents-ios-form-zoom/  
- https://defensivecss.dev/tip/input-zoom-safari/  
- https://www.stefanjudis.com/notes/mobile-safari-doesnt-zoom-into-form-inputs-with-minimum-16px/

---

### 6. `-webkit-text-size-adjust: 100%`

**What it is:**  
When an iPhone rotates from portrait to landscape, iOS Safari historically scaled text up to improve readability at the wider viewport. `-webkit-text-size-adjust: 100%` disables this automatic adjustment, preventing unexpected font-size changes on rotation.

**iOS version applicability:**  
All iOS versions. Still relevant in iOS 18, especially on iPhones (not iPads, which don't show this behaviour).

**How it applies to shouldigetgas:**  
`styles.css` does **not** include `-webkit-text-size-adjust`. The `68px` `.price-number` and `88px` `.verdict-word` could scale unpredictably in landscape mode, breaking the compressed mobile layout.

**Recommendation:**  
Add to the `html` rule in `styles.css`:
```css
html {
  -webkit-text-size-adjust: 100%;
  text-size-adjust: 100%; /* standard, for future-proofing */
}
```

**Sources:**  
- https://kilianvalkhof.com/2022/css-html/your-css-reset-needs-text-size-adjust-probably/  
- https://www.browserstack.com/guide/webkit-text-size-adjust

---

### 7. `constant()` — iOS 10/11 Safe Area Fallback Syntax

**What it is:**  
iOS 11.0 shipped `env()` for safe area insets, but iOS 11.0–11.2 used the now-deprecated `constant()` syntax. Devices on these versions will not understand `env()`.

**iOS version applicability:**  
- iOS 11.0–11.2: `constant()` only  
- iOS 11.3+: `env()` (constant() still works but is deprecated)  
- iOS 12+: `env()` only

**How it applies to shouldigetgas:**  
With iOS 11.0–11.2 representing an extremely small user share in 2026 (< 0.1%), this is a low-priority concern. The current `env()` usage is correct for all supported iOS versions.

**Recommendation:**  
No action required for 2026. If supporting iOS 11.0–11.2 were necessary, the pattern would be:
```css
/* iOS 11.0-11.2 only */
padding: constant(safe-area-inset-top) 0 0;
/* iOS 11.3+ */
padding: env(safe-area-inset-top, 0px) 0 0;
```
The two must be listed in this order (constant first, env second), as iOS 11.3 ignores `constant()` and only reads `env()`.

**Sources:**  
- https://webkit.org/blog/7929/designing-websites-for-iphone-x/

---

### 8. `-webkit-tap-highlight-color`

**What it is:**  
When users tap any clickable element on iOS, WebKit flashes a semi-transparent gray highlight. In native-app-style SPAs, this conflicts with custom `:active` states and looks broken.

**iOS version applicability:**  
All iOS versions. Non-standard but universally supported in WebKit.

**How it applies to shouldigetgas:**  
`styles.css` does **not** set `-webkit-tap-highlight-color`. Every button (`.chip`, `.icon-btn`, `.loc-item`, `.news-pill`, `.gb-btn`) will flash gray on tap, clashing with the custom `transform: scale(0.96)` active states already defined.

**Recommendation:**  
Add to the universal selector block in `styles.css`:
```css
* {
  -webkit-tap-highlight-color: transparent;
}
```
Ensure all interactive elements have visible `:active` CSS feedback (the app already has `transform: scale()` on `:active` — this is correct). Never remove tap highlight without providing an alternative visual response.

---

### 9. `touch-action: manipulation`

**What it is:**  
Declares that an element handles panning/tapping and does not use double-tap gestures. Eliminates any residual 300ms tap delay and prevents the browser from waiting to distinguish a single tap from a double-tap.

**iOS version applicability:**  
- iOS 9.3+: 300ms delay already eliminated by the viewport `width=device-width` meta tag, but `touch-action: manipulation` makes the intent explicit  
- iOS 12.1+: Verified no delay without the property on modern viewports

**How it applies to shouldigetgas:**  
`styles.css` has no `touch-action` declarations. While the delay is already eliminated on modern iOS by the viewport tag, adding `manipulation` is a belt-and-suspenders best practice.

**Recommendation:**  
Add to interactive elements:
```css
button, a, [role="button"], input, select, textarea {
  touch-action: manipulation;
}
```

**Sources:**  
- https://www.sitepoint.com/5-ways-prevent-300ms-click-delay-mobile-devices/

---

### 10. `overscroll-behavior` and Pull-to-Refresh

**What it is:**  
iOS Safari triggers a "pull-to-refresh" and elastic bounce when overscrolling. `overscroll-behavior` can suppress this. iOS support landed in Safari 16.

**iOS version applicability:**  
- iOS 16+: `overscroll-behavior` supported  
- iOS 15 and below: Not supported; the property is ignored

**How it applies to shouldigetgas:**  
The app uses `overflow: hidden` on `.site-wrap` on mobile, which largely suppresses scroll on the body level. However, the `.news-track` and `.sheet` inner containers scroll, and could trigger the elastic bounce. No `overscroll-behavior` is set anywhere.

**Recommendation:**  
```css
/* Prevent body-level pull-to-refresh */
body {
  overscroll-behavior-y: none;
}

/* Prevent scroll chaining on horizontal news track */
.news-track {
  overscroll-behavior-x: contain;
}

/* Allow the sheet to scroll but not chain to body */
.sheet {
  overscroll-behavior: contain;
}
```
Use `contain` (not `none`) on inner containers — `none` prevents the bounce but also kills the native "scroll past edge" affordance that tells users they've hit the end of a list.

**Sources:**  
- https://css-tricks.com/almanac/properties/o/overscroll-behavior/  
- https://developer.chrome.com/blog/overscroll-behavior/

---

### 11. `-webkit-overflow-scrolling: touch`

**What it is:**  
A legacy WebKit-only property that enabled momentum (inertial) scrolling on overflow containers. Removed from the spec and deprecated in iOS 13, where momentum scrolling became the default.

**iOS version applicability:**  
- iOS 5–12: Required for smooth scrolling in overflow containers  
- iOS 13+: Default behavior; property is a no-op  
- iOS 16+: Property is fully ignored

**How it applies to shouldigetgas:**  
The app does not use this property — correct. Do not add it.

**Recommendation:**  
No action required. Modern iOS scrolls smoothly by default. Do NOT add `-webkit-overflow-scrolling: touch` to new code.

---

### 12. `backdrop-filter` — Prefix and Performance

**What it is:**  
Blurs or applies other filters to content behind an element. GPU-intensive; can cause frame drops on older iPhones.

**iOS version applicability:**  
- iOS 9–17: Requires `-webkit-backdrop-filter`  
- iOS 18: Standard `backdrop-filter` works unprefixed  
- All iOS: Performance cost scales with blur radius and covered area

**How it applies to shouldigetgas:**  
`styles.css` correctly includes both prefixes on `.chip`, `.icon-btn`, `.loc-dropdown`, `.sheet`, and `.gb-btn`. The blur values range from `blur(6px)` to `blur(28px)`. The `.sheet` with `blur(28px)` over a full-width overlay is the heaviest operation.

**Recommendation:**  
The prefix pairing is correct. For performance on lower-end iPhones (SE, iPhone 11):
1. Reduce `.sheet`'s blur to `blur(16px)` — visually similar but cheaper  
2. Add `will-change: backdrop-filter` to hint GPU compositing on the elements that animate in/out  
3. Do not add `will-change` to static elements

**Sources:**  
- https://caniuse.com/css-backdrop-filter  
- https://www.testmuai.com/learning-hub/css-backdrop-filter-browser-support/

---

### 13. `text-wrap: balance` and `text-wrap: pretty`

**What it is:**  
New CSS properties for better multi-line text layout. `balance` evens line lengths; `pretty` prevents orphan words on the last line.

**iOS version applicability:**  
- `text-wrap: balance`: Safari 17.5+ (iOS 17.5+, June 2024)  
- `text-wrap: pretty`: Safari 18.2+ (iOS 18.2+)

**How it applies to shouldigetgas:**  
`styles.css` uses `text-wrap: balance` on `.verdict-word` and `text-wrap: pretty` on `.why`. Both are supported on current iOS 18. On older iOS, the properties are ignored and text wraps normally — graceful degradation.

**Recommendation:**  
Current usage is correct. No changes needed.

**Sources:**  
- https://webkit.org/blog/15383/webkit-features-in-safari-17-5/  
- https://caniuse.com/css-text-wrap-balance

---

### 14. Scroll Snap (`scroll-snap-type`) in iOS Safari

**What it is:**  
CSS scroll snapping aligns scroll positions to defined snap points, giving carousels and horizontal lists a native feel.

**iOS version applicability:**  
- iOS 11+: Full support  
- iOS 9.3–10.3: Partial support (older `-webkit-` prefixed spec)

**How it applies to shouldigetgas:**  
`.news-track` uses `scroll-snap-type: x mandatory` and `.news-card` uses `scroll-snap-align: start`. This works correctly on iOS 11+.

**Recommendation:**  
No changes needed. For maximum compatibility with any remaining iOS 9–10 devices (< 0.1% in 2026), no prefixed version is worth adding.

---

## Part 2: Progressive Web App (PWA) Requirements

### 15. Apple-Specific PWA Meta Tags

**What it is:**  
iOS uses `<meta name="apple-mobile-web-app-*">` tags rather than (or in addition to) the Web App Manifest to configure home screen behaviour. Without these, an installed shortcut behaves like a regular Safari bookmark — no standalone chrome, no custom status bar, no custom icon.

**iOS version applicability:**  
- iOS 11.3+: `apple-mobile-web-app-capable` enables standalone mode  
- iOS 15.4+: Web App Manifest is preferred; meta tags still work as override

**How it applies to shouldigetgas:**  
`index.html` has **none** of these tags. If a user adds the app to their home screen today, they get a bare Safari tab — address bar visible, browser controls present, no app-like experience.

**Recommendation:**  
Add to `index.html` `<head>`:
```html
<!-- PWA: iOS Home Screen support -->
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
<meta name="apple-mobile-web-app-title" content="Gas Prices" />

<!-- Touch icon (iOS uses this for the home screen icon) -->
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />
<link rel="apple-touch-icon" sizes="167x167" href="/apple-touch-icon-167.png" />
<link rel="apple-touch-icon" sizes="152x152" href="/apple-touch-icon-152.png" />
```

**Status bar style options:**
| Value | Effect |
|---|---|
| `default` | White bar, black text — content starts below status bar |
| `black` | Black bar, white text — content starts below status bar |
| `black-translucent` | Transparent bar, white text — content extends to top edge (use with `viewport-fit=cover`) |

For this app's dark `#0a0b0e` background, `black-translucent` is the right choice — it lets the dark background show through the status bar for a seamless look.

**Required icon sizes:**
- 180×180px: iPhone (required — iOS 9+)
- 167×167px: iPad Pro
- 152×152px: iPad, iPad mini

**Sources:**  
- https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariWebContent/ConfiguringWebApplications/ConfiguringWebApplications.html

---

### 16. Web App Manifest

**What it is:**  
The W3C standard JSON file for configuring installable web apps. iOS 15.4+ supports it, but Apple's implementation is still partial — many fields like `shortcuts`, `protocol_handlers`, and `share_target` are ignored. Crucially, iOS 16.4+ added `id` for tracking installs.

**iOS version applicability:**  
- iOS 15.4+: Basic manifest support (name, icons, display, start_url)  
- iOS 16.4+: `id` field, improved icon handling  
- iOS 18: Broader support, still no `shortcuts` or `share_target`

**How it applies to shouldigetgas:**  
No manifest exists in the project. Without one, Chrome/Android users also cannot install the app, and lighthouse scores are penalised.

**Recommendation:**  
Create `frontend/manifest.json`:
```json
{
  "id": "/",
  "name": "Should I Get Gas?",
  "short_name": "Gas Prices",
  "description": "AI-powered gas price timing advice. Know when to fill up, not just where.",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "orientation": "portrait-primary",
  "theme_color": "#0a0b0e",
  "background_color": "#0a0b0e",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
```

Link in `index.html`:
```html
<link rel="manifest" href="/manifest.json" />
```

**iOS-specific note:** iOS ignores `orientation`, `shortcuts`, `protocol_handlers`, and `share_target`. Use the `apple-mobile-web-app-*` meta tags (§15) alongside the manifest for full iOS coverage.

**Sources:**  
- https://web.dev/learn/pwa/enhancements  
- https://firt.dev/notes/pwa-ios/  
- https://brainhub.eu/library/pwa-on-ios

---

### 17. iOS Standalone Mode Quirks

**What it is:**  
When launched from the home screen (`display: standalone`), iOS removes browser chrome but also removes certain browser capabilities. These are not bugs — they are deliberate constraints.

**iOS version applicability:**  
iOS 11.3+ for all items below. iOS 16.4+ for push notifications.

**Known breakages in standalone mode:**

| Feature | Behaviour | Workaround |
|---|---|---|
| `target="_blank"` links | Opens in an in-app browser overlay, not Safari | Use `rel="noopener noreferrer"`; consider `window.location.href` for external links |
| `window.open()` | Blocked silently | Use `<a>` tags with `href` instead |
| Status bar scroll-to-top tap | Does not work unless `overflow-y: auto` is on `body` | Ensure body is the scroll container, or implement a custom scroll-to-top button |
| History navigation | Back/forward is unavailable (no browser controls) | Implement in-app navigation with `history.pushState()` or a routing library |
| Share sheet | No native share button | Implement a custom share button using `navigator.share()` |
| Cookie behaviour | Third-party cookies blocked; first-party work | Avoid third-party authentication flows |
| Clipboard | Works with user gesture | No change required |

**How it applies to shouldigetgas:**  
The app currently has no external links reviewed in the provided code, but any GasBuddy or news links rendered in components would be affected. The `.gb-btn` almost certainly opens an external URL.

**Recommendation:**  
```jsx
// For external links in React components:
const openExternal = (url) => {
  // In standalone mode, this opens in Safari (correct behaviour)
  // In browser mode, this opens a new tab
  window.open(url, '_blank', 'noopener,noreferrer');
};
```

Detect standalone mode to show a "Share" button:
```javascript
const isStandalone =
  window.navigator.standalone === true ||
  window.matchMedia('(display-mode: standalone)').matches;
```

**Sources:**  
- https://www.magicbell.com/blog/pwa-ios-limitations-safari-support-complete-guide  
- https://mobiloud.com/blog/progressive-web-apps-ios

---

### 18. `display-mode: standalone` CSS Detection

**What it is:**  
A CSS media query that detects when the app is running as an installed PWA (from home screen).

**iOS version applicability:**  
- iOS 15.4+: `@media (display-mode: standalone)` works  
- iOS 11.3–15.3: `window.navigator.standalone` JS property works; CSS media query does not

**How it applies to shouldigetgas:**  
The app could hide the "Add to Home Screen" prompt or adjust padding when already running standalone.

**Recommendation:**  
```css
@media (display-mode: standalone) {
  /* App is running installed — no browser chrome */
  .site-wrap {
    /* Remove any browser-specific padding; rely on env() safe areas */
  }
  
  /* Optionally show an in-app back button or navigation bar */
  .standalone-only {
    display: flex;
  }
}
```

Combine with JS for older iOS:
```javascript
const isStandalone =
  window.navigator.standalone === true ||
  window.matchMedia('(display-mode: standalone)').matches;

if (isStandalone) {
  document.documentElement.setAttribute('data-standalone', 'true');
}
```

---

### 19. `apple-touch-startup-image` (Splash Screens)

**What it is:**  
Historically, iOS used `<link rel="apple-touch-startup-image">` to show a custom splash screen during app launch from the home screen. Apple deprecated these tags in iOS 16.4+ when it gained manifest-based splash screen support.

**iOS version applicability:**  
- iOS 11.3–16.3: `apple-touch-startup-image` required per device resolution  
- iOS 16.4+: Splash screen is auto-generated from the manifest's `background_color` and `icons`

**How it applies to shouldigetgas:**  
No splash images exist in the project. On iOS 16.4+, a basic splash is auto-generated from the manifest (§16). For iOS 11.3–16.3, no custom splash is shown — the app shows a white screen briefly.

**Recommendation:**  
For iOS 16.4+, rely on the manifest `background_color: "#0a0b0e"` for the splash. For pre-16.4 support, consider using a tool like [pwa-asset-generator](https://github.com/elegantapp/pwa-asset-generator) to generate all required splash image sizes automatically (there are 30+ required sizes for full iOS coverage).

---

### 20. Service Worker on iOS — Current State (June 2026)

**What it is:**  
Service workers enable offline caching, push notifications, and background operations. iOS added service worker support in iOS 11.3 but has historically lagged Chrome's implementation significantly.

**iOS version support matrix (June 2026):**

| Feature | iOS 16 | iOS 17 | iOS 18 |
|---|---|---|---|
| Service Worker (basic) | ✓ | ✓ | ✓ |
| Cache API | ✓ | ✓ | ✓ |
| Background Sync | ✗ | ✗ | ✗ |
| Background Fetch | ✗ | ✗ | Partial |
| Web Push (installed PWA only) | iOS 16.4+ | ✓ | ✓ |
| Periodic Background Sync | ✗ | ✗ | ✗ |
| Silent Push (data-only) | ✗ | ✗ | ✗ |
| Push without display | ✗ | ✗ | ✗ |

**iOS SW lifetime:**  
iOS terminates service workers aggressively. An SW that hasn't been needed recently may be killed and restarted on next fetch. Do not rely on in-memory SW state persisting.

**Push notification requirements (iOS 16.4+):**
1. HTTPS required  
2. App must be installed to home screen (does NOT work from a Safari tab)  
3. User must grant permission (must be triggered by user gesture)  
4. Every push must show a notification — no silent/data-only pushes  
5. Web push uses VAPID keys like on desktop

**How it applies to shouldigetgas:**  
The app has no service worker. The `data/data.json` file is the only dynamic content — it changes every 30 minutes. A basic cache-first service worker would make the app work offline with the last known prices.

**Recommendation:**  
A minimal SW for shouldigetgas (`frontend/sw.js`):
```javascript
const CACHE = 'shouldigetgas-v1';
const STATIC = [
  '/',
  '/index.html',
  '/css/styles.css',
  '/js/app.js',
  '/js/components.js',
  '/js/data.js',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // data.json: network-first (fresh prices), fall back to cache
  if (url.pathname.endsWith('data.json')) {
    e.respondWith(
      fetch(e.request)
        .then(r => { caches.open(CACHE).then(c => c.put(e.request, r.clone())); return r; })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Static assets: cache-first
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
```

Register in `index.html`:
```html
<script>
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(console.error);
  }
</script>
```

**Sources:**  
- https://pwa.io/articles/web-push-with-ios-safari-16-4-made-easy  
- https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers  
- https://www.magicbell.com/blog/using-push-notifications-in-pwas

---

## Part 3: Cross-Browser SPA Best Practices

### 21. Viewport Meta Tag — Complete Correct Form

**What it is:**  
The `<meta name="viewport">` tag controls how mobile browsers scale and display the page. The current app uses a minimal form.

**Recommendation:**  
Update `index.html` to:
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
```

`interactive-widget=resizes-content` is a Chrome Android feature (not supported on iOS) that controls how the virtual keyboard affects the viewport. On iOS, `100dvh` handles this instead. Omit it from the viewport meta; it does nothing on Safari and has no effect on the app's current architecture.

---

### 22. Touch Target Size (Apple HIG: 44×44pt Minimum)

**What it is:**  
Apple's Human Interface Guidelines and WCAG 2.5.5 both recommend a minimum touch target of 44×44pt (≈ 44×44px on 1x screens, proportionally larger on Retina). Small targets cause mis-taps and reduce accessibility.

**How it applies to shouldigetgas:**  

| Element | Current size | Compliant? |
|---|---|---|
| `.icon-btn` | 36×36px | ✗ (8px short) |
| `.day-cell` (mobile) | 22×22px | ✗ (22px short) |
| `.news-dot` | 6px height | ✗ (decorative, not interactive) |
| `.chip` | 36px height approx. | Borderline |
| `.loc-item` | ~40px height | Close |

**Recommendation:**  
```css
/* Increase icon buttons to meet the 44px minimum */
.icon-btn {
  width: 44px;
  height: 44px;
}

/* Day cells are too small — expand tap area with padding */
.day-col {
  padding: 8px 2px; /* Increases tap area without changing visual size */
}
```

For very small decorative elements that are also interactive, use `padding` or `::after` pseudo-elements to expand the tap area without affecting layout:
```css
.news-dot {
  position: relative;
}
.news-dot::after {
  content: '';
  position: absolute;
  inset: -8px;
}
```

---

### 23. Pull-to-Refresh Handling

**What it is:**  
iOS Safari's pull-to-refresh (overscroll bounce) can accidentally reload the page or create a confusing UX in a SPA that manages its own data refresh.

**How it applies to shouldigetgas:**  
The app is a single-page app where data is loaded once on mount (`loadGasData()`). Accidental pull-to-refresh in the location sheet or news track would reload the page, losing any user selections.

**Recommendation:**  
```css
html, body {
  overscroll-behavior-y: none; /* Disable pull-to-refresh on body (iOS 16+) */
}
```

For a custom pull-to-refresh implementation (future feature), intercept `touchstart`/`touchmove` events manually — `overscroll-behavior: none` blocks the native gesture completely.

---

### 24. Scroll Position Preservation

**What it is:**  
SPAs that hide/show sections (like the sheet overlay) can inadvertently reset scroll positions. iOS Safari also restores scroll positions on back-navigation, which may conflict with programmatic scroll management.

**How it applies to shouldigetgas:**  
When the `.sheet` opens, `html, body` has `overflow: hidden` on mobile (preventing background scroll). When the sheet closes, scroll position must be restored. If not handled, the page jumps to the top.

**Recommendation:**  
Save and restore scroll position around sheet open/close:
```javascript
let savedScrollY = 0;

function openSheet() {
  savedScrollY = window.scrollY;
  document.body.style.top = `-${savedScrollY}px`;
  document.body.classList.add('sheet-open'); /* applies overflow:hidden */
}

function closeSheet() {
  document.body.classList.remove('sheet-open');
  document.body.style.top = '';
  window.scrollTo(0, savedScrollY);
}
```

---

### 25. External Link Behaviour in SPAs

**What it is:**  
Links that navigate to external domains should open in a new tab (browser) or in Safari (standalone). Internal navigation should be handled without full page reloads.

**How it applies to shouldigetgas:**  
The GasBuddy button (`.gb-btn`) and any news source links (`.news-src`) open external sites. In standalone mode, `target="_blank"` opens an in-app browser overlay rather than Safari.

**Recommendation:**  
```jsx
// In React components — external links
<a
  href={url}
  target="_blank"
  rel="noopener noreferrer"
  onClick={(e) => {
    // In standalone mode, force open in Safari via location
    if (window.navigator.standalone) {
      e.preventDefault();
      window.location.href = url;
    }
  }}
>
  {children}
</a>
```

---

### 26. Keyboard Avoidance — `visualViewport` API

**What it is:**  
When the iOS keyboard opens, `window.innerHeight` stays unchanged, but `window.visualViewport.height` shrinks. This lets JavaScript detect the keyboard height and reposition fixed elements accordingly.

**iOS version applicability:**  
iOS 13+ for `visualViewport` API. iOS 18: stable.

**How it applies to shouldigetgas:**  
The `.loc-search` input lives inside `.sheet` (a `position: fixed` bottom sheet). When the keyboard opens, the sheet may be partially obscured by the keyboard.

**Recommendation:**  
```javascript
// In the React component that manages the location sheet
useEffect(() => {
  if (!window.visualViewport) return;

  const onViewportResize = () => {
    const sheet = document.querySelector('.sheet');
    if (!sheet) return;
    const keyboardHeight = window.innerHeight - window.visualViewport.height;
    sheet.style.paddingBottom = `${keyboardHeight + 28}px`; // 28px = base padding
  };

  window.visualViewport.addEventListener('resize', onViewportResize);
  return () => window.visualViewport.removeEventListener('resize', onViewportResize);
}, [sheetOpen]);
```

Alternatively, `100dvh` (already used) naturally excludes the keyboard from the viewport height, which is simpler and works for most cases.

**Sources:**  
- https://dev.to/franciscomoretti/fix-mobile-keyboard-overlap-with-visualviewport-3a4a  
- https://tkte.ch/articles/2019/09/23/safari-13-mobile-keyboards-and-the-visualviewport-api.html

---

### 27. Loading State — Skeleton vs. Spinner

**What it is:**  
The app currently shows a pulsing dots loading screen while `data.json` fetches. Skeleton screens (shape placeholders that match the layout) are preferable for perceived performance.

**How it applies to shouldigetgas:**  
The current `.loading-screen` is a centred spinner. On mobile with a 4G connection, `data.json` loads in 200–500ms. The pulsing dots appear very briefly — no problem. On slow 3G or cold cache, the spinner shows for 2–3 seconds.

**Recommendation:**  
For the current load time profile, the dots spinner is acceptable. If fetch times increase (e.g., with a backend API), switch to a skeleton that mirrors the hero layout:
```css
.skeleton-price {
  height: 80px;
  width: 60%;
  border-radius: 8px;
  background: linear-gradient(90deg, rgba(255,255,255,0.08) 25%, rgba(255,255,255,0.16) 50%, rgba(255,255,255,0.08) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

---

### 28. `-webkit-user-select` for App-Like Feel

**What it is:**  
Prevents text selection on non-text elements (labels, buttons, icons), which would otherwise trigger an iOS callout (the "Copy / Look Up / Share" popup) on long-press.

**iOS version applicability:**  
All iOS versions. Standard `user-select` now works in Safari 15.3+.

**How it applies to shouldigetgas:**  
UI elements like `.chip`, `.verdict-word`, `.eyebrow`, and day labels should not be selectable. Currently nothing prevents the iOS selection callout from appearing on long-press.

**Recommendation:**  
```css
/* Non-content UI elements */
.chip, .icon-btn, .topbar, .verdict-word, .eyebrow,
.day-cell, .day-tick, .sup-label, .advice, .delta,
.sheet-grab, .brand {
  -webkit-user-select: none;
  user-select: none;
}

/* Ensure text content remains selectable */
.why, .news-head, .ctx-v {
  -webkit-user-select: text;
  user-select: text;
}
```

---

## Part 4: Performance on Mobile

### 29. React 18 UMD Dev Builds vs. Production

**What it is:**  
The app loads React 18 **development** builds from unpkg. Dev builds include warnings, prop-type checks, and debugging infrastructure that doubles the file size and adds runtime overhead.

**File size comparison (uncompressed):**

| File | Dev | Production | Savings |
|---|---|---|---|
| `react.js` | ~1,300 KB | ~11 KB | −98% |
| `react-dom.js` | ~4,800 KB | ~160 KB | −97% |
| **Total** | ~6.1 MB | ~171 KB | −97% |

Over a slow 4G connection (10 Mbps), dev builds add ~4.9 seconds of download.

**How it applies to shouldigetgas:**  
`index.html` loads:
```html
<script src="https://unpkg.com/react@18.3.1/umd/react.development.js" ...>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" ...>
```
These are the development builds.

**Recommendation:**  
Switch to production builds in `index.html`. Note: new SRI hashes are required.
```html
<script src="https://unpkg.com/react@18.3.1/umd/react.production.min.js"
  crossorigin="anonymous"></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js"
  crossorigin="anonymous"></script>
```
This is the **single highest-impact performance change** available to this project.

**Sources:**  
- https://legacy.reactjs.org/docs/optimizing-performance.html  
- https://app.unpkg.com/react@18.3.1/files/umd

---

### 30. Babel Standalone — Elimination Strategy

**What it is:**  
Babel standalone 7.29.0 (~2 MB compressed, ~8 MB uncompressed) is loaded to compile JSX in the browser on every page load. This is appropriate for demos and development but is the **wrong approach for production**.

**Performance cost:**
- Download: ~2 MB (even compressed)  
- CPU time: 100–500ms on-device JSX compilation on each page load  
- Combined with dev React: total cold-load JS parse/exec burden is ~8–10 MB

**How it applies to shouldigetgas:**  
`index.html` loads `@babel/standalone@7.29.0` to process `type="text/babel"` script tags.

**Recommendation — Option A: Pre-compile JSX (strongly recommended)**  
Use esbuild as a one-step build tool. Install as a dev dependency (not in `requirements.txt` — this is a `package.json` dev dep):
```bash
npm init -y
npm install -D esbuild
```

Create `build.mjs`:
```javascript
import * as esbuild from 'esbuild';

await esbuild.build({
  entryPoints: ['frontend/js/app.js'],
  bundle: false,       // keep files separate; they reference global React
  outdir: 'frontend/js/dist',
  loader: { '.js': 'jsx' },
  minify: true,
  target: ['safari16'],
});
```

Update `index.html` to load compiled files:
```html
<!-- Remove Babel -->
<!-- <script src="...babel..."></script> -->

<!-- Load compiled JS (no type="text/babel") -->
<script src="js/dist/data.js" defer></script>
<script src="js/dist/components.js" defer></script>
<script src="js/dist/app.js" defer></script>
```

This saves ~2 MB per page load and eliminates all in-browser compilation overhead.

**Recommendation — Option B: Keep Babel, load asynchronously**  
If the zero-build constraint must be maintained:
```html
<!-- Load Babel async — doesn't block first paint -->
<script async src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js"
  onload="Babel.transformElement(document.body)"></script>
```
This is a compromise; the JSX still compiles in the browser but doesn't block the initial render.

**Sources:**  
- https://babeljs.io/docs/babel-standalone  
- https://esbuild.github.io/

---

### 31. Critical Rendering Path — Font Loading

**What it is:**  
Google Fonts are render-blocking when loaded synchronously. The app currently preconnects to Google's servers but loads fonts in the `<head>` with a standard `<link>`. With `display=swap`, text renders immediately with a fallback font, then swaps — but the font files still block `LCP` if not preloaded.

**How it applies to shouldigetgas:**  
`index.html` loads Bricolage Grotesque and Hanken Grotesk. Bricolage Grotesque is used only for the giant `88px` `.verdict-word` — this is the app's primary Largest Contentful Paint element.

**Recommendation:**  
Add `rel="preload"` for the Bricolage Grotesque WOFF2 to front-load the key display font:
```html
<!-- Preconnect (already present) -->
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />

<!-- Preload the display font for LCP -->
<link rel="preload" as="font" type="font/woff2" crossorigin
  href="https://fonts.gstatic.com/s/bricolagegrotesque/v...woff2" />

<!-- Font stylesheet -->
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700;800&family=Hanken+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet" />
```

Note: the WOFF2 URL for preloading must be the exact hash URL from the Google Fonts CSS response — it changes per user agent/subset. An alternative is to self-host the WOFF2 files.

**Sources:**  
- https://www.debugbear.com/blog/ensure-text-remains-visible-during-webfont-load  
- https://www.debugbear.com/blog/web-font-layout-shift

---

### 32. CDN vs. Self-Hosting for React/Babel

**What it is:**  
Loading React from unpkg.com means the browser must resolve `unpkg.com`, negotiate TLS, and download. With HTTP/2 and CDN caching, this is usually fast — but it introduces a third-party dependency.

**Recommendation:**  
Self-hosting React production builds alongside the `frontend/` directory eliminates the dependency on unpkg and enables the Vercel CDN to serve React with the same cache headers as the rest of the app. If esbuild bundling (§30) is adopted, React can be bundled directly into the output — eliminating the separate React CDN request entirely.

---

### 33. Image and Icon Optimization

**What it is:**  
The app has no images in the current codebase, but adding PWA icons requires correctly sized and formatted files. All icons should use PNG (JPEG is not supported by iOS for touch icons).

**Recommendation for PWA assets:**
- Use square PNGs with transparent or `#0a0b0e` dark background  
- Icons for iOS should NOT use adaptive icon features (those are Android-only)  
- Use a tool like [realfavicongenerator.net](https://realfavicongenerator.net) or pwa-asset-generator to produce all sizes from a single master SVG

---

## Part 5: iOS-Specific Issues & Workarounds

### 34. iOS `position: fixed` + Keyboard Interaction

**What it is:**  
When the iOS virtual keyboard opens, fixed-positioned elements can "jump" because iOS repaints them relative to the pre-keyboard layout viewport. This is distinct from the address bar issue (§3).

**iOS version applicability:**  
All iOS versions. Improved but not fully fixed in iOS 18.

**How it applies to shouldigetgas:**  
`.sheet-overlay { position: fixed; inset: 0 }` and `.toast { position: fixed; bottom: 28px }` are both vulnerable. If the `.loc-search` input (inside the sheet) receives focus and the keyboard opens, the sheet may shift or clip.

**Recommendation:**  
The safest fix is to use the Visual Viewport API (§26) to adjust the sheet's `bottom` value when the keyboard appears:
```javascript
if (window.visualViewport) {
  window.visualViewport.addEventListener('resize', () => {
    const keyboardOffset = window.innerHeight - window.visualViewport.height;
    document.querySelector('.sheet').style.transform =
      `translateY(-${keyboardOffset}px)`;
  });
}
```

Alternatively, ensure `.loc-search` is positioned high enough in the sheet that the keyboard does not cover it even without JS compensation.

---

### 35. iOS LocalStorage / IndexedDB Size Limits

**What it is:**  
iOS enforces a storage quota per origin. LocalStorage is limited to ~5MB (same as desktop). IndexedDB can use up to ~50MB. However, **Safari aggressively purges storage after 7 days of no site visits** (ITP — Intelligent Tracking Prevention). Standalone installed apps are exempt from ITP purge.

**iOS version applicability:**  
- iOS 12+: ITP storage purge (7-day rule for Safari browser sessions)  
- iOS 14.5+: Stronger ITP; even first-party localStorage can be purged  
- Standalone PWA: Exempt from 7-day purge

**How it applies to shouldigetgas:**  
If the app stores user preferences (selected region, theme) in `localStorage`, these may disappear for users who don't visit the site for 7 days. The `data.json` cache in a service worker (IndexedDB-backed) is subject to the same purge if the SW is not in standalone mode.

**Recommendation:**  
1. Design the app to work without persisted preferences (sensible defaults from IP geolocation already handle the region case)  
2. For the service worker cache, accept that it may be purged and implement a graceful fallback (re-fetch from network)  
3. Encourage users to install the app to the home screen to avoid ITP purge

**Sources:**  
- https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/

---

### 36. CSS `clamp()` and `min()`/`max()` Support

**iOS version applicability:** iOS 13.1+ fully, iOS 11.3+ partially.

**How it applies to shouldigetgas:**  
`styles.css` already uses `clamp()` correctly for responsive typography:
```css
.price-number { font-size: clamp(48px, 13vw, 68px); }
.verdict-word { font-size: clamp(64px, 18vw, 88px); }
```
This is correct and well-supported. No changes needed.

---

### 37. iOS Audio Autoplay Restrictions

**What it is:**  
iOS requires user interaction before any audio can play. `AudioContext` is also locked until user interaction. Relevant for future features (e.g., an audio price alert).

**How it applies to shouldigetgas:**  
Not currently relevant. Note for future feature work: any audio feature must be triggered directly by a user tap (not a setTimeout or programmatic call).

---

### 38. Cookie Behaviour in Standalone Mode

**What it is:**  
When running as a standalone PWA (installed to home screen), iOS treats the app as a separate browser context. Cookies are not shared between Safari and the standalone app — they have separate cookie jars.

**How it applies to shouldigetgas:**  
The current app makes no use of cookies (pure static frontend + IP geolocation). If authentication or user sessions are added, this isolation must be handled — users would need to log in separately in the standalone app vs. Safari.

---

## Priority Summary

### Priority 1 — Critical (Fix before next deploy)

| # | Issue | File | Fix |
|---|---|---|---|
| 1 | Missing `viewport-fit=cover` — `env()` values all resolve to 0px | `index.html` | Add to viewport meta |
| 2 | Input font-size 15px triggers iOS auto-zoom | `styles.css` | `.loc-search { font-size: 16px }` |
| 3 | React dev builds — ~6MB vs 171KB for production | `index.html` | Switch to `.production.min.js` URLs |
| 4 | `overflow: hidden` on `.site-wrap` breaks `position: sticky` on topbar | `styles.css` | Change to `overflow: clip` or restructure scroll container |

### Priority 2 — High Impact (Next sprint)

| # | Issue | File | Fix |
|---|---|---|---|
| 5 | Babel standalone ~2MB in-browser compilation | `index.html` | Pre-compile JSX with esbuild |
| 6 | Missing `-webkit-text-size-adjust: 100%` | `styles.css` | Add to `html {}` |
| 7 | No `-webkit-tap-highlight-color: transparent` | `styles.css` | Add to `* {}` |
| 8 | No `touch-action: manipulation` | `styles.css` | Add to interactive elements |
| 9 | No PWA meta tags — home screen installs behave as plain Safari tabs | `index.html` | Add `apple-mobile-web-app-*` meta tags |

### Priority 3 — PWA Foundation

| # | Issue | Files | Fix |
|---|---|---|---|
| 10 | No Web App Manifest | New: `frontend/manifest.json` | Create manifest; link in HTML |
| 11 | No service worker — no offline support | New: `frontend/sw.js` | Implement cache-first SW |
| 12 | No apple-touch-icon | New PNG files | Create 180×180, 167×167, 152×152 icons |
| 13 | No `overscroll-behavior` — pull-to-refresh can reload the SPA | `styles.css` | Add `overscroll-behavior-y: none` to body |

### Priority 4 — Polish

| # | Issue | File | Fix |
|---|---|---|---|
| 14 | Touch targets below 44×44px (`.icon-btn` is 36px, `.day-cell` is 22px) | `styles.css` | Increase or expand tap areas |
| 15 | No `user-select: none` on non-text UI elements | `styles.css` | Add to buttons, labels, headers |
| 16 | iOS keyboard may obscure location search sheet | `app.js` component | Visual Viewport API compensation |
| 17 | `backdrop-filter: blur(28px)` on sheet may drop frames on low-end iPhones | `styles.css` | Reduce to `blur(16px)` |

---

## Sources

### iOS Safari & WebKit
- https://developer.apple.com/documentation/safari-release-notes  
- https://webkit.org/blog/  
- https://webkit.org/blog/7929/designing-websites-for-iphone-x/  
- https://webkit.org/blog/12445/new-webkit-features-in-safari-15-4/  
- https://webkit.org/blog/15383/webkit-features-in-safari-17-5/

### Viewport & Safe Area
- https://css-tricks.com/the-notch-and-css/  
- https://mohammadshehadeh.com/css/safe-area-insets/  
- https://medium.com/@tharunbalaji110/understanding-mobile-viewport-units-a-complete-guide-to-svh-lvh-and-dvh-0c905d96e21a  
- https://caniuse.com/viewport-unit-variants

### Input Zoom & Font Adjustment
- https://css-tricks.com/16px-or-larger-text-prevents-ios-form-zoom/  
- https://defensivecss.dev/tip/input-zoom-safari/  
- https://www.stefanjudis.com/notes/mobile-safari-doesnt-zoom-into-form-inputs-with-minimum-16px/  
- https://kilianvalkhof.com/2022/css-html/your-css-reset-needs-text-size-adjust-probably/  
- https://www.browserstack.com/guide/webkit-text-size-adjust

### Touch & Interaction
- https://www.sitepoint.com/5-ways-prevent-300ms-click-delay-mobile-devices/  
- https://css-tricks.com/practical-css-scroll-snapping/  
- https://css-tricks.com/almanac/properties/o/overscroll-behavior/  
- https://developer.chrome.com/blog/overscroll-behavior/

### Scrolling
- https://css-tricks.com/snippets/css/momentum-scrolling-on-ios-overflow-elements/  
- https://stripearmy.medium.com/i-fixed-a-decade-long-ios-safari-problem-0d85f76caec0

### Backdrop Filter
- https://caniuse.com/css-backdrop-filter  
- https://www.testmuai.com/learning-hub/css-backdrop-filter-browser-support/

### PWA & iOS Home Screen
- https://web.dev/learn/pwa/enhancements  
- https://www.magicbell.com/blog/pwa-ios-limitations-safari-support-complete-guide  
- https://brainhub.eu/library/pwa-on-ios  
- https://firt.dev/notes/pwa-ios/  
- https://www.mobiloud.com/blog/progressive-web-apps-ios  
- https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariWebContent/ConfiguringWebApplications/ConfiguringWebApplications.html

### Push Notifications & Service Workers
- https://pwa.io/articles/web-push-with-ios-safari-16-4-made-easy  
- https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers  
- https://documentation.onesignal.com/docs/en/web-push-for-ios  
- https://developer.apple.com/videos/play/wwdc2025/235/  
- https://www.magicbell.com/blog/using-push-notifications-in-pwas

### Keyboard & Visual Viewport
- https://dev.to/franciscomoretti/fix-mobile-keyboard-overlap-with-visualviewport-3a4a  
- https://tkte.ch/articles/2019/09/23/safari-13-mobile-keyboards-and-the-visualviewport-api.html  
- https://developer.mozilla.org/en-US/docs/Web/API/Visual_Viewport_API

### React & Build Tools
- https://legacy.reactjs.org/docs/optimizing-performance.html  
- https://app.unpkg.com/react@18.3.1/files/umd  
- https://esbuild.github.io/  
- https://babeljs.io/docs/babel-standalone

### Font Loading
- https://fonts.google.com/knowledge/using_type/using_web_fonts  
- https://www.debugbear.com/blog/ensure-text-remains-visible-during-webfont-load  
- https://www.debugbear.com/blog/web-font-layout-shift

### Storage & ITP
- https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/

### CSS Features
- https://caniuse.com/css-content-visibility  
- https://caniuse.com/mdn-css_at-rules_layer  
- https://caniuse.com/css-text-wrap-balance  
- https://caniuse.com/css-snappoints

---

*Research compiled 2026-06-07 — iOS 18 is the current platform release.*
