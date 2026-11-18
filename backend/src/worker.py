import json,time,logging
from redis import Redis
from sqlalchemy import select
from .config.database import Session
from .config.settings import REDIS_URL,ARTIFACT_DIR
from .models.run import Run
from .models.privacy import PrivacyStudy
from .models import source,record,user,note,audit
from .services.algorithm import calculate
from .services.privacy_algorithm import calculate_private
from .services.privacy import finish_study,fail_study,recover,QUEUE_KEY
from .services.audit import log
from .services.export import csv_response
queue=Redis.from_url(REDIS_URL)
ARTIFACT_DIR.mkdir(parents=True,exist_ok=True)
def execute(id):
    with Session() as db:
        r=db.get(Run,id)
        if not r or r.state!='queued':return
        r.state='running';db.commit()
        try:
            result=calculate(r.snapshot['records'],r.parameters)
            json.dumps(result,allow_nan=False)
            r.result=result;r.state='completed'
            response=csv_response(result,'run.csv')
            (ARTIFACT_DIR/f'run-{r.id}.csv').write_bytes(response.body)
            log(db,'worker','run.completed',r.id)
        except Exception as e:
            logging.exception('analysis failed');r.state='failed';r.error=str(e)[:2000]
            log(db,'worker','run.failed',r.id,r.error)
        db.commit()
def execute_privacy(id):
    with Session() as db:
        r=db.get(PrivacyStudy,id)
        if not r or r.state!='queued':return
        r.state='running';db.commit()
        try:
            result=calculate_private(r.snapshot['records'],r.parameters,r.cache_key)
            json.dumps(result,allow_nan=False)
            if finish_study(db,r.id,result):
                try:
                    response=csv_response(result,'privacy.csv')
                    (ARTIFACT_DIR/f'privacy-{r.id}.csv').write_bytes(response.body)
                except Exception:logging.exception('privacy artifact write failed; result already confirmed')
        except Exception as e:
            logging.exception('privacy analysis failed');fail_study(db,id,str(e))
def recover_interrupted():
    with Session() as db:
        for id in recover(db):
            try:queue.rpush(QUEUE_KEY,id)
            except Exception:logging.exception('privacy requeue unavailable')
def main():
    recover_interrupted()
    while True:
        (ARTIFACT_DIR/'heartbeat').write_text(str(time.time()))
        value=queue.blpop(['analysis:queue',QUEUE_KEY],timeout=2)
        if value:
            key,id=value[0].decode(),int(value[1])
            if key==QUEUE_KEY:execute_privacy(id)
            else:execute(id)
if __name__=='__main__':main()
