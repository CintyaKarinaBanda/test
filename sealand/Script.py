import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'funciones'))

import shutil
from datetime import datetime

#Funciones extraidas dentro del mismo proyecto
from email_manager import send_email
from bd_manager import send_status
from excel_manager import write_report, write_column
from aws_managers import process_rds_metrics, get_rds_event_logs, process_rds_dashboard_metrics, process_lambda_metrics, return_comments
from config import SOURCE_FILENAME, REGION, RDS_ID, ROLE_ARN, API_LINK, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, CUENTA, PROJECT, host, database, user, password

if __name__ == "__main__":
    print("Script iniciado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    today = datetime.now().strftime("%Y-%m-%d")
    target_filename = f"excel/CheckList_{today}.xlsx"
    shutil.copy(SOURCE_FILENAME, target_filename)

    lambda_data = process_lambda_metrics(REGION, ROLE_ARN)
    write_report(lambda_data, start_row=5, start_col=16, target_filename=target_filename)
    
    rds_data = process_rds_metrics(RDS_ID, REGION, ROLE_ARN, 'Sealand')
    write_report([rds_data], start_row=5, start_col=2, target_filename=target_filename)

    rds_event_status = get_rds_event_logs(RDS_ID, REGION, ROLE_ARN)
    write_column(rds_event_status, start_row=9, start_col=2, target_filename=target_filename)

    api_availability = verify_page(API_LINK)
    write_column([api_availability], start_row=9, start_col=8, target_filename=target_filename)

    #Finalizar el CheckList
    comentarios = return_comments()
    if not comentarios:
        comentarios.append('Todo Ok')
    write_column(comentarios, start_row=17, start_col=2, target_filename=target_filename)

    #Actualizacion en Xoc
    send_status(comentarios, CUENTA, PROJECT, host, database, user, password)
    
    parametros = {
        "CPU Utilization": ("Menor al 85% en RDS e instancias", "Ok", "NoK"),
        "Snapshot": ("Respaldo de RDS del día anterior", "Completado", "Incompleto")

    }
    #Envio de correo
    send_email(target_filename, comentarios, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, parametros)

    print("Script terminado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))