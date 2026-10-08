from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI(
    title="DeployHub Control Plane API",
    description="Automated Self-Service Application Deployment Platform",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "name": "DeployHub Control Plane API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(
        "# HELP deployhub_up Indicates if DeployHub API is up\n"
        "# TYPE deployhub_up gauge\n"
        "deployhub_up 1\n"
    )

