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