# Stage 1: Build the React Frontend
FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

# Copy all frontend files
COPY frontend/ ./
# Build the production optimized static site to frontend/dist
RUN npm run build


# Stage 2: Build the Python Backend
FROM python:3.11-slim

# Prevent python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy minimum python requirements first to cache dependency installations
COPY requirements.txt .
# Install everything (including fastapi + uvicorn added to the top-level env) 
RUN pip install --no-cache-dir -r requirements.txt fastapi uvicorn python-dotenv

# Copy the rest of the python backend framework
COPY . .

# Copy the compiled React assets from Stage 1 into the unified directory
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Expose the API and UI port
EXPOSE 8000

# Start Uvicorn pointing at server.py
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
