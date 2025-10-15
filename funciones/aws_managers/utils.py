import boto3
from datetime import datetime, timedelta

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
    start_time = end_time - timedelta(hours=12)  # Cambiar a 12 horas para capturar más datos

    try:
        response = cw_client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_time,
            EndTime=end_time,
            Period=3600, # 1 HORA para más granularidad
            Statistics=statistics
        )
        if response['Datapoints']:
            # Obtener todos los datapoints y calcular estadísticas reales
            datapoints = response['Datapoints']
            values = []
            for dp in datapoints:
                for stat in statistics:
                    if stat in dp:
                        values.append(dp[stat])
            
            if values:
                if len(statistics) == 1:
                    return (round(sum(values), 2),)
                else:
                    # Para múltiples estadísticas, tomar el máximo de cada tipo
                    result = []
                    for stat in statistics:
                        stat_values = [dp.get(stat, 0) for dp in datapoints if stat in dp]
                        if stat == 'Minimum':
                            result.append(round(min(stat_values) if stat_values else 0, 2))
                        elif stat == 'Maximum':
                            result.append(round(max(stat_values) if stat_values else 0, 2))
                        elif stat == 'Average':
                            result.append(round(sum(stat_values)/len(stat_values) if stat_values else 0, 2))
                        else:
                            result.append(round(sum(stat_values) if stat_values else 0, 2))
                    return tuple(result)
            return tuple(0.0 for _ in statistics)
        else:
            return tuple(0.0 for _ in statistics)
    except Exception as e:
        print(f"Error getting {metric_name}: {e}")
        return tuple('-' for _ in statistics)