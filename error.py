import streamlit as st
import pandas as pd
import requests

# URL base para las solicitudes a la API
BASE_URL = "http://localhost:8000/api"

# Función para obtener los datos desde la API
def get_data(endpoint):
    try:
        response = requests.get(f"{BASE_URL}/{endpoint}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error al obtener datos de {endpoint}: {str(e)}")
        return None

# Aplicación Streamlit simplificada
def main():
    st.title('Generador de Horarios UTS - Depuración')
    
    st.write("Esta es una versión simplificada para depuración.")
    
    # Botón para cargar datos
    if st.button('Cargar Datos'):
        with st.spinner('Cargando datos...'):
            profesores = get_data('profesores')
            materias = get_data('materias')
            salones = get_data('salones')
            horarios_disponibles = get_data('horarios_disponibles')
            profesor_materia = get_data('profesor_materia')
        
        if all([profesores, materias, salones, horarios_disponibles, profesor_materia]):
            st.success("Todos los datos se cargaron correctamente")
            
            # Mostrar una muestra de los datos
            st.subheader("Muestra de datos:")
            st.write("Profesores:", pd.DataFrame(profesores[:5]))
            st.write("Materias:", pd.DataFrame(materias[:5]))
            st.write("Salones:", pd.DataFrame(salones[:5]))
            st.write("Horarios disponibles:", pd.DataFrame(horarios_disponibles[:5]))
            st.write("Profesor-Materia:", pd.DataFrame(profesor_materia[:5]))
        else:
            st.error('No se pudieron cargar todos los datos necesarios. Por favor, verifica la conexión con la API.')

if __name__ == "__main__":
    main()