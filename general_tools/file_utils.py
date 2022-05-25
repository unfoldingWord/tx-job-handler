import json
import os
import zipfile
import shutil
import yaml
import tempfile
from glob import glob
from mimetypes import MimeTypes
from typing import Dict, List, Any, Optional, Union
from distutils.version import LooseVersion

from general_tools.data_utils import json_serial
from app_settings.app_settings import AppSettings


def unzip(source_file:str, destination_dir:str) -> None:
    """
    Unzips <source_file> into <destination_dir>.

    :param str source_file: The name of the file to read
    :param str destination_dir: The name of the directory to write the unzipped files

    NOTE: This is UNSAFE if the zipfile comes from an untrusted source
            as it may contain absolute paths outside of the desired folder.
        The zipfile should really be examined first.
    """
    with zipfile.ZipFile(source_file) as zf:
        zf.extractall(destination_dir)


def add_contents_to_zip(zip_file:str, path:str, include_root:bool=False) -> None:
    """
    Zip the contents of <path> into <zip_file>.

    :param str zip_file: The file name of the zip file
    :param str path: Full path of the directory to zip up
    :param bool include_root: If true, the zip file will start with the directory of the path parameter
    """
    path = path.rstrip(os.path.sep)
    if include_root:
        path_start_index = len(os.path.dirname(path))+1
    else:
        path_start_index = len(path)+1
    with zipfile.ZipFile(zip_file, 'a') as zf:
        for root, _dirs, files in os.walk(path):
            for f in files:
                file_path = os.path.join(root, f)
                zf.write(file_path, file_path[path_start_index:])


def add_file_to_zip(zip_file:str, file_name:str, arc_name:Optional[str]=None, compress_type:Optional[str]=None) -> None:
    """
    Zip <file_name> into <zip_file> as <arc_name>.

    :param str zip_file: The file name of the zip file
    :param str file_name: The name of the file to add, including the path
    :param str arc_name: The new name, with directories, of the file, the same as filename if not given
    :param str compress_type:
    """
    with zipfile.ZipFile(zip_file, 'a') as zf:
        zf.write(file_name, arc_name, compress_type)


def make_dir(dir_name:str, linux_mode:int=0o755, error_if_not_writable:bool=False) -> None:
    """
    Creates a directory, if it doesn't exist already.

    If the directory does exist, and <error_if_not_writable> is True,
    the directory will be checked for writability.

    :param str dir_name: The name of the directory to create
    :param int linux_mode: The mode/permissions to set for the new directory expressed as an octal integer (ex. 0o755)
    :param bool error_if_not_writable: The name of the file to read
    """
    if not os.path.exists(dir_name):
        os.makedirs(dir_name, linux_mode)
    elif error_if_not_writable:
        if not os.access(dir_name, os.R_OK | os.W_OK | os.X_OK):
            raise IOError(f"Directory {dir_name} is not writable.")


def load_json_object(file_name:str, default=None) -> Dict[str,Any]:
    """
    Deserialized JSON file <file_name> into a Python dict.
    :param str file_name: The name of the file to read
    :param default: The value to return if the file is not found
    """
    if not os.path.isfile(file_name):
        return default
    # return a deserialized object
    return json.loads(read_file(file_name))


def load_yaml_object(file_name:str, default=None) -> Dict[str,Any]:
    """
    Deserialized YAML file <file_name> into a Python dict.
    :param str file_name: The name of the file to read
    :param default: The value to return if the file is not found
    """
    if not os.path.isfile(file_name):
        return default
    # return a deserialized object
    # TODO: Check if full_load (less safe for untrusted input) is required
    #       See https://github.com/yaml/pyyaml/wiki/PyYAML-yaml.load(input)-Deprecation
    return yaml.safe_load(read_file(file_name))


def read_file(filepath:str, encoding:str='utf-8') -> str:
    """
    Read a UTF-8 text file,
        remove the optional BOM prefix,
        convert Windows line endings to Linux line endings,
        and remove the text
    """
    with open(filepath, 'r', encoding=encoding) as f:
        content = f.read()
    if content.startswith(chr(65279)): # U+FEFF or \ufeff
        AppSettings.logger.info(f"Detected Unicode Byte Order Marker (BOM) in {filepath}")
        content = content[1:] # remove (optional) BOM prefix
    content = content.replace('\r\n', '\n') # convert Windows line endings to Linux line endings
    return content
# end of read_file function


def write_file(filepath:str, file_contents:Union[str,Dict[str,Any]], indent=None) -> None:
    """
    Writes the <file_contents> to <filepath>.

    If <file_contents> is not a string, it is serialized as JSON.

    :param str filepath: The name of the file to write
    :param str|object file_contents: The string to write or the object to serialize
    :param int indent: Specify a value if you want the output formatted to be more easily readable
    """
    # Make sure the directory exists
    make_dir(os.path.dirname(filepath))

    if isinstance(file_contents, str):
        text_to_write = file_contents
    else:
        if os.path.splitext(filepath)[1] == '.yaml':
            text_to_write = yaml.safe_dump(file_contents)
        else:
            text_to_write = json.dumps(file_contents, sort_keys=True, indent=indent, default=json_serial)

    with open(filepath, 'wt', encoding='utf8') as out_file:
        out_file.write(text_to_write)


