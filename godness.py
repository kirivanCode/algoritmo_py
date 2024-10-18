import streamlit as st
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
import requests
from ortools.sat.python import cp_model

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

# Función para preprocesar los datos
def preprocesar_datos(profesores, materias, salones, horarios_disponibles, profesor_materia):
    df_profesores = pd.DataFrame(profesores)
    df_materias = pd.DataFrame(materias)
    df_salones = pd.DataFrame(salones)
    df_horarios_disponibles = pd.DataFrame(horarios_disponibles)
    df_profesor_materia = pd.DataFrame(profesor_materia)
    
    return df_profesores, df_materias, df_salones, df_horarios_disponibles, df_profesor_materia

def preparar_datos_ml(df_profesores, df_materias, df_salones, df_horarios_disponibles, df_profesor_materia):
    # Combinar datos
    df_combined = pd.merge(df_horarios_disponibles, df_profesor_materia, left_on='profesor_id', right_on='profesor_id')
    df_combined = pd.merge(df_combined, df_materias, left_on='materia_id', right_on='id', suffixes=('_horario', '_materia'))
    df_combined = pd.merge(df_combined, df_profesores, left_on='profesor_id', right_on='id', suffixes=('', '_profesor'))
    
    # Verificar si 'cedula' existe en los datos de profesores
    if 'cedula' in df_combined.columns:
        profesor_col = 'cedula'
    else:
        raise KeyError("La columna 'cedula' no se encuentra en los datos de profesores.")
    
    # Verificar si 'nombre_materia' existe en los datos de materias
    if 'nombre' in df_combined.columns:
        nombre_materia_col = 'nombre'
    else:
        raise KeyError("La columna 'nombre_materia' no se encuentra en los datos de materias.")

    # Codificar variables categóricas usando 'cedula' en lugar de 'nombre'
    le = LabelEncoder()
    df_combined['dia_encoded'] = le.fit_transform(df_combined['dia'])
    df_combined['profesor_encoded'] = le.fit_transform(df_combined[profesor_col])  # Usar 'cedula'
    df_combined['materia_encoded'] = le.fit_transform(df_combined[nombre_materia_col])

    # Crear características
    X = df_combined[['dia_encoded', 'hora_inicio', 'hora_fin', 'profesor_encoded', 'materia_encoded', 'experiencia', 'calificacion_alumno']]
    X['hora_inicio'] = pd.to_datetime(X['hora_inicio']).dt.hour + pd.to_datetime(X['hora_inicio']).dt.minute / 60
    X['hora_fin'] = pd.to_datetime(X['hora_fin']).dt.hour + pd.to_datetime(X['hora_fin']).dt.minute / 60

    return X, df_combined



# Función para aplicar restricciones al horario generado
def aplicar_restricciones(horario_df, df_profesores, df_materias, df_salones):
    model = cp_model.CpModel()
    
    # Crear variables
    clases = {}
    for i, clase in horario_df.iterrows():
        for j, salon in df_salones.iterrows():
            clases[(i, j)] = model.NewBoolVar(f'clase_{i}_salon_{j}')
    
    # Restricción 1: Un profesor no puede dar más de una clase al mismo tiempo
    for dia in horario_df['dia'].unique():
        for hora in horario_df['hora_inicio'].unique():
            for profesor in horario_df['profesor'].unique():
                clases_simultaneas = [
                    clases[(i, j)]
                    for i, clase in horario_df.iterrows()
                    for j in df_salones.index
                    if clase['dia'] == dia and clase['hora_inicio'] == hora and clase['profesor'] == profesor
                ]
                if clases_simultaneas:
                    model.Add(sum(clases_simultaneas) <= 1)
    
    # Restricción 2: Un salón no puede tener más de una clase al mismo tiempo
    for dia in horario_df['dia'].unique():
        for hora in horario_df['hora_inicio'].unique():
            for j in df_salones.index:
                clases_simultaneas = [
                    clases[(i, j)]
                    for i, clase in horario_df.iterrows()
                    if clase['dia'] == dia and clase['hora_inicio'] == hora
                ]
                if clases_simultaneas:
                    model.Add(sum(clases_simultaneas) <= 1)
    
    # Restricción 3: Respetar la capacidad de los salones
    for i, clase in horario_df.iterrows():
        materia = df_materias[df_materias['nombre'] == clase['materia']].iloc[0]
        for j, salon in df_salones.iterrows():
            model.Add(clases[(i, j)] * materia['alumnos'] <= salon['capacidad_alumnos'])
    
    # Restricción 4: Asegurar que todas las materias se impartan al menos una vez
    for materia in df_materias['nombre']:
        model.Add(sum(clases[(i, j)]
                      for i, clase in horario_df.iterrows()
                      if clase['materia'] == materia
                      for j in df_salones.index) >= 1)
    
    # Resolver el modelo
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        # Actualizar el horario con las asignaciones de salones
        horario_actualizado = []
        for i, clase in horario_df.iterrows():
            for j, salon in df_salones.iterrows():
                if solver.BooleanValue(clases[(i, j)]):
                    horario_actualizado.append({
                        'dia': clase['dia'],
                        'hora_inicio': clase['hora_inicio'],
                        'hora_fin': clase['hora_fin'],
                        'profesor': clase['profesor'],
                        'materia': clase['materia'],
                        'salon': salon['codigo']
                    })
        return pd.DataFrame(horario_actualizado)
    else:
        st.error("No se pudo encontrar una solución que cumpla todas las restricciones")
        return None

