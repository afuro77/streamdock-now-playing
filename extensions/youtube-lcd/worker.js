import {parseSession, youtubeURL, decodeFrame,channelURL} from './protocol.js';
import {ensureReader} from './reader.js';
async function settings() {
  const saved = await chrome.storage.local.get('sessionURL');
  if (saved.sessionURL) return parseSession(saved.sessionURL);
  const local = await fetch(chrome.runtime.getURL('pairing.local.json'),{cache:'no-store'}).then(r => r.json());
  return parseSession(local.url);
}
const diagnosticTimes=new Map();
async function diagnostic(stage) {
  if(Date.now()-(diagnosticTimes.get(stage)||0)<5000)return;
  const config=await settings();
  await fetch(config.base+'/diagnostic',{method:'POST',headers:{'X-Capture-Token':config.token,'Content-Type':'application/json'},body:JSON.stringify({stage}),signal:AbortSignal.timeout(2000)});
  diagnosticTimes.set(stage,Date.now());
}
const badgeStates=new Map();
async function badge(tabId, text, title) {
  const state=text+'\n'+title;
  if(badgeStates.get(tabId)===state)return;
  await chrome.action.setBadgeText({tabId, text});
  await chrome.action.setTitle({tabId, title});
  badgeStates.set(tabId,state);
}
async function browserPost(config,path,data) {
  return fetch(config.base+'/browser/'+path,{method:'POST',headers:{'X-Capture-Token':config.token,'Content-Type':'application/json'},body:JSON.stringify(data),signal:AbortSignal.timeout(3000)});
}
let openingCommand=null;
async function navigateCommand(config,command) {
  if(!command||openingCommand===command.id)return;
  const stored=await chrome.storage.session.get('lastCommand');
  if(stored.lastCommand===command.id||openingCommand===command.id)return;
  openingCommand=command.id;
  try {
    const url=new URL(command.url);
    if(command.kind==='focus') {if(!youtubeURL(command.url))throw Error('Invalid focus target');}
    else if(command.kind==='list-more') {if(!youtubeURL(command.url))throw Error('Invalid list target');}
    else if(command.kind==='channel'||command.kind==='channel-more') {if(channelURL(command.url)!==command.url)throw Error('Invalid channel selection');}
    else if(!youtubeURL(command.url)||url.pathname!=='/watch'||!/^[\w-]{11}$/.test(url.searchParams.get('v')||''))throw Error('Invalid video selection');
    const target=await chrome.tabs.get(command.tab);
    if(!youtubeURL(target.url))throw Error('YouTube tab was closed or changed');
    await chrome.storage.session.set({lastCommand:command.id});
    if(command.kind==='list-more'){
      await ensureReader(target,chrome);
      const result=await chrome.tabs.sendMessage(command.tab,{type:'fetch-list-more',url:command.url});
      if(!result||result.error||!Array.isArray(result.items))throw Error(result?.error||'List continuation unavailable');
      await browserPost(config,'catalog',{tab:command.tab,page:command.url,items:result.items,request_id:command.id,has_more:result.hasMore===true});
      return;
    }
    if(command.kind==='channel'||command.kind==='channel-more'){
      await ensureReader(target,chrome);
      const result=await chrome.tabs.sendMessage(command.tab,{type:command.kind==='channel'?'fetch-channel':'fetch-channel-more',url:command.url});
      if(!result||result.error||!Array.isArray(result.items))throw Error(result?.error||'Channel data unavailable');
      await browserPost(config,'catalog',{tab:command.tab,page:command.url,items:result.items,request_id:command.id,has_more:result.hasMore===true});
      return;
    }
    await chrome.tabs.update(command.tab,command.kind==='focus'?{active:true}:{url:command.url,active:true});
    if(chrome.windows&&target.windowId!==undefined){
      const window=await chrome.windows.get(target.windowId);
      if(window.state==='minimized')await chrome.windows.update(target.windowId,{state:'normal'});
      await chrome.windows.update(target.windowId,{focused:true});
    }
    if(command.kind==='channel'||command.kind==='focus'){
      await chrome.storage.session.remove('pendingPlay');
      await browserPost(config,'ack',{id:command.id,ok:true});
    }else await chrome.storage.session.set({selectedTab:command.tab,pendingPlay:{id:command.id,tab:command.tab,url:command.url,at:Date.now()}});
  }catch {
    await browserPost(config,'ack',{id:command.id,ok:false});
  }finally{openingCommand=null;}
}
chrome.action.onClicked.addListener(async tab => {
  if (!youtubeURL(tab.url)) { await chrome.runtime.openOptionsPage(); return; }
  const state = await chrome.storage.session.get('selectedTab');
  if (state.selectedTab === tab.id) {
    await chrome.storage.session.remove('selectedTab');
    await badge(tab.id, '', 'AKP03J：停止中');return;
  }
  try {
    await settings();
    const reader=await ensureReader(tab,chrome);
    if(reader.readable===false)throw Error(reader.error||'動画を読み取れません');
    if (state.selectedTab !== undefined) await badge(state.selectedTab, '', 'AKP03J：停止中').catch(()=>{});
    await chrome.storage.session.set({selectedTab:tab.id});
    await badge(tab.id, 'WAIT', 'AKP03J：開始済み・フレーム待ち');
  } catch(error) {
    await chrome.storage.local.set({lastError:String(error.message)});
    await badge(tab.id,'ERR',String(error.message));await chrome.runtime.openOptionsPage();
  }
});
chrome.tabs.onRemoved.addListener(async id => {
  badgeStates.delete(id);
  const state=await chrome.storage.session.get('selectedTab');
  if(state.selectedTab===id)await chrome.storage.session.remove('selectedTab');
});
const lastRegistration=new Map();
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if(message.type==='fps-sample' && sender.id===chrome.runtime.id && sender.url===chrome.runtime.getURL('options.html')) {
    (async()=>{
      const config=await settings();
      const response=await fetch(config.base+'/diagnostics',{headers:{'X-Capture-Token':config.token},signal:AbortSignal.timeout(3000)});
      if(!response.ok)throw Error('DEVに接続できません。接続設定を確認してください。');
      const data=await response.json();
      const saved=await chrome.storage.local.get('targetFps');
      const configuredTarget=[4,6,8,10,12,15,20,24,30,40,45,50,60,75,90,120].includes(saved.targetFps)?saved.targetFps:12;
      return {sampleTime:data.sample_time,instance:data.instance,frames:data.sources?.extension,target:data.target_fps,configuredTarget,enabled:data.enabled,fresh:data.fresh};
    })().then(reply).catch(()=>reply({error:'測定情報を取得できません。DEVと接続設定を確認してください。'}));
    return true;
  }
  if(message.type==='inspect' && sender.id===chrome.runtime.id && sender.url===chrome.runtime.getURL('options.html')) {
    (async()=>{
      const result={version:chrome.runtime.getManifest().version};
      result.targetFps=(await chrome.storage.local.get('targetFps')).targetFps||12;
      try {
        const config=await settings();
        const response=await fetch(config.base+'/state',{headers:{'X-Capture-Token':config.token},signal:AbortSignal.timeout(3000)});
        result.receiver=response.status;result.receiverState=response.ok?await response.json():null;
      }catch(error){result.receiverError=error.message;}
      const selected=await chrome.storage.session.get('selectedTab');
      const tabs=await chrome.tabs.query({url:'https://www.youtube.com/*'});
      result.youtubeTabs=tabs.length;result.videos=[];
      for(const tab of tabs){
        try {
          const video=await ensureReader(tab,chrome);
          result.videos.push({selected:tab.id===selected.selectedTab,...video});
        }catch(error){result.videos.push({selected:tab.id===selected.selectedTab,error:error.message});}
      }
      return result;
    })().then(reply).catch(e=>reply({error:e.message}));
    return true;
  }
  if (!sender.tab || !youtubeURL(sender.url)) return false;
  (async()=>{
    const config=await settings(),headers={'X-Capture-Token':config.token};
    if(message.type==='catalog') {
      if(!Array.isArray(message.items)||message.items.length>100)throw Error('Invalid catalog');
      if(!youtubeURL(message.pageURL))throw Error('Invalid catalog page');
      await browserPost(config,'catalog',{tab:sender.tab.id,page:message.pageURL,items:message.items});return {ok:true};
    }
    if(message.type==='current-channel'){
      const selected=await chrome.storage.session.get('selectedTab');
      if(selected.selectedTab!==undefined&&selected.selectedTab!==sender.tab.id)return {ok:false};
      await browserPost(config,'current',{tab:sender.tab.id,page:message.pageURL,channel_url:message.channel_url,title:message.title});return {ok:true};
    }
    if(message.type==='play-result') {
      const stored=await chrome.storage.session.get('pendingPlay'),pending=stored.pendingPlay;
      if(pending && pending.id===message.id && pending.tab===sender.tab.id) {
        await browserPost(config,'ack',{id:pending.id,ok:message.ok===true});
        await chrome.storage.session.remove('pendingPlay');
      }
      return {ok:true};
    }
    if(message.type==='state') {
      if(youtubeURL(message.pageURL)&&Date.now()-(lastRegistration.get(sender.tab.id)||0)>2000){
        const selected=await chrome.storage.session.get('selectedTab');
        await browserPost(config,'register',{tab:sender.tab.id,page:message.pageURL,active:sender.tab.active===true,selected:selected.selectedTab===sender.tab.id});
        lastRegistration.set(sender.tab.id,Date.now());
      }
      const response=await fetch(config.base+'/state',{headers,signal:AbortSignal.timeout(2000)});
      if(!response.ok)throw Error('DEV接続設定を更新してください');
      const result=await response.json();
      await navigateCommand(config,result.command);
      const stored=await chrome.storage.session.get(['selectedTab','pendingPlay']);
      const selected=stored.selectedTab===sender.tab.id,pending=stored.pendingPlay;
      const playRequest=pending && pending.tab===sender.tab.id && Date.now()-pending.at>1500 && Date.now()-pending.at<15000 && message.pageURL===pending.url ? pending.id:null;
      if(selected){await diagnostic(result.enabled?'ready':'waiting-view');if(!result.enabled)await badge(sender.tab.id,'WAIT','AKP03J：画像LCDの拡大表示待ち');}
      return {...result,enabled:result.enabled&&selected,selected,playRequest};
    }
    const state=await chrome.storage.session.get('selectedTab');
    if(state.selectedTab!==sender.tab.id){await diagnostic('not-selected');return {enabled:false,selected:false};}
    if(message.type==='failure') {
      await diagnostic('read-error');
      await chrome.storage.session.remove('selectedTab');
      await badge(sender.tab.id,'ERR','直接読取できません：'+String(message.reason).slice(0,100));
      return {enabled:false};
    }
    if(message.type==='diagnostic'){if(message.stage==='no-video')await diagnostic('no-video');return {ok:true};}
    if(message.type==='frame') {
      const body=decodeFrame(message.data);
      const targetFps=[4,6,8,10,12,15,20,24,30,40,45,50,60,75,90,120].includes(message.targetFps)?message.targetFps:12;
      const response=await fetch(config.base+'/frame',{method:'POST',headers:{...headers,'Content-Type':'image/jpeg','X-Frame-Source':'extension','X-Target-Fps':String(targetFps)},body,signal:AbortSignal.timeout(2000)});
      if(!response.ok&&response.status!==409)throw Error('フレーム転送失敗');
      if(response.ok){await diagnostic('sent');await badge(sender.tab.id,'ON','AKP03J：映像フレームの受信確認済み');}
      else await badge(sender.tab.id,'WAIT','AKP03J：表示切替のため待機');
      return {ok:response.ok};
    }
    return {enabled:false};
  })().then(reply).catch(async error=>{
    await diagnostic('send-error').catch(()=>{});
    await chrome.storage.local.set({lastError:String(error.message)});
    await badge(sender.tab.id,'ERR',String(error.message)).catch(()=>{});
    reply({enabled:false,error:error.message});
  });
  return true;
});
