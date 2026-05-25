import streamlit as st

def render_sidebar():
    # Diccionario centralizado de rutas de imágenes 
    LOGOS = {
        "holding": "assets/images/logo_cayena.jpg",
        "hacp": "assets/images/logo_hacp_putumayo.png",
        "hacmc": "assets/images/logo_hacmc_magdalena_centro.png",
        "ctm": "assets/images/logo_ctm_traumanorte.png",
        "ucm": "assets/images/logo_ucm_magdalena_sas.png",
        "hact": "assets/images/logo_hact_tolima_grande.webp",
    }

    with st.sidebar:
        
        st.markdown("<h3 style='text-align:center; margin-top:-10px; color:#1f6feb;'>HOLDING CAYENA AZUL</h3>", unsafe_allow_html=True)
        st.write("---")
        
        st.markdown("<p style='text-align:center; font-weight:bold; color:#555; margin-bottom:15px;'>SEDES Y HOSPITALES</p>", unsafe_allow_html=True)
        
        # INYECCIÓN DE CSS PARA ELIMINAR EL ESPACIADO INTERNO Y AGRANDAR BOTONES
        st.markdown(
            """
            <style>
                /* Estilo personalizado para las filas de las sedes */
                .fila-sede {
                    display: flex;
                    align-items: center;
                    gap: 15px; /* Espacio horizontal entre el logo y el botón */
                    margin-bottom: 12px;
                    width: 100%;
                }
                
                /* Forzamos a que la imagen ocupe un espacio real grande y visible */
                .contenedor-logo-sidebar img {
                    width: 55px !important;
                    height: 45px !important;
                    object-fit: contain !important; /* Mantiene la proporción original sin aplastar */
                }
                
                /* Ajustamos el botón nativo de Streamlit para que llene el espacio restante */
                .fila-sede div[data-testid="stButton"] {
                    flex-grow: 1;
                    width: auto !important;
                }
                
                /* Opcional: Alinear el texto del botón a la izquierda si prefieres */
                .fila-sede button {
                    text-align: left !important;
                    padding-left: 15px !important;
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        # FUNCIÓN CON CONTENEDORES HTML + COMPONENTE NATIVO
        def crear_opcion_sede(id_pagina, nombre_sede, url_imagen):
            # Contenedor div que agrupa el logo y el botón en la misma línea
            st.markdown(f'<div class="fila-sede">', unsafe_allow_html=True)
            
            
            st.markdown('<div class="contenedor-logo-sidebar">', unsafe_allow_html=True)
            st.image(url_imagen, use_container_width=False)
            st.markdown('</div>', unsafe_allow_html=True)
            
            
            if st.button(nombre_sede, key=f"sidebar_btn_{id_pagina}", use_container_width=True):
                st.session_state.active_page = id_pagina
                st.rerun()
                
            st.markdown('</div>', unsafe_allow_html=True) # Cierre de .fila-sede

        # Renderizado de la lista de hospitales
        crear_opcion_sede("hacp", "HACP Putumayo", LOGOS["hacp"])
        crear_opcion_sede("hacmc", "HACMC Mag. Centro", LOGOS["hacmc"])
        crear_opcion_sede("ctm", "CTM Traumanorte", LOGOS["ctm"])
        crear_opcion_sede("ucm", "UCM La Magdalena", LOGOS["ucm"])
        crear_opcion_sede("hact", "HACT Tolima Grande", LOGOS["hact"])
        
        st.write("---")
        
        # Botón destacado para la vista consolidada global
        if st.button("📊 VER TOTAL HOLDING", key="sidebar_btn_total", use_container_width=True, type="primary"):
            st.session_state.active_page = "total"
            st.rerun()