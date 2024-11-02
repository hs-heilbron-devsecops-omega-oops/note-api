# Step 1: Use a base image
FROM python:3.10.4

# Step 2: Set the working directory in the container
WORKDIR /note_api

# Step 3: Copy the application files into the container
COPY . /note_api

# Step 4: Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-dev.txt

# Step 5: Define the command to run the application
CMD ["python", "main.py"]
