"""Queue preview screen; normal Now Playing renderer is untouched."""
from PIL import Image, ImageDraw
from .renderer import _font, encode, fit_lines


class QueueRenderer:
    def __init__(self,label='NEXT',compact=False): self.key = None; self.images = None;self.label=label;self.compact=compact

    def render(self, items, message, offset=0):
        key = repr((items, message, offset))
        if key == self.key: return self.images
        titles, artists = [], []
        for column in range(3):
            top = Image.new('RGB', (128, 128), '#10261f')
            bottom = Image.new('RGB', (128, 128), '#10261f')
            draw = ImageDraw.Draw(top)
            margin,width=(3,122) if self.compact else (5,118)
            heading='#'+str(offset+column+1) if self.compact else self.label+' '+str(offset+column+1)
            draw.text((margin, 1 if self.compact else 3), heading, font=_font(12 if self.compact else 16, True), fill='#71cbaa')
            item = items[column] if column < len(items) else None
            title = item.get('title', '') if item else (message if column == 0 else '') or '—'
            size,lines,y,step=(20,4,17,21) if self.compact else (25,2,26,29)
            for index, line in enumerate(fit_lines(title, _font(size, True), width, lines)):
                draw.text((margin, y+index*step), line, font=_font(size, True), fill='white', anchor='lt')
            if item:
                size,lines,y,step=(14,1,110,15) if self.compact else (18,2,87,20)
                for index, line in enumerate(fit_lines(item.get('artist', ''), _font(size), width, lines)):
                    draw.text((margin, y+index*step), line, font=_font(size), fill='#c3e7d7', anchor='lt')
            if not item or not item.get('cover'):
                draw = ImageDraw.Draw(bottom)
                draw.text((10, 51), 'NO COVER' if item else '—', font=_font(18), fill='#71cbaa', anchor='lt')
            titles.append(encode(top)); artists.append(item.get('cover') if item and item.get('cover') else encode(bottom))
        self.key = key; self.images = titles+artists
        return self.images
