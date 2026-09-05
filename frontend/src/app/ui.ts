import { Component, input, output, computed } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { UIComponent } from './contracts';
import { validUi } from './ui-validation';
import { ChartComponent } from './chart';
@Component({selector:'app-ui',standalone:true,imports:[MatButtonModule,ChartComponent],template:`
@if (card(); as c) {<section class="generated-card" [attr.data-type]="c.type">
@if(c.title){<h3>{{c.title}}</h3>}
@switch(c.type){
@case('text'){<p class="preserve">{{c.text}}</p>}
@case('question'){<p class="question">{{c.text}}</p><details><summary>這個問題想釐清什麼？</summary><p>{{c.purpose}}</p><small>{{c.target_uncertainty}}</small></details>}
@case('choice_cards'){<div class="choices">@for(choice of c.choices;track choice.id){<button mat-stroked-button (click)="choose.emit(choice.label)">{{choice.label}}<small>{{choice.description}}</small></button>}</div>}
@case('evidence_card'){<span class="eyebrow">原始脈絡</span><p>{{c.text}}</p><button mat-button (click)="why.emit(c.evidence_refs)">查看來源 ↗</button>}
@case('hypothesis_card'){<span class="badge">AI 假設 · 等待你確認</span><h3>{{c.statement}}</h3><p class="muted">{{c.uncertainty}}</p><button mat-button (click)="why.emit([...c.evidence_refs, ...(c.counter_evidence_refs ?? [])])">為什麼？查看證據與反證 ↗</button>@if(c.hypothesis_id){<div class="button-row"><button mat-flat-button (click)="feedback.emit({id:c.hypothesis_id,version:c.version??1,decision:'agree',statement:c.statement})">符合我的理解</button><button mat-stroked-button (click)="feedback.emit({id:c.hypothesis_id,version:c.version??1,decision:'partial',statement:c.statement})">部分符合，修正</button><button mat-button (click)="feedback.emit({id:c.hypothesis_id,version:c.version??1,decision:'reject',statement:c.statement})">不符合</button><button mat-button (click)="feedback.emit({id:c.hypothesis_id,version:c.version??1,decision:'explore',statement:c.statement})">繼續探索</button></div>}}
@case('reflection_card'){<span class="badge">{{c.confirmed?'已確認成果':'整理草稿 · 尚未確認'}}</span><h3>{{c.question}}</h3><p>{{c.current_understanding}}</p><h4>仍然未知</h4><ul>@for(item of c.unknowns;track $index){<li>{{item}}</li>}</ul><h4>可以試試</h4><ul>@for(item of c.actions;track $index){<li>{{item}}</li>}</ul>@if(c.reflection_id){<button mat-button (click)="openReflection.emit(c.reflection_id)">編輯與保存</button>}}
@case('timeline'){<app-chart [options]="timeline(c)" label="探索時間軸"/><ol>@for(item of c.items;track $index){<li><b>{{item.date??'日期未知'}} · {{item.label}}</b><span class="badge">{{item.confirmed?'已確認':'待確認'}}</span><button mat-button (click)="why.emit(item.evidence_refs)">來源</button></li>}</ol>}
@case('comparison'){<p class="muted">{{c.time_range}}</p><div class="table-scroll"><table><thead><tr><th>比較面向</th>@for(option of c.options;track $index){<th>{{option.label}} <small>{{option.confirmed?'已確認':'待確認'}}</small></th>}</tr></thead><tbody>@for(dimension of c.dimensions;track $index;let i=$index){<tr><th>{{dimension}}</th>@for(option of c.options;track $index){<td>{{option.values[i]??'未知'}}</td>}</tr>}</tbody></table></div>@for(option of c.options;track $index){<button mat-button (click)="why.emit(option.evidence_refs)">{{option.label}}的來源</button>}}
@case('action_card'){<span class="eyebrow">下一個小行動</span><h3>{{c.text}}</h3><p>{{c.purpose}}</p><p class="muted">回顧時：{{c.review_prompt}}</p><button mat-stroked-button (click)="action.emit(c.text)">加入行動清單</button>}
}</section>} @else {<p role="status" class="muted">這則互動內容格式不正確，已略過。</p>}
`,styles:[`.generated-card{padding:22px;border:1px solid #d7e2da;border-radius:14px;background:#f5f8f2;margin:14px 0}.generated-card h3{margin:12px 0}.choices{display:flex;gap:12px;flex-wrap:wrap}.choices button{height:auto;padding:14px}.choices small{display:block}`]})
export class UiComponent {
  value=input.required<unknown>(); card=computed(()=>validUi(this.value())?this.value() as UIComponent:null);
  choose=output<string>();why=output<string[]>();feedback=output<{id:string;version:number;decision:'agree'|'partial'|'reject'|'explore';statement:string}>();openReflection=output<string>();action=output<string>();
  timeline(c:Extract<UIComponent,{type:'timeline'}>){return {grid:{left:20,right:20,top:20,bottom:60},xAxis:{type:'category',data:c.items.map(i=>i.date??'日期未知'),axisLabel:{rotate:25}},yAxis:{show:false,min:0,max:2},series:[{type:'scatter',symbolSize:16,data:c.items.map(()=>1),itemStyle:{color:'#23796c'}}]};}
}
