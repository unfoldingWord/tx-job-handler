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
import tempfile
import json
from datetime import datetime, timedelta, date
from time import time
import sys
sys.setrecursionlimit(1500) # Default is 1,000—beautifulSoup hits this limit with UST
import traceback
import requests
import boto3
import watchtower
import logging

from rq import get_current_job, Queue
from statsd import StatsClient # Graphite front-end
from rq_settings import prefix, debug_mode_flag, webhook_queue_name, WORKER_NAME
from general_tools.file_utils import unzip, remove_tree, empty_folder
from general_tools.url_utils import download_file
from app_settings.app_settings import AppSettings
from linters.obs_linter import ObsLinter
from linters.obs_notes_linter import ObsNotesLinter
from linters.ta_linter import TaLinter
from linters.tn_linter import TnLinter, TnTsvLinter
from linters.tq_linter import TqLinter
from linters.tw_linter import TwLinter
from linters.markdown_linter import MarkdownLinter
from linters.usfm_linter import UsfmLinter
from linters.lexicon_linter import LexiconLinter
from converters.converter import Converter
from converters.md2html_converter import Md2HtmlConverter
from converters.tsv2html_converter import Tsv2HtmlConverter
from converters.usfm2html_converter import Usfm2HtmlConverter

from door43_tools.subjects import SUBJECT_ALIASES
from door43_tools.subjects import ALIGNED_BIBLE, BIBLE, OPEN_BIBLE_STORIES, OBS_STUDY_NOTES, OBS_STUDY_QUESTIONS, \
    OBS_TRANSLATION_NOTES, OBS_TRANSLATION_QUESTIONS, TRANSLATION_ACADEMY, TRANSLATION_WORDS, TRANSLATION_QUESTIONS, \
    TSV_STUDY_NOTES, TSV_STUDY_QUESTIONS, TSV_TRANSLATION_NOTES, TSV_TRANSLATION_QUESTIONS, GREEK_NEW_TESTAMENT, HEBREW_OLD_TESTAMENT
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

# NOTE: The following two tables are each scanned in order
#       (so put 'other' entries lower)
# All searching of the tables is case-sensitive
# Columns are: 1/ linter name 2/ linter 3/ input formats 4/ resource types
LINTER_TABLE = (
    ('obs',      ObsLinter,      ('md',),      ('Open_Bible_Stories','obs'),              ),
    ('obsNotes', ObsNotesLinter, ('md',),      ('OBS_Study_Notes',
                                                'OBS_Study_Questions',
                                                'OBS_Translation_Notes',
                                                'OBS_Translation_Questions'),             ),
    ('ta',       TaLinter,       ('md',),      ('Translation_Academy','ta'),              ),
    ('tn-tsv',   TnTsvLinter,    ('tsv',),     ('TSV_Translation_Notes','tn'),            ),
    ('tn',       TnLinter,       ('md',),      ('Translation_Notes','tn'),                ),
    ('tq',       TqLinter,       ('md',),      ('Translation_Questions','tq'),            ),
    ('tw',       TwLinter,       ('md',),      ('Translation_Words','tw'),                ),
    ('lexicon',  LexiconLinter,  ('md',),      ('Greek_Lexicon','Hebrew-Aramaic_Lexicon'), ),
    ('markdown', MarkdownLinter, ('md','txt'), ('Generic_Markdown','other'),              ),
    ('usfm',     UsfmLinter,     ('usfm',),    ('Bible','Aligned_Bible',
                                                'Greek_New_Testament','Hebrew_Old_Testament',
                                                'bible', 'reg', 'other'),                 ),
    )
