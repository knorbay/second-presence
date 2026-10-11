"""
Alien on the Ship - gameplay/AI prototype.

Run with:  python3 main.py
(pip install pygame first - see README.md)
"""

import math
import random
import sys

import pygame

import config as C
from render_surfaces import opaque_surface
import fov
from shipmap import ShipMap, SPAWN_TILE
from pathfinding import tile_to_world_center, find_path
from entities import (Player, Alien, STATE_DORMANT, STATE_WANDER, STATE_SUSPICIOUS,
                       STATE_INVESTIGATE, STATE_CHASE, STATE_SEARCH_LAST_SEEN,
                       STATE_SEARCH_AREA)
from systems import NoiseSystem, TaskSystem, BehaviorTracker, get_day_params
from presentation import Presentation, NAMES
from audio import Audio
from survival import ShipConditions, conditions_for
from maintenance import PanelWork, work_for_day, job_title
from shift_plan import new_campaign_seed
from localization import language, set_language
from creature import draw_creature
from scenery import equipment_point
from death_effect import DeathSequence
from ship_atmosphere import ShipAtmosphere
from crew_logs import Logbook
from ui_fonts import ui_font
from game_storage import SaveStore
from menu_ui import MenuUI, TITLE, label


PHASE_MAIN_MENU = "MAIN_MENU"
PHASE_SETTINGS = "SETTINGS"
PHASE_LOADING = "LOADING"
PHASE_DAY_TRANSITION = "DAY_TRANSITION"
PHASE_PLAYING = "PLAYING"
PHASE_GAME_OVER = "GAME_OVER"
PHASE_GAME_WON = "GAME_WON"

STATE_COLORS = {
    STATE_DORMANT: (90, 90, 90),
    STATE_WANDER: (120, 170, 120),
    STATE_SUSPICIOUS: (230, 210, 60),
    STATE_INVESTIGATE: (240, 150, 40),
    STATE_CHASE: (230, 40, 40),
    STATE_SEARCH_LAST_SEEN: (230, 90, 200),
    STATE_SEARCH_AREA: (170, 90, 230),
}


class Alarm:
    def __init__(self, room, real, duration):
        self.room = room
        self.real = real
        self.timer = duration
        self.message = f"ALARM: {room.name} system fault"


