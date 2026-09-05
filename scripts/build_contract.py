"""Authoritative contract builder. Integration owner only; no third-party deps."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = {}
def st(**kw): return {"type": "string", **kw}
def ref(n): return {"$ref": f"#/components/schemas/{n}"}
def arr(item): return {"type": "array", "items": item}
def enum(*xs): return st(enum=list(xs))
def obj(name, props, required=()):
    S[name] = {"type":"object", "additionalProperties":False, "properties":props, "required":list(required)}
    return ref(name)
def nullable(x): return {"anyOf":[x,{"type":"null"}]}
ID=st(format="uuid"); TS=st(format="date-time"); DATE=st(format="date"); INT={"type":"integer"}; BOOL={"type":"boolean"}; STRS=arr(st()); IDS=arr(ID)
BASE={"id":ID,"user_id":ID,"version":{**INT,"minimum":1},"created_at":TS,"updated_at":TS}
def entity(name, props, required=()): return obj(name,{**BASE,**props},list(BASE)+list(required))
obj("Error",{"code":st(),"message":st(),"trace_id":st(),"details":{"type":"object","additionalProperties":True}},["code","message","trace_id","details"])
obj("User",{"id":ID,"email":st(),"name":st(),"csrf_token":st(),"ai_mode":enum("fake","compatible")},["id","email","name","csrf_token","ai_mode"])
obj("Usage",{"daily_generations":INT,"daily_limit":INT,"storage_bytes":INT,"storage_limit_bytes":INT,"global_model_calls":INT,"global_limit":INT},["daily_generations","daily_limit","storage_bytes","storage_limit_bytes","global_model_calls","global_limit"])
record={"type":enum("manual","blog","conversation","reflection","file"),"title":st(maxLength=300),"content":st(maxLength=200000),"occurred_at":nullable(DATE),"source_reflection_id":nullable(ID)}
obj("RecordCreate",record,["type","title","content"]); obj("RecordUpdate",{"version":INT,**record},["version"])
entity("Record",record,["type","title","content"])
event={"title":st(maxLength=300),"description":st(maxLength=20000),"event_type":st(),"started_at":nullable(DATE),"ended_at":nullable(DATE),"date_precision":enum("day","month","year","unknown"),"tags":STRS,"user_verified":BOOL}
obj("EventCreate",event,["title"]);obj("EventUpdate",{"version":INT,**event},["version"])
entity("Event",{**event,"available_slots":INT,"total_slots":INT,"evidence_count":INT,"record_ids":IDS,"file_ids":IDS},["title"])
slot={"name":st(maxLength=200),"category":st(),"status":enum("AVAILABLE","PENDING","EXPECTED","MISSING","NOT_REQUIRED","ARCHIVED"),"expected_at":nullable(DATE),"required":BOOL,"linked_file_id":nullable(ID)}
obj("SlotCreate",slot,["name"]);obj("SlotUpdate",{"version":INT,**slot},["version"]);entity("FileSlot",{"event_id":ID,**slot},["event_id","name","status"])
obj("EventTemplate",{"id":st(),"name":st(),"description":st(),"slots":arr(ref("SlotCreate"))},["id","name","description","slots"])
obj("TemplateApply",{"slots":arr(ref("SlotCreate"))},["slots"])
obj("EventLink",{"record_id":nullable(ID),"file_id":nullable(ID)},[])
entity("File",{"filename":st(),"mime_type":st(),"size":INT,"checksum":st(),"status":enum("QUARANTINED","SCANNING","CLEAN","REJECTED","FAILED"),"error":nullable(st()),"record_id":nullable(ID)},["filename","mime_type","size","checksum","status"])
evidence={"source_type":enum("record","event","insight","reflection"),"source_id":ID,"source_version":INT,"excerpt":st(),"context":st(),"occurred_at":nullable(DATE),"status":enum("VALID","STALE","SOURCE_REMOVED")}
obj("EvidenceCreate",evidence,["source_type","source_id","source_version","excerpt"]);entity("Evidence",evidence,list(evidence))
entity("Observation",{"statement":st(),"evidence_refs":IDS,"status":st()},["statement","evidence_refs","status"])
hyp={"session_id":ID,"statement":st(),"evidence_refs":IDS,"counter_evidence_refs":IDS,"uncertainty":st(),"status":enum("PROPOSED","CONFIRMED","REVISED","REJECTED"),"source_removed":BOOL}
entity("Hypothesis",hyp,["session_id","statement","evidence_refs","counter_evidence_refs","uncertainty","status"])
obj("HypothesisFeedback",{"version":INT,"decision":enum("agree","partial","reject","explore"),"statement":st(maxLength=10000)},["version","decision"])
insight={"statement":st(),"evidence_refs":IDS,"source_hypothesis_id":nullable(ID),"valid_from":TS,"last_confirmed_at":TS,"supersedes":nullable(ID),"status":enum("ACTIVE","SUPERSEDED","WITHDRAWN","ARCHIVED","NEEDS_REVIEW")}
entity("Insight",insight,["statement","evidence_refs","valid_from","last_confirmed_at","status"])
obj("InsightUpdate",{"version":INT,"statement":st(),"status":enum("ACTIVE","WITHDRAWN","ARCHIVED")},["version"])
obj("FeedbackResult",{"hypothesis":ref("Hypothesis"),"insight":nullable(ref("Insight"))},["hypothesis","insight"])
rf={"session_id":ID,"record_id":nullable(ID),"question":st(),"core_conflict":st(),"evidence_refs":IDS,"counter_evidence_refs":IDS,"current_understanding":st(),"unknowns":STRS,"actions":STRS,"confirmed":BOOL,"source_removed":BOOL}
entity("Reflection",rf,["session_id","question","core_conflict","evidence_refs","counter_evidence_refs","current_understanding","unknowns","actions","confirmed"])
obj("ReflectionUpdate",{"version":INT,**{k:v for k,v in rf.items() if k not in ("session_id","record_id","source_removed")}},["version"])
obj("ArtifactSave",{"version":INT,"confirmed":BOOL},["version","confirmed"])
entity("Action",{"session_id":nullable(ID),"reflection_id":nullable(ID),"title":st(),"status":enum("PLANNED","IN_PROGRESS","COMPLETED","ABANDONED"),"result":st(),"result_record_id":nullable(ID)},["title","status","result"])
obj("ActionCreate",{"title":st(),"session_id":nullable(ID),"reflection_id":nullable(ID)},["title"])
obj("ActionUpdate",{"version":INT,"title":st(),"status":enum("PLANNED","IN_PROGRESS","COMPLETED","ABANDONED"),"result":st()},["version"])
intent=enum("INFORMATION","EXPLORATION","CONFLICT","VALIDATION","ACTION","REFLECTION")
stage=enum("UNDERSTAND","RETRIEVE","EXPLORE","IDENTIFY","VERIFY","SYNTHESIZE","VISUALIZE","ACTION","RECORD")
entity("Session",{"title":st(),"intent":nullable(intent),"stage":stage,"consecutive_questions":INT},["title","stage","consecutive_questions"])
obj("SessionCreate",{"title":st(maxLength=300)},[])
entity("Message",{"session_id":ID,"role":enum("user","assistant"),"content":st(),"run_id":nullable(ID),"ui":arr({"type":"object","additionalProperties":True}),"complete":BOOL},["session_id","role","content","ui","complete"])
obj("MessageCreate",{"content":st(minLength=1,maxLength=20000)},["content"])
obj("MessageAccepted",{"message_id":ID,"run_id":ID,"stream_url":st()},["message_id","run_id","stream_url"])
entity("Run",{"session_id":ID,"message_id":ID,"status":enum("QUEUED","RUNNING","COMPLETED","FAILED","CANCELLED"),"error":nullable(st()),"trace_id":st()},["session_id","message_id","status","trace_id"])
obj("StreamEvent",{"schema_version":enum("1.0"),"event_id":ID,"run_id":ID,"sequence":INT,"occurred_at":TS,"type":enum("stage.changed","text.delta","ui.ready","artifact.ready","run.completed","run.failed","run.cancelled"),"payload":{"type":"object","additionalProperties":True}},["schema_version","event_id","run_id","sequence","occurred_at","type","payload"])
obj("ContextItem",{"id":ID,"source_type":st(),"source_id":ID,"source_version":INT,"title":st(),"excerpt":st(),"occurred_at":nullable(DATE),"confirmed":BOOL,"status":st(),"counter_evidence":BOOL},["id","source_type","source_id","source_version","title","excerpt","confirmed","status"])
obj("Health",{"status":st(),"version":st()},["status","version"])
obj("DevLogin",{"email":st(),"name":st()},["email"])
for n in ["Record","Event","FileSlot","File","Evidence","Observation","Hypothesis","Insight","Reflection","Action","Session","Message","EventTemplate"]:
    obj(n+"Page",{"items":arr(ref(n)),"next_cursor":nullable(st())},["items","next_cursor"])

paths={}
def op(path,method,response=None,body=None,status=200,idem=False,binary=False):
    params=[]
    import re
    for p in re.findall(r"\{(.*?)\}",path): params.append({"name":p,"in":"path","required":True,"schema":ID})
    if idem:params.append({"name":"Idempotency-Key","in":"header","required":True,"schema":st()})
    if method=="get" and response and response.endswith("Page"):
        params += [{"name":q,"in":"query","schema":st()} for q in ("cursor","q","view","event_id","session_id","status")]
        params.append({"name":"limit","in":"query","schema":{**INT,"default":30,"minimum":1,"maximum":100}})
    if method not in ("get",) and not path.startswith("/auth/"):
        params.append({"name":"X-CSRF-Token","in":"header","required":True,"schema":st()})
    responses={str(status):{"description":"Success"}}
    if response:responses[str(status)]["content"]={"application/json":{"schema":ref(response)}}
    if binary:responses[str(status)]["content"]={"application/octet-stream":{"schema":st(format="binary")}}
    for code in (400,401,403,404,409,422,429,503): responses[str(code)]={"description":"Error","content":{"application/json":{"schema":ref("Error")}}}
    operation={"operationId":method+"_"+path.replace("/","_").replace("{","").replace("}",""),"parameters":params,"responses":responses,"security":[{"sessionCookie":[]}]}
    if body:operation["requestBody"]={"required":True,"content":{"application/json":{"schema":ref(body)}}}
    paths.setdefault("/api/v1"+path,{})[method]=operation
op("/health","get","Health");op("/auth/google","get",status=302);op("/auth/google/callback","get",status=302);op("/auth/logout","post",status=204);op("/auth/dev","post","User","DevLogin")
op("/me","get","User");op("/me/usage","get","Usage");op("/me/export","get",binary=True);op("/me","delete",status=202)
for path,n in [("records","Record"),("blogs","Record"),("events","Event"),("actions","Action")]:
    op('/'+path,"get",n+"Page");op('/'+path,"post",n,n+"Create",201)
    op('/'+path+'/{id}',"get",n);op('/'+path+'/{id}',"patch",n,n+"Update");op('/'+path+'/{id}',"delete",status=204)
op("/event-templates","get","EventTemplatePage");op("/events/{id}/template","post","FileSlotPage","TemplateApply",201)
op("/events/{id}/links","post","Event","EventLink");op("/events/{id}/links","delete","Event","EventLink")
op("/events/{id}/file-slots","get","FileSlotPage");op("/events/{id}/file-slots","post","FileSlot","SlotCreate",201)
op("/events/{id}/file-slots/{slot_id}","patch","FileSlot","SlotUpdate");op("/events/{id}/file-slots/{slot_id}","delete",status=204)
op("/files","get","FilePage");op("/files","post","File",status=202)
paths['/api/v1/files']['post']['requestBody']={"required":True,"content":{"multipart/form-data":{"schema":{"type":"object","properties":{"file":st(format="binary")},"required":["file"]}}}}
op("/files/{id}","get","File");op("/files/{id}/download","get",binary=True);op("/files/{id}","delete",status=204)
for path,n in [("evidences","Evidence"),("observations","Observation"),("hypotheses","Hypothesis"),("insights","Insight"),("reflections","Reflection")]:
    op('/'+path,"get",n+"Page");op('/'+path+'/{id}',"get",n)
op("/evidences","post","Evidence","EvidenceCreate",201)
op("/hypotheses/{id}/feedback","post","FeedbackResult","HypothesisFeedback",idem=True)
op("/insights/{id}","patch","Insight","InsightUpdate")
op("/reflections/{id}","patch","Reflection","ReflectionUpdate")
op("/reflections/{id}/blog","post","Record",status=201,idem=True)
op("/sessions","get","SessionPage");op("/sessions","post","Session","SessionCreate",201);op("/sessions/{id}","get","Session")
op("/sessions/{id}/messages","get","MessagePage");op("/sessions/{id}/messages","post","MessageAccepted","MessageCreate",202,True)
op("/sessions/{id}/artifact","get","Reflection");op("/sessions/{id}/artifact","post","Reflection",status=201,idem=True);op("/sessions/{id}/artifact","put","Reflection","ArtifactSave",idem=True)
op("/runs/{id}","get","Run");op("/runs/{id}/cancel","post","Run")
op("/runs/{id}/events","get")
paths['/api/v1/runs/{id}/events']['get']['parameters'].append({"name":"Last-Event-ID","in":"header","schema":st()})
paths['/api/v1/runs/{id}/events']['get']['responses']['200']['content']={"text/event-stream":{"schema":st(),"example":"id: event-uuid\nevent: run.completed\ndata: {\"schema_version\":\"1.0\"}\n\n"}}
document={"openapi":"3.1.0","info":{"title":"SocraLife API","version":"0.1.0"},"paths":paths,"components":{"securitySchemes":{"sessionCookie":{"type":"apiKey","in":"cookie","name":"socralife_session"}},"schemas":S}}
(ROOT/'contracts').mkdir(exist_ok=True)
(ROOT/'contracts/openapi.yaml').write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# The whitelist is independently usable by jsonschema/Ajv.
common={"schema_version":{"const":"1.0"},"title":st(maxLength=300)}
variants=[]
def ui(kind,props,required):
    variants.append({"type":"object","additionalProperties":False,"properties":{**common,"type":{"const":kind},**props},"required":["schema_version","type"]+required})
ui("text",{"text":st(maxLength=20000)},["text"])
ui("question",{"text":st(),"purpose":st(),"target_uncertainty":st()},["text","purpose","target_uncertainty"])
ui("choice_cards",{"choices":arr({"type":"object","additionalProperties":False,"properties":{"id":st(),"label":st(),"description":st()},"required":["id","label"]})},["choices"])
ui("evidence_card",{"evidence_refs":arr(st()),"text":st()},["evidence_refs","text"])
ui("hypothesis_card",{"hypothesis_id":nullable(st()),"version":INT,"statement":st(),"evidence_refs":arr(st()),"counter_evidence_refs":arr(st()),"uncertainty":st()},["hypothesis_id","statement","evidence_refs","uncertainty"])
ui("reflection_card",{"reflection_id":nullable(st()),"question":st(),"current_understanding":st(),"unknowns":STRS,"actions":STRS,"confirmed":BOOL},["question","current_understanding","unknowns","actions","confirmed"])
ui("timeline",{"items":arr({"type":"object","additionalProperties":False,"properties":{"label":st(),"date":nullable(st()),"evidence_refs":arr(st()),"confirmed":BOOL},"required":["label","date","evidence_refs","confirmed"]})},["items"])
ui("comparison",{"dimensions":STRS,"options":arr({"type":"object","additionalProperties":False,"properties":{"label":st(),"values":STRS,"evidence_refs":arr(st()),"confirmed":BOOL},"required":["label","values","evidence_refs","confirmed"]}),"time_range":st()},["dimensions","options","time_range"])
ui("action_card",{"action_id":nullable(st()),"text":st(),"purpose":st(),"review_prompt":st()},["text","purpose","review_prompt"])
uis={"$schema":"http://json-schema.org/draft-07/schema#","title":"UIComponent","oneOf":variants}
(ROOT/'contracts/ui.schema.json').write_text(json.dumps(uis,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
