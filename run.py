import socket
from backend import run as backend_run

def find_available_port(start_port=5000, max_tries=20):
    port = start_port
    for _ in range(max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("No available port found.")

if __name__ == '__main__':
    port = find_available_port(5000)
    print(f"Running on http://localhost:{port}")
    backend_run(port=port)
