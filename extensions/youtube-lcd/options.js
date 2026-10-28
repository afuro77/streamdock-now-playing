import {parseSession} from './protocol.js';
import {measureFrameRate} from './measurement.js';
const field=document.querySelector('#url'),status=document.querySelector('#status');
const fps=document.querySelector('#fps'),fpsStatus=document.querySelector('#fps-status');
chrome.storage.local.get('targetFps').then(v=>{fps.value=String([4,6,8,10,12,15,20,24,30,40,45,50,60,75,90,120].includes(v.targetFps)?v.targetFps:12);});
document.querySelector('#save-fps').onclick=async()=>{
  const targetFps=Number(fps.value);
  if(![4,6,8,10,12,15,20,24,30,40,45,50,60,75,90,120].includes(targetFps))return;
  await chrome.storage.local.set({targetFps});
  fpsStatus.textContent=targetFps+' fpsを適用しました。動画・DEVの再起動は不要です。';
};
document.querySelector('#inspect').onclick=async()=>{
  const output=document.querySelector('#diagnosis');output.textContent='診断中…';
  try {
    const result=await Promise.race([chrome.runtime.sendMessage({type:'inspect'}),new Promise((_,reject)=>setTimeout(()=>reject(Error('拡張のバックグラウンドから応答がありません')),10000))]);
    output.textContent=JSON.stringify(result,null,2);
  }catch(error){output.textContent=error.message;}
};
chrome.storage.local.get(['sessionURL','lastError']).then(v=>{field.value=v.sessionURL||'';if(v.lastError)status.textContent='直近の接続エラー: '+v.lastError;});
document.querySelector('#save').onclick=async()=>{
  try{parseSession(field.value.trim());await chrome.storage.local.set({sessionURL:field.value.trim()});status.textContent='保存しました。YouTubeタブで拡張ボタンを押してください。'}
  catch(e){status.textContent=e.message;}
};
document.querySelector('#reset').onclick=async()=>{await chrome.storage.local.remove('sessionURL');field.value='';status.textContent='準備済み設定を使用します';};

const measureButton=document.querySelector('#measure-fps'),cancelButton=document.querySelector('#cancel-measure');
const measurementStatus=document.querySelector('#measurement-status'),resultsBody=document.querySelector('#measurement-results');
const history=[];let measuring=false,cancelled=false;
function renderMeasurements(){
  resultsBody.replaceChildren();
  for(const row of history){
    const tr=document.createElement('tr');
    for(const value of [row.at,row.target+' コマ／秒',row.fps.toFixed(1),String(row.frames),row.seconds.toFixed(1)]){
      const td=document.createElement('td');td.textContent=value;td.style.padding='6px';tr.append(td);
    }
    resultsBody.append(tr);
  }
}
measureButton.onclick=async()=>{
  if(measuring)return;
  measuring=true;cancelled=false;measureButton.disabled=true;cancelButton.disabled=false;
  const apply=document.querySelector('#save-fps');apply.disabled=true;fps.disabled=true;
  measurementStatus.textContent='適用中の設定を確認しています…';
  try{
    const result=await measureFrameRate({
      getSample:()=>chrome.runtime.sendMessage({type:'fps-sample'}),isCancelled:()=>cancelled,
      onProgress:r=>{measurementStatus.textContent=r.target+' コマ／秒設定で測定中：'+Math.min(5,r.seconds).toFixed(1)+' / 5秒、受信 '+r.fps.toFixed(1)+' コマ／秒';}
    });
    history.unshift({...result,at:new Date().toLocaleTimeString()});history.splice(10);renderMeasurements();
    measurementStatus.textContent='記録しました：設定 '+result.target+' → 受信実測 '+result.fps.toFixed(1)+' コマ／秒（'+result.seconds.toFixed(1)+'秒）';
  }catch(error){measurementStatus.textContent=error.message||'測定できませんでした。';}
  finally{measuring=false;measureButton.disabled=false;cancelButton.disabled=true;apply.disabled=false;fps.disabled=false;}
};
cancelButton.onclick=()=>{cancelled=true;measurementStatus.textContent='測定を中止しています…';};
document.querySelector('#clear-measurements').onclick=()=>{history.length=0;renderMeasurements();};
