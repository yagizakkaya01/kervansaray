"""Gunicorn giris noktasi:  gunicorn kervansaray.wsgi:app"""
from kervansaray.api import create_app

app = create_app()
