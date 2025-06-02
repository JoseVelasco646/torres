import streamlit as st
from login import login_page
from register import register_page
from crear_torre import crear_torre


if "user" not in st.session_state:
    st.session_state.user = None


if st.session_state.user is None:
    option = st.sidebar.selectbox("Navegación", ["Login", "Registro"])

    if option == "Login":
        login_page()
    elif option == "Registro":
        register_page()
else:
    crear_torre()
