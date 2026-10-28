// Read embedded public channel-page data. No script execution or private API.
(() => {
  function initialData(html){
    if(typeof html!=='string'||html.length>6_000_000)throw Error('Channel page too large');
    const match=/(?:var\s+ytInitialData|window\["ytInitialData"\]|ytInitialData)\s*=\s*\{/.exec(html);
    if(!match)throw Error('Channel data not found');
    const start=match.index+match[0].length-1;let depth=0,string=false,escape=false;
    for(let i=start;i<html.length;i++){
      const c=html[i];
      if(string){if(escape)escape=false;else if(c==='\\')escape=true;else if(c==='"')string=false;continue;}
      if(c==='"')string=true;else if(c==='{')depth++;else if(c==='}'&&--depth===0)return JSON.parse(html.slice(start,i+1));
    }
    throw Error('Incomplete channel data');
  }
  const text=value=>typeof value==='string'?value:value?.simpleText||value?.content||(value?.runs||[]).map(r=>r.text||'').join('');
  function page(root){
    const stack=[root],items=[],seen=new Set();let nodes=0,continuation=null;
    while(stack.length&&nodes++<100000&&items.length<100){
      const node=stack.pop();if(!node||typeof node!=='object')continue;
      const token=node.continuationItemRenderer?.continuationEndpoint?.continuationCommand?.token;
      if(typeof token==='string'&&token.length<=16384)continuation=token;
      const video=node.videoRenderer,lockup=node.lockupViewModel;
      const id=video?.videoId||lockup?.contentId;
      if(/^[\w-]{11}$/.test(id||'')&&!seen.has(id)){
        const meta=lockup?.metadata?.lockupMetadataViewModel;
        const title=text(video?.title||meta?.title).trim();
        if(title){
          seen.add(id);
          items.push({url:'https://www.youtube.com/watch?v='+id,title:title.slice(0,240),channel:text(video?.shortBylineText||video?.ownerText||meta?.metadata?.contentMetadataViewModel?.metadataRows?.[0]?.metadataParts?.[0]?.text).slice(0,120),image:'https://i.ytimg.com/vi/'+id+'/hqdefault.jpg'});
        }
      }
      const values=Array.isArray(node)?node:Object.values(node);
      for(let i=values.length-1;i>=0;i--)if(values[i]&&typeof values[i]==='object')stack.push(values[i]);
    }
    return {items,continuation};
  }
  function bootstrap(html){
    const result=page(initialData(html));
    // Only copy the page's public client identity, never visitor/authentication data.
    const version=/"INNERTUBE_CLIENT_VERSION"\s*:\s*"([\w.\-]+)"/.exec(html)?.[1];
    return {...result,clientVersion:version||null};
  }
  const parse=html=>bootstrap(html).items;
  globalThis.__akp03jChannelParser={parse,page,bootstrap};
})();
