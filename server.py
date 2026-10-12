import os,json,calendar,datetime,tempfile
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from solver import solve,validate,build_days,PEOPLE
from openpyxl import Workbook
BASE=os.path.dirname(os.path.abspath(__file__))
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=BASE,**kw)
 def do_POST(self):
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n>200000:raise ValueError('Za duży formularz')
   data=json.loads(self.rfile.read(n));path=self.path.split('?')[0]
   if path=='/api/generate':return self.json(solve(data))
   if path=='/api/diagnose':return self.json(solve(data,diagnostic=True))
   if path=='/api/validate':return self.json({'issues':validate(data)})
   if path=='/api/export':
    issues=validate(data)
    if issues:return self.json({'error':'Grafik narusza zasady','issues':issues},422)
    return self.export(data)
   return self.json({'error':'Nieznana ścieżka'},404)
  except Exception as e:return self.json({'error':str(e)},400)
 def json(self,obj,status=200):
  b=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def export(self,data):
  days=build_days(int(data['year']),int(data['month']),set(map(int,data.get('closed',[]))))
  wb=Workbook();ws=wb.active;ws.title='Grafik miesięczny';D=len(days)
  ws.append(['Pracownik']+[x['day'] for x in days]+['Godziny','Zm. 6','Zm. 18','Nominał','Nadgodziny'])
  for p in PEOPLE:
   v=data['schedule'][p];h=12*sum(x in ('6','18') for x in v);n=int(data.get('nominal',176))
   ws.append([p]+v+[h,v.count('6'),v.count('18'),n,h-n])
  ws.append(['Dzień tyg.']+[('Pn','Wt','Śr','Cz','Pt','So','Nd')[x['weekday']] for x in days])
  ws.append(['Obsada 6']+[','.join(p for p in PEOPLE if data['schedule'][p][i]=='6') for i in range(D)])
  ws.append(['Obsada 18']+[','.join(p for p in PEOPLE if data['schedule'][p][i]=='18') for i in range(D)])
  from openpyxl.styles import PatternFill,Font
  for c in ws[1]:c.fill=PatternFill('solid',fgColor='17324E');c.font=Font(color='FFFFFF',bold=True)
  ws.freeze_panes='B2';ws.column_dimensions['A'].width=18
  from openpyxl.utils import get_column_letter
  for i,day in enumerate(days,2):
   ws.column_dimensions[get_column_letter(i)].width=5
   if day['type']!='weekday':
    for row in ws.iter_rows(min_col=i,max_col=i):
     row[0].fill=PatternFill('solid',fgColor='F2E8FA' if day['type']=='closed' else 'FFF0C9')
  info=wb.create_sheet('Informacje')
  for row in [['Generator Grafiku WEB','v1'],['Miesiąc',str(data['month'])+'/'+str(data['year'])],['Nominał',int(data.get('nominal',176))],['Uwaga','Format importu ShiftMate wymaga potwierdzenia']]:info.append(row)
  import io
  out=io.BytesIO();wb.save(out);b=out.getvalue()
  self.send_response(200);self.send_header('Content-Type','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');self.send_header('Content-Disposition','attachment; filename="Grafik_%s_%02d.xlsx"'%(data['year'],int(data['month'])));self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
if __name__=='__main__':
 port=int(os.environ.get('PORT','8000'));ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
