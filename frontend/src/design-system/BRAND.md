# Market Signal Research — Design System

Design system for an internal **AI market-prediction research platform**: a data-collection
tool that ingests YouTube commentary about companies, transcribes it, runs AI extraction to
pull structured facts (outcome, ROI, causes, timeframe, confidence), and exposes the labeled
dataset to a downstream trading model via `/export/data`.

The product is a single internal surface — a local FastAPI + React dashboard used by one
analyst. There is no marketing site, no mobile app, no logged-in customer. The design system
is therefore small and dense: instrument panel, not consumer product.

> The brand has no public name in the supplied materials. This system uses **Market Signal
> Research** as the working product name in mockups. Replace it if the real name differs.

## Sources given

| Source | Path | What it gave us |
| --- | --- | --- |
| Brand mark (raster) | `assets/logo-emboss.png` (from `uploads/ChatGPT Image Aug 14, 2026, 01_05_13 PM.png`) | The only brand asset: an embossed circle with a three-node rising trendline in pale blue on off-white paper |
| Product screenshot | `assets/reference-dashboard.png` (from `uploads/Screenshot 2026-08-14 at 1.32.32 pm.png`) | The entire visual language: blueprint grid, hand-drawn panels, mono type, overline labels, outline bar chart, handwritten asides |
| Technical brief | pasted into chat | Architecture, data model, endpoints, screens, build order |

**No codebase, repository or Figma file was supplied** — the brief describes a greenfield
build that does not exist yet. Everything visual here is derived from the screenshot and the
mark; everything structural (entities, screen list, endpoints) from the brief. Where the
screenshot is silent (settings, empty states, export view) the work is a documented proposal,
not a recreation.

## Index

- `styles.css` — the single entry point consumers link. Imports only.
- `tokens/` — `fonts.css`, `colors.css`, `typography.css`, `spacing.css`, `effects.css`, `motion.css`
- `components/core/` — Button, IconButton, Input (+ FieldLabel), Select, Checkbox (+ Radio), Switch
- `components/surfaces/` — SketchPanel (+ PanelLabel), Annotation, Dialog, Tabs
- `components/display/` — Badge, Tag, StatusDot, StatBlock, BarChart, DataTable
- `components/assistant/` — ChatBubble, SuggestionChip, PromptInput, Toast, Tooltip
- `ui_kits/research-platform/` — click-through recreation of the platform (4 screens) + its README
- `guidelines/` — 19 foundation specimen cards (colour, type, spacing, effects, brand)
- `assets/` — `logo-emboss.png`, `reference-dashboard.png`
- `SKILL.md` — Agent Skills entry point

### Intentional additions

Nothing in the source enumerates a component library, so the inventory is the standard set
(button, inputs, select, checkbox/radio, switch, card, badge, tag, tabs, dialog, toast,
tooltip) plus five families the screenshot clearly defines and the standard set does not
cover: `SketchPanel`, `PanelLabel`, `Annotation`, `StatBlock`, `BarChart`, `ChatBubble`,
`SuggestionChip`, `PromptInput`, `StatusDot`, `DataTable`.

---

## Content fundamentals

The voice is **an instrument reporting on itself**. Terse, technical, factual. It states what
was processed and what was found; it never sells, encourages, or apologises.

**Casing is the load-bearing rule.**

- **Section labels are UPPERCASE, letterspaced, and joined with ` // `** — the brand's single
  most recognisable device: `AI ANALYST CHAT // INTERACTIVE DECK`, `DATASET PROFILE // VISUAL
  SCHEMATIC`, `EXECUTIVE SUMMARY // SYSTEM METRICS`, `MODEL CONFIDENCE`. Two segments maximum,
  scope first then view. No trailing punctuation.
- **Titles are Title Case, and may carry a bracketed qualifier**: `Data Intelligence
  Assistant`, `Active Profile: [Bar Distribution]`.
- **Body and bullets are sentence case, full stops included**: "Initialization complete.
  Processed 7 primary business vectors with 98.4% model confidence."

**Person.** Neither "I" nor "you". The system speaks in impersonal declaratives — "Processed
7 primary business vectors", "Identified 3 minor metric deviations requiring monitoring",
"Requires sensitivity review". No "we", no "let's", no "your data". The one exception is the
chat author label `YOU`, which identifies a turn rather than addressing the reader.

**Numbers are always specific and always carry their unit.** `98.4%`, `424`, `3`, `+17.4%`,
`−92%`, `41m 12s`, `0.88`. Never "high", "several", "a few". Confidence is a decimal to two
places; ROI is a signed percentage; durations are `NNm NNs`.

