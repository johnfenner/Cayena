import streamlit as st

def render_header():
    col1, col2 = st.columns([1, 9])

    with col1:
        st.image("assets/images/logo_cayena.jpg")

    with col2:
        st.markdown(
            "<h2 style='margin: 0; color:#1f6feb; line-height: 65px;'>HOLDING EMPRESARIAL CAYENA AZUL</h2>",
            unsafe_allow_html=True
        )

    st.markdown("<hr style='margin-top:10px; margin-bottom:20px;'>", unsafe_allow_html=True)