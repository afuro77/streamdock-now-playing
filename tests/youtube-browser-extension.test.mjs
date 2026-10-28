import {strict as assert} from 'node:assert';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const root=new URL('../extensions/youtube-lcd/',import.meta.url);
const protocol=await readFile(new URL('protocol.js',root),'utf8');
const helpers=await import('data:text/javascript;base64,'+Buffer.from(protocol).toString('base64'));
let listener,tabURL='https://www.youtube.com/',navigations=0,failed=false;
const store={},posts=[];
const command={id:'test-command',url:'https://www.youtube.com/watch?v=abcdefghijk',tab:9};
const chrome={runtime:{id:'test',getURL:p=>'chrome-extension://test/'+p,onMessage:{addListener:f=>listener=f}},
  storage:{local:{get:async()=>({}),set:async()=>{}},session:{get:async()=>({...store}),set:async value=>Object.assign(store,value),remove:async key=>{delete store[key];}}},
  action:{onClicked:{addListener(){}},setBadgeText:async()=>{},setTitle:async()=>{}},
  tabs:{onRemoved:{addListener(){}},get:async()=>({id:9,url:tabURL}),sendMessage:async(id,message)=>{assert.ok(['fetch-channel','fetch-channel-more','fetch-list-more'].includes(message.type));return {items:[{url:'https://www.youtube.com/watch?v=12345678901',title:'Channel video'}],hasMore:true};},update:async(id,props)=>{if(failed)throw Error('tab gone');assert.equal(id,9);if(props.url){tabURL=props.url;navigations++;}}}
};
const windowChanges=[];let windowState='minimized';
const previousGet=chrome.tabs.get;
chrome.tabs.get=async id=>({...await previousGet(id),windowId:7});
chrome.windows={get:async id=>{assert.equal(id,7);return {state:windowState};},update:async(id,props)=>{assert.equal(id,7);windowChanges.push(props);if(props.state)windowState=props.state;}};
const context=vm.createContext({...helpers,ensureReader:async()=>({reader:true}),chrome,URL,AbortSignal,setTimeout,clearTimeout,Uint8Array,Date,
  fetch:async(url,options={})=>{
    if(url.startsWith('chrome-extension:'))return {json:async()=>({url:'http://127.0.0.1:8766/#'+'a'.repeat(43)})};
    if(url.endsWith('/state'))return {ok:true,json:async()=>({enabled:false,browse:true,command})};
    if(url.endsWith('/diagnostics'))return {ok:true,json:async()=>({sample_time:10,instance:'test-instance',sources:{extension:200},target_fps:12,enabled:true,fresh:true})};
    if(url.endsWith('/frame')){posts.push({url,headers:options.headers});return {ok:true,status:204};}
    if(options.body)posts.push({url,data:JSON.parse(options.body)});
    return {ok:true,status:204};
  }});
const worker=(await readFile(new URL('worker.js',root),'utf8')).replace(/^import .*;\r?\n/gm,'');
vm.runInContext(worker,context);
const send=(message,sender={tab:{id:9},url:'https://www.youtube.com/'})=>new Promise(resolve=>{assert.equal(listener(message,sender,resolve),true);});
const measured=await send({type:'fps-sample'},{id:'test',url:chrome.runtime.getURL('options.html')});
assert.equal(measured.frames,200);assert.equal(measured.configuredTarget,12);assert.equal(measured.sampleTime,10);
assert.equal('token' in measured,false);
assert.equal(listener({type:'fps-sample'},{id:'other',url:chrome.runtime.getURL('options.html')},()=>{}),false);
await Promise.all([send({type:'state',pageURL:'https://www.youtube.com/'}),send({type:'state',pageURL:'https://www.youtube.com/'})]);
assert.equal(navigations,1);assert.equal(store.selectedTab,9);
assert.equal(windowChanges[0].state,'normal');assert.equal(windowChanges[1].focused,true);
store.pendingPlay.at=Date.now()-2500;
const state=await send({type:'state',pageURL:command.url});
assert.equal(navigations,1);assert.equal(state.playRequest,command.id);
await send({type:'play-result',id:command.id,ok:true});
assert.equal(posts.find(p=>p.url.endsWith('/ack')).data.ok,true);assert.equal(store.pendingPlay,undefined);
await send({type:'catalog',pageURL:'https://www.youtube.com/',items:[{url:command.url,title:'Video'}]});
assert.equal(posts.find(p=>p.url.endsWith('/catalog')).data.tab,9);
store.lastCommand=undefined;command.id='failed-command';failed=true;
await send({type:'state',pageURL:command.url});
assert.equal(posts.filter(p=>p.url.endsWith('/ack')).at(-1).data.ok,false);
failed=false;command.id='channel-command';command.kind='channel';command.url='https://www.youtube.com/@Example/videos';
const playingURL=tabURL,playingNavigations=navigations;
await send({type:'state',pageURL:tabURL});
assert.equal(tabURL,playingURL);assert.equal(navigations,playingNavigations);assert.equal(store.pendingPlay,undefined);
assert.equal(posts.filter(p=>p.url.endsWith('/catalog')).at(-1).data.page,command.url);
command.id='more-command';command.kind='channel-more';
await send({type:'state',pageURL:tabURL});
assert.equal(navigations,playingNavigations);
assert.equal(posts.filter(p=>p.url.endsWith('/catalog')).at(-1).data.request_id,'more-command');
assert.equal(posts.filter(p=>p.url.endsWith('/catalog')).at(-1).data.has_more,true);
command.id='list-more-command';command.kind='list-more';command.url=tabURL;
await send({type:'state',pageURL:tabURL});
assert.equal(navigations,playingNavigations);
assert.equal(posts.filter(p=>p.url.endsWith('/catalog')).at(-1).data.request_id,'list-more-command');
const previousURL=tabURL,previousNavigations=navigations;
windowState='minimized';const beforeFocus=windowChanges.length;
command.id='focus-command';command.kind='focus';
await send({type:'state',pageURL:tabURL});
assert.equal(tabURL,previousURL);assert.equal(navigations,previousNavigations);
assert.equal(windowChanges[beforeFocus].state,'normal');assert.equal(windowChanges[beforeFocus+1].focused,true);
await send({type:'frame',data:'data:image/jpeg;base64,/9j/2Q==',targetFps:30});
assert.equal(posts.filter(p=>p.url.endsWith('/frame')).at(-1).headers['X-Target-Fps'],'30');
await send({type:'frame',data:'data:image/jpeg;base64,/9j/2Q==',targetFps:60});
assert.equal(posts.filter(p=>p.url.endsWith('/frame')).at(-1).headers['X-Target-Fps'],'60');
await send({type:'frame',data:'data:image/jpeg;base64,/9j/2Q==',targetFps:120});
assert.equal(posts.filter(p=>p.url.endsWith('/frame')).at(-1).headers['X-Target-Fps'],'120');
await send({type:'frame',data:'data:image/jpeg;base64,/9j/2Q==',targetFps:999});
assert.equal(posts.filter(p=>p.url.endsWith('/frame')).at(-1).headers['X-Target-Fps'],'12');

