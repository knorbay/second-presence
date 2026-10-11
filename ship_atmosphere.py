"""Local steam releases and fading physical traces of actual creature movement."""
import math
import random
from collections import deque
import pygame
import config as C
from scenery import equipment_point
from survival import conditions_for


class ShipAtmosphere:
    def __init__(self):
        self.rng=random.Random()
        self.reset(1)

    def reset(self,day):
        self.day=day
        self.clock=0.0
        self.cooldown=self.rng.uniform(16,24)
        self.steam=None
        self.tracks=deque(maxlen=120)
        self.last_track=None

    def presence_cues(self,day_time,dt,ship_map,listener,seed):
        if listener is None or self.day not in (2,3):return []
        # Absolute shift time prevents old cues from replaying or bunching up on load.
        timeline=((36,'vent_knock'),(103,'vent_drag'),(192,'vent_knock'),(307,'vent_drag')) if self.day==2 else ((18,'vent_knock'),(43,'vent_drag'))
        events=[]
        for index,(when,sound) in enumerate(timeline):
            when+=(seed//(index+1))%9
            if not day_time<=when<day_time+dt:continue
            # Use the actual corridor grilles drawn by Presentation, close enough
            # to hear through a partition without implying a visible creature.
            points=[]
            for y,row in enumerate(ship_map.grid):
                for x,tile in enumerate(row):
                    point=pygame.Vector2((x+.5)*C.TILE,(y+.5)*C.TILE)
                    if tile or (x*3+y)%6 or not 90<point.distance_to(listener)<240:continue
                    if ship_map.room_at_world(*point):continue
                    if any(ship_map.is_wall_tile(x+dx,y+dy) for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))):points.append(point)
            if not points:points=[equipment_point(r) for r in ship_map.rooms]
            nearby=sorted(points,key=lambda p:p.distance_to(listener))[:3]
            if nearby:events.append((sound,nearby[(seed+index)%len(nearby)]))
        return events

    def update(self,dt,ship_map,serviced,noise,day_time=None,listener=None,seed=0):
        events=self.presence_cues(self.clock if day_time is None else day_time,dt,ship_map,listener,seed)
        self.clock+=dt
        while self.tracks and self.clock-self.tracks[0][2]>90:self.tracks.popleft()
        if self.steam:
            self.steam['age']+=dt
            if self.steam['age']>=3.2 or serviced.get('Cooling') or serviced.get(self.steam['room']):
                self.steam=None
        self.cooldown-=dt
        if self.cooldown>0:return events
        self.cooldown=self.rng.uniform(25,43)
        leaks=[name for name in conditions_for(self.day).leak_rooms if not serviced.get(name)]
        if serviced.get('Cooling') or not leaks or self.steam:return events
        name=self.rng.choice(leaks)
        point=equipment_point(ship_map.room_by_name(name))
        self.steam={'room':name,'point':point,'age':0.0,'phase':self.rng.random()*math.tau}
        # Machinery can legitimately draw the hunter's attention to this room.
        noise.emit(point,260,12,'steam')
        return events+[('steam',point)]

    def record_motion(self,alien,ship_map):
        if self.day<2 or not alien.moved_this_frame or alien.state=='DORMANT':return
        if self.last_track is not None and alien.pos.distance_to(self.last_track)<30:return
        if ship_map.is_blocked_circle(*alien.pos,C.ALIEN_RADIUS):return
        self.last_track=alien.pos.copy()
        self.tracks.append((alien.pos.copy(),alien.facing_angle,self.clock))

    def draw(self,surface,visible=lambda point:True):
        for position,angle,stamp in self.tracks:
            if not visible(position):continue
            fade=max(0,1-(self.clock-stamp)/90)
            color=(int(40+57*fade),int(35+27*fade),int(33+18*fade))
            forward=pygame.Vector2(math.cos(angle),math.sin(angle))
            side=pygame.Vector2(-forward.y,forward.x)
            for sign in (-1,1):
                for n in range(3):
                    p=position+side*(sign*8+n*2)
                    bend=p+forward*2+side*sign
                    pygame.draw.lines(surface,color,False,[p-forward*4,bend,bend+forward*3-side*sign*2],1)
        if self.steam and visible(self.steam['point']):
            age=self.steam['age'];source=self.steam['point'];phase=self.steam['phase']
            opacity=math.sin(math.pi*min(1,age/3.2))
            # Render particles at their room, before the normal flashlight / wall mask.
            for n in range(18):
                life=(age*.7+n*.17)%1
                direction=pygame.Vector2(-1,math.sin(n*2.3+phase)*.6).normalize()
                p=source+direction*(12+life*72)+pygame.Vector2(0,math.sin(age*2+n)*5)
                radius=6+round(life*12)
                puff=pygame.Surface((radius*2+2,radius*2+2),pygame.SRCALPHA)
                for ring in range(radius,0,-1):
                    alpha=round(50*opacity*(1-life)*(1-ring/radius)**.6)
                    pygame.draw.circle(puff,(112,117,118,alpha),(radius+1,radius+1),ring)
                surface.blit(puff,(p.x-radius,p.y-radius))
