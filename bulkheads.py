"""Manual bulkheads: solid sight barriers that a physically nearby hunter can breach."""
from dataclasses import dataclass
import math
import pygame
import config as C


@dataclass
class Bulkhead:
    name: str
    tiles: tuple
    closed: bool=False
    broken: bool=False
    damage: float=0.0
    visual: float=0.0
    cooldown: float=0.0
    hit_timer: float=0.0
    impact: float=0.0

    @property
    def rect(self):return pygame.Rect(*(value*C.TILE for value in self.tiles))
    @property
    def center(self):return pygame.Vector2(self.rect.center)


def circle_touches(position,radius,rect):
    x,y=position
    nx=max(rect.left,min(x,rect.right));ny=max(rect.top,min(y,rect.bottom))
    return (x-nx)**2+(y-ny)**2<radius**2


class Bulkheads:
    def __init__(self,ship_map):
        self.ship_map=ship_map
        self.doors=[Bulkhead('Oxygen',(7,14,3,1)),Bulkhead('Reactor',(52,13,3,1)),
                    Bulkhead('Cooling',(92,12,3,1)),Bulkhead('Hangar',(93,27,3,1))]
        self.reset(1)

    def reset(self,day):
        self.day=day;self.events=[]
        for door in self.doors:
            door.closed=door.broken=False
            door.damage=door.visual=door.cooldown=door.hit_timer=door.impact=0.0

    def at_tile(self,tx,ty):
        return next((door for door in self.doors if pygame.Rect(door.tiles).collidepoint(tx,ty)),None)

    def blocking(self,position,radius):
        return next((door for door in self.doors if door.closed and circle_touches(position,radius,door.rect)),None)

    def nearby(self,position):
        candidates=[]
        for door in self.doors:
            r=door.rect
            if pygame.Vector2(position).distance_to(door.center)>65:continue
            handles=((r.centerx,r.top-14),(r.centerx,r.bottom+14))
            if any(self.ship_map.line_of_sight(*position,*handle) for handle in handles):candidates.append(door)
        return min(candidates,key=lambda door:pygame.Vector2(position).distance_to(door.center)) if candidates else None

    def _set_closed(self,door,closed):
        if door.closed==closed:return
        door.closed=closed
        x,y,w,h=door.tiles
        for ty in range(y,y+h):
            for tx in range(x,x+w):self.ship_map.grid[ty][tx]=1 if closed else 0
        self.ship_map.geometry_revision+=1

    def toggle(self,door,actors):
        if door.broken:return 'broken'
        if door.cooldown>0:return 'busy'
        if not door.closed and any(circle_touches(pos,radius,door.rect) for pos,radius in actors):return 'occupied'
        self._set_closed(door,not door.closed)
        door.cooldown=.65
        kind='close' if door.closed else 'open'
        self.events.append((kind,pygame.Vector2(actors[0][0]) if actors else door.center))
        return kind

    def update(self,dt):
        for door in self.doors:
            door.cooldown=max(0,door.cooldown-dt)
            door.impact=max(0,door.impact-dt)
            desired=1.0 if door.closed else 0.0
            door.visual+=max(-dt*5,min(dt*5,desired-door.visual))

    @property
    def breach_time(self):return max(2.2,3.2-.12*max(0,self.day-2))

    def force(self,door,position,dt):
        if not door.closed or door.broken or not circle_touches(position,24,door.rect):return False
        door.damage+=max(0,dt)
        door.hit_timer-=dt
        if door.damage>=self.breach_time:
            door.broken=True;self._set_closed(door,False)
            door.impact=.25
            self.events.append(('breach',pygame.Vector2(position)))
            return True
        if door.hit_timer<=0:
            door.hit_timer=.5;door.impact=.16
            self.events.append(('hit',pygame.Vector2(position)))
        return False

    def drain_events(self):
        events=self.events;self.events=[]
        return events

    def draw(self,surface,time):
        for door in self.doors:self._draw_door(surface,door,time)

    def _draw_door(self,surface,door,time,offset=(0,0)):
        r=door.rect.move(offset)
        # Solid rails and retracted leaves explain where the passage can close.
        pygame.draw.rect(surface,(89,85,74),r,2)
        pygame.draw.line(surface,(18,21,24),(r.left,r.top+3),(r.right,r.top+3),2)
        pygame.draw.line(surface,(18,21,24),(r.left,r.bottom-4),(r.right,r.bottom-4),2)
        width=max(5,round(r.w*.5*door.visual))
        shake=round(math.sin(time*100)*2*min(1,door.impact/.16)) if door.closed else 0
        left=pygame.Rect(r.x,r.y+4+shake,width,r.h-8);right=pygame.Rect(r.right-width,r.y+4-shake,width,r.h-8)
        for leaf in (left,right):
            pygame.draw.rect(surface,(72,74,72),leaf)
            pygame.draw.rect(surface,(115,111,94),leaf,1)
            for xx in range(leaf.x+4,leaf.right-2,9):
                pygame.draw.line(surface,(37,40,42),(xx,leaf.top+3),(xx,leaf.bottom-3))
        if door.closed:
            pygame.draw.line(surface,(20,22,24),(r.centerx,r.top+4),(r.centerx,r.bottom-4),2)
        color=(140,94,66) if door.closed else (99,118,99)
        pygame.draw.rect(surface,color,(r.right+2,r.centery-3,3,6))
        for n in range(min(3,math.ceil(door.damage))) if door.closed else ():
            x=r.centerx-7+n*5
            pygame.draw.line(surface,(20,21,24),(x-5,r.top+5),(x+3,r.bottom-5),2)
        if door.broken:
            for side in (-1,1):
                x=r.centerx+side*(r.w//2-8)
                pygame.draw.lines(surface,(125,114,91),False,[(x,r.top+5),(x-side*5,r.centery),(x+side*3,r.bottom-5)],2)

    def draw_front_faces(self,surface,time,origin,facing,lighting,radius,power,ambient=0):
        """Light the first solid surface, without revealing actors or floor behind it."""
        for door in self.doors:
            if not door.closed:continue
            r=door.rect
            if abs(origin[1]-r.centery)<r.h/2:continue
            face_y=r.bottom+1 if origin[1]>r.centery else r.top-1
            sprite=pygame.Surface(r.size,pygame.SRCALPHA)
            self._draw_door(sprite,door,time,(-r.x,-r.y))
            # Visibility is checked per strip at the near surface, not at its blocked centre.
            for x in range(0,r.w,3):
                strength=lighting.strength_at(self.ship_map,origin,facing,(r.x+x+1,face_y),radius,power,ambient)
                if not strength:continue
                strip=sprite.subsurface((x,0,min(3,r.w-x),r.h)).copy()
                strip.set_alpha(strength)
                surface.blit(strip,(r.x+x,r.y))
