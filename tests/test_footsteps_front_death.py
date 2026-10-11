"""Audible contacts, reserved voice channels and frontal capture framing."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
import math
import unittest
from array import array
from unittest.mock import patch
import pygame
import config as C
from main import Game
from shipmap import ShipMap
from entities import Player
from systems import NoiseSystem,BehaviorTracker
from death_effect import DeathSequence
from audio import Audio,FOOTSTEP_LEVELS


class Voice:
    def __init__(self):self.calls=[];self.volume=(0,0)
    def set_volume(self,left,right):self.volume=(left,right)
    def play(self,sound):self.calls.append((sound,self.volume))


class FootstepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.g=Game(campaign_seed=0)
    @classmethod
    def tearDownClass(cls):pygame.quit()
    def setUp(self):
        g=self.g;g.paused=False;g.audio.enabled=True;g.audio.pause(False)
        g._restart_game(campaign_seed=0);g._advance_from_transition();g._keys=lambda:{}

    def test_boot_contacts_are_audible_transients_without_sample_clipping(self):
        a=self.g.audio;rate,_,channels=pygame.mixer.get_init()
        self.assertEqual(len(a.sounds['step']),4)
        for sound in a.sounds['step']:
            samples=array('h',sound.get_raw());initial=samples[:round(rate*.1)*channels]
            rms=math.sqrt(sum(value*value for value in initial)/len(initial))/32768
            self.assertGreater(rms*FOOTSTEP_LEVELS['walk'],.035)
            self.assertLess(max(map(abs,samples)),30000)
            self.assertLessEqual(sound.get_length(),.31)

    def test_real_walking_events_reach_the_reserved_voice_and_standing_emits_no_new_steps(self):
        g=self.g;g._keys=lambda:{'d':True}
        with patch.object(g.audio,'footstep',wraps=g.audio.footstep) as step:
            for _ in range(60):g._update(1/60)
            self.assertEqual(step.call_count,2)
            self.assertTrue(all(call.args==('player','walk') for call in step.call_args_list))
            self.assertIn(g.audio.footstep_channels['player'].get_sound(),g.audio.sounds['step'])
            g._keys=lambda:{}
            for _ in range(60):g._update(1/60)
            self.assertEqual(step.call_count,2)

    def test_pressing_against_a_solid_door_makes_no_false_footsteps(self):
        ship=ShipMap();door=ship.doors.doors[1]
        ship.doors.toggle(door,[])
        p=Player(ship,door.center-pygame.Vector2(0,door.rect.h/2+C.PLAYER_RADIUS))
        noise=NoiseSystem();tracker=BehaviorTracker();start=p.pos.copy()
        for _ in range(30):p.update(.05,{'s':True,'shift':True},noise,[],lambda _:None,tracker)
        self.assertEqual(p.pos,start);self.assertFalse(p.moving)
        self.assertFalse(p.sprinting);self.assertEqual(noise.events,[])

    def test_run_walk_and_crouch_have_distinct_gains(self):
        a=self.g.audio;voice=Voice()
        with patch.dict(a.footstep_channels,{'player':voice}):
            for gait in ('run','walk','crouch'):a.footstep('player',gait)
        volumes=[max(volume) for _,volume in voice.calls]
        self.assertGreater(volumes[0],volumes[1]);self.assertGreater(volumes[1],volumes[2]*3)

    def test_general_effect_saturation_cannot_silence_or_replace_either_actor_step(self):
        a=self.g.audio
        for _ in range(30):a.play('death_breath',.1)
        self.assertIsNone(pygame.mixer.find_channel())
        a.footstep('player')
        self.assertIn(a.footstep_channels['player'].get_sound(),a.sounds['step'])
        point=self.g.player.pos
        a.footstep('hunter',source=point+pygame.Vector2(24,0),listener=point,ship_map=self.g.ship_map)
        self.assertIn(a.footstep_channels['hunter'].get_sound(),a.sounds['alien'])
        a.play('repair',.2)
        self.assertIn(a.footstep_channels['player'].get_sound(),a.sounds['step'])

    def test_hunter_step_pan_range_and_wall_muffling_follow_its_physical_source(self):
        g=self.g;a=g.audio;voice=Voice();listener=g.player.pos
        with patch.dict(a.footstep_channels,{'hunter':voice}):
            with patch.object(g.ship_map,'line_of_sight',return_value=True):
                a.footstep('hunter',source=listener-pygame.Vector2(60,0),listener=listener,ship_map=g.ship_map)
                a.footstep('hunter',source=listener+pygame.Vector2(60,0),listener=listener,ship_map=g.ship_map)
            with patch.object(g.ship_map,'line_of_sight',return_value=False):
                a.footstep('hunter',source=listener+pygame.Vector2(60,0),listener=listener,ship_map=g.ship_map)
            a.footstep('hunter',source=listener+pygame.Vector2(500,0),listener=listener,ship_map=g.ship_map)
        self.assertEqual(len(voice.calls),3)
        left,right,blocked=(volumes for _,volumes in voice.calls)
        self.assertGreater(left[0],left[1]);self.assertGreater(right[1],right[0])
        self.assertAlmostEqual(max(blocked),max(right)*.5)

    def test_mute_and_pause_prevent_new_footsteps_and_stop_all_actor_channels(self):
        a=self.g.audio;voice=Voice()
        a.footstep('player');a.toggle()
        self.assertTrue(all(not channel.get_busy() for channel in a.footstep_channels.values()))
        with patch.dict(a.footstep_channels,{'player':voice}):
            a.footstep('player');a.toggle();a.pause(True);a.footstep('player')
            self.assertEqual(voice.calls,[])
            a.pause(False);a.footstep('player');self.assertEqual(len(voice.calls),1)

    def test_adjacent_steps_use_different_recordings(self):
        a=self.g.audio;voice=Voice()
        with patch.dict(a.footstep_channels,{'player':voice}):
            for _ in range(16):a.footstep('player')
        for previous,current in zip(voice.calls,voice.calls[1:]):self.assertIsNot(previous[0],current[0])

    def test_audio_initialization_failure_keeps_reason_and_m_retries_without_losing_pause(self):
        g=self.g
        with patch('pygame.mixer.get_init',return_value=None),patch('pygame.mixer.init',side_effect=pygame.error('No output device')):
            audio=Audio()
        self.assertFalse(audio.available);self.assertEqual(audio.error,'No output device')
        audio.paused=True
        with patch.object(g,'audio',audio):
            self.assertEqual(g.presentation.audio_status(),'Ses cihazı yok · M: Tekrar dene')
            audio.toggle()
            self.assertTrue(audio.available);self.assertTrue(audio.paused)
            self.assertEqual(audio.error,'');self.assertEqual(g.presentation.audio_status(),'')
            audio.pause(False)

    def test_muting_has_visible_feedback_and_enabling_clears_it(self):
        g=self.g;g.audio.toggle()
        self.assertEqual(g.presentation.audio_status(),'Ses kapalı · M: Aç')
        g.audio.toggle();self.assertEqual(g.presentation.audio_status(),'')

    def test_running_has_a_faster_contact_cadence_than_walking(self):
        ship=ShipMap();counts=[]
        for keys in ({'d':True},{'d':True,'shift':True},{'d':True,'ctrl':True}):
            p=Player(ship,(1056,852));noise=NoiseSystem();tracker=BehaviorTracker()
            for _ in range(60):p.update(1/60,keys,noise,[],lambda _:None,tracker)
            counts.append(len(noise.events))
        self.assertGreater(counts[1],counts[0]);self.assertEqual(counts[0],counts[2])


class FrontalDeathTests(unittest.TestCase):
    def sequence(self,player,attacker):
        frame=pygame.Surface((C.SCREEN_W,C.SCREEN_H));frame.fill((13,17,20))
        return DeathSequence(frame,player,attacker,(0,-1))

    def test_capture_framing_faces_camera_even_at_opposite_world_view_edges(self):
        left=self.sequence((0,0),(-12,0));right=self.sequence((C.SCREEN_W,C.SCREEN_H),(C.SCREEN_W+12,C.SCREEN_H))
        a=pygame.Surface(left.size);b=pygame.Surface(right.size)
        left.update(.5);right.update(.5);left.draw(a);right.draw(b)
        self.assertEqual(pygame.image.tobytes(a,'RGB'),pygame.image.tobytes(b,'RGB'))

    def test_rendering_does_not_advance_animation_or_replay_impact_state(self):
        death=self.sequence((624,384),(636,384));death.update(.7)
        before=(death.elapsed,set(death.triggered),[p['pos'].copy() for p in death.particles])
        surface=pygame.Surface(death.size)
        for _ in range(5):death.draw(surface)
        self.assertEqual(before,(death.elapsed,death.triggered,[p['pos'] for p in death.particles]))
        self.assertEqual(death.update(.01),[])

    def test_last_frame_fades_completely_before_the_ending(self):
        death=self.sequence((624,384),(636,384));death.update(10)
        surface=pygame.Surface(death.size);death.draw(surface)
        for point in ((0,0),(624,429),(1247,857)):
            self.assertLess(max(surface.get_at(point)[:3]),9)


if __name__=='__main__':unittest.main()
