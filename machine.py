# Importaciones del algoritmo original
import streamlit as st
import pandas as pd
import numpy as np
from ortools.sat.python import cp_model
import requests
from faker import Faker

# Nuevas importaciones para machine learning
from sklearn.preprocessing import OneHotEncoder
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.optimizers import Adam

# Importaciones adicionales que podrían ser útiles
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, classification_report
import seaborn as sns

# Inicializar Faker
fake = Faker()

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

# Función para enviar los datos a la API
def post_data(endpoint, data):
    try:
        response = requests.post(f"{BASE_URL}/{endpoint}", json=data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error al enviar datos a {endpoint}: {str(e)}")
        return None

# Función para generar un acrónimo único para el grupo
def generar_acronimo():
    return fake.unique.bothify(text='??##', letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ')

def preprocesar_datos_ml(profesores, materias, salones, horarios_disponibles, profesor_materia):
    # Crear DataFrames
    df_profesores = pd.DataFrame(profesores)
    df_materias = pd.DataFrame(materias)
    df_salones = pd.DataFrame(salones)
    df_horarios = pd.DataFrame(horarios_disponibles)
    df_prof_mat = pd.DataFrame(profesor_materia)
    
    # Combinar datos
    df_combined = pd.merge(df_horarios, df_prof_mat, on='profesor_id')
    df_combined = pd.merge(df_combined, df_materias, left_on='materia_id', right_on='id')
    df_combined = pd.merge(df_combined, df_profesores, left_on='profesor_id', right_on='id')
    
    # One-hot encoding para variables categóricas
    encoder = OneHotEncoder(sparse=False)
    encoded_features = encoder.fit_transform(df_combined[['dia', 'hora_inicio', 'profesor_id', 'materia_id']])
    
    # Crear matriz de características
    X = np.hstack((encoded_features, df_combined[['alumnos']].values))
    
    # La variable objetivo podría ser la asignación de salón
    y = df_combined['salon_id'].values
    
    return X, y, encoder

def crear_modelo(input_shape, num_salones):
    model = Sequential([
        Dense(128, activation='relu', input_shape=(input_shape,)),
        Dropout(0.3),
        Dense(64, activation='relu'),
        Dropout(0.3),
        Dense(32, activation='relu'),
        Dense(num_salones, activation='softmax')
    ])
    
    model.compile(optimizer=Adam(learning_rate=0.001),
                  loss='sparse_categorical_crossentropy',
                  metrics=['accuracy'])
    
    return model

def entrenar_modelo(X, y, num_salones):
    model = crear_modelo(X.shape[1], num_salones)
    history = model.fit(X, y, epochs=50, batch_size=32, validation_split=0.2, verbose=1)
    return model, history

def generar_horario_ml(model, encoder, profesores, materias, salones, horarios_disponibles, profesor_materia):
    # Preprocesar datos de entrada
    X, _, _ = preprocesar_datos_ml(profesores, materias, salones, horarios_disponibles, profesor_materia)
    
    # Predecir asignaciones de salones
    predicciones = model.predict(X)
    salon_asignados = np.argmax(predicciones, axis=1)
    
    # Crear horario
    horario_generado = []
    for i, (_, horario) in enumerate(pd.DataFrame(horarios_disponibles).iterrows()):
        clase_data = {
            'grupo': generar_acronimo(),
            'dia_semana': horario['dia'],
            'hora_inicio': horario['hora_inicio'],
            'hora_fin': horario['hora_fin'],
            'alumnos': int(materias[i]['alumnos']),
            'materia_id': int(materias[i]['id']),
            'salon_id': int(salones[salon_asignados[i]]['id']),
            'profesor_id': int(profesores[i]['id'])
        }
        horario_generado.append(clase_data)
    
    return horario_generado

# En la función main
def main():
    st.title('Generador de Horarios UTS con Machine Learning')
    
    # Obtener datos
    profesores = get_data('profesores')
    materias = get_data('materias')
    salones = get_data('salones')
    horarios_disponibles = get_data('horarios_disponibles')
    profesor_materia = get_data('profesor_materia')
    
    if all([profesores, materias, salones, horarios_disponibles, profesor_materia]):
        st.success("Datos cargados correctamente")
        
        if st.button('Entrenar modelo y generar horario'):
            with st.spinner('Entrenando modelo de ML...'):
                X, y, encoder = preprocesar_datos_ml(profesores, materias, salones, horarios_disponibles, profesor_materia)
                model, history = entrenar_modelo(X, y, len(salones))
                
            st.success('Modelo entrenado. Generando horario...')
            
            horario_generado = generar_horario_ml(model, encoder, profesores, materias, salones, horarios_disponibles, profesor_materia)
            
            if horario_generado:
                st.success('Horario generado con éxito')
                df_horario = crear_vista_horario(horario_generado, pd.DataFrame(profesores), pd.DataFrame(materias), pd.DataFrame(salones))
                st.write("Vista del Horario:")
                st.dataframe(df_horario.style.set_properties(**{'white-space': 'pre-wrap'}))
            else:
                st.error('No fue posible generar el horario')
    else:
        st.error('No se pudieron cargar todos los datos necesarios.')

if __name__ == "__main__":
    main()