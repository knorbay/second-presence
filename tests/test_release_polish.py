"""First-contact fairness, purposeful Foley and complete player-facing localisation."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import math
import tempfile
import unittest
from array import array
from unittest.mock import patch
import pygame
from main import Game,PHASE_PLAYING
from entities import STATE_DORMANT,STATE_CHASE
from systems import NoiseSystem,BehaviorTracker
from localization import tr,set_language,EN
from survival import DAYS
from crew_logs import LOGS
from maintenance import PanelWork


class ReleasePolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.g=Game(cls.tmp.name,campaign_seed=17)
    @classmethod
    def tearDownClass(cls):
        set_language('tr');pygame.quit();cls.tmp.cleanup()
    def setUp(self):
        self.g.paused=False;self.g._restart_game(campaign_seed=17)
        self.g.phase=PHASE_PLAYING;self.g._keys=lambda:{}
        self.g.audio.pause(False);self.g.audio.enabled=True
    def day(self,n,time=0):
        g=self.g;g.day=n;g._start_day();g.day_time=time;g.phase=PHASE_PLAYING
        return g
    def test_day_two_is_safe_even_with_direct_contact_and_loud_noise(self):
        g=self.day(2)
        for time in (0,45,150,300,419):
            g.alien.pos=g.player.pos.copy();g.alien.state=STATE_CHASE
            g.noise.emit(g.player.pos,600,100,'run')
            g.alien.update(.05,g.player,g.ship_map,g.noise,g.tracker,2,time,time)
            g._check_catch()
            self.assertEqual(g.alien.state,STATE_DORMANT)
            self.assertFalse(g.alien.moved_this_frame)
            self.assertEqual(g.phase,PHASE_PLAYING)
    def test_first_hunt_starts_off_screen_after_warning_interval(self):
        g=self.day(3,64.9);g.player.pos=g.alien.pos.copy()
        g._update_playing(.05)
        self.assertEqual(g.alien.state,STATE_DORMANT)
        g.day_time=65;g._update_playing(.05)
        self.assertNotEqual(g.alien.state,STATE_DORMANT)
        self.assertGreater(g.alien.pos.distance_to(g.player.pos),300)
        self.assertFalse(g.ship_map.line_of_sight(*g.player.pos,*g.alien.pos))
        self.assertIsNone(g.alien.last_seen_position)
        self.assertEqual(g.phase,PHASE_PLAYING)
    def test_load_of_old_day_two_chase_does_not_restore_an_early_attack(self):
        g=self.day(2,120);g.alien.state=STATE_CHASE
        g.alien.pos=g.player.pos.copy();snapshot=g.store.snapshot(g)
        g.store.load(g,snapshot)
        self.assertEqual(g.alien.state,STATE_DORMANT)
        g._update_playing(.05);self.assertEqual(g.phase,PHASE_PLAYING)
        self.assertAlmostEqual(g.day_time,120.05)
    def test_warning_cues_do_not_replay_past_events_after_loading(self):
        g=self.day(2);at=g.atmosphere
        calls=[]
        for t in range(420):calls+=at.presence_cues(t,1,g.ship_map,g.player.pos,17)
        self.assertEqual([n for n,p in calls],['vent_knock','vent_drag','vent_knock','vent_drag'])
        self.assertEqual(at.presence_cues(360,.05,g.ship_map,g.player.pos,17),[])
        at.reset(1);self.assertEqual(at.presence_cues(0,420,g.ship_map,g.player.pos,17),[])
    def test_waiting_at_panel_makes_no_fake_hammering_but_real_actions_have_feedback(self):
        g=self.g;g.tasks.campaign_seed=0;g.tasks.reset_day(1)
        g.panel_work=PanelWork('Power','rewire',1)
        g.player.pos=g.ship_map.room_by_name('Power').world_center.copy()
        with patch.object(g.audio,'play') as sound:
            g._update_panel(.7,{})
            self.assertEqual(sound.call_count,0)
            g.panel_inputs=['1'];g._update_panel(.1,{})
            self.assertIn('switch',[c.args[0] for c in sound.call_args_list])
            for kind in ('filter','valves','cargo'):
                g.audio._panel_cooldown=0;g.audio.panel_feedback(kind,'progress')
            self.assertTrue({'brush','valve','cargo'}<={c.args[0] for c in sound.call_args_list})
    def test_muted_audio_does_not_start_detail_voices(self):
        g=self.g;g.audio.enabled=False
        with patch('pygame.mixer.find_channel') as channel:
            g.audio.panel_feedback('filter','progress')
            g.audio.panel_feedback('inspect','wrong')
            g.audio.panel_feedback('wires','complete')
            self.assertEqual(channel.call_count,0)
    def test_new_foley_has_no_clipping_or_click_at_endpoints(self):
        for name in ('vent_knock','vent_drag','creature','brush','switch','cargo','valve','confirm','reject'):
            for sound in self.g.audio.sounds[name]:
                data=array('h',sound.get_raw())
                self.assertGreater(max(map(abs,data)),150)
                self.assertLess(max(map(abs,data)),30000)
                self.assertLess(max(map(abs,data[:2])),10)
                self.assertLess(max(map(abs,data[-2:])),50)
    def test_full_daily_descriptions_and_logs_translate_without_turkish_fragments(self):
        set_language('en')
        for text in [d.description for d in DAYS.values()]+[e.body for e in LOGS]:
            self.assertIn(text,EN)
            self.assertNotRegex(tr(text),r'[şŞğĞıİçÇöÖüÜ]')
        self.assertEqual(tr('3. vardiyada yakalandın. Görüşü kesmeden saklanmak tehlikeli.'),
                         'Caught on shift 3. Break line of sight before hiding.')
        self.assertEqual(tr('Önceki gün 3/5 bakım tamamlandı.'),'Previous shift: 3 of 5 jobs completed.')
        self.assertEqual(tr('Gün 3 · Genel aydınlatma kapalı.'),'Day 3 · General lighting offline.')
        self.assertEqual(tr('Gemi %80'),'Hull 80%')
        set_language('tr');self.assertEqual(tr('Gemi %80'),'Gemi %80')

if __name__=='__main__':unittest.main()
