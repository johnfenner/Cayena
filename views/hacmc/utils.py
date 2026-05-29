import pandas as pd
from fpdf import FPDF
import os
import json
import streamlit as st
import tempfile
from datetime import date, timedelta

# Archivo local para persistencia de la meta del Hospital de la Dorada
ARCHIVO_META_DORADA = "config_meta_dorada.json"
META_INICIAL_DORADA = 31700000000  

# ==========================================
# 0. PERSISTENCIA DE CONFIGURACIÓN GLOBAL
# ==========================================

def obtener_meta_guardada_dorada():
    """Lee la meta del archivo JSON de la Dorada. Si no existe, lo crea con el valor inicial."""
    if not os.path.exists(ARCHIVO_META_DORADA):
        guardar_nueva_meta_dorada(META_INICIAL_DORADA)
        return META_INICIAL_DORADA
    
    try:
        with open(ARCHIVO_META_DORADA, 'r') as file:
            datos = json.load(file)
            return datos.get("meta_mensual", META_INICIAL_DORADA)
    except Exception:
        return META_INICIAL_DORADA

def guardar_nueva_meta_dorada(nueva_meta):
    """Sobreescribe el archivo JSON con el nuevo valor de la meta de la Dorada."""
    try:
        with open(ARCHIVO_META_DORADA, 'w') as file:
            json.dump({"meta_mensual": nueva_meta}, file)
    except Exception as e:
        st.error(f"Error al guardar la meta de La Dorada: {e}")


