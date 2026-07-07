import json
import os

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r') as json_file:
            data = json.load(json_file)
        return data
    else: 
        return None