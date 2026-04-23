"""GESTIS Provider — German DGUV substance database.

Requires: httpx + tenacity (pip install iil-enrichment[gestis])

Extracts:
- Physical properties (flash point, boiling point, density, ...)
- Occupational exposure limits (AGW, BGW)
- Safety measures (first aid, protective equipment, storage)
- Regulations (WGK, TRGS 510, StörfallV)
- Transport info (ADR, IMDG)

Source: https://gestis-api.dguv.de/api
"""

from __future__ import annotations

import html
import logging
import os
import re
import warnings

from enrichment._http import get_json
from enrichment.config import HTTPDefaults
from enrichment.providers._base import HTTPProviderBase
from enrichment.types import CAS_PATTERN, EnrichmentResult, PropertyValue, ValueType

logger = logging.getLogger(__name__)

GESTIS_API = "https://gestis-api.dguv.de/api"
GESTIS_DEFAULT_KEY = os.environ.get(
    "GESTIS_API_KEY", "dddiiasjhduuvnnasdkkwUUSHhjaPPKMasd"
)
API_TIMEOUT = 15

# CMR H-codes for is_cmr detection
_CMR_CODES = frozenset({"H340", "H341", "H350", "H351", "H360", "H361", "H362"})

# Mapping: GESTIS sub-chapter drnr → (property_key, SDS section, value_type)
# drnr values verified against actual GESTIS API response format.
_CHAPTER_MAP: dict[str, tuple[str, str, str]] = {
    "0303": ("physical_state", "9", "text"),
    "0304": ("properties", "9", "text"),
    "0305": ("chemical_characterization", "9", "text"),
    "1201": ("agw", "8.1", "text"),
    "1205": ("bgw", "8.1", "text"),
    "0703": ("first_aid", "4", "text"),
    "0802": ("protective_measures", "8.2", "text"),
    "0803": ("storage", "7.2", "text"),
    "1108": ("transport", "14", "text"),
    "1106": ("wgk", "15", "text"),
    "0804": ("fire_protection", "5", "text"),
    "1215": ("stoerfallv", "15", "text"),
    "0807": ("disposal", "13", "text"),
    "0808": ("spill_response", "6", "text"),
}

# Sub-chapter drnr → property key for temperature-based physical data
_PHYSICAL_TEMP_PROPS: dict[str, str] = {
    "0602": "melting_point_c",
    "0603": "boiling_point_c",
    "0607": "flash_point_c",
    "0608": "ignition_temperature_c",
}


