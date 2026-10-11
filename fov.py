"""
Two distinct visibility systems:

1. player_visibility_polygon() - 360 degree raycast used purely for
   rendering the fog of war. It has nothing to do with what the alien
   knows; it's just "what pixels can the human see right now".

2. can_see_point() - a narrow forward-facing cone + line-of-sight check.
   This is the ONLY function the alien is allowed to use to determine if
   it currently sees the player. It never has access to player.pos
   directly for decision-making outside of this check.
"""

import math
from config import PLAYER_VIEW_RADIUS, PLAYER_VIEW_RAYS, TILE


def _cast_ray(ship_map, ox, oy, angle, max_dist, step=6):
    """Intersect tile boundaries exactly so the light does not chew into walls."""
    dx, dy = math.cos(angle), math.sin(angle)
    tx,ty=math.floor(ox/TILE),math.floor(oy/TILE)
    if ship_map.is_wall_tile(tx,ty):return ox,oy,0
    sx=1 if dx>=0 else -1;sy=1 if dy>=0 else -1
    delta_x=TILE/abs(dx) if abs(dx)>1e-12 else math.inf
    delta_y=TILE/abs(dy) if abs(dy)>1e-12 else math.inf
    next_x=(((tx+1)*TILE-ox) if sx>0 else (ox-tx*TILE))/abs(dx) if abs(dx)>1e-12 else math.inf
    next_y=(((ty+1)*TILE-oy) if sy>0 else (oy-ty*TILE))/abs(dy) if abs(dy)>1e-12 else math.inf
    while min(next_x,next_y)<=max_dist:
        distance=min(next_x,next_y)
        if abs(next_x-next_y)<1e-9:
            # A ray touching two solid corners cannot shine through their seam.
            if ship_map.is_wall_tile(tx+sx,ty) or ship_map.is_wall_tile(tx,ty+sy):
                return ox+dx*distance,oy+dy*distance,distance
            tx+=sx;ty+=sy;next_x+=delta_x;next_y+=delta_y
        elif next_x<next_y:tx+=sx;next_x+=delta_x
        else:ty+=sy;next_y+=delta_y
        if ship_map.is_wall_tile(tx,ty):return ox+dx*distance,oy+dy*distance,distance
    return ox + dx * max_dist, oy + dy * max_dist, max_dist


def player_visibility_polygon(ship_map, origin, radius=PLAYER_VIEW_RADIUS,
                               rays=PLAYER_VIEW_RAYS):
    """Returns a list of (x, y) points forming the visible-area polygon
    around origin, built by casting rays in all directions and stopping
    at the first wall. This is a real visibility polygon, not a circle -
    it hugs corners and leaves everything behind a wall dark."""
    ox, oy = origin
    points = []
    step_angle = (2 * math.pi) / rays
    for i in range(rays):
        angle = i * step_angle
        x, y, _ = _cast_ray(ship_map, ox, oy, angle, radius)
        points.append((x, y))
    return points


def angle_diff(a, b):
    """Smallest signed difference between two angles, in radians."""
    d = (a - b + math.pi) % (2 * math.pi) - math.pi
    return d


def can_see_point(ship_map, viewer_pos, facing_angle, target_pos,
                   fov_deg, max_range):
    """Cone + line-of-sight visibility check, used by the alien.
    Returns (visible: bool, distance: float, centrality: float 0-1)."""
    vx, vy = viewer_pos
    tx, ty = target_pos
    dx, dy = tx - vx, ty - vy
    dist = math.hypot(dx, dy)
    if dist > max_range:
        return False, dist, 0.0
    if dist < 1e-6:
        return True, dist, 1.0

    target_angle = math.atan2(dy, dx)
    half_fov = math.radians(fov_deg) / 2.0
    diff = abs(angle_diff(target_angle, facing_angle))
    if diff > half_fov:
        return False, dist, 0.0

    if not ship_map.line_of_sight(vx, vy, tx, ty):
        return False, dist, 0.0

    centrality = 1.0 - (diff / half_fov)     # 1.0 = dead ahead, 0 = edge of cone
    return True, dist, centrality


def cone_polygon(ship_map, origin, facing_angle, fov_deg, max_range, rays=24):
    """Debug-only: a polygon approximating the alien's vision cone,
    clipped by walls, for the F3 overlay."""
    ox, oy = origin
    half_fov = math.radians(fov_deg) / 2.0
    points = [(ox, oy)]
    for i in range(rays + 1):
        t = i / rays
        angle = facing_angle - half_fov + t * (2 * half_fov)
        x, y, _ = _cast_ray(ship_map, ox, oy, angle, max_range)
        points.append((x, y))
    return points
