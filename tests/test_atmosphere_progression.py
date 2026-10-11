"""Task dependencies, retained progress, language switching, sound layers and AI motion."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
import math
import unittest
from unittest.mock import patch
import pygame
import config as C
from systems import TaskSystem,NoiseSystem,BehaviorTracker,get_day_params
from shipmap import ShipMap
from maintenance import PanelWork
from entities import Alien,Player,STATE_CHASE,STATE_INVESTIGATE
from main import Game,PHASE_PLAYING
from localization import language,set_language,tr

class ProgressionTests(unittest.TestCase):
    def setUp(self):self.ship=ShipMap();self.tasks=TaskSystem(self.ship)
    def test_priority_dependency_blocks_direct_completion(self):
        self.assertEqual(self.tasks.blocked_by('Cooling'),['Power'])
        self.assertFalse(self.tasks.complete_task('Cooling',1))
        self.assertFalse(self.tasks.advance_task('Reactor',1))
        self.assertTrue(self.tasks.complete_task('Power',2))
        self.assertEqual(self.tasks.blocked_by('Reactor'),['Cooling'])
        self.assertTrue(self.tasks.complete_task('Cooling',3))
        self.assertTrue(self.tasks.available('Reactor'))
    def test_one_minigame_does_not_finish_a_multistage_job(self):
        task=self.tasks.tasks['Power']
        self.assertFalse(self.tasks.advance_task('Power',1))
        self.assertEqual(task.step,1);self.assertFalse(task.done)
        while not task.done:self.tasks.advance_task('Power',2)
        self.assertTrue(self.tasks.available('Cooling'))
    def test_internal_parameters_change_with_day_and_revision(self):
        a=PanelWork('Power','wires',1,0);b=PanelWork('Power','wires',1,1)
        self.assertNotEqual((a.readings,a.target,a.pattern),(b.readings,b.target,b.pattern))
        self.assertEqual(a.readings,PanelWork('Power','wires',1,0).readings)
    def test_wide_main_corridor_is_connected_after_all_bulkhead_closures(self):
        for day in range(1,9):
            self.ship.set_day(day)
            for ty in range(21,27):self.assertFalse(self.ship.is_wall_tile(45,ty))
            self.assertEqual(self.ship.connected_component_size((7,35)),self.ship.total_floor_tiles())

class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.g=Game(campaign_seed=0)
    @classmethod
    def tearDownClass(cls):set_language('tr');pygame.quit()
    def setUp(self):
        set_language('tr');g=self.g;g.paused=False;g._restart_game(campaign_seed=0);g._advance_from_transition();g._keys=lambda:{}
    def open(self,name):
        g=self.g;g.player.pos=g.ship_map.room_by_name(name).world_center.copy();g._e_pressed=True;g._update_panel(.01,{})
    def test_locked_panel_has_a_reason_and_no_work_session(self):
        self.open('Cooling');g=self.g
        self.assertIsNone(g.panel_work);self.assertIn('Güç',g.notification)
        self.assertEqual(g.tasks.tasks['Cooling'].step,0)
    def test_partially_connected_wires_survive_closing_and_reopening(self):
        g=self.g;g.tasks.advance_task('Power',0);self.open('Power');w=g.panel_work
        w.act('wire_start',0);w.act('wire_end',w.wire_goal[0]);g._cancel_panel();self.open('Power')
        self.assertIs(g.panel_work,w);self.assertEqual(w.connected,{0})
        self.assertIsNone(w.dragging)
    def test_reopened_power_fault_locks_later_work_and_discards_old_session(self):
        g=self.g;g.tasks.complete_task('Power',0);self.open('Cooling');self.assertIsNotNone(g.panel_work)
        g.tasks.tasks['Power'].reopen();g._update_panel(.01,{})
        self.assertIsNone(g.panel_work);self.assertEqual(g.tasks.blocked_by('Cooling'),['Power'])
    def test_language_key_and_menu_buttons_switch_without_restarting(self):
        g=self.g;time=g.day_time
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_l));g._handle_events()
        self.assertEqual(language(),'en');self.assertEqual(tr('GÜN 3'),'DAY 3')
        self.assertEqual(tr('Önce: Güç'),'First: Power')
        self.assertEqual(tr('Görev tamamlandı: Soğutma'),'Task complete: Cooling')
        self.assertEqual(g.day_time,time)
        g.paused=True;rect=g.presentation.language_rects()[0][1]
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=rect.center));g._handle_events()
        self.assertEqual(language(),'tr');self.assertEqual(tr('Güç'),'Güç')
    def test_environment_has_three_layers_and_mute_pause_controls_them(self):
        a=self.g.audio;self.assertTrue(a.available);self.assertEqual(set(a.layers),{'vent','engine','hull'})
        a.enabled=True;a.pause(False);a.environment(.2,'Reactor',4,False)
        bright=dict(a.layer_volumes);self.assertTrue(all(v>0 for v in bright.values()))
        a.pause(True);a.environment(10,'Reactor',4,True)
        self.assertEqual(a.layer_volumes,bright)
        a.pause(False);a.toggle();self.assertFalse(a.enabled)
        self.assertTrue(all(not channel.get_busy() for channel,sound in a.layers.values()))
        a.toggle();a.environment(.1,'Reactor',4,False)
        self.assertTrue(all(channel.get_busy() for channel,sound in a.layers.values()))

class HuntingTests(unittest.TestCase):
    def setUp(self):
        self.ship=ShipMap();self.noise=NoiseSystem();self.tracker=BehaviorTracker()
    def test_movement_spends_full_budget_across_tile_centres(self):
        a=Alien(self.ship,(1200,564));a.state=STATE_CHASE;a.current_target=pygame.Vector2(1500,564)
        start=a.pos.copy();a._follow_path(.2,get_day_params(3))
        self.assertAlmostEqual(a.pos.distance_to(start),C.ALIEN_CHASE_SPEED*.2,places=4)
        self.assertFalse(self.ship.is_blocked_circle(*a.pos,C.ALIEN_RADIUS))
    def test_weak_noise_does_not_reset_investigation_path(self):
        a=Alien(self.ship,(1200,564));a.last_heard_position=pygame.Vector2(1440,564);a._heard_recently=True;a._enter_investigate()
        a.path=[(1308,564),(1332,564)];original=list(a.path);a._heard_recently=False
        p=Player(self.ship,(1200,852))
        a._run_state_machine(.01,p,self.ship,self.tracker,get_day_params(3),False,pygame.Vector2(1290,564),3,0)
        self.assertEqual(a.path,original)
    def test_chase_leads_observed_motion_but_stops_using_it_after_losing_sight(self):
        a=Alien(self.ship,(1200,564));p=Player(self.ship,(1340,564))
        a.state=STATE_CHASE;a.last_seen_position=p.pos.copy();a.last_seen_velocity=pygame.Vector2(118,0)
        a._run_state_machine(.01,p,self.ship,self.tracker,get_day_params(3),True,None,3,0)
        self.assertGreater(a.current_target.x,a.last_seen_position.x)
        p.pos=pygame.Vector2(2200,100)
        a._run_state_machine(1,p,self.ship,self.tracker,get_day_params(3),False,None,3,1)
        self.assertEqual(a.current_target,a.last_seen_position)
        self.assertNotEqual(a.current_target,p.pos)

    def test_observed_stop_clears_velocity_before_new_chase_prediction(self):
        a=Alien(self.ship,(1200,564));p=Player(self.ship,(1300,564));a.facing_angle=0
        a._update_vision(p,self.ship,get_day_params(3),0,.05)
        p.pos.x+=5;a._update_vision(p,self.ship,get_day_params(3),.05,.05)
        self.assertGreater(a.last_seen_velocity.x,0)
        a._update_vision(p,self.ship,get_day_params(3),.1,.05)
        self.assertEqual(a.last_seen_velocity,pygame.Vector2())