# Función para generar el horario con machine learning y aplicar restricciones
def generar_horario_ml(profesores, materias, salones, horarios_disponibles, profesor_materia):
    df_profesores, df_materias, df_salones, df_horarios_disponibles, df_profesor_materia = preprocesar_datos(profesores, materias, salones, horarios_disponibles, profesor_materia)
    
    X, df_combined = preparar_datos_ml(df_profesores, df_materias, df_salones, df_horarios_disponibles, df_profesor_materia)
    
    # Entrenar modelo
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    y = np.random.randint(0, len(df_salones), size=len(X))  # Asignación aleatoria de salones para demostración
    model.fit(X, y)
    
    # Generar predicciones
    predicciones = model.predict(X)
    
    # Crear horario inicial
    horario_inicial = []
    for i, (_, row) in enumerate(df_combined.iterrows()):
        horario_inicial.append({
            'dia': row['dia'],
            'hora_inicio': row['hora_inicio'],
            'hora_fin': row['hora_fin'],
            'profesor': row['cedula'],  # Usar 'cedula' en lugar de 'nombre_x'
            'materia': row['nombre'],
            'salon': df_salones.iloc[predicciones[i]]['codigo']
        })
    
    horario_df = pd.DataFrame(horario_inicial)
    
    # Aplicar restricciones
    horario_final = aplicar_restricciones(horario_df, df_profesores, df_materias, df_salones)
    
    return horario_final

# Aplicación Streamlit
def main():
    st.title('Generador de Horarios UTS con Machine Learning y Restricciones')
    
    # Obtener los datos
    with st.spinner('Cargando datos...'):
        profesores = get_data('profesores')
        materias = get_data('materias')
        salones = get_data('salones')
        horarios_disponibles = get_data('horarios_disponibles')
        profesor_materia = get_data('profesor_materia')
    
    if all([profesores, materias, salones, horarios_disponibles, profesor_materia]):
        st.success("Todos los datos se cargaron correctamente")
        
        # Mostrar una muestra de los datos
        if st.checkbox('Mostrar muestra de datos'):
            st.subheader("Muestra de datos:")
            st.write("Profesores:", pd.DataFrame(profesores).head())
            st.write("Materias:", pd.DataFrame(materias).head())
            st.write("Salones:", pd.DataFrame(salones).head())
            st.write("Horarios Disponibles:", pd.DataFrame(horarios_disponibles).head())
            st.write("Profesor-Materia:", pd.DataFrame(profesor_materia).head())
        
        # Generar horario
        if st.button('Generar Horario'):
            with st.spinner('Generando horario...'):
                horario = generar_horario_ml(profesores, materias, salones, horarios_disponibles, profesor_materia)
            
            if horario is not None:
                st.success("Horario generado con éxito")
                st.write(horario)
    else:
        st.error("Error al cargar algunos de los datos.")

if __name__ == "__main__":
    main()
