import socket
import threading
import os

# تنظیمات سرور
HOST = '127.0.0.1'
PORT = 8080
MAX_POST_CONNECTIONS = 5
LOG_FILE = 'server.log'

# تابع برای نوشتن در فایل log
def log_request(request):
    with threading.Lock():  # قفل برای همگام‌سازی نوشتن در فایل log
        with open(LOG_FILE, 'a') as log_file:
            log_file.write(request + '\n')

# تابع برای پردازش درخواست GET
def handle_get(file_name, connection):
    try:
        with open(os.path.join('static', file_name), 'rb') as file:
            response_body = file.read()
            response_headers = (
                "HTTP/1.1 200 OK\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                "Connection: keep-alive\r\n"
                "Content-Type: text/plain\r\n\r\n"
            ).encode()
            connection.sendall(response_headers + response_body)
    except FileNotFoundError:
        response_body = b"File not found."
        response_headers = (
            "HTTP/1.1 404 Not Found\r\n"
            f"Content-Length: {len(response_body)}\r\n"
            "Connection: close\r\n"
            "Content-Type: text/plain\r\n\r\n"
        ).encode()
        connection.sendall(response_headers + response_body)
    log_request(f'GET {file_name}')

# تابع برای پردازش درخواست POST
def handle_post(connection, data):
    # محدودیت همزمانی برای POST
    with threading.Semaphore(MAX_POST_CONNECTIONS):
        file_name = 'data.txt'  # نام فایل برای ذخیره داده‌ها
        with open(os.path.join('static', file_name), 'a') as file:
            file.write(data + '\n')
        response_body = b"Data received."
        response_headers = (
            "HTTP/1.1 200 OK\r\n"
            f"Content-Length: {len(response_body)}\r\n"
            "Connection: keep-alive\r\n"
            "Content-Type: text/plain\r\n\r\n"
        ).encode()
        connection.sendall(response_headers + response_body)
        log_request(f'POST Data: {data}')

# تابع برای پردازش درخواست‌های کلاینت
def handle_client(connection):
    try:
        request = connection.recv(1024).decode()
        if request:
            request_line = request.splitlines()[0]
            method, path, _ = request_line.split()

            if method == 'GET':
                file_name = path.lstrip('/')  # حذف / از ابتدا
                handle_get(file_name, connection)
            elif method == 'POST':
                headers_body = request.split('\r\n\r\n')
                if len(headers_body) > 1:
                    data = headers_body[1]  # داده‌های POST را جدا کنید
                    handle_post(connection, data)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        connection.close()

# تابع اصلی برای راه‌اندازی سرور
def run_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # بازاستفاده از آدرس
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f'Server running on http://{HOST}:{PORT}')

    while True:
        client_connection, client_address = server_socket.accept()
        print(f'Connected by {client_address}')
        client_thread = threading.Thread(target=handle_client, args=(client_connection,))
        client_thread.start()

if __name__ == "__main__":
    run_server()
