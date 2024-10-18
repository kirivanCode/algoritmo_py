import streamlit as st
import random
import numpy as np
import pandas as pd
from deap import base, creator, tools, algorithms
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import requests

# URL base para las solicitudes a la API
BASE_URL = "http://localhost:8000/api"

# Función para obtener los datos desde la API
@st.cache_data
def get_data(endpoint):
    try:
        response = requests.get(f"{BASE_URL}/{endpoint}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error al obtener datos de {endpoint}: {str(e)}")
        return None

# Definir los días de la semana y los bloques de horario
DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']
BLOQUES = ['06:00-07:30', '07:30-09:00', '09:00-10:30', '10:30-12:00', '12:00-13:30', 
           '13:30-15:00', '15:00-16:30', '16:30-18:00', '18:00-19:30', '19:30-21:00']

# Actualizar el LabelEncoder para manejar nuevas etiquetas
def update_label_encoder(le, new_labels):
    le_classes = set(le.classes_)
    new_classes = set(new_labels)
    combined_classes = np.array(sorted(le_classes.union(new_classes)))
    le.classes_ = combined_classes
    return le

# Preparar datos para el modelo de ML
def prepare_data():
    profesores = get_data('profesores')
    materias = get_data('materias')
    salones = get_data('salones')
    horarios_disponibles = get_data('horarios_disponibles')
    profesor_materia = get_data('profesor_materia')

    df_profesores = pd.DataFrame(profesores)
    df_materias = pd.DataFrame(materias)
    df_salones = pd.DataFrame(salones)
    df_horarios_disponibles = pd.DataFrame(horarios_disponibles)
    df_profesor_materia = pd.DataFrame(profesor_materia)

    le_profesores = LabelEncoder()
    le_materias = LabelEncoder()

    # Codificar los IDs de profesores y materias
    df_profesor_materia['profesor_encoded'] = le_profesores.fit_transform(df_profesor_materia['profesor_id'])
    df_profesor_materia['materia_encoded'] = le_materias.fit_transform(df_profesor_materia['materia_id'])

    X = df_profesor_materia[['profesor_encoded', 'materia_encoded', 'experiencia', 'calificacion_alumno']]
    y = df_profesor_materia['calificacion_alumno']

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)

    return df_profesores, df_materias, df_salones, df_horarios_disponibles, df_profesor_materia, model, le_profesores, le_materias

# Crear el tipo de fitness
creator.create("FitnessMax", base.Fitness, weights=(1.0,))
creator.create("Individual", list, fitness=creator.FitnessMax)

# Inicializar toolbox
toolbox = base.Toolbox()

# Función para crear un gen (una clase)
def create_class(df_profesores, df_materias, df_salones):
    profesor = random.choice(df_profesores['id'].tolist())
    materia = random.choice(df_materias['id'].tolist())
    salon = random.choice(df_salones['id'].tolist())
    dia = random.choice(DIAS)
    bloque = random.choice(BLOQUES)
    return (profesor, materia, salon, dia, bloque)

# Función de evaluación con manejo de errores y depuración
def evalSchedule(individual, df_profesores, df_materias, df_salones, df_profesor_materia, model, le_profesores, le_materias):
    conflicts = 0
    profesor_schedule = {}
    salon_schedule = {}
    total_score = 0
    
    unseen_labels_profesores = set()
    unseen_labels_materias = set()

    for clase in individual:
        profesor, materia, salon, dia, bloque = clase
        
        # Verificar conflictos
        if (profesor, dia, bloque) in profesor_schedule or (salon, dia, bloque) in salon_schedule:
            conflicts += 1
        else:
            profesor_schedule[(profesor, dia, bloque)] = materia
            salon_schedule[(salon, dia, bloque)] = materia
        
        # Verificar capacidad del salón
        capacidad_salon = df_salones[df_salones['id'] == salon]['capacidad_alumnos'].values[0]
        alumnos_materia = df_materias[df_materias['id'] == materia]['alumnos'].values[0]
        if alumnos_materia > capacidad_salon:
            conflicts += 1
        
        # Usar el modelo de ML para evaluar la idoneidad de la asignación
        if profesor in le_profesores.classes_ and materia in le_materias.classes_:
            profesor_encoded = le_profesores.transform([profesor])[0]
            materia_encoded = le_materias.transform([materia])[0]
            experiencia = df_profesor_materia[(df_profesor_materia['profesor_id'] == profesor) & 
                                              (df_profesor_materia['materia_id'] == materia)]['experiencia'].values
            if len(experiencia) > 0:
                X_pred = [[profesor_encoded, materia_encoded, experiencia[0], 0]]  # 0 es un placeholder para calificacion_alumno
                score = model.predict(X_pred)[0]
                total_score += score
            else:
                conflicts += 1  # Si no hay registro de profesor-materia, lo consideramos un conflicto
        else:
            if profesor not in le_profesores.classes_:
                unseen_labels_profesores.add(profesor)
            if materia not in le_materias.classes_:
                unseen_labels_materias.add(materia)
            conflicts += 1  # Penalizar etiquetas no vistas
    
    if unseen_labels_profesores:
        st.error(f"Profesores no reconocidos por el LabelEncoder: {unseen_labels_profesores}")
    if unseen_labels_materias:
        st.error(f"Materias no reconocidas por el LabelEncoder: {unseen_labels_materias}")

    # La fitness es una combinación de la puntuación del modelo y los conflictos
    fitness = total_score - (conflicts * 10)  # Penalizamos fuertemente los conflictos
    return fitness,

# Algoritmo principal
def generate_schedule(df_profesores, df_materias, df_salones, df_profesor_materia, model, le_profesores, le_materias):
    # Registrar funciones en el toolbox
    toolbox.register("attr_class", create_class, df_profesores, df_materias, df_salones)
    toolbox.register("individual", tools.initRepeat, creator.Individual, toolbox.attr_class, n=len(df_materias))
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("evaluate", evalSchedule, df_profesores=df_profesores, df_materias=df_materias, 
                     df_salones=df_salones, df_profesor_materia=df_profesor_materia, 
                     model=model, le_profesores=le_profesores, le_materias=le_materias)
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("mutate", tools.mutShuffleIndexes, indpb=0.05)
    toolbox.register("select", tools.selTournament, tournsize=3)

    random.seed(42)
    pop = toolbox.population(n=300)
    hof = tools.HallOfFame(1)
    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", np.mean)
    stats.register("std", np.std)
    stats.register("min", np.min)
    stats.register("max", np.max)
    
    pop, log = algorithms.eaSimple(pop, toolbox, cxpb=0.5, mutpb=0.2, ngen=50, 
                                   stats=stats, halloffame=hof, verbose=True)
    
    return hof[0]

# Función principal de Streamlit
def main():
    st.title('Generador de Horarios UTS con Machine Learning')
    
    st.write("Preparando datos...")
    df_profesores, df_materias, df_salones, df_horarios_disponibles, df_profesor_materia, model, le_profesores, le_materias = prepare_data()
    st.write("Datos preparados.")

    if st.button('Generar Horario'):
        with st.spinner('Generando horario...'):
            best = generate_schedule(df_profesores, df_materias, df_salones, df_profesor_materia, model, le_profesores, le_materias)
        
        st.success("Horario generado con éxito")
        
        # Crear DataFrame con el mejor horario
        mejor_horario = pd.DataFrame(best, columns=['profesor_id', 'materia_id', 'salon_id', 'dia', 'hora_inicio'])
        mejor_horario['hora_fin'] = mejor_horario['hora_inicio'].apply(lambda x: x.split('-')[1])
        mejor_horario['hora_inicio'] = mejor_horario['hora_inicio'].apply(lambda x: x.split('-')[0])
        mejor_horario['grupo'] = mejor_horario.index + 1
        mejor_horario['alumnos'] = mejor_horario['materia_id'].map(df_materias.set_index('id')['alumnos'])

        st.write(mejor_horario)

        if st.button('Guardar Horario en la Base de Datos'):
            with st.spinner('Guardando horario...'):
                for _, row in mejor_horario.iterrows():
                    data = row.to_dict()
                    response = requests.post(f"{BASE_URL}/clases", json=data)
                    if response.status_code != 201:
                        st.error(f"Error al guardar clase: {response.status_code}")
                    else:
                        st.success(f"Clase guardada con éxito: {response.json()['id']}")

            st.success("Proceso completado. El horario ha sido guardado en la base de datos.")

if __name__ == "__main__":
    main()