def generar_pdf_fidedigno(tabla, fig, periodo, total_rango, meta_acumulada, cumplimiento, 
                          meta_global, faltante, avance, cuota_req, promedio_diario, meta_diaria):
    
    periodo_seguro = periodo.replace("→", " al ")
    
    pdf = FPDF()
    pdf.add_page()
    
    # --- LOGO EN EL ENCABEZADO ---
    ruta_logo = "assets/images/logo_hacmc_magdalena_centro.png"
    if os.path.exists(ruta_logo):
        pdf.image(ruta_logo, x=10, y=8, w=60)
    
    # Título limpio debajo del logo
    pdf.set_y(23)
    
    # --- COLORES BASE ---
    COLOR_TITULO = (44, 62, 80)      
    COLOR_VERDE = (39, 174, 96)      
    COLOR_ROJO = (192, 57, 43)       
    COLOR_TEXTO = (50, 50, 50)       
    COLOR_GRIS = (189, 195, 199)     
    
    fecha_corte = (date.today() - timedelta(days=1)).strftime('%d-%m-%Y')
    
    # --- 1. ENCABEZADO ---
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(*COLOR_TITULO)
    pdf.cell(0, 10, "HOSPITAL DE ALTA COMPLEJIDAD DEL MAGDALENA CENTRO", ln=True, align="C")
    pdf.cell(0, 10, "INFORME GENERAL - CONSUMO DIARIO", ln=True, align="C")
    
    pdf.set_font("Arial", "", 11)
    pdf.set_text_color(*COLOR_TEXTO)
    pdf.cell(0, 6, f"Periodo de Analisis: {periodo_seguro} |  corte: {fecha_corte}", ln=True, align="C")
    pdf.ln(5)
    
    # --- 2. CUADRO DE CONTROL ---
    pdf.set_font("Arial", "B", 12)
    pdf.set_fill_color(245, 245, 245)
    pdf.cell(0, 8, "  CUADRO DE CONTROL Y CIERRE DE METAS", border=0, ln=True, fill=True)
    pdf.ln(3)
    
    y_inicial = pdf.get_y()
    
    # -- COLUMNA IZQUIERDA --
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(*COLOR_TITULO)
    pdf.cell(90, 6, "RENDIMIENTO ACUMULADO", ln=True)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*COLOR_TEXTO)
    pdf.cell(90, 5, "Total Facturado:", ln=True)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(90, 6, total_rango, ln=True)
    pdf.set_font("Arial", "", 9)
    pdf.cell(90, 5, f"Meta Ideal Acumulada: {meta_acumulada}", ln=True)
    
    if cumplimiento >= 1:
        pdf.set_text_color(*COLOR_VERDE)
    else:
        pdf.set_text_color(*COLOR_ROJO)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(90, 6, f"Eficiencia / Cumplimiento: {formato_porcentaje(cumplimiento)}", ln=True)
    
    # Promedio diario en columna izquierda
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*COLOR_TEXTO)
    pdf.cell(90, 5, f"Promedio Facturado por Día: {promedio_diario}", ln=True)
    
    y_final_izq = pdf.get_y()
    
    # -- COLUMNA DERECHA --
    pdf.set_xy(105, y_inicial)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(*COLOR_TITULO)
    pdf.cell(90, 6, "PROYECCION DE CIERRE", ln=True)
    
    pdf.set_xy(105, pdf.get_y())
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*COLOR_TEXTO)
    pdf.cell(90, 5, "Meta Total del Periodo:", ln=True)
    
    pdf.set_xy(105, pdf.get_y())
    pdf.set_font("Arial", "B", 12)
    pdf.cell(90, 6, meta_global, ln=True)
    
    pdf.set_xy(105, pdf.get_y())
    pdf.set_font("Arial", "", 9)
    if faltante > 0:
        pdf.set_text_color(*COLOR_ROJO)
        texto_faltante = f"Falta por facturar: {formato_cop(faltante)}"
    else:
        pdf.set_text_color(*COLOR_VERDE)
        texto_faltante = f"Superavit: +{formato_cop(abs(faltante))}"
    pdf.cell(90, 5, texto_faltante, ln=True)

    pdf.set_xy(105, pdf.get_y())
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(*COLOR_TITULO)
    pdf.cell(90, 6, f"Avance Total: {formato_porcentaje(avance)}", ln=True)
    
    # Meta diaria en columna derecha
    pdf.set_xy(105, pdf.get_y())
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*COLOR_TEXTO)
    pdf.cell(90, 5, f"Meta Base Esperada por Día: {meta_diaria}", ln=True)
    
    y_final_der = pdf.get_y()
    pdf.set_y(max(y_final_izq, y_final_der) + 8) 
    
    # --- 3. GRÁFICO DE RENDIMIENTO ---
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
        fig.write_image(tmpfile.name, engine="kaleido", width=900, height=350, scale=2)
        pdf.image(tmpfile.name, x=10, w=190) 
        tmp_path = tmpfile.name
    os.remove(tmp_path) 
    pdf.ln(5)
    
    # --- 4. TABLA DE DATOS ---
    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(52, 73, 94) 
    pdf.set_text_color(255, 255, 255) 
    
    anchos = [30, 55, 55, 45] 
    cols = tabla.columns[:4]
    
    for i in range(4):
        pdf.cell(anchos[i], 8, str(cols[i]), border=1, fill=True, align="C")
    pdf.ln()
    
    for _, fila in tabla.iterrows():
        fill = False
        pdf.set_text_color(0, 0, 0)
        
        # LOGICA ACTUALIZADA PARA EL COLOR DEL TOTAL GENERAL
        if fila[cols[0]] == "Total general":
            pdf.set_font("Arial", "B", 9)
            val_diferencia = str(fila[cols[2]])
            
            # Si hay déficit  -> Rojo
            if "-" in val_diferencia:
                pdf.set_fill_color(248, 215, 218) # Fondo rojo claro
                pdf.set_text_color(114, 28, 36)   # Texto rojo oscuro
            # Si hay superávit (alcanzó o superó meta) -> Verde
            else:
                pdf.set_fill_color(212, 237, 218) # Fondo verde claro
                pdf.set_text_color(21, 87, 36)    # Texto verde oscuro
            fill = True
        else:
            pdf.set_font("Arial", "", 9)
            val_diferencia = str(fila[cols[2]])
            if "-" in val_diferencia:
                pdf.set_text_color(192, 57, 43)
            else:
                pdf.set_text_color(39, 174, 96)
                
        pdf.cell(anchos[0], 7, str(fila[cols[0]]), border=1, align="C", fill=fill)
        pdf.set_text_color(0,0,0) if not fill else None 
        pdf.cell(anchos[1], 7, str(fila[cols[1]]), border=1, align="R", fill=fill)
        
        if not fill:
            if "-" in str(fila[cols[2]]): pdf.set_text_color(192, 57, 43)
            else: pdf.set_text_color(39, 174, 96)
        pdf.cell(anchos[2], 7, str(fila[cols[2]]), border=1, align="R", fill=fill)
        
        pdf.set_text_color(0,0,0) if not fill else None
        pdf.cell(anchos[3], 7, str(fila[cols[3]]), border=1, align="C", fill=fill)
        pdf.ln()
        
    return pdf.output(dest="S").encode("latin-1")


