"""Live panel work: diagnosis, safe repair, calibration and circuit correction."""
import random

KINDS = {"inspect":"Kontrol", "repair":"Onarım", "calibrate":"Kalibrasyon", "rewire":"Devre düzeltme",
         "filter":"Filtre temizliği", "wires":"Kablo bağlantısı", "sequence":"Başlatma sırası",
         "signal":"Sinyal ayarı", "valves":"Vana ayarı", "course":"Rota hizalama",
         "cargo":"Yük sabitleme", "fuel":"Yakıt transferi"}
ROOM_WORK = {"Oxygen":("filter","inspect"), "Reactor":("sequence","repair"),
             "Power":("wires","rewire"), "Communications":("signal",),
             "Cooling":("valves","calibrate"), "Navigation":("course",),
             "Cargo Bay":("cargo",), "Storage":("fuel",), "Airlock":("repair",)}
ESCAPE_WORK = {"Power":"rewire", "Navigation":"course", "Hangar":"repair"}


DAILY_AUXILIARY={1:("Oxygen","Communications"),2:("Storage","Navigation"),
                 3:("Cargo Bay","Airlock"),4:("Oxygen","Navigation"),
                 5:("Storage","Communications"),6:("Cargo Bay","Airlock"),
                 7:("Oxygen","Communications")}
RECIPES={
    "Power":(("inspect","wires","calibrate"),("inspect","rewire","calibrate")),
    "Cooling":(("inspect","valves","calibrate"),("valves","repair","calibrate")),
    "Reactor":(("inspect","sequence"),("repair","sequence")),
    "Oxygen":(("inspect","filter","calibrate"),("filter","inspect","valves")),
    "Communications":(("wires","signal"),("rewire","signal")),
    "Navigation":(("calibrate","course"),("inspect","course")),
    "Storage":(("fuel","inspect"),("repair","fuel")),
    "Cargo Bay":(("cargo","repair"),("inspect","cargo")),
    "Airlock":(("repair","inspect"),("inspect","repair"))}
DEPENDENCIES={"Power":(),"Cooling":("Power",),"Reactor":("Power","Cooling")}


def active_rooms(day):
    return ("Power","Cooling","Reactor")+DAILY_AUXILIARY[max(1,min(7,day))]


def recipe_for_day(day,name):
    variants=RECIPES.get(name,((work_for_day(day,name),),))
    return variants[(max(1,day)-1)%len(variants)]


def prerequisites(name):return DEPENDENCIES.get(name,("Reactor",))


def work_for_day(day, name=None):
    if day==8:return ESCAPE_WORK.get(name,"rewire")
    choices=ROOM_WORK.get(name,("inspect",))
    return choices[(max(1,min(7,day))-1)%len(choices)]


def job_title(name,kind):
    if name=="Airlock" and kind=='repair':return "Kapak contası"
    if name=="Hangar" and kind=='repair':return "Kapsül kilidi"
    return KINDS[kind]


def repair_steps(name):
    if name=='Airlock':
        return ('1: Dış kapağı kilitle.', 'SPACE: Contayı taralı alanda sabitle.', '3: Sızdırmazlık testini çalıştır.')
    if name=='Hangar':
        return ('1: Emniyet mandalını aç.', 'SPACE: Kapsül kilidini taralı alanda hizala.', '3: Ayrılma düzeneğini hazırla.')
    return ('1: Önce devrenin gücünü kes.', 'SPACE: İbre taralı alandayken bağlantıyı kur.', '3: Gücü geri ver ve işlemi bitir.')


