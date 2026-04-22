"""Tests for enrichment core types."""

from enrichment.types import EnrichmentResult, PropertyValue


class TestPropertyValue:
    def test_should_create_numeric_property(self):
        pv = PropertyValue(value=40.0, unit="°C", section="9.1", value_type="numeric")
        assert pv.value == 40.0
        assert pv.unit == "°C"
        assert pv.value_type == "numeric"

    def test_should_create_text_property(self):
        pv = PropertyValue(value="Bei Einatmen: Frische Luft", section="4")
        assert pv.value_type == "text"

    def test_should_be_immutable(self):
        pv = PropertyValue(value="test")
        try:
            pv.value = "changed"
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass


class TestEnrichmentResult:
    def test_should_detect_empty_result(self):
        r = EnrichmentResult(source="test", confidence=0.0)
        assert r.is_empty

    def test_should_detect_non_empty_result(self):
        r = EnrichmentResult(
            source="test",
            confidence=0.8,
            properties={"key": PropertyValue(value="val")},
        )
        assert not r.is_empty

    def test_should_get_property(self):
        pv = PropertyValue(value=40.0, unit="°C")
        r = EnrichmentResult(
            source="test",
            confidence=0.8,
            properties={"flash_point_c": pv},
        )
        assert r.get("flash_point_c") is pv
        assert r.get("missing") is None

    def test_should_merge_results(self):
        r1 = EnrichmentResult(
            source="GESTIS",
            confidence=0.9,
            properties={
                "agw": PropertyValue(value="50 mg/m³"),
                "flash_point_c": PropertyValue(value=40.0),
            },
            raw_sections={"gestis_0700": "AGW: 50 mg/m³"},
        )
        r2 = EnrichmentResult(
            source="PubChem",
            confidence=0.7,
            properties={
                "molecular_formula": PropertyValue(value="C7H8"),
                "flash_point_c": PropertyValue(value=4.0),
            },
            raw_sections={"pubchem_ghs": "..."},
        )

        merged = r1.merge(r2)

        assert "GESTIS" in merged.source
        assert "PubChem" in merged.source
        assert merged.confidence == 0.9
        assert merged.get("agw").value == "50 mg/m³"
        assert merged.get("molecular_formula").value == "C7H8"
        # r1 (self) wins on conflict
        assert merged.get("flash_point_c").value == 40.0
        # Raw sections merged
        assert "gestis_0700" in merged.raw_sections
        assert "pubchem_ghs" in merged.raw_sections

    def test_should_be_immutable(self):
        r = EnrichmentResult(source="test", confidence=0.5)
        try:
            r.source = "changed"
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass
