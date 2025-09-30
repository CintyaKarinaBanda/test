# AWS Managers package
from .lambda_aws import process_lambda_metrics, get_lambda_logs, get_all_lambda_functions
from .rds import process_rds_metrics, get_rds_event_logs, process_rds_dashboard_metrics
from .utils import assume_role, get_metric_statistics

# Comentarios globales
GLOBAL_COMMENTS = []

def add_comment(comment):
    """Agregar comentario a la lista global"""
    GLOBAL_COMMENTS.append(comment)

def return_comments():
    """Retornar todos los comentarios"""
    return GLOBAL_COMMENTS.copy()

def clear_comments():
    """Limpiar comentarios"""
    GLOBAL_COMMENTS.clear()

__all__ = [
    'process_lambda_metrics',
    'get_lambda_logs', 
    'get_all_lambda_functions',
    'process_rds_metrics',
    'get_rds_event_logs',
    'process_rds_dashboard_metrics',
    'assume_role',
    'get_metric_statistics',
    'add_comment',
    'return_comments',
    'clear_comments'
]