"""Hand-drawn deck materials and wall-mounted equipment, baked once per map."""
import math
import pygame
import config as C
from ui_fonts import ui_font

STEEL=(77,81,80)
BRASS=(137,122,88)
ROOM_CODES={'Quarters':'Q / 01','Oxygen':'O2 / 02','Communications':'COM / 03',
            'Power':'PWR / 04','Reactor':'RX / 05','Cargo Bay':'CG / 06',
            'Cooling':'CL / 07','Navigation':'NAV / 08','Hangar':'H / 09',
            'Medbay':'MED / 10','Storage':'ST / 11','Airlock':'AIR / 12','Observation':'OBS / 13'}


def screw(surface,point):
    x,y=point
    pygame.draw.circle(surface,(96,97,87),(x,y),2)
    pygame.draw.line(surface,(26,29,30),(x-1,y+1),(x+1,y-1))


def casing(surface,rect,color=(52,59,60)):
    pygame.draw.rect(surface,(12,16,19),rect.move(3,5),border_radius=3)
    pygame.draw.rect(surface,color,rect,border_radius=3)
    pygame.draw.line(surface,(104,109,102),(rect.left+2,rect.top),(rect.right-2,rect.top))
    pygame.draw.line(surface,(25,31,34),(rect.right-1,rect.top+2),(rect.right-1,rect.bottom),3)
    for point in ((rect.left+4,rect.top+4),(rect.right-5,rect.bottom-5)):screw(surface,point)


def room_floor(surface,room):
    x,y,w,h=room.rect;r=pygame.Rect(x*C.TILE,y*C.TILE,w*C.TILE,h*C.TILE)
    # Flush floor panels and paint remain traversable; fixtures occupy the wall edge.
    inner=r.inflate(-20,-20)
    tint=(39,47,49) if room.name in ('Cooling','Oxygen','Medbay') else (47,44,37) if room.name in ('Cargo Bay','Storage','Hangar') else (40,43,44)
    pygame.draw.rect(surface,tint,inner,1)
    for yy in range(r.top+24,r.bottom-12,48):
        pygame.draw.line(surface,(18,24,27),(r.left+12,yy),(r.right-12,yy))
        pygame.draw.line(surface,(54,58,57),(r.left+12,yy+1),(r.right-12,yy+1))
    # Worn department stencil, kept away from the interaction point.
    face=ui_font(25,True)
    stamp=face.render(ROOM_CODES[room.name],True,(73,76,69))
    surface.blit(stamp,(r.left+17,r.bottom-42))
    for n in range(4):
        pygame.draw.line(surface,(33,38,39),(r.left+18,r.bottom-33+n*5),(r.left+18+stamp.get_width(),r.bottom-33+n*5))
    if room.name in ('Cargo Bay','Hangar','Storage'):
        for xx in (r.left+28,r.right-28):
            pygame.draw.line(surface,(92,83,60),(xx,r.top+48),(xx,r.bottom-46),2)
            for yy in range(r.top+55,r.bottom-46,20):
                pygame.draw.rect(surface,(24,29,31),(xx-3,yy,7,9))


def wall_edges(surface,ship):
    """Draw visible inward wall faces; silhouettes still use the real collision grid."""
    for y,row in enumerate(ship.grid):
        for x,tile in enumerate(row):
            if tile:continue
            px,py=x*C.TILE,y*C.TILE
            for dx,dy in ((0,-1),(0,1),(-1,0),(1,0)):
                if not ship.is_wall_tile(x+dx,y+dy):continue
                if dy:
                    edge=py if dy<0 else py+C.TILE-1
                    for offset,color in enumerate(((111,113,103),(61,69,70),(42,50,53),(29,35,38),(18,24,27),(23,29,32))):
                        yy=edge-dy*offset
                        pygame.draw.line(surface,color,(px,yy),(px+C.TILE-1,yy))
                    pygame.draw.line(surface,(28,33,34),(px,edge),(px,edge-dy*5))
                    if x%2==0:screw(surface,(px+12,edge-dy*2))
                else:
                    edge=px if dx<0 else px+C.TILE-1
                    for offset,color in enumerate(((81,90,87),(50,61,62),(33,43,46),(20,29,32))):
                        xx=edge-dx*offset
                        pygame.draw.line(surface,color,(xx,py),(xx,py+C.TILE-1))
                    if y%2==0:screw(surface,(edge-dx*2,py+12))


