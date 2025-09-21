# Usar una imagen base oficial de Python (la versión completa, no la slim)
FROM python:3.10

# Instalar las dependencias del sistema operativo necesarias para CadQuery
# - build-essential: Para compilar paquetes.
# - libgl1: Librería de OpenGL para renderizado.
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar el archivo de dependencias e instalarlas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación
COPY . .

# Exponer el puerto
EXPOSE 80

# --- LÍNEA MODIFICADA ---
# Comando para ejecutar la aplicación con Gunicorn, AUMENTANDO EL TIMEOUT
CMD ["gunicorn", "--bind", "0.0.0.0:80", "--workers", "3", "--timeout", "120", "app:app"]
