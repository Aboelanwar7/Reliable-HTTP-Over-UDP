import urllib.parse

class HTTPMessage:
    def __init__(self,):
        self.method = None
        self.path = None
        self.query_params = {}
        self.version = "HTTP/1.0"
        self.status_code = None
        self.status_phrase = None
        self.headers = {}
        self.body = None

class HTTPParser:
    MIME_TYPES = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".mp4": "video/mp4",
        ".txt": "text/plain",
    }

    @staticmethod
    def get_mime_type(file_path):
        """Returns the correct Content-Type based on the file extension."""
        import os
        _, ext = os.path.splitext(file_path)
        # Default to binary stream if extension is unknown
        return HTTPParser.MIME_TYPES.get(ext.lower(), "application/octet-stream")

    @staticmethod
    def build_request(method, path, body="", headers=None):
        """Constructs a raw HTTP/1.0 request string."""
        if headers is None:
            headers = {}

        request = f"{method} {path} HTTP/1.0\r\n"

        if body and "Content-Length" not in headers:
            headers["Content-Length"] = str(len(body.encode('utf-8')))

        for key, value in headers.items():
            request += f"{key}: {value}\r\n"

        request += "\r\n" + body
        return request.encode('utf-8')

    @staticmethod
    def build_response(status_code, status_phrase, body="", headers=None):
        """Constructs a raw HTTP/1.0 response string."""
        if headers is None:
            headers = {}

        # If the body is a standard text string, encode to bytes
        if isinstance(body, str):
            body = body.encode('utf-8')

        if body and "Content-Length" not in headers:
            headers["Content-Length"] = str(len(body))

        # Default to HTML if no content type is provided
        if "Content-Type" not in headers:
            headers["Content-Type"] = "text/html"

        response_headers = f"HTTP/1.0 {status_code} {status_phrase}\r\n"

        for key, value in headers.items():
            response_headers += f"{key}: {value}\r\n"

        response_headers += "\r\n"
        return response_headers.encode('utf-8') + body

    @staticmethod
    def parse(raw_data):
        """Parses a raw HTTP string into an HTTPMessage object."""
        # Ensure we are working with a string
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode('utf-8', errors='ignore')

        # HTTP headers and body are separated by a double CRLF
        parts = raw_data.split("\r\n\r\n", 1)
        header_section = parts[0]
        body = parts[1] if len(parts) > 1 else ""

        lines = header_section.split("\r\n")
        start_line = lines[0].split(" ")

        msg = HTTPMessage()
        msg.body = body

        # Check if it's a Request or Response
        if start_line[0].startswith("HTTP"):
            # It's a Response
            msg.version = start_line[0]
            msg.status_code = int(start_line[1])
            msg.status_phrase = " ".join(start_line[2:])
        else:
            # It's a Request
            msg.method = start_line[0]
            raw_url = start_line[1]
            msg.version = start_line[2]

        parsed_url = urllib.parse.urlparse(raw_url)
        msg.path = parsed_url.path
        msg.query_params = urllib.parse.parse_qs(parsed_url.query)
        
        # Parse Headers
        for line in lines[1:]:
            if ": " in line:
                key, value = line.split(": ", 1)
                msg.headers[key] = value

        return msg