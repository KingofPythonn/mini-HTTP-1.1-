import socket
import os
import multiprocessing

# تنظیمات سرور
HOST = '127.0.0.1'
PORT = 8080
NUM_WORKERS = 4

# تابع پردازش درخواست توسط پردازه‌های کارگر
def worker(worker_id, pipe):
    while True:
        connection = pipe.recv()  # دریافت کانکشن از پردازه اصلی
        try:
            request = connection.recv(1024).decode()
            if request:
                request_line = request.splitlines()[0]
                method, path, _ = request_line.split()
                
                if method == 'GET':
                    response = b"HTTP/1.1 200 OK\r\n\r\nWorker handled GET request"
                elif method == 'POST':
                    response = b"HTTP/1.1 200 OK\r\n\r\nWorker handled POST request"
                else:
                    response = b"HTTP/1.1 400 Bad Request\r\n\r\nUnsupported method"
                
                connection.sendall(response)
        except Exception as e:
            print(f"Worker {worker_id} error: {e}")
        finally:
            connection.close()

# تابع اصلی سرور
def run_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f'Server running on http://{HOST}:{PORT}')

    # ایجاد پردازه‌های کارگر و کانال ارتباطی (Pipe)
    worker_processes = []
    pipes = []
    for worker_id in range(NUM_WORKERS):
        parent_conn, child_conn = multiprocessing.Pipe()
        process = multiprocessing.Process(target=worker, args=(worker_id, child_conn))
        process.start()
        worker_processes.append(process)
        pipes.append(parent_conn)

    # زمان‌بندی Round Robin
    current_worker = 0

    try:
        while True:
            client_connection, client_address = server_socket.accept()
            print(f'Connected by {client_address}')

            # ارسال کانکشن به پردازه کارگر
            pipes[current_worker].send(client_connection)

            # انتخاب پردازه بعدی به صورت Round Robin
            current_worker = (current_worker + 1) % NUM_WORKERS
    except KeyboardInterrupt:
        print("Shutting down server...")
    finally:
        for process in worker_processes:
            process.terminate()
        server_socket.close()

if __name__ == "__main__":
    run_server()
