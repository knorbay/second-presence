import math
import os
import tempfile
import unittest
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
import config as C
from main import Game,PHASE_PLAYING,PHASE_DAY_TRANSITION
from entities import Alien,STATE_WANDER,STATE_CHASE
from systems import get_day_params
from maintenance import PanelWork
from game_storage import SaveStore
from survival import ShipConditions
from pathfinding import find_path,segment_clear,smooth_path
from localization import language


class MenuAndSaveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.g=Game(self.temp.name,campaign_seed=0)
        pygame.event.clear()
    def tearDown(self):self.temp.cleanup()
    def click(self,rect):
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=rect.center));self.g._handle_events()
    def finish_loading(self):
        for _ in range(16):self.g._update(.05)
    def test_new_load_pause_settings_work_without_advancing_world(self):
        g=self.g;self.assertEqual(g.phase,'MAIN_MENU');self.assertIsNone(g.menu.save_summary)
        before=g.sim_time;g._update(.5);self.assertEqual(g.sim_time,before)
        self.click(g.menu.buttons()[0][2]);self.assertEqual(g.phase,'LOADING')
        self.finish_loading();self.assertEqual(g.phase,PHASE_DAY_TRANSITION)
        g._advance_from_transition();g.day_time=42;g.integrity=84
        g.paused=True;g.audio.pause(True)
        self.click(g.menu.buttons()[1][2]);self.assertEqual(g.store.read()['integrity'],84)
        self.click(g.menu.buttons()[2][2]);self.assertEqual(g.phase,'SETTINGS')
        position=g.player.pos.copy();g._update(1);self.assertEqual(g.player.pos,position);self.assertEqual(g.day_time,42)
        g.menu.adjust('volume',g.menu.slider('volume').x+g.menu.slider('volume').w*.4)
        g.menu.change_language('en');g.menu.back();self.assertTrue(g.paused);self.assertEqual(g.phase,PHASE_PLAYING)
        self.assertAlmostEqual(g.store.settings()['volume'],.4);self.assertEqual(language(),'en')
        self.click(g.menu.buttons()[3][2]);self.assertEqual(g.phase,'MAIN_MENU')
        g.integrity=3;self.click(g.menu.buttons()[1][2]);self.finish_loading()
        self.assertEqual(g.phase,PHASE_PLAYING);self.assertFalse(g.paused);self.assertEqual(g.integrity,84)
    def test_partial_instruments_learning_hiding_doors_and_decoys_survive_load(self):
        g=self.g;g._advance_from_transition();g.day=4;g._start_day();g.phase=PHASE_PLAYING
        task=g.tasks.tasks['Power'];task.step=1
        work=PanelWork('Power',task.operation,g.day,task.step);work.bits[0]=1-work.bits[0]
        task.sessions[(task.step,task.revision)]=work
        g.tracker.route_counts[('Power','Cooling')]=4;g.tracker._pending_routes[('Reactor','Oxygen')]=2
        g.tracker.task_order_history=[['Power','Cooling']]
        g.logbook.found={'shift','glass'}
        g.player.hidden=True;g.player.hidden_spot='Quarters';g.player.pos=g.lockers['Quarters'].copy()
        door=g.ship_map.doors.doors[1];g.ship_map.doors._set_closed(door,True);door.damage=.7
        g._throw_decoy();g.player.hidden=False;g._throw_decoy();g.player.hidden=True
        g.alien.last_heard_position=pygame.Vector2(120,132)
        g.alien._chase_start_room=g.ship_map.room_by_name('Power')
        self.assertTrue(g.store.save(g));g.store.load(g)
        self.assertEqual(g.tasks.tasks['Power'].sessions[(1,0)].bits,work.bits)
        self.assertEqual(g.tracker.route_counts[('Power','Cooling')],4)
        self.assertEqual(g.tracker._pending_routes[('Reactor','Oxygen')],2)
        self.assertTrue(g.player.hidden);self.assertEqual(g.player.hidden_spot,'Quarters')
        self.assertTrue(g.ship_map.doors.doors[1].closed);self.assertAlmostEqual(g.ship_map.doors.doors[1].damage,.7)
        self.assertEqual(g.alien.last_heard_position,pygame.Vector2(120,132))
        self.assertEqual(g.alien._chase_start_room.name,'Power');self.assertEqual(len(g.decoys),1)
        self.assertEqual(g.logbook.found,{'shift','glass'})
        g._update(.05);g._render()
    def test_corrupt_file_is_unavailable_and_does_not_replace_world(self):
        g=self.g;g.store.root.mkdir(exist_ok=True);g.store.path.write_text('{"schema":1,"day":99}')
        self.assertIsNone(g.store.summary());position=g.player.pos.copy()
        with self.assertRaises(ValueError):g.store.load(g)
        self.assertEqual(g.player.pos,position)
    def test_escape_panel_and_previous_campaign_are_preserved(self):
        g=self.g;g.day=8;g._start_day();g.phase=PHASE_PLAYING
        g.tasks.day8_step=2
        g.panel_work=PanelWork('Hangar','repair',8);g.panel_work.stage=1
        g.last_day_summary={'day':7,'order':['Power'],'timed_out':True,'total':5}
        g.store.save(g);g.store.load(g)
        self.assertEqual(g.panel_work.stage,1);self.assertEqual(g.tasks.day8_current_target(),'Hangar')
        self.assertEqual(g.last_day_summary['day'],7)
        g._new_game_from_menu()
        previous=g.store._read(g.store.root/'previous_save.json')
        self.assertEqual(previous['day'],8);self.assertEqual(g.store.read()['day'],1)

    def test_animated_title_scene_leaves_campaign_and_exploration_untouched(self):
        g=self.g;g._advance_from_transition();before=g.store.snapshot(g)
        explored=pygame.image.tobytes(g.presentation.explored,'RGBA')
        for time in (0,3,9):g.menu.scene.draw(g.screen,time)
        self.assertEqual(g.store.snapshot(g),before)
        self.assertEqual(pygame.image.tobytes(g.presentation.explored,'RGBA'),explored)

    def test_wrapped_text_respects_the_typefaces_actual_line_spacing(self):
        g=self.g;face=g.presentation.small
        width=face.size('Yukarı')[0]+1
        end=g.presentation.wrapped('Yukarı Aşağı',20,10,width,font=face,line_height=1)
        self.assertGreaterEqual(end,10+2*face.get_linesize())

    def test_settings_persist_and_audio_retry_keeps_gain(self):
        g=self.g;g.menu.adjust('brightness',g.menu.slider('brightness').right)
        self.assertAlmostEqual(g.lamp_power,1.6)
        g.menu.adjust('volume',g.menu.slider('volume').x)
        g.audio.retry();self.assertEqual(g.audio.master_volume,0)
        second=SaveStore(self.temp.name);self.assertEqual(second.settings()['brightness'],1.6)


