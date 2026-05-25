import streamlit as st
import pandas as pd

# ======================================================================================
# SCRIPT DE PRUEBA Y AUDITORÍA - CONSUMO DIARIO
# ======================================================================================
# Objetivo: Validar que la extracción de datos desde PostgreSQL mediante Python 
# coincida exactamente con los filtros manuales aplicados en el archivo de Excel.
# ======================================================================================

# 1. CONEXIÓN A LA BASE DE DATOS
# Utilizamos la misma configuración de st.connection que usa la aplicación principal
# para garantizar que estamos apuntando a la misma base de datos con los mismos permisos.
conn = st.connection("postgresql", type="sql")

# 2. DEFINICIÓN DE LA CONSULTA SQL (QUERY)
# Usamos un CTE (Common Table Expression) llamado 'datos_crudos' usando la cláusula WITH.
# Esto nos permite primero extraer y limpiar la información, y luego agruparla abajo.
query = """
WITH datos_crudos AS (
    
    -- ========================================================================
    -- BLOQUE 1: CARGOS DE INVENTARIOS Y MEDICAMENTOS ('IMD', 'DIMD')
    -- ========================================================================
    SELECT 
        cd.fecha_cargo::DATE AS fecha_cargo, 
        cd.valor_cargo
    FROM cuentas_detalle cd 
        INNER JOIN bodegas_documentos_d bdd ON cd.consecutivo = bdd.consecutivo 
        INNER JOIN inventarios_productos inp ON inp.codigo_producto = bdd.codigo_producto 
        INNER JOIN cuentas c ON c.numerodecuenta = cd.numerodecuenta
    WHERE 
        -- Rango de fechas fijo para hacer la prueba y comparar con la captura de Excel
        cd.fecha_cargo::DATE >= '2026-05-01' AND cd.fecha_cargo::DATE <= '2026-05-11'
        AND cd.cargo IN ('IMD','DIMD')
        
        -- --------------------------------------------------------------------
        -- PARÁMETRO DE EXTRACCIÓN 1: "INF G" (Facturado)
        -- Regla Excel: Solo incluye "SI" y "(en blanco)". Excluye "NO".
        -- Traducción SQL: '1' representa "SI". IS NULL o TRIM vacío representan "(en blanco)".
        -- --------------------------------------------------------------------
        AND (cd.facturado = '1' OR cd.facturado IS NULL OR TRIM(cd.facturado) = '')
        
        -- --------------------------------------------------------------------
        -- PARÁMETRO DE EXTRACCIÓN 2: "SW" (sw_paquete_facturado)
        -- Regla Excel: Solo incluye "1" y "(en blanco)". Excluye "0".
        -- Traducción SQL: Trae el '1' literal, los valores nulos o los vacíos.
        -- --------------------------------------------------------------------
        AND (cd.sw_paquete_facturado = '1' OR cd.sw_paquete_facturado IS NULL OR TRIM(cd.sw_paquete_facturado) = '')
        
        -- --------------------------------------------------------------------
        -- PARÁMETRO DE EXTRACCIÓN 3: "Estados" (estado_cuentas)
        -- Regla Excel: Incluye FACTURADA, ACTIVA, INACTIVA, CUADRADA y (en blanco). 
        --              Única excluida: "ANULADA".
        -- Traducción SQL: El código '5' es ANULADA. Al definir estrictamente los 
        --                 códigos '0', '1', '2' y '3', dejamos fuera el '5'.
        -- --------------------------------------------------------------------
        AND (c.estado IN ('0', '1', '2', '3') OR c.estado IS NULL)

    UNION ALL
    -- UNION ALL junta los resultados del Bloque 1 con los del Bloque 2 en una sola tabla

    -- ========================================================================
    -- BLOQUE 2: CARGOS DE PROCEDIMIENTOS Y OTROS (No son 'IMD' ni 'DIMD')
    -- ========================================================================
    SELECT 
        cd.fecha_cargo::DATE AS fecha_cargo, 
        cd.valor_cargo
    FROM cuentas_detalle cd 
        INNER JOIN tarifarios_detalle td ON cd.cargo = td.cargo AND cd.tarifario_id = td.tarifario_id 
        INNER JOIN cuentas c ON c.numerodecuenta = cd.numerodecuenta 
    WHERE 
        cd.fecha_cargo::DATE >= '2026-05-01' AND cd.fecha_cargo::DATE <= '2026-05-11'
        AND cd.cargo NOT IN ('IMD','DIMD')
        
        -- Aplicamos exactamente las mismas reglas de negocio (filtros) del bloque anterior
        AND (cd.facturado = '1' OR cd.facturado IS NULL OR TRIM(cd.facturado) = '')
        AND (cd.sw_paquete_facturado = '1' OR cd.sw_paquete_facturado IS NULL OR TRIM(cd.sw_paquete_facturado) = '')
        AND (c.estado IN ('0', '1', '2', '3') OR c.estado IS NULL)
)

-- ========================================================================
-- AGRUPACIÓN DE DATOS (Equivalente a df.groupby() en Pandas)
-- ========================================================================
-- En lugar de traer miles de filas de cargos individuales, le pedimos a SQL 
-- que agrupe todos los registros que compartan la misma fecha y sume sus valores.
SELECT 
    TO_CHAR(fecha_cargo, 'DD/MM/YYYY') AS "Fecha",
    SUM(valor_cargo) AS "Facturacion_del_Dia"
FROM datos_crudos
GROUP BY fecha_cargo
ORDER BY fecha_cargo ASC;
"""

# 3. EJECUCIÓN DE LA CONSULTA
# Mandamos el query a la base de datos y guardamos el resultado en un DataFrame de Pandas
df_resultado = conn.query(query)

# 4. FORMATO VISUAL
# Le damos formato de moneda colombiana a los números para poder compararlos 
# visualmente con mayor facilidad contra la imagen de Streamlit/Excel
df_resultado['Facturacion_del_Dia'] = df_resultado['Facturacion_del_Dia'].apply(lambda x: f"$ {x:,.0f}".replace(",", "."))

# 5. SALIDA EN CONSOLA
# Imprimimos el resultado limpio en la terminal de VS Code
print("\n=== RESULTADOS DE LA AUDITORÍA DE EXTRACCIÓN ===")
print(df_resultado.to_string(index=False))
print("================================================\n")