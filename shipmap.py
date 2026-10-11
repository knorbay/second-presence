"""
Hand-authored spaceship layout.

The map is built from a list of rectangular ROOMS plus a list of CORRIDOR
rectangles that connect them. Corridors deliberately form loops (not a
simple ring) so there are usually 2+ routes into a task room, plus a
couple of narrow "service" shortcuts and two true dead ends.

Coordinates are in TILE units: rect = (x, y, w, h) covering tiles
[x, x+w) x [y, y+h).
"""

import collections
import pygame
from config import TILE, COLS, ROWS, ALIEN_RADIUS
from bulkheads import Bulkheads

WALL = 1
FLOOR = 0


class Room:
    def __init__(self, name, rect, task=None, dead_end=False):
        self.name = name
        self.rect = rect  # (x, y, w, h) in tiles
        self.task = task  # task-system key, or None
        self.dead_end = dead_end

    @property
    def tile_center(self):
        x, y, w, h = self.rect
        return (x + w // 2, y + h // 2)

    @property
    def world_center(self):
        tx, ty = self.tile_center
        return pygame.math.Vector2(tx * TILE + TILE / 2, ty * TILE + TILE / 2)

    def contains_tile(self, tx, ty):
        x, y, w, h = self.rect
        return x <= tx < x + w and y <= ty < y + h

    def contains_world(self, wx, wy):
        return self.contains_tile(int(wx // TILE), int(wy // TILE))


# ---------------------------------------------------------------- rooms ----
ROOMS = [
    Room("Quarters", (3, 32, 8, 6)),
    Room("Oxygen", (4, 3, 9, 7), task="Oxygen"),
    Room("Communications", (26, 14, 9, 6), task="Communications"),
    Room("Power", (30, 31, 10, 7), task="Power"),
    Room("Reactor", (48, 3, 10, 7), task="Reactor"),
    Room("Cargo Bay", (63, 14, 12, 6), task="Cargo Bay"),
    Room("Cooling", (88, 3, 10, 7), task="Cooling"),
    Room("Navigation", (68, 31, 9, 6), task="Navigation"),
    Room("Hangar", (88, 29, 13, 10)),
    Room("Medbay", (16, 39, 7, 4), dead_end=True),
    Room("Storage", (48, 32, 8, 6), task="Storage"),
    Room("Airlock", (93, 14, 6, 5), task="Airlock", dead_end=True),
    Room("Observation", (68, 4, 7, 5)),
]
CORRIDORS = [
    # Broad stretches joined by offset turns; no uninterrupted end-to-end sightline.
    (7, 21, 18, 6),      # western approach
    (22, 21, 6, 10),     # turn down around the maintenance bulkhead
    (22, 27, 17, 5),     # lower maintenance gallery
    (35, 21, 5, 11),     # return to the central junction
    (39, 21, 21, 6),     # broad engineering hall
    (57, 17, 6, 10),     # northern cargo approach
    (57, 17, 17, 4),     # cargo becomes an open junction
    (70, 20, 6, 11),     # drop to the navigation branch
    (73, 24, 12, 5),     # east gallery
    (82, 21, 15, 6),     # final stretch towards cooling / hangar
    (26, 19, 6, 4),      # communications side entrance
    (12, 19, 5, 3),      # recessed vent bay
    (43, 26, 6, 3),      # engineering alcove
    (86, 26, 5, 3),      # hangar-side loading recess
    (7, 10, 3, 22),       # oxygen to quarters
    (29, 20, 3, 3),
    (34, 25, 3, 6),
    (52, 10, 3, 12),
    (67, 20, 3, 3),
    (92, 10, 3, 12),
    (71, 25, 3, 6),
    (93, 25, 3, 4),
    (13, 6, 35, 2),       # upper engineering loop
    (58, 6, 30, 2),
    (11, 35, 19, 2),      # lower accommodation loop
    (40, 35, 28, 2),
    (77, 34, 11, 2),
    (20, 8, 2, 27),       # west service route
    (81, 8, 2, 26),       # east service route
    (18, 37, 2, 2),       # medbay spur
]
SPAWN_TILE = (7, 35)


class ShipMap:
    def __init__(self):
        self.grid = [[WALL for _ in range(COLS)] for _ in range(ROWS)]
        self.rooms = ROOMS
        self.corridors = CORRIDORS
        self._carve_all()
        self.task_rooms = {r.task: r for r in self.rooms if r.task}
        self.sealed_tiles = set()
        self.lockers = {}
        self.geometry_revision=0
        self.doors=Bulkheads(self)

    # -- construction --------------------------------------------------
    def _carve_rect(self, rect):
        x, y, w, h = rect
        for ty in range(max(y, 0), min(y + h, ROWS)):
            for tx in range(max(x, 0), min(x + w, COLS)):
                self.grid[ty][tx] = FLOOR

    def _carve_all(self):
        for room in self.rooms:
            self._carve_rect(room.rect)
        for corridor in self.corridors:
            self._carve_rect(corridor)

    def set_day(self, day):
        """Bulkheads close shortcuts, while every room remains reachable."""
        self.grid = [[WALL for _ in range(COLS)] for _ in range(ROWS)]
        self._carve_all()
        self.sealed_tiles = set()
        if day >= 4:
            self.sealed_tiles.update((x, 18) for x in (20, 21))
        if day >= 6:
            self.sealed_tiles.update((x, 18) for x in (81, 82))
        for x, y in self.sealed_tiles:
            self.grid[y][x] = WALL
        self.doors.reset(day)
        self.geometry_revision+=1

    # -- queries ---------------------------------------------------------
    def is_wall_tile(self, tx, ty):
        if tx < 0 or ty < 0 or tx >= COLS or ty >= ROWS:
            return True
        return self.grid[ty][tx] == WALL

    def is_wall_world(self, wx, wy):
        return self.is_wall_tile(int(wx // TILE), int(wy // TILE))

    def is_path_wall(self,tx,ty,allow_closed_doors=False):
        if allow_closed_doors:
            door=self.doors.at_tile(tx,ty)
            if door and door.closed:return False
        return self.is_wall_tile(tx,ty)

    def is_blocked_circle(self, wx, wy, radius=ALIEN_RADIUS):
        """Exact circle / tile overlap, including corners."""
        import math
        for ty in range(math.floor((wy-radius)/TILE), math.floor((wy+radius)/TILE)+1):
            for tx in range(math.floor((wx-radius)/TILE), math.floor((wx+radius)/TILE)+1):
                if self.is_wall_tile(tx, ty):
                    nx = max(tx*TILE, min(wx, (tx+1)*TILE))
                    ny = max(ty*TILE, min(wy, (ty+1)*TILE))
                    if (wx-nx)**2 + (wy-ny)**2 < radius**2:
                        return True
        return False

    def room_at_world(self, wx, wy):
        tx, ty = int(wx // TILE), int(wy // TILE)
        for room in self.rooms:
            if room.contains_tile(tx, ty):
                return room
        return None

    def room_by_name(self, name):
        for r in self.rooms:
            if r.name == name:
                return r
        return None

    def line_of_sight(self, x0, y0, x1, y1, step=6):
        """True if nothing solid lies between the two world points."""
        dx, dy = x1 - x0, y1 - y0
        dist = (dx ** 2 + dy ** 2) ** 0.5
        if dist == 0:
            return True
        steps = max(1, int(dist // step))
        for i in range(steps + 1):
            t = i / steps
            x = x0 + dx * t
            y = y0 + dy * t
            if self.is_wall_world(x, y):
                return False
        return True

    def connected_component_size(self, start_tile):
        """BFS flood fill - used by the self-test to guarantee full connectivity."""
        sx, sy = start_tile
        if self.is_wall_tile(sx, sy):
            return 0
        seen = {(sx, sy)}
        q = collections.deque([(sx, sy)])
        while q:
            cx, cy = q.popleft()
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if (nx, ny) not in seen and not self.is_wall_tile(nx, ny):
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return len(seen)

    def total_floor_tiles(self):
        return sum(row.count(FLOOR) for row in self.grid)

    # -- rendering ---------------------------------------------------------
    def render(self, surface):
        from config import COL_BG, COL_WALL, COL_FLOOR
        surface.fill(COL_BG)
        for ty in range(ROWS):
            row = self.grid[ty]
            for tx in range(COLS):
                rect = pygame.Rect(tx * TILE, ty * TILE, TILE, TILE)
                if row[tx] == WALL:
                    pygame.draw.rect(surface, COL_WALL, rect)
                else:
                    pygame.draw.rect(surface, COL_FLOOR, rect)
