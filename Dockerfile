# Usar una imagen base oficial de Python
FROM python3.10-slim

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR app

# Copiar el archivo de dependencias y luego instalarlas
# Esto aprovecha el cache de Docker para no reinstalar si no cambian
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación
COPY . .

# Exponer el puerto en el que la aplicación Flask se ejecutará
EXPOSE 80

# Comando para ejecutar la aplicación cuando el contenedor inicie
CMD [python, app.py]