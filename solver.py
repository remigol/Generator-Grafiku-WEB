import calendar,datetime,numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import lil_matrix
PEOPLE=list('ABCDEFGHI');PROD=set('ABCDEF');PACK=set('GHI')
def holidays(year):
 a=year%19;b=year//100;c=year%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3
 h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32+2*e+2*i-h-k)%7;m=(a+11*h+22*l)//451
 month=(h+l-7*m+114)//31;day=(h+l-7*m+114)%31+1
 easter=datetime.date(year,month,day)
 fixed=[(1,1),(1,6),(5,1),(5,3),(8,15),(11,1),(11,11),(12,24),(12,25),(12,26)]
 return {datetime.date(year,mo,da) for mo,da in fixed}|{easter+datetime.timedelta(days=x) for x in (1,60)}
def build_days(year,month,closed):
 hol=holidays(year);days=[]
 for d in range(1,calendar.monthrange(year,month)[1]+1):
  dt=datetime.date(year,month,d)
  typ='closed' if dt.weekday()==6 or dt in hol or d in closed else ('sat' if dt.weekday()==5 else 'weekday')
  days.append({'day':d,'weekday':dt.weekday(),'type':typ})
 return days
def solve(payload):
 year=int(payload['year']);month=int(payload['month']);nominal=int(payload.get('nominal',176))
 locks=payload.get('locks',{});days=build_days(year,month,set(map(int,payload.get('closed',[]))))
 D=len(days);N=9*D*2;rows=[];lo=[];hi=[]
 def idx(p,d,s):return (p*D+d)*2+s
 def add(terms,low=-np.inf,high=np.inf):rows.append(terms);lo.append(low);hi.append(high)
 for p in range(9):
  for d,day in enumerate(days):
   add([(idx(p,d,0),1),(idx(p,d,1),1)],high=1)
   if day['type']=='closed':add([(idx(p,d,s),1) for s in range(2)],high=0)
   if day['type']=='sat':add([(idx(p,d,1),1)],high=0)
   val=locks.get(f'{PEOPLE[p]}-{d+1}')
   if val in ('6','18','W'):
    if val=='W':add([(idx(p,d,s),1) for s in range(2)],high=0)
    else:add([(idx(p,d,0 if val=='6' else 1),1)],low=1)
  for d in range(D-4):add([(idx(p,t,s),1) for t in range(d,d+5) for s in range(2)],high=4)
  for d in range(D-2):
   add([(idx(p,d,s),1) for s in range(2)]+[(idx(p,d+1,s),-1) for s in range(2)]+[(idx(p,d+2,s),1) for s in range(2)],high=1)
  for d in range(D-1):
   add([(idx(p,d,0),1),(idx(p,d+1,1),1)],high=1)
   add([(idx(p,d,1),1),(idx(p,d+1,0),1)],high=1)
  add([(idx(p,d,s),1) for d in range(D) for s in range(2)],high=max(1,(nominal+24)//12))
  if PEOPLE[p]=='E':
   for d in range(D-3):add([(idx(p,t,1),1) for t in range(d,d+4)],high=3)
   for d in range(min(2,D)):add([(idx(p,d,0),1)],high=0)
 for d,day in enumerate(days):
  if day['type']=='closed':continue
  for s in ([0] if day['type']=='sat' else [0,1]):
   add([(idx(p,d,s),1) for p in range(9)],low=2,high=2 if day['type']=='sat' else 3)
   add([(idx(p,d,s),1) for p in range(6)],low=1)
   add([(idx(p,d,s),1) for p in range(6,9)],high=2)
 A=lil_matrix((len(rows),N),dtype=float)
 for r,terms in enumerate(rows):
  for j,v in terms:A[r,j]+=v
 c=np.array([1+.01*p+.0001*d+(.004 if s else 0) for p in range(9) for d in range(D) for s in range(2)])
 res=milp(c,integrality=np.ones(N),bounds=Bounds(np.zeros(N),np.ones(N)),constraints=LinearConstraint(A.tocsr(),np.array(lo),np.array(hi)),options={'time_limit':25,'mip_rel_gap':.04})
 if res.x is None:return {'ok':False,'message':'Nie znaleziono grafiku spełniającego ograniczenia','days':days}
 sched={PEOPLE[p]:[('6' if res.x[idx(p,d,0)]>.5 else '18' if res.x[idx(p,d,1)]>.5 else '') for d in range(D)] for p in range(9)}
 return {'ok':True,'schedule':sched,'days':days,'message':'Grafik wygenerowany; sprawdź równowagę zmian i godziny.'}
def validate(payload):
 days=build_days(int(payload['year']),int(payload['month']),set(map(int,payload.get('closed',[]))))
 sched=payload['schedule'];issues=[]
 for p in PEOPLE:
  vals=sched.get(p,[])
  if len(vals)!=len(days):issues.append(f'{p}: niepełny grafik');continue
  for d,day in enumerate(days):
   if day['type']=='closed' and vals[d] in ('6','18'):issues.append(f'{p}, dzień {d+1}: praca w dniu zamkniętym')
   if day['type']=='sat' and vals[d]=='18':issues.append(f'{p}, dzień {d+1}: nocna zmiana w sobotę')
  for d in range(len(days)-4):
   if all(vals[t] in ('6','18') for t in range(d,d+5)):issues.append(f'{p}: ponad 4 dni pracy od {d+1}')
  for d in range(len(days)):
   if vals[d] not in ('6','18') or (d>0 and vals[d-1] in ('6','18')):continue
   run=0
   while d+run<len(days) and vals[d+run] in ('6','18'):run+=1
   if d+run+1<len(days) and any(vals[t] in ('6','18') for t in range(d+run,min(d+run+2,len(days)))):issues.append(f'{p}: brak 2 dni wolnych od {d+1}')
   if len({v for v in vals[d:d+run] if v in ('6','18')})>1:issues.append(f'{p}: mieszane zmiany w bloku od {d+1}')
 for d,day in enumerate(days):
  for shift in (['6'] if day['type']=='sat' else ['6','18'] if day['type']=='weekday' else []):
   workers=[p for p in PEOPLE if len(sched.get(p,[]))>d and sched[p][d]==shift]
   if len(workers)<2 or len(workers)>(2 if day['type']=='sat' else 3):issues.append(f'Dzień {d+1}, zmiana {shift}: nieprawidłowa obsada')
   if not set(workers)&PROD:issues.append(f'Dzień {d+1}, zmiana {shift}: brak produkcji')
   if len(set(workers)&PACK)>2:issues.append(f'Dzień {d+1}, zmiana {shift}: za dużo pakowania')
 return issues weekly=payload.get('weeklyShifts',{})
 for key,group in weekly.items():
  try:monday=datetime.date.fromisoformat(key)
  except ValueError:continue
  indices=[d for d in range(D) if monday<=datetime.date(year,month,d+1)<monday+datetime.timedelta(days=7)]
  for p in range(9):
   chosen=group.get(PEOPLE[p],'any')
   if chosen in ('6','18'):
    forbidden=1 if chosen=='6' else 0
    for d in indices:add([(idx(p,d,forbidden),1)],high=0)
 for d,day in enumerate(days):
   add([(idx(p,d,0),1),(idx(p,d,1),1)],high=1)
   if day['type']=='closed':add([(idx(p,d,s),1) for s in range(2)],high=0)
   if day['type']=='sat':add([(idx(p,d,1),1)],high=0)
   val=locks.get(f'{PEOPLE[p]}-{d+1}')
   if val in ('6','18','W'):
    if val=='W':add([(idx(p,d,s),1) for s in range(2)],high=0)
    else:add([(idx(p,d,0 if val=='6' else 1),1)],low=1)
  for d in range(D-4):add([(idx(p,t,s),1) for t in range(d,d+5) for s in range(2)],high=4)
  for d in range(D-2):
   add([(idx(p,d,s),1) for s in range(2)]+[(idx(p,d+1,s),-1) for s in range(2)]+[(idx(p,d+2,s),1) for s in range(2)],high=1)
  for d in range(D-1):
   add([(idx(p,d,0),1),(idx(p,d+1,1),1)],high=1)
   add([(idx(p,d,1),1),(idx(p,d+1,0),1)],high=1)
  add([(idx(p,d,s),1) for d in range(D) for s in range(2)],high=max(1,(nominal+24)//12))
  if PEOPLE[p]=='E':
   for d in range(D-3):add([(idx(p,t,1),1) for t in range(d,d+4)],high=3)
   for d in range(min(2,D)):add([(idx(p,d,0),1)],high=0)
 for d,day in enumerate(days):
  if day['type']=='closed':continue
  for s in ([0] if day['type']=='sat' else [0,1]):
   add([(idx(p,d,s),1) for p in range(9)],low=2,high=2 if day['type']=='sat' else 3)
   add([(idx(p,d,s),1) for p in range(6)],low=1)
   add([(idx(p,d,s),1) for p in range(6,9)],high=2)
 A=lil_matrix((len(rows),N),dtype=float)
 for r,terms in enumerate(rows):
  for j,v in terms:A[r,j]+=v
 c=np.array([1+.01*p+.0001*d+(.004 if s else 0) for p in range(9) for d in range(D) for s in range(2)])
 res=milp(c,integrality=np.ones(N),bounds=Bounds(np.zeros(N),np.ones(N)),constraints=LinearConstraint(A.tocsr(),np.array(lo),np.array(hi)),options={'time_limit':25,'mip_rel_gap':.04})
 if res.x is None:return {'ok':False,'message':'Nie znaleziono grafiku spełniającego ograniczenia','days':days}
 sched={PEOPLE[p]:[('6' if res.x[idx(p,d,0)]>.5 else '18' if res.x[idx(p,d,1)]>.5 else '') for d in range(D)] for p in range(9)}
 return {'ok':True,'schedule':sched,'days':days,'message':'Grafik wygenerowany; sprawdź równowagę zmian i godziny.'}
def validate(payload):
 days=build_days(int(payload['year']),int(payload['month']),set(map(int,payload.get('closed',[]))))
 sched=payload['schedule'];issues=[]
 for p in PEOPLE:
  vals=sched.get(p,[])
  if len(vals)!=len(days):issues.append(f'{p}: niepełny grafik');continue
  for d,day in enumerate(days):
   if day['type']=='closed' and vals[d] in ('6','18'):issues.append(f'{p}, dzień {d+1}: praca w dniu zamkniętym')
   if day['type']=='sat' and vals[d]=='18':issues.append(f'{p}, dzień {d+1}: nocna zmiana w sobotę')
  for d in range(len(days)-4):
   if all(vals[t] in ('6','18') for t in range(d,d+5)):issues.append(f'{p}: ponad 4 dni pracy od {d+1}')
  for d in range(len(days)):
   if vals[d] not in ('6','18') or (d>0 and vals[d-1] in ('6','18')):continue
   run=0
   while d+run<len(days) and vals[d+run] in ('6','18'):run+=1
   if d+run+1<len(days) and any(vals[t] in ('6','18') for t in range(d+run,min(d+run+2,len(days)))):issues.append(f'{p}: brak 2 dni wolnych od {d+1}')
   if len({v for v in vals[d:d+run] if v in ('6','18')})>1:issues.append(f'{p}: mieszane zmiany w bloku od {d+1}')
 for d,day in enumerate(days):
  for shift in (['6'] if day['type']=='sat' else ['6','18'] if day['type']=='weekday' else []):
   workers=[p for p in PEOPLE if len(sched.get(p,[]))>d and sched[p][d]==shift]
   if len(workers)<2 or len(workers)>(2 if day['type']=='sat' else 3):issues.append(f'Dzień {d+1}, zmiana {shift}: nieprawidłowa obsada')
   if not set(workers)&PROD:issues.append(f'Dzień {d+1}, zmiana {shift}: brak produkcji')
   if len(set(workers)&PACK)>2:issues.append(f'Dzień {d+1}, zmiana {shift}: za dużo pakowania')
 return issues for key,group in payload.get('weeklyShifts',{}).items():
  try:monday=datetime.date.fromisoformat(key)
  except ValueError:issues.append('Nieprawidłowy tydzień: '+key);continue
  indices=[d for d in range(len(days)) if monday<=datetime.date(int(payload['year']),int(payload['month']),d+1)<monday+datetime.timedelta(days=7)]
  for p in PEOPLE:
   chosen=group.get(p,'any')
   if chosen not in ('6','18'):continue
   for d in indices:
    if d<len(sched.get(p,[])) and sched[p][d] in ('6','18') and sched[p][d]!=chosen:
     issues.append(f'{p}, dzień {d+1}: zmiana {sched[p][d]} niezgodna z tygodniowym wyborem {chosen}')
 return issues weekly=payload.get('weeklyShifts',{})
 for key,group in weekly.items():
  try:monday=datetime.date.fromisoformat(key)
  except ValueError:continue
  indices=[d for d in range(D) if monday<=datetime.date(year,month,d+1)<monday+datetime.timedelta(days=7)]
  for p in range(9):
   chosen=group.get(PEOPLE[p],'any')
   if chosen in ('6','18'):
    forbidden=1 if chosen=='6' else 0
    for d in indices:add([(idx(p,d,forbidden),1)],high=0)
 for d,day in enumerate(days):
   add([(idx(p,d,0),1),(idx(p,d,1),1)],high=1)
   if day['type']=='closed':add([(idx(p,d,s),1) for s in range(2)],high=0)
   if day['type']=='sat':add([(idx(p,d,1),1)],high=0)
   val=locks.get(f'{PEOPLE[p]}-{d+1}')
   if val in ('6','18','W'):
    if val=='W':add([(idx(p,d,s),1) for s in range(2)],high=0)
    else:add([(idx(p,d,0 if val=='6' else 1),1)],low=1)
  for d in range(D-4):add([(idx(p,t,s),1) for t in range(d,d+5) for s in range(2)],high=4)
  for d in range(D-2):
   add([(idx(p,d,s),1) for s in range(2)]+[(idx(p,d+1,s),-1) for s in range(2)]+[(idx(p,d+2,s),1) for s in range(2)],high=1)
  for d in range(D-1):
   add([(idx(p,d,0),1),(idx(p,d+1,1),1)],high=1)
   add([(idx(p,d,1),1),(idx(p,d+1,0),1)],high=1)
  add([(idx(p,d,s),1) for d in range(D) for s in range(2)],high=max(1,(nominal+24)//12))
  if PEOPLE[p]=='E':
   for d in range(D-3):add([(idx(p,t,1),1) for t in range(d,d+4)],high=3)
   for d in range(min(2,D)):add([(idx(p,d,0),1)],high=0)
 for d,day in enumerate(days):
  if day['type']=='closed':continue
  for s in ([0] if day['type']=='sat' else [0,1]):
   add([(idx(p,d,s),1) for p in range(9)],low=2,high=2 if day['type']=='sat' else 3)
   add([(idx(p,d,s),1) for p in range(6)],low=1)
   add([(idx(p,d,s),1) for p in range(6,9)],high=2)
 A=lil_matrix((len(rows),N),dtype=float)
 for r,terms in enumerate(rows):
  for j,v in terms:A[r,j]+=v
 c=np.array([1+.01*p+.0001*d+(.004 if s else 0) for p in range(9) for d in range(D) for s in range(2)])
 res=milp(c,integrality=np.ones(N),bounds=Bounds(np.zeros(N),np.ones(N)),constraints=LinearConstraint(A.tocsr(),np.array(lo),np.array(hi)),options={'time_limit':25,'mip_rel_gap':.04})
 if res.x is None:return {'ok':False,'message':'Nie znaleziono grafiku spełniającego ograniczenia','days':days}
 sched={PEOPLE[p]:[('6' if res.x[idx(p,d,0)]>.5 else '18' if res.x[idx(p,d,1)]>.5 else '') for d in range(D)] for p in range(9)}
 return {'ok':True,'schedule':sched,'days':days,'message':'Grafik wygenerowany; sprawdź równowagę zmian i godziny.'}
def validate(payload):
 days=build_days(int(payload['year']),int(payload['month']),set(map(int,payload.get('closed',[]))))
 sched=payload['schedule'];issues=[]
 for p in PEOPLE:
  vals=sched.get(p,[])
  if len(vals)!=len(days):issues.append(f'{p}: niepełny grafik');continue
  for d,day in enumerate(days):
   if day['type']=='closed' and vals[d] in ('6','18'):issues.append(f'{p}, dzień {d+1}: praca w dniu zamkniętym')
   if day['type']=='sat' and vals[d]=='18':issues.append(f'{p}, dzień {d+1}: nocna zmiana w sobotę')
  for d in range(len(days)-4):
   if all(vals[t] in ('6','18') for t in range(d,d+5)):issues.append(f'{p}: ponad 4 dni pracy od {d+1}')
  for d in range(len(days)):
   if vals[d] not in ('6','18') or (d>0 and vals[d-1] in ('6','18')):continue
   run=0
   while d+run<len(days) and vals[d+run] in ('6','18'):run+=1
   if d+run+1<len(days) and any(vals[t] in ('6','18') for t in range(d+run,min(d+run+2,len(days)))):issues.append(f'{p}: brak 2 dni wolnych od {d+1}')
   if len({v for v in vals[d:d+run] if v in ('6','18')})>1:issues.append(f'{p}: mieszane zmiany w bloku od {d+1}')
 for d,day in enumerate(days):
  for shift in (['6'] if day['type']=='sat' else ['6','18'] if day['type']=='weekday' else []):
   workers=[p for p in PEOPLE if len(sched.get(p,[]))>d and sched[p][d]==shift]
   if len(workers)<2 or len(workers)>(2 if day['type']=='sat' else 3):issues.append(f'Dzień {d+1}, zmiana {shift}: nieprawidłowa obsada')
   if not set(workers)&PROD:issues.append(f'Dzień {d+1}, zmiana {shift}: brak produkcji')
   if len(set(workers)&PACK)>2:issues.append(f'Dzień {d+1}, zmiana {shift}: za dużo pakowania')
 return issues
