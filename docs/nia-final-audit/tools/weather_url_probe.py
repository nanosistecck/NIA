import requests

base = 'https://api.open-meteo.com/v1/forecast?timezone=auto&forecast_days=7&latitude=-23.55&longitude=-46.63'
partes = [
    ('basico', '&current=temperature_2m,weather_code'),
    ('mais', '&current=temperature_2m,weather_code,apparent_temperature,relative_humidity_2m,wind_speed_10m'),
    ('pressao', '&current=temperature_2m,weather_code,pressure_msl'),
    ('visibilidade', '&current=temperature_2m,weather_code,visibility'),
    ('uv', '&current=temperature_2m,weather_code,uv_index'),
    ('time', '&current=temperature_2m,weather_code,time'),
    ('todo', '&current=temperature_2m,weather_code,apparent_temperature,relative_humidity_2m,wind_speed_10m,pressure_msl,visibility,uv_index,time'),
]
for nome, extra in partes:
    try:
        r = requests.get(base + extra, timeout=20)
        print(nome, r.status_code, r.text[:180].replace('\n', ' '))
    except Exception as exc:
        print(nome, 'ERRO', type(exc).__name__, str(exc)[:120])
