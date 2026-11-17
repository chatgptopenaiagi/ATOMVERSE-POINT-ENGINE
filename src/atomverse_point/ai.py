"""Optional loopback Ollama interpreter. Never executes commands or accesses the OS."""
import json
import time
import urllib.parse
import urllib.request
from .model import validate_command

COMMAND_SCHEMA = {
    'type':'object','additionalProperties':False,
    'properties':{
        'action':{'enum':['teleport','translate','velocity','appearance','collision','trajectory','pause','resume','stop','reset']},
        'position':{'type':'array','items':{'type':'number'},'minItems':3,'maxItems':3},
        'delta':{'type':'array','items':{'type':'number'},'minItems':3,'maxItems':3},
        'velocity':{'type':'array','items':{'type':'number'},'minItems':3,'maxItems':3},
        'color':{'type':'array','items':{'type':'number','minimum':0,'maximum':1},'minItems':4,'maxItems':4},
        'radius':{'type':'number','minimum':.001,'maximum':1e6},
        'mode':{'enum':['pass','stop','reflect','slide']},
        'trajectory':{'type':'object','additionalProperties':False,'properties':{
            'kind':{'enum':['line','circle','spiral','helix']},'target':{'type':'array','items':{'type':'number'},'minItems':3,'maxItems':3},
            'duration':{'type':'number','minimum':.001,'maximum':86400},'amplitude':{'type':'number','minimum':0,'maximum':1e6},
            'frequency':{'type':'number','minimum':-100,'maximum':100},'pitch':{'type':'number'},'growth':{'type':'number'}},'required':['kind']}
    },'required':['action']
}

def propose(text,state,endpoint='http://127.0.0.1:11434',model='qwen3.8:27b',num_gpu=0,timeout=90):
    url=urllib.parse.urlparse(endpoint)
    if url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost','::1') or url.username or url.password or url.query or url.fragment:
        raise ValueError('AI endpoint must be an unauthenticated local HTTP endpoint')
    if not isinstance(text,str) or not 1<=len(text)<=4096: raise ValueError('Request length must be 1 to 4096 characters')
    payload={'model':model,'stream':False,'think':False,'format':COMMAND_SCHEMA,'keep_alive':'5m',
             'options':{'temperature':0,'num_ctx':2048,'num_predict':160,'num_thread':4,'num_gpu':num_gpu},
             'messages':[{'role':'system','content':'Translate the operator request into exactly one JSON command. No prose. The phrase move TO coordinates ALWAYS means {"action":"teleport","position":[x,y,z]}. The phrase move BY a displacement means {"action":"translate","delta":[dx,dy,dz]}. Never use translate for an absolute destination, even if the point is at the origin. For example: Move to X 1 Y 2 Z 3 => {"action":"teleport","position":[1,2,3]}. Coordinates are dimensionless simulation units. Color is RGBA 0..1. Only use fields required by the action. Return to origin uses reset. Current point state: '+json.dumps({k:state[k] for k in ('position','radius','color','velocity','movement_mode','collision_mode')})},
                         {'role':'user','content':text}]}
    started=time.perf_counter()
    request=urllib.request.Request(endpoint.rstrip('/')+'/api/chat',json.dumps(payload).encode(),{'Content-Type':'application/json'})
    # No proxy routing or redirects to remote services.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs): raise ValueError('AI redirects are disabled')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(request,timeout=timeout) as response:
        raw=response.read(65537)
    if len(raw)>65536: raise ValueError('AI response exceeds size limit')
    data=json.loads(raw)
    command=validate_command(json.loads(data['message']['content']))
    return {'command':command,'model':model,'classification':'AI_INTERPRETATION',
            'elapsed_seconds':time.perf_counter()-started,'eval_count':data.get('eval_count'),
            'eval_duration_ns':data.get('eval_duration'),'load_duration_ns':data.get('load_duration')}
