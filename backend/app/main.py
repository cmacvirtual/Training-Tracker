from datetime import datetime, timedelta
import base64, hashlib, hmac, json, os, secrets, csv, io
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv('TOC_DATABASE_URL','sqlite:///./toc.db')
SECRET = os.getenv('TOC_SECRET_KEY','dev-secret-change-me').encode()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith('sqlite') else {})
SessionLocal = sessionmaker(bind=engine)
app = FastAPI(title='Training Operations Center API', version='6.7')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()

def now(): return datetime.utcnow().isoformat(timespec='seconds')+'Z'
def hash_pw(p,s=None):
    s=s or secrets.token_hex(16)
    h=hashlib.pbkdf2_hmac('sha256', p.encode(), s.encode(), 120000).hex()
    return f'{s}${h}'
def verify_pw(p, stored):
    try: s,h=stored.split('$',1); return hmac.compare_digest(hash_pw(p,s).split('$',1)[1],h)
    except Exception: return False

def make_token(user):
    payload={'id':user['id'],'username':user['username'],'role':user['role'],'exp':(datetime.utcnow()+timedelta(hours=12)).timestamp()}
    raw=base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    sig=hmac.new(SECRET, raw.encode(), hashlib.sha256).hexdigest()
    return raw+'.'+sig

def read_token(token):
    try:
        raw,sig=token.split('.',1)
        if not hmac.compare_digest(hmac.new(SECRET, raw.encode(), hashlib.sha256).hexdigest(),sig): return None
        data=json.loads(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)))
        if data.get('exp',0) < datetime.utcnow().timestamp(): return None
        return data
    except Exception: return None

def current_user(authorization: Optional[str]=Header(None), s=Depends(db)):
    if not authorization or not authorization.lower().startswith('bearer '): raise HTTPException(401,'Login required')
    data=read_token(authorization.split(' ',1)[1])
    if not data: raise HTTPException(401,'Invalid or expired token')
    row=s.execute(text('select id,username,full_name,email,role,active from users where id=:id'), {'id':data['id']}).mappings().first()
    if not row or not row['active']: raise HTTPException(401,'User disabled')
    return dict(row)

def require_admin(u=Depends(current_user)):
    if u['role']!='admin': raise HTTPException(403,'Admin role required')
    return u

def rows(s, q, p={}): return [dict(r) for r in s.execute(text(q),p).mappings().all()]
def one(s, q, p={}):
    r=s.execute(text(q),p).mappings().first(); return dict(r) if r else None

