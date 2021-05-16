FROM python:3

WORKDIR /app

COPY requirements.txt ./
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY ginlong-wifi-mqtt.py ./

CMD ["/app/ginlong-wifi-mqtt.py", "-c", "/config/config.ini"]

ENTRYPOINT ["python"]
