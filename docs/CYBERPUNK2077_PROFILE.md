# Cyberpunk 2077 — soloPAW v2.8 profile

Current public profile: `soloPAW-Cyberpunk2077-v2.8-JDirect-ScanH-QuickW.json`

## Current mouse-side map

| G502 control | Normal | Double | Hold | G-Shift tap | G-Shift double | G-Shift hold |
|---|---|---|---|---|---|---|
| G4 | `S` | Right Shift sprint toggle | held `S` | same normal mapping | same | same |
| G5 | held `J` | — | held `J` | `R` | held `E` ~1.93 s | held `R` |
| G6 | soloPAW modifier | — | modifier held | — | — | — |
| G7 | Space | natural repeated Space taps | held `/` | `C` | held `Z` ~1.93 s | held `C` |
| G8 | Left Ctrl | `1` | held `B` | `H` | `3` | held `O` |
| G9 | `T` | `M` | held `T` | `[` | `K` | `W` |
| Wheel Click | `F` | — | held `F` | `L` | — | — |
| Left Tilt | held `A` | — | held `A` | `Q` | none | `V` |
| Right Tilt | held `D` | — | held `D` | Esc | none | Esc |
| LMB | native LMB | — | native hold | `X` | — | held `X` |
| RMB | native RMB | — | native hold | MMB | `N` | held MMB |
| Wheel Up | native passthrough | — | native/free-spin | native | — | — |
| Wheel Down | native passthrough | — | native/free-spin | native | — | — |

G8's single/double classifier uses the accepted **225 ms** double window so Left Ctrl/Dash remains responsive.

## Matching Cyberpunk key-binding decisions

- Move Forward / Swim Forward → `J`
- Vehicle Accelerate → `J`
- Move Backward → `S`
- Vehicle Brake → `S`
- UI Up remains Cyberpunk's forced `W`
- Scan Toggle → `H`
- BrainDance Analysis → `H`
- Quicksave → `W`
- Main Menu → `L`
- BrainDance Change Layer → `L`
- Jump → Space
- Dodge/Dash → Left Ctrl
- Left/Right movement → `A` / `D`

The shared `L` binding is contextual: Main Menu during normal play and Change Layer during BrainDance. The shared `W` binding remains usable for Quicksave while Cyberpunk retains W for UI Up.

## Reference control-density audit

The detailed v2.5 audit reviewed **87 visible Cyberpunk binding rows** and found **65 covered rows (74.7%)**. Under the same methodology, the v2.8 layout retains those rows and adds direct Main Menu access through contextual `L`, producing **66 / 87 = 75.9%** reference coverage.

This is a transparent reference count, not a claim that 75.9% of every possible Cyberpunk action, mod, platform binding, or future game version is covered. Hold/toggle rows count separately when Cyberpunk exposes them separately, and Wheel Up/Down count as distinct inputs.

See [`CYBERPUNK_REFERENCE_AUDIT_v2.5.md`](CYBERPUNK_REFERENCE_AUDIT_v2.5.md) for the original methodology.
