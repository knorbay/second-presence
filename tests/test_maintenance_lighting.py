"""Interactive work and directional, attenuated, occluded lighting."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
import math
import unittest
from unittest.mock import patch
from collections import defaultdict
import pygame
import config as C
from maintenance import PanelWork,work_for_day,ROOM_WORK,KINDS,active_rooms
from lighting import Lighting,light_strength
from shipmap import ShipMap
from survival import ShipConditions
from main import Game,PHASE_PLAYING


class WorkTests(unittest.TestCase):
    def test_escape_and_room_work_match_their_equipment(self):
        self.assertEqual([work_for_day(8,n) for n in C.DAY8_SEQUENCE],['rewire','course','repair'])
        for day in range(1,8):
            for name in C.TASK_ROOM_NAMES:
                self.assertIn(work_for_day(day,name),ROOM_WORK[name])

    def test_every_shift_has_five_jobs_and_multiple_stages(self):
        from systems import TaskSystem
        tasks=TaskSystem(ShipMap())
        for day in range(1,8):
            tasks.reset_day(day)
            self.assertEqual(len(tasks.tasks),5)
            self.assertEqual(tuple(tasks.tasks),active_rooms(day))
            self.assertTrue(all(2<=len(t.operations)<=3 for t in tasks.tasks.values()))
            self.assertGreaterEqual(sum(len(t.operations) for t in tasks.tasks.values()),12)

    def test_multi_operation_rooms_rotate_between_themed_jobs(self):
        for name,choices in ROOM_WORK.items():
            self.assertEqual({work_for_day(day,name) for day in range(1,8)},set(choices))

    def test_diagnosis_requires_identifying_the_fault(self):
        work=PanelWork('Oxygen','inspect',1)
        for i,value in enumerate(work.readings):
            self.assertEqual(not 40<=value<=60,i==work.fault)
        wrong=str((work.fault+1)%3+1)
        self.assertEqual(work.press(wrong),'wrong')
        self.assertFalse(work.complete)
        self.assertEqual(work.press(str(work.fault+1)),'complete')

    def test_repair_requires_isolation_timing_and_restoration(self):
        work=PanelWork('Power','repair',2)
        self.assertEqual(work.press('3'),'wrong');self.assertEqual(work.stage,0)
        self.assertEqual(work.press('1'),'progress')
        work.cursor=0;self.assertEqual(work.press('space'),'wrong')
        self.assertEqual(work.stage,1);self.assertFalse(work.complete)
        work.cursor=work.target;self.assertEqual(work.press('space'),'progress')
        self.assertFalse(work.complete)
        self.assertEqual(work.press('3'),'complete')

    def test_calibration_requires_actual_adjustment_and_confirmation(self):
        work=PanelWork('Reactor','calibrate',3)
        self.assertEqual(work.press('space'),'wrong')
        before=work.cursor;work.update(.5,{'right':True})
        self.assertGreater(work.cursor,before)
        work.cursor=work.target;self.assertEqual(work.press('space'),'complete')

    def test_rewiring_requires_matching_all_switches(self):
        work=PanelWork('Cooling','rewire',4)
        self.assertNotEqual(work.bits,work.goal)
        self.assertEqual(work.press('space'),'wrong')
        for i,(value,target) in enumerate(zip(work.bits.copy(),work.goal)):
            if value!=target:self.assertEqual(work.press(str(i+1)),'progress')
        self.assertFalse(work.complete)
        self.assertEqual(work.press('space'),'complete')

    def test_time_and_holding_e_never_finish_any_work(self):
        for kind in KINDS:
            work=PanelWork('Power',kind,2)
            for _ in range(200):work.update(.1,{'e':True})
            self.assertFalse(work.complete)

    def test_same_panel_keeps_stable_values_when_reopened(self):
        a=PanelWork('Oxygen','inspect',5);b=PanelWork('Oxygen','inspect',5)
        self.assertEqual(a.readings,b.readings)
        self.assertEqual(a.fault,b.fault)
        self.assertNotEqual(a.readings,PanelWork('Oxygen','inspect',1).readings)

    def test_unpowered_repair_is_quieter_than_making_the_connection(self):
        work=PanelWork('Power','repair',2);idle=work.noise
        work.press('1')
        self.assertGreater(work.noise[0],idle[0])
        self.assertGreater(work.noise[1],idle[1])


class LightTests(unittest.TestCase):
    def setUp(self):
        self.ship=ShipMap();self.light=Lighting()
        self.ship.grid=[[0]*C.COLS for _ in range(C.ROWS)]

    def test_distance_fades_smoothly_instead_of_flat_disk(self):
        values=[light_strength(d,0,0,230) for d in (0,25,50,100,125,150,175,200,229,230)]
        self.assertEqual(values[-1],0)
        # Maximum display brightness can saturate near the player; the outer beam still fades.
        self.assertTrue(all(a>=b for a,b in zip(values,values[1:])) and all(a>b for a,b in zip(values[3:8],values[4:9])),values)
        self.assertLess(values[-2],3)

    def test_light_is_fifty_percent_brighter_than_v08_without_extending_range(self):
        for dx,dy,power in ((85,0,1),(100,20,1),(35,35,.45),(120,0,.45)):
            with patch.object(C,'FLASHLIGHT_BRIGHTNESS',2.484):
                before=light_strength(dx,dy,0,230,power)
            after=light_strength(dx,dy,0,230,power)
            self.assertLessEqual(abs(after-min(255,before*1.5)),1.5)
        self.assertEqual(light_strength(230,0,0,230),0)
        self.assertEqual(light_strength(0,0,0,230),255)

    def test_beam_favors_facing_direction_and_has_close_peripheral_light(self):
        front=light_strength(100,0,0,230)
        side=light_strength(0,100,0,230)
        behind=light_strength(-100,0,0,230)
        self.assertGreater(front,side)
        self.assertEqual(behind,0)
        self.assertGreater(light_strength(-25,0,0,230),0)

    def test_wall_blocks_light_measurement_and_rendered_pixels(self):
        for row in self.ship.grid:row[20]=1
        origin=(444,564);behind=(540,564)
        self.assertEqual(self.light.strength_at(self.ship,origin,0,behind,230),0)
        screen=pygame.Surface((C.WORLD_W,C.WORLD_H));screen.fill((100,100,100))
        explored=pygame.Surface(screen.get_size(),pygame.SRCALPHA);explored.fill((0,0,0,255))
        self.light.apply(screen,explored,self.ship,origin,0,230,1)
        self.assertEqual(screen.get_at(behind).r,0)
        self.assertGreater(screen.get_at((460,564)).r,0)

    def test_rendered_floor_gets_darker_with_distance(self):
        screen=pygame.Surface((C.WORLD_W,C.WORLD_H));screen.fill((100,100,100))
        explored=pygame.Surface(screen.get_size(),pygame.SRCALPHA);explored.fill((0,0,0,255))
        self.light.apply(screen,explored,self.ship,(600,564),0,230,1)
        near=screen.get_at((640,564)).r;far=screen.get_at((780,564)).r
        self.assertGreater(near,far*3)
        self.assertLess(screen.get_at((500,564)).r,3)

    def test_blackout_transition_dims_ship_light_but_keeps_torch(self):
        c=ShipConditions();c.start_day(2)
        c.update(.01,11)
        self.assertTrue(c.blackout)
        self.assertGreater(c.ambient_strength,.6)
        c.update(.8,11)
        self.assertLess(c.ambient_strength,.04)
        before=c.ambient_strength;c.update(.05,20)
        self.assertGreater(c.ambient_strength,before)
        self.assertLess(c.ambient_strength,.65)
        self.assertEqual(c.lamp_power,1)

    def test_ship_has_no_removed_physiology_state(self):
        c=ShipConditions()
        for field in ('health','oxygen','fatigue','medkits','airless_seconds'):
            self.assertFalse(hasattr(c,field))


class PanelIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.g=Game(campaign_seed=0)
    @classmethod
    def tearDownClass(cls):pygame.quit()
    def setUp(self):
        g=self.g;g.paused=False;g._restart_game(campaign_seed=0);g.day=2;g._start_day();g._advance_from_transition()
        g._keys=lambda:{}
        g.player.pos=g.ship_map.room_by_name('Power').world_center.copy()

    def open_panel(self):
        g=self.g
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_e))
        g._handle_events();g._update(.01)
        self.assertIsNotNone(g.panel_work)

    def test_short_e_press_opens_panel_without_holding(self):
        self.open_panel()
        self.assertEqual(self.g.panel_work.kind,'inspect')
        self.assertFalse(self.g.tasks.tasks['Power'].done)

    def test_real_number_key_confirms_inspection_and_closes_panel(self):
        self.open_panel();g=self.g
        key=(pygame.K_1,pygame.K_2,pygame.K_3)[g.panel_work.fault]
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=key))
        g._handle_events();g._update(.01)
        self.assertFalse(g.tasks.tasks['Power'].done)
        self.assertEqual(g.tasks.tasks['Power'].step,1)
        self.assertIsNone(g.panel_work)

    def test_escape_closes_panel_before_pausing_the_game(self):
        self.open_panel();g=self.g
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_ESCAPE))
        g._handle_events()
        self.assertIsNone(g.panel_work);self.assertFalse(g.paused)
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_ESCAPE));g._handle_events()
        self.assertTrue(g.paused)

    def test_wrong_choice_emits_noise_but_does_not_complete(self):
        self.open_panel();g=self.g
        g.panel_inputs=[str((g.panel_work.fault+1)%3+1)];g._update(.01)
        self.assertFalse(g.tasks.tasks['Power'].done)
        self.assertTrue(any(e.kind=='panel_error' for e in g.noise.events))

    def test_panel_is_live_and_can_be_abandoned_for_hiding(self):
        self.open_panel();g=self.g;before=g.day_time
        g._update(.5);self.assertGreater(g.day_time,before)
        g.player.pos=g.lockers['Power'].copy();g._toggle_hiding()
        self.assertTrue(g.player.hidden);self.assertIsNone(g.panel_work)

    def test_pause_freezes_timing_operation(self):
        g=self.g;g.day=2;g._start_day();g.phase=PHASE_PLAYING
        g.tasks.complete_task('Power',0);g.tasks.complete_task('Cooling',0)
        g.player.pos=g.ship_map.room_by_name('Reactor').world_center.copy()
        self.open_panel();g.panel_inputs=['1'];g._update(.01)
        cursor=g.panel_work.cursor
        g.paused=True;g._update(5)
        self.assertEqual(g.panel_work.cursor,cursor)

    def test_calibration_arrow_adjustment_does_not_move_player(self):
        g=self.g;g.day=2;g._start_day();g.phase=PHASE_PLAYING
        g.tasks.complete_task('Power',0);g.tasks.tasks['Cooling'].step=2
        g.player.pos=g.ship_map.room_by_name('Cooling').world_center.copy()
        self.open_panel();position=g.player.pos.copy()
        cursor=g.panel_work.cursor
        g._keys=lambda:{'right':True};g._update(.2)
        self.assertEqual(g.player.pos,position)
        self.assertGreater(g.panel_work.cursor,cursor)

    def test_arrow_keys_only_adjust_horizontal_axis_during_calibration(self):
        g=self.g
        pressed=defaultdict(bool);pressed[pygame.K_RIGHT]=True
        g.panel_work=PanelWork('Power','calibrate',3)
        with patch('pygame.key.get_pressed',return_value=pressed):
            keys=Game._keys(g)
        self.assertTrue(keys['right']);self.assertFalse(keys['d'])
        g.panel_work=PanelWork('Power','inspect',1)
        with patch('pygame.key.get_pressed',return_value=pressed):
            keys=Game._keys(g)
        self.assertTrue(keys['d'])
        g.panel_work=PanelWork('Power','calibrate',3)
        pressed[pygame.K_UP]=True
        with patch('pygame.key.get_pressed',return_value=pressed):
            self.assertTrue(Game._keys(g)['w'])

    def test_font_supports_turkish_instructions(self):
        for font in (self.g.presentation.font,self.g.presentation.small,self.g.presentation.tiny):
            self.assertTrue(all(metric is not None for metric in font.metrics('şŞıİğĞçÇöÖüÜ')))

    def test_each_operation_panel_renders(self):
        g=self.g
        for day in range(1,9):
            g.day=day;g._start_day();g.phase=PHASE_PLAYING
            name='Power';g.player.pos=g.ship_map.room_by_name(name).world_center.copy()
            g.panel_work=PanelWork(name,work_for_day(day,name),day)
            if g.panel_work.kind=='repair':g.panel_work.press('1')
            g._render()
            self.assertEqual(g.screen.get_size(),(C.SCREEN_W,C.SCREEN_H))


if __name__=='__main__':unittest.main()
