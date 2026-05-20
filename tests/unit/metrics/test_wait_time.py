from reviewstats.wait_time import (
    bucket_wait_days,
    first_review_timestamp,
    percentile_days,
    wait_time_days,
)


class TestFirstReviewTimestamp:
    def test_ignores_author_transactions(self):
        txs = [
            {"type": "update", "authorPHID": "PHID-USER-author", "dateCreated": 100},
            {"type": "comment", "authorPHID": "PHID-USER-author", "dateCreated": 101},
            {"type": "comment", "authorPHID": "PHID-USER-reviewer", "dateCreated": 200},
        ]
        assert first_review_timestamp(txs, author_phid="PHID-USER-author") == 200

    def test_accepts_status_change(self):
        txs = [
            {"type": "accept", "authorPHID": "PHID-USER-reviewer", "dateCreated": 150},
        ]
        assert first_review_timestamp(txs, author_phid="PHID-USER-author") == 150

    def test_returns_none_when_no_review_action(self):
        txs = [
            {"type": "update", "authorPHID": "PHID-USER-author", "dateCreated": 100},
        ]
        assert first_review_timestamp(txs, author_phid="PHID-USER-author") is None

    def test_returns_earliest(self):
        txs = [
            {"type": "comment", "authorPHID": "PHID-USER-r1", "dateCreated": 300},
            {"type": "accept",  "authorPHID": "PHID-USER-r2", "dateCreated": 250},
        ]
        assert first_review_timestamp(txs, author_phid="PHID-USER-author") == 250

    def test_skips_bot_actors(self):
        # `phab-bot` / herald rules add transactions but aren't human reviews.
        txs = [
            {"type": "comment", "authorPHID": "PHID-APPS-PhabricatorHeraldApplication", "dateCreated": 100},
            {"type": "comment", "authorPHID": "PHID-USER-reviewer", "dateCreated": 200},
        ]
        assert first_review_timestamp(txs, author_phid="PHID-USER-author") == 200


class TestWaitTimeDays:
    def test_basic(self):
        # 2 days = 172800 seconds
        assert wait_time_days(date_created=1_000_000, first_review=1_172_800) == 2.0

    def test_none_when_no_review(self):
        assert wait_time_days(date_created=1_000_000, first_review=None) is None


class TestBucketWaitDays:
    def test_under_one_day(self):
        assert bucket_wait_days(0.4) == "< 1 day"

    def test_one_to_three(self):
        assert bucket_wait_days(2.0) == "1-3 days"

    def test_three_to_seven(self):
        assert bucket_wait_days(5.0) == "3-7 days"

    def test_one_to_two_weeks(self):
        assert bucket_wait_days(10.0) == "1-2 weeks"

    def test_two_to_four_weeks(self):
        assert bucket_wait_days(20.0) == "2-4 weeks"

    def test_over_one_month(self):
        assert bucket_wait_days(45.0) == "> 1 month"


class TestPercentileDays:
    def test_median(self):
        assert percentile_days([1, 2, 3, 4, 5], 50) == 3

    def test_p90(self):
        # Linear interpolation: rank 0.9 * 9 = 8.1 → 9 + 0.1*(10-9) = 9.1
        assert percentile_days([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 90) == 9.1

    def test_empty(self):
        assert percentile_days([], 50) is None
