"""Title scene built with the game's deck, lighting and creature renderer."""
import math
import pygame
import config as C
from shipmap import ShipMap
from creature import draw_creature
from lighting import Lighting
from localization import language
from render_surfaces import opaque_surface


def draw_ship_mark(surface,rect,color=(213,212,198)):
    """Two offset hatch silhouettes: a simple mark that survives small sizes."""
    x,y,w,h=rect;unit=min(w,h)/40
    def points(coords):return [(round(x+a*unit),round(y+b*unit)) for a,b in coords]
    thickness=max(1,round(unit*2))
    pygame.draw.lines(surface,color,False,points([(3,34),(3,8),(10,2),(25,2),(31,8),(31,34)]),thickness)
    pygame.draw.lines(surface,color,False,points([(10,38),(10,13),(16,7),(31,7),(37,13),(37,38)]),thickness)
    pygame.draw.line(surface,color,points([(1,38)])[0],points([(39,38)])[0],thickness)
    # One interrupted threshold, rather than a textured badge or character portrait.
    pygame.draw.line(surface,color,points([(16,29)])[0],points([(16,35)])[0],thickness)


class MenuScene:
    def __init__(self,game):
        self.g=game
        self.ship_map=ShipMap();self.ship_map.set_day(3)
        self.lighting=Lighting()
        self.deck=None;self.deck_language=None
        self.world=opaque_surface((C.WORLD_W,C.WORLD_H))
        self.fog=pygame.Surface(self.world.get_size(),pygame.SRCALPHA);self.fog.fill((0,0,0,255))
        self.player=pygame.Vector2(1284,588)
        self.crop=pygame.Rect(974,186,460,477)
        self.viewport=pygame.Rect(420,0,C.SCREEN_W-420,C.SCREEN_H)
        # Fixed composition; no game actors or player state are changed for this scene.
        self.fade=pygame.Surface(self.viewport.size,pygame.SRCALPHA)
        for x in range(self.viewport.w):
            alpha=round(235*max(0,1-x/190))
            pygame.draw.line(self.fade,(7,10,12,alpha),(x,0),(x,self.viewport.h))
        vertical=pygame.Surface(self.viewport.size,pygame.SRCALPHA)
        for y in range(self.viewport.h):
            alpha=round(120*max(0,1-min(y,self.viewport.h-1-y)/110))
            pygame.draw.line(vertical,(7,10,12,alpha),(0,y),(self.viewport.w,y))
        self.fade.blit(vertical,(0,0),special_flags=pygame.BLEND_RGBA_MAX)

    def draw(self,surface,time,still=False):
        if self.deck is None or self.deck_language!=language():
            self.deck=self.g.presentation._build_ship(self.ship_map)
            self.deck.fill((15,17,18),special_flags=pygame.BLEND_RGB_ADD)
            self.deck_language=language()
        self.world.blit(self.deck,(0,0))
        angle=-math.pi/2+(0 if still else math.sin(time*.32)*.09)
        pos=self.player
        draw_creature(self.world,(1282,402),math.pi/2,time,moving=False)
        pygame.draw.circle(self.world,(10,22,29),tuple(pos),C.PLAYER_RADIUS+3)
        pygame.draw.circle(self.world,C.COL_PLAYER,tuple(pos),C.PLAYER_RADIUS)
        facing=pygame.Vector2(math.cos(angle),math.sin(angle))
        pygame.draw.circle(self.world,(169,174,177),tuple(pos+facing*3),3)
        pygame.draw.line(self.world,C.COL_PLAYER,pos,pos+facing*(C.PLAYER_RADIUS+6),2)
        # Render the same wall-clipped falloff used in play; darkness has geometry.
        self.lighting.apply(self.world,self.fog,self.ship_map,tuple(pos),angle,330,1.0,.26)
        art=pygame.transform.scale(self.world.subsurface(self.crop),self.viewport.size)
        surface.blit(art,self.viewport)
        surface.blit(self.fade,self.viewport)