def room_fixtures(surface,room):
    tx,ty,w,h=room.rect;x=tx*C.TILE+14;y=ty*C.TILE+36
    width=max(42,(w-4)*C.TILE-8)
    name=room.name
    if name in ('Oxygen','Cooling'):
        for i in range(min(3,width//36)):
            r=pygame.Rect(x+i*37,y,30,34);casing(surface,r)
            c=(r.centerx,r.centery)
            pygame.draw.circle(surface,(16,23,27),c,12)
            pygame.draw.circle(surface,(104,117,114),c,12,1)
            for a in range(6):
                angle=a*math.tau/6
                pygame.draw.line(surface,(65,82,84),c,(c[0]+math.cos(angle)*9,c[1]+math.sin(angle)*9),3)
            pygame.draw.circle(surface,(148,151,131),c,3)
        pygame.draw.lines(surface,(86,105,105),False,[(x,y+41),(x+width,y+41),(x+width,y+20)],3)
        for xx in range(x+12,x+width,25):pygame.draw.line(surface,(38,50,52),(xx,y+37),(xx,y+45),2)
    elif name=='Power':
        for i in range(3):
            r=pygame.Rect(x+i*42,y,36,39);casing(surface,r,(57,61,57))
            for n in range(3):
                pygame.draw.rect(surface,(20,27,27),(r.x+8,r.y+8+n*9,20,5))
                pygame.draw.rect(surface,BRASS,(r.x+9+(n+i)%2*10,r.y+9+n*9,8,3))
            pygame.draw.line(surface,(88,78,55),(r.centerx,r.bottom),(r.centerx,y+49),3)
    elif name in ('Communications','Navigation','Observation'):
        r=pygame.Rect(x,y,width,33);casing(surface,r)
        for i in range(max(1,width//35)):
            glass=pygame.Rect(x+6+i*35,y+5,28,16)
            pygame.draw.rect(surface,(13,27,29),glass)
            for n in range(3):pygame.draw.line(surface,(74,108,99),(glass.x+4,glass.y+4+n*4),(glass.x+11+(n*7+i*3)%13,glass.y+4+n*4))
            pygame.draw.rect(surface,(106,101,82),(glass.x+2,y+25,18,2))
    elif name in ('Reactor','Hangar'):
        r=pygame.Rect(x,y,min(width,116),38);casing(surface,r,(60,61,53))
        for i in range(3):
            c=(r.x+19+i*35,r.y+18)
            pygame.draw.circle(surface,(15,25,27),c,13)
            pygame.draw.circle(surface,(106,114,97),c,12,2)
            pygame.draw.circle(surface,(61,84,82),c,7,2)
        pygame.draw.line(surface,BRASS,(r.x+5,r.bottom+5),(r.right-5,r.bottom+5),2)
    elif name in ('Cargo Bay','Storage'):
        for i in range(min(3,width//37)):
            r=pygame.Rect(x+i*37,y,31,37);casing(surface,r,(64,59,46))
            for xx in (r.x+6,r.right-7):pygame.draw.line(surface,(127,113,83),(xx,r.top+2),(xx,r.bottom-3),3)
            pygame.draw.rect(surface,(168,154,120),(r.x+12,r.y+12,8,9))
    elif name in ('Quarters','Medbay'):
        for i in range(min(3,width//43)):
            r=pygame.Rect(x+i*43,y,34,45);casing(surface,r)
            pygame.draw.rect(surface,(78,89,88),r.inflate(-8,-8),border_radius=3)
            pygame.draw.rect(surface,(154,156,136),(r.x+6,r.y+5,22,9),border_radius=2)
            pygame.draw.line(surface,(43,56,60),(r.x+5,r.y+25),(r.right-5,r.y+25),3)
    elif name=='Airlock':
        r=pygame.Rect(x,y,width,34);casing(surface,r)
        for i in range(3):pygame.draw.line(surface,(109,108,88),(r.x+7,r.y+9+i*7),(r.right-7,r.y+9+i*7),2)


def corridor_details(surface,ship):
    for index,(x,y,w,h) in enumerate(ship.corridors[:10]):
        r=pygame.Rect(x*C.TILE,y*C.TILE,w*C.TILE,h*C.TILE)
        if w<h:continue
        # Flush inspection plates break up the long floor, not the walking route.
        for xx in range(r.x+60,r.right-35,144):
            plate=pygame.Rect(xx,r.centery-15,38,29)
            pygame.draw.rect(surface,(25,34,38),plate,border_radius=2)
            pygame.draw.rect(surface,(65,72,71),plate,1,border_radius=2)
            for yy in range(plate.y+5,plate.bottom-3,4):pygame.draw.line(surface,(13,24,28),(plate.x+5,yy),(plate.right-5,yy),2)
            for point in ((plate.x+3,plate.y+3),(plate.right-4,plate.bottom-4)):screw(surface,point)
        stamp=ui_font(15,True).render(f'{index+1:02d}  /  TRANSIT',True,(97,94,76))
        surface.blit(stamp,(r.x+28,r.bottom-30))


def ship_chart(ship,size=(800,339)):
    """A legible plan, independent of the world's dark material textures."""
    from render_surfaces import opaque_surface
    s=opaque_surface(size);s.fill((15,26,31))
    sx=size[0]/C.WORLD_W;sy=size[1]/C.WORLD_H
    for x in range(0,size[0],32):pygame.draw.line(s,(24,39,43),(x,0),(x,size[1]))
    for y in range(0,size[1],32):pygame.draw.line(s,(24,39,43),(0,y),(size[0],y))
    for y,row in enumerate(ship.grid):
        for x,tile in enumerate(row):
            if tile:continue
            r=pygame.Rect(round(x*C.TILE*sx),round(y*C.TILE*sy),round((x+1)*C.TILE*sx)-round(x*C.TILE*sx),round((y+1)*C.TILE*sy)-round(y*C.TILE*sy))
            pygame.draw.rect(s,(49,68,70),r)
            for dx,dy in ((0,-1),(0,1),(-1,0),(1,0)):
                if not ship.is_wall_tile(x+dx,y+dy):continue
                a,b=(r.topleft,r.topright) if dy<0 else (r.bottomleft,r.bottomright) if dy>0 else (r.topleft,r.bottomleft) if dx<0 else (r.topright,r.bottomright)
                pygame.draw.line(s,(124,143,133),a,b)
    for room in ship.rooms:
        x,y,w,h=room.rect
        r=pygame.Rect(round(x*C.TILE*sx)+3,round(y*C.TILE*sy)+3,round(w*C.TILE*sx)-6,round(h*C.TILE*sy)-6)
        pygame.draw.rect(s,(66,80,77),r,1)
    pygame.draw.rect(s,(75,95,94),s.get_rect(),1)
    for x in (8,size[0]-9):
        for y in (8,size[1]-9):
            pygame.draw.line(s,(136,151,137),(x-4,y),(x+4,y))
            pygame.draw.line(s,(136,151,137),(x,y-4),(x,y+4))
    return s
