#DockerFile
# Step 1: Use a base image

FROM python:3.10.4

# Step 2: Set the working directory in the container
WORKDIR /note_api

# Step 3: Copy only the requirements files first for better caching
COPY requirements.txt requirements-dev.txt ./
RUN python -m pip install --upgrade pip
# Step 4: Install production dependencies first
RUN pip install --no-cache-dir -r requirements.txt

# Step 5: Install development dependencies
RUN pip install --no-cache-dir -r requirements-dev.txt

# Step 6: Copy the rest of the application files into the container
COPY . .

EXPOSE 8080

# Step 7: Define the command to run the application
CMD ["uvicorn", "note_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
