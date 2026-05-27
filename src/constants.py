import os

TRACKER_HOST = '127.0.0.1'
TRACKER_PORT = 5000

PEER_HOST = '127.0.0.1'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

SHARED_FOLDER = os.path.join(BASE_DIR, "shared")
DOWNLOAD_FOLDER = os.path.join(PROJECT_DIR, "downloads")