def get_mime_type(path:str) -> str:
    mime = MimeTypes()

    mime_type = mime.guess_type(path)[0]
    if not mime_type:
        mime_type = f'text/{os.path.splitext(path)[1][1:]}' # Skip past the period
    assert '.' not in mime_type
    return mime_type


def get_files(directory:str, relative_paths:bool=False, include_directories:bool=False,
                                topdown:bool=False, extensions=None, exclude=None) -> List[str]:
    file_list = []
    for root, dirs, files in os.walk(directory, topdown=topdown):
        if exclude and (os.path.basename(root) in exclude or os.path.basename(root).lower() in exclude):
            continue
        if relative_paths:
            path = root[len(directory)+1:]
        else:
            path = root
        for filename in files:
            if (not exclude or (filename not in exclude and filename.lower() not in exclude)) and \
                    (not extensions or os.path.splitext(filename)[1] in extensions
                     or os.path.splitext(filename)[1].lower() in extensions):
                file_list.append(os.path.join(path, filename))
        if include_directories:
            for dir_name in dirs:
                file_list.append(os.path.join(path, dir_name))
    return file_list


def get_subdirs(dir:str, relative_paths:bool=False, topdown:bool=False) -> List[str]:
    dir_list = []
    for root, dirs, _files in os.walk(dir, topdown=topdown):
        if relative_paths:
            path = os.path.relpath(root, dir)
        else:
            path = root
        for dirname in dirs:
            dir_list.append(os.path.join(path, dirname))
    return dir_list


def copy_tree(src:str, dst:str, symlinks:bool=False, ignore=None) -> None:
    """
    Recursively copy a directory and all subdirectories.

    Parameters same as shutil.copytree

    :param src:
    :param dst:
    :param symlinks:
    :param ignore:
    :return:
    """
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copy_tree(s, d, symlinks, ignore)
        else:
            # only replace file if modified
            if not os.path.exists(d) or os.stat(s).st_mtime - os.stat(d).st_mtime > 1:
                shutil.copy2(s, d)


def remove_tree(dir_path:str, ignore_errors:bool=True) -> None:
    # Following line deleted by RJH coz we want to know if there's a programming error
    # if os.path.isdir(dir_path):
    shutil.rmtree(dir_path, ignore_errors=ignore_errors)


def remove_file(file_path:str, ignore_errors:bool=True) -> None:
    if ignore_errors:
        try:
            os.remove(file_path)
        except OSError:
            pass
    else:
        os.remove(file_path)


def empty_folder(folder_path:str, only_prefix:Optional[str]=None) -> None:
    for filename in os.listdir(folder_path):
        if not only_prefix or filename.startswith(only_prefix):
            filepath = os.path.join(folder_path, filename)
            try:
                shutil.rmtree(filepath)
            except OSError:
                os.remove(filepath)


def symlink(target, link_name, overwrite=False):
    """
    Create a symbolic link named link_name pointing to target.
    If link_name exists then FileExistsError is raised, unless overwrite=True.
    When trying to overwrite a directory, IsADirectoryError is raised.
    """
    if not overwrite:
        if not os.path.exists(link_name):
            os.symlink(target, link_name)
        return

    # os.replace() may fail if files are on different filesystems
    link_dir = os.path.dirname(link_name)

    # Create link to target with temporary filename
    while True:
        temp_link_name = tempfile.mktemp(dir=link_dir)

        # os.* functions mimic as closely as possible system functions
        # The POSIX symlink() returns EEXIST if link_name already exists
        # https://pubs.opengroup.org/onlinepubs/9699919799/functions/symlink.html
        try:
            os.symlink(target, temp_link_name)
            break
        except FileExistsError:
            pass

    # Replace link_name with temp_link_name
    try:
        # Pre-empt os.replace on a directory with a nicer message
        if os.path.isdir(link_name):
            raise IsADirectoryError(f"Cannot symlink over existing directory: '{link_name}'")
        os.replace(temp_link_name, link_name)
    except Exception:
        if os.path.islink(temp_link_name):
            os.remove(temp_link_name)
        raise


def get_latest_version_path(parent_path):
    version = get_latest_version(parent_path)
    if version:
        return os.path.join(parent_path, version)
    else:
        return None


def get_latest_version(parent_path):
    versions = get_versions(parent_path)
    if len(versions):
        return versions[-1]
    else:
        return None


def get_versions(parent_path):
    versions = get_child_directories(parent_path, 'v[0-9]*')
    versions.sort(key=LooseVersion)
    return versions


def get_child_directories(parent_path, mask='*'):
    child_paths = glob(os.path.join(parent_path, mask))
    child_dirs = [os.path.basename(child_path) for child_path in child_paths if os.path.isdir(child_path)]
    return child_dirs