# Columns are: 1/ converter name 2/ converter 3/ input formats 4/ resource types 5/ output format
CONVERTER_TABLE = (
    ('md2html',   Md2HtmlConverter,   ('md','markdown','txt','text'),
                    ('Generic_Markdown',
                    'Open_Bible_Stories','OBS_Study_Notes','OBS_Study_Questions',
                    'OBS_Translation_Notes','OBS_Translation_Questions','obs',
                    'Translation_Academy','ta', 'Translation_Questions','tq', 'Translation_Words',
                    'Translation_Words','tw', 'Translation_Notes','tn',
                    'Greek_Lexicon', 'Hebrew-Aramaic_Lexicon',
                'other',),                                                          'html'),
    ('tsv2html',  Tsv2HtmlConverter,  ('tsv',),
                    ('TSV_Translation_Notes','tn',
                    'other',),                                                      'html'),
    ('usfm2html', Usfm2HtmlConverter, ('usfm',),
                    ('Bible','Aligned_Bible',
                    'Greek_New_Testament','Hebrew_Old_Testament',
                    'bible', 'reg',
                    'other',),                                                      'html'),
    (ALIGNED_BIBLE,             AlignedBiblePdfConverter, ('usfm'),                       SUBJECT_ALIASES[ALIGNED_BIBLE] + SUBJECT_ALIASES[BIBLE] + SUBJECT_ALIASES[GREEK_NEW_TESTAMENT] + SUBJECT_ALIASES[HEBREW_OLD_TESTAMENT], 'pdf'),
    (OPEN_BIBLE_STORIES,        ObsPdfConverter,    ('', 'md','markdown','txt','text'),   SUBJECT_ALIASES[OPEN_BIBLE_STORIES], 'pdf'),
    (OBS_STUDY_NOTES,           ObsSnPdfConverter, ('', 'md', 'markdown', 'txt', 'text'), SUBJECT_ALIASES[OBS_STUDY_NOTES], 'pdf'),
    (OBS_STUDY_QUESTIONS,       ObsSqPdfConverter, ('', 'md','markdown','txt','text'),    SUBJECT_ALIASES[OBS_STUDY_QUESTIONS], 'pdf'),
    (OBS_TRANSLATION_NOTES,     ObsTnPdfConverter, ('', 'md','markdown','txt','text'),    SUBJECT_ALIASES[OBS_TRANSLATION_NOTES], 'pdf'),
    (OBS_TRANSLATION_QUESTIONS, ObsTqPdfConverter, ('', 'md','markdown','txt','text'),    SUBJECT_ALIASES[OBS_TRANSLATION_QUESTIONS], 'pdf'),
    (TRANSLATION_ACADEMY,       TaPdfConverter,    ('', 'md','markdown','txt','text'),    SUBJECT_ALIASES[TRANSLATION_ACADEMY], 'pdf'),
    (TRANSLATION_WORDS,         TwPdfConverter,    ('', 'md','markdown','txt','text'),    SUBJECT_ALIASES[TRANSLATION_WORDS], 'pdf'),
    (TSV_STUDY_NOTES,           SnPdfConverter,    ('', 'tsv'),                           SUBJECT_ALIASES[TSV_STUDY_NOTES], 'pdf'),
    (TSV_STUDY_QUESTIONS,       SqPdfConverter,    ('', 'tsv'),                           SUBJECT_ALIASES[TSV_STUDY_QUESTIONS], 'pdf'),
    (TSV_TRANSLATION_NOTES,     TnPdfConverter,    ('', 'tsv'),                           SUBJECT_ALIASES[TSV_TRANSLATION_NOTES], 'pdf'),
    (TSV_TRANSLATION_QUESTIONS, TqPdfConverter,    ('', 'tsv'),                           SUBJECT_ALIASES[TSV_TRANSLATION_QUESTIONS], 'pdf'),
    )


AppSettings(prefix=prefix)
if prefix not in ('', 'dev-'):
    AppSettings.logger.critical(f"Unexpected prefix: '{prefix}' — expected '' or 'dev-'")
tx_stats_prefix = f"tx.{'dev' if prefix else 'prod'}"
job_handler_stats_prefix = f"{tx_stats_prefix}.tx-job-handler"


# Get the Graphite URL from the environment, otherwise use a local test instance
graphite_url = os.getenv('GRAPHITE_HOSTNAME', 'localhost')
stats_client = StatsClient(host=graphite_url, port=8125, prefix=job_handler_stats_prefix)


def get_linter_module(glm_job:Dict[str,Any]) -> Tuple[Optional[str],Any]:
    """
    :param dict glm_job:
    :return linter name and linter class:
    """
    # Search the table to find the appropriate linter
    for linter_name, linter_class, input_formats, resource_types in LINTER_TABLE:
        if glm_job['input_format'] in input_formats:
            if glm_job['resource_type'] in resource_types:
                return linter_name, linter_class
            if 'other' in resource_types:
                AppSettings.logger.warning(f"Got linter from 'other' for input_format='{glm_job['input_format']}' and resource_type='{glm_job['resource_type']}'")
                return linter_name, linter_class
    # Didn't find one
    return None, None
# end of get_linter_module function


