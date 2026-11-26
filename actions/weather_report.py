"""Previsao do tempo FALADA (01/10/2026).

Ate esta data a ferramenta so abria uma busca do Google no navegador e
respondia, em ingles, "Showing the weather for Curitiba, today, sir." — o dono
perguntava "vai chover amanha?" e ouvia uma frase em ingles sem a previsao.
Sem cidade, a resposta era "Sir, the city is missing", tambem em ingles, mesmo
com a regra do cerebro mandando "chame assim mesmo, o PC usa a cidade
cadastrada" (cidade cadastrada que ninguem lia).

Agora a previsao vem do Open-Meteo (gratis, sem chave, ~0,3 s) e sai pronta
para falar: temperatura, ceu e chance de chuva, para hoje, amanha, um dia da
semana ou a semana inteira. Sem cidade: a da memoria do dono; depois a da
conexao de internet. So se a rede inteira falhar ele volta a abrir o navegador.
"""
import json
import time
import unicodedata
import urllib.parse
import urllib.request
import webbrowser
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

_RAIZ = Path(__file__).resolve().parents[1]
_TIMEOUT = 6

# Codigo do tempo (WMO) -> como se fala.
_CEU_PT = {
    0: "céu limpo", 1: "quase sem nuvens", 2: "parcialmente nublado", 3: "nublado",
    45: "neblina", 48: "neblina", 51: "garoa fraca", 53: "garoa", 55: "garoa forte",
    56: "garoa gelada", 57: "garoa gelada", 61: "chuva fraca", 63: "chuva",
    65: "chuva forte", 66: "chuva gelada", 67: "chuva gelada", 71: "neve fraca",
    73: "neve", 75: "neve forte", 77: "neve", 80: "pancadas de chuva fracas",
    81: "pancadas de chuva", 82: "pancadas de chuva fortes", 85: "neve", 86: "neve forte",
    95: "trovoadas", 96: "trovoadas com granizo", 99: "trovoadas com granizo",
}
_CEU_EN = {
    0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "freezing drizzle", 57: "freezing drizzle", 61: "light rain", 63: "rain",
    65: "heavy rain", 66: "freezing rain", 67: "freezing rain", 71: "light snow",
    73: "snow", 75: "heavy snow", 77: "snow", 80: "light showers", 81: "showers",
    82: "heavy showers", 85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail",
}
_DIAS_PT = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
_DIAS_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _em_ingles() -> bool:
    try:
        from core.idioma import em_ingles  # noqa: PLC0415
        return bool(em_ingles())
    except Exception:
        return False


