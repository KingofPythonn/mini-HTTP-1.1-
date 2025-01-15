import os
import socket
import threading
from queue import Queue
from threading import Semaphore
from datetime import datetime

# Configuration
HOST = '127.0.0.1'
PORT = 8080
STATIC_DIR = './static'
LOG_FILE = './server.log'
WORKER_COUNT = 4
MAX_POST_REQUESTS = 5
REQUEST_TIMEOUT = 10  # Timeout in seconds for idle connections

# Create static directory if it doesn't exist
os.makedirs(STATIC_DIR, exist_ok=True)

# Semaphore for limiting POST requests
post_semaphore = Semaphore(MAX_POST_REQUESTS)

# Thread-safe log file writing
log_lock = threading.Lock()

def log_request(request, response):
    """Log the request and response to a file."""
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    with log_lock:
        with open(LOG_FILE, 'a') as log_file:
            log_file.write(f"[{timestamp}] Request:\n{request}\nResponse:\n{response}\n\n")

def parse_headers(header_lines):
    """Parse HTTP headers into a dictionary."""
    headers = {}
    for line in header_lines:
        if ': ' in line:
            key, value = line.split(': ', 1)
            headers[key.lower()] = value
    return headers



def send_response(conn, status, body, headers=None):
    """Send an HTTP response to the client and log it."""
    if headers is None:
        headers = {}
    headers['Content-Length'] = len(body)
    headers['Date'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    headers['Connection'] = 'keep-alive'

    header_lines = '\r\n'.join(f"{key}: {value}" for key, value in headers.items())
    response = f"HTTP/1.1 {status}\r\n{header_lines}\r\n\r\n{body}"
    conn.sendall(response.encode('utf-8'))

    # Log the response after sending it
    log_request(f"Response Status: {status}", body)



def handle_client(conn, addr):
    """Handle incoming client connections."""
    conn.settimeout(REQUEST_TIMEOUT)
    try:
        while True:
            request = conn.recv(1024).decode('utf-8')
            if not request:
                break

            # Parse request
            lines = request.split('\r\n')
            request_line = lines[0].split()
            if len(request_line) < 2:
                break

            method, path = request_line[0], request_line[1]
            headers = parse_headers(lines[1:])

            # Handle requests
            if method == 'GET':
                serve_get(conn, path, headers)
            elif method == 'POST':
                serve_post(conn, path, headers, request)
            else:
                send_response(conn, "405 Method Not Allowed", "Method Not Allowed")
                log_request(f"{method} {path}", "405 Method Not Allowed")
    except socket.timeout:
        print(f"Connection with {addr} timed out.")
    finally:
        conn.close()

def serve_get(conn, path, headers):
    """Handle GET requests."""
    file_path = os.path.join(STATIC_DIR, path.lstrip('/'))
    if os.path.isfile(file_path):
        with open(file_path, 'r') as file:
            content = file.read()
        send_response(conn, "200 OK", content)
        log_request(f"GET {path}", "200 OK")
    else:
        send_response(conn, "404 Not Found", "File Not Found")
        log_request(f"GET {path}", "404 Not Found")

def serve_post(conn, path, headers, request):
    """Handle POST requests."""
    if not post_semaphore.acquire(blocking=False):
        send_response(conn, "503 Service Unavailable", "Too many POST requests")
        log_request(f"POST {path}", "503 Service Unavailable")
        return

    try:
        # Extract body using Content-Length
        content_length = int(headers.get('content-length', 0))
        body = request.split('\r\n\r\n', 1)[1]
        if len(body) < content_length:
            body += conn.recv(content_length - len(body)).decode('utf-8')

        file_path = os.path.join(STATIC_DIR, path.lstrip('/'))
        with open(file_path, 'a') as file:
            file.write(body + '\n')

        send_response(conn, "201 Created", "Resource Created")
        log_request(f"POST {path} Body: {body}", "201 Created")
    finally:
        post_semaphore.release()

def main():
    """Main function to start the server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"Server running on http://{HOST}:{PORT}")

    try:
        while True:
            conn, addr = server_socket.accept()
            threading.Thread(target=handle_client, args=(conn, addr)).start()
    except KeyboardInterrupt:
        print("Shutting down the server...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()
