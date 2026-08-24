"""Canonical Coordinate Frames & Explicit Metric Transformations for 3D Pipe Reconstruction.

UNITS DECLARATION:
- Cartesian Positions (x, y, z): Meters (m)
- Cylindrical Longitudinal Distance (s): Meters (m)
- Cylindrical Angular Position (theta): Radians (rad), [0, 2*pi). 0 = Top/12 o'clock, pi/2 = Right/3 o'clock, pi = Bottom/6 o'clock, 3*pi/2 = Left/9 o'clock.
- Cylindrical Radius Offset (r / delta_r): Millimeters (mm) or Meters (m) as explicitly typed.
- Angles & Orientations: Radians (rad) unless suffix explicitly specifies _deg.

COORDINATE FRAMES:
1. CAMERA FRAME:
   - +Z_c: Forward along camera optical axis (view direction)
   - +X_c: Right
   - +Y_c: Down
2. ROBOT / LOCALIZATION FRAME:
   - +X_r: Longitudinal forward along crawler travel direction
   - +Y_r: Lateral left
   - +Z_r: Vertical up
3. PIPE CYLINDRICAL FRAME:
   - s: Distance along longitudinal pipe axis (m)
   - theta: Angular clock position (rad)
   - r: Radial distance from pipe center (m)
4. RECONSTRUCTED 3D / WORLD FRAME:
   - X_w: World longitudinal axis (m)
   - Y_w: World horizontal cross axis (m)
   - Z_w: World vertical elevation axis (m)
"""

from __future__ import annotations

import math

from reconstruction.exceptions import CoordinateTransformError
from reconstruction.models import PipeCenterline, PipeCenterlinePoint, Point3D
from robot.localization.models import RobotPose


def camera_to_robot(
    point_camera: Point3D,
    camera_offset_m: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Point3D:
    """Transform a 3D point from Camera Frame (Z-forward, X-right, Y-down) to Robot Body Frame (X-forward, Y-left, Z-up).

    Units: Meters (m)
    """
    dx, dy, dz = camera_offset_m
    # Camera +Z_c -> Robot +X_r
    # Camera +X_c -> Robot -Y_r
    # Camera +Y_c -> Robot -Z_r
    x_r = point_camera.z + dx
    y_r = -point_camera.x + dy
    z_r = -point_camera.y + dz

    return Point3D(x=x_r, y=y_r, z=z_r, nx=point_camera.nx, ny=point_camera.ny, nz=point_camera.nz)


def robot_to_world(
    point_robot: Point3D,
    pose: RobotPose,
) -> Point3D:
    """Transform a 3D point from Robot Body Frame to Reconstructed World 3D Frame using RobotPose.

    Units: Meters (m), Radians (rad)
    """
    heading = pose.heading_rad
    cos_h = math.cos(heading)
    sin_h = math.sin(heading)

    # 2D rotation around vertical Z axis + 2D translation (pose.x = distance_m, pose.y = lateral y)
    x_w = pose.x + (point_robot.x * cos_h - point_robot.y * sin_h)
    y_w = pose.y + (point_robot.x * sin_h + point_robot.y * cos_h)
    z_w = point_robot.z  # Robot Z_r corresponds to World Z_w elevation

    nx_w, ny_w, nz_w = None, None, None
    if point_robot.nx is not None and point_robot.ny is not None and point_robot.nz is not None:
        nx_w = point_robot.nx * cos_h - point_robot.ny * sin_h
        ny_w = point_robot.nx * sin_h + point_robot.ny * cos_h
        nz_w = point_robot.nz

    return Point3D(x=x_w, y=y_w, z=z_w, nx=nx_w, ny=ny_w, nz=nz_w)


def cylindrical_to_cartesian(
    longitudinal_s_m: float,
    angular_theta_rad: float,
    radius_r_m: float,
    centerline_point: PipeCenterlinePoint,
) -> Point3D:
    """Convert Cylindrical Pipe Surface Coordinates (s, theta, r) to Cartesian 3D World Point (X_w, Y_w, Z_w).

    Units:
    - s: meters
    - theta: radians [0, 2*pi) (0 = Top/12 o'clock, pi/2 = Right/3 o'clock, etc.)
    - radius_r_m: meters
    """
    # Normalize theta to [0, 2*pi)
    theta = angular_theta_rad % (2.0 * math.pi)

    # Pipe cross-section offsets relative to centerline:
    # 0 rad (Top) -> +Z (up)
    # pi/2 rad (Right) -> +Y (right)
    # pi rad (Bottom) -> -Z (down)
    # 3*pi/2 rad (Left) -> -Y (left)
    dy = radius_r_m * math.sin(theta)
    dz = radius_r_m * math.cos(theta)

    # Heading rotation of the cross section:
    cos_h = math.cos(centerline_point.heading_rad)
    sin_h = math.sin(centerline_point.heading_rad)

    x_w = centerline_point.x - dy * sin_h
    y_w = centerline_point.y + dy * cos_h
    z_w = centerline_point.z + dz

    # Surface normal pointing outwards from pipe center
    nx = -sin_h * math.sin(theta)
    ny = cos_h * math.sin(theta)
    nz = math.cos(theta)

    return Point3D(x=x_w, y=y_w, z=z_w, nx=nx, ny=ny, nz=nz)


def cartesian_to_cylindrical(
    point: Point3D,
    centerline: PipeCenterline,
) -> tuple[float, float, float]:
    """Convert Cartesian 3D World Point back to Pipe Cylindrical Coordinates (s_m, theta_rad, r_m).

    Returns:
    (longitudinal_s_m, angular_theta_rad, radius_r_m)
    """
    if not centerline.points:
        raise CoordinateTransformError("Cannot transform point against an empty pipe centerline.")

    # Find closest centerline segment
    best_pt = centerline.points[0]
    min_dist_sq = float("inf")

    for pt in centerline.points:
        dist_sq = (point.x - pt.x) ** 2 + (point.y - pt.y) ** 2 + (point.z - pt.z) ** 2
        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq
            best_pt = pt

    longitudinal_s_m = best_pt.distance_m

    # Relative offset from closest centerline point
    cos_h = math.cos(best_pt.heading_rad)
    sin_h = math.sin(best_pt.heading_rad)

    dx_w = point.x - best_pt.x
    dy_w = point.y - best_pt.y
    dz_w = point.z - best_pt.z

    # Rotate into cross-section plane
    dy_local = -dx_w * sin_h + dy_w * cos_h
    dz_local = dz_w

    radius_r_m = math.sqrt(dy_local**2 + dz_local**2)
    angular_theta_rad = math.atan2(dy_local, dz_local) % (2.0 * math.pi)

    return (longitudinal_s_m, angular_theta_rad, radius_r_m)
