import hashlib,hmac,json
import numpy as np
from ..config.settings import CONFIG,PRIVACY_SECRET
def privacy_chapters():return CONFIG['privacy']['chapters']
def cache_key_for(records,parameters):
    canon={'v':1,'chapters':privacy_chapters(),'parameters':parameters,'records':sorted([r['values']['session'],r['values']['path']] for r in records)}
    return hashlib.sha256(json.dumps(canon,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def _noise_seed(cache_key):
    digest=hmac.new(PRIVACY_SECRET.encode(),('privacy-noise:'+cache_key).encode(),hashlib.sha256).digest()
    return int.from_bytes(digest[:8],'big')
def calculate_private(records,parameters,cache_key):
    chapters=privacy_chapters();index={c:i for i,c in enumerate(chapters)};k=len(chapters)
    counts=np.zeros((k,k));sessions=set()
    for r in records:
        v=r['values'];sid=v['session']
        if sid in sessions:raise ValueError('会话编号重复，请将一个完整会话保存在同一行')
        sessions.add(sid);path=[s.strip() for s in v['path'].split('>')]
        if len(path)<2:continue
        a,b=path[0],path[1]
        if a in index and b in index:counts[index[a],index[b]]+=1
    epsilon=parameters['epsilon'];scale=1/epsilon
    rng=np.random.default_rng(_noise_seed(cache_key))
    clipped=np.maximum(counts+rng.laplace(0,scale,(k,k)),0)
    outgoing=clipped.sum(axis=1);incoming=clipped.sum(axis=0);total=float(clipped.sum())
    rows=[]
    for i,a in enumerate(chapters):
        for j,b in enumerate(chapters):
            count=float(clipped[i,j])
            if count<parameters['min_count']:continue
            prob=count/outgoing[i] if outgoing[i]>0 else 0
            base=float(incoming[j])/total if total>0 else 0
            rows.append({'from':a,'to':b,'count':round(count,4),'conditional_probability':round(prob,6),'target_base_rate':round(base,6),'lift':round(prob/base,6) if base>0 else 0,'support':round(count/total,6) if total>0 else 0})
    rows.sort(key=lambda r:(-r['lift'],-r['count'],r['from'],r['to']));rows=rows[:parameters['top_n']]
    return {'summary':[{'label':'独立会话','value':len(records)},{'label':'噪声接续边合计','value':round(total,4)},{'label':'达标规则','value':len(rows)},{'label':'登记章节','value':k}],
        'rows':rows,'columns':['from','to','count','conditional_probability','target_base_rate','lift','support'],
        'chart':[{'label':r['from']+' → '+r['to'],'value':r['lift']} for r in rows[:12]],
        'target_counts':{c:round(float(incoming[i]),4) for i,c in enumerate(chapters)},
        'outgoing_counts':{c:round(float(outgoing[i]),4) for i,c in enumerate(chapters)},
        'explanation':'隐私保护口径：'+CONFIG['privacy']['noise_rule'],
        'privacy':{'epsilon':epsilon,'noise_scale':round(scale,6),'chapters':chapters,'cache_key':cache_key,'rule':CONFIG['privacy']['noise_rule']},
        'checksum':hashlib.sha256(json.dumps([r['values'] for r in records],sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'seed':None}
