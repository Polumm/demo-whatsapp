FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8001

# Use Uvicorn for better performance
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
