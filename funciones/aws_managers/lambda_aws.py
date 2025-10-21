import boto3
from datetime import datetime, timedelta
from .utils import assume_role, get_metric_statistics

# Importar función para agregar comentarios globales
def add_comment(comment):
    from . import GLOBAL_COMMENTS
    GLOBAL_COMMENTS.append(comment)

#Inicio del Proceso para Lambda
def get_all_lambda_functions(REGION, role_arn=None):
    if role_arn:
        session = assume_role(role_arn, REGION)
        if not session:
            return []
        lambda_client = session.client('lambda')
    else:
        lambda_client = boto3.client('lambda', region_name=REGION)
    
    try:
        response = lambda_client.list_functions()
        function_names = [func['FunctionName'] for func in response['Functions']]
        return function_names
    except Exception as e:
        print(f"Error listando funciones Lambda: {e}")
        return []

def process_lambda_metrics(REGION, role_arn=None, account_name='Default'):
    from .config import get_account_config
    config = get_account_config(account_name)
    if role_arn:
        session = assume_role(role_arn, REGION)
        if not session:
            return [("Error", "Error", "Error", "Error")]
        lambda_client = session.client('lambda')
        cw_client = session.client('cloudwatch')
    else:
        lambda_client = boto3.client('lambda', region_name=REGION)
        cw_client = boto3.client('cloudwatch', region_name=REGION)
    
    function_names = get_all_lambda_functions(REGION, role_arn)
    lambda_data = []
    
    for function_name in function_names:
        try:
            # Solo 3 métricas principales
            duration = get_metric_statistics(cw_client, 'AWS/Lambda', [{'Name': 'FunctionName', 'Value': function_name}], 'Duration', ['Average'])
            errors = get_metric_statistics(cw_client, 'AWS/Lambda', [{'Name': 'FunctionName', 'Value': function_name}], 'Errors', ['Sum'])
            invocations = get_metric_statistics(cw_client, 'AWS/Lambda', [{'Name': 'FunctionName', 'Value': function_name}], 'Invocations', ['Sum'])
            
            # Alertas
            #if errors[0] > 0:
            #    add_comment(f'Lambda {function_name}: Se detectaron {errors[0]} errores')
            
            lambda_data.append((function_name, duration[0], errors[0], invocations[0]))
            
        except Exception as e:
            print(f"Error procesando Lambda {function_name}: {e}")
            lambda_data.append((function_name, 'Error', 'Error', 'Error'))
    
    return lambda_data

def get_lambda_logs(function_name, REGION, role_arn=None):
    if role_arn:
        session = assume_role(role_arn, REGION)
        if not session:
            return f"Error asumiendo rol para logs de {function_name}"
        logs_client = session.client('logs')
    else:
        logs_client = boto3.client('logs', region_name=REGION)
    
    try:
        log_group_name = f'/aws/lambda/{function_name}'
        
        start_time = datetime.utcnow() - timedelta(hours=24)
        end_time = datetime.utcnow()
        
        response = logs_client.filter_log_events(
            logGroupName=log_group_name,
            startTime=int(start_time.timestamp() * 1000),
            endTime=int(end_time.timestamp() * 1000),
            filterPattern='ERROR'
        )
        
        error_events = response.get('events', [])
        
        if error_events:
            return f"Se encontraron {len(error_events)} errores en los logs de {function_name}"
        else:
            return f"No se encontraron errores en los logs de {function_name}"
            
    except Exception as e:
        print(f"Error obteniendo logs de Lambda {function_name}: {e}")
        return f"Error al obtener logs de {function_name}"
#Fin del Proceso para Lambda