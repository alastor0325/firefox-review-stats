# Media Health access control — design & plan

**Status:** proposed, not started
**Date:** 2026-08-10
**Context:** the Media Health view (`36694c9`, branch `media-health-roadmap-prototype`) is
not yet pushed to `origin/main`. Nothing confidential has been published, so this is a
clean-slate decision rather than a cleanup.

---

## The problem

The Roadmap subview carries candid internal assessment — partner names, contested
ownership, individual owners. The dashboard is published to a public GitHub Pages site
built from a public repo. We want the roadmap visible to Mozillians only, without giving
up the public site.

## Decisions

| # | Decision |
|---|---|
| 1 | **Roadmap is confidential. Metrics is public.** Metrics derives entirely from Treeherder Perfherder (framework 13) and locally-run browser capability probes. Nothing in it is non-public in origin. |
| 2 | **Keep the current public repo and site.** `alastor0325/firefox-review-stats` → `alastor0325.github.io/firefox-review-stats/` stays exactly as it is. No migration, no URL change. |
| 3 | **The Media Health tab stays visible on the public site**, carrying Metrics inline and a sign-in gate where Roadmap would be. |
| 4 | **Quick is the internal host.** `quick.mozilla.cloud` is Mozilla's MoCo-SSO'd static hosting, explicitly sanctioned for confidential Mozilla data. It supersedes the Cloudflare Access and GitHub-Enterprise-Pages options considered earlier. |
| 5 | **Keep the `internal:` redaction layer in `roadmap.py`.** Quick is MoCo-wide, not media-team-scoped, so redaction still does real work — peer-team discretion rather than public-vs-not. |

## Chosen architecture

One codebase, two artifacts.

**Public build** (GitHub Actions, weekly cron → committed → Pages)
Renders with no roadmap payload. Media Health tab present; Metrics subview populated;
Roadmap subview shows a gate card with a "Load Roadmap" button.

**Internal build** (local → `quick deploy`)
Same code, roadmap YAML present, `--roadmap-audience internal`. Full page, both subviews.

**The bridge** — how the public page shows roadmap data without ever storing it.
Clicking "Load Roadmap" opens a popup to a small `bridge.html` hosted on Quick. The popup
is a top-level navigation, so it is a first-party context: the SSO cookie is sent normally
and IAP's login flow works as designed. `bridge.html` reads the roadmap JSON same-origin
and hands it back via `postMessage`, and the public page renders it inline.

```js
// public page
const QUICK = 'https://<app>.quick.mozilla.cloud';
const popup = window.open(QUICK + '/bridge.html', 'mh', 'width=520,height=640');
window.addEventListener('message', (e) => {
  if (e.origin !== QUICK) return;         // origin check is the security control
  renderRoadmap(e.data);
  popup.close();
});
```

```html
<!-- bridge.html, deployed to Quick -->
<script>
  fetch('/playback/roadmap.json')          // same-origin
    .then(r => r.json())
    .then(d => window.opener.postMessage(d, 'https://alastor0325.github.io'));
</script>
```

No CORS configuration needed on Quick, no third-party cookies, no framing. `bridge.html`
hardcodes its target origin, so it will only ever release data to our page.

## Rejected alternatives

Recorded so we don't relitigate them.

**Client-side password / obfuscated payload / unlisted URL.** Cosmetic. The data would sit
in a committed file in a public repo, fetchable from `raw.githubusercontent.com` and from
every clone, fork and archive. GitHub Pages has no server-side auth hook.

**Credentialed cross-origin `fetch()` from the public page to Quick.** Needs
`Access-Control-Allow-Origin` for our origin plus `Access-Control-Allow-Credentials`, a
`SameSite=None` session cookie, and a CORS-visible error when signed out. We control none
of it, and asking a confidential-data platform to whitelist a personal public origin for
credentialed reads is a request that *should* be refused — it would make any XSS on the
public page an exfiltration path for everyone's Quick content.

**`<iframe>` embed of the Quick page.** Requires Quick's session cookie in a third-party
context. Firefox partitions those under Total Cookie Protection and Safari blocks them
outright, so our own audience is the worst case. Google's login pages also refuse to be
framed, making the signed-out path unrecoverable.

**Move the whole dashboard to Quick.** Works, but gives up public visibility of the
review-load stats, which have value to non-MoCo contributors. Rejected in favour of
decision 2.

## Code seams (verified 2026-08-10)

The architecture already has most of what this needs.

- `reviewstats/render.py:27` — `render_html(roadmap_data=None, metrics_data=None)`.
  Placeholders serialize to `null`.
