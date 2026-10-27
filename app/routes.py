from app import app


@app.route("/")
def home():
    return {"message": "Budget Tracker API is running"}