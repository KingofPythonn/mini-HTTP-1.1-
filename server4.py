import os
import socket
import multiprocessing
import threading
from queue import Queue
from threading import Semaphore

# Configuration
HOST = '127.0.0.1'  # Localhost
PORT = 8080  # Port to listen on
STATIC_DIR = './static'  # Directory for static files
LOG_FILE = './server.log'
WORKER_COUNT = 4  # Number of worker processes
MAX_POST_REQUESTS = 5  # Maximum concurrent POST requests

# Create static directory if it doesn't exist
os.makedirs(STATIC_DIR, exist_ok=True)

# Semaphore for limiting POST requests
post_semaphore = Semaphore(MAX_POST_REQUESTS)

# Thread-safe log file writing
def log_request(request, response):
    with threading.Lock():
        with open(LOG_FILE, 'a') as log_file:
            log_file.write(f"Request:\n{request}\nResponse:\n{response}\n\n")

def handle_client(conn, addr):
    try:
        request = conn.recv(1024).decode('utf-8')
        headers = request.split('\r\n')
        if len(headers) < 1:
            return
        request_line = headers[0].split()

        if len(request_line) < 2:
            return

        method, path = request_line[0], request_line[1]
        if method == 'GET':
            serve_get(conn, path)
        elif method == 'POST':
            serve_post(conn, path, request)
        else:
            send_response(conn, "405 Method Not Allowed", "Method Not Allowed")
    finally:
        conn.close()

def serve_get(conn, path):
    file_path = os.path.join(STATIC_DIR, path.lstrip('/'))
    if os.path.isfile(file_path):
        with open(file_path, 'r') as file:
            content = file.read()
        send_response(conn, "200 OK", content)
    else:
        send_response(conn, "404 Not Found", "File Not Found")

def serve_post(conn, path, request):
    if not post_semaphore.acquire(blocking=False):
        send_response(conn, "503 Service Unavailable", "Too many POST requests")
        return

    try:
        body = request.split('\r\n\r\n', 1)[1]
        file_path = os.path.join(STATIC_DIR, path.lstrip('/'))

        def write_to_file(part):
            with open(file_path, 'a') as file:
                file.write(part)

        # Split body into parts and write concurrently
        threads = []
        for part in body.splitlines():
            thread = threading.Thread(target=write_to_file, args=(part,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        send_response(conn, "201 Created", "Resource Created")
    finally:
        post_semaphore.release()

def send_response(conn, status, body):
    response = f"HTTP/1.0 {status}\r\nContent-Length: {len(body)}\r\n\r\n{body}"
    conn.sendall(response.encode('utf-8'))
    log_request(status, body)

def worker_task(task_queue):
    while True:
        conn, addr = task_queue.get()
        if conn is None:
            break
        handle_client(conn, addr)

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"Server running on http://{HOST}:{PORT}")

    # Create a task queue for Round Robin scheduling
    task_queue = multiprocessing.Queue()

    # Create worker processes
    workers = []
    for _ in range(WORKER_COUNT):
        process = multiprocessing.Process(target=worker_task, args=(task_queue,))
        process.start()
        workers.append(process)

    try:
        while True:
            conn, addr = server_socket.accept()
            task_queue.put((conn, addr))
    finally:
        for _ in range(WORKER_COUNT):
            task_queue.put((None, None))  # Signal workers to exit
        for process in workers:
            process.join()
        server_socket.close()

if __name__ == "__main__":
    main()
