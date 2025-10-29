import sys
import os
sys.path.append(os.path.abspath('../funciones'))

import boto3
from datetime import datetime
from email_manager import send_email
from config import REGION, CLOUDWATCH_ALARMS, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, TARGET_ACCOUNT_ID, CROSS_ACCOUNT_ROLE_NAME

def check_cross_account_alarms():
    """Verificación de alarmas en otra cuenta AWS"""
    
    # Asumir rol en cuenta objetivo
    sts_client = boto3.client('sts')
    role_arn = f'arn:aws:iam::{TARGET_ACCOUNT_ID}:role/{CROSS_ACCOUNT_ROLE_NAME}'
    
    try:
        assumed_role = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName='AlarmCheckSession'
        )
        
        credentials = assumed_role['Credentials']
        cw_client = boto3.client(
            'cloudwatch',
            region_name=REGION,
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
        
        response = cw_client.describe_alarms(AlarmNames=CLOUDWATCH_ALARMS)
        
        ok_alarms = []
        problem_alarms = []
        
        for alarm in response['MetricAlarms']:
            if alarm['StateValue'] == 'OK':
                ok_alarms.append(alarm['AlarmName'])
            else:
                problem_alarms.append({
                    'name': alarm['AlarmName'],
                    'state': alarm['StateValue'],
                    'reason': alarm['StateReason']
                })
        
        return ok_alarms, problem_alarms
        
    except Exception as e:
        print(f"Error cross-account: {e}")
        return [], []

def send_cross_account_report():
    """Envía reporte cross-account"""
    ok_alarms, problem_alarms = check_cross_account_alarms()
    
    message_lines = []
    message_lines.append(f"Reporte Cross-Account CloudWatch - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    message_lines.append(f"Cuenta objetivo: {TARGET_ACCOUNT_ID}")
    message_lines.append("")
    
    if ok_alarms:
        message_lines.append("✅ Alarmas OK:")
        for alarm in ok_alarms:
            message_lines.append(f"  • {alarm}")
    
    if problem_alarms:
        message_lines.append("⚠️ Alarmas con problemas:")
        for alarm in problem_alarms:
            message_lines.append(f"  • {alarm['name']}: {alarm['state']}")
    
    message_lines.append(f"\nTotal OK: {len(ok_alarms)}/{len(CLOUDWATCH_ALARMS)}")
    
    message_text = "\n".join(message_lines)
    subject = f"Cross-Account Alarms - {len(ok_alarms)}/{len(CLOUDWATCH_ALARMS)} OK"
    
    temp_file = f"cross_account_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write(message_text)
    
    try:
        send_email(temp_file, [message_text], REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, subject)
        print("✅ Email enviado")
    except Exception as e:
        print(f"❌ Error email: {e}")
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

if __name__ == "__main__":
    print(f"🔍 Verificando alarmas cross-account en cuenta: {TARGET_ACCOUNT_ID}")
    
    ok_alarms, problem_alarms = check_cross_account_alarms()
    
    print(f"✅ OK: {len(ok_alarms)}")
    print(f"⚠️ Problemas: {len(problem_alarms)}")
    
    send_cross_account_report()
    print("✅ Completado")