# NASSAQ Product Intelligence Hub — Design System
# مركز ذكاء المنتج — نظام التصميم

Version: 1.0
Last Updated: 2026-04-01
Scope: Product Intelligence Hub (internal enterprise system)

---

## 1. Design Vision

The Product Intelligence Hub is a premium internal enterprise control center for issue governance, AI-assisted triage, and product quality intelligence.

**Visual Identity**: Calm, structured, authoritative. The interface communicates institutional credibility and operational precision. Every element exists to reduce cognitive load and accelerate decision-making.

**Target Feel**:
- Premium enterprise SaaS dashboard
- Calm operational control center
- Structured product intelligence workspace
- Intelligent but never flashy
- Refined and trustworthy

**Tone**: Serious, elegant, practical, modern, clear, quietly intelligent.

**What to Avoid**:
- Visual noise or over-decoration
- Crowded layouts or competing elements
- Excessive gradients or shadows
- Childish visuals, random icon sizes, inconsistent spacing
- Playful or gimmicky AI presentation
- Over-highlighting or excessive accent color usage

---

## 2. Design Principles

### 2.1 No-Brain UX
Users should immediately understand what to do. Important actions are obvious. Cognitive load is minimized at every level.

### 2.2 Progressive Disclosure
Reveal complexity only when needed. Avoid overwhelming forms and detail pages. Use collapsible sections, step-based flows, and contextual reveals.

### 2.3 Visual Hierarchy First
Title, status, priority, owner, and actions must always be easy to scan. The eye should follow a natural path: identification → status → context → actions.

### 2.4 Enterprise Clarity
Every card, badge, table, and interaction should feel structured and purposeful. No decorative-only elements.

### 2.5 AI Visibility with Restraint
Hakim AI components are clearly visible and differentiated, but never noisy, distracting, or playful. AI is a trusted advisor, not a mascot.

### 2.6 Bilingual Integrity
Arabic and English must both feel native and intentional. RTL/LTR are first-class design rules, not afterthoughts.

---

## 3. Color System

### 3.1 Brand Colors (Primary Palette)

| Token | Hex | HSL | Usage |
|---|---|---|---|
| `brand-navy` | `#1C3D74` | 217 61% 28% | Primary brand, headings, primary buttons, data emphasis |
| `brand-navy-light` | `#2a5096` | — | Hover states on navy elements |
| `brand-navy-dark` | `#152d57` | — | Active/pressed states |
| `brand-turquoise` | `#46C1BE` | 179 49% 51% | Accent, AI identity, CTAs, interactive highlights |
| `brand-turquoise-light` | `#5fd1ce` | — | Hover states on turquoise elements |
| `brand-turquoise-dark` | `#38a19e` | — | Active/pressed states |
| `brand-purple` | `#615090` | 255 29% 44% | Tertiary accent, in-progress status, secondary highlight |
| `brand-purple-light` | `#7a68a8` | — | Hover states |
| `brand-purple-dark` | `#4a3d70` | — | Active states |

### 3.2 Neutral Scale

| Token | Value | Usage |
|---|---|---|
| `brand-black` | `#312E2F` | Body text on white backgrounds |
| `brand-gray` | `#EAECED` | Dividers, light borders |
| `slate-50` | Tailwind default | Page backgrounds, empty area fills |
| `slate-100` | — | Table row dividers, subtle borders |
| `slate-200` | — | Default borders, inactive pill borders |
| `slate-300` | — | Disabled text, faint separators |
| `slate-400` | — | Placeholder text, low-priority dot |
| `slate-500` | — | Secondary text, muted labels |
| `slate-600` | — | Body text in data contexts |
| `slate-700` | — | Strong secondary text |
| `slate-900` | — | Code block backgrounds |

### 3.3 Semantic Colors

| Meaning | Solid | Light BG | Border | Text |
|---|---|---|---|---|
| **Success / Done** | `emerald-500` | `emerald-50` | `emerald-200` | `emerald-700` |
| **Warning / Review** | `amber-500` | `amber-50` | `amber-200` | `amber-700` |
| **Error / Rejected** | `red-500` | `red-50` | `red-200` | `red-700` |
| **Info / New** | `blue-500` | `blue-50` | `blue-200` | `blue-700` |
| **Critical** | `red-600` | `red-50` | `red-200` | `red-700` |
| **In Progress** | `violet-500` | `violet-50` | `violet-200` | `violet-700` |
| **QA** | `cyan-500` | `cyan-50` | `cyan-200` | `cyan-700` |
| **AI / Hakim** | `brand-turquoise` | `brand-turquoise/5` | `brand-turquoise/20` | `brand-navy` |
| **Duplicate** | `amber-500` | `amber-50` | `amber-200` | `amber-600` |

### 3.4 Surface & Background Colors

| Surface | Value | Usage |
|---|---|---|
| Page background | `from-slate-50 via-white to-blue-50/20` | Subtle gradient, never flat gray |
| Card surface | `bg-white` | All cards, always white |
| Elevated surface | `bg-white` + `shadow-sm` | Cards with hover potential |
| AI surface | `from-brand-turquoise/5 via-white to-brand-turquoise/3` | Hakim-specific panels |
| Code surface | `bg-slate-900` | Prompt panels, error messages |
| Feedback surface | `bg-amber-50/50` | Feedback loop card |

### 3.5 Color Usage Rules

- **Buttons**: `brand-turquoise` at full opacity is used for primary CTA buttons (`bg-brand-turquoise`). This is the only context where full-opacity turquoise background is permitted.
- **Panels/Cards**: Never use `brand-turquoise` as a panel/card background at full opacity. Always use `/5`, `/10`, or `/20`.
- **Never** combine multiple accent colors in the same component. One accent per component.
- **Never** use semantic colors decoratively. Red means error/critical. Green means success/done.
- **Limit** highlighted elements per viewport. If everything is highlighted, nothing is.
- **Hover states** use the `-light` variant or reduced opacity (`/90`), never a different color family.
- **Disabled states** use `slate-300` text on `slate-50` background. Never gray out with opacity alone.

---

## 4. Typography

### 4.1 Font Families

