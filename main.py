from fastapi import FastAPI

app = FastAPI(title="CodeAtlas API")


@app.get("/")
def home():
    return {"message": "CodeAtlas backend running"}


@app.get("/health")
def health():
    return {"status":"ok"}