def generar_pdf_entidades(df_final, df_dashboard, etiqueta_periodo, total_general, total_entidades, entidad_top, valor_top, participacion_top):
    pdf = FPDF()
    pdf.add_page()
    
    # --- LOGO EN EL ENCABEZADO ---
    ruta_logo = "assets/images/logo_hacmc_magdalena_centro.png"
    if os.path.exists(ruta_logo):
        pdf.image(ruta_logo, x=10, y=8, w=60)
        
    # Bajamos el cursor Y para que los títulos inicien limpios debajo del logo
    pdf.set_y(23)
    
    # 1. Calculo de la fecha de corte
    fecha_corte = (date.today() - timedelta(days=1)).strftime('%d-%m-%Y')

    # Configuración de página y título principal
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(0, 10, "HOSPITAL DE ALTA COMPLEJIDAD DEL MAGDALENA CENTRO", ln=True, align="C")
    pdf.cell(0, 10, "REPORTE DE FACTURACIÓN POR ENTIDADES", ln=True, align="C")
    pdf.set_font("helvetica", style="I", size=10)
    
    etiqueta_segura = etiqueta_periodo.replace("→", " al ")
    pdf.cell(0, 6, f"Período de Análisis: {etiqueta_segura} |  corte: {fecha_corte}", ln=True, align="C")
    pdf.ln(6)
    
    # Sección 1: Bloques de Resumen
    pdf.set_font("helvetica", style="B", size=11)
    pdf.set_fill_color(230, 240, 250)
    pdf.cell(0, 7, "  RESUMEN EJECUTIVO DEL PERÍODO", ln=True, fill=True)
    pdf.ln(2)
    
    pdf.set_font("helvetica", size=10)
    pdf.cell(95, 6, f"Total Facturado General: {total_general}", ln=True)
    pdf.cell(95, 6, f"Total de Entidades Atendidas: {total_entidades}", ln=True)
    pdf.cell(95, 6, f"Entidad Principal: {entidad_top.encode('latin-1', 'replace').decode('latin-1')}", ln=True)
    pdf.cell(95, 6, f"Facturación Entidad Top: {valor_top} ({participacion_top} del total)", ln=True)
    pdf.ln(6)
    
    # Sección 2: Tabla de Síntesis Estratégica
    pdf.set_font("helvetica", style="B", size=11)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 7, "  SÍNTESIS DE ENTIDADES", ln=True, fill=True)
    pdf.ln(2)
    
    # Encabezados de tabla
    pdf.set_font("helvetica", style="B", size=9)
    pdf.cell(95, 7, "Entidad", border=1, align="C")
    pdf.cell(45, 7, "Total Facturado", border=1, align="C")
    pdf.cell(45, 7, "Promedio Diario", border=1, ln=True, align="C")
    
    # Filas de datos
    pdf.set_font("helvetica", size=9)
    
    for _, row in df_dashboard.iterrows():
        # Limpiamos textos y forzamos a string los valores numéricos
        nombre = str(row['entidad'])[:48].encode('latin-1', 'replace').decode('latin-1')
        total_f = str(formato_cop(row['Total_Facturado']))
        promedio_d = str(formato_cop(row['Promedio_Diario']))
        
        pdf.cell(95, 6, f" {nombre}", border=1)
        pdf.cell(45, 6, total_f, border=1, align="R")
        pdf.cell(45, 6, promedio_d, border=1, ln=True, align="R")
        
    # Retorno limpio de bytes 
    return pdf.output(dest="S").encode("latin-1")


