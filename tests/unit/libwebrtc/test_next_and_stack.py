"""Pure helpers for the libwebrtc view's Next-update and Patch-stack
sub-views."""

from datetime import date

from reviewstats.libwebrtc import (
    build_next_update,
    count_patches,
    gitiles_date,
    known_history,
    main_position,
    month_samples,
    parse_env_vars,
    parse_rel_target,
    plan_history,
    project_view,
)


class TestConfigEnv:
    def test_one_parser_for_every_key(self):
        text = ('export MOZ_FASTFORWARD_BUG="2072400"\n'
                "export MOZ_NEXT_FIREFOX_REL_TARGET=159\n"
                "# export MOZ_NEXT_FIREFOX_REL_TARGET=1\n"
                "MOZ_LOCAL=x\n")
        assert parse_env_vars(text) == {"MOZ_FASTFORWARD_BUG": "2072400",
                                        "MOZ_NEXT_FIREFOX_REL_TARGET": "159",
                                        "MOZ_LOCAL": "x"}
        assert parse_rel_target(text) == (159, 2072400)

    def test_missing_values_are_none(self):
        assert parse_rel_target("") == (None, None)


SCHEDULE = {156: ("2026-09-28", "2026-10-20"), 157: ("2026-10-12", "2026-11-03"),
            158: ("2026-10-26", "2026-11-17")}
TRAINS = {159: ("2026-09-24", "2026-10-08"), 160: ("2026-10-08", "2026-10-22"),
          161: ("2026-10-22", "2026-11-05"), 162: ("2026-11-05", "2026-11-19")}
LAG = {"last_vendored": "2026-09-18", "upstream_head": "2026-10-05", "behind": 201}


def _next(**kw):
    args = dict(milestone=155, rel_target=159, fastforward_bug=2072400,
                in_progress=False, schedule=SCHEDULE, trains=TRAINS, lag=LAG)
    args.update(kw)
    return build_next_update(**args)


class TestBuildNextUpdate:
    def test_current_update_has_its_beta_merge_deadline(self):
        assert _next()["current"] == {"milestone": 155, "firefox": 159,
                                      "fastforward_bug": 2072400, "in_progress": False,
                                      "deadline": "2026-10-08"}

    def test_upcoming_milestones_are_projected_one_per_train(self):
        up = _next()["upcoming"]
        assert [(u["milestone"], u["firefox"]) for u in up] == [
            (156, 160), (157, 161), (158, 162)]
        assert up[0] == {"milestone": 156, "firefox": 160,
                         "chrome_branch": "2026-09-28", "chrome_stable": "2026-10-20",
                         "nightly_start": "2026-10-08", "merge_day": "2026-10-22"}

    def test_a_milestone_too_late_for_its_train_loses_the_projection(self):
        """Cadences drift (Chrome's M159 -> M160 is three weeks). A milestone
        that branches on or after the train's Beta merge can't be in it."""
        late = {**SCHEDULE, 157: ("2026-11-05", "2026-11-24")}
        up = _next(schedule=late)["upcoming"][1]
        assert up["firefox"] is None and up["merge_day"] is None
        assert up["chrome_branch"] == "2026-11-05"

    def test_unscheduled_dates_stay_blank(self):
        up = _next(schedule={}, trains={})["upcoming"]
        assert up[0]["chrome_branch"] is None and up[0]["merge_day"] is None
        assert _next(trains={})["current"]["deadline"] is None

    def test_lag_passes_through(self):
        assert _next()["lag"] == LAG
        assert _next(lag=None)["lag"] is None


class TestGitiles:
    def test_dates_with_and_without_offset(self):
        assert gitiles_date("Mon Oct 05 15:02:17 2026") == "2026-10-05"
        assert gitiles_date("Thu Sep 24 09:00:00 2026 +0000") == "2026-09-24"

    def test_main_position_of_a_main_commit(self):
        assert main_position("x\n\nCr-Commit-Position: refs/heads/main@{#48794}\n") == 48794

    def test_branch_head_commit_uses_its_branch_point(self):
        msg = ("x\n\nCr-Commit-Position: refs/branch-heads/8059@{#1}\n"
               "Cr-Branched-From: 8d208e76fb-refs/heads/main@{#48593}\n")
        assert main_position(msg) == 48593

    def test_no_position_is_none(self):
        assert main_position("no footers") is None


