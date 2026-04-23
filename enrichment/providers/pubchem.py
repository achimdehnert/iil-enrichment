"""PubChem Provider — NIH compound database.

Requires: httpx + tenacity (pip install iil-enrichment[pubchem])

Extracts:
- Molecular formula, weight, IUPAC name
- GHS classification (H-codes, P-codes, pictograms, signal word)
- CAS number (reverse lookup by name)

Source: https://pubchem.ncbi.nlm.nih.gov/
"""

from __future__ import annotations

import logging
import re
import warnings

from enrichment._http import get_json
from enrichment.config import HTTPDefaults
from enrichment.providers._base import HTTPProviderBase
from enrichment.types import EnrichmentResult, PropertyValue, ValueType

logger = logging.getLogger(__name__)

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest"
API_TIMEOUT = 15


class PubChemProvider(HTTPProviderBase):
    """Enrichment provider for PubChem compound data."""

    _CONFIDENCE_DENOMINATOR = 10

    def __init__(
        self,
        timeout: int | None = None,
        *,
        defaults: HTTPDefaults | None = None,
    ) -> None:
        if timeout is not None:
            warnings.warn(
                "Pass `defaults=HTTPDefaults(timeout_seconds=...)` instead of "
                "`timeout=...`. The `timeout` argument is deprecated and will "
                "be removed in 0.3.",
                DeprecationWarning,
                stacklevel=2,
            )
            defaults = HTTPDefaults(timeout_seconds=float(timeout))
        super().__init__(defaults=defaults)

    @property
    def name(self) -> str:
        return "PubChem"

    @property
    def supported_domains(self) -> list[str]:
        return ["substance", "sds"]

    def enrich(self, domain: str, natural_key: str) -> EnrichmentResult:
        """Fetch compound data from PubChem."""
        key = natural_key.strip()
        try:
            cid = self._resolve_cid(key)
            if not cid:
                return EnrichmentResult(source=self.name, confidence=0.0, natural_key=key)
            return self._fetch_compound(cid, key)
        except Exception:
            logger.exception("PubChem enrichment failed for key=%s", key)
            return EnrichmentResult(source=self.name, confidence=0.0, natural_key=key)

    def _resolve_cid(self, query: str) -> int | None:
        """Resolve CAS or name to PubChem CID."""
        url = f"{PUBCHEM_BASE}/pug/compound/name/{query}/cids/JSON"
        data = get_json(self._get_client(), url, defaults=self._defaults)
        if not isinstance(data, dict):
            return None
        cids = data.get("IdentifierList", {}).get("CID", [])
        return cids[0] if cids else None

    def _fetch_compound(self, cid: int, natural_key: str) -> EnrichmentResult:
        """Fetch molecular properties for a CID."""
        client = self._get_client()
        properties: dict[str, PropertyValue] = {
            "pubchem_cid": PropertyValue(value=cid, value_type="numeric"),
        }
        raw_sections: dict[str, str] = {}

        # Molecular properties
        prop_url = (
            f"{PUBCHEM_BASE}/pug/compound/cid/{cid}"
            f"/property/MolecularFormula,MolecularWeight,IUPACName/JSON"
        )
        if prop_data := get_json(client, prop_url, defaults=self._defaults):
            props = prop_data.get("PropertyTable", {}).get("Properties", [{}])[0]
            if formula := props.get("MolecularFormula"):
                properties["molecular_formula"] = PropertyValue(
                    value=formula, value_type="text"
                )
            if weight := props.get("MolecularWeight"):
                properties["molecular_weight"] = PropertyValue(
                    value=float(weight), unit="g/mol", value_type="numeric"
                )
            if iupac := props.get("IUPACName"):
                properties["iupac_name"] = PropertyValue(value=iupac, value_type="text")

        # GHS classification
        ghs_url = (
            f"{PUBCHEM_BASE}/pug_view/data/compound/{cid}/JSON"
            f"?heading=GHS+Classification"
        )
        if ghs_data := get_json(client, ghs_url, defaults=self._defaults):
            self._parse_ghs(ghs_data, properties, raw_sections)

        confidence = min(1.0, len(properties) / self._CONFIDENCE_DENOMINATOR)
        return EnrichmentResult(
            source=self.name,
            confidence=confidence,
            properties=properties,
            raw_sections=raw_sections,
            natural_key=natural_key,
        )

    def _parse_ghs(
        self,
        data: dict,
        properties: dict[str, PropertyValue],
        raw_sections: dict[str, str],
    ) -> None:
        """Parse GHS classification from PubChem PUG View."""
        h_codes: set[str] = set()
        p_codes: set[str] = set()
        pictograms: set[str] = set()
        signal_word = ""

        try:
            record = data.get("Record", {})
            for section in record.get("Section", []):
                for sub in section.get("Section", []):
                    heading = sub.get("TOCHeading", "")
                    for info in sub.get("Information", []):
                        val = info.get("Value", {})
                        strings = val.get("StringWithMarkup", [])

                        if heading == "GHS Hazard Statements":
                            for s in strings:
                                text = s.get("String", "")
                                m = re.match(r"(H\d{3}[a-z]*)", text)
                                if m:
                                    h_codes.add(m.group(1))
                            raw_sections["pubchem_h_statements"] = "; ".join(
                                s.get("String", "") for s in strings
                            )

                        elif heading == "Precautionary Statement Codes":
                            for s in strings:
                                for code in re.findall(r"P\d{3}", s.get("String", "")):
                                    p_codes.add(code)

                        elif heading in ("GHS Signal Word", "Signal"):
                            for s in strings:
                                word = s.get("String", "").strip().lower()
                                if word in ("danger", "warning"):
                                    signal_word = word

                        elif "Pictogram" in heading:
                            for s in strings:
                                for m in re.finditer(r"GHS\d{2}", s.get("String", "")):
                                    pictograms.add(m.group())
                                for markup in s.get("Markup", []):
                                    extra = markup.get("Extra", "")
                                    for m in re.finditer(r"GHS\d{2}", extra):
                                        pictograms.add(m.group())
        except Exception:
            logger.exception("GHS parsing failed")

        if h_codes:
            properties["h_statements"] = PropertyValue(
                value=sorted(h_codes), section="2.1", value_type=ValueType.LIST
            )
        if p_codes:
            properties["p_statements"] = PropertyValue(
                value=sorted(p_codes), section="2.2", value_type=ValueType.LIST
            )
        if pictograms:
            properties["pictograms"] = PropertyValue(
                value=sorted(pictograms), section="2.2", value_type=ValueType.LIST
            )
        if signal_word:
            properties["signal_word"] = PropertyValue(
                value=signal_word, section="2.2", value_type="text"
            )
