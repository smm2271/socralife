import { Component, ElementRef, input, effect, viewChild, OnDestroy } from '@angular/core';
import * as echarts from 'echarts/core';
import { GraphChart, ScatterChart } from 'echarts/charts';
import { TooltipComponent, GridComponent, TitleComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
echarts.use([GraphChart, ScatterChart, TooltipComponent, GridComponent, TitleComponent, CanvasRenderer]);
@Component({selector:'app-chart',standalone:true,template:'<div #canvas class="chart" role="img" [attr.aria-label]="label()"></div>',styles:['.chart{width:100%;height:280px}']})
export class ChartComponent implements OnDestroy {
  options=input<echarts.EChartsCoreOption>({}); label=input(''); canvas=viewChild<ElementRef<HTMLDivElement>>('canvas'); private chart?:echarts.ECharts; private observer?:ResizeObserver;
  constructor(){effect(()=>{const el=this.canvas(); const options=this.options(); if(!el)return; if(!this.chart){this.chart=echarts.init(el.nativeElement);this.observer=new ResizeObserver(()=>this.chart?.resize());this.observer.observe(el.nativeElement);}this.chart.setOption(options,true);});}
  ngOnDestroy(){this.observer?.disconnect();this.chart?.dispose();}
}
