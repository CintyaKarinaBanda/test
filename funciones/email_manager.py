import yagmail

#Funcion para envio del correo
def send_email(archivo_adjunto, comentarios, remitente, password, destinatario, copias, cuenta, parametros):
    #Diseño del correo
    comentarios_texto = '\n'.join(comentarios) if isinstance(comentarios, list) else comentarios

    message = f"Buenos días, \n\nAdjunto el informe de monitoreo diario (checklist) del sistema. Los resultados de la revisión "
    if comentarios_texto == 'Todo Ok':
        message += "indican que todos los parámetros se encuentran dentro de los rangos normales.\n"
    else:
        message += "indican que se encontró una alteración en uno de los parámetros. Favor de validar el reporte anexo.\n"

    message += "\nParámetros evaluados:\n"
    for parametro, (descripcion, estado_ok, estado_nok) in parametros.items():
        message += f"\t• {parametro}: {descripcion} - "
        if parametro in comentarios_texto:
            message += f"{estado_nok}\n"
        else:
            message += f"{estado_ok}\n"

    if comentarios_texto == 'Todo Ok':
        subject = f"Checklist Diario {cuenta} - Status: ✅"
        message += "\nEstado general: Todo en orden\n"
    else:
        subject = f"Checklist Diario {cuenta} - Status: ❌"
        message += "\nEstado general: Se recomienda una revisión\n"

    message += "\nEste es un mensaje automático. \n"
    message += "Por favor, no responda a este correo.\n\n"
    message += "Saludos cordiales."

    #Envio del correo
    try:
        yag = yagmail.SMTP(remitente, password)
        destinatarios = [destinatario]

        yag.send(
            to=destinatarios,
            subject=subject,
            contents=message,
            cc=copias,
            attachments=archivo_adjunto
        )

    except Exception as e:
        print(f"[Error al enviar el correo: {e}]")