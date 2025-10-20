from .utils import assume_role, get_metric_statistics

def process_apigateway_metrics(region, role_arn):
    session = assume_role(role_arn, region)
    if not session:
        return []
    
    cw_client = session.client('cloudwatch')
    apigateway_client = session.client('apigateway')
    
    try:
        # Obtener todas las APIs
        apis = apigateway_client.get_rest_apis()['items']
        
        api_metrics = []
        for api in apis:
            api_name = api['name']
            
            # Dimensiones para API Gateway
            dimensions = [
                {'Name': 'ApiName', 'Value': api_name}
            ]
            
            # Obtener métricas con min, max, avg usando utils.py
            count_stats = get_metric_statistics(cw_client, 'AWS/ApiGateway', dimensions, 'Count')
            latency_stats = get_metric_statistics(cw_client, 'AWS/ApiGateway', dimensions, 'Latency')
            error_4xx_stats = get_metric_statistics(cw_client, 'AWS/ApiGateway', dimensions, '4XXError')
            
            api_metrics.append([
                api_name,
                count_stats[0] if count_stats else 0,    # Count Min
                count_stats[1] if len(count_stats) > 1 else 0,    # Count Max
                count_stats[2] if len(count_stats) > 2 else 0,    # Count Avg
                latency_stats[0] if latency_stats else 0,  # Latency Min
                latency_stats[1] if len(latency_stats) > 1 else 0,  # Latency Max
                latency_stats[2] if len(latency_stats) > 2 else 0,  # Latency Avg
                error_4xx_stats[0] if error_4xx_stats else 0,  # 4XX Min
                error_4xx_stats[1] if len(error_4xx_stats) > 1 else 0,  # 4XX Max
                error_4xx_stats[2] if len(error_4xx_stats) > 2 else 0   # 4XX Avg
            ])
        
        return api_metrics
        
    except Exception as e:
        print(f"Error procesando métricas de API Gateway: {e}")
        return []

def return_apigateway_comments():
    comments = []
    return comments