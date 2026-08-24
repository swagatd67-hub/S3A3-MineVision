"""Multi-Frame Defect Projection Clustering and Association Engine (Phase 11 & 12)."""

from __future__ import annotations

import math
import uuid

from reconstruction.defect_models import (
    Grouped3DDefect,
    Projected3DDefect,
    ProjectionStatus,
)
from reconstruction.models import Point3D


class MultiFrameDefectAssociator:
    """Clusters and groups 3D projected defects corresponding to the same physical defect across multiple frames."""

    def __init__(
        self,
        longitudinal_threshold_m: float = 0.30,  # 30 cm longitudinal window
        angular_threshold_rad: float = 0.50,      # ~28 degrees angular window
        spatial_distance_threshold_m: float = 0.50,
    ) -> None:
        self.longitudinal_threshold_m = longitudinal_threshold_m
        self.angular_threshold_rad = angular_threshold_rad
        self.spatial_distance_threshold_m = spatial_distance_threshold_m

    def cluster_projections(
        self,
        projections: tuple[Projected3DDefect, ...],
    ) -> tuple[Grouped3DDefect, ...]:
        """Group 3D projected defects by class code and spatial/longitudinal proximity."""
        valid_projections = [p for p in projections if p.point_3d is not None and p.longitudinal_distance_m is not None]
        if not valid_projections:
            return ()

        # Group by class code first
        by_class: dict[str, list[Projected3DDefect]] = {}
        for p in valid_projections:
            by_class.setdefault(p.class_code, []).append(p)

        grouped_results: list[Grouped3DDefect] = []

        for class_projs in by_class.values():
            # Sort by longitudinal distance
            sorted_projs = sorted(class_projs, key=lambda x: x.longitudinal_distance_m or 0.0)
            visited = set()

            for i, p_curr in enumerate(sorted_projs):
                if p_curr.projection_id in visited:
                    continue

                cluster_members: list[Projected3DDefect] = [p_curr]
                visited.add(p_curr.projection_id)

                for j in range(i + 1, len(sorted_projs)):
                    p_next = sorted_projs[j]
                    if p_next.projection_id in visited:
                        continue

                    # Check proximity criteria
                    s_diff = abs((p_curr.longitudinal_distance_m or 0.0) - (p_next.longitudinal_distance_m or 0.0))
                    if s_diff > self.longitudinal_threshold_m:
                        break  # Outside longitudinal window

                    # Angular difference
                    theta_diff = abs((p_curr.angular_position_rad or 0.0) - (p_next.angular_position_rad or 0.0))
                    theta_diff = min(theta_diff, 2.0 * math.pi - theta_diff)

                    # Spatial 3D distance
                    dx = p_curr.point_3d.x - p_next.point_3d.x  # type: ignore[union-attr]
                    dy = p_curr.point_3d.y - p_next.point_3d.y  # type: ignore[union-attr]
                    dz = p_curr.point_3d.z - p_next.point_3d.z  # type: ignore[union-attr]
                    dist_3d = math.sqrt(dx**2 + dy**2 + dz**2)

                    if theta_diff <= self.angular_threshold_rad or dist_3d <= self.spatial_distance_threshold_m:
                        cluster_members.append(p_next)
                        visited.add(p_next.projection_id)

                # Form Grouped3DDefect
                grouped_results.append(self._create_grouped_defect(cluster_members))

        return tuple(grouped_results)

    def _create_grouped_defect(self, members: list[Projected3DDefect]) -> Grouped3DDefect:
        """Create a Grouped3DDefect from a set of member projections."""
        cluster_id = f"grp_{uuid.uuid4().hex[:12]}"
        primary = max(members, key=lambda m: m.ai_confidence)

        s_avg = sum(m.longitudinal_distance_m or 0.0 for m in members) / len(members)
        theta_avg = sum(m.angular_position_rad or 0.0 for m in members) / len(members)

        x_avg = sum(m.point_3d.x for m in members if m.point_3d is not None) / len(members)
        y_avg = sum(m.point_3d.y for m in members if m.point_3d is not None) / len(members)
        z_avg = sum(m.point_3d.z for m in members if m.point_3d is not None) / len(members)

        mean_pt = Point3D(x=x_avg, y=y_avg, z=z_avg)
        max_ai_conf = max(m.ai_confidence for m in members)
        frame_ids = tuple(m.frame_id for m in members if m.frame_id is not None)

        has_valid = any(m.quality_state == ProjectionStatus.VALID for m in members)

        return Grouped3DDefect(
            cluster_id=cluster_id,
            mission_id=primary.mission_id,
            class_code=primary.class_code,
            primary_projection_id=primary.projection_id,
            member_projection_ids=tuple(m.projection_id for m in members),
            frame_ids=frame_ids,
            mean_longitudinal_distance_m=s_avg,
            mean_angular_position_rad=theta_avg,
            mean_point_3d=mean_pt,
            observation_count=len(members),
            max_ai_confidence=max_ai_conf,
            overall_quality_state=ProjectionStatus.VALID if has_valid else ProjectionStatus.DEGRADED,
        )
