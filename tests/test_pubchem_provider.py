"""Tests for PubChem provider — mock HTTP, verify property extraction."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from enrichment.providers.pubchem import PubChemProvider


@pytest.fixture()
def provider():
    return PubChemProvider(timeout=5)


@pytest.fixture()
def _mock_session(provider):
    session = MagicMock()
    provider._session = session
    return session


CID_RESPONSE = {"IdentifierList": {"CID": [180]}}

PROPERTY_RESPONSE = {
    "PropertyTable": {
        "Properties": [{
            "CID": 180,
            "MolecularFormula": "C3H6O",
            "MolecularWeight": 58.08,
            "IUPACName": "propan-2-one",
        }]
    }
}

GHS_RESPONSE = {
    "Record": {
        "Section": [{
            "Section": [
                {
                    "TOCHeading": "GHS Hazard Statements",
                    "Information": [{
                        "Value": {
                            "StringWithMarkup": [
                                {"String": "H225 Highly flammable liquid and vapour"},
                                {"String": "H319 Causes serious eye irritation"},
                                {"String": "H336 May cause drowsiness or dizziness"},
                            ]
                        }
                    }],
                },
                {
                    "TOCHeading": "Precautionary Statement Codes",
                    "Information": [{
                        "Value": {
                            "StringWithMarkup": [
                                {"String": "P210, P233, P240, P241"},
                            ]
                        }
                    }],
                },
                {
                    "TOCHeading": "GHS Signal Word",
                    "Information": [{
                        "Value": {
                            "StringWithMarkup": [
                                {"String": "Danger"},
                            ]
                        }
                    }],
                },
                {
                    "TOCHeading": "Pictogram(s)",
                    "Information": [{
                        "Value": {
                            "StringWithMarkup": [
                                {
                                    "String": "GHS02",
                                    "Markup": [{"Extra": "GHS07"}],
                                },
                            ]
                        }
                    }],
                },
            ]
        }]
    }
}


class TestPubChemCanEnrich:
    def test_should_accept_cas(self, provider):
        assert provider.can_enrich("substance", "67-64-1") is True

    def test_should_accept_name(self, provider):
        assert provider.can_enrich("substance", "acetone") is True

    def test_should_reject_empty(self, provider):
        assert provider.can_enrich("substance", "") is False


class TestPubChemEnrich:
    def _setup_responses(self, session):
        cid_resp = MagicMock(status_code=200)
        cid_resp.json.return_value = CID_RESPONSE
        prop_resp = MagicMock(status_code=200)
        prop_resp.json.return_value = PROPERTY_RESPONSE
        ghs_resp = MagicMock(status_code=200)
        ghs_resp.json.return_value = GHS_RESPONSE
        session.get.side_effect = [cid_resp, prop_resp, ghs_resp]

    def test_should_extract_molecular_data(self, provider, _mock_session):
        self._setup_responses(_mock_session)
        result = provider.enrich("substance", "67-64-1")

        assert result.properties["molecular_formula"].value == "C3H6O"
        assert result.properties["molecular_weight"].value == pytest.approx(58.08)
        assert result.properties["iupac_name"].value == "propan-2-one"
        assert result.properties["pubchem_cid"].value == 180

    def test_should_extract_ghs(self, provider, _mock_session):
        self._setup_responses(_mock_session)
        result = provider.enrich("substance", "67-64-1")

        assert "H225" in result.properties["h_statements"].value
        assert "H319" in result.properties["h_statements"].value
        assert result.properties["signal_word"].value == "danger"
        assert "GHS02" in result.properties["pictograms"].value
        assert "GHS07" in result.properties["pictograms"].value

    def test_should_extract_p_codes(self, provider, _mock_session):
        self._setup_responses(_mock_session)
        result = provider.enrich("substance", "67-64-1")

        assert "P210" in result.properties["p_statements"].value
        assert "P233" in result.properties["p_statements"].value

    def test_should_handle_cid_not_found(self, provider, _mock_session):
        resp = MagicMock(status_code=404)
        _mock_session.get.return_value = resp

        result = provider.enrich("substance", "unknown-substance")
        assert result.is_empty

    def test_should_handle_api_error(self, provider, _mock_session):
        _mock_session.get.side_effect = ConnectionError("timeout")
        result = provider.enrich("substance", "67-64-1")
        assert result.is_empty

    def test_should_have_confidence(self, provider, _mock_session):
        self._setup_responses(_mock_session)
        result = provider.enrich("substance", "67-64-1")
        assert result.confidence > 0.0
        assert result.source == "PubChem"
