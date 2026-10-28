// Recover a missing content script without reloading or starting tab sharing.
export async function ensureReader(tab, api) {
  const url=new URL(tab.url);
  if(url.protocol!=='https:'||url.hostname!=='www.youtube.com')throw Error('YouTube以外には読み込みません');
  async function probe() {
    let timer;
    try{return await Promise.race([
      api.tabs.sendMessage(tab.id,{type:'probe-video'}),
      new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('スクリプト応答なし')),2000);})
    ]);}finally{clearTimeout(timer);}
  }
  try {const result=await probe();if(result?.reader)return result;}catch{}
  await api.scripting.executeScript({target:{tabId:tab.id},files:['channel.js','video.js']});
  const result=await probe();
  if(!result?.reader)throw Error('読み込み後も動画スクリプトが応答しません');
  return {...result,injected:true};
}
