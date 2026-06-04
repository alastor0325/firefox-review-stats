# Summary baselines

Snapshots of the Recent Changes per-area overviews at a point in time, kept
for **model comparison**. Each `baseline-<date>-<model>.json` records, per
team / window / feature area:

- `label`, `count`, `feature`
- `summary` — the overview text that model produced
- `patch_subjects` — the **inputs** the overview was generated from

Because the inputs are captured alongside the output, a different model can
later be run on the *same* `patch_subjects` and the results diffed against a
baseline — e.g. comparing the Claude-Opus baseline against a smaller model
(GitHub Models) once that path is wired up.

`baseline-2026-06-04-opus.json` — the initial Claude-authored (Opus-grade)
overviews, captured before introducing the GitHub Models backend.
