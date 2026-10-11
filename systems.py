"""
Systems that sit between the player and the alien:

NoiseSystem     - turns player actions into noise events with an
                  approximate (never exact) perceived position for
                  whoever hears them.
TaskSystem      - the room-specific maintenance tasks + the Day 8 escape sequence.
BehaviorTracker - the "learning" system. Purely statistical / weighted
                  counters, persisted across days. No ML, no magic
                  access to player state - it only ever sees what
                  already happened.
DAY_PARAMS      - per-day tuning knobs that implement the Day 1-8
                  progression described in the design.
"""

import collections
import math
import random

import config as C
from maintenance import work_for_day, job_title, active_rooms, recipe_for_day, prerequisites
from shift_plan import make_plan,PLAN_VERSION,new_campaign_seed


# --------------------------------------------------------------------- day
# parameters, data-driven so the F3 debug overlay can show exactly what
# is active and nothing is happening "invisibly"
DAY_PARAMS = {
    1: dict(alien_active=False, hearing_error=1.6, vision_range=C.ALIEN_VIEW_RANGE * 0.7,
            suspicion_mult=0.4, memory_bias=0.0, use_hiding_memory=False,
            sabotage=False, search_time_mult=0.7, escape_bias=0.0,
            label="Routine. Learn the ship."),
    2: dict(alien_active=False, hearing_error=1.5, vision_range=C.ALIEN_VIEW_RANGE * 0.8,
            suspicion_mult=0.55, memory_bias=0.0, use_hiding_memory=False,
            sabotage=False, search_time_mult=0.8, escape_bias=0.0,
            label="Disturbance. Sounds inside the hull."),
    3: dict(alien_active=True, hearing_error=1.3, vision_range=C.ALIEN_VIEW_RANGE,
            suspicion_mult=0.8, memory_bias=0.0, use_hiding_memory=False,
            sabotage=False, search_time_mult=1.0, escape_bias=0.0,
            label="It hunts. See / hear / chase / search."),
    4: dict(alien_active=True, hearing_error=1.2, vision_range=C.ALIEN_VIEW_RANGE,
            suspicion_mult=0.9, memory_bias=0.45, use_hiding_memory=False,
            sabotage=False, search_time_mult=1.0, escape_bias=0.0,
            label="Memory. It recalls your routines."),
    5: dict(alien_active=True, hearing_error=0.9, vision_range=C.ALIEN_VIEW_RANGE,
            suspicion_mult=1.0, memory_bias=0.6, use_hiding_memory=True,
            sabotage=False, search_time_mult=1.2, escape_bias=0.15,
            label="Better tracking. It knows your hiding spots."),
    6: dict(alien_active=True, hearing_error=0.8, vision_range=C.ALIEN_VIEW_RANGE,
            suspicion_mult=1.05, memory_bias=0.7, use_hiding_memory=True,
            sabotage=True, search_time_mult=1.2, escape_bias=0.25,
            label="Deception. Not every alarm is real."),
    7: dict(alien_active=True, hearing_error=0.7, vision_range=C.ALIEN_VIEW_RANGE * 1.05,
            suspicion_mult=1.1, memory_bias=0.85, use_hiding_memory=True,
            sabotage=True, search_time_mult=1.35, escape_bias=0.4,
            label="It knows you."),
    8: dict(alien_active=True, hearing_error=0.6, vision_range=C.ALIEN_VIEW_RANGE * 1.1,
            suspicion_mult=1.15, memory_bias=1.0, use_hiding_memory=True,
            sabotage=True, search_time_mult=1.4, escape_bias=0.5,
            label="Escape sequence."),
}


def hunter_awake(day, day_time):
    """Day two builds unease; the first hunt has a quiet opening on day three."""
    return day >= 3 and day_time >= (65.0 if day == 3 else 12.0)


def get_day_params(day):
    return DAY_PARAMS[max(1, min(C.NUM_DAYS, day))]


# ------------------------------------------------------------------ noise
NoiseEvent = collections.namedtuple(
    "NoiseEvent", ["pos", "radius", "strength", "kind"]
)


