from __future__ import annotations

import math
import uuid
from typing import Any
from pydantic import BaseModel, Field


class CellNode(BaseModel):
    """A single cell node in 3D biological space."""
    id: str
    parent_id: str | None = None
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    radius: float = 1.0
    color: str = "#ffffff"
    generation: int = 0
    source_title: str = "原初核 (Origin Nucleus)"


class CellEdge(BaseModel):
    """Connection/fiber between two cell nodes."""
    source_id: str
    target_id: str


class Morphology3D(BaseModel):
    """3D body graph of an organism that grows autonomously from a single core."""
    cells: list[CellNode] = Field(default_factory=list)
    edges: list[CellEdge] = Field(default_factory=list)

    @classmethod
    def initial_seed(cls, theme_color: str) -> Morphology3D:
        """Spawn with strictly a single nucleus at (0, 0, 0)."""
        nucleus = CellNode(
            id="cell-origin",
            parent_id=None,
            x=0.0,
            y=0.0,
            z=0.0,
            radius=1.8,
            color=theme_color,
            generation=0,
            source_title="原初核 (Origin Nucleus)",
        )
        return cls(cells=[nucleus], edges=[])

    def grow_cell(
        self,
        anchor_choice: str,
        azimuth_deg: float,
        elevation_deg: float,
        growth_distance: float,
        cell_radius: float,
        cell_color: str,
        source_title: str,
    ) -> Morphology3D:
        """Add a new cell in 3D space branching from an existing anchor cell."""
        if not self.cells:
            return self

        # 1. Select anchor cell based on Tierra memory allocation mode
        anchor = self.cells[0]  # default origin
        if anchor_choice == "latest_tip":
            anchor = self.cells[-1]
        elif anchor_choice == "random_branch" and len(self.cells) > 1:
            import random
            anchor = random.choice(self.cells)

        # 2. Compute 3D direction vector with biological phyllotaxis divergence
        # Golden angle (~137.5 deg) ensures organic 3D arborization across all 3 axes (X, Y, Z)
        divergence = (anchor.generation * 137.5) % 360.0
        effective_azimuth = (azimuth_deg + divergence) % 360.0

        rad_az = math.radians(effective_azimuth)
        rad_el = math.radians(elevation_deg)

        dx = growth_distance * math.cos(rad_el) * math.cos(rad_az)
        dy = growth_distance * math.sin(rad_el)
        dz = growth_distance * math.cos(rad_el) * math.sin(rad_az)

        new_x = round(anchor.x + dx, 2)
        new_y = round(anchor.y + dy, 2)
        new_z = round(anchor.z + dz, 2)

        new_id = f"c{len(self.cells)}-{uuid.uuid4().hex[:4]}"
        new_cell = CellNode(
            id=new_id,
            parent_id=anchor.id,
            x=new_x,
            y=new_y,
            z=new_z,
            radius=round(cell_radius, 2),
            color=cell_color,
            generation=anchor.generation + 1,
            source_title=source_title,
        )

        new_edge = CellEdge(source_id=anchor.id, target_id=new_id)

        # Immutability: return updated copy
        return self.model_copy(
            update={
                "cells": self.cells + [new_cell],
                "edges": self.edges + [new_edge],
            }
        )

    def lose_cells(self, count: int) -> Morphology3D:
        """Prune the `count` most recently grown cells (disease/parasite damage), keeping at least one.

        A cell's `parent_id` always points earlier in `cells` than the cell itself (parents exist
        before their children can be grown), so trimming the tail never orphans a surviving cell.
        """
        if count <= 0 or len(self.cells) <= 1:
            return self
        count = min(count, len(self.cells) - 1)
        removed_ids = {c.id for c in self.cells[-count:]}
        return self.model_copy(
            update={
                "cells": self.cells[:-count],
                "edges": [e for e in self.edges if e.source_id not in removed_ids and e.target_id not in removed_ids],
            }
        )
