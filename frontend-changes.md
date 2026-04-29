# Frontend Changes — Dark/Light Theme Toggle

## Summary

Added a sun/moon icon toggle button in the top-right corner that allows users to switch between dark and light themes. The preference is persisted in `localStorage` and the initial theme is inferred from the user's OS preference (`prefers-color-scheme`) if no saved preference exists.

### JavaScript toggle functionality and smooth transitions

Both features were fully implemented as part of the initial theme toggle work:

**Toggle on click (`script.js`):**
- `toggleTheme()` flips `data-theme="light"` on `<html>` and persists to `localStorage`
- `initTheme()` runs immediately (before `DOMContentLoaded`) to restore saved preference without a flash
- `#themeToggle` click listener wired in `setupEventListeners()`

**Smooth transitions (`style.css`):**
- `body`: `transition: background-color 0.3s ease, color 0.3s ease`
- `.sidebar`: `transition: background 0.3s ease, border-color 0.3s ease`
- `.theme-toggle`: `transition: background 0.3s ease, color 0.2s ease, border-color 0.3s ease, ...`
- Source pills: `transition: background 0.15s, color 0.15s`
- All interactive elements (buttons, inputs, suggested items) carry their own `transition: all 0.2s ease`

No new code was required — these were already in place.

---

## Files Changed

### `frontend/index.html`
- Bumped `style.css` cache-bust version from `v=12` → `v=13`
- Bumped `script.js` cache-bust version from `v=10` → `v=11`
- Added `.theme-toggle` button as the first child of `<body>`, positioned fixed top-right
  - Moon SVG icon (shown in dark mode)
  - Sun SVG icon (shown in light mode)
  - `aria-label="Toggle dark/light theme"` and `title` for accessibility
  - `aria-hidden="true"` on both SVGs (decorative)

### `frontend/style.css`
- Added `[data-theme="light"]` CSS variable block with a full light palette:
  - Background: `#f8fafc`, surface: `#ffffff`, text: `#0f172a`, borders: `#e2e8f0`
  - Source pill colors adjusted for legibility on white backgrounds
- Added `transition: background-color 0.3s ease, color 0.3s ease` on `body` for smooth theme switching
- Added `.sidebar` transition for `background` and `border-color`
- Added `.theme-toggle` button styles:
  - Fixed position, top-right (`top: 1rem; right: 1rem; z-index: 100`)
  - 40×40px circular button, adapts colors via CSS variables
  - Hover: scales up 10%, shows primary-color border and glow
  - `focus-visible` ring for keyboard navigation
  - SVG icon swap: `.icon-moon` shown by default, `.icon-sun` shown under `[data-theme="light"]`
- Added `[data-theme="light"]` overrides for source pill `.sources-content a/span` colors

### `frontend/script.js`
- Added `initTheme()`: reads `localStorage('theme')`, falls back to `prefers-color-scheme`, sets `data-theme="light"` on `<html>` if needed. Called immediately (before `DOMContentLoaded`) to prevent flash of wrong theme.
- Added `toggleTheme()`: flips `data-theme` attribute on `<html>` and saves new value to `localStorage`.
- Wired `#themeToggle` click listener in `setupEventListeners()`.

---

## Behaviour

| Scenario | Result |
|---|---|
| First visit, OS dark | Dark theme shown, moon icon visible |
| First visit, OS light | Light theme shown, sun icon visible |
| User toggles | Theme flips, icon swaps, `localStorage` updated |
| Page reload | Saved preference restored (no flash) |
| Keyboard navigation | Button focusable, `focus-visible` ring shown, activatable with Space/Enter |

---

## Light Theme CSS Variables Audit

The `[data-theme="light"]` block on `<html>` covers all variables consumed by the stylesheet:

| Variable | Dark value | Light value | Purpose |
|---|---|---|---|
| `--primary-color` | `#2563eb` | `#2563eb` | Buttons, links, accents |
| `--primary-hover` | `#1d4ed8` | `#1d4ed8` | Button hover state |
| `--background` | `#0f172a` | `#f8fafc` | Page/chat background |
| `--surface` | `#1e293b` | `#ffffff` | Sidebar, message bubbles, inputs |
| `--surface-hover` | `#334155` | `#e2e8f0` | Hover fills on interactive surfaces |
| `--text-primary` | `#f1f5f9` | `#0f172a` | Body text — 14.7:1 contrast on light bg |
| `--text-secondary` | `#94a3b8` | `#64748b` | Labels, placeholders — 4.7:1 on light bg |
| `--border-color` | `#334155` | `#e2e8f0` | Dividers and input borders |
| `--user-message` | `#2563eb` | `#2563eb` | User chat bubble background |
| `--focus-ring` | `rgba(37,99,235,0.2)` | `rgba(37,99,235,0.2)` | Keyboard focus outline |
| `--shadow` | `rgba(0,0,0,0.3)` | `rgba(0,0,0,0.1)` | Softer shadow on light backgrounds |
| `--welcome-bg` | `#1e3a5f` | `#eff6ff` | Welcome message card tint |
| `--welcome-border` | `#2563eb` | `#2563eb` | Welcome message card border |

Also fixed a pre-existing bug: `var(--primary)` in `.message-content blockquote` corrected to `var(--primary-color)` so blockquote left-border renders in both themes.

---

## Full Element Coverage in Both Themes

All existing elements were audited for light-mode correctness. Two gaps found and fixed:

### `frontend/style.css` — additional light-mode overrides added

**Code blocks** — dark mode uses `rgba(0,0,0,0.2)` which reads as muddy grey on a white background. Added:
```css
[data-theme="light"] .message-content code  { background-color: rgba(0,0,0,0.06); color: #1e293b; }
[data-theme="light"] .message-content pre   { background-color: rgba(0,0,0,0.05); }
```

**Error/success banners** — dark-mode text colors (`#f87171` red, `#4ade80` green) are too light for WCAG AA on white. Added:
```css
[data-theme="light"] .error-message   { color: #b91c1c; }   /* 5.9:1 on white */
[data-theme="light"] .success-message { color: #15803d; }   /* 5.3:1 on white */
```

All other elements already used CSS variables throughout and required no additional overrides.