class NoiseSystem:
    """Noise events live for exactly one frame; the alien (or anything
    else listening) polls `events` right after `emit`/`update`."""

    def __init__(self):
        self.events = []

    def clear(self):
        self.events = []

    def emit(self, pos, radius, strength, kind):
        self.events.append(NoiseEvent(pos=pygame_vec(pos), radius=radius,
                                       strength=strength, kind=kind))

    def perceived_position(self, event, listener_pos, error_scale):
        """Turn a real noise position into an approximate one. Error grows
        with distance from the listener and shrinks as the alien's
        hearing improves on later days (error_scale < 1)."""
        dx = event.pos.x - listener_pos.x
        dy = event.pos.y - listener_pos.y
        dist = math.hypot(dx, dy) or 1.0
        # up to ~35% of the distance as positional error at max range,
        # scaled by how "sharp" the alien's hearing currently is
        max_error = min(dist * 0.35, event.radius * 0.5) * error_scale
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, max_error)
        return pygame_vec((event.pos.x + math.cos(angle) * r,
                            event.pos.y + math.sin(angle) * r))


def pygame_vec(v):
    import pygame
    if isinstance(v, pygame.math.Vector2):
        return v.copy()
    return pygame.math.Vector2(v[0], v[1])


# ------------------------------------------------------------------- task
class Task:
    def __init__(self,name,room,day=1,operations=None,requires=None):
        self.name=name;self.room=room
        self.operations=tuple(operations) if operations is not None else recipe_for_day(day,name)
        self.step=0;self.revision=0
        self.requires=tuple(requires) if requires is not None else prerequisites(name)
        self.done=False;self.completed_at=None
        self.sessions={}

    @property
    def operation(self):return self.operations[min(self.step,len(self.operations)-1)]

    @property
    def title(self):return job_title(self.name,self.operation)

    @property
    def progress(self):return 1 if self.done else self.step/len(self.operations)

    def reopen(self):
        self.done=False;self.completed_at=None;self.step=0;self.revision+=1;self.sessions.clear()


class TaskSystem:
    def __init__(self, ship_map, campaign_seed=0):
        self.ship_map = ship_map
        self.campaign_seed=campaign_seed
        self.plan_version=PLAN_VERSION if campaign_seed else 0
        self.tasks = {}
        self.reset_day()
        self.day8_step = 0  # index into C.DAY8_SEQUENCE
        self.day8_complete = False

    def reset_day(self, day=1):
        self.day = day
        if self.campaign_seed:
            self.incident,plan=make_plan(self.campaign_seed,day)
            self.tasks={name:Task(name,self.ship_map.task_rooms[name],day,operations,requires)
                        for name,operations,requires in plan}
        else:
            self.incident=None
            self.tasks={name:Task(name,self.ship_map.task_rooms[name],day) for name in active_rooms(day)}
        self.day8_step = 0
        self.day8_complete = False
        self.first_completion_order = []

    def new_campaign(self):
        self.campaign_seed=new_campaign_seed(self.campaign_seed)
        self.plan_version=PLAN_VERSION

    def panel(self,name,kind,revision=0):
        from maintenance import PanelWork
        return PanelWork(name,kind,self.day,revision,self.campaign_seed)

    def all_standard_tasks_done(self):
        return all(t.done for t in self.tasks.values())

    def blocked_by(self,name):
        ancestors=set()
        def visit(current):
            for parent in self.tasks[current].requires:
                if parent in self.tasks and parent not in ancestors:
                    ancestors.add(parent);visit(parent)
        visit(name)
        return [n for n in self.tasks if n in ancestors and not self.tasks[n].done]

    def available(self,name):return name in self.tasks and not self.tasks[name].done and not self.blocked_by(name)

    def advance_task(self,name,day_time):
        if not self.available(name):return False
        t=self.tasks[name];t.step+=1
        if t.step>=len(t.operations):return self.complete_task(name,day_time)
        return False

    def complete_task(self,name,day_time):
        if not self.available(name):return False
        t=self.tasks[name];t.step=len(t.operations);t.done=True;t.completed_at=day_time
        if name not in self.first_completion_order:self.first_completion_order.append(name)
        return True

    def completion_order(self):
        done = [t for t in self.tasks.values() if t.done]
        done.sort(key=lambda t: t.completed_at)
        return [t.name for t in done]

    # -- day 8 special sequence ------------------------------------------
    def day8_current_target(self):
        if self.day8_step >= len(C.DAY8_SEQUENCE):
            return None
        return C.DAY8_SEQUENCE[self.day8_step]

    def day8_advance(self, room_name):
        target = self.day8_current_target()
        if target is not None and room_name == target:
            self.day8_step += 1
            if self.day8_step >= len(C.DAY8_SEQUENCE):
                self.day8_complete = True
            return True
        return False


