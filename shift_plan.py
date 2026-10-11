"""Seeded incidents: a different campaign, a reproducible saved shift."""
import random
import secrets

PLAN_VERSION=1
AUXILIARY=('Oxygen','Communications','Navigation','Storage','Cargo Bay','Airlock')
INCIDENTS=(
    ('bus','Dağıtım arızası','Distribution fault',
     'Önce gücü kararlı hale getir; ardından soğutmayı ve reaktörü devreye al.',
     'Stabilize power first, then bring cooling and the reactor online.'),
    ('thermal','Soğutma kaçağı','Coolant leak',
     'Acil pompa çalışıyor. Önce soğutma hattını dengele, sonra güç dağıtımını düzelt.',
     'The emergency pump is running. Balance coolant flow before restoring distribution.'),
    ('fuel','Yakıt hattı tıkanıklığı','Fuel-line blockage',
     'Depodaki besleme hattını aç. Güç ve soğutma kontrolleri yakıttan sonra yapılabilir.',
     'Restore the storage feed line before servicing power and cooling.'),
    ('pressure','Basınç kaybı','Pressure loss',
     'Oksijen sistemini ve hava kilidini istediğin sırayla onar. Güç testi için ikisi de hazır olmalı.',
     'Service oxygen and the airlock in either order. Both must be ready for the power test.'),
    ('telemetry','Telemetri kesintisi','Telemetry failure',
     'Önce iletişim hattını kur. Ardından navigasyon ve güç işlerini istediğin sırayla yap.',
     'Restore communications first. Navigation and power can then be serviced separately.'),
    ('cargo','Kargo hattı hasarı','Cargo-line damage',
     'Yerinden çıkan yükü sabitle. Soğutma ve güç hatlarına sonra erişebilirsin.',
     'Secure the shifted cargo before accessing the coolant and power lines.'),
)

RECIPES={
 'Power':(('inspect','wires','calibrate'),('rewire','inspect'),('repair','calibrate'),('wires','rewire','inspect')),
 'Cooling':(('inspect','valves','calibrate'),('valves','repair','inspect'),('repair','valves'),('calibrate','inspect','valves')),
 'Reactor':(('inspect','sequence'),('repair','calibrate','sequence'),('calibrate','sequence'),('inspect','repair','sequence')),
 'Oxygen':(('inspect','filter','valves'),('filter','calibrate'),('valves','repair','inspect'),('filter','valves','calibrate')),
 'Communications':(('wires','signal'),('inspect','rewire','signal'),('repair','signal'),('signal','calibrate','inspect')),
 'Navigation':(('calibrate','course'),('inspect','course'),('repair','calibrate','course'),('signal','course','inspect')),
 'Storage':(('fuel','inspect'),('repair','fuel'),('valves','fuel','inspect'),('inspect','repair','fuel')),
 'Cargo Bay':(('cargo','repair'),('inspect','cargo'),('repair','cargo','inspect'),('cargo','calibrate','inspect')),
 'Airlock':(('repair','inspect'),('inspect','valves','repair'),('valves','calibrate','inspect'),('repair','calibrate')),
}


def new_campaign_seed(previous=None):
    # A fresh retry must not start with the incident that just killed the player.
    while True:
        seed=secrets.randbits(63) or 1
        if previous is None or seed%len(INCIDENTS)!=previous%len(INCIDENTS):return seed


def incident_for(seed,day):
    order=list(range(len(INCIDENTS)))
    random.Random(seed ^ 0x73591).shuffle(order)
    first=seed%len(INCIDENTS);order.remove(first);order.insert(0,first)
    return INCIDENTS[order[(day-1)%len(order)]]


def make_plan(seed,day):
    incident=incident_for(seed,day)
    rng=random.Random(seed+day*104729)
    extras=rng.sample(AUXILIARY,len(AUXILIARY))
    key=incident[0]
    if key=='bus':
        names=['Power','Cooling','Reactor',*extras[:2]]
        requires=[(),('Power',),('Cooling',),('Reactor',),('Reactor',)]
    elif key=='thermal':
        names=['Cooling','Power','Reactor',*extras[:2]]
        requires=[(),('Cooling',),('Cooling','Power'),('Power',),('Reactor',)]
    elif key=='fuel':
        names=['Storage','Power','Cooling','Reactor',next(n for n in extras if n!='Storage')]
        requires=[(),('Storage',),('Power',),('Cooling',),('Power',)]
    elif key=='pressure':
        names=['Oxygen','Airlock','Power','Cooling','Reactor']
        requires=[(),(),('Oxygen','Airlock'),('Power',),('Cooling',)]
    elif key=='telemetry':
        names=['Communications','Power','Navigation','Cooling','Reactor']
        requires=[(),('Communications',),('Communications',),('Power',),('Cooling',)]
    else:
        names=['Cargo Bay','Cooling','Power','Reactor',next(n for n in extras if n!='Cargo Bay')]
        requires=[(),('Cargo Bay',),('Cargo Bay',),('Cooling','Power'),('Reactor',)]
    result=[]
    for name,parents in zip(names,requires):
        variants=RECIPES[name]
        salt=sum((i+1)*ord(c) for i,c in enumerate(name))
        start=random.Random(seed+salt*7919).randrange(len(variants))
        operations=variants[(start+day-1)%len(variants)]
        result.append((name,operations,parents))
    return incident,result
