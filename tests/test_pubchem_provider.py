"""Tests for PubChem provider — respx-mocked HTTP, verify property extraction."""

from __future__ import annotations

import httpx
import pytest
import respx

from enrichment.config import HTTPDefaults
from enrichment.providers.pubchem import PubChemProvider

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov"


@pytest.fixture()
def fast_defaults(tmp_path):
    return HTTPDefaults(
        timeout_seconds=2,
        max_retries=1,
        backoff_initial=0.01,
        backoff_max=0.05,
        cache_enabled=False,
        cache_dir=tmp_path,
        rate_limit_enabled=False,
    )


@pytest.fixture()
def provider(fast_defaults):
    return PubChemProvider(defaults=fast_defaults)


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
    @staticmethod
    def _setup_routes():
        respx.get(url__regex=r".*/pug/compound/name/.*/cids/JSON").mock(
            return_value=httpx.Response(200, json=CID_RESPONSE)
        )
        respx.get(url__regex=r".*/pug/compound/cid/.*/property/.*").mock(
            return_value=httpx.Response(200, json=PROPERTY_RESPONSE)
        )
        respx.get(url__regex=r".*/pug_view/data/compound/.*/JSON.*").mock(
            return_value=httpx.Response(200, json=GHS_RESPONSE)
        )

    @respx.mock
    def test_should_extract_molecular_data(self, provider):
        self._setup_routes()
        result = provider.enrich("substance", "67-64-1")

        assert result.properties["molecular_formula"].value == "C3H6O"
        assert result.properties["molecular_weight"].value == pytest.approx(58.08)
        assert result.properties["iupac_name"].value == "propan-2-one"
        assert result.properties["pubchem_cid"].value == 180

    @respx.mock
    def test_should_extract_ghs(self, provider):
        self._setup_routes()
        result = provider.enrich("substance", "67-64-1")

        assert "H225" in result.properties["h_statements"].value
        assert "H319" in result.properties["h_statements"].value
        assert result.properties["signal_word"].value == "danger"
        assert "GHS02" in result.properties["pictograms"].value
        assert "GHS07" in result.properties["pictograms"].value

    @respx.mock
    def test_should_extract_p_codes(self, provider):
        self._setup_routes()
        result = provider.enrich("substance", "67-64-1")

        assert "P210" in result.properties["p_statements"].value
        assert "P233" in result.properties["p_statements"].value

    @respx.mock
    def test_should_handle_cid_not_found(self, provider):
        respx.get(url__regex=r".*/pug/compound/name/.*/cids/JSON").mock(
            return_value=httpx.Response(404)
        )
        result = provider.enrich("substance", "unknown-substance")
        assert result.is_empty

    @respx.mock
    def test_should_handle_api_error(self, provider):
        respx.get(url__regex=r".*/pug/compound/name/.*/cids/JSON").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        result = provider.enrich("substance", "67-64-1")
        assert result.is_empty

    @respx.mock
    def test_should_have_confidence(self, provider):
        self._setup_routes()
        result = provider.enrich("substance", "67-64-1")
        assert result.confidence > 0.0
        assert result.source == "PubChem"
