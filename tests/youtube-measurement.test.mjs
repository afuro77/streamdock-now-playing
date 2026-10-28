import {strict as assert} from 'node:assert';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const root=new URL('../extensions/youtube-lcd/',import.meta.url);
const source=await readFile(new URL('measurement.js',root),'utf8');
const {FrameRateMeasurement,measureFrameRate}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const sample=(seconds=0,extra={})=>({sampleTime:100+seconds,instance:'one',frames:100+Math.round(seconds*20),target:30,configuredTarget:30,enabled:true,fresh:true,...extra});
let m=new FrameRateMeasurement();m.sample(sample());let result=m.sample(sample(5));
assert.equal(result.done,true);assert.equal(result.fps,20);assert.equal(result.frames,100);assert.equal(result.target,30);
for(const bad of [sample(1,{enabled:false}),sample(1,{fresh:false}),sample(1,{instance:'two'}),sample(1,{frames:0}),sample(-1),sample(1,{target:60,configuredTarget:60}),sample(1,{target:60}),{}]){
 m=new FrameRateMeasurement();m.sample(sample());assert.throws(()=>m.sample(bad));
}
m=new FrameRateMeasurement();m.sample(sample());result=m.sample(sample(8));assert.equal(result.seconds,8);assert.equal(result.fps,20);
let time=0;result=await measureFrameRate({getSample:async()=>sample(time),wait:async()=>{time+=.5;}});
assert.equal(result.seconds,5);assert.equal(result.target,30);
await assert.rejects(()=>measureFrameRate({getSample:async()=>sample(),isCancelled:()=>true}),/中止/);

// Run real options handlers with a minimal DOM and accelerated sample clock.
class Element{
 constructor(){this.value='';this.disabled=false;this.textContent='';this.style={};this.children=[];}
 append(e){this.children.push(e);}replaceChildren(){this.children=[];}
}
const elements=new Map();const element=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
let mode='normal',cancelOnWait=false,persistentWrites=0,timeNow=0;
const runtime={sendMessage:async message=>{
 assert.equal(message.type,'fps-sample');
 return sample(timeNow,mode==='inactive'?{enabled:false}:mode==='changed'&&timeNow>0?{target:60,configuredTarget:60}:{});
}};
const context=vm.createContext({document:{querySelector:element,createElement:()=>new Element()},Date,parseSession:()=>({}),
 chrome:{runtime,storage:{local:{get:async()=>({targetFps:30}),set:async()=>persistentWrites++,remove:async()=>{}}}},
 measureFrameRate:args=>measureFrameRate({...args,wait:async()=>{timeNow+=.5;if(cancelOnWait)element('#cancel-measure').onclick();}})});
vm.runInContext((await readFile(new URL('options.js',root),'utf8')).replace(/^import .*;\r?\n/gm,''),context);
await Promise.resolve();
await element('#measure-fps').onclick();
assert.equal(element('#measurement-results').children.length,1);
assert.equal(element('#measurement-results').children[0].children[1].textContent,'30 コマ／秒');
assert.equal(element('#measurement-results').children[0].children[2].textContent,'20.0');
assert.equal(element('#save-fps').disabled,false);assert.equal(persistentWrites,0);
for(const failure of ['inactive','changed']){
 mode=failure;timeNow=0;await element('#measure-fps').onclick();
 assert.equal(element('#measurement-results').children.length,1);
}
mode='normal';cancelOnWait=true;timeNow=0;await element('#measure-fps').onclick();
assert.equal(element('#measurement-results').children.length,1);cancelOnWait=false;
for(let i=0;i<12;i++){timeNow=0;await element('#measure-fps').onclick();}
assert.equal(element('#measurement-results').children.length,10);assert.equal(persistentWrites,0);
element('#clear-measurements').onclick();assert.equal(element('#measurement-results').children.length,0);
const html=await readFile(new URL('options.html',root),'utf8');
assert.ok(html.includes('約5秒'));assert.ok(html.includes('120 fps'));assert.ok(!html.includes('約18.5'));
console.log('PASS: current-setting measurement, monotonic elapsed time, interruption detection, cancellation, real options handlers, memory-only bounded history and 120fps choices');
