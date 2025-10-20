import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'funciones'))

from datetime import datetime

#Funciones extraidas dentro del mismo proyecto
from email_manager import send_email
from bd_manager import send_status
from twilio_manager import consultar_twilio_messages
from aws_managers.apigateway import process_apigateway_metrics, return_apigateway_comments
from config import REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, CUENTA, PROJECT, host, database, user, password, API_KEY, API_SECRET, ACCOUNT_SID, REGION, ROLE_ARN


if __name__ == "__main__":
    print("Script iniciado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
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
    
    try:
        # Consulta API Gateway
        api_metrics = process_apigateway_metrics(REGION, ROLE_ARN)
        api_comments = return_apigateway_comments()
        
        if api_metrics:
            print(f"APIs encontradas: {len(api_metrics)}")
            for api in api_metrics:
                print(f"API: {api[0]} - Requests: {api[2]}, Latencia: {api[3]}ms")
        else:
            comentarios.append("No se encontraron APIs")
            
        comentarios.extend(api_comments)
        
    except Exception as e:
        print(f"Error consultando API Gateway: {e}")
        comentarios.append("Error API Gateway")
    
    status = "Todo Ok" if not comentarios else "Revisar"
    
    #Actualizacion en Xoc
    final_comments = comentarios if comentarios else ["Todo Ok"]
    send_status(final_comments, CUENTA, PROJECT, host, database, user, password)
    
    parametros = {
        "Chats": ("Actividad en el chat", "Ok" if status == "Todo Ok" else "Nok", "Nok"),
        "API Gateway": ("Estado de las APIs", "Ok" if status == "Todo Ok" else "Nok", "Nok")
    }
    #Envio de correo
    send_email(None, final_comments, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, parametros)

    print("Script terminado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))