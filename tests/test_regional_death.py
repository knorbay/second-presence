"""Spatial audio and finite death-flow regressions."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
import unittest
from unittest.mock import patch
import pygame
import config as C
from audio import regional_targets
from scenery import ROOM_AUDIO,equipment_point
from shipmap import ShipMap
from main import Game,PHASE_PLAYING,PHASE_GAME_OVER,PHASE_DAY_TRANSITION
from entities import STATE_CHASE
from death_effect import DeathSequence


class SpatialAudioTests(unittest.TestCase):
    def setUp(self):self.ship=ShipMap()

    def test_equipment_nearby_and_far_away_have_different_loudness(self):
        source=equipment_point(self.ship.room_by_name('Reactor'))
        near=regional_targets(source,self.ship)['Reactor'][0]
        with patch.object(self.ship,'line_of_sight',return_value=True):
            middle=regional_targets(source+pygame.Vector2(150,0),self.ship)['Reactor'][0]
        far=regional_targets(source+pygame.Vector2(400,0),self.ship)['Reactor'][0]
        self.assertGreater(near,middle);self.assertGreater(middle,far);self.assertEqual(far,0)

    def test_wall_attenuation_and_left_right_pan_follow_the_source(self):
        source=equipment_point(self.ship.room_by_name('Cooling'))
        with patch.object(self.ship,'line_of_sight',return_value=True):
            left=regional_targets(source+pygame.Vector2(70,0),self.ship)['Cooling']
            right=regional_targets(source-pygame.Vector2(70,0),self.ship)['Cooling']
        with patch.object(self.ship,'line_of_sight',return_value=False):
            blocked=regional_targets(source+pygame.Vector2(70,0),self.ship)['Cooling'][0]
        self.assertLess(left[1],0);self.assertGreater(right[1],0)
        self.assertAlmostEqual(left[0],right[0]);self.assertLess(blocked,left[0]*.3)

    def test_power_loss_affects_machines_but_retains_pressure_and_hull(self):
        for name in ('Reactor','Airlock','Cargo Bay'):
            source=equipment_point(self.ship.room_by_name(name))
            normal=regional_targets(source,self.ship)[name][0]
            blackout=regional_targets(source,self.ship,True)[name][0]
            if name=='Reactor':self.assertLess(blackout,normal*.3)
            else:self.assertEqual(blackout,normal)


class DeathFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.g=Game(campaign_seed=0)
    @classmethod
    def tearDownClass(cls):pygame.quit()

    def setUp(self):
        g=self.g;g.paused=False;g.audio.pause(False);g.audio.enabled=True
        g._restart_game(campaign_seed=0);g._advance_from_transition();g._keys=lambda:{}

    def catch(self):
        g=self.g
        g.player.pos=pygame.Vector2(1260,576);g.camera=g.camera_target()
        g.alien.pos=g.player.pos+pygame.Vector2(12,0);g.alien.state=STATE_CHASE
        g._check_catch()

    def test_catch_animates_once_and_freezes_tasks_day_time_and_actor_positions(self):
        g=self.g;self.catch();death=g.death
        self.assertEqual(g.phase,PHASE_GAME_OVER);self.assertIsNotNone(death)
        before=(g.day_time,g.player.pos.copy(),g.alien.pos.copy(),g.tasks.tasks['Power'].step)
        g._check_catch();self.assertIs(g.death,death)
        g._update(.5)
        self.assertGreater(death.elapsed,0);self.assertFalse(death.complete)
        self.assertEqual(before,(g.day_time,g.player.pos,g.alien.pos,g.tasks.tasks['Power'].step))
        g._render()

    def test_impacts_sound_once_and_sequence_is_bounded_even_on_large_updates(self):
        self.catch();g=self.g
        with patch.object(g.audio,'play') as sound:
            g._update(10);g._update(10)
        self.assertTrue(g.death.complete);self.assertEqual(g.death.elapsed,DeathSequence.DURATION)
        self.assertEqual([call.args[0] for call in sound.call_args_list],['death_hit','tear','death_hit','tear'])
        self.assertLessEqual(len(g.death.particles),208)
        g._render()

    def test_restart_waits_until_animation_finishes_and_clears_all_death_state(self):
        self.catch();g=self.g
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_r));g._handle_events()
        self.assertEqual(g.phase,PHASE_GAME_OVER)
        g._update(DeathSequence.DURATION)
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_r));g._handle_events()
        self.assertEqual(g.phase,PHASE_DAY_TRANSITION);self.assertIsNone(g.death)
        self.assertFalse(g.player.caught)
        self.assertTrue(all(v==(0,0) for v in g.audio.regional_volumes.values()))

    def test_pause_and_mute_include_positional_channels_and_death_animation(self):
        g=self.g;source=equipment_point(g.ship_map.room_by_name('Oxygen'))
        g.audio.environment(1,'Oxygen',2,False,False,source,g.ship_map)
        before=dict(g.audio.regional_volumes)
        self.assertGreater(max(before['Oxygen']),0)
        g.audio.pause(True);g.audio.environment(10,'Cooling',4,True,False,source,g.ship_map)
        self.assertEqual(g.audio.regional_volumes,before)
        g.audio.pause(False);g.audio.toggle()
        self.assertTrue(all(not c.get_busy() for c,_ in g.audio.regional_channels.values()))
        g.audio.toggle();self.catch();g.paused=True;g._update(1)
        self.assertEqual(g.death.elapsed,0)

    def test_ship_system_failure_uses_normal_ending_without_an_attack(self):
        g=self.g;g.integrity=1;g._end_day()
        self.assertEqual(g.phase,PHASE_GAME_OVER);self.assertIsNone(g.death)
        g._render()

    def test_regional_sources_fade_out_after_leaving_a_room_and_return_after_muting(self):
        g=self.g;source=equipment_point(g.ship_map.room_by_name('Cooling'))
        g.audio.environment(1,'Cooling',2,False,False,source,g.ship_map)
        volume=max(g.audio.regional_volumes['Cooling'])
        g.audio.environment(.1,None,2,False,False,source+pygame.Vector2(500,0),g.ship_map)
        self.assertLess(max(g.audio.regional_volumes['Cooling']),volume)
        self.assertGreater(max(g.audio.regional_volumes['Cooling']),0)
        g.audio.toggle();g.audio.toggle()
        g.audio.environment(.1,'Cooling',2,False,False,source,g.ship_map)
        self.assertTrue(g.audio.regional_channels['Cooling'][0].get_busy())


if __name__=='__main__':unittest.main()
