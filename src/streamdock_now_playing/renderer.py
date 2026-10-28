"""Artwork splitting and temporary overlay images extracted from v1."""
import base64, io, os
import math
import time
from dataclasses import dataclass, fields
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

def encode(image):
 b=io.BytesIO(); image.save(b,'PNG'); return 'data:image/png;base64,'+base64.b64encode(b.getvalue()).decode()

def tiles(data):
 im=Image.open(io.BytesIO(data)).convert('RGB') if data else Image.new('RGB',(384,256),'#142b25')
 # Fit preserves the square cover's proportions, cropping top/bottom to fill 3:2.
 canvas=ImageOps.fit(im,(384,256),method=Image.Resampling.LANCZOS)
 return [encode(canvas.crop((x*128,y*128,(x+1)*128,(y+1)*128))) for y in range(2) for x in range(3)]

def card(text):
 im=Image.new('RGB',(128,128),'#10261f'); d=ImageDraw.Draw(im)
 try: font=ImageFont.truetype(str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'meiryo.ttc'),14)
 except OSError: font=ImageFont.load_default()
 lines=[]
 for part in text.split('\n'):
  while part:
   n=min(len(part),12)
   while n>1 and d.textlength(part[:n],font=font)>120:n-=1
   lines.append(part[:n]);part=part[n:]
 d.multiline_text((4,8),'\n'.join(lines[:6]),font=font,fill='white',spacing=4)
 return encode(im)


@dataclass(frozen=True)
class DisplaySettings:
    title_font_size: int = 32
    title_min_font_size: int = 28
    artist_font_size: int = 20
    album_font_size: int = 11
    status_font_size: int = 32
    time_font_size: int = 32
    feedback_font_size: int = 40
    expanded_title_font_size: int = 48
    expanded_artist_font_size: int = 36
    expanded_scroll_step_seconds: float = .55  # Legacy config compatibility; unused.
    expanded_scroll_pixels_per_second: float = 36.0
    expanded_scroll_pause_seconds: float = 0.0
    expanded_timeout_seconds: float = 30.0
    title_lines: int = 3
    artist_lines: int = 1
    text_overflow: str = 'ellipsis'
    show_album: bool = False
    show_progress: bool = True
    feedback_seconds: float = 2.5

    @classmethod
    def from_config(cls, values):
        if not isinstance(values, dict):
            raise ValueError('display must be an object')
        known = {f.name for f in fields(cls)}
        if set(values) - known:
            raise ValueError('Unknown display setting')
        settings = cls(**values)
        for name, low, high in (('expanded_scroll_pixels_per_second', 1, 120),
                                ('expanded_scroll_step_seconds', .1, 5),
                                ('expanded_scroll_pause_seconds', 0, 10),
                                ('expanded_timeout_seconds', 1, 600)):
            value = getattr(settings, name)
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError('Invalid expanded display timing')
        for field in fields(cls):
            value = getattr(settings, field.name)
            limit = 96 if field.name.startswith('expanded_') else 48
            if field.name.endswith('_font_size') and (type(value) is not int or not 8 <= value <= limit):
                raise ValueError('Font size is outside the supported range')
        if settings.title_min_font_size > settings.title_font_size:
            raise ValueError('Minimum title font cannot exceed maximum')
        for name in ('title_lines', 'artist_lines'):
            if type(getattr(settings, name)) is not int or not 1 <= getattr(settings, name) <= 3:
                raise ValueError('Text line counts must be from 1 to 3')
        if settings.text_overflow not in ('ellipsis', 'clip'):
            raise ValueError('text_overflow must be ellipsis or clip')
        if any(type(getattr(settings, name)) is not bool for name in ('show_album', 'show_progress')):
            raise ValueError('Display visibility settings must be booleans')
        if (type(settings.feedback_seconds) not in (int, float) or
            not math.isfinite(settings.feedback_seconds) or not .1 <= settings.feedback_seconds <= 60):
            raise ValueError('feedback_seconds must be from 0.1 to 60')
        return settings


def _font(size, bold=False):
    try:
        return ImageFont.truetype(str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / ('meiryob.ttc' if bold else 'meiryo.ttc')), size)
    except OSError:
        return ImageFont.load_default(size=size)


def fit_lines(text, font, width, count, overflow='ellipsis'):
    """Pixel-measured wrapping; leave room for a visible truncation marker."""
    remaining = ' '.join(str(text or '').split())
    lines = []
    for index in range(count):
        if not remaining:
            break
        n = len(remaining)
        while n > 0 and font.getlength(remaining[:n]) > width:
            n -= 1
        if n == 0:
            break
        if index == count - 1 and n < len(remaining) and overflow == 'ellipsis':
            while n > 0 and font.getlength(remaining[:n].rstrip() + '…') > width:
                n -= 1
            lines.append(remaining[:n].rstrip() + '…')
            break
        # Prefer word boundaries for Latin text, while supporting Japanese.
        if n < len(remaining) and ' ' in remaining[:n] and index < count - 1:
            boundary = remaining.rfind(' ', 0, n + 1)
            if boundary > 0:
                n = boundary
        lines.append(remaining[:n].rstrip())
        remaining = remaining[n:].lstrip()
    return lines


