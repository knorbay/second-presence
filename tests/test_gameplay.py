"""Headless gameplay regressions. Run: python -m unittest discover -s tests -v"""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import math
import unittest
import pygame
import config as C
import fov
from main import Game, PHASE_PLAYING, PHASE_DAY_TRANSITION, PHASE_GAME_OVER, PHASE_GAME_WON
from entities import Player, Alien, STATE_CHASE, STATE_INVESTIGATE, STATE_SEARCH_LAST_SEEN, STATE_SEARCH_AREA, STATE_WANDER
from systems import NoiseSystem, BehaviorTracker, TaskSystem, get_day_params
from shipmap import ShipMap
from pathfinding import find_path


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.ship = ShipMap()
        self.noise = NoiseSystem()
        self.tracker = BehaviorTracker()

    def test_ship_is_connected_and_service_route_has_two_exits(self):
        self.assertEqual(self.ship.connected_component_size(self.ship.room_by_name('Quarters').tile_center),self.ship.total_floor_tiles())
        self.assertFalse(self.ship.is_wall_tile(20,8))
        for room in self.ship.rooms:
            self.assertTrue(find_path(self.ship, tuple(self.ship.room_by_name('Quarters').world_center), tuple(room.world_center)))

    def test_diagonal_circle_collision(self):
        # Corner of a wall tile: cardinal-only checks miss this overlap.
        self.ship.grid = [[0]*C.COLS for _ in range(C.ROWS)]
        self.ship.grid[5][5] = 1
        self.assertTrue(self.ship.is_blocked_circle(115,115,8))
        self.assertFalse(self.ship.is_blocked_circle(113,113,8))

    def test_main_gallery_requires_a_turn_and_has_no_end_to_end_sightline(self):
        start=(468,564);end=(996,564)
        for day in range(1,9):
            self.ship.set_day(day)
            self.assertFalse(self.ship.line_of_sight(*start,*end))
            route=find_path(self.ship,start,end)
            self.assertTrue(route)
            self.assertTrue(any(y>=27*C.TILE for x,y in route))
            self.assertTrue(all(not self.ship.is_blocked_circle(x,y,C.ALIEN_RADIUS) for x,y in route))
            alien=Alien(self.ship,start);alien.state=STATE_CHASE
            alien.current_target=pygame.Vector2(end)
            for _ in range(240):
                alien._follow_path(.05,get_day_params(3))
                self.assertFalse(self.ship.is_blocked_circle(*alien.pos,C.ALIEN_RADIUS))
                if alien.pos.distance_to(end)<1:break
            self.assertLess(alien.pos.distance_to(end),1)

    def test_noise_position_is_a_snapshot(self):
        pos = pygame.Vector2(150,630)
        self.noise.emit(pos,100,20,'run')
        pos.x += 100
        self.assertEqual(self.noise.events[0].pos,pygame.Vector2(150,630))

    def test_hearing_target_is_reachable_even_if_noise_estimate_is_in_wall(self):
        a=Alien(self.ship,self.ship.room_by_name('Quarters').world_center)
        a.last_heard_position=pygame.Vector2(270,828)
        self.assertTrue(self.ship.is_wall_world(*a.last_heard_position))
        a._enter_investigate()
        self.assertFalse(self.ship.is_wall_world(*a.current_target))
        for _ in range(600):
            a._follow_path(1/60,get_day_params(3))
        self.assertTrue(a._arrived_at(a.current_target))

    def test_ai_uses_only_previous_days_for_route_and_hiding_priors(self):
        q=self.ship.room_by_name('Quarters');p=self.ship.room_by_name('Power')
        self.tracker.start_day()
        self.tracker.on_room_entered(q); self.tracker.on_room_entered(p)
        self.tracker.on_player_lost(p)
        self.tracker.on_chase_flee_direction(q,'Power')
        self.assertEqual(self.tracker.frequent_routes_from('Quarters'),[])
        self.assertEqual(self.tracker.top_hiding_rooms(),[])
        self.assertIsNone(self.tracker.preferred_escape_direction('Quarters'))
        self.tracker.end_day(TaskSystem(self.ship));self.tracker.start_day()
        self.assertEqual(self.tracker.frequent_routes_from('Quarters'),['Power'])
        self.assertEqual(self.tracker.top_hiding_rooms(),['Power'])
        self.assertEqual(self.tracker.preferred_escape_direction('Quarters'),'Power')

    def test_ai_does_not_follow_player_through_wall_after_losing_sight(self):
        a=Alien(self.ship,(528,564));p=Player(self.ship,(600,564))
        a.facing_angle=0;a.suspicion=100
        a.update(.05,p,self.ship,self.noise,self.tracker,3,90,0)
        self.assertEqual(a.state,STATE_CHASE)
        seen=a.last_seen_position.copy()
        p.pos=self.ship.room_by_name('Oxygen').world_center.copy()
        for i in range(13):
            a.update(.05,p,self.ship,self.noise,self.tracker,3,90,(i+1)*.05)
        self.assertEqual(a.last_seen_position,seen)
        self.assertIn(a.state,(STATE_SEARCH_LAST_SEEN,STATE_SEARCH_AREA))
        self.assertEqual(a.current_target,seen)

    def test_crouch_is_quieter_and_slower_than_walking(self):
        p=Player(self.ship,(852,828))
        p.update(.1,{'d':True,'ctrl':True},self.noise,[],lambda _:None,self.tracker)
        self.assertAlmostEqual(p.pos.x,858.5)
        self.assertEqual(self.noise.events[0].kind,'crouch')
        self.assertEqual(self.noise.events[0].radius,C.NOISE_RADIUS_CROUCH)
        self.assertFalse(p.sprinting)

    def test_repair_cannot_reach_through_a_wall(self):
        self.ship.grid = [[0]*C.COLS for _ in range(C.ROWS)]
        p=Player(self.ship,(108,132))
        self.ship.grid[5][5]=1
        self.assertIsNone(p._nearby_interactable([{'name':'Power','point':pygame.Vector2(156,132),'done':False}]))

    def test_escape_sequence_is_strict(self):
        tasks=TaskSystem(self.ship)
        self.assertFalse(tasks.day8_advance('Hangar'))
        self.assertFalse(tasks.day8_complete)
        for name in C.DAY8_SEQUENCE:
            self.assertTrue(tasks.day8_advance(name))
        self.assertTrue(tasks.day8_complete)
        self.assertFalse(tasks.day8_advance('Hangar'))


class GameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game=Game(campaign_seed=0)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.g=self.game
        self.g.paused=False
        self.g._restart_game(campaign_seed=0)
        self.g._advance_from_transition()
        self.g._keys=lambda:{}

    def test_timeout_costs_integrity_and_eventually_loses(self):
        for expected in (60,20):
            self.g.day_time=self.g.day_length
            self.g._update(.01)
            self.assertEqual(self.g.integrity,expected)
            self.assertEqual(self.g.phase,PHASE_DAY_TRANSITION)
            self.g._advance_from_transition()
        self.g.day_time=self.g.day_length
        self.g._update(.01)
        self.assertEqual(self.g.phase,PHASE_GAME_OVER)
        self.assertEqual(self.g.integrity,0)

    def test_full_repairs_preserve_integrity_and_eight_day_escape_wins(self):
        for day in range(1,8):
            self.assertEqual(self.g.day,day)
            for name in self.g.tasks.tasks:
                while not self.g.tasks.tasks[name].done:self.g._on_interact_complete(name)
            self.g._update(.01)
            self.g._advance_from_transition()
        self.assertEqual(self.g.integrity,100)
        self.assertEqual(self.g.day,8)
        for name in C.DAY8_SEQUENCE:
            self.g._on_interact_complete(name)
        self.g._update(.01)
        self.assertEqual(self.g.phase,PHASE_GAME_WON)

    def test_holding_e_opens_panel_but_does_not_complete_and_movement_cancels(self):
        self.g.player.pos=self.g.ship_map.room_by_name('Power').world_center.copy()
        self.g._keys=lambda:{'e':True}
        for _ in range(80):self.g._update(.05)
        self.assertFalse(self.g.tasks.tasks['Power'].done)
        self.assertIsNotNone(self.g.panel_work)
        self.g._keys=lambda:{'a':True}
        self.g._update(.05)
        self.assertIsNone(self.g.panel_work)
        self.g._keys=lambda:{'e':True}
        self.g._update(.05)
        self.g.panel_inputs=[str(self.g.panel_work.fault+1)]
        self.g._keys=lambda:{}
        self.g._update(.05)
        self.assertFalse(self.g.tasks.tasks['Power'].done)
        self.assertEqual(self.g.tasks.tasks['Power'].step,1)

    def test_pause_freezes_all_simulation(self):
        self.g._throw_decoy()
        self.g.paused=True
        before=(self.g.day_time,self.g.sim_time,self.g.decoys[0]['timer'])
        self.g._update(10)
        self.assertEqual((self.g.day_time,self.g.sim_time,self.g.decoys[0]['timer']),before)

    def test_decoys_have_delay_and_limited_charges(self):
        for _ in range(4): self.g._throw_decoy()
        self.assertEqual(self.g.decoy_charges,0)
        self.assertEqual(len(self.g.decoys),3)
        self.g.noise.clear(); self.g._update_decoys(.5)
        self.assertEqual(self.g.noise.events,[])
        self.g._update_decoys(.51)
        self.assertEqual(len(self.g.noise.events),3)
        self.assertTrue(all(e.kind=='decoy' for e in self.g.noise.events))
        self.assertTrue(all(not self.g.ship_map.is_wall_world(*d['point']) for d in self.g.decoys))

    def test_unseen_locker_entry_protects_player(self):
        self.g.day=3
        self.g.player.pos=self.g.lockers['Quarters'].copy()
        self.g.alien.pos=self.g.ship_map.room_by_name('Cooling').world_center.copy()
        self.g._toggle_hiding()
        self.assertTrue(self.g.player.hidden)
        self.g.alien.pos=self.g.player.pos.copy()
        self.g.alien.suspicion=100;self.g.alien.state=STATE_WANDER
        self.g._update(.05)
        self.assertEqual(self.g.phase,PHASE_PLAYING)
        self.assertFalse(self.g.player.caught)
        self.g._toggle_hiding()
        self.assertFalse(self.g.player.hidden)

    def test_witnessed_locker_entry_can_be_caught(self):
        self.g.day=3;self.g.day_time=90
        point=self.g.lockers['Quarters']
        self.g.player.pos=point.copy()
        self.g.alien.pos=point-pygame.Vector2(25,0)
        self.g.alien.facing_angle=0;self.g.alien.state=STATE_CHASE
        self.g.alien.suspicion=100
        self.g._toggle_hiding()
        self.assertEqual(self.g.alien.observed_hiding_spot,'Quarters')
        for _ in range(60):
            if self.g.phase!=PHASE_PLAYING:break
            self.g._update(.05)
        self.assertEqual(self.g.phase,PHASE_GAME_OVER)

    def test_fog_keeps_unseen_area_opaque_and_explored_area_dim(self):
        self.g.presentation.explored.fill((0,0,0,255))
        self.g._render()
        old=self.g.player.pos.copy()
        self.assertEqual(self.g.presentation.fog.get_at(tuple(map(int,self.g.ship_map.room_by_name('Cooling').world_center))).a,255)
        self.assertLess(self.g.presentation.fog.get_at(tuple(map(int,old))).a,90)
        self.g.player.pos=self.g.ship_map.room_by_name('Cooling').world_center.copy()
        self.g._render()
        self.assertEqual(self.g.presentation.fog.get_at(tuple(map(int,old))).a,242)

    def test_restart_clears_summary_and_supplies(self):
        self.g.last_day_summary={'day':7,'order':[]}
        self.g.integrity=20; self.g.decoy_charges=0
        self.g._restart_game(campaign_seed=0)
        self.assertIsNone(self.g.last_day_summary)
        self.assertEqual(self.g.integrity,100)
        self.assertEqual(self.g.decoy_charges,3)
        self.assertEqual(self.g.phase,PHASE_DAY_TRANSITION)

    def test_render_every_day_phase_and_overlay(self):
        for day in range(1,9):
            self.g.day=day;self.g._start_day()
            self.g.phase=PHASE_DAY_TRANSITION;self.g._render()
            self.g._advance_from_transition();self.g._render()
            self.g.debug=True;self.g._render();self.g.debug=False
            self.g.show_map=True;self.g._render();self.g.show_map=False
            self.g.paused=True;self.g._render();self.g.paused=False
        for phase in (PHASE_GAME_OVER,PHASE_GAME_WON):
            self.g.phase=phase;self.g._render()


if __name__=='__main__':
    unittest.main()
