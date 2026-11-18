from sqlalchemy import Column,Integer,String,JSON,Text,ForeignKey,Numeric,UniqueConstraint
from ..config.database import Base
from ..config.settings import CONFIG
class PrivacyStudy(Base):
    __tablename__='privacy_studies'
    id=Column(Integer,primary_key=True)
    source_id=Column(Integer,ForeignKey(CONFIG['source_table']+'.id'),nullable=False)
    name=Column(String(160),nullable=False)
    state=Column(String(20),default='queued')
    parameters=Column(JSON,nullable=False)
    snapshot=Column(JSON,nullable=False)
    cache_key=Column(String(64),unique=True,nullable=False)
    result=Column(JSON,nullable=True)
    error=Column(Text,default='')
    created_at=Column(String(40),nullable=False)
class PrivacyLedger(Base):
    __tablename__='privacy_ledger'
    __table_args__=(UniqueConstraint('cache_key',name='uq_privacy_ledger_key'),)
    id=Column(Integer,primary_key=True)
    study_id=Column(Integer,ForeignKey('privacy_studies.id'),unique=True,nullable=False)
    cache_key=Column(String(64),nullable=False)
    amount=Column(Numeric(12,4),nullable=False)
    state=Column(String(20),nullable=False,default='held')
    created_at=Column(String(40),nullable=False)
    updated_at=Column(String(40),nullable=False)
class PrivacyAccount(Base):
    __tablename__='privacy_account'
    id=Column(Integer,primary_key=True)
    total=Column(Numeric(12,4),nullable=False)
