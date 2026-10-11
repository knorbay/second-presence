"""Muted title screen, real save slot, settings and short loading transition."""
import math
import pygame
import config as C
from localization import language,set_language
from ui_fonts import ui_font,normalize_text
from menu_scene import MenuScene,draw_ship_mark

TITLE='SECOND PRESENCE'
TEXT=(231,228,217);DIM=(161,160,153);BRASS=(189,164,119)


def label(turkish,english):return turkish if language()=='tr' else english


class MenuUI:
    def __init__(self,game):
        self.g=game
        self.scene=MenuScene(game)
        self.title=ui_font(74,True)
        self.heading=ui_font(34,True)
        self.body=ui_font(23)
        self.small=ui_font(17)
        self.time=0;self.selection=0;self.dragging=None
        self.message='';self.message_time=0
        self.return_phase='MAIN_MENU';self.return_paused=False
        self.loading_job=None;self.loading_elapsed=0;self.loading_done=False
        self.refresh_save()

    def refresh_save(self):self.save_summary=self.g.store.summary()

    def text(self,text,pos,font=None,color=TEXT):
        self.g.screen.blit((font or self.body).render(normalize_text(text),True,color),pos)

    def buttons(self):
        g=self.g
        if g.paused:
            names=[('resume',label('Devam et','Resume')),('save',label('Kaydet','Save')),
                   ('settings',label('Ayarlar','Settings')),('menu',label('Ana menü','Main menu')),('quit',label('Çıkış','Quit'))]
        else:
            names=[('play',label('Oyna','Play')),('load',label('Yükle','Load')),
                   ('settings',label('Ayarlar','Settings')),('quit',label('Çıkış','Quit'))]
        return [(key,text,pygame.Rect(92,442+i*56,310,46)) for i,(key,text) in enumerate(names)]

    def enabled(self,key):
        if key=='save':return self.g.phase in ('PLAYING','DAY_TRANSITION')
        return key!='load' or self.save_summary is not None

    def open_settings(self):
        g=self.g;self.return_phase=g.phase;self.return_paused=g.paused
        g.phase='SETTINGS';g.paused=False;g.audio.pause(True)
        self.selection=0;self.dragging=None

    def back(self):
        g=self.g;g.phase=self.return_phase;g.paused=self.return_paused
        g.audio.pause(g.paused or g.phase=='MAIN_MENU')
        self.selection=0;self.dragging=None

    def start_loading(self,job):
        self.g.phase='LOADING';self.g.paused=False;self.g.audio.pause(True)
        self.loading_job=job;self.loading_elapsed=0;self.loading_done=False
        self.selection=0

    def act(self,key):
        g=self.g
        if not self.enabled(key):return
        if key=='play':self.start_loading(g._new_game_from_menu)
        elif key=='load':self.start_loading(lambda:g.store.load(g))
        elif key=='settings':self.open_settings()
        elif key=='resume':g.paused=False;g.audio.pause(False)
        elif key=='save':
            if g._save_game():self.refresh_save()
        elif key=='menu':
            if g.phase=='PLAYING' and not g._save_game(notify=False):return
            g._cancel_panel();g.show_map=False;g.logbook.open=False
            g.phase='MAIN_MENU';g.paused=False;g.audio.reset();g.audio.pause(True)
            self.refresh_save();self.selection=0
        elif key=='quit':g.running=False

    def change_language(self,code):
        set_language(code);self.g.settings['language']=code
        self.g.presentation.refresh();self.persist_settings()

    def persist_settings(self):
        try:self.g.store.save_settings(self.g.settings)
        except OSError:self.notice(label('Ayarlar diske yazılamadı.','Settings could not be saved.'))

    def notice(self,text):self.message=text;self.message_time=4

    def slider(self,key):return pygame.Rect(140,335 if key=='volume' else 454,510,18)

    def adjust(self,key,position):
        r=self.slider(key);ratio=max(0,min(1,(position-r.x)/r.w))
        self.g.settings[key]=ratio if key=='volume' else .6+ratio
        if key=='volume':self.g.audio.set_master(self.g.settings[key])
        self.persist_settings()

    def handle(self,event):
        g=self.g
        if g.phase not in ('MAIN_MENU','SETTINGS','LOADING') and not g.paused:return False
        if event.type==pygame.QUIT:return False
        if g.phase=='LOADING':return True
        if event.type==pygame.KEYDOWN:
            if event.key==pygame.K_l:self.change_language('en' if language()=='tr' else 'tr');return True
            if event.key==pygame.K_m:g.audio.toggle();return True
        if g.phase=='SETTINGS':
            if event.type==pygame.KEYDOWN:
                if event.key==pygame.K_ESCAPE:self.back()
                elif event.key in (pygame.K_UP,pygame.K_DOWN):self.selection=(self.selection+(-1 if event.key==pygame.K_UP else 1))%3
                elif event.key in (pygame.K_LEFT,pygame.K_RIGHT):
                    if self.selection==0:self.change_language('tr' if event.key==pygame.K_LEFT else 'en')
                    else:
                        key='volume' if self.selection==1 else 'brightness';r=self.slider(key)
                        current=self.g.settings[key]-(.6 if key=='brightness' else 0)
                        self.adjust(key,r.x+(current+(.05 if event.key==pygame.K_RIGHT else -.05))*r.w)
                elif event.key in (pygame.K_RETURN,pygame.K_SPACE) and self.selection==0:self.change_language('en' if language()=='tr' else 'tr')
            elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                for code,r in self.language_rects():
                    if r.collidepoint(event.pos):self.change_language(code)
                for key in ('volume','brightness'):
                    if self.slider(key).inflate(0,22).collidepoint(event.pos):self.dragging=key;self.adjust(key,event.pos[0])
                if pygame.Rect(140,615,210,45).collidepoint(event.pos):self.back()
            elif event.type==pygame.MOUSEMOTION and self.dragging:self.adjust(self.dragging,event.pos[0])
            elif event.type==pygame.MOUSEBUTTONUP:self.dragging=None
            return True
        buttons=self.buttons()
        if event.type==pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE,pygame.K_p) and g.paused:self.act('resume')
            elif event.key==pygame.K_q:self.act('quit')
            elif event.key in (pygame.K_UP,pygame.K_DOWN):
                step=-1 if event.key==pygame.K_UP else 1
                for _ in buttons:
                    self.selection=(self.selection+step)%len(buttons)
                    if self.enabled(buttons[self.selection][0]):break
            elif event.key in (pygame.K_RETURN,pygame.K_SPACE):self.act(buttons[self.selection][0])
        elif event.type==pygame.MOUSEMOTION:
            for i,(key,text,r) in enumerate(buttons):
                if r.collidepoint(event.pos) and self.enabled(key):self.selection=i
        elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            for code,r in self.language_rects():
                if r.collidepoint(event.pos):self.change_language(code);return True
            for key,text,r in buttons:
                if r.collidepoint(event.pos):self.act(key);break
        return True

    def update(self,dt):
        self.time+=dt;self.message_time=max(0,self.message_time-dt)
        if self.g.phase!='LOADING':return
        self.loading_elapsed+=dt
        if not self.loading_done:
            try:
                self.loading_job();self.target_phase=self.g.phase
                self.g.phase='LOADING';self.loading_done=True
            except (OSError,ValueError,TypeError,KeyError,IndexError) as error:
                self.g.phase='MAIN_MENU';self.g.paused=False
                self.notice(label('Kayıt yüklenemedi. Dosya bozuk veya erişilemiyor.','Unable to load. The save is invalid or inaccessible.'))
                self.refresh_save();return
        if self.loading_elapsed>=.75:
            self.g.phase=self.target_phase;self.g.audio.pause(False)
            self.refresh_save()

    def language_rects(self):return [('tr',pygame.Rect(C.SCREEN_W-200,39,72,35)),('en',pygame.Rect(C.SCREEN_W-120,39,72,35))]

    def language_buttons(self):
        for code,r in self.language_rects():
            pygame.draw.rect(self.g.screen,(42,44,43),r,border_radius=2)
            pygame.draw.rect(self.g.screen,BRASS if code==language() else (86,87,83),r,1,border_radius=2)
            self.text(code.upper(),(r.x+24,r.y+8),self.small,BRASS if code==language() else DIM)

    def draw(self,pause=False):
        g=self.g;screen=g.screen
        if pause:
            shade=pygame.Surface(screen.get_size(),pygame.SRCALPHA);shade.fill((3,5,7,235));screen.blit(shade,(0,0))
        else:
            screen.fill((7,10,12))
            self.scene.draw(screen,self.time)
            # Quiet registration marks frame the live deck rather than a separate illustration.
            for x,y,dx,dy in ((756,106,1,1),(1184,106,-1,1),(756,780,1,-1),(1184,780,-1,-1)):
                pygame.draw.lines(screen,(63,77,75),False,[(x+20*dx,y),(x,y),(x,y+20*dy)],1)
        self.language_buttons()
        if g.phase=='SETTINGS':self.draw_settings();return
        if g.phase=='LOADING':
            draw_ship_mark(screen,pygame.Rect(C.SCREEN_W//2-27,304,54,54))
            self.text(label('Yükleniyor…','Loading…'),(C.SCREEN_W//2-70,426),self.body)
            center=(C.SCREEN_W//2,490)
            for i in range(12):
                angle=i*math.tau/12;color=BRASS if i==int(self.time*12)%12 else (67,66,59)
                pygame.draw.circle(screen,color,(int(center[0]+math.cos(angle)*19),int(center[1]+math.sin(angle)*19)),2)
            self.text(label('Sesleri dinle. Gürültü rotanı ele verir.','Listen closely. Noise gives away your route.'),(C.SCREEN_W//2-220,552),self.small,DIM)
            return
        draw_ship_mark(screen,pygame.Rect(92,120,36,36))
        self.text(label('BAKIM VARDİYASI','MAINTENANCE SHIFT'),(148,130),self.small,DIM)
        if pause:
            self.text(label('DURAKLATILDI','PAUSED'),(92,245),self.heading)
            self.text(label('Gün '+str(g.day)+' · Gemi %'+str(round(g.integrity)),
                            'Day '+str(g.day)+' · Hull '+str(round(g.integrity))+'%'),(94,303),self.body,DIM)
        else:
            self.text('SECOND',(87,224),self.title)
            self.text('PRESENCE',(87,297),self.title)
            self.text(label('İKİNCİ VARLIK','SECOND PRESENCE'),(94,395),self.small,DIM)
        for i,(key,text,r) in enumerate(self.buttons()):
            enabled=self.enabled(key);selected=i==self.selection and enabled
            if selected:
                pygame.draw.rect(screen,(35,44,46),r)
                pygame.draw.line(screen,BRASS,(r.x,r.y+8),(r.x,r.bottom-8),3)
                pygame.draw.lines(screen,BRASS,False,[(r.right-23,r.centery-4),(r.right-19,r.centery),(r.right-23,r.centery+4)],1)
            pygame.draw.line(screen,(54,67,67),(r.x+12,r.bottom),(r.right,r.bottom))
            self.text(text,(r.x+19,r.y+9),self.body,TEXT if enabled else (96,96,91))
            if key=='load':
                description=label('Kayıt yok','No save') if not self.save_summary else label('Gün ','Day ')+str(self.save_summary['day'])
                self.text(description,(r.right-110,r.y+14),self.small,DIM if enabled else (96,96,91))
        y=766
        pygame.draw.line(screen,(63,73,69),(92,739),(402,739))
        if self.message_time>0:self.text(self.message,(92,y),self.small,BRASS)
        elif pause:self.text(label('ESC / P devam · M ses','ESC / P resume · M audio'),(92,y),self.small,DIM)
        else:self.text(label('Sekiz vardiya. Bir gemi.','Eight shifts. One ship.'),(92,y),self.small,DIM)
        self.text(label('0.9 · ÇALIŞMA ADI','0.9 · WORKING TITLE'),(92,C.SCREEN_H-33),self.small,(125,124,116))

    def draw_settings(self):
        g=self.g;screen=g.screen
        pygame.draw.rect(screen,(19,23,26),(92,168,650,540),border_radius=4)
        pygame.draw.rect(screen,(89,87,77),(92,168,650,540),1,border_radius=4)
        self.text(label('AYARLAR','SETTINGS'),(140,199),self.heading)
        self.text(label('Dil','Language'),(140,264),self.body,BRASS if self.selection==0 else TEXT)
        self.text('TR  /  EN  ·  L',(420,268),self.small,BRASS)
        for key,title in (('volume',label('Ses düzeyi','Master volume')),('brightness',label('Fener parlaklığı','Flashlight brightness'))):
            r=self.slider(key);value=g.settings[key];ratio=value if key=='volume' else value-.6
            self.text(title,(r.x,r.y-45),self.body,BRASS if self.selection==(1 if key=="volume" else 2) else TEXT)
            self.text(str(round(value*100))+'%',(r.right-45,r.y-43),self.small,BRASS)
            pygame.draw.rect(screen,(60,62,60),r,border_radius=3)
            pygame.draw.rect(screen,(147,133,103),(r.x,r.y,int(r.w*ratio),r.h),border_radius=3)
            pygame.draw.circle(screen,TEXT,(int(r.x+r.w*ratio),r.centery),10)
        self.text(label('Fener ayarı genel aydınlatmayı açmaz.','Flashlight brightness does not restore ship lighting.'),(140,507),self.small,DIM)
        self.text(label('Yukarı/Aşağı: seç · Sol/Sağ: ayarla · L: dil','Up/Down: select · Left/Right: adjust · L: language'),(140,548),self.small,DIM)
        if not g.audio.available:self.text(label('Ses cihazı yok. M ile yeniden dene.','No audio device. Press M to retry.'),(140,581),self.small,BRASS)
        pygame.draw.rect(screen,(49,51,49),(140,615,210,45),border_radius=3)
        self.text(label('Geri · ESC','Back · ESC'),(160,627),self.body)
