"""Optional crew recordings found physically in unused parts of the ship."""
from dataclasses import dataclass
import pygame
import config as C


@dataclass(frozen=True)
class CrewLog:
    key: str
    room: str
    day: int
    title: str
    body: str


LOGS=(
    CrewLog('shift','Quarters',1,'Vardiya devri',
        'Vardiya planını kontrol et. Her arızada önce müdahale edilecek sistem değişiyor. '
        'Kilidi açılan işlerden başla; bağlı sistemleri sonra devreye al. Diğer ranzalar hâlâ boş.'),
    CrewLog('glass','Observation',2,'Camın öte tarafı',
        'Gözlem camında iki yansıma gördüm. Arkama döndüğümde koridor boştu. '
        'Geçtiği yerde üç uzun çizik kalıyor. İzler bir süre sonra soluyor; yakın zamanda geçmiş olabilir.'),
    CrewLog('locker','Medbay',4,'Son muayene',
        'Dolaba girmemi gördü. Kapının önünde bekledi, sonra geri dönüp kontrol etti. '
        'Önce bir köşede görüşünü kesmeliyim. Aynı kaçış yolunu her vardiyada kullanmak artık işe yaramıyor.'),
    CrewLog('escape','Hangar',6,'Ayrılma izni',
        'Kapsülün kilidini denedim. Güç ve rota hazır olmadan açılmıyor. '
        'Son vardiyada sıra belli: Güç, Navigasyon, Hangar. Gövdenin içinden gelen sesler yaklaşırken bu kaydı bırakıyorum.'),
)


def log_point(ship_map,entry):
    x,y,_,_=ship_map.room_by_name(entry.room).rect
    return pygame.Vector2(x*C.TILE+28,y*C.TILE+50)


class Logbook:
    def __init__(self):
        self.found=set()
        self.selected=None
        self.open=False

    @property
    def entries(self):return [entry for entry in LOGS if entry.key in self.found]

    @property
    def current(self):
        return next((entry for entry in self.entries if entry.key==self.selected),None)

    def nearby(self,ship_map,position,day):
        candidates=[entry for entry in LOGS if day>=entry.day and
            pygame.Vector2(position).distance_to(log_point(ship_map,entry))<44 and
            ship_map.line_of_sight(*position,*log_point(ship_map,entry))]
        return min(candidates,key=lambda entry:pygame.Vector2(position).distance_to(log_point(ship_map,entry))) if candidates else None

    def discover(self,entry):
        self.found.add(entry.key);self.selected=entry.key;self.open=True

    def turn(self,direction):
        entries=self.entries
        if entries:
            index=next((i for i,entry in enumerate(entries) if entry.key==self.selected),0)
            self.selected=entries[(index+direction)%len(entries)].key