def _sem_acento(t: str) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _baixar(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "NIA-CyberBot"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _cidade_da_memoria() -> str:
    """Cidade do dono guardada no longo prazo.

    19/11/2026: a identidade do dono nao guarda mais `city`, mas o endereco
    completo (`identity.address.value`, ex.: "Santa Maria das Barreiras,
    Estado do Pará"). Sem ler o campo `address` a previsao do tempo caia na
    localizacao da internet do PC e puxava um municipio errado.
    """
    try:
        dados = json.loads((_RAIZ / "memory" / "long_term.json").read_text(encoding="utf-8"))
        ident = dados.get("identity") or {}
        prioridade = ("city", "cidade", "hometown", "location", "address")
        achados: list[str] = []
        for chave in prioridade:
            valor = ident.get(chave) or {}
            valor = valor.get("value") if isinstance(valor, dict) else valor
            if valor:
                achados.append(str(valor).strip())
        for valor in achados:
            if valor:
                return valor
    except Exception:
        pass
    return ""


_CIDADE_IP = {"valor": "", "quando": 0.0}


def _cidade_da_internet() -> str:
    """A cidade da conexao do PC. Guardada por 6 h: ela nao muda a toda hora."""
    if _CIDADE_IP["valor"] and time.time() - _CIDADE_IP["quando"] < 6 * 3600:
        return _CIDADE_IP["valor"]
    for url, campo in (("https://ipapi.co/json/", "city"), ("https://ipinfo.io/json", "city")):
        try:
            v = str(_baixar(url).get(campo) or "").strip()
            if v:
                _CIDADE_IP.update(valor=v, quando=time.time())
                return v
        except Exception:
            continue
    return ""


def _onde(cidade: str) -> tuple:
    """(latitude, longitude, nome falado) da cidade pedida."""
    pedido = str(cidade or "").strip()
    if not pedido:
        raise LookupError(pedido)
    nome = pedido.split(",")[0].strip()
    lingua = "en" if _em_ingles() else "pt"
    url = ("https://geocoding-api.open-meteo.com/v1/search?count=5&format=json&language="
           + lingua + "&name=" + urllib.parse.quote(nome))
    achados = _baixar(url).get("results") or []
    if not achados:
        raise LookupError(pedido)
    # Com estado/pais no pedido ("Antonina, Parana"), prefere o que bate.
    resto = _sem_acento(pedido[len(nome):])
    melhor = achados[0]
    if resto.strip(" ,"):
        for a in achados:
            junto = _sem_acento(f"{a.get('admin1', '')} {a.get('country', '')}")
            if any(p and p in junto for p in resto.replace(",", " ").split()):
                melhor = a
                break
    return melhor["latitude"], melhor["longitude"], melhor.get("name") or nome


def _qual_dia(quando: str, hoje: date) -> int | None:
    """Indice do dia pedido (0 = hoje). None = a semana inteira."""
    q = _sem_acento(quando)
    if any(p in q for p in ("semana", "week", "proximos dias", "next days")):
        return None
    if "depois de amanha" in q or "day after tomorrow" in q:
        return 2
    if "amanha" in q or "tomorrow" in q:
        return 1
    for lista in (_DIAS_PT, _DIAS_EN):
        for i, nome in enumerate(lista):
            if _sem_acento(nome) in q:
                return (i - hoje.weekday()) % 7 or 0
    return 0


def _qual_turno(texto: str) -> str:
    """Turno ou hora pedida, para filtrar a previsão horária localmente."""
    import re
    q = _sem_acento(texto)
    # Hora explícita tem prioridade sobre "tarde" em "às 3h da tarde".
    hora = re.search(r"\b(\d{1,2})\s*(?:h\b|:(\d{2})\b|horas?\b)", q)
    if hora:
        h = int(hora.group(1))
        if h < 12 and re.search(r"\b(tarde|noite|pm)\b", q):
            h += 12
        if 0 <= h <= 23 and (hora.group(2) is None or int(hora.group(2)) < 60):
            return str(h)
    for padrao, turno in ((r"\b(manha|morning)\b", "manha"),
                          (r"\b(tarde|afternoon)\b|\bmeio[ -]?dia\b", "tarde"),
                          (r"\b(noite|night|evening)\b", "noite"),
                          (r"\b(madrugada|dawn)\b", "madrugada")):
        if re.search(padrao, q):
            return turno
    return ""


def _hora_local_atual(dados: dict, agora=None) -> int | None:
    """Hora local da cidade consultada.

    O Open-Meteo **não** aceita `time` dentro de `current` (HTTP 400). Com
    `timezone=auto` ele devolve `utc_offset_seconds`; a hora local é calculada
    a partir do UTC + esse offset, sem depender do fuso do PC. Mantemos a
    leitura de `current.time` apenas para respostas antigas/ caches que já
    tenham o campo.
    """
    dados = dados or {}
    atual = dados.get("current") or {}
    valor = str(atual.get("time") or "")
    if valor:
        try:
            hora = int(valor[11:13])
            return hora if 0 <= hora <= 23 else None
        except (TypeError, ValueError, IndexError):
            return None
    try:
        offset = int(dados.get("utc_offset_seconds"))
    except (TypeError, ValueError):
        return None
    agora = agora or datetime.now(timezone.utc)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=timezone.utc)
    hora = (agora + timedelta(seconds=offset)).hour
    return hora if 0 <= hora <= 23 else None


def _filtrar_horas(horas: list[dict], turno: str, desde: int | None = None) -> list[dict]:
    """Filtra por turno/hora; `desde` limita às horas restantes do turno."""
    if not turno:
        return list(horas or [])
    resultado = []
    for item in horas or []:
        try:
            hora = int(str(item.get("hora", ""))[:2])
        except (TypeError, ValueError):
            continue
        if desde is not None and not turno.isdigit() and hora < desde:
            continue
        if turno == "manha" and 5 <= hora < 12:
            resultado.append(item)
        elif turno == "tarde" and 12 <= hora < 18:
            resultado.append(item)
        elif turno == "noite" and hora >= 18:
            resultado.append(item)
        elif turno == "madrugada" and hora < 5:
            resultado.append(item)
        elif turno.isdigit() and hora == int(turno):
            resultado.append(item)
    return resultado


