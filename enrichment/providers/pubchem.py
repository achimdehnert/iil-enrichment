"""PubChem Provider — NIH compound database.

Requires: requests (pip install iil-enrichment[pubchem])

Extracts:
- Molecular formula, weight, IUPAC name
- GHS classification (H-codes, P-codes, pictograms, signal word)
- CAS number (reverse lookup by name)

Source: https://pubchem.ncbi.nlm.nih.gov/
"""

from __future__ import annotations

import logging
import re

from enrichment.types import EnrichmentResult, PropertyValue

logger = logging.getLogger(__name__)

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest"
API_TIMEOUT = 15

CAS_PATTERN = re.compile(r"^\d{1,7}-\d{2}-\d$")


class PubChemProvider:
    """Enrichment provider for PubChem compound data."""

    @property
    def name(self) -> str:
        return "PubChem"

    @property
    def supported_domains(self) -> list[str]:
        return ["substance", "sds"]

    def __init__(self, timeout: int = API_TIMEOUT) -> None:
        self._timeout = timeout
        self._session = None

    def _get_session(self):
        if self._session is None:
            import requests

            self._session = requests.Session()
            self._session.headers.update({
                "Accept": "application/json",
                "User-Agent": "iil-enrichment/0.1",
            })
        return self._session

    def can_enrich(self, domain: str, natural_key: str) -> bool:
        if domain not in self.supported_domains:
            return False
        key = natural_key.strip()
        return bool(key) and (bool(CAS_PATTERN.match(key)) or len(key) >= 3)

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
        session = self._get_session()
        is_cas = bool(CAS_PATTERN.match(query))

        if is_cas:
            url = f"{PUBCHEM_BASE}/pug/compound/name/{query}/cids/JSON"
        else:
            url = f"{PUBCHEM_BASE}/pug/compound/name/{query}/cids/JSON"

        try:
            resp = session.get(url, timeout=self._timeout)
            if resp.status_code != 200:
                return None
            data = resp.json()
            cids = data.get("IdentifierList", {}).get("CID", [])
            return cids[0] if cids else None
        except Exception:
            logger.exception("PubChem CID resolution failed for %s", query)
            return None

    def _fetch_compound(self, cid: int, natural_key: str) -> EnrichmentResult:
        """Fetch molecular properties for a CID."""
        session = self._get_session()
        properties: dict[str, PropertyValue] = {}
        raw_sections: dict[str, str] = {}

        properties["pubchem_cid"] = PropertyValue(value=cid, value_type="numeric")

        # Molecular properties
        prop_url = (
            f"{PUBCHEM_BASE}/pug/compound/cid/{cid}"
            f"/property/MolecularFormula,MolecularWeight,IUPACName/JSON"
        )
        try:
            resp = session.get(prop_url, timeout=self._timeout)
            if resp.status_code == 200:
                data = resp.json()
                props = data.get("PropertyTable", {}).get("Properties", [{}])[0]
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
        except Exception:
            logger.exception("PubChem properties fetch failed for CID %d", cid)

        # GHS classification
        ghs_url = f"{PUBCHEM_BASE}/pug_view/data/compound/{cid}/JSON?heading=GHS+Classification"
        try:
            resp = session.get(ghs_url, timeout=self._timeout)
            if resp.status_code == 200:
                self._parse_ghs(resp.json(), properties, raw_sections)
        except Exception:
            logger.exception("PubChem GHS fetch failed for CID %d", cid)

        confidence = min(1.0, len(properties) / 10.0)

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

                        elif heading == "GHS Signal Word" or heading == "Signal":
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
                value=sorted(h_codes), section="2.1", value_type="text"
            )
        if p_codes:
            properties["p_statements"] = PropertyValue(
                value=sorted(p_codes), section="2.2", value_type="text"
            )
        if pictograms:
            properties["pictograms"] = PropertyValue(
                value=sorted(pictograms), section="2.2", value_type="text"
            )
        if signal_word:
            properties["signal_word"] = PropertyValue(
                value=signal_word, section="2.2", value_type="text"
            )
