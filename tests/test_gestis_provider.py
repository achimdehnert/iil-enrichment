"""Tests for GESTIS provider — mock HTTP, verify property extraction."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from enrichment.providers.gestis import GESTISProvider
from enrichment.types import ValueType


@pytest.fixture()
def provider():
    return GESTISProvider(timeout=5)


@pytest.fixture()
def _mock_session(provider):
    """Patch requests.Session so no real HTTP calls are made."""
    session = MagicMock()
    provider._session = session
    return session


SEARCH_HIT = {
    "zvg_nr": "001140",
    "name": "Aceton",
    "cas_nr": "67-64-1",
}

ARTICLE_RESPONSE = {
    "name": "Aceton",
    "chapters": {
        "01": {
            "text": "Identifikation",
            "sub_chapters": [
                {
                    "number": "0100",
                    "text": "EG Nr: 200-662-2 EINECS",
                },
            ],
        },
        "04": {
            "text": "Molekulardaten",
            "sub_chapters": [
                {
                    "number": "0400",
                    "text": "C3H6O Molare Masse: 58,08",
                },
            ],
        },
        "06": {
            "text": "Physikalische Daten",
            "sub_chapters": [
                {
                    "number": "0602",
                    "text": "-94,7 °C",
                },
                {
                    "number": "0603",
                    "text": "56,2 °C",
                },
                {
                    "number": "0604",
                    "text": "-20 °C",
                },
                {
                    "number": "0608",
                    "text": "Dichte: 0,79 g/cm³ Temperaturklasse: T1",
                },
                {
                    "number": "0609",
                    "text": "2,5 - 12,8 Vol% Explosionsgruppe: IIA",
                },
            ],
        },
        "07": {
            "text": "AGW",
            "sub_chapters": [
                {"number": "0700", "text": "500 ml/m³ (1200 mg/m³)"},
            ],
        },
        "13": {
            "text": "GHS-Einstufung",
            "sub_chapters": [
                {
                    "number": "1303",
                    "text": (
                        "Gefahr H225 H319 H336 "
                        "Entzündbare Flüssigkeiten Kategorie 2"
                    ),
                },
            ],
        },
        "12": {
            "text": "Regelungen",
            "sub_chapters": [
                {"number": "1209", "text": "TRGS 510 Lagerung"},
                {"number": "1210", "text": "DGUV Regel 113-001"},
                {"number": "1208", "text": "REACH Registrierung"},
            ],
        },
    },
}


class TestGESTISCanEnrich:
    def test_should_accept_cas(self, provider):
        assert provider.can_enrich("substance", "67-64-1") is True

    def test_should_accept_name(self, provider):
        assert provider.can_enrich("substance", "Aceton") is True

    def test_should_reject_short_name(self, provider):
        assert provider.can_enrich("substance", "AB") is False

    def test_should_reject_empty(self, provider):
        assert provider.can_enrich("substance", "") is False

    def test_should_reject_wrong_domain(self, provider):
        assert provider.can_enrich("trading", "67-64-1") is False


class TestGESTISEnrich:
    def test_should_extract_identity(self, provider, _mock_session):
        """Name, CAS, EC number from search hit + article."""
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = [SEARCH_HIT]
        article_resp = MagicMock(status_code=200)
        article_resp.json.return_value = ARTICLE_RESPONSE
        _mock_session.get.side_effect = [search_resp, article_resp]

        result = provider.enrich("substance", "67-64-1")

        assert result.source == "GESTIS"
        assert result.properties["name"].value == "Aceton"
        assert result.properties["cas_number"].value == "67-64-1"
        assert result.properties["ec_number"].value == "200-662-2"

    def test_should_extract_physical_properties(self, provider, _mock_session):
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = [SEARCH_HIT]
        article_resp = MagicMock(status_code=200)
        article_resp.json.return_value = ARTICLE_RESPONSE
        _mock_session.get.side_effect = [search_resp, article_resp]

        result = provider.enrich("substance", "67-64-1")

        assert result.properties["melting_point_c"].value == pytest.approx(-94.7)
        assert result.properties["boiling_point_c"].value == pytest.approx(56.2)
        assert result.properties["flash_point_c"].value == pytest.approx(-20.0)
        assert result.properties["density"].value == pytest.approx(0.79)

    def test_should_extract_ghs(self, provider, _mock_session):
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = [SEARCH_HIT]
        article_resp = MagicMock(status_code=200)
        article_resp.json.return_value = ARTICLE_RESPONSE
        _mock_session.get.side_effect = [search_resp, article_resp]

        result = provider.enrich("substance", "67-64-1")

        assert "H225" in result.properties["h_statements"].value
        assert "H319" in result.properties["h_statements"].value
        assert result.properties["signal_word"].value == "danger"
        assert result.properties["is_cmr"].value is False
        assert result.properties["ghs_einstufung"].value_type == ValueType.TEXT

    def test_should_extract_explosion_details(self, provider, _mock_session):
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = [SEARCH_HIT]
        article_resp = MagicMock(status_code=200)
        article_resp.json.return_value = ARTICLE_RESPONSE
        _mock_session.get.side_effect = [search_resp, article_resp]

        result = provider.enrich("substance", "67-64-1")

        assert result.properties["temperature_class"].value == "T1"
        assert result.properties["explosion_group"].value == "IIA"
        assert "explosion_limits" in result.properties

    def test_should_extract_regulations(self, provider, _mock_session):
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = [SEARCH_HIT]
        article_resp = MagicMock(status_code=200)
        article_resp.json.return_value = ARTICLE_RESPONSE
        _mock_session.get.side_effect = [search_resp, article_resp]

        result = provider.enrich("substance", "67-64-1")

        regs = result.properties["regulations"].value
        assert any("TRGS 510" in r for r in regs)
        assert any("DGUV" in r for r in regs)

    def test_should_extract_molecular_data(self, provider, _mock_session):
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = [SEARCH_HIT]
        article_resp = MagicMock(status_code=200)
        article_resp.json.return_value = ARTICLE_RESPONSE
        _mock_session.get.side_effect = [search_resp, article_resp]

        result = provider.enrich("substance", "67-64-1")

        assert result.properties["molecular_formula"].value == "C3H6O"
        assert result.properties["molecular_weight"].value == "58,08"

    def test_should_handle_search_not_found(self, provider, _mock_session):
        resp = MagicMock(status_code=200)
        resp.json.return_value = []
        _mock_session.get.return_value = resp

        result = provider.enrich("substance", "99-99-9")

        assert result.is_empty
        assert result.confidence == 0.0

    def test_should_handle_api_error(self, provider, _mock_session):
        _mock_session.get.side_effect = ConnectionError("timeout")

        result = provider.enrich("substance", "67-64-1")

        assert result.is_empty
        assert result.confidence == 0.0

    def test_should_detect_cmr(self, provider, _mock_session):
        """H350 → is_cmr True."""
        hit = {**SEARCH_HIT}
        article = {
            "name": "Benzol",
            "chapters": {
                "13": {
                    "text": "",
                    "sub_chapters": [{
                        "number": "1303",
                        "text": "Gefahr H225 H350 H304 H315",
                    }],
                },
            },
        }
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = [hit]
        article_resp = MagicMock(status_code=200)
        article_resp.json.return_value = article
        _mock_session.get.side_effect = [search_resp, article_resp]

        result = provider.enrich("substance", "71-43-2")

        assert result.properties["is_cmr"].value is True

    def test_should_store_gestis_url(self, provider, _mock_session):
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = [SEARCH_HIT]
        article_resp = MagicMock(status_code=200)
        article_resp.json.return_value = ARTICLE_RESPONSE
        _mock_session.get.side_effect = [search_resp, article_resp]

        result = provider.enrich("substance", "67-64-1")

        assert "001140" in result.properties["gestis_url"].value
        assert result.properties["gestis_zvg"].value == "001140"