def _numero_ou_none(valor):
    if valor is None:
        return None
    try:
        return round(float(valor), 1)
    except (TypeError, ValueError):
        return None


def _card_do_tempo(dados: dict, nome: str, quando: str, en: bool) -> dict | None:
    """Dados estruturados para o Canvas, da MESMA resposta do Open-Meteo."""
    daily = dados.get("daily") or {}
    tempos = list(daily.get("time") or [])
    if not tempos:
        return None
    try:
        hoje = date.fromisoformat(str(tempos[0])[:10])
    except Exception:
        return None
    indice = _qual_dia(quando, hoje)
    semana = indice is None
    solicitada = hoje + timedelta(days=0 if semana else indice)
    codigos = list(daily.get("weather_code") or [])
    minimas = list(daily.get("temperature_2m_min") or [])
    maximas = list(daily.get("temperature_2m_max") or [])
    chuvas = list(daily.get("precipitation_probability_max") or [])
    ceu = _CEU_EN if en else _CEU_PT
    dias = []
    for k, iso in enumerate(tempos[:7]):
        try:
            dia = date.fromisoformat(str(iso)[:10])
        except Exception:
            continue
        codigo = codigos[k] if k < len(codigos) else None
        try:
            condicao = ceu.get(int(codigo), "") if codigo is not None else ""
        except (TypeError, ValueError):
            condicao = ""
        dias.append({
            "data": str(iso)[:10],
            "dia_semana": ((_DIAS_EN if en else _DIAS_PT)[dia.weekday()]),
            "codigo": codigo,
            "condicao": condicao,
            "min": _numero_ou_none(minimas[k] if k < len(minimas) else None),
            "max": _numero_ou_none(maximas[k] if k < len(maximas) else None),
            # 0% é valor válido: só some quando o campo não veio.
            "chuva": (_numero_ou_none(chuvas[k])
                      if k < len(chuvas) and chuvas[k] is not None else None),
        })
    if not dias:
        return None
    destaque = dict(next((dia for dia in dias if dia['data'] == solicitada.isoformat()),
                        {'data': solicitada.isoformat(),
                         'condicao': 'Forecast unavailable' if en else 'Previsão indisponível'}))
    if solicitada == hoje:
        atual = dados.get("current") or {}
        destaque.update({
            "agora": _numero_ou_none(atual.get("temperature_2m")),
            "sensacao": _numero_ou_none(atual.get("apparent_temperature")),
            "umidade": _numero_ou_none(atual.get("relative_humidity_2m")),
            "vento": _numero_ou_none(atual.get("wind_speed_10m")),
        })

    # Campos ricos da prancha (todos locais, derivados da mesma resposta).
    atual = dados.get("current") or {}
    diario = dados.get("daily") or {}
    horario = dados.get("hourly") or {}
    i_dia = 0 if solicitada.isoformat() == tempos[0] else next(
        (k for k, iso in enumerate(tempos) if iso[:10] == solicitada.isoformat()), 0)

    def _diario(chave, indice=i_dia):
        lista = diario.get(chave) or []
        return lista[indice] if indice < len(lista) else None

    visibilidade = atual.get("visibility")
    try:
        visibilidade = round(float(visibilidade) / 1000.0, 1)  # m -> km
    except (TypeError, ValueError):
        visibilidade = None
    destaque.update({
        "pressao": _numero_ou_none(atual.get("pressure_msl")),
        "visibilidade": visibilidade,
        "uv": _numero_ou_none(atual.get("uv_index") or _diario("uv_index_max")),
        "nascer": _diario("sunrise"),
        "poente": _diario("sunset"),
    })

    horas = []
    tempos_h = list(horario.get("time") or [])
    def _horario(chave, indice):
        valores = horario.get(chave) or []
        return valores[indice] if indice < len(valores) else None

    for k, iso in enumerate(tempos_h):
        if str(iso)[:10] != solicitada.isoformat():
            continue
        horas.append({
            "hora": str(iso)[11:16],
            "temp": _numero_ou_none(_horario("temperature_2m", k)),
            "chuva": _numero_ou_none(_horario("precipitation_probability", k)),
            "codigo": _horario("weather_code", k),
        })
    try:
        chuva_max = max((h["chuva"] for h in horas if h["chuva"] is not None), default=None)
    except (TypeError, ValueError):
        chuva_max = None
    chance = destaque.get("chuva")
    if chuva_max is not None and (chance is None or chuva_max > chance):
        chance = chuva_max
    destaque["alerta"] = (
        "Alerta: chuva forte e trovoadas hoje ({}%). Evite áreas abertas.".format(
            round(chance)) if (chance is not None and chance >= 70
                               and int(destaque.get("codigo") or 0) in (95, 96, 99))
        else "")

    return {
        "tipo": "clima",
        "cidade": nome,
        "fuso": str(dados.get("timezone") or ""),
        "semana": semana,
        "destaque": destaque,
        "dias": dias,
        "horas": horas,
    }