def do_linting(param_dict:Dict[str,Any], source_dir:str, linter_name:str, linter_class) -> None:
    """
    :param dict param_dict: Will be updated for build log!
    :param str linter_name:

    Updates param_dict as a side-effect.
    """
    AppSettings.logger.debug(f"do_linting( {param_dict}, {source_dir}, {linter_name}, {linter_class} )")
    param_dict['status'] = 'linting'

    linter = linter_class(repo_subject=param_dict['resource_type'], source_dir=source_dir)
    lint_result = linter.run()
    linter.close()  # do cleanup after run
    param_dict['linter_success'] = lint_result['success']
    param_dict['linter_warnings'] = lint_result['warnings']
    param_dict['status'] = 'linted'
# end of do_linting function


def get_converter_module(gcm_job:Dict[str,Any], output_format:str) -> Tuple[Optional[str],Any]:
    """
    :param dict gcm_job:
    :return TxModule:
    """
    for converter_name, converter_class, input_formats, resource_types, opf in CONVERTER_TABLE:
        if gcm_job and 'input_format' in gcm_job and gcm_job['input_format'] in input_formats and opf and opf == output_format:
            if gcm_job['resource_type'] in resource_types:
                return converter_name, converter_class
            if 'other' in resource_types:
                AppSettings.logger.warning(f"Got converter from 'other' for input_format='{gcm_job['input_format']}' and resource_type='{gcm_job['resource_type']}'")
                return converter_name, converter_class
    # Didn't find one
    return None, None
# end if get_converter_module function


def do_converting(param_dict:Dict[str,Any], source_dir:str, converter_name:str, converter_class:Type[Converter]) -> None:
    """
    :param dict param_dict: Will be updated for build log!
    :param str source_dir: Directory of the download source files
    :param str converter_name: Name of the converter
    :param class converter_class: Class of the converter
    Updates param_dict as a side-effect.
    """
    AppSettings.logger.debug(f"do_converting( {len(param_dict)} fields, {source_dir}, {converter_name}, {converter_class} )")
    param_dict['status'] = 'converting'

    if 'cdn.door43.org/' in param_dict['output']:
        cdn_file_key = param_dict['output'].split('cdn.door43.org/')[1] # Get the last part
    else:
        cdn_file_key = param_dict['output']
    converter = converter_class(param_dict['resource_type'],
                                source_dir=source_dir,
                                source_url=param_dict['source'],
                                cdn_file_key=cdn_file_key, #  Key for uploading
                                identifier=param_dict['identifier'],
                                options={'debug_mode_flag': debug_mode_flag},
                                repo_owner=param_dict['repo_owner'],
                                repo_name=param_dict['repo_name'],
                                repo_ref=param_dict['repo_ref'],
                                repo_data_url=param_dict['repo_data_url'],
                                dcs_domain=param_dict['dcs_domain'],
                                project_ids=param_dict['project_ids'] if 'project_ids' in param_dict else None)
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


