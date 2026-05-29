import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
import calendar
import io
import os

from .utils import (
    formato_cop,
    formato_porcentaje,
    obtener_datos_holding,
    obtener_meta_guardada,
)

# --- Mapeo conn_name -> (archivo JSON de meta) ------------

_SEDES = {
    "postgresql":  ("Hospital de Alta Complejidad del Magdalena Centro",          "config_meta_dorada.json"),
    "ucm":         ("Unidad Clínica La Magdalena",        "config_meta_magdalena.json"),
    "putumayo":    ("Hospital de Alta Complejidad del Putumayo", "config_meta_putu.json"),
    "traumanorte": ("Clínica Traumanorte",                "config_meta_traumanorte.json"),
}

# Definición del orden específico requerido para la visualización
_ORDEN_SEDES = [
    "Hospital de Alta Complejidad del Putumayo",
    "Hospital de Alta Complejidad del Magdalena Centro",
    "Clínica Traumanorte",
    "Unidad Clínica La Magdalena"
]

# Paleta de colores fija y diferenciada por sede
_COLORES_SEDES = {
    "Hospital de Alta Complejidad del Putumayo": "#1d4ed8",
    "Hospital de Alta Complejidad del Magdalena Centro": "#10b981",
    "Clínica Traumanorte": "#f59e0b",
    "Unidad Clínica La Magdalena": "#6366f1"
}

def _sede(raw: str) -> str:
    key = str(raw).lower()
    return _SEDES[key][0] if key in _SEDES else key.replace("_", " ").title()

def _metas_por_sede(modo: str) -> dict:
    """Lee el JSON de cada sede y devuelve {nombre_sede: meta_del_periodo}."""
    factor = 12 if modo == "Por Año" else 1
    return {
        nombre: obtener_meta_guardada(archivo) * factor
        for _, (nombre, archivo) in _SEDES.items()
    }

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
           COALESCE(igi.descripcion,'MEDICAMENTOS/INSUMOS') AS linea_mercadeo,
           current_database()                               AS sede_origen
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
           'PROCEDIMIENTOS/OTROS'                           AS linea_mercadeo,
           current_database()                               AS sede_origen
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

# --- Graficos ----------------------------------------------------------------