class Game:
    def __init__(self,storage_dir=None,campaign_seed=None):
        self.store=SaveStore(storage_dir)
        self.settings=self.store.settings()
        set_language(self.settings["language"])
        self._autosave_enabled=False
        pygame.init()
        pygame.display.set_caption(TITLE+" — Spaceship Horror")
        self.screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
        self.clock = pygame.time.Clock()
        self.font = ui_font(16)
        self.font_small = ui_font(14)
        self.font_big = ui_font(34,True)
        self.font_mid = ui_font(20,True)

        self.ship_map = ShipMap()
        self.audio = Audio()
        self.audio.set_master(self.settings["volume"])
        self.integrity = C.SHIP_INTEGRITY_MAX
        self.conditions = ShipConditions()
        self.paused = False
        self.show_map = False
        self.logbook=Logbook()
        self.atmosphere=ShipAtmosphere()
        self.notification = ""
        self.notification_timer = 0.0
        self.heard_timer = 0.0
        self.heard_message='... ayak sesleri'
        self.heard_direction = pygame.Vector2(0, -1)
        self.heartbeat_timer = 0.0
        self.creature_cue_timer=0.0
        self._last_creature_state=None
        self.lockers = {}
        for name in ("Quarters", "Oxygen", "Cargo Bay", "Power", "Reactor"):
            room = self.ship_map.room_by_name(name)
            x, y, w, h = room.rect
            self.lockers[name] = pygame.Vector2((x+1.5)*C.TILE, (y+h-1.5)*C.TILE)
        self.ship_map.lockers = self.lockers
        self.presentation = Presentation(self)
        self.world_surface = opaque_surface((C.WORLD_W, C.WORLD_H))
        self.camera_surface = opaque_surface((C.SCREEN_W, C.VIEW_H))
        self.camera = pygame.Vector2()
        self.noise = NoiseSystem()
        self.tasks = TaskSystem(self.ship_map,new_campaign_seed() if campaign_seed is None else campaign_seed)
        self.tracker = BehaviorTracker()

        self.day = 1
        self.sim_time = 0.0
        self.debug = False
        self.running = True
        self.last_day_summary = None
        self.game_over_reason = ""
        self.death = None

        self.alarms = []
        self.sabotage_cooldown = random.uniform(20, 30)

        self._start_day(first=True)
        self.phase = PHASE_MAIN_MENU
        self.menu=MenuUI(self)
        self.audio.pause(True)

    @property
    def lamp_power(self):return self.conditions.lamp_power*self.settings['brightness']

    def _save_game(self,notify=True):
        try:
            saved=self.store.save(self)
        except (OSError,ValueError,TypeError):
            self.menu.notice(label('Kayıt diske yazılamadı.','Unable to write the save.'))
            return False
        if saved and notify:self.menu.notice(label('Vardiya kaydedildi.','Shift saved.'))
        return saved

    def _autosave(self):
        if self._autosave_enabled:self._save_game(notify=False)

    def _new_game_from_menu(self):
        # Preserve the previous slot before beginning a new campaign.
        if self.store.path.exists():
            import shutil
            shutil.copy2(self.store.path,self.store.root/'previous_save.json')
        self._restart_game();self.paused=False;self.show_map=False
        self._autosave_enabled=True;self._autosave()

    # ------------------------------------------------------------ setup
    def _pick_alien_spawn_room(self, origin=None):
        candidates = [r for r in self.ship_map.rooms if r.name != "Quarters"]
        # Every day starts outside immediate contact, including late days.
        far = []
        spawn = pygame.Vector2(origin) if origin is not None else self.ship_map.room_by_name("Quarters").world_center
        for r in candidates:
            path = find_path(self.ship_map, (spawn.x, spawn.y),
                              (r.world_center.x, r.world_center.y))
            if len(path) > (34 if self.day <= 3 else 22) and (origin is None or not self.ship_map.line_of_sight(*spawn,*r.world_center)):
                far.append(r)
        if far:
            candidates = far
        if self.day >= 4 and self.tracker.task_order_history and random.random() < get_day_params(self.day)["memory_bias"]:
            predicted = self.ship_map.room_by_name(self.tracker.most_likely_first_task_room())
            if predicted in candidates:
                return predicted
        return random.choice(candidates)

    def _start_day(self, first=False):
        self.death = None
        self.logbook.open=False
        self.atmosphere.reset(self.day)
        self.ship_map.set_day(self.day)
        self.presentation.refresh()
        self.conditions.start_day(self.day)
        self._last_blackout=self.conditions.blackout
        self.tasks.reset_day(self.day)
        self.panel_work = None
        self.panel_inputs = []
        self._last_e = False
        self._e_pressed = False
        self._b_pressed=False
        self.tracker.start_day()
        self.day_time = 0.0
        self.decoy_charges = conditions_for(self.day).capsules
        self.decoys = []
        self.show_map = False
        self.heard_timer = 0.0
        self.heard_message='... ayak sesleri'
        self.notification_timer = 0.0
        self.noise.clear()
        self.alarms = []
        self.sabotage_cooldown = random.uniform(20, 35)

        quarters = self.ship_map.room_by_name("Quarters").world_center
        self.player = Player(self.ship_map, (quarters.x, quarters.y))
        self.camera = self.camera_target()

        spawn_room = self._pick_alien_spawn_room()
        self.alien = Alien(self.ship_map, (spawn_room.world_center.x, spawn_room.world_center.y))
        self.alien.state = STATE_DORMANT
        self.creature_cue_timer = 0.0
        self._last_creature_state = STATE_DORMANT

        if self.day >= 4:
            self.alien._patrol_pause = 8.0
        params = get_day_params(self.day)
        self.day_length = C.DAY_LENGTH_SECONDS if self.day < C.NUM_DAYS else 360.0
        self._day_label = params["label"]

    # -------------------------------------------------------------- run
    def run(self):
        while self.running:
            dt = self.clock.tick(C.FPS) / 1000.0
            dt = min(dt, 0.05)  # clamp huge stalls (e.g. window drag)
            self._handle_events()
            self._update(dt)
            self._render()
            pygame.display.flip()
        pygame.quit()
        sys.exit(0)

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type==pygame.MOUSEBUTTONUP and self.panel_work and (self.paused or self.phase!=PHASE_PLAYING):
                self.panel_work.dragging=None;self.panel_work.pumping=False
            if self.menu.handle(event):continue
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP,pygame.MOUSEMOTION):
                if event.type==pygame.MOUSEBUTTONDOWN and event.button==1 and (self.paused or self.phase==PHASE_DAY_TRANSITION):
                    for code,rect in self.presentation.language_rects():
                        if rect.collidepoint(event.pos):set_language(code);self.presentation.refresh()
                    continue
                if self.panel_work and self.phase==PHASE_PLAYING:
                    if self.paused or self.show_map:
                        if event.type==pygame.MOUSEBUTTONUP:
                            self.panel_work.dragging=None;self.panel_work.pumping=False
                        continue
                    if event.type==pygame.MOUSEMOTION:
                        self.panel_inputs.append(('move',event.pos))
                    elif event.button==1:
                        self.panel_inputs.append(('down' if event.type==pygame.MOUSEBUTTONDOWN else 'up',event.pos))
            elif event.type == pygame.KEYDOWN:
                panel_keys = {pygame.K_1:"1",pygame.K_2:"2",pygame.K_3:"3",pygame.K_SPACE:"space",pygame.K_RETURN:"space"}
                if self.panel_work and not self.paused and not self.show_map and event.key in panel_keys:
                    if not getattr(event,"repeat",False): self.panel_inputs.append(panel_keys[event.key])
                    continue
                if event.key==pygame.K_l:
                    set_language('en' if language()=='tr' else 'tr');self.presentation.refresh()
                elif event.key==pygame.K_j and self.phase==PHASE_PLAYING and not self.paused:
                    self.logbook.open=not self.logbook.open
                    self.show_map=False;self._cancel_panel()
                elif self.logbook.open and not self.paused and event.key in (pygame.K_LEFT,pygame.K_RIGHT):
                    self.logbook.turn(-1 if event.key==pygame.K_LEFT else 1)
                elif event.key==pygame.K_ESCAPE and self.logbook.open and not self.paused:
                    self.logbook.open=False
                elif event.key == pygame.K_F3:
                    self.debug = not self.debug
                elif event.key == pygame.K_ESCAPE and self.panel_work:
                    self._cancel_panel()
                elif event.key in (pygame.K_ESCAPE, pygame.K_p):
                    self.paused = not self.paused
                    self.audio.pause(self.paused)
                elif event.key == pygame.K_q and (self.paused or self.phase in (PHASE_GAME_OVER, PHASE_GAME_WON)):
                    self.running = False
                elif event.key == pygame.K_m:
                    self.audio.toggle()
                elif event.key == pygame.K_TAB and self.phase == PHASE_PLAYING and not self.paused:
                    self.logbook.open=False
                    self.show_map = not self.show_map
                    self._cancel_panel()
                elif event.key == pygame.K_e and self.phase == PHASE_PLAYING and not self.paused and not self.show_map:
                    if not getattr(event,"repeat",False): self._e_pressed = True
                elif event.key==pygame.K_b and self.phase==PHASE_PLAYING and not self.paused and not self.show_map and not self.logbook.open:
                    if not getattr(event,'repeat',False):self._b_pressed=True
                elif event.key == pygame.K_f and self.phase == PHASE_PLAYING and not self.paused:
                    self._toggle_hiding()
                elif event.key == pygame.K_g and self.phase == PHASE_PLAYING and not self.paused:
                    self._throw_decoy()
                elif event.key == pygame.K_SPACE and self.phase == PHASE_DAY_TRANSITION and not self.paused:
                    self._advance_from_transition()
                elif event.key == pygame.K_r and self.phase in (PHASE_GAME_OVER, PHASE_GAME_WON) and not self.paused and (not self.death or self.death.complete):
                    self._restart_game()

    def _advance_from_transition(self):
        if self.day > C.NUM_DAYS:
            self.phase = PHASE_GAME_WON
            return
        self.phase = PHASE_PLAYING
        self.audio.pause(False)
        self._autosave()

    def _restart_game(self,campaign_seed=None):
        self.audio.reset()
        self.logbook=Logbook()
        self.sim_time=0.0
        self.day = 1
        self.integrity = C.SHIP_INTEGRITY_MAX
        self.conditions = ShipConditions()
        self.last_day_summary = None
        self.game_over_reason = ""
        self.tracker = BehaviorTracker()
        if campaign_seed is None:self.tasks.new_campaign()
        else:
            self.tasks.campaign_seed=campaign_seed
            self.tasks.plan_version=1 if campaign_seed else 0
        self.presentation.explored.fill('black')
        self._start_day(first=True)
        self.phase = PHASE_DAY_TRANSITION
        self._autosave()

    # ----------------------------------------------------------- update
    def _update(self, dt):
        self.menu.update(dt)
        if self.phase in (PHASE_MAIN_MENU,PHASE_SETTINGS,PHASE_LOADING):return
        if self.paused:
            return
        self.sim_time += dt
        if self.phase == PHASE_PLAYING:
            self._update_playing(dt)
        elif self.phase==PHASE_DAY_TRANSITION:
            self.audio.environment(dt,'Quarters',self.day,False)
        elif self.phase==PHASE_GAME_OVER and self.death:
            for cue in self.death.update(dt):self.audio.play(cue,.42 if cue=='death_hit' else .36)
            self.audio.fade_environment(dt)

    def _keys(self):
        pressed = pygame.key.get_pressed()
        arrows_move = not self.logbook.open and (self.panel_work is None or self.panel_work.kind not in ("calibrate","signal","course"))
        vertical_move = not self.logbook.open and (self.panel_work is None or self.panel_work.kind != "course")
        return {
            "w": pressed[pygame.K_w] or (vertical_move and pressed[pygame.K_UP]),
            "a": pressed[pygame.K_a] or (arrows_move and pressed[pygame.K_LEFT]),
            "s": pressed[pygame.K_s] or (vertical_move and pressed[pygame.K_DOWN]),
            "d": pressed[pygame.K_d] or (arrows_move and pressed[pygame.K_RIGHT]),
            "shift": pressed[pygame.K_LSHIFT] or pressed[pygame.K_RSHIFT],
            "e": pressed[pygame.K_e],
            "ctrl": pressed[pygame.K_LCTRL] or pressed[pygame.K_RCTRL],
            "left": pressed[pygame.K_LEFT],
            "right": pressed[pygame.K_RIGHT],
            "up": pressed[pygame.K_UP],
            "down": pressed[pygame.K_DOWN],
        }

    def camera_target(self):
        return pygame.Vector2(max(0,min(C.WORLD_W-C.CAMERA_W,self.player.pos.x-C.CAMERA_W/2)),
                              max(0,min(C.WORLD_H-C.CAMERA_H,self.player.pos.y-C.CAMERA_H/2)))

    def world_to_view(self,point):
        return pygame.Vector2((point.x-int(self.camera.x))*C.SCREEN_W/C.CAMERA_W,
                              (point.y-int(self.camera.y))*C.VIEW_H/C.CAMERA_H)

    def interaction_label(self, name):
        return NAMES.get(name,name)

    def _interactables(self):
        if self.day < C.NUM_DAYS:
            items = [{"name": t.name, "point": t.room.world_center, "done": t.done, "operation": t.operation, "blocked": self.tasks.blocked_by(t.name)}
                     for t in self.tasks.tasks.values()]
        else:
            target = self.tasks.day8_current_target()
            items = ([{"name": target, "point": self.ship_map.room_by_name(target).world_center, "done": False, "operation": work_for_day(8,target)}]
                     if target else [])
        return items

    def _notify(self, text):
        self.notification = text
        self.notification_timer = 3.0

    def nearby_locker(self):
        for name, point in self.lockers.items():
            if self.player.pos.distance_to(point) < 42 and self.ship_map.line_of_sight(*self.player.pos, *point):
                return name
        return None

    def _toggle_hiding(self):
        if self.player.hidden:
            self.player.hidden = False
            self.player.hidden_spot = None
            self._notify("Dolaptan çıktın. Koridoru dinle.")
            return
        name = self.nearby_locker()
        if name is None:
            self._notify("Saklanmak için bir dolaba yaklaş. TAB: gemi planı.")
            return
        point = self.lockers[name]
        visible, _, _ = fov.can_see_point(self.ship_map, tuple(self.alien.pos),
            self.alien.facing_angle, tuple(self.player.pos), C.ALIEN_FOV_ANGLE,
            get_day_params(self.day)["vision_range"])
        if visible and self.alien.state != STATE_DORMANT and get_day_params(self.day)["alien_active"]:
            self.alien.observed_hiding_spot = name
            self.alien.last_seen_position = point.copy()
            self.alien.current_target = point.copy()
            self.alien.path = []
        self._cancel_panel()
        self.player.pos = point.copy()
        self.player.hidden = True
        self.player.hidden_spot = name
        self.player.interacting = self.player.moving = self.player.sprinting = False
        self.player.interact_progress = 0.0
        self._notify("Saklandın. İçeri girdiğini gördüyse yerini biliyor.")

    def _throw_decoy(self):
        if self.player.hidden or self.decoy_charges <= 0:
            self._notify("Dolaptayken kapsül atamazsın." if self.player.hidden else "Ses kapsüllerin tükendi.")
            return
        point = self.player.pos.copy()
        for distance in range(8, C.DECOY_RANGE+1, 8):
            candidate = self.player.pos+self.player.facing*distance
            if self.ship_map.is_blocked_circle(*candidate, 4):
                break
            point = candidate
        self.decoys.append({"point": point, "timer": C.DECOY_DELAY, "pulses": 3})
        self.decoy_charges -= 1
        self._notify("Kapsül atıldı. Ses başlamadan rotanı değiştir.")

    def _update_decoys(self, dt):
        for decoy in self.decoys[:]:
            decoy["timer"] -= dt
            if decoy["timer"] <= 0:
                self.noise.emit(decoy["point"], C.DECOY_RADIUS, 36, "decoy")
                self.audio.play_at("decoy",decoy["point"],self.player.pos,self.ship_map,.45,C.DECOY_RADIUS)
                decoy["pulses"] -= 1
                decoy["timer"] = .4
                if decoy["pulses"] <= 0:
                    self.decoys.remove(decoy)

    def _on_interact_complete(self,name):
        if self.day<C.NUM_DAYS:
            if not self.tasks.available(name):return
            task=self.tasks.tasks[name]
            previous=task.title
            finished=self.tasks.advance_task(name,self.day_time)
            self.audio.play('latch',.16)
            self._notify('Görev tamamlandı: '+NAMES[name] if finished else previous+' aşaması bitti. Sıradaki: '+task.title)
            if finished and name in ('Power','Cooling','Reactor'):
                self._notify({'Power':'Güç kararlı. Kesintiler durdu.' if self.day<3 else 'Makine gücü geri geldi. Genel aydınlatma hâlâ kapalı.',
                    'Cooling':'Soğutma dengelendi. Buhar tahliyesi durdu.',
                    'Reactor':'Reaktör dengelendi. Makine uğultusu azaldı.'}[name])
        else:
            self.tasks.day8_advance(name)
            self._notify('Görev tamamlandı: '+NAMES[name])
        self._autosave()

    def _cancel_panel(self):
        if self.panel_work:
            self.panel_work.dragging=None;self.panel_work.selected=None;self.panel_work.pumping=False
        self.panel_work = None
        self.panel_inputs = []
        self.player.interacting = False
        self.player.interact_task = None
        self.player.interact_progress = 0.0

    def _update_panel(self, dt, keys):
        pressed = bool(keys.get("e")) or self._e_pressed
        self._e_pressed = False
        if self.logbook.open:
            self._last_e=bool(keys.get('e'));self.panel_inputs=[]
            return
        if self.panel_work:
            point = self.ship_map.room_by_name(self.panel_work.name).world_center
            if self.player.moving or self.player.hidden or self.player.pos.distance_to(point)>=60 or (self.day<8 and not self.tasks.available(self.panel_work.name)):
                self._cancel_panel()
        elif pressed and not self._last_e and not self.player.hidden and not self.player.moving:
            near = self.player._nearby_interactable(self._interactables())
            entry=self.logbook.nearby(self.ship_map,self.player.pos,self.day)
            if entry and near is None:
                self.logbook.discover(entry)
                self.audio.play('terminal',.07)
            elif near and near.get("operation"):
                if near.get('blocked'):
                    self._notify('Önce: '+', '.join(NAMES[n] for n in near['blocked']))
                elif self.day<8:
                    task=self.tasks.tasks[near['name']];key=(task.step,task.revision)
                    if key not in task.sessions:task.sessions[key]=self.tasks.panel(task.name,task.operation,task.revision*31+task.step)
                    self.panel_work=task.sessions[key]
                    self.audio.play('open',.08)
                else:self.panel_work=self.tasks.panel(near['name'],near['operation'])
        self._last_e = bool(keys.get("e"))
        if not self.panel_work:
            self.panel_inputs = []
            return
        work = self.panel_work
        self.player.interacting = True
        self.player.interact_task = {"name":work.name}
        work.update(dt,keys)
        self.audio.panel_activity(dt,work)
        self.player.interact_progress = work.progress
        work.noise_timer -= dt
        if work.noise_timer<=0:
            radius,strength = work.noise
            self.noise.emit(self.player.pos,radius,strength,"panel")
            work.noise_timer = .65
        for key in self.panel_inputs:
            outcome = self.presentation.task_panels.pointer(work,*key) if isinstance(key,tuple) else work.press(key)
            self.audio.panel_feedback(work.kind,outcome)
            if outcome == "wrong":
                self.noise.emit(self.player.pos,230,16,"panel_error")
            if outcome == "complete":
                name = work.name
                self._cancel_panel()
                self._on_interact_complete(name)
                break
        self.panel_inputs = []

    def _update_playing(self, dt):
        self.noise.clear()
        self.notification_timer = max(0, self.notification_timer-dt)
        self.heard_timer = max(0, self.heard_timer-dt)
        keys = self._keys()
        self.player.update(dt, keys, self.noise, self._interactables(),
                            self._on_interact_complete, self.tracker)
        self._update_doors(dt)
        if self.player.moving:self.logbook.open=False
        self._update_panel(dt,keys)
        serviced=self.serviced_systems()
        self.conditions.update(dt,self.day_time,serviced.get('Power',False))
        for sound,point in self.atmosphere.update(dt,self.ship_map,serviced,self.noise,
                day_time=self.day_time,listener=self.player.pos,seed=self.tasks.campaign_seed):
            self.audio.play_at(sound,point,self.player.pos,self.ship_map,.28,380)
        self._update_decoys(dt)
        self.camera += (self.camera_target()-self.camera)*min(1,dt*9)
        from systems import hunter_awake
        if self.alien.state == STATE_DORMANT and hunter_awake(self.day,self.day_time):
            # The player may have walked to the original spawn during the quiet opening.
            # Introduce the hunter off screen, then let its ordinary senses take over.
            room = self._pick_alien_spawn_room(self.player.pos)
            self.alien.pos = room.world_center.copy()
            self.alien._patrol_pause = 4.0
        self.alien.update(dt, self.player, self.ship_map, self.noise,
                           self.tracker, self.day, self.day_time, self.sim_time)
        self._process_door_events()
        self.atmosphere.record_motion(self.alien,self.ship_map)

        self._update_alarms(dt)
        self._update_audio(dt)
        self._check_catch()
        if self.phase != PHASE_PLAYING:
            return  # caught this frame
        self.day_time += dt

        if self.day < C.NUM_DAYS:
            if self.tasks.all_standard_tasks_done() or self.day_time >= self.day_length:
                self._end_day()
        else:
            if self.tasks.day8_complete:
                self.phase = PHASE_GAME_WON
            elif self.day_time >= self.day_length:
                self.phase = PHASE_GAME_OVER
                self.game_over_reason = "Kaçış dizisi tamamlanamadı. Geminin sistemleri kapandı."

    def serviced_systems(self):
        if self.day==8:return {name:i<self.tasks.day8_step for i,name in enumerate(C.DAY8_SEQUENCE)}
        return {name:task.done for name,task in self.tasks.tasks.items()}

    def _update_doors(self,dt):
        doors=self.ship_map.doors
        if self._b_pressed:
            self._b_pressed=False
            door=doors.nearby(self.player.pos)
            if self.player.hidden:self._notify('Dolaptayken kapıya uzanamazsın.')
            elif door is None:self._notify('Kapı koluna yaklaş.')
            else:
                result=doors.toggle(door,[(self.player.pos,C.PLAYER_RADIUS),(self.alien.pos,C.ALIEN_RADIUS)])
                self._notify({'close':'Kapı kapandı. Metal sesi koridorda yankılandı.',
                    'open':'Kapı açıldı.','occupied':'Kapının önü kapalı.',
                    'busy':'Kapı hareket ediyor. Bir an bekle.',
                    'broken':'Kapı parçalandı. Bu vardiyada kapanmaz.'}[result])
                if result in ('open','close'):self._cancel_panel()
        doors.update(dt)
        self._process_door_events()

    def _process_door_events(self):
        for kind,point in self.ship_map.doors.drain_events():
            sound='open' if kind=='open' else 'latch' if kind=='close' else 'repair'
            hostile=kind in ('hit','breach')
            radius=360 if kind=='breach' else 280 if kind=='close' else 260
            strength=32 if kind=='breach' else 24 if kind=='close' else 20 if hostile else 17
            self.noise.emit(point,radius,strength,'alien_door' if hostile else 'door')
            self.audio.play_at(sound,point,self.player.pos,self.ship_map,.36 if kind=='breach' else .24,radius)
            delta=point-self.player.pos
            if hostile and delta.length()<radius:
                self.heard_timer=1.2
                self.heard_direction=delta.normalize() if delta.length_squared() else pygame.Vector2(0,-1)
                self.heard_message='... kapı parçalandı' if kind=='breach' else '... metal zorlanıyor'

    def _check_catch(self):
        if self.phase != PHASE_PLAYING or self.alien.state != STATE_CHASE:
            return
        d = self.alien.pos.distance_to(self.player.pos)
        if d <= C.CATCH_RADIUS and self.ship_map.line_of_sight(
                self.alien.pos.x, self.alien.pos.y, self.player.pos.x, self.player.pos.y):
            self.player.caught = True
            self._cancel_panel()
            self.logbook.open=False
            self.show_map=False
            self.screen.fill(C.COL_BG)
            self._render_playing(actors=False,hud=False)
            self.death=DeathSequence(self.screen.copy(),self.world_to_view(self.player.pos),
                self.world_to_view(self.alien.pos),self.player.facing,self.sim_time)
            self.phase = PHASE_GAME_OVER
            self.game_over_reason = f"{self.day}. vardiyada yakalandın. Görüşü kesmeden saklanmak tehlikeli."
            self.audio.play('creature',.29)
            self.audio.play('death_breath',.22)

    def _end_day(self):
        missed = sum(not task.done for task in self.tasks.tasks.values())
        self.integrity = max(0, self.integrity-missed*C.MISSED_TASK_DAMAGE)
        if self.integrity <= 0:
            self.phase = PHASE_GAME_OVER
            self.game_over_reason = "İhmal edilen bakımlar gemiyi kullanılamaz hale getirdi."
            return
        self.tracker.end_day(self.tasks)
        self.last_day_summary = dict(
            day=self.day,
            order=self.tasks.completion_order(),
            timed_out=not self.tasks.all_standard_tasks_done(),
            total=len(self.tasks.tasks),
        )
        self.day += 1
        if self.day > C.NUM_DAYS:
            self.phase = PHASE_DAY_TRANSITION  # final summary screen, then GAME_WON check
        else:
            self._start_day()
            self.phase = PHASE_DAY_TRANSITION
            self._autosave()

    def _update_alarms(self, dt):
        params = get_day_params(self.day)
        for a in list(self.alarms):
            a.timer -= dt
            if a.timer <= 0:
                self.alarms.remove(a)

        self.sabotage_cooldown -= dt
        if params["sabotage"] and not self.alarms and self.sabotage_cooldown <= 0:
            self.sabotage_cooldown = random.uniform(38, 60)
            if random.random() < 0.55:  # deliberately not-guaranteed - "do not overuse"
                fake = random.random() < 0.5
                if fake:
                    room = random.choice([t.room for t in self.tasks.tasks.values()])
                else:
                    room = random.choice([t.room for t in self.tasks.tasks.values()])
                self.alarms.append(Alarm(room, real=not fake, duration=14.0))
                if not fake:
                    # Real faults reopen a maintained panel. Fake alarms remain a warning.
                    self.tasks.tasks[room.name].reopen()
                self.audio.play_at('alarm',equipment_point(room),self.player.pos,self.ship_map,.24,600)

    def _update_audio(self, dt):
        for event in self.noise.events:
            if event.kind == "alien_step":
                distance = self.player.pos.distance_to(event.pos)
                if distance <= event.radius:
                    direction = event.pos-self.player.pos
                    self.heard_direction = direction.normalize() if direction.length_squared() else pygame.Vector2(0,-1)
                    self.heard_timer = 1.2
                    self.heard_message='... ayak sesleri'
                    self.audio.footstep('hunter',source=event.pos,listener=self.player.pos,
                                        ship_map=self.ship_map,radius=event.radius)
            elif event.kind in ("walk", "run", "crouch"):
                self.audio.footstep('player',event.kind)
            elif event.kind == "repair":
                self.audio.play("repair", .18)
        direction=self.alien.pos-self.player.pos
        distance=direction.length()
        visible=self.alien.state!=STATE_DORMANT and self.ship_map.line_of_sight(*self.player.pos,*self.alien.pos) and self.presentation.lighting.strength_at(self.ship_map,tuple(self.player.pos),math.atan2(self.player.facing.y,self.player.facing.x),tuple(self.alien.pos),self.conditions.view_radius,self.lamp_power,self.conditions.ambient_strength)>=18
        contact=visible or self.heard_timer>0
        room=self.player.current_room
        if self.conditions.blackout!=self._last_blackout:
            self.audio.play('latch',.3)
            self.audio.play('terminal',.09 if self.conditions.blackout else .15)
            self._last_blackout=self.conditions.blackout
        self.audio.environment(dt,room.name if room else None,self.day,self.conditions.blackout,contact,
                               self.player.pos,self.ship_map,self.serviced_systems())
        self.creature_cue_timer-=dt
        if self.alien.state!=STATE_DORMANT and distance<170 and contact and self.creature_cue_timer<=0:
            self.audio.play_at('creature',self.alien.pos,self.player.pos,self.ship_map,.22,220)
            self.audio.play_at('breath',self.alien.pos,self.player.pos,self.ship_map,.14,200)
            self.creature_cue_timer=random.uniform(3.5,7)
        if self.alien.state==STATE_CHASE and self._last_creature_state!=STATE_CHASE and contact:
            self.audio.play_at('creature',self.alien.pos,self.player.pos,self.ship_map,.28,300)
        self._last_creature_state=self.alien.state
        self.heartbeat_timer-=dt
        if self.heartbeat_timer<=0:
            source=self.player.pos+pygame.Vector2(random.uniform(-190,190),random.uniform(-110,110))
            self.audio.play_at('creak',source,self.player.pos,self.ship_map,.16,350)
            self.heartbeat_timer=random.uniform(12,27)

    # ----------------------------------------------------------- render
    def _render(self):
        self.screen.fill(C.COL_BG)
        if self.phase in (PHASE_MAIN_MENU,PHASE_SETTINGS,PHASE_LOADING):
            self.menu.draw()
            return
        if self.phase == PHASE_PLAYING:
            self._render_playing()
        elif self.phase == PHASE_DAY_TRANSITION:
            self._render_transition()
        elif self.phase == PHASE_GAME_OVER:
            if self.death and not self.death.complete:self.death.draw(self.screen)
            else:self.presentation.ending("SİNYAL KESİLDİ", self.game_over_reason, (233, 100, 107))
        elif self.phase == PHASE_GAME_WON:
            self.presentation.ending("HAYATTASIN", "Kaçış kapsülü ayrıldı. Gemi artık sessiz.", (110, 218, 159))

        self.presentation.overlay()

    def _render_playing(self,actors=True,hud=True):
        window = self.screen
        self.screen = self.world_surface
        self.presentation.world()

        visible_to_player = self.ship_map.line_of_sight(
            self.player.pos.x, self.player.pos.y, self.alien.pos.x, self.alien.pos.y
        ) and self.presentation.lighting.strength_at(self.ship_map, tuple(self.player.pos),
                math.atan2(self.player.facing.y,self.player.facing.x), tuple(self.alien.pos),
                self.conditions.view_radius,self.lamp_power,self.conditions.ambient_strength)>=18

        # task markers (only visible through fog naturally, drawn before fog)
        self._draw_tasks()

        if actors and visible_to_player and self.alien.state != STATE_DORMANT:
            self._draw_alien()

        if actors:self._draw_player()

        for decoy in self.decoys:
            p = decoy["point"]
            pygame.draw.circle(self.screen, (142,128,104), (int(p.x),int(p.y)), 5, 2)
        self._apply_fog()
        if self.debug:
            self._draw_debug_world()
        self.screen = window
        crop=self.world_surface.subsurface(pygame.Rect(int(self.camera.x),int(self.camera.y),C.CAMERA_W,C.CAMERA_H))
        pygame.transform.smoothscale(crop,(C.SCREEN_W,C.VIEW_H),self.camera_surface)
        self.screen.blit(self.camera_surface,(0,0))
        if hud:self.presentation.hud()
        if self.debug:
            self._draw_debug_panel()

    # -- world drawing ----------------------------------------------------
    def _draw_tasks(self):
        if self.day < C.NUM_DAYS:
            for t in self.tasks.tasks.values():
                c = self.ship_map.task_rooms[t.name].world_center
                color = C.COL_TASK_DONE if t.done else C.COL_TASK_TODO
                pygame.draw.circle(self.screen, color, (int(c.x), int(c.y)), 9, 2)
        else:
            target = self.tasks.day8_current_target()
            if target:
                c = self.ship_map.room_by_name(target).world_center
                pygame.draw.circle(self.screen, C.COL_TASK_TODO, (int(c.x), int(c.y)), 10, 2)

    def _draw_player(self):
        p = self.player
        if p.hidden:
            pygame.draw.circle(self.screen, (137,139,136), (int(p.pos.x),int(p.pos.y)),14,1)
            return
        pygame.draw.circle(self.screen, (10,22,29), (int(p.pos.x),int(p.pos.y)),p.radius+3)
        pygame.draw.circle(self.screen, C.COL_PLAYER, (int(p.pos.x),int(p.pos.y)),p.radius)
        pygame.draw.circle(self.screen, (169,174,177),
            (int(p.pos.x+p.facing.x*3),int(p.pos.y+p.facing.y*3)),3)
        tip = p.pos + p.facing * (p.radius + 6)
        pygame.draw.line(self.screen, C.COL_PLAYER, p.pos, tip, 2)
        if p.interacting and not self.panel_work:
            self._progress_ring(p.pos, p.radius + 8, p.interact_progress, C.COL_TASK_TODO)
        if p.sprinting:
            pygame.draw.circle(self.screen, C.COL_PLAYER, (int(p.pos.x), int(p.pos.y)),
                                int(p.radius + 4), 1)

    def _draw_alien(self):
        a=self.alien
        draw_creature(self.screen,a.pos,a.facing_angle,self.sim_time,moving=a.moved_this_frame or a.attacking_door is not None,alert=a.state==STATE_CHASE)

    def _progress_ring(self, center, radius, progress, color):
        steps = max(1, int(36 * progress))
        for i in range(steps):
            ang0 = -math.pi / 2 + (i / 36) * 2 * math.pi
            ang1 = -math.pi / 2 + ((i + 1) / 36) * 2 * math.pi
            p0 = center + pygame.math.Vector2(math.cos(ang0), math.sin(ang0)) * radius
            p1 = center + pygame.math.Vector2(math.cos(ang1), math.sin(ang1)) * radius
            pygame.draw.line(self.screen, color, p0, p1, 3)

    # -- fog of war ---------------------------------------------------------
    def _apply_fog(self):
        self.presentation.fog_of_war()

    # -- debug (F3) ------------------------------------------------------
    def _draw_debug_world(self):
        a = self.alien
        # true alien position, always shown in debug regardless of visibility
        pygame.draw.circle(self.screen, C.COL_DEBUG, (int(a.pos.x), int(a.pos.y)), C.ALIEN_RADIUS, 2)

        # vision cone
        params = get_day_params(self.day)
        cone = fov.cone_polygon(self.ship_map, (a.pos.x, a.pos.y), a.facing_angle,
                                 C.ALIEN_FOV_ANGLE, params["vision_range"])
        if len(cone) >= 3:
            surf = pygame.Surface((C.WORLD_W, C.WORLD_H), pygame.SRCALPHA)
            pygame.draw.polygon(surf, (*C.COL_DEBUG_FOV, 40), cone)
            pygame.draw.lines(surf, (*C.COL_DEBUG_FOV, 160), True, cone, 1)
            self.screen.blit(surf, (0, 0))

        # path
        if len(a.path) >= 2:
            pygame.draw.lines(self.screen, C.COL_DEBUG_PATH, False, a.path, 2)
        for wp in a.path:
            pygame.draw.circle(self.screen, C.COL_DEBUG_PATH, (int(wp[0]), int(wp[1])), 3)

        # memory markers
        if a.last_seen_position:
            self._x_mark(a.last_seen_position, (255, 80, 80))
        if a.last_heard_position:
            self._x_mark(a.last_heard_position, (255, 220, 80))
        for wp in a.search_area:
            pygame.draw.circle(self.screen, (170, 90, 230), (int(wp.x), int(wp.y)), 6, 1)

        # noise event radii this frame
        for event in self.noise.events:
            pygame.draw.circle(self.screen, C.COL_DEBUG_SOUND, (int(event.pos.x), int(event.pos.y)),
                                int(event.radius), 1)

        # state label above alien head
        label = self.font_small.render(f"{a.state}  susp={a.suspicion:.0f}", True, C.COL_DEBUG)
        self.screen.blit(label, (a.pos.x - 40, a.pos.y - 28))

    def _x_mark(self, pos, color):
        s = 6
        pygame.draw.line(self.screen, color, (pos.x - s, pos.y - s), (pos.x + s, pos.y + s), 2)
        pygame.draw.line(self.screen, color, (pos.x - s, pos.y + s), (pos.x + s, pos.y - s), 2)

    def _draw_debug_panel(self):
        panel_w = 340
        surf = pygame.Surface((panel_w, 250), pygame.SRCALPHA)
        surf.fill((10, 10, 14, 210))
        lines = []
        a = self.alien
        d = a.debug
        lines.append(f"STATE: {d.get('state')}")
        lines.append(f"suspicion: {d.get('suspicion')}")
        lines.append(f"last_seen_pos: {d.get('last_seen_position')}")
        lines.append(f"last_heard_pos: {d.get('last_heard_position')}")
        lines.append(f"current_target: {d.get('current_target')}")
        lines.append(f"vision_range: {d.get('vision_range')}  fov: {d.get('fov_deg')} deg")
        lines.append(f"path length (tiles): {d.get('path_len')}")
        lines.append(f"intent: {d.get('intent', '')}")
        lines.append("")
        probs = self.tracker.predicted_first_task()
        lines.append("learned P(first task):")
        for name, p in probs.items():
            lines.append(f"  {name}: {p:.2f}")
        lines.append(f"top hiding rooms: {self.tracker.top_hiding_rooms(3)}")

        y = 6
        for line in lines:
            txt = self.font_small.render(line, True, (230, 230, 230))
            surf.blit(txt, (8, y))
            y += 16
        self.screen.blit(surf, (C.SCREEN_W - panel_w - 10, 10))

    # -- transition / end screens --------------------------------------
    def _render_transition(self):
        self.presentation.transition()



if __name__ == "__main__":
    Game().run()
