# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** DocForge Enterprise
**Generated:** 2026-06-15 · **Revised:** 2026-06-21
**Category:** B2B Application (AI document drafting / review / collaboration)
**Surface:** In-app product UI (NOT a marketing site) — workspace, editor, chat, panels.

> Tokens below mirror the live Tailwind v4 `@theme` in `frontend/src/assets/main.css`.
> **Never hardcode hex in components** — use the theme utilities (`bg-primary`,
> `text-foreground`, `border-border`, …). Dark mode is first-class via `.dark`.

---

## Global Rules

### Color Tokens (Tailwind v4 `@theme` — single source of truth)

| Role | Light | Dark | Utility examples |
|------|-------|------|------------------|
| Primary (brand/authority navy) | `#1E3A8A` | `#3B82F6` | `bg-primary`, `text-primary`, `ring-primary` |
| Primary light | `#1E40AF` | `#60A5FA` | `hover:bg-primary-light` |
| Secondary | `#475569` | `#94A3B8` | `text-secondary` |
| CTA / Accent (trust gold) | `#B45309` | `#F97316` | `bg-cta`, `text-cta` |
| Danger | `#DC2626` | `#EF4444` | `text-danger`, `bg-danger` |
| Warning (also placeholder marks) | `#D97706` | `#FBBF24` | `text-warning`, `border-warning` |
| Surface (app background) | `#F8FAFC` | `#0F172A` | `bg-surface` |
| Foreground (text) | `#0F172A` | `#F1F5F9` | `text-foreground` |
| Card / panel | `#FFFFFF` | `#1E293B` | `bg-card` |
| Muted (secondary text) | `#64748B` | `#94A3B8` | `text-muted`, `text-foreground/70` |
| Border | `#E2E8F0` | `#334155` | `border-border`, `border-primary/10` |

**Color Notes:** Authority navy + trust gold. Single accent (CTA) — do not introduce
a second accent hue. No AI purple/pink gradients.

### Typography

- **Heading:** Lexend (`--font-heading`)
- **Body:** Source Sans 3 (`--font-sans`)
- **Mood:** corporate, trustworthy, accessible, readable, professional, clean
- **Editor body copy:** prefer a comfortable reading measure (`max-w-[70ch]`),
  `text-base`/`leading-relaxed`. Document content is the product — optimize legibility.
