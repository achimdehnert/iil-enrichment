"""Tests for GHS hazard statement utilities."""

from __future__ import annotations

from enrichment.ghs import H_STATEMENTS_DE, h_codes_to_descriptions


class TestHStatementsDE:
    def test_should_contain_common_codes(self):
        assert "H225" in H_STATEMENTS_DE
        assert "H350" in H_STATEMENTS_DE
        assert "H400" in H_STATEMENTS_DE

    def test_should_have_german_descriptions(self):
        assert "entzündbar" in H_STATEMENTS_DE["H225"]
        assert "Krebs" in H_STATEMENTS_DE["H350"]


class TestHCodesToDescriptions:
    def test_should_return_sorted_descriptions(self):
        result = h_codes_to_descriptions({"H319", "H225"})
        assert len(result) == 2
        assert result[0].startswith("H225:")
        assert result[1].startswith("H319:")

    def test_should_skip_unknown_codes(self):
        result = h_codes_to_descriptions({"H999", "H225"})
        assert len(result) == 1
        assert "H225" in result[0]

    def test_should_handle_empty_set(self):
        assert h_codes_to_descriptions(set()) == []

    def test_should_accept_list_input(self):
        result = h_codes_to_descriptions(["H336", "H225"])
        assert len(result) == 2
        assert result[0].startswith("H225:")
