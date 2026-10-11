"""Restrained original-style presentation with a scrolling, larger ship."""
import math
import pygame
import config as C
from render_surfaces import opaque_surface
from survival import conditions_for
from lighting import Lighting
from maintenance import KINDS, work_for_day, job_title, repair_steps
from task_panels import TaskPanels, NEW_KINDS, panel_rect
from localization import tr, language
from creature import draw_creature
from scenery import draw_deck_tile, draw_room_equipment, animate_equipment
from crew_logs import LOGS,log_point
from ui_fonts import ui_font,normalize_text,ui_upper
from deck_art import room_floor,room_fixtures,wall_edges,corridor_details,ship_chart

TEXT=(226,224,216)
DIM=(169,168,163)
FAINT=(127,126,123)
WARNING=(206,178,139)
DANGER=(149,76,70)
NAMES={'Oxygen':'Oksijen','Reactor':'Reaktör','Power':'Güç','Communications':'İletişim',
       'Cooling':'Soğutma','Quarters':'Mürettebat','Navigation':'Navigasyon','Hangar':'Hangar',
       'Cargo Bay':'Kargo','Medbay':'Revir','Airlock':'Hava kilidi','Storage':'Depo','Observation':'Gözlem'}


class Presentation:
    def __init__(self, game):
        self.g=game
        self.heading=ui_font(30,True)
        self.font=ui_font(21)
        self.small=ui_font(18)
        self.tiny=ui_font(16)
        self.explored=pygame.Surface((C.WORLD_W,C.WORLD_H),pygame.SRCALPHA)
        self.explored.fill((0,0,0,255))
        self.fog=self.explored.copy()
        self.lighting=Lighting()
        self.task_panels=TaskPanels(self)
        self.ambient_tint=opaque_surface((C.WORLD_W,C.WORLD_H))
        self._ambient_color=None
        self.ship=self._build_ship()
        self.refresh()

    def text(self,text,x,y,color=TEXT,font=None,center=False):
        s=(font or self.font).render(normalize_text(tr(text)),True,color)
        self.g.screen.blit(s,(x-s.get_width()//2 if center else x,y))

    def _build_ship(self,ship_map=None):
        ship=ship_map or self.g.ship_map
        s=opaque_surface((C.WORLD_W,C.WORLD_H))
        s.fill((12,18,22))
        for y,row in enumerate(ship.grid):
            for x,tile in enumerate(row):
                if tile==0:
                    r=pygame.Rect(x*C.TILE,y*C.TILE,C.TILE,C.TILE)
                    draw_deck_tile(s,r,x,y)
                    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        if ship.is_wall_tile(x+dx,y+dy):
                            a=(r.right-1,r.top) if dx==1 else (r.left,r.top) if dx==-1 else (r.left,r.bottom-1) if dy==1 else (r.left,r.top)
                            b=(a[0],r.bottom) if dx else (r.right,a[1])
                            pygame.draw.line(s,(49,48,51),a,b)
        for room in ship.rooms:
            x,y,w,h=room.rect
            rect=pygame.Rect(x*C.TILE,y*C.TILE,w*C.TILE,h*C.TILE)
            room_floor(s,room)
            room_fixtures(s,room)
            label=self.tiny.render(ui_upper(tr(NAMES[room.name]),language()=="tr"),True,(146,149,133))
            s.blit(label,(rect.x+12,rect.y+12))
            draw_room_equipment(s,room)
            if h>=5:
                for n in range(2):
                    rr=pygame.Rect(rect.right-29,rect.y+35+n*32,18,25)
                    pygame.draw.rect(s,(34,33,36),rr)
                    pygame.draw.rect(s,(43,41,44),rr,1)
                    pygame.draw.line(s,(54,50,46),(rr.x+4,rr.y+8),(rr.right-4,rr.y+8))
        # Grilles follow the real corridor walls, including turns and recessed bays.
        for yy,row in enumerate(ship.grid):
            for xx,tile in enumerate(row):
                if tile or ship.room_at_world((xx+.5)*C.TILE,(yy+.5)*C.TILE) or (xx*3+yy)%6:
                    continue
                if ship.is_wall_tile(xx,yy-1) or ship.is_wall_tile(xx,yy+1):
                    r=pygame.Rect(xx*C.TILE+4,yy*C.TILE+8,16,7)
                elif ship.is_wall_tile(xx-1,yy) or ship.is_wall_tile(xx+1,yy):
                    r=pygame.Rect(xx*C.TILE+8,yy*C.TILE+4,7,16)
                else:continue
                pygame.draw.rect(s,(65,62,53),r)
                if r.w>r.h:
                    for n in range(3,16,4):pygame.draw.line(s,(24,25,29),(r.x+n,r.y),(r.x+n,r.bottom))
                else:
                    for n in range(3,16,4):pygame.draw.line(s,(24,25,29),(r.x,r.y+n),(r.right,r.y+n))
        # Different-width galleries retain a quiet centre marking without painting walls.
        for x,y,w,h in ship.corridors[:10]:
            points=[(tx,y+h//2) for tx in range(x+2,x+w-1,5)] if w>=h else [(x+w//2,ty) for ty in range(y+2,y+h-1,5)]
            for tx,ty in points:
                if ship.is_wall_tile(tx,ty):continue
                r=pygame.Rect(tx*C.TILE+8,ty*C.TILE+10,9,3) if w>=h else pygame.Rect(tx*C.TILE+10,ty*C.TILE+8,3,9)
                pygame.draw.rect(s,(62,57,46),r)
        for name,point in self.g.lockers.items():
            r=pygame.Rect(point.x-9,point.y-12,18,24)
            pygame.draw.rect(s,(38,38,40),r)
            pygame.draw.rect(s,(70,68,63),r,1)
            pygame.draw.line(s,(89,86,79),(r.right-4,r.y+9),(r.right-4,r.y+15))
        for x,y in ship.sealed_tiles:
            r=pygame.Rect(x*C.TILE,y*C.TILE,C.TILE,C.TILE)
            pygame.draw.rect(s,(49,42,38),r)
            for n in range(0,C.TILE,8):
                pygame.draw.line(s,(85,69,49),(r.x+n,r.top),(r.x+n-8,r.bottom),2)
        corridor_details(s,ship)
        wall_edges(s,ship)
        return s

    def refresh(self):
        self.ship=self._build_ship()
        self.chart=ship_chart(self.g.ship_map)
        self.geometry_revision=self.g.ship_map.geometry_revision

    def world(self):
        if self.geometry_revision!=self.g.ship_map.geometry_revision:self.refresh()
        self.g.screen.blit(self.ship,(0,0))
        if self.g.conditions.ambient_strength>.04:
            warm=tuple(int(c*self.g.conditions.ambient_strength) for c in (58,53,43))
            if warm!=self._ambient_color:
                self.ambient_tint.fill(warm);self._ambient_color=warm
            self.g.screen.blit(self.ambient_tint,(0,0),special_flags=pygame.BLEND_RGB_ADD)
        serviced=self.g.serviced_systems()
        ambient=self.g.conditions.ambient_strength
        for room in self.g.ship_map.rooms:
            x,y,w,h=room.rect
            for xx in range(x+2,x+w-1,4):
                lamp=pygame.Rect(xx*C.TILE,y*C.TILE+5,23,4)
                color=tuple(int(a+(b-a)*ambient) for a,b in zip((41,40,39),(235,225,198)))
                pygame.draw.rect(self.g.screen,(19,20,22),lamp.inflate(4,4))
                pygame.draw.rect(self.g.screen,color,lamp)

        for room in self.g.ship_map.rooms:
            animate_equipment(self.g.screen,room,self.g.sim_time,not self.g.conditions.blackout,serviced.get(room.name))
        for entry in LOGS:
            if self.g.day<entry.day:continue
            point=log_point(self.g.ship_map,entry)
            r=pygame.Rect(point.x-10,point.y-8,20,16)
            pygame.draw.rect(self.g.screen,(28,34,35),r,border_radius=2)
            pygame.draw.rect(self.g.screen,(109,125,113) if entry.key in self.g.logbook.found else (157,139,102),r,1,border_radius=2)
            for n in range(3):pygame.draw.line(self.g.screen,(121,128,123),(r.x+5,r.y+4+n*3),(r.right-5,r.y+4+n*3))
        g=self.g
        def visible(point):
            if g.player.pos.distance_to(point)>=g.conditions.view_radius:return False
            return self.lighting.strength_at(g.ship_map,tuple(g.player.pos),math.atan2(g.player.facing.y,g.player.facing.x),point,g.conditions.view_radius,g.lamp_power,g.conditions.ambient_strength)>=18
        g.atmosphere.draw(g.screen,visible)
        c=conditions_for(self.g.day)
        # Quiet signs of failing rooms, visible only through the fog.
        for name in c.leak_rooms:
            if serviced.get('Cooling') or serviced.get(name):continue
            r=self.g.ship_map.room_by_name(name)
            point=r.world_center
            for i in range(8):
                t=(self.g.day_time*.8+i*.13)%1
                p=point+pygame.Vector2(20+t*70, -10+math.sin(i*3.2)*19)
                pygame.draw.circle(self.g.screen,(46,45,45),tuple(map(int,p)),1)
        self.g.ship_map.doors.draw(self.g.screen,self.g.sim_time)

    def fog_of_war(self):
        g=self.g
        facing=math.atan2(g.player.facing.y,g.player.facing.x)
        self.fog=self.lighting.apply(g.screen,self.explored,g.ship_map,tuple(g.player.pos),
                                    facing,g.conditions.view_radius,g.lamp_power,g.conditions.ambient_strength)
        g.ship_map.doors.draw_front_faces(g.screen,g.sim_time,tuple(g.player.pos),facing,
                                        self.lighting,g.conditions.view_radius,g.lamp_power,g.conditions.ambient_strength)

    def meter(self,x,y,w,value,color=TEXT):
        pygame.draw.rect(self.g.screen,(33,32,35),(x,y,w,4))
        pygame.draw.rect(self.g.screen,color,(x,y,int(w*max(0,min(1,value))),4))

    def card(self,rect):
        pygame.draw.rect(self.g.screen,(19,20,23),rect,border_radius=4)
        pygame.draw.rect(self.g.screen,(85,84,81),rect,1,border_radius=4)

    def caption(self,label,cx,y,color=TEXT):
        label=tr(label)
        width=self.small.size(label)[0]+28
        self.card(pygame.Rect(cx-width//2,y,width,32))
        self.text(label,cx,y+6,color,self.small,True)

    def wrapped(self,label,x,y,width,color=TEXT,font=None,line_height=21):
        font=font or self.small
        label=normalize_text(tr(label))
        line_height=max(line_height,font.get_linesize())
        line=''
        for word in label.split():
            candidate=(line+' '+word).strip()
            if line and font.size(candidate)[0]>width:
                self.text(line,x,y,color,font);y+=line_height;line=word
            else:line=candidate
        self.text(line,x,y,color,font)
        return y+line_height

    def hud(self):
        g=self.g;y=C.VIEW_H
        screen=g.screen
        pygame.draw.rect(screen,(17,23,26),(0,y,C.SCREEN_W,C.UI_HEIGHT))
        pygame.draw.line(screen,(99,102,92),(0,y),(C.SCREEN_W,y))
        pygame.draw.line(screen,(31,39,41),(0,y+3),(C.SCREEN_W,y+3))
        for xx in (236,966):pygame.draw.line(screen,(60,69,68),(xx,y+18),(xx,y+72))
        left=max(0,int(g.day_length-g.day_time))
        r=pygame.Rect(18,18,286,79)
        pygame.draw.rect(screen,(11,17,20),r,border_radius=3)
        pygame.draw.line(screen,WARNING,(r.x,r.y),(r.x,r.bottom),3)
        self.text('VARDİYA',32,28,DIM,self.tiny)
        self.text(f'{g.day:02d}',31,49,TEXT,self.heading)
        pygame.draw.line(screen,(68,78,78),(89,31),(89,82))
        room=g.player.current_room
        self.text(NAMES[room.name] if room else 'Koridor',104,29,TEXT,self.font)
        self.text(f'{left//60:02d}:{left%60:02d}',104,61,WARNING,self.small)
        self.text('/ 08',245,62,FAINT,self.tiny)
        if g.day>=3:self.caption('Genel aydınlatma kapalı.',C.SCREEN_W//2,18,WARNING)
        elif g.conditions.blackout:self.caption('Elektrik kesildi.',C.SCREEN_W//2,18,WARNING)
        if g.notification_timer>0:self.caption(g.notification,C.SCREEN_W//2,58)
        elif g.alarms:self.caption('Hat arızası: '+NAMES[g.alarms[0].room.name],C.SCREEN_W//2,58,WARNING)
        self.text('DAYANIKLILIK',22,y+13,DIM,self.tiny)
        stamina=max(0,min(1,g.player.stamina/C.STAMINA_MAX))
        for i in range(20):
            pygame.draw.rect(screen,(174,183,169) if i<round(stamina*20) else (45,56,57),(22+i*9,y+39,6,5))
        self.text(f'Gemi %{g.integrity}',22,y+57,TEXT,self.small)
        if g.day<8:
            remaining=[t for t in g.tasks.tasks.values() if not t.done]
            remaining.sort(key=lambda t:(bool(g.tasks.blocked_by(t.name)),g.player.pos.distance_to(t.room.world_center)))
            done=len(g.tasks.tasks)-len(remaining)
            self.text('BAKIM PLANI',260,y+13,DIM,self.tiny)
            self.text(f'{done:02d} / {len(g.tasks.tasks):02d}',382,y+11,TEXT,self.small)
            for i,t in enumerate(g.tasks.tasks.values()):
                color=(157,176,147) if t.done else WARNING if not g.tasks.blocked_by(t.name) else (62,72,73)
                pygame.draw.rect(screen,color,(475+i*16,y+19,10,5))
            available=[t for t in remaining if not g.tasks.blocked_by(t.name)]
            label=NAMES[available[0].name]+' — '+available[0].title if available else 'Vardiya tamamlandı'
            self.text(label,260,y+42,WARNING,self.font)
            self.text('TAB: bütün görevler ve gemi planı',702,y+16,DIM,self.tiny)
        else:
            name=g.tasks.day8_current_target()
            self.text(f'Kaçış dizisi: {g.tasks.day8_step} / {len(C.DAY8_SEQUENCE)}',260,y+13,TEXT,self.small)
            self.text(NAMES[name]+' — '+job_title(name,work_for_day(8,name)) if name else 'Kapsül hazır',260,y+42,WARNING,self.font)
        self.text(f'Ses kapsülü: {g.decoy_charges}',991,y+13,TEXT,self.small)
        status=self.audio_status()
        self.text(status or 'TAB plan · ESC duraklat',991,y+40,WARNING if status else DIM,self.tiny)
        self.text('CTRL sessiz · F saklan · J kayıt',991,y+63,DIM,self.tiny)
        near=g.player._nearby_interactable(g._interactables())
        prompt='F: Dolaptan çık' if g.player.hidden else ('Önce: '+', '.join(NAMES[n] for n in near['blocked']) if near.get('blocked') else 'E: '+job_title(near['name'],near['operation'])) if near else 'F: Dolaba saklan' if g.nearby_locker() else ''
        if not g.player.hidden and near is None and g.logbook.nearby(g.ship_map,g.player.pos,g.day):prompt='E: Mürettebat kaydını oku'
        door=g.ship_map.doors.nearby(g.player.pos)
        if door and not g.player.hidden:
            door_prompt='Kapı parçalanmış' if door.broken else 'B: Kapıyı aç' if door.closed else 'B: Kapıyı kapat'
            prompt=(prompt+' · ' if prompt else '')+door_prompt
        if prompt and not g.panel_work:
            self.caption(prompt,C.SCREEN_W//2,y-48)
        if g.player.interacting and not g.panel_work:
            self.meter(C.SCREEN_W//2-120,y-12,240,g.player.interact_progress,WARNING)
        if g.heard_timer>0:
            direction=g.heard_direction
            p=g.world_to_view(g.player.pos)+direction*40
            pygame.draw.line(g.screen,(178,174,162),p-direction*4,p+direction*4,2)
            self.caption(g.heard_message,C.SCREEN_W//2,94,DIM)
        if g.panel_work:
            self.work_panel()

    def work_panel(self):
        work=self.g.panel_work
        x,y,w,h=panel_rect()
        screen=self.g.screen
        self.task_panels.chassis(work)
        self.text(NAMES[work.name]+' / '+job_title(work.name,work.kind),x+74,y+15,TEXT,self.font)
        step=self.g.tasks.tasks.get(work.name) if self.g.day<8 else None
        label=f'Aşama {step.step+1}/{len(step.operations)} · ' if step else ''
        self.text(label+'ESC kapat · Hareket etmek işlemi bırakır',x+74,y+46,DIM,self.tiny)
        pygame.draw.line(self.g.screen,(85,84,81),(x+20,y+76),(x+w-20,y+76))
        if work.kind in NEW_KINDS:
            self.task_panels.draw(work)
        elif work.kind=='inspect':
            self.text('Normal aralık: 40–60. Hangi kanal arızalı?',x+20,y+91,TEXT,self.small)
            labels={'Oxygen':['Basınç','Akış','Saflık'],'Reactor':['Isı','Basınç','Akım'],
                    'Power':['Voltaj','Frekans','Akım'],'Communications':['Sinyal','Frekans','Gürültü'],
                    'Cooling':['Akış','Basınç','Isı']}.get(work.name,['Kanal A','Kanal B','Kanal C'])
            for i,value in enumerate(work.readings):
                self.task_panels.diagnostic_gauge(pygame.Rect(x+26+i*178,y+127,166,144),labels[i],value)
        elif work.kind=='repair':
            instructions=repair_steps(work.name)
            self.text(f'Aşama {work.stage+1} / 3',x+20,y+94,DIM,self.small)
            self.text(instructions[work.stage],x+20,y+128,TEXT,self.small)
            if work.stage==1:self.adjustment_bar(work,x+24,y+185,w-48)
            else:self.meter(x+24,y+193,w-48,work.progress,DIM)
            points=[(x+90+i*195,y+245) for i in range(3)]
            pygame.draw.lines(screen,(79,81,76),False,points,3)
            for i,point in enumerate(points):
                pygame.draw.circle(screen,(33,37,39),point,17)
                pygame.draw.circle(screen,WARNING if i<=work.stage else DIM,point,17,2)
                self.text(str(i+1),point[0],point[1]-8,WARNING if i==work.stage else DIM,self.tiny,True)
        elif work.kind=='calibrate':
            self.text('Sol / Sağ ok: Ayarla. SPACE: Doğrula.',x+20,y+94,TEXT,self.small)
            self.text(f'Ölçüm: {int(work.cursor*100)}     Hedef: {int(work.target*100)}',x+20,y+132,DIM,self.small)
            self.adjustment_bar(work,x+24,y+185,w-48)
        elif work.kind=='rewire':
            self.text('1 / 2 / 3: Anahtarı değiştir. SPACE: Doğrula.',x+20,y+94,TEXT,self.small)
            self.text('ANAHTAR',x+26,y+129,DIM,self.tiny)
            self.text('ŞİMDİ',x+173,y+129,DIM,self.tiny)
            self.text('HEDEF',x+317,y+129,DIM,self.tiny)
            for i,(value,target) in enumerate(zip(work.bits,work.goal)):
                row=y+155+i*29
                self.text(f'[{i+1}]',x+26,row,TEXT,self.small)
                self.text('AÇIK' if value else 'KAPALI',x+173,row,TEXT,self.small)
                self.text('AÇIK' if target else 'KAPALI',x+317,row,TEXT,self.small)
                knob=pygame.Rect(x+452,row+2,58,21)
                pygame.draw.rect(screen,(55,57,56),knob,border_radius=10)
                pygame.draw.circle(screen,WARNING if value else DIM,(knob.right-11 if value else knob.left+11,knob.centery),8)
        if work.kind not in NEW_KINDS:self.task_panels.legacy_buttons(work)
        if work.message_timer<=0:
            self.text('Panel açıkken oyun devam eder. P ile duraklatabilirsin.',x+22,y+355,FAINT,self.tiny)
        if work.message_timer>0:
            pygame.draw.rect(self.g.screen,(38,33,28),(x+12,y+343,w-24,53),border_radius=3)
            self.wrapped(work.message,x+20,y+350,w-40,WARNING,self.tiny,19)

    def adjustment_bar(self,work,x,y,w):
        pygame.draw.rect(self.g.screen,(54,54,57),(x,y,w,22))
        left=max(0,work.target-work.tolerance);right=min(1,work.target+work.tolerance)
        pygame.draw.rect(self.g.screen,(111,105,84),(x+int(left*w),y,int((right-left)*w),22))
        for tx in range(int(x+left*w),int(x+right*w)-5,8):
            pygame.draw.line(self.g.screen,(164,153,120),(tx,y+21),(tx+6,y),1)
        pygame.draw.rect(self.g.screen,(137,134,125),(x,y,w,22),1)
        pygame.draw.line(self.g.screen,TEXT,(x+int(work.cursor*w),y-4),(x+int(work.cursor*w),y+26),3)

    def background(self):
        self.g.screen.fill((7,7,10))

    def transition(self):
        g=self.g;self.background();cx=C.SCREEN_W//2
        self.language_buttons()
        c=conditions_for(g.day)
        self.text(f'GÜN {g.day}',cx,180,TEXT,self.heading,True)
        incident=g.tasks.incident if g.day<8 else None
        title=incident[1 if language()=='tr' else 2] if incident else c.title
        description=incident[3 if language()=='tr' else 4] if incident else c.description
        self.text(title,cx,239,WARNING,self.font,True)
        self.wrapped(description,220,287,808,TEXT,self.small)
        self.wrapped(c.description,220,337,808,DIM,self.small)
        self.text(f'Gemi %{g.integrity}  ·  Ses kapsülü {g.decoy_charges}',cx,390,DIM,self.small,True)
        if g.last_day_summary:
            self.text(f"Önceki gün {len(g.last_day_summary['order'])}/{g.last_day_summary.get('total',5)} bakım tamamlandı.",cx,430,WARNING,self.small,True)
        self.text('SPACE — devam et',cx,474,TEXT,self.font,True)
        if self.audio_status():self.text(self.audio_status(),cx,520,WARNING,self.small,True)
        self.text('WASD hareket  SHIFT koş  CTRL çömel  E panel',cx,566,DIM,self.small,True)
        self.text('F saklan  G kapsül  B kapı  J kayıt  TAB plan  ESC duraklat',cx,592,DIM,self.small,True)
        if g.day<8:
            self.text(f'Bugünün bakım planı · {len(g.tasks.tasks)} görev · 7 dakika',cx,631,TEXT,self.small,True)
            first=[NAMES[name] for name in g.tasks.tasks if g.tasks.available(name)]
            self.text('Önce: '+', '.join(first),cx,662,WARNING,self.tiny,True)
            for i,task in enumerate(g.tasks.tasks.values()):
                col,row=i%3,i//3
                self.text(NAMES[task.name]+' — '+task.title,90+col*374,696+row*28,DIM,self.tiny)
        else:
            self.text('Kaçış: güç dağıtımı → rota hizalama → kapsül kilidi.',cx,641,DIM,self.small,True)

    def language_rects(self):
        if self.g.paused and hasattr(self.g,"menu"):return self.g.menu.language_rects()
        return [('tr',pygame.Rect(C.SCREEN_W-272,18,118,36)),('en',pygame.Rect(C.SCREEN_W-144,18,118,36))]

    def audio_status(self):
        if not self.g.audio.available:return 'Ses cihazı yok · M: Tekrar dene'
        if not self.g.audio.enabled:return 'Ses kapalı · M: Aç'
        return ''

    def language_buttons(self):
        for code,rect in self.language_rects():
            self.task_panels.button(rect,'Türkçe' if code=='tr' else 'English',language()==code)
        self.text('L: Türkçe / English',C.SCREEN_W-270,61,DIM,self.tiny)

    def ending(self,title,subtitle,color=TEXT):
        self.background();cx=C.SCREEN_W//2
        if title=='SİNYAL KESİLDİ':draw_creature(self.g.screen,(cx,175),-math.pi/2,self.g.sim_time,False,2.4)
        self.text(title,cx,278,TEXT,self.heading,True)
        self.text(subtitle,cx,342,DIM,self.small,True)
        self.text(f'Gün {self.g.day}  ·  Gemi %{self.g.integrity}',cx,392,DIM,self.small,True)
        self.text('R yeni deneme · Q çıkış',cx,463,TEXT,self.font,True)

    def overlay(self):
        g=self.g
        journal=g.logbook.open and g.phase=='PLAYING'
        if not g.show_map and not g.paused and not journal:return
        shade=pygame.Surface((C.SCREEN_W,C.SCREEN_H),pygame.SRCALPHA)
        shade.fill((4,4,7,245));g.screen.blit(shade,(0,0))
        if g.paused:
            g.menu.draw(pause=True)
            return
        if journal:
            self.journal()
            return
        self.text('Gemi planı',24,86,TEXT,self.heading)
        self.text('TAB kapat — zaman akıyor',24,126,DIM,self.small)
        pygame.draw.line(g.screen,(99,112,105),(24,168),(1224,168))
        if g.day<8 and g.tasks.incident:
            incident=g.tasks.incident
            self.text(incident[1 if language()=='tr' else 2],24,185,WARNING,self.font)
            self.wrapped(incident[3 if language()=='tr' else 4],24,217,780,DIM,self.tiny)
        self.text(f'{g.day:02d} / 08',744,187,WARNING,self.small)
        g.screen.blit(self.chart,(24,264))
        sx=800/C.WORLD_W;sy=339/C.WORLD_H
        def point(p):return pygame.Vector2(24+p.x*sx,264+p.y*sy)
        for room in g.ship_map.rooms:
            p=point(room.world_center)
            label=self.tiny.render(tr(NAMES[room.name]),True,TEXT)
            backing=pygame.Rect(p.x-label.get_width()/2-4,p.y-24,label.get_width()+8,label.get_height()+2)
            pygame.draw.rect(g.screen,(19,31,34),backing,border_radius=2)
            g.screen.blit(label,(backing.x+4,backing.y+1))
            if room.name in conditions_for(g.day).leak_rooms:
                pygame.draw.circle(g.screen,(105,70,58),tuple(map(int,p)),10,1)
            if room.name in g.tasks.tasks and g.day<8:
                task=g.tasks.tasks[room.name]
                pygame.draw.circle(g.screen,FAINT if task.done else WARNING,tuple(map(int,p)),5,1)
            elif g.day==8 and room.name==g.tasks.day8_current_target():
                pygame.draw.circle(g.screen,WARNING,tuple(map(int,p)),6,1)
        p=point(g.player.pos)
        pygame.draw.circle(g.screen,TEXT,tuple(map(int,p)),4)
        for door in g.ship_map.doors.doors:
            p=point(door.center)
            color=DANGER if door.broken else WARNING if door.closed else DIM
            pygame.draw.line(g.screen,color,(p.x-7,p.y),(p.x+7,p.y),3)
        self.text('Nokta: sen · Halkalar: bakım noktaları',24,622,DIM,self.small)
        self.text('Çizgili bölmeler kapalı. Alternatif yolları kullan.',24,654,DIM,self.small)
        self.text('Kısa çizgiler: kapılar · B: Yakında aç/kapat',24,686,DIM,self.small)
        self.card(pygame.Rect(847,184,377,555))
        self.text('GÜNLÜK GÖREVLER' if g.day<8 else 'KAÇIŞ SIRASI',865,194,TEXT,self.font)
        names=list(g.tasks.tasks) if g.day<8 else C.DAY8_SEQUENCE
        for i,name in enumerate(names):
            task=g.tasks.tasks.get(name)
            done=task.done if g.day<8 else i<g.tasks.day8_step
            kind=task.operation if g.day<8 else work_for_day(8,name)
            yy=236+i*88
            if i%2==0:pygame.draw.rect(g.screen,(26,34,37),(855,yy-5,361,85))
            self.text(NAMES[name],884,yy,DIM if done else TEXT,self.small)
            if done:pygame.draw.lines(g.screen,DIM,False,[(866,yy+10),(870,yy+14),(878,yy+5)],2)
            else:self.text('·',865,yy,TEXT,self.small)
            blocked=g.tasks.blocked_by(name) if g.day<8 else []
            label='Tamamlandı' if done else ('Bekliyor: '+', '.join(NAMES[n] for n in blocked)) if blocked else f'{task.step+1}/{len(task.operations)} · '+job_title(name,kind) if g.day<8 else job_title(name,kind)
            self.text(label,884,yy+23,DIM if done or blocked else WARNING,self.tiny)
            if g.day<8:
                stages=' → '.join(job_title(name,operation) for operation in task.operations)
                self.wrapped(stages,884,yy+46,320,DIM,self.tiny,18)

    def journal(self):
        g=self.g;book=g.logbook
        self.card(pygame.Rect(140,142,968,550))
        self.text('MÜRETTEBAT KAYITLARI',174,173,TEXT,self.heading)
        self.text(f'Bulunan kayıt: {len(book.entries)} / {len(LOGS)}',174,222,DIM,self.small)
        entry=book.current
        if entry:
            self.text(NAMES[entry.room],174,283,WARNING,self.small)
            self.text(entry.title,174,323,TEXT,self.heading)
            self.wrapped(entry.body,174,386,885,TEXT,self.font,31)
        else:
            self.wrapped('Henüz kayıt bulamadın. Mürettebat, Gözlem, Revir ve Hangardaki küçük kayıt terminallerine bak.',174,320,865,TEXT,self.font,31)
        self.text('Sol / Sağ: Kayıt değiştir · J / ESC: Kapat',174,603,DIM,self.small)
        self.text('Kayıt okurken oyun devam eder. P: Duraklat.',174,644,WARNING,self.small)
