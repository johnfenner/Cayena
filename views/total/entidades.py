# views/total/entidades.py
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import calendar
import plotly.graph_objects as go

# IMPORTANTE: Cambiamos las importaciones para usar las funciones del Holding
from .utils import (
    formato_cop, 
    formato_porcentaje, 
    obtener_datos_holding, 
    generar_pdf_entidades_holding
)

def mostrar_entidades():
    st.markdown("<h2 style='text-align: center;'>🏥 ANÁLISIS DE FACTURACIÓN POR ENTIDADES (HOLDING)</h2>", unsafe_allow_html=True)

    # ==========================================
    # 1. CONFIGURACIÓN DINÁMICA DE PERÍODOS 
    # ==========================================
    with st.expander("⚙️ CONTROL DE PERÍODO", expanded=True):
        modo_periodo = st.radio(
            "🗓️ ¿Cómo quiere ver los datos?",
            options=["Por Mes", "Por Año", "Rango de Fechas"],
            index=0,
            horizontal=True,
            key="ent_modo_periodo_holding"
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
                ano_sel = st.selectbox("Año", lista_anos, index=0, key="ent_ano_mes_h")
            with col2:
                mes_sel = st.selectbox(
                    "Mes", list(meses_dic.keys()),
                    format_func=lambda x: meses_dic[x],
                    index=ayer.month - 1,
                    key="ent_mes_mes_h"
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
            ano_sel = st.selectbox("Año", lista_anos, index=0, key="ent_ano_solo_h")
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
                fecha_ini_sel = st.date_input("Desde", value=primer_dia_mes, max_value=ayer, key="ent_fecha_ini_h") 
            with col2:
                fecha_fin_sel = st.date_input("Hasta", value=ayer, max_value=ayer, key="ent_fecha_fin_h")

            if fecha_fin_sel < fecha_ini_sel:
                st.error("⚠️ La fecha de fin debe ser mayor o igual a la de inicio.")
                return

            fecha_inicio = fecha_ini_sel.strftime("%Y-%m-%d")
            fecha_fin = fecha_fin_sel.strftime("%Y-%m-%d")
            etiqueta_periodo = f"{fecha_ini_sel.strftime('%d/%m/%Y')} → {fecha_fin_sel.strftime('%d/%m/%Y')}"

        st.info(f"📅 **Período de Análisis Holding:** {etiqueta_periodo} | 📌 **corte:** {ayer.strftime('%d-%m-%Y')}")

    # ==========================================
    # 2. EXTRACCIÓN MULTI-SEDE Y CARGA DE DATOS
    # ==========================================
    filtros_negocio = """
        AND (cd.facturado = '1' OR cd.facturado IS NULL OR TRIM(cd.facturado) = '')
        AND (cd.sw_paquete_facturado = '1' OR cd.sw_paquete_facturado IS NULL OR TRIM(cd.sw_paquete_facturado) = '')
        AND (c.estado IN ('0', '1', '2', '3') OR c.estado IS NULL)
    """

    query = f"""
    SELECT
        t.nombre_tercero AS entidad,
        cd.fecha_cargo::DATE AS fecha,
        SUM(cd.valor_cargo) AS total_valor
    FROM cuentas_detalle cd
    INNER JOIN cuentas c        ON c.numerodecuenta = cd.numerodecuenta
    INNER JOIN planes pl        ON pl.plan_id = c.plan_id
    INNER JOIN terceros t       ON pl.tipo_tercero_id = t.tipo_id_tercero
                                AND pl.tercero_id      = t.tercero_id
    WHERE cd.fecha_cargo::DATE >= '{fecha_inicio}'::DATE AND cd.fecha_cargo::DATE <= '{fecha_fin}'::DATE
    {filtros_negocio}
    GROUP BY t.nombre_tercero, cd.fecha_cargo::DATE
    ORDER BY fecha ASC
    """

    with st.spinner("📥 Consolidando registros de facturación por entidades de todas las sedes..."):
        try:
            # LLAMADA AL MOTOR DEL HOLDING
            df_ent = obtener_datos_holding(query)
            if df_ent.empty:
                st.warning("⚠️ No se encontraron registros para las fechas seleccionadas en ninguna sede.")
                return
        except Exception as query_error:
            st.error(f"❌ Error en la ejecución de la consolidación: {query_error}")
            return

    df_ent['total_valor'] = pd.to_numeric(df_ent['total_valor'], errors='coerce').fillna(0)

    # ==========================================
    # 3. PROCESAMIENTO Y MÉTRICAS
    # ==========================================
    total_facturado_general = df_ent['total_valor'].sum()
    
    if total_facturado_general == 0:
        st.warning("⚠️ La facturación total para este período es $0.")
        return

    # Pandas agrupará automáticamente las entidades que se llamen igual en diferentes clínicas
    df_resumen_entidades = df_ent.groupby('entidad')['total_valor'].sum().reset_index().sort_values(by='total_valor', ascending=False)
    
    entidad_top = df_resumen_entidades.iloc[0]['entidad']
    valor_top = df_resumen_entidades.iloc[0]['total_valor']
    participacion_top = valor_top / total_facturado_general

    st.divider()
    
    # Cuadro de Resumen
    c_izq, c_der = st.columns(2)
    with c_izq:
        st.markdown(f"<h4 style='color: #34495e; border-bottom: 2px solid #bdc3c7; padding-bottom: 5px;'>📊 RESUMEN DEL PERÍODO HOLDING</h4>", unsafe_allow_html=True)
        st.markdown(f"<p style='margin-bottom: 0px;'><b>Total Facturado en el Período:</b></p>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='color: #2980b9; margin-top: 0px;'>{formato_cop(total_facturado_general)}</h2>", unsafe_allow_html=True)
        st.markdown(f"**Total de Entidades Atendidas Globales:** {len(df_resumen_entidades)}")

    with c_der:
        st.markdown(f"<h4 style='color: #34495e; border-bottom: 2px solid #bdc3c7; padding-bottom: 5px;'>🏆 ENTIDAD PRINCIPAL GLOBAL</h4>", unsafe_allow_html=True)
        st.markdown(f"<p style='margin-bottom: 0px;'><b>{entidad_top}</b></p>", unsafe_allow_html=True)
        st.markdown(f"<h3 style='color: #27ae60; margin-top: 0px;'>{formato_cop(valor_top)}</h3>", unsafe_allow_html=True)
        st.markdown(f"**Representa el:** {formato_porcentaje(participacion_top)} del total del holding")

    # ==========================================
    # 4. TABLA DE DISTRIBUCIÓN MATRICIAL 
    # ==========================================
    st.header(f"📋 DISTRIBUCIÓN GLOBAL POR ENTIDAD")
    
    df_ent['fecha_obj'] = pd.to_datetime(df_ent['fecha'])
    dias_unicos = df_ent['fecha_obj'].nunique()

    if dias_unicos > 31:
        df_ent['columna_tiempo'] = df_ent['fecha_obj'].dt.strftime('%m/%Y')
    else:
        df_ent['columna_tiempo'] = df_ent['fecha_obj'].dt.strftime('%d/%m/%Y')
    
    df_ent = df_ent.sort_values('fecha_obj')
    orden_columnas_tiempo = df_ent['columna_tiempo'].unique().tolist()

    df_pivot = df_ent.pivot_table(
        index='entidad',
        columns='columna_tiempo',
        values='total_valor',
        aggfunc='sum',
        fill_value=0
    )
    
    df_pivot = df_pivot.reindex(columns=orden_columnas_tiempo)
    df_pivot['Total general'] = df_pivot.sum(axis=1)
    df_pivot = df_pivot.sort_values(by='Total general', ascending=False)
    
    fila_totales = df_pivot.sum(axis=0)
    df_fila_totales = pd.DataFrame(fila_totales).T
    df_fila_totales.index = ['Total general']
    
    df_final = pd.concat([df_pivot, df_fila_totales])
    df_final = df_final.reset_index().rename(columns={'index': 'Entidad'})

    dict_formatos = {col: formato_cop for col in df_final.columns if col != 'Entidad'}

    def estilar_tabla(row):
        if row['Entidad'] == 'Total general':
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
    st.header("💡 SÍNTESIS ESTRATÉGICA CONSOLIDADA")
    st.caption("Visión integral que combina el impacto de cada entidad a nivel Holding, sus promedios exactos y su comportamiento cronológico.")

    df_resumen_avanzado = df_ent.groupby('entidad').agg(
        Total_Facturado=('total_valor', 'sum'),
        Dias_Activos=('fecha', 'nunique')
    ).reset_index()

    total_facturado_global = df_resumen_avanzado['Total_Facturado'].sum()
    df_resumen_avanzado['Participacion_Pct'] = (df_resumen_avanzado['Total_Facturado'] / total_facturado_global) * 100
    df_resumen_avanzado['Promedio_Diario'] = df_resumen_avanzado['Total_Facturado'] / df_resumen_avanzado['Dias_Activos']

    df_tendencia = df_ent.groupby(['entidad', 'fecha_obj'])['total_valor'].sum().reset_index()
    df_tendencia = df_tendencia.sort_values(by='fecha_obj')
    serie_tendencia = df_tendencia.groupby('entidad')['total_valor'].apply(list).reset_index(name='Tendencia_Visual')

    df_dashboard = pd.merge(df_resumen_avanzado, serie_tendencia, on='entidad')
    df_dashboard = df_dashboard.sort_values(by='Total_Facturado', ascending=False)

    altura_dashboard_calculada = (len(df_dashboard) * 35) + 45

    st.dataframe(
        df_dashboard.style.format({
            'Total_Facturado': formato_cop,
            'Promedio_Diario': formato_cop
        }),
        column_config={
            "entidad": st.column_config.TextColumn(
                "🏢 Entidad", 
                width="large"
            ),
            "Total_Facturado": st.column_config.TextColumn(
                "💰 Total Facturado",
            ),
            "Participacion_Pct": st.column_config.ProgressColumn(
                "📊 (%) de Participación", 
                format="%.1f %%", 
                min_value=0, 
                max_value=100,
            ),
            "Promedio_Diario": st.column_config.TextColumn(
                "📅 Promedio Diario Global",
            ),
            "Tendencia_Visual": st.column_config.LineChartColumn(
                "📈 Curva del Período",
            ),
            "Dias_Activos": None  
        },
        hide_index=True,
        use_container_width=True,
        height=altura_dashboard_calculada  
    )

    # ==========================================
    # 6. BOTÓN DE EXPORTACIÓN A PDF HOLDING
    # ==========================================
    st.divider()
    col_vacia1, col_boton, col_vacia2 = st.columns([1, 2, 1])
    
    with col_boton:
        # LLAMADA A LA FUNCIÓN DE PDF DEL HOLDING
        pdf_bytes = generar_pdf_entidades_holding(
            df_final=df_final,
            df_dashboard=df_dashboard,
            etiqueta_periodo=etiqueta_periodo,
            total_general=formato_cop(total_facturado_general),
            total_entidades=len(df_resumen_entidades),
            entidad_top=entidad_top,
            valor_top=formato_cop(valor_top),
            participacion_top=formato_porcentaje(participacion_top)
        )
        
        st.download_button(
            label="📄 Exportar Informe Total de Entidades del Holding a PDF",
            data=pdf_bytes,
            file_name=f"Reporte_Facturacion_Entidades_{df_ent['fecha_obj'].min().strftime('%Y-%m-%d')}_al_{df_ent['fecha_obj'].max().strftime('%Y-%m-%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary"
        )

def mostrar_entidades_mejorado():
    mostrar_entidades()