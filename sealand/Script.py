import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'funciones'))

import shutil
import requests
from datetime import datetime

#Funciones extraidas dentro del mismo proyecto
from email_manager import send_email
from bd_manager import send_status
from excel_manager import write_report, write_comments, write_rds_dashboard_metrics
from aws_managers import process_rds_metrics, get_rds_event_logs, process_rds_dashboard_metrics, process_lambda_metrics, return_comments
from config import SOURCE_FILENAME, REGION, FOLDER_ID, RDS_ID, ROLE_ARN, API_LINK, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, CUENTA, PROJECT

def verify_page(url):
    #Funcion para consultar API
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return "Todo ok"
        else:
            return f"La página {url} devolvió {response.status_code}."
    except requests.exceptions.RequestException as e:
        print(f"No se pudo conectar a {url}. Error: {e}")
        return f"Error de conexión a {url}: {e}"

if __name__ == "__main__":
    print("Script iniciado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    today = datetime.now().strftime("%Y-%m-%d")
    target_filename = f"excel/CheckList_{today}.xlsx"
    shutil.copy(SOURCE_FILENAME, target_filename)

    # Usar configuración específica para Sealand
    lambda_data = process_lambda_metrics(REGION, ROLE_ARN, 'Sealand')
    write_report(lambda_data, start_row=5, start_col=15, target_filename=target_filename)
    
    rds_data = process_rds_metrics(RDS_ID, REGION, ROLE_ARN, 'Sealand')
    write_report([rds_data], start_row=5, start_col=2, target_filename=target_filename)

    rds_event_status = get_rds_event_logs(RDS_ID, REGION, ROLE_ARN)
    write_comments([rds_event_status], start_row=9, start_col=2, target_filename=target_filename)

    rds_dashboard_data = process_rds_dashboard_metrics(RDS_ID, REGION, ROLE_ARN)
    write_rds_dashboard_metrics(rds_dashboard_data, start_row=14, start_col=2, target_filename=target_filename)

    api_availability = verify_page(API_LINK)
    write_comments([api_availability], start_row=9, start_col=8, target_filename=target_filename)

    #Finalizar el CheckList
    comentarios = return_comments()
    if not comentarios:
        comentarios.append('Todo Ok')
    write_comments(comentarios, start_row=21, start_col=7, target_filename=target_filename)

    #Actualizacion en Xoc
    #send_status(comentarios, CUENTA, PROJECT)
    
    #Envio de correo
    send_email(target_filename, comentarios, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT)

    print("Script terminado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))