def generar_pdf_unidades_funcionales(df_dashboard, etiqueta_periodo, total_general, total_cantidad, uf_top, valor_top, participacion_top):
    pdf = FPDF()
    pdf.add_page()

    # --- LOGO EN EL ENCABEZADO ---
    ruta_logo = "assets/images/logo_hacmc_magdalena_centro.png"
    if os.path.exists(ruta_logo):
        pdf.image(ruta_logo, x=10, y=8, w=60)
        
    # Bajamos el cursor Y para que los títulos inicien limpios debajo del logo
    pdf.set_y(23)

    # 1. Calculo de la fecha de corte
    fecha_corte = (date.today() - timedelta(days=1)).strftime('%d-%m-%Y')
    
    # Configuración de página y título principal
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(0, 10, "HOSPITAL DE ALTA COMPLEJIDAD DEL MAGDALENA CENTRO", ln=True, align="C")
    pdf.cell(0, 10, "REPORTE DE FACTURACIÓN POR UNIDADES FUNCIONALES", ln=True, align="C")
    pdf.set_font("helvetica", style="I", size=10)
    
    etiqueta_segura = etiqueta_periodo.replace("→", " al ")
    pdf.cell(0, 6, f"Período de Análisis: {etiqueta_segura} |  corte: {fecha_corte}", ln=True, align="C")
    pdf.ln(6)
    
    # Sección 1: Bloques de Resumen Operativo
    pdf.set_font("helvetica", style="B", size=11)
    pdf.set_fill_color(230, 240, 250)
    pdf.cell(0, 7, "  RESUMEN OPERATIVO DEL PERÍODO", ln=True, fill=True)
    pdf.ln(2)
    
    pdf.set_font("helvetica", size=10)
    pdf.cell(95, 6, f"Total Facturado General: {total_general}", ln=True)
    pdf.cell(95, 6, f"Cantidad Total de Servicios: {total_cantidad}", ln=True)
    # Limpieza de caracteres para evitar errores en FPDF
    uf_top_clean = uf_top.encode('latin-1', 'replace').decode('latin-1')
    pdf.cell(95, 6, f"Unidad Estratégica Top: {uf_top_clean}", ln=True)
    pdf.cell(95, 6, f"Facturación Unidad Top: {valor_top} ({participacion_top} del total)", ln=True)
    pdf.ln(6)
    
    # Sección 2: Tabla de Síntesis Estratégica
    pdf.set_font("helvetica", style="B", size=11)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 7, "  SÍNTESIS ESTRATÉGICA POR UNIDAD", ln=True, fill=True)
    pdf.ln(2)
    
    # Encabezados de tabla
    pdf.set_font("helvetica", style="B", size=9)
    pdf.cell(85, 7, "Unidad Funcional", border=1, align="C")
    pdf.cell(25, 7, "Cantidad", border=1, align="C")
    pdf.cell(40, 7, "Total Facturado", border=1, align="C")
    pdf.cell(40, 7, "Promedio Diario", border=1, ln=True, align="C")
    
    # Filas de datos
    pdf.set_font("helvetica", size=9)
    
    for _, row in df_dashboard.iterrows():
        # Limpiamos textos y forzamos a string los valores numéricos
        nombre = str(row['unidad_funcional'])[:45].encode('latin-1', 'replace').decode('latin-1')
        cantidad = f"{int(row['Total_Cantidad']):,}"
        total_f = str(formato_cop(row['Total_Facturado']))
        promedio_d = str(formato_cop(row['Promedio_Diario_Valor']))
        
        pdf.cell(85, 6, f" {nombre}", border=1)
        pdf.cell(25, 6, cantidad, border=1, align="C")
        pdf.cell(40, 6, total_f, border=1, align="R")
        pdf.cell(40, 6, promedio_d, border=1, ln=True, align="R")
        
    # Retorno limpio de bytes
    return pdf.output(dest="S").encode("latin-1")    


