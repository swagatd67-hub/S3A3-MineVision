"""Camera-Ray Projection and Cylindrical Surface Intersection Engine."""

from __future__ import annotations

import math

from reconstruction.coordinates import (
    camera_to_robot,
    cartesian_to_cylindrical,
    robot_to_world,
)
from reconstruction.models import CameraCalibration, PipeCenterline, Point3D
from robot.localization.models import RobotPose


def pixel_to_camera_ray(
    u: float,
    v: float,
    calibration: CameraCalibration,
) -> tuple[float, float, float]:
    """Convert 2D image pixel coordinate (u, v) into a normalized 3D ray direction in Camera Frame.

    Camera Frame Convention:
    +Z_c: Forward along optical axis
    +X_c: Right
    +Y_c: Down
    """
    fx = calibration.fx if calibration.fx > 0 else 1000.0
    fy = calibration.fy if calibration.fy > 0 else 1000.0
    cx = calibration.cx if calibration.cx > 0 else (calibration.image_width / 2.0)
    cy = calibration.cy if calibration.cy > 0 else (calibration.image_height / 2.0)

    # Standard pinhole back-projection
    x_norm = (u - cx) / fx
    y_norm = (v - cy) / fy

    # Apply radial undistortion approximation if k1 is non-zero
    k1 = calibration.k1
    k2 = calibration.k2
    if k1 != 0.0 or k2 != 0.0:
        r2 = x_norm**2 + y_norm**2
        radial_factor = 1.0 + k1 * r2 + k2 * (r2**2)
        if radial_factor > 0:
            x_norm /= radial_factor
            y_norm /= radial_factor

    # Ray direction vector in camera frame (Z_c = 1.0 forward)
    len_ray = math.sqrt(x_norm**2 + y_norm**2 + 1.0)
    return (x_norm / len_ray, y_norm / len_ray, 1.0 / len_ray)