def init_db():
    os.makedirs('/app/data', exist_ok=True)
    with engine.begin() as c:
        c.execute(text('create table if not exists users(id integer primary key autoincrement, username text unique, password_hash text, full_name text, email text, role text, active integer default 1, created_at text)'))
        c.execute(text('create table if not exists courses(id integer primary key autoincrement, title text, category text, description text, duration text, level text, active integer default 1)'))
        c.execute(text('create table if not exists classes(id integer primary key autoincrement, course_id integer, instructor_id integer, start_date text, end_date text, time_window text, location text, capacity integer, status text default "scheduled", lab_template text)'))
        c.execute(text('create table if not exists attendees(id integer primary key autoincrement, first_name text, last_name text, email text, company text, manager text, experience text, notes text, created_at text)'))
        c.execute(text('create table if not exists registrations(id integer primary key autoincrement, class_id integer, attendee_id integer, status text default "pending", requested_at text, reviewed_at text, reviewed_by integer)'))
        c.execute(text('create table if not exists enrollments(id integer primary key autoincrement, class_id integer, attendee_id integer, status text default "approved", pod_name text, pod_status text default "not_started", account_status text default "not_started", snapshot_status text default "not_started", docs_status text default "not_started", completed integer default 0, completion_date text, score text, certificate_issued integer default 0, completion_notes text)'))
        admin_row = c.execute(text('select id from users where username="admin"')).first()
        reset_admin = os.getenv('TOC_RESET_DEFAULT_ADMIN','true').lower() in ('1','true','yes')
        if not admin_row:
            c.execute(text('insert into users(username,password_hash,full_name,email,role,active,created_at) values(:u,:p,:f,:e,"admin",1,:t)'), {'u':'admin','p':hash_pw('admin123'),'f':'Administrator','e':'admin@example.local','t':now()})
        elif reset_admin:
            c.execute(text('update users set password_hash=:p, role="admin", active=1 where username="admin"'), {'p':hash_pw('admin123')})
        if not c.execute(text('select id from courses')).first():
            c.execute(text('insert into courses(title,category,description,duration,level,active) values (:t,:c,:d,:du,:l,1)'), {'t':'VCF 9 Deploy & Configure','c':'VMware Cloud Foundation','d':'Hands-on deployment and configuration of a VCF 9 management domain.','du':'5 days','l':'Intermediate'})
            c.execute(text('insert into courses(title,category,description,duration,level,active) values (:t,:c,:d,:du,:l,1)'), {'t':'VCF 9 Troubleshooting','c':'VMware Cloud Foundation','d':'Operational troubleshooting scenarios for VCF, NSX, Operations, and Logs.','du':'5 days','l':'Advanced'})
            c.execute(text('insert into courses(title,category,description,duration,level,active) values (:t,:c,:d,:du,:l,1)'), {'t':'VCAP Operations Prep','c':'Certification','d':'Scenario-based preparation for VCAP-level operations objectives.','du':'3 days','l':'Advanced'})
            admin_id=c.execute(text('select id from users where username="admin"')).scalar()
            for cid,sd,ed,cap in [(1,'2026-07-06','2026-07-10',24),(2,'2026-07-20','2026-07-24',20),(3,'2026-08-10','2026-08-12',16)]:
                c.execute(text('insert into classes(course_id,instructor_id,start_date,end_date,time_window,location,capacity,status,lab_template) values(:cid,:iid,:sd,:ed,"1500-1700 EST","Virtual Lab",:cap,"scheduled","VCF-LAB-STANDARD")'), {'cid':cid,'iid':admin_id,'sd':sd,'ed':ed,'cap':cap})
init_db()

class Login(BaseModel): username:str; password:str
class CourseIn(BaseModel): title:str; category:str='General'; description:str=''; duration:str=''; level:str='Intermediate'; active:int=1
class ClassIn(BaseModel): course_id:int; instructor_id:int; start_date:str; end_date:str; time_window:str=''; location:str=''; capacity:int=20; status:str='scheduled'; lab_template:str=''
class Signup(BaseModel): class_id:int; first_name:str; last_name:str; email:EmailStr; company:str=''; manager:str=''; experience:str=''; notes:str=''
class Decision(BaseModel): status:str
class PodUpdate(BaseModel): pod_name:Optional[str]=None; pod_status:Optional[str]=None; account_status:Optional[str]=None; snapshot_status:Optional[str]=None; docs_status:Optional[str]=None
class CompletionUpdate(BaseModel): completed:int; completion_date:Optional[str]=None; score:Optional[str]=None; certificate_issued:int=0; completion_notes:Optional[str]=None
class UserIn(BaseModel): username:str; password:str; full_name:str; email:str=''; role:str='instructor'; active:int=1
class AttendeeIn(BaseModel): first_name:str; last_name:str; email:EmailStr; company:str=''; manager:str=''; experience:str=''; notes:str=''
class AttendeeUpdate(BaseModel): first_name:Optional[str]=None; last_name:Optional[str]=None; email:Optional[EmailStr]=None; company:Optional[str]=None; manager:Optional[str]=None; experience:Optional[str]=None; notes:Optional[str]=None
class CourseUpdate(BaseModel): title:Optional[str]=None; category:Optional[str]=None; description:Optional[str]=None; duration:Optional[str]=None; level:Optional[str]=None; active:Optional[int]=None
class ClassUpdate(BaseModel): course_id:Optional[int]=None; instructor_id:Optional[int]=None; start_date:Optional[str]=None; end_date:Optional[str]=None; time_window:Optional[str]=None; location:Optional[str]=None; capacity:Optional[int]=None; status:Optional[str]=None; lab_template:Optional[str]=None
class EnrollmentCreate(BaseModel): attendee_ids:List[int]; status:str='approved'; pod_status:str='not_started'