class TestPatchStackHistory:
    def test_counts_only_patch_files(self):
        entries = [{"name": "s0001.patch"}, {"name": "s0002.patch"},
                   {"name": "README.md"}, {"name": "s0003.patch.orig"}]
        assert count_patches(entries) == 2

    def test_month_samples_end_on_today_and_go_back(self):
        assert month_samples(date(2026, 10, 5), 3) == [
            ("2026-08", "2026-08-31"), ("2026-09", "2026-09-30"),
            ("2026-10", "2026-10-05")]

    def test_month_samples_cross_a_year(self):
        assert month_samples(date(2026, 1, 10), 2) == [
            ("2025-12", "2025-12-31"), ("2026-01", "2026-01-10")]

    def test_final_points_are_reused_and_the_current_month_left_out(self):
        known = {"2026-09": {"month": "2026-09", "count": 149, "sampled": "2026-09-30"}}
        reuse, fetch = plan_history(date(2026, 10, 5), known)
        assert reuse == known
        assert ("2026-09", "2026-09-30") not in fetch
        assert all(m != "2026-10" for m, _ in fetch)
        assert len(fetch) == 10

    def test_a_mid_month_sample_is_refetched_once_the_month_closes(self):
        """Last week's run sampled September on the 28th; that is not the
        end-of-month value the chart claims, so fetch it again."""
        known = {"2026-09": {"month": "2026-09", "count": 148, "sampled": "2026-09-28"}}
        reuse, fetch = plan_history(date(2026, 10, 5), known)
        assert "2026-09" not in reuse and ("2026-09", "2026-09-30") in fetch

    def test_points_without_a_sample_date_are_refetched(self):
        """Files written before sample dates were recorded."""
        reuse, _ = plan_history(date(2026, 10, 5),
                                {"2026-09": {"month": "2026-09", "count": 149}})
        assert reuse == {}

    def test_known_history_from_last_weeks_file(self):
        point = {"month": "2026-09", "count": 145, "sampled": "2026-09-30"}
        assert known_history({"patch_stack": {"history": [point]}}) == {"2026-09": point}
        assert known_history(None) == {} and known_history({"rows": []}) == {}


class TestProjectionCoversTheNewSubviews:
    """The whitelist covers the new sections too, nested fields included,
    so nothing but these fields reaches the public page."""

    VIEW = {
        "chrome_stable": 154, "as_of": "2026-10-05", "rows": [],
        "next_update": {
            "as_of": "2026-10-05",
            "current": {"milestone": 155, "firefox": 159, "fastforward_bug": 1,
                        "in_progress": False, "deadline": "2026-10-08",
                        "missing": ["x"]},
            "upcoming": [{"milestone": 156, "firefox": 160, "chrome_branch": None,
                          "chrome_stable": None, "nightly_start": None,
                          "merge_day": None, "sha": "f"}, None],
            "lag": {**LAG, "commits": ["c"]},
            "extra": 1,
        },
        "patch_stack": {"as_of": "2026-10-05",
                        "releases": [{"label": "Nightly", "count": 1, "names": []}],
                        "history": [{"month": "2026-10", "count": 1,
                                     "sampled": "2026-10-05", "x": 1}],
                        "change": 3},
    }

    def test_unknown_fields_are_dropped_everywhere(self):
        got = project_view(self.VIEW)
        assert "missing" not in got["next_update"]["current"]
        assert "sha" not in got["next_update"]["upcoming"][0]
        assert "commits" not in got["next_update"]["lag"]
        assert "extra" not in got["next_update"]
        assert "names" not in got["patch_stack"]["releases"][0]
        assert "x" not in got["patch_stack"]["history"][0]
        assert "change" not in got["patch_stack"]

    def test_null_list_entries_are_dropped(self):
        """A None entry would throw in the page's renderer."""
        assert len(project_view(self.VIEW)["next_update"]["upcoming"]) == 1

    def test_sections_keep_their_own_as_of(self):
        got = project_view(self.VIEW)
        assert got["next_update"]["as_of"] == got["patch_stack"]["as_of"] == "2026-10-05"
