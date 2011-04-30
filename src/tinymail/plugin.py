import sys
import os.path
import json
import logging

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def load_plugins(configuration):
    plugins_path = os.path.join(configuration.home, 'plugins')

    for folder_name in os.listdir(plugins_path):
        folder_path = os.path.join(plugins_path, folder_name)
        sys.path.append(folder_path)

        with open(os.path.join(folder_path, 'manifest.json'), 'rb') as f:
            plugin_manifest = json.loads(f.read())

        plugin_name = plugin_manifest['name']

        module_name, func_name = plugin_manifest['init'].split(':')
        exec('from %s import %s as init; init()' % (module_name, func_name))

        log.info("Plugin loaded: %s", plugin_name)
