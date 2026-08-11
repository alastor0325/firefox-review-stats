#!/usr/bin/env python3
"""Report what the probe results say, across engines.

    .venv/bin/python tools/media-caps/run_probe.py      # ask the browsers
    .venv/bin/python tools/media-caps/build_matrix.py   # summarise the answers

This **does not write** the dashboard's data any more. `analyze_git.py` rebuilds
the caps payload from `results/*.json` on every render, so there is no derived
file to keep in step -- a stored one went stale the moment the transform changed
and rendered the previous shape with every test passing.

So this is a read-only summary: run it to see what the last probe found without
regenerating the site.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from reviewstats.mediacaps import (  # noqa: E402
    build_conformance,
    build_payload,
)

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def load_results(directory: Path) -> list:
    """Every engine's probe output, in a stable order."""
    out = []
    for f in sorted(directory.glob("*.json")):
        if f.name == "summary.json":
            continue
        out.append(json.loads(f.read_text(encoding="utf-8")))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default=str(RESULTS))
    args = ap.parse_args(argv)

    payload = build_payload(load_results(Path(args.results)))
    if payload is None:
        print(f"No probe results in {args.results}. Run run_probe.py first.",
              file=sys.stderr)
        return 1

    print(f"Probed {payload['probed_at'][:10]} across "
          f"{len(payload['browsers'])} engines on "
          f"{payload.get('platform') or 'an unrecorded platform'}")
    for s, m in payload["surfaces"].items():
        c = m["counts"]
        print(f"  {s:12s} {c['total']:3d} combos: {c['differing']:3d} differ "
              f"({c['we_lack']} where Firefox lacks it), {c['agreed']} agree, "
              f"{c.get('indeterminate', 0)} unanswered")
    hidden = sum(st["hidden_none"]
                 for cont in payload["by_container"]["containers"]
                 for st in cont["surfaces"].values())
    print(f"  {hidden} rows no engine supports (counted, not listed)")
    print(f"  apis         {len(payload['apis'])} tracked")
    for w in payload.get("warnings") or []:
        print(f"  WARNING      {w}")

    # Reported here rather than on the dashboard, where the section was removed.
    # Still worth running: it is how the FlacDecoder::IsSupportedType bug turned
    # up -- Firefox accepts type strings that cannot exist because the codecs
    # parameter is never read.
    cf = build_conformance(load_results(Path(args.results)))
    wrong = [(r["type"], t) for r in cf.get("rows", [])
             for t, v in r["support"].items() if v in ("yes", "partial")]
    if wrong:
        print(f"  conformance  {len(wrong)} impossible type(s) wrongly accepted:")
        for ty, target in wrong:
            print(f"                 {target}: {ty}")
    else:
        print("  conformance  all impossible types correctly rejected")
    # A split or mixed-platform run is not a matrix, so this is an error for any
    # caller that checks -- CI must not commit results assembled from two runs.
    return 1 if payload.get("warnings") else 0


if __name__ == "__main__":
    sys.exit(main())
