.PHONY: install lint test eval schema synth

install:
	pip install -e ".[dev]"

lint:
	ruff check .

test:
	pytest -q

eval:
	python scripts/eval.py

# Olay sozlesmesi JSON Schema'sini modelden yeniden uret (ROADMAP Faz 0).
schema:
	python -m kervansaray.events.export_schema

# Sentetik veri: populasyonu DB'ye yaz + olaylari ingest API'sine gonder.
synth:
	python scripts/synth.py --reset --seed-db --post http://localhost:8000
