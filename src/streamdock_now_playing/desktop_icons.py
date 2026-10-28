"""Original vector-style desktop icons, drawn at LCD resolution."""
import math
from PIL import Image, ImageDraw
from .renderer import encode


def icon_panel(lines, kind, icon_path=None):
    from .desktop import panel
    import io, base64
    image=Image.open(io.BytesIO(base64.b64decode(panel(lines).split(',')[1]))).convert('RGB')
    d=ImageDraw.Draw(image)
    if icon_path:
        try:
            icon=Image.open(icon_path).convert('RGBA');size=100 if kind=='app_only' else 68
            icon=icon.resize((size,size),Image.Resampling.LANCZOS)
            image.paste(icon,((128-icon.width)//2,(128-size)//2 if kind=='app_only' else 8),icon)
            return encode(image)
        except OSError: pass
    if kind in ('app','app_only'):kind='launcher'
    if kind=='laundry':
        # Shirt silhouette and washing line.
        d.line([(22,14),(106,14)],fill='#8ca8ba',width=3)
        d.polygon([(47,22),(56,18),(72,18),(81,22),(101,38),(89,52),(80,45),(80,77),(48,77),(48,45),(39,52),(27,38)],fill='#73d8cb')
        d.arc((54,12,74,32),0,180,fill='#10212e',width=4)
    elif kind=='launcher':
        d.rounded_rectangle((29,12,99,77),radius=10,fill='#254b68',outline='#89c8ee',width=3)
        for y in (25,45):
            for x in (42,62,82):d.rounded_rectangle((x-5,y,x+5,y+10),radius=2,fill='#bce9f5')
    else:
        if kind in ('sun','partly'):
            x=64 if kind=='sun' else 44;y=43
            for i in range(8):
                a=i*math.pi/4
                d.line([(x+25*math.cos(a),y+25*math.sin(a)),(x+33*math.cos(a),y+33*math.sin(a))],fill='#ffd05a',width=4)
            d.ellipse((x-19,y-19,x+19,y+19),fill='#ffd05a')
        if kind!='sun':
            for box in [(29,35,67,67),(45,24,87,68),(67,39,103,68)]:d.ellipse(box,fill='#c2d8eb')
            d.rectangle((43,51,88,68),fill='#c2d8eb')
            if kind=='rain':
                for x in (42,64,86):d.line((x,75,x-5,85),fill='#61b8ff',width=4)
            if kind=='snow':
                for x in (43,65,87):d.ellipse((x-2,76,x+2,80),fill='white')
    return encode(image)


def detail_icon_card(title, value, kind, size=34):
    """Small header, isolated pictogram and large value; no explanatory prose."""
    from .desktop import panel
    import io,base64
    image=Image.open(io.BytesIO(base64.b64decode(panel([(title,19,0,'#b9d8ef'),(value,size,81,'white')]).split(',')[1]))).convert('RGB')
    icon=Image.new('RGBA',(80,52));d=ImageDraw.Draw(icon)
    if kind in ('sun','partly','cloud','rain','snow'):
        source=Image.open(io.BytesIO(base64.b64decode(icon_panel([],kind).split(',')[1]))).convert('RGB')
        source=source.crop((16,8,112,88)).resize((64,53),Image.Resampling.LANCZOS)
        image.paste(source,(32,26));return encode(image)
    if kind=='drop':
        d.polygon([(40,0),(22,25),(20,34),(24,44),(34,50),(46,50),(56,43),(60,33),(56,23)],fill='#61b8ff')
        d.arc((27,22,52,46),70,170,fill='white',width=3)
    elif kind=='wind':
        for y,end in [(10,60),(26,72),(42,54)]:
            d.line((5,y,end,y),fill='#9adfdb',width=4);d.arc((end-12,y-12,end+8,y+2),180,360,fill='#9adfdb',width=3)
    elif kind=='thermometer':
        d.rounded_rectangle((32,0,46,37),radius=7,outline='#ffb778',width=3)
        d.ellipse((26,29,52,51),fill='#ffb778');d.line((39,13,39,38),fill='#ffb778',width=5)
    elif kind=='clock':
        d.ellipse((16,1,65,50),outline='#b9d8ef',width=4);d.line((40,10,40,26,53,32),fill='white',width=4)
    image.paste(icon,(24,27),icon)
    return encode(image)
