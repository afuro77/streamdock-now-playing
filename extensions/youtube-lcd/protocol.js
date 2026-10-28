export function parseSession(value) {
  const url = new URL(value);
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' ||
      url.username || url.password || url.pathname !== '/' || url.search ||
      !/^[A-Za-z0-9_-]{32,128}$/.test(url.hash.slice(1))) throw Error('DEV接続URLが不正です');
  return {base: url.origin, token: url.hash.slice(1)};
}
export function youtubeURL(value) {
  try { const u = new URL(value); return u.protocol === 'https:' && u.hostname === 'www.youtube.com'; }
  catch { return false; }
}
export function decodeFrame(value) {
  if (typeof value !== 'string' || value.length > 270000 ||
      !/^data:image\/jpeg;base64,[A-Za-z0-9+/]+=*$/.test(value)) throw Error('Invalid JPEG frame');
  const raw = atob(value.split(',')[1]);
  if (raw.length > 200000) throw Error('Frame too large');
  return Uint8Array.from(raw, c => c.charCodeAt(0));
}
export function channelURL(value) {
  const u=new URL(value),match=u.pathname.match(/^(\/@[^/\s?#\\]+|\/(?:channel|c|user)\/[^/\s?#\\]+)(?:\/(?:videos|featured|shorts|streams))?\/?$/);
  if(u.protocol!=='https:'||u.host!=='www.youtube.com'||!match||u.pathname.length>512||/%2f|%5c/i.test(u.pathname))throw Error('Invalid channel URL');
  return 'https://www.youtube.com'+match[1]+'/videos';
}
