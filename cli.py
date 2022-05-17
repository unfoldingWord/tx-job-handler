#!/usr/bin/env python3
#
#  Copyright (c) 2021 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
# TX WEBHOOK
#
# NOTE: This module name and function name are defined by the rq package and our own tx-enqueue-job package
# This code adapted by RJH June 2018 from tx-manager/client_webhook/ClientWebhook/process_webhook

# NOTE: rq_settings.py is executed at program start-up, reads some environment variables, and sets queue name, etc.
#       job() function (at bottom here) is executed by rq package when there is an available entry in the named queue.

# Python imports
from typing import Dict, Tuple, Any, Optional, Type
import os
import sys
import argparse
import traceback
import tempfile
from glob import glob

# Local imports
from rq_settings import prefix, debug_mode_flag
from general_tools.file_utils import unzip, remove_tree
from general_tools.url_utils import download_file
from app_settings.app_settings import AppSettings
from door43_tools.bible_books import BOOK_NUMBERS

from converters.converter import Converter

from door43_tools.subjects import SUBJECT_ALIASES
from door43_tools.subjects import ALIGNED_BIBLE, BIBLE, OPEN_BIBLE_STORIES, OBS_STUDY_NOTES, OBS_STUDY_QUESTIONS, \
    OBS_TRANSLATION_NOTES, TRANSLATION_ACADEMY, TRANSLATION_WORDS, TRANSLATION_QUESTIONS, TSV_STUDY_NOTES, \
    TSV_STUDY_QUESTIONS, TSV_TRANSLATION_NOTES, OBS_TRANSLATION_QUESTIONS
from converters.pdf.aligned_bible_pdf_converter import AlignedBiblePdfConverter
from converters.pdf.bible_pdf_converter import BiblePdfConverter
from converters.pdf.obs_pdf_converter import ObsPdfConverter
from converters.pdf.obs_sn_pdf_converter import ObsSnPdfConverter
from converters.pdf.obs_sq_pdf_converter import ObsSqPdfConverter
from converters.pdf.obs_tn_pdf_converter import ObsTnPdfConverter
from converters.pdf.obs_tq_pdf_converter import ObsTqPdfConverter
from converters.pdf.sn_pdf_converter import SnPdfConverter
from converters.pdf.sq_pdf_converter import SqPdfConverter
from converters.pdf.ta_pdf_converter import TaPdfConverter
from converters.pdf.tn_pdf_converter import TnPdfConverter
from converters.pdf.tq_pdf_converter import TqPdfConverter
from converters.pdf.tw_pdf_converter import TwPdfConverter

sys.setrecursionlimit(1500) # Default is 1,000—beautifulSoup hits this limit with UST


# Columns are: 1/ converter name 2/ converter 3/ input formats 4/ resource types 5/ output format
CONVERTER_TABLE = (
    (ALIGNED_BIBLE,             AlignedBiblePdfConverter, ('usfm'),                          SUBJECT_ALIASES[ALIGNED_BIBLE], 'pdf'),
    (BIBLE,                     BiblePdfConverter,        ('usfm'),                          SUBJECT_ALIASES[BIBLE], 'pdf'),
    (OPEN_BIBLE_STORIES,        ObsPdfConverter,     ('md','markdown','txt','text'), SUBJECT_ALIASES[OPEN_BIBLE_STORIES], 'pdf'),
    (OBS_STUDY_NOTES,           ObsSnPdfConverter,   ('md', 'markdown', 'txt', 'text'), SUBJECT_ALIASES[OBS_STUDY_NOTES], 'pdf'),
    (OBS_STUDY_QUESTIONS,       ObsSqPdfConverter,   ('md','markdown','txt','text'), SUBJECT_ALIASES[OBS_STUDY_QUESTIONS], 'pdf'),
    (OBS_TRANSLATION_NOTES,     ObsTnPdfConverter,   ('md','markdown','txt','text'), SUBJECT_ALIASES[OBS_TRANSLATION_NOTES], 'pdf'),
    (OBS_TRANSLATION_QUESTIONS, ObsTqPdfConverter,   ('md','markdown','txt','text'), SUBJECT_ALIASES[OBS_TRANSLATION_QUESTIONS], 'pdf'),
    (TRANSLATION_ACADEMY,       TaPdfConverter,      ('md','markdown','txt','text'), SUBJECT_ALIASES[TRANSLATION_ACADEMY], 'pdf'),
    (TSV_STUDY_NOTES,           SnPdfConverter,      ('tsv'),                    SUBJECT_ALIASES[TSV_STUDY_NOTES], 'pdf'),
    (TSV_STUDY_QUESTIONS,       SqPdfConverter,      ('tsv'),         SUBJECT_ALIASES[TSV_STUDY_QUESTIONS], 'pdf'),
    (TSV_TRANSLATION_NOTES,     TnPdfConverter,      ('tsv'),         SUBJECT_ALIASES[TSV_TRANSLATION_NOTES], 'pdf'),
    (TRANSLATION_QUESTIONS,     TqPdfConverter,      ('md','markdown','txt','text'), SUBJECT_ALIASES[TRANSLATION_QUESTIONS], 'pdf'),
    (TRANSLATION_WORDS,         TwPdfConverter,      ('md','markdown','txt','text'), SUBJECT_ALIASES[TRANSLATION_WORDS], 'pdf'),
    )

