FROM python:3.12-slim

WORKDIR /app

COPY tracker.py protocol.py constants.py ./

RUN mkdir -p shared downloads peer_state partial_chunks

EXPOSE 5000
EXPOSE 8000

CMD ["python", "tracker.py", \
     "--host", "0.0.0.0", \
     "--port", "5000", \
     "--api-host", "0.0.0.0", \
     "--api-port", "8000"]