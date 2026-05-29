import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import calendar
import io
import os

from .utils import (
    formato_cop,
    formato_porcentaje,
    obtener_meta_guardada_traumanorte,
)

# --- Query SQL ----------------------------------------------------------------

_FILTROS = """
    AND (cd.facturado = '1' OR cd.facturado IS NULL OR TRIM(cd.facturado) = '')
    AND (cd.sw_paquete_facturado = '1' OR cd.sw_paquete_facturado IS NULL OR TRIM(cd.sw_paquete_facturado) = '')
    AND (c.estado IN ('0','1','2','3') OR c.estado IS NULL)
"""

def _query(f0: str, f1: str) -> str:
    return f"""
    SELECT cd.valor_cargo,
           COALESCE(t.nombre_tercero,'SIN ENTIDAD')         AS entidad_id,
           COALESCE(uf.descripcion,'SIN UNIDAD FUNCIONAL')  AS uf_id,
           COALESCE(igi.descripcion,'MEDICAMENTOS/INSUMOS') AS linea_mercadeo
    FROM cuentas_detalle cd
        INNER JOIN bodegas_documentos_d bdd ON cd.consecutivo=bdd.consecutivo
        INNER JOIN inventarios_productos inp ON inp.codigo_producto=bdd.codigo_producto
        LEFT  JOIN inv_grupos_inventarios igi ON igi.grupo_id=inp.grupo_id
        INNER JOIN cuentas c ON c.numerodecuenta=cd.numerodecuenta
        LEFT  JOIN planes pl ON pl.plan_id=c.plan_id
        LEFT  JOIN terceros t ON pl.tipo_tercero_id=t.tipo_id_tercero AND pl.tercero_id=t.tercero_id
        LEFT  JOIN departamentos de ON de.departamento=cd.departamento_al_cargar
        LEFT  JOIN unidades_funcionales uf ON uf.unidad_funcional=de.unidad_funcional
    WHERE cd.fecha_cargo::DATE BETWEEN '{f0}'::DATE AND '{f1}'::DATE
      AND cd.cargo IN ('IMD','DIMD') {_FILTROS}

    UNION ALL

    SELECT cd.valor_cargo,
           COALESCE(t.nombre_tercero,'SIN ENTIDAD')         AS entidad_id,
           COALESCE(uf.descripcion,'SIN UNIDAD FUNCIONAL')  AS uf_id,
           'PROCEDIMIENTOS/OTROS'                           AS linea_mercadeo
    FROM cuentas_detalle cd
        INNER JOIN tarifarios_detalle td ON cd.cargo=td.cargo AND cd.tarifario_id=td.tarifario_id
        INNER JOIN cuentas c ON c.numerodecuenta=cd.numerodecuenta
        LEFT  JOIN planes pl ON pl.plan_id=c.plan_id
        LEFT  JOIN terceros t ON pl.tipo_tercero_id=t.tipo_id_tercero AND pl.tercero_id=t.tercero_id
        LEFT  JOIN departamentos de ON de.departamento=cd.departamento_al_cargar
        LEFT  JOIN unidades_funcionales uf ON uf.unidad_funcional=de.unidad_funcional
    WHERE cd.fecha_cargo::DATE BETWEEN '{f0}'::DATE AND '{f1}'::DATE
      AND cd.cargo NOT IN ('IMD','DIMD') {_FILTROS}
    """

# --- Utilidades de Datos ------------------------------------------------------

def _top5(df: pd.DataFrame, col: str, excluir: str = None) -> pd.DataFrame:
    tmp = df[df[col] != excluir].copy() if excluir else df.copy()
    out = (
        tmp.groupby(col)["valor_cargo"]
        .sum()
        .nlargest(5)
        .reset_index()
        .rename(columns={col: "Nombre", "valor_cargo": "Facturado"})
    )
    out.index = range(1, len(out) + 1)
    out["Facturado"] = out["Facturado"].apply(formato_cop)
    return out

# --- Exportacion PDF (Adaptado a ReportLab) -----------------------------------

