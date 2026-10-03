FROM python:3.12-alpine

WORKDIR /app

COPY app.py .

RUN adduser -D -u 10001 appuser
USER 10001

ENV PORT=8080
EXPOSE 8080

CMD ["python", "app.py"]