| Context | Font | Tailwind Class | Fallback |
|---|---|---|---|
| Arabic body (default) | Tajawal | `font-tajawal` | `sans-serif` |
| Arabic headings | Cairo | `font-cairo` | `sans-serif` |
| English body | Tajawal (shared) | `font-tajawal` | `sans-serif` |
| Monospace | IBM Plex Mono | `font-mono` | `monospace` |

Fonts are loaded via Google Fonts in `index.css`:
```
Cairo: 300–800 weights
Tajawal: 300–800 weights
IBM Plex Mono: 400, 500, 600
```

The `body` applies `font-tajawal`. Headings (`h1`–`h6`) apply `font-cairo font-bold`.

### 4.2 Type Scale

| Role | Size | Weight | Line Height | Usage |
|---|---|---|---|---|
| Page title | `text-2xl` / `text-3xl` on lg | `font-bold` (700) | 1.2 | Page headers |
| Section title | `text-base` | `font-semibold` (600) | 1.4 | Card headers, panel titles |
| Card title | `text-sm` / `text-base` | `font-semibold` (600) | 1.4 | Card titles, table issue names |
| Body text | `text-sm` | `font-normal` (400) | 1.6 `leading-relaxed` | Descriptions, behavior text |
| Label | `text-xs` | `font-medium` (500) | 1.4 | Form labels, info labels |
| Caption / Meta | `text-[11px]` / `text-[10px]` | `font-medium` (500) | 1.3 | Timestamps, issue numbers, metadata |
| Chip text | `text-xs` (default), `text-[10px]` (sm) | `font-medium` (500) | 1 | Status chips, priority badges |
| Table header | `text-xs` | `font-semibold` (600) | 1.4 | Column headers |
| Table cell | `text-sm` / `text-xs` | `font-normal` (400) | 1.4 | Cell data |
| KPI value | `text-3xl` | `font-bold` (700) | 1.1 `tracking-tight` | StatCard numbers |
| Code/Prompt | `text-xs` | `font-normal` | 1.6 `leading-relaxed` | Developer prompt display |
| Mono identifiers | `text-xs` / `text-[10px]` | `font-mono` | 1 | Issue numbers (#42), short IDs |

### 4.3 Typography Rules

- **Headings**: Always `text-brand-navy`. Never plain black.
- **Body text in data cards**: `text-slate-600`. Not full black.
- **Muted/secondary**: `text-muted-foreground` (maps to slate-500).
- **Never** use `font-light` (300). Minimum weight is `font-normal` (400).
- **Arabic text**: Never apply `letter-spacing`. Arabic kerning is handled by the font.
- **English in Arabic context**: Numbers and short English labels (team names, IDs) remain LTR inline.
- **Truncation**: Use `truncate` (single-line) or `line-clamp-2` (multi-line) with `max-w-*` constraints. Never let text break layout.

---

## 5. Spacing System

### 5.1 Spacing Scale (Tailwind tokens)

| Token | Value | Usage |
|---|---|---|
| `0.5` | 2px | Icon-text micro gap |
| `1` | 4px | Chip internal padding (sm) |
| `1.5` | 6px | Badge gaps, tight groupings |
| `2` | 8px | Small element gaps, compact card padding |
| `2.5` | 10px | Icon containers internal padding |
| `3` | 12px | Card section gaps, form field gaps |
| `3.5` | 14px | Kanban card internal padding |
| `4` | 16px | Standard card padding, page padding (mobile) |
| `5` | 20px | StatCard padding, Hakim card padding |
| `6` | 24px | Section spacing, grid gap, main content spacing |
| `8` | 32px | Page padding (desktop), major section spacing |

### 5.2 Spacing Rules

| Context | Value |
|---|---|
| Page padding (mobile) | `p-4` (16px) |
| Page padding (desktop) | `lg:p-8` (32px) |
| Section spacing (vertical) | `space-y-6` (24px) |
| Card padding | `p-4` (16px) standard, `p-5` (20px) premium cards |
| Card header bottom padding | `pb-3` (12px) |
| Grid gap (cards) | `gap-4` (16px) |
| Grid gap (analytics) | `gap-6` (24px) |
| Form field spacing | `space-y-5` (20px) |
| Filter toolbar internal | `gap-3` (12px) |
| Table cell padding | `px-4 py-3` (16px × 12px) |
| Button internal spacing | `gap-2` (8px) icon+text |
| Inline metadata spacing | `gap-2` or `gap-3` with `•` separators |

### 5.3 Max Widths

| Context | Value |
|---|---|
| Main content area | `max-w-[1600px]` with `mx-auto` |
| Form pages | `max-w-4xl` (896px) |
| Issue detail page | `max-w-[1400px]` |
| Issue title in table | `max-w-[280px]` |
| Reporter name in cards | `max-w-[120px]` |

---

## 6. Layout Rules

### 6.1 Page Structure

Every Product Hub page follows this structure:

```
<Sidebar>
  <div dir="rtl" className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/20">
    <div className="p-4 lg:p-8 space-y-6 max-w-[1600px] mx-auto">
      {/* Page Header */}
      {/* Tab Navigation or Content */}
    </div>
  </div>
</Sidebar>
```

### 6.2 Page Header Pattern

```
<div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
  <div>
    <h1> icon + title </h1>
    <p> subtitle </p>
  </div>
  <div className="flex items-center gap-3">
    {/* Action buttons */}
  </div>
</div>
```

- Title icon sits in a `rounded-xl bg-brand-turquoise/10 p-2` container.
- Title is `text-2xl lg:text-3xl font-bold text-brand-navy`.
- Subtitle is `text-muted-foreground text-sm`.

### 6.3 Grid Layouts

| Context | Grid |
|---|---|
| KPI stat cards | `grid-cols-2 md:grid-cols-4` |
| Analytics charts | `grid-cols-1 lg:grid-cols-2` |
| Form fields (2-col) | `grid-cols-1 md:grid-cols-2` |
| Issue detail (main + sidebar) | `grid-cols-1 lg:grid-cols-3` (2:1 ratio via `lg:col-span-2`) |
| Type selection buttons | `grid-cols-2 md:grid-cols-3 lg:grid-cols-4` |
| Info fields grid | `grid-cols-2 md:grid-cols-3` |

### 6.4 Responsive Breakpoints

| Breakpoint | Behavior |
|---|---|
| Default (< 768px) | Single column, stacked cards, full-width filters |
| `md` (768px) | 2-column grids, side-by-side form fields |
| `lg` (1024px) | Full layout: 3-column detail page, 4-col stat cards, side panels |
| `xl` (1280px) | Show extra table column labels |

### 6.5 Tab Navigation

```
<TabsList className="bg-white border shadow-sm rounded-xl p-1">
  <TabsTrigger className="rounded-lg data-[state=active]:bg-brand-navy data-[state=active]:text-white gap-2">
```

- Tab list: white background, border, slight shadow, rounded-xl, 1px internal padding.
- Active tab: `bg-brand-navy` with `text-white`.
- Inactive tab: default text color, no background.
- Each tab includes an icon (16px) + label.

---

## 7. Card Standards

### 7.1 Base Card

```
className="border shadow-sm rounded-xl"
```

| Property | Value |
|---|---|
| Background | `bg-white` (via Card component, `bg-card`) |
| Border | `border` (1px `slate-200`) |
| Border radius | `rounded-xl` (12px) — set in base Card component |
| Shadow | `shadow` (base Card default) |
| Hover (interactive) | `hover:shadow-md hover:border-brand-turquoise/50` |
| Padding (content) | `p-4` standard, `p-5` premium |

### 7.2 Card Header

```
<CardHeader className="pb-3">
  <CardTitle className="text-sm font-semibold flex items-center gap-2 text-brand-navy">
    <div className="p-1.5 rounded-lg bg-brand-turquoise/10">
      <Icon className="h-4 w-4 text-brand-turquoise" />
    </div>
    Title Text
  </CardTitle>
</CardHeader>
```

- Icon wrapped in `rounded-lg bg-brand-turquoise/10 p-1.5` container.
- Title: `text-sm font-semibold text-brand-navy`.

### 7.3 Card Types

| Type | Distinct Styling |
|---|---|
| **StatCard** | `rounded-2xl`, `p-5`, `hover:-translate-y-0.5`, decorative circle at bottom-left |
| **Analytics Card** | Standard base card, chart content inside |
| **AI Insight Card** | `border-brand-turquoise/20`, gradient background, special header strip |
| **Empty State Card** | No shadow, centered content, icon in `rounded-2xl bg-slate-50 p-5` |
| **Feedback Card** | `border-2 border-amber-300 bg-gradient-to-r from-amber-50` |
| **Filter Card** | Standard base, `p-4` content, no header |
| **Kanban Card** | `rounded-xl`, `p-3.5`, compact, `hover:border-brand-turquoise/40` |

### 7.4 Card Do's and Don'ts

- **Do**: Keep card content scannable. One primary action or message per card.
- **Do**: Use consistent internal spacing (`space-y-3` or `space-y-4`).
- **Don't**: Nest cards inside cards.
- **Don't**: Use colored card backgrounds except for AI and feedback cards.
- **Don't**: Add shadows heavier than `shadow-md`.

---

## 8. Table Standards

### 8.1 Structure

```html
<Card className="border rounded-xl overflow-hidden shadow-sm">
  <div className="overflow-x-auto">
    <table className="w-full">
      <thead>
        <tr className="bg-slate-50/80 border-b">
          <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500">
      </thead>
      <tbody className="divide-y divide-slate-100">
        <tr className="hover:bg-brand-turquoise/3 cursor-pointer transition-colors group">
          <td className="px-4 py-3">
```

### 8.2 Styling Rules

| Property | Value |
|---|---|
| Header background | `bg-slate-50/80` |
| Header text | `text-xs font-semibold text-slate-500` |
| Header alignment | `text-right` (RTL) |
| Row divider | `divide-y divide-slate-100` |
| Row hover | `hover:bg-brand-turquoise/3` (very subtle) |
| Row cursor | `cursor-pointer` for clickable rows |
| Cell padding | `px-4 py-3` |
| Cell text | `text-sm` for primary, `text-xs` for secondary data |
| Zebra striping | Not used. Hover states provide sufficient distinction. |
| Sticky header | Not currently applied. Use `sticky top-0 z-10 bg-slate-50` if table exceeds viewport. |

### 8.3 Sortable Headers

```jsx
<th onClick={onSort} className="cursor-pointer hover:text-brand-navy select-none">
  <span className="inline-flex items-center gap-1">
    {children}
    {isActive && <ArrowUpDown className="h-3 w-3 text-brand-turquoise" />}
  </span>
</th>
```

- Sortable headers show `ArrowUpDown` icon (12px) in `text-brand-turquoise` when active.
- Rotate icon 180deg for ascending.
- Non-active sortable headers: icon hidden.

### 8.4 Pagination

```
<div className="flex justify-center items-center gap-4 pt-2">
  <Button variant="outline" size="sm" className="rounded-lg" />
  <span className="text-sm text-muted-foreground">صفحة X من Y (Z مشكلة)</span>
  <Button variant="outline" size="sm" className="rounded-lg" />
</div>
```

- Centered below table.
- Outline buttons with `rounded-lg`.
- RTL: Right chevron for "previous", Left chevron for "next".
- Show total count in parentheses.

### 8.5 Table Truncation

- Issue title: `truncate` with `max-w-[280px]`.
- Reporter name: `truncate` with `max-w-[120px]`.
- Long text cells: Always constrain with `max-w-*` + `truncate`.

---

## 9. Form Standards

### 9.1 Field Layout

```jsx
<div>
  <Label className="text-sm font-medium">
    Field Name <span className="text-red-500">*</span>
  </Label>
  <Input className="mt-1.5 text-right rounded-lg" />
  <p className="text-[11px] text-muted-foreground mt-1">Helper text</p>
</div>
```

| Property | Value |
|---|---|
| Label size | `text-sm font-medium` |
| Required indicator | `<span className="text-red-500">*</span>` after label |
| Field margin from label | `mt-1.5` (6px) |
| Helper text | `text-[11px] text-muted-foreground mt-1` |
| Field border radius | `rounded-lg` (8px) |
| Text alignment | `text-right` (RTL) |
| Textarea min height | `min-h-[80px]` (compact) or `min-h-[100px]` (standard) |

### 9.2 Character Counter

```jsx
<p className="text-[11px] text-muted-foreground mt-1 text-left">
  {value.length}/5000
</p>
```

- Position: Below textarea, aligned to the left (end in RTL).
- Only show for long-text fields.

### 9.3 Validation States

| State | Treatment |
|---|---|
| Error | `toast.error('message')` — toast notification, no inline red border |
| Success | `toast.success('message')` — success notification |
| Required missing | Toast with specific field name in Arabic |
| Server error | Parse `err.response?.data?.detail` — show structured message or fallback |

### 9.4 Select/Dropdown Styling

- Use shadcn `Select` component with `SelectTrigger`, `SelectContent`, `SelectItem`.
- Trigger: `rounded-lg`, fixed width (e.g., `w-[140px]`).
- Placeholder: Descriptive Arabic text.
- "All" option: Always include as first option with value `"all"`.

### 9.5 Button-Style Selection (Type Picker, Platform, Reproducibility)

```jsx
<button
  className={`px-4 py-2 rounded-lg border-2 text-sm transition-all ${
    selected
      ? 'border-brand-turquoise bg-brand-turquoise/10 text-brand-navy font-medium'
      : 'border-slate-200 text-muted-foreground hover:border-slate-300'
  }`}
>
```

- Selected: `border-brand-turquoise` + `bg-brand-turquoise/10` + `text-brand-navy`.
- Unselected: `border-slate-200` + `text-muted-foreground`.
- Never use checkboxes for single-select visual choices.

### 9.6 Multi-Select Pills (Impact)

```jsx
<button
  className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
    selected
      ? 'border-brand-turquoise bg-brand-turquoise/10 text-brand-navy'
      : 'border-slate-200 text-muted-foreground hover:border-slate-300'
  }`}
