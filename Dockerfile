# Use the official Python image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy your app code to the container
COPY app.py .
COPY linkedin_scraper.py .
COPY .env .
COPY requirements.txt .

# Install system dependencies (like git)
RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Streamlit port
EXPOSE 8501

# Run Streamlit app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
