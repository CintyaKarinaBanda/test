import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'funciones'))

import shutil
from datetime import datetime

#Funciones extraidas dentro del mismo proyecto
from email_manager import send_email
from bd_manager import send_status
from excel_manager import write_report, write_column
from api_manager import verify_page
from aws_managers import process_rds_metrics, get_rds_event_logs, return_comments
from aws_managers.ec2 import process_ec2_metrics, return_ec2_comments
from config import SOURCE_FILENAME, REGION, ROLE_ARN, API_LINK, RDS_IDS, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, CUENTA, PROJECT, host, database, user, password


if __name__ == "__main__":
    print("Script iniciado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    today = datetime.now().strftime("%Y-%m-%d")
    target_filename = f"excel/CheckList_{today}.xlsx"
    shutil.copy(SOURCE_FILENAME, target_filename)
    
    comentarios = []
    
    try:
        # Monitoreo EC2
        ec2_data = process_ec2_metrics(REGION, ROLE_ARN, include_names=['quala'])
        write_report(ec2_data, start_row=5, start_col=2, target_filename=target_filename)
        
    except Exception as e:
        print(f"Error consultando EC2: {e}")
        comentarios.append("Error EC2")
    
    try:
        # Monitoreo RDS - Primera instancia
        rds_data_1 = process_rds_metrics(RDS_IDS[0], REGION, ROLE_ARN, 'Quala')
        write_report([rds_data_1], start_row=19, start_col=2, target_filename=target_filename)
        
        # Monitoreo RDS - Segunda instancia
        rds_data_2 = process_rds_metrics(RDS_IDS[1], REGION, ROLE_ARN, 'Quala')
        write_report([rds_data_2], start_row=20, start_col=2, target_filename=target_filename)
        
        # Eventos RDS
        rds_events_1 = get_rds_event_logs(RDS_IDS[0], REGION, ROLE_ARN)
        rds_events_2 = get_rds_event_logs(RDS_IDS[1], REGION, ROLE_ARN)
        write_column([rds_events_1, rds_events_2], start_row=24, start_col=2, target_filename=target_filename)
        
    except Exception as e:
        print(f"Error consultando RDS: {e}")
        comentarios.append("Error RDS")
    
    try:
        # Verificación de API
        api_availability = verify_page(API_LINK)
        write_column([api_availability], start_row=24, start_col=8, target_filename=target_filename)
        
        if "Todo ok" not in api_availability:
            comentarios.append("Error en API")
            
    except Exception as e:
        print(f"Error verificando API: {e}")
        comentarios.append("Error API")
    
    #Finalizar el CheckList
    comentarios.extend(return_comments())
    comentarios.extend(return_ec2_comments())
    final_comments = comentarios if comentarios else ["Todo Ok"]
    write_column(final_comments, start_row=17, start_col=15, target_filename=target_filename)
    
    #Actualizacion en Xoc
    for project in PROJECT:
        send_status(final_comments, CUENTA, project, host, database, user, password)
    
    parametros = {
        "Status Check": ("Estado de instancias EC2", "Ok", "NoK"),
        "CPU Utilization": ("Menor al 85% en RDS", "Ok", "NoK"),
        "API": ("Disponibilidad de la API", "Ok", "Nok")
    }
    #Envio de correo
    send_email(target_filename, final_comments, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, parametros)

    print("Script terminado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
