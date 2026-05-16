import json
from unittest.mock import patch, MagicMock

from reviewstats.phab import (
    _batches,
    build_form_payload,
    parse_revision_search_response,
)


class TestBatches:
    def test_chunks_evenly(self):
        assert list(_batches([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]

    def test_fewer_than_size(self):
        assert list(_batches([1, 2], 5)) == [[1, 2]]

    def test_empty(self):
        assert list(_batches([], 5)) == []


class TestBuildFormPayload:
    def test_encodes_scalar(self):
        out = build_form_payload({"api.token": "tok", "method": "x"})
        assert "api.token=tok" in out
        assert "method=x" in out

    def test_encodes_list_with_bracket_index(self):
        out = build_form_payload(
            {"api.token": "tok", "constraints[ids][]": [1, 2, 3]}
        )
        assert "constraints%5Bids%5D%5B0%5D=1" in out
        assert "constraints%5Bids%5D%5B1%5D=2" in out
        assert "constraints%5Bids%5D%5B2%5D=3" in out


class TestParseRevisionSearchResponse:
    def test_extracts_id_phid_and_dates(self):
        raw = {
            "result": {
                "data": [
                    {
                        "id": 12345,
                        "phid": "PHID-DREV-abc",
                        "fields": {
                            "title": "Bug 1 - Fix",
                            "authorPHID": "PHID-USER-xyz",
                            "dateCreated": 1700000000,
                            "dateModified": 1700100000,
                        },
                    }
                ]
            }
        }
        parsed = parse_revision_search_response(raw)
        assert parsed["D12345"]["phid"] == "PHID-DREV-abc"
        assert parsed["D12345"]["author_phid"] == "PHID-USER-xyz"
        assert parsed["D12345"]["date_created"] == 1700000000
        assert parsed["D12345"]["date_modified"] == 1700100000

    def test_handles_empty(self):
        assert parse_revision_search_response({"result": {"data": []}}) == {}

    def test_surfaces_error(self):
        import pytest
        with pytest.raises(RuntimeError, match="ERR-CONDUIT"):
            parse_revision_search_response(
                {"error_code": "ERR-CONDUIT", "error_info": "boom"}
            )