# ------------------------------------------------------------ behavior AI
class BehaviorTracker:
    """Weighted-statistics learning system. Everything here is derived
    from things the player actually did on previous days - never from
    the player's current live position."""

    def __init__(self):
        self.first_task_counts = collections.Counter()
        self.task_order_history = []          # list of lists (per day)
        self.room_visit_counts = collections.Counter()
        self.route_counts = collections.Counter()  # (roomA, roomB) edges
        self.sprint_count = 0
        self.hiding_counts = collections.Counter()   # rooms alien lost player in
        self.escape_direction_counts = collections.Counter()  # (room, dir) -> n

        self._last_room_this_day = None
        self._visited_rooms_this_day = set()
        self._pending_routes = collections.Counter()
        self._pending_hiding = collections.Counter()
        self._pending_escape = collections.Counter()

    # -- called during play -------------------------------------------
    def on_room_entered(self, room):
        if room is None:
            return
        self.room_visit_counts[room.name] += 1
        self._visited_rooms_this_day.add(room.name)
        if self._last_room_this_day and self._last_room_this_day != room.name:
            self._pending_routes[(self._last_room_this_day, room.name)] += 1
        self._last_room_this_day = room.name

    def on_sprint_tick(self):
        self.sprint_count += 1

    def on_player_lost(self, room):
        """Called when the alien's SEARCH_AREA ends without success -
        the room the player was last confirmed near becomes a slightly
        more likely 'hiding spot' in the statistical model."""
        if room:
            self._pending_hiding[room.name] += 1

    def on_chase_flee_direction(self, room, direction_label):
        if room:
            self._pending_escape[(room.name, direction_label)] += 1

    # -- called at day boundaries ---------------------------------------
    def start_day(self):
        self._last_room_this_day = None
        self._visited_rooms_this_day = set()
        self._pending_routes = collections.Counter()
        self._pending_hiding = collections.Counter()
        self._pending_escape = collections.Counter()

    def end_day(self, task_system):
        self.route_counts.update(self._pending_routes)
        self.hiding_counts.update(self._pending_hiding)
        self.escape_direction_counts.update(self._pending_escape)
        order = list(task_system.first_completion_order)
        self.task_order_history.append(order)
        if order:
            self.first_task_counts[order[0]] += 1

    # -- predictions used by the alien -----------------------------------
    def predicted_first_task(self):
        """Returns dict {task_name: probability} - purely statistical,
        can be shown directly in the debug overlay."""
        if not self.first_task_counts:
            return {name: 1.0 / len(C.TASK_ROOM_NAMES) for name in C.TASK_ROOM_NAMES}
        total = sum(self.first_task_counts.values())
        probs = {name: self.first_task_counts.get(name, 0) / total
                 for name in C.TASK_ROOM_NAMES}
        return probs

    def most_likely_first_task_room(self):
        probs = self.predicted_first_task()
        return max(probs, key=probs.get)

    def next_task_after(self, task_name):
        """Rank transitions from committed, prior-day task orders only."""
        counts = collections.Counter()
        for order in self.task_order_history:
            for a, b in zip(order, order[1:]):
                if a == task_name:
                    counts[b] += 1
        return [name for name, _ in counts.most_common()]

    def top_hiding_rooms(self, n=3):
        return [name for name, _ in self.hiding_counts.most_common(n)]

    def preferred_escape_direction(self, room_name):
        candidates = {d: c for (r, d), c in self.escape_direction_counts.items() if r == room_name}
        if not candidates:
            return None
        return max(candidates, key=candidates.get)

    def frequent_routes_from(self, room_name, n=3):
        candidates = {b: c for (a, b), c in self.route_counts.items() if a == room_name}
        ranked = sorted(candidates.items(), key=lambda kv: -kv[1])
        return [name for name, _ in ranked[:n]]
