"""Replay diversity, real-input completion and exact saved puzzle continuity."""
import os
import json
import math
import tempfile
import unittest
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
import config as C
from shift_plan import make_plan,new_campaign_seed,RECIPES,INCIDENTS
from shipmap import ShipMap
from systems import TaskSystem,get_day_params
from maintenance import PanelWork,KINDS
from main import Game,PHASE_PLAYING,PHASE_GAME_OVER,PHASE_DAY_TRANSITION
from entities import Alien,STATE_CHASE,STATE_WANDER
import test_room_tasks as room_tests


def signature(tasks):
    return tuple((t.name,t.operations,t.requires) for t in tasks.tasks.values())


class PlanTests(unittest.TestCase):
    def test_hundreds_of_shifts_have_five_reachable_jobs_and_no_dependency_cycles(self):
        ship=ShipMap();signatures=set();roots=set()
        for seed in range(1,81):
            system=TaskSystem(ship,seed)
            for day in range(1,8):
                system.reset_day(day);signatures.add(signature(system))
                self.assertEqual(len(system.tasks),5)
                self.assertTrue({'Power','Cooling','Reactor'}<=set(system.tasks))
                roots.add(tuple(name for name in system.tasks if system.available(name)))
                for t in system.tasks.values():
                    self.assertIn(t.operations,RECIPES[t.name]);self.assertTrue(set(t.requires)<=set(system.tasks))
                for _ in range(5):
                    available=[n for n in system.tasks if system.available(n)]
                    self.assertTrue(available,'A generated plan deadlocked')
                    system.complete_task(available[0],10)
                self.assertTrue(system.all_standard_tasks_done())
        self.assertGreater(len(signatures),400);self.assertGreaterEqual(len(roots),6)

    def test_shift_incidents_and_recipes_rotate_but_seed_recreates_them(self):
        for seed in (2,81,94621):
            ids=[make_plan(seed,day)[0][0] for day in range(1,7)]
            self.assertEqual(len(set(ids)),6)
            for day in range(1,7):
                self.assertEqual(make_plan(seed,day),make_plan(seed,day))
                a={n:ops for n,ops,_ in make_plan(seed,day)[1]}
                b={n:ops for n,ops,_ in make_plan(seed,day+1)[1]}
                for name in a.keys()&b.keys():self.assertNotEqual(a[name],b[name])

    def test_new_seed_avoids_the_previous_opening_incident(self):
        previous=0  # Also leave the fixed opening of an older saved campaign.
        for _ in range(100):
            seed=new_campaign_seed(previous)
            self.assertNotEqual(seed%len(INCIDENTS),previous%len(INCIDENTS));previous=seed

    def test_panel_values_change_across_runs_not_every_time_a_panel_reopens(self):
        a=PanelWork('Power','wires',1,0,111)
        b=PanelWork('Power','wires',1,0,111)
        c=PanelWork('Power','wires',1,0,112)
        self.assertEqual(vars(a),vars(b));self.assertNotEqual(vars(a),vars(c))

    def test_reopened_upstream_fault_blocks_all_dependent_unfinished_jobs(self):
        tasks=TaskSystem(ShipMap(),6)
        tasks.complete_task('Power',1);tasks.complete_task('Cooling',2)
        self.assertTrue(tasks.available('Reactor'))
        tasks.tasks['Power'].reopen()
        self.assertIn('Power',tasks.blocked_by('Reactor'))
        self.assertFalse(tasks.advance_task('Reactor',3))
        tasks.complete_task('Power',4);self.assertTrue(tasks.available('Reactor'))


class CampaignIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.g=Game(self.temp.name,campaign_seed=6)
        self.g._keys=lambda:{};pygame.event.clear()
    def tearDown(self):self.temp.cleanup()

    def test_r_after_death_resets_progress_with_a_different_plan(self):
        g=self.g;before=signature(g.tasks);seed=g.tasks.campaign_seed
        g.tasks.complete_task('Power',1);g.tracker.sprint_count=9;g.day=5
        g.phase=PHASE_GAME_OVER;g.death=None
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_r));g._handle_events()
        self.assertEqual(g.phase,PHASE_DAY_TRANSITION);self.assertEqual(g.day,1)
        self.assertNotEqual(g.tasks.campaign_seed,seed);self.assertNotEqual(signature(g.tasks),before)
        self.assertEqual(g.tracker.sprint_count,0);self.assertFalse(any(t.done for t in g.tasks.tasks.values()))

    def test_save_load_keeps_generated_goals_progress_and_next_shift_and_never_writes_during_load(self):
        g=self.g;g.phase=PHASE_PLAYING
        task=g.tasks.tasks['Power'];kind=task.operation
        work=g.tasks.panel(task.name,kind);task.sessions[(0,0)]=work
        work.cursor=.43;work.bits[0]=1-work.bits[0]
        g.day_time=79;g.store.save(g);stored=g.store.path.read_bytes()
        before=vars(work).copy();plan=signature(g.tasks);seed=g.tasks.campaign_seed
        next_plan=make_plan(seed,2)
        g._autosave_enabled=True;g.tasks.campaign_seed=27
        g.store.load(g)
        restored=g.tasks.tasks['Power'].sessions[(0,0)]
        for key,value in before.items():self.assertEqual(getattr(restored,key),value,key)
        self.assertEqual(signature(g.tasks),plan);self.assertEqual(make_plan(g.tasks.campaign_seed,2),next_plan)
        self.assertEqual(g.day_time,79);self.assertEqual(g.store.path.read_bytes(),stored)

    def test_previous_save_without_seed_still_loads_its_original_recipe_and_progress(self):
        g=self.g;g._restart_game(campaign_seed=0);g.phase=PHASE_PLAYING
        g.tasks.tasks['Power'].step=1
        w=PanelWork('Power','wires',1,1);w.connected.add(1)
        g.tasks.tasks['Power'].sessions[(1,0)]=w
        data=g.store.snapshot(g);data.pop('campaign_seed');data.pop('plan_version')
        for record in data['tasks'].values():record.pop('operations');record.pop('requires')
        g.store.load(g,data)
        self.assertEqual(g.tasks.tasks['Power'].operations,('inspect','wires','calibrate'))
        self.assertEqual(g.tasks.tasks['Power'].sessions[(1,0)].connected,{1})
        self.assertEqual(g.tasks.campaign_seed,0)

    def test_all_six_incidents_complete_through_real_keys_and_pointer_events(self):
        # Reuse the existing instrument driver, but exercise production randomized plans.
        self.pointer=lambda action,pos:room_tests.PointerTests.pointer(self,action,pos)
        self.open=lambda name,prepare=False:room_tests.PointerTests.open(self,name,prepare=prepare)
        for seed in range(6,12):
            g=self.g;g._restart_game(campaign_seed=seed);g._advance_from_transition()
            self.assertIsNotNone(g.tasks.incident)
            for name in list(g.tasks.tasks):
                for _ in g.tasks.tasks[name].operations:
                    work=self.open(name)
                    room_tests.PointerTests.solve(self,work)
            self.assertEqual(g.day,2);self.assertEqual(len(g.last_day_summary['order']),5)


class IntruderCadenceTests(unittest.TestCase):
    def test_surges_vary_speed_but_stay_below_sprint_and_respect_walls(self):
        ship=ShipMap();a=Alien(ship,(1260,564));a.state=STATE_CHASE
        values=[]
        for i in range(100):
            a.motion_clock=i*.05;values.append(a.movement_cadence()*C.ALIEN_CHASE_SPEED)
        self.assertGreater(max(values)-min(values),30);self.assertLess(max(values),C.SPRINT_SPEED)
        door=ship.doors.doors[0];ship.doors._set_closed(door,True)
        a.pos=door.center-pygame.Vector2(0,door.rect.h/2+20)
        a.current_target=door.center+pygame.Vector2(0,80);a.gait_scale=max(values)/C.ALIEN_CHASE_SPEED
        for _ in range(3):
            a._follow_path(.05,get_day_params(3));self.assertFalse(ship.is_blocked_circle(*a.pos,C.ALIEN_RADIUS))
