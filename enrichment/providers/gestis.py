"""GESTIS Provider — German DGUV substance database.

Requires: requests (pip install iil-enrichment[gestis])

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
import re

from enrichment.types import EnrichmentResult, PropertyValue

logger = logging.getLogger(__name__)

GESTIS_API = "https://gestis-api.dguv.de/api"
GESTIS_KEY = "dddiiasjhduuvnnasdkkwUUSHhjaPPKMasd"
API_TIMEOUT = 15

CAS_PATTERN = re.compile(r"^\d{1,7}-\d{2}-\d$")


def _strip_html(text: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


class GESTISProvider:
    """Enrichment provider for GESTIS (DGUV) substance data."""

    @property
    def name(self) -> str:
        return "GESTIS"

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
        """GESTIS can enrich if key looks like a CAS number or substance name."""
        if domain not in self.supported_domains:
            return False
        key = natural_key.strip()
        return bool(key) and (bool(CAS_PATTERN.match(key)) or len(key) >= 3)

    def enrich(self, domain: str, natural_key: str) -> EnrichmentResult:
        """Fetch substance data from GESTIS API."""
        key = natural_key.strip()
        try:
            zvg = self._search(key)
            if not zvg:
                return EnrichmentResult(source=self.name, confidence=0.0, natural_key=key)
            return self._fetch_article(zvg, key)
        except Exception:
            logger.exception("GESTIS enrichment failed for key=%s", key)
            return EnrichmentResult(source=self.name, confidence=0.0, natural_key=key)

    def _search(self, query: str) -> str | None:
        """Search GESTIS, return ZVG number of best match."""
        session = self._get_session()
        is_cas = bool(CAS_PATTERN.match(query))
        field = "cas_nr" if is_cas else "stoffname"

        url = f"{GESTIS_API}/search"
        params = {"exact": "true", field: query, "api_key": GESTIS_KEY}
        resp = session.get(url, params=params, timeout=self._timeout)

        if resp.status_code != 200:
            if not is_cas:
                params = {"exact": "false", field: query, "api_key": GESTIS_KEY}
                resp = session.get(url, params=params, timeout=self._timeout)
            if resp.status_code != 200:
                return None

        data = resp.json()
        if not data:
            return None

        return data[0].get("zvg_nr", "")

    def _fetch_article(self, zvg: str, natural_key: str) -> EnrichmentResult:
        """Fetch full GESTIS article by ZVG number."""
        session = self._get_session()
        url = f"{GESTIS_API}/article/de/{zvg}"
        resp = session.get(url, params={"api_key": GESTIS_KEY}, timeout=self._timeout)

        if resp.status_code != 200:
            return EnrichmentResult(source=self.name, confidence=0.0, natural_key=natural_key)

        article = resp.json()
        chapters = article.get("chapters", {})

        properties: dict[str, PropertyValue] = {}
        raw_sections: dict[str, str] = {}

        self._parse_chapters(chapters, properties, raw_sections)

        gestis_url = f"https://gestis.dguv.de/data?name={zvg}"

        properties["gestis_zvg"] = PropertyValue(value=zvg, value_type="text")
        properties["gestis_url"] = PropertyValue(value=gestis_url, value_type="text")

        confidence = min(1.0, len(properties) / 20.0)

        return EnrichmentResult(
            source=self.name,
            confidence=confidence,
            properties=properties,
            raw_sections=raw_sections,
            natural_key=natural_key,
        )

    def _parse_chapters(
        self,
        chapters: dict,
        properties: dict[str, PropertyValue],
        raw_sections: dict[str, str],
    ) -> None:
        """Extract structured data from GESTIS chapters."""
        s = _strip_html

        # Chapter mapping: GESTIS chapter ID → extraction logic
        for chap_id, chapter in chapters.items():
            chap_text = s(chapter.get("text", ""))
            if chap_text:
                raw_sections[f"gestis_{chap_id}"] = chap_text

            sub_chapters = chapter.get("sub_chapters", [])
            for sub in sub_chapters:
                sub_id = sub.get("number", "")
                sub_text = s(sub.get("text", ""))

                if not sub_text:
                    continue

                raw_sections[f"gestis_{sub_id}"] = sub_text

                # Physical properties
                if sub_id == "0600":
                    properties["physical_state"] = PropertyValue(
                        value=sub_text, section="9", value_type="text"
                    )
                if sub_id == "0601":
                    properties["chemical_characterization"] = PropertyValue(
                        value=sub_text, section="9", value_type="text"
                    )

                # Occupational exposure limits (AGW)
                if sub_id == "0700":
                    properties["agw"] = PropertyValue(
                        value=sub_text, section="8.1", value_type="text"
                    )
                if sub_id == "0701":
                    properties["bgw"] = PropertyValue(
                        value=sub_text, section="8.1", value_type="text"
                    )

                # Safety measures
                if sub_id == "0900":
                    properties["first_aid"] = PropertyValue(
                        value=sub_text, section="4", value_type="text"
                    )
                if sub_id == "1000":
                    properties["protective_measures"] = PropertyValue(
                        value=sub_text, section="8.2", value_type="text"
                    )
                if sub_id == "1100":
                    properties["storage"] = PropertyValue(
                        value=sub_text, section="7.2", value_type="text"
                    )
                if sub_id == "1200":
                    properties["fire_protection"] = PropertyValue(
                        value=sub_text, section="5", value_type="text"
                    )
                if sub_id == "1300":
                    properties["disposal"] = PropertyValue(
                        value=sub_text, section="13", value_type="text"
                    )
                if sub_id == "1301":
                    properties["spill_response"] = PropertyValue(
                        value=sub_text, section="6", value_type="text"
                    )
                if sub_id == "1400":
                    properties["transport"] = PropertyValue(
                        value=sub_text, section="14", value_type="text"
                    )

                # Regulations
                if sub_id == "1500":
                    properties["wgk"] = PropertyValue(
                        value=sub_text, section="15", value_type="text"
                    )
                if sub_id == "1501":
                    properties["stoerfallv"] = PropertyValue(
                        value=sub_text, section="15", value_type="text"
                    )

        # Parse physical data from sub-chapters 06xx
        self._parse_physical_properties(chapters, properties)

    def _parse_physical_properties(
        self,
        chapters: dict,
        properties: dict[str, PropertyValue],
    ) -> None:
        """Extract numeric physical properties from GESTIS chapter 06xx."""
        for chapter in chapters.values():
            for sub in chapter.get("sub_chapters", []):
                sub_id = sub.get("number", "")
                text = _strip_html(sub.get("text", ""))
                if not text:
                    continue

                temp_match = re.search(r"(-?\d+(?:[.,]\d+)?)\s*°?\s*C", text)

                if sub_id == "0602" and temp_match:
                    val = float(temp_match.group(1).replace(",", "."))
                    properties["melting_point_c"] = PropertyValue(
                        value=val, unit="°C", section="9.1", value_type="numeric"
                    )
                if sub_id == "0603" and temp_match:
                    val = float(temp_match.group(1).replace(",", "."))
                    properties["boiling_point_c"] = PropertyValue(
                        value=val, unit="°C", section="9.1", value_type="numeric"
                    )
                if sub_id == "0604" and temp_match:
                    val = float(temp_match.group(1).replace(",", "."))
                    properties["flash_point_c"] = PropertyValue(
                        value=val, unit="°C", section="9.1", value_type="numeric"
                    )
                if sub_id == "0605" and temp_match:
                    val = float(temp_match.group(1).replace(",", "."))
                    properties["ignition_temperature_c"] = PropertyValue(
                        value=val, unit="°C", section="9.1", value_type="numeric"
                    )

                density_match = re.search(
                    r"(\d+[.,]\d+)\s*(?:g/cm|kg/m)", text
                )
                if sub_id == "0608" and density_match:
                    val = float(density_match.group(1).replace(",", "."))
                    properties["density"] = PropertyValue(
                        value=val, unit="g/cm³", section="9.1", value_type="numeric"
                    )