class NavigationTests(unittest.TestCase):
    def setUp(self):
        from shipmap import ShipMap
        self.ship=ShipMap()
    def test_continuous_non_axis_motion_and_complete_budget(self):
        room=self.ship.room_by_name('Quarters');a=Alien(self.ship,tuple(room.world_center))
        a.state=STATE_CHASE;a.current_target=a.pos+pygame.Vector2(67,31)
        start=a.pos.copy();a._follow_path(.05,get_day_params(4));delta=a.pos-start
        self.assertGreater(delta.x,0);self.assertGreater(delta.y,0)
        self.assertAlmostEqual(delta.length(),C.ALIEN_CHASE_SPEED*.05,places=3)
        self.assertAlmostEqual(math.atan2(delta.y,delta.x),math.atan2(31,67),places=3)
    def test_smoothing_cannot_cut_a_wall_or_closed_bulkhead(self):
        door=self.ship.doors.doors[0];self.ship.doors._set_closed(door,True)
        start=(door.center.x,door.rect.top-36);end=(door.center.x,door.rect.bottom+36)
        self.assertFalse(segment_clear(self.ship,start,end,C.ALIEN_RADIUS))
        path=find_path(self.ship,start,end,allow_closed_doors=True,diagonal=True)
        smoothed=smooth_path(self.ship,start,path,C.ALIEN_RADIUS)
        self.assertGreater(len(smoothed),1)
        # Diagonal neighbors require both perpendicular neighbors to be open.
        from pathfinding import world_to_tile
        for p,q in zip(path,path[1:]):
            x,y=world_to_tile(*p);xx,yy=world_to_tile(*q)
            if x!=xx and y!=yy:
                self.assertFalse(self.ship.is_path_wall(xx,y,allow_closed_doors=True))
                self.assertFalse(self.ship.is_path_wall(x,yy,allow_closed_doors=True))
    def test_patrol_points_vary_inside_room_and_avoid_recent_rooms(self):
        from systems import BehaviorTracker
        a=Alien(self.ship,tuple(self.ship.room_by_name('Quarters').world_center));a._patrol_pause=0
        points=set()
        for _ in range(25):
            a.current_target=None;a._do_wander(self.ship,BehaviorTracker(),get_day_params(4),4)
            points.add(tuple(a.current_target))
            self.assertFalse(self.ship.is_blocked_circle(*a.current_target,C.ALIEN_RADIUS))
            self.assertNotEqual(a.current_target,a._wander_target_room.world_center)
        self.assertGreater(len(points),20)


class DailyPowerTests(unittest.TestCase):
    def test_day_one_lit_day_two_outages_day_three_torch_only(self):
        c=ShipConditions();c.start_day(1);c.update(1,200)
        self.assertFalse(c.blackout);self.assertGreater(c.ambient_strength,.7)
        c.start_day(2);c.update(1,11)
        self.assertTrue(c.blackout);self.assertLess(c.ambient_strength,.04);self.assertEqual(c.lamp_power,1)
        c.update(1,20);self.assertFalse(c.blackout);self.assertGreater(c.ambient_strength,.6)
        for day in range(3,9):
            c.start_day(day)
            for time in (0,20,100,250):
                for repaired in (False,True):
                    c.update(1,time,repaired);self.assertEqual(c.ambient_strength,0);self.assertEqual(c.lamp_power,1)
    def test_ambient_is_direction_independent_but_wall_occluded(self):
        from shipmap import ShipMap
        from lighting import Lighting
        ship=ShipMap();origin=tuple(ship.room_by_name('Quarters').world_center);lamp=Lighting()
        behind=(origin[0]-100,origin[1])
        self.assertGreater(lamp.strength_at(ship,origin,0,behind,330,1,.78),100)
        self.assertEqual(lamp.strength_at(ship,origin,0,behind,230,1,0),0)
        door=ship.doors.doors[0];ship.doors._set_closed(door,True)
        self.assertEqual(lamp.strength_at(ship,(door.center.x,door.rect.top-25),math.pi/2,(door.center.x,door.rect.bottom+25),330,1,.78),0)
