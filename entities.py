"""
Player and Alien.

The Alien class is written so that every piece of information it acts on
traces back to something it legitimately perceived:

  - self.last_seen_position / self.last_seen_time  <- only set inside
    _update_vision(), which itself only fires when fov.can_see_point()
    (a cone + line-of-sight check) returns True.
  - self.last_heard_position                        <- only set inside
    _update_hearing(), from an *approximated* noise position, never the
    real player position.
  - self.current_target                              <- always derived
    from the above two, or from statistical predictions in
    BehaviorTracker (which only reflect *past* days), never from
    player.pos directly.

`player.pos` is passed into Alien.update() only so the vision/hearing
checks themselves have something to test against - the state machine
below never reads it outside of those two functions.
"""

import math
import random

import pygame

import config as C
import fov
from pathfinding import find_path, smooth_path, segment_clear, world_to_tile


# --------------------------------------------------------------- player
class Player:
    def __init__(self, ship_map, spawn_world):
        self.ship_map = ship_map
        self.pos = pygame.math.Vector2(spawn_world)
        self.radius = C.PLAYER_RADIUS
        self.stamina = C.STAMINA_MAX
        self.sprinting = False
        self.exhausted = False
        self.crouching = False
        self.hidden = False
        self.hidden_spot = None
        self.moving = False
        self.facing = pygame.math.Vector2(0, -1)

        self.interacting = False
        self.interact_task = None
        self.interact_progress = 0.0

        self.current_room = ship_map.room_at_world(self.pos.x, self.pos.y)

        self._noise_timer = 0.0
        self.caught = False

    def update(self, dt, keys, noise_system, interactables, on_complete, behavior_tracker):
        """Movement and footsteps; the game loop owns active panel work."""
        if self.caught:
            return
        maximum = C.STAMINA_MAX
        regen = C.STAMINA_REGEN
        if self.hidden:
            self.moving = self.sprinting = self.interacting = False
            self.interact_progress = 0.0
            self.stamina = min(maximum, self.stamina + regen * dt)
            return

        move = pygame.math.Vector2(0, 0)
        if keys.get("w"):
            move.y -= 1
        if keys.get("s"):
            move.y += 1
        if keys.get("a"):
            move.x -= 1
        if keys.get("d"):
            move.x += 1

        self.moving = move.length_squared() > 0
        if self.moving:
            move = move.normalize()
            self.facing = pygame.math.Vector2(move)

        self.crouching = keys.get("ctrl", False)
        want_sprint = keys.get("shift", False) and self.moving and not self.crouching
        if self.stamina <= C.STAMINA_MIN_TO_SPRINT:
            self.exhausted = True
        elif self.stamina >= 25:
            self.exhausted = False
        can_sprint = not self.exhausted
        self.sprinting = want_sprint and can_sprint

        # PanelWork in the game loop owns maintenance input; E does not auto-repair.
        self.interacting = False
        self.interact_task = None
        self.interact_progress = 0.0
        speed = C.SPRINT_SPEED if self.sprinting else (C.CROUCH_SPEED if self.crouching else C.WALK_SPEED)

        previous_pos=self.pos.copy()
        if speed > 0:
            self._move_with_collision(move * speed * dt)
        self.moving=self.pos.distance_squared_to(previous_pos)>.001
        if not self.moving:self.sprinting=False
        if self.sprinting:
            self.stamina = max(0.0, self.stamina - C.STAMINA_DRAIN * dt)
            behavior_tracker.on_sprint_tick()
        else:
            self.stamina = min(maximum, self.stamina + regen * dt)

        # room-change bookkeeping (ground-truth analytics, not alien knowledge)
        room = self.ship_map.room_at_world(self.pos.x, self.pos.y)
        if room is not self.current_room:
            self.current_room = room
            behavior_tracker.on_room_entered(room)

        self._emit_noise(dt, noise_system)

    def _nearby_interactable(self, interactables):
        best, best_d = None, 1e9
        for item in interactables:
            if item.get("done"):
                continue
            d = self.pos.distance_to(item["point"])
            if (d < 60 and d < best_d and self.ship_map.line_of_sight(
                    self.pos.x, self.pos.y, *item["point"])):
                best, best_d = item, d
        return best

    def _move_with_collision(self, delta):
        ship_map = self.ship_map
        # move on X then Y independently so the player slides along walls
        new_x = self.pos.x + delta.x
        if not ship_map.is_blocked_circle(new_x, self.pos.y, self.radius):
            self.pos.x = new_x
        new_y = self.pos.y + delta.y
        if not ship_map.is_blocked_circle(self.pos.x, new_y, self.radius):
            self.pos.y = new_y

    def _emit_noise(self, dt, noise_system):
        self._noise_timer -= dt
        if self.interacting:
            if self._noise_timer <= 0:
                noise_system.emit(self.pos, C.NOISE_RADIUS_REPAIR,
                                   C.NOISE_STRENGTH_REPAIR, "repair")
                self._noise_timer = 0.45
        elif self.moving:
            if self.sprinting:
                if self._noise_timer <= 0:
                    noise_system.emit(self.pos, C.NOISE_RADIUS_RUN,
                                       C.NOISE_STRENGTH_RUN, "run")
                    self._noise_timer = 0.28
            else:
                if self._noise_timer <= 0:
                    noise_system.emit(self.pos,
                                       C.NOISE_RADIUS_CROUCH if self.crouching else C.NOISE_RADIUS_WALK,
                                       2 if self.crouching else C.NOISE_STRENGTH_WALK,
                                       "crouch" if self.crouching else "walk")
                    self._noise_timer = 0.5
        else:
            self._noise_timer = 0.0


