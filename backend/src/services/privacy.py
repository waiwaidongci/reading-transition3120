from decimal import Decimal
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from redis import Redis
from ..config.settings import REDIS_URL,CONFIG
from ..models.privacy import PrivacyStudy,PrivacyLedger,PrivacyAccount
from ..utils.serialization import row,now
from .sources import source_or_404,list_records
from .domain_validation import validate_privacy_parameters
from .privacy_algorithm import cache_key_for
from .audit import log
queue=Redis.from_url(REDIS_URL)
QUEUE_KEY='privacy:queue'
def get_account(db,lock=False):
    q=select(PrivacyAccount).where(PrivacyAccount.id==1)
    if lock:q=q.with_for_update()
    a=db.scalar(q)
    if not a:
        a=PrivacyAccount(id=1,total=Decimal(str(CONFIG['privacy']['total_quota'])));db.add(a);db.flush()
    return a
def _sums(db):
    rows=db.execute(select(PrivacyLedger.state,func.coalesce(func.sum(PrivacyLedger.amount),0)).group_by(PrivacyLedger.state)).all()
    return {state:Decimal(str(total)) for state,total in rows}
def account_view(db):
    a=get_account(db);s=_sums(db);held=s.get('held',0);confirmed=s.get('confirmed',0)
    return {'total':float(a.total),'held':float(held),'confirmed':float(confirmed),'refunded':float(s.get('refunded',0)),
        'balance':float(a.total-held-confirmed),'chapters':CONFIG['privacy']['chapters'],
        'epsilon_range':CONFIG['privacy']['epsilon_range'],'default_parameters':CONFIG['privacy']['default_parameters'],'noise_rule':CONFIG['privacy']['noise_rule']}
def get_study(db,id):
    r=db.get(PrivacyStudy,id)
    if not r:raise HTTPException(404,'未找到隐私研究')
    return r
def _ledger_of(db,study_id):return db.scalar(select(PrivacyLedger).where(PrivacyLedger.study_id==study_id))
def _view(db,r,full=False):
    d={k:v for k,v in row(r).items() if full or k not in ('snapshot','result')}
    led=_ledger_of(db,r.id)
    d['ledger_state']=led.state if led else 'none';d['amount']=float(led.amount) if led else 0
    return d
def list_studies(db):
    return [_view(db,r) for r in db.scalars(select(PrivacyStudy).order_by(PrivacyStudy.id.desc()))]
def study_detail(db,id):return _view(db,get_study(db,id),full=True)
def create_study(db,user,data):
    s=source_or_404(db,data.source_id);records=list_records(db,s.id)
    if not records:raise HTTPException(422,'至少录入1个完整阅读会话后才能执行')
    try:params=validate_privacy_parameters(data.parameters)
    except ValueError as e:raise HTTPException(422,str(e))
    snapshot={'source':row(s),'records':records};cache_key=cache_key_for(records,params)
    existing=db.scalar(select(PrivacyStudy).where(PrivacyStudy.cache_key==cache_key))
    if existing:return {'study':_view(db,existing),'reused':True}
    account=get_account(db,lock=True)
    used=_sums(db);reserved=used.get('held',0)+used.get('confirmed',0);amount=Decimal(str(params['epsilon']))
    if reserved+amount>account.total:raise HTTPException(409,f'隐私额度不足：本次需占用 ε={amount}，可用余额 ε={account.total-reserved}')
    r=PrivacyStudy(source_id=s.id,name=data.name,parameters=params,snapshot=snapshot,cache_key=cache_key,state='queued',created_at=now())
    db.add(r)
    try:db.flush()
    except IntegrityError:
        db.rollback();existing=db.scalar(select(PrivacyStudy).where(PrivacyStudy.cache_key==cache_key))
        if existing:return {'study':_view(db,existing),'reused':True}
        raise HTTPException(409,'并发冲突，请重试')
    t=now();db.add(PrivacyLedger(study_id=r.id,cache_key=cache_key,amount=amount,state='held',created_at=t,updated_at=t))
    log(db,user,'privacy.queued',r.id,f'{data.name} · 占额 ε={amount}');db.commit()
    try:queue.rpush(QUEUE_KEY,r.id)
    except Exception:
        r.state='failed';r.error='队列暂不可用，请重新创建任务'
        led=_ledger_of(db,r.id)
        if led and led.state=='held':led.state='refunded';led.updated_at=now()
        db.commit();raise HTTPException(503,r.error)
    return {'study':_view(db,r),'reused':False}
def cancel_study(db,user,id):
    r=db.scalar(select(PrivacyStudy).where(PrivacyStudy.id==id).with_for_update())
    if not r:raise HTTPException(404,'未找到隐私研究')
    if r.state not in ('queued','running'):raise HTTPException(409,'仅队列中或计算中的研究可取消；已公开结果永不退回')
    r.state='cancelled'
    led=db.scalar(select(PrivacyLedger).where(PrivacyLedger.study_id==id).with_for_update())
    if led and led.state=='held':led.state='refunded';led.updated_at=now()
    log(db,user,'privacy.cancelled',id,r.name);db.commit();return _view(db,r)
def finish_study(db,id,result):
    r=db.scalar(select(PrivacyStudy).where(PrivacyStudy.id==id).with_for_update())
    if not r or r.state not in ('queued','running'):return False
    led=db.scalar(select(PrivacyLedger).where(PrivacyLedger.study_id==id).with_for_update())
    if not led or led.state not in ('held','confirmed'):return False
    r.result=result;r.state='completed'
    if led.state=='held':led.state='confirmed';led.updated_at=now()
    log(db,'worker','privacy.completed',id);db.commit();return True
def fail_study(db,id,error):
    r=db.scalar(select(PrivacyStudy).where(PrivacyStudy.id==id).with_for_update())
    if not r or r.state not in ('queued','running'):return False
    r.state='failed';r.error=error[:2000]
    led=db.scalar(select(PrivacyLedger).where(PrivacyLedger.study_id==id).with_for_update())
    if led and led.state=='held':led.state='refunded';led.updated_at=now()
    log(db,'worker','privacy.failed',id,error[:200]);db.commit();return True
def recover(db):
    for r in db.scalars(select(PrivacyStudy).where(PrivacyStudy.state=='running')):r.state='queued'
    for led in db.scalars(select(PrivacyLedger).where(PrivacyLedger.state=='held')):
        r=db.get(PrivacyStudy,led.study_id)
        if r and r.state in ('failed','cancelled'):led.state='refunded';led.updated_at=now()
        if r and r.state=='completed':led.state='confirmed';led.updated_at=now()
    ids=[r.id for r in db.scalars(select(PrivacyStudy).where(PrivacyStudy.state=='queued'))]
    db.commit();return ids
