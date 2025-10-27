import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'funciones'))

from datetime import datetime

#Funciones extraidas dentro del mismo proyecto
from email_manager import send_email
from bd_manager import send_status
from twilio_manager import consultar_twilio_messages
from config import REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, CUENTA, PROJECT, host, database, user, password, API_KEY, API_SECRET, ACCOUNT_SID


if __name__ == "__main__":
    print("Script iniciado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    monthList = [5, 6, 7]
    
    if (datetime.now().month not in monthList):
        #Actualizacion en Xoc
        send_status(["Todo Ok"], CUENTA, PROJECT, host, database, user, password)
    else:
        comentarios = []
        
        try:
            # Consulta Twilio
            resultado_twilio = consultar_twilio_messages(API_KEY, API_SECRET, ACCOUNT_SID)
            stats = resultado_twilio["estadisticas"]
            tiempo_resp = resultado_twilio["tiempo_respuesta"]
            
            print(f"Mensajes últimas 24h: {stats['total']}")
            print(f"Inbound: {stats['inbound']} | Outbound: {stats['outbound']}")
            if tiempo_resp["promedio"]:
                print(f"Tiempo respuesta promedio: {tiempo_resp['promedio']:.1f}s")
            
            if stats['total'] == 0:
                comentarios.append("Sin actividad en Twilio")
                
        except Exception as e:
            print(f"Error consultando Twilio: {e}")
            comentarios.append("Error Twilio")
        
        #Finalizar el CheckList
        final_comments = comentarios if comentarios else ["Todo Ok"]
        
        #Actualizacion en Xoc
        send_status(final_comments, CUENTA, PROJECT, host, database, user, password)
        
        parametros = {
            "Chats": ("Actividad en el chat", "Ok", "Nok")
        }
        #Envio de correo
        send_email(None, final_comments, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, parametros)

    print("Script terminado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))