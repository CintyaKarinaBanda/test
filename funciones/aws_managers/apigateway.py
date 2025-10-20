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
            api_id = api['id']
            
            # Probar diferentes dimensiones para API Gateway
            dimensions_options = [
                [{'Name': 'ApiName', 'Value': api_name}],
                [{'Name': 'ApiId', 'Value': api_id}],
                [{'Name': 'ApiName', 'Value': api_name}, {'Name': 'Stage', 'Value': 'prod'}],
                [{'Name': 'ApiName', 'Value': api_name}, {'Name': 'Stage', 'Value': 'dev'}]
            ]
            
            best_count = (0, 0, 0)
            best_latency = (0, 0, 0)
            best_4xx = (0, 0, 0)
            best_5xx = (0, 0, 0)
            
            for dimensions in dimensions_options:
                try:
                    count_stats = get_metric_statistics(cw_client, 'AWS/ApiGateway', dimensions, 'Count')
                    latency_stats = get_metric_statistics(cw_client, 'AWS/ApiGateway', dimensions, 'Latency')
                    error_4xx_stats = get_metric_statistics(cw_client, 'AWS/ApiGateway', dimensions, '4XXError')
                    error_5xx_stats = get_metric_statistics(cw_client, 'AWS/ApiGateway', dimensions, '5XXError')
                    
                    # Usar las mejores métricas encontradas
                    if count_stats and sum(count_stats) > sum(best_count):
                        best_count = count_stats
                    if latency_stats and sum(latency_stats) > sum(best_latency):
                        best_latency = latency_stats
                    if error_4xx_stats and sum(error_4xx_stats) > sum(best_4xx):
                        best_4xx = error_4xx_stats
                    if error_5xx_stats and sum(error_5xx_stats) > sum(best_5xx):
                        best_5xx = error_5xx_stats
                        
                except:
                    continue
            
            api_metrics.append([
                api_name,
                best_count[0] if best_count else 0,    # Count Min
                best_count[1] if len(best_count) > 1 else 0,    # Count Max
                best_count[2] if len(best_count) > 2 else 0,    # Count Avg
                best_latency[0] if best_latency else 0,  # Latency Min
                best_latency[1] if len(best_latency) > 1 else 0,  # Latency Max
                best_latency[2] if len(best_latency) > 2 else 0,  # Latency Avg
                best_4xx[0] if best_4xx else 0,  # 4XX Min
                best_4xx[1] if len(best_4xx) > 1 else 0,  # 4XX Max
                best_4xx[2] if len(best_4xx) > 2 else 0,  # 4XX Avg
                best_5xx[0] if best_5xx else 0,  # 5XX Min
                best_5xx[1] if len(best_5xx) > 1 else 0,  # 5XX Max
                best_5xx[2] if len(best_5xx) > 2 else 0   # 5XX Avg
            ])
        
        return api_metrics
        
    except Exception as e:
        print(f"Error procesando métricas de API Gateway: {e}")
        return []

def return_apigateway_comments():
    comments = []
    return comments