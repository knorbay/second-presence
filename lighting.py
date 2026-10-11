"""Soft flashlight falloff, directional beam and wall occlusion, without extra dependencies."""
import math
import pygame
import fov
import config as C


def light_strength(dx,dy,facing,radius,power=1.0):
    distance=math.hypot(dx,dy)
    if distance>=radius:return 0
    if distance<.001:return min(255,int(214*power*C.FLASHLIGHT_BRIGHTNESS))
    radial=(1-(distance/radius)**2)**2/(1+(distance/130)**2)
    forward=max(0,(dx*math.cos(facing)+dy*math.sin(facing))/distance)**2
    beam=214*radial*forward
    local=184*max(0,1-(distance/76)**2)**2
    return min(255,int(max(beam,local)*power*C.FLASHLIGHT_BRIGHTNESS))


def combined_strength(dx,dy,facing,radius,power=1,ambient=0):
    distance=math.hypot(dx,dy)
    if distance>=radius:return 0
    # Local ceiling light fades toward the edge and still obeys wall occlusion.
    diffuse=255*ambient*max(0,1-(distance/radius)**4)
    return min(255,int(max(light_strength(dx,dy,facing,radius,power),diffuse)))


class Lighting:
    def __init__(self):
        self.cache={}

    def strength_at(self,ship_map,origin,facing,point,radius,power=1,ambient=0):
        if not ship_map.line_of_sight(*origin,*point):return 0
        return combined_strength(point[0]-origin[0],point[1]-origin[1],facing,radius,power,ambient)

    def mask(self,radius,facing,power,ambient=0):
        radius=int(radius)
        direction=round(facing/(math.pi/16))%32
        level=round(power*20)/20
        ambient=round(ambient*20)/20
        key=(radius,direction,level,ambient)
        if key not in self.cache:
            size=129
            small=pygame.Surface((size,size),pygame.SRCALPHA)
            for y in range(size):
                dy=(y/(size-1)*2-1)*radius
                for x in range(size):
                    dx=(x/(size-1)*2-1)*radius
                    strength=combined_strength(dx,dy,direction*math.pi/16,radius,level,ambient)
                    small.set_at((x,y),(0,0,0,255-strength))
            self.cache[key]=pygame.transform.smoothscale(small,(radius*2+1,radius*2+1))
            if len(self.cache)>48:self.cache.pop(next(iter(self.cache)))
        return self.cache[key]

    def apply(self,screen,explored,ship_map,origin,facing,radius,power,ambient=0):
        # Remember only areas inside the beam or close peripheral vision.
        cone=fov.cone_polygon(ship_map,origin,facing,140,radius)
        near=fov.player_visibility_polygon(ship_map,origin,radius=min(72,radius),rays=100)
        pygame.draw.polygon(explored,(0,0,0,242),cone)
        pygame.draw.polygon(explored,(0,0,0,242),near)
        fog=explored.copy()
        lamp=self.mask(radius,facing,power,ambient).copy()
        offset=pygame.Vector2(origin)-pygame.Vector2(radius,radius)
        poly=fov.player_visibility_polygon(ship_map,origin,radius=radius,rays=200)
        if ambient>.08:pygame.draw.polygon(explored,(0,0,0,242),poly)
        # Alpha 255 outside line of sight: the gradient cannot pass through a wall.
        occlusion=pygame.Surface(lamp.get_size(),pygame.SRCALPHA)
        occlusion.fill((0,0,0,255))
        pygame.draw.polygon(occlusion,(0,0,0,0),[(x-offset.x,y-offset.y) for x,y in poly])
        lamp.blit(occlusion,(0,0),special_flags=pygame.BLEND_RGBA_MAX)
        if ambient>.08:fog=explored.copy()
        fog.blit(lamp,(int(offset.x),int(offset.y)),special_flags=pygame.BLEND_RGBA_MIN)
        screen.blit(fog,(0,0))
        return fog
