"""Task-specific instruments. Rendering and mouse hit areas share one layout."""
import math
import pygame
import config as C

NEW_KINDS={'filter','wires','sequence','signal','valves','course','cargo','fuel'}
COLORS=((186,153,124),(147,169,182),(177,176,142))


def panel_rect():return pygame.Rect(24,C.VIEW_H-430,580,406)


def widgets(work):
    x,y,w,h=panel_rect()
    if work.kind=='filter':
        return [pygame.Rect(x+54+(i%4)*116,y+128+(i//4)*51,98,41) for i in range(12)]
    if work.kind=='wires':
        return ([pygame.Rect(x+63,y+134+i*56,52,40) for i in range(3)],
                [pygame.Rect(x+457,y+134+i*56,52,40) for i in range(3)])
    if work.kind=='sequence':return [pygame.Rect(x+62+i*150,y+176,110,68) for i in range(3)]
    if work.kind=='signal':return pygame.Rect(x+40,y+232,500,24)
    if work.kind=='valves':return [pygame.Rect(x+64+i*156,y+149,108,84) for i in range(3)]
    if work.kind=='course':return pygame.Rect(x+40,y+127,346,175)
    if work.kind=='cargo':
        return ([pygame.Rect(x+36+i*132,y+140,112,48) for i in range(4)],
                [pygame.Rect(x+40+i*177,y+232,147,61) for i in range(3)])
    if work.kind=='fuel':return pygame.Rect(x+376,y+147,162,90)
    return []


def confirm_rect(work):
    x,y,w,h=panel_rect()
    return pygame.Rect(x+408,y+246,138,44) if work.kind=='course' else pygame.Rect(x+189,y+285,202,36)


class TaskPanels:
    def __init__(self,presentation):self.p=presentation

    def chassis(self,work):
        p=self.p;s=p.g.screen;r=panel_rect();x,y,w,h=r
        pygame.draw.rect(s,(4,8,10),r.move(5,7),border_radius=8)
        pygame.draw.rect(s,(71,79,77),r,border_radius=6)
        pygame.draw.rect(s,(30,39,43),r.inflate(-4,-4),border_radius=5)
        pygame.draw.rect(s,(17,25,29),r.inflate(-14,-14),border_radius=3)
        pygame.draw.line(s,(160,158,139),(x+9,y+1),(x+w-10,y+1))
        pygame.draw.rect(s,(41,51,54),(x+7,y+7,w-14,63),border_radius=2)
        pygame.draw.line(s,(95,106,101),(x+8,y+70),(x+w-9,y+70))
        for xx in (x+5,x+w-6):
            for yy in (y+6,y+h-7):
                pygame.draw.circle(s,(139,141,123),(xx,yy),2)
                pygame.draw.line(s,(30,38,40),(xx-1,yy+1),(xx+1,yy-1))
        for yy in range(y+133,y+327,16):
            pygame.draw.line(s,(24,33,36),(x+18,yy),(x+w-19,yy))
        for xx in range(x+22,x+w-20,24):
            pygame.draw.line(s,(22,31,35),(xx,y+127),(xx,y+326))
        # Mechanical department pictogram, assembled from simple stamped parts.
        icon=pygame.Rect(x+20,y+18,38,38)
        pygame.draw.rect(s,(22,31,35),icon,border_radius=3)
        pygame.draw.rect(s,(97,109,105),icon,1,border_radius=3)
        center=icon.center;color=(200,186,151)
        if work.kind in ('wires','rewire','repair','sequence'):
            for i in range(3):
                xx=icon.x+10+i*9
                pygame.draw.line(s,color,(xx,icon.y+7),(xx,icon.bottom-7),2)
                pygame.draw.rect(s,(133,150,139),(xx-3,icon.y+12+(i%2)*9,7,5))
        elif work.kind in ('course','signal','calibrate','inspect'):
            pygame.draw.circle(s,color,center,12,1)
            pygame.draw.line(s,color,(center[0]-9,center[1]+5),(center[0]+6,center[1]-7),2)
            pygame.draw.circle(s,color,center,2)
        else:
            pygame.draw.rect(s,color,icon.inflate(-16,-10),2,border_radius=3)
            for i in range(3):pygame.draw.line(s,color,(icon.x+11,icon.y+12+i*6),(icon.right-11,icon.y+12+i*6))
        p.meter(x+20,y+h-14,w-40,work.progress,(183,169,132))

    def diagnostic_gauge(self,rect,label,value):
        p=self.p;s=p.g.screen
        pygame.draw.rect(s,(29,38,40),rect,border_radius=3)
        self.bezel(rect)
        p.text(label,rect.centerx,rect.y+9,(194,199,186),p.small,True)
        cx,cy=rect.centerx,rect.y+88;radius=49
        for n in range(0,101,5):
            a=math.pi+n/100*math.pi
            inner=radius-(8 if n%20==0 else 4)
            pygame.draw.line(s,(142,153,139),(cx+math.cos(a)*inner,cy+math.sin(a)*inner),(cx+math.cos(a)*radius,cy+math.sin(a)*radius))
        arc=[(cx+math.cos(math.pi+n/100*math.pi)*(radius-12),cy+math.sin(math.pi+n/100*math.pi)*(radius-12)) for n in range(40,61)]
        pygame.draw.lines(s,(131,150,124),False,arc,4)
        a=math.pi+value/100*math.pi
        pygame.draw.line(s,(222,199,152),(cx,cy),(cx+math.cos(a)*(radius-5),cy+math.sin(a)*(radius-5)),2)
        pygame.draw.circle(s,(173,173,150),(cx,cy),4)
        pygame.draw.rect(s,(12,23,27),(cx-28,rect.y+104,56,29),border_radius=2)
        p.text(f'{value:02d}',cx,rect.y+106,(232,228,203),p.font,True)

    def pointer(self,work,action,pos):
        if work.complete:return 'ignored'
        if action=='move':
            work.pointer_pos=pos
        areas=widgets(work)
        if work.kind=='filter' and action=='down':
            for i,r in enumerate(areas):
                if r.collidepoint(pos):return work.act('clean',i)
        elif work.kind in ('wires','cargo'):
            sources,targets=areas
            if action=='down':
                for i,r in enumerate(sources):
                    if r.collidepoint(pos):
                        work.pointer_pos=pos
                        return work.act('wire_start' if work.kind=='wires' else 'crate_start',i)
            elif action=='up':
                index=next((i for i,r in enumerate(targets) if r.collidepoint(pos)),None)
                return work.act('wire_end' if work.kind=='wires' else 'crate_end',index)
        elif work.kind in ('signal','course'):
            if action=='down' and areas.collidepoint(pos):work.dragging='instrument'
            if action in ('down','move') and work.dragging=='instrument':
                value=(pos[0]-areas.x)/areas.w
                if work.kind=='course':value=(value,(pos[1]-areas.y)/areas.h)
                return work.act('tune' if work.kind=='signal' else 'course',value)
            if action=='up':work.dragging=None
        elif work.kind in ('sequence','valves') and action=='down':
            for i,r in enumerate(areas):
                if r.collidepoint(pos):return work.press(str(i+1))
        elif work.kind=='fuel':
            if action=='down' and areas.collidepoint(pos):
                work.dragging='pump'
                return work.press('space') if not work.pumping else 'ignored'
            if action=='up' and work.dragging=='pump':
                work.dragging=None
                return work.press('space') if work.pumping else 'ignored'
        if action=='down' and work.kind in ('signal','valves','course') and confirm_rect(work).collidepoint(pos):
            return work.press('space')
        if action=='down' and work.kind=='calibrate':
            return work.press('space') if confirm_rect(work).collidepoint(pos) else 'ignored'
        if action=='down' and work.kind not in NEW_KINDS:
            x,y,w,h=panel_rect()
            buttons=[pygame.Rect(x+28+i*178,y+286,166,34) for i in range(3)]
            keys=['1','2','3'] if work.kind in ('inspect','rewire') else (['1','space','3'] if work.kind=='repair' else ['space']*3)
            for i,r in enumerate(buttons):
                if r.collidepoint(pos):return work.press(keys[i])
        return 'ignored'

    def bezel(self,rect,inset=True):
        screen=self.p.g.screen
        pygame.draw.rect(screen,(10,12,14),rect.inflate(6,6),3,border_radius=4)
        pygame.draw.rect(screen,(64,65,64),rect,1,border_radius=3)
        if inset:pygame.draw.line(screen,(89,88,83),(rect.left+4,rect.top),(rect.right-4,rect.top))

    def button(self,rect,label,active=False):
        p=self.p;screen=p.g.screen
        hovered=rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(screen,(8,9,11),rect.move(0,3),border_radius=4)
        pygame.draw.rect(screen,(139,124,88) if active else (110,123,120) if hovered else (73,88,89),rect,border_radius=4)
        inner=rect.inflate(-4,-4)
        pygame.draw.rect(screen,(81,76,55) if active else (47,62,66) if hovered else (39,51,56),inner,border_radius=3)
        pygame.draw.line(screen,(185,168,126) if active else (103,106,104),(rect.x+5,rect.y+1),(rect.right-5,rect.y+1))
        p.text(label,rect.centerx,rect.centery-p.small.get_height()//2,(235,231,219),p.small,True)

    def cable(self,start,end,color):
        screen=self.p.g.screen
        points=[]
        for n in range(31):
            t=n/30
            points.append((start[0]+(end[0]-start[0])*t,start[1]+(end[1]-start[1])*t+math.sin(t*math.pi)*18))
        pygame.draw.lines(screen,(10,12,14),False,points,8)
        pygame.draw.lines(screen,color,False,points,4)
        pygame.draw.lines(screen,tuple(min(255,c+22) for c in color),False,[(a,b-1) for a,b in points],1)

    def socket(self,rect,label,color,connected=False):
        p=self.p;s=p.g.screen;cx,cy=rect.center
        pygame.draw.rect(s,(45,59,63),rect,border_radius=3)
        pygame.draw.rect(s,(113,125,118),rect,1,border_radius=3)
        pygame.draw.circle(s,(10,21,26),(cx,cy),16)
        pygame.draw.circle(s,color,(cx,cy),14,3)
        pygame.draw.circle(s,(43,58,62),(cx,cy),10)
        p.text(label,cx,cy-p.small.get_height()//2,(232,231,213),p.small,True)
        for xx in (rect.x+4,rect.right-5):
            pygame.draw.line(s,(144,150,131),(xx,rect.y+4),(xx,rect.y+6))
        if connected:pygame.draw.rect(s,(164,185,144),(rect.right-5,rect.bottom-7,3,3))

    def instrument_details(self,work):
        p=self.p;screen=p.g.screen;x,y,w,h=panel_rect();areas=widgets(work)
        metal=(77,79,77);dark=(17,20,23);accent=(206,178,139)
        if work.kind=='filter':
            for i,r in enumerate(areas):
                if i in work.debris:
                    for yy in range(r.top+5,r.bottom-4,6):pygame.draw.line(screen,metal,(r.left+6,yy),(r.right-6,yy))
                    for n in range(6):
                        cx=r.x+12+(i*17+n*19)%72;cy=r.y+9+(i*7+n*13)%24
                        pygame.draw.circle(screen,(47,43,35),(cx,cy),6)
                        pygame.draw.circle(screen,(131,111,77),(cx-1,cy-1),3)
        elif work.kind=='sequence':
            for r in areas:
                pygame.draw.rect(screen,(15,17,20),(r.x+10,r.bottom-12,r.w-20,5),border_radius=2)
            for i in range(len(work.pattern)):
                color=accent if i<work.sequence_index else metal
                pygame.draw.circle(screen,color,(x+72+i*22,y+258),3)
        elif work.kind=='valves':
            for i,r in enumerate(areas):
                pygame.draw.line(screen,dark,(r.left-16,r.centery),(r.right+16,r.centery),14)
                pygame.draw.line(screen,metal,(r.left-16,r.centery),(r.right+16,r.centery),8)
                center=(r.centerx,r.centery)
                pygame.draw.circle(screen,(20,22,24),center,29)
                pygame.draw.circle(screen,(138,130,111),center,25,3)
                angle=work.valves[i]/10*math.tau-math.pi/2
                for offset in (0,math.tau/3,2*math.tau/3):
                    end=(r.centerx+math.cos(angle+offset)*22,r.centery+math.sin(angle+offset)*22)
                    pygame.draw.line(screen,accent,center,end,3)
                pygame.draw.circle(screen,(191,185,165),center,5)
        elif work.kind=='course':
            self.bezel(areas)
            for j in range(19):
                px=areas.x+12+(j*71)%320;py=areas.y+9+(j*37)%150
                pygame.draw.circle(screen,(114,116,118),(px,py),1)
            gx=areas.x+work.course_goal[0]*areas.w;gy=areas.y+work.course_goal[1]*areas.h
            pygame.draw.circle(screen,accent,(int(gx),int(gy)),22,1)
            p.text('X '+str(round(work.course[0]*100)),x+407,y+143,(169,178,168),p.tiny)
            p.text('Y '+str(round(work.course[1]*100)),x+407,y+165,(169,178,168),p.tiny)
        elif work.kind=='cargo':
            crates,bays=areas
            for i,r in enumerate(crates):
                if i in work.delivered:continue
                for xx in (r.left+5,r.right-7):pygame.draw.rect(screen,(115,105,84),(xx,r.top+5,3,r.h-10))
                for j in range(12):pygame.draw.line(screen,metal,(r.x+24+j*3,r.bottom-9),(r.x+24+j*3,r.bottom-4))
            for i,r in enumerate(bays):
                for n in range(5):pygame.draw.line(screen,(94,82,57),(r.left+7+n*9,r.top+3),(r.left+13+n*9,r.top+9),2)
                count=sum(work.crates[j]==i for j in work.delivered)
                for n in range(count):pygame.draw.rect(screen,accent,(r.right-12-n*8,r.bottom-12,5,5))
        elif work.kind=='fuel':
            tank=pygame.Rect(x+60,y+145,266,146);self.bezel(tank)
            for n in range(1,10):
                yy=tank.bottom-n*tank.h//10
                pygame.draw.line(screen,(198,187,157),(tank.left+5,yy),(tank.left+15+(n%5==0)*8,yy))
            pygame.draw.lines(screen,metal,False,[(tank.right+4,tank.centery),(x+353,tank.centery),(x+353,y+174),(areas.left,y+174)],5)
            pygame.draw.circle(screen,accent,(x+353,y+174),5,1)
        elif work.kind=='signal':
            graph=pygame.Rect(x+40,y+132,500,75);self.bezel(graph)
            # Fine divisions stay beneath the live signal trace.
            for xx in range(graph.left+20,graph.right,40):pygame.draw.line(screen,(53,56,54),(xx,graph.bottom-4),(xx,graph.bottom-9))

    def draw(self,work):
        p=self.p;screen=p.g.screen;x,y,w,h=panel_rect();areas=widgets(work)
        white=(226,224,216);dim=(169,168,163);accent=(206,178,139)
        instructions={
            'filter':'Kirli bölmelere tıkla; filtredeki bütün birikintileri temizle.',
            'wires':'Soldaki kabloyu aynı harfli sağ girişe sürükle.',
            'sequence':'Önce yanıp sönen sırayı izle; sonra 1 / 2 / 3 ile tekrarla.',
            'signal':'Frekans çubuğunu sürükle veya oklarla ayarla; sinyali doğrula.',
            'valves':'Vanalara tıkla veya 1 / 2 / 3 kullan. Akışları hedefe getir.',
            'course':'Nişangâhı sürükle veya oklarla hedefe getir; rotayı kilitle.',
            'cargo':'Her kasayı aynı harfli yük yuvasına sürükle.',
            'fuel':'Pompayı basılı tut; seviye taralı alana gelince bırak. SPACE aç/kapat.'}
        p.wrapped(instructions[work.kind],x+20,y+91,w-40,white,p.small,21)
        if work.kind=='filter':
            for i,r in enumerate(areas):
                self.button(r,'')
                for xx in range(r.left+5,r.right-4,5):pygame.draw.line(screen,(19,34,39),(xx,r.top+5),(xx,r.bottom-5),2)
                if i not in work.debris:
                    pygame.draw.lines(screen,(167,188,148),False,[(r.centerx-6,r.centery),(r.centerx-1,r.centery+5),(r.centerx+7,r.centery-5)],2)
                if i in work.debris:
                    for n in range(5):
                        dx=(i*19+n*13)%70;dy=(i*7+n*11)%23
                        pygame.draw.circle(screen,(137,127,106),(r.x+14+dx,r.y+9+dy),4+(n%2))
            p.text(f'Temizlenen: {work.debris_count-len(work.debris)} / {work.debris_count}',x+24,y+300,dim,p.small)
        elif work.kind=='wires':
            sources,targets=areas
            for i,r in enumerate(sources):
                pygame.draw.line(screen,COLORS[i],(x+23,r.centery),r.center,4)
                self.socket(r,chr(65+i),COLORS[i],i in work.connected)
            for j,r in enumerate(targets):
                source=work.wire_goal.index(j)
                pygame.draw.line(screen,COLORS[source],r.center,(x+w-23,r.centery),4)
                self.socket(r,chr(65+source),COLORS[source],source in work.connected)
            for i in work.connected:self.cable(sources[i].center,targets[work.wire_goal[i]].center,COLORS[i])
            if work.dragging=='wire' and work.pointer_pos is not None:
                self.cable(sources[work.selected].center,work.pointer_pos,COLORS[work.selected])
            p.text(f'Bağlı hat: {len(work.connected)} / 3',x+24,y+308,dim,p.small)
        elif work.kind=='sequence':
            total=len(work.pattern)*.65+.35
            elapsed=total-work.sequence_timer
            slot=int(elapsed/.65)
            flash=work.pattern[slot] if work.sequence_timer>0 and slot<len(work.pattern) and elapsed% .65<.4 else None
            p.text('Sırayı izle…' if work.sequence_timer>0 else f'Tekrarla: {work.sequence_index} / {len(work.pattern)}',x+24,y+135,accent,p.small)
            for i,r in enumerate(areas):self.button(r,str(i+1),i==flash)
            p.meter(x+62,y+269,410,work.sequence_index/len(work.pattern),accent)
        elif work.kind=='signal':
            graph=pygame.Rect(x+40,y+132,500,75)
            pygame.draw.rect(screen,(14,29,33),graph)
            for xx in range(graph.x+10,graph.right,25):pygame.draw.line(screen,(30,50,51),(xx,graph.top),(xx,graph.bottom))
            for yy in range(graph.y+10,graph.bottom,15):pygame.draw.line(screen,(30,50,51),(graph.left,yy),(graph.right,yy))
            points=[]
            for j in range(101):
                v=j/100;strength=math.exp(-((v-work.target)/.13)**2)
                points.append((graph.x+int(v*graph.w),graph.bottom-7-int(strength*57)))
            pygame.draw.lines(screen,(155,186,157),False,points,2)
            sx=graph.x+int(work.cursor*graph.w)
            pygame.draw.line(screen,accent,(sx,graph.top),(sx,graph.bottom),2)
            pygame.draw.rect(screen,(63,63,64),areas)
            pygame.draw.line(screen,white,(sx,areas.top-3),(sx,areas.bottom+3),4)
            quality=int(100*math.exp(-((work.cursor-work.target)/.13)**2))
            p.text(f'Sinyal: %{quality}  ·  Frekans: {int(work.cursor*100)}',x+40,y+260,dim,p.tiny)
            self.button(confirm_rect(work),'Sinyali doğrula')
        elif work.kind=='valves':
            for i,r in enumerate(areas):
                self.button(r,'')
                pygame.draw.circle(screen,dim,r.center,25,2)
                angle=work.valves[i]/10*math.tau-math.pi/2
                end=(r.centerx+math.cos(angle)*23,r.centery+math.sin(angle)*23)
                pygame.draw.line(screen,accent,r.center,end,3)
                p.text(str(i+1),r.x+8,r.y+4,white,p.tiny)
                p.text(f'%{work.valves[i]*10} / %{work.valve_goal[i]*10}',r.centerx,r.bottom+10,dim,p.tiny,True)
            self.button(confirm_rect(work),'Akışı doğrula')
        elif work.kind=='course':
            pygame.draw.rect(screen,(14,28,34),areas)
            for n in range(1,5):
                pygame.draw.line(screen,(39,59,61),(areas.x+areas.w*n//5,areas.top),(areas.x+areas.w*n//5,areas.bottom))
                pygame.draw.line(screen,(39,59,61),(areas.left,areas.y+areas.h*n//5),(areas.right,areas.y+areas.h*n//5))
            target=(int(areas.x+work.course_goal[0]*areas.w),int(areas.y+work.course_goal[1]*areas.h))
            point=(int(areas.x+work.course[0]*areas.w),int(areas.y+work.course[1]*areas.h))
            pygame.draw.circle(screen,accent,target,12,2)
            pygame.draw.line(screen,white,(point[0]-14,point[1]),(point[0]+14,point[1]),2)
            pygame.draw.line(screen,white,(point[0],point[1]-14),(point[0],point[1]+14),2)
            self.button(confirm_rect(work),'Rotayı kilitle')
        elif work.kind=='cargo':
            crates,bays=areas
            for i,r in enumerate(crates):
                if i in work.delivered:
                    p.text('Sabitlendi',r.centerx,r.y+14,dim,p.tiny,True)
                else:self.button(r,f'{i+1} · KASA {chr(65+work.crates[i])}')
            for i,r in enumerate(bays):self.button(r,f'YUVA {chr(65+i)}')
            if work.dragging=='crate' and work.pointer_pos is not None:
                r=pygame.Rect(0,0,110,42);r.center=work.pointer_pos
                self.button(r,'KASA '+chr(65+work.crates[work.selected]))
            p.text(f'Sabitlenen yük: {len(work.delivered)} / 4',x+24,y+312,dim,p.small)
        elif work.kind=='fuel':
            tank=pygame.Rect(x+60,y+145,266,146)
            pygame.draw.rect(screen,(35,37,39),tank)
            fill=int(work.fuel*tank.h)
            pygame.draw.rect(screen,(114,104,79),(tank.x,tank.bottom-fill,tank.w,fill))
            top=tank.bottom-int((work.target+work.tolerance)*tank.h)
            bottom=tank.bottom-int((work.target-work.tolerance)*tank.h)
            for xx in range(tank.left,tank.right-10,14):pygame.draw.line(screen,accent,(xx,top),(xx+10,bottom),2)
            pygame.draw.rect(screen,dim,tank,1)
            self.button(areas,'POMPALIYOR' if work.pumping else 'POMPA',work.pumping)
            p.text(f'Seviye: %{int(work.fuel*100)}',x+64,y+307,dim,p.small)
        self.instrument_details(work)

    def legacy_buttons(self,work):
        if work.kind=='calibrate':
            self.button(confirm_rect(work),'Doğrula')
            return
        x,y,w,h=panel_rect()
        labels=['1','2','3'] if work.kind in ('inspect','rewire') else (['1: Gücü kes','SPACE: Bağla','3: Gücü ver'] if work.kind=='repair' else ['Doğrula','Doğrula','Doğrula'])
        if work.name=='Airlock' and work.kind=='repair':labels=['1: Kapağı kilitle','SPACE: Sabitle','3: Test et']
        if work.name=='Hangar' and work.kind=='repair':labels=['1: Mandalı aç','SPACE: Hizala','3: Hazırla']
        for i,label in enumerate(labels):self.button(pygame.Rect(x+28+i*178,y+286,166,34),label)
