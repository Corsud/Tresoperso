from flask import Flask, send_from_directory
import webbrowser
import threading
import os

app = Flask(__name__, static_folder='../frontend', static_url_path='')

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


def open_browser():
    """Open the application homepage in the default web browser."""
    webbrowser.open_new('http://localhost:5000/')


def run():
    threading.Timer(1, open_browser).start()
    app.run()


if __name__ == '__main__':
    run()
