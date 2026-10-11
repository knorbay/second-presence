"""Finite first-person capture: a frontal face, claws against the lens and blood."""
import math
import random
import pygame
from creature_portrait import FrontCreature


class DeathSequence:
    DURATION=3.4
    IMPACTS=((.18,'death_hit'),(.63,'tear'),(1.08,'death_hit'),(1.52,'tear'))

    def __init__(self,frame,player,attacker,facing,time=0):
        self.elapsed=0.0;self.time=time
        self.rng=random.Random(710)
        self.particles=[];self.triggered=set()
        self.size=frame.get_size();self.frozen=frame.copy()
        self.background=self._corridor()
        self.creature=FrontCreature()
        self.stains=pygame.Surface(self.size,pygame.SRCALPHA)
        w,h=self.size
        self.drips=[(self.rng.randrange(w),self.rng.randint(4,10),self.rng.uniform(.2,1.5)) for _ in range(24)]
        self.strikes=[[(w*.12,h*.22),(w*.46,h*.58)],[(w*.86,h*.30),(w*.60,h*.70)],
                      [(w*.20,h*.69),(w*.65,h*.84)],[(w*.70,h*.13),(w*.46,h*.45)]]

    def _corridor(self):
        w,h=self.size;s=pygame.Surface(self.size);s.fill((8,10,13))
        vanishing=(round(w*.5),round(h*.43))
        pygame.draw.polygon(s,(23,24,26),[(0,0),(w*.34,h*.19),vanishing,(0,h)])
        pygame.draw.polygon(s,(16,18,22),[(w,0),(w*.66,h*.19),vanishing,(w,h)])
        pygame.draw.polygon(s,(20,21,24),[(0,h),vanishing,(w,h)])
        for t in (.14,.27,.42,.60,.80):
            left=round(vanishing[0]*(1-t));right=w-left
            top=round(vanishing[1]*(1-t));bottom=round(vanishing[1]+(h-vanishing[1])*t)
            pygame.draw.lines(s,(34,34,34),False,[(left,bottom),(left,top),(right,top),(right,bottom)],max(1,round(t*5)))
            pygame.draw.line(s,(42,42,38),(left+5,top+12),(left+5,round(top+(bottom-top)*.23)),max(1,round(t*3)))
        for x in range(0,w+1,max(1,w//8)):pygame.draw.line(s,(30,31,31),vanishing,(x,h),2)
        return s

    @property
    def complete(self):return self.elapsed>=self.DURATION

    def update(self,dt):
        if self.complete:return []
        dt=max(0,dt);previous=self.elapsed
        self.elapsed=min(self.DURATION,self.elapsed+dt)
        cues=[]
        for index,(when,sound) in enumerate(self.IMPACTS):
            if previous<when<=self.elapsed and index not in self.triggered:
                self.triggered.add(index);cues.append(sound);self._spray(index)
        for particle in self.particles[:]:
            particle['age']+=dt
            particle['pos']+=particle['velocity']*dt
            particle['velocity']*=max(0,1-dt*2.8)
            if particle['age']>=particle['life']:
                pygame.draw.circle(self.stains,particle['color'],particle['pos'],particle['radius'])
                self.particles.remove(particle)
        return cues

    def _spray(self,index):
        w,h=self.size
        start,end=(pygame.Vector2(point) for point in self.strikes[index])
        origin=start.lerp(end,.5)
        for _ in range(52):
            angle=self.rng.uniform(0,math.tau);speed=self.rng.uniform(130,660)
            self.particles.append({'pos':origin.copy(),
                'velocity':pygame.Vector2(math.cos(angle),math.sin(angle))*speed,
                'age':0.0,'life':self.rng.uniform(.18,.65),'radius':self.rng.randint(3,10),
                'color':self.rng.choice([(107,13,23,230),(138,25,30,235),(70,8,18,240),(155,41,37,235)])})
        direction=end-start;normal=pygame.Vector2(-direction.y,direction.x).normalize()
        for finger in range(3):
            shift=normal*(finger-1)*18
            pygame.draw.line(self.stains,(76,7,18,210),start+shift,end+shift,8-finger)
            pygame.draw.line(self.stains,(137,32,33,190),start+shift+normal*3,end+shift+normal*3,2)
        for _ in range(25):
            position=origin+pygame.Vector2(self.rng.uniform(-w*.29,w*.29),self.rng.uniform(-h*.26,h*.30))
            radius=self.rng.randrange(4,19)
            pygame.draw.ellipse(self.stains,(85+self.rng.randrange(36),11,21,210),
                                (position.x-radius,position.y-radius,radius*2,radius*1.4))

    def draw(self,surface):
        t=self.elapsed
        impact=max(max(0,1-(t-when)/.22) if t>=when else 0 for when,_ in self.IMPACTS)
        offset=pygame.Vector2(math.sin(t*93),math.cos(t*77))*impact*14
        surface.fill((5,5,8));surface.blit(self.background,offset)
        self.creature.draw(surface,t,impact,offset)
        if t<.12:
            frozen=self.frozen.copy();frozen.set_alpha(round(255*(1-t/.12)));surface.blit(frozen,(0,0))
        overlay=pygame.Surface(self.size,pygame.SRCALPHA)
        overlay.blit(self.stains,(0,0))
        for index,(when,_) in enumerate(self.IMPACTS):
            age=t-when
            if 0<=age<.16:
                start,end=(pygame.Vector2(point) for point in self.strikes[index])
                normal=pygame.Vector2(-(end-start).y,(end-start).x).normalize()
                for finger in range(3):
                    shift=normal*(finger-1)*18
                    pygame.draw.line(overlay,(178,145,115,235),start+shift,start.lerp(end,age/.16)+shift,3)
        for particle in self.particles:
            p=particle['pos']
            pygame.draw.circle(overlay,particle['color'],p,particle['radius'])
            pygame.draw.line(overlay,particle['color'],p,p-particle['velocity']*.025,max(1,particle['radius']//2))
        if t>.25:
            amount=min(1,(t-.25)/1.5)
            for x,width,delay in self.drips:
                length=max(0,int((t-delay)*95))*amount
                if length>0:
                    pygame.draw.line(overlay,(77,7,18,185),(x,0),(x,length),width)
                    pygame.draw.circle(overlay,(111,16,26,205),(x,round(length)),width)
            for n in range(14):
                pygame.draw.rect(overlay,(42,0,8,round(9*amount)),
                                  pygame.Rect(n*7,n*7,self.size[0]-n*14,self.size[1]-n*14),7)
        if impact>.05:
            flash=pygame.Surface(self.size,pygame.SRCALPHA);flash.fill((130,105,92,round(impact*45)))
            overlay.blit(flash,(0,0))
        if t>2.25:
            fade=min(1,(t-2.25)/1.15)
            shade=pygame.Surface(self.size,pygame.SRCALPHA);shade.fill((5,1,4,round(255*fade)))
            overlay.blit(shade,(0,0))
        surface.blit(overlay,(0,0))