>
```

- Same color scheme as button-style selectors but `rounded-full` for pill shape.
- Toggle on/off behavior.

### 9.7 Step-Based Form

```
Steps indicator: horizontal bar with icons
Active step: bg-brand-turquoise text-white shadow-sm
Completed step: bg-emerald-50 text-emerald-700 + CheckCircle2 icon
Future step: text-muted-foreground
Step connectors: h-0.5 lines, emerald-400 for completed, slate-200 for pending
```

| Property | Value |
|---|---|
| Step bar container | `bg-white rounded-xl border p-3 shadow-sm` |
| Active step | `bg-brand-turquoise text-white shadow-sm rounded-lg` |
| Done step | `bg-emerald-50 text-emerald-700` with `CheckCircle2` |
| Future step | `text-muted-foreground`, no background |
| Connector line | `flex-1 h-0.5 rounded` |

---

## 10. Status / Priority / SLA Visual System

### 10.1 Status Chips (`StatusChip`)

| Status | Solid Color | Light BG | Text Color | Border | Icon |
|---|---|---|---|---|---|
| New (جديد) | `bg-blue-500` | `bg-blue-50` | `text-blue-700` | `border-blue-200` | `Zap` |
| Under Review (تحت المراجعة) | `bg-amber-500` | `bg-amber-50` | `text-amber-700` | `border-amber-200` | `Eye` |
| In Progress (قيد التنفيذ) | `bg-violet-500` | `bg-violet-50` | `text-violet-700` | `border-violet-200` | `Clock` |
| QA Validation (تحقق الجودة) | `bg-cyan-500` | `bg-cyan-50` | `text-cyan-700` | `border-cyan-200` | `Shield` |
| Done (مكتمل) | `bg-emerald-500` | `bg-emerald-50` | `text-emerald-700` | `border-emerald-200` | `CheckCircle2` |
| Rejected (مرفوض) | `bg-red-500` | `bg-red-50` | `text-red-700` | `border-red-200` | `XCircle` |
| Confirmed (أكده المستخدم) | `bg-emerald-600` | `bg-emerald-50` | `text-emerald-700` | `border-emerald-300` | `CheckCircle2` |

**Chip Sizing**:

| Size | Text | Padding | Icon Size |
|---|---|---|---|
| `sm` | `text-[10px]` | `px-2 py-0.5` | `h-3 w-3` |
| `default` | `text-xs` | `px-2.5 py-1` | `h-3.5 w-3.5` |
| `lg` | `text-sm` | `px-3 py-1.5` | `h-3.5 w-3.5` |

**Chip Shape**: `rounded-full`, `font-medium`, `text-white` on solid color.

### 10.2 Priority Badges (`PriorityBadge`)

| Priority | Color | Icon | Dot Color |
|---|---|---|---|
| Critical (حرج) | `bg-red-600` | `AlertOctagon` | `bg-red-500` |
| High (عالي) | `bg-orange-500` | `AlertTriangle` | `bg-orange-500` |
| Medium (متوسط) | `bg-yellow-500` | `Target` | `bg-yellow-500` |
| Low (منخفض) | `bg-slate-400` | `ArrowUpRight` | `bg-slate-400` |

Same sizing system as StatusChip.

### 10.3 SLA Indicators (`SLAIndicator`)

| State | Background | Text | Border | Icon |
|---|---|---|---|---|
| Exceeded | `bg-red-100` | `text-red-700` | `border-red-200` | `AlertTriangle` + `animate-pulse` |
| Warning (≤12h) | `bg-amber-100` | `text-amber-700` | `border-amber-200` | `Timer` |
| On Track | `bg-emerald-100` | `text-emerald-700` | `border-emerald-200` | `CheckCircle2` |
| No SLA | Not rendered | — | — | — |

**Shape**: `rounded-full`, same sizing tokens as chips.

### 10.4 Progress Bars

| Context | Height | Style |
|---|---|---|
| Table row | `h-1.5` with `w-12` | Minimal, with `text-[10px]` percentage label |
| Issue detail page | `h-2` full width | With percentage label above |
| Kanban card | `h-1` full width | Compact, with `text-[10px]` label |
| Dashboard charts | `h-2` full width | Gradient: `from-brand-turquoise to-brand-turquoise/70` |

**Base Progress component** (`components/ui/progress.jsx`): `bg-primary/20 rounded-full overflow-hidden`.
**Fill**: `bg-primary transition-all` (where `primary` = brand-navy).
Product Hub pages may override these with inline gradient backgrounds for dashboard chart bars.

---

## 11. Hakim AI UI Standards

### 11.1 Design Philosophy

Hakim is the AI assistant identity. Its visual presence must communicate:
- Intelligence and analysis capability
- Trustworthiness and precision
- Premium quality — not playful, not gimmicky
- Clear differentiation from standard UI elements

### 11.2 Hakim Identity Colors

| Element | Value |
|---|---|
| Primary | `brand-turquoise` (#46C1BE) |
| Icon | `Brain` (lucide-react) — always `text-brand-turquoise` |
| Secondary icon | `Sparkles` — always `text-brand-turquoise/60` |
| Background | Gradient: `from-brand-turquoise/5 via-white to-brand-turquoise/3` |
| Border | `border-brand-turquoise/20` |
| Header strip | `bg-brand-turquoise/5` with `border-b border-brand-turquoise/10` |

### 11.3 HakimInsightCard (Full)

```
Container: rounded-2xl, border-brand-turquoise/20, gradient background
Header: Brain icon + "تحليل حكيم" + Sparkles, bg-brand-turquoise/5
Content: p-5 space-y-3
Each insight row: p-3 bg-white rounded-xl border-slate-100
  - Title: text-[11px] text-muted-foreground font-medium
  - Value: text-sm font-semibold (color varies by type)
  - Detail: text-xs text-muted-foreground leading-relaxed