def _emitir_card(player, card: dict) -> None:
    if not card:
        return
    mostrar = getattr(player, "show_canvas_brief", None)
    if callable(mostrar):
        try:
            mostrar(card)
        except Exception:
            pass


def _frase_do_dia(d: dict, i: int, en: bool) -> str:
    def valor(campo):
        valores = d.get(campo) or []
        return _numero_ou_none(valores[i]) if i < len(valores) else None

    codigo = valor('weather_code')
    ceu = (_CEU_EN if en else _CEU_PT).get(int(codigo), '') if codigo is not None else ''
    minima, maxima = valor('temperature_2m_min'), valor('temperature_2m_max')
    chuva = valor('precipitation_probability_max')
    partes = [ceu] if ceu else []
    if minima is not None and maxima is not None:
        partes.append(f'from {round(minima)} to {round(maxima)} degrees' if en
                      else f'de {round(minima)} a {round(maxima)} graus')
    elif minima is not None:
        partes.append(f'low of {round(minima)} degrees' if en else f'mínima de {round(minima)} graus')
    elif maxima is not None:
        partes.append(f'high of {round(maxima)} degrees' if en else f'máxima de {round(maxima)} graus')
    if chuva is not None:
        partes.append(f'{chuva:g}% chance of rain' if en else f'{chuva:g}% de chance de chuva')
    return ', '.join(partes) or ('Forecast unavailable' if en else 'Previsão indisponível')


def _frase_do_periodo(horas: list[dict], en: bool) -> str:
    """Resume apenas o intervalo pedido, sem substituir ausências por dados diários."""
    temperaturas = [h["temp"] for h in horas if h.get("temp") is not None]
    chuvas = [h["chuva"] for h in horas if h.get("chuva") is not None]
    codigos = list(dict.fromkeys(h["codigo"] for h in horas if h.get("codigo") is not None))
    diario = {
        "weather_code": [],
        "temperature_2m_min": [min(temperaturas)] if temperaturas else [],
        "temperature_2m_max": [max(temperaturas)] if temperaturas else [],
        "precipitation_probability_max": [max(chuvas)] if chuvas else [],
    }
    ceus = (_CEU_EN if en else _CEU_PT)
    condicoes = list(dict.fromkeys(ceus[c] for c in codigos if c in ceus))
    resumo = _frase_do_dia(diario, 0, en)
    if condicoes:
        condicao = (" / ").join(condicoes)
        if not temperaturas and not chuvas:
            return condicao
        return condicao + ", " + resumo
    return resumo


