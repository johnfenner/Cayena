import streamlit as st
from components.header import render_header
from components.sidebar import render_sidebar

# ===== IMPORTACIÓN DE VISTAS =====
import views.total as total
import views.hacp as hacp
import views.hacmc as hacmc
import views.ctm as ctm
import views.ucm as ucm
import views.hact as hact

# ===== CONFIGURACIÓN GENERAL =====
st.set_page_config(
    page_title="Holding Cayena Azul",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== CONTROL DE ESTADO DE NAVEGACIÓN =====
if "active_page" not in st.session_state:
    # 1. Cambiamos el valor inicial a None (o puedes usar "inicio")
    st.session_state.active_page = None 

# ===== RENDERIZADO DE COMPONENTES DE INTERFAZ =====
render_sidebar()
render_header()

# ===== ENRUTADOR DINÁMICO =====
sede_actual = st.session_state.active_page

# Contenedor dinámico que renderiza el archivo de la vista correspondiente
with st.container():
    # Condición para cuando el estado sea nulo
    if sede_actual is None:
        st.info("👈 Por favor, selecciona una sede o vista en el menú lateral para cargar los datos.")
        # pass 

    elif sede_actual == "total":
        total.mostrar_vista()

    elif sede_actual == "hacp":
        hacp.mostrar_vista()

    elif sede_actual == "hacmc":
        hacmc.mostrar_vista()

    elif sede_actual == "ctm":
        ctm.mostrar_vista()

    elif sede_actual == "ucm":
        ucm.mostrar_vista()

    elif sede_actual == "hact":
        hact.mostrar_vista()