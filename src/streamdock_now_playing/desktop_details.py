"""Desktop detail cards; each LCD remains a readable independent block."""
from datetime import datetime, timedelta, timezone
import time
from .laundry import assess_laundry, laundry_window


def weather_name(code):
    return '晴れ' if code==0 else '晴れ・曇り' if code<=2 else '曇り' if code==3 else '霧' if code<=48 else '雪' if code in (71,73,75,77,85,86) else '雷雨' if code>=95 else '雨'


def detail_cards(weather, kind, now=None):
    from .desktop import panel
    def card(*lines):
        return panel([(text, size, y, color) for text,size,y,color in lines])
    def block(title, lines):
        return card((title,20,2,'#b9d8ef'),*[(text,23,34+i*29,'white') for i,text in enumerate(lines[:3])])
    data=weather.data if weather else None
    if not data or weather.failed or time.monotonic()-weather.fetched>1800:
        return [block('天気' if kind=='weather' else '洗濯',['更新待ち'])]+[block('',[]) for _ in range(4)]+[block('戻る',['LCDを押す'])]
    now=now or datetime.now(timezone(timedelta(seconds=data.get('utc_offset_seconds',32400))))
    hourly=data.get('hourly',{});times=[datetime.fromisoformat(t) for t in hourly.get('time',[])]
    def values(name,indices):
        data=hourly.get(name,[])
        return [data[i] for i in indices if i<len(data) and data[i] is not None]
    from .desktop_icons import detail_icon_card
    def symbol(code):
        return 'sun' if code==0 else 'partly' if code<=2 else 'cloud' if code<=48 else 'snow' if code in (71,73,75,77,85,86) else 'rain'
    def aggregate(title,indices):
        temps=values('temperature_2m',indices);rain=values('precipitation_probability',indices);codes=values('weather_code',indices)
        if not temps:return block(title,['--']),detail_icon_card('降水','--','drop')
        return (detail_icon_card(title,f'{min(temps):.0f}〜{max(temps):.0f}℃',symbol(max(codes)) if codes else 'cloud',27),
                detail_icon_card('降水',f'{max(rain):.0f}%' if rain else '--','drop',36))
    if kind=='weather':
        current=data['current']
        tonight=[i for i,t in enumerate(times) if t.date()==now.date() and max(18,now.hour)<=t.hour<24]
        tomorrow=[i for i,t in enumerate(times) if t.date()==now.date()+timedelta(days=1) and 8<=t.hour<16]
        present=[i for i,t in enumerate(times) if t.date()==now.date() and t.hour==now.hour]
        rain=values('precipitation_probability',present)
        nt,nb=aggregate('今夜',tonight);tt,tb=aggregate('明日',tomorrow)
        return [detail_icon_card('現在',f"{current['temperature_2m']:.0f}℃",symbol(int(current['weather_code']))),nt,tt,
                detail_icon_card('降水',f'{max(rain):.0f}%' if rain else '--','drop',36),nb,tb]
    result=assess_laundry(data,weather.config.get('laundry',{}),now)
    target,day,start,end=laundry_window(now,weather.config.get('laundry',{}))
    def metric(value,suffix):return '--' if value is None else f'{value:.0f}'+suffix
    grade_color={'◎':'#73e6b1','○':'#73e6b1','△':'#ffd05a','×':'#ff8d8d'}.get(result.grade,'white')
    return [card((target+'の洗濯',19,0,'#b9d8ef'),(result.grade,65,24,grade_color)),
            detail_icon_card('判定時間',f'{start}〜{end}時','clock',28),
            detail_icon_card('降水',metric(result.rain_probability,'%'),'drop',36),
            detail_icon_card('湿度',metric(result.humidity,'%'),'drop',36),
            detail_icon_card('風',f'{result.wind_ms:.1f}m/s' if result.wind_ms is not None else '--','wind',29),
            detail_icon_card('気温',metric(result.temperature,'℃'),'thermometer',34)]

