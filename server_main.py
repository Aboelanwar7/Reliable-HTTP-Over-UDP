import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from src.application.http_server import HTTPServer
def main():
    HOST = '127.0.0.1'
    PORT = 8080

    # We set the document root to the current directory
    DOCUMENT_ROOT = os.path.join(current_dir, "www")

    server = HTTPServer(host=HOST, port=PORT, document_root=DOCUMENT_ROOT)

    try:
        server.run()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down gracefully...")
        sys.exit(0)

if __name__ == "__main__":
    main()