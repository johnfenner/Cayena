import streamlit as st
import pandas as pd

def mostrar_vista():
    st.title("📊 Consumo Diario")
    st.subheader("Hospital del Magdalena Centro")
    
    # 1. Inicializar la conexión usando el gestor nativo de Streamlit
    try:
        conn = st.connection("postgresql", type="sql")
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return

    # 2. Definir tu query SQL
    query = """
    --CONSUMO DIARIO
    SELECT
         p.tipo_id_paciente t_id,
         p.paciente_id as identificacion, 
         p.primer_nombre||' '||p.segundo_nombre||' '||p.primer_apellido||' '||p.segundo_apellido as paciente,
         TO_CHAR(i.fecha_ingreso, 'YYYY-MM-DD') AS fecha_ingreso,
         EXTRACT(DAY FROM i.fecha_ingreso) AS dia_ingreso,
         cd.numerodecuenta,
         i.ingreso,
         igi.descripcion grupo_inventario,
         pl.plan_descripcion,
         CASE 
              WHEN LOWER(pl.plan_descripcion) LIKE '%unico%' THEN 'PGP'
              ELSE 'EVENTO'
         END AS modalidad,
         CASE WHEN ta.tipo_afiliado_id ='0' THEN 'SOAT'
               WHEN ta.tipo_afiliado_id ='11' THEN 'ARL'
               WHEN ta.tipo_afiliado_id ='13' THEN 'PREPAGADA'
               ELSE ta.tipo_afiliado_nombre
         END tipos_afiliado,
         pl.tercero_id NIT,
         t.nombre_tercero,
         CASE WHEN c.estado ='0' THEN 'FACTURADA'
               WHEN c.estado ='1' THEN 'ACTIVA'
               WHEN c.estado ='2' THEN 'INACTIVA'
               WHEN c.estado ='3' THEN 'CUADRADA'
               WHEN c.estado ='5' THEN 'ANULADA' 
         END estado_cuentas,
         TO_CHAR(cd.fecha_cargo, 'YYYY-MM-DD') AS fecha_cargo,
         EXTRACT(DAY FROM cd.fecha_cargo) AS dia_cargo,
         cd.cargo,
         cd.cargo_cups,
         cp.descripcion cups_descripcion,
         cd.cantidad, 
         cd.precio, 
         cd.valor_cargo,
         CASE
               WHEN cd.facturado = '1' THEN 'SI'
               WHEN cd.facturado = '0' THEN 'NO'
         END facturable, 
         cd.paquete_codigo_id, 
         cd.sw_paquete_facturado, 
         su.nombre AS usuario_carga,
         d.descripcion AS estacion_enfermeria_actual,
         de.descripcion AS departamento,
         sd.descripcion AS sede,
         uf.descripcion unidad_funcional,
         inp.descripcion,
         tc.descripcion as regimen,
         '' AS estacion_solicitud,
         inp.codigo_producto,
         inp.codigo_alterno,
         ipca.descripcion as descripcion_alterno
    FROM
         cuentas_detalle cd 
         INNER JOIN bodegas_documentos_d bdd ON cd.consecutivo=bdd.consecutivo 
         INNER JOIN inventarios_productos inp ON inp.codigo_producto=bdd.codigo_producto 
         LEFT JOIN inv_grupos_inventarios igi ON igi.grupo_id = inp.grupo_id
         INNER JOIN cuentas c ON c.numerodecuenta=cd.numerodecuenta
         INNER JOIN planes pl ON pl.plan_id = c.plan_id
         INNER JOIN ingresos i ON i.ingreso=c.ingreso 
         INNER JOIN pacientes p ON p.tipo_id_paciente=i.tipo_id_paciente AND p.paciente_id=i.paciente_id
         INNER JOIN system_usuarios su ON su.usuario_id = cd.usuario_id
         INNER JOIN departamentos d ON d.departamento = i.departamento_actual
         INNER JOIN departamentos de ON de.departamento = cd.departamento_al_cargar
         LEFT JOIN sedes sd ON sd.sede_id = de.sede_id
         INNER JOIN unidades_funcionales uf ON uf.unidad_funcional = de.unidad_funcional
         --------------------------------------------------------------------------------
         INNER JOIN planes_rangos pr ON (c.plan_id=pr.plan_id AND c.rango=pr.rango AND c.tipo_afiliado_id=pr.tipo_afiliado_id)
         INNER JOIN tipos_afiliado ta ON (pr.tipo_afiliado_id=ta.tipo_afiliado_id)
         FULL JOIN cups cp ON (cd.cargo_cups=cp.cargo)
         INNER JOIN terceros t ON (pl.tipo_tercero_id=t.tipo_id_tercero AND pl.tercero_id=t.tercero_id)
         ---------------------------------------------------------------------------------
         INNER JOIN tipos_cliente tc ON tc.tipo_cliente = pl.tipo_cliente
         INNER JOIN regimenes r ON r.regimen_id = tc.regimen_id
         ---------------------------------------------------------------------------------
         LEFT JOIN inventarios_productos_codigo_alterno ipca ON inp.codigo_alterno=ipca.codigo_alterno
    WHERE 
         cd.fecha_cargo::DATE = CURRENT_DATE - INTERVAL '1 day'
         AND cd.cargo IN ('IMD','DIMD') 

    UNION ALL

    SELECT 
         p.tipo_id_paciente t_id,
         p.paciente_id as identificacion,
         p.primer_nombre||' '||p.segundo_nombre||' '||p.primer_apellido||' '||p.segundo_apellido as paciente, 
         TO_CHAR(i.fecha_ingreso, 'YYYY-MM-DD') AS fecha_ingreso,
         EXTRACT(DAY FROM i.fecha_ingreso) AS dia_ingreso,
         cd.numerodecuenta,
         i.ingreso,
         cd.centro_de_costo_id centro_costo,
         pl.plan_descripcion,
         CASE 
              WHEN LOWER(pl.plan_descripcion) LIKE '%unico%' THEN 'PGP'
              ELSE 'EVENTO'
         END AS modalidad,
         CASE WHEN ta.tipo_afiliado_id ='0' THEN 'SOAT'
               WHEN ta.tipo_afiliado_id ='11' THEN 'ARL'
               WHEN ta.tipo_afiliado_id ='13' THEN 'PREPAGADA'
               ELSE ta.tipo_afiliado_nombre
         END tipos_afiliado,
         pl.tercero_id NIT,
         t.nombre_tercero,
         CASE WHEN c.estado ='0' THEN 'FACTURADA'
               WHEN c.estado ='1' THEN 'ACTIVA'
               WHEN c.estado ='2' THEN 'INACTIVA'
               WHEN c.estado ='3' THEN 'CUADRADA'
               WHEN c.estado ='5' THEN 'ANULADA'
         END estado_cuentas,
         TO_CHAR(cd.fecha_cargo, 'YYYY-MM-DD') AS fecha_cargo,
         EXTRACT(DAY FROM cd.fecha_cargo) AS dia_cargo,
         cd.cargo,
         cd.cargo_cups,
         cp.descripcion cups_descripcion,
         cd.cantidad, 
         cd.precio, 
         cd.valor_cargo, 
         CASE
               WHEN cd.facturado = '1' THEN 'SI'
               WHEN cd.facturado = '0' THEN 'NO'
         END facturable, 
         cd.paquete_codigo_id, 
         cd.sw_paquete_facturado, 
         su.nombre AS usuario_carga,
         d.descripcion AS estacion_enfermeria_actual,
         de.descripcion AS departamento,
         sd.descripcion AS sede,
         uf.descripcion unidad_funcional,
         td.descripcion,
         tc.descripcion as regimen,
         ee.descripcion AS estacion_solicitud,
         '' as codigo_producto,
         '' as codigo_alterno,
         '' as descripcion_alterno
    FROM 
         cuentas_detalle cd 
         INNER JOIN tarifarios_detalle td ON cd.cargo=td.cargo AND cd.tarifario_id=td.tarifario_id 
         INNER JOIN cuentas c ON c.numerodecuenta=cd.numerodecuenta 
         INNER JOIN planes pl ON pl.plan_id = c.plan_id
         INNER JOIN ingresos i ON i.ingreso=c.ingreso 
         LEFT JOIN os_maestro_cargos omc ON cd.transaccion = omc.transaccion
         LEFT JOIN os_maestro om ON omc.numero_orden_id = om.numero_orden_id 
         LEFT JOIN hc_os_solicitudes hos ON om.hc_os_solicitud_id = hos.hc_os_solicitud_id
         LEFT JOIN hc_evoluciones he on hos.evolucion_id = he.evolucion_id
         LEFT JOIN estaciones_enfermeria ee ON he.estacion_id = ee.estacion_id
         INNER JOIN pacientes p ON p.tipo_id_paciente=i.tipo_id_paciente AND p.paciente_id=i.paciente_id 
         INNER JOIN system_usuarios su ON su.usuario_id = cd.usuario_id
         INNER JOIN departamentos d ON d.departamento = i.departamento_actual
         INNER JOIN departamentos de ON de.departamento = cd.departamento_al_cargar
         LEFT JOIN sedes sd ON sd.sede_id = de.sede_id
         INNER JOIN unidades_funcionales uf ON uf.unidad_funcional = de.unidad_funcional
         --------------------------------------------------------------------------------
         INNER JOIN planes_rangos pr ON (c.plan_id=pr.plan_id AND c.rango=pr.rango AND c.tipo_afiliado_id=pr.tipo_afiliado_id)
         INNER JOIN tipos_afiliado ta ON (pr.tipo_afiliado_id=ta.tipo_afiliado_id)
         FULL JOIN cups cp ON (cd.cargo_cups=cp.cargo)
         INNER JOIN terceros t ON (pl.tipo_tercero_id=t.tipo_id_tercero AND pl.tercero_id=t.tercero_id)
         ---------------------------------------------------------------------------------
         INNER JOIN tipos_cliente tc ON tc.tipo_cliente = pl.tipo_cliente
         INNER JOIN regimenes r ON r.regimen_id = tc.regimen_id
    WHERE 
         cd.fecha_cargo::DATE = CURRENT_DATE - INTERVAL '1 day'
         AND cd.cargo NOT IN ('IMD','DIMD')
    """

    # 3. Renderizado en la interfaz con feedback visual de carga
    with st.spinner("Consultando los datos en la base de datos UROSOFT..."):
        try:
            # conn.query incluye el parámetro ttl para guardar el resultado en caché por 1 hora
            df = conn.query(query, ttl="1h")
            
            if df.empty:
                st.warning("No se encontraron registros de consumo para el día de ayer.")
            else:
                st.success(f"¡Datos cargados con éxito! Se encontraron {len(df)} registros.")
                
                # Métricas rápidas
                m1, m2 = st.columns(2)
                m1.metric("Total Registros", f"{len(df):,}")
                if 'valor_cargo' in df.columns:
                    m2.metric("Valor Total Cargado", f"${df['valor_cargo'].sum():,.2f}")
                
                # Mostrar la tabla interactiva
                st.dataframe(df, use_container_width=True)
                
        except Exception as query_error:
            st.error(f"Error al ejecutar la consulta: {query_error}")

if __name__ == "__main__":
    mostrar_vista()