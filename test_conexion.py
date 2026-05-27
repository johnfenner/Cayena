import socket
import psycopg2
from psycopg2 import OperationalError

# Credenciales extraídas de tu secrets.toml
HOST = "urosoft.clinicalamagdalena.com"
PORT = 5432
DB = "UROSOFT_MAGDALENA"
USER = "lector"
PASSWORD = "*5^Ob4vYoo"

# Rutas de certificados extraídas de tu informe_general.py
SSL_ARGS = {
    "sslmode": "verify-ca",
    "sslrootcert": "C:/Users/JOHN/Documents/Proyecto/.streamlit/ca_ucm.crt",
    "sslcert": "C:/Users/JOHN/Documents/Proyecto/.streamlit/lector_ucm.crt",
    "sslkey": "C:/Users/JOHN/Documents/Proyecto/.streamlit/lector_ucm.key"
}

def diagnostico_conexion():
    print("=========================================================")
    print("🛰️  INICIANDO DIAGNÓSTICO DE CONEXIÓN - UCM")
    print("=========================================================\n")

    # --- PASO 1: PRUEBA DE RED BÁSICA (SOCKET) ---
    print("=== PASO 1: Verificando conectividad de red (TCP Socket) ===")
    try:
        # Intenta abrir una conexión de red cruda en el puerto 5432
        s = socket.create_connection((HOST, PORT), timeout=5)
        print(f"✅ ¡ÉXITO DE RED! El host responde y el puerto {PORT} está ABIERTO.")
        s.close()
        paso_1_exitoso = True
    except Exception as e:
        print(f"❌ ERROR DE RED: No se pudo abrir el canal en el puerto {PORT}.")
        print(f"Detalle del sistema operativo: {e}")
        print("\n💡 CONCLUSIÓN PASO 1:")
        print("Si las otras clínicas te funcionan y esta no pasa de aquí, el firewall de")
        print("Clínica La Magdalena te está bloqueando el paso o el servidor está apagado.")
        paso_1_exitoso = False

    if not paso_1_exitoso:
        print("\n⚠️ Abortando Paso 2 ya que no hay conectividad de red básica.")
        return

    # --- PASO 2: AUTENTICACIÓN Y SSL EN POSTGRESQL ---
    print("\n=== PASO 2: Intentando apretón de manos con PostgreSQL (SSL) ===")
    try:
        conn = psycopg2.connect(
            host=HOST,
            port=PORT,
            database=DB,
            user=USER,
            password=PASSWORD,
            sslmode=SSL_ARGS["sslmode"],
            sslrootcert=SSL_ARGS["sslrootcert"],
            sslcert=SSL_ARGS["sslcert"],
            sslkey=SSL_ARGS["sslkey"]
        )
        
        # Si llega aquí, la conexión fue un éxito total
        print("✅ ¡CONEXIÓN EXITOSA A LA BASE DE DATOS!")
        
        # Validar que podamos ejecutar una consulta simple
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"   Motor: {version}")
        
        cursor.close()
        conn.close()
        
    except OperationalError as err_postgres:
        print("❌ ERROR DE POSTGRESQL: La red está abierta, pero el motor rechazó el intento.")
        print(f"Detalle de la BD: {err_postgres}")
        print("\n💡 CONCLUSIÓN PASO 2:")
        print("El puerto responde, pero hay un problema con las llaves SSL, el usuario")
        print("o tu IP no está autorizada en el archivo 'pg_hba.conf' de este servidor específico.")
    except Exception as e:
        print(f"❌ ERROR INESPERADO: {e}")

if __name__ == "__main__":
    diagnostico_conexion()