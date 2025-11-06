"""
Script para limpiar CheckLists de meses anteriores
Ejecuta el primer día de cada mes para eliminar archivos del mes anterior
"""

import os
import glob
from datetime import datetime, date

def cleanup_old_checklists():
    """Elimina CheckLists de meses anteriores al actual"""
    
    # Obtener fecha actual
    today = date.today()
    current_month_str = today.strftime("%Y-%m")
    
    print(f"Iniciando limpieza de CheckLists anteriores a {current_month_str}")
    
    # Directorio base donde están los proyectos
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Proyectos conocidos que tienen carpeta excel
    project_folders = [
        "cotemar", "enco_appLealtad", "quala", "sealand", 
        "sisamex", "upaep", "verdeValle"
    ]
    
    total_deleted = 0
    
    for project_name in project_folders:
        project_path = os.path.join(script_dir, project_name)
        excel_path = os.path.join(project_path, "excel")
        
        # Verificar si existe la carpeta excel
        if os.path.isdir(excel_path):
            print(f"\nLimpiando proyecto: {project_name}")
            deleted_count = cleanup_project_excel(excel_path, current_month_str)
            total_deleted += deleted_count
        else:
            print(f"\n⚠️  Proyecto {project_name}: carpeta excel no encontrada")
    
    print(f"\n✅ Limpieza completada. Total archivos eliminados: {total_deleted}")

def cleanup_project_excel(excel_path, current_month_str):
    """Limpia archivos CheckList de un proyecto específico"""
    
    deleted_count = 0
    
    # Buscar todos los archivos CheckList_*.xlsx
    pattern = os.path.join(excel_path, "CheckList_*.xlsx")
    checklist_files = glob.glob(pattern)
    
    for file_path in checklist_files:
        filename = os.path.basename(file_path)
        
        # Extraer fecha del nombre del archivo (formato: CheckList_YYYY-MM-DD.xlsx)
        try:
            date_part = filename.replace("CheckList_", "").replace(".xlsx", "")
            file_month = date_part[:7]  # YYYY-MM
            
            # Si el archivo es de un mes anterior, eliminarlo
            if file_month < current_month_str:
                os.remove(file_path)
                print(f"  🗑️  Eliminado: {filename}")
                deleted_count += 1
            else:
                print(f"  ✅ Conservado: {filename}")
                
        except (ValueError, IndexError) as e:
            print(f"  ⚠️  Archivo con formato incorrecto ignorado: {filename}")
    
    return deleted_count

def should_run_cleanup():
    """Verifica si debe ejecutar la limpieza (solo el primer día del mes)"""
    today = date.today()
    return today.day == 1

if __name__ == "__main__":
    print("=== Script de Limpieza de CheckLists ===")
    
    # Mostrar información del ambiente
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Directorio base: {script_dir}")
    
    # Solo ejecutar limpieza el primer día del mes
    if should_run_cleanup():
        print("\n📅 Es el primer día del mes - Ejecutando limpieza automática")
        cleanup_old_checklists()
    else:
        today = date.today()
        print(f"\n📅 Hoy es {today} - Limpieza solo se ejecuta el día 1 de cada mes.")
        print("\n🔄 Para forzar limpieza manual, descomenta la siguiente línea:")
        print("# cleanup_old_checklists()")
        
        # Descomenta esta línea para forzar limpieza manual:
        # cleanup_old_checklists()