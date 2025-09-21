# Usar una imagen base oficial de Python (la versión completa, no la slim)
FROM python:3.10

# Instalar las dependencias del sistema operativo necesarias para CadQuery
# - build-essential: Para compilar paquetes.
# - libgl1-mesa-glx: Librería de OpenGL para renderizado (aunque no rendericemos visualmente, a veces es necesaria).
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1-mesa-glx \
    && apt-get clean

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar el archivo de dependencias e instalarlas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación
COPY . .

# Exponer el puerto
EXPOSE 80

# Comando para ejecutar la aplicación
CMD ["python", "app.py"]
