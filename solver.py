import calendar,datetime,math,numpy as np
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
def block_days(year,month,days):
 # Święta ustawowe w dni pon.-sob. są neutralne dla ciągłości bloków.
 # Niedziele oraz ręcznie zamknięte dni pozostają dniami odpoczynku.
 # Niedziela NIE jest usuwana z osi bloków: zawsze rozdziela pracę.
 hol=holidays(year)
 return [i for i,day in enumerate(days) if not (day['type']=='closed' and datetime.date(year,month,i+1) in hol and day['weekday']!=6)]

def solve(payload, diagnostic=False, relax=None):
 relax=set(relax or [])
 year=int(payload['year']);month=int(payload['month']);nominal=int(payload.get('nominal',176))
 locks=payload.get('locks',{});days=build_days(year,month,set(map(int,payload.get('closed',[]))))
 D=len(days);N=9*D*2;rows=[];lo=[];hi=[]
 target=max(0,math.ceil(nominal/12))
 capacity=sum(2 if day['type']=='sat' else 6 if day['type']=='weekday' else 0 for day in days)
 if 9*target>capacity and 'quota' not in relax and 'fallback' not in relax:
  return {'ok':False,'message':f'Nominał wymaga dokładnie {9*target} zmian (po {target} na osobę), ale maksymalna obsada miesiąca pozwala na {capacity}. Zmniejsz nominał lub zmień zasady obsady.','days':days}
 # Wstepna kontrola liczby dostepnych miejsc na zmiany nocne i dzienne.
 weekday_count=sum(day['type']=='weekday' for day in days)
 sat_count=sum(day['type']=='sat' for day in days)
 if 'quota' not in relax and 'balance' not in relax and 'fallback' not in relax:
  min_nights=max(0,math.ceil((target-4)/2))
  if 9*min_nights>3*weekday_count:
   return {'ok':False,'status':2,'message':f'Za malo miejsc nocnych: potrzeba co najmniej {9*min_nights}, dostepnych maksymalnie {3*weekday_count}.','days':days}
  min_days=max(0,math.ceil((target-4)/2))
  if 9*min_days>3*weekday_count+2*sat_count:
   return {'ok':False,'status':2,'message':'Za malo miejsc na zmiany dzienne przy wybranej rownowadze.','days':days}
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
  # Zakaz przejścia z nocnej 18 na poranną 6 następnego dnia.
  # Dotyczy także ręcznych blokad i jest regułą bezwzględną.
  for d in range(D-1):
   add([(idx(p,d,1),1),(idx(p,d+1,0),1)],high=1)
  if 'blocks' not in relax:
   # Bloki trwaja od 2 do 4 dni kalendarzowych.
   # Pojedynczy dzien jest niedozwolony wewnatrz miesiaca;
   # na granicy miesiaca nie znamy sasiedniego grafiku.
   for d in range(1,D-1):
    if days[d]['type']=='closed':continue
    add([(idx(p,d,t),1) for t in range(2)]
        +[(idx(p,d-1,t),-1) for t in range(2)]
        +[(idx(p,d+1,t),-1) for t in range(2)],high=0)
   for d in range(D-4):
    add([(idx(p,j,t),1) for j in range(d,d+5) for t in range(2)],high=4)
  if 'rest' not in relax:
   # Dwa dni odpoczynku liczymy kalendarzowo, również przez święta.
   for d in range(D-2):
    add([(idx(p,d,t),1) for t in range(2)]
        +[(idx(p,d+1,t),-1) for t in range(2)]
        +[(idx(p,d+2,t),1) for t in range(2)],high=1)
   # Po pracującej sobocie wolna jest niedziela i poniedziałek.
   for d in range(D-2):
    if days[d]['weekday']==5:
     add([(idx(p,d,t),1) for t in range(2)]
         +[(idx(p,d+2,t),1) for t in range(2)],high=1)
  if 'rotation' not in relax:
   for d in range(D-1):
    n=d+1
    add([(idx(p,d,0),1),(idx(p,n,1),1)],high=1)
    add([(idx(p,d,1),1),(idx(p,n,0),1)],high=1)
  quota=target
  if 'quota' not in relax and 'fallback' not in relax:add([(idx(p,d,s),1) for d in range(D) for s in range(2)],low=quota,high=quota)
  if 'fallback' in relax:add([(idx(p,d,s),1) for d in range(D) for s in range(2)],high=quota)
  if 'balance' not in relax:
   # Roznica miedzy zmianami 6 i 18 nie moze przekroczyc 4.
   add([(idx(p,d,0),1) for d in range(D)]+[(idx(p,d,1),-1) for d in range(D)],low=-4,high=4)
 weekly={} if 'weekly' in relax else payload.get('weeklyShifts',{})
 for key,group in weekly.items():
  try: monday=datetime.date.fromisoformat(key)
  except ValueError: continue
  indices=[d for d in range(D) if monday<=datetime.date(year,month,d+1)<monday+datetime.timedelta(days=7)]
  for p in range(9):
   chosen=group.get(PEOPLE[p],'any')
   if chosen in ('6','18'):
    forbidden=1 if chosen=='6' else 0
    for d in indices: add([(idx(p,d,forbidden),1)],high=0)
 for d,day in enumerate(days):
  if day['type']=='closed':continue
  for s in ([0] if day['type']=='sat' else [0,1]):
   add([(idx(p,d,s),1) for p in range(9)],low=2 if 'staffing' not in relax else 1,high=2 if day['type']=='sat' else 3)
   if 'staffing' not in relax:add([(idx(p,d,s),1) for p in range(6)],low=1)
   if 'staffing' not in relax:add([(idx(p,d,s),1) for p in range(6,9)],high=2)
 A=lil_matrix((len(rows),N),dtype=float)
 for r,terms in enumerate(rows):
  for j,v in terms:A[r,j]+=v
 c=np.array([(-1.0+0.00001*(d%7)) if 'fallback' in relax else 0.001*(d%7) for p in range(9) for d in range(D) for shift in range(2)])
 res=milp(c,integrality=np.ones(N),bounds=Bounds(np.zeros(N),np.ones(N)),constraints=LinearConstraint(A.tocsr(),np.array(lo),np.array(hi)),options={'time_limit':20 if relax else 120})
 # Drugi etap: przy zachowaniu uzyskanej liczby zmian minimalizuj
 # największy niedobór pojedynczego pracownika (minimax).
 if 'fallback' in relax and res.x is not None:
  total=int(round(sum(res.x[:N])))
  B=lil_matrix((len(rows)+10,N+1),dtype=float)
  B[:len(rows),:N]=A
  low2=list(lo)+[total]+[-np.inf]*9
  high2=list(hi)+[np.inf]+[0]*9
  B[len(rows),:N]=1
  for p in range(9):
   for d in range(D):
    for sh in range(2):B[len(rows)+1+p,idx(p,d,sh)]=-1
   B[len(rows)+1+p,N]=-1
  # -liczba_zmian - max_niedobor <= -target
  for p in range(9):high2[len(rows)+1+p]=-target
  fair_obj=np.zeros(N+1);fair_obj[N]=1
  fair=milp(fair_obj,integrality=np.r_[np.ones(N),0],
            bounds=Bounds(np.zeros(N+1),np.r_[np.ones(N),target]),
            constraints=LinearConstraint(B.tocsr(),np.array(low2),np.array(high2)),
            options={'time_limit':40})
  if fair.x is not None:res=fair
 if res.x is None:
  if not relax and res.status==2 and not diagnostic:
   alternative=solve(payload,False,{'fallback'})
   if alternative.get('ok'):
    alternative['partial']=True
    alternative['status']=2
    alternative['message']='Pełny nominał jest niewykonalny. Wygenerowano grafik z brakami godzinowymi, zachowując pozostałe zasady.'
    return alternative
  report=[]
  if diagnostic and res.status==2:
   for group,label in [('blocks','maksymalnie 4 dni pracy'),('rest','dwa dni odpoczynku'),('rotation','jednolita zmiana w bloku'),('balance','równowaga zmian 6/18'),('weekly','wybory tygodniowe'),('quota','minimalny nominał'),('staffing','obsada zmian')]:
    probe=solve(payload,False,{group})
    report.append({'group':group,'label':label,'feasible':probe['ok'],'status':probe.get('status')})
  return {'ok':False,'status':int(res.status),'diagnostics':report,'message':f'Nie znaleziono grafiku z dokładnie {target*12} h na osobę. Status solvera: {res.message}. '+('Diagnostyka: '+('; '.join(x['label']+(' — usunięcie tej jednej reguły pozwala znaleźć grafik' if x['feasible'] else ' — brak potwierdzenia, że sama ta reguła blokuje grafik') for x in report)) if report else 'Spróbuj diagnostyki.'),'days':days}
 sched={PEOPLE[p]:[('6' if res.x[idx(p,d,0)]>.5 else '18' if res.x[idx(p,d,1)]>.5 else '') for d in range(D)] for p in range(9)}
 shortfalls=[{'employee':p,'hours':12*sum(x in ('6','18') for x in sched[p]),'required':target*12,'missing':12*(target-sum(x in ('6','18') for x in sched[p]))} for p in PEOPLE]
 return {'ok':True,'schedule':sched,'days':days,'partial':'fallback' in relax,'shortfalls':shortfalls,'message':f'Grafik wygenerowany. Wymagany wymiar: {target*12} h na osobę (nominał {nominal} h).'}
