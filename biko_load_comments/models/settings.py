import yaml
import os

B24_URI = ''
RESULT_FILE = ''
SOURCE_FILE = ''
CHARSET = ''

relpath = os.path.dirname(os.path.realpath(__file__))
# get settings from YAML file
with open(relpath+'/settings.yaml', 'r', encoding='UTF_8') as yaml_file:
    objects = yaml.load(yaml_file, yaml.Loader)
    B24_URI = objects['B24_WEBHOOK'] if objects['B24_WEBHOOK'][-1] != '/' else objects['B24_WEBHOOK'][0:-1]
    RESULT_FILE = objects['RESULT_FILE']
    SOURCE_FILE = objects['SOURCE_FILE']
    CHARSET = objects['CHARSET']
