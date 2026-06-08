# Use an official, lightweight Python base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy dependency definition and install packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the webhook app script
COPY app.py .

# Inform Docker that the container listens on port 8000
EXPOSE 80

# Execute the application when the container starts
CMD ["python", "app.py"]
