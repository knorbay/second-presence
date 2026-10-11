"""Small, dry Foley layers built from the bundled CC0 contacts at mixer format."""
import math
from array import array
import pygame


def layer(parts, duration, rate, channels, peak=.70):
    """Mix (sound, gain, delay, playback-rate) without altering source assets."""
    frames=round(duration*rate)
    values=[0.0]*(frames*channels)
    for sound,gain,delay,speed in parts:
        source=array('h',sound.get_raw()); offset=round(delay*rate)
        length=len(source)//channels
        for frame in range(max(0,offset),frames):
            position=(frame-offset)*speed; first=int(position)
            if first>=length-1:break
            fraction=position-first
            for channel in range(channels):
                a=source[first*channels+channel];b=source[(first+1)*channels+channel]
                values[frame*channels+channel]+=(a+(b-a)*fraction)*gain
    # Remove DC and round off transients, keeping all variants at a known ceiling.
    means=[sum(values[c::channels])/max(1,frames) for c in range(channels)]
    low=[0.0]*channels; data=[]
    for i,value in enumerate(values):
        channel=i%channels;low[channel]+=.38*(value-means[channel]-low[channel])
        t=(i//channels)/rate
        fade=max(0,min(1,t/.004,(duration-t)/.035))
        data.append(low[channel]*fade)
    gain=min(2.0,32767*peak/max(1,max(map(abs,data))))
    return pygame.mixer.Sound(buffer=array('h',(round(v*gain) for v in data)))


def seamless(sound,rate,channels,overlap=.16):
    """Overlap the loop boundary, removing the repeated silence/click at its seam."""
    samples=array('h',sound.get_raw()); frames=len(samples)//channels
    blend=min(round(rate*overlap),frames//4)
    output=array('h',samples[blend*channels:])
    for frame in range(blend):
        u=frame/max(1,blend-1)
        # Linear weights avoid a level jump for correlated low-frequency machinery.
        for c in range(channels):
            i=(frames-2*blend+frame)*channels+c
            output[i]=round(output[i]*(1-u)+samples[frame*channels+c]*u)
    return pygame.mixer.Sound(buffer=output)


def build_details(sounds,root,rate,channels):
    def load(pattern):return [pygame.mixer.Sound(str(p)) for p in sorted(root.glob(pattern))]
    plates=load('impactPlate_light_*.ogg');metal=load('impactMetal_heavy_*.ogg')
    if not plates or not metal:return
    latch=sounds['latch'][0];breath=sounds['death_breath']
    sounds['switch']=[layer([(p,.6,0,1.25+i*.07)],.16,rate,channels,.38) for i,p in enumerate(plates)]
    sounds['valve']=[layer([(p,.45,0,.63),(latch,.18,.09,1.2)],.45,rate,channels,.48) for p in plates]
    sounds['brush']=[layer([(sounds['breath'][i],.65,0,1.7),(p,.15,0,1.4)],.35,rate,channels,.36) for i,p in enumerate(plates)]
    sounds['cargo']=[layer([(m,.65,0,.85),(plates[i%len(plates)],.32,.09,.72)],.58,rate,channels,.60) for i,m in enumerate(metal)]
    sounds['vent_knock']=[layer([(p,.7,0,.72),(plates[(i+1)%len(plates)],.45,.27,.61),
                                (p,.22,.63,.82)],1.0,rate,channels,.60) for i,p in enumerate(plates)]
    sounds['vent_drag']=[layer([(breath[i%len(breath)],.8,0,.55),(p,.22,.22,.45),
                               (p,.16,.79,.38)],1.9,rate,channels,.50) for i,p in enumerate(plates)]
    sounds['creature']=[layer([(b,.85,0,.52),(metal[i%len(metal)],.12,.12,.34)],2.0,rate,channels,.64) for i,b in enumerate(breath)]
    sounds['confirm']=[layer([(latch,.6,0,1.3),(p,.25,.11,1.45)],.3,rate,channels,.38) for p in plates]
    sounds['reject']=[layer([(p,.6,0,.78),(p,.35,.10,.70)],.33,rate,channels,.40) for p in plates]