def process_tx_job(pj_prefix: str, queued_json_payload) -> str:
    """
    pj_prefix is normally 'dev-' or ''

    queued_json_payload MUST have the following fields:
        job_id (string)
        source (url string of zip file)
        resource_type = a subject as specified in https://api.door43.org/v3/subjects
        input_format (e.g., md, usfm, tsv)
        output_format (currently only 'html' is recognised)
    The following OPTIONAL fields are used if present:
        identifier (string)
        options (dict)
        callback (url string)
    The following fields are included by the Door43 Job Handler but ignored here:
        user_token—was already checked by tX enqueue job

    Conversion and linting are now initiated by sending a request to each.

    This code is "successful" once the conversion/linting jobs are all completed.

    Does a callback (if requested) to advise of completion.

    The given payload will be appended to the 'failed' queue
        if an exception is thrown in this module.
    """
    AppSettings.logger.info(f"PROCESSING {pj_prefix+' ' if pj_prefix else ''}job: {queued_json_payload}")
    job_descriptive_name = f"{queued_json_payload['resource_type']}({queued_json_payload['input_format']})"
    if 'identifier' in queued_json_payload and queued_json_payload['identifier'] \
            and queued_json_payload['identifier'] != queued_json_payload['job_id']:
        job_descriptive_name = f"{queued_json_payload['identifier']} {job_descriptive_name}"

    if 'identifier' not in queued_json_payload or len(queued_json_payload['identifier'].split('--')) < 3:
        if 'door43.org/' in queued_json_payload['source'] and queued_json_payload['source']:
            parts = queued_json_payload['source'].split('door43.org/')[1].split('/')
            owner = repo = ref = ''
            if len(parts) >= 2:
                owner = parts[0]
                repo = parts[1]
            if len(parts) >= 4:
                ref = parts[3].split('.')[0]
            queued_json_payload['identifier'] = f'{owner}--{repo}--{ref}'

    # Create a build log
    build_log_dict = queued_json_payload.copy()
    # Delete fields from our response which have already been used
    #   or are unneeded in the build log and in our response
    for fieldname in ('callback', 'input_format', 'user_token', 'queue_name',
                                'tx_job_queued_at', 'eta', 'tx_retry_count'):
        if fieldname in build_log_dict:
            del build_log_dict[fieldname]
    build_log_dict['started_at'] = datetime.utcnow()
    if 'expires_at' not in build_log_dict:
        build_log_dict['expires_at'] = build_log_dict['started_at'] + timedelta(days=1)
    if 'eta' not in build_log_dict:
        build_log_dict['eta'] = build_log_dict['started_at'] + timedelta(minutes=5)
    build_log_dict['status'] = 'started'
    build_log_dict['message'] = 'tX job started…'

    # Setup a temp folder to use
    # Move everything down one directory level for simple delete
    base_temp_dir_name = os.path.join(tempfile.gettempdir(), f"tX_job_{queued_json_payload['job_id']}")
    AppSettings.logger.debug(f"base_temp_dir_name = {base_temp_dir_name}")
    try:
        os.makedirs(base_temp_dir_name)
    except Exception as e:
        AppSettings.logger.critical(f"SetupTempFolder threw an exception: {e}: {traceback.format_exc()}")
        AppSettings.logger.critical(f"Oh, folder {base_temp_dir_name} already existed!")
        AppSettings.logger.info(f"It contained {os.listdir(base_temp_dir_name)}")

    # Download and unzip the specified source file
    AppSettings.logger.debug(f"Getting source file from {queued_json_payload['source']} …")
    if not debug_mode_flag or not len(os.listdir(base_temp_dir_name)):
        download_source_file(queued_json_payload['source'], base_temp_dir_name)

    # Find correct source folder
    source_folder_path = base_temp_dir_name
    dirList = os.listdir(base_temp_dir_name)
    str_dirList = str(dirList)
    str_dirList_adjusted = str_dirList if len(str_dirList)<1500 \
                            else f'{str_dirList[:1000]} …… {str_dirList[-500:]}'
    AppSettings.logger.debug(f"Discovering source folder from"
                                f" '{base_temp_dir_name}' with {str_dirList_adjusted} …")
    if len(dirList) == 1:
        tryFolder = os.path.join(base_temp_dir_name, dirList[0])
        if os.path.isdir(tryFolder):
            AppSettings.logger.debug(f"Switching source folder to {tryFolder}")
            source_folder_path = tryFolder
    if source_folder_path != base_temp_dir_name:
        AppSettings.logger.info(f"Source folder '{source_folder_path}'"
                                f" contains {os.listdir(source_folder_path)}")

    # Save some stats
    stats_output_cat = queued_json_payload['output_format'].upper()
    stats_client.incr(f"jobs.output.{stats_output_cat}")
    stats_client.incr(f"jobs.{stats_output_cat}.input.{queued_json_payload['input_format']}")
    stats_client.incr(f"jobs.{stats_output_cat}.subject.{queued_json_payload['resource_type']}")
    stats_client.incr(f"jobs.input.{queued_json_payload['input_format']}")
    stats_client.incr(f"jobs.subject.{queued_json_payload['resource_type']}")

    # Find the correct linter and converter
    AppSettings.logger.debug(f"Finding linter and converter for {queued_json_payload['input_format']}"
                                f" '{queued_json_payload['resource_type']}'")
    linter_name, linter = get_linter_module(queued_json_payload)
    AppSettings.logger.info(f"Got linter = {linter_name}")
    door43_pages_converter_name, door43_pages_converter = get_converter_module(queued_json_payload, queued_json_payload['output_format'])
    AppSettings.logger.info(f"Got door43_pages_converter = {door43_pages_converter_name}")

    # Run the linter first
    if linter:
        build_log_dict['status'] = 'linting'
        build_log_dict['message'] = 'tX job linting…'
        build_log_dict['lint_module'] = linter_name
        # Log dict gets updated by the following line
        do_linting(build_log_dict, source_folder_path, linter_name, linter)
    else:
        warning_message = f"No linter was found to lint {queued_json_payload['input_format']}" \
                          f" {queued_json_payload['resource_type']}"
        AppSettings.logger.warning(warning_message)
        build_log_dict['lint_module'] = 'NO LINTER'
        build_log_dict['linter_success'] = 'false'
        build_log_dict['linter_warnings'] = [warning_message]

    # Now run the door43_pages_converter
    if door43_pages_converter:
        build_log_dict['status'] = 'converting'
        build_log_dict['message'] = 'tX job converting…'
        build_log_dict['convert_module'] = door43_pages_converter_name
        do_converting(build_log_dict, source_folder_path, door43_pages_converter_name, door43_pages_converter)
    else:
        error_message = f"No converter was found to convert {queued_json_payload['resource_type']}" \
                        f" from {queued_json_payload['input_format']} to {queued_json_payload['output_format']}"
        AppSettings.logger.error(error_message)
        build_log_dict['convert_module'] = 'NO CONVERTER'
        build_log_dict['converter_success'] = 'false'
        build_log_dict['converter_info'] = []
        build_log_dict['converter_warnings'] = []
        build_log_dict['converter_errors'] = [error_message]

    build_log_dict['status'] = 'finished'
    build_log_dict['message'] = 'tX job completed.'


    # Do the callback (if requested) to advise the caller of our results
    if 'callback' in queued_json_payload:
        AppSettings.logger.info(f"tX JobHandler about to do callback to {queued_json_payload['callback']} …")
        # Copy the build log but convert times to strings
        callback_payload = build_log_dict
        for key, value in callback_payload.items():
            if isinstance(value, (datetime, date)):
                callback_payload[key] = value.strftime('%Y-%m-%dT%H:%M:%SZ')

        stats_client.incr(f'callbacks.{stats_output_cat}.attempted')
        stats_client.incr(f'callbacks.attempted')
        response:Optional[requests.Response]
        try:
            response = requests.post(queued_json_payload['callback'], json=callback_payload)
        except requests.exceptions.ConnectionError as e:
            AppSettings.logger.critical(f"Callback connection error: {e}")
            response = None
        if response:
            #AppSettings.logger.info(f"response.status_code = {response.status_code}, response.reason = {response.reason}")
            #AppSettings.logger.debug(f"response.headers = {response.headers}")
            try:
                AppSettings.logger.info(f"response.json = {response.json()}")
            except json.decoder.JSONDecodeError:
                AppSettings.logger.info("No valid response JSON found")
                AppSettings.logger.debug(f"response.text = {response.text}")
            if response.status_code != 200:
                AppSettings.logger.critical(f"Failed to submit callback to Door43:"
                                               f" {response.status_code}={response.reason}")
        else: # no response
            error_msg = "Submission of callback job to Door43 system got no response"
            AppSettings.logger.critical(error_msg)
            #raise Exception(error_msg) # Is this the best thing to do here?
    else:
        AppSettings.logger.info("No callback requested.")

    if prefix and debug_mode_flag:
        AppSettings.logger.debug(f"Temp folder '{base_temp_dir_name}' has been left on disk for debugging!")
    else:
        remove_tree(base_temp_dir_name)  # cleanup
    str_build_log = str(build_log_dict)
    str_build_log_adjusted = str_build_log if len(str_build_log)<1500 \
                            else f'{str_build_log[:1000]} …… {str_build_log[-500:]}'
    AppSettings.logger.info(f"{prefix}process_tx_job() for {job_descriptive_name} is returning with {str_build_log_adjusted}")
    return job_descriptive_name
