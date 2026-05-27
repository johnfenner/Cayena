# views/total/total.py
import streamlit as st
from .informe_general import mostrar_informe_general
from .entidades import mostrar_entidades
from .unidades_funcionales import mostrar_unidades_funcionales
from .mercadeo import mostrar_mercadeo 

def mostrar_vista():
    st.markdown("<h2 style='text-align: center; color: #1f6feb;'> VISIÓN TOTAL HOLDING EMPRESARIAL CAYENA AZUL</h2>", unsafe_allow_html=True)
    st.divider()
    
    # Encabezado con los logos de las 4 sedes del holding (Tolima Grande comentado por el momento - 4 columnas)
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.image("assets/images/logo_hacp_putumayo.png", use_container_width=True)
    with col2: st.image("assets/images/logo_hacmc_magdalena_centro.png", use_container_width=True)
    with col3: st.image("assets/images/logo_ctm_traumanorte.png", use_container_width=True)
    with col4: st.image("assets/images/logo_ucm_magdalena_sas.png", use_container_width=True)
    # with col5: st.image("assets/images/logo_hact_tolima_grande.webp", use_container_width=True)
        
    st.write("<br>", unsafe_allow_html=True)
    
    # Pestañas 
    tab1, tab2, tab3, tab4 = st.tabs([
        "INFORME GENERAL", 
        "ENTIDADES", 
        "UNIDADES FUNCIONALES", 
        "MERCADEO"
    ])
    
    with tab1: mostrar_informe_general()
    with tab2: mostrar_entidades()
    with tab3: mostrar_unidades_funcionales()
    with tab4: mostrar_mercadeo()