"""
Simple grid A*. The alien never moves directly toward the player's vector;
every destination it picks (investigate point, search waypoint, wander
point) gets turned into a tile path here, which is then walked waypoint
by waypoint. Permanent walls block every route. A hunter may plan through
closed doors at extra cost; physical movement still waits for a breach.
"""

import heapq
import math
from config import TILE, COLS, ROWS


def world_to_tile(wx, wy):
    return int(wx // TILE), int(wy // TILE)


def tile_to_world_center(tx, ty):
    return tx * TILE + TILE / 2, ty * TILE + TILE / 2


def _heuristic(a, b, diagonal=False):
    dx,dy=abs(a[0]-b[0]),abs(a[1]-b[1])
    return max(dx,dy)+(math.sqrt(2)-1)*min(dx,dy) if diagonal else dx+dy


def _nearest_floor_tile(ship_map, tile, max_radius=4,allow_closed_doors=False):
    """If a destination tile is (or becomes) a wall, hunt outward for the
    closest open tile so a path request never silently fails."""
    if not ship_map.is_path_wall(*tile,allow_closed_doors=allow_closed_doors):
        return tile
    tx, ty = tile
    for r in range(1, max_radius + 1):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                cand = (tx + dx, ty + dy)
                if not ship_map.is_path_wall(*cand,allow_closed_doors=allow_closed_doors):
                    return cand
    return tile


def find_path(ship_map, start_world, goal_world,allow_closed_doors=False,diagonal=False,tile_cost=None):
    """A* over the tile grid. Returns a list of world-space waypoints
    (tile centers), or an empty list if no path exists."""
    start = world_to_tile(*start_world)
    goal = _nearest_floor_tile(ship_map, world_to_tile(*goal_world),allow_closed_doors=allow_closed_doors)

    if ship_map.is_path_wall(*start,allow_closed_doors=allow_closed_doors):
        start = _nearest_floor_tile(ship_map, start,allow_closed_doors=allow_closed_doors)

    if start == goal:
        return [tile_to_world_center(*goal)]

    open_heap = [(0, start)]
    came_from = {}
    g_score = {start: 0}
    visited = set()

    while open_heap:
        _, current = heapq.heappop(open_heap)
        if current in visited:
            continue
        visited.add(current)

        if current == goal:
            return _reconstruct(came_from, current)

        cx, cy = current
        directions=((1,0),(-1,0),(0,1),(0,-1))+(((1,1),(1,-1),(-1,1),(-1,-1)) if diagonal else ())
        for dx, dy in directions:
            neighbor = (cx + dx, cy + dy)
            if ship_map.is_path_wall(*neighbor,allow_closed_doors=allow_closed_doors):
                continue
            if dx and dy and (ship_map.is_path_wall(cx+dx,cy,allow_closed_doors=allow_closed_doors) or
                              ship_map.is_path_wall(cx,cy+dy,allow_closed_doors=allow_closed_doors)):
                continue
            door=ship_map.doors.at_tile(*neighbor) if allow_closed_doors else None
            tentative = g_score[current] + math.hypot(dx,dy) + (12 if door and door.closed else 0) + (max(0,tile_cost(neighbor)) if tile_cost else 0)
            if tentative < g_score.get(neighbor, 1 << 30):
                g_score[neighbor] = tentative
                came_from[neighbor] = current
                priority = tentative + _heuristic(neighbor, goal, diagonal)
                heapq.heappush(open_heap, (priority, neighbor))

    return []  # unreachable


def _reconstruct(came_from, current):
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return [tile_to_world_center(tx, ty) for tx, ty in path]


def segment_clear(ship_map,start,end,radius):
    """Sweep the actor footprint, including corners and closed bulkheads."""
    dx,dy=end[0]-start[0],end[1]-start[1]
    samples=max(1,math.ceil(math.hypot(dx,dy)/3))
    return all(not ship_map.is_blocked_circle(start[0]+dx*i/samples,start[1]+dy*i/samples,radius)
               for i in range(samples+1))


def smooth_path(ship_map,start,path,radius):
    """Remove grid bends only when a whole actor can physically pass."""
    result=[];anchor=start;index=0
    while index<len(path):
        chosen=index
        # A solid doorway must remain a waypoint so the hunter can breach it.
        for j in range(index,len(path)):
            if segment_clear(ship_map,anchor,path[j],radius):chosen=j
        result.append(path[chosen]);anchor=path[chosen];index=chosen+1
    return result