#end of process_tx_job function


def job(queued_json_payload:Dict[str,Any]) -> None:
    """
    This function is called by the rq package to process a job in the queue(s).
        (Don't rename this function.)

    The job is removed from the queue before the job is started,
        but if the job throws an exception or times out (timeout specified in enqueue process)
            then the job gets added to the 'failed' queue.
    """
    AppSettings.logger.debug("tX JobHandler received a job" + (" (in debug mode)" if debug_mode_flag else ""))
    stats_output_cat = queued_json_payload["output_format"].upper()
    start_time = time()
    stats_client.incr(f'jobs.{stats_output_cat}.attempted')
    stats_client.incr(f'jobs.attempted')
    stats_client.incr(f'jobs.workers')
    stats_client.incr(f'jobs.workers.{WORKER_NAME}')
    stats_client.incr(f'jobs.{stats_output_cat}.workers')
    stats_client.incr(f'jobs.{stats_output_cat}.workers.{WORKER_NAME}')

    AppSettings.logger.info(f"Clearing /tmp folder…")
    empty_folder('/tmp/', only_prefix='tX_') # Stops failed jobs from accumulating in /tmp

    # AppSettings.logger.info(f"Updating queue statistics…")
    our_queue= Queue(webhook_queue_name, connection=get_current_job().connection)
    len_our_queue = len(our_queue) # Should normally sit at zero here
    # AppSettings.logger.debug(f"Queue '{webhook_queue_name}' length={len_our_queue}")
    stats_client.gauge(f'queue.length.current', len_our_queue)
    AppSettings.logger.info(f"Updated stats for '{tx_stats_prefix}.enqueue-job.queue.length.current' to {len_our_queue}")

    try:
        job_descriptive_name = process_tx_job(prefix, queued_json_payload)
    except Exception as e:
        # Catch most exceptions here so we can log them to CloudWatch
        prefixed_name = f"{prefix}tx-job-handler"
        AppSettings.logger.critical(f"{prefixed_name} threw an exception while processing: {queued_json_payload}")
        AppSettings.logger.critical(f"{e}: {traceback.format_exc()}")
        AppSettings.close_logger() # Ensure queued logs are uploaded to AWS CloudWatch
        # Now attempt to log it to an additional, separate FAILED log
        logger2 = logging.getLogger(prefixed_name)
        test_mode_flag = os.getenv('TEST_MODE', '')
        travis_flag = os.getenv('TRAVIS_BRANCH', '')
        log_group_name = f"FAILED_{'' if test_mode_flag or travis_flag else prefix}tX" \
                         f"{'_DEBUG' if debug_mode_flag else ''}" \
                         f"{'_TEST' if test_mode_flag else ''}" \
                         f"{'_TravisCI' if travis_flag else ''}"
        aws_access_key_id = os.environ['AWS_ACCESS_KEY_ID']
        aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY']
        boto3_client = boto3.client("logs", aws_access_key_id=aws_access_key_id,
                            aws_secret_access_key=aws_secret_access_key,
                            region_name='us-west-2')
        failure_watchtower_log_handler = watchtower.CloudWatchLogHandler(boto3_client=boto3_client,
                                                use_queues=False,
                                                log_group_name=log_group_name,
                                                stream_name=prefixed_name)
        logger2.addHandler(failure_watchtower_log_handler)
        logger2.setLevel(logging.DEBUG)
        logger2.info(f"Logging to AWS CloudWatch group '{log_group_name}' using key '…{aws_access_key_id[-2:]}'.")
        logger2.critical(f"{prefixed_name} threw an exception while processing: {queued_json_payload}")
        logger2.critical(f"{e}: {traceback.format_exc()}")
        failure_watchtower_log_handler.close()
        raise e # We raise the exception again so it goes into the failed queue

    elapsed_milliseconds = round((time() - start_time) * 1000)
    stats_client.timing(f'job.{stats_output_cat}.duration', elapsed_milliseconds)
    stats_client.timing(f'job.{stats_output_cat}.duration.{WORKER_NAME}', elapsed_milliseconds)
    stats_client.timing(f'job.duration.{WORKER_NAME}', elapsed_milliseconds)
    if elapsed_milliseconds < 2000:
        AppSettings.logger.info(f"{prefix}tX job handling for {job_descriptive_name} completed in {elapsed_milliseconds:,} milliseconds.")
    else:
        AppSettings.logger.info(f"{prefix}tX job handling for {job_descriptive_name} completed in {round(time() - start_time)} seconds.")

    stats_client.incr(f'jobs.{stats_output_cat}.completed')
    stats_client.incr(f'jobs.completed')
    AppSettings.close_logger() # Ensure queued logs are uploaded to AWS CloudWatch
# end of job function

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Syntax: webhook.py <payload_file>.json")
        exit(1)
    tempfile.tempdir = '/tmp'
    print(sys.argv[1])
    with open(sys.argv[1]) as f:
        data = json.load(f)
    process_tx_job("dev", data)

# end of webhook.py for tX HTML Job Handler
