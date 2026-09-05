import { Injectable, signal } from '@angular/core';
import type { User, StreamEvent } from './contracts';
export class ApiError extends Error { constructor(public status: number, public code: string, message: string, public traceId = '') { super(message); } }
export function parseSse(frame: string): StreamEvent | null {
  const data = frame.split(/\r?\n/).filter(l => l.startsWith('data:')).map(l => l.slice(5).trimStart()).join('\n');
  if (!data) return null;
  const event = JSON.parse(data) as StreamEvent;
  if (event.schema_version !== '1.0' || !event.event_id || !Number.isInteger(event.sequence)) throw new Error('無法辨識的串流資料');
  return event;
}
@Injectable({providedIn:'root'})
export class Api {
  readonly user = signal<User | null>(null);
  async request<T>(path: string, method = 'GET', body?: unknown, key?: string): Promise<T> {
    const headers: {[key:string]:string} = {};
    if (body !== undefined && !(body instanceof FormData)) headers['Content-Type'] = 'application/json';
    if (method !== 'GET') headers['X-CSRF-Token'] = this.user()?.csrf_token ?? '';
    if (key) headers['Idempotency-Key'] = key;
    const response = await fetch('/api/v1'+path, {method, credentials:'same-origin', headers, body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body)});
    if (!response.ok) { const e = await response.json().catch(()=>({})); throw new ApiError(response.status, e.code ?? 'REQUEST_FAILED', e.message ?? `請求失敗 (${response.status})`, e.trace_id ?? ''); }
    return response.status === 204 ? undefined as T : response.json();
  }
  async page<T>(path: string): Promise<T[]> {
    const all:T[]=[]; let cursor: string|null=null;
    do { const page: {items:T[]; next_cursor:string|null} = await this.request(path + (cursor ? `${path.includes('?')?'&':'?'}cursor=${encodeURIComponent(cursor)}` : '')); all.push(...page.items); cursor=page.next_cursor; } while(cursor);
    return all;
  }
  async me() { this.user.set(await this.request<User>('/me')); }
  async stream(url: string, onEvent:(e:StreamEvent)=>void, signal:AbortSignal) {
    if (!url.startsWith('/api/v1/runs/')) throw new Error('無效串流網址');
    let last=''; let sequence=0; let terminal=false;
    for(let attempt=0; attempt<5 && !terminal && !signal.aborted; attempt++) {
      try {
        const response=await fetch(url,{credentials:'same-origin',signal,headers:last?{'Last-Event-ID':last}:{}});
        if(!response.ok || !response.body) throw new Error(`串流連線失敗 (${response.status})`);
        const reader=response.body.getReader(); const decoder=new TextDecoder(); let buffer='';
        try { while(!terminal) { const {value,done}=await reader.read(); buffer+=decoder.decode(value,{stream:!done}); buffer=buffer.replace(/\r\n/g,'\n'); let boundary;
          while((boundary=buffer.indexOf('\n\n'))>=0) {const frame=buffer.slice(0,boundary); buffer=buffer.slice(boundary+2); const event=parseSse(frame); if(!event || event.sequence<=sequence) continue; last=event.event_id; sequence=event.sequence; onEvent(event); terminal=['run.completed','run.failed','run.cancelled'].includes(event.type); }
          if(done) break;
        }} finally {await reader.cancel().catch(()=>{});}
        if(terminal) return;
      } catch(error) { if(signal.aborted) return; if(attempt===4) throw error; }
      if(!terminal) await new Promise<void>((resolve)=>{const timer=setTimeout(resolve,Math.min(500*2**attempt,5000)); signal.addEventListener('abort',()=>{clearTimeout(timer);resolve();},{once:true});});
    }
    if(!terminal && !signal.aborted) throw new Error('連線中斷，請重新開啟此探索以查看進度。');
  }
}
