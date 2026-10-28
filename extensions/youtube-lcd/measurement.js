// Measurement state is held only by the open options page. No persistent history.
export class FrameRateMeasurement {
  constructor(seconds=5){this.seconds=seconds;this.first=null;this.last=null;}
  sample(value){
    if(value?.error)throw Error(value.error);
    if(!Number.isFinite(value?.sampleTime)||!Number.isSafeInteger(value.frames)||value.frames<0||typeof value.instance!=='string'||!value.instance)
      throw Error('DEVの測定情報が古いか不正です。DEVを更新してください。');
    if(value.enabled!==true)throw Error('YouTubeの全面動画表示にしてから測定してください。');
    if(value.fresh!==true)throw Error('動画の受信が止まっています。動画と拡張の接続を確認してください。');
    const choices=[4,6,8,10,12,15,20,24,30,40,45,50,60,75,90,120];
    if(!choices.includes(value.target)||value.target!==value.configuredTarget)
      throw Error('コマ数の設定反映を待って、もう一度測定してください。');
    if(this.first&&(value.instance!==this.first.instance||value.frames<this.last.frames||value.sampleTime<this.last.sampleTime))
      throw Error('DEVが再起動したため測定を中止しました。');
    if(this.first&&value.target!==this.first.target)throw Error('測定中にコマ数が変わりました。もう一度測定してください。');
    if(!this.first)this.first={...value};
    this.last={...value};
    const seconds=value.sampleTime-this.first.sampleTime,frames=value.frames-this.first.frames;
    return {target:this.first.target,seconds,frames,fps:seconds>0?frames/seconds:0,done:seconds>=this.seconds};
  }
}

export async function measureFrameRate({getSample,onProgress=()=>{},wait=ms=>new Promise(resolve=>setTimeout(resolve,ms)),isCancelled=()=>false}){
  const measurement=new FrameRateMeasurement();
  while(!isCancelled()){
    const result=measurement.sample(await getSample());
    if(isCancelled())break;
    onProgress(result);
    if(result.done)return result;
    await wait(500);
  }
  throw Error('測定を中止しました。');
}