if prefix not in ('', 'dev-'):
    AppSettings.logger.critical(f"Unexpected prefix: '{prefix}' — expected '' or 'dev-'")
AppSettings(prefix=prefix)


def get_converter_module(subject) -> Tuple[Optional[str],Any]:
    for converter_name, converter_class, input_formats, resource_types, output_format in CONVERTER_TABLE:
        if subject == converter_name:
            return converter_name, converter_class
    # Didn't find one
    return None, None
# end if get_converter_module function


def do_converting(param_dict, source_dir:str, converter_name:str, converter_class:Type[Converter]) -> None:
    """
    :param dict param_dict: Will be updated for build log!
    :param str source_dir: Directory of the download source files
    :param str converter_name: Name of the converter
    :param class converter_class: Class of the converter
    Updates param_dict as a side-effect.
    """
    AppSettings.logger.debug(f"do_converting( {len(param_dict)} fields, {source_dir}, {converter_name}, {converter_class} )")

    if 'cdn.door43.org/' in param_dict['output']:
        cdn_file_key = param_dict['output'].split('cdn.door43.org/')[1]  # Get the last part
    else:
        cdn_file_key = param_dict['output']
    converter = converter_class(param_dict['resource_type'],
                                source_dir=source_dir,
                                source_url=param_dict['source'],
                                cdn_file_key=cdn_file_key,  # Key for uploading
                                identifier=param_dict['identifier'],
                                options={'debug_mode_flag': debug_mode_flag})
    convert_result_dict = converter.run()
    converter.close() # do cleanup after run
    param_dict['converter_success'] = convert_result_dict['success']
    param_dict['converter_info'] = convert_result_dict['info']
    param_dict['converter_warnings'] = convert_result_dict['warnings']
    param_dict['converter_errors'] = convert_result_dict['errors']
    param_dict['status'] = 'converted'
# end of do_converting function


def download_source_file(source_url, destination_folder):
    """
    Downloads the specified source file
        and unzips it if necessary.

    :param str source_url: The URL of the file to download
    :param str destination_folder:   The directory where the downloaded file should be unzipped
    :return: None
    """
    AppSettings.logger.debug(f"download_source_file( {source_url}, {destination_folder} )")
    source_filepath = os.path.join(destination_folder, source_url.rpartition(os.path.sep)[2])
    AppSettings.logger.debug(f"source_filepath: {source_filepath}")

    try:
        AppSettings.logger.info(f"Downloading {source_url} …")

        # if the file already exists, remove it, we want a fresh copy
        if os.path.isfile(source_filepath):
            os.remove(source_filepath)

        download_file(source_url, source_filepath)
    finally:
        AppSettings.logger.debug("Downloading finished.")

    if source_url.lower().endswith('.zip'):
        try:
            AppSettings.logger.debug(f"Unzipping {source_filepath} …")
            # TODO: This is unsafe if the zipfile comes from an untrusted source
            unzip(source_filepath, destination_folder)
        finally:
            AppSettings.logger.debug("Unzipping finished.")

        # clean up the downloaded zip file
        if os.path.isfile(source_filepath):
            os.remove(source_filepath)

    str_filelist = str(os.listdir(destination_folder))
    str_filelist_adjusted = str_filelist if len(str_filelist)<1500 \
                            else f'{str_filelist[:1000]} …… {str_filelist[-500:]}'
    AppSettings.logger.debug(f"Destination folder '{destination_folder}' now has: {str_filelist_adjusted}")
    return os.path.join(destination_folder, str_filelist_adjusted)
