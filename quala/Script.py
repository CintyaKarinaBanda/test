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
from config import SOURCE_FILENAME, REGION, API_LINK, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, CUENTA, PROJECT, host, database, user, password


if __name__ == "__main__":
    print("Script iniciado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    today = datetime.now().strftime("%Y-%m-%d")
    target_filename = f"excel/CheckList_{today}.xlsx"
    shutil.copy(SOURCE_FILENAME, target_filename)
    
    comentarios = []
    
    try:
        # Verificación de API
        api_availability = verify_page(API_LINK)
        write_column([api_availability], start_row=5, start_col=2, target_filename=target_filename)
        
        if "Todo ok" not in api_availability:
            comentarios.append("Error en API")
            
    except Exception as e:
        print(f"Error verificando API: {e}")
        comentarios.append("Error API")
    
    #Finalizar el CheckList
    final_comments = comentarios if comentarios else ["Todo Ok"]
    write_column(final_comments, start_row=10, start_col=2, target_filename=target_filename)
    
    #Actualizacion en Xoc
    for project in PROJECT:
        send_status(final_comments, CUENTA, project, host, database, user, password)
    
    parametros = {
        "API": ("Disponibilidad de la API", "Ok", "Nok")
    }
    #Envio de correo
    send_email(target_filename, final_comments, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, parametros)

    print("Script terminado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