# ---------------------------------------------------------------- alien
STATE_DORMANT = "DORMANT"          # only used on Day 1
STATE_WANDER = "WANDER"
STATE_SUSPICIOUS = "SUSPICIOUS"
STATE_INVESTIGATE = "INVESTIGATE"
STATE_CHASE = "CHASE"
STATE_SEARCH_LAST_SEEN = "SEARCH_LAST_SEEN"
STATE_SEARCH_AREA = "SEARCH_AREA"


class Alien:
    def __init__(self, ship_map, spawn_world):
        self.ship_map = ship_map
        self.pos = pygame.math.Vector2(spawn_world)
        self.facing_angle = 0.0
        self.state = STATE_WANDER

        # --- memory (only ever written by _update_vision / _update_hearing
        # or by state-transition code that derives from them) ---
        self.last_seen_position = None
        self.last_heard_position = None
        self.last_seen_time = -999.0
        self.suspicion = 0.0
        self.current_target = None
        self.search_area = []
        self._search_index = 0

        self.path = []
        self._path_target_key = None
        self._repath_timer = 0.0
        self._step_noise_timer = 0.0
        self.moved_this_frame = False
        self.attacking_door=None
        self._path_geometry_revision=-1

        self._suspicious_timer = 0.0
        self._search_timer = 0.0
        self._waypoint_pause = 0.0
        self._los_grace_timer = 0.0
        self._chase_start_room = None

        self._wander_target_room = None
        self.observed_hiding_spot = None
        self.inspect_spot = None
        self.last_seen_direction = pygame.Vector2()
        self.last_seen_velocity = pygame.Vector2()
        self._investigate_timer = 0.0
        self._previous_seen_pos = None
        self._previous_seen_time = -999
        self._last_confirmed_room = None
        self._recent_patrol = []
        self._visited_tiles = {}
        self._route_seed = random.randrange(100000)
        self._scan_angle = 0.0
        self._scan_time = 0.0
        self.intent = "patrol"
        self._patrol_pause = 4.0
        self._frame_dt = 0.0
        self._day_time = 0
        self._search_origin = None
        self._heard_recently = False
        self.motion_clock=0.0
        self.stride_offset=random.uniform(0,math.tau)
        self.gait_scale=1.0

        # debug-visible snapshot, refreshed every update()
        self.debug = {}

    # ------------------------------------------------------------ update
    def update(self, dt, player, ship_map, noise_system, behavior_tracker,
               day, day_time, sim_time):
        params = _day_params(day)
        self._frame_dt = dt
        self._day_time = day_time
        self.attacking_door=None
        if self.inspect_spot:
            point = ship_map.lockers.get(self.inspect_spot)
            if point is None or self.pos.distance_to(point)>55:
                self.inspect_spot = None

        from systems import hunter_awake
        if not params["alien_active"] or not hunter_awake(day, day_time):
            self.state = STATE_DORMANT
            self.moved_this_frame = False
            self.suspicion = 0.0
            self.path = []
            self.current_target = None
            self.debug = {"state": self.state, "note": "inactive this day"}
            return

        if self.state == STATE_DORMANT:
            self.state = STATE_WANDER

        visible, dist, centrality = self._update_vision(player, ship_map, params, sim_time, dt)
        heard_event = self._update_hearing(noise_system, ship_map, behavior_tracker, params)

        self.suspicion = max(0.0, self.suspicion - C.SUSPICION_DECAY_PER_SEC * dt)

        self._run_state_machine(dt, player, ship_map, behavior_tracker, params,
                                 visible, heard_event, day, sim_time)

        self.motion_clock+=dt
        self.gait_scale=self.movement_cadence()

        self.moved_this_frame = False
        self._follow_path(dt, params)
        self._emit_footsteps(dt, noise_system)

        self.debug = dict(
            state=self.state,
            suspicion=round(self.suspicion, 1),
            last_seen_position=_v(self.last_seen_position),
            last_heard_position=_v(self.last_heard_position),
            current_target=_v(self.current_target),
            search_area=[_v(p) for p in self.search_area],
            facing_deg=round(math.degrees(self.facing_angle), 1),
            vision_range=round(params["vision_range"], 1),
            fov_deg=C.ALIEN_FOV_ANGLE,
            path_len=len(self.path),
            intent=self.intent,
            motion_prediction=_v(self.last_seen_direction),
            inspecting=self.inspect_spot,
        )

    # ------------------------------------------------------------ vision
    def _update_vision(self, player, ship_map, params, sim_time, dt):
        if player.hidden:
            # A locker is checked only if entry was witnessed in line of sight.
            if self.ship_map.line_of_sight(
                    *self.pos, *player.pos) and self.pos.distance_to(player.pos) <= 35:
                if player.hidden_spot in (self.observed_hiding_spot, self.inspect_spot):
                    self.last_seen_position = player.pos.copy()
                    self.last_seen_time = sim_time
                    self.suspicion = C.SUSPICION_MAX
                    return True, self.pos.distance_to(player.pos), 1.0
            return False, float("inf"), 0.0
        visible, dist, centrality = fov.can_see_point(
            ship_map, (self.pos.x, self.pos.y), self.facing_angle,
            (player.pos.x, player.pos.y), C.ALIEN_FOV_ANGLE,
            C.ALIEN_VIEW_RANGE_CHASE if self.state==STATE_CHASE else params["vision_range"])

        # Contact range is physical awareness, not sight through walls or lockers.
        if not visible and not player.hidden and self.pos.distance_to(player.pos)<32 and ship_map.line_of_sight(*self.pos,*player.pos):
            visible=True;dist=self.pos.distance_to(player.pos);centrality=1.0
        if visible:
            if self._previous_seen_pos is not None and 0 < sim_time-self._previous_seen_time <= .3:
                displacement = player.pos-self._previous_seen_pos
                if displacement.length_squared() > .2:
                    self.last_seen_direction = displacement.normalize()
                    self.last_seen_velocity=displacement/(sim_time-self._previous_seen_time)
                    if self.last_seen_velocity.length()>C.SPRINT_SPEED:self.last_seen_velocity.scale_to_length(C.SPRINT_SPEED)
                else:self.last_seen_velocity=pygame.Vector2()
            else:self.last_seen_velocity=pygame.Vector2()
            self._previous_seen_pos = player.pos.copy()
            self._previous_seen_time = sim_time
            self._last_confirmed_room = ship_map.room_at_world(*player.pos)
            if self.state in (STATE_SEARCH_LAST_SEEN, STATE_SEARCH_AREA) and sim_time-self.last_seen_time<8:
                self.suspicion = max(self.suspicion,C.SUSPICION_CHASE_THRESHOLD)
            self.last_seen_position = pygame.math.Vector2(player.pos)
            self.last_seen_time = sim_time
            # closer + more centered contact raises suspicion faster (per second);
            # a one-frame edge-of-cone glimpse barely moves the needle, sustained
            # dead-ahead contact at close range crosses the CHASE threshold in ~1-2s
            rate_per_sec = (0.35 + 0.65 * centrality) * (1.0 - min(dist, 400) / 500.0)
            rate_per_sec = max(0.15, rate_per_sec) * 72.0 * params["suspicion_mult"]
            self.suspicion = min(C.SUSPICION_MAX, self.suspicion + rate_per_sec * dt)
            self._los_grace_timer = C.CHASE_LOS_GRACE
        return visible, dist, centrality

    # ------------------------------------------------------------ hearing
    def _update_hearing(self, noise_system, ship_map, behavior_tracker, params):
        heard = None
        strongest = 0.0
        for event in noise_system.events:
            if event.kind in ("alien_step","alien_door"):
                continue
            distance = self.pos.distance_to(event.pos)
            # Walls muffle sound rather than granting exact visual knowledge.
            acoustic_distance = distance * (1.0 if ship_map.line_of_sight(*self.pos,*event.pos) else 1.35)
            if acoustic_distance <= event.radius:
                falloff = max(.15,1-acoustic_distance/event.radius)
                gain = event.strength*falloff*params["suspicion_mult"]
                self.suspicion = min(C.SUSPICION_MAX,self.suspicion+gain)
                if gain>strongest:
                    strongest=gain
                    heard=noise_system.perceived_position(event,self.pos,params["hearing_error"])
        if heard is not None:
            if self.last_heard_position is not None and heard.distance_to(self.last_heard_position)<160:
                heard = self.last_heard_position.lerp(heard,.45)
            self.last_heard_position=heard.copy()
        self._heard_recently = strongest>=5
        return heard

    # -------------------------------------------------------- state fsm
    def _run_state_machine(self, dt, player, ship_map, behavior_tracker, params,
                            visible, heard_event, day, sim_time):
        if self.state == STATE_WANDER:
            if self.suspicion >= C.SUSPICION_CHASE_THRESHOLD and visible:
                self._enter_chase(player)
            elif heard_event is not None and self._heard_recently:
                self._enter_investigate()
            elif self.suspicion >= C.SUSPICION_SUSPICIOUS_THRESHOLD:
                self._enter_suspicious()
            else:
                self._do_wander(ship_map, behavior_tracker, params, day)

        elif self.state == STATE_SUSPICIOUS:
            self._suspicious_timer -= dt
            self.current_target = None
            clue = self.last_seen_position or self.last_heard_position
            if clue is not None:
                direction = clue-self.pos
                wanted = math.atan2(direction.y,direction.x)
                self.facing_angle += fov.angle_diff(wanted,self.facing_angle)*min(1,dt*5)
            if visible and self.suspicion >= C.SUSPICION_CHASE_THRESHOLD:
                self._enter_chase(player)
            elif self.suspicion >= C.SUSPICION_INVESTIGATE_THRESHOLD:
                self._enter_investigate()
            elif self._suspicious_timer <= 0:
                if self.suspicion >= C.SUSPICION_INVESTIGATE_THRESHOLD:
                    self._enter_investigate()
                elif self.last_seen_position is not None or self.last_heard_position is not None:
                    self._enter_investigate()
                else:
                    self.state = STATE_WANDER

        elif self.state == STATE_INVESTIGATE:
            if visible and self.suspicion >= C.SUSPICION_CHASE_THRESHOLD:
                self._enter_chase(player)
                return
            if visible:
                self.current_target = self.last_seen_position.copy()
            elif heard_event is not None and self._heard_recently:
                target=self._reachable_target(heard_event)
                if self.current_target is None or target.distance_to(self.current_target)>36:
                    self.current_target=target;self.path=[];self._investigate_timer=max(self._investigate_timer,10)
            self._investigate_timer-=dt
            if self._arrived_at(self.current_target) or self._investigate_timer<=0:
                self._begin_search_area(ship_map, behavior_tracker, params, origin=self.current_target)

        elif self.state == STATE_CHASE:
            if visible:
                self.current_target = self.last_seen_position.copy()
                # Lead comes only from observed velocity and is clipped by geometry.
                lead=self.last_seen_position+self.last_seen_velocity*.18
                if ship_map.line_of_sight(*self.last_seen_position,*lead) and not ship_map.is_blocked_circle(*lead,C.ALIEN_RADIUS):
                    self.current_target=lead
                self._los_grace_timer = C.CHASE_LOS_GRACE
            else:
                self._los_grace_timer -= dt
                if self._los_grace_timer <= 0:
                    # lost them - NOT allowed to keep following real position
                    self._enter_search_last_seen(ship_map, behavior_tracker)

        elif self.state == STATE_SEARCH_LAST_SEEN:
            if visible and self.suspicion >= C.SUSPICION_CHASE_THRESHOLD:
                self._enter_chase(player)
            elif heard_event is not None and self._heard_recently:
                self._enter_investigate()
            elif self._arrived_at(self.current_target):
                self._begin_search_area(ship_map, behavior_tracker, params, origin=self.current_target)

        elif self.state == STATE_SEARCH_AREA:
            if visible and self.suspicion >= C.SUSPICION_CHASE_THRESHOLD:
                self._enter_chase(player)
            elif heard_event is not None and self._heard_recently:
                self._enter_investigate()
            else:
                self._update_search_area(dt, ship_map, behavior_tracker, params)

    # -- state entry helpers ------------------------------------------
    def _enter_suspicious(self):
        self.state = STATE_SUSPICIOUS
        self.intent = "listen and turn toward evidence"
        self._suspicious_timer = random.uniform(C.SUSPICIOUS_STATE_MIN_TIME,
                                                  C.SUSPICIOUS_STATE_MAX_TIME)
        self.path = []

    def _enter_investigate(self):
        self.state = STATE_INVESTIGATE
        self.intent = "investigate approximate sound"
        target = self.last_heard_position if self._heard_recently else (self.last_seen_position or self.last_heard_position)
        self.current_target = self._reachable_target(target)
        self._investigate_timer=max(12,len(find_path(self.ship_map,tuple(self.pos),tuple(self.current_target),allow_closed_doors=True,diagonal=True))*C.TILE/C.ALIEN_INVESTIGATE_SPEED+6)
        self.path = []

    def _enter_chase(self, player):
        if self.state != STATE_CHASE:
            self._chase_start_room = self.ship_map.room_at_world(*self.last_seen_position)
        self.state = STATE_CHASE
        self.intent = "pursue visual contact"
        self.current_target = self.last_seen_position.copy()
        self._los_grace_timer = C.CHASE_LOS_GRACE

    def _enter_search_last_seen(self, ship_map, behavior_tracker):
        self.state = STATE_SEARCH_LAST_SEEN
        self.intent = "return to last visual evidence"
        self.current_target = self.last_seen_position
        self.path = []
        # ground-truth analytics logged by the world, not alien "cheating":
        # we only ever *use* this on later days as a prior, never this frame
        if self._chase_start_room is not None:
            end_room = ship_map.room_at_world(*self.last_seen_position) \
                if self.last_seen_position else None
            if end_room is not None:
                behavior_tracker.on_chase_flee_direction(self._chase_start_room, end_room.name)

    def _begin_search_area(self, ship_map, behavior_tracker, params, origin):
        self.state = STATE_SEARCH_AREA
        self.intent = "sweep exits and inspect hiding places"
        origin = origin.copy() if origin is not None else self.pos.copy()
        self._search_origin = origin
        self._waypoint_pause = 0.0
        self.search_area = self._build_search_waypoints(ship_map, behavior_tracker, params, origin)
        self._search_index = 0
        self.current_target = self.search_area[0]
        # The search now has time to travel; the old timer expired before reaching rooms.
        travel = 0.0
        previous = self.pos
        for point in self.search_area:
            travel += max(0,len(find_path(ship_map,tuple(previous),tuple(point),allow_closed_doors=True,diagonal=True))-1)*C.TILE/C.ALIEN_SEARCH_SPEED
            previous = point
        self._search_timer = max(C.SEARCH_AREA_BASE_TIME*params["search_time_mult"],travel+len(self.search_area)*C.SEARCH_AREA_WAYPOINT_TIME+3)
        self.path = []

    def _build_search_waypoints(self, ship_map, behavior_tracker, params, origin):
        points = [origin.copy()]
        # Project the last OBSERVED movement, clipped at walls. No live player vector.
        if self.last_seen_direction.length_squared() and self.last_seen_position is not None and origin.distance_to(self.last_seen_position)<60:
            projected = origin.copy()
            for d in range(24,193,12):
                test = origin+self.last_seen_direction*d
                if ship_map.is_blocked_circle(*test,C.ALIEN_RADIUS):break
                projected=test
            if projected.distance_to(origin)>40:
                points.append(self._reachable_target(projected))
        ranked = []
        origin_room = ship_map.room_at_world(*origin)
        likely = behavior_tracker.frequent_routes_from(origin_room.name) if origin_room and params["escape_bias"] else []
        for room in ship_map.rooms:
            path = find_path(ship_map,tuple(origin),tuple(room.world_center),allow_closed_doors=True,diagonal=True)
            length=len(path)
            if not 0<length<=52:continue
            score=length
            if room.name in likely:score-=20*params["escape_bias"]
            if params["use_hiding_memory"] and room.name in behavior_tracker.top_hiding_rooms():score-=18
            ranked.append((score,room))
        ranked.sort(key=lambda item:item[0])
        for _,room in ranked[:3]:
            if room.world_center.distance_to(origin)>35:
                points.append(room.world_center.copy())
            # A locker is checked by walking to it, even when nobody was seen entering.
            locker=ship_map.lockers.get(room.name)
            if locker is not None and (params["use_hiding_memory"] or room is origin_room):
                points.append(locker.copy())
        # Short corridor branches also get checked when no room lies nearby.
        if len(points)<3:
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                test=origin+pygame.Vector2(dx,dy)*96
                if ship_map.line_of_sight(*origin,*test) and not ship_map.is_blocked_circle(*test):
                    points.append(test)
        return points[:7]

    def _update_search_area(self, dt, ship_map, behavior_tracker, params):
        if self._arrived_at(self.current_target):
            self.facing_angle += dt*1.5
            for name, point in ship_map.lockers.items():
                if self.current_target is not None and self.current_target.distance_to(point)<20 and self.pos.distance_to(point)<30:
                    self.inspect_spot = name
            self._waypoint_pause += dt
            if self._waypoint_pause >= C.SEARCH_AREA_WAYPOINT_TIME:
                self._waypoint_pause = 0.0
                self._search_index += 1
                if self._search_index < len(self.search_area):
                    self.current_target = self.search_area[self._search_index]
                    self.path = []

        self._search_timer -= dt
        if self._search_timer <= 0 or self._search_index >= len(self.search_area):
            room = self._last_confirmed_room
            if room is not None:
                behavior_tracker.on_player_lost(room)
            self.suspicion = min(self.suspicion, C.SUSPICION_SUSPICIOUS_THRESHOLD * 0.5)
            self.state = STATE_WANDER
            self.current_target = None
            self.path = []

    # -- wander ----------------------------------------------------------
    def _do_wander(self, ship_map, behavior_tracker, params, day):
        if self._patrol_pause > 0:
            self._patrol_pause -= self._frame_dt
            self._scan_time += self._frame_dt
            self.facing_angle = self._scan_angle + math.sin(self._scan_time*1.7)*.8
            self.current_target = None
            return
        if self.current_target is not None and self._arrived_at(self.current_target, tol=20):
            self._patrol_pause = random.uniform(.8,2.1)
            self._scan_angle=self.facing_angle
            self._scan_time=0
            self.current_target = None
            self.path = []
            return
        if self.current_target is None:
            self._wander_target_room = self._pick_wander_room(ship_map, behavior_tracker, params, day)
            self._recent_patrol.append(self._wander_target_room.name)
            self._recent_patrol = self._recent_patrol[-4:]
            room=self._wander_target_room
            x,y,w,h=room.rect
            self.current_target=room.world_center
            for _ in range(16):
                point=pygame.Vector2(random.uniform(x+1,x+w-1)*C.TILE,random.uniform(y+1,y+h-1)*C.TILE)
                if not ship_map.is_blocked_circle(*point,C.ALIEN_RADIUS):
                    self.current_target=point;break
            self._route_seed=random.randrange(100000)
            self.path = []

    def _pick_wander_room(self, ship_map, behavior_tracker, params, day):
        rooms=[r for r in ship_map.rooms if r.name not in self._recent_patrol]
        if not rooms:rooms=list(ship_map.rooms)
        weights=[]
        current=ship_map.room_at_world(*self.pos)
        routes=behavior_tracker.frequent_routes_from(current.name) if current else []
        next_tasks=behavior_tracker.next_task_after(current.name) if current else []
        priors=behavior_tracker.predicted_first_task()
        for room in rooms:
            distance=self.pos.distance_to(room.world_center)
            weight=1/(1+distance/700)
            if params["memory_bias"] and behavior_tracker.task_order_history:
                if self._day_time<65:
                    weight+=priors.get(room.name,0)*10*params["memory_bias"]
                    self.intent="patrol learned first-task rooms"
                elif room.name in next_tasks:
                    weight+=4*params["memory_bias"]
                    self.intent="patrol learned task sequence"
                if room.name in routes:weight+=3*params["memory_bias"]
                if params["use_hiding_memory"] and room.name in behavior_tracker.top_hiding_rooms():
                    weight+=2*params["memory_bias"]
            weights.append(weight)
        return random.choices(rooms,weights=weights,k=1)[0]

    # -- movement / pathing -----------------------------------------------
    def movement_cadence(self):
        """A readable gathering of weight, then a short surge. Never a teleport."""
        phase=self.motion_clock*(4.2 if self.state==STATE_CHASE else 2.5)+self.stride_offset
        if self.state==STATE_CHASE:
            return .94+.27*max(0,math.sin(phase))**6
        if self.state in (STATE_WANDER,STATE_INVESTIGATE,STATE_SEARCH_AREA,STATE_SEARCH_LAST_SEEN):
            return .86+.17*math.sin(phase)+.05*math.sin(phase*2.3)
        return 1.0

    def _reachable_target(self, target):
        if target is None:
            return self.pos.copy()
        path = find_path(self.ship_map, tuple(self.pos), tuple(target),allow_closed_doors=True,diagonal=True)
        return pygame.math.Vector2(path[-1]) if path else self.pos.copy()

    def _arrived_at(self, target, tol=18):
        if target is None:
            return True
        return self.pos.distance_to(target) <= tol

    def _follow_path(self, dt, params):
        if self.state == STATE_DORMANT or self.current_target is None:
            return

        speed = {
            STATE_WANDER: C.ALIEN_WANDER_SPEED,
            STATE_SUSPICIOUS: 0.0,
            STATE_INVESTIGATE: C.ALIEN_INVESTIGATE_SPEED,
            STATE_CHASE: C.ALIEN_CHASE_SPEED,
            STATE_SEARCH_LAST_SEEN: C.ALIEN_SEARCH_SPEED,
            STATE_SEARCH_AREA: C.ALIEN_SEARCH_SPEED,
        }.get(self.state, 0.0)

        if speed <= 0:
            return

        target_key = (round(self.current_target.x, -1), round(self.current_target.y, -1))
        self._repath_timer -= dt
        needs_path = (not self.path) or self._path_geometry_revision!=self.ship_map.geometry_revision or (target_key != self._path_target_key
                                          and self._repath_timer <= 0)
        if needs_path:
            def patrol_cost(tile):
                # Remember our own traversed tiles, never the unseen player's position.
                jitter=((tile[0]*73856093 ^ tile[1]*19349663 ^ self._route_seed)%101)/500
                return jitter+min(2.4,self._visited_tiles.get(tile,0)*.35)
            raw=find_path(self.ship_map,tuple(self.pos),tuple(self.current_target),
                          allow_closed_doors=True,diagonal=True,
                          tile_cost=patrol_cost if self.state==STATE_WANDER else None)
            if raw and segment_clear(self.ship_map,raw[-1],tuple(self.current_target),C.ALIEN_RADIUS):
                raw[-1]=tuple(self.current_target)
            self.path=smooth_path(self.ship_map,tuple(self.pos),raw,C.ALIEN_RADIUS)
            if len(self.path)>1 and self.pos.distance_to(self.path[0])<.1:self.path.pop(0)
            self._path_target_key = target_key
            self._path_geometry_revision=self.ship_map.geometry_revision
            self._repath_timer = 0.35 if self.state == STATE_CHASE else 0.6

        if not self.path:
            return

        # Spend the entire movement budget across waypoints; no stutter at tile centres.
        budget=speed*dt*self.gait_scale
        for _ in range(16):
            if not self.path or budget<=.001:break
            waypoint=pygame.Vector2(self.path[0]);delta=waypoint-self.pos;distance=delta.length()
            if distance<.01:self.path.pop(0);continue
            direction=delta/distance
            step=min(budget,distance)
            candidate=self.pos+direction*step
            if not segment_clear(self.ship_map,tuple(self.pos),tuple(candidate),C.ALIEN_RADIUS):
                door=self.ship_map.doors.blocking(candidate,C.ALIEN_RADIUS)
                if door:
                    self.attacking_door=door
                    self.facing_angle=math.atan2(door.center.y-self.pos.y,door.center.x-self.pos.x)
                    if self.ship_map.doors.force(door,self.pos,dt):self.path=[];self._repath_timer=0
                    break
                self.path=[];self._repath_timer=0;break
            self.pos=candidate;self.moved_this_frame=True;budget-=step
            wanted=math.atan2(direction.y,direction.x)
            self.facing_angle+=fov.angle_diff(wanted,self.facing_angle)*min(1,dt*(12 if self.state==STATE_CHASE else 7))
            tile=world_to_tile(*self.pos)
            if tile!=getattr(self,'_last_walk_tile',None):
                self._last_walk_tile=tile
                self._visited_tiles[tile]=self._visited_tiles.get(tile,0)+1
                if len(self._visited_tiles)>220:self._visited_tiles.pop(next(iter(self._visited_tiles)))
            if step>=distance-.01:self.path.pop(0)

    def _emit_footsteps(self, dt, noise_system):
        """The alien makes its own noise while moving so the player can
        hear it nearby without seeing it. This never feeds back into its
        own hearing (filtered out by kind in _update_hearing)."""
        self._step_noise_timer -= dt
        if not self.moved_this_frame or self._step_noise_timer > 0:
            return
        radius, strength, interval = {
            STATE_WANDER: (170, 5, 0.6),
            STATE_INVESTIGATE: (240, 7, 0.45),
            STATE_CHASE: (310, 9, 0.3),
            STATE_SEARCH_LAST_SEEN: (230, 7, 0.45),
            STATE_SEARCH_AREA: (220, 6, 0.5),
        }.get(self.state, (0, 0, 1.0))
        if radius > 0:
            noise_system.emit(self.pos, radius, strength, "alien_step")
            self._step_noise_timer = interval*(.85+.25*abs(math.sin(self.motion_clock*3+self.stride_offset)))


def _day_params(day):
    from systems import get_day_params
    return get_day_params(day)


def _v(vec):
    if vec is None:
        return None
    return (round(vec.x, 1), round(vec.y, 1))