**Nouns are borrowed from measurement, not finance.** "vectors", "variance index", "deviation
clusters", "sub-segment parameters", "baseline spread", "profile", "schematic", "deck". A
company is a *record*; a video is a *source*; an AI output is an *extraction*.

**Bullets** start with the finding, not the framing: "Revenue & CAC Efficiency vectors show
stable upward trajectory." — not "It's worth noting that…". Markers are a mono `·`.

**Emoji: exactly one place.** Prompt-starter chips carry a single leading emoji
(📈 Deep Dive Anomalies, ⚡ Forecast Q4 Shift, 🎯 Recalibrate Baseline). Nowhere else — not in
headings, labels, badges, toasts or data. Unicode glyphs used as UI marks are fine and
preferred over icon art: `//`, `·`, `↵`, `✓`, `✕`, `▾`, `↗`, `↻`, `⌕`, `—`, `→`, `↘`.

**Handwriting carries commentary only.** The Caveat asides ("Analytical Summary Deck",
"captions first — whisper is expensive") are the analyst's own margin notes. They are lower
case, informal, and never contain a number the user must act on.

**Empty and error states** report the condition, no consolation: "No companies match that
query", "No sources attached yet", "Enter a full http(s) URL", "provider returned 429 ·
retrying in 30s".

---

## Visual foundations

The whole system is one idea: **an engineer's notebook page with instrument panels laid on
it.** Blueprint grid underneath, white paper panels floating on top, everything drawn in one
navy ink with one monospace face.

### Colour

One ink ramp, one paper ramp, one blue accent, three status colours. That is the entire
palette — see `guidelines/color-*.html`.

- **Ink** `#16222e → #eef2f5` does all the work: text, borders, rules, chart strokes, the
  solid button, the meter bar. Body text is `--ink-700`, headings `--ink-900`, muted
  `--ink-400`, hairlines `--ink-100`.
- **Paper** `#ffffff` panels on a `#fcfcfb` page. Hover and sunken fills are `#f7f8f9` /
  `#f1f3f5`. Grid rules are `#e4eaf0`.
- **Blue** `#41718f → #eef6fa`, sampled from the logo's pale nodes. It appears only as: link
  and accent text, the focus ring, the user's chat fill, one highlighted chart bar, and the
  `--rail-user` rail. It is never a background for a large area and never a gradient.
- **Status** green `#2fa85a` (success / high ROI), amber `#c8901f` (processing / review), red
  `#bc4a3d` (failure / error). Only ever in badges, dots and toast rails — never as body text
  colour, never as a filled panel.

There are **no gradients anywhere** — the only gradient token is `--fade-bottom`, a paper-to-
transparent scroll fade. No purple, no duotone, no dark mode (the emboss and the grid both
depend on a light ground).

### Type

**IBM Plex Mono for everything** — labels, headings, body, tables, numbers. A single face with
weight and case doing the differentiating: 400 body, 600 uppercase labels, 700 headings and
metrics. Scale: 30 / 22 / 17 / 15 / 14 / 13 / 11 / 10. Body line-height 1.6; headings 1.15.
Uppercase labels take `0.12em` tracking (`0.16em` at 10px); headings take `-0.01em`.

**Caveat** is the only second face: handwritten asides, rotated -1.2°, one per panel maximum.

Both are Google Fonts **substitutions** — no font binaries were supplied. See Caveats.

### Panels, borders, radii

The `SketchPanel` is the only container. Its recipe:

- white fill, **1px `--ink-100` hairline** border
- **uneven multi-value radius** `12px 9px 14px 10px / 10px 13px 9px 12px` — corners differ so
  the box reads as drawn rather than rendered
- a **second, fainter inner stroke** inset 2px and rotated 0.35°, which produces the
  double-line hand-drawn edge seen in the screenshot
- a **-0.25° tilt** on the whole panel (`tilt={false}` when panels sit in a strict grid)
- soft paper-lift shadow

Left **accent rails** (3px) mark provenance: ink for assistant/system output, blue for the
operator's own input, status colour on toasts. Rails are the only coloured border in the
system — and note the deliberate absence of the "rounded card with a coloured left border and
no other structure" pattern: rails only ever appear on panels that already have a hairline.

Radii: `3px` badges, `5px` controls, `7px 5px 8px 6px / …` small sketch (chips, chat bubbles,
composer), full sketch on panels, pill **only** on the Switch and the meter bar.

### Backgrounds

