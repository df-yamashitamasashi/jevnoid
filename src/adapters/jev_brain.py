from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.adapters.secrets import read_secret
from src.domain.dna import DNA_REGISTRY, OrganismDNA
from src.domain.species import SpeciesType

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SECRETS_KEY_FILE = ROOT_DIR / ".secrets" / "typesafe_api_key"

# Tierra-style growth vectors Jev chooses from: (azimuth_deg, elevation_deg)
GROWTH_VECTORS: dict[str, tuple[str, tuple[float, float]]] = {
    "spiral_ascend": ("Ascend diagonally in a radiant golden spiral towards celestial enlightenment (+35 deg elevation, +50 deg azimuth)", (50.0, 35.0)),
    "orthogonal_branch": ("Sprout an orthogonal lateral branch to explore a complementary dimension (0 deg elevation, +90 deg azimuth)", (90.0, 0.0)),
    "descend_root": ("Penetrate downward into deep foundational grounding / abyssal organic depth (-35 deg elevation, +135 deg azimuth)", (135.0, -35.0)),
    "helical_expansion": ("Curve outward in a cosmic helical expansion (+15 deg elevation, +140 deg azimuth)", (140.0, 15.0)),
    "contra_lateral": ("Branch across into opposing dialectic balance (-15 deg elevation, -90 deg azimuth)", (-90.0, -15.0)),
    "polar_zenith": ("Erupt straight upward toward the apex summit (+65 deg elevation, +20 deg azimuth)", (20.0, 65.0)),
    "nadir_abyss": ("Plunge downward into the primordial subterranean root core (-65 deg elevation, -45 deg azimuth)", (-45.0, -65.0)),
}
GROWTH_ANCHORS = {
    "latest_tip": "Sprout outward from the latest exterior tip (progressive elongation and exploration)",
    "random_branch": "Branch orthogonally from an existing somatic trunk node (complex arborization and diversification)",
    "nucleus_origin": "Emanate a new primary axis directly from the central core origin nucleus",
}
MAX_LINK_CANDIDATES = 6


def get_typesafe_api_key() -> str | None:
    """TYPESAFE_API_KEY env var, then the SSM parameter in TYPESAFE_API_KEY_PARAM, then local .secrets file."""
    try:
        key = read_secret("TYPESAFE_API_KEY", "TYPESAFE_API_KEY_PARAM") or ""
    except Exception as e:
        print(f"[JevBrain] Could not read API key from SSM ({type(e).__name__}); using heuristic decisions.")
        key = ""
    if not key and SECRETS_KEY_FILE.exists():
        key = SECRETS_KEY_FILE.read_text("utf-8").strip()
    candidates = [
        line.strip()
        for line in key.splitlines()
        if re.fullmatch(r"[A-Za-z0-9_\-]{20,}", line.strip())
    ]
    return candidates[0] if candidates else None


@dataclass(frozen=True)
class ActionRequest:
    key: str
    species: SpeciesType
    perception: str
    energy: float
    hunger: float


@dataclass(frozen=True)
class GrowthRequest:
    key: str
    species: SpeciesType
    prey_title: str
    prey_content: str
    cells_count: int
    energy: float
    sprouts: int


@dataclass(frozen=True)
class LocusRequest:
    key: str
    species: SpeciesType
    prey_title: str
    prey_content: str
    candidate_links: list[str]
    current_locus: str


# (anchor_choice, azimuth_deg, elevation_deg, growth_distance, cell_radius, hex_color)
Sprout = tuple[str, float, float, float, float, str]


