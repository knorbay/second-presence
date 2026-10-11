"""Task consequences, physical traces and optional crew-log interaction."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
import unittest
from collections import defaultdict
from unittest.mock import patch
import pygame
from main import Game,PHASE_PLAYING,PHASE_GAME_OVER
from ship_atmosphere import ShipAtmosphere
from crew_logs import LOGS,log_point,Logbook
from entities import Alien,STATE_WANDER,STATE_CHASE
from shipmap import ShipMap
from systems import NoiseSystem
from audio import regional_targets
from scenery import equipment_point
from localization import set_language,tr


class PhysicalEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.ship=ShipMap();self.env=ShipAtmosphere();self.env.reset(3);self.noise=NoiseSystem()

    def test_steam_has_a_real_room_source_and_one_noise_event_per_release(self):
        self.env.cooldown=0
        cues=self.env.update(.1,self.ship,{},self.noise)
        self.assertEqual(len(cues),1);self.assertEqual(self.env.steam['room'],'Cargo Bay')
        self.assertEqual(self.noise.events[0].kind,'steam')
        self.assertEqual(self.noise.events[0].pos,equipment_point(self.ship.room_by_name('Cargo Bay')))
        self.noise.clear();self.env.update(.1,self.ship,{},self.noise)
        self.assertEqual(self.noise.events,[])
        self.env.update(3.3,self.ship,{},self.noise);self.assertIsNone(self.env.steam)

    def test_cooling_stops_releases_and_a_new_fault_can_restore_them(self):
        self.env.cooldown=0;self.env.update(.1,self.ship,{},self.noise)
        self.assertIsNotNone(self.env.steam)
        self.env.update(.1,self.ship,{'Cooling':True},self.noise);self.assertIsNone(self.env.steam)
        self.env.cooldown=0;self.noise.clear()
        self.assertEqual(self.env.update(.1,self.ship,{'Cooling':True},self.noise),[])
        self.assertEqual(self.noise.events,[])
        self.env.cooldown=0
        self.assertTrue(self.env.update(.1,self.ship,{'Cooling':False},self.noise))

    def test_traces_follow_actual_motion_and_fade_without_growing_indefinitely(self):
        a=Alien(self.ship,(1200,564));a.state=STATE_WANDER;a.moved_this_frame=False
        self.env.record_motion(a,self.ship);self.assertEqual(len(self.env.tracks),0)
        a.moved_this_frame=True;self.env.record_motion(a,self.ship)
        saved=self.env.tracks[0][0].copy();a.pos.x+=5
        self.env.record_motion(a,self.ship);self.assertEqual(len(self.env.tracks),1)
        a.pos.x+=40;self.env.record_motion(a,self.ship)
        self.assertEqual(len(self.env.tracks),2);self.assertEqual(saved,pygame.Vector2(1200,564))
        self.env.update(91,self.ship,{'Cooling':True},self.noise)
        self.assertEqual(len(self.env.tracks),0)

    def test_logs_need_physical_proximity_visibility_and_their_unlock_day(self):
        book=Logbook();entry=LOGS[2];point=log_point(self.ship,entry)
        self.assertIsNone(book.nearby(self.ship,point,3))
        self.assertEqual(book.nearby(self.ship,point,4),entry)
        self.assertIsNone(book.nearby(self.ship,point+pygame.Vector2(90,0),4))
        with patch.object(self.ship,'line_of_sight',return_value=False):self.assertIsNone(book.nearby(self.ship,point,4))


class EnvironmentIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.g=Game(campaign_seed=0)
    @classmethod
    def tearDownClass(cls):set_language('tr');pygame.quit()
    def setUp(self):
        g=self.g;g.paused=False;g.audio.pause(False);g._restart_game(campaign_seed=0);g._advance_from_transition();g._keys=lambda:{}

    def test_power_requires_full_job_then_stops_blackouts_and_fault_reactivates_them(self):
        g=self.g;g.day=3;g._start_day();g.phase=PHASE_PLAYING;g.day_time=74
        g._update(.1);self.assertTrue(g.conditions.blackout)
        g._on_interact_complete('Power');g._update(.1);self.assertTrue(g.conditions.blackout)
        while not g.tasks.tasks['Power'].done:g._on_interact_complete('Power')
        g._update(.1);self.assertFalse(g.conditions.blackout)
        g.tasks.tasks['Power'].reopen();g._update(.1);self.assertTrue(g.conditions.blackout)

    def test_completed_task_changes_the_room_mix_without_changing_other_sources(self):
        g=self.g;source=equipment_point(g.ship_map.room_by_name('Power'))
        before=regional_targets(source,g.ship_map,serviced=g.serviced_systems())
        while not g.tasks.tasks['Power'].done:g._on_interact_complete('Power')
        after=regional_targets(source,g.ship_map,serviced=g.serviced_systems())
        self.assertLess(after['Power'][0],before['Power'][0])
        self.assertEqual(after['Cooling'],before['Cooling'])

    def discover(self,entry):
        g=self.g;g.player.pos=log_point(g.ship_map,entry);g._e_pressed=True;g._update_panel(.01,{})

    def test_reading_log_adds_no_tasks_and_keeps_clock_running(self):
        g=self.g;self.discover(LOGS[0]);self.assertTrue(g.logbook.open)
        self.assertEqual(len(g.tasks.tasks),5);self.assertIsNone(g.panel_work)
        before=g.day_time;g._update(.1);self.assertGreater(g.day_time,before)
        g.paused=True;g._update(1);self.assertEqual(g.day_time,before+.1)

    def test_records_persist_between_shifts_but_clear_on_restart(self):
        g=self.g;self.discover(LOGS[0]);g.day=2;g._start_day()
        self.assertIn('shift',g.logbook.found);self.assertFalse(g.logbook.open)
        g._restart_game(campaign_seed=0);self.assertEqual(g.logbook.found,set())

    def test_journal_keyboard_pages_do_not_move_player_and_escape_only_closes_it(self):
        g=self.g;g.logbook.discover(LOGS[0]);g.logbook.discover(LOGS[1]);before=g.player.pos.copy()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_LEFT));g._handle_events()
        self.assertEqual(g.logbook.current.key,'shift')
        g._keys=lambda:Game._keys(g)
        with patch('pygame.key.get_pressed',return_value=defaultdict(bool,{pygame.K_LEFT:True})):g._update(.1)
        self.assertTrue(g.logbook.open);self.assertEqual(g.player.pos,before)
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_ESCAPE));g._handle_events()
        self.assertFalse(g.logbook.open);self.assertFalse(g.paused)

    def test_walking_closes_reading_and_death_cannot_leave_journal_over_the_attack(self):
        g=self.g;self.discover(LOGS[0]);g._keys=lambda:{'d':True};g._update(.1)
        self.assertFalse(g.logbook.open)
        g.player.pos=pygame.Vector2(1260,576);g.camera=g.camera_target()
        g.logbook.open=True;g.alien.pos=g.player.pos+pygame.Vector2(12,0);g.alien.state=STATE_CHASE
        g._check_catch();self.assertEqual(g.phase,PHASE_GAME_OVER);self.assertFalse(g.logbook.open)
        g._render()

    def test_all_recording_text_and_new_feedback_have_english_translations(self):
        set_language('en')
        for entry in LOGS:
            self.assertNotEqual(tr(entry.title),entry.title);self.assertNotEqual(tr(entry.body),entry.body)
        self.assertEqual(tr('Bulunan kayıt: 2 / 4'),'Logs found: 2 / 4')
        self.assertEqual(tr('Güç kararlı. Kesintiler durdu.'),'Power is stable. Outages stopped.')
        set_language('tr')


if __name__=='__main__':unittest.main()
