.PHONY: package

package:
        pyinstaller --onefile --add-data "frontend:frontend" run.py