def weather_action(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    en = _em_ingles()
    cidade = str(params.get("city") or "").strip()
    quando = str(params.get("time") or params.get("when") or params.get("day") or "hoje").strip()
    if not cidade:
        cidade = _cidade_da_memoria() or _cidade_da_internet()
    if not cidade:
        msg = "Which city, sir?" if en else "Para qual cidade, senhor?"
        _log(msg, player)
        return msg
    try:
        lat, lon, nome = _onde(cidade)
        dados = _baixar(
            "https://api.open-meteo.com/v1/forecast?timezone=auto&forecast_days=7"
            f"&latitude={lat}&longitude={lon}"
            "&current=temperature_2m,weather_code,apparent_temperature,"
            "relative_humidity_2m,wind_speed_10m,pressure_msl,visibility,"
            "uv_index"
            "&hourly=temperature_2m,precipitation_probability,weather_code"
            "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max,sunrise,sunset,uv_index_max")
        d = dados["daily"]
        hoje = date.fromisoformat(d["time"][0])
        i = _qual_dia(quando, hoje)
        if i is None:
            partes = []
            for k in range(min(5, len(d["time"]))):
                dia = date.fromisoformat(d["time"][k])
                rotulo = (("today" if en else "hoje") if k == 0 else
                          ("tomorrow" if en else "amanhã") if k == 1 else
                          (_DIAS_EN if en else _DIAS_PT)[dia.weekday()])
                partes.append(f"{rotulo}: {_frase_do_dia(d, k, en)}")
            msg = (f"Next days in {nome}: " if en else f"Próximos dias em {nome}: ") + "; ".join(partes) + "."
        else:
            dia = hoje + timedelta(days=i)
            if dia.isoformat() not in d['time']:
                card = _card_do_tempo(dados, nome, quando, en)
                if card:
                    card['token'] = int(params.get('_brief_token') or 0)
                    _emitir_card(player, card)
                msg = (f'Forecast unavailable for {dia:%d/%m/%Y} in {nome}.' if en
                       else f'Previsão indisponível para {dia:%d/%m/%Y} em {nome}.')
                _log(msg, player)
                return msg
            i = d['time'].index(dia.isoformat())
            rotulo = (("Today" if en else "Hoje") if i == 0 else
                      ("Tomorrow" if en else "Amanhã") if i == 1 else
                      ("On " + _DIAS_EN[dia.weekday()].capitalize() if en
                       else "Na " + _DIAS_PT[dia.weekday()] if dia.weekday() < 5
                       else "No " + _DIAS_PT[dia.weekday()]))
            turno = _qual_turno(quando)
            if turno:
                card_previo = _card_do_tempo(dados, nome, quando, en)
                horas = _filtrar_horas((card_previo or {}).get("horas") or [], turno)
                if "agora" in _sem_acento(quando):
                    # Só as horas que ainda podem acontecer na cidade consultada.
                    # `utc_offset_seconds` vem com timezone=auto, então a hora
                    # local não depende do fuso do PC. Sem ele, turno inteiro.
                    desde = _hora_local_atual(dados)
                    if desde is not None:
                        restantes = _filtrar_horas(
                            (card_previo or {}).get("horas") or [], turno, desde)
                        if restantes:
                            horas = restantes
                rotulos = ({"manha": "in the morning", "tarde": "in the afternoon",
                            "noite": "at night", "madrugada": "in the early morning"} if en else
                           {"manha": "pela manhã", "tarde": "à tarde",
                            "noite": "à noite", "madrugada": "de madrugada"})
                periodo = rotulos.get(turno, f"at {int(turno):02d}:00" if turno.isdigit() and en
                                      else f"às {int(turno):02d}:00" if turno.isdigit() else turno)
                resumo = _frase_do_periodo(horas, en)
                msg = f"{rotulo}, {periodo}, {'in' if en else 'em'} {nome}: {resumo}."
            else:
                msg = f"{rotulo} {'in' if en else 'em'} {nome}: {_frase_do_dia(d, i, en)}."
                agora = (dados.get("current") or {}).get("temperature_2m")
                if i == 0 and agora is not None:
                    msg += (f" Right now it's {round(agora)} degrees." if en
                            else f" Agora faz {round(agora)} graus.")
        # O MESMO resultado alimenta a fala e o card. Só há card depois de
        # uma consulta bem-sucedida: erro não reaproveita dado velho.
        card = _card_do_tempo(dados, nome, quando, en)
        if card:
            card["token"] = int(params.get("_brief_token") or 0)
            _emitir_card(player, card)
        _log(msg, player)
        if session_memory:
            try:
                session_memory.set_last_search(query=f"tempo {cidade} {quando}", response=msg)
            except Exception:
                pass
        return msg
    except LookupError:
        msg = (f"I couldn't find the city {cidade}, sir." if en
               else f"Não achei a cidade {cidade}, senhor.")
        _log(msg, player)
        return msg
    except Exception as exc:
        # Sem rede para a previsao: o jeito antigo, mas dito na lingua dele.
        _log(f"previsao falhou: {exc}", player)
        try:
            webbrowser.open("https://www.google.com/search?q="
                            + quote_plus(f"previsao do tempo {cidade} {quando}"))
            return (f"I couldn't get the forecast now, so I opened it in the browser for {cidade}."
                    if en else
                    f"Não consegui buscar a previsão agora; abri o tempo de {cidade} no navegador.")
        except Exception:
            return ("I couldn't get the weather right now, sir." if en
                    else "Não consegui ver a previsão do tempo agora, senhor.")


def _log(message: str, player=None) -> None:
    print(f"[Weather] {message}")
    if player:
        try:
            player.write_log(f"NIA: {message}")
        except Exception:
            pass