def _fig_barras(df_s: pd.DataFrame) -> go.Figure:
    colores = [
        _COLORES_SEDES.get(r["sede_mapeada"], "#6e7681")
        for _, r in df_s.iterrows()
    ]
    fig = go.Figure(go.Bar(
        y=df_s["sede_mapeada"],
        x=df_s["valor_cargo"],
        orientation="h",
        marker_color=colores,
        text=[formato_cop(v) for v in df_s["valor_cargo"]],
        textposition="outside",
        textfont=dict(size=11),
        cliponaxis=False,
    ))
    for _, r in df_s.iterrows():
        if r["meta"] > 0:
            fig.add_shape(
                type="line",
                x0=r["meta"], x1=r["meta"],
                y0=r["sede_mapeada"],
                y1=r["sede_mapeada"],
                xref="x", yref="y",
                line=dict(color="#6e7681", width=1.5, dash="dot"),
            )
    fig.update_layout(
        height=60 + 65 * len(df_s),
        margin=dict(l=0, r=140, t=10, b=0),
        xaxis=dict(tickformat="$,.0f", showgrid=True, gridcolor="#e5e7eb", zeroline=False),
        yaxis=dict(showgrid=False, autorange="reversed"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig

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

# --- Cards por sede ----------------------------------------------------------

_LOGOS = {
    "Hospital de Alta Complejidad del Magdalena Centro": "assets/images/logo_hacmc_magdalena_centro.png",
    "Unidad Clínica La Magdalena": "assets/images/logo_ucm_magdalena_sas.png",
    "Hospital de Alta Complejidad del Putumayo": "assets/images/logo_hacp_putumayo.png",
    "Clínica Traumanorte": "assets/images/logo_ctm_traumanorte.png",
}

def _cards_sedes(df_s: pd.DataFrame, dias_trans: int, dias_tot: int):
    cols = st.columns(len(df_s))

    for col, (_, r) in zip(cols, df_s.iterrows()):
        v    = r["valor_cargo"]
        meta = r["meta"]
        pct  = r["pct"]

        if pct >= 1.0:
            color_delta = "normal"
        elif pct >= 0.85:
            color_delta = "off"
        else:
            color_delta = "inverse"

        with col:
            # st.markdown(f"**{r['sede_mapeada']}**") --- Para ponerle titulo a los logos, descomentar .

            ruta_logo = _LOGOS.get(r['sede_mapeada'], "")
            if os.path.exists(ruta_logo):
                st.image(ruta_logo)
            else:
                st.write("")

            st.metric("Facturado al día de hoy", formato_cop(v))
            st.metric("Meta total del periodo", formato_cop(meta))
            st.metric(
                "Nivel de Cumplimiento",
                formato_porcentaje(pct),
                delta=f"{(pct - 1)*100:+.1f}% vs Meta",
                delta_color=color_delta,
            )

            st.divider()

# --- Exportacion PDF ---------------------------------------------------------

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
    df_s: pd.DataFrame,
    df: pd.DataFrame,
) -> bytes:
    """
    Construye un PDF ejecutivo con los mismos datos que se muestran en pantalla
    para el periodo y filtro activo, usando ReportLab.
    Devuelve los bytes del PDF listo para descargar.
    """
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

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
    col_w = (W - 3.6 * cm) / 4  # ancho de columna para tablas de 4 cols

    styles = getSampleStyleSheet()

    # ---- Estilos personalizados ----
    estilo_titulo = ParagraphStyle(
        "Titulo",
        parent=styles["Title"],
        fontSize=16,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=4,
        alignment=TA_CENTER,
    )
    estilo_subtitulo = ParagraphStyle(
        "Subtitulo",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=10,
        alignment=TA_CENTER,
    )
    estilo_seccion = ParagraphStyle(
        "Seccion",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=14,
        spaceAfter=6,
        borderPad=2,
    )
    estilo_normal = ParagraphStyle(
        "Normal2",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#374151"),
    )
    estilo_celda_label = ParagraphStyle(
        "CeldaLabel",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#6b7280"),
        alignment=TA_CENTER,
    )
    estilo_celda_valor = ParagraphStyle(
        "CeldaValor",
        parent=styles["Normal"],
        fontSize=12,
        textColor=colors.HexColor("#111827"),
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )
    estilo_delta_verde = ParagraphStyle(
        "DeltaVerde",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#10b981"),
        alignment=TA_CENTER,
    )
    estilo_delta_rojo = ParagraphStyle(
        "DeltaRojo",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#ef4444"),
        alignment=TA_CENTER,
    )
    estilo_delta_gris = ParagraphStyle(
        "DeltaGris",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#6b7280"),
        alignment=TA_CENTER,
    )

    story = []

    # =========================================================
    # ENCABEZADO
    # =========================================================
    story.append(Paragraph("CONSOLIDADO HOLDING EMPRESARIAL CAYENA AZUL", estilo_titulo))
    story.append(Paragraph(f"Informe Ejecutivo — {etiqueta}", estilo_subtitulo))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#003e8f")))
    story.append(Spacer(1, 10))

    # =========================================================
    # SECCION 1: Balance Financiero Global
    # =========================================================
    story.append(Paragraph("Balance Financiero Global del Holding", estilo_seccion))

    # Fila 1: Meta | Facturado | Eficiencia
    delta_efic_txt  = f"{formato_porcentaje(eficiencia_momento - 1)} vs ideal" if eficiencia_momento != 0 else "0%"
    color_efic      = estilo_delta_verde if eficiencia_momento >= 1 else estilo_delta_rojo
    avance_txt      = f"{formato_porcentaje(porcentaje_avance_global)} de la meta"

    fila1 = [
        [
            Paragraph("Meta Global", estilo_celda_label),
            Paragraph("Total Facturado Holding", estilo_celda_label),
            Paragraph("Eficiencia a la Fecha", estilo_celda_label),
        ],
        [
            Paragraph(formato_cop(meta_per), estilo_celda_valor),
            Paragraph(formato_cop(total), estilo_celda_valor),
            Paragraph(formato_porcentaje(eficiencia_momento), estilo_celda_valor),
        ],
        [
            Paragraph("", estilo_celda_label),
            Paragraph(avance_txt, estilo_delta_verde if porcentaje_avance_global >= 1 else estilo_delta_rojo),
            Paragraph(delta_efic_txt, color_efic),
        ],
    ]

    ancho3 = (W - 3.6 * cm) / 3
    t1 = Table(fila1, colWidths=[ancho3] * 3, rowHeights=[16, 22, 14])
    t1.setStyle(TableStyle([
        ("BOX",        (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("INNERGRID",  (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("BACKGROUND", (0, 0), (-1, 0),  colors.HexColor("#f8fafc")),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t1)
    story.append(Spacer(1, 8))

    # Fila 2: Faltante/Superávit | Días totales | Días transcurridos
    label_faltante = "Faltante para Meta" if monto_faltante > 0 else "Meta Superada (Superávit)"
    valor_faltante = formato_cop(abs(monto_faltante))

    fila2 = [
        [
            Paragraph(label_faltante, estilo_celda_label),
            Paragraph("Total Días del Período", estilo_celda_label),
            Paragraph("Días Transcurridos", estilo_celda_label),
        ],
        [
            Paragraph(valor_faltante, estilo_celda_valor),
            Paragraph(f"{dias_tot} Días", estilo_celda_valor),
            Paragraph(f"{dias_trans} Días", estilo_celda_valor),
        ],
        [
            Paragraph("", estilo_celda_label),
            Paragraph("", estilo_celda_label),
            Paragraph(f"{dias_rest} días restantes", estilo_delta_gris),
        ],
    ]

    t2 = Table(fila2, colWidths=[ancho3] * 3, rowHeights=[16, 22, 14])
    t2.setStyle(TableStyle([
        ("BOX",        (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("INNERGRID",  (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("BACKGROUND", (0, 0), (-1, 0),  colors.HexColor("#f8fafc")),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t2)

    # =========================================================
    # SECCION 2: Situación por Sede
    # =========================================================
    story.append(Paragraph("Situación por Sede", estilo_seccion))

    # Cabecera de la tabla de sedes
    cab_sedes = ["Sede", "Facturado", "Meta del Período", "Eficiencia"]
    filas_sedes = [cab_sedes]

    for _, r in df_s.iterrows():
        pct_val = r["pct"]
        cumpl_txt = formato_porcentaje(pct_val)
        delta_txt = f"{(pct_val - 1)*100:+.1f}% vs Meta"
        filas_sedes.append([
            r["sede_mapeada"],
            formato_cop(r["valor_cargo"]),
            formato_cop(r["meta"]),
            f"{cumpl_txt}  ({delta_txt})",
        ])

    tw = W - 3.6 * cm
    col_anchos_sedes = [tw * 0.38, tw * 0.22, tw * 0.22, tw * 0.18]
    t_sedes = Table(filas_sedes, colWidths=col_anchos_sedes)

    # Colores de fondo por fila según cumplimiento
    sede_styles = [
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#1e293b")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  9),
        ("ALIGN",        (0, 0), (-1, 0),  "CENTER"),
        ("FONTSIZE",     (0, 1), (-1, -1), 9),
        ("ALIGN",        (1, 1), (-1, -1), "CENTER"),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (0, -1),  8),
    ]

    # Colorear la columna de cumplimiento según nivel
    for i, (_, r) in enumerate(df_s.iterrows(), start=1):
        pct_val = r["pct"]
        if pct_val >= 1.0:
            txt_color = colors.HexColor("#10b981")
        elif pct_val >= 0.85:
            txt_color = colors.HexColor("#f59e0b")
        else:
            txt_color = colors.HexColor("#ef4444")
        sede_styles.append(("TEXTCOLOR", (3, i), (3, i), txt_color))
        sede_styles.append(("FONTNAME",  (3, i), (3, i), "Helvetica-Bold"))

    t_sedes.setStyle(TableStyle(sede_styles))
    story.append(t_sedes)

    # =========================================================
    # GRAFICA: Facturación por Sede (barras nativas ReportLab)
    # =========================================================
    story.append(Paragraph("Facturación por Sede", estilo_seccion))

    from reportlab.platypus import Table as RLTable, TableStyle as RLTS
    from reportlab.lib.units import cm as _cm
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    from reportlab.graphics import renderPDF

    _tw = W - 3.6 * cm
    _bar_col_w = _tw * 0.52   # columna de la barra
    _max_val = df_s["valor_cargo"].max() if df_s["valor_cargo"].max() > 0 else 1

    _graf_filas = []
    for _, _r in df_s.iterrows():
        _sede_nm  = str(_r["sede_mapeada"])
        _val      = _r["valor_cargo"]
        _ratio    = _val / _max_val
        _hex      = _COLORES_SEDES.get(_sede_nm, "#6e7681")

        # Dibujo de la barra con Drawing de ReportLab
        _dw, _dh = _bar_col_w, 18
        _d = Drawing(_dw, _dh)
        # fondo gris claro
        _d.add(Rect(0, 4, _dw, 10, fillColor=colors.HexColor("#f1f5f9"), strokeColor=None))
        # barra coloreada
        _bw = max(_ratio * _dw, 2)
        _d.add(Rect(0, 4, _bw, 10, fillColor=colors.HexColor(_hex), strokeColor=None))

        _graf_filas.append([
            Paragraph(f"<b>{_sede_nm}</b>", ParagraphStyle("SN", parent=estilo_normal, fontSize=8)),
            _d,
            Paragraph(formato_cop(_val), ParagraphStyle("SV", parent=estilo_normal, fontSize=8, alignment=2)),  # TA_RIGHT=2
        ])

    _col_ws = [_tw * 0.32, _tw * 0.48, _tw * 0.20]
    _t_graf = RLTable(_graf_filas, colWidths=_col_ws, rowHeights=[26] * len(_graf_filas))
    _t_graf.setStyle(RLTS([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (0, -1),  4),
        ("RIGHTPADDING",  (2, 0), (2, -1),  4),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.5, colors.HexColor("#f1f5f9")),
    ]))
    story.append(_t_graf)
    story.append(Spacer(1, 4))

    # =========================================================
    # SECCION 3: Diagnóstico Operativo (Top 5)
    # =========================================================
    story.append(Paragraph("Diagnóstico Operativo", estilo_seccion))

    def _tabla_top5_pdf(df_src: pd.DataFrame, col: str, titulo: str, excluir: str = None):
        tmp = df_src[df_src[col] != excluir].copy() if excluir else df_src.copy()
        top = (
            tmp.groupby(col)["valor_cargo"]
            .sum()
            .nlargest(5)
            .reset_index()
        )
        story.append(Paragraph(titulo, ParagraphStyle(
            "SubHead", parent=estilo_normal, fontName="Helvetica-Bold", fontSize=9, spaceBefore=8
        )))

        filas = [["#", "Nombre", "Facturado"]]
        for i, row in enumerate(top.itertuples(), 1):
            filas.append([str(i), getattr(row, col), formato_cop(row.valor_cargo)])

        tw2 = W - 3.6 * cm
        t = Table(filas, colWidths=[tw2 * 0.06, tw2 * 0.66, tw2 * 0.28])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#334155")),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("ALIGN",         (0, 0), (0, -1),  "CENTER"),
            ("ALIGN",         (2, 0), (2, -1),  "RIGHT"),
            ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 1), (1, -1),  8),
            ("RIGHTPADDING",  (2, 0), (2, -1),  8),
        ]))
        story.append(t)

    _tabla_top5_pdf(df, "entidad_id",    "Top 5 de Entidades",          excluir="SIN ENTIDAD")
    _tabla_top5_pdf(df, "uf_id",         "Top 5 Unidades Funcionales",  excluir="SIN UNIDAD FUNCIONAL")
    _tabla_top5_pdf(df, "linea_mercadeo","Top 5 Líneas de Inventario")

    # =========================================================
    # PIE DE PÁGINA (fecha de generación)
    # =========================================================
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} — CONSOLIDADO HOLDING EMPRESARIAL CAYENA AZUL",
        ParagraphStyle("Pie", parent=estilo_normal, fontSize=7, textColor=colors.HexColor("#9ca3af"), alignment=TA_CENTER)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


# --- Funcion principal -------------------------------------------------------

def mostrar_resumen():
    st.markdown(
        "<h3 style='text-align:center;'>CONSOLIDADO HOLDING EMPRESARIAL CAYENA AZUL</h3>",
        unsafe_allow_html=True,
    )

    st.markdown("""
    <style>
    [data-testid="stMetricValue"] {
        font-size: 1.4rem;
    }
    </style>
""", unsafe_allow_html=True)

    MESES = {
        1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio",
        7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre",
    }
    hoy  = date.today()
    ayer = hoy - timedelta(days=1)

    with st.expander("FILTRO DE PERIODO DE ANALISIS", expanded=True):
        modo = st.radio(
            "Seleccione el rango de visualizacion:",
            ["Por Mes", "Por Año"],
            index=0, horizontal=True, key="res_modo",
        )
        anos = [hoy.year, hoy.year - 1, hoy.year - 2]

        if modo == "Por Mes":
            c1, c2 = st.columns(2)
            ano     = c1.selectbox("Año", anos, key="res_ano_m")
            mes_nom = c2.selectbox("Mes", list(MESES.values()), index=hoy.month - 1, key="res_mes_m")
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
            ano      = st.selectbox("Año", anos, key="res_ano_a")
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

    with st.spinner("Consolidando analítica..."):
        df = obtener_datos_holding(_query(f0, f1))

    if df is None or df.empty:
        st.warning(f"No se encontraron registros para el periodo seleccionado ({etiqueta}).")
        return

    df["valor_cargo"] = pd.to_numeric(df["valor_cargo"], errors="coerce").fillna(0)
    for col in ["entidad_id", "uf_id", "linea_mercadeo"]:
        if col not in df.columns:
            df[col] = "NO ESPECIFICADO"
    df["sede_mapeada"] = df["sede_origen"].apply(_sede) if "sede_origen" in df.columns else "Holding"

    metas = _metas_por_sede(modo)

    df_s = (
        df.groupby("sede_mapeada")["valor_cargo"]
        .sum()
        .reset_index()
    )
    df_s["meta"] = df_s["sede_mapeada"].map(metas).fillna(0)

    factor_dias = dias_trans / dias_tot if dias_tot > 0 else 1
    df_s["pct"]  = df_s.apply(lambda r: r.valor_cargo / (r.meta * factor_dias) if (r.meta * factor_dias) > 0 else 0, axis=1)

    df_s["sede_mapeada"] = pd.Categorical(df_s["sede_mapeada"], categories=_ORDEN_SEDES, ordered=True)
    df_s = df_s.sort_values("sede_mapeada").reset_index(drop=True)

    # Totales globales
    meta_per  = df_s["meta"].sum()
    total     = df["valor_cargo"].sum()
    pct       = total / meta_per if meta_per else 0
    diff      = total - meta_per
    diario    = total / dias_trans
    proj      = diario * dias_tot
    dias_rest = max(dias_tot - dias_trans, 1)

    meta_diaria_base             = meta_per / dias_tot if dias_tot > 0 else 0
    meta_proporcional_acumulada  = meta_diaria_base * dias_trans
    eficiencia_momento           = (total / meta_proporcional_acumulada) if meta_proporcional_acumulada > 0 else 0
    porcentaje_avance_global     = (total / meta_per) if meta_per > 0 else 0
    monto_faltante               = meta_per - total

    # === SECCION 1: Balance global ===================

    st.markdown("<h3 style='text-align: center; margin-bottom: 25px;'> Balance Financiero Global del Holding</h3>", unsafe_allow_html=True)

    r1_c1, r1_c2, r1_c3 = st.columns(3)

    with r1_c1:
        st.metric(label="Meta Global", value=formato_cop(meta_per))

    with r1_c2:
        st.metric(
            label="Total Facturado Holding",
            value=formato_cop(total),
            delta=f"{formato_porcentaje(porcentaje_avance_global)} de la meta"
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

    # === SECCION 1.5: Gráfica comparativa facturado vs meta por sede ==========
    meta_prop = df_s["meta"] * factor_dias  # meta proporcional al periodo transcurrido

    fig_comp = go.Figure()
    fig_comp.add_trace(go.Bar(
        name="Facturado",
        x=df_s["sede_mapeada"],
        y=df_s["valor_cargo"],
        marker_color=[_COLORES_SEDES.get(s, "#6e7681") for s in df_s["sede_mapeada"]],
        text=[formato_cop(v) for v in df_s["valor_cargo"]],
        textposition="outside",
        textfont=dict(size=10),
    ))
    fig_comp.add_trace(go.Bar(
        name="Meta proporcional",
        x=df_s["sede_mapeada"],
        y=meta_prop,
        marker_color="rgba(110,118,129,0.25)",
        marker_line=dict(color="rgba(110,118,129,0.6)", width=1.5),
        text=[formato_cop(v) for v in meta_prop],
        textposition="outside",
        textfont=dict(size=10, color="#6e7681"),
    ))
    fig_comp.update_layout(
        barmode="group",
        height=340,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(showgrid=False),
        yaxis=dict(tickformat="$,.0f", showgrid=True, gridcolor="#e5e7eb", zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_comp, use_container_width=True)

    st.divider()

    # === SECCION 2: Situación por sede ========================================
    st.markdown("### Situación por Sede")
    _cards_sedes(df_s, dias_trans, dias_tot)

    st.divider()

    # === SECCION 3: Grafico ===================================================
    st.markdown("### Facturación por Sede")
    st.plotly_chart(_fig_barras(df_s), use_container_width=True)

    st.divider()

    # === SECCION 4: Top 5 apilados ============================================
    st.markdown("### Diagnóstico Operativo")

    st.markdown("**Top 5 de Entidades**")
    st.dataframe(_top5(df, "entidad_id", "SIN ENTIDAD"), use_container_width=True)

    st.write("")
    st.markdown("**Top 5 Unidades Funcionales**")
    st.dataframe(_top5(df, "uf_id", "SIN UNIDAD FUNCIONAL"), use_container_width=True)

    st.write("")
    st.markdown("**Top 5 Líneas de Inventario**")
    st.dataframe(_top5(df, "linea_mercadeo"), use_container_width=True)

    st.divider()

    # === SECCION 5: Exportar informe ejecutivo ================================
    nombre_archivo = f"informe_ejecutivo_{etiqueta.replace(' ', '_').replace('/', '-').replace(':', '')}.pdf"
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
        df_s=df_s,
        df=df,
    )
    _, col_dl, _ = st.columns([3, 2, 3])
    with col_dl:
        st.download_button(
            label="📄 Exportar Informe Consolidado en PDF",
            data=pdf_bytes,
            file_name=nombre_archivo,
            mime="application/pdf",
            type="primary",
        )