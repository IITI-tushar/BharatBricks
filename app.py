from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {
        "project": "BharatBricks",
        "status": "Live",
        "message": "AI Civic Complaint System"
    }

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/stats")
def stats():
    return {
        "total_complaints": 5234,
        "resolved": 4102,
        "pending": 1132
    }
