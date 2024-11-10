import json
import logging
import os
import os.path

logger = logging.getLogger('Config')

config = {}
mapping = {}

with open('data/config.json', 'r') as configFile:
    config = json.load(configFile)

with open('data/mapping.json', 'r') as mappingFile:
    mapping = json.load(mappingFile)

def persist_mapping():
    dumps = json.dumps(mapping, sort_keys=True, indent=4, separators=(',', ': '))
    with open('data/mapping.json', 'w+') as mappingFile:
        mappingFile.write(dumps)