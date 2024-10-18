import requests
from faker import Faker

# Crear una instancia de Faker
fake = Faker()

# URL de tu API
base_url = 'http://localhost:8000/api'

# Crear materias
def crear_materias(num):
    materias_ids = []
    for _ in range(num):
        data = {
            'codigo': fake.word(),
            'nombre': fake.word(),
            'alumnos': fake.random_int(min=10, max=45),
            '': fake.random_int(min=10, max=45),
        }
        response = requests.post(f'{base_url}/materias', json=data)
        if response.status_code == 201:
            materias_ids.append(response.json()['id'])
            print(f'Materia creada: {data["nombre"]} - {response.status_code}')
        else:
            print(f"Error al crear materia: {response.status_code}, {response.text}")
    return materias_ids

# Generar 5 materias
num_materias = 5
materias_ids = crear_materias(num_materias)
