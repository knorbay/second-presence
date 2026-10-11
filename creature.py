"""The deck intruder: heavy shoulders, a split face and an uneven grasping gait."""
import math
import pygame


def draw_creature(surface,position,facing,time,moving=True,scale=1,alert=False):
    origin=pygame.Vector2(position)
    forward=pygame.Vector2(math.cos(facing),math.sin(facing));side=pygame.Vector2(-forward.y,forward.x)
    phase=time*(8.6 if moving else 1.25)
    breath=math.sin(time*2.1)*.65
    skin=(101,116,111);pale=(173,174,149);shade=(44,56,58);bruise=(66,53,54);dark=(12,16,19)
    def pt(a,b):return origin+(forward*a+side*b)*scale
    def line(color,a,b,width=1):pygame.draw.line(surface,color,pt(*a),pt(*b),max(1,round(width*scale)))
    def poly(color,coords):
        if len(coords)>=7:
            # Curved flesh contours avoid hard, armour-like plates at world scale.
            points=[]
            for i,p1 in enumerate(coords):
                p0=coords[i-1];p2=coords[(i+1)%len(coords)];p3=coords[(i+2)%len(coords)]
                for j in range(4):
                    t=j/4
                    points.append(tuple(.5*((2*p1[k])+(-p0[k]+p2[k])*t+(2*p0[k]-5*p1[k]+4*p2[k]-p3[k])*t*t+(-p0[k]+3*p1[k]-3*p2[k]+p3[k])*t*t*t) for k in (0,1)))
            coords=points
        pygame.draw.polygon(surface,color,[pt(*point) for point in coords])
    def joint(color,p,r):pygame.draw.circle(surface,color,pt(*p),max(1,round(r*scale)))
    # A compact shadow anchors the body; each leg plants on a different beat.
    poly((10,15,18),[(-4+math.cos(i*math.tau/24)*29,math.sin(i*math.tau/24)*17) for i in range(24)])
    for sign in (-1,1):
        swing=math.sin(phase+sign*1.1)*(6 if moving else .35)
        hip=(-12,sign*8);knee=(-25+swing,sign*(14+breath));ankle=(-35-swing*.4,sign*11)
        line(shade,hip,knee,9);line(skin,hip,knee,5)
        line(dark,knee,ankle,7);line(shade,knee,ankle,5);line(pale,knee,ankle,2)
        joint(shade,knee,3)
        for n in range(3):line(skin,ankle,(-40-swing*.4+n,sign*(10+n*3)),2)
        # One dragging arm is longer. Hands close before the shoulders catch up.
        reach=math.sin(phase+sign*.8)*(7 if moving else 1.0)
        shoulder=(4,sign*(13+breath));elbow=(-13+reach*.6,sign*(24+breath))
        wrist=((-24 if sign<0 else 5)+reach,sign*(28 if sign<0 else 32))
        line(dark,shoulder,elbow,12);line(shade,shoulder,elbow,10);line(skin,shoulder,elbow,6)
        line(dark,elbow,wrist,9);line(shade,elbow,wrist,7);line(skin,elbow,wrist,4)
        joint(shade,elbow,3);joint(skin,shoulder,4);joint(shade,wrist,4)
        for n in range(4):
            start=(wrist[0]+n,wrist[1]+sign*(n-1))
            bend=(wrist[0]+9+n*1.7,wrist[1]+sign*(n*2))
            end=(wrist[0]+17+n,wrist[1]-sign*(7-n))
            line(shade,start,bend,3);line(pale,start,bend,1)
            line(skin,bend,end,2);line(dark,end,(end[0]+3,end[1]-sign*3),1)
    # Skin stretches over a hunched, asymmetric spine rather than an exposed skeleton.
    poly(shade,[(-25,-4),(-15,-13),(2,-18),(14,-11),(13,8),(3,18),(-13,11),(-24,5)])
    poly(skin,[(-20,-4),(-12,-10),(1,-14),(11,-9),(9,5),(1,13),(-11,7)])
    joint(skin,(-5,-1),10);joint(skin,(2,0),12)
    poly((82,100,99),[(-16,-7),(-4,-12),(6,-11),(9,-3),(-5,2),(-19,1)])
    poly((67,77,72),[(-20,3),(-5,1),(8,5),(1,12),(-10,8)])
    for n in range(5):
        a=-15+n*4;joint((121,136,119),(a,-1+math.sin(n)*1.2),1)
        line(shade,(a,-3),(a+4,-9+n*.2),1)
        line(bruise,(a,3),(a+5,9-n*.3),1)
    # The neck lags behind the torso. A sideways twitch makes the face hard to read.
    twitch=(math.sin(time*1.3)**15)*2.4
    head=breath+(2 if alert else 0);tilt=twitch-1.2
    line(shade,(8,0),(20+head,tilt),11);line(skin,(9,-2),(20+head,tilt-2),6)
    poly(shade,[(14,-6+tilt),(21+head,-10+tilt),(32+head,-7+tilt),(36+head,1+tilt),(30+head,10+tilt),(18,8+tilt)])
    poly(skin,[(16,-5+tilt),(23+head,-8+tilt),(31+head,-5+tilt),(33+head,0+tilt),(28+head,7+tilt),(20,6+tilt)])
    poly(pale,[(20,-6+tilt),(25+head,-7+tilt),(28+head,-3+tilt),(24,-1+tilt),(18,0+tilt)])
    # An offset eye slit and a deep facial tear. Nothing emits its own light.
    line(dark,(25+head,-6+tilt),(28+head,-3+tilt),3)
    line(dark,(25+head,4+tilt),(29+head,5+tilt),2)
    gape=3+(2 if alert else 0)+abs(math.sin(time*2.3))
    poly(dark,[(24+head,-1+tilt),(34+head,-gape+tilt),(38+head,tilt),(33+head,gape+tilt),(24+head,2+tilt)])
    for n in range(4):
        a=28+head+n*2
        line(pale,(a,-2+tilt),(a-.5,tilt),1)
        line(skin,(a,3+tilt),(a-1,1+tilt),1)
    line(bruise,(29+head,7+tilt),(35+head,5+tilt),2)
