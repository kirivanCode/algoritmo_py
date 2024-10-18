import streamlit as st
import pandas as pd
import numpy as np
from ortools.sat.python import cp_model
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

# Función para enviar los datos a la API
def post_data(endpoint, data):
    try:
        response = requests.post(f"{BASE_URL}/{endpoint}", json=data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error al enviar datos a {endpoint}: {str(e)}")
        return None

# Función para preprocesar los datos
def preprocesar_datos(profesores, materias, salones, horarios_disponibles, profesor_materia):
    df_profesores = pd.DataFrame(profesores)
    df_materias = pd.DataFrame(materias)
    df_salones = pd.DataFrame(salones)
    df_horarios_disponibles = pd.DataFrame(horarios_disponibles)
    df_profesor_materia = pd.DataFrame(profesor_materia)
    
    return df_profesores, df_materias, df_salones, df_horarios_disponibles, df_profesor_materia

# Función para generar el horario y hacer el POST a la API
def generar_horario(profesores, materias, salones, horarios_disponibles, profesor_materia):
    df_profesores, df_materias, df_salones, df_horarios_disponibles, df_profesor_materia = preprocesar_datos(profesores, materias, salones, horarios_disponibles, profesor_materia)
    
    st.write("Datos preprocesados:")
    st.write(f"Profesores: {len(df_profesores)}")
    st.write(f"Materias: {len(df_materias)}")
    st.write(f"Salones: {len(df_salones)}")
    st.write(f"Horarios disponibles: {len(df_horarios_disponibles)}")
    st.write(f"Relaciones profesor-materia: {len(df_profesor_materia)}")
    
    model = cp_model.CpModel()
    
    # Variables
    clases = {}
    for i, horario in df_horarios_disponibles.iterrows():
        for j, salon in df_salones.iterrows():
            for k, prof_mat in df_profesor_materia.iterrows():
                clave = (i, j, k)
                clases[clave] = model.NewBoolVar(f'clase_h{i}_s{j}_pm{k}')
    
    st.write(f"Variables creadas: {len(clases)}")
    
    # Restricciones
    restricciones_aplicadas = 0
    
    # 1. Un profesor no puede dar más de una clase al mismo tiempo
    for i, horario in df_horarios_disponibles.iterrows():
        for profesor_id in df_profesores['id']:
            model.Add(sum(clases[(i, j, k)] 
                          for j in df_salones.index 
                          for k in df_profesor_materia[df_profesor_materia['profesor_id'] == profesor_id].index) <= 1)
            restricciones_aplicadas += 1
    
    # 2. Un salón no puede tener más de una clase al mismo tiempo
    for i, horario in df_horarios_disponibles.iterrows():
        for j in df_salones.index:
            model.Add(sum(clases[(i, j, k)] for k in df_profesor_materia.index) <= 1)
            restricciones_aplicadas += 1
    
    # 3. Respetar la disponibilidad de los profesores
    for i, horario in df_horarios_disponibles.iterrows():
        for k, prof_mat in df_profesor_materia.iterrows():
            if prof_mat['profesor_id'] != horario['profesor_id']:
                for j in df_salones.index:
                    model.Add(clases[(i, j, k)] == 0)
                    restricciones_aplicadas += 1
 # 4. Respetar la capacidad de los salones
   # for j, salon in df_salones.iterrows():
       # for i in df_horarios_disponibles.index:
           # for k, prof_mat in df_profesor_materia.iterrows():
              #  materia = df_materias.loc[df_materias['id'] == prof_mat['materia_id']].iloc[0]
             #   model.Add(clases[(i, j, k)] * materia['alumnos'] <= salon['capacidad_alumnos'])
              #  restricciones_aplicadas += 1
    
    # 5. Asegurar que todas las materias se impartan al menos una vez
    #for materia_id in df_materias['id']:
     #   model.Add(sum(clases[(i, j, k)] 
      #                for i in df_horarios_disponibles.index 
       #               for j in df_salones.index 
        #              for k in df_profesor_materia[df_profesor_materia['materia_id'] == materia_id].index) >= 1)
        #restricciones_aplicadas += 1
    # Función objetivo: maximizar el número de clases asignadas

    # Función objetivo: maximizar el número de clases asignadas
    model.Maximize(sum(clases.values()))
    
    # Resolver el modelo
    solver = cp_model.CpSolver()
    st.write("Resolviendo el modelo...")
    status = solver.Solve(model)
    
    st.write(f"Estado de la solución: {solver.StatusName(status)}")
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        st.write("Se encontró una solución")
        horario_generado = []
        for i, horario in df_horarios_disponibles.iterrows():
            for j, salon in df_salones.iterrows():
                for k, prof_mat in df_profesor_materia.iterrows():
                    if solver.BooleanValue(clases[(i, j, k)]):
                        materia = df_materias.loc[df_materias['id'] == prof_mat['materia_id']].iloc[0]
                        
                        # Añadir manejo de errores y logging
                        profesor_match = df_profesores.loc[df_profesores['id'] == prof_mat['profesor_id']]
                        if profesor_match.empty:
                            st.warning(f"No se encontró profesor con cédula {prof_mat['profesor_id']}. Datos del profesor_materia: {prof_mat}")
                            continue
                        profesor = profesor_match.iloc[0]
                        
                        clase_data = {
                            'grupo': materia['alumnos'],
                            'dia_semana': horario['dia'],
                            'hora_inicio': horario['hora_inicio'],
                            'hora_fin': horario['hora_fin'],
                            'alumnos': materia['alumnos'],
                            'materia_id': materia['id'],
                            'salon_id': salon['id'],
                            'profesor_id': profesor['id']
                        }
                        
                        # Convertir valores a tipos de Python nativos
                        clase_data = {k: (v.item() if hasattr(v, 'item') else v) for k, v in clase_data.items()}
                        
                        # Enviar los datos a la API
                        response = post_data('clases', clase_data)
                        if response is not None:
                            st.success(f"Clase creada: {clase_data}")
                        else:
                            st.error(f"Error al crear la clase: {clase_data}")



# Aplicación Streamlit
def main():
    st.title('Generador de Horarios UTS')
    
    # Obtener los datos
    with st.spinner('Cargando datos...'):
        profesores = get_data('profesores')
        materias = get_data('materias')
        salones = get_data('salones')
        horarios_disponibles = get_data('horarios_disponibles')
        profesor_materia = get_data('profesor_materia')
    
    if all([profesores, materias, salones, horarios_disponibles, profesor_materia]):
        st.success("Todos los datos se cargaron correctamente")
        
        if st.button('Generar Horario para los profesores'):
            with st.spinner('Generando horario...'):
                horario_df = generar_horario(profesores, materias, salones, horarios_disponibles, profesor_materia)
            
            if horario_df is not None:
                st.success('Horario generado con éxito')
                st.write(horario_df)
            else:
                st.error('No fue posible generar el horario')
    else:
        st.error('No se pudieron cargar todos los datos necesarios. Por favor, verifica la conexión con la API.')

if __name__ == "__main__":
    main()