Page background is the **blueprint grid**: 24px squares of `--grid-line` on `--paper-050`,
applied at page level only. The grid never shows through a panel and never carries content.
No photography, no illustration, no texture overlay, no noise/grain — the paper reads as flat
white. The one raster in the system is the embossed mark.

### Shadows, transparency, blur

Shadows are neutral, low-opacity paper lifts (`0 1px 2px / 0 6px 18px` at 5–6% ink). Nothing
is tinted, coloured or larger than 32px blur. `--shadow-inset` gives the pressed-paper look
on sunken code blocks.

Transparency is used in exactly two places: the modal scrim (`ink @ 32%`, with a 3px
`backdrop-filter` blur) and the `--fade-bottom` scroll fade. No frosted-glass panels, no
translucent headers.

### Motion

Instrument-like: 90–320ms, `cubic-bezier(.2,.6,.3,1)`, no bounce, no spring, no easing
overshoot. Controls transition colour/border/shadow at 140ms. Panels and toasts fade+rise at
200ms. **Charts and metrics never animate on load** — a number that counts up is a number you
can't read. The pulse halo on `StatusDot` is the only continuous animation, and only for a
live state.

### Interaction states

- **Hover**: fill tints one step (`--surface-sunken`), or the ink button darkens 800 → 900.
  Buttons and icon buttons also rise 1px with a slightly stronger paper lift (140ms). Never a
  hue change, never a shadow bloom.
- **Press**: `scale(0.985)`, cancelling the hover lift. No colour flash.
- **Focus**: 1px `--blue-500` border + 3px `rgba(91,141,179,.28)` ring.
- **Disabled**: `opacity: .45`, `not-allowed`. Never greyed-out custom colours.
- **Selected**: fills with ink and inverts the label (tags, tabs use a 2px ink underline).
- **Links**: `--blue-600`, no underline at rest, darkening to `--ink-900` on hover.

### Layout

Sticky 62px white header with a hairline bottom rule; content max-width 1240px, 28px page
padding. Panels sit in a 2-column grid (`1.5fr 1fr` is the recurring split) with 20px gutters.
Panel padding is 24px; internal stacks 12px; label-to-value 6px. Tables are hairline-ruled with
uppercase micro column heads, right-aligned numerics and no zebra striping. Toasts dock
bottom-right, stacked with 8px gaps.

### Charts

Outline bars only: `--chart-fill` (near-white) with a 1px ink stroke on three sides, no fill
colour, no legend, no data labels. Y axis ticks in 10px mono; x labels rotated -40° about their
right end so each label terminates under its own bar and long names never collide (the label
gutter defaults to 84px — raise `labelHeight` for longer names).
Highlighting is done by swapping one bar's fill to `--blue-100`, never by hue coding a series.

---

## Iconography

**There is no icon set in the supplied materials — none was provided and none was invented.**
The reference UI carries essentially no icon art, and the system leans on that:

1. **Unicode glyphs as marks.** `//` in overlines, `·` for bullets and separators, `↵` on
   send, `✓` in checkboxes, `✕` for close/remove, `▾` on selects, `↗` open-external,
   `↻` re-run, `⌕` search, `—` for null values, `→` `↘` on handwritten pointers. These are set
   in IBM Plex Mono so they match the surrounding text exactly.
2. **Emoji, in one place only**: the prompt-starter chips (📈 ⚡ 🎯), which is how they appear
   in the reference screenshot.
3. **No icon font, no sprite sheet, no SVG icon library** is shipped here. If a build needs
   true icons (a sidebar, a file browser), use **Lucide** from CDN at `1.5px` stroke,
   `--ink-500`, 16px — it is the closest match to the hairline mono aesthetic. This would be a
   **substitution, not brand truth**: flag it and get real assets before shipping.

The brand mark (`assets/logo-emboss.png`) is a raster emboss and cannot be recoloured or
inverted. Use it at 30–150px on white or `--paper-050`, circular-cropped in headers. There is
**no supplied logotype**; set the product name in IBM Plex Mono 700, `--ink-900`, tracking
-0.01em, beside the mark with 14px of clear space.

---

## Caveats

- **Fonts are substitutions.** No binaries were supplied. IBM Plex Mono stands in for the
  screenshot's mono face and Caveat for its handwriting. Both load from Google Fonts in
  `tokens/fonts.css`. Send the real files and we will swap them in and re-tune the scale.
- **No logotype exists.** The mark is used as given; the wordmark is plain type by design.
- **The screenshot is the only visual source.** No code, no Figma. Values were read from the
  image, so paddings and sizes are close but not provably exact.
- **Product name is a placeholder.**
