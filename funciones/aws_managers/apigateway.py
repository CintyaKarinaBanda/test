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
            
            # Dimensiones para API Gateway
            dimensions = [
                {'Name': 'ApiName', 'Value': api_name}
            ]
            
            # Métricas principales de API Gateway
            count = get_metric_statistics(cw_client, 'AWS/ApiGateway', dimensions, 'Count', ['Sum'])
            latency = get_metric_statistics(cw_client, 'AWS/ApiGateway', dimensions, 'Latency', ['Average', 'Maximum'])
            error_4xx = get_metric_statistics(cw_client, 'AWS/ApiGateway', dimensions, '4XXError', ['Sum'])
            error_5xx = get_metric_statistics(cw_client, 'AWS/ApiGateway', dimensions, '5XXError', ['Sum'])
            
            api_metrics.append([
                api_name,
                api_id,
                count[0] if count else 0,
                latency[0] if latency else 0,  # Average latency
                latency[1] if len(latency) > 1 else 0,  # Max latency
                error_4xx[0] if error_4xx else 0,
                error_5xx[0] if error_5xx else 0
            ])
        
        return api_metrics
        
    except Exception as e:
        print(f"Error procesando métricas de API Gateway: {e}")
        return []

def return_apigateway_comments():
    comments = []
    return comments