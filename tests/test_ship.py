"""Ship conditions and perception-based tactical AI regressions."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
import random
import unittest
from unittest.mock import patch
import pygame
import config as C
from survival import ShipConditions,conditions_for
from shipmap import ShipMap
from systems import NoiseSystem,BehaviorTracker,get_day_params
from entities import Player,Alien,STATE_CHASE,STATE_INVESTIGATE
from main import Game,PHASE_PLAYING,PHASE_GAME_OVER


class TacticalAITests(unittest.TestCase):
    def setUp(self):
        self.ship=ShipMap();self.noise=NoiseSystem();self.tracker=BehaviorTracker()

    def test_loud_sound_is_investigated_without_visual_contact(self):
        a=Alien(self.ship,(780,852));p=Player(self.ship,self.ship.room_by_name('Cooling').world_center)
        self.noise.emit((860,852),340,30,'repair')
        a.update(.05,p,self.ship,self.noise,self.tracker,3,90,0)
        self.assertEqual(a.state,STATE_INVESTIGATE)
        self.assertIsNone(a.last_seen_position)
        self.assertIsNotNone(a.current_target)
        self.assertFalse(self.ship.is_wall_world(*a.current_target))

    def test_chase_repath_does_not_walk_backward_to_tile_centers(self):
        a=Alien(self.ship,(972,564));p=Player(self.ship,(1080,564))
        a.facing_angle=0;a.suspicion=100
        previous=a.pos.x
        for i in range(50):
            p.pos.x+=C.WALK_SPEED*.05
            self.noise.clear()
            a.update(.05,p,self.ship,self.noise,self.tracker,3,90,i*.05)
            self.assertGreaterEqual(a.pos.x,previous-.01)
            previous=a.pos.x
        self.assertEqual(a.state,STATE_CHASE)
        self.assertGreater(a.pos.x,1100)

    def test_search_projects_last_observed_motion(self):
        a=Alien(self.ship,(528,564));p=Player(self.ship,(600,564));a.facing_angle=0
        a._update_vision(p,self.ship,get_day_params(5),0,.05)
        p.pos.x+=8;a._update_vision(p,self.ship,get_day_params(5),.05,.05)
        origin=a.last_seen_position.copy()
        p.pos=self.ship.room_by_name('Oxygen').world_center.copy()
        a._update_vision(p,self.ship,get_day_params(5),.1,.05)
        points=a._build_search_waypoints(self.ship,self.tracker,get_day_params(5),origin)
        self.assertEqual(points[0],origin)
        self.assertGreater(points[1].x,origin.x+40)
        self.assertEqual(a.last_seen_position,origin)

    def test_search_budget_includes_travel_and_locker_visits(self):
        point=self.ship.room_by_name('Power').world_center.copy()
        self.ship.lockers={'Power':point+pygame.Vector2(-70,25)}
        a=Alien(self.ship,point)
        a._begin_search_area(self.ship,self.tracker,get_day_params(5),point)
        self.assertTrue(any(p.distance_to(self.ship.lockers['Power'])<1 for p in a.search_area))
        self.assertGreater(a._search_timer,18)

    def test_learned_next_task_changes_later_patrol_distribution(self):
        self.tracker.task_order_history=[['Power','Cooling']]*4
        self.tracker.first_task_counts['Power']=4
        self.assertEqual(self.tracker.next_task_after('Power'),['Cooling'])
        a=Alien(self.ship,self.ship.room_by_name('Power').world_center)
        a._day_time=150
        state=random.getstate();random.seed(18)
        try:
            choices=[a._pick_wander_room(self.ship,self.tracker,get_day_params(7),7).name for _ in range(200)]
        finally:random.setstate(state)
        self.assertGreater(choices.count('Cooling'),40)


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.g=Game(campaign_seed=0)
    @classmethod
    def tearDownClass(cls):pygame.quit()
    def setUp(self):
        self.g.paused=False;self.g._restart_game(campaign_seed=0);self.g._advance_from_transition();self.g._keys=lambda:{}

    def test_camera_scrolls_and_world_exceeds_viewport(self):
        self.assertGreater(C.WORLD_W,C.SCREEN_W)
        self.g.player.pos=self.g.ship_map.room_by_name('Cooling').world_center.copy()
        for _ in range(30):self.g._update(.05)
        self.assertGreater(self.g.camera.x,1000)
        self.assertLessEqual(self.g.camera.x,C.WORLD_W-C.CAMERA_W)
        self.g._render()
        self.assertEqual(self.g.screen.get_size(),(C.SCREEN_W,C.SCREEN_H))

    def test_a_physically_inspected_unseen_locker_can_reveal_player(self):
        g=self.g;g.day=5;g._start_day();g.day_time=90;g.alien.state='WANDER';g.phase=PHASE_PLAYING
        g.player.pos=g.lockers['Quarters'].copy()
        g.alien.pos=g.ship_map.room_by_name('Cooling').world_center.copy()
        g._toggle_hiding()
        self.assertIsNone(g.alien.last_seen_position)
        g.alien.pos=g.player.pos-pygame.Vector2(12,0)
        g.alien.inspect_spot='Quarters'
        g._update(.05)
        self.assertEqual(g.phase,PHASE_GAME_OVER)

    def test_a_real_fault_reopens_a_repaired_system(self):
        g=self.g;g.day=6;g._start_day();g.phase=PHASE_PLAYING
        room=g.ship_map.room_by_name('Power')
        g.tasks.complete_task('Power',1)
        g.sabotage_cooldown=0
        with patch('main.random.random',side_effect=[.1,.9]),patch('main.random.choice',return_value=room),patch.object(g.audio,'play'):
            g._update_alarms(.1)
        self.assertFalse(g.tasks.tasks['Power'].done)
        self.assertTrue(g.alarms[0].real)

    def test_reopened_fault_does_not_rewrite_first_task_learning(self):
        g=self.g
        g.tasks.complete_task('Power',1);g.tasks.complete_task('Cooling',2)
        g.tasks.tasks['Power'].reopen();g.tasks.complete_task('Power',3)
        g.tracker.end_day(g.tasks)
        self.assertEqual(g.tracker.task_order_history[-1],['Power','Cooling'])
        self.assertEqual(g.tracker.most_likely_first_task_room(),'Power')

    def test_late_day_spawn_uses_committed_first_task_prior(self):
        g=self.g
        g.tracker.first_task_counts['Oxygen']=3
        g.tracker.task_order_history=[['Oxygen','Power']]*3
        g.day=4
        with patch('main.random.random',return_value=0):
            room=g._pick_alien_spawn_room()
        self.assertEqual(room.name,'Oxygen')



if __name__=='__main__':unittest.main()
