import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'funciones'))


from datetime import datetime

#Funciones extraidas dentro del mismo proyecto
from bd_manager import send_status
from api_manager import verify_page
from email_manager import send_email
from config import API_LINK, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, CUENTA, PROJECT, host, database, user, password

if __name__ == "__main__":
    print("Script iniciado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    api_availability = verify_page(API_LINK)
    
    # Generar comentarios basado en disponibilidad de API
    comentarios = "Todo Ok" if api_availability else "API no disponible"

    #Actualizacion en Xoc
    send_status(comentarios, CUENTA, PROJECT, host, database, user, password)
    
    parametros = {
        "Status Pagina Web": ("Si la página esta arriba", "Ok", "NoK"),
    }
    
    #Envio de correo
    send_email(None, comentarios, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, parametros)

    print("Script terminado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))