import psycopg2
from datetime import date
import os

# Database config with environment variables
host = os.getenv('DB_HOST')
database = os.getenv('DB_NAME')
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')

def send_status(comments, cuenta, project):
    comments_texto = '\n'.join(comments) if isinstance(comments, list) else comments
    status = ''
    comments_bd = ''

    try:
        conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=password
        )
        cursor = conn.cursor()

        fecha_hoy = date.today().isoformat()

        if comments_texto.strip() == 'Todo Ok':
            status = 'Ok'
            comments_bd = 'Sin relevantes'
        else:
            status = 'NoK'
            comments_bd = comments_texto

        cursor.execute("""
            SELECT p.project_id
            FROM project p
            JOIN identity i ON p.identity_id = i.identity_id
            WHERE p.name = %s AND i.name = %s
            LIMIT 1
        """, (project, cuenta))
        result = cursor.fetchone()

        if not result:
            print(f"❌ No se encontró el proyecto {project} para la identidad:", cuenta)
            return

        project_id = result[0]

        cursor.execute("""
            SELECT daily_report_id
            FROM daily_report
            WHERE DATE(date) = %s AND project_id = %s
        """, (fecha_hoy, project_id))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE daily_report
                SET status = %s,
                    comments = %s
                WHERE daily_report_id = %s
            """, (status, comments_bd, existing[0]))
            print(f"✅ Reporte actualizado: ID {existing[0]}")
        else:
            cursor.execute("""
                INSERT INTO daily_report (date, status, comments, project_id)
                VALUES (%s, %s, %s, %s)
            """, (fecha_hoy, status, comments_bd, project_id))
            print("🆕 Nuevo reporte insertado en daily_report.")

        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"🚨 Ocurrió un error: {e}")

