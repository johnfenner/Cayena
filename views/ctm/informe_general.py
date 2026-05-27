import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import calendar
import plotly.graph_objects as go
from .utils import formato_cop, formato_porcentaje, color_filas_vr, generar_pdf_fidedigno

def mostrar_informe_general():
    st.markdown(
        "<h2 style='text-align: center;'>📊 INFORME GENERAL - CONSUMO DIARIO</h2>", 
        unsafe_allow_html=True
    )
    
    # 1. CONFIGURACIÓN DINÁMICA DE PERÍODOS Y METAS
    with st.expander("⚙️ CONTROL DE PERÍODO Y METAS", expanded=True):
        modo_periodo = st.radio(
            "🗓️ ¿Cómo quiere ver los datos?",
            options=["Por Mes", "Por Año", "Rango de Fechas"],
            index=0,
            horizontal=True,
            help=(
                "**Por Mes**: Ver un mes específico con meta mensual.\n\n"
                "**Por Año**: Ver todo un año con meta anual basada en la cuota mensual.\n\n"
                "**Rango de Fechas**: Elegir libremente fechas de inicio y fin."
            )
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

        fecha_inicio = None
        fecha_fin = None
        etiqueta_periodo = ""
        meta_mensual_base = 9_000_000_000

        if modo_periodo == "Por Mes":
            col1, col2, col3 = st.columns(3)
            with col1:
                ano_sel = st.selectbox("Año", lista_anos, index=0)
            with col2:
                mes_sel = st.selectbox(
                    "Mes", list(meses_dic.keys()),
                    format_func=lambda x: meses_dic[x],
                    index=ayer.month - 1
                )
            
            _, dias_en_mes = calendar.monthrange(ano_sel, mes_sel)
            fecha_inicio = f"{ano_sel}-{mes_sel:02d}-01"
            fecha_fin = f"{ano_sel}-{mes_sel:02d}-{dias_en_mes:02d}"
            etiqueta_periodo = f"{meses_dic[mes_sel].upper()} {ano_sel}"

            with col3:
                meta_mensual_base = st.number_input(
                    "Meta del Mes (COP)",
                    value=9_000_000_000,
                    step=500_000_000,
                    format="%d"
                )
            
            meta_global_total = meta_mensual_base
            meta_comparativa_fila = meta_mensual_base / dias_en_mes 
            dias_totales_periodo = dias_en_mes

        elif modo_periodo == "Por Año":
            col1, col2 = st.columns(2)
            with col1:
                ano_sel = st.selectbox("Año", lista_anos, index=0)
            
            fecha_inicio = f"{ano_sel}-01-01"
            fecha_fin = f"{ano_sel}-12-31"
            etiqueta_periodo = f"AÑO {ano_sel}"

            with col2:
                meta_mensual_base = st.number_input(
                    "Meta Mensual Estándar (COP)",
                    value=9_000_000_000,
                    step=500_000_000,
                    format="%d"
                )
            
            meta_global_total = meta_mensual_base * 12
            meta_comparativa_fila = meta_mensual_base 
            dias_totales_periodo = 12 

        else:
            primer_dia_mes = ayer.replace(day=1)

            col1, col2, col3 = st.columns(3)
            with col1:
                fecha_ini_sel = st.date_input("Desde", value=primer_dia_mes, max_value=ayer)
            with col2:
                fecha_fin_sel = st.date_input("Hasta", value=ayer, max_value=ayer)

            if fecha_fin_sel < fecha_ini_sel:
                st.error("⚠️ La fecha de fin debe ser mayor o igual a la de inicio.")
                return

            fecha_inicio = fecha_ini_sel.strftime("%Y-%m-%d")
            fecha_fin = fecha_fin_sel.strftime("%Y-%m-%d")
            dias_filtrados = (fecha_fin_sel - fecha_ini_sel).days + 1
            etiqueta_periodo = f"{fecha_ini_sel.strftime('%d/%m/%Y')} → {fecha_fin_sel.strftime('%d/%m/%Y')}"
            
            with col3:
                meta_mensual_base = st.number_input(
                    "Meta Mensual de Referencia (COP)",
                    value=9_000_000_000,
                    step=500_000_000,
                    format="%d"
                )
            
            _, dias_mes_ref = calendar.monthrange(fecha_ini_sel.year, fecha_ini_sel.month)
            meta_comparativa_fila = meta_mensual_base / dias_mes_ref 
            meta_global_total = meta_comparativa_fila * dias_filtrados 
            dias_totales_periodo = dias_filtrados

        if modo_periodo == "Por Año":
            st.info(f"📅 **Análisis:** {etiqueta_periodo} ｜ 📌 **Cohorte:** {ayer.strftime('%d-%m-%Y')} ｜ 🎯 **Meta Mensual Unitario:** {formato_cop(meta_mensual_base)} ｜ 🚀 **Meta Anual Total (Suma):** {formato_cop(meta_global_total)}")
        else:
            st.info(f"📅 **Análisis:** {etiqueta_periodo} ｜ 📌 **Cohorte:** {ayer.strftime('%d-%m-%Y')} ｜ 🎯 **Meta Global en Base a la Meta Mensual de Referencia:** {formato_cop(meta_global_total)}")

    # 2. CONEXIÓN Y CARGA DE DATOS
    try:
        conn = st.connection(
            "traumanorte", 
            type="sql",
            connect_args={
                "sslmode": "verify-ca",
                "sslrootcert": "C:/Users/JOHN/Documents/Proyecto/.streamlit/ca_traumanorte.crt",
                "sslcert": "C:/Users/JOHN/Documents/Proyecto/.streamlit/lector_traumanorte.crt",
                "sslkey": "C:/Users/JOHN/Documents/Proyecto/.streamlit/lector_traumanorte.key"
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
    SELECT TO_CHAR(cd.fecha_cargo, 'YYYY-MM-DD') AS fecha_cargo, cd.valor_cargo
    FROM cuentas_detalle cd 
        INNER JOIN bodegas_documentos_d bdd ON cd.consecutivo=bdd.consecutivo 
        INNER JOIN inventarios_productos inp ON inp.codigo_producto=bdd.codigo_producto 
        INNER JOIN cuentas c ON c.numerodecuenta=cd.numerodecuenta
    WHERE cd.fecha_cargo::DATE >= '{fecha_inicio}'::DATE AND cd.fecha_cargo::DATE <= '{fecha_fin}'::DATE
        AND cd.cargo IN ('IMD','DIMD') {filtros_negocio}
    UNION ALL
    SELECT TO_CHAR(cd.fecha_cargo, 'YYYY-MM-DD') AS fecha_cargo, cd.valor_cargo
    FROM cuentas_detalle cd 
        INNER JOIN tarifarios_detalle td ON cd.cargo=td.cargo AND cd.tarifario_id=td.tarifario_id 
        INNER JOIN cuentas c ON c.numerodecuenta=cd.numerodecuenta 
    WHERE cd.fecha_cargo::DATE >= '{fecha_inicio}'::DATE AND cd.fecha_cargo::DATE <= '{fecha_fin}'::DATE
        AND cd.cargo NOT IN ('IMD','DIMD') {filtros_negocio}
    """

    with st.spinner("📥 Extrayendo registros de la base de datos..."):
        try:
            df = conn.query(query, ttl="1m")
            if df.empty:
                st.warning(f"⚠️ No se encontraron registros en las fechas seleccionadas.")
                return
        except Exception as query_error:
            st.error(f"❌ Error en la ejecución de la consulta SQL: {query_error}")
            return

    # 3. PROCESAMIENTO ADAPTATIVO
    df['fecha_cargo'] = pd.to_datetime(df['fecha_cargo'])
    df['valor_cargo'] = pd.to_numeric(df['valor_cargo'], errors='coerce').fillna(0)

    ayer_dt = pd.Timestamp.now().normalize() - pd.Timedelta(days=1)
    df = df[df['fecha_cargo'] <= ayer_dt]

    if df.empty:
        st.warning("⚠️ No hay datos válidos hasta la fecha actual en el rango seleccionado.")
        return

    if modo_periodo == "Por Año":
        df['periodo'] = df['fecha_cargo'].dt.to_period('M')
        consumo_agrupado = df.groupby('periodo')['valor_cargo'].sum().reset_index()
        consumo_agrupado = consumo_agrupado.sort_values('periodo')
        consumo_agrupado['fecha_label'] = consumo_agrupado['periodo'].dt.strftime('%B %Y').str.upper()
        consumo_agrupado['fecha_plot'] = consumo_agrupado['periodo'].dt.to_timestamp()
        
        unidades_con_datos = len(consumo_agrupado)
        unidades_restantes = max(0, 12 - unidades_con_datos)
        
        lbl_unidad = "Meses"
        lbl_unidad_sing = "Mes"
        lbl_facturacion = "Facturación del Mes"
        lbl_diferencia = "Diferencia vs Meta Mensual"
        lbl_cumplimiento = "% Cumplimiento Mes"
        
        lbl_rango_tit = "📊 RENDIMIENTO DEL AÑO A LA FECHA"
        lbl_cierre_tit = "🎯 PROYECCIÓN PARA CERRAR EL AÑO COMPLETO"
        lbl_txt_unidades = "Meses transcurridos con registros"
        lbl_txt_total = "Total Facturado en lo que va del Año"
        lbl_txt_esperado = "Meta Ideal Acumulada que deberíamos llevar"
        lbl_txt_meta_global = "Meta Final de todo el Año Completo"
        lbl_txt_faltante = "Dinero que falta facturar para salvar el Año"
        lbl_txt_restantes = "Meses que le quedan al año para trabajar"
        lbl_req = "Cuota Mensual Requerida (Para los Meses Restantes)"
        lbl_caption_req = "Monto promedio que cada mes restante del año debe registrar para cumplir el objetivo anual."
        lbl_txt_avance = "Avance Real frente a la Meta de todo el Año"

    elif modo_periodo == "Por Mes":
        consumo_agrupado = df.groupby('fecha_cargo')['valor_cargo'].sum().reset_index()
        consumo_agrupado = consumo_agrupado.sort_values('fecha_cargo')
        consumo_agrupado['fecha_label'] = consumo_agrupado['fecha_cargo'].dt.strftime('%d/%m/%Y')
        consumo_agrupado['fecha_plot'] = consumo_agrupado['fecha_cargo']
        
        unidades_con_datos = len(consumo_agrupado)
        unidades_restantes = max(0, dias_totales_periodo - unidades_con_datos)
            
        lbl_unidad = "Días"
        lbl_unidad_sing = "Día"
        lbl_facturacion = "Facturación del Día"
        lbl_diferencia = "Diferencia vs Meta Diaria"
        lbl_cumplimiento = "% Cumplimiento Día"
        
        lbl_rango_tit = "📊 RENDIMIENTO DE LOS DÍAS TRANSCURRIDOS"
        lbl_cierre_tit = "🎯 PROYECCIÓN PARA CERRAR EL MES COMPLETO"
        lbl_txt_unidades = "Días Evaluados con Registros"
        lbl_txt_total = "Total Facturado Hasta el Día de Hoy"
        lbl_txt_esperado = "Meta Ideal Acumulada"
        lbl_txt_meta_global = "Meta Final Fijada Para Este Mes Completo"
        lbl_txt_faltante = "Dinero que Falta Facturar para Alcanzar la Meta del Mes"
        lbl_txt_restantes = "Días Disponibles que le Quedan al Mes"
        lbl_req = "Meta Diaria Promedio (Para los Días Restantes)"
        lbl_caption_req = "Cada Día que le Queda al Calendario Debemos Facturar esto como Mínimo."
        lbl_txt_avance = "Avance Real frente a la Meta de este Mes"

    else:
        consumo_agrupado = df.groupby('fecha_cargo')['valor_cargo'].sum().reset_index()
        consumo_agrupado = consumo_agrupado.sort_values('fecha_cargo')
        consumo_agrupado['fecha_label'] = consumo_agrupado['fecha_cargo'].dt.strftime('%d/%m/%Y')
        consumo_agrupado['fecha_plot'] = consumo_agrupado['fecha_cargo']
        
        unidades_con_datos = len(consumo_agrupado)
        unidades_restantes = max(0, dias_filtrados - unidades_con_datos)
            
        lbl_unidad = "Días"
        lbl_unidad_sing = "Día"
        lbl_facturacion = "Facturación del Día"
        lbl_diferencia = "Diferencia vs Meta Diaria"
        lbl_cumplimiento = "% Cumplimiento Día"
        
        lbl_rango_tit = "📊 RENDIMIENTO DEL PERÍODO SELECCIONADO"
        lbl_cierre_tit = "🎯 BALANCE FINAL DEL PERÍODO SELECCIONADO"
        lbl_txt_unidades = "Días con registros dentro del rango"
        lbl_txt_total = "Total Facturado en este Rango de Fechas"
        lbl_txt_esperado = "Meta Proporcional esperada para los días con datos"
        lbl_txt_meta_global = "Meta Total Objetivo asignada a todo el Rango Elegido"
        lbl_txt_faltante = "Dinero que faltó/falta para cumplir el objetivo del Rango"
        lbl_txt_restantes = "Días sin datos o futuros dentro del Rango"
        lbl_req = "Facturación Diaria Requerida (Para completar el Rango)"
        lbl_caption_req = "Monto diario necesario si el rango seleccionado incluye días futuros o por completar."
        lbl_txt_avance = "Avance del Rango Evaluado frente a su propia Meta"

    total_facturado_rango = consumo_agrupado['valor_cargo'].sum()
    meta_proporcional_acumulada = meta_comparativa_fila * unidades_con_datos
    cumplimiento_rango = (total_facturado_rango / meta_proporcional_acumulada) if meta_proporcional_acumulada > 0 else 0
    promedio_real_unidad = total_facturado_rango / unidades_con_datos if unidades_con_datos > 0 else 0
    
    monto_faltante_cierre = meta_global_total - total_facturado_rango
    cuota_requerida_cierre = (monto_faltante_cierre / unidades_restantes) if unidades_restantes > 0 else 0
    porcentaje_avance_global = (total_facturado_rango / meta_global_total) if meta_global_total > 0 else 0

    # 4. TABLA DINÁMICA DE FACTURACIÓN
    st.header(f"📋 TABLA DE FACTURACIÓN ({lbl_unidad.upper()})")
    st.markdown(f"**Meta Base Promedio por {lbl_unidad_sing} de acuerdo a la Meta Planteada:** {formato_cop(meta_comparativa_fila)}")

    tabla_base = pd.DataFrame()
    tabla_base['Fecha'] = consumo_agrupado['fecha_label']
    tabla_base['Suma de valor_cargo_num'] = consumo_agrupado['valor_cargo']
    tabla_base['_vr_num'] = consumo_agrupado['valor_cargo'] - meta_comparativa_fila
    tabla_base['%_num'] = consumo_agrupado['valor_cargo'] / meta_comparativa_fila

    tabla_mostrar = pd.DataFrame()
    tabla_mostrar['Fecha'] = tabla_base['Fecha']
    tabla_mostrar[lbl_facturacion] = tabla_base['Suma de valor_cargo_num'].apply(formato_cop)
    tabla_mostrar[lbl_diferencia] = tabla_base['_vr_num'].apply(formato_cop)
    tabla_mostrar[lbl_cumplimiento] = tabla_base['%_num'].apply(formato_porcentaje)
    tabla_mostrar['_vr_num'] = tabla_base['_vr_num']

    total_vr_esperado = total_facturado_rango - (meta_comparativa_fila * unidades_con_datos)
    fila_total = pd.DataFrame([{
        'Fecha': 'Total general',
        lbl_facturacion: formato_cop(total_facturado_rango),
        lbl_diferencia: formato_cop(total_vr_esperado),
        lbl_cumplimiento: formato_porcentaje(total_facturado_rango / meta_proporcional_acumulada) if meta_proporcional_acumulada > 0 else "0%",
        '_vr_num': total_vr_esperado
    }])

    tabla_final = pd.concat([tabla_mostrar, fila_total], ignore_index=True)
    tabla_estilizada = tabla_final.style.apply(color_filas_vr, axis=1)

    altura_tabla = (len(tabla_final) * 35) + 38

    st.dataframe(
        tabla_estilizada,
        use_container_width=True,
        hide_index=True,
        height=altura_tabla,
        column_order=("Fecha", lbl_facturacion, lbl_diferencia, lbl_cumplimiento)
    )

    # 5. CUADRO DE CONTROL Y CIERRE DE METAS 
    st.divider()
    st.markdown("<h2 style='text-align: center; color: #2c3e50;'>CUADRO DE CONTROL Y CIERRE DE METAS</h2>", unsafe_allow_html=True)
    st.write("") 

    c_izq, c_der = st.columns(2)
    tit_izq = lbl_rango_tit.replace("📊 ", "")
    tit_der = lbl_cierre_tit.replace("🎯 ", "")

    with c_izq:
        st.markdown(f"<h4 style='color: #34495e; border-bottom: 2px solid #bdc3c7; padding-bottom: 5px;'>{tit_izq}</h4>", unsafe_allow_html=True)
        st.markdown(f"**{lbl_txt_unidades}:** {unidades_con_datos} {lbl_unidad.lower()}")
        st.markdown(f"<p style='margin-bottom: 0px; margin-top: 0px;'><b>{lbl_txt_total}:</b></p>", unsafe_allow_html=True)
        st.markdown(f"<h3 style='color: #2980b9; margin-top: 0px;'>{formato_cop(total_facturado_rango)}</h3>", unsafe_allow_html=True)
        st.markdown(f"**{lbl_txt_esperado}:** {formato_cop(meta_proporcional_acumulada)}")
        color_cumplimiento = "#27ae60" if cumplimiento_rango >= 1 else "#c0392b"
        st.markdown(f"**Eficiencia / Cumplimiento:** <span style='color:{color_cumplimiento}; font-weight:bold; font-size:18px;'>{formato_porcentaje(cumplimiento_rango)}</span>", unsafe_allow_html=True)
        st.markdown("<hr style='margin: 15px 0px; border-top: 1px solid #e0e0e0;'>", unsafe_allow_html=True)
        
        diferencia_promedio = promedio_real_unidad - meta_comparativa_fila
        color_dif = "#27ae60" if diferencia_promedio >= 0 else "#c0392b"
        signo_dif = "+" if diferencia_promedio >= 0 else ""
        texto_dif = "Superávit" if diferencia_promedio >= 0 else "Déficit"
        
        st.markdown(f"**Promedio Facturado por {lbl_unidad_sing}:** {formato_cop(promedio_real_unidad)}")
        st.markdown(f"**Meta Base Esperada por {lbl_unidad_sing}:** {formato_cop(meta_comparativa_fila)}")
        
        st.markdown(
            f"<div style='background-color: #f8f9fa; padding: 10px; border-left: 4px solid {color_dif}; border-radius: 4px; margin-top: 8px;'>"
            f"<span style='font-size: 14px; color: #555;'>{texto_dif} promedio por {lbl_unidad_sing.lower()}: </span>"
            f"<strong style='color: {color_dif}; font-size: 15px;'>{signo_dif}{formato_cop(diferencia_promedio)}</strong>"
            f"</div>", 
            unsafe_allow_html=True
        )

    with c_der:
        st.markdown(f"<h4 style='color: #34495e; border-bottom: 2px solid #bdc3c7; padding-bottom: 5px;'>{tit_der}</h4>", unsafe_allow_html=True)
        st.markdown(f"<p style='margin-bottom: 2px; margin-top: 10px;'><b>{lbl_txt_meta_global}:</b></p>", unsafe_allow_html=True)
        st.markdown(f"<h4 style='color: #2c3e50; margin-top: 0px;'>{formato_cop(meta_global_total)}</h4>", unsafe_allow_html=True)
        
        if monto_faltante_cierre > 0:
            st.markdown(f"**{lbl_txt_faltante}:** <span style='color: #c0392b; font-weight: bold; font-size:16px;'>{formato_cop(monto_faltante_cierre)}</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"**Superávit (Meta Superada):** <span style='color: #27ae60; font-weight: bold; font-size:16px;'>+{formato_cop(abs(monto_faltante_cierre))}</span>", unsafe_allow_html=True)
            
        st.markdown(f"**{lbl_txt_restantes}:** {unidades_restantes} {lbl_unidad.lower()}")
        st.markdown("<hr style='margin: 15px 0px; border-top: 1px solid #e0e0e0;'>", unsafe_allow_html=True)
        
        st.markdown(f"<p style='margin-bottom: 2px;'><b>{lbl_req}:</b></p>", unsafe_allow_html=True)
        
        if monto_faltante_cierre <= 0:
            st.markdown(f"<h3 style='color: #27ae60; margin-top: 0px;'>¡Objetivo Logrado!</h3>", unsafe_allow_html=True)
            st.caption("La meta total establecida para este período fue alcanzada o superada con éxito.")
        elif unidades_restantes > 0:
            st.markdown(f"<h3 style='color: #d35400; margin-top: 0px;'>{formato_cop(cuota_requerida_cierre)}</h3>", unsafe_allow_html=True)
            st.caption(lbl_caption_req)
        else:
            st.markdown(f"<h3 style='color: #c0392b; margin-top: 0px;'>Meta No Alcanzada</h3>", unsafe_allow_html=True)
            st.caption("El tiempo de este rango ya finalizó por completo y no se logró cubrir el objetivo financiero.")
            
        st.markdown("<hr style='margin: 10px 0px; border: none;'>", unsafe_allow_html=True)
        st.markdown(f"**{lbl_txt_avance}:** <span style='font-weight: bold; font-size:15px;'>{formato_porcentaje(porcentaje_avance_global)}</span> completado.", unsafe_allow_html=True)

    # 6. GRÁFICO DE RENDIMIENTO
    st.divider()
    st.header("📊 CONTROL GRÁFICO DE CONSUMO")

    fig_comparativa = go.Figure()
    fig_comparativa.add_trace(go.Bar(
        x=consumo_agrupado['fecha_plot'], y=consumo_agrupado['valor_cargo'],
        name='Facturado Real', marker_color='#1f77b4'
    ))
    fig_comparativa.add_trace(go.Scatter(
        x=consumo_agrupado['fecha_plot'], y=[meta_comparativa_fila] * len(consumo_agrupado),
        name=f"Meta Base por {lbl_unidad_sing} ({formato_cop(meta_comparativa_fila)})",
        mode='lines', line=dict(color='#d62728', dash='dash', width=2),
    ))
    fig_comparativa.update_layout(
        title=f'Rendimiento de Facturación vs Meta Asignada — {etiqueta_periodo}',
        xaxis_title=lbl_unidad, yaxis_title='COP ($)',
        hovermode='x unified', height=450
    )
    st.plotly_chart(fig_comparativa, use_container_width=True)

    # ==========================================
    # BOTÓN DE EXPORTACIÓN A PDF
    # ==========================================
    st.divider()
    col_vacia1, col_boton, col_vacia2 = st.columns([1, 2, 1])
    
    with col_boton:
        pdf_bytes = generar_pdf_fidedigno(
            tabla_final, 
            fig_comparativa, 
            etiqueta_periodo, 
            formato_cop(total_facturado_rango),
            formato_cop(meta_proporcional_acumulada),
            cumplimiento_rango,
            formato_cop(meta_global_total),
            monto_faltante_cierre,
            porcentaje_avance_global,
            cuota_requerida_cierre,
            formato_cop(promedio_real_unidad),
            formato_cop(meta_comparativa_fila)
        )
        
        st.download_button(
            label="📄 Exportar Informe a PDF",
            data=pdf_bytes,
            file_name=f"Informe_General_Consumo_{df['fecha_cargo'].min().strftime('%Y-%m-%d')}_al_{df['fecha_cargo'].max().strftime('%Y-%m-%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary"
        )