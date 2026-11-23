# ---------------------------------------------------------------
# Imagen del sistema web Dino Park (Flask + Waitress)
# ---------------------------------------------------------------
# 1) Imagen base: Python 3.12 en versión ligera (slim)
FROM python:3.12-slim

# 2) Ajustes de Python dentro del contenedor
#    - no generar archivos .pyc
#    - mostrar los print/logs al instante
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PUERTO=8000

# 3) Carpeta de trabajo dentro del contenedor
WORKDIR /app

# 4) Instalar dependencias primero (Docker las guarda en caché y
#    no las reinstala si solo cambias el código)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5) Copiar el resto del proyecto
COPY . .

# 6) Crear un usuario sin privilegios y la carpeta de comprobantes
RUN useradd --create-home dino \
    && mkdir -p /app/uploads/comprobantes \
    && chown -R dino:dino /app
USER dino

# 7) Puerto en el que escucha Waitress
EXPOSE 8000

# 8) Comando de arranque (servidor de producción)
CMD ["python", "servidor.py"]
