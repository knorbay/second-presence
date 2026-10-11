"""Daily ship conditions; the player has no health or survival meters."""
from dataclasses import dataclass
import config as C


@dataclass(frozen=True)
class DayConditions:
    title: str
    description: str
    blackout_duration: float
    blackout_interval: float
    leak_rooms: tuple
    capsules: int


DAYS = {
    1: DayConditions('Rutin', 'Genel aydınlatma açık. Gemiyi ve bakım sırasını öğren.', 0, 90, (), 3),
    2: DayConditions('Sesler', 'Işıklar kesilip geliyor. Havalandırmadan düzensiz sesler duyuluyor.', 8, 55, (), 3),
    3: DayConditions('Sızıntı', 'Genel aydınlatma devre dışı. Fenerini kullan. Bu kez koridorlarda bir şey dolaşıyor.', 5, 75, ('Cargo Bay',), 3),
    4: DayConditions('Kapanan yollar', 'Batı servis geçidi mühürlendi. Devre anahtarlarını yeniden düzenle.', 7, 65, ('Cargo Bay',), 2),
    5: DayConditions('Göstergeler', 'Navigasyonda da kaçak var. Arızalı göstergeleri kontrol et.', 9, 60, ('Cargo Bay','Navigation'), 2),
    6: DayConditions('Sessizlik', 'Doğu servis geçidi de kapandı. Bakımlar tekrar arızalanabilir.', 11, 55, ('Cargo Bay','Navigation'), 2),
    7: DayConditions('Sapma', 'Gösterge ayarları bozuldu. Avcı eski rotalarını arıyor.', 13, 50, ('Cargo Bay','Navigation','Reactor'), 1),
    8: DayConditions('Son gün', 'Güç, Navigasyon, Hangar. Sistemleri sırayla devreye al.', 14, 48, ('Cargo Bay','Navigation','Reactor'), 1),
}


def conditions_for(day):
    return DAYS[max(1,min(8,day))]


class ShipConditions:
    """Ship lighting only: no health, oxygen tank, fatigue or medicine."""
    def __init__(self):
        self.day=1
        self.blackout=False
        self.lamp_power=1.0
        self.ambient_strength=.78

    def start_day(self,day):
        self.day=day
        self.blackout=day>=3
        self.lamp_power=1.0
        self.ambient_strength=.78 if day==1 else .65 if day==2 else 0

    @property
    def view_radius(self):
        return int(C.PLAYER_VIEW_RADIUS+300*self.ambient_strength)

    def update(self,dt,day_time,power_restored=False):
        c=conditions_for(self.day)
        phase=(day_time+(36 if self.day==2 else 0))%c.blackout_interval
        self.blackout=bool(not power_restored and (self.day>=3 or
            (c.blackout_duration and phase>=c.blackout_interval-c.blackout_duration)))
        desired=.78 if self.day==1 else (.025 if self.blackout else .65) if self.day==2 else 0.0
        self.ambient_strength+=max(-dt*.9,min(dt*.9,desired-self.ambient_strength))
        # The crew torch is battery powered and independent of the ship grid.
        self.lamp_power=1.0
