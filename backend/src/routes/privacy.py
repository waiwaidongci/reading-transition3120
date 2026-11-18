from fastapi import APIRouter,Depends
from ..config.database import db_session
from ..schemas.privacy import PrivacyInput
from ..services.auth import current_user,writer
from ..services.export import privacy_csv
from ..controllers.privacy import PrivacyController as C
router=APIRouter()
@router.get('/privacy/account')
def account(db=Depends(db_session),u=Depends(current_user)):return C.account(db)
@router.get('/privacy')
def studies(db=Depends(db_session),u=Depends(current_user)):return C.list(db)
@router.post('/privacy')
def create(data:PrivacyInput,db=Depends(db_session),u=Depends(writer)):return C.create(db,u,data)
@router.get('/privacy/{id}')
def detail(id:int,db=Depends(db_session),u=Depends(current_user)):return C.get(db,id)
@router.post('/privacy/{id}/cancel')
def cancel(id:int,db=Depends(db_session),u=Depends(writer)):return C.cancel(db,u,id)
@router.get('/privacy/{id}/export')
def export(id:int,db=Depends(db_session),u=Depends(current_user)):return privacy_csv(db,id)