def generar_pdf_mercadeo(df_dashboard, etiqueta_periodo, total_general, total_categorias, categoria_top, valor_top, participacion_top):
    pdf = FPDF()
    pdf.add_page()

    # --- LOGO EN EL ENCABEZADO ---
    ruta_logo = "assets/images/logo_hacmc_magdalena_centro.png"
    if os.path.exists(ruta_logo):
        pdf.image(ruta_logo, x=10, y=8, w=60)
        
    # Bajamos el cursor Y para que los títulos inicien limpios debajo del logo
    pdf.set_y(23)

    # 1. Calculo de la fecha de corte
    fecha_corte = (date.today() - timedelta(days=1)).strftime('%d-%m-%Y')
    
    # Configuración de página y título principal
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(0, 10, "HOSPITAL DE ALTA COMPLEJIDAD DEL MAGDALENA CENTRO", ln=True, align="C")
    pdf.cell(0, 10, "REPORTE DE FACTURACIÓN POR LÍNEA DE MERCADEO", ln=True, align="C")
    pdf.set_font("helvetica", style="I", size=10)
    pdf.cell(0, 6, f"Período de Análisis: {etiqueta_periodo} |  corte: {fecha_corte}", ln=True, align="C")
    pdf.ln(6)
    
    # Sección 1: Bloques de Resumen Operativo
    pdf.set_font("helvetica", style="B", size=11)
    pdf.set_fill_color(230, 240, 250)
    pdf.cell(0, 7, "  RESUMEN DE MERCADEO", ln=True, fill=True)
    pdf.ln(2)
    
    pdf.set_font("helvetica", size=10)
    pdf.cell(95, 6, f"Total Facturado General: {total_general}", ln=True)
    pdf.cell(95, 6, f"Líneas de Negocio Activas: {total_categorias}", ln=True)
    # Limpieza de caracteres para evitar errores en FPDF
    categoria_top_clean = categoria_top.encode('latin-1', 'replace').decode('latin-1')
    pdf.cell(95, 6, f"Línea de Mayor Impacto: {categoria_top_clean}", ln=True)
    pdf.cell(95, 6, f"Facturación Línea Top: {valor_top} ({participacion_top} del total)", ln=True)
    pdf.ln(6)
    
    # Sección 2: Tabla de Síntesis Estratégica
    pdf.set_font("helvetica", style="B", size=11)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 7, "  SÍNTESIS POR LÍNEA DE PRODUCTO/SERVICIO", ln=True, fill=True)
    pdf.ln(2)
    
    # Encabezados de tabla
    pdf.set_font("helvetica", style="B", size=9)
    pdf.cell(85, 7, "Línea de Mercadeo", border=1, align="C")
    pdf.cell(25, 7, "Días Activos", border=1, align="C")
    pdf.cell(40, 7, "Total Facturado", border=1, align="C")
    pdf.cell(40, 7, "Promedio Diario", border=1, ln=True, align="C")
    
    # Filas de datos
    pdf.set_font("helvetica", size=9)
    
    for _, row in df_dashboard.iterrows():
        nombre = str(row['linea_mercadeo'])[:45].encode('latin-1', 'replace').decode('latin-1')
        dias = str(row['Dias_Activos'])
        total_f = str(formato_cop(row['Total_Facturado']))
        promedio_d = str(formato_cop(row['Promedio_Diario']))
        
        pdf.cell(85, 6, f" {nombre}", border=1)
        pdf.cell(25, 6, dias, border=1, align="C")
        pdf.cell(40, 6, total_f, border=1, align="R")
        pdf.cell(40, 6, promedio_d, border=1, ln=True, align="R")
        
    return pdf.output(dest="S").encode("latin-1")


def formato_cop(numero):
    if pd.isna(numero):
        return "$ 0"
    abs_val = abs(numero)
    formatted = f"{abs_val:,.0f}".replace(",", ".")
    return f"$ {formatted}" if numero >= 0 else f"-$ {formatted}"


def formato_porcentaje(numero):
    if pd.isna(numero):
        return "0%"
    valor_pct = numero * 100
    if numero < 1.0 and valor_pct >= 99.9:
        return "99.9%"
    return f"{valor_pct:.1f}%"


def color_filas_vr(row):
    style = [''] * len(row)
    val_vr = row['_vr_num']
    
    # 1. Validación para la fila de Total general 
    if row['Fecha'] == 'Total general':
        if val_vr < 0:
            style = ['background-color: #f8d7da; font-weight: bold; color: #721c24;'] * len(row)
        else:
            style = ['background-color: #d4edda; font-weight: bold; color: #155724;'] * len(row)
        return style
        
    # 2. Validación para las filas normales
    if val_vr < 0:
        style = ['background-color: #f8d7da; color: #721c24;'] * len(row)
    else:
        style = ['background-color: #d4edda; color: #155724;'] * len(row)
        
    return style