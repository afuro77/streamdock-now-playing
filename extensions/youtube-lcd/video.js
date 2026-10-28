(() => {
  if(globalThis.__akp03jVideoReader)return;
  globalThis.__akp03jVideoReader=true;
  const canvas=document.createElement('canvas');canvas.width=384;canvas.height=256;
  const context=canvas.getContext('2d');let busy=false,lastCatalog=0,lastPlay=null,lastChannel=0;
  let channelSession=null,targetFps=12;
  function currentChannel(){
    if(location.pathname!=='/watch')return null;
    for(const link of document.querySelectorAll('ytd-video-owner-renderer a[href], #owner a[href], #upload-info a[href]')){
      try{
        const u=new URL(link.href,location.href),match=u.pathname.match(/^(\/@[^/\s?#\\]+|\/(?:channel|c|user)\/[^/\s?#\\]+)(?:\/(?:videos|featured|shorts|streams))?\/?$/);
        if(u.protocol!=='https:'||u.host!=='www.youtube.com'||!match)continue;
        const heading=document.querySelector('ytd-watch-metadata h1, #title h1, h1.ytd-watch-metadata');
        const title=(heading?.innerText||heading?.textContent||document.title||'').replace(/ - YouTube$/,'').replace(/^\(\d+\)\s*/,'').trim();
        return {channel_url:u.origin+match[1]+'/videos',title:title.slice(0,240)};
      }catch{}
    }
    return null;
  }
  function catalog(tail=false) {
    const rows=document.querySelectorAll('ytd-rich-item-renderer, ytd-compact-video-renderer, ytd-video-renderer, yt-lockup-view-model');
    const items=new Map();
    const clean=value=>typeof value==='string'?value.replace(/\s+/g,' ').trim():'';
    function titleText(nodes) {
      for(const node of nodes){
        if(!node)continue;
        for(const value of [node.getAttribute('title'),node.innerText,node.textContent,node.getAttribute('aria-label')]){
          const text=clean(value);
          if(text&&!/^\d+(?::\d+){1,2}$/.test(text))return text;
        }
      }
      return '';
    }
    function channelLink(row,channel) {
      const links=[channel?.closest?.('a[href]'),channel?.querySelector?.('a[href]'),...row.querySelectorAll('a[href*="/@"], a[href*="/channel/"], a[href*="/c/"], a[href*="/user/"]')];
      for(const link of links){
        if(!link)continue;
        try{
          const u=new URL(link.href,location.href),match=u.pathname.match(/^(\/@[^/\s?#\\]+|\/(?:channel|c|user)\/[^/\s?#\\]+)(?:\/(?:videos|featured|shorts|streams))?\/?$/);
          if(u.protocol==='https:'&&u.host==='www.youtube.com'&&match&&!/%2f|%5c/i.test(u.pathname))return u.origin+match[1]+'/videos';
        }catch{}
      }
      return '';
    }
    for(const row of rows) {
      const links=[...row.querySelectorAll('a[href*="/watch?v="]')];
      const link=links[0];if(!link)continue;
      let id;try{const url=new URL(link.href,location.href);if(url.hostname!=='www.youtube.com')continue;id=url.searchParams.get('v');}catch{continue;}
      if(!/^[\w-]{11}$/.test(id||'')||(!items.has(id)&&items.size>=(tail?1000:100)))continue;
      const title=row.querySelector('#video-title, #video-title-link, .yt-lockup-metadata-view-model__title');
      const heading=row.querySelector('h3, h4, [role="heading"], .yt-lockup-metadata-view-model__heading-reset');
      const channel=row.querySelector('#channel-name, .yt-content-metadata-view-model__metadata-row');
      const label=titleText([title,heading,...links]);
      const existing=items.get(id);
      const channelURL=channelLink(row,channel);
      if(!existing)items.set(id,{url:'https://www.youtube.com/watch?v='+id,title:(label||'Title unavailable').slice(0,240),channel:clean(channel?.textContent).slice(0,120),channel_url:channelURL,image:'https://i.ytimg.com/vi/'+id+'/hqdefault.jpg'});
      else{
        if(existing.title==='Title unavailable'&&label)existing.title=label.slice(0,240);
        if(!existing.channel_url&&channelURL)existing.channel_url=channelURL;
        if(!existing.channel)existing.channel=clean(channel?.textContent).slice(0,120);
      }
    }
    const result=[...items.values()];return tail?result.slice(-100):result;
  }
  chrome.runtime.onMessage.addListener((message,sender,reply)=>{
    if(message.type==='fetch-list-more'&&sender.id===chrome.runtime.id){
      (async()=>{
        const url=new URL(message.url);
        if(url.origin!=='https://www.youtube.com'||url.href!==location.href)throw Error('List page changed');
        // Trigger the existing page's lazy loader, without navigating or pausing.
        const before=location.href;
        const nodes=document.querySelectorAll('ytd-rich-item-renderer, ytd-compact-video-renderer, ytd-video-renderer, yt-lockup-view-model');
        if(nodes.length)nodes[nodes.length-1].scrollIntoView({block:'end',behavior:'instant'});
        await new Promise(resolve=>setTimeout(resolve,1500));
        if(location.href!==before)throw Error('List page changed');
        return {items:catalog(true),hasMore:true};
      })().then(reply).catch(e=>reply({error:e.message}));
      return true;
    }
    if((message.type==='fetch-channel'||message.type==='fetch-channel-more')&&sender.id===chrome.runtime.id){
      (async()=>{
        const u=new URL(message.url);
        if(u.protocol!=='https:'||u.host!=='www.youtube.com'||!/^\/(?:@[^/]+|(?:channel|c|user)\/[^/]+)\/videos$/.test(u.pathname))throw Error('Invalid channel URL');
        if(message.type==='fetch-channel-more'){
          const session=channelSession;
          if(!session||session.url!==u.href||!session.continuation||!session.clientVersion)throw Error('Channel continuation unavailable');
          // Undocumented website continuation, not the YouTube Data API.
          // Same-origin request only; no cookies or authentication headers are extracted.
          const response=await fetch('https://www.youtube.com/youtubei/v1/browse',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({context:{client:{clientName:'WEB',clientVersion:session.clientVersion}},continuation:session.continuation}),signal:AbortSignal.timeout(10000)});
          if(!response.ok||new URL(response.url).hostname!=='www.youtube.com')throw Error('Channel continuation failed');
          const raw=await response.text();if(raw.length>6000000)throw Error('Channel page too large');
          const next=globalThis.__akp03jChannelParser.page(JSON.parse(raw));
          if(channelSession!==session)throw Error('Channel selection changed');
          session.continuation=next.continuation===session.continuation?null:next.continuation;
          return {items:next.items,hasMore:!!session.continuation};
        }
        const response=await fetch(u.href,{credentials:'same-origin',signal:AbortSignal.timeout(10000)});
        if(!response.ok||new URL(response.url).hostname!=='www.youtube.com')throw Error('Channel page unavailable');
        const html=await response.text();
        if(!globalThis.__akp03jChannelParser)throw Error('Reload extension and YouTube page');
        const result=globalThis.__akp03jChannelParser.bootstrap(html);
        channelSession={url:u.href,continuation:result.continuation,clientVersion:result.clientVersion};
        return {items:result.items,hasMore:!!(result.continuation&&result.clientVersion)};
      })().then(reply).catch(e=>reply({error:e.message}));
      return true;
    }
    if(message.type!=='probe-video'||sender.id!==chrome.runtime.id)return false;
    const video=document.querySelector('video.html5-main-video')||document.querySelector('video');
    if(!video){reply({reader:true,video:false,catalog:catalog().length});return false;}
    try {
      const probe=document.createElement('canvas');probe.width=16;probe.height=16;
      probe.getContext('2d').drawImage(video,0,0,16,16);
      const data=probe.toDataURL('image/jpeg');
      reply({reader:true,video:true,width:video.videoWidth,height:video.videoHeight,readable:data.startsWith('data:image/jpeg;'),catalog:catalog().length});
    }catch(error){reply({reader:true,video:true,readable:false,error:error.name+': '+error.message});}
    return false;
  });
  const tick=async()=>{
    if(busy)return;busy=true;
    try {
      const state=await chrome.runtime.sendMessage({type:'state',pageURL:location.href});
      if(Date.now()-lastChannel>2000){const info=currentChannel();if(info)await chrome.runtime.sendMessage({type:'current-channel',pageURL:location.href,...info});lastChannel=Date.now();}
      if(state?.browse&&Date.now()-lastCatalog>2000){await chrome.runtime.sendMessage({type:'catalog',pageURL:location.href,items:catalog()});lastCatalog=Date.now();}
      if(state?.playRequest&&state.playRequest!==lastPlay) {
        const video=document.querySelector('video.html5-main-video')||document.querySelector('video');
        if(video&&video.readyState>=2){lastPlay=state.playRequest;try{await video.play();await chrome.runtime.sendMessage({type:'play-result',id:lastPlay,ok:!video.paused});}catch{await chrome.runtime.sendMessage({type:'play-result',id:lastPlay,ok:false});}}
      }
      if(!state||state.selected===false||(!state.enabled&&state.selected!==true))return;
      const video=document.querySelector('video.html5-main-video')||document.querySelector('video');
      if(!video||video.readyState<2||!video.videoWidth){await chrome.runtime.sendMessage({type:'diagnostic',stage:'no-video'});return;}
      canvas.width=384;
      const scale=Math.min(384/video.videoWidth,256/video.videoHeight);
      const width=video.videoWidth*scale,height=video.videoHeight*scale;
      context.fillStyle='black';context.fillRect(0,0,384,256);
      context.drawImage(video,(384-width)/2,(256-height)/2,width,height);
      let data;
      try { data=canvas.toDataURL('image/jpeg',0.65); }
      catch(error){
        await chrome.runtime.sendMessage({type:'failure',reason:error.name+': 動画画素の読取がブラウザに拒否されました'});
        return;
      }
      if(state.enabled)await chrome.runtime.sendMessage({type:'frame',data,targetFps});
    } catch { /* Reloading/removing the extension or disconnecting DEV must not affect YouTube. */ }
    finally {busy=false;}
  };
  let timer;
  function applyFps(value){
    const fps=[4,6,8,10,12,15,20,24,30,40,45,50,60,75,90,120].includes(Number(value))?Number(value):12;
    targetFps=fps;
    if(timer!==undefined)clearInterval(timer);
    timer=setInterval(tick,Math.round(1000/fps));
  }
  applyFps(12);
  if(chrome.storage?.local&&chrome.storage.onChanged){
    chrome.storage.local.get('targetFps').then(v=>applyFps(v.targetFps));
    chrome.storage.onChanged.addListener((changes,area)=>{if(area==='local'&&changes.targetFps)applyFps(changes.targetFps.newValue);});
  }
})();
