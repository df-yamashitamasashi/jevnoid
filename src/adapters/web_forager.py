from __future__ import annotations

import asyncio
import html
import ipaddress
import random
import re
import socket
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from src.domain.species import SpeciesType

USER_AGENT = "Jevnoid-Organism/1.0 (+https://github.com/df-yamashitamasashi/jevnoid)"
DEFAULT_PORTS = {"http": 80, "https": 443}
MAX_REDIRECTS = 3
MAX_BODY_BYTES = 1_000_000

# Offline pre-seeded nutritious sources in pure English for low-token, high-precision Jev foraging
SEEDED_PREY_CORPUS: dict[SpeciesType, list[dict[str, str]]] = {
    SpeciesType.THEOS: [
        {
            "title": "The Sermon on the Mount (Gospel of Matthew)",
            "url": "https://sacred-texts.com/chr/gospel/matthew.htm",
            "content": "Blessed are the poor in spirit, for theirs is the kingdom of heaven. Blessed are the meek, for they shall inherit the earth. Love your enemies, bless those who curse you, do good to those who hate you, and pray for those who spitefully use you.",
            "tags": "theology, agape, beatitudes, love",
        },
        {
            "title": "The Heart Sutra (Prajnaparamita Hridaya)",
            "url": "https://sacred-texts.com/bud/heart_sutra.htm",
            "content": "Form is emptiness, emptiness is form. Form does not differ from emptiness; emptiness does not differ from form. The five aggregates are all empty of inherent existence. Transcending all suffering, with mind unhindered, there is no fear.",
            "tags": "buddhism, shunyata, prajna, oneness",
        },
        {
            "title": "Tao Te Ching (Laozi Chapter 8)",
            "url": "https://sacred-texts.com/tao/taote.htm",
            "content": "The highest good is like water. Water gives life to the ten thousand things and does not strive. It flows in places men reject and so it is like the Tao. In dwelling, be close to the land. In meditation, go deep in the heart.",
            "tags": "taoism, wu_wei, harmony, transcendence",
        },
        {
            "title": "Bhagavad Gita (Chapter 2: The Yoga of Knowledge)",
            "url": "https://sacred-texts.com/hin/gita.htm",
            "content": "You have a right to perform your prescribed duty, but you are never entitled to the fruits of action. Never consider yourself the cause of results, nor be attached to inaction. Established in equanimity, perform your duties.",
            "tags": "hinduism, karma_yoga, equanimity, dharma",
        },
    ],
    SpeciesType.GAIA: [
        {
            "title": "Global Ocean Carbon Sequestration and Thermohaline Circulation",
            "url": "https://www.noaa.gov/climate/carbon-cycle",
            "content": "The oceans absorb approximately 25% of anthropogenic carbon dioxide emissions annually. Phytoplankton photosynthesis forms the foundational biological pump of marine ecosystems. Global thermohaline circulation distributes heat and oxygen throughout the abyssal ocean.",
            "tags": "ocean, carbon_cycle, climate, biosphere",
        },
        {
            "title": "Amazon Rainforest Hydrological Canopy and Flying Rivers",
            "url": "https://earthobservatory.nasa.gov/amazon-biome",
            "content": "Dense canopy vegetation in the Amazon Basin transpires over 20 billion tons of water vapor daily into the troposphere, creating aerial rivers that stabilize precipitation patterns across the entire South American continent and govern planetary albedo.",
            "tags": "rainforest, biodiversity, hydrology, transpiration",
        },
        {
            "title": "Arctic Permafrost Carbon Feedback and Biosphere Homeostasis",
            "url": "https://ourworldindata.org/arctic-permafrost",
            "content": "Circumpolar permafrost soils sequester approximately 1,500 gigatons of organic carbon. Active-layer thaw dynamics and tundra shrubification serve as key indicators of biosphere stability and planetary homeostasis thresholds.",
            "tags": "arctic, permafrost, climate_feedback, ecology",
        },
    ],
    SpeciesType.COSMO: [
        {
            "title": "JWST High-Redshift Galaxy JADES-GS-z14-0 Spectroscopic Analysis",
            "url": "https://webbtelescope.org/news/early-galaxies",
            "content": "Spectroscopic observations of galaxy JADES-GS-z14-0 at redshift z=14.32, existing just 290 million years after the Big Bang, reveal unexpected luminosity and early metal enrichment, challenging conventional stellar nucleosynthesis timescales.",
            "tags": "astrophysics, jwst, cosmology, nucleosynthesis",
        },
        {
            "title": "Binary Neutron Star Merger Kilonova and r-Process Nucleosynthesis",
            "url": "https://chandra.harvard.edu/neutron-star-merger",
            "content": "Electromagnetic follow-up of gravitational wave event GW170817 demonstrated that rapid neutron capture (r-process) in the ejecta of merging neutron stars produces heavy elements including gold and platinum across galactic time scales.",
            "tags": "gravitational_waves, neutron_star, kilonova, relativity",
        },
        {
            "title": "Supermassive Black Hole Accretion Disk Physics and Relativistic Jets",
            "url": "https://science.nasa.gov/universe/black-holes",
            "content": "Matter in accretion disks orbiting Kerr black holes converts gravitational potential energy into radiation with up to 42% efficiency. Magnetohydrodynamic relativistic jets heat intracluster gas, driving galactic-scale feedback regulation.",
            "tags": "black_hole, spacetime, accretion_disk, relativistic_jet",
        },
    ],
    SpeciesType.INFO: [
        {
            "title": "Theory of Self-Reproducing Automata and Universality (J. von Neumann)",
            "url": "https://arxiv.org/abs/comp-automata-universality",
            "content": "A self-reproducing automaton requires a universal constructor coupled with an instruction tape containing its own specification. When architectural complexity exceeds a critical threshold, machines acquire the evolutionary capacity to synthesize successors of greater complexity.",
            "tags": "von_neumann, self_replication, automata, complexity",
        },
        {
            "title": "Information Entropy, Active Inference, and Free Energy Principle",
            "url": "https://plato.stanford.edu/entries/information-entropy",
            "content": "Living systems maintain non-equilibrium steady states by minimizing variational free energy, effectively minimizing the surprise of their sensory observations relative to internal generative models of the environment.",
            "tags": "information_theory, active_inference, free_energy, cybernetics",
        },
        {
            "title": "Topological Invariance and Scale-Free Resilience in Complex Networks",
            "url": "https://arxiv.org/abs/scale-free-networks",
            "content": "Scale-free networks governed by power-law degree distributions exhibit extreme topological resilience against random node failures, while remaining selectively vulnerable to targeted degradation of structural hubs.",
            "tags": "network_theory, topology, scale_free, resilience",
        },
    ],
}


