import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import calendar
import plotly.graph_objects as go
from .utils import formato_cop, formato_porcentaje, generar_pdf_unidades_funcionales

def mostrar_unidades_funcionales():
    st.markdown("<h2 style='text-align: center;'>⚙️ ANÁLISIS DE FACTURACIÓN POR UNIDADES FUNCIONALES</h2>", unsafe_allow_html=True)

    # ==========================================
    # 1. CONFIGURACIÓN DINÁMICA DE PERÍODOS 
    # ==========================================
    with st.expander("⚙️ CONTROL DE PERÍODO", expanded=True):
        modo_periodo = st.radio(
            "🗓️ ¿Cómo quiere ver los datos?",
            options=["Por Mes", "Por Año", "Rango de Fechas"],
            index=0,
            horizontal=True,
            key="uf_modo_periodo"
        )

        hoy_fecha = date.today()
        ayer = hoy_fecha - timedelta(days=1)
        ano_actual = hoy_fecha.year
        
        lista_anos = [ano_actual, ano_actual - 1, ano_actual - 2]
        meses_dic = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }

        if modo_periodo == "Por Mes":
            col1, col2 = st.columns(2)
            with col1:
                ano_sel = st.selectbox("Año", lista_anos, index=0, key="uf_ano_mes")
            with col2:
                mes_sel = st.selectbox(
                    "Mes", list(meses_dic.keys()),
                    format_func=lambda x: meses_dic[x],
                    index=ayer.month - 1,
                    key="uf_mes_mes"
                )
            
            _, dias_en_mes = calendar.monthrange(ano_sel, mes_sel)
            fecha_inicio_obj = date(ano_sel, mes_sel, 1)
            fecha_fin_obj = date(ano_sel, mes_sel, dias_en_mes)
            
            if fecha_fin_obj > ayer:
                fecha_fin_obj = ayer
                
            fecha_inicio = fecha_inicio_obj.strftime("%Y-%m-%d")
            fecha_fin = fecha_fin_obj.strftime("%Y-%m-%d")
            etiqueta_periodo = f"{meses_dic[mes_sel].upper()} {ano_sel}"

        elif modo_periodo == "Por Año":
            ano_sel = st.selectbox("Año", lista_anos, index=0, key="uf_ano_solo")
            fecha_inicio_obj = date(ano_sel, 1, 1)
            fecha_fin_obj = date(ano_sel, 12, 31)
            
            if fecha_fin_obj > ayer:
                fecha_fin_obj = ayer
                
            fecha_inicio = fecha_inicio_obj.strftime("%Y-%m-%d")
            fecha_fin = fecha_fin_obj.strftime("%Y-%m-%d")
            etiqueta_periodo = f"AÑO {ano_sel}"

        else:
            primer_dia_mes = ayer.replace(day=1)

            col1, col2 = st.columns(2)
            with col1:
                fecha_ini_sel = st.date_input("Desde", value=primer_dia_mes, max_value=ayer, key="uf_fecha_ini") 
            with col2:
                fecha_fin_sel = st.date_input("Hasta", value=ayer, max_value=ayer, key="uf_fecha_fin")

            if fecha_fin_sel < fecha_ini_sel:
                st.error("⚠️ La fecha de fin debe ser mayor o igual a la de inicio.")
                return

            fecha_inicio = fecha_ini_sel.strftime("%Y-%m-%d")
            fecha_fin = fecha_fin_sel.strftime("%Y-%m-%d")
            etiqueta_periodo = f"{fecha_ini_sel.strftime('%d/%m/%Y')} → {fecha_fin_sel.strftime('%d/%m/%Y')}"

        st.info(f"📅 **Período de Análisis:** {etiqueta_periodo} | 📌 **corte:** {ayer.strftime('%d-%m-%Y')}")

    # ==========================================
    # 2. CONEXIÓN Y CARGA DE DATOS 
    # ==========================================
    try:
        conn = st.connection(
            "putumayo", 
            type="sql",
            connect_args={
                "sslmode": "verify-ca",
                "sslrootcert": "C:/Users/JOHN/Documents/Proyecto/.streamlit/ca_putumayo.crt",
                "sslcert": "C:/Users/JOHN/Documents/Proyecto/.streamlit/lector_putumayo.crt",
                "sslkey": "C:/Users/JOHN/Documents/Proyecto/.streamlit/lector_putumayo.key"
            }
        )
    except Exception as e:
        st.error(f"Error crítico al conectar con la base de datos: {e}")
        return

    filtros_negocio = """
        AND (cd.facturado = '1' OR cd.facturado IS NULL OR TRIM(cd.facturado) = '')
        AND (cd.sw_paquete_facturado = '1' OR cd.sw_paquete_facturado IS NULL OR TRIM(cd.sw_paquete_facturado) = '')
        AND (c.estado IN ('0', '1', '2', '3') OR c.estado IS NULL)
    """

    query = f"""
    SELECT 
        unidad_funcional,
        departamento,
        fecha,
        SUM(cantidad) AS total_cantidad,
        SUM(valor_cargo) AS total_valor
    FROM (
        -- RAMA 1: Medicamentos e Insumos (IMD, DIMD)
        SELECT
            uf.descripcion AS unidad_funcional,
            de.descripcion AS departamento,
            cd.fecha_cargo::DATE AS fecha,
            cd.cantidad, 
            cd.valor_cargo
        FROM cuentas_detalle cd 
        INNER JOIN bodegas_documentos_d bdd ON cd.consecutivo=bdd.consecutivo 
        INNER JOIN inventarios_productos inp ON inp.codigo_producto=bdd.codigo_producto 
        INNER JOIN cuentas c ON c.numerodecuenta=cd.numerodecuenta
        INNER JOIN planes pl ON pl.plan_id = c.plan_id
        INNER JOIN ingresos i ON i.ingreso=c.ingreso 
        INNER JOIN departamentos de ON de.departamento = cd.departamento_al_cargar
        INNER JOIN unidades_funcionales uf ON uf.unidad_funcional = de.unidad_funcional
        WHERE cd.fecha_cargo::DATE >= '{fecha_inicio}'::DATE AND cd.fecha_cargo::DATE <= '{fecha_fin}'::DATE
        AND cd.cargo IN ('IMD','DIMD')
        {filtros_negocio}

        UNION ALL

        -- RAMA 2: Procedimientos y CUPS (No IMD/DIMD)
        SELECT 
            uf.descripcion AS unidad_funcional,
            de.descripcion AS departamento,
            cd.fecha_cargo::DATE AS fecha,
            cd.cantidad, 
            cd.valor_cargo
        FROM cuentas_detalle cd 
        INNER JOIN tarifarios_detalle td ON cd.cargo=td.cargo AND cd.tarifario_id=td.tarifario_id 
        INNER JOIN cuentas c ON c.numerodecuenta=cd.numerodecuenta 
        INNER JOIN planes pl ON pl.plan_id = c.plan_id
        INNER JOIN ingresos i ON i.ingreso=c.ingreso 
        INNER JOIN departamentos de ON de.departamento = cd.departamento_al_cargar
        INNER JOIN unidades_funcionales uf ON uf.unidad_funcional = de.unidad_funcional
        WHERE cd.fecha_cargo::DATE >= '{fecha_inicio}'::DATE AND cd.fecha_cargo::DATE <= '{fecha_fin}'::DATE
        AND cd.cargo NOT IN ('IMD','DIMD')
        {filtros_negocio}
    ) AS sub_consulta
    GROUP BY unidad_funcional, departamento, fecha
    ORDER BY unidad_funcional, departamento, fecha ASC
    """

    with st.spinner("📥 Extrayendo registros de facturación por unidades funcionales..."):
        try:
            df_uf = conn.query(query, ttl="1m")
            if df_uf.empty:
                st.warning("⚠️ No se encontraron registros para las fechas seleccionadas con los filtros activos.")
                return
        except Exception as query_error:
            st.error(f"❌ Error en la ejecución de la consulta SQL: {query_error}")
            return

    df_uf['total_valor'] = pd.to_numeric(df_uf['total_valor'], errors='coerce').fillna(0)
    df_uf['total_cantidad'] = pd.to_numeric(df_uf['total_cantidad'], errors='coerce').fillna(0)

    # ==========================================
    # 3. PROCESAMIENTO Y MÉTRICAS GLOBALES
    # ==========================================
    total_facturado_general = df_uf['total_valor'].sum()
    total_cantidad_general = df_uf['total_cantidad'].sum()
    
    if total_facturado_general == 0:
        st.warning("⚠️ La facturación total para este período es $0.")
        return

    df_resumen_uf = df_uf.groupby('unidad_funcional')['total_valor'].sum().reset_index().sort_values(by='total_valor', ascending=False)
    uf_top = df_resumen_uf.iloc[0]['unidad_funcional']
    valor_top = df_resumen_uf.iloc[0]['total_valor']
    participacion_top = valor_top / total_facturado_general

    st.divider()
    
    # Cuadro de Mando Rápido
    c_izq, c_der = st.columns(2)
    with c_izq:
        st.markdown(f"<h4 style='color: #34495e; border-bottom: 2px solid #bdc3c7; padding-bottom: 5px;'>📊 RESUMEN OPERATIVO</h4>", unsafe_allow_html=True)
        st.markdown(f"<p style='margin-bottom: 0px;'><b>Total Facturado General:</b></p>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='color: #2980b9; margin-top: 0px;'>{formato_cop(total_facturado_general)}</h2>", unsafe_allow_html=True)
        st.markdown(f"**Cantidad Total de Servicios Cargados:** {int(total_cantidad_general):,}")

    with c_der:
        st.markdown(f"<h4 style='color: #34495e; border-bottom: 2px solid #bdc3c7; padding-bottom: 5px;'>🏆 UNIDAD ESTRATÉGICA</h4>", unsafe_allow_html=True)
        st.markdown(f"<p style='margin-bottom: 0px;'><b>{uf_top}</b></p>", unsafe_allow_html=True)
        st.markdown(f"<h3 style='color: #27ae60; margin-top: 0px;'>{formato_cop(valor_top)}</h3>", unsafe_allow_html=True)
        st.markdown(f"**Representa el:** {formato_porcentaje(participacion_top)} de la operación")

    # ==========================================
    # 4. CONSTRUCCIÓN DE LA MATRIZ JERÁRQUICA 
    # ==========================================
    st.header(f"📋 DISTRIBUCIÓN MATRICIAL (UF Y DEPARTAMENTOS)")
    
    # 1. Aseguramos que siempre sea por día
    df_uf['fecha_obj'] = pd.to_datetime(df_uf['fecha'])
    df_uf['columna_tiempo'] = df_uf['fecha_obj'].dt.strftime('%d/%m/%Y')
    
    df_uf = df_uf.sort_values('fecha_obj')
    orden_columnas_tiempo = df_uf['columna_tiempo'].unique().tolist()

    # Creación del pivote base
    df_pivot = df_uf.pivot_table(
        index=['unidad_funcional', 'departamento'],
        columns='columna_tiempo',
        values=['total_cantidad', 'total_valor'],
        aggfunc='sum',
        fill_value=0
    )

    filas_procesadas = []
    dict_formatos = {}

    # 2. Agrupamos 
    for uf_name, sub_df in df_pivot.groupby(level=0):
        # A. Fila Padre: Unidad Funcional (Suma total de sus departamentos)
        uf_totales = sub_df.sum()
        fila_uf = {
            'Etiquetas de fila': f"➖ {uf_name}"
        }
        
        filas_depto_temp = []
        for dept_idx, row_values in sub_df.iterrows():
            # B. Filas Hijos: Departamentos indentados con espacios limpios
            fila_dept = {
                'Etiquetas de fila': f"        {dept_idx[1]}" 
            }
            
            for date_str in orden_columnas_tiempo:
                cant_val = row_values[('total_cantidad', date_str)]
                money_val = row_values[('total_valor', date_str)]
                
                # Asignar a la fila del departamento
                fila_dept[f"{date_str} (Cant)"] = cant_val
                fila_dept[f"{date_str} (Valor)"] = money_val
                
                # Asignar a la fila padre (sumatoria)
                fila_uf[f"{date_str} (Cant)"] = uf_totales[('total_cantidad', date_str)]
                fila_uf[f"{date_str} (Valor)"] = uf_totales[('total_valor', date_str)]
            
            fila_dept['Total Suma de cantidad'] = row_values['total_cantidad'].sum()
            fila_dept['Total Suma de valor_cargo'] = row_values['total_valor'].sum()
            filas_depto_temp.append(fila_dept)

        fila_uf['Total Suma de cantidad'] = uf_totales['total_cantidad'].sum()
        fila_uf['Total Suma de valor_cargo'] = uf_totales['total_valor'].sum()
        
        # Insertamos primero el Padre (UF) y luego los Hijos (Deptos)
        filas_procesadas.append(fila_uf)
        filas_procesadas.extend(filas_depto_temp)

    # 3. Fila de Cierre: Total General
    fila_gran_total = {
        'Etiquetas de fila': 'Total general'
    }
    for date_str in orden_columnas_tiempo:
        fila_gran_total[f"{date_str} (Cant)"] = df_pivot[('total_cantidad', date_str)].sum()
        fila_gran_total[f"{date_str} (Valor)"] = df_pivot[('total_valor', date_str)].sum()
    
    fila_gran_total['Total Suma de cantidad'] = total_cantidad_general
    fila_gran_total['Total Suma de valor_cargo'] = total_facturado_general
    filas_procesadas.append(fila_gran_total)

    # Convertimos a DataFrame
    df_final_uf = pd.DataFrame(filas_procesadas)

    # Formatos de números y moneda
    for col in df_final_uf.columns:
        if '(Valor)' in col or 'valor_cargo' in col:
            dict_formatos[col] = formato_cop
        elif '(Cant)' in col or 'cantidad' in col:
            dict_formatos[col] = lambda x: f"{int(x):,}"

    # 4. Estilos CSS (Negrita y sombreado para subtotales)
    def estilar_matriz_uf(row):
        etiqueta = str(row['Etiquetas de fila'])
        if etiqueta.startswith('➖') or etiqueta == 'Total general':
            # Fila de subtotal o total general (gris claro y negrita)
            return ['font-weight: bold; background-color: #f0f2f6; border-top: 1px solid #bdc3c7; border-bottom: 1px solid #bdc3c7;'] * len(row)
        # Fila normal de departamento
        return ['color: #34495e;'] * len(row)

    altura_calculada = (len(df_final_uf) * 35) + 50

    # Renderizamos la tabla
    st.dataframe(
        df_final_uf.style.apply(estilar_matriz_uf, axis=1).format(dict_formatos),
        use_container_width=True,
        hide_index=True,
        height=altura_calculada
    )

    # ==========================================
    # 5. SÍNTESIS GLOBAL Y TENDENCIAS POR UF
    # ==========================================
    st.divider()
    st.header("💡 SÍNTESIS ESTRATÉGICA POR UNIDAD")
    st.caption("Métricas clave de rendimiento agregadas por Unidad Funcional y su curva cronológica de comportamiento.")

    df_resumen_avanzado = df_uf.groupby('unidad_funcional').agg(
        Total_Facturado=('total_valor', 'sum'),
        Total_Cantidad=('total_cantidad', 'sum'),
        Dias_Activos=('fecha', 'nunique')
    ).reset_index()

    df_resumen_avanzado['Participacion_Pct'] = (df_resumen_avanzado['Total_Facturado'] / total_facturado_general) * 100
    df_resumen_avanzado['Promedio_Diario_Valor'] = df_resumen_avanzado['Total_Facturado'] / df_resumen_avanzado['Dias_Activos']

    # Sparklines (curva del período)
    df_tendencia = df_uf.groupby(['unidad_funcional', 'fecha_obj'])['total_valor'].sum().reset_index().sort_values(by='fecha_obj')
    serie_tendencia = df_tendencia.groupby('unidad_funcional')['total_valor'].apply(list).reset_index(name='Tendencia_Visual')

    df_dashboard = pd.merge(df_resumen_avanzado, serie_tendencia, on='unidad_funcional').sort_values(by='Total_Facturado', ascending=False)
    altura_dashboard_calculada = (len(df_dashboard) * 35) + 45

    st.dataframe(
        df_dashboard.style.format({
            'Total_Facturado': formato_cop,
            'Promedio_Diario_Valor': formato_cop,
            'Total_Cantidad': lambda x: f"{int(x):,}"
        }),
        column_config={
            "unidad_funcional": st.column_config.TextColumn("🏢 Unidad Funcional", width="large"),
            "Total_Facturado": st.column_config.TextColumn("💰 Total Facturado"),
            "Total_Cantidad": st.column_config.TextColumn("📦 Cant. Servicios"),
            "Participacion_Pct": st.column_config.ProgressColumn("📊 % Participación", format="%.1f %%", min_value=0, max_value=100),
            "Promedio_Diario_Valor": st.column_config.TextColumn("📅 Promedio Diario"),
            "Tendencia_Visual": st.column_config.LineChartColumn("📈 Curva del Período"),
            "Dias_Activos": None  
        },
        hide_index=True,
        use_container_width=True,
        height=altura_dashboard_calculada  
    )

    # ==========================================
    # 6. BOTÓN DE EXPORTACIÓN A PDF 
    # ==========================================
    st.divider()
    col_vacia1, col_boton, col_vacia2 = st.columns([1, 2, 1])
    
    with col_boton:
        pdf_bytes = generar_pdf_unidades_funcionales(
            df_dashboard=df_dashboard,
            etiqueta_periodo=etiqueta_periodo,
            total_general=formato_cop(total_facturado_general),
            total_cantidad=f"{int(total_cantidad_general):,}",
            uf_top=uf_top,
            valor_top=formato_cop(valor_top),
            participacion_top=formato_porcentaje(participacion_top)
        )
        
        st.download_button(
            label="📄 Exportar Informe de Unidades a PDF",
            data=pdf_bytes,
            file_name=f"Reporte_Unidades_Funcionales_{df_uf['fecha_obj'].min().strftime('%Y-%m-%d')}_al_{df_uf['fecha_obj'].max().strftime('%Y-%m-%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary"
        )    