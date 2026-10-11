"""Keep the zoomed camera and precise light boundaries aligned with the real map."""
import math
import os
import tempfile
import unittest
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
import config as C
from fov import _cast_ray
from shipmap import ShipMap
from main import Game,PHASE_PLAYING


class LightBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.ship=ShipMap()
        self.ship.grid=[[0]*C.COLS for _ in range(C.ROWS)]

    def test_wall_hits_are_on_the_surface_at_multiple_angles(self):
        for row in self.ship.grid:row[20]=1
        for angle in (-.7,-.3,0,.3,.7):
            x,y,distance=_cast_ray(self.ship,400,300,angle,230)
            self.assertAlmostEqual(x,480)
            self.assertAlmostEqual(y,300+math.tan(angle)*80)
            self.assertLess(distance,230)

    def test_touching_solid_corners_do_not_leak_light(self):
        self.ship.grid[4][5]=1
        self.ship.grid[5][4]=1
        x,y,_=_cast_ray(self.ship,108,108,math.pi/4,230)
        self.assertAlmostEqual(x,120);self.assertAlmostEqual(y,120)

    def test_negative_direction_and_open_space_respect_range(self):
        for row in self.ship.grid:row[2]=1
        x,y,distance=_cast_ray(self.ship,100,300,math.pi,230)
        self.assertAlmostEqual(x,72);self.assertAlmostEqual(distance,28)
        x,y,distance=_cast_ray(self.ship,100,300,0,77)
        self.assertAlmostEqual(x,177);self.assertEqual(distance,77)


class CameraFramingTests(unittest.TestCase):
    def test_camera_stays_on_the_deck_and_actor_coordinates_match_the_crop(self):
        with tempfile.TemporaryDirectory() as storage:
            g=Game(storage,campaign_seed=0);g.phase=PHASE_PLAYING
            for point in ((1,1),(C.WORLD_W-1,1),(1,C.WORLD_H-1),(C.WORLD_W-1,C.WORLD_H-1),(1100,600)):
                g.player.pos=pygame.Vector2(point);g.camera=g.camera_target()
                r=pygame.Rect(*g.camera,C.CAMERA_W,C.CAMERA_H)
                self.assertTrue(g.world_surface.get_rect().contains(r))
                p=g.world_to_view(g.player.pos)
                self.assertGreaterEqual(p.x,0);self.assertLess(p.x,C.SCREEN_W)
                self.assertGreaterEqual(p.y,0);self.assertLess(p.y,C.VIEW_H)
                g._render()
            self.assertLess(g.world_to_view(g.player.pos).distance_to((C.SCREEN_W/2,C.VIEW_H/2)),2)
