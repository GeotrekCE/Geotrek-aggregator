import argparse
import os
import sys
import json
import re
import shutil
from distutils.dir_util import copy_tree
from jsonmerge import Merger


schema = {
    "properties": {
        "features": {
            "mergeStrategy": "append"
        }
    }
}
merger = Merger(schema)


def transform_id(previous_dict, key, obj, i, lang):
    if key and key == 'themes':
        themes = previous_dict.get('themes')
        for element in obj:
            element['id'] = element['id'] * 100 + i
            fix_mapping_themes(element, lang)
            if obj['id'] in themes:
                themes.remove(obj)
    elif isinstance(obj, dict):
        if "id" in obj:
            if isinstance(obj['id'], int):
                obj['id'] = obj['id'] * 100 + i

            else:
                if not 'E' in obj['id']:
                    add_id = str(i).zfill(2)
                    obj['id'] = obj['id'] + add_id
                    fix_mapping(obj, lang)

        if "category_id" in obj:
            if not 'E' in obj['category_id']:
                add_id = str(i).zfill(2)
                obj['category_id'] = obj['category_id'] + add_id
                fix_mapping(obj, lang)

        for key, value in obj.items():
            transform_id(obj, key, value, i, lang)
    elif isinstance(obj, (list, tuple)):
        for n, element in enumerate(obj):
            transform_id(None, None, element, i, lang)


def fix_mapping(obj, lang):
    for key, value in json_mapping[lang].items():
        try:
            if obj['id'] in value['matches']:
                obj['label'] = key
                obj['id'] = value['id']
                obj['pictogram'] = value['pictogram']
                if "C" in obj['id']:
                    obj["type1_label"] = value["type1_label"]
                    obj["type2_label"] = value["type2_label"]
                break
            if obj['category_id'] in value['matches']:
                obj['category_id'] = value['id']
                break
        except KeyError as e:
            pass


def fix_mapping_themes(obj, lang):
    for key, value in json_mapping[lang].items():
        try:
            if 'THEME{}'.format(obj['id']) in value['matches']:
                obj['label'] = key
                obj['id'] = value['id']
                obj['pictogram'] = value['pictogram']
        except KeyError:
            pass


def transform_file_string(obj, i, lang):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str):
                reg_api = re.search('api/{lang}/'.format(lang=lang), value)
                reg_paperclip_1 = re.search('/paperclip/get/', value)
                reg_paperclip_2 = re.search('/media/paperclip/', value)
                reg_image = re.search('/image/', value)
                add_id = str(i).zfill(2)
                if reg_api or reg_paperclip_1 or reg_paperclip_2:
                    obj[key] = re.sub('/([0-9]+)/', '/\\g<1>{}/'.format(add_id), value)
                if reg_image:
                    obj[key] = re.sub('-([0-9]+)', '-\\g<1>{}'.format(add_id), value)
            transform_file_string(value, i, lang)
    elif isinstance(obj, (list, tuple)):
        for element in obj:
            transform_file_string(element, i, lang)


def open_files_api(lang, initial_directory, file_name, extent):
    file_path = os.path.join(initial_directory, 'api', lang, '.'.join((file_name, extent)))
    if os.path.exists(file_path):
        with open(file_path) as f:
            return json.load(f)


def mkdirs(name):
    dirname = os.path.dirname(name)
    if not os.path.exists(dirname):
        os.makedirs(dirname)


def write_files_new_place(initial_directory, directory_api, filename, target_directory, id, data):
    file_path_before = os.path.join(directory_api, filename)
    file_place_in = directory_api.replace(initial_directory, '')
    add_id = str(id).zfill(2)
    f_place_in_after = re.sub('/([0-9]+)', '/\\g<1>{}'.format(add_id), file_place_in)

    file_path_after = os.path.join(target_directory, f_place_in_after[1:], filename)
    mkdirs(file_path_after)

    if isinstance(data, (list, tuple, dict)):
        if not os.path.exists(file_path_after):
            f = open(file_path_after, "w+")
            dump = json.dumps(data)
            f.write(dump)
            f.close()
        else:
            result = None
            with open(file_path_after) as f:
                data_2 = json.load(f)
            if isinstance(data_2, (list, tuple)) and isinstance(data, (list, tuple)):
                data.extend(data_2)
                result = data
            elif isinstance(data_2, dict) and isinstance(data, dict):
                result = merger.merge(data, data_2)
            elif data_2:
                result = data_2
            if result:
                with open(file_path_after, "w+"):
                    f = open(file_path_after, "w+")
                    dump = json.dumps(result)
                    f.write(dump)
                    f.close()
    else:
        shutil.copy(file_path_before, file_path_after)


parser = argparse.ArgumentParser()
parser.add_argument("directories", help="Give the directory of each sync_rando folders", nargs="*")
parser.add_argument("--langs", "-l", dest= 'langs', help="Lang of your projects", nargs="*")
parser.add_argument("--target", "-t", help="Give the target directory")
parser.add_argument("--mapping", "-p", help="Json of mapping", default=os.path.join(os.path.dirname(__file__),
                                                                                    'mapping.json'))
parser.add_argument("-v", "--verbosity", action="count", default=0)

args = parser.parse_args()

with open(args.mapping) as f:
    json_mapping = json.load(f)

if args.verbosity >= 2:
    sys.stdout.write("Running '{}'".format(__file__))

for i, initial_directory in enumerate(args.directories):
    for lang in args.langs:
        for root, dirs, files in os.walk(os.path.join(initial_directory, 'api', lang)):
            for file in files:
                if file.endswith(".geojson") or file.endswith(".json"):
                    with open(os.path.join(root, file)) as f:
                        data = json.load(f)
                        transform_id(None, None, data, i, lang)
                        transform_file_string(data, i, lang)
                    if data:
                        write_files_new_place(initial_directory, root, file, args.target, i, data)
                else:
                    write_files_new_place(initial_directory, root, file, args.target, i, None)
    for root, dirs, files in os.walk(os.path.join(initial_directory, 'media')):
        for file in files:
            write_files_new_place(initial_directory, root, file, args.target, i, None)
    copy_tree(os.path.join(initial_directory, 'static'), os.path.join(args.target, 'static'))
