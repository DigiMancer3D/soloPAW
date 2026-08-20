# Changelog

## v0.1.0-rc.1 — Release Seal & Recovery

- Promoted the user-verified Alpha 6 desktop build to release candidate status.
- Removed development-only tests, historical GUI screenshots, roadmap material, generated preview artwork, and unused reference assets from the distributable runtime.
- Added `verify_release.sh`, `RELEASE_MANIFEST.json`, and per-file SHA256 verification.
- Added `RECOVERY.md` covering `.udata`, complete export bundles, Input Remapper profiles, user preferences, desktop reinstall, and launch logs.
- Preserved schema-v5 migration, single-route connectors, multi-selection/alignment, controller transforms, gesture authoring, dependency safety, complete export bundles, KDE desktop integration, MIME association, and direct `.udata` opening.
- Revalidated the current user-authored `soloPAW_Cyberpunk2077_v2.2_2.3.udata` against the RC runtime without modifying the source project.

## Development lineage

- Alpha 6 — CachyOS Desktop Build + Release Polish.
- Alpha 5 — Single-Route Connectors + Advanced Authoring.
- Alpha 4 — Authoring Ergonomics + Image/Save Reliability.
- Alpha 3 — Structured G502 Macros + Dependency Safety.
- Alpha 2 — GUI Panel Update + Visual Authoring + Mapping Intelligence.
- Alpha 1 — WYSIWYG map foundation and linked `.udata`/PNG/Remapper/Binding exports.