- `templates/index.html.tmpl:1378` — the Roadmap markup is **empty scaffolding**; all rows
  are injected by JS from `ROADMAP` (`:1460`). A `null` payload therefore means *no content
  in the file*, not CSS-hidden content. This is the property that makes the split safe.
- `templates/index.html.tmpl:1928` — `if (!ROADMAP)` hides the Media Health tab.
  **Must become `if (!ROADMAP && !METRICS)`** so the tab survives on the public build.
- `analyze_git.py:307` — `if roadmap_data and metrics_path.exists()`. **The `roadmap_data`
  condition must go**, or the public build silently loses Metrics too.
- `templates/index.html.tmpl:1129` — `data-health="roadmap"` is the default subview.
  Consider defaulting to `metrics` on the public build so the tab opens on real content
  rather than a gate card.
- `analyze_git.py:64` — `DEFAULT_ROADMAP_YAML` points outside the repo
  (`~/firefox-bug-investigation/roadmap/roadmap.yaml`), so CI physically cannot render it.
- `analyze_git.py:361` — `--roadmap-audience`, defaults to `public`.
- `reviewstats/roadmap.py` module docstring — already warns that `internal` output is a
  strict superset and that committing it publishes exactly the fields the annotation
  protects.

## Work plan

Ordered so the Quick unknowns are front-loaded and steps 1–3 are safe to do now.

**1. Gitignore the Media Health data artifacts — do first.**
`playback/data_metrics.json` is untracked and *not* ignored, and
`.github/workflows/refresh.yml` runs `git add -A index.html playback/ …`. The next cron
(Mondays 09:00 UTC) will commit it. The measured caps table needs no equivalent: it is derived from the
tracked `tools/media-caps/results/*.json` at render time, not committed.
*Not a leak today* — both are public-derived — but the wrong default once the section is
partly internal, and it keeps generated data out of the repo regardless.

**2. Decouple Metrics from Roadmap.** The two seams above (`:1928`, `analyze_git.py:307`)
plus tests. After this the public build renders a working Metrics-only Media Health tab.

**3. Public-side gate card.** Roadmap subview renders a "this is Mozilla-internal" card
with a button. Until the bridge exists the button is a plain link to Quick — useful on its
own and never wrong.

**4. Make the public build refuse rather than default.** Add an explicit `--no-media-health`
(or equivalent) and pass it in CI, so public-safety stops depending on the YAML happening
to be absent from the runner.

**5. Quick deploy of the internal build.** Separate, gitignored output directory so
`git add -A` is structurally unable to publish it.

**6. The bridge.** Only after the open questions below are answered.

## Open questions

**Q1 — Does `quick init --github` create a public or private repo under `mozilla/`?**
Decisive. If public, the committed HTML is public again and the SSO gate protects nothing;
we would use plain Quick (no `--github`) with source in a separate private repo.
`mozilla/firefox-review-stats` appeared unclaimed as of 2026-08-10.

**Q2 — Does pushing to that repo redeploy?** If yes, the weekly cron can drive the internal
build too. If not, Actions needs `gcloud`/`quick` credentials — significantly heavier.

**Q3 — Does COOP sever `window.opener` on the login path?** If the popup runs the full
chain (Quick → IAP → `accounts.google.com` → back), Google's `Cross-Origin-Opener-Policy:
same-origin` drops it into a fresh browsing-context group and `window.opener` becomes
`null` permanently. Workaround: `bridge.html` detects `!window.opener` and shows "Signed in
— click Load again"; the second click finds a session, skips the Google redirect, and the
opener survives. Decides whether the UX is one click or two. Prototype early.

**Q4 — Is a public-origin page an acceptable rendering surface for this data?**
Not a technical question. Nothing is ever stored in the public repo — the payload lives
only in an authenticated Mozillian's browser memory — but the public page becomes a trusted
consumer of confidential data, so a compromise of that page (bad commit, leaked Actions
token, XSS via injected report data) is an exfiltration path. The hardcoded `postMessage`
target origin is the mitigating control. **Worth a data-steward sign-off before step 6.**

## Downstream

`fx-bug-toolkit`'s `/open-team` skill hardcodes the site URL in three places
(`skills/open-team/skill.md:10,25,43`). This plan does not change the public URL, so no
update is needed — but if the Quick site becomes the primary entry point for the media
team, that skill should learn about it. `/bump-version` already treats fx-bug-toolkit sync
as mandatory.

## Notes

- Implementation must follow the dev loop in `.claude/skills/firefox-review-stats-dev/skill.md`
  per `CLAUDE.md`. This document is design only.
- Quick being fronted by Google Cloud IAP is **inferred** from the `gcloud` setup
  requirement, not read from documentation. Q3 depends on it; confirm before relying on it.
