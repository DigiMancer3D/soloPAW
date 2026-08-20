# soloPAW design philosophy

## One mouse, fewer reaches

soloPAW treats a gaming mouse as a compact control surface rather than a pointer with a few extra buttons. The goal is to put the right actions under fingers that can reach them quickly and repeatedly.

Useful scenarios include one-handed and mouse-first gameplay, reduced keyboard reaching, accessibility experiments, streamers changing games, advanced per-game controls, and editing/creative-tool layouts.

Accessibility needs vary. soloPAW is a toolkit and reference design, not a universal prescription or medical device.

## Why a G502-style layout?

Dense MMO/numpad mice can expose more raw buttons, which can be excellent for coding, editing, or applications with many discrete shortcuts. soloPAW's gameplay approach favors **spatially distinct controls**: thumb buttons, top buttons, wheel click, wheel tilt, primary buttons, and a shift layer.

That can reduce the need to locate one key inside a dense side grid while preserving hardware behavior such as the G502's free-spin vertical wheel.

## Context is a feature

A single output can represent different actions in different game modes when the game itself distinguishes those contexts. soloPAW optimizes for contextual density while avoiding combinations that interfere with critical gameplay.

## Direct keys when games require them

Not every game accepts macro-like input equally. The Megabonk profile is a direct-key example where jump, slide, map-hold, and interaction are ordinary injected key presses/holds.

## Preserve rollback

soloPAW profiles are versioned instead of overwritten. New experiments should create a new profile, preserve the last accepted profile, and only become autoload after runtime testing.
