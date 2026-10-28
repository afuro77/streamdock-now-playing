"""Reusable forecast-based laundry estimate, independent of LCD rendering."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math

@dataclass(frozen=True)
class LaundryResult:
    grade: str
    reason: str
    target: str = ""
    rain_probability: float | None = None
    humidity: float | None = None
    wind_ms: float | None = None
    temperature: float | None = None


def laundry_window(now, settings=None):
    settings=settings or {}
    start_hour=int(settings.get('start_hour',8));end_hour=int(settings.get('end_hour',16))
    cutoff=int(settings.get('tomorrow_from_hour',14))
    target=now.date()+timedelta(days=1 if now.hour>=cutoff else 0)
    start=start_hour if target!=now.date() else max(start_hour,now.hour)
    return ('明日' if target!=now.date() else '今日',target,start,end_hour)


def assess_laundry(data, settings=None, now=None):
    settings=settings or {}
    target=''
    try:
        if now is None:
            now=datetime.now(timezone(timedelta(seconds=data.get('utc_offset_seconds',32400))))
        target,day,start,end=laundry_window(now,settings)
        times=[datetime.fromisoformat(t) for t in data['hourly']['time']]
        indices=[i for i,t in enumerate(times) if t.date()==day and start<=t.hour<end]
        if len(indices)!=end-start or end<=start:return LaundryResult('?','予報不足',target)
        names=('precipitation_probability','precipitation','relative_humidity_2m',
               'wind_speed_10m','temperature_2m','sunshine_duration')
        values=[[data['hourly'][name][i] for i in indices] for name in names]
        if any(any(x is None or not math.isfinite(float(x)) for x in v) for v in values):
            return LaundryResult('?', '予報不足',target)
        probability,rain,humidity,wind,temp,sun=values
        probability=max(probability); humidity=sum(humidity)/len(indices)
        wind=max(wind)/3.6; temp=sum(temp)/len(indices)
        metrics=dict(target=target,rain_probability=probability,humidity=humidity,wind_ms=wind,temperature=temp)
        if probability>=settings.get('rain_probability',30) or max(rain)>=.1:
            return LaundryResult('×','雨の可能性',**metrics)
        if wind>=settings.get('strong_wind_ms',8):
            return LaundryResult('×','強風',**metrics)
        if temp<10 or humidity>=80:
            return LaundryResult('△','乾きにくい',**metrics)
        if probability<=10 and humidity<=60 and temp>=18 and 1<=wind<=5 and sum(sun)>=7200:
            return LaundryResult('◎','外干し向き',**metrics)
        return LaundryResult('○','外干し可の目安',**metrics)
    except (KeyError,TypeError,ValueError,IndexError): return LaundryResult('?', '予報不足',target)