@app.get('/health')
def health(): return {'ok':True,'version':'6.7'}
@app.post('/auth/login')
def login(body:Login, s=Depends(db)):
    username=(body.username or '').strip().lower()
    password=(body.password or '').strip()
    u=one(s,'select * from users where lower(username)=lower(:u)', {'u':username})
    if not u or not verify_pw(password,u['password_hash']) or not u['active']:
        raise HTTPException(401,'Invalid login')
    return {'token':make_token(u),'user':{k:u[k] for k in ['id','username','full_name','email','role']}}

@app.post('/bootstrap/reset-admin')
def bootstrap_reset_admin(s=Depends(db)):
    enabled=os.getenv('TOC_ENABLE_BOOTSTRAP_RESET','true').lower() in ('1','true','yes')
    if not enabled:
        raise HTTPException(403,'Bootstrap reset is disabled')
    existing=one(s,'select id from users where lower(username)=lower(:u)', {'u':'admin'})
    if existing:
        s.execute(text('update users set password_hash=:p, role="admin", active=1 where id=:id'), {'p':hash_pw('admin123'), 'id':existing['id']})
    else:
        s.execute(text('insert into users(username,password_hash,full_name,email,role,active,created_at) values(:u,:p,:f,:e,"admin",1,:t)'), {'u':'admin','p':hash_pw('admin123'),'f':'Administrator','e':'admin@example.local','t':now()})
    s.commit()
    return {'ok':True,'message':'admin reset to admin123'}
@app.get('/auth/me')
def me(u=Depends(current_user)): return u

@app.get('/public/classes')
def public_classes(s=Depends(db)):
    q='''select cl.*, co.title, co.category, co.description, co.duration, co.level, u.full_name instructor,
    (select count(*) from enrollments e where e.class_id=cl.id and e.status="approved") approved_count,
    (select count(*) from registrations r where r.class_id=cl.id and r.status="pending") pending_count
    from classes cl join courses co on co.id=cl.course_id left join users u on u.id=cl.instructor_id where co.active=1 and cl.status in ("scheduled","open") order by cl.start_date'''
    data=rows(s,q)
    for d in data: d['seats_remaining']=max(0,(d['capacity'] or 0)-(d['approved_count'] or 0))
    return data
@app.post('/public/signup')
def signup(b:Signup, s=Depends(db)):
    att=one(s,'select id from attendees where lower(email)=lower(:e)', {'e':b.email})
    if not att:
        s.execute(text('insert into attendees(first_name,last_name,email,company,manager,experience,notes,created_at) values(:fn,:ln,:e,:c,:m,:x,:n,:t)'), {'fn':b.first_name,'ln':b.last_name,'e':b.email,'c':b.company,'m':b.manager,'x':b.experience,'n':b.notes,'t':now()}); s.commit(); aid=s.execute(text('select last_insert_rowid()')).scalar()
    else:
        aid=att['id']; s.execute(text('update attendees set first_name=:fn,last_name=:ln,company=:c,manager=:m,experience=:x,notes=:n where id=:id'), {'fn':b.first_name,'ln':b.last_name,'c':b.company,'m':b.manager,'x':b.experience,'n':b.notes,'id':aid}); s.commit()
    existing=one(s,'select * from registrations where class_id=:c and attendee_id=:a', {'c':b.class_id,'a':aid}) or one(s,'select * from enrollments where class_id=:c and attendee_id=:a', {'c':b.class_id,'a':aid})
    if existing: return {'message':'You already have a registration or enrollment for this class.','attendee_id':aid}
    s.execute(text('insert into registrations(class_id,attendee_id,status,requested_at) values(:c,:a,"pending",:t)'), {'c':b.class_id,'a':aid,'t':now()}); s.commit()
    return {'message':'Registration submitted for instructor approval.','attendee_id':aid}
