import requests
from faker import Faker
from datetime import datetime, timedelta

# Crear una instancia de Faker
fake = Faker('es_ES')

# URL de tu API
base_url = 'http://localhost:8000/api'

# Horarios permitidos (bloques de dos consecutivos)
horarios_inicio = ["06:00","6:45", "07:30", "08:15","09:00","9:45", "10:30","11:15", "12:00","12:45", "13:30","14:15", "15:00","15:45","16:30", "17:15", "18:30", "20:15"]

# Crear profesores
def crear_profesores(num):
    profesores_ids = []
    for _ in range(num):
        data = {
            'tipo_cedula': fake.random_element(elements=('Cédula de Ciudadanía', 'Cédula de Extrangería','Targeta de Identidad','Registro Civil','Pasaporte')),
            'cedula': fake.unique.random_number(digits=10),
            'nombre': fake.name(),
            'tipo_contrato': fake.random_element(elements=('Cátedra', 'Planta', 'Tiempo Completo')),
            'estado': fake.random_element(elements=('Activo', 'Inactivo', 'En proceso')),
            'image_path': fake.image_url(),
        }
        response = requests.post(f'{base_url}/profesores', json=data)
        if response.status_code == 201:
            profesores_ids.append(response.json()['id'])
        print(f'Profesor creado: {response.status_code}')
    return profesores_ids

# Crear materias
def crear_materias(num):
    materias_ids = []
    for _ in range(num):
        data = {
            'codigo': fake.word(),
            'nombre': fake.word(),
            'alumnos': fake.random_int(min=10, max=45),
            'bloques': fake.random_int(min=1, max=3),
        }
        response = requests.post(f'{base_url}/materias', json=data)
        if response.status_code == 201:
            materias_ids.append(response.json()['id'])
        else:
            print(f"Error al crear materia: {response.status_code}")
    return materias_ids

# Crear salones
def crear_salones(num):
    salones_ids = []
    for _ in range(num):
        data = {
            'codigo': fake.word(),
            'capacidad_alumnos': fake.random_int(min=20, max=100),
            'tipo': fake.random_element(elements=('Teórico', 'Laboratorio')),
        }
        response = requests.post(f'{base_url}/salones', json=data)
        if response.status_code == 201:
            salones_ids.append(response.json()['id'])
        print(f'Salón creado: {response.status_code}')
    return salones_ids

# Crear horarios disponibles con bloques consecutivos
def crear_horarios_disponibles(profesor_ids, max_bloques_por_profesor):
    for profesor_id in profesor_ids:
        bloques_creados = 0
        while bloques_creados < max_bloques_por_profesor:
            hora_inicio = fake.random_element(horarios_inicio)
            hora_fin = (datetime.strptime(hora_inicio, "%H:%M") + timedelta(minutes=45)).strftime("%H:%M")
            hora_inicio_bloque2 = hora_fin
            hora_fin_bloque2 = (datetime.strptime(hora_inicio_bloque2, "%H:%M") + timedelta(minutes=45)).strftime("%H:%M")

            # Crear primer bloque
            data1 = {
                'dia': fake.day_of_week(),
                'hora_inicio': hora_inicio,
                'hora_fin': hora_fin,
                'profesor_id': profesor_id,
            }
            response1 = requests.post(f'{base_url}/horarios_disponibles', json=data1)
            print(f'Horario disponible creado: {response1.status_code} - {hora_inicio} a {hora_fin}')

            # Crear segundo bloque
            data2 = {
                'dia': fake.day_of_week(),
                'hora_inicio': hora_inicio_bloque2,
                'hora_fin': hora_fin_bloque2,
                'profesor_id': profesor_id,
            }
            response2 = requests.post(f'{base_url}/horarios_disponibles', json=data2)
            print(f'Horario disponible creado: {response2.status_code} - {hora_inicio_bloque2} a {hora_fin_bloque2}')

            bloques_creados += 1

# Crear profesor_materia asegurando que cada profesor tenga un máximo de 3 materias
def crear_profesor_materia(profesor_ids, materia_ids, num):
    if not materia_ids:
        print("No se crearon materias, abortando asignación de profesor a materia.")
        return
    
    # Diccionario para controlar cuántas materias tiene asignadas cada profesor
    materias_por_profesor = {profesor_id: 0 for profesor_id in profesor_ids}

    for _ in range(num):
        profesor_id = fake.random_element(profesor_ids)
        
        # Verificar si el profesor ya tiene asignadas 3 materias
        if materias_por_profesor[profesor_id] >= 3:
            continue  # Saltar a la siguiente iteración si ya tiene 3 materias
        
        # Asignar una materia
        materia_id = fake.random_element(materia_ids)
        data = {
            'profesor_id': profesor_id,
            'materia_id': materia_id,
            'experiencia': fake.random_int(min=1, max=10),
            'calificacion_alumno': fake.random_int(min=1, max=5),
        }
        response = requests.post(f'{base_url}/profesor_materia', json=data)
        
        if response.status_code == 201:
            materias_por_profesor[profesor_id] += 1  # Incrementar el conteo de materias para ese profesor
            print(f'Profesor-Materia creada: {response.status_code} para el profesor {profesor_id}')
        else:
            print(f'Error al crear Profesor-Materia: {response.status_code}')

# Generar datos
num_materias = 100
num_profesores = 100
num_salones = 100
num_horarios_por_profesor = 2  # Máximo 3 bloques de 2 consecutivos
num_profesor_materia = min(num_profesores * 3, num_materias)

# Llamar a las funciones para generar los datos
materias_ids = crear_materias(num_materias)
profesores_ids = crear_profesores(num_profesores)
salones_ids = crear_salones(num_salones)
crear_horarios_disponibles(profesores_ids, num_horarios_por_profesor)
crear_profesor_materia(profesores_ids, materias_ids, num_profesor_materia)
