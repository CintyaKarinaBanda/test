import boto3
import concurrent.futures
from datetime import datetime, timedelta

COMENTARIOS = []

def assume_role(role_arn, region):
    sts_client = boto3.client('sts')
    
    try:
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName='monitoring-session'
        )
        
        credentials = response['Credentials']
        
        session = boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken'],
            region_name=region
        )
        
        return session
    except Exception as e:
        print(f"Error asumiendo rol: {e}")
        return None

def get_metric_statistics(cw_client, namespace, dimensions, metric_name, statistics=None):
    #Funcion para obtiener datos de meticas de Cloud Watch
    if statistics is None:
        statistics = ['Minimum', 'Maximum', 'Average']

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)

    try:
        response = cw_client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_time,
            EndTime=end_time,
            Period=43200, #12 HORAS
            Statistics=statistics
        )
        if response['Datapoints']:
            data = response['Datapoints'][0]
            return tuple(round(data.get(stat, 0.0), 2) for stat in statistics)
        else:
            return tuple(0.0 for _ in statistics)
    except Exception as e:
        print(f"Error getting {metric_name}: {e}")
        return tuple('-' for _ in statistics)


#Inicio del Proceso para la RDS
def process_rds_metrics(rds_id, REGION, role_arn=None, checkSnapshot = True ):
    # Función para ordenar los datos
    if role_arn:
        session = assume_role(role_arn, REGION)
        if not session:
            return (rds_id, 'Error', 'Error', 'Error')
        rds_client = session.client('rds')
        cw_client = session.client('cloudwatch')
    else:
        rds_client = boto3.client('rds', region_name=REGION)
        cw_client = boto3.client('cloudwatch', region_name=REGION)

    response = rds_client.describe_db_instances(DBInstanceIdentifier=rds_id)
    total_storage = response['DBInstances'][0]['AllocatedStorage'] 

    rds_metrics = [
        ('CPUUtilization', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
        ('DatabaseConnections', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
        ('FreeStorageSpace', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}])
    ]

    rds_metrics_data = []
    for metric_name, namespace, dimensions in rds_metrics:
        metric_data = get_metric_statistics(cw_client, namespace, dimensions, metric_name)
        rds_metrics_data.extend(metric_data)
        if metric_name == 'CPUUtilization' and len(metric_data) > 1 and metric_data[1] >= 95:
            COMENTARIOS.append('CPU Utilization: el procentaje es mayor a 95 en el RDS')
        if metric_name == 'FreeStorageSpace' and len(metric_data) >= 3:
            metric_data = [round(value / (1024 ** 3), 2) for value in metric_data]
            free_storage_percent = (metric_data[2] / total_storage) * 100  
            if free_storage_percent < 5:
                COMENTARIOS.append(f'Free Storage Space: el espacio libre es menor al 5% en el RDS')
        rds_metrics_data.extend(metric_data)

    if checkSnapshot:
        response = rds_client.describe_db_snapshots(
            DBInstanceIdentifier=rds_id,
            SnapshotType='automated',
            IncludePublic=False
        )

        snapshots = response.get('DBSnapshots', [])
        from datetime import datetime, timedelta

        if snapshots:
            latest_snapshot = max(snapshots, key=lambda x: x['SnapshotCreateTime'])
            latest_snapshot_date = latest_snapshot['SnapshotCreateTime'].strftime('%Y-%m-%d %H:%M:%S')

            today = datetime.now().strftime('%Y-%m-%d')
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            snapshot_date = latest_snapshot['SnapshotCreateTime'].strftime('%Y-%m-%d')
            if snapshot_date != yesterday and snapshot_date != today:
                COMENTARIOS.append('Snapshot: hubo un error el crear el respaldo del día de ayer.')


    return (rds_id, *rds_metrics_data, latest_snapshot_date if checkSnapshot else None)

def get_rds_event_logs(rds_id, REGION, role_arn=None):
    if role_arn:
        session = assume_role(role_arn, REGION)
        if not session:
            return "Error asumiendo rol para RDS logs"
        rds_client = session.client('rds')
    else:
        rds_client = boto3.client('rds', region_name=REGION)

    try:
        start_time = datetime.utcnow() - timedelta(days=2)
        end_time = datetime.utcnow()

        response = rds_client.describe_events(
            SourceIdentifier=rds_id,
            SourceType='db-instance',
            StartTime=start_time,
            EndTime=end_time
        )

        events = response.get('Events', [])
        error_found = False

        if events:
            for event in events:
                message = event['Message'].lower()
                if "error" in message or "failure" in message or "down" in message:
                    print(f"Error en RDS: {event['Message']}, Hora: {event['Date']}")
                    error_found = True

        if error_found:
            return "Errores encontrados en los logs de la RDS."
        else:
            return "No se encontraron errores en los logs para la RDS."

    except Exception as e:
        print(f"Error obteniendo los logs de eventos de RDS: {e}")
        return "Error al obtener los logs de eventos de RDS."


def process_rds_dashboard_metrics(rds_id, REGION, role_arn=None):
    if role_arn:
        session = assume_role(role_arn, REGION)
        if not session:
            return [("Error", "Error", "Error", "Error")]
        cw_client = session.client('cloudwatch')
    else:
        cw_client = boto3.client('cloudwatch', region_name=REGION)

    rds_dashboard_metrics = [
        ('DiskQueueDepth', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
        ('ReadLatency', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
        ('WriteLatency', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
        ('ReadThroughput', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
        ('WriteThroughput', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
        ('ReplicaLag', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
    ]

    rds_dashboard_data = []
    for metric_name, namespace, dimensions in rds_dashboard_metrics:
        metric_data = get_metric_statistics(cw_client, namespace, dimensions, metric_name)
        rds_dashboard_data.append((metric_name, *metric_data))

    return rds_dashboard_data

#Fin del Proceso para la RDS

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

def process_lambda_metrics(REGION, role_arn=None):
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
            if errors[0] > 0:
                COMENTARIOS.append(f'Lambda {function_name}: Se detectaron {errors[0]} errores')
            
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

def return_comments():
    return COMENTARIOS
