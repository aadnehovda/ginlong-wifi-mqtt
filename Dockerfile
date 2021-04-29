FROM python:2

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ginlong-wifi-mqtt.py ./

CMD python ./ginlong-wifi-mqtt.py -c /config/config.ini
