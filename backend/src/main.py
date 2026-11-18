import os,logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text,inspect
from .config.database import Base,engine,Session
from .config.settings import CONFIG
from .models import user,source,record,run,note,audit,privacy
from .middlewares.errors import error_boundary
from .middlewares.rate_limit import rate_limit
from .routes import auth,sources,runs,notes,audit as audit_routes,privacy as privacy_routes
from .services.runs import queue
from .services.privacy import account_view,recover,QUEUE_KEY
def migrate():
    insp=inspect(engine);note_table=CONFIG['note_table']
    if note_table not in insp.get_table_names():return
    cols={c['name']:c for c in insp.get_columns(note_table)}
    with engine.begin() as c:
        if 'privacy_id' not in cols:c.execute(text(f'ALTER TABLE {note_table} ADD COLUMN privacy_id INT NULL'))
        if cols.get('run_id') and not cols['run_id']['nullable'] and engine.dialect.name=='mysql':
            c.execute(text(f'ALTER TABLE {note_table} MODIFY run_id INT NULL'))
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    migrate()
    with Session() as db:
        account_view(db);db.commit()
        for id in recover(db):
            try:queue.rpush(QUEUE_KEY,id)
            except Exception:logging.exception('privacy requeue unavailable')
    if os.getenv('SEED_DEMO','true')=='true':
        try:
            from scripts.seed_demo import seed
            seed()
        except Exception:logging.exception('seed failed; service remains available')
    yield
app=FastAPI(title=CONFIG['title'],lifespan=lifespan)
app.middleware('http')(error_boundary)
app.middleware('http')(rate_limit)
for router in (auth.router,sources.router,runs.router,notes.router,audit_routes.router,privacy_routes.router):app.include_router(router)
@app.get('/health')
def health():
    with engine.connect() as c:c.execute(text('SELECT 1'))
    queue.ping();return {'status':'ok'}
@app.get('/catalog')
def catalog():return CONFIG