def _generar_pdf(
    etiqueta: str,
    meta_per: float,
    total: float,
    porcentaje_avance_global: float,
    eficiencia_momento: float,
    monto_faltante: float,
    dias_tot: int,
    dias_trans: int,
    dias_rest: int,
    df: pd.DataFrame,
) -> bytes:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image, KeepTogether
    )
    from reportlab.lib.enums import TA_CENTER

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    W, H = landscape(letter)
    styles = getSampleStyleSheet()

    estilo_titulo = ParagraphStyle("Titulo", parent=styles["Title"], fontSize=16, textColor=colors.HexColor("#1e293b"), spaceAfter=4, alignment=TA_CENTER)
    estilo_subtitulo = ParagraphStyle("Subtitulo", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#64748b"), spaceAfter=10, alignment=TA_CENTER)
    estilo_seccion = ParagraphStyle("Seccion", parent=styles["Heading2"], fontSize=11, textColor=colors.HexColor("#1e293b"), spaceBefore=14, spaceAfter=6)
    estilo_celda_label = ParagraphStyle("CeldaLabel", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#6b7280"), alignment=TA_CENTER)
    estilo_celda_valor = ParagraphStyle("CeldaValor", parent=styles["Normal"], fontSize=12, textColor=colors.HexColor("#111827"), alignment=TA_CENTER, fontName="Helvetica-Bold")
    estilo_delta_verde = ParagraphStyle("DeltaVerde", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#10b981"), alignment=TA_CENTER)
    estilo_delta_rojo = ParagraphStyle("DeltaRojo", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#ef4444"), alignment=TA_CENTER)
    estilo_delta_gris = ParagraphStyle("DeltaGris", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#6b7280"), alignment=TA_CENTER)
    estilo_normal = ParagraphStyle("Normal2", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#374151"))

    story = []

    # LOGO 
    ruta_logo = "assets/images/logo_ctm_traumanorte.png"
    if os.path.exists(ruta_logo):
        img = Image(ruta_logo, width=5*cm, height=1.5*cm)
        img.hAlign = 'CENTER'
        story.append(img)
        story.append(Spacer(1, 10))

    # ENCABEZADO
    story.append(Paragraph("CLÍNICA TRAUMANORTE", estilo_titulo))
    story.append(Paragraph(f"Resumen Ejecutivo — {etiqueta}", estilo_subtitulo))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2c3e50")))
    story.append(Spacer(1, 10))

    # SECCION 1: Balance Financiero Global
    story.append(Paragraph("Balance Financiero del Período", estilo_seccion))

    delta_efic_txt  = f"{formato_porcentaje(eficiencia_momento - 1)} vs ideal" if eficiencia_momento != 0 else "0%"
    color_efic      = estilo_delta_verde if eficiencia_momento >= 1 else estilo_delta_rojo
    avance_txt      = f"{formato_porcentaje(porcentaje_avance_global)} de la meta"

    fila1 = [
        [Paragraph("Meta Asignada", estilo_celda_label), Paragraph("Total Facturado", estilo_celda_label), Paragraph("Eficiencia a la Fecha", estilo_celda_label)],
        [Paragraph(formato_cop(meta_per), estilo_celda_valor), Paragraph(formato_cop(total), estilo_celda_valor), Paragraph(formato_porcentaje(eficiencia_momento), estilo_celda_valor)],
        [Paragraph("", estilo_celda_label), Paragraph(avance_txt, estilo_delta_verde if porcentaje_avance_global >= 1 else estilo_delta_rojo), Paragraph(delta_efic_txt, color_efic)],
    ]

    ancho3 = (W - 3.6 * cm) / 3
    t1 = Table(fila1, colWidths=[ancho3] * 3, rowHeights=[16, 22, 14])
    t1.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t1)
    story.append(Spacer(1, 8))

    label_faltante = "Faltante para Meta" if monto_faltante > 0 else "Meta Superada (Superávit)"
    valor_faltante = formato_cop(abs(monto_faltante))

    fila2 = [
        [Paragraph(label_faltante, estilo_celda_label), Paragraph("Total Días del Período", estilo_celda_label), Paragraph("Días Transcurridos", estilo_celda_label)],
        [Paragraph(valor_faltante, estilo_celda_valor), Paragraph(f"{dias_tot} Días", estilo_celda_valor), Paragraph(f"{dias_trans} Días", estilo_celda_valor)],
        [Paragraph("", estilo_celda_label), Paragraph("", estilo_celda_label), Paragraph(f"{dias_rest} días restantes", estilo_delta_gris)],
    ]

    t2 = Table(fila2, colWidths=[ancho3] * 3, rowHeights=[16, 22, 14])
    t2.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t2)
    story.append(Spacer(1, 15))

    # SECCION 2: Diagnóstico Operativo (Top 5)
    story.append(Paragraph("Diagnóstico Operativo (Top 5)", estilo_seccion))

    def _tabla_top5_pdf(df_src: pd.DataFrame, col: str, titulo: str, excluir: str = None):
        tmp = df_src[df_src[col] != excluir].copy() if excluir else df_src.copy()
        top = tmp.groupby(col)["valor_cargo"].sum().nlargest(5).reset_index()
        
        bloque = []
        bloque.append(Paragraph(titulo, ParagraphStyle("SubHead", parent=estilo_normal, fontName="Helvetica-Bold", fontSize=9, spaceBefore=8, spaceAfter=4)))

        filas = [["#", "Nombre", "Facturado"]]
        for i, row in enumerate(top.itertuples(), 1):
            filas.append([str(i), getattr(row, col), formato_cop(row.valor_cargo)])

        tw2 = W - 3.6 * cm
        t = Table(filas, colWidths=[tw2 * 0.06, tw2 * 0.66, tw2 * 0.28])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")), 
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 1), (1, -1), 8),
            ("RIGHTPADDING", (2, 0), (2, -1), 8),
        ]))
        
        bloque.append(t)
        story.append(KeepTogether(bloque))

    _tabla_top5_pdf(df, "entidad_id", "Top 5 de Entidades", excluir="SIN ENTIDAD")
    _tabla_top5_pdf(df, "uf_id", "Top 5 Unidades Funcionales", excluir="SIN UNIDAD FUNCIONAL")
    _tabla_top5_pdf(df, "linea_mercadeo", "Top 5 Líneas de Inventario")

    # PIE DE PÁGINA
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} — CLÍNICA TRAUMANORTE",
        ParagraphStyle("Pie", parent=estilo_normal, fontSize=7, textColor=colors.HexColor("#9ca3af"), alignment=TA_CENTER)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


