# Design System

The site uses a **Cyberpunk / Glitch** aesthetic. Dark mode only — no theme toggle.

**Philosophy:** *"High-Tech, Low-Life."* The interface should feel like a hacked terminal or forbidden console. Visual references: Blade Runner, Akira, The Matrix, Ghost in the Shell.

## Color Palette

| Token | Role | Value |
|-------|------|-------|
| `background` | Page background (void black) | `#0a0a0f` |
| `foreground` | Primary text | `#e0e0e0` |
| `card` | Card background | `#12121a` |
| `muted` | Elevated UI backgrounds | `#1c1c2e` |
| `mutedForeground` | Secondary text | `#6b7280` |
| `accent` | Primary neon (electric green) | `#00ff88` |
| `accentSecondary` | Secondary neon (hot magenta) | `#ff00ff` |
| `accentTertiary` | Tertiary neon (cyan) | `#00d4ff` |
| `border` | Subtle borders | `#2a2a3a` |
| `destructive` | Error/danger | `#ff3366` |

## Typography

| Use | Font Stack |
|-----|-----------|
| Headings | `"Orbitron", "Share Tech Mono", monospace` |
| Body | `"JetBrains Mono", "Fira Code", "Consolas", monospace` |
| Labels / UI | `"Share Tech Mono", monospace` |

## Visual Signatures

1. **Chromatic Aberration** — RGB color splitting on hero text (magenta/cyan offset shadows)
2. **Scanlines Overlay** — Subtle full-page horizontal lines mimicking CRT refresh
3. **Glitch Effects** — `clip-path` animations, skewed transforms, flickering text
4. **Neon Glow** — Multi-layered `box-shadow` / `text-shadow` on borders and interactive elements
5. **Corner Cuts** — Chamfered corners via `clip-path` instead of `border-radius`
6. **Circuit Patterns** — Decorative SVG/CSS backgrounds resembling PCB traces

## Layout

- `max-w-7xl` content container, full-bleed sections
- 8px base grid; section padding `py-24` to `py-32`
- Asymmetric layouts: hero is 60/40 split; at least one section uses overlapping elements
- Subtle `rotate-1` / `skew-y-1` transforms on section containers

## Animations

- **Motion feel:** Sharp, digital, slightly mechanical — quick snaps over smooth eases
- **Transitions:** `all 150ms cubic-bezier(0.4, 0, 0.2, 1)` or `all 100ms steps(4)` for digital feel
- **Hero headline:** Chromatic aberration + occasional glitch keyframe animation
- **Blinking cursor:** `animation: blink 1s step-end infinite`
- **Neon glow on hover:** Border and shadow color transitions
- **Chatbot widget:** Slide-up open, slide-down close
- **`prefers-reduced-motion`:** Disables glitch animations; static chromatic aberration is kept

## Responsive Breakpoints

Mobile-first: `sm` 640px · `md` 768px · `lg` 1024px · `xl` 1280px

| Element | Mobile | Desktop |
|---------|--------|---------|
| Hero h1 | `text-5xl` | `text-7xl` → `text-8xl` |
| Project grid | 1 column | 2 columns (md) / 3 columns (lg) |
| Touch targets | 44px minimum | — |

Scanlines, chamfered corners, neon glows, and monospace fonts are maintained at all sizes.

## Accessibility

- WCAG 2.1 AA contrast (accent green on dark background = 7.5:1)
- `focus-visible` outlines styled with neon glow
- Semantic HTML throughout
- All animations respect `prefers-reduced-motion`
