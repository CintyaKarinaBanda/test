import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'funciones'))

import shutil
from datetime import datetime

#Funciones extraidas dentro del mismo proyecto
from email_manager import send_email
from bd_manager import send_status
from excel_manager import write_report, write_column
from twilio_manager import consultar_twilio_messages
from aws_managers.apigateway import process_apigateway_metrics
from config import SOURCE_FILENAME, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, CUENTA, PROJECT, host, database, user, password, API_KEY, API_SECRET, ACCOUNT_SID, REGION, ROLE_ARN


if __name__ == "__main__":
    print("Script iniciado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    today = datetime.now().strftime("%Y-%m-%d")
    target_filename = f"excel/CheckList_{today}.xlsx"
    shutil.copy(SOURCE_FILENAME, target_filename)
    
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
        
        # Escribir datos de Twilio en Excel
        inbound = stats['inbound']
        outbound = stats['outbound']
        twilio_data = [stats['total'], f'Entrada: {inbound}, Salida: {outbound}', tiempo_resp.get('promedio', 0)]
        write_column(twilio_data, start_row=10, start_col=3, target_filename=target_filename)
        
        if stats['total'] == 0:
            comentarios.append("Sin actividad en Twilio")
            
    except Exception as e:
        print(f"Error consultando Twilio: {e}")
        comentarios.append("Error Twilio")
    
    try:
        # Consulta API Gateway
        api_metrics = process_apigateway_metrics(REGION, ROLE_ARN)
        
        if api_metrics:
            print(f"APIs encontradas: {len(api_metrics)}")
            for api in api_metrics:
                print(f"API: {api[0]} - Requests: {api[3]}, Latencia: {api[6]}ms")
            write_report(api_metrics, start_row=5, start_col=2, target_filename=target_filename)
        else:
            comentarios.append("No se encontraron APIs")
            
    except Exception as e:
        print(f"Error consultando API Gateway: {e}")
        comentarios.append("Error API Gateway")
    
    
    #Finalizar el CheckList
    final_comments = comentarios if comentarios else ["Todo Ok"]
    write_column(final_comments, start_row=16, start_col=2, target_filename=target_filename)
    
    #Actualizacion en Xoc
    send_status(final_comments, CUENTA, PROJECT, host, database, user, password)
    
    parametros = {
        "Chats": ("Actividad en el chat", "Ok", "Nok"),
        "API Gateway": ("Estado de las APIs", "Ok", "Nok")
    }
    #Envio de correo
    send_email(target_filename, final_comments, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, parametros)

    print("Script terminado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))