let tick,moreListener;const messages=[];
function row(id,title){const link={href:'https://www.youtube.com/watch?v='+id,getAttribute:()=>''};return {querySelectorAll:()=>[link],querySelector:selector=>selector.startsWith('#video-title')?{textContent:title,getAttribute:()=>title}:{textContent:'Channel',getAttribute:()=>''}};}
const nodes=[row('abcdefghijk','One'),row('abcdefghijk','Duplicate'),row('12345678901','Two'),row('bad','Invalid')];
function modernRow(id,heading,linkText,aria=''){
 const link={href:'https://www.youtube.com/watch?v='+id,textContent:linkText,getAttribute:name=>name==='aria-label'?aria:''};
 return {querySelectorAll:()=>[link],querySelector:selector=>selector.startsWith('#video-title')?{textContent:' \n ',getAttribute:()=> '   '}:selector.startsWith('h3')?(heading?{textContent:heading,getAttribute:()=>''}:null):{textContent:'Channel'}};
}
nodes.push(modernRow('abcdefghij2','',''),modernRow('abcdefghij2','Heading title',''),modernRow('abcdefghij3','','Readable link'),modernRow('abcdefghij4','','','Accessible title'));
const page=vm.createContext({URL,Date,location:{href:'https://www.youtube.com/'},document:{querySelectorAll:()=>nodes,createElement:()=>({getContext:()=>({})})},
  chrome:{runtime:{id:'test',onMessage:{addListener:f=>moreListener=f},sendMessage:async m=>{messages.push(m);return {browse:true,selected:false};}}},setInterval:fn=>tick=fn,setTimeout:fn=>fn()});
vm.runInContext(await readFile(new URL('video.js',root),'utf8'),page);
await tick();const catalog=messages.find(m=>m.type==='catalog');
assert.equal(catalog.items.length,5);assert.equal(catalog.items[0].title,'One');assert.equal(catalog.items[1].image,'https://i.ytimg.com/vi/12345678901/hqdefault.jpg');
assert.equal(catalog.items[2].title,'Heading title');assert.equal(catalog.items[3].title,'Readable link');assert.equal(catalog.items[4].title,'Accessible title');
assert.equal(messages.some(m=>m.type==='frame'),false);
nodes.at(-1).scrollIntoView=()=>{for(let i=0;i<130;i++)nodes.push(row(String(i).padStart(11,'0'),'Lazy '+i));};
const more=await new Promise(resolve=>moreListener({type:'fetch-list-more',url:'https://www.youtube.com/'},{id:'test'},resolve));
assert.equal(more.items.length,100);assert.equal(more.items.at(-1).title,'Lazy 129');
assert.equal(page.location.href,'https://www.youtube.com/');
const stale=await new Promise(resolve=>moreListener({type:'fetch-list-more',url:'https://www.youtube.com/watch?v=abcdefghijk'},{id:'test'},resolve));
assert.match(stale.error,/changed/);
console.log('PASS: rendered catalog extraction/deduplication, selected-video navigation, command deduplication, playback acknowledgement, failed navigation, catalog without capture selection');