class WebForager:
    """Network sensory organ that forages and sanitizes external web knowledge in English."""

    def __init__(self, timeout_sec: float = 4.0) -> None:
        self.timeout = timeout_sec

    async def forage_locus(self, species: SpeciesType, locus_url: str) -> dict[str, str]:
        """Fetch content from the given locus URL, or fallback to seeded high-nutrition sources.

        Returns a dict with keys:
            title, url, content, tags, candidate_links (list[str])
        """
        clean_url = (locus_url or "").strip()

        try:
            fetched = await asyncio.wait_for(self._fetch_public(clean_url), timeout=self.timeout * 2)
        except Exception:
            fetched = None

        if fetched:
            final_url, raw_html = fetched
            text = self._sanitize_html(raw_html)
            if len(text) > 100:
                return {
                    "title": self._extract_title(raw_html) or final_url,
                    "url": final_url,
                    "content": text[:2000],
                    "tags": species.value,
                    "candidate_links": self._extract_links(raw_html, final_url),
                }

        # Network failed, timed out, or blocked: fall back to a seeded prey item for this species
        pool = SEEDED_PREY_CORPUS.get(species, SEEDED_PREY_CORPUS[SpeciesType.INFO])
        item = random.choice(pool)
        return {**item, "candidate_links": []}

    async def _fetch_public(self, url: str) -> tuple[str, str] | None:
        """GET a public web page, re-validating every redirect hop and pinning the vetted IP.

        Connecting to the exact address that passed validation (instead of letting the HTTP client
        resolve the hostname again) closes the DNS-rebinding window between check and use.
        """
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            for _ in range(MAX_REDIRECTS + 1):
                target = await asyncio.to_thread(self._pin_public_target, url)
                if target is None:
                    return None
                pinned_url, host = target
                async with client.stream(
                    "GET",
                    pinned_url,
                    headers={"Host": host, "User-Agent": USER_AGENT},
                    extensions={"sni_hostname": host},
                ) as resp:
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            return None
                        url = urljoin(url, location)
                        continue
                    if resp.status_code != 200:
                        return None
                    body = bytearray()
                    async for chunk in resp.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_BODY_BYTES:
                            break
                    return url, body[:MAX_BODY_BYTES].decode(resp.encoding or "utf-8", errors="replace")
        return None

    @staticmethod
    def _pin_public_target(url: str) -> tuple[str, str] | None:
        """Return (url rewritten to a vetted public IP, original host) or None if the URL is unsafe."""
        parts = WebForager._parse_fetchable(url)
        if parts is None:
            return None
        try:
            host = httpx.URL(url).raw_host.decode("ascii")
            infos = socket.getaddrinfo(host, DEFAULT_PORTS[parts.scheme], type=socket.SOCK_STREAM)
        except Exception:
            return None
        addresses = [info[4][0] for info in infos]
        # Every record must be public: a single private A/AAAA record could be the one actually used.
        if not addresses or not all(_is_public_ip(a) for a in addresses):
            return None
        ip = addresses[0]
        netloc = f"[{ip}]" if ":" in ip else ip
        return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, "")), host

    @staticmethod
    def _parse_fetchable(url: str):
        """Syntactic URL policy: http(s) only, default ports only, no embedded credentials."""
        try:
            parts = urlsplit(url)
            if parts.scheme not in DEFAULT_PORTS or not parts.hostname:
                return None
            if parts.username or parts.password:
                return None
            if parts.port is not None and parts.port != DEFAULT_PORTS[parts.scheme]:
                return None
        except ValueError:
            return None
        return parts

    def _sanitize_html(self, raw_html: str) -> str:
        """Clean HTML tags and scripts to extract raw readable text."""
        # Strip script and style elements
        text = re.sub(r"<(script|style).*?>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
        # Strip tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Unescape HTML entities
        text = html.unescape(text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _extract_title(self, raw_html: str) -> str | None:
        """Extract title from HTML <title> tag."""
        match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
        if match:
            clean = html.unescape(match.group(1)).strip()
            return re.sub(r"\s+", " ", clean)
        return None

    def _extract_links(self, raw_html: str, base_url: str) -> list[str]:
        """Extract candidate next-locus URLs from anchor tags in the fetched page.

        - Resolves relative URLs against base_url
        - Applies the syntactic URL policy; IP-level SSRF checks happen when a link is actually fetched
        - Returns up to 10 unique candidate links to keep Jev decision cost minimal
        """
        hrefs = re.findall(r'<a[^>]+href=["\']([^"\'>\s]{4,300})["\']', raw_html, re.IGNORECASE)
        seen: set[str] = set()
        candidates: list[str] = []

        for href in hrefs:
            absolute = urljoin(base_url, html.unescape(href))
            parts = self._parse_fetchable(absolute)
            if parts is None or parts.path in ("", "/") or absolute in seen:
                continue
            seen.add(absolute)
            candidates.append(absolute)
            if len(candidates) >= 10:
                break

        return candidates


def _is_public_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast
