"""Tests for enrichment core types."""

from enrichment.types import CAS_PATTERN, EnrichmentResult, PropertyValue, ValueType


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
            raise AssertionError("Should raise FrozenInstanceError")
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

        assert "GESTIS" in merged.source.split(",")
        assert "PubChem" in merged.source.split(",")
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
            raise AssertionError("Should raise FrozenInstanceError")
        except AttributeError:
            pass

    def test_should_serialize_to_dict(self):
        r = EnrichmentResult(
            source="GESTIS",
            confidence=0.9,
            properties={
                "agw": PropertyValue(value="50 mg/m³", section="8.1"),
                "flash_point_c": PropertyValue(value=40.0, unit="°C", value_type=ValueType.NUMERIC),
            },
        )
        d = r.to_dict()
        assert d["agw"]["value"] == "50 mg/m³"
        assert d["agw"]["section"] == "8.1"
        assert d["flash_point_c"]["unit"] == "°C"
        assert d["flash_point_c"]["value_type"] == "numeric"

    def test_should_serialize_property_value_to_dict(self):
        pv = PropertyValue(
            value=40.0, unit="°C", section="9.1",
            value_type=ValueType.NUMERIC, note="closed cup",
        )
        d = pv.to_dict()
        assert d == {
            "value": 40.0,
            "unit": "°C",
            "section": "9.1",
            "value_type": "numeric",
            "note": "closed cup",
        }

    def test_should_return_source_list(self):
        r = EnrichmentResult(source="GESTIS,PubChem", confidence=0.9)
        assert r.source_list == ["GESTIS", "PubChem"]

    def test_should_return_empty_source_list(self):
        r = EnrichmentResult(source="", confidence=0.0)
        assert r.source_list == []

    def test_should_handle_list_values(self):
        pv = PropertyValue(value=["H301", "H311", "H331"], value_type=ValueType.LIST)
        assert pv.value == ["H301", "H311", "H331"]
        d = pv.to_dict()
        assert d["value"] == ["H301", "H311", "H331"]
        assert d["value_type"] == "list"


class TestValueType:
    def test_should_be_string_compatible(self):
        assert ValueType.NUMERIC == "numeric"
        assert ValueType.TEXT == "text"
        assert ValueType.LIST == "list"

    def test_should_use_as_default(self):
        pv = PropertyValue(value="test")
        assert pv.value_type == ValueType.TEXT
        assert pv.value_type == "text"


class TestCASPattern:
    def test_should_match_valid_cas(self):
        assert CAS_PATTERN.match("67-64-1")
        assert CAS_PATTERN.match("108-88-3")
        assert CAS_PATTERN.match("7732-18-5")

    def test_should_reject_invalid_cas(self):
        assert not CAS_PATTERN.match("not-a-cas")
        assert not CAS_PATTERN.match("12345678-12-3")
        assert not CAS_PATTERN.match("")
