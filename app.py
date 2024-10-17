from fastapi import FastAPI, Request
from pydantic import BaseModel
from datetime import datetime
import pandas as pd
import os

# Inicializar la aplicación FastAPI
app = FastAPI()

# Definir el nombre del archivo CSV
CSV_FILE = "datos_sensor.csv"

# Crear la estructura del modelo de datos
class SensorData(BaseModel):
    valor_sensor: int
    voltaje: float

# Ruta para recibir datos mediante POST
@app.post("/sensor")
async def recibir_datos(sensor_data: SensorData):
    # Obtener la fecha y hora actual del sistema
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Mostrar los datos recibidos y la fecha/hora en la consola
    print(f"Datos recibidos: {sensor_data}, Fecha y Hora: {fecha_hora}")

    # Crear un DataFrame con los datos recibidos
    data = {
        "fecha_hora": [fecha_hora],
        "valor_sensor": [sensor_data.valor_sensor],
        "voltaje": [sensor_data.voltaje],
    }
    df = pd.DataFrame(data)

    # Verificar si el archivo CSV ya existe
    if not os.path.isfile(CSV_FILE):
        df.to_csv(CSV_FILE, index=False)  # Crear el archivo CSV si no existe
    else:
        df.to_csv(CSV_FILE, mode='a', header=False, index=False)  # Añadir datos al archivo existente

    return {"status": "success", "message": "Datos almacenados correctamente"}

# Iniciar la aplicación con Uvicorn
# Ejecuta este comando: uvicorn app:app --reload --host 0.0.0.0 --port 8000