Duplicate alert: p-3 bg-amber-50 rounded-xl border-amber-200
```

### 11.4 HakimInsightCard (Compact)

Used inline in tables and cards:
```
flex items-center gap-2 text-xs
Brain icon: h-3.5 w-3.5 text-brand-turquoise
Team suggestion: text-brand-turquoise font-medium
Duplicate count: text-amber-600 with AlertTriangle icon
```

### 11.5 AI Loading State

```
<Loader2 className="h-4 w-4 animate-spin" />
"حكيم يحلل..."
```

- Show during issue submission.
- Button text changes to loading message.
- Use `Loader2` with `animate-spin`, not a custom animation.

### 11.6 Prompt Panel (Admin-Only)

```
Container: border-brand-turquoise/30, standard card
Header: ClipboardCheck icon + "Developer Prompt"
Content: pre tag with bg-slate-900 text-emerald-400 p-5 rounded-xl
  font-mono text-xs leading-relaxed, dir="ltr"
Action: "نسخ مرة أخرى" button below, outline style
```

### 11.7 AI Do's and Don'ts

- **Do**: Use `Brain` icon consistently for all Hakim references.
- **Do**: Keep AI panels in the sidebar (right column on desktop).
- **Do**: Show AI suggestions with clear labels ("المقترح", "المُكتشف").
- **Don't**: Animate AI panels beyond `transition-colors`.
- **Don't**: Use emoji or playful language in AI components.
- **Don't**: Show AI confidence scores unless the backend provides them.
- **Don't**: Mix AI styling with generic alert styling.

---

## 12. Button Standards

### 12.1 Button Hierarchy

| Level | Style | Usage |
|---|---|---|
| **Primary** | `bg-brand-turquoise hover:bg-brand-turquoise/90 text-white shadow-lg shadow-brand-turquoise/20` | Submit Issue, main CTA |
| **Secondary** | `bg-brand-navy hover:bg-brand-navy/90 text-white` | Send comment, assign team |
| **Tertiary/Outline** | `variant="outline"` | Back, cancel, refresh, secondary actions |
| **Ghost** | `variant="ghost"` | Clear filters, minor toggles |
| **Destructive** | `text-red-500 hover:text-red-700 hover:bg-red-50` | Clear, remove |

### 12.2 Button Sizing

| Size | Class | Usage |
|---|---|---|
| Default | Standard Button | Primary actions |
| `sm` | `size="sm"` | Table actions, inline buttons, status transitions |
| `lg` | `size="lg"` | Full-width CTAs |
| Min width | `min-w-[120px]` to `min-w-[180px]` | CTAs to prevent text-wrapping |

### 12.3 Button Styling Rules

| Property | Value |
|---|---|
| Border radius | `rounded-md` (6px) — base shadcn default. Product Hub overrides to `rounded-lg` on key buttons via className. |
| Focus ring | `focus-visible:ring-1 ring-ring` (base shadcn behavior) |
| Icon placement | Before text in RTL (`ml-2` for spacing) |
| Icon size | `h-4 w-4` |
| Loading state | Replace icon with `<Loader2 className="h-4 w-4 animate-spin" />` |
| Disabled state | `disabled` prop, built-in opacity reduction |
| Gap (icon + text) | `gap-2` or manual `ml-2` |

### 12.4 Button Do's and Don'ts

- **Do**: Use one primary CTA per section maximum.
- **Do**: Place primary actions on the left (end) in RTL.
- **Don't**: Stack more than 3 buttons horizontally without wrapping.
- **Don't**: Use brand-turquoise for destructive actions.

---

## 13. Iconography Rules

### 13.1 Icon Library

All icons come from **Lucide React** (`lucide-react`). No mixing of icon libraries.

### 13.2 Icon Sizes

| Context | Size |
|---|---|
| Page title icon | `h-7 w-7` or `h-8 w-8` |
| Card header icon | `h-4 w-4` |
| Button icon | `h-4 w-4` |
| Status chip icon | `h-3 w-3` (sm) or `h-3.5 w-3.5` (default) |
| Table type icon | `h-3.5 w-3.5` |
| Timeline dot (inner) | `w-2 h-2` inside `w-6 h-6` container |
| Inline metadata icon | `h-3 w-3` or `h-3.5 w-3.5` |
| Empty state icon | `h-10 w-10` |
| Feedback card icon | `h-8 w-8` |

### 13.3 Icon Containers

Title-level icons get a background container:

```jsx
<div className="p-2 rounded-xl bg-brand-turquoise/10">
  <Brain className="h-7 w-7 text-brand-turquoise" />
