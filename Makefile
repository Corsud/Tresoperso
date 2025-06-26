.PHONY: package test

package:
	pyinstaller --onefile --add-data "frontend:frontend" run.py

test:
	pip install -r requirements-dev.txt
	pytest
