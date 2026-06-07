# Nexora Design Constitution

## Visual DNA: Matrix Terminal / Sci-Fi Observation Deck

Nexora is an autonomous research interface. Its aesthetics are rooted in high-density data visualization, terminal-inspired interaction patterns, and a strict monochrome-with-accents color economy.

### Reference Archetypes
1. **RainingLetters**: A modern-animated hero section with 300 raining monospace characters, green glow highlights, and `TextScramble` resolving titles.
2. **UIMIX**: A dot-grid sci-fi interface with L-bracket corner accents, system telemetry bars, and coordinate-tracked panels.

---

## 🎨 Color Tokens (Zero Hardcoded Hex)

All colors are stored in `lib/design-tokens.ts` and extended via Tailwind.

| Token | Value | Usage |
| :--- | :--- | :--- |
| `nexora.black` | `#000000` | Root background |
| `nexora.surface.1` | `rgba(255,255,255,0.02)` | Panel fill |
| `nexora.surface.2` | `rgba(255,255,255,0.04)` | Elevated card |
| `nexora.surface.3` | `rgba(255,255,255,0.06)` | Highlighted card |
| `nexora.border.subtle` | `rgba(255,255,255,0.08)` | Structural layout lines |
| `nexora.border.mid` | `rgba(255,255,255,0.15)` | Component borders |
| `nexora.border.accent` | `rgba(255,255,255,0.30)` | Active/Focused borders |
| `nexora.text.primary` | `#F8FAFC` | Main reading text |
| `nexora.text.secondary` | `#94A3B8` | Descriptions & metadata |
| `nexora.text.muted` | `#475569` | Decorative & ambient data |
| `nexora.green` | `#00FF00` | **LIVE**: Raining highlights, executing nodes |
| `nexora.indigo` | `#818CF8` | **ACTION**: Primary buttons, links, user focus |
| `nexora.amber` | `#FCD34D` | **WARNING**: Methodological contradictions |
| `nexora.red` | `#F87171` | **DANGER**: Direct contradictions |
| `nexora.blue` | `#60A5FA` | **SCOPE**: Out-of-bounds findings |

---

## 🔡 Typography

Strict Monospace Mandate: No Sans-Serif fonts allowed.

- **Stack**: `ui-monospace, "Cascadia Code", "Fira Code", monospace`
- **Heading XL**: `4rem`, Bold (700), Tracking-widest, Uppercase
- **Heading L**: `2.5rem`, Bold (700), Tracking-wider, Uppercase
- **Heading M**: `1.25rem`, Semibold (600), Tracking-wide
- **Body**: `0.875rem`, Regular (400), Tracking-wide, Leading-7
- **Caption/Status**: `0.6875rem`, Regular (400), Tracking-widest, Uppercase, Opacity 0.5

---

## 🎬 Motion Language

- **TextScramble**: Characters cycle through `!<>-_/[]{}—=+*^?#` before resolving (40 frames). Usage: Page titles, queries.
- **RainAnimation**: 300 descending characters, random speed/reset. Usage: Hero background.
- **StatusPulse**: Opacity `0.4 → 1.0 → 0.4` (2s loop). Usage: Execution badges.
- **SlideIn**: `translateX(-16px) → 0`, Opacity `0 → 1` (250ms). Usage: Timeline steps.
- **ScaleReveal**: `scale(0.95) → 1`, Opacity `0 → 1` (200ms). Usage: Modals/Panels.

---

## 📡 Ambient Data Patterns

- **Coordinates**: Every major view contains coordinate readouts in the top-right (`LAT/LONG` or `SESSION_ID`).
- **System Status**: Bottom-left persistent telemetry (`SYSTEM.ACTIVE`, `V1.0.0`).
- **Frame Counter**: Bottom-right animation counter (`FRAME: {n}`).
- **Corner Accents**: 8px–12px L-brackets (`border-white/20`) defining container boundaries.

---

## ⚖️ The 5 Design Rules

1. **Every font is monospace.** No exceptions.
2. **Color is earned.** Green means **LIVE**. Red means **DANGER**. Indigo means **ACT**. White means **READ**.
3. **The terminal shows its own status.** Every panel knows its own coordinates and version.
4. **Motion has meaning.** `TextScramble` = Updating. `Rain` = System Vitality. `Pulse` = Busy.
5. **Borders are structure.** Shadow is for depth only (modals), never for decoration.
6. **Data is active.** Every node and edge must represent a live or historical research state.

---

## 8. Technical Manifest & Integration

The interface is built for high-throughput observability of autonomous agents.

- **SSE Stream**: All events are delivered via a persistent EventSource connection.
- **Graph Engine**: D3.js force-directed layouts with strict coordinate snapping.
- **State Management**: Zustand-powered reactive store for real-time telemetry.
- **Accessibility**: Monospace mandate ensures high legibility for technical analysis.