def validate(payload,allow_shortfall=False):
 days=build_days(int(payload['year']),int(payload['month']),set(map(int,payload.get('closed',[]))))
 sched=payload['schedule'];issues=[];nominal=int(payload.get('nominal',176));target=max(0,math.ceil(nominal/12))
 for p in PEOPLE:
  vals=sched.get(p,[])
  if len(vals)!=len(days):issues.append(f'{p}: niepełny grafik');continue
  worked=sum(v in ('6','18') for v in vals)
  expected=target
  if worked!=expected and not (allow_shortfall and worked<expected):issues.append(f'{p}: {worked*12} h, wymagane dokładnie {expected*12} h (nominał {nominal} h)')
  if abs(vals.count('6')-vals.count('18'))>4:issues.append(f'{p}: różnica zmian 6/18 przekracza 4')
  for d,day in enumerate(days):
   if day['type']=='closed' and vals[d] in ('6','18'):issues.append(f'{p}, dzień {d+1}: praca w dniu zamkniętym')
   if day['type']=='sat' and vals[d]=='18':issues.append(f'{p}, dzień {d+1}: nocna zmiana w sobotę')
  for d in range(len(vals)-1):
   if vals[d]=='18' and vals[d+1]=='6':issues.append(f'{p}: niedozwolone przejście 18→6 w dniach {d+1}–{d+2}')
   if vals[d] in ('6','18') and vals[d+1] in ('6','18') and vals[d]!=vals[d+1]:
    issues.append(f'{p}: mieszane zmiany w bloku {d+1}–{d+2}')
  for d in range(len(vals)-4):
   if all(v in ('6','18') for v in vals[d:d+5]):issues.append(f'{p}: ponad 4 dni pracy od {d+1}')
  for d in range(1,len(vals)-1):
   if vals[d] in ('6','18') and vals[d-1] not in ('6','18') and vals[d+1] not in ('6','18'):
    issues.append(f'{p}: pojedynczy dzień pracy {d+1}')
  for d in range(len(vals)-2):
   if vals[d] in ('6','18') and vals[d+1] not in ('6','18') and vals[d+2] in ('6','18'):
    issues.append(f'{p}: tylko jeden dzień wolny między dniami {d+1} i {d+3}')
   if days[d]['weekday']==5 and vals[d] in ('6','18') and vals[d+2] in ('6','18'):
    issues.append(f'{p}: poniedziałek po sobocie {d+1} musi być wolny')
  for d,v in enumerate(vals):
   locked=payload.get('locks',{}).get(f'{p}-{d+1}')
   if locked=='W' and v in ('6','18'):issues.append(f'{p}, dzień {d+1}: naruszona blokada wolnego')
   if locked in ('6','18') and v!=locked:issues.append(f'{p}, dzień {d+1}: naruszona blokada {locked}')
 for d,day in enumerate(days):
  for shift in (['6'] if day['type']=='sat' else ['6','18'] if day['type']=='weekday' else []):
   workers=[p for p in PEOPLE if len(sched.get(p,[]))>d and sched[p][d]==shift]
   if len(workers)<2 or len(workers)>(2 if day['type']=='sat' else 3):issues.append(f'Dzień {d+1}, zmiana {shift}: nieprawidłowa obsada')
   if not set(workers)&PROD:issues.append(f'Dzień {d+1}, zmiana {shift}: brak produkcji')
   if len(set(workers)&PACK)>2:issues.append(f'Dzień {d+1}, zmiana {shift}: za dużo pakowania')
 for key,group in payload.get('weeklyShifts',{}).items():
  try: monday=datetime.date.fromisoformat(key)
  except ValueError:
   issues.append('Nieprawidłowy tydzień: '+key)
   continue
  indices=[d for d in range(len(days)) if monday<=datetime.date(int(payload['year']),int(payload['month']),d+1)<monday+datetime.timedelta(days=7)]
  for p in PEOPLE:
   chosen=group.get(p,'any')
   if chosen not in ('6','18'): continue
   for d in indices:
    if d<len(sched.get(p,[])) and sched[p][d] in ('6','18') and sched[p][d]!=chosen:
     issues.append(f'{p}, dzień {d+1}: zmiana {sched[p][d]} niezgodna z tygodniowym wyborem {chosen}')
 return issues