#end of download_source_file function


def process_pdfs(pj_prefix, langs=None, subjects=None, owners=None, repos=None, project_ids=None, stage=None,
                 regenerate=None, working_dir=None, tags=None, dcs_domain='https://git.door43.org', debug=True):
    AppSettings.logger.info(f"PROCESSING {pj_prefix+' ' if pj_prefix else ''}obs_helps: {subjects} {langs}")

    # stage = 'latest'
    # langs = ['en']
    # repos = ['en_obs']
    # owners = ['Door43-Catalog']
    debug = True

    items = []

    if stage:
        response = AppSettings.catalog_client.catalog_search(subject=subjects, owner=owners, repo=repos, lang=langs, tag=tags, stage=stage)
        if not response or not response.ok or len(response.data):
            AppSettings.logger.error(f'No entries found.')
            exit(1)
        items = response.data
    else:
        if repos:
            langs = None
            subjects = None
        response = AppSettings.repo_client.repo_search(langs=langs, subjects=subjects, owners=owners, repos=repos, books=project_ids)
        if 'ok' not in response or 'data' not in response or not len(response['data']):
            AppSettings.logger.error(f'No entries for {subjects}')
            exit(1)
        for repo in response['data']:
            tag = tags[0] if tags else 'master'
            item = {
                'repo': repo,
                'branch_or_tag_name': tag,
                'zipball_url': f"{repo['html_url']}/archive/{tag}.zip",
            }
            items.append(item)

    tempfile.tempdir = os.path.join('/tmp', 'working')
    if working_dir:
        tempfile.tempdir = working_dir

    AppSettings.logger.info("TO BE GENERATED:")

    for item in items:
        repo = item['repo']
        AppSettings.logger.info(f"  lang:{repo['language']} :: subject:{repo['subject']} :: owner:{repo['owner']['username']} :: item:{repo['name']}")

        # Setup a temp folder to use
        # Move everything down one directory level for simple delete
        outdir = os.path.join(repo['owner']['username'], repo['language'], repo['name'].split('_')[1])
        base_temp_dir_name = os.path.join(tempfile.tempdir, outdir)
        output_dir = os.path.join(base_temp_dir_name, 'Output')
        pdfs = glob(os.path.join(output_dir, '*.pdf'))
        if len(pdfs) > 0 and regenerate != 'all':
            if regenerate == 'none':
                continue
            reply = str(input(f"{pdfs[0]} exists. Generate PDF anyway? " + ' (y/N/all/none): ')).lower().strip()
            if not reply or reply[0] != 'y' and reply != 'all':
                if reply == 'none':
                    regenerate = 'none'
                continue
            if reply == 'all':
                regenerate = 'all'
        os.makedirs(base_temp_dir_name, exist_ok=True)
        AppSettings.logger.debug(f"base_temp_dir_name = {base_temp_dir_name}")

        # Download and unzip the specified source file
        AppSettings.logger.debug(f"Getting source file from {item['zipball_url']} …")
        zipball_url = item['zipball_url']
        download_source_file(zipball_url, base_temp_dir_name)

        # Find correct source folder
        source_folder_path = os.path.join(base_temp_dir_name, repo['name'])

        converter_name, converter = get_converter_module(repo['subject'])
        AppSettings.logger.info(f"Got converter = {converter_name}")
        build_log_dict = {
            'resource_type': repo['subject'],
            'identifier': f"{repo['owner']['username']}--{repo['name']}--{item['branch_or_tag_name']}",
            'output': os.path.join(tempfile.tempdir, outdir, f"{repo['name']}-item['branch_or_tag_name].zip"),
            'source': item['zipball_url']
        }

        if converter:
            build_log_dict['status'] = 'converting'
            build_log_dict['message'] = 'tX job converting…'
            build_log_dict['convert_module'] = converter_name
            do_converting(build_log_dict, source_folder_path, converter_name, converter)
        else:
            error_message = f"No converter was found to convert {repo['subject']}"
            AppSettings.logger.error(error_message)
            build_log_dict['convert_module'] = 'NO CONVERTER'
            build_log_dict['converter_success'] = 'false'
            build_log_dict['converter_info'] = []
            build_log_dict['converter_warnings'] = []
            build_log_dict['converter_errors'] = [error_message]

        build_log_dict['status'] = 'finished'

        if prefix and debug_mode_flag:
            AppSettings.logger.debug(f"Temp folder '{base_temp_dir_name}' has been left on disk for debugging!")
        else:
            remove_tree(base_temp_dir_name)  # cleanup
        str_build_log = str(build_log_dict)
        str_build_log_adjusted = str_build_log if len(str_build_log)<1500 \
            else f'{str_build_log[:1000]} …… {str_build_log[-500:]}'

        AppSettings.logger.info(f"Finished: {str_build_log_adjusted}")
