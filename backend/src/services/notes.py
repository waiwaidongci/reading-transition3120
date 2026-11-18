from fastapi import HTTPException
from sqlalchemy import select
from ..models.note import Note
from ..models.privacy import PrivacyStudy
from ..utils.serialization import row
from .runs import get_run
from .audit import log
def _view(n):
    d=row(n);d['kind']='privacy' if n.privacy_id else 'plain';return d
def list_notes(db):return [_view(n) for n in db.scalars(select(Note).order_by(Note.id.desc()))]
def create_note(db,user,data):
    if bool(data.run_id)==bool(data.privacy_id):raise HTTPException(422,'说明必须且只能关联一个常规任务或隐私研究')
    if data.privacy_id:
        p=db.get(PrivacyStudy,data.privacy_id)
        if not p:raise HTTPException(404,'未找到隐私研究')
        if p.state!='completed':raise HTTPException(409,'只可为已完成结果提交说明')
        n=Note(privacy_id=p.id,title=data.title,body=data.body,state='draft',frozen_result=p.result,author=user.email)
    else:
        r=get_run(db,data.run_id)
        if r.state!='completed':raise HTTPException(409,'只可为已完成结果提交说明')
        n=Note(run_id=r.id,title=data.title,body=data.body,state='draft',frozen_result=r.result,author=user.email)
    db.add(n);db.flush();log(db,user,'note.created',n.id,n.title);db.commit();return _view(n)
def approve_note(db,user,id):
    n=db.get(Note,id)
    if not n:raise HTTPException(404,'未找到说明')
    if n.state!='draft':raise HTTPException(409,'该说明已经批准')
    n.state='approved';n.approved_by=user.email;log(db,user,'note.approved',n.id,n.title);db.commit();return _view(n)