@app.get('/public/status')
def status(email:str, s=Depends(db)):
    return rows(s,'''select co.title, cl.start_date, cl.end_date, r.status, r.requested_at, null as pod_status, 0 as completed from registrations r join classes cl on cl.id=r.class_id join courses co on co.id=cl.course_id join attendees a on a.id=r.attendee_id where lower(a.email)=lower(:e)
    union all select co.title, cl.start_date, cl.end_date, e.status, null, e.pod_status, e.completed from enrollments e join classes cl on cl.id=e.class_id join courses co on co.id=cl.course_id join attendees a on a.id=e.attendee_id where lower(a.email)=lower(:e)''', {'e':email})



def norm_key(k):
    return (k or '').strip().lower().replace(' ', '_').replace('-', '_').replace('/', '_')

def getv(row, *keys, default=''):
    normalized={norm_key(k):v for k,v in (row or {}).items()}
    for k in keys:
        v=normalized.get(norm_key(k))
        if v is not None and str(v).strip() != '':
            return str(v).strip()
    return default

async def read_csv_upload(file: UploadFile):
    """Read messy CSV exports without crashing the API.

    Handles common Excel encodings, Windows/Mac/Linux line endings, blank rows,
    BOMs, tab/semicolon/comma delimiters, and malformed rows. If a row is bad,
    it is skipped and reported back to the UI instead of raising a 500 error.
    """
    if not file or not file.filename:
        raise HTTPException(400, 'No CSV file was uploaded')
    raw = await file.read()
    if not raw:
        raise HTTPException(400, 'Uploaded CSV file is empty')

    text_content = None
    used_encoding = None
    for enc in ('utf-8-sig', 'utf-16', 'utf-16le', 'utf-16be', 'utf-8', 'cp1252', 'latin-1'):
        try:
            candidate = raw.decode(enc)
            # Avoid false-positive latin/cp decoding of UTF-16 files full of NULs.
            if candidate.count('\x00') > max(5, len(candidate) // 20):
                continue
            text_content = candidate
            used_encoding = enc
            break
        except UnicodeDecodeError:
            continue
    if text_content is None:
        raise HTTPException(400, 'Could not decode CSV file. Save it as UTF-8 CSV and try again.')

    # Remove null bytes and normalize line endings before csv parsing.
    text_content = text_content.replace('\x00', '')
    text_content = text_content.replace('\r\n', '\n').replace('\r', '\n')
    text_content = '\n'.join(line for line in text_content.split('\n') if line.strip())
    if not text_content.strip():
        raise HTTPException(400, 'CSV does not contain any readable rows')

    sample = text_content[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',\t;|')
    except csv.Error:
        # Pick the most likely delimiter from the first line.
        first_line = text_content.split('\n', 1)[0]
        delimiter = max([',', '\t', ';', '|'], key=lambda d: first_line.count(d))
        dialect = csv.excel
        dialect.delimiter = delimiter

    errors = []
    clean_rows = []
    headers = []

    try:
        reader = csv.DictReader(io.StringIO(text_content, newline=''), dialect=dialect)
        if not reader.fieldnames:
            raise HTTPException(400, 'CSV does not contain a header row')
        headers = [norm_key(h) for h in (reader.fieldnames or []) if h is not None]
        for idx, row in enumerate(reader, start=2):
            if not row:
                continue
            # Drop malformed extra columns under the None key and record the issue.
            if None in row:
                errors.append(f'Row {idx}: extra columns were ignored')
                row.pop(None, None)
            if any(str(v or '').strip() for v in row.values()):
                clean_rows.append(row)
    except csv.Error as exc:
        # Last-resort parser for badly exported CSVs with unquoted embedded newlines.
        lines = [ln for ln in text_content.split('\n') if ln.strip()]
        if not lines:
            raise HTTPException(400, 'CSV does not contain any readable rows')
        delimiter = getattr(dialect, 'delimiter', ',') or ','
        raw_headers = [h.strip().strip('"') for h in lines[0].split(delimiter)]
        headers = [norm_key(h) for h in raw_headers if h]
        if not headers:
            raise HTTPException(400, f'CSV header row could not be parsed: {exc}')
        for idx, ln in enumerate(lines[1:], start=2):
            try:
                cols = next(csv.reader([ln], delimiter=delimiter))
            except Exception:
                errors.append(f'Row {idx}: could not parse row and skipped')
                continue
            if not any(str(c or '').strip() for c in cols):
                continue
            # Pad or trim so dict creation is stable.
            if len(cols) < len(raw_headers):
                cols = cols + [''] * (len(raw_headers) - len(cols))
                errors.append(f'Row {idx}: missing columns were filled as blank')
            elif len(cols) > len(raw_headers):
                cols = cols[:len(raw_headers)]
                errors.append(f'Row {idx}: extra columns were ignored')
            clean_rows.append(dict(zip(raw_headers, cols)))
        errors.insert(0, f'CSV required fallback parsing because of malformed formatting: {exc}')

    if not headers:
        raise HTTPException(400, 'CSV does not contain a header row')

    return clean_rows, headers, errors, used_encoding

@app.post('/import/courses')
async def import_courses(file: UploadFile = File(...), u=Depends(require_admin), s=Depends(db)):
    imported=0; skipped=0
    csv_rows, headers, parse_errors, encoding = await read_csv_upload(file)
    for row in csv_rows:
        title=getv(row,'title','course','course_title','course_name','name','class','class_name')
        if not title:
            skipped+=1; continue
        existing=one(s,'select id from courses where lower(title)=lower(:t)', {'t':title})
        data={'title':title,'category':getv(row,'category','track','course_category',default='General'),'description':getv(row,'description','details','course_description'),'duration':getv(row,'duration','length','course_duration'),'level':getv(row,'level','difficulty','course_level',default='Intermediate'),'active':1}
        if existing:
            s.execute(text('update courses set category=:category,description=:description,duration=:duration,level=:level,active=:active where id=:id'), {**data,'id':existing['id']})
        else:
            s.execute(text('insert into courses(title,category,description,duration,level,active) values(:title,:category,:description,:duration,:level,:active)'), data)
        imported+=1
    s.commit(); return {'ok':True,'imported':imported,'skipped':skipped,'headers':headers,'parse_errors':parse_errors,'encoding':encoding}

@app.post('/import/attendees')
async def import_attendees(file: UploadFile = File(...), u=Depends(require_admin), s=Depends(db)):
    imported=0; skipped=0
    csv_rows, headers, parse_errors, encoding = await read_csv_upload(file)
    for row in csv_rows:
        email=getv(row,'email','email_address','student_email','attendee_email','e_mail')
        first=getv(row,'first_name','firstname','first','student_first_name','attendee_first_name')
        last=getv(row,'last_name','lastname','last','student_last_name','attendee_last_name')
        full=getv(row,'name','full_name','student_name','attendee_name','student')
        if (not first or not last) and full:
            parts=full.split(); first=first or (parts[0] if parts else ''); last=last or (' '.join(parts[1:]) if len(parts)>1 else '')
        if not email and not (first or last):
            skipped+=1; continue
        if not email: email=f"{first}.{last}@unknown.local".lower().replace(' ','')
        data={'first_name':first,'last_name':last,'email':email,'company':getv(row,'company','organization','org'),'manager':getv(row,'manager','supervisor'),'experience':getv(row,'experience','level','experience_level'),'notes':getv(row,'notes','comments'),'created_at':now()}
        existing=one(s,'select id from attendees where lower(email)=lower(:e)', {'e':email})
        if existing:
            s.execute(text('update attendees set first_name=:first_name,last_name=:last_name,company=:company,manager=:manager,experience=:experience,notes=:notes where id=:id'), {**data,'id':existing['id']})
        else:
            s.execute(text('insert into attendees(first_name,last_name,email,company,manager,experience,notes,created_at) values(:first_name,:last_name,:email,:company,:manager,:experience,:notes,:created_at)'), data)
        imported+=1
    s.commit(); return {'ok':True,'imported':imported,'skipped':skipped,'headers':headers,'parse_errors':parse_errors,'encoding':encoding}



def csv_stream(filename, records):
    output=io.StringIO()
    if records:
        writer=csv.DictWriter(output, fieldnames=list(records[0].keys()), extrasaction='ignore')
        writer.writeheader(); writer.writerows(records)
    else:
        output.write('message\nNo records\n')
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="{filename}"'})

@app.post('/admin/reset-admin-password')
def reset_admin_password(u=Depends(require_admin), s=Depends(db)):
    s.execute(text('update users set password_hash=:p, role="admin", active=1 where username="admin"'), {'p':hash_pw('admin123')})
    s.commit(); return {'ok':True,'message':'admin password reset to admin123'}

@app.get('/dashboard')
def dashboard(u=Depends(current_user), s=Depends(db)):
    return {'classes':one(s,'select count(*) count from classes')['count'], 'students':one(s,'select count(*) count from attendees')['count'], 'pending':one(s,'select count(*) count from registrations where status="pending"')['count'], 'pods_ready':one(s,'select count(*) count from enrollments where pod_status="ready"')['count'], 'completions':one(s,'select count(*) count from enrollments where completed=1')['count']}
@app.get('/reports/summary')
def report_summary(u=Depends(current_user), s=Depends(db)):
    by_course=rows(s,'select co.title, count(e.id) enrollments, sum(case when e.completed=1 then 1 else 0 end) completions, sum(case when e.certificate_issued=1 then 1 else 0 end) certificates from courses co left join classes cl on cl.course_id=co.id left join enrollments e on e.class_id=cl.id group by co.id order by co.title')
    upcoming=rows(s,'select co.title, cl.start_date, cl.end_date, cl.capacity, (select count(*) from enrollments e where e.class_id=cl.id) enrolled from classes cl join courses co on co.id=cl.course_id order by cl.start_date')
    labs=rows(s,'select pod_status, count(*) count from enrollments group by pod_status')
    return {'by_course':by_course,'upcoming':upcoming,'labs':labs}
@app.get('/reports/students.csv')
def students_csv(u=Depends(current_user), s=Depends(db)):
    return csv_stream('students.csv', rows(s,'select * from attendees order by last_name, first_name'))
@app.get('/reports/classes.csv')
def classes_csv(u=Depends(current_user), s=Depends(db)):
    return csv_stream('classes.csv', rows(s,'select cl.*, co.title, u.full_name instructor from classes cl join courses co on co.id=cl.course_id left join users u on u.id=cl.instructor_id order by cl.start_date'))
@app.get('/reports/enrollments.csv')
def enrollments_csv(u=Depends(current_user), s=Depends(db)):
    return csv_stream('enrollments.csv', rows(s,'select co.title course, cl.start_date, a.first_name, a.last_name, a.email, e.status, e.pod_name, e.pod_status, e.account_status, e.snapshot_status, e.docs_status, e.completed, e.completion_date, e.score, e.certificate_issued, e.completion_notes from enrollments e join attendees a on a.id=e.attendee_id join classes cl on cl.id=e.class_id join courses co on co.id=cl.course_id order by cl.start_date, a.last_name'))
@app.get('/reports/completions.csv')
def completions_csv(u=Depends(current_user), s=Depends(db)):
    return csv_stream('completions.csv', rows(s,'select co.title course, cl.start_date, a.first_name, a.last_name, a.email, e.completed, e.completion_date, e.score, e.certificate_issued, e.completion_notes from enrollments e join attendees a on a.id=e.attendee_id join classes cl on cl.id=e.class_id join courses co on co.id=cl.course_id where e.completed=1 order by e.completion_date desc'))
@app.get('/courses')
def courses(u=Depends(current_user), s=Depends(db)): return rows(s,'select * from courses order by title')
@app.post('/courses')
def add_course(b:CourseIn, u=Depends(current_user), s=Depends(db)):
    s.execute(text('insert into courses(title,category,description,duration,level,active) values(:title,:category,:description,:duration,:level,:active)'), b.model_dump()); s.commit(); return {'ok':True}
@app.patch('/courses/{cid}')
def update_course(cid:int,b:CourseUpdate,u=Depends(current_user),s=Depends(db)):
    fields={k:v for k,v in b.model_dump().items() if v is not None}
    if not fields: return {'ok':True}
    fields['id']=cid
    s.execute(text('update courses set '+','.join([f'{k}=:{k}' for k in fields if k!='id'])+' where id=:id'), fields); s.commit(); return {'ok':True}
@app.get('/classes')
def classes(u=Depends(current_user), s=Depends(db)): return rows(s,'select cl.*,co.title,u.full_name instructor from classes cl join courses co on co.id=cl.course_id left join users u on u.id=cl.instructor_id order by cl.start_date')
@app.post('/classes')
def add_class(b:ClassIn, u=Depends(current_user), s=Depends(db)):
    s.execute(text('insert into classes(course_id,instructor_id,start_date,end_date,time_window,location,capacity,status,lab_template) values(:course_id,:instructor_id,:start_date,:end_date,:time_window,:location,:capacity,:status,:lab_template)'), b.model_dump()); s.commit(); return {'ok':True}
@app.patch('/classes/{cid}')
def update_class(cid:int,b:ClassUpdate,u=Depends(current_user),s=Depends(db)):
    fields={k:v for k,v in b.model_dump().items() if v is not None}
    if not fields: return {'ok':True}
    fields['id']=cid
    s.execute(text('update classes set '+','.join([f'{k}=:{k}' for k in fields if k!='id'])+' where id=:id'), fields); s.commit(); return {'ok':True}
@app.get('/attendees')
def attendees(u=Depends(current_user), s=Depends(db)):
    return rows(s,'select * from attendees order by last_name, first_name')
@app.post('/attendees')
def add_attendee(b:AttendeeIn, u=Depends(current_user), s=Depends(db)):
    existing=one(s,'select id from attendees where lower(email)=lower(:e)', {'e':b.email})
    if existing: raise HTTPException(400,'A student with that email already exists.')
    d=b.model_dump(); d['created_at']=now()
    s.execute(text('insert into attendees(first_name,last_name,email,company,manager,experience,notes,created_at) values(:first_name,:last_name,:email,:company,:manager,:experience,:notes,:created_at)'), d); s.commit(); return {'ok':True}
@app.patch('/attendees/{aid}')
def update_attendee(aid:int,b:AttendeeUpdate,u=Depends(current_user),s=Depends(db)):
    fields={k:v for k,v in b.model_dump().items() if v is not None}
    if not fields: return {'ok':True}
    fields['id']=aid
    s.execute(text('update attendees set '+','.join([f'{k}=:{k}' for k in fields if k!='id'])+' where id=:id'), fields); s.commit(); return {'ok':True}
@app.get('/instructors')
def instructors(u=Depends(current_user), s=Depends(db)): return rows(s,'select id,username,full_name,email,role,active from users where role in ("admin","instructor") order by full_name')
@app.post('/users')
def add_user(b:UserIn, u=Depends(require_admin), s=Depends(db)):
    try:
        d=b.model_dump(); d['password_hash']=hash_pw(d.pop('password')); d['created_at']=now()
        s.execute(text('insert into users(username,password_hash,full_name,email,role,active,created_at) values(:username,:password_hash,:full_name,:email,:role,:active,:created_at)'), d); s.commit(); return {'ok':True}
    except Exception as e: raise HTTPException(400, 'Unable to create user. Username may already exist.')
@app.get('/registrations')
def regs(u=Depends(current_user), s=Depends(db)):
    return rows(s,'select r.*, a.first_name,a.last_name,a.email,a.company,co.title,cl.start_date from registrations r join attendees a on a.id=r.attendee_id join classes cl on cl.id=r.class_id join courses co on co.id=cl.course_id order by r.requested_at desc')
@app.post('/registrations/{rid}/decision')
def decision(rid:int,b:Decision,u=Depends(current_user),s=Depends(db)):
    r=one(s,'select * from registrations where id=:id', {'id':rid})
    if not r: raise HTTPException(404,'Registration not found')
    if b.status not in ['approved','waitlisted','declined']: raise HTTPException(400,'Invalid status')
    s.execute(text('update registrations set status=:st, reviewed_at=:t, reviewed_by=:u where id=:id'), {'st':b.status,'t':now(),'u':u['id'],'id':rid})
    if b.status=='approved' and not one(s,'select id from enrollments where class_id=:c and attendee_id=:a', {'c':r['class_id'],'a':r['attendee_id']}):
        s.execute(text('insert into enrollments(class_id,attendee_id,status) values(:c,:a,"approved")'), {'c':r['class_id'],'a':r['attendee_id']})
    s.commit(); return {'ok':True}
@app.get('/classes/{cid}/roster')
def roster(cid:int,u=Depends(current_user),s=Depends(db)):
    return rows(s,'select e.*,a.first_name,a.last_name,a.email,a.company from enrollments e join attendees a on a.id=e.attendee_id where e.class_id=:cid order by a.last_name,a.first_name', {'cid':cid})
@app.get('/classes/{cid}/available-attendees')
def available_attendees(cid:int,u=Depends(current_user),s=Depends(db)):
    return rows(s,'''select a.* from attendees a
    where not exists (select 1 from enrollments e where e.class_id=:cid and e.attendee_id=a.id)
    and not exists (select 1 from registrations r where r.class_id=:cid and r.attendee_id=a.id and r.status in ("pending","approved"))
    order by a.last_name, a.first_name''', {'cid':cid})

@app.post('/classes/{cid}/enroll')
def enroll_existing_students(cid:int,b:EnrollmentCreate,u=Depends(current_user),s=Depends(db)):
    cl=one(s,'select id, capacity from classes where id=:id', {'id':cid})
    if not cl: raise HTTPException(404,'Class not found')
    if not b.attendee_ids: raise HTTPException(400,'Select at least one student to enroll')
    valid_statuses=['approved','waitlisted','dropped']
    if b.status not in valid_statuses: raise HTTPException(400,'Invalid enrollment status')
    added=0; skipped=0
    for aid in b.attendee_ids:
        att=one(s,'select id from attendees where id=:id', {'id':aid})
        if not att:
            skipped+=1; continue
        existing=one(s,'select id from enrollments where class_id=:c and attendee_id=:a', {'c':cid,'a':aid})
        if existing:
            skipped+=1; continue
        s.execute(text('insert into enrollments(class_id,attendee_id,status,pod_status) values(:c,:a,:st,:pod)'), {'c':cid,'a':aid,'st':b.status,'pod':b.pod_status})
        # If this student had a pending public registration for the same class, mark it reviewed/approved.
        s.execute(text('update registrations set status=:st, reviewed_at=:t, reviewed_by=:u where class_id=:c and attendee_id=:a and status="pending"'), {'st':b.status,'t':now(),'u':u['id'],'c':cid,'a':aid})
        added+=1
    s.commit()
    return {'ok':True,'added':added,'skipped':skipped}

@app.delete('/enrollments/{eid}')
def remove_enrollment(eid:int,u=Depends(current_user),s=Depends(db)):
    existing=one(s,'select id from enrollments where id=:id', {'id':eid})
    if not existing: raise HTTPException(404,'Enrollment not found')
    s.execute(text('delete from enrollments where id=:id'), {'id':eid})
    s.commit(); return {'ok':True}
@app.patch('/enrollments/{eid}/pod')
def pod(eid:int,b:PodUpdate,u=Depends(current_user),s=Depends(db)):
    fields={k:v for k,v in b.model_dump().items() if v is not None}
    if not fields: return {'ok':True}
    q='update enrollments set '+','.join([f'{k}=:{k}' for k in fields])+' where id=:id'; fields['id']=eid
    s.execute(text(q), fields); s.commit(); return {'ok':True}
@app.patch('/enrollments/{eid}/completion')
def comp(eid:int,b:CompletionUpdate,u=Depends(current_user),s=Depends(db)):
    d=b.model_dump(); d['id']=eid
    s.execute(text('update enrollments set completed=:completed, completion_date=:completion_date, score=:score, certificate_issued=:certificate_issued, completion_notes=:completion_notes where id=:id'), d); s.commit(); return {'ok':True}
