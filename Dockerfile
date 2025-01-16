#DockerFile

FROM python:3.10.4

WORKDIR /note_api

COPY requirements.txt requirements-dev.txt ./
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "note_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