#end of process_obs_helps


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-r', '--regenerate', dest='regenerate', action='store_true',
                        help='Regenerate PDF even if exists.')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='Turn debugging mode on. Prints debug messages and uses the QA DCS server.')
    parser.add_argument('-l', '--lang', dest='langs', required=False, action='append',
                        help='Language Code. Can specify multiple -l\'s, e.g. -l en -l fr. Default: en')
    parser.add_argument('-p', '--project_id', metavar='PROJECT ID', dest='project_ids', required=False,
                        action='append',
                        help='Project ID for resources with projects, such as a Bible book (-p gen). Can specify multiple -p\'s. Default: None (different converters will handle no or multiple projects differently, such as compiling all into one PDF, or running for each project.)')
    parser.add_argument('-w', '--working', dest='working_dir', required=False,
                        help='Working directory where multiple repos can be cloned into. Default: a temp directory that gets removed on exit')
    parser.add_argument('--owner', dest='owners', default=['unfoldingWord', 'Door43-Catalog'], required=False,
                        help=f'Owner of the resource repo on GitHub. Can be multiple. Default: unfoldingWord, Door43-Catalog')
    parser.add_argument('--repo', dest='repos', required=False,
                        help=f'Repo name. Can be multiple.')
    parser.add_argument('-s', '--subject', dest='subjects', action='append', required=False,
                        help='Subject to generate. Can give multiple. Ex.: -s "Open Bible Stories" -s "Translation Notes"')
    parser.add_argument('--tags', dest='tags', default=None, required=False,
                        help='The tags to use. If not specified, uses latest version or master if stage is "latest"')
    parser.add_argument('--stage', dest='stage', default=None, required=False,
                        help='The stage of the resource. If set, will use thec catalog rather than repo search.')
    args = parser.parse_args(sys.argv[1:])

    project_ids = args.project_ids
    if not project_ids or 'all' in project_ids[0]:
        project_id = '' if not project_ids else project_ids[0]
        project_ids_map = {'': BOOK_NUMBERS.keys(), 'all': BOOK_NUMBERS.keys()}
        if project_id in project_ids_map:
            project_ids = project_ids_map[project_id]
        elif not project_ids:
            project_ids = [None]

    prefix = ''
    dcs_domain = 'https://git.door43.org'
    if args.debug:
        prefix = 'dev'
        dcs_domain = 'https://qa.door43.org'

    args_map = vars(args)
    args_map['dcs_domain'] = dcs_domain
    process_pdfs(prefix, **args_map)
