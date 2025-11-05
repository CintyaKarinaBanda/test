import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'funciones'))

import shutil
from datetime import datetime

#Funciones extraidas dentro del mismo proyecto
from email_manager import send_email
from bd_manager import send_status
from excel_manager import write_report, write_column
from aws_managers import return_comments
from aws_managers.ec2 import process_ec2_metrics, return_ec2_comments
from config import SOURCE_FILENAME, REGION, ROLE_ARN, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, CUENTA, PROJECT, host, database, user, password

if __name__ == "__main__":
    print("Script iniciado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    today = datetime.now().strftime("%Y-%m-%d")
    target_filename = f"excel/CheckList_{today}.xlsx"
    shutil.copy(SOURCE_FILENAME, target_filename)

    comentarios = []

    try:
        # Monitoreo EC2
        ec2_data = process_ec2_metrics(REGION, ROLE_ARN, include_names=['lealtad'], exclude_names=['bastion'])
        write_report(ec2_data, start_row=5, start_col=2, target_filename=target_filename)
        
    except Exception as e:
        print(f"Error consultando EC2: {e}")
        comentarios.append("Error EC2")

    #Finalizar el CheckList
    comentarios.extend(return_comments())
    comentarios.extend(return_ec2_comments())
    final_comments = comentarios if comentarios else ['Todo Ok']
    write_column(final_comments, start_row=20, start_col=15, target_filename=target_filename)

    #Actualizacion en Xoc
    send_status(final_comments, CUENTA, PROJECT, host, database, user, password)
    
    parametros = {
        "Status Check": ("Estado de instancia, sistema y volumen", "Ok", "NoK"),
        "CPU Utilization": ("Menor al 85% en las instancias", "Ok", "NoK"),
    }
    
    #Envio de correo
    send_email(target_filename, final_comments, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, parametros)

    print("Script terminado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))