- **Google Fonts:** [Lexend + Source Sans 3](https://fonts.google.com/share?selection.family=Lexend:wght@300;400;500;600;700|Source+Sans+3:wght@300;400;500;600;700)

| Level | Size | Weight | Use |
|-------|------|--------|-----|
| Display | 32–40px | 600 | Empty states, onboarding |
| H1 | 24px | 600 | Page / workspace title |
| H2 | 20px | 600 | Section / panel header |
| H3 | 16px | 600 | Card / subsection |
| Body | 16px | 400 | Editor + UI text |
| Small | 14px | 400–500 | Metadata, captions, chips |
| Micro | 12px | 500 | Labels, badge text, source tags |

### Spacing (8px base)

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | 4px | Tight gaps, chip padding |
| `--space-sm` | 8px | Icon gaps, inline spacing |
| `--space-md` | 16px | Standard padding |
| `--space-lg` | 24px | Panel / section padding |
| `--space-xl` | 32px | Large gaps |
| `--space-2xl` | 48px | Major section margins |

### Radius & Elevation

| Token | Value | Usage |
|-------|-------|-------|
| `rounded-md` | 8px | Buttons, inputs, chips |
| `rounded-lg` | 12px | Cards, panels |
| `rounded-xl` | 16px | Modals |
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, dropdowns |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Popovers, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Modals |

> App UI favors **borders over heavy shadows** (Swiss/minimal). Reserve `lg`/`xl`
> shadows for floating layers (modals, popovers, command palette).

### Motion

- Transitions **150–250ms**, `transition-colors`/`transition-shadow` (avoid layout-shifting `transform: scale` on hover).
- Respect `prefers-reduced-motion`.

---

## App Layout Pattern (primary surface)

**Pattern Name:** Three-Pane Document Workspace

- **Shell:** persistent top bar (logo, doc title, status, user menu) + left rail.
- **Left:** Document Outline / source navigation (collapsible).
- **Center:** Tiptap/ProseMirror editor — the focal surface, max reading width, generous padding.
- **Right:** tabbed dock — Chat (co-drafting) ↔ Sources/Provenance ↔ Comments/Review.
- **Density:** information-dense but calm; group with borders + whitespace, not color.
- **Empty states:** explain the next action (upload sources, start chat), never a blank pane.

### Provenance & Placeholder visual language (signature feature)

Every generated span is **either sourced or an explicit placeholder** — the UI must
make this unmissable (a hallucinated clause is a liability).

| State | Visual | Token |
|-------|--------|-------|
| **Sourced** (provenance mark) | subtle primary underline / left border; hover reveals source title + confidence | `text-foreground`, `decoration-primary/40`, badge `bg-primary/10 text-primary` |
| **Placeholder** (`placeholderMark`) | dashed **warning** underline; chip "Da completare" | `decoration-dashed decoration-warning`, chip `bg-warning/10 text-warning border-warning/30` |
| **Confidence buckets** | high/medium/low → solid / medium / faint accent | high `text-primary`, medium `text-primary/70`, low `text-muted` |
| **Missing slot** (transparency line) | alert chip in chat: "Informazioni mancanti: …" | `bg-warning/10 text-warning` + `AlertTriangle` icon |
| **Understood intent** | one-line summary chip "Ho capito: <tipo> — fonti: …" | `bg-primary/8 text-primary` + `Info` icon |

---

## Component Specs (express in Tailwind v4 tokens)

> Snippets are reference utilities — apply via classes, not raw hex.

### Buttons

```html
<!-- Primary action (use CTA gold for the single most-important action per view) -->
<button class="bg-cta text-white px-4 py-2 rounded-md font-semibold
               transition-colors duration-200 hover:opacity-90
               focus-visible:ring-2 focus-visible:ring-cta cursor-pointer">
  Genera bozza
</button>

<!-- Primary brand (navigation / confirm) -->
<button class="bg-primary text-white px-4 py-2 rounded-md font-semibold
               transition-colors hover:bg-primary-light
               focus-visible:ring-2 focus-visible:ring-primary cursor-pointer">…</button>

<!-- Secondary / ghost -->
<button class="border border-primary text-primary px-4 py-2 rounded-md font-semibold
               transition-colors hover:bg-primary/8 cursor-pointer">…</button>
```

### Cards / Panels

```html
<div class="bg-card border border-border rounded-lg p-6
            transition-shadow duration-200 hover:shadow-md cursor-pointer">…</div>
```

### Inputs

```html
<input class="w-full bg-card text-foreground placeholder:text-muted
              border border-border rounded-md px-4 py-2
              focus:border-primary focus:ring-2 focus:ring-primary/30 outline-none
              transition-colors" />
```

### Chips / Tags (sources, slots, status)

```html
<span class="inline-flex items-center gap-1 text-xs font-medium
             bg-primary/10 text-primary rounded-md px-2 py-1">Fonte: NDA_acme.pdf</span>
```

### Modal

```html
<div class="fixed inset-0 bg-black/50 backdrop-blur-sm"></div>
<div class="bg-card text-foreground rounded-xl p-8 shadow-xl max-w-lg w-[90%]"></div>
```

---

## Style Guidelines

**Style:** Trust & Authority × Swiss/Minimal (enterprise app)

**Keywords:** rational grid, clear hierarchy, generous whitespace, single accent,
border-led separation, high contrast, credibility signals (provenance, confidence,
audit), zero decoration-for-decoration's-sake.

**Best For:** legal/contract drafting, enterprise document tooling, professional services.

**Key Effects:** calm color-shift hovers, smooth panel/tab transitions, source-mark
hover reveals, confidence/state reveals. No flashy motion.

---

## Anti-Patterns (Do NOT Use)

- ❌ Playful / vibrant block design (wrong audience for legal/document work)
- ❌ AI purple/pink gradients
- ❌ Hardcoded hex in components — use theme tokens
- ❌ A second accent color competing with the CTA gold
- ❌ Generated content that looks sourced without a provenance mark (must be marked sourced OR placeholder)
- ❌ Emojis as icons — use SVG (Lucide via `lucide-vue-next`)
- ❌ Missing `cursor-pointer` on clickable elements
- ❌ Layout-shifting hover (`scale` transforms)
- ❌ Low-contrast text (4.5:1 minimum); invisible borders/focus in dark mode
- ❌ Instant state changes (always 150–250ms transitions)
- ❌ Marketing-funnel chrome (Contact Sales heroes, client-logo carousels) inside the app

---

## Pre-Delivery Checklist

- [ ] No emojis as icons (Lucide SVG only)
- [ ] All colors via theme tokens (no raw hex)
- [ ] `cursor-pointer` + visible hover feedback on interactive elements
- [ ] Transitions 150–250ms; `prefers-reduced-motion` respected
- [ ] Contrast ≥ 4.5:1 in **both** light and dark mode; borders/focus visible in both
- [ ] Focus states visible for keyboard nav
- [ ] Sourced vs placeholder spans visually distinct (provenance vs dashed-warning)
- [ ] Responsive: 375 / 768 / 1024 / 1440; panels collapse gracefully on narrow widths
- [ ] No content hidden behind fixed top bar; no horizontal scroll on mobile
