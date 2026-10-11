"""Muted deck machinery and animation; equipment positions also locate audio."""
import math
import pygame
import config as C

# Sound, volume, audible radius, affected by power loss.
ROOM_AUDIO = {
    'Oxygen': ('airflow', .30, 290, True),
    'Cooling': ('coolant', .34, 310, True),
    'Reactor': ('reactor', .34, 350, True),
    'Power': ('relay', .25, 280, True),
    'Communications': ('electronics', .21, 245, True),
    'Navigation': ('electronics', .16, 235, True),
    'Cargo Bay': ('hull_local', .22, 300, False),
    'Storage': ('hull_local', .15, 235, False),
    'Airlock': ('pressure', .31, 260, False),
    'Hangar': ('reactor', .19, 340, True),
}


def equipment_point(room):
    x, y, w, h = room.rect
    return pygame.Vector2((x+w)*C.TILE-43, y*C.TILE+65)


def draw_deck_tile(surface, rect, x, y):
    wear = ((x//3)*17+(y//2)*11) % 4
    pygame.draw.rect(surface, (31+wear, 39+wear, 43+wear), rect)
    # Larger staggered plates replace the repeated checkerboard of small tiles.
    if y%2==0:
        pygame.draw.line(surface,(16,25,29),rect.topleft,rect.topright)
        pygame.draw.line(surface,(48,57,59),(rect.x,rect.y+1),(rect.right,rect.y+1))
    if (x+y//2)%3==0:
        pygame.draw.line(surface,(18,27,31),rect.topleft,rect.bottomleft)
        if y%2==0:pygame.draw.circle(surface,(76,81,77),(rect.x+4,rect.y+5),1)
    for n in range(7):
        dx=(x*13+y*7+n*19)%23;dy=(x*5+y*11+n*13)%23
        surface.set_at((rect.x+dx,rect.y+dy),(36+wear,44+wear,47+wear))
    if (x*7+y)%11==0:
        pygame.draw.line(surface,(58,62,57),(rect.x+6,rect.y+14),(rect.x+17,rect.y+10))


def draw_room_equipment(surface, room):
    p = equipment_point(room)
    x, y = round(p.x), round(p.y)
    r = pygame.Rect(x-29, y-24, 58, 48)
    pygame.draw.rect(surface, (12,14,17), r.move(4,5), border_radius=5)
    pygame.draw.rect(surface, (52,54,55), r, border_radius=4)
    pygame.draw.rect(surface, (94,92,81), r, 1, border_radius=4)
    pygame.draw.line(surface, (112,108,95), (r.x+4,r.y+3), (r.right-5,r.y+3))
    for sx in (r.x+4,r.right-5):
        for sy in (r.y+6,r.bottom-6): pygame.draw.circle(surface, (22,24,27), (sx,sy), 2)
    name = room.name
    if name in ('Oxygen','Cooling','Airlock'):
        for i in (-1,1):
            tank=pygame.Rect(x+i*13-8,y-17,16,34)
            pygame.draw.rect(surface, (34,40,42), tank, border_radius=7)
            pygame.draw.rect(surface, (99,111,108) if name=='Cooling' else (111,111,100), tank, 2, border_radius=7)
            pygame.draw.line(surface,(64,75,77),(tank.x+5,tank.y+6),(tank.x+5,tank.bottom-6),2)
            pygame.draw.line(surface,(129,120,97),(tank.x-3,y),(tank.right+3,y),3)
        pygame.draw.lines(surface,(85,87,80),False,[(x-15,y+22),(x-15,y+34),(x+11,y+34)],3)
    elif name in ('Reactor','Hangar'):
        pygame.draw.circle(surface,(19,22,24),(x,y),20)
        pygame.draw.circle(surface,(104,98,80),(x,y),19,3)
        pygame.draw.circle(surface,(57,66,62),(x,y),12)
        for i in range(8):
            a=i*math.tau/8
            pygame.draw.line(surface,(117,108,87),(x+math.cos(a)*13,y+math.sin(a)*13),(x+math.cos(a)*18,y+math.sin(a)*18),2)
        pygame.draw.circle(surface,(132,124,91),(x,y),4)
    elif name in ('Communications','Navigation','Power'):
        pygame.draw.rect(surface,(13,21,23),(x-21,y-17,42,22),border_radius=2)
        for i in range(4):
            pygame.draw.line(surface,(92,116,104),(x-17,y-13+i*5),(x-6+(i*7)%20,y-13+i*5))
        for i in range(5):
            pygame.draw.rect(surface,(100,95,78),(x-20+i*9,y+11,5,5))
        pygame.draw.line(surface,(85,88,82),(x-20,y+23),(x-20,y+33),2)
    elif name in ('Cargo Bay','Storage'):
        for i in range(2):
            crate=pygame.Rect(x-23+i*25,y-17+i*8,24,30)
            pygame.draw.rect(surface,(67,61,48),crate)
            pygame.draw.rect(surface,(114,99,75),crate,1)
            pygame.draw.line(surface,(37,36,34),crate.topleft,crate.bottomright,2)
            pygame.draw.line(surface,(37,36,34),crate.topright,crate.bottomleft,2)
    else:
        pygame.draw.rect(surface,(33,39,44),(x-21,y-15,42,29),border_radius=3)
        for i in range(4):pygame.draw.line(surface,(78,83,83),(x-17,y-10+i*6),(x+17,y-10+i*6))
    # Wall conduits, kept clear of the central maintenance point and lockers.
    rx,ry,rw,rh=room.rect
    left=rx*C.TILE+10;top=ry*C.TILE+30
    pygame.draw.lines(surface,(17,20,23),False,[(left,top),(x,top),(x,y-24)],6)
    pygame.draw.lines(surface,(72,73,68),False,[(left,top),(x,top),(x,y-24)],2)


def animate_equipment(surface, room, time, powered=True,serviced=None):
    p=equipment_point(room)
    if room.name in ('Oxygen','Cooling'):
        angle=time*(2.3 if powered else .15)
        for n in range(3):
            v=pygame.Vector2(math.cos(angle+n*math.tau/3),math.sin(angle+n*math.tau/3))*7
            pygame.draw.line(surface,(118,124,114),p,p+v,2)
        pygame.draw.circle(surface,(41,45,43),p,2)
    elif room.name in ('Reactor','Power','Communications','Navigation'):
        level=int(8+12*(.5+.5*math.sin(time*1.6))) if powered else 3
        pygame.draw.circle(surface,(77+level,82+level,62+level),p,3)
    if serviced is not None:
        color=(104,127,103) if serviced else (144,116,76)
        pygame.draw.rect(surface,color,(p.x-23,p.y+17,10,3))
