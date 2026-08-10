#!/usr/bin/env python3
"""Turn probe results into the cross-browser support data the page renders.

    .venv/bin/python tools/media-caps/run_probe.py      # ask the browsers
    .venv/bin/python tools/media-caps/build_matrix.py   # build the table

Writes `<team>/data_mediacaps.json`. Thin I/O; the transform is in
`reviewstats.mediacaps`.

Re-run both whenever you want fresh answers — that is the point of doing this
with a probe page rather than by reading engine source. The source-derived matrix
this replaces claimed Chrome plays PCM and AC-3 in Matroska, because Chromium
lists both in its codec set; shipping Chrome answers `no` to both.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from reviewstats.mediacaps import (  # noqa: E402
    SURFACES,
    build_api_table,
    build_conformance,
    build_container_view,
    build_support_matrix,
)

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def load_results() -> list:
    out = []
    for f in sorted(RESULTS.glob("*.json")):
        if f.name == "summary.json":
            continue
        out.append(json.loads(f.read_text(encoding="utf-8")))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--team", default="playback")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2]))
    args = ap.parse_args(argv)

    results = load_results()
    if not results:
        print(f"No probe results in {RESULTS}. Run run_probe.py first.",
              file=sys.stderr)
        return 1

    payload = {
        "probed_at": max((r.get("probedAt") or "") for r in results),
        "browsers": [{
            "target": r.get("target"), "label": r.get("label"),
            "version": r.get("browser_version"),
            "is_proxy_for_safari": bool(r.get("is_proxy_for_safari")),
            "is_nonshipping_build": bool(r.get("is_nonshipping_build")),
        } for r in results],
        "surfaces": {s: build_support_matrix(results, surface=s) for s in SURFACES},
        # Container-first grouping is what the page renders; the flat
        # disagreement lists above are kept for the counts.
        "by_container": build_container_view(results),
        "conformance": build_conformance(results),
        "apis": build_api_table(results),
    }

    path = Path(args.out) / args.team / "data_mediacaps.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Wrote {path.name}")
    for s, m in payload["surfaces"].items():
        c = m["counts"]
        print(f"  {s:12s} {c['total']:3d} combos: {c['differing']:3d} differ "
              f"({c['we_lack']} where Firefox lacks it), {c['agreed']} agree, "
              f"{c.get('indeterminate', 0)} unanswered")
    print(f"  apis         {len(payload['apis'])} tracked across "
          f"{len(payload['browsers'])} engines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