def _strip_html(text: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


class GESTISProvider(HTTPProviderBase):
    """Enrichment provider for GESTIS (DGUV) substance data."""

    _CONFIDENCE_DENOMINATOR = 20

    def __init__(
        self,
        timeout: int | None = None,
        api_key: str | None = None,
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
        self._api_key = api_key or GESTIS_DEFAULT_KEY

    @property
    def name(self) -> str:
        return "GESTIS"

    @property
    def supported_domains(self) -> list[str]:
        return ["substance", "sds"]

    def enrich(self, domain: str, natural_key: str) -> EnrichmentResult:
        """Fetch substance data from GESTIS API."""
        key = natural_key.strip()
        try:
            hit = self._search(key)
            if not hit:
                return EnrichmentResult(source=self.name, confidence=0.0, natural_key=key)
            return self._fetch_article(hit, key)
        except Exception:
            logger.exception("GESTIS enrichment failed for key=%s", key)
            return EnrichmentResult(source=self.name, confidence=0.0, natural_key=key)

    def _search(self, query: str) -> dict | None:
        """Search GESTIS, return best match dict with zvg_nr, name, cas_nr."""
        client = self._get_client()
        is_cas = bool(CAS_PATTERN.match(query))
        search_field = "cas_nr" if is_cas else "stoffname"

        url = f"{GESTIS_API}/search"
        params = {"exact": "true", search_field: query, "api_key": self._api_key}
        data = get_json(client, url, params=params, defaults=self._defaults)

        if not data:
            if not is_cas:
                params = {
                    "exact": "false",
                    search_field: query,
                    "api_key": self._api_key,
                }
                data = get_json(client, url, params=params, defaults=self._defaults)
            if not data:
                return None

        if isinstance(data, list) and data:
            return data[0]
        return None

    def _fetch_article(self, hit: dict, natural_key: str) -> EnrichmentResult:
        """Fetch full GESTIS article by search hit dict."""
        zvg = hit.get("zvg_nr", "")
        url = f"{GESTIS_API}/article/de/{zvg}"
        article = get_json(
            self._get_client(),
            url,
            params={"api_key": self._api_key},
            defaults=self._defaults,
        )

        if not isinstance(article, dict):
            return EnrichmentResult(
                source=self.name, confidence=0.0, natural_key=natural_key
            )

        # Flatten hauptkapitel/unterkapitel/drnr → {drnr: text}
        chapters: dict[str, str] = {}
        for hk in article.get("hauptkapitel", []):
            for uk in hk.get("unterkapitel", []):
                drnr = uk.get("drnr", "")
                text = uk.get("text") or ""
                if drnr and text:
                    chapters[drnr] = text

        properties: dict[str, PropertyValue] = {}
        raw_sections: dict[str, str] = {}

        # Identity from search hit + article
        if name := (article.get("name") or hit.get("name", "")):
            properties["name"] = PropertyValue(value=name, value_type=ValueType.TEXT)
        if cas := hit.get("cas_nr", ""):
            properties["cas_number"] = PropertyValue(
                value=cas, section="1", value_type=ValueType.TEXT
            )

        self._parse_chapters(chapters, properties, raw_sections)

        gestis_url = f"https://gestis.dguv.de/data?name={zvg}"
        properties["gestis_zvg"] = PropertyValue(value=zvg, value_type=ValueType.TEXT)
        properties["gestis_url"] = PropertyValue(value=gestis_url, value_type=ValueType.TEXT)

        confidence = min(1.0, len(properties) / self._CONFIDENCE_DENOMINATOR)

        return EnrichmentResult(
            source=self.name,
            confidence=confidence,
            properties=properties,
            raw_sections=raw_sections,
            natural_key=natural_key,
        )

    def _parse_chapters(
        self,
        chapters: dict[str, str],
        properties: dict[str, PropertyValue],
        raw_sections: dict[str, str],
    ) -> None:
        """Extract structured data from flattened GESTIS drnr→text dict."""
        s = _strip_html

        for drnr, raw_text in chapters.items():
            text = s(raw_text)
            if not text:
                continue

            raw_sections[f"gestis_{drnr}"] = text

            if drnr in _CHAPTER_MAP:
                prop_key, section, vtype = _CHAPTER_MAP[drnr]
                properties[prop_key] = PropertyValue(
                    value=text, section=section, value_type=vtype
                )

        # Parse physical data from sub-chapters 06xx
        self._parse_physical_properties(chapters, properties)
        # Parse GHS classification (chapter 1303)
        self._parse_ghs_classification(chapters, properties, raw_sections)
        # Parse identification (chapter 0100)
        self._parse_identification(chapters, properties)
        # Parse explosion details (0608, 0609)
        self._parse_explosion_details(chapters, properties)
        # Parse regulations (1208, 1209, 1210)
        self._parse_regulations(chapters, properties)

    def _parse_physical_properties(
        self,
        chapters: dict[str, str],
        properties: dict[str, PropertyValue],
    ) -> None:
        """Extract numeric physical properties from flattened chapters."""
        for drnr, raw_text in chapters.items():
            text = _strip_html(raw_text)
            if not text:
                continue

            temp_match = re.search(r"(-?\d+(?:[.,]\d+)?)\s*°?\s*C", text)

            if drnr in _PHYSICAL_TEMP_PROPS and temp_match:
                val = float(temp_match.group(1).replace(",", "."))
                properties[_PHYSICAL_TEMP_PROPS[drnr]] = PropertyValue(
                    value=val, unit="°C", section="9.1", value_type=ValueType.NUMERIC
                )

            # Density is in sub-chapter 0604
            if drnr == "0604":
                density_match = re.search(
                    r"(\d+[.,]\d+)\s*(?:g/cm|kg/m)", text
                )
                if density_match:
                    val = float(density_match.group(1).replace(",", "."))
                    properties["density"] = PropertyValue(
                        value=val, unit="g/cm³", section="9.1",
                        value_type=ValueType.NUMERIC,
                    )

    def _parse_ghs_classification(
        self,
        chapters: dict[str, str],
        properties: dict[str, PropertyValue],
        raw_sections: dict[str, str],
    ) -> None:
        """Extract GHS classification from GESTIS chapter 1303."""
        raw_text = chapters.get("1303", "")
        txt = _strip_html(raw_text)
        if not txt:
            return

        raw_sections["gestis_ghs"] = txt
        properties["ghs_einstufung"] = PropertyValue(
            value=txt[:500], section="2.1", value_type=ValueType.TEXT
        )

        h_codes = set(re.findall(r"H\d{3}[a-z]?", txt))
        if h_codes:
            properties["h_statements"] = PropertyValue(
                value=sorted(h_codes), section="2.1", value_type=ValueType.LIST
            )
            is_cmr = bool(h_codes & _CMR_CODES)
            properties["is_cmr"] = PropertyValue(
                value=is_cmr, value_type=ValueType.BOOLEAN
            )

        if "Gefahr" in txt or "Danger" in txt:
            properties["signal_word"] = PropertyValue(
                value="danger", section="2.1", value_type=ValueType.TEXT
            )
        elif "Achtung" in txt or "Warning" in txt:
            properties["signal_word"] = PropertyValue(
                value="warning", section="2.1", value_type=ValueType.TEXT
            )

    @staticmethod
    def _parse_identification(
        chapters: dict[str, str],
        properties: dict[str, PropertyValue],
    ) -> None:
        """Extract EC number and molecular data from GESTIS chapter 0100/0400."""
        s = _strip_html
        if txt := s(chapters.get("0100", "")):
            ec_m = re.search(r"EG Nr:\s*([\d-]+)", txt)
            if ec_m:
                properties["ec_number"] = PropertyValue(
                    value=ec_m.group(1), section="1", value_type=ValueType.TEXT
                )

        if txt := s(chapters.get("0400", "")):
            mw = re.search(r"Molare Masse:\s*([\d.,]+)", txt)
            if mw:
                properties["molecular_weight"] = PropertyValue(
                    value=mw.group(1), unit="g/mol", section="3",
                    value_type=ValueType.TEXT,
                )
            mf = re.match(r"([A-Z][A-Za-z0-9]+)", txt)
            if mf:
                properties["molecular_formula"] = PropertyValue(
                    value=mf.group(1), section="3", value_type=ValueType.TEXT
                )

    @staticmethod
    def _parse_explosion_details(
        chapters: dict[str, str],
        properties: dict[str, PropertyValue],
    ) -> None:
        """Extract explosion group, temperature class from drnr 0608/0609."""
        s = _strip_html
        if txt := s(chapters.get("0608", "")):
            tc = re.search(r"Temperaturklasse:\s*(T\d)", txt)
            if tc:
                properties["temperature_class"] = PropertyValue(
                    value=tc.group(1), section="9.1", value_type=ValueType.TEXT
                )

        if txt := s(chapters.get("0609", "")):
            properties["explosion_limits"] = PropertyValue(
                value=txt[:300], section="9.1", value_type=ValueType.TEXT
            )
            eg = re.search(r"Explosionsgruppe:\s*(II[ABC])", txt)
            if eg:
                properties["explosion_group"] = PropertyValue(
                    value=eg.group(1), section="9.1", value_type=ValueType.TEXT
                )

    @staticmethod
    def _parse_regulations(
        chapters: dict[str, str],
        properties: dict[str, PropertyValue],
    ) -> None:
        """Extract regulations from GESTIS drnr 1208/1209/1210."""
        s = _strip_html
        regs: list[str] = []

        if txt := s(chapters.get("1209", "")):
            for trgs in re.findall(r"TRGS \d+[^.]*", txt):
                regs.append(trgs.strip()[:120])

        if txt := s(chapters.get("1210", "")):
            for dguv in re.findall(r"DGUV [^,.\n]+", txt):
                regs.append(dguv.strip()[:120])

        if (txt := s(chapters.get("1208", ""))) and "REACH" in txt:
            regs.append(txt[:120])

        if regs:
            properties["regulations"] = PropertyValue(
                value=regs[:20], section="15", value_type=ValueType.LIST
            )
