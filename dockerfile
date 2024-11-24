# Use an official Python runtime as a parent image
FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg 

# Set the working directory in the container
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Make port 8001 available to the world outside this container
EXPOSE 8001
EXPOSE 7860

# Run the application
CMD ["gunicorn", "-c", "gunicorn_config.py", "main:app"]

# CMD ["python", "-u","ui.py"]