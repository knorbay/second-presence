"""Manual door input, physical barriers and evidence-driven breaching."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
import math
import unittest
from unittest.mock import patch
import pygame
import config as C
from shipmap import ShipMap
from entities import Alien,Player,STATE_CHASE,STATE_WANDER,STATE_INVESTIGATE
from systems import NoiseSystem,BehaviorTracker,get_day_params
from pathfinding import find_path
from lighting import Lighting
from main import Game,PHASE_PLAYING
from localization import set_language,tr


class BarrierTests(unittest.TestCase):
    def setUp(self):
        self.ship=ShipMap();self.ship.set_day(3)
        self.doors=self.ship.doors;self.door=self.doors.doors[1]
        self.north=self.door.center-pygame.Vector2(0,48)
        self.south=self.door.center+pygame.Vector2(0,48)

    def close(self):return self.doors.toggle(self.door,[(self.south,C.PLAYER_RADIUS)])

    def test_closing_blocks_collision_sight_and_light_and_opening_restores_them(self):
        light=Lighting()
        self.assertTrue(self.ship.line_of_sight(*self.north,*self.south))
        self.assertGreater(light.strength_at(self.ship,self.north,math.pi/2,self.south,300),0)
        revision=self.ship.geometry_revision
        self.assertEqual(self.close(),'close')
        self.assertEqual(self.ship.geometry_revision,revision+1)
        self.assertTrue(self.ship.is_blocked_circle(*self.door.center,C.PLAYER_RADIUS))
        self.assertFalse(self.ship.line_of_sight(*self.north,*self.south))
        self.assertEqual(light.strength_at(self.ship,self.north,math.pi/2,self.south,300),0)
        self.doors.update(.7)
        self.assertEqual(self.doors.toggle(self.door,[(self.north,8)]),'open')
        self.assertFalse(self.ship.is_blocked_circle(*self.door.center,8))
        self.assertTrue(self.ship.line_of_sight(*self.north,*self.south))

    def test_all_handles_work_from_both_sides_when_closed(self):
        for door in self.doors.doors:
            north=door.center-pygame.Vector2(0,36);south=door.center+pygame.Vector2(0,36)
            self.assertFalse(self.ship.is_blocked_circle(*north,8),door.name)
            self.assertFalse(self.ship.is_blocked_circle(*south,8),door.name)
            self.assertEqual(self.doors.toggle(door,[(south,8)]),'close')
            self.assertIs(self.doors.nearby(north),door)
            self.assertIs(self.doors.nearby(south),door)
        with patch.object(self.ship,'line_of_sight',return_value=False):
            self.assertIsNone(self.doors.nearby(self.south))
        self.assertIsNone(self.doors.nearby(self.south+pygame.Vector2(0,100)))

    def test_door_will_not_close_on_either_actor(self):
        for actors in ([(self.door.center,8)],[(self.south,8),(self.door.center,9)]):
            self.assertEqual(self.doors.toggle(self.door,actors),'occupied')
            self.assertFalse(self.door.closed);self.assertEqual(self.doors.events,[])

    def test_lamp_lights_the_closed_material_without_revealing_the_world_behind_it(self):
        self.close();self.doors.update(.2)
        for origin,facing in ((self.north,math.pi/2),(self.south,-math.pi/2)):
            surface=pygame.Surface((C.WORLD_W,C.WORLD_H));surface.fill((0,0,0))
            self.doors.draw_front_faces(surface,0,origin,facing,Lighting(),300,1)
            self.assertGreater(sum(surface.get_at((self.door.rect.x+12,self.door.rect.centery))[:3]),0)
            behind=self.south if origin==self.north else self.north
            self.assertEqual(surface.get_at(tuple(map(int,behind)))[:3],(0,0,0))
        hidden=pygame.Surface((C.WORLD_W,C.WORLD_H));hidden.fill((0,0,0))
        with patch.object(self.ship,'line_of_sight',return_value=False):
            self.doors.draw_front_faces(hidden,0,self.south,-math.pi/2,Lighting(),300,1)
        self.assertEqual(hidden.get_at(self.door.rect.center)[:3],(0,0,0))

    def test_closed_gate_stops_real_player_motion(self):
        self.close();p=Player(self.ship,self.north)
        for _ in range(40):p.update(.05,{'s':True},NoiseSystem(),[],lambda _:None,BehaviorTracker())
        self.assertLessEqual(p.pos.y,self.door.rect.top-C.PLAYER_RADIUS)
        self.assertFalse(self.ship.is_blocked_circle(*p.pos,C.PLAYER_RADIUS))

    def test_path_planning_routes_around_doors_or_explicitly_plans_a_breach(self):
        self.close()
        ordinary=find_path(self.ship,self.north,self.south)
        hunter=find_path(self.ship,self.north,self.south,allow_closed_doors=True)
        self.assertTrue(ordinary);self.assertTrue(hunter)
        self.assertTrue(all(not self.ship.is_wall_world(*p) for p in ordinary))
        self.assertTrue(any(self.door.rect.collidepoint(p) for p in hunter))
        self.assertLess(len(hunter),len(ordinary))

    def test_hunter_prefers_an_open_short_detour_over_breaking_a_gate(self):
        self.close()
        # Add a three-tile bypass in this fixture to distinguish weighted costs.
        x,y,_,_=self.door.tiles
        for ty in range(y-1,y+2):self.ship.grid[ty][x-1]=0
        start=((x+.5)*C.TILE,(y-.5)*C.TILE);goal=((x+.5)*C.TILE,(y+1.5)*C.TILE)
        path=find_path(self.ship,start,goal,allow_closed_doors=True)
        self.assertTrue(path)
        self.assertFalse(any(self.door.rect.collidepoint(p) for p in path))

    def test_hunter_reaches_gate_then_spends_real_time_breaking_it(self):
        self.close();alien=Alien(self.ship,self.north)
        alien.state=STATE_CHASE;alien.current_target=self.south.copy()
        elapsed=0
        for _ in range(160):
            alien._follow_path(.05,get_day_params(3));elapsed+=.05
            self.assertFalse(self.ship.is_blocked_circle(*alien.pos,C.ALIEN_RADIUS))
            if self.door.closed:self.assertLess(alien.pos.y,self.door.rect.top)
            if self.door.broken:break
        self.assertTrue(self.door.broken)
        self.assertGreaterEqual(elapsed,self.doors.breach_time)
        self.assertIs(alien.attacking_door,self.door)
        for _ in range(30):alien._follow_path(.05,get_day_params(3))
        self.assertLess(alien.pos.distance_to(self.south),1)

    def test_remote_actor_cannot_damage_door_and_damage_survives_manual_toggle(self):
        self.close();self.assertFalse(self.doors.force(self.door,self.north,10))
        self.assertEqual(self.door.damage,0)
        contact=self.door.center-pygame.Vector2(0,24)
        self.doors.force(self.door,contact,1);damage=self.door.damage
        self.doors.update(.7);self.doors.toggle(self.door,[(self.south,8)])
        self.assertFalse(self.doors.force(self.door,contact,5))
        self.doors.update(.7);self.doors.toggle(self.door,[(self.south,8)])
        self.assertEqual(self.door.damage,damage)

    def test_broken_door_stays_open_until_next_shift_without_a_softlock(self):
        self.close();contact=self.door.center-pygame.Vector2(0,24)
        self.assertTrue(self.doors.force(self.door,contact,self.doors.breach_time))
        self.assertFalse(self.door.closed);self.assertEqual(self.doors.toggle(self.door,[]),'broken')
        for day in range(1,9):
            self.ship.set_day(day)
            self.assertTrue(all(not d.closed and not d.broken and not d.damage for d in self.doors.doors))
            spawn=self.ship.room_by_name('Quarters').world_center
            for room in self.ship.rooms:self.assertTrue(find_path(self.ship,spawn,room.world_center),(day,room.name))

    def test_geometry_change_replans_immediately_even_with_a_live_path_timer(self):
        self.close();alien=Alien(self.ship,self.north)
        alien.state=STATE_CHASE;alien.current_target=self.south.copy()
        alien._follow_path(.01,get_day_params(3))
        old_revision=alien._path_geometry_revision
        self.doors.update(.7);self.doors.toggle(self.door,[(self.south,8)])
        alien._follow_path(.01,get_day_params(3))
        self.assertGreater(alien._path_geometry_revision,old_revision)
        self.assertEqual(alien._path_geometry_revision,self.ship.geometry_revision)

    def test_close_event_origin_is_the_operator_and_consumed_once(self):
        self.close();event=self.doors.drain_events()
        self.assertEqual(event,[('close',self.south)])
        self.south.x+=50;self.assertNotEqual(event[0][1],self.south)
        self.assertEqual(self.doors.drain_events(),[])


class DoorIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.g=Game(campaign_seed=0)
    @classmethod
    def tearDownClass(cls):set_language('tr');pygame.quit()
    def setUp(self):
        g=self.g;g.paused=False;g.audio.pause(False);g._restart_game(campaign_seed=0)
        g.day=3;g._start_day();g.day_time=90;g.phase=PHASE_PLAYING;g._keys=lambda:{}
        self.door=g.ship_map.doors.doors[1]
        g.player.pos=self.door.center+pygame.Vector2(0,36)
        g.alien.pos=self.door.center-pygame.Vector2(0,48)
        g.alien.state=STATE_WANDER;g.alien.facing_angle=-math.pi/2
        pygame.event.clear()

    def press(self,key,repeat=False):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=key,repeat=repeat));self.g._handle_events()

    def test_real_b_input_emits_noise_that_the_hunter_hears(self):
        g=self.g
        with patch.object(g.audio,'play_at') as sound:
            self.press(pygame.K_b);g._update(.05)
        self.assertTrue(self.door.closed)
        self.assertEqual(len([e for e in g.noise.events if e.kind=='door']),1)
        self.assertIsNotNone(g.alien.last_heard_position)
        self.assertEqual(g.alien.state,STATE_INVESTIGATE)
        self.assertTrue(any(call.args[0]=='latch' for call in sound.call_args_list))
        g.alien.pos=g.ship_map.room_by_name('Hangar').world_center.copy()
        g._update(.7);self.press(pygame.K_b);g._update(.01)
        self.assertFalse(self.door.closed)

    def test_repeat_pause_map_and_reading_cannot_toggle_a_door(self):
        g=self.g
        self.press(pygame.K_b,repeat=True);g._update(.01);self.assertFalse(self.door.closed)
        for attribute in ('paused','show_map'):
            setattr(g,attribute,True);self.press(pygame.K_b);g._update(.01)
            self.assertFalse(self.door.closed);setattr(g,attribute,False)
        g.logbook.open=True;self.press(pygame.K_b);g._update(.01)
        self.assertFalse(self.door.closed)

    def test_hostile_hits_play_once_and_do_not_feed_back_into_alien_hearing(self):
        g=self.g;doors=g.ship_map.doors
        doors.toggle(self.door,[(g.player.pos,8)]);g._process_door_events();g.noise.clear()
        doors.force(self.door,self.door.center-pygame.Vector2(0,24),.1)
        with patch.object(g.audio,'play_at') as sound:
            g._process_door_events();g._process_door_events()
        self.assertEqual(sound.call_count,1);self.assertEqual(g.heard_message,'... metal zorlanıyor')
        self.assertEqual(g.noise.events[0].kind,'alien_door')
        g.alien.suspicion=0;g.alien.last_heard_position=None
        heard=g.alien._update_hearing(g.noise,g.ship_map,g.tracker,get_day_params(3))
        self.assertIsNone(heard);self.assertEqual(g.alien.suspicion,0)

    def test_pause_freezes_breach_and_day_reset_keeps_five_tasks(self):
        g=self.g;doors=g.ship_map.doors
        doors.toggle(self.door,[(g.player.pos,8)]);doors.force(self.door,self.door.center-pygame.Vector2(0,24),.5)
        g.paused=True;g._update(5);self.assertEqual(self.door.damage,.5)
        g.day=3;g._start_day();self.assertFalse(self.door.closed);self.assertEqual(self.door.damage,0)
        self.assertEqual(len(g.tasks.tasks),5)

    def test_closed_geometry_refreshes_the_world_and_map_and_translates_feedback(self):
        g=self.g;doors=g.ship_map.doors
        doors.toggle(self.door,[(g.player.pos,8)]);doors.update(.2)
        g.camera=g.camera_target();g.player.facing=pygame.Vector2(0,-1)
        for code in ('tr','en'):
            set_language(code);g._render();g.show_map=True;g._render();g.show_map=False
        self.assertEqual(g.presentation.geometry_revision,g.ship_map.geometry_revision)
        self.assertEqual(tr('B: Kapıyı aç'),'B: Open door')
        self.assertEqual(tr('... kapı parçalandı'),'... door breached')
        set_language('tr')


if __name__=='__main__':unittest.main()
