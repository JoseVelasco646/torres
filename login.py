import streamlit as st
from supabase import create_client, Client
import runpy

SUPABASE_URL = "https://wkimchzmykvcofvprfat.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndraW1jaHpteWt2Y29mdnByZmF0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgwMjQ4ODgsImV4cCI6MjA2MzYwMDg4OH0.O84iGohEv1kgLZFoUaQun-SoFGO2XaDWHYJCsudYArQ"

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def login_page():
    st.title("Login de Usuario")

    with st.form("login_form"):
        email = st.text_input("Correo electrónico")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Iniciar sesión")

    if submit:
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if response.user:
                st.success(f"Bienvenido, {response.user.email}!")
                st.session_state.user = response.user  
                st.experimental_rerun()  
            else:
                st.error("Correo o contraseña incorrectos.")
        except Exception as e:
            st.error(f"Error: {e}")
