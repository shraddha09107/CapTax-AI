# CapTax AI — Theme Color Audit & Worklist

**Date:** 2026-10-29  
**Scope:** `frontend/index.html` (CSS styles, HTML inline attributes, SVG artwork, JavaScript chart rendering)  
**Objective:** Document every color literal, hex code, rgb/rgba value, and gradient definition prior to refactoring into unified semantic tokens under `:root[data-theme="dark"]` and `:root[data-theme="light"]`.

---

## 1. Stack & Chart Library Detection

- **Architecture:** Pure semantic HTML5 + Modern CSS3 + Vanilla ES6+ JavaScript SPA (Single Page Application). Zero build step required.
- **Styling Paradigm:** CSS Custom Properties (Variables) with BEM-inspired naming and scoped components.
- **Chart & Visualization Implementation:** Zero external charting dependencies (no Chart.js, D3, or Canvas). Custom high-precision SVG vector charts (`<polyline>`, `<rect>`, `<path>`, `<circle>`, `<line>`) with animated gradients and hover state interactions.
- **Rule:** Maintain existing lightweight stack; migrate all hardcoded SVG and canvas fills to CSS variables (`var(--...)`) or computed property getters.

---

## 2. Raw Color Literals Inventory (`frontend/index.html`)

### A. Current CSS Variables & Global Rules (`<style>` lines 18–42)
| Variable / Selector | Current Literal | Semantic Role | Target Light Token |
|---|---|---|---|
| `--bg-dark` | `#0c0c0e` | App background | `--bg-app` (`#F3F1EE`) |
| `--card-bg` | `#121214` | Primary card background | `--bg-card` (`#FFFFFF`) |
| `--card-inner` | `#18181b` | Inset panels, inputs, subnav | `--bg-card-inset` (`#F7F5F2`) |
| `--card-hover` | `#1f1f23` | Interactive hover states | Derived inset hover |
| `--border-subtle` | `rgba(255, 255, 255, 0.08)` | Borders & table dividers | `--border-subtle` (`rgba(20,20,25,0.08)`) |
| `--border-accent` | `rgba(240, 80, 45, 0.35)` | Accent border borders | `--border-accent` (`rgba(240,80,45,0.3)`) |
| `--accent` | `#F0502D` | Primary brand orange | `--accent` (`#F0502D`) |
| `--accent-hover` | `#ff6342` | Primary button hover | `--accent-hover` (`#ff6342`) |
| `--accent-glow` | `rgba(240, 80, 45, 0.25)` | Orange button & card glow | Light box shadow variant |
| `--green` | `#10B981` | Gains, dividends, positive | `--positive` (`#12A150`) |
| `--green-glow` | `rgba(16, 185, 129, 0.2)` | Success indicator glow | `--positive-glow` |
| `--red` | `#F87171` | Losses, tax withheld | `--negative` (`#D93025`) |
| `--red-glow` | `rgba(248, 113, 113, 0.2)` | Warning glow | `--negative-glow` |
| `--yellow` | `#FBBF24` | DTAA notices, warnings | `--warning` (`#B45309`) |
| `--purple` | `#8B5CF6` | LTCG tax & foreign equity | `--chart-4` (`#7A4DF0`) |
| `--blue` | `#38BDF8` | Informational callouts | `--blue` (`#0284C7`) |
| `--text-main` | `#FFFFFF` | Primary headings & text | `--text-primary` (`#15151A`) |
| `--text-muted` | `#94A3B8` | Secondary labels & subheadings| `--text-secondary` (`#55555F`) |
| `--text-dim` | `#64748B` | Subtle captions & timestamps | `--text-muted` (`#8A8A94`) |

---

### B. Hardcoded CSS Color Literals in Component Classes
| Selector | Line(s) | Hardcoded Literals | Migration Action |
|---|---|---|---|
| `.brand-badge` | 117, 121 | `rgba(240, 80, 45, 0.15)`, `rgba(240, 80, 45, 0.3)` | Replace with `var(--accent-subtle)` & `var(--border-accent)` |
| `.nav-pill-group` | 134 | `box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4)` | Replace with `var(--shadow-card)` |
| `.nav-pill:hover` | 156 | `background: rgba(255, 255, 255, 0.04)` | Replace with `var(--bg-pill-hover)` |
| `.nav-pill.active` | 161 | `color: #FFFFFF` | Use `var(--accent-contrast)` |
| `.btn-run-pipeline` | 173, 174 | `linear-gradient(135deg, var(--accent) 0%, #d43818 100%)`, `#FFFFFF` | Replace `#d43818` with variable |
| `.icon-btn:hover` | 218 | `border-color: rgba(255, 255, 255, 0.2)` | Replace with `var(--border-hover)` |
| `.avatar-chip` | 237, 239 | `linear-gradient(135deg, #27272a 0%, #3f3f46 100%)`, `#FFFFFF` | Themed avatar background |
| `.curr-btn.active` | 271, 272 | `rgba(255, 255, 255, 0.1)`, `#FFFFFF` | Themed toggle active background |
| `.card` | 298, 303 | `rgba(0, 0, 0, 0.35)`, `rgba(255, 255, 255, 0.14)` | Use `var(--shadow-card)` & `var(--border-subtle)` |
| `.card-arrow-btn` | 330, 341 | `rgba(255, 255, 255, 0.04)`, `rgba(255, 255, 255, 0.1)` | Use `var(--bg-card-inset)` & hover variable |
| `.hero-card` | 355 | `linear-gradient(135deg, #131317 0%, #17171c 100%)` | Use `--hero-bg` (soft gradient for light) |
| `.hero-tag` | 385, 387 | `rgba(16, 185, 129, 0.12)`, `rgba(16, 185, 129, 0.25)` | Use `var(--positive-subtle)` |
| `.hero-amount` | 395, 396 | `#FFFFFF`, `rgba(0, 0, 0, 0.5)` | Use `var(--text-primary)`, eliminate text-shadow in light |
| `.hero-sub-pill` | 410, 413 | `rgba(255, 255, 255, 0.05)`, `rgba(255, 255, 255, 0.08)` | Use `var(--bg-card-inset)` |
| `.tx-ticker-badge` | 562, 570 | `rgba(255, 255, 255, 0.04)`, `#FFFFFF` | Use `var(--bg-card-inset)` & `var(--text-primary)` |
| `.tx-broker-tag` | 582, 584 | `#27272a`, `rgba(255, 255, 255, 0.15)` | Use `var(--bg-card)` & `var(--border-subtle)` |
| `.broker-mini-action`| 674, 687 | `rgba(255, 255, 255, 0.08)`, `#FFFFFF` | Use `var(--bg-card)` & `var(--text-primary)` |
| `.report-card` | 975 | `background: #09090b` | Use `var(--bg-card-inset)` |
| `.report-pre` | 1015, 1016 | `#e2e8f0`, `#050507` | Use `var(--text-primary)` & `var(--code-bg)` |
| `.stepper-step` | 1105, 1129 | `rgba(255, 255, 255, 0.08)`, `#0c0c0e` | Themed step connector line & text |
| `.settings-drawer` | 1202, 1210 | `#141417`, `rgba(0, 0, 0, 0.6)` | Use `var(--bg-card)` & `var(--shadow-drawer)` |
| `.drawer-overlay` | 1183 | `rgba(0, 0, 0, 0.7)` | Use `var(--overlay)` |
| `.offline-banner` | 1250, 1251 | `#7f1d1d`, `#991b1b`, `#fee2e2` | Keep distinct alert gradient with high contrast |
| `.toast` | 1279, 1281 | `#1e1e24`, `#FFFFFF` | Use `var(--bg-card-inset)` & `var(--text-primary)` |

