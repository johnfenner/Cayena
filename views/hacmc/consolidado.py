import streamlit as st
import pandas as pd
from datetime import date, timedelta
from .utils import formato_cop, generar_pdf_consolidado
# Asegúrate de importar lo necesario para la gráfica si la vas a generar aquí

def mostrar_consolidado():
    st.markdown("<h2 style='text-align: center;'>🗂️ CONSOLIDADO GENERAL MAESTRO</h2>", unsafe_allow_html=True)
    
    # Cálculos fijos de fechas
    hoy = date.today()
    ayer = hoy - timedelta(days=1)
    primer_dia_mes = ayer.replace(day=1)
    
    fecha_inicio = primer_dia_mes.strftime("%Y-%m-%d")
    fecha_fin = ayer.strftime("%Y-%m-%d")
    etiqueta_periodo = f"{primer_dia_mes.strftime('%d/%m/%Y')} al {ayer.strftime('%d/%m/%Y')}"
    
    st.info(f"📅 **Generando corte automático al día vencido:** {etiqueta_periodo}")

    # Consulta a BD aislada (Se ejecuta al entrar a la pestaña)
    try:
        conn = st.connection("postgresql", type="sql")
        
        filtros = """AND (cd.facturado = '1' OR cd.facturado IS NULL OR TRIM(cd.facturado) = '')
                     AND (c.estado IN ('0', '1', '2', '3') OR c.estado IS NULL)"""

        with st.spinner("Compilando reporte gerencial maestro..."):
            
            # ==========================================================
            # 1. CÁLCULOS DEL CUADRO DE CONTROL Y CIERRE DE METAS
            # ==========================================================
            import calendar
            dias_mes_total = calendar.monthrange(ayer.year, ayer.month)[1]
            dias_transcurridos = ayer.day
            dias_restantes = dias_mes_total - dias_transcurridos
            
            meta_global_num = 31700000000  # Ejemplo basado en tu PDF: 31,700 Millones
            meta_dia_base_num = meta_global_num / dias_mes_total
            meta_acumulada_num = meta_dia_base_num * dias_transcurridos 

            df_gen = conn.query(f"SELECT SUM(cd.valor_cargo) as total FROM cuentas_detalle cd INNER JOIN cuentas c ON c.numerodecuenta = cd.numerodecuenta WHERE cd.fecha_cargo::DATE BETWEEN '{fecha_inicio}' AND '{fecha_fin}' {filtros}")
            total_facturado_num = float(df_gen['total'].iloc[0]) if not df_gen.empty and pd.notna(df_gen['total'].iloc[0]) else 0.0

            faltante_num = meta_global_num - total_facturado_num
            promedio_dia_real_num = total_facturado_num / dias_transcurridos if dias_transcurridos > 0 else 0
            deficit_num = promedio_dia_real_num - meta_dia_base_num
            meta_diaria_restante_num = faltante_num / dias_restantes if dias_restantes > 0 else 0
            
            eficiencia_pct = (total_facturado_num / meta_acumulada_num * 100) if meta_acumulada_num > 0 else 0
            avance_pct = (total_facturado_num / meta_global_num * 100) if meta_global_num > 0 else 0

            # Diccionario con las métricas formateadas para pasarlas a utils.py
            metricas_cuadro = {
                "dias_transcurridos": f"{dias_transcurridos} días",
                "total_facturado": formato_cop(total_facturado_num),
                "meta_acumulada": formato_cop(meta_acumulada_num),
                "eficiencia": f"{eficiencia_pct:.1f}%",
                "promedio_dia_real": formato_cop(promedio_dia_real_num),
                "meta_dia_base": formato_cop(meta_dia_base_num),
                "deficit": formato_cop(deficit_num), # Si es positivo es Superávit
                "meta_global": formato_cop(meta_global_num),
                "faltante": formato_cop(faltante_num),
                "dias_restantes": f"{dias_restantes} días",
                "meta_diaria_restante": formato_cop(meta_diaria_restante_num),
                "avance": f"{avance_pct:.1f}% completado"
            }

            # ==========================================================
            # 2. CONSULTAS SQL (Top 20 para ver más datos como en tu PDF)
            # ==========================================================
            query_ent = f"""
                SELECT COALESCE(t.nombre_tercero, 'OTRAS ENTIDADES') AS nombre, 
                       SUM(cd.valor_cargo) AS total,
                       SUM(cd.valor_cargo) / {dias_transcurridos} AS promedio_diario
                FROM cuentas_detalle cd 
                INNER JOIN cuentas c ON c.numerodecuenta = cd.numerodecuenta 
                INNER JOIN planes pl ON pl.plan_id = c.plan_id
                INNER JOIN terceros t ON (pl.tipo_tercero_id = t.tipo_id_tercero AND pl.tercero_id = t.tercero_id)
                WHERE cd.fecha_cargo::DATE BETWEEN '{fecha_inicio}' AND '{fecha_fin}' {filtros}
                GROUP BY t.nombre_tercero ORDER BY total DESC LIMIT 20
            """
            df_ent = conn.query(query_ent)
            
            query_und = f"""
                SELECT COALESCE(uf.descripcion, 'SIN UNIDAD ASIGNADA') AS nombre, 
                       SUM(cd.cantidad) AS cantidad,
                       SUM(cd.valor_cargo) AS total,
                       SUM(cd.valor_cargo) / {dias_transcurridos} AS promedio_diario
                FROM cuentas_detalle cd 
                INNER JOIN cuentas c ON c.numerodecuenta = cd.numerodecuenta 
                INNER JOIN departamentos de ON de.departamento = cd.departamento_al_cargar
                INNER JOIN unidades_funcionales uf ON uf.unidad_funcional = de.unidad_funcional
                WHERE cd.fecha_cargo::DATE BETWEEN '{fecha_inicio}' AND '{fecha_fin}' {filtros}
                GROUP BY uf.descripcion ORDER BY total DESC LIMIT 15
            """
            df_und = conn.query(query_und)
            
            # Mercadeo incluye el conteo de días distintos donde hubo cargos
            query_merc = f"""
                SELECT COALESCE(igi.descripcion, '(en blanco)') AS nombre, 
                       COUNT(DISTINCT cd.fecha_cargo::DATE) AS dias_activos,
                       SUM(cd.valor_cargo) AS total,
                       SUM(cd.valor_cargo) / {dias_transcurridos} AS promedio_diario
                FROM cuentas_detalle cd 
                INNER JOIN cuentas c ON c.numerodecuenta = cd.numerodecuenta 
                INNER JOIN bodegas_documentos_d bdd ON cd.consecutivo = bdd.consecutivo 
                INNER JOIN inventarios_productos inp ON inp.codigo_producto = bdd.codigo_producto 
                LEFT JOIN inv_grupos_inventarios igi ON igi.grupo_id = inp.grupo_id 
                WHERE cd.fecha_cargo::DATE BETWEEN '{fecha_inicio}' AND '{fecha_fin}' 
                AND cd.cargo IN ('IMD','DIMD') {filtros} 
                GROUP BY igi.descripcion ORDER BY total DESC LIMIT 15
            """
            df_merc = conn.query(query_merc)

            figura_grafico = st.session_state.get('figura_informe_general', None)

            # ==========================================================
            # 3. GENERACIÓN DEL PDF
            # ==========================================================
            pdf_bytes = generar_pdf_consolidado(
                etiqueta_periodo, metricas_cuadro, figura_grafico, df_ent, df_und, df_merc
            )

        st.download_button(
            label="⬇️ Descargar PDF Consolidado Maestro",
            data=pdf_bytes,
            file_name=f"Consolidado_Maestro_{fecha_fin}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary"
        )
        
    except Exception as e:
        st.error(f"Error al generar el consolidado maestro: {e}")