import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import calendar
from .utils import formato_cop, formato_porcentaje, generar_pdf_mercadeo

def mostrar_mercadeo():
    st.markdown("<h2 style='text-align: center;'>💉 ANÁLISIS DE MERCADEO Y SUMINISTROS</h2>", unsafe_allow_html=True)

    # ==========================================
    # 1. CONFIGURACIÓN DINÁMICA DE PERÍODOS 
    # ==========================================
    with st.expander("⚙️ CONTROL DE PERÍODO", expanded=True):
        modo_periodo = st.radio(
            "🗓️ ¿Cómo quiere ver los datos?",
            options=["Por Mes", "Por Año", "Rango de Fechas"],
            index=0,
            horizontal=True,
            key="merc_modo_periodo"
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
                ano_sel = st.selectbox("Año", lista_anos, index=0, key="merc_ano_mes")
            with col2:
                mes_sel = st.selectbox(
                    "Mes", list(meses_dic.keys()),
                    format_func=lambda x: meses_dic[x],
                    index=ayer.month - 1,
                    key="merc_mes_mes"
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
            ano_sel = st.selectbox("Año", lista_anos, index=0, key="merc_ano_solo")
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
                fecha_ini_sel = st.date_input("Desde", value=primer_dia_mes, max_value=ayer, key="merc_fecha_ini") 
            with col2:
                fecha_fin_sel = st.date_input("Hasta", value=ayer, max_value=ayer, key="merc_fecha_fin")

            if fecha_fin_sel < fecha_ini_sel:
                st.error("⚠️ La fecha de fin debe ser mayor o igual a la de inicio.")
                return

            fecha_inicio = fecha_ini_sel.strftime("%Y-%m-%d")
            fecha_fin = fecha_fin_sel.strftime("%Y-%m-%d")
            etiqueta_periodo = f"{fecha_ini_sel.strftime('%d/%m/%Y')} al {fecha_fin_sel.strftime('%d/%m/%Y')}"

        st.info(f"📅 **Período de Análisis:** {etiqueta_periodo} | 📌 **Cohorte:** {ayer.strftime('%d-%m-%Y')}")

    # ==========================================
    # 2. CONEXIÓN Y CARGA DE DATOS
    # ==========================================
    try:
        conn = st.connection(
            "ucm", 
            type="sql",
            connect_args={
                "sslmode": "verify-ca",
                "sslrootcert": "C:/Users/JOHN/Documents/Proyecto/.streamlit/ca_ucm.crt",
                "sslcert": "C:/Users/JOHN/Documents/Proyecto/.streamlit/lector_ucm.crt",
                "sslkey": "C:/Users/JOHN/Documents/Proyecto/.streamlit/lector_ucm.key"
            }
        )
    except Exception as e:
        st.error(f"Error crítico al conectar: {e}")
        return

    filtros_negocio = """
        AND (cd.facturado = '1' OR cd.facturado IS NULL OR TRIM(cd.facturado) = '')
        AND (cd.sw_paquete_facturado = '1' OR cd.sw_paquete_facturado IS NULL OR TRIM(cd.sw_paquete_facturado) = '')
        AND (c.estado IN ('0', '1', '2', '3') OR c.estado IS NULL)
    """

    query = f"""
    SELECT 
        linea_mercadeo,
        fecha,
        SUM(valor_cargo) AS total_valor
    FROM (
        -- RAMA 1: Medicamentos, Insumos, Alimentos (Tienen grupo de inventario)
        SELECT 
            COALESCE(igi.descripcion, '(en blanco)') AS linea_mercadeo,
            cd.fecha_cargo::DATE AS fecha,
            cd.valor_cargo
        FROM cuentas_detalle cd
        INNER JOIN cuentas c ON c.numerodecuenta = cd.numerodecuenta
        INNER JOIN bodegas_documentos_d bdd ON cd.consecutivo = bdd.consecutivo 
        INNER JOIN inventarios_productos inp ON inp.codigo_producto = bdd.codigo_producto 
        LEFT JOIN inv_grupos_inventarios igi ON igi.grupo_id = inp.grupo_id
        WHERE cd.fecha_cargo::DATE >= '{fecha_inicio}'::DATE AND cd.fecha_cargo::DATE <= '{fecha_fin}'::DATE
        AND cd.cargo IN ('IMD','DIMD')
        {filtros_negocio}

        UNION ALL

        -- RAMA 2: Procedimientos y Servicios (No pasan por bodega, van a '(en blanco)')
        SELECT 
            '(en blanco)' AS linea_mercadeo,
            cd.fecha_cargo::DATE AS fecha,
            cd.valor_cargo
        FROM cuentas_detalle cd
        INNER JOIN cuentas c ON c.numerodecuenta = cd.numerodecuenta
        WHERE cd.fecha_cargo::DATE >= '{fecha_inicio}'::DATE AND cd.fecha_cargo::DATE <= '{fecha_fin}'::DATE
        AND cd.cargo NOT IN ('IMD','DIMD')
        {filtros_negocio}
    ) AS sub_consulta
    GROUP BY linea_mercadeo, fecha
    ORDER BY fecha ASC
    """

    try:
        # Ejecutamos la consulta y la guardamos en el DataFrame df_merc
        df_merc = conn.query(query)
        
        # Validación de seguridad: si no hay datos, detenemos la ejecución
        if df_merc.empty:
            st.warning("⚠️ No se encontraron datos de mercadeo para el período seleccionado.")
            return
            
    except Exception as e:
        st.error(f"❌ Error al ejecutar la consulta SQL: {e}")
        return

    # ==========================================
    # 3. PROCESAMIENTO Y MÉTRICAS
    # ==========================================
    total_facturado_general = df_merc['total_valor'].sum()
    df_resumen = df_merc.groupby('linea_mercadeo')['total_valor'].sum().reset_index().sort_values(by='total_valor', ascending=False)
    
    categoria_top = df_resumen.iloc[0]['linea_mercadeo']
    valor_top = df_resumen.iloc[0]['total_valor']
    participacion_top = valor_top / total_facturado_general if total_facturado_general > 0 else 0

    st.divider()
    c_izq, c_der = st.columns(2)
    with c_izq:
        st.markdown(f"<h4 style='color: #34495e; border-bottom: 2px solid #bdc3c7;'>📊 RESUMEN DEL PERÍODO</h4>", unsafe_allow_html=True)
        st.markdown(f"<b>Total Facturado:</b>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='color: #2980b9; margin-top: 0px;'>{formato_cop(total_facturado_general)}</h2>", unsafe_allow_html=True)

    with c_der:
        st.markdown(f"<h4 style='color: #34495e; border-bottom: 2px solid #bdc3c7;'>🏆 LÍNEA PRINCIPAL</h4>", unsafe_allow_html=True)
        st.markdown(f"<b>{categoria_top}</b>", unsafe_allow_html=True)
        st.markdown(f"<h3 style='color: #27ae60; margin-top: 0px;'>{formato_cop(valor_top)}</h3>", unsafe_allow_html=True)

    # ==========================================
    # 4. TABLA MATRICIAL 
    # ==========================================
    st.header(f"📋 DISTRIBUCIÓN MATRICIAL POR DÍA")
    
    df_merc['fecha_obj'] = pd.to_datetime(df_merc['fecha'])
    df_merc['columna_tiempo'] = df_merc['fecha_obj'].dt.strftime('%d/%m/%Y')
    
    df_merc = df_merc.sort_values('fecha_obj')
    orden_columnas = df_merc['columna_tiempo'].unique().tolist()

    df_pivot = df_merc.pivot_table(
        index='linea_mercadeo',
        columns='columna_tiempo',
        values='total_valor',
        aggfunc='sum',
        fill_value=0
    )
    
    df_pivot = df_pivot.reindex(columns=orden_columnas)
    df_pivot['Total general'] = df_pivot.sum(axis=1)
    df_pivot = df_pivot.sort_values(by='Total general', ascending=False)
    
    fila_totales = df_pivot.sum(axis=0)
    df_fila_totales = pd.DataFrame(fila_totales).T
    df_fila_totales.index = ['Total general']
    
    df_final = pd.concat([df_pivot, df_fila_totales]).reset_index().rename(columns={'index': 'Etiquetas de fila'})

    dict_formatos = {col: formato_cop for col in df_final.columns if col != 'Etiquetas de fila'}

    def estilar_tabla(row):
        if row['Etiquetas de fila'] == 'Total general':
            return ['font-weight: bold; background-color: #f0f2f6; border-top: 2px solid #bdc3c7;'] * len(row)
        return [''] * len(row)

    altura_calculada = (len(df_final) * 35) + 45

    st.dataframe(
        df_final.style.apply(estilar_tabla, axis=1).format(dict_formatos),
        use_container_width=True,
        hide_index=True,
        height=altura_calculada
    )

    # ==========================================
    # 5. SÍNTESIS GLOBAL Y TENDENCIAS
    # ==========================================
    st.divider()
    st.header("💡 SÍNTESIS ESTRATÉGICA")
    
    df_resumen_avanzado = df_merc.groupby('linea_mercadeo').agg(
        Total_Facturado=('total_valor', 'sum'),
        Dias_Activos=('fecha', 'nunique')
    ).reset_index()

    df_resumen_avanzado['Participacion_Pct'] = (df_resumen_avanzado['Total_Facturado'] / total_facturado_general) * 100
    df_resumen_avanzado['Promedio_Diario'] = df_resumen_avanzado['Total_Facturado'] / df_resumen_avanzado['Dias_Activos']

    df_tendencia = df_merc.groupby(['linea_mercadeo', 'fecha_obj'])['total_valor'].sum().reset_index().sort_values(by='fecha_obj')
    serie_tendencia = df_tendencia.groupby('linea_mercadeo')['total_valor'].apply(list).reset_index(name='Tendencia_Visual')

    df_dashboard = pd.merge(df_resumen_avanzado, serie_tendencia, on='linea_mercadeo').sort_values(by='Total_Facturado', ascending=False)
    
    altura_dashboard = (len(df_dashboard) * 35) + 45

    st.dataframe(
        df_dashboard.style.format({
            'Total_Facturado': formato_cop,
            'Promedio_Diario': formato_cop
        }),
        column_config={
            "linea_mercadeo": st.column_config.TextColumn("📦 Línea / Grupo"),
            "Total_Facturado": st.column_config.TextColumn("💰 Total Facturado"),
            "Participacion_Pct": st.column_config.ProgressColumn("📊 Participación", format="%.1f %%", min_value=0, max_value=100),
            "Promedio_Diario": st.column_config.TextColumn("📅 Promedio Diario"),
            "Tendencia_Visual": st.column_config.LineChartColumn("📈 Tendencia"),
            "Dias_Activos": None  
        },
        hide_index=True,
        use_container_width=True,
        height=altura_dashboard  
    )

    # ==========================================
    # 6. BOTÓN DE EXPORTACIÓN A PDF 
    # ==========================================
    st.divider()
    _, col_boton, _ = st.columns([1, 2, 1])
    
    with col_boton:
        pdf_bytes = generar_pdf_mercadeo(
            df_dashboard=df_dashboard,
            etiqueta_periodo=etiqueta_periodo,
            total_general=formato_cop(total_facturado_general),
            total_categorias=len(df_resumen),
            categoria_top=categoria_top,
            valor_top=formato_cop(valor_top),
            participacion_top=formato_porcentaje(participacion_top)
        )
        
        st.download_button(
            label="📄 Exportar Informe de Mercadeo a PDF",
            data=pdf_bytes,
            file_name=f"Reporte_Mercadeo_Suministros_{df_merc['fecha_obj'].min().strftime('%Y-%m-%d')}_al_{df_merc['fecha_obj'].max().strftime('%Y-%m-%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary"
        )