class PanelWork:
    """Input changes actual state. Updating time alone never completes a job."""
    def __init__(self, name, kind, day, revision=0, campaign_seed=0):
        self.name=name
        self.kind=kind
        seed=day*1009+revision*7919+sum((i+1)*ord(c) for i,c in enumerate(name))
        if campaign_seed:
            seed ^= campaign_seed*65537+sum((i+1)*ord(c) for i,c in enumerate(kind))*104729
        rng=random.Random(seed)
        self.readings=[rng.randint(44,56) for _ in range(3)]
        self.fault=rng.randrange(3)
        self.readings[self.fault]=rng.choice([rng.randint(12,30),rng.randint(72,89)])
        self.stage=0
        self.cursor=rng.uniform(.05,.25)
        self.target=rng.uniform(.44,.68)
        self.tolerance=.10
        self.bits=[rng.randrange(2) for _ in range(3)]
        self.goal=[rng.randrange(2) for _ in range(3)]
        if self.bits==self.goal:self.bits[0]=1-self.bits[0]
        self.debris_count=5+(day+revision)%4
        self.debris=set(rng.sample(range(12),self.debris_count))
        self.wire_goal=list(range(3));rng.shuffle(self.wire_goal)
        self.connected=set()
        self.selected=None
        self.dragging=None
        self.pointer_pos=None
        self.pattern=[rng.randrange(3) for _ in range(4+(day+revision)%3)]
        self.sequence_index=0
        self.sequence_timer=len(self.pattern)*.65+.35
        self.valves=[rng.randrange(3) for _ in range(3)]
        self.valve_goal=[rng.randint(4,8) for _ in range(3)]
        self.course=[.12,.85]
        self.course_goal=[rng.uniform(.45,.85),rng.uniform(.15,.6)]
        self.crates=[0,1,2,rng.randrange(3)];rng.shuffle(self.crates)
        self.delivered=set()
        self.pumping=False
        self.fuel=0.0
        if kind=='signal':self.tolerance=.035
        if kind=='fuel':self.tolerance=.07
        self.complete=False
        self.message=""
        self.message_timer=0
        self.noise_timer=0

    @property
    def progress(self):
        if self.complete:return 1.0
        if self.kind=="repair":return self.stage/3
        if self.kind=="rewire":return sum(a==b for a,b in zip(self.bits,self.goal))/3
        if self.kind=='filter':return (self.debris_count-len(self.debris))/self.debris_count
        if self.kind=='wires':return len(self.connected)/3
        if self.kind=='sequence':return self.sequence_index/len(self.pattern)
        if self.kind=='cargo':return len(self.delivered)/len(self.crates)
        if self.kind=='valves':return sum(a==b for a,b in zip(self.valves,self.valve_goal))/3
        if self.kind=='fuel':return min(1,self.fuel/self.target)
        return 0.0

    @property
    def noise(self):
        if self.kind=="repair":return (280,24) if self.stage==1 else (70,4)
        if self.kind=='fuel' and not self.pumping:return (70,3)
        return {"inspect":(55,2), "calibrate":(100,6), "rewire":(165,12),
                "filter":(95,5), "wires":(120,8), "sequence":(200,14), "signal":(70,4),
                "valves":(180,12), "course":(55,2), "cargo":(240,18), "fuel":(220,16)}[self.kind]

    def update(self,dt,keys):
        self.message_timer=max(0,self.message_timer-dt)
        if self.kind=="repair" and self.stage==1:
            self.cursor=(self.cursor+dt*.48)%1
        elif self.kind in ("calibrate","signal"):
            direction=int(bool(keys.get('right')))-int(bool(keys.get('left')))
            self.cursor=max(0,min(1,self.cursor+direction*dt*.3))

        elif self.kind=='sequence':
            self.sequence_timer=max(0,self.sequence_timer-dt)
        elif self.kind=='course':
            self.course[0]=max(0,min(1,self.course[0]+(bool(keys.get('right'))-bool(keys.get('left')))*dt*.3))
            self.course[1]=max(0,min(1,self.course[1]+(bool(keys.get('down'))-bool(keys.get('up')))*dt*.3))
        elif self.kind=='fuel' and self.pumping:
            self.fuel=min(1,self.fuel+dt*.22)

    def act(self,action,index=None):
        if self.complete:return 'ignored'
        if action=='clean' and self.kind=='filter':
            if index not in self.debris:return 'ignored'
            self.debris.remove(index)
            if not self.debris:self.complete=True
        elif action=='wire_start' and self.kind=='wires':
            if index not in range(3) or index in self.connected:return 'ignored'
            self.selected=index;self.dragging='wire'
            return 'progress'
        elif action=='wire_end' and self.kind=='wires':
            self.dragging=None
            source=self.selected;self.selected=None
            if source is None or index is None:return 'ignored'
            if self.wire_goal[source]!=index:return self._wrong('Yanlış giriş. Kabloyu aynı harfli yuvaya bağla.')
            self.connected.add(source)
            if len(self.connected)==3:self.complete=True
        elif action=='tune' and self.kind=='signal':
            self.cursor=max(0,min(1,index));return 'progress'
        elif action=='course' and self.kind=='course':
            self.course=[max(0,min(1,v)) for v in index];return 'progress'
        elif action=='crate_start' and self.kind=='cargo':
            if index not in range(4) or index in self.delivered:return 'ignored'
            self.selected=index;self.dragging='crate';return 'progress'
        elif action=='crate_end' and self.kind=='cargo':
            self.dragging=None
            source=self.selected;self.selected=None
            if source is None or index is None:return 'ignored'
            if self.crates[source]!=index:return self._wrong('Yanlış bölme. Kasayı aynı harfli yuvaya yerleştir.')
            self.delivered.add(source)
            if len(self.delivered)==4:self.complete=True
        else:return 'ignored'
        return 'complete' if self.complete else 'progress'

    def _wrong(self,message):
        self.message=message
        self.message_timer=2.0
        return "wrong"

    def press(self,key):
        if self.complete:return "ignored"
        if self.kind=='sequence':
            if key not in ('1','2','3') or self.sequence_timer>0:return 'ignored'
            if int(key)-1!=self.pattern[self.sequence_index]:
                self.sequence_index=0;self.sequence_timer=len(self.pattern)*.65+.35
                return self._wrong('Sıra bozuldu. Yanıp sönen düğmeleri yeniden izle.')
            self.sequence_index+=1
            if self.sequence_index==len(self.pattern):self.complete=True
            return 'complete' if self.complete else 'progress'
        if self.kind=='valves':
            if key in ('1','2','3'):
                i=int(key)-1;self.valves[i]=(self.valves[i]+1)%10;return 'progress'
            if key!='space':return 'ignored'
            if self.valves!=self.valve_goal:return self._wrong('Akışlar hedefte değil. Her vanayı ayrı ayarla.')
            self.complete=True;return 'complete'
        if self.kind=='signal':
            if key!='space':return 'ignored'
            if abs(self.cursor-self.target)>self.tolerance:return self._wrong('Sinyal zayıf. Frekansı tepe noktasına getir.')
            self.complete=True;return 'complete'
        if self.kind=='course':
            if key!='space':return 'ignored'
            if sum((a-b)**2 for a,b in zip(self.course,self.course_goal))>.045**2:
                return self._wrong('Rota hizalı değil. Nişangâhı hedef halkasına getir.')
            self.complete=True;return 'complete'
        if self.kind=='fuel':
            if key!='space':return 'ignored'
            if not self.pumping:self.pumping=True;return 'progress'
            self.pumping=False
            if abs(self.fuel-self.target)>self.tolerance:
                self.fuel=0;return self._wrong('Seviye hedefte değil. Transferi taralı alanda durdur.')
            self.complete=True;return 'complete'
        if self.kind in ('filter','wires','cargo'):return 'ignored'
        if self.kind=="inspect":
            if key not in ("1","2","3"):return "ignored"
            if int(key)-1!=self.fault:return self._wrong("Bu kanal normal. Sınırların dışındaki değeri bul.")
            self.complete=True
        elif self.kind=="repair":
            if self.stage==0:
                if key!="1":return self._wrong(repair_steps(self.name)[0])
                self.stage=1;return "progress"
            elif self.stage==1:
                if key!="space":return "ignored"
                if abs(self.cursor-self.target)>self.tolerance:return self._wrong(repair_steps(self.name)[1])
                self.stage=2;return "progress"
            else:
                if key!="3":return "ignored"
                self.complete=True
        elif self.kind=="calibrate":
            if key!="space":return "ignored"
            if abs(self.cursor-self.target)>self.tolerance:return self._wrong("Değer hedefin dışında. Oklarla ayarla.")
            self.complete=True
        elif self.kind=="rewire":
            if key in ("1","2","3"):
                i=int(key)-1;self.bits[i]=1-self.bits[i]
                return "progress"
            if key!="space":return "ignored"
            if self.bits!=self.goal:return self._wrong("Devre eşleşmiyor. 1 / 2 / 3 anahtarlarını değiştir.")
            self.complete=True
        return "complete"