class JevBrain:
    """System One decision-making and intuition engine powered by TypeSafe AI (Jev).

    Every heartbeat asks Jev about all organisms at once: one call for their actions, and one call
    for the growth and next locus of those that fed. The number of calls does not grow with the population.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or get_typesafe_api_key()
        self._client = None
        if self.api_key:
            try:
                from typesafe_sdk import TypeSafeClient
                os.environ["TYPESAFE_API_KEY"] = self.api_key
                self._client = TypeSafeClient(api_key=self.api_key)
            except Exception as e:
                print(f"[JevBrain] Failed to initialize TypeSafeClient: {e}")

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def _ask(self, state: dict[str, str], questions: dict[str, Any]) -> dict[str, Any] | None:
        if not self._client or not questions:
            return None
        try:
            return self._client.system_one(state=state, questions=questions).answers
        except Exception as e:
            print(f"[JevBrain] API error: {type(e).__name__}: {e}. Falling back to heuristic decisions.")
            return None

    def decide_actions(self, requests: list[ActionRequest]) -> dict[str, tuple[str, float, str]]:
        """Metabolic action and perceived nutritional quality for each organism, in a single Jev call."""
        results = {r.key: self._heuristic_decision(r) for r in requests}
        if not self._client or not requests:
            return results

        from typesafe_sdk import Choice, Noul

        state: dict[str, str] = {}
        questions: dict[str, Any] = {}
        for i, r in enumerate(requests):
            dna = DNA_REGISTRY[r.species]
            tag = f"organism_{i}"
            state[tag] = (
                f"Species: {r.species.value}, Somatic Energy: {r.energy:.1f}%, Hunger Level: {r.hunger:.2f}\n"
                f"Perceived Environmental Feed:\n{r.perception.strip()[:2000]}"
            )
            questions[f"action_{i}"] = Choice(
                instructions=f"For `{tag}` only: select the immediate metabolic action for this {r.species.value} organism according to its survival imperative.",
                criteria=dna.action_criteria,
            )
            questions[f"quality_{i}"] = Noul(instructions=f"For `{tag}` only: {dna.noul_prompt}")

        answers = self._ask(state, questions)
        if answers is None:
            return results
        for i, r in enumerate(requests):
            try:
                action = answers[f"action_{i}"]
                quality = float(answers[f"quality_{i}"].noul)
                confidence = getattr(action, "confidence", 0.9)
                results[r.key] = (action.choice, quality, f"Jev intuition: {action.choice} (confidence: {confidence:.2f})")
            except Exception as e:
                print(f"[JevBrain] Missing action answer for {r.key}: {type(e).__name__}")
        return results

    def decide_growth_and_locus(
        self, growths: list[GrowthRequest], loci: list[LocusRequest]
    ) -> tuple[dict[str, list[Sprout]], dict[str, str]]:
        """3D morphogenesis for each sprouting cell and the next foraging locus, in a single Jev call."""
        sprout_plans: dict[str, list[tuple[str, str, float]]] = {
            g.key: [self._fallback_geometry(g.prey_content, n) for n in range(g.sprouts)] for g in growths
        }
        next_loci = {l.key: self._heuristic_next_locus(l.candidate_links[:MAX_LINK_CANDIDATES], l) for l in loci}
        if not self._client or not (growths or loci):
            return self._materialize_all(growths, sprout_plans), next_loci

        from typesafe_sdk import Choice, Noul

        state: dict[str, str] = {}
        questions: dict[str, Any] = {}
        for i, g in enumerate(growths):
            tag = f"growth_{i}"
            state[tag] = (
                f"Ingested Knowledge: {g.prey_title}\nContent Snippet: {g.prey_content[:800]}\n"
                f"Organism Topology: Existing Cells={g.cells_count}, Excess Energy={g.energy:.1f}%"
            )
            for n in range(g.sprouts):
                ordinal = f"new cell #{n + 1} of {g.sprouts}" if g.sprouts > 1 else "the newly sprouting cell"
                questions[f"vector_{i}_{n}"] = Choice(
                    instructions=f"For `{tag}` only: select the developmental morphogenesis trajectory for {ordinal}, based on the ingested knowledge.",
                    criteria={name: desc for name, (desc, _) in GROWTH_VECTORS.items()},
                )
                questions[f"anchor_{i}_{n}"] = Choice(
                    instructions=f"For `{tag}` only: select the structural anchor node where {ordinal} branches from (Tierra self-morphogenesis).",
                    criteria=GROWTH_ANCHORS,
                )
                questions[f"scale_{i}_{n}"] = Noul(
                    instructions=f"For `{tag}` only: evaluate the cognitive impact and nutritional density to size {ordinal} (0.0 to 1.0).",
                )
        for i, l in enumerate(loci):
            tag = f"forager_{i}"
            dna = DNA_REGISTRY[l.species]
            candidates = l.candidate_links[:MAX_LINK_CANDIDATES]
            links = "\n".join(f"  {k + 1}. {url}" for k, url in enumerate(candidates))
            state[tag] = (
                f"Species: {l.species.value} — {dna.preferred_keywords[:4]}\n"
                f"Just ingested: '{l.prey_title}'\nContent snippet: {l.prey_content[:400]}\n"
                f"Discovered frontier links on this page:\n{links}"
            )
            criteria = {f"follow_{k}": f"Follow link {k + 1}: {url}" for k, url in enumerate(candidates)}
            criteria["stay_current"] = "Remain at the current locus — the page was nutritious but no link looks more promising."
            questions[f"locus_{i}"] = Choice(
                instructions=(
                    f"For `{tag}` only: you are the foraging instinct of a {l.species.value} organism. Select the most "
                    "ecologically relevant next locus that aligns with your species niche, or stay at the current page "
                    "if no link offers richer nutrition."
                ),
                criteria=criteria,
            )

        answers = self._ask(state, questions)
        if answers is not None:
            for i, g in enumerate(growths):
                for n in range(g.sprouts):
                    try:
                        vector = answers[f"vector_{i}_{n}"].choice
                        anchor = answers[f"anchor_{i}_{n}"].choice
                        scale = float(answers[f"scale_{i}_{n}"].noul)
                        if vector in GROWTH_VECTORS and anchor in GROWTH_ANCHORS:
                            sprout_plans[g.key][n] = (anchor, vector, scale)
                    except Exception as e:
                        print(f"[JevBrain] Missing growth answer for {g.key}: {type(e).__name__}")
            for i, l in enumerate(loci):
                try:
                    choice = answers[f"locus_{i}"].choice
                except Exception as e:
                    print(f"[JevBrain] Missing locus answer for {l.key}: {type(e).__name__}")
                    continue
                if choice == "stay_current":
                    next_loci[l.key] = l.current_locus
                else:
                    idx = choice.removeprefix("follow_")
                    candidates = l.candidate_links[:MAX_LINK_CANDIDATES]
                    if idx.isdigit() and int(idx) < len(candidates):
                        next_loci[l.key] = candidates[int(idx)]

        return self._materialize_all(growths, sprout_plans), next_loci

    def _materialize_all(
        self, growths: list[GrowthRequest], sprout_plans: dict[str, list[tuple[str, str, float]]]
    ) -> dict[str, list[Sprout]]:
        growth_by_key = {g.key: g for g in growths}
        return {
            key: [self._materialize(growth_by_key[key], anchor, vector, scale) for anchor, vector, scale in plans]
            for key, plans in sprout_plans.items()
        }

    def _materialize(self, g: GrowthRequest, anchor: str, vector: str, scale: float) -> Sprout:
        azimuth_deg, elevation_deg = GROWTH_VECTORS[vector][1]
        growth_distance = round(3.5 + scale * 10.5, 2)  # 3.5 to 14.0 units between nodes
        cell_radius = round(0.8 + scale * 2.0, 2)       # 0.8 to 2.8 units
        return anchor, azimuth_deg, elevation_deg, growth_distance, cell_radius, self._determine_pigment(g.species, g.prey_content, scale)

    def _fallback_geometry(self, content: str, sprout_index: int = 0) -> tuple[str, str, float]:
        """Deterministic hash-based (anchor, vector, scale) when Jev is unavailable."""
        h = hashlib.sha256(f"{content}#{sprout_index}".encode("utf-8")).digest()
        anchors = list(GROWTH_ANCHORS)
        vectors = list(GROWTH_VECTORS)
        return anchors[h[0] % len(anchors)], vectors[h[1] % len(vectors)], round(0.35 + (h[2] / 255.0) * 0.60, 2)

    def _determine_pigment(self, species: SpeciesType, content: str, scale: float) -> str:
        """Calculate subtle bio-luminescent tint variations based on digested concepts."""
        base_palette = {
            SpeciesType.THEOS: ["#ffd166", "#ffe082", "#ffca28", "#fff8e1"],
            SpeciesType.GAIA:  ["#06d6a0", "#2ec4b6", "#57cc99", "#80ed99"],
            SpeciesType.COSMO: ["#b5179e", "#7209b7", "#9d4edd", "#c77dff"],
            SpeciesType.INFO:  ["#4cc9f0", "#4895ef", "#4361ee", "#70e000"],
        }
        palette = base_palette.get(species, ["#ffffff"])
        idx = int(hashlib.md5(content.encode()).hexdigest(), 16) % len(palette)
        return palette[idx]

    def _heuristic_next_locus(self, candidates: list[str], request: LocusRequest) -> str:
        """Score URLs by preferred keyword presence in the URL path itself."""
        dna: OrganismDNA = DNA_REGISTRY[request.species]
        best_url = request.current_locus
        best_score = -1
        for url in candidates:
            url_lower = url.lower()
            score = sum(1 for kw in dna.preferred_keywords if kw.lower() in url_lower)
            score -= sum(1 for kw in dna.repelled_keywords if kw.lower() in url_lower)
            if score > best_score:
                best_score = score
                best_url = url
        return best_url

    def _heuristic_decision(self, request: ActionRequest) -> tuple[str, float, str]:
        """Deterministic heuristic fallback based on keyword scoring."""
        dna = DNA_REGISTRY[request.species]
        text_lower = request.perception.lower()
        score = 0.5
        score += sum(1 for kw in dna.preferred_keywords if kw.lower() in text_lower) * 0.12
        score -= sum(1 for kw in dna.repelled_keywords if kw.lower() in text_lower) * 0.20
        score = max(0.05, min(0.98, score))

        if request.energy < 20.0 or request.hunger > 0.7:
            if score > 0.35:
                return "ingest_nourish", score, f"Urgent hunger satisfied ({score:.2f})"
            return "swim_next", score, "Migrating locus to find richer nutrients"

        if score >= 0.65:
            return "ingest_nourish", score, f"High nutritional density assimilated ({score:.2f})"
        if score < 0.25:
            return "swim_next", score, "Barren locus detected. Migrating to new frontier"
        return "rest_meditate", score, "Harmonious balance achieved. Entering resting meditation"