</div>
```

Card header icons get a smaller container:

```jsx
<div className="p-1.5 rounded-lg bg-brand-turquoise/10">
  <Icon className="h-4 w-4 text-brand-turquoise" />
</div>
```

### 13.4 Icon Color Rules

- Status icons: Use the status `textColor` from STATUS_CONFIG.
- Priority icons: Use the priority `textColor` from PRIORITY_CONFIG.
- Issue type icons: Use the type `color` from TYPE_CONFIG.
- AI icons: Always `text-brand-turquoise`.
- Generic/muted icons: `text-muted-foreground`.
- Action buttons: Inherit button text color.

### 13.5 Icon Do's and Don'ts

- **Do**: Use consistent icon assignments (Brain = Hakim, Shield = QA, etc.)
- **Do**: Keep stroke width consistent (Lucide default: 2px stroke).
- **Don't**: Use filled icon variants. Always outline/stroke.
- **Don't**: Place icons without text labels in primary actions (tooltip required for icon-only buttons).
- **Don't**: Mix icon sizes within the same visual row.

---

## 14. Timeline / Activity Log

### 14.1 Structure

```
Vertical timeline with:
- Continuous line: absolute, right-[11px], w-0.5 bg-slate-200
- Event nodes: w-6 h-6 rounded-full with w-2 h-2 inner dot
- Content: actor name, event label (in pill), details, timestamp
```

### 14.2 Event Node Colors

| Event Type | Outer BG | Inner Dot |
|---|---|---|
| Created / Issue Created | `bg-emerald-100` | `bg-emerald-500` |
| Status Changed | `bg-blue-100` | `bg-blue-500` |
| Done / Marked Done | `bg-emerald-100` | `bg-emerald-500` |
| Reopened | `bg-amber-100` | `bg-amber-500` |
| All other events | `bg-slate-100` | `bg-slate-400` |

### 14.3 Event Content

```
Actor name: text-sm font-medium
Event label: text-xs text-muted-foreground bg-slate-50 px-2 py-0.5 rounded-full
Status transition: StatusChip(from) → StatusChip(to) using sm size
Note: text-slate-500, text-xs
Team assignment: "الفريق: " + text-brand-turquoise font-medium
Timestamp: text-[10px] text-muted-foreground, block, mt-1
```

### 14.4 Timeline Section Behavior

- Default: **collapsed** (`expandedSections.timeline: false`).
- Toggle via CardHeader click.
- Show item count in header: `({count})`.
- Chevron icon: `ChevronDown` / `ChevronUp`.

---

## 15. Comments Thread

### 15.1 Comment Types

| Type | Background | Border | Text Accent |
|---|---|---|---|
| Admin Note (ملاحظة إدارية) | `bg-blue-50` | `border-blue-200` | `text-blue-700` |
| QA Note (ملاحظة QA) | `bg-purple-50` | `border-purple-200` | `text-purple-700` |
| General (تعليق) | `bg-slate-50` | `border-slate-200` | `text-slate-700` |

### 15.2 Comment Layout (Flat Style)

```
<div className="flex gap-3 p-3 rounded-xl border {borderColor} {bgColor}">
  <Avatar h-8 w-8 with initials, bg-brand-navy text-white text-xs>
  <div className="flex-1">
    <metadata row: name, admin badge, type badge, • separator, timestamp>
    <p className="text-sm mt-1.5 leading-relaxed">{content}</p>
  </div>
</div>
```

### 15.3 Comment Type Selector (Admin Only)

Shown above the input area when user is admin:

```
<button className="px-3 py-1 rounded-full text-[11px] font-medium border transition-all">
```

Active: Type-specific `bgColor`, `textColor`, `borderColor`.
Inactive: `border-slate-200 text-muted-foreground`.

### 15.4 Comment Input

```
<div className="flex gap-2">
  <Textarea min-h-[60px] flex-1 rounded-lg text-right />
  <Button bg-brand-navy self-end rounded-lg>
    <Send or Loader2 icon />
  </Button>
</div>
```

### 15.5 Comment Rules

- **Do**: Show comment count in section header.
- **Do**: Show admin badge for platform_admin comments.
- **Don't**: Use bubble/chat style. Use flat card style.
- **Don't**: Indent or nest replies. All comments are flat.

---

## 16. Empty / Loading / Error States

### 16.1 Loading State

```
<div className="flex justify-center items-center py-20">
  <div className="flex flex-col items-center gap-3">
    <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand-turquoise border-t-transparent" />
    <p className="text-sm text-muted-foreground">{message}</p>
  </div>
</div>
```

- Spinner: `h-8 w-8` (or `h-10 w-10` for full-page).
- Border: `brand-turquoise` with transparent top.
- Animation: `animate-spin`.
- Message: Arabic, `text-sm text-muted-foreground`.

### 16.2 Empty State (`EmptyState` Component)

```
<div className="flex flex-col items-center justify-center py-16 px-6 text-center">
  <div className="rounded-2xl bg-slate-50 p-5 mb-4">
    <Icon className="h-10 w-10 text-slate-300" />
  </div>
  <h3 className="text-base font-semibold text-slate-500">{title}</h3>
  <p className="text-sm text-slate-400 mt-1 max-w-sm">{description}</p>
  {action && <div className="mt-4">{action}</div>}
