"""Gunicorn giris noktasi:  gunicorn kervansaray.wsgi:app"""
from kervansaray.api import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
