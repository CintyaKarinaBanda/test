import requests

def verify_page(url):
    #Funcion para consultar API
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return "Todo ok"
        elif response.status_code == 503:
            return f"Servicio temporalmente no disponible (503) - Servidor en mantenimiento o sobrecargado"
        elif response.status_code == 502:
            return f"Bad Gateway (502) - Error del servidor upstream"
        elif response.status_code == 504:
            return f"Gateway Timeout (504) - Servidor no responde"
        else:
            return f"Error HTTP {response.status_code}: {response.reason}"
    except requests.exceptions.Timeout:
        return f"Timeout: El servidor no respondió en 10 segundos"
    except requests.exceptions.ConnectionError:
        return f"Error de conexión: No se pudo conectar al servidor"
    except requests.exceptions.RequestException as e:
        return f"Error de solicitud: {e}"