"""Ship ambience, positional room machinery and restrained Foley."""
import math
import random
from array import array
import pygame
from pathlib import Path
from scenery import ROOM_AUDIO, equipment_point
from sound_design import build_details,seamless

FOOTSTEP_LEVELS={'walk':.62,'run':.80,'crouch':.16}

def regional_targets(listener, ship_map, blackout=False,serviced=None):
    """Physical source falloff; no AI information is involved in the room mix."""
    targets={}
    for name,(_,volume,radius,powered) in ROOM_AUDIO.items():
        point=equipment_point(ship_map.room_by_name(name))
        delta=point-pygame.Vector2(listener)
        distance=delta.length()
        gain=max(0,1-distance/radius)**1.4
        if gain and not ship_map.line_of_sight(*listener,*point):gain*=.18
        if blackout and powered:gain*=.23
        if serviced and serviced.get(name):gain*=.65
        targets[name]=(volume*gain,max(-.9,min(.9,delta.x/190)))
    return targets


class Audio:
    def __init__(self):
        self.enabled=True
        self.available=False
        self.error=''
        self.sounds={}
        self.ambient=None
        self.paused=False
        self.layers={}
        self.layer_volumes={}
        self.regional_channels={}
        self.regional_volumes={}
        self.footstep_channels={}
        self._last_step={'player':-1,'hunter':-1}
        self._step_side=1
        self._panel_cooldown=0.0
        self._activity_cooldown=0.0
        self._detail_cooldown=7.0
        try:
            if not pygame.mixer.get_init():pygame.mixer.init(22050,-16,2,512)
            rate,fmt,channels=pygame.mixer.get_init()
            if fmt!=-16:
                self.error=f'Unsupported mixer format: {fmt}'
                return
            pygame.mixer.set_num_channels(28)
            pygame.mixer.set_reserved(5+len(ROOM_AUDIO))
            self.footstep_channels={'player':pygame.mixer.Channel(3+len(ROOM_AUDIO)),
                                    'hunter':pygame.mixer.Channel(4+len(ROOM_AUDIO))}
            rng=random.Random(914)
            shapes={'step':.16,'alien':.3,'repair':.34,'decoy':.32,'alarm':.75,'creak':1.1,'breath':1.0,
                    'death_hit':.55,'tear':.65,'death_breath':1.25}
            for name,duration in shapes.items():
                variants=[]
                for variant in range(3):
                    samples=array('h')
                    low=0.0;mid=0.0
                    pitch=rng.uniform(.9,1.1)
                    for i in range(int(rate*duration)):
                        t=i/rate
                        white=rng.uniform(-1,1)
                        low += .025*(white-low)
                        mid += .18*(white-mid)
                        if name in ('tear','death_hit'):
                            envelope=min(1,t*200)*math.exp(-t*(8 if name=='death_hit' else 5))
                            wet=math.sin(math.tau*(45*pitch*t+14*t*t))*.3
                            crack=white*.55*max(0,math.sin(math.tau*17*t))**4
                            value=(mid*.8+low*1.5+wet+crack)*envelope
                        elif name=='death_breath':
                            envelope=math.sin(math.pi*t/duration)**2
                            value=(mid+low*1.4)*envelope*(.6+.4*math.sin(math.tau*13*t)**2)
                        elif name=='breath':
                            envelope=math.sin(math.pi*t/duration)**2
                            value=(mid*.9+low)*envelope
                        elif name in ('creak','alarm'):
                            envelope=math.sin(math.pi*t/duration)**2
                            rough=math.sin(2*math.pi*31*pitch*t)*mid
                            value=(low+rough*.24)*envelope*.7
                        elif name=='repair':
                            envelope=min(1,t*100)*math.exp(-t*8)
                            chatter=max(0,math.sin(2*math.pi*23*t))**8
                            value=(mid*.45+white*chatter*.18)*envelope
                        else:
                            decay=22 if name=='step' else 14
                            envelope=min(1,t*700)*math.exp(-t*decay)
                            modes=(math.sin(2*math.pi*73*pitch*t)*.12+
                                   math.sin(2*math.pi*191*pitch*t)*.07+
                                   math.sin(2*math.pi*431*pitch*t)*.04)
                            value=(low*2+mid*.4+modes*math.exp(-t*25))*envelope
                        sample=max(-32767,min(32767,int(value*22000)))
                        samples.extend([sample]*channels)
                    variants.append(pygame.mixer.Sound(buffer=samples))
                self.sounds[name]=variants
            root=Path(__file__).parent/'assets/audio'
            effects={'repair':['impactMetal_000','impactMetal_002'], 'latch':['doorClose_000'],
                     'open':['doorOpen_000'], 'terminal':['computerNoise_001']}
            for name,files in effects.items():
                loaded=[pygame.mixer.Sound(str(root/(file+'.ogg'))) for file in files if (root/(file+'.ogg')).exists()]
                if loaded:self.sounds[name]=loaded
            self._build_footsteps(root,rate,channels)
            build_details(self.sounds,root,rate,channels)
            # Quiet, broadband airflow; the seam fades rather than clicking.
            samples=array('h');low=0;mid=0;duration=4
            for i in range(int(rate*duration)):
                t=i/rate;white=rng.uniform(-1,1)
                low+=.013*(white-low);mid+=.08*(white-mid)
                envelope=min(1,t/.12,(duration-t)/.12)
                pressure=.82+.12*math.sin(math.tau*t/duration)
                value=(mid*.8+low*1.5)*pressure*envelope
                sample=int(max(-1,min(1,value))*26000)
                samples.extend([sample]*channels)
            self.layers['vent']=(pygame.mixer.Channel(0),seamless(pygame.mixer.Sound(buffer=samples),rate,channels))
            for name,index,file in [('engine',1,'spaceEngineLow_000.ogg'),('hull',2,'infestation.mp3')]:
                if (root/file).exists():self.layers[name]=(pygame.mixer.Channel(index),pygame.mixer.Sound(str(root/file)))
            self.layer_volumes={name:0.0 for name in self.layers}
            room_sounds={}
            for kind in {profile[0] for profile in ROOM_AUDIO.values()}:
                samples=array('h');low=0;mid=0;duration=4
                for i in range(int(rate*duration)):
                    t=i/rate;white=rng.uniform(-1,1)
                    low+=.015*(white-low);mid+=.16*(white-mid)
                    pulse=.65+.35*math.sin(math.tau*t/2)**2
                    if kind=='coolant':value=(low*1.8+mid*.45)*pulse+math.sin(math.tau*32*t)*.035*pulse
                    elif kind=='airflow':value=mid*.8+low*.9+white*.045
                    elif kind=='pressure':value=(mid*.7+white*.09)*(.16+.84*math.sin(math.pi*t/4)**4)
                    elif kind=='electronics':value=low*.5+mid*.18+math.sin(math.tau*112*t)*.035*(.6+.4*math.sin(math.tau*t/2))
                    elif kind=='relay':value=low*.6+math.sin(math.tau*50*t)*.09+math.sin(math.tau*100*t)*.035*pulse
                    elif kind=='reactor':value=low*1.2+math.sin(math.tau*38*t)*.15+math.sin(math.tau*76*t)*.07*pulse
                    else:value=low*1.1+math.sin(math.tau*61*t)*.025*math.sin(math.pi*t/4)**6
                    envelope=max(0,min(1,t/.035,(duration-t)/.035))
                    samples.extend([max(-32767,min(32767,int(value*26000*envelope)))]*channels)
                room_sounds[kind]=seamless(pygame.mixer.Sound(buffer=samples),rate,channels)
            self.sounds['steam']=[room_sounds['pressure']]
            for index,(name,profile) in enumerate(ROOM_AUDIO.items(),3):
                self.regional_channels[name]=(pygame.mixer.Channel(index),room_sounds[profile[0]])
                self.regional_volumes[name]=(0.0,0.0)
            self.available=True
        except (pygame.error,ValueError) as error:
            self.available=False
            self.error=str(error)
            self.layers={}
            self.regional_channels={}
            self.footstep_channels={}

    def _build_footsteps(self,root,rate,channels):
        """Boot-contact assets with a short metal-deck resonance; no long ringing bell."""
        boots=[pygame.mixer.Sound(str(p)) for p in sorted(root.glob('footstep_concrete_*.ogg'))]
        plates=[pygame.mixer.Sound(str(p)) for p in sorted(root.glob('impactPlate_light_*.ogg'))]
        heavy=[pygame.mixer.Sound(str(p)) for p in sorted(root.glob('impactMetal_heavy_*.ogg'))]
        if not boots or not plates or not heavy:return
        def mix(parts,duration):
            count=round(rate*duration)*channels
            values=[0.0]*count
            for sound,gain,delay in parts:
                samples=array('h',sound.get_raw());offset=round(rate*delay)*channels
                for i,value in enumerate(samples[:max(0,count-offset)]):values[i+offset]+=value*gain
            peak=max(map(abs,values),default=1) or 1
            scale=28000/peak
            data=array('h')
            for i,value in enumerate(values):
                t=(i//channels)/rate
                fade=max(0,min(1,t/.0015,(duration-t)/.025))
                data.append(round(value*scale*fade))
            return pygame.mixer.Sound(buffer=data)
        self.sounds['step']=[mix([(boot,1,0),(plates[i%len(plates)],.19,.016),
                                    (boot,.13,.038)],.30) for i,boot in enumerate(boots)]
        self.sounds['alien']=[mix([(impact,.8,0),(boots[i%len(boots)],.4,.035),
                                     (self.sounds['alien'][i%len(self.sounds['alien'])],.55,.055)],.36)
                              for i,impact in enumerate(heavy)]

    def footstep(self,actor,gait='walk',source=None,listener=None,ship_map=None,radius=250):
        if not self.available or not self.enabled or self.paused:return
        volume=FOOTSTEP_LEVELS.get(gait,FOOTSTEP_LEVELS['walk'])
        pan=self._step_side*.07
        name='step'
        if actor=='hunter':
            if source is None or listener is None or ship_map is None:return
            delta=pygame.Vector2(source)-pygame.Vector2(listener)
            volume=.68*max(0,1-delta.length()/radius)**.8
            if volume and not ship_map.line_of_sight(*listener,*source):volume*=.5
            pan=max(-.9,min(.9,delta.x/190));name='alien'
        else:self._step_side*=-1
        if volume<=.005:return
        choices=self.sounds[name];previous=self._last_step[actor]
        index=random.randrange(len(choices)-1) if len(choices)>1 and previous>=0 else random.randrange(len(choices))
        if len(choices)>1 and previous>=0 and index>=previous:index+=1
        self._last_step[actor]=index
        channel=self.footstep_channels[actor]
        channel.set_volume(volume*(1-max(0,pan)),volume*(1+min(0,pan)))
        channel.play(choices[index])

    def environment(self,dt,room,day,blackout,contact=False,listener=None,ship_map=None,serviced=None):
        if not self.available or not self.enabled or self.paused:return
        target={"vent":.065 if room in ("Oxygen","Cooling") else .035,
                "engine":.09 if room in ("Reactor","Power","Storage") else .028,
                "hull":.010+max(0,day-2)*.003}
        if blackout:target["vent"]*=.55;target["engine"]*=.4;target["hull"]*=1.25
        if contact:target["vent"]*=.7;target["engine"]*=.7
        for name,(channel,sound) in self.layers.items():
            current=self.layer_volumes[name]
            current+=(target[name]-current)*min(1,dt*1.8)
            self.layer_volumes[name]=current
            channel.set_volume(current,current)
            if not channel.get_busy():channel.play(sound,loops=-1,fade_ms=500)
        targets=regional_targets(listener,ship_map,blackout,serviced) if listener is not None and ship_map is not None else {}
        for name,(channel,sound) in self.regional_channels.items():
            volume,pan=targets.get(name,(0,0))
            left=volume*(1-max(0,pan));right=volume*(1+min(0,pan))
            old_left,old_right=self.regional_volumes[name]
            blend=min(1,dt*2.4)
            current=(old_left+(left-old_left)*blend,old_right+(right-old_right)*blend)
            self.regional_volumes[name]=current
            if max(current)>.002:
                channel.set_volume(*current)
                if not channel.get_busy():channel.play(sound,loops=-1,fade_ms=150)
            elif channel.get_busy():channel.stop()

        self._detail_cooldown-=dt
        if self._detail_cooldown<=0 and listener is not None and ship_map is not None:
            audible=[name for name,(volume,_) in targets.items() if volume>.06]
            if audible:
                name=random.choice(audible)
                sound='valve' if name in ('Cooling','Airlock','Oxygen') else 'switch' if name in ('Power','Communications','Navigation') else 'creak'
                self.play_at(sound,equipment_point(ship_map.room_by_name(name)),listener,ship_map,.12,330)
            self._detail_cooldown=random.uniform(9,18)

    def panel_activity(self,dt,work):
        self._panel_cooldown=max(0,self._panel_cooldown-dt)
        self._activity_cooldown=max(0,self._activity_cooldown-dt)
        if work.kind=='fuel' and work.pumping and self._activity_cooldown<=0:
            self.play('valve',.12)
            self._activity_cooldown=.58

    def panel_feedback(self,kind,outcome):
        if outcome not in ('progress','complete','wrong'):return
        if outcome=='wrong':self.play('reject',.18);return
        if outcome=='complete':self.play('confirm',.20);return
        if self._panel_cooldown>0:return
        sound={'filter':'brush','wires':'switch','cargo':'cargo','valves':'valve',
               'repair':'repair','fuel':'valve'}.get(kind,'switch')
        self.play(sound,.16 if kind!='cargo' else .22)
        self._panel_cooldown=.12

    def fade_environment(self,dt):
        if not self.available or self.paused:return
        factor=max(0,1-dt*3)
        for name,(channel,_) in self.layers.items():
            self.layer_volumes[name]*=factor
            channel.set_volume(self.layer_volumes[name])
        for name,(channel,_) in self.regional_channels.items():
            self.regional_volumes[name]=tuple(v*factor for v in self.regional_volumes[name])
            channel.set_volume(*self.regional_volumes[name])

    def reset(self):
        if self.available:pygame.mixer.stop()
        self.layer_volumes={name:0.0 for name in self.layers}
        self.regional_volumes={name:(0.0,0.0) for name in self.regional_channels}
        self._last_step={'player':-1,'hunter':-1};self._step_side=1
        self._panel_cooldown=0.0;self._activity_cooldown=0.0;self._detail_cooldown=7.0

    def play(self,name,volume=.2,pan=0):
        if not self.available or not self.enabled or self.paused:return
        choices=self.sounds.get(name)
        if not choices:return
        channel=pygame.mixer.find_channel()
        if channel:
            pan=max(-1,min(1,pan))
            channel.set_volume(volume*(1-max(0,pan)),volume*(1+min(0,pan)))
            channel.play(random.choice(choices))

    def play_at(self,name,source,listener,ship_map,volume=.2,radius=350):
        delta=pygame.Vector2(source)-pygame.Vector2(listener)
        gain=max(0,1-delta.length()/radius)**1.3
        if gain and not ship_map.line_of_sight(*listener,*source):gain*=.25
        if gain:self.play(name,volume*gain,max(-.9,min(.9,delta.x/190)))

    def set_master(self,value):
        self.master_volume=max(0,min(1,float(value)))
        sounds=[sound for choices in self.sounds.values() for sound in choices]
        sounds += [sound for _,sound in self.layers.values()]
        sounds += [sound for _,sound in self.regional_channels.values()]
        for sound in sounds:sound.set_volume(self.master_volume)

    def toggle(self):
        if not self.available:
            self.retry()
            return
        self.enabled=not self.enabled
        if self.available and not self.enabled:pygame.mixer.stop()

    def retry(self):
        paused=self.paused
        master=getattr(self,"master_volume",1.0)
        if pygame.mixer.get_init() and pygame.mixer.get_init()[1]!=-16:pygame.mixer.quit()
        self.__init__()
        self.set_master(master)
        self.pause(paused)

    def pause(self,paused):
        self.paused=paused
        if self.available:
            pygame.mixer.pause() if paused else pygame.mixer.unpause()
