# This is a simple test server for use with the Well-Architected labs
# It simulates an engine for recommending Movies for users
#
# This code is only for use in Well-Architected labs
# *** NOT FOR PRODUCTION USE ***
#

from http.server import BaseHTTPRequestHandler, HTTPServer
from functools import partial
import sys
import getopt
import random
import traceback
import json
import os

# HTML template with placeholders
HTML_TEMPLATE = ""
with open("static/index.html", "r") as f:
    HTML_TEMPLATE = f.read()

# CSS styles as a string
CSS_STYLES = ""
with open("static/styles.css", "r") as f:
    CSS_STYLES = f.read()

# JavaScript as a string
JAVASCRIPT = ""
with open("static/script.js", "r") as f:
    JAVASCRIPT = f.read()

# Mock data for recommendations
MOVIES = [
    {"title": "The Shawshank Redemption", "year": 1994, "genre": "Drama"},
    {"title": "The Godfather", "year": 1972, "genre": "Crime"},
    {"title": "The Dark Knight", "year": 2008, "genre": "Action"},
    {"title": "12 Angry Men", "year": 1957, "genre": "Drama"},
    {"title": "Schindler's List", "year": 1993, "genre": "Biography"},
    {"title": "The Lord of the Rings", "year": 2003, "genre": "Adventure"},
    {"title": "Pulp Fiction", "year": 1994, "genre": "Crime"},
    {"title": "The Good, the Bad and the Ugly", "year": 1966, "genre": "Western"}
]

USERS = [
    {"id": 1, "name": "Alice Johnson"},
    {"id": 2, "name": "Bob Smith"},
    {"id": 3, "name": "Charlie Brown"},
    {"id": 4, "name": "Diana Prince"}
]

# RequestHandler: Response depends on type of request made
class RequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_GET(self):
        print("path: ", self.path)

        # Main page
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            # Generate random user and movie recommendation
            user = random.choice(USERS)
            movie = random.choice(MOVIES)
            
            # Create metadata string
            metadata_html = f"""
            <p>Server Info: Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}</p>
            <p>Request Time: {self.date_time_string()}</p>
            <p>User ID: {user['id']}</p>
            """
            
            # Replace placeholders in HTML template
            html_content = HTML_TEMPLATE.replace("{USER_NAME}", user["name"])
            html_content = html_content.replace("{MOVIE_TITLE}", movie["title"])
            html_content = html_content.replace("{METADATA}", metadata_html)
            
            # Send the HTML response
            self.wfile.write(bytes(html_content, "utf-8"))
        
        # CSS file
        elif self.path == '/styles.css':
            self.send_response(200)
            self.send_header('Content-type', 'text/css')
            self.end_headers()
            self.wfile.write(bytes(CSS_STYLES, "utf-8"))
        
        # JavaScript file
        elif self.path == '/script.js':
            self.send_response(200)
            self.send_header('Content-type', 'application/javascript')
            self.end_headers()
            self.wfile.write(bytes(JAVASCRIPT, "utf-8"))
        
        # API endpoint for JSON data
        elif self.path == '/api/recommendations':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Generate random user and movie recommendation
            user = random.choice(USERS)
            movie = random.choice(MOVIES)
            
            response_data = {
                "user": user,
                "recommendation": movie,
                "timestamp": self.date_time_string()
            }
            
            self.wfile.write(bytes(json.dumps(response_data), "utf-8"))
        
        # Healthcheck endpoint
        elif self.path == '/healthcheck':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(bytes("OK", "utf-8"))
        
        # 404 for any other path
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(bytes("<html><body><h1>404 Not Found</h1></body></html>", "utf-8"))

# Initialize server
def run(argv):
    try:
        opts, args = getopt.getopt(
            argv,
            "hs:p:",
            [
                "help",
                "server_ip=",
                "server_port="
            ]
        )
    except getopt.GetoptError:
        print('server.py -s <server_ip> -p <server_port>')
        sys.exit(2)
    print(opts)

    # Default values
    server_port = 8000
    server_ip = '0.0.0.0'

    # Get commandline arguments
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print('server.py -s <server_ip> -p <server_port>')
            sys.exit()
        elif opt in ("-s", "--server_ip"):
            server_ip = arg
        elif opt in ("-p", "--server_port"):
            server_port = int(arg)

    # Start server
    print(f'Starting server on {server_ip}:{server_port}...')
    server_address = (server_ip, server_port)

    httpd = HTTPServer(server_address, RequestHandler)
    print('Server running. Press Ctrl+C to stop.')
    httpd.serve_forever()

if __name__ == "__main__":
    run(sys.argv[1:])