---

### C. JavaScript Dynamic Chart Literals (`<script>` lines 2226–2758)
| Function | Lines | Literals in Template Strings | Migration Action |
|---|---|---|---|
| `renderLineChart()` | 2252, 2253 | `rgba(255,255,255,0.15)` (zero-line), `#64748B` | Use `var(--chart-grid)`, `var(--text-muted)` |
| `renderLineChart()` | 2256, 2259 | `#10B981` (LTCG line), `#F0502D` (STCG line) | Use `var(--chart-3)`, `var(--chart-1)` |
| `renderLineChart()` | 2270, 2273 | `#121214` (node border stroke) | Use `var(--bg-card)` |
| `renderLineChart()` | 2283, 2284 | `rgba(240,80,45,0.2)`, `#F0502D` (badge) | Use `var(--negative-subtle)`, `var(--negative)` |
| `renderBarChart()` | 2317, 2319 | `rgba(240,80,45,0.06)`, `#F0502D` (active frame) | Use `var(--accent-subtle)`, `var(--accent)` |
| `renderBarChart()` | 2330, 2333 | `#8B5CF6` (LTCG tax), `#F0502D` (STCG tax) | Use `var(--chart-4)`, `var(--chart-1)` |
| `renderBarChart()` | 2337 | `#fff`, `#94A3B8` (FY labels) | Use `var(--text-primary)`, `var(--text-muted)` |
| `renderTaxExposureGauge()` | 2424–2428 | `#10B981`, `#FBBF24`, `#F97316`, `#F0502D`, `#8B5CF6` | Speedometer color stops |
| `renderTaxExposureGauge()` | 2433 | `rgba(255,255,255,0.06)` (track) | Use `var(--gauge-track)` |
| `renderTaxExposureGauge()` | 2439, 2442 | `#121214`, `rgba(255,255,255,0.3)`, `#FFFFFF` (needle) | Use `var(--bg-card)`, `var(--text-primary)` |
| `renderInvestmentsPage()` | 2496 | `rgba(255,255,255,0.06)`, `#fff` | Use `var(--bg-card-inset)`, `var(--text-primary)` |
| `renderBrokersPage()` | 2532, 2539 | `#fff` | Use `var(--text-primary)` |

---

### D. SVG 3D Artwork Assets (`lines 1443–1488`)
- The 3D Wallet SVG contains linear gradients (`cardGrad1`, `cardGrad2`, `walletBody`, `claspGrad`) and coin styling.
- **Rule:** As noted in Step 2, the 3D graphic artwork itself is a brand visual asset. For the light theme, the backdrop card (`.hero-card`) will use a soft warm ambient gradient (`linear-gradient(135deg, #FFFFFF 0%, #F5F3EF 100%)`) without a dark vignette, and text will utilize `--text-primary`. The 3D drop-shadow filter will be tuned for light mode so it casts a clean, natural shadow rather than a heavy black halo.

---

## 3. Worklist & Execution Plan

1. **Step 1:** Create `frontend/styles/theme.css` with the complete token contract for both `:root[data-theme="dark"]` and `:root[data-theme="light"]`.
2. **Step 2:** Refactor `frontend/index.html` CSS rules to reference semantic variables exclusively.
3. **Step 3:** Update JavaScript chart rendering (`renderLineChart`, `renderBarChart`, `renderTaxExposureGauge`) to use CSS variable references so they dynamically adapt upon theme switch.
4. **Step 4:** Add Theme Switcher in Settings drawer (Light, Dark, System) with inline `<head>` script to eliminate flash-of-unthemed-content (FOUC) and listen to `prefers-color-scheme`.
5. **Step 5:** Validate WCAG AA contrast compliance for both modes.
6. **Step 6:** Capture multi-viewport desktop and mobile screenshots across all pages in both themes into `docs/theme-screenshots/`.

