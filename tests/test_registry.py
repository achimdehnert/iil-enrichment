"""Tests for EnrichmentRegistry."""

from enrichment.provider import EnrichmentProvider
from enrichment.registry import EnrichmentRegistry
from enrichment.types import EnrichmentResult, PropertyValue


class FakeProvider:
    """Test provider that returns canned data."""

    def __init__(self, name: str, domains: list[str], data: dict | None = None):
        self._name = name
        self._domains = domains
        self._data = data or {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def supported_domains(self) -> list[str]:
        return self._domains

    def can_enrich(self, domain: str, natural_key: str) -> bool:
        return domain in self._domains and bool(natural_key)

    def enrich(self, domain: str, natural_key: str) -> EnrichmentResult:
        props = {k: PropertyValue(value=v) for k, v in self._data.items()}
        return EnrichmentResult(
            source=self._name,
            confidence=0.8,
            properties=props,
            natural_key=natural_key,
        )


class FailingProvider:
    """Provider that raises on enrich."""

    @property
    def name(self) -> str:
        return "Failing"

    @property
    def supported_domains(self) -> list[str]:
        return ["test"]

    def can_enrich(self, domain: str, natural_key: str) -> bool:
        return True

    def enrich(self, domain: str, natural_key: str) -> EnrichmentResult:
        raise RuntimeError("Provider error")


def test_should_satisfy_protocol():
    provider = FakeProvider("Test", ["substance"])
    assert isinstance(provider, EnrichmentProvider)


class TestRegistry:
    def test_should_register_and_list_providers(self):
        reg = EnrichmentRegistry()
        p1 = FakeProvider("A", ["substance"])
        p2 = FakeProvider("B", ["substance"])
        reg.register("substance", p1)
        reg.register("substance", p2)

        assert len(reg.get_providers("substance")) == 2
        assert "substance" in reg.domains

    def test_should_not_duplicate_provider(self):
        reg = EnrichmentRegistry()
        p1 = FakeProvider("A", ["substance"])
        reg.register("substance", p1)
        reg.register("substance", p1)

        assert len(reg.get_providers("substance")) == 1

    def test_should_unregister_provider(self):
        reg = EnrichmentRegistry()
        p1 = FakeProvider("A", ["substance"])
        reg.register("substance", p1)
        assert reg.unregister("substance", "A")
        assert len(reg.get_providers("substance")) == 0

    def test_should_enrich_from_multiple_providers(self):
        reg = EnrichmentRegistry()
        reg.register("substance", FakeProvider("GESTIS", ["substance"], {"agw": "50 mg/m³"}))
        reg.register("substance", FakeProvider("PubChem", ["substance"], {"formula": "C7H8"}))

        results = reg.enrich("substance", "108-88-3")
        assert len(results) == 2
        sources = {r.source for r in results}
        assert sources == {"GESTIS", "PubChem"}

    def test_should_return_empty_for_unknown_domain(self):
        reg = EnrichmentRegistry()
        results = reg.enrich("unknown", "key")
        assert results == []

    def test_should_merge_results(self):
        reg = EnrichmentRegistry()
        reg.register("substance", FakeProvider("GESTIS", ["substance"], {"agw": "50 mg/m³"}))
        reg.register("substance", FakeProvider("PubChem", ["substance"], {"formula": "C7H8"}))

        merged = reg.enrich_merged("substance", "108-88-3")
        assert merged.get("agw").value == "50 mg/m³"
        assert merged.get("formula").value == "C7H8"

    def test_should_return_empty_merged_for_no_providers(self):
        reg = EnrichmentRegistry()
        merged = reg.enrich_merged("unknown", "key")
        assert merged.is_empty
        assert merged.source == "none"

    def test_should_survive_provider_error(self):
        reg = EnrichmentRegistry()
        reg.register("test", FailingProvider())
        reg.register("test", FakeProvider("OK", ["test"], {"key": "val"}))

        results = reg.enrich("test", "123")
        assert len(results) == 1
        assert results[0].source == "OK"

    def test_should_skip_provider_that_cannot_enrich(self):
        reg = EnrichmentRegistry()
        reg.register("substance", FakeProvider("A", ["substance"], {"key": "val"}))

        results = reg.enrich("substance", "")
        assert len(results) == 0