# --- Funcion principal Vista --------------------------------------------------

def mostrar_resumen_ejecutivo():
    st.markdown("<h2 style='text-align: center;'>🏥 RESUMEN EJECUTIVO</h2>", unsafe_allow_html=True)

    MESES = {
        1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio",
        7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre",
    }
    hoy  = date.today()
    ayer = hoy - timedelta(days=1)

    with st.expander("⚙️ CONTROL DE PERÍODO", expanded=True):
        modo = st.radio(
            "Seleccione el rango de visualizacion:",
            ["Por Mes", "Por Año"],
            index=0, horizontal=True, key="res_ctm_modo",
        )
        anos = [hoy.year, hoy.year - 1, hoy.year - 2]

        if modo == "Por Mes":
            c1, c2 = st.columns(2)
            ano     = c1.selectbox("Año", anos, key="res_ctm_ano_m")
            mes_nom = c2.selectbox("Mes", list(MESES.values()), index=hoy.month - 1, key="res_ctm_mes_m")
            mes     = [k for k, v in MESES.items() if v == mes_nom][0]
            f0      = date(ano, mes, 1).strftime("%Y-%m-%d")
            nd      = calendar.monthrange(ano, mes)[1]
            dias_tot = nd
            if ano == hoy.year and mes == hoy.month and hoy.day > 1:
                f1       = ayer.strftime("%Y-%m-%d")
                etiqueta = f"{mes_nom} de {ano} (Corte: {f1})"
            else:
                f1       = date(ano, mes, nd).strftime("%Y-%m-%d")
                etiqueta = f"{mes_nom} de {ano} (Mes Cerrado)"
        else:
            ano      = st.selectbox("Año", anos, key="res_ctm_ano_a")
            f0       = f"{ano}-01-01"
            dias_tot = 366 if calendar.isleap(ano) else 365
            if ano == hoy.year:
                f1       = ayer.strftime("%Y-%m-%d")
                etiqueta = f"Año {ano} (Corte: {f1})"
            else:
                f1       = f"{ano}-12-31"
                etiqueta = f"Año {ano} (Año Cerrado)"

    d0         = datetime.strptime(f0, "%Y-%m-%d").date()
    d1         = datetime.strptime(f1, "%Y-%m-%d").date()
    dias_trans = max((d1 - d0).days + 1, 1)

    # Conexión local a Traumanorte
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

    with st.spinner("Consolidando analítica..."):
        try:
            df = conn.query(_query(f0, f1), ttl="1m")
        except Exception as e:
            st.error(f"Error en consulta: {e}")
            return

    if df is None or df.empty:
        st.warning(f"No se encontraron registros para el periodo seleccionado ({etiqueta}).")
        return

    df["valor_cargo"] = pd.to_numeric(df["valor_cargo"], errors="coerce").fillna(0)
    for col in ["entidad_id", "uf_id", "linea_mercadeo"]:
        if col not in df.columns:
            df[col] = "NO ESPECIFICADO"

    # Meta de Traumanorte
    factor_meta = 12 if modo == "Por Año" else 1
    meta_per = obtener_meta_guardada_traumanorte() * factor_meta

    total = df["valor_cargo"].sum()
    dias_rest = max(dias_tot - dias_trans, 1)

    meta_diaria_base             = meta_per / dias_tot if dias_tot > 0 else 0
    meta_proporcional_acumulada  = meta_diaria_base * dias_trans
    eficiencia_momento           = (total / meta_proporcional_acumulada) if meta_proporcional_acumulada > 0 else 0
    porcentaje_avance_global     = (total / meta_per) if meta_per > 0 else 0
    monto_faltante               = meta_per - total

    # === SECCION 1: Balance global ===================
    st.divider()
    st.markdown("<h3 style='text-align: center; color: #34495e; margin-bottom: 25px;'> Balance Financiero del Período</h3>", unsafe_allow_html=True)

    r1_c1, r1_c2, r1_c3 = st.columns(3)

    with r1_c1:
        st.metric(label="Meta Asignada", value=formato_cop(meta_per))

    with r1_c2:
        st.metric(
            label="Total Facturado",
            value=formato_cop(total),
            delta=f"{formato_porcentaje(porcentaje_avance_global)} de la meta total"
        )

    with r1_c3:
        delta_eficiencia = f"{formato_porcentaje(eficiencia_momento - 1)} vs ideal" if eficiencia_momento != 0 else "0%"
        st.metric(
            label="Eficiencia a la Fecha",
            value=formato_porcentaje(eficiencia_momento),
            delta=delta_eficiencia,
            delta_color="normal" if eficiencia_momento >= 1 else "inverse"
        )

    st.write("")

    r2_c1, r2_c2, r2_c3 = st.columns(3)

    with r2_c1:
        if monto_faltante > 0:
            st.metric(label="Faltante para Meta", value=formato_cop(monto_faltante))
        else:
            st.metric(label="Meta Superada (Superávit)", value=formato_cop(abs(monto_faltante)))

    with r2_c2:
        st.metric(label="Total Días del Período", value=f"{dias_tot} Días")

    with r2_c3:
        st.metric(
            label="Días Transcurridos",
            value=f"{dias_trans} Días",
            delta=f"{dias_rest} días restantes",
            delta_color="off"
        )

    st.divider()

    # === SECCION 2: Top 5 apilados ============================================
    st.markdown("### 📊 Diagnóstico Operativo")
    
    col_t1, col_t2 = st.columns(2)
    
    with col_t1:
        st.markdown("**Top 5 de Entidades**")
        st.dataframe(_top5(df, "entidad_id", "SIN ENTIDAD"), use_container_width=True, hide_index=True)

    with col_t2:
        st.markdown("**Top 5 Unidades Funcionales**")
        st.dataframe(_top5(df, "uf_id", "SIN UNIDAD FUNCIONAL"), use_container_width=True, hide_index=True)

    st.write("")
    st.markdown("**Top 5 Líneas de Inventario (Mercadeo)**")
    st.dataframe(_top5(df, "linea_mercadeo"), use_container_width=True, hide_index=True)

    st.divider()

    # === SECCION 3: Exportar informe ejecutivo ================================
    nombre_archivo = f"Resumen_Ejecutivo_CTM_{etiqueta.replace(' ', '_').replace('/', '-').replace(':', '')}.pdf"
    
    col_vacia1, col_dl, col_vacia2 = st.columns([1, 2, 1])
    with col_dl:
        pdf_bytes = _generar_pdf(
            etiqueta=etiqueta,
            meta_per=meta_per,
            total=total,
            porcentaje_avance_global=porcentaje_avance_global,
            eficiencia_momento=eficiencia_momento,
            monto_faltante=monto_faltante,
            dias_tot=dias_tot,
            dias_trans=dias_trans,
            dias_rest=dias_rest,
            df=df,
        )
        
        st.download_button(
            label="📄 Exportar Resumen Ejecutivo a PDF",
            data=pdf_bytes,
            file_name=nombre_archivo,
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )