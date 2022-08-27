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
from typing import Tuple, Any, Optional, Type
import os
import io
import sys
import traceback
import tempfile
import shutil
import base64
import ruamel.yaml
import requests
from dcs_api_client.rest import ApiException
from glob import glob
from ruamel.yaml.comments import CommentedMap as OrderedDict
from ruamel.yaml.scalarstring import SingleQuotedScalarString

# Local imports
from rq_settings import prefix, debug_mode_flag
from general_tools.file_utils import unzip, remove_tree
from general_tools.url_utils import download_file
from app_settings.app_settings import AppSettings

from converters.converter import Converter

from door43_tools.subjects import SUBJECT_ALIASES
from door43_tools.subjects import ALIGNED_BIBLE, BIBLE, OPEN_BIBLE_STORIES, OBS_STUDY_NOTES, OBS_STUDY_QUESTIONS, \
    OBS_TRANSLATION_NOTES, TRANSLATION_ACADEMY, TRANSLATION_WORDS, TRANSLATION_QUESTIONS, TSV_STUDY_NOTES, \
    TSV_STUDY_QUESTIONS, TSV_TRANSLATION_NOTES, OBS_TRANSLATION_QUESTIONS
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

yaml = ruamel.yaml.YAML()  # defaults to round-trip
yaml.preserve_quotes = True

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

def get_converter_module(entry) -> Tuple[Optional[str],Any]:
    for converter_name, converter_class, input_formats, resource_types, output_format in CONVERTER_TABLE:
        if entry['subject'] == converter_name:
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


def process_obs_helps(pj_prefix, lang=None, subject=None):
    AppSettings.logger.info(f"PROCESSING {pj_prefix+' ' if pj_prefix else ''}obs_helps: {subject} {lang}")

    tempfile.tempdir = '/tmp'
    if not subject:
        subject = [OPEN_BIBLE_STORIES, OBS_TRANSLATION_QUESTIONS, OBS_TRANSLATION_NOTES, OBS_STUDY_QUESTIONS, OBS_STUDY_NOTES]
        # subject = [OBS_TRANSLATION_NOTES, OBS_TRANSLATION_QUESTIONS]
        # subject = [OBS_TRANSLATION_NOTES]
        # subject = [OBS_TRANSLATION_QUESTIONS]
        # subject = [OPEN_BIBLE_STORIES]
        # subject = [OBS_TRANSLATION_QUESTIONS]
    stage = 'latest'
    owner = ['Door43-Catalog']
    lang = None

    response = api.query_catalog(subjects=subject, owners=owner, langs=lang, stage=stage, order='desc')

    if 'ok' not in response or 'data' not in response or not len(response['data']):
        AppSettings.logger.error(f'No entries for {subject}')
        exit(1)

    print("TO BE GENERATED:")
    for entry in response['data']:
        print(f"  {entry['lang_code']} :: {entry['subject']} :: {entry['owner']} :: {entry['repo']}")

    for entry in response['data']:
        AppSettings.logger.debug(f"entry: {entry}")
        upload_and_update(entry)


def get_pdfs(entry):
        # Setup a temp folder to use
        # Move everything down one directory level for simple delete
        outdir = os.path.join(entry['owner'], entry['lang_code'], entry['repo'].split('_')[1])
        base_temp_dir_name = os.path.join('/tmp', 'working', entry['subject'], outdir)
        output_dir = os.path.join(base_temp_dir_name, 'Output')
        AppSettings.logger.debug(f"base_temp_dir_name = {base_temp_dir_name}")
        if entry['subject'] == OPEN_BIBLE_STORIES:
            outdir = os.path.join(entry['owner'], entry['lang_code'], entry['repo'].split('_')[1])
            base_temp_dir_name = os.path.join('/tmp', 'working', entry['subject'], outdir)
        try:
            os.makedirs(base_temp_dir_name)
        except Exception as e:
            AppSettings.logger.critical(f"SetupTempFolder threw an exception: {e}: {traceback.format_exc()}")
            AppSettings.logger.critical(f"Oh, folder {base_temp_dir_name} already existed!")
            AppSettings.logger.info(f"It contained {os.listdir(base_temp_dir_name)}")

        # Download and unzip the specified source file
        AppSettings.logger.debug(f"Getting source file from {entry['zipball_url']} …")
        download_source_file(entry['zipball_url'], base_temp_dir_name)

        # Find correct source folder
        source_folder_path = os.path.join(base_temp_dir_name, entry['repo'])

        converter_name, converter = get_converter_module(entry)
        AppSettings.logger.info(f"Got converter = {converter_name}")
        build_log_dict = {
            'resource_type': entry['subject'],
            'identifier': f"{entry['owner']}--{entry['repo']}--{entry['branch_or_tag_name']}",
            'output': os.path.join('/tmp', 'working', entry['subject'], outdir, f'{entry["repo"]}-{entry["branch_or_tag_name"]}.zip'),
            'source': entry['zipball_url']
        }

        if converter:
            build_log_dict['status'] = 'converting'
            build_log_dict['message'] = 'tX job converting…'
            build_log_dict['convert_module'] = converter_name
            do_converting(build_log_dict, source_folder_path, converter_name, converter)
        else:
            error_message = f"No converter was found to convert {entry['subject']}"
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

        for file in glob(os.path.join(output_dir, "*.pdf")):
            print(file)
            shutil.copy(file, '/Users/richmahn/obs')

        AppSettings.logger.info(f"Finished: {str_build_log_adjusted}")
#end of process_obs_helps


def upload_and_update(entry):
    org = entry['owner']
    repo = entry['repo']

    pdf_mask = f"{entry['lang_code']}_{SUBJECT_ALIASES[entry['subject']][0]}_*"
    if entry['subject'] == OBS_STUDY_NOTES:
        pdf_mask = f"{entry['lang_code']}_{SUBJECT_ALIASES[entry['subject']][0]}*"
    pdf_dir = '/Users/richmahn/obs'
    done_dir = os.path.join(pdf_dir, 'done')
    done2_dir = os.path.join(pdf_dir, 'done')
    pdfs = glob(os.path.join(pdf_dir, pdf_mask))
    cdn_links = []
    if not pdfs:
        AppSettings.logger.error(f"ERROR! NO PDFs FOR {pdf_mask}!!!")
        get_pdfs(entry)
        pdfs = glob(os.path.join(pdf_dir, pdf_mask))
        if not pdfs:
            AppSettings.logger.error(f"ERROR! NO PDFs FOR {pdf_mask}!!!")
            return
    if os.path.exists(os.path.join(pdf_dir, 'done2', os.path.basename(pdfs[0]))):
        print(f"ALREADY DONE {pdfs[0]}")
        return
    for pdf in pdfs:
        basename = os.path.basename(pdf)
        done = os.path.join(done_dir, basename)
        done2 = os.path.join(done2_dir, basename)
        version = os.path.splitext(basename)[0].split('_')[-1].split('-')[0]
        # 1. Upload pdf(s) to proper place on Amazon S3 in the cdn.door43.org bucket as u/Door43-Org/<repo>/<file>.pdf
        key = f"{entry['lang_code']}/{org}/{repo}/{version}/pdf/{basename}"
        cdn_link = f"https://cdn.door43.org/{key}"
        cdn_links.append(cdn_link)
        if not os.path.exists(done) and not os.path.exists(done2):
            AppSettings.logger.info(f"Uploading {pdf} to {cdn_link}")
            AppSettings.cdn_s3_handler().upload_file(pdf, key, cache_time=0)
            shutil.copyfile(pdf, done)
        else:
            AppSettings.logger.info(f"Already uploaded {pdf}")
    sha = None
    try:
        resp = AppSettings.repo_api.repo_get_contents(org, repo, 'media.yaml')
        media = yaml.load(base64.b64decode(resp.content))
        sha = resp.sha
        print(media)
    except ApiException as e:
        print(e)
        media = {
            'projects': []
        }
    version_str = os.path.splitext(os.path.basename(pdfs[0]))[0].split('_')[-1].split('-')[0]
    for pdf in pdfs:
        basename = os.path.basename(pdf)
        identifier = os.path.splitext(basename)[0].split('_')[1]
        version_str = os.path.splitext(basename)[0].split('_')[-1].split('-')[0]
        version_num = version_str.removeprefix('v')
        key = f"{entry['lang_code']}/{org}/{repo}/{version_str}/pdf/{basename}"
        cdn_link = f"https://cdn.door43.org/{key}"
        project_found = False
        door43_found = False
        for project_idx, project in enumerate(media['projects']):
            if project['identifier'] != identifier:
                continue
            if project['version'] == '{latest}' or project['version'] == version_num:
                project_found = True
                project['version'] = SingleQuotedScalarString(version_num)
                pdf_found = False
                if 'media' not in project:
                    project['media'] = []
                if len(project['media']):
                    for media_idx, m in enumerate(project['media']):
                        if m['identifier'] == 'pdf':
                            pdf_found = True
                            project['media'][media_idx]['url'] = SingleQuotedScalarString(cdn_link)
                            project['media'][media_idx]['version'] = SingleQuotedScalarString(version_num)
                        if m['identifier'] == 'door43':
                            door43_found = True
                if not pdf_found:
                    project['media'].append(OrderedDict([
                        ('identifier', SingleQuotedScalarString('pdf')),
                        ('version', SingleQuotedScalarString(version_num)),
                        ('contributor', []),
                        ('url', SingleQuotedScalarString(cdn_link)),
                    ]))
                if not door43_found:
                    project['media'].append(OrderedDict([
                        ('identifier', SingleQuotedScalarString('door43')),
                        ('version', SingleQuotedScalarString('{latest}')),
                        ('contributor', []),
                        ('url', SingleQuotedScalarString(f'https://door43.org/u/{org}/{repo}/'))
                    ]))
                media['projects'][project_idx] = project
                break
        if not project_found:
            media['projects'].append(OrderedDict([
                ('identifier', SingleQuotedScalarString(identifier)),
                ('version', SingleQuotedScalarString(version_num)),
                ('media', [
                    OrderedDict([
                        ('identifier', SingleQuotedScalarString('pdf')),
                        ('version', SingleQuotedScalarString(version_num)),
                        ('contributor', []),
                        ('url', SingleQuotedScalarString(cdn_link))
                    ]),
                    OrderedDict([
                        ('identifier', SingleQuotedScalarString('door43')),
                        ('version', SingleQuotedScalarString('{latest}')),
                        ('contributor', []),
                        ('url', SingleQuotedScalarString(f'https://door43.org/u/{org}/{repo}/'))
                    ])
                ])
            ]))
    print(media)
    string = io.StringIO()
    yaml.dump(media, string)
    media_str = string.getvalue()
    # media_str = media_str.replace(' !!omap', '')
    media_content = base64.b64encode(media_str.encode('ascii')).strip().decode()
    try:
        if sha:
            resp = AppSettings.repo_api.repo_update_file(org, repo, 'media.yaml', body={'content': str(media_content), 'sha': sha, 'new_branch': 'pdf-update'})
        else:
            resp = AppSettings.repo_api.repo_create_file(org, repo, 'media.yaml', body={'content': str(media_content), 'new_branch': 'pdf-update'})
        print(resp)
    except ApiException as e:
        print(e)
        exit(1)
    resp = AppSettings.repo_api.repo_create_pull_request(org, repo, body={
        'head': f'pdf-update',
        'base': 'master',
        'title': 'Updates media.yaml with new PDF url' if sha else 'Adds media.yaml'
    })
    resp = AppSettings.repo_api.repo_merge_pull_request(org, repo, resp.number, body={"Do": "merge", "force_merge": True})
    x = requests.delete(f'https://git.door43.org/api/v1/repos/Door43-Catalog/{repo}/branches/pdf-update?access_token=da16dd8ddee7dbc4ab84bf5daa1bd5353d0050ee')
    # resp = AppSettings.repo_api.repo_edit_pull_request(org, repo, resp.number, body={"state": "closed"})
    releases = AppSettings.repo_api.repo_list_releases(org, repo)
    for release in releases:
        if release.tag_name == version_str:
            AppSettings.repo_api.repo_delete_release(org, repo, release.id)
    AppSettings.repo_api.repo_create_release(org, repo, body={"name": version_str, "tag_name": version_str, "prerelease": False, "draft": False, "target_commitish": "master"})
    print(resp)
    for pdf in pdfs:
        done_path = os.path.join(pdf_dir, 'done', os.path.basename(pdf))
        done2_path = os.path.join(pdf_dir, 'done2', os.path.basename(pdf))
        os.rename(done_path, done2_path)
    # 10. Verify all PDFs are signed and listed in the pivoted catalog JSON fie
    # 11. See what OBS and OBS help files get listed on the OBS website. Update website to include all helps


if __name__ == '__main__':
    process_obs_helps("dev", *sys.argv[1:])