def _seconds(value):
    try:
        value = float(value)
        return max(0, value) if math.isfinite(value) else 0
    except (TypeError, ValueError):
        return 0


def clock_text(value):
    seconds = int(_seconds(value))
    return f'{seconds // 3600}:{seconds // 60 % 60:02}:{seconds % 60:02}' if seconds >= 3600 else f'{seconds // 60}:{seconds % 60:02}'


class LayoutRenderer:
    """v1.1: four immutable artwork tiles plus two independent information tiles."""
    def __init__(self, settings=None):
        self.settings = DisplaySettings.from_config(settings or {})
        self._scroll_rows = {}

    def reset_metadata_scroll(self):
        self._scroll_rows.clear()

    def text_row(self, text, size, bold, row, now):
        """One continuous 384px viewport, with independent pixel scrolling."""
        text = ' '.join(str(text or '').split())
        key = (text, size, bold)
        state = self._scroll_rows.get(row)
        if state is None or state['key'] != key:
            font = _font(size, bold)
            bounds = font.getbbox(text, anchor='ls')
            width = max(font.getlength(text), bounds[2])-min(0, bounds[0])
            state = dict(key=key, start=now, font=font, width=width,
                         bearing=min(0, bounds[0]))
            self._scroll_rows[row] = state
        width = state['width']
        if width <= 372:
            x = (384-width)/2
        else:
            speed = self.settings.expanded_scroll_pixels_per_second
            # Repeat after a small blank gap, allowing both copies on screen.
            gap = 64
            pitch = width+gap
            offset = (max(0, now-state['start'])*speed) % pitch
            x = 6-offset
            marker = '｜'
            marker_width = state['font'].getlength(marker)
            positions = [(text, x-state['bearing']),
                         (marker, x+width+(gap-marker_width)/2),
                         (text, x+pitch-state['bearing'])]
            return state['font'], positions
        return state['font'], [(text, x-state['bearing'])]

    def artwork(self, data):
        canvas = Image.new('RGB', (256, 256), '#142b25')
        if data:
            image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('RGB')
            image = ImageOps.contain(image, canvas.size, method=Image.Resampling.LANCZOS)
            canvas.paste(image, ((256 - image.width) // 2, (256 - image.height) // 2))
        return [encode(canvas.crop((x*128, y*128, (x+1)*128, (y+1)*128))) for y in range(2) for x in range(2)]

    @staticmethod
    def split_canvas(canvas):
        return [encode(canvas.crop((x*128, y*128, (x+1)*128, (y+1)*128)))
                for y in range(2) for x in range(3)]

    def expanded_artwork(self, data):
        canvas = Image.new('RGB', (384, 256), '#142b25')
        if data:
            image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('RGB')
            image = ImageOps.contain(image, canvas.size, method=Image.Resampling.LANCZOS)
            canvas.paste(image, ((384-image.width)//2, (256-image.height)//2))
        return self.split_canvas(canvas)

    def artist_lines(self, text):
        text = ' '.join(str(text or '').split())
        if not text:
            return ['', '']
        font = _font(self.settings.expanded_artist_font_size)
        bounds = font.getbbox(text, anchor='ls')
        width = max(font.getlength(text), bounds[2])-min(0, bounds[0])
        if width <= 372:
            return [text, '']
        # Prefer a word boundary and balance the two full strings; never truncate.
        boundaries = [(text[:i].rstrip(), text[i:].lstrip())
                      for i, char in enumerate(text) if char == ' ']
        if not boundaries:
            boundaries = [(text[:i+1], text[i+1:])
                          for i, char in enumerate(text[:-1]) if char in '・／/、']
        if not boundaries and any('\u3040' <= char <= '\u9fff' for char in text):
            boundaries = [(text[:i], text[i:]) for i in range(1, len(text))]
        if not boundaries:
            return [text, '']
        return list(min(boundaries, key=lambda parts: max(font.getlength(parts[0]), font.getlength(parts[1]))))

    def expanded_metadata(self, snapshot, now=None):
        now = time.monotonic() if now is None else now
        canvas = Image.new('RGB', (384, 256), '#10261f')
        draw = ImageDraw.Draw(canvas)
        artists = self.artist_lines(snapshot.get('artist'))
        rows = [(0, snapshot.get('title') or 'No media', self.settings.expanded_title_font_size, True, 0, 128)]
        if artists[1]:
            rows += [(1, artists[0], self.settings.expanded_artist_font_size, False, 128, 64),
                     (2, artists[1], self.settings.expanded_artist_font_size, False, 192, 64)]
        else:
            rows += [(1, artists[0], self.settings.expanded_artist_font_size, False, 128, 128)]
        for row, text, size, bold, top, height in rows:
            font, glyphs = self.text_row(text, size, bold, row, now)
            bounds = font.getbbox('Agあ', anchor='ls')
            y = top + (height-(bounds[3]-bounds[1]))//2 - bounds[1]
            for char, x in glyphs:
                draw.text((x, y), char, font=font, fill='white' if bold else '#e3f1eb', anchor='ls')
        return self.split_canvas(canvas)

    def metadata(self, snapshot, detailed=False):
        image = Image.new('RGB', (128, 128), '#10261f')
        draw = ImageDraw.Draw(image)
        artist = snapshot.get('artist') or ''
        artist_size = self.settings.artist_font_size
        artist_height = artist_size + 3 if artist else 0
        title_height = 120 - artist_height - (6 if artist else 0)
        size = self.settings.title_font_size
        while True:
            font = _font(size, bold=True)
            lines = fit_lines(snapshot.get('title') or 'No media', font, 120,
                              self.settings.title_lines, self.settings.text_overflow)
            if len(lines)*(size+1) <= title_height or size <= self.settings.title_min_font_size:
                break
            size -= 1
        y = 4
        available = max(1, int(title_height // (size+1)))
        lines = fit_lines(snapshot.get('title') or 'No media', font, 120,
                          min(self.settings.title_lines, available), self.settings.text_overflow)
        for line in lines:
            draw.text((4, y), line, font=font, fill='white', anchor='lt')
            y += size+1
        if artist:
            line = fit_lines(artist, _font(artist_size), 120, 1, self.settings.text_overflow)
            if line:
                draw.text((4, min(124-artist_height, y+6)), line[0], font=_font(artist_size), fill='#e3f1eb', anchor='lt')
        # Both information modes retain the same readable pane; no album/header.
        return encode(image)

    def status(self, snapshot, feedback=''):
        image = Image.new('RGB', (128, 128), '#10261f')
        draw = ImageDraw.Draw(image)
        if feedback:
            words = feedback.split()
            lines = words if len(words) <= 2 else None
            size = self.settings.feedback_font_size
            if lines:
                while size > 16 and any(_font(size, True).getlength(line) > 120 for line in lines):
                    size -= 1
            font = _font(size, True)
            if not lines:
                lines = fit_lines(feedback, font, 120, 2, self.settings.text_overflow)
            y = max(4, (128-len(lines)*(size+5))//2)
            for line in lines:
                draw.text((4, y), line, font=font, fill='white', anchor='lt')
                y += size + 5
            return encode(image)
        playing = snapshot.get('playing')
        label = 'PLAY' if playing is True else 'PAUSE' if playing is False else 'READY'
        size = self.settings.status_font_size
        while size > 16 and _font(size, True).getlength(label) > 120:
            size -= 1
        draw.text((4, 8), label, font=_font(size, True), fill='white', anchor='lt')
        position, duration = _seconds(snapshot.get('position')), _seconds(snapshot.get('duration'))
        time_text = clock_text(position)
        size = self.settings.time_font_size
        while size > 8 and _font(size, True).getlength(time_text) > 116:
            size -= 1
        lines = fit_lines(time_text, _font(size, True), 116, 2, self.settings.text_overflow)
        for index, line in enumerate(lines):
            draw.text((4, 61 + index*(size+4)), line, font=_font(size, True), fill='white', anchor='lt')
        if self.settings.show_progress and duration > 0:
            draw.rounded_rectangle((6, 109, 122, 115), radius=3, fill='#345346')
            progress = int(116 * min(1, position / duration))
            if progress:
                draw.rectangle((6, 109, 6+progress, 115), fill='#71cbaa')
        return encode(image)

    def compose(self, artwork, snapshot, feedback='', detailed=False):
        # Physical row-major order: [art TL, art TR, metadata, art BL, art BR, status].
        return [artwork[0], artwork[1], self.metadata(snapshot, detailed), artwork[2], artwork[3], self.status(snapshot, feedback)]


def operation_feedback(command, result, snapshot):
    """Presentation only: do not report a rejected operation as successful."""
    if command == 'play' and result == 'Play / Pause':
        playing = snapshot.get('playing')
        return 'PAUSE' if playing is True else 'PLAY' if playing is False else 'PLAY / PAUSE'
    text = str(result).upper()
    if text.startswith('VOLUME '):
        text = 'VOL ' + text[len('VOLUME '):]
    return 'PREV' if text == 'PREVIOUS' else text

