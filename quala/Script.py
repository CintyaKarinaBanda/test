import sys
import os
sys.path.append(os.path.abspath('../funciones'))

import shutil
import requests
from datetime import datetime

from email_manager import send_email
from bd_manager import send_status
from excel_manager import write_report, write_comments, write_rds_dashboard_metrics
from aws_manager import get_instance_status, process_rds_metrics, get_rds_event_logs, process_rds_dashboard_metrics, return_comments, get_cloudwatch_alarms_status
from excel_manager import write_report, write_comments, write_rds_dashboard_metrics, write_cloudwatch_alarms
from config import SOURCE_FILENAME, REGION, FOLDER_ID, ACOUNT_NAME, API_LINK, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, CUENTA, PROJECT, CLOUDWATCH_ALARMS, TARGET_ACCOUNT_ID, CROSS_ACCOUNT_ROLE_NAME, VALIDACIONES_ACTIVAS

def verify_page(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return "Todo ok"
        else:
            return f"La página {url} devolvió {response.status_code}."
    except requests.exceptions.RequestException as e:
        print(f"No se pudo conectar a {url}. Error: {e}")


if __name__ == "__main__":
    print("Script iniciado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    today = datetime.now().strftime("%Y-%m-%d")
    target_filename = f"excel/CheckList_quala_{today}.xlsx"
    shutil.copy(SOURCE_FILENAME, target_filename)

    #instances_data = get_instance_status(REGION,ACOUNT_NAME)
    #write_report(instances_data, start_row=5, start_col=2, target_filename=target_filename)
    
    #rds_data = process_rds_metrics(RDS_ID, REGION, False)
    #write_report([rds_data], start_row=16, start_col=2, target_filename=target_filename)

    #rds_event_status = get_rds_event_logs(RDS_ID, REGION)
    #write_comments([rds_event_status], start_row=20, start_col=2, target_filename=target_filename)

    #rds_dashboard_data = process_rds_dashboard_metrics(RDS_ID, REGION)
    #write_rds_dashboard_metrics(rds_dashboard_data, start_row=25, start_col=2, target_filename=target_filename)

    api_availability = verify_page(API_LINK)
    write_comments([api_availability], start_row=20, start_col=8, target_filename=target_filename)
    
    # Monitoreo de alarmas de CloudWatch (cross-account)
    alarms_status = get_cloudwatch_alarms_status(REGION, CLOUDWATCH_ALARMS, TARGET_ACCOUNT_ID, CROSS_ACCOUNT_ROLE_NAME)
    write_cloudwatch_alarms(alarms_status, start_row=24, start_col=2, target_filename=target_filename)
    
    comentarios = return_comments()
    if not comentarios:
        comentarios.append('Todo Ok')
    write_comments(comentarios, start_row=14, start_col=15, target_filename=target_filename)

    for name in PROJECT:
        send_status(comentarios, CUENTA, name)

    send_email(target_filename, comentarios, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, VALIDACIONES_ACTIVAS)

    print("Script terminado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
