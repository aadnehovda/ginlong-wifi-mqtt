FROM python:2

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY config.ini ginlong-wifi-mqtt.py ./

CMD [ "python", "./ginlong-wifi-mqtt.py" ]
