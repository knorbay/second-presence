"""Versioned local JSON saves. No executable objects or pickle data."""
import collections
import json
import math
import os
import sys
from pathlib import Path
import pygame
from maintenance import PanelWork, KINDS
from shift_plan import PLAN_VERSION
from crew_logs import LOGS

DEFAULT_SETTINGS={'language':'tr','volume':1.0,'brightness':1.0}
ALIEN_FIELDS=('facing_angle','state','last_seen_position','last_heard_position','last_seen_time',
 'suspicion','current_target','search_area','_search_index','_step_noise_timer','_suspicious_timer',
 '_search_timer','_waypoint_pause','_los_grace_timer','observed_hiding_spot','inspect_spot',
 'last_seen_direction','last_seen_velocity','_investigate_timer','_previous_seen_pos',
 '_previous_seen_time','_recent_patrol','intent','_patrol_pause','_search_origin','_heard_recently',
 'motion_clock','stride_offset','gait_scale')
COUNTERS=('first_task_counts','room_visit_counts','route_counts','hiding_counts',
 'escape_direction_counts','_pending_routes','_pending_hiding','_pending_escape')


def encode(value):
    if isinstance(value,pygame.Vector2):return list(value)
    if isinstance(value,set):return sorted(value)
    if isinstance(value,(tuple,list)):return [encode(v) for v in value]
    if isinstance(value,dict):return {str(k):encode(v) for k,v in value.items()}
    return value


def numeric(value,low,high):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and low<=value<=high


def vector(value):return isinstance(value,list) and len(value)==2 and all(numeric(v,-10000,10000) for v in value)


def safe_tree(value,depth=0):
    if depth>12:raise ValueError('Save nesting is invalid')
    if isinstance(value,float) and not math.isfinite(value):raise ValueError('Non-finite value')
    if isinstance(value,(list,dict)):
        if len(value)>10000:raise ValueError('Save collection is too large')
        for child in (value.values() if isinstance(value,dict) else value):safe_tree(child,depth+1)
    elif not isinstance(value,(str,int,float,bool,type(None))):raise ValueError('Invalid value')
    elif isinstance(value,str) and len(value)>4000:raise ValueError('Invalid text')


def restore_fields(obj,data,fields):
    """Accept only the types produced by the explicit template fields."""
    for key in fields:
        if key not in data or not hasattr(obj,key):continue
        old=getattr(obj,key);value=data[key]
        if isinstance(old,pygame.Vector2):
            if vector(value):setattr(obj,key,pygame.Vector2(value))
        elif isinstance(old,set):
            if isinstance(value,list) and all(isinstance(v,(str,int)) for v in value):setattr(obj,key,set(value))
        elif isinstance(old,bool):
            if isinstance(value,bool):setattr(obj,key,value)
        elif isinstance(old,(int,float)):
            if numeric(value,-1000000,1000000):setattr(obj,key,type(old)(value))
        elif isinstance(old,list):
            if isinstance(value,list):setattr(obj,key,value)
        elif isinstance(old,str):
            if isinstance(value,str):setattr(obj,key,value)
        elif old is None:
            if value is None or isinstance(value,str):setattr(obj,key,value)
            elif vector(value):setattr(obj,key,pygame.Vector2(value))


def default_storage_root():
    # A .app can live in a read-only disk image. Never write inside its bundle.
    if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
        return Path.home()/'Library'/'Application Support'/'Second Presence'
    return Path(__file__).resolve().parent/'.user_data'


