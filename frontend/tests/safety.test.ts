import {describe,it,expect,vi,afterEach} from 'vitest';
import {validUi,validatedUi} from '../src/app/ui-validation';
import {Api,parseSse} from '../src/app/api';
const event=(sequence:number,type='text.delta')=>({schema_version:'1.0',event_id:'event-'+sequence,run_id:'run',sequence,occurred_at:'2026-09-05T00:00:00Z',type,payload:{text:'hello'}});
describe('UI schema safety',()=>{
 it('accepts canonical choices and rejects arbitrary properties',()=>{expect(validUi({schema_version:'1.0',type:'choice_cards',choices:[{id:'a',label:'A'}]})).toBe(true);expect(validUi({schema_version:'1.0',type:'text',text:'safe',html:'<script>'})).toBe(false);});
 it('requires question rationale and hypothesis uncertainty',()=>{expect(validUi({schema_version:'1.0',type:'question',text:'why'})).toBe(false);expect(validUi({schema_version:'1.0',type:'hypothesis_card',statement:'guess',hypothesis_id:null,evidence_refs:[]})).toBe(false);});
 it('rejects future versions and keeps only whitelisted components',()=>{expect(validatedUi([{schema_version:'2.0',type:'text',text:'no'},{schema_version:'1.0',type:'text',text:'yes'}])).toHaveLength(1);});
});
describe('Authenticated API and durable SSE',()=>{
 afterEach(()=>vi.unstubAllGlobals());
 it('parses multiline data and ignores heartbeat comments',()=>{expect(parseSse(': heartbeat')).toBeNull();expect(parseSse('event: text.delta\r\ndata: '+JSON.stringify(event(1)))).toEqual(event(1));expect(()=>parseSse('data: {"schema_version":"2"}')).toThrow();});
 it('sends CSRF and idempotency only on authorized mutations',async()=>{const fetch=vi.fn().mockResolvedValue(new Response('{}'));vi.stubGlobal('fetch',fetch);const api=new Api();api.user.set({id:'u',name:'U',email:'u@x',csrf_token:'csrf',ai_mode:'fake'});await api.request('/sessions','POST',{title:'hi'},'unique');expect(fetch.mock.calls[0][1]).toMatchObject({credentials:'same-origin',headers:{'X-CSRF-Token':'csrf','Idempotency-Key':'unique'}});});
 it('reconnects with Last-Event-ID, deduplicates replay and never submits a new generation',async()=>{const frames=(events:unknown[])=>new Response(events.map(e=>'data: '+JSON.stringify(e)+'\n\n').join(''));const fetch=vi.fn().mockResolvedValueOnce(frames([event(1)])).mockResolvedValueOnce(frames([event(1),event(2,'run.completed')]));vi.stubGlobal('fetch',fetch);const received:number[]=[];await new Api().stream('/api/v1/runs/run/events',e=>received.push(e.sequence),new AbortController().signal);expect(received).toEqual([1,2]);expect(fetch.mock.calls[1][1].headers).toEqual({'Last-Event-ID':'event-1'});expect(fetch.mock.calls.every(c=>!c[1].method)).toBe(true);});
 it('rejects external stream URLs',async()=>{await expect(new Api().stream('https://evil.test',()=>{},new AbortController().signal)).rejects.toThrow();});
});
