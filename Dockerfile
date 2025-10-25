FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY frontend ./frontend
COPY mock_assets ./mock_assets
ENV PORT=7860
ENV FRONT_DIR=/app/frontend
EXPOSE 7860
CMD ["uvicorn", "backend.entry:app", "--host", "0.0.0.0", "--port", "7860"]