class SaveStore:
    def __init__(self,root=None):
        self.root=Path(root) if root is not None else default_storage_root()
        self.path=self.root/'save.json'
        self.settings_path=self.root/'settings.json'

    def _read(self,path):
        if path.stat().st_size>1500000:raise ValueError('Save is too large')
        data=json.loads(path.read_text(encoding='utf-8'));safe_tree(data)
        if not isinstance(data,dict):raise ValueError('Invalid document')
        return data

    def _write(self,path,data):
        self.root.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.tmp')
        with temporary.open('w',encoding='utf-8') as stream:
            json.dump(data,stream,ensure_ascii=False,allow_nan=False,separators=(',',':'))
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)

    def settings(self):
        result=DEFAULT_SETTINGS.copy()
        try:data=self._read(self.settings_path)
        except (OSError,ValueError,RecursionError):return result
        if data.get('language') in ('tr','en'):result['language']=data['language']
        for key,limits in (('volume',(0,1)),('brightness',(.6,1.6))):
            if numeric(data.get(key),*limits):result[key]=data[key]
        return result

    def save_settings(self,settings):self._write(self.settings_path,settings)

    def read(self):
        data=self._read(self.path)
        if data.get('schema')!=1 or data.get('phase') not in ('PLAYING','DAY_TRANSITION'):raise ValueError('Unsupported save')
        if not isinstance(data.get('day'),int) or not 1<=data['day']<=8:raise ValueError('Invalid day')
        for key,limits in (('day_time',(0,10000)),('sim_time',(0,1000000)),('integrity',(0,100))):
            if not numeric(data.get(key),*limits):raise ValueError('Invalid '+key)
        if not isinstance(data.get('player'),dict) or not vector(data['player'].get('pos')):raise ValueError('Invalid player')
        if not isinstance(data.get('alien'),dict) or not vector(data['alien'].get('pos')):raise ValueError('Invalid hunter')
        player=data['player'];alien=data['alien']
        if not vector(player.get('facing')) or not numeric(player.get('stamina'),0,100):raise ValueError('Invalid player state')
        states=('DORMANT','WANDER','SUSPICIOUS','INVESTIGATE','CHASE','SEARCH_LAST_SEEN','SEARCH_AREA')
        if alien.get('state') not in states:raise ValueError('Invalid hunter state')
        for key in ('last_seen_position','last_heard_position','current_target','_previous_seen_pos','_search_origin'):
            if alien.get(key) is not None and not vector(alien[key]):raise ValueError('Invalid hunter memory')
        if not isinstance(alien.get('search_area'),list) or not all(vector(v) for v in alien['search_area']):raise ValueError('Invalid search')
        for key in ('decoy_charges','day8_step'):
            if not numeric(data.get(key),0,3):raise ValueError('Invalid '+key)
        if not isinstance(data.get('tracker'),dict):raise ValueError('Invalid learning')
        if not isinstance(data.get('decoys'),list) or not isinstance(data.get('logs'),list):raise ValueError('Invalid equipment')
        if not isinstance(data.get('tasks'),dict) or not isinstance(data.get('doors'),list):raise ValueError('Invalid ship')
        seed=data.get('campaign_seed',0)
        if type(seed) is not int or not 0<=seed<2**63:raise ValueError('Invalid campaign seed')
        if data.get('plan_version',0) not in (0,PLAN_VERSION):raise ValueError('Unsupported maintenance plan')
        for record in data['doors']:
            if not isinstance(record,dict) or not isinstance(record.get('name'),str) or not numeric(record.get('damage'),0,10):raise ValueError('Invalid bulkhead')
        for record in data['tasks'].values():
            if not isinstance(record,dict) or not numeric(record.get('step'),0,3) or not numeric(record.get('revision'),0,10000):raise ValueError('Invalid task')
            if 'operations' in record:
                if not isinstance(record['operations'],list) or not 2<=len(record['operations'])<=3 or not all(kind in KINDS for kind in record['operations']):raise ValueError('Invalid task recipe')
                if not isinstance(record.get('requires'),list) or not all(name in data['tasks'] for name in record['requires']):raise ValueError('Invalid prerequisites')
            for session in record.get('sessions',[]):
                if not isinstance(session,dict) or session.get('kind') not in KINDS or not isinstance(session.get('fields'),dict):raise ValueError('Invalid panel')
                fields=session['fields']
                for name,length in (('bits',3),('valves',3),('course',2)):
                    if name in fields and (not isinstance(fields[name],list) or len(fields[name])!=length):raise ValueError('Invalid instrument length')
                for name,limit in (('debris',11),('connected',2),('delivered',3)):
                    if name in fields and (not isinstance(fields[name],list) or not all(isinstance(v,int) and 0<=v<=limit for v in fields[name])):raise ValueError('Invalid progress')
                for name in ('readings','bits','goal','wire_goal','pattern','valves','valve_goal','crates'):
                    if name in fields and (not isinstance(fields[name],list) or not all(numeric(v,0,100) for v in fields[name])):raise ValueError('Invalid instrument')
                for name in ('course','course_goal'):
                    if name in fields and not vector(fields[name]):raise ValueError('Invalid course')
        return data

    def summary(self):
        try:
            data=self.read();return {'day':data['day'],'minutes':int(data['day_time']//60)}
        except (OSError,ValueError,TypeError,KeyError,RecursionError):return None

    def snapshot(self,g):
        tasks={}
        for name,task in g.tasks.tasks.items():
            sessions=[{'step':key[0],'revision':key[1],'kind':work.kind,'fields':encode(vars(work))} for key,work in task.sessions.items()]
            tasks[name]={'operations':list(task.operations),'requires':list(task.requires),'step':task.step,'revision':task.revision,'done':task.done,'completed_at':task.completed_at,'sessions':sessions}
        tracker={name:[[encode(k),v] for k,v in getattr(g.tracker,name).items()] for name in COUNTERS}
        tracker.update({name:encode(getattr(g.tracker,name)) for name in ('task_order_history','sprint_count','_last_room_this_day','_visited_rooms_this_day')})
        alien={'pos':list(g.alien.pos),**{key:encode(getattr(g.alien,key)) for key in ALIEN_FIELDS}}
        for key in ('_wander_target_room','_last_confirmed_room','_chase_start_room'):
            value=getattr(g.alien,key);alien[key]=value.name if hasattr(value,'name') else value
        return {'schema':1,'phase':g.phase,'day':g.day,'day_time':g.day_time,'sim_time':g.sim_time,'integrity':g.integrity,
            'campaign_seed':g.tasks.campaign_seed,'plan_version':g.tasks.plan_version,
            'player':{'pos':list(g.player.pos),'facing':list(g.player.facing),'stamina':g.player.stamina,
                      'hidden':g.player.hidden,'locker':g.player.hidden_spot},
            'alien':alien,'tasks':tasks,'day8_step':g.tasks.day8_step,'order':g.tasks.first_completion_order,
            'tracker':tracker,'logs':list(g.logbook.found),'decoy_charges':g.decoy_charges,
            'decoys':[{**d,'point':list(d['point'])} for d in g.decoys],
            'sabotage_cooldown':g.sabotage_cooldown,'last_day_summary':g.last_day_summary,
            'escape_panel':encode(vars(g.panel_work)) if g.day==8 and g.panel_work else None,
            'alarms':[{'room':a.room.name,'real':a.real,'timer':a.timer} for a in g.alarms],
            'doors':[{'name':d.name,'closed':d.closed,'broken':d.broken,'damage':d.damage} for d in g.ship_map.doors.doors]}

    def save(self,g):
        if g.phase not in ('PLAYING','DAY_TRANSITION'):return False
        self._write(self.path,self.snapshot(g));return True

    def load(self,g,data=None):
        data=self.read() if data is None else data
        # Restore the campaign before rebuilding goals. Loading must not autosave
        # a half-restored day over the file the player is trying to continue.
        g.tasks.campaign_seed=data.get('campaign_seed',0)
        g.tasks.plan_version=data.get('plan_version',0)
        g.day=data['day'];autosave=g._autosave_enabled;g._autosave_enabled=False
        try:g._start_day()
        finally:g._autosave_enabled=autosave
        g.phase=data['phase']
        g.day_time=data['day_time'];g.sim_time=data['sim_time'];g.integrity=data['integrity']
        for record in data['doors']:
            door=next((d for d in g.ship_map.doors.doors if d.name==record.get('name')),None)
            if door:
                door.broken=bool(record.get('broken'))
                door.damage=max(0,min(10,record.get('damage',0)))
                g.ship_map.doors._set_closed(door,bool(record.get('closed')) and not door.broken)
                door.visual=float(door.closed)
        for name,record in data['tasks'].items():
            if name not in g.tasks.tasks:continue
            task=g.tasks.tasks[name];task.revision=int(record['revision']);task.step=int(record['step'])
            if 'operations' in record:
                task.operations=tuple(record['operations']);task.requires=tuple(record['requires'])
            task.done=task.step>=len(task.operations);task.completed_at=record.get('completed_at') if task.done else None
            if task.done and not numeric(task.completed_at,0,10000):task.completed_at=g.day_time
            for session in record.get('sessions',[]):
                step=session.get('step',0);revision=session.get('revision',0)
                if not isinstance(step,int) or not 0<=step<len(task.operations) or revision!=task.revision:continue
                kind=task.operations[step]
                if session['kind']!=kind:continue
                work=g.tasks.panel(name,kind,revision*31+step)
                # Fixed generated goals stay deterministic; only interaction state is restored.
                fields=('stage','cursor','bits','debris','connected','sequence_index','sequence_timer',
                        'valves','course','delivered','fuel','complete')
                restore_fields(work,session['fields'],fields)
                work.stage=max(0,min(2,work.stage));work.cursor=max(0,min(1,work.cursor))
                work.debris&=set(range(12));work.connected&=set(range(3));work.delivered&=set(range(4))
                task.sessions[(step,revision)]=work
        g.tasks.first_completion_order=[n for n in data.get('order',[]) if n in g.tasks.tasks]
        g.tasks.day8_step=int(max(0,min(3,data.get('day8_step',0))))
        g.tasks.day8_complete=g.tasks.day8_step>=3
        player=data['player'];point=pygame.Vector2(player['pos'])
        if not g.ship_map.is_blocked_circle(*point,g.player.radius):g.player.pos=point
        if vector(player.get('facing')) and pygame.Vector2(player['facing']).length_squared()>0:g.player.facing=pygame.Vector2(player['facing']).normalize()
        g.player.stamina=max(0,min(100,player.get('stamina',100)))
        g.player.current_room=g.ship_map.room_at_world(*g.player.pos)
        if player.get('hidden') and player.get('locker') in g.lockers:
            g.player.hidden=True;g.player.hidden_spot=player['locker'];g.player.pos=g.lockers[g.player.hidden_spot].copy()
        alien=data['alien'];point=pygame.Vector2(alien['pos'])
        if not g.ship_map.is_blocked_circle(*point,9):g.alien.pos=point
        restore_fields(g.alien,alien,ALIEN_FIELDS)
        from systems import hunter_awake
        if not hunter_awake(g.day,g.day_time):
            g.alien.state='DORMANT';g.alien.moved_this_frame=False;g.alien.suspicion=0.0
        for key in ('last_seen_position','last_heard_position','current_target','_previous_seen_pos','_search_origin'):
            value=alien.get(key);setattr(g.alien,key,pygame.Vector2(value) if vector(value) else None)
        g.alien.search_area=[pygame.Vector2(v) for v in alien.get('search_area',[]) if vector(v)]
        g.alien._search_index=max(0,min(len(g.alien.search_area),g.alien._search_index))
        for key in ('_wander_target_room','_last_confirmed_room','_chase_start_room'):
            value=alien.get(key)
            # Stored room names are resolved against this day’s physical map.
            setattr(g.alien,key,next((r for r in g.ship_map.rooms if r.name==value),None))
        tracker=data.get('tracker',{})
        for name in COUNTERS:
            counter=collections.Counter()
            for entry in tracker.get(name,[]):
                if not isinstance(entry,list) or len(entry)!=2:continue
                key,count=entry
                if isinstance(key,list) and all(isinstance(v,str) for v in key):key=tuple(key)
                if isinstance(key,(str,tuple)) and numeric(count,0,1000000):counter[key]=int(count)
            setattr(g.tracker,name,counter)
        restore_fields(g.tracker,tracker,('task_order_history','sprint_count','_last_room_this_day','_visited_rooms_this_day'))
        g.logbook.found=set(data.get('logs',[]))&{entry.key for entry in LOGS}
        g.decoy_charges=int(max(0,min(3,data.get('decoy_charges',0))))
        g.decoys=[{**d,'point':pygame.Vector2(d['point'])} for d in data.get('decoys',[]) if isinstance(d,dict) and vector(d.get('point')) and numeric(d.get('timer'),0,10) and numeric(d.get('pulses'),0,100)]
        g.sabotage_cooldown=max(0,min(100,data.get('sabotage_cooldown',20)))
        g.last_day_summary=data.get('last_day_summary')
        if g.day==8 and isinstance(data.get('escape_panel'),dict):
            fields=data['escape_panel'];name=g.tasks.day8_current_target()
            from maintenance import work_for_day
            if name and fields.get('name')==name and fields.get('kind')==work_for_day(8,name):
                work=g.tasks.panel(name,work_for_day(8,name))
                restore_fields(work,fields,('stage','cursor','bits','course','complete'))
                g.panel_work=work
        from main import Alarm
        for record in data.get('alarms',[]):
            room=next((r for r in g.ship_map.rooms if r.name==record.get('room')),None)
            if room and numeric(record.get('timer'),0,100):g.alarms.append(Alarm(room,bool(record.get('real')),record['timer']))
        g.conditions.update(100,g.day_time,g.serviced_systems().get('Power',False))
        g.camera=g.camera_target();g.presentation.refresh()
        g.paused=False;g.audio.pause(False)
        g._autosave_enabled=True
