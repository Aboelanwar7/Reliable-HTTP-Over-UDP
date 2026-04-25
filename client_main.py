import sys
import os
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from src.application.http_client import HTTPClient

def main():
    SERVER_IP = '127.0.0.1'
    SERVER_PORT = 8080

    client = HTTPClient(server_ip=SERVER_IP, server_port=SERVER_PORT)

    print("Test 1: GET request to '/' (should return index.html by default)")
    client.send_request("GET", "/")
    time.sleep(1)
    print("Test 2: GET request to an existing file")
    client.send_request("GET", "/admin.html")
    time.sleep(1)
    print("Test 3: GET request to a non existing file")
    client.send_request("GET", "/does_not_exist.html")
    time.sleep(1)
    print("Test 4: POST request with body")
    client.send_request("POST", "/submit", body="user=youssef&password=2004")
    print("Test 5: Non existing method")
    client.send_request("PUT", "/submit", body="user=youssef&password=2004")

if __name__ == "__main__":
    main()