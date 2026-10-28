import {strict as assert} from 'node:assert';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const source=await readFile(new URL('../extensions/youtube-lcd/channel.js',import.meta.url),'utf8');
const context=vm.createContext({});vm.runInContext(source,context);
const parse=context.__akp03jChannelParser.parse;
const old={videoRenderer:{videoId:'abcdefghijk',title:{runs:[{text:'Title with } and " braces'}]},shortBylineText:{runs:[{text:'Channel'}]}}};
const modern={lockupViewModel:{contentId:'12345678901',metadata:{lockupMetadataViewModel:{title:{content:'Modern title'}}}}};
const html='<script>var ytInitialData = '+JSON.stringify({contents:[old,modern,old]})+';</script>';
const items=parse(html);
assert.equal(items.length,2);assert.equal(items[0].title,'Title with } and " braces');assert.equal(items[1].title,'Modern title');
assert.equal(items[0].url,'https://www.youtube.com/watch?v=abcdefghijk');
assert.throws(()=>parse('<script>alert(1)</script>'),/not found/);
assert.throws(()=>parse('var ytInitialData = {bad}'));
assert.throws(()=>parse('x'.repeat(6000001)),/too large/);
assert.equal(parse('window["ytInitialData"] = '+JSON.stringify({contents:[modern]})).length,1);
console.log('PASS: channel-page JSON parsing, escaped braces, modern/legacy cards, deduplication and malformed/oversized input rejection');
const {bootstrap,page}=context.__akp03jChannelParser;
const continued={contents:[old,{continuationItemRenderer:{continuationEndpoint:{continuationCommand:{token:'page-two'}}}}]};
const boot=bootstrap('ytInitialData = '+JSON.stringify(continued)+'; ytcfg.set({"INNERTUBE_CLIENT_VERSION":"2.20261028.00.00"});');
assert.equal(boot.continuation,'page-two');assert.equal(boot.clientVersion,'2.20261028.00.00');
assert.equal(page({onResponseReceivedActions:[{appendContinuationItemsAction:{continuationItems:[modern]}}]}).items[0].title,'Modern title');
assert.equal(page({}).continuation,null);

// Exercise the content reader: continuation must not navigate or pause the video.
let listener,fetches=[],fail=false;
const chrome={runtime:{id:'test',onMessage:{addListener:f=>listener=f}}};
const reader=vm.createContext({chrome,URL,AbortSignal,location:{href:'https://www.youtube.com/watch?v=abcdefghijk'},
 document:{createElement:()=>({getContext:()=>({})})},setInterval(){},
 fetch:async(url,options={})=>{
   fetches.push({url,options});
   if(fail)return {ok:false,url};
   return {ok:true,url,text:async()=>url.includes('/youtubei/')?JSON.stringify({onResponseReceivedActions:[{appendContinuationItemsAction:{continuationItems:[modern]}}]}):'ytInitialData = '+JSON.stringify(continued)+'; "INNERTUBE_CLIENT_VERSION":"2.20261028.00.00"'};
 }});
vm.runInContext(source,reader);
vm.runInContext(await readFile(new URL('../extensions/youtube-lcd/video.js',import.meta.url),'utf8'),reader);
const send=m=>new Promise(resolve=>assert.equal(listener(m,{id:'test'},resolve),true));
const target='https://www.youtube.com/@Example/videos';
let result=await send({type:'fetch-channel',url:target});assert.equal(result.hasMore,true);
fail=true;result=await send({type:'fetch-channel-more',url:target});assert.match(result.error,/failed/);
fail=false;result=await send({type:'fetch-channel-more',url:target});assert.equal(result.items[0].title,'Modern title');assert.equal(result.hasMore,false);
assert.equal(JSON.parse(fetches.at(-1).options.body).continuation,'page-two');
assert.equal(reader.location.href,'https://www.youtube.com/watch?v=abcdefghijk');
result=await send({type:'fetch-channel-more',url:target});assert.match(result.error,/unavailable/);
result=await send({type:'fetch-channel',url:'https://evil.example/videos'});assert.match(result.error,/Invalid/);
console.log('PASS: continuation parsing, same-origin page fetch, retry, exhaustion and unchanged watch URL');
