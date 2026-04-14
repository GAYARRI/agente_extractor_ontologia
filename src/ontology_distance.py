from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set


@dataclass
class DistanceResult:
    source: str
    target: str
    distance: int
    similarity: float
    lca: Optional[str]
    source_depth: int
    target_depth: int


class OntologyDistance:
    """
    Distancia semántica jerárquica sobre una taxonomía padre->hijo.
    """

    def __init__(self, parent_map: Dict[str, Optional[str]]):
        self.parent_map = parent_map
        self.depth_cache: Dict[str, int] = {}

        self.generic_classes: Set[str] = {
            "Thing",
            "Place",
            "Organization",
            "Service",
            "Concept",
            "Accommodation",
            "EventAttendanceFacility",
        }

    def distance(self, source: Optional[str], target: Optional[str]) -> int:
        if not source or not target:
            return 999

        source = self._normalize(source)
        target = self._normalize(target)

        if source == target:
            return 0

        source_anc = self._ancestor_chain(source)
        target_anc = self._ancestor_chain(target)

        common = set(source_anc).intersection(target_anc)
        if not common:
            return 999

        lca = min(
            common,
            key=lambda c: self._distance_to_ancestor(source, c) + self._distance_to_ancestor(target, c),
        )
        return self._distance_to_ancestor(source, lca) + self._distance_to_ancestor(target, lca)

    def similarity(self, source: Optional[str], target: Optional[str]) -> float:
        if not source or not target:
            return 0.0

        source = self._normalize(source)
        target = self._normalize(target)

        if source == target:
            return 1.0

        d = self.distance(source, target)
        if d >= 999:
            return 0.0

        base = {
            0: 1.00,
            1: 0.83,
            2: 0.66,
            3: 0.50,
            4: 0.33,
        }.get(d, max(0.10, 1.0 - 0.18 * d))

        penalty = self._generic_penalty(source, target)
        sim = base * penalty

        return max(0.0, min(1.0, sim))

    def compare(self, source: Optional[str], target: Optional[str]) -> DistanceResult:
        source_n = self._normalize(source) if source else "Unknown"
        target_n = self._normalize(target) if target else "Unknown"

        d = self.distance(source_n, target_n)
        lca = self.lowest_common_ancestor(source_n, target_n)
        sim = self.similarity(source_n, target_n)

        return DistanceResult(
            source=source_n,
            target=target_n,
            distance=d,
            similarity=sim,
            lca=lca,
            source_depth=self.depth(source_n),
            target_depth=self.depth(target_n),
        )

    def lowest_common_ancestor(self, source: Optional[str], target: Optional[str]) -> Optional[str]:
        if not source or not target:
            return None

        source = self._normalize(source)
        target = self._normalize(target)

        source_anc = self._ancestor_chain(source)
        target_anc = self._ancestor_chain(target)

        common = set(source_anc).intersection(target_anc)
        if not common:
            return None

        return max(common, key=lambda c: self.depth(c))

    def depth(self, cls: Optional[str]) -> int:
        if not cls:
            return 0

        cls = self._normalize(cls)

        if cls in self.depth_cache:
            return self.depth_cache[cls]

        depth = 0
        cur = cls
        visited = set()

        while cur is not None and cur not in visited:
            visited.add(cur)
            parent = self.parent_map.get(cur)
            if parent is None:
                break
            depth += 1
            cur = parent

        self.depth_cache[cls] = depth
        return depth

    def _normalize(self, cls: str) -> str:
        return str(cls).strip()

    def _ancestor_chain(self, cls: str) -> List[str]:
        chain = [cls]
        visited = {cls}
        cur = cls

        while True:
            parent = self.parent_map.get(cur)
            if parent is None or parent in visited:
                break
            chain.append(parent)
            visited.add(parent)
            cur = parent

        return chain

    def _distance_to_ancestor(self, cls: str, ancestor: str) -> int:
        if cls == ancestor:
            return 0

        dist = 0
        cur = cls
        visited = {cls}

        while True:
            parent = self.parent_map.get(cur)
            if parent is None or parent in visited:
                return 999
            dist += 1
            if parent == ancestor:
                return dist
            visited.add(parent)
            cur = parent

    def _generic_penalty(self, source: str, target: str) -> float:
        source_generic = source in self.generic_classes
        target_generic = target in self.generic_classes

        if source_generic and target_generic:
            return 0.85

        if source_generic or target_generic:
            return 0.75

        depth_gap = abs(self.depth(source) - self.depth(target))
        if depth_gap >= 3:
            return 0.85

        return 1.0