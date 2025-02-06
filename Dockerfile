# Utilizziamo una versione leggera di Python
FROM python:3.9-slim

# Impostiamo la directory di lavoro
WORKDIR /app

# Copiamo il file dei requisiti e installiamo le dipendenze
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copiamo il resto del codice dell'applicazione
COPY . .

# Impostiamo le variabili d'ambiente per Flask
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Esporremo la porta su cui gira l'app (default Flask: 5000)
EXPOSE 5000

# Comando di avvio dell'app
CMD ["flask", "run"]