</div>
```

| Property | Value |
|---|---|
| Icon container | `rounded-2xl bg-slate-50 p-5` |
| Icon | `h-10 w-10 text-slate-300` |
| Title | `text-base font-semibold text-slate-500` |
| Description | `text-sm text-slate-400 mt-1 max-w-sm` |
| Action CTA | Optional, placed `mt-4` below |

### 16.3 Empty State Messages

| Context | Icon | Title | Description |
|---|---|---|---|
| No issues | `Bug` | لا توجد مشاكل | لم يتم العثور على مشاكل تطابق معايير البحث |
| No comments | `MessageSquare` | لا توجد تعليقات بعد | — |
| No activity | `Activity` | لا يوجد نشاط | — |
| No data (chart) | `Inbox` | لا توجد بيانات | — |
| No kanban items | `Kanban` | لا توجد مشاكل | سيظهر تتبع المشاكل هنا بمجرد إنشائها |

### 16.4 Error State

- API errors: `toast.error(message)` using Sonner.
- Parse backend `detail` field: if object with `message`, show `message`. If string, show directly. Fallback to generic Arabic message.
- Permission denied: Toast with specific message.
- Navigation fallback: On 404/error, redirect to `/admin/product-hub`.

### 16.5 Messaging Tone

- Arabic, professional, clear.
- No exclamation marks in error messages.
- No blame language ("you did something wrong").
- Factual and actionable: "فشل في تحميل المشاكل" (failed to load issues).

---

## 17. RTL/LTR Rules

### 17.1 Base Direction

All Product Hub pages set `dir="rtl"` on the content container. The `<Sidebar>` wrapper handles its own direction.

### 17.2 Layout Mirroring

| Element | RTL Behavior |
|---|---|
| Page content | Flows right-to-left |
| Text alignment | `text-right` default for inputs, labels |
| Action buttons | Placed on the left (end of RTL flow) |
| Back arrow | `ArrowRight` icon (points right = "go back" in RTL) |
| Forward arrow | `ArrowRight` rotated 180deg or `ArrowLeft` |
| Chevron pagination | `ChevronRight` = previous, `ChevronLeft` = next |
| Search icon | `absolute right-3` (start of input in RTL) |
| Progress percentage | `text-left` (appears at the end in RTL) |
| Metadata separators | Use `•` (middle dot) between items |

### 17.3 Components That Don't Mirror

| Element | Behavior |
|---|---|
| Code/Prompt blocks | Always `dir="ltr"` |
| Issue numbers (#42) | Displayed LTR inline within RTL text |
| English team names | Rendered as-is within RTL context |
| Progress bars | Fill from left to right (universal) |
| Timestamps | Rendered via `toLocaleString('ar-SA')` |

### 17.4 Kanban Board

- Columns flow left-to-right regardless of RTL (universal board convention).
- Card content within columns follows RTL.
- Horizontal scroll: `overflow-x-auto` with `min-w-max`.

### 17.5 RTL Do's and Don'ts

- **Do**: Test every component in both Arabic and English content.
- **Do**: Use logical CSS properties where possible (`mr-*` in RTL = start margin).
- **Don't**: Hardcode `left`/`right` for content positioning — use `start`/`end`.
- **Don't**: Mirror icons that have universal meaning (play, check, close).

---

## 18. Component Styling Standards

### 18.1 StatCard

| Property | Value |
|---|---|
| **Purpose** | Display a single KPI metric with icon and optional trend |
| **Visual Role** | Dashboard hero metric |
| **Container** | `rounded-2xl border bg-white p-5 shadow-sm` |
| **Hover** | `hover:shadow-md hover:-translate-y-0.5` |
| **Icon Container** | `rounded-xl p-2.5 {bg}`, scales on hover (`group-hover:scale-110`) |
| **Icon Size** | `h-5 w-5` |
| **Value** | `text-3xl font-bold text-brand-navy tracking-tight` |
| **Label** | `text-sm text-muted-foreground mt-0.5` |
| **Trend Badge** | `text-[10px] font-semibold px-2 py-0.5 rounded-full`, green or red |
| **Decorative** | Subtle circle at bottom-left, `opacity-5` |

### 18.2 StatusChip

| Property | Value |
|---|---|
| **Purpose** | Display issue status as a colored pill |
| **Shape** | `rounded-full` |
| **Background** | Solid semantic color from STATUS_CONFIG |
| **Text** | `text-white font-medium` |
| **Sizes** | sm / default / lg (see Section 10.1) |
| **Icon** | Optional, shown when `showIcon=true` |
| **Do** | Use consistently everywhere status appears |
| **Don't** | Modify colors per-instance. Always use config. |

### 18.3 PriorityBadge

Same structure as StatusChip. Uses PRIORITY_CONFIG colors.

### 18.4 SLAIndicator

| Property | Value |
|---|---|
| **Purpose** | Show SLA compliance status |
| **Shape** | `rounded-full` with border |
| **Exceeded** | Red background + `animate-pulse` |
| **Warning** | Amber background, shows remaining hours |
| **On Track** | Green background |
| **Hidden** | When no SLA or `no_sla` status |

### 18.5 HakimInsightCard

| Property | Value |
|---|---|
| **Purpose** | Display Hakim AI analysis results |
| **Container** | `rounded-2xl`, gradient background, turquoise border |
| **Header** | Brain + Sparkles icons, `bg-brand-turquoise/5` strip |
| **Insight Rows** | White cards with `rounded-xl border-slate-100` |
| **Duplicate Alert** | Amber background within the card |
| **Compact Mode** | Inline flex with Brain icon + key info, no card wrapper |
| **Do** | Place in sidebar on detail pages |
| **Don't** | Show on listing pages (use compact mode on cards instead) |

### 18.6 IssueKanbanCard

| Property | Value |
|---|---|
| **Purpose** | Represent an issue in the Kanban board |
| **Container** | `rounded-xl border-slate-200 p-3.5 shadow-sm` |
| **Hover** | `hover:shadow-md hover:border-brand-turquoise/40` |
| **Title** | `text-sm font-semibold text-brand-navy line-clamp-2` |
| **Metadata** | `text-[11px] text-muted-foreground` with type icon |
| **Progress** | `h-1` bar with `text-[10px]` label |
| **Footer** | Reporter name (truncated) + SLA indicator + duplicate badge |
| **Width** | Determined by column: `w-[280px]` |

### 18.7 EmptyState

| Property | Value |
|---|---|
| **Purpose** | Placeholder when no data exists |
| **Layout** | Centered vertically and horizontally |
| **Icon** | `h-10 w-10 text-slate-300` in `rounded-2xl bg-slate-50 p-5` |
| **Title** | `text-base font-semibold text-slate-500` |
| **Description** | `text-sm text-slate-400 max-w-sm` |
| **Action** | Optional button/link below |

### 18.8 FilterToolbar

| Property | Value |
|---|---|
| **Purpose** | Filter and search issues |
| **Container** | Standard card with `p-4` |
| **Layout** | `flex flex-wrap gap-3 items-center` |
| **Search Input** | `flex-1 min-w-[220px]` with search icon |
| **Dropdowns** | Fixed width (`w-[130px]` to `w-[150px]`), `rounded-lg` |
| **Clear Button** | Ghost variant, red text, `XCircle` icon |
| **Visibility** | Clear button only shown when filters are active |

### 18.9 AdminActionBar

| Property | Value |
|---|---|
| **Purpose** | Admin-only status transitions and team assignment |
| **Container** | Standard card in sidebar |
| **Header** | Shield icon + "إجراءات الإدارة" |
| **Status Buttons** | `size="sm" variant="outline" rounded-lg text-xs` |
| **Note Input** | Below status buttons, `text-sm rounded-lg` |
| **Team Selector** | Select + assign button in flex row |
| **Visibility** | Only rendered when `isAdmin && allowedTransitions.length > 0` |

### 18.10 PromptPanel

| Property | Value |
|---|---|
| **Purpose** | Display generated developer prompt (admin-only) |
| **Trigger** | "نسخ Prompt" button in page header |
| **Container** | Card with `border-brand-turquoise/30` |
| **Content** | `<pre>` with `bg-slate-900 text-emerald-400 rounded-xl p-5 font-mono text-xs` |
| **Direction** | Always `dir="ltr"` |
| **Actions** | Copy button below the code block |
| **Visibility** | Only rendered when admin clicks copy and prompt is loaded |

### 18.11 CommentThread

| Property | Value |
|---|---|
| **Purpose** | Display and add comments on issues |
| **Comment Layout** | Flat cards (not bubbles), typed by comment_type |
| **Avatar** | `h-8 w-8`, brand-navy background, white text initials |
| **Type Selector** | Admin-only pills above input area |
| **Input** | Textarea + send button in flex row |
| **Empty State** | `EmptyState` with `MessageSquare` icon |

### 18.12 TimelinePanel

| Property | Value |
|---|---|
| **Purpose** | Show chronological activity log |
| **Layout** | Vertical timeline with connected line |
| **Line** | `absolute right-[11px] w-0.5 bg-slate-200` |
| **Nodes** | `w-6 h-6 rounded-full` with colored inner dot |
| **Collapsible** | Default collapsed, toggle via header click |
| **Events** | Actor + label pill + details + timestamp |

---

## 19. Responsive Rules

### 19.1 Dashboard Cards

| Breakpoint | Columns |
|---|---|
| Mobile | 2 columns |
| md+ | 4 columns |
| Cards stack vertically on narrow screens |

### 19.2 Filter Toolbar

- `flex-wrap` allows filters to wrap to next line on small screens.
- Search input: `min-w-[220px] flex-1` ensures it takes full width when alone.
- Dropdowns maintain fixed widths.

### 19.3 Tables

- Wrapped in `overflow-x-auto` for horizontal scroll on small screens.
- Some column labels hidden on smaller screens (`hidden xl:inline`).
- Table never collapses to cards — horizontal scroll is preferred for data integrity.

### 19.4 Issue Detail Page

| Breakpoint | Layout |
|---|---|
| Mobile | Single column, sidebar stacks below main content |
| lg+ | 3-column grid (2:1 ratio) with sidebar |

### 19.5 Kanban Board

- Always horizontal scroll via `overflow-x-auto`.
- Columns: `w-[280px] flex-shrink-0`.
- `min-w-max` on container to prevent column squishing.

### 19.6 Forms

| Breakpoint | Layout |
|---|---|
| Mobile | Single column fields |
| md+ | 2-column grid for short fields |
| Type selection: `grid-cols-2` → `md:grid-cols-3` → `lg:grid-cols-4` |

### 19.7 Action Bars

- Page header actions: `flex-col lg:flex-row` stacking.
- Status transition buttons: `flex-wrap gap-2` for auto-wrapping.

---

## 20. Accessibility Rules

### 20.1 Color Contrast

- All text on white backgrounds must meet WCAG AA (4.5:1 for body, 3:1 for large text).
- White text on status chips: Verified against all status colors (minimum blue-500 provides sufficient contrast).
- Never use color alone to convey meaning — always pair with icon or text label.

### 20.2 Focus States

- All interactive elements must have visible focus indicators.
- Use browser default or `focus-visible:ring-2 ring-brand-turquoise ring-offset-2`.
- Tab order follows visual reading order (right-to-left in RTL).

### 20.3 Keyboard Navigation

- All buttons, links, and form controls are keyboard-accessible via shadcn primitives.
- Tab panels switch with arrow keys (shadcn Tabs built-in).
- Select dropdowns support keyboard selection (shadcn Select built-in).
- **Target**: Kanban cards should have `tabIndex={0}` and `onKeyDown` handlers for Enter/Space. Currently clickable via `onClick` only.

### 20.4 Form Accessibility

- All inputs have associated `<Label>` elements.
- Required fields marked visually with `*`.
- **Target**: Add `aria-required="true"` to required form controls. Currently visual-only.
- Error messages announced via toast. **Target**: Add `aria-live="polite"` region for inline validation errors in future.

### 20.5 RTL Accessibility

- `dir="rtl"` set on content containers.
- Screen readers interpret RTL text correctly with proper HTML direction.
- Form labels properly associated regardless of direction.

---

## 21. UI Do's and Don'ts

### Do's

1. Use the shared component library for all status, priority, and SLA display.
2. Import constants from `hubConstants.js` — never define local copies.
3. Use `toast.success()` for success, `toast.error()` for errors.
4. Parse backend error details before displaying.
5. Gate admin-only UI behind `isAdmin` checks.
6. Use `rounded-xl` for cards, `rounded-lg` for buttons and inputs, `rounded-full` for chips.
7. Place AI panels in the sidebar column on detail pages.
8. Use Arabic for all user-facing text. English only for technical identifiers.
9. Show loading spinners for async operations.
10. Use `transition-all` or `transition-colors` for smooth state changes.

### Don'ts

1. Don't create local STATUS_CONFIG or PRIORITY_CONFIG copies. Import from shared constants.
2. Don't use `shadow-lg` or `shadow-xl` on cards. Maximum `shadow-md` on hover.
3. Don't use more than one primary CTA button per section.
4. Don't use colored backgrounds on standard cards (white only).
5. Don't show admin-only data (prompts, AI analysis details) to non-admin users.
6. Don't use `alert()` or `confirm()` — use toast or custom dialogs.
7. Don't hardcode team names, status labels, or type labels — use config objects.
8. Don't mix Lucide icons with other icon libraries.
9. Don't animate anything beyond hover transitions and loading spinners.
10. Don't use inline styles unless for dynamic values (e.g., calculated bar widths). All static styling via Tailwind utility classes.
11. Target: Keep components under 300 lines. Split into sub-components. (Current pages exceed this — refactoring is tracked separately.)
12. Don't use `console.log` for user-facing errors. Use toast notifications.
