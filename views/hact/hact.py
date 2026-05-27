import streamlit as st

from .informe_general import mostrar_informe_general
from .entidades import mostrar_entidades
from .unidades_funcionales import mostrar_unidades_funcionales
from .mercadeo import mostrar_mercadeo 

def mostrar_vista():
    # 1. Configuración de la página
    st.set_page_config(page_title="Informe General - Consumo Diario", layout="wide")
    
    col_izq, col_logo, col_der = st.columns([1, 2, 1])
    
    with col_logo:
        st.image("assets/images/logo_hact_tolima_grande.webp")
    
    # 2. Creación de las Pestañas 
    tab1, tab2, tab3, tab4 = st.tabs([
        "INFORME GENERAL", 
        "ENTIDADES", 
        "UNIDADES FUNCIONALES", 
        "MERCADEO"  
    ])
    
    # 3. Asignación de contenido modularizado a cada pestaña
    with tab1:
        mostrar_informe_general()
        
    with tab2:
        mostrar_entidades()
        
    with tab3:
        mostrar_unidades_funcionales()
        
    with tab4:
        mostrar_mercadeo() 
    

if __name__ == "__main__":
    mostrar_vista()