"""TRACK is delegated unchanged; supplementary pages use only ready data."""
import io,time,os
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageFont
from .desktop import panel
from .renderer import LayoutRenderer

class DetailRenderer:
    def __init__(self):self.photo_cache={}
    def artist(self,data,snapshot,message):
        people=(data or {}).get('artists') or []
        index=int(time.monotonic()/8)%len(people) if people else 0
        person=people[index] if people else {'name':snapshot.get('artist',''),'image':None}
        name=person.get('name') or snapshot.get('artist','')
        label=name+(f'  {index+1}/{len(people)}' if len(people)>1 else '')
        picture=person.get('image')
        key=(person.get('id'),id(picture),label,message if not picture else '')
        if key in self.photo_cache:return self.photo_cache[key]
        canvas=Image.new('RGB',(384,256),'#10261f');draw=ImageDraw.Draw(canvas)
        if picture:
            try:
                photo=ImageOps.exif_transpose(Image.open(io.BytesIO(picture))).convert('RGB')
                photo=ImageOps.contain(photo,(384,216),Image.Resampling.LANCZOS)
                canvas.paste(photo,((384-photo.width)//2,(216-photo.height)//2))
            except Exception:picture=None
        fontpath=str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/meiryo.ttc')
        def text(value,y,size):
            try:font=ImageFont.truetype(fontpath,size)
            except OSError:font=ImageFont.load_default()
            while draw.textlength(value,font=font)>376 and size>14:
                size-=1
                try:font=ImageFont.truetype(fontpath,size)
                except OSError:break
            while draw.textlength(value,font=font)>376 and len(value)>1:value=value[:-2]+'…'
            draw.text(((384-draw.textlength(value,font=font))/2,y),value,font=font,fill='white')
        if not picture:text('ARTIST',45,32);text(message or 'No artist image',105,24)
        text(label,218,24)
        result=LayoutRenderer.split_canvas(canvas)
        if len(self.photo_cache)>=32:self.photo_cache.clear()
        self.photo_cache[key]=result;return result
    def album(self,data,snapshot,layout,message):
        track=(data or {}).get('track') or {};album=track.get('album') or {}
        title=album.get('name') or snapshot.get('album') or 'Album unavailable'
        top=layout.expanded_metadata({'title':title,'artist':''})[:3]
        year=(album.get('release_date') or '')[:4] or '--'
        number=track.get('track_number');total=album.get('total_tracks')
        duration=track.get('duration_ms',0)/1000 or snapshot.get('duration') or 0
        cards=[panel([('YEAR',18,5,'#b9d8ef'),(year,36,48,'white')]),
               panel([('TRACK',18,5,'#b9d8ef'),(f'{number}/{total}' if number and total else '--',34,48,'white')]),
               panel([('LENGTH',18,5,'#b9d8ef'),(f'{int(duration)//60}:{int(duration)%60:02}' if duration else '--',34,48,'white')])]
        return top+cards
