from twilio.rest import Client
from datetime import datetime, timedelta, timezone
from collections import defaultdict

def create_client(API_KEY, API_SECRET, ACCOUNT_SID):
    try:
        return Client(API_KEY, API_SECRET, ACCOUNT_SID)
    except Exception as e:
        raise Exception(f"Error creando cliente Twilio: {e}")

def obtener_mensajes(client, periodo=24, limite=1000):
    try:
        since = datetime.now(timezone.utc) - timedelta(hours=periodo)
        
        # Usar filtros de fecha de Twilio directamente
        msgs = client.messages.list(
            date_sent_after=since,
            limit=limite
        )
        
        messages = []
        for m in msgs:
            dt = m.date_sent or m.date_created
            if dt:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                messages.append({
                    "sid": m.sid,
                    "from": str(m.from_),
                    "to": str(m.to),
                    "direction": m.direction,
                    "date": dt,
                })
        return messages
    except Exception as e:
        raise Exception(f"Error obteniendo mensajes: {e}")

def calcular_estadisticas(messages):
    total = len(messages)
    inbound = sum(1 for x in messages if "inbound" in (x["direction"] or ""))
    outbound = total - inbound
    return {"total": total, "inbound": inbound, "outbound": outbound}

def calcular_tiempo_respuesta(messages):
    by_user = defaultdict(list)
    for m in messages:
        key = m["from"] if "inbound" in (m["direction"] or "") else m["to"]
        by_user[key].append(m)

    deltas = []
    for user, ms in by_user.items():
        ms_sorted = sorted(ms, key=lambda x: x["date"])
        for i, msg in enumerate(ms_sorted):
            if "inbound" in (msg["direction"] or ""):
                for nxt in ms_sorted[i+1:]:
                    if "outbound" in (nxt["direction"] or ""):
                        delta = (nxt["date"] - msg["date"]).total_seconds()
                        if delta >= 0:
                            deltas.append(delta)
                        break
    
    if deltas:
        return {"promedio": sum(deltas) / len(deltas), "pares": len(deltas)}
    return {"promedio": None, "pares": 0}

def consultar_twilio_messages(API_KEY, API_SECRET, ACCOUNT_SID, periodo=24):
    try:
        client = create_client(API_KEY, API_SECRET, ACCOUNT_SID)
        messages = obtener_mensajes(client, periodo)
        stats = calcular_estadisticas(messages)
        tiempo_resp = calcular_tiempo_respuesta(messages)
        
        return {
            "estadisticas": stats,
            "tiempo_respuesta": tiempo_resp,
            "mensajes": messages
        }
    except Exception as e:
        raise Exception(f"Error en consulta Twilio: {e}")
