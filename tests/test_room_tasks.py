"""Task outcomes and real pointer routing; wrong inputs cannot finish work."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
import unittest
from unittest.mock import patch
from collections import defaultdict
import pygame
import config as C
from maintenance import PanelWork,work_for_day,active_rooms
from main import Game,PHASE_PLAYING
from task_panels import widgets,confirm_rect,panel_rect
from pathfinding import find_path

class RoomWorkTests(unittest.TestCase):
    def test_filter_requires_each_dirty_cell_once(self):
        w=PanelWork('Oxygen','filter',1);original=set(w.debris)
        first=next(iter(original));w.act('clean',first)
        self.assertEqual(w.act('clean',first),'ignored');self.assertFalse(w.complete)
        for i in original-{first}:w.act('clean',i)
        self.assertTrue(w.complete)

    def test_wires_require_matching_labels_and_all_connections(self):
        w=PanelWork('Power','wires',1);w.act('wire_start',0)
        self.assertEqual(w.act('wire_end',(w.wire_goal[0]+1)%3),'wrong');self.assertFalse(w.connected)
        w.act('wire_start',0);w.act('wire_end',None);self.assertFalse(w.connected)
        for i in range(3):
            w.act('wire_start',i);result=w.act('wire_end',w.wire_goal[i])
        self.assertEqual(result,'complete');self.assertEqual(w.progress,1)

    def test_sequence_blocks_demo_input_and_replays_on_mistake(self):
        w=PanelWork('Reactor','sequence',1);self.assertEqual(w.press('1'),'ignored');w.update(10,{})
        self.assertEqual(w.press(str((w.pattern[0]+1)%3+1)),'wrong');self.assertGreater(w.sequence_timer,0)
        w.update(10,{})
        for step in w.pattern:result=w.press(str(step+1))
        self.assertEqual(result,'complete')

    def test_signal_requires_peak_and_confirmation(self):
        w=PanelWork('Communications','signal',1);self.assertEqual(w.press('space'),'wrong')
        w.act('tune',w.target);self.assertFalse(w.complete);self.assertEqual(w.press('space'),'complete')

    def test_three_valves_have_independent_targets(self):
        w=PanelWork('Cooling','valves',1);self.assertEqual(w.press('space'),'wrong')
        for i in range(3):
            while w.valves[i]!=w.valve_goal[i]:w.press(str(i+1))
        self.assertFalse(w.complete);self.assertEqual(w.press('space'),'complete')

    def test_course_needs_alignment_in_both_axes(self):
        w=PanelWork('Navigation','course',1);w.act('course',(w.course_goal[0],1))
        self.assertEqual(w.press('space'),'wrong');w.act('course',w.course_goal)
        self.assertEqual(w.press('space'),'complete')

    def test_cargo_rejects_wrong_bays_and_delivers_every_crate(self):
        w=PanelWork('Cargo Bay','cargo',1);w.act('crate_start',0)
        self.assertEqual(w.act('crate_end',(w.crates[0]+1)%3),'wrong');self.assertFalse(w.delivered)
        for i in range(4):
            w.act('crate_start',i);result=w.act('crate_end',w.crates[i])
        self.assertEqual(result,'complete')

    def test_fuel_needs_pumping_and_stopping_in_target_zone(self):
        w=PanelWork('Storage','fuel',1);w.update(10,{});self.assertEqual(w.fuel,0)
        w.press('space');w.update(10,{});self.assertFalse(w.complete)
        self.assertEqual(w.press('space'),'wrong');self.assertEqual(w.fuel,0)
        w.press('space');w.update(w.target/.22,{});self.assertEqual(w.press('space'),'complete')

class PointerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.g=Game(campaign_seed=0)
    @classmethod
    def tearDownClass(cls):pygame.quit()
    def setUp(self):
        g=self.g;g.paused=False;g._restart_game(campaign_seed=0);g._advance_from_transition();g._keys=lambda:{}
    def open(self,name,kind=None,prepare=True):
        g=self.g
        if name not in g.tasks.tasks:
            g.day=next(d for d in range(1,8) if name in active_rooms(d));g._start_day();g.phase=PHASE_PLAYING
        task=g.tasks.tasks[name]
        if prepare:
            for parent in ('Power','Cooling','Reactor'):
                if parent!=name:g.tasks.complete_task(parent,0)
        if kind is not None:task.step=task.operations.index(kind)
        g.player.pos=g.ship_map.room_by_name(name).world_center.copy()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_e));g._handle_events();g._update(.01)
        self.assertIsNotNone(g.panel_work);return g.panel_work
    def pointer(self,action,pos):
        event={'down':pygame.MOUSEBUTTONDOWN,'up':pygame.MOUSEBUTTONUP,'move':pygame.MOUSEMOTION}[action]
        pygame.event.post(pygame.event.Event(event,pos=pos,button=1));self.g._handle_events();self.g._update(.01)

    def test_real_clicks_clean_filter_and_complete_only_oxygen(self):
        w=self.open('Oxygen','filter')
        for i in list(w.debris):self.pointer('down',widgets(w)[i].center)
        self.assertIsNone(self.g.panel_work);self.assertFalse(self.g.tasks.tasks['Oxygen'].done)
        self.assertEqual(self.g.tasks.tasks['Oxygen'].step,2)

    def test_wire_release_outside_cancels_and_real_drag_finishes(self):
        w=self.open('Power','wires');left,right=widgets(w)
        self.pointer('down',left[0].center);self.pointer('up',(0,0));self.assertFalse(w.connected);self.assertIsNone(w.dragging)
        for i in range(3):
            self.pointer('down',left[i].center);self.pointer('move',right[w.wire_goal[i]].center);self.pointer('up',right[w.wire_goal[i]].center)
        self.assertFalse(self.g.tasks.tasks['Power'].done)
        self.assertEqual(self.g.tasks.tasks['Power'].step,2)

    def test_course_drag_and_confirm_use_actual_board_coordinates(self):
        w=self.open('Navigation','course');r=widgets(w)
        target=(round(r.x+w.course_goal[0]*r.w),round(r.y+w.course_goal[1]*r.h))
        self.pointer('down',target);self.pointer('up',target);self.assertFalse(self.g.tasks.tasks['Navigation'].done)
        self.pointer('down',confirm_rect(w).center);self.assertTrue(self.g.tasks.tasks['Navigation'].done)

    def test_course_arrows_adjust_both_axes_without_moving_player(self):
        w=self.open('Navigation','course');g=self.g;pressed=defaultdict(bool)
        pressed[pygame.K_RIGHT]=True;pressed[pygame.K_UP]=True
        with patch('pygame.key.get_pressed',return_value=pressed):keys=Game._keys(g)
        self.assertFalse(keys['w']);self.assertFalse(keys['d'])
        pos=g.player.pos.copy();before=w.course.copy();g._keys=lambda:keys;g._update(.2)
        self.assertEqual(g.player.pos,pos);self.assertGreater(w.course[0],before[0]);self.assertLess(w.course[1],before[1])

    def test_pause_blocks_clicks_and_cancels_released_pump(self):
        w=self.open('Storage','fuel');self.pointer('down',widgets(w).center);g=self.g;g.paused=True;before=w.fuel
        self.pointer('up',(0,0));self.assertEqual(w.fuel,before);self.assertFalse(w.pumping)
        self.assertIsNone(w.dragging);self.assertFalse(w.complete)

    def solve(self,w):
        g=self.g;areas=widgets(w)
        if w.kind=='filter':
            for i in list(w.debris):self.pointer('down',areas[i].center)
        elif w.kind=='sequence':
            g._update(5)
            for step in w.pattern:self.pointer('down',areas[step].center)
        elif w.kind=='wires':
            for i in range(3):
                self.pointer('down',areas[0][i].center);self.pointer('up',areas[1][w.wire_goal[i]].center)
        elif w.kind=='signal':
            point=(round(areas.x+w.target*areas.w),areas.centery)
            self.pointer('down',point);self.pointer('up',point);self.pointer('down',confirm_rect(w).center)
        elif w.kind=='valves':
            for i in range(3):
                while w.valves[i]!=w.valve_goal[i]:self.pointer('down',areas[i].center)
            self.pointer('down',confirm_rect(w).center)
        elif w.kind=='course':
            point=(round(areas.x+w.course_goal[0]*areas.w),round(areas.y+w.course_goal[1]*areas.h))
            self.pointer('down',point);self.pointer('up',point);self.pointer('down',confirm_rect(w).center)
        elif w.kind=='cargo':
            for i in range(4):
                self.pointer('down',areas[0][i].center);self.pointer('up',areas[1][w.crates[i]].center)
        elif w.kind=='fuel':
            self.pointer('down',areas.center);g._update(w.target/.22);self.pointer('up',areas.center)
        else:
            x,y,_,_=panel_rect()
            if w.kind=='inspect':self.pointer('down',(x+111+w.fault*178,y+303))
            elif w.kind=='calibrate':
                w.cursor=w.target;self.pointer('down',confirm_rect(w).center)
            elif w.kind=='repair':
                self.pointer('down',(x+111,y+303));w.cursor=w.target
                self.pointer('down',(x+289,y+303));self.pointer('down',(x+467,y+303))
            elif w.kind=='rewire':
                for i in range(3):
                    if w.bits[i]!=w.goal[i]:self.pointer('down',(x+111+i*178,y+303))
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE));g._handle_events();g._update(.01)
        self.assertTrue(w.complete,w.kind)

    def test_five_jobs_finish_all_stages_in_priority_order_through_real_inputs(self):
        g=self.g
        self.assertEqual(len(g.tasks.tasks),5)
        names=list(g.tasks.tasks)
        for name in names:
            stages=len(g.tasks.tasks[name].operations)
            for _ in range(stages):self.solve(self.open(name,prepare=False))
        self.assertEqual(g.day,2)
        self.assertEqual(len(g.last_day_summary['order']),5)
        self.assertEqual(g.integrity,100)

    def test_map_and_all_room_panels_render_every_day(self):
        g=self.g
        for day in range(1,8):
            g.day=day;g._start_day();g.phase=PHASE_PLAYING
            for name in g.tasks.tasks:
                point=g.ship_map.room_by_name(name).world_center
                self.assertTrue(find_path(g.ship_map,tuple(g.player.pos),tuple(point)))
                g.panel_work=PanelWork(name,work_for_day(day,name),day);g._render()
                self.assertLessEqual(panel_rect().bottom,C.VIEW_H)
            g._cancel_panel();g.show_map=True;g._render();g.show_map=False
        self.assertEqual(g.screen.get_size(),(C.SCREEN_W,C.SCREEN_H))