def camera_ray_to_world_ray(
    ray_dir_camera: tuple[float, float, float],
    pose: RobotPose,
    camera_offset_m: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> tuple[Point3D, Point3D]:
    """Transform Camera Frame ray into Reconstructed World 3D Frame.

    Returns:
    (ray_origin_world, ray_direction_world)
    """
    # 1. Ray origin in Camera Frame is (0, 0, 0)
    origin_cam = Point3D(x=0.0, y=0.0, z=0.0)
    origin_robot = camera_to_robot(origin_cam, camera_offset_m=camera_offset_m)
    origin_world = robot_to_world(origin_robot, pose)

    # 2. Point along ray in Camera Frame
    dx, dy, dz = ray_dir_camera
    pt_ray_cam = Point3D(x=dx, y=dy, z=dz)
    pt_ray_robot = camera_to_robot(pt_ray_cam, camera_offset_m=camera_offset_m)
    pt_ray_world = robot_to_world(pt_ray_robot, pose)

    # Ray direction in world frame
    dir_x = pt_ray_world.x - origin_world.x
    dir_y = pt_ray_world.y - origin_world.y
    dir_z = pt_ray_world.z - origin_world.z
    norm_dir = math.sqrt(dir_x**2 + dir_y**2 + dir_z**2)

    if norm_dir > 0:
        dir_world = Point3D(x=dir_x / norm_dir, y=dir_y / norm_dir, z=dir_z / norm_dir)
    else:
        dir_world = Point3D(x=1.0, y=0.0, z=0.0)

    return (origin_world, dir_world)


def intersect_ray_with_pipe_cylinder(
    ray_origin: Point3D,
    ray_direction: Point3D,
    centerline: PipeCenterline,
    pipe_radius_m: float,
) -> tuple[Point3D | None, float | None, float | None, tuple[float, float, float] | None]:
    """Compute analytical 3D intersection of world camera ray with reconstructed cylindrical pipe wall.

    Returns:
    (intersection_point_3d, longitudinal_s_m, angular_theta_rad, surface_normal_xyz)
    """
    if not centerline.points or pipe_radius_m <= 0:
        return (None, None, None, None)

    # Find closest centerline segment to ray origin
    closest_cl = centerline.points[0]
    min_d_sq = float("inf")
    for cl in centerline.points:
        d_sq = (ray_origin.x - cl.x) ** 2 + (ray_origin.y - cl.y) ** 2 + (ray_origin.z - cl.z) ** 2
        if d_sq < min_d_sq:
            min_d_sq = d_sq
            closest_cl = cl

    # Cylinder axis unit direction V (from centerline heading)
    heading = closest_cl.heading_rad
    V_x = math.cos(heading)
    V_y = math.sin(heading)
    V_z = 0.0

    # Ray origin O, direction D
    O = (ray_origin.x, ray_origin.y, ray_origin.z)
    D = (ray_direction.x, ray_direction.y, ray_direction.z)
    C = (closest_cl.x, closest_cl.y, closest_cl.z)

    # W = O - C
    W = (O[0] - C[0], O[1] - C[1], O[2] - C[2])

    # Projections perpendicular to V:
    # D_perp = D - (D . V) V
    dot_D_V = D[0] * V_x + D[1] * V_y + D[2] * V_z
    D_perp = (D[0] - dot_D_V * V_x, D[1] - dot_D_V * V_y, D[2] - dot_D_V * V_z)

    # W_perp = W - (W . V) V
    dot_W_V = W[0] * V_x + W[1] * V_y + W[2] * V_z
    W_perp = (W[0] - dot_W_V * V_x, W[1] - dot_W_V * V_y, W[2] - dot_W_V * V_z)

    # Quadratic equation: a t^2 + b t + c = 0
    a = D_perp[0] ** 2 + D_perp[1] ** 2 + D_perp[2] ** 2
    b = 2.0 * (D_perp[0] * W_perp[0] + D_perp[1] * W_perp[1] + D_perp[2] * W_perp[2])
    c = (W_perp[0] ** 2 + W_perp[1] ** 2 + W_perp[2] ** 2) - (pipe_radius_m**2)

    if abs(a) < 1e-9:
        return (None, None, None, None)

    discriminant = b**2 - 4.0 * a * c
    if discriminant < 0:
        return (None, None, None, None)

    sqrt_disc = math.sqrt(discriminant)
    t1 = (-b - sqrt_disc) / (2.0 * a)
    t2 = (-b + sqrt_disc) / (2.0 * a)

    # Select smallest positive t (front intersection)
    t_solution: float | None = None
    if t1 > 0:
        t_solution = t1
    elif t2 > 0:
        t_solution = t2

    if t_solution is None:
        return (None, None, None, None)

    # 3D intersection point
    int_x = O[0] + t_solution * D[0]
    int_y = O[1] + t_solution * D[1]
    int_z = O[2] + t_solution * D[2]

    # Calculate local surface normal (pointing inwards/towards pipe center)
    # Vector from cylinder axis to intersection point
    dx_axis = int_x - (C[0] + dot_W_V * V_x)
    dy_axis = int_y - (C[1] + dot_W_V * V_y)
    dz_axis = int_z - C[2]
    norm_len = math.sqrt(dx_axis**2 + dy_axis**2 + dz_axis**2)

    if norm_len > 0:
        # Inward surface normal for pipe interior camera view
        nx, ny, nz = -dx_axis / norm_len, -dy_axis / norm_len, -dz_axis / norm_len
    else:
        nx, ny, nz = 0.0, 0.0, 1.0

    pt_int = Point3D(x=int_x, y=int_y, z=int_z, nx=nx, ny=ny, nz=nz)

    # Convert to cylindrical s, theta
    s_m, theta_rad, _ = cartesian_to_cylindrical(pt_int, centerline)

    return (pt_int, s_m, theta_rad, (nx, ny, nz))
