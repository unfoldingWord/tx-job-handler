# NOTE: This module name and function name are defined by the rq package and our own tx-enqueue-job package
# This code adapted by RJH June 2018 from tx-manager/client_webhook/ClientWebhook/process_webhook

# NOTE: rq_settings.py is executed at program start-up, reads some environment variables, and sets queue name, etc.
#       job() function (at bottom here) is executed by rq package when there is an available entry in the named queue.

# Python imports
import os
#import shutil
import tempfile
#import logging
#import ssl
#import urllib.request as urllib2
from urllib import error as urllib_error
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import hashlib
from datetime import datetime, timedelta, date
from time import time

# Library (PyPi) imports
import requests
#from rq import
from statsd import StatsClient # Graphite front-end

# Local imports
from rq_settings import prefix, debug_mode_flag
from general_tools.file_utils import unzip, add_contents_to_zip, write_file, remove_tree
from general_tools.url_utils import download_file
from resource_container.ResourceContainer import RC
from preprocessors.preprocessors import do_preprocess
from models.manifest import TxManifest
from models.job import TxJob
from models.module import TxModule
from global_settings.global_settings import GlobalSettings

from linters.markdown_linter import MarkdownLinter
from linters.obs_linter import ObsLinter
from linters.ta_linter import TaLinter
from linters.tn_linter import TnLinter
from linters.tq_linter import TqLinter
from linters.tw_linter import TwLinter
from linters.udb_linter import UdbLinter
from linters.ulb_linter import UlbLinter
from linters.usfm_linter import UsfmLinter
LINTER_MAP = {'md':MarkdownLinter, 'obs':ObsLinter,
              'ta':TaLinter, 'tn':TnLinter, 'tq':TqLinter, 'tw':TwLinter,
              'udb':UdbLinter, 'ulb':UlbLinter,
              'usfm':UsfmLinter}

from converters.md2html_converter import Md2HtmlConverter
from converters.usfm2html_converter import Usfm2HtmlConverter
CONVERTER_MAP = {'md2html':Md2HtmlConverter, 'usfm2html':Usfm2HtmlConverter}


#OUR_NAME = 'tX_job_handler'

GlobalSettings(prefix=prefix)
if prefix not in ('', 'dev-'):
    GlobalSettings.logger.critical(f"Unexpected prefix: {prefix!r} -- expected '' or 'dev-'")
stats_prefix = f"tx.{'dev' if prefix else 'prod'}.job-handler"


# Get the Graphite URL from the environment, otherwise use a local test instance
graphite_url = os.getenv('GRAPHITE_HOSTNAME', 'localhost')
stats_client = StatsClient(host=graphite_url, port=8125, prefix=stats_prefix)



def get_linter_module(glm_job):
    """
    :param dict glm_job:
    :return TxModule:
    """
    linters = TxModule.query().filter(TxModule.type == 'linter') \
        .filter(TxModule.input_format.contains(glm_job['input_format']))
    linter = linters.filter(TxModule.resource_types.contains(glm_job['resource_type'])).first()
    if not linter:
        linter = linters.filter(TxModule.resource_types.contains('other')).first()
    return linter
# end of get_linter_module function


def do_linting(param_dict, source_dir, linter_name):
    """
    :param dict param_dict: Will be updated!
    :param str linter_name:
    """
    GlobalSettings.logger.debug(f'do_linting( {param_dict}, {source_dir}, {linter_name} )')
    param_dict['status'] = 'linting'

    # Find the right linter
    try:
        # TODO: Why does the linter download the (zip) file again???
        #linter = LINTER_MAP[linter_name](source_url=param_dict['source'])
        linter = LINTER_MAP[linter_name](source_dir=source_dir)
    except KeyError:
        GlobalSettings.logger.critical(f"Can't find correct linter for {linter_name!r}")
        linter = None

    if linter: # Run the linter and grab the results
        lint_result = linter.run()
        linter.close()  # do cleanup after run
        param_dict['linter_success'] = lint_result['success']
        param_dict['linter_warnings'] = lint_result['warnings']
    else:
        param_dict['linter_success'] = 'false'
        param_dict['linter_warnings'] = ['Cannot find correct linter']

    param_dict['status'] = 'linted'
    GlobalSettings.logger.debug(f'do_lint is returning with {param_dict}')
    #return param_dict
# end of do_linting function


def get_converter_module(gcm_job):
    """
    :param dict gcm_job:
    :return TxModule:
    """
    converters = TxModule.query().filter(TxModule.type == 'converter') \
        .filter(TxModule.input_format.contains(gcm_job['input_format'])) \
        .filter(TxModule.output_format.contains(gcm_job['output_format']))
    converter = converters.filter(TxModule.resource_types.contains(gcm_job['resource_type'])).first()
    if not converter:
        converter = converters.filter(TxModule.resource_types.contains('other')).first()
    return converter
# end if get_converter_module function


def do_converting(param_dict, source_dir, converter_name):
    """
    :param dict param_dict: Will be updated!
    :param str converter_name:
    """
    GlobalSettings.logger.debug(f'do_converting( {param_dict}, {source_dir}, {converter_name} )')
    param_dict['status'] = 'converting'

    # Find the right converter
    try:
        # TODO: Why does the converter download the (zip) file again???
        converter = CONVERTER_MAP[converter_name](param_dict['source'],
                                                  param_dict['resource_type'],
                                                  cdn_file=param_dict['output'])
    except KeyError:
        GlobalSettings.logger.critical(f"Can't find correct converter for {converter_name!r}")
        converter = None

    if converter: # Run the converter and grab the results
        convert_result = converter.run()
        converter.close()  # do cleanup after run
        param_dict['converter_success'] = convert_result['success']
        param_dict['converter_info'] = convert_result['info']
        param_dict['converter_warnings'] = convert_result['warnings']
        param_dict['converter_errors'] = convert_result['errors']
    else:
        param_dict['converter_success'] = 'false'
        param_dict['converter_warnings'] = ['Cannot find correct converter']

    param_dict['status'] = 'converted'
    GlobalSettings.logger.debug(f'do_convert is returning with {param_dict}')
    #return param_dict
# end of do_converting function


#def send_request_to_converter(srtc_job, converter):
    #"""
    #:param TxJob srtc_job:
    #:param TxModule converter:
    #:return bool:
    #"""
    #payload = {
        #'identifier': srtc_job.identifier,
        #'source_url': srtc_job.source,
        #'resource_id': srtc_job.resource_type,
        #'cdn_bucket': srtc_job.cdn_bucket,
        #'cdn_file': srtc_job.cdn_file,
        #'options': srtc_job.options,
        #'convert_callback': f'{GlobalSettings.api_url}/client/callback/converter'
    #}
    ## NOTE: The returned result is not currently used
    #return send_payload_to_converter(payload, converter)
## end of send_request_to_converter function


#def send_payload_to_converter(payload, converter):
    #"""
    #:param dict payload:
    #:param TxModule converter:
    #:return bool:
    #"""
    ## TODO: Make this use urllib2 to make a async POST to the API. Currently invokes Lambda directly XXXXXXXXXXXXXXXXX
    #payload = {
        #'data': payload,
        #'vars': {
            #'prefix': GlobalSettings.prefix
        #}
    #}
    #converter_name = converter.name
    #if not isinstance(converter_name, str): # bytes in Python3 -- not sure where it gets set
        #converter_name = converter_name.decode()
    #print("converter_name", repr(converter_name))
    #GlobalSettings.logger.debug(f'Sending Payload to converter {converter_name}:')
    #GlobalSettings.logger.debug(payload)
    #converter_function = f'{GlobalSettings.prefix}tx_convert_{converter_name}'
    #print(f"send_payload_to_converter: converter_function is {converter_function!r} payload={payload}")
    #stats_client.incr('ConvertersInvoked')
    ## TODO: Put an alternative function call in here RJH
    #response = GlobalSettings.lambda_handler().invoke(function_name=converter_function, payload=payload, asyncFlag=True)
    #GlobalSettings.logger.debug('finished.')
    #return response
## end of send_payload_to_converter function


def update_project_json(base_temp_dir_name, commit_id, upj_job, repo_name, repo_owner):
    """
    :param string commit_id:
    :param TxJob upj_job:
    :param string repo_name:
    :param string repo_owner:
    :return:
    """
    project_json_key = f'u/{repo_owner}/{repo_name}/project.json'
    project_json = GlobalSettings.cdn_s3_handler().get_json(project_json_key)
    project_json['user'] = repo_owner
    project_json['repo'] = repo_name
    project_json['repo_url'] = f'https://git.door43.org/{repo_owner}/{repo_name}'
    commit = {
        'id': commit_id,
        'created_at': upj_job.created_at,
        'status': upj_job.status,
        'success': upj_job.success,
        'started_at': None,
        'ended_at': None
    }
    # TODO: CHECK AND DELETE Rewrite of the following lines as a list comprehension
    if 'commits' not in project_json:
        project_json['commits'] = []
    commits1 = []
    for c in project_json['commits']:
        if c['id'] != commit_id:
            commits1.append(c)
    commits1.append(commit)
    #project_json['commits'] = commits1
    print(f"project_json['commits (old)'] = {commits1}")
    # Get all other previous commits, and then add this one
    if 'commits' in project_json:
        commits = [c for c in project_json['commits'] if c['id'] != commit_id]
        commits.append(commit)
    else:
        commits = [commit]
    print(f"project_json['commits (new)'] = {commits}")
    assert commits == commits1
    project_json['commits'] = commits
    project_file = os.path.join(base_temp_dir_name, 'project.json')
    write_file(project_file, project_json)
    GlobalSettings.cdn_s3_handler().upload_file(project_file, project_json_key)
# end of update_project_json function


def upload_build_log_to_s3(base_temp_dir_name, build_log, s3_commit_key, part=''):
    """
    :param dict build_log:
    :param string s3_commit_key:
    :param string part:
    :return:
    """
    build_log_file = os.path.join(base_temp_dir_name, 'build_log.json')
    write_file(build_log_file, build_log)
    upload_key = f'{s3_commit_key}/{part}build_log.json'
    GlobalSettings.logger.debug(f'Saving build log to {GlobalSettings.cdn_bucket_name}/{upload_key}')
    GlobalSettings.cdn_s3_handler().upload_file(build_log_file, upload_key, cache_time=0)
    # GlobalSettings.logger.debug('build log contains: ' + json.dumps(build_log_json))
#end of upload_build_log_to_s3


def create_build_log(commit_id, commit_message, commit_url, compare_url, cbl_job, pusher_username, repo_name, repo_owner):
    """
    :param string commit_id:
    :param string commit_message:
    :param string commit_url:
    :param string compare_url:
    :param TxJob cbl_job:
    :param string pusher_username:
    :param string repo_name:
    :param string repo_owner:
    :return dict:
    """
    build_log_json = dict(cbl_job)
    build_log_json['repo_name'] = repo_name
    build_log_json['repo_owner'] = repo_owner
    build_log_json['commit_id'] = commit_id
    build_log_json['committed_by'] = pusher_username
    build_log_json['commit_url'] = commit_url
    build_log_json['compare_url'] = compare_url
    build_log_json['commit_message'] = commit_message

    return build_log_json
# end of create_build_log function


def clear_commit_directory_in_cdn(s3_commit_key):
    """
    Clear out the commit directory in the cdn bucket for this project revision.
    """
    for obj in GlobalSettings.cdn_s3_handler().get_objects(prefix=s3_commit_key):
        GlobalSettings.logger.debug('Removing s3 cdn file: ' + obj.key)
        GlobalSettings.cdn_s3_handler().delete_file(obj.key)
# end of clear_commit_directory_in_cdn function


def build_multipart_source(source_url_base, file_key, book_filename):
    params = urlencode({'convert_only': book_filename})
    source_url = f'{source_url_base}/{file_key}?{params}'
    return source_url
# end of build_multipart_source function


def get_unique_job_id():
    """
    :return string:
    """
    job_id = hashlib.sha256(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f").encode('utf-8')).hexdigest()
    while TxJob.get(job_id):
        job_id = hashlib.sha256(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f").encode('utf-8')).hexdigest()
    return job_id
# end of get_unique_job_id()


def upload_zip_file(commit_id, zip_filepath):
    file_key = f'preconvert/{commit_id}.zip'
    GlobalSettings.logger.debug(f'Uploading {zip_filepath} to {GlobalSettings.pre_convert_bucket_name}/{file_key}...')
    try:
        GlobalSettings.pre_convert_s3_handler().upload_file(zip_filepath, file_key, cache_time=0)
    except Exception as e:
        GlobalSettings.logger.error('Failed to upload zipped repo up to server')
        GlobalSettings.logger.exception(e)
    finally:
        GlobalSettings.logger.debug('finished.')
    return file_key
# end of upload_zip_file function


def get_repo_files(base_temp_dir_name, commit_url, repo_name):
    temp_dir = tempfile.mkdtemp(dir=base_temp_dir_name, prefix=f'{repo_name}_')
    download_repo(base_temp_dir_name, commit_url, temp_dir)
    repo_dir = os.path.join(temp_dir, repo_name.lower())
    if not os.path.isdir(repo_dir):
        repo_dir = temp_dir
    return repo_dir
# end of get_repo_files function


def download_source_file(source_url, destination_folder):
    """
    Downloads the specified source file
        and unzips it if necessary.

    :param str source_url: The URL of the file to download
    :param str destination_folder:   The directory where the downloaded file should be unzipped
    :return: None
    """
    GlobalSettings.logger.debug(f"download_source_file( {source_url}, {destination_folder} )")
    source_filepath = os.path.join(destination_folder, source_url.rpartition(os.path.sep)[2])
    GlobalSettings.logger.info(f"source_filepath: {source_filepath}")

    try:
        GlobalSettings.logger.debug(f'Downloading {source_url} ...')

        # if the file already exists, remove it, we want a fresh copy
        if os.path.isfile(source_filepath):
            os.remove(source_filepath)

        download_file(source_url, source_filepath)
    finally:
        GlobalSettings.logger.debug('Downloading finished.')

    if source_url.lower().endswith('.zip'):
        try:
            GlobalSettings.logger.debug(f'Unzipping {source_filepath}...')
            # TODO: This is unsafe if the zipfile comes from an untrusted source
            unzip(source_filepath, destination_folder)
        finally:
            GlobalSettings.logger.debug('Unzipping finished.')

        # clean up the downloaded zip file
        if os.path.isfile(source_filepath):
            os.remove(source_filepath)

    GlobalSettings.logger.debug(f"Destination folder now has: {os.listdir(destination_folder)}")
#end of download_repo function


#def download_repo(base_temp_dir_name, commit_url, repo_dir):
    #"""
    #Downloads and unzips a git repository from Github or git.door43.org
    #:param str commit_url: The URL of the repository to download
    #:param str repo_dir:   The directory where the downloaded file should be unzipped
    #:return: None
    #"""
    #repo_zip_url = commit_url.replace('commit', 'archive') + '.zip'
    #repo_zip_file = os.path.join(base_temp_dir_name, repo_zip_url.rpartition(os.path.sep)[2])

    #try:
        #GlobalSettings.logger.debug(f'Downloading {repo_zip_url}...')

        ## if the file already exists, remove it, we want a fresh copy
        #if os.path.isfile(repo_zip_file):
            #os.remove(repo_zip_file)

        #download_file(repo_zip_url, repo_zip_file)
    #finally:
        #GlobalSettings.logger.debug('Downloading finished.')

    #try:
        #GlobalSettings.logger.debug(f'Unzipping {repo_zip_file}...')
        ## NOTE: This is unsafe if the zipfile comes from an untrusted source
        #unzip(repo_zip_file, repo_dir)
    #finally:
        #GlobalSettings.logger.debug('Unzipping finished.')

    ## clean up the downloaded zip file
    #if os.path.isfile(repo_zip_file):
        #os.remove(repo_zip_file)
##end of download_repo function


def process_tx_job(pj_prefix, queued_json_payload):
    """
    Sets up a temp folder in the AWS S3 bucket.

    It gathers details from the JSON payload.

    It downloads a zip file from the given repo to the temp folder and unzips the files,
        and then creates a ResourceContainer (RC) object.

    It creates a manifest_data dictionary,
        gets a TxManifest from the DB and updates it with the above,
        or creates a new one if none existed.

    It then gets and runs a preprocessor on the files in the temp folder.
        A preprocessor has a ResourceContainer (RC) and source and output folders.
        It copies the file(s) from the RC in the source folder, over to the output folder,
            assembling chunks/chapters if necessary.

    The preprocessed files are zipped up in the temp folder
        and then uploaded to the pre-convert bucket in S3.

    A TxJob is now setup and passed on to TxModule in order to
            query the AWS Dynamo DB to
            select a converter module, and
            a linter module.
        The converter and linter settings are then added to the job info
            and the job is inserted into the DB table.

    An S3 CDN folder is now named and emptied
        and a build log dictionary is created and uploaded to it.

    The project.json (in the folder above the CDN one) is also updated, e.g., with new commits.

    Conversion and linting are now initiated by sending a request to each,
        or by creating book_jobs and sending multiple requests to each.

    This code is "successful" once the conversion/linting jobs are all completed.

    The given payload will be appended to the 'failed' queue
        if an exception is thrown in this module.
    """
    GlobalSettings.logger.debug(f"Processing {pj_prefix+' ' if pj_prefix else ''}job: {queued_json_payload}")

    # Create a build log
    build_log_json = queued_json_payload
    build_log_json['started_at'] = datetime.utcnow()
    if 'expires_at' not in build_log_json:
        build_log_json['expires_at'] = build_log_json['started_at'] + timedelta(days=1)
    if 'eta' not in build_log_json:
        build_log_json['eta'] = build_log_json['started_at'] + timedelta(minutes=5)
    build_log_json['status'] = 'started'
    build_log_json['message'] = 'tX job started...'

    # Setup a temp folder to use
    # Move everything down one directory level for simple delete
    intermediate_dir_name = queued_json_payload['job_id']
    base_temp_dir_name = os.path.join(tempfile.gettempdir(), intermediate_dir_name)
    GlobalSettings.logger.debug(f"base_temp_dir_name = {base_temp_dir_name}")
    try:
        os.makedirs(base_temp_dir_name)
    except:
        GlobalSettings.logger.critical(f"Oh, folder {base_temp_dir_name} already existed!")
        GlobalSettings.logger.info(f"It contained {os.listdir(base_temp_dir_name)}")

    # Download and unzip the specified source file
    GlobalSettings.logger.debug(f"Getting source file from {queued_json_payload['source']}...")
    download_source_file(queued_json_payload['source'], base_temp_dir_name)

    # Find correct source folder
    source_folder_path = base_temp_dir_name
    dirList = os.listdir(base_temp_dir_name)
    GlobalSettings.logger.debug(f"Discovering source folder from {dirList}...")
    if len(dirList)==1:
        tryFolder = os.path.join(base_temp_dir_name, dirList[0])
        if os.path.isdir(tryFolder):
            GlobalSettings.logger.debug(f"Switching source folder to {tryFolder}")
            source_folder_path = tryFolder
    GlobalSettings.logger.info(f"Source folder contains {os.listdir(source_folder_path)}")


    ##print(f"Webhook.process_tx_job setting up TxJob with username={user.username}...")
    #print("Webhook.process_tx_job setting up TxJob...")
    #pj_job = TxJob()
    #pj_job.job_id = get_unique_job_id()
    #pj_job.identifier = pj_job.job_id
    #pj_job.user_name = user_name
    #pj_job.repo_name = repo_name
    #pj_job.commit_id = commit_id
    #pj_job.manifests_id = tx_manifest.id
    #pj_job.created_at = datetime.utcnow()
    ## Seems never used (RJH)
    ##pj_job.user = user.username  # Username of the token, not necessarily the repo's owner
    #pj_job.input_format = rc.resource.file_ext
    #pj_job.resource_type = rc.resource.identifier
    #pj_job.source = source_url_base + "/" + file_key
    #pj_job.cdn_bucket = GlobalSettings.cdn_bucket_name
    #pj_job.cdn_file = f'tx/job/{pj_job.job_id}.zip'
    #pj_job.output = f'https://{GlobalSettings.cdn_bucket_name}/{pj_job.cdn_file}'
    #pj_job.callback = GlobalSettings.api_url + '/client/callback'
    #pj_job.output_format = 'html'
    #pj_job.links = {
        #"href": f'{GlobalSettings.api_url}/tx/job/{pj_job.job_id}',
        #"rel": "self",
        #"method": "GET"
    #}
    #pj_job.success = False


    GlobalSettings.logger.debug(f"Finding linter/converter for {queued_json_payload['input_format']} {queued_json_payload['resource_type']}")
    linter = get_linter_module(queued_json_payload)
    GlobalSettings.logger.debug(f"Got linter = {linter}, {linter.__dict__}")
    converter = get_converter_module(queued_json_payload)
    GlobalSettings.logger.debug(f"Got converter = {converter}")


    if linter:
        linter_name = linter.name
        if not isinstance(linter_name, str): # bytes
            linter_name = linter_name.decode()
        build_log_json['lint_module'] = linter_name
        #extra_payload = {'s3_results_key': s3_commit_key}
        #send_request_to_linter(pj_job, linter, commit_url, queued_json_payload, extra_payload=extra_payload)
        # Log dict gets updated by the following line
        do_linting(build_log_json, source_folder_path, linter_name)
    else:
        GlobalSettings.logger.warning(f"No linter was found to lint {queued_json_payload['input_format']} {queued_json_payload['resource_type']}")

    if converter:
        converter_name = converter.name
        if not isinstance(converter_name, str): # bytes
            converter_name = converter_name.decode()
        build_log_json['convert_module'] = converter_name
        #extra_payload = {'s3_results_key': s3_commit_key}
        #send_request_to_converter(pj_job, converter, commit_url, queued_json_payload, extra_payload=extra_payload)
        # Log dict gets updated by the following line
        do_converting(build_log_json, source_folder_path, converter_name)
    else:
        GlobalSettings.logger.warning(f"No converter was found to convert {queued_json_payload['input_format']} {queued_json_payload['resource_type']} to {queued_json_payload['output_format']}")


    #if converter:
        #pj_job.convert_module = converter.name
        #pj_job.started_at = datetime.utcnow()
        #pj_job.expires_at = pj_job.started_at + timedelta(days=1)
        #pj_job.eta = pj_job.started_at + timedelta(minutes=5)
        #pj_job.status = 'started'
        #pj_job.message = 'Conversion started...'
        #pj_job.log_message(f'Started job for {pj_job.user_name}/{pj_job.repo_name}/{pj_job.commit_id}')
    #else:
        #pj_job.error_message(f'No converter was found to convert {pj_job.resource_type} ' \
                                    #f'from {pj_job.input_format} to {pj_job.output_format}')
        #pj_job.message = 'No converter found'
        #pj_job.status = 'failed'

    #pj_job.insert() # into DB

    ## Get S3 cdn bucket/dir and empty it
    #s3_commit_key = f'u/{pj_job.user_name}/{pj_job.repo_name}/{pj_job.commit_id}'
    #clear_commit_directory_in_cdn(s3_commit_key)

    ## Create a build log
    #build_log_json = create_build_log(commit_id, commit_message, commit_url, compare_url, pj_job,
                                            #pusher_username, repo_name, user_name)
    ## Upload an initial build_log
    #upload_build_log_to_s3(base_temp_dir_name, build_log_json, s3_commit_key)

    ## Update the project.json file
    #update_project_json(base_temp_dir_name, commit_id, pj_job, repo_name, user_name)


    ## Convert and lint
    #if converter:
        #if not preprocessor.is_multiple_jobs():
            #send_request_to_converter(pj_job, converter)
            #if linter:
                #extra_payload = {'s3_results_key': s3_commit_key}
                #send_request_to_linter(pj_job, linter, commit_url, queued_json_payload, extra_payload=extra_payload)
        #else:
            ## -----------------------------
            ## Project with multiple books
            ## -----------------------------
            #book_filenames = preprocessor.get_book_list()
            #GlobalSettings.logger.debug('Splitting job into separate parts for books: ' + ','.join(book_filenames))
            #book_count = len(book_filenames)
            #build_log_json['multiple'] = True
            #build_log_json['build_logs'] = []
            #for i, book_filename in enumerate(book_filenames):
                #GlobalSettings.logger.debug(f'Adding job for {book_filename}, part {i} of {book_count}')
                ## Send job request to tx-manager
                #if i == 0:
                    #book_job = pj_job  # use the original job created above for the first book
                    #book_job.identifier = f'{pj_job.job_id}/{book_count}/{i}/{book_filename}'
                #else:
                    #book_job = pj_job.clone()  # copy the original job for this book's job
                    #book_job.job_id = get_unique_job_id()
                    #book_job.identifier = f'{book_job.job_id}/{book_count}/{i}/{book_filename}'
                    #book_job.cdn_file = f'tx/job/{book_job.job_id}.zip'
                    #book_job.output = f'https://{GlobalSettings.cdn_bucket_name}/{book_job.cdn_file}'
                    #book_job.links = {
                        #"href": f"{GlobalSettings.api_url}/tx/job/{book_job.job_id}",
                        #"rel": "self",
                        #"method": "GET"
                    #}
                    #book_job.insert()

                #book_job.source = build_multipart_source(source_url_base, file_key, book_filename)
                #book_job.update()
                #book_build_log = create_build_log(commit_id, commit_message, commit_url, compare_url, book_job,
                                                        #pusher_username, repo_name, user_name)
                #if book_filename:
                    #book_build_log['book'] = book_filename
                    #book_build_log['part'] = str(i)
                #build_log_json['build_logs'].append(book_build_log)
                #upload_build_log_to_s3(base_temp_dir_name, book_build_log, s3_commit_key, str(i) + "/")
                #send_request_to_converter(book_job, converter)
                #if linter:
                    #extra_payload = {
                        #'single_file': book_filename,
                        #'s3_results_key': f'{s3_commit_key}/{i}'
                    #}
                    #send_request_to_linter(book_job, linter, commit_url, queued_json_payload, extra_payload=extra_payload)

    # Do the callback if requested
    if 'callback' in queued_json_payload:
        GlobalSettings.logger.debug(f"tX-Job-Handler about to do callback to {queued_json_payload['callback']} ...")
        # Copy the build log but convert times to strings
        callback_payload = build_log_json
        for key,value in callback_payload.items():
            if isinstance(value, (datetime, date)):
                callback_payload[key] = value.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            response = requests.post(queued_json_payload['callback'], json=callback_payload)
        except requests.exceptions.ConnectionError as e:
            GlobalSettings.logger.critical(f"Callback connection error: {e}")
            response = None
        if response:
            GlobalSettings.logger.info(f"response.status_code = {response.status_code}")
            GlobalSettings.logger.info(f"response.reason = {response.reason}")
            GlobalSettings.logger.debug(f"response.headers = {response.headers}")
            GlobalSettings.logger.debug(f"response.text = {response.text}")
            try:
                GlobalSettings.logger.info(f"response.json = {response.json()}")
            except json.decoder.JSONDecodeError:
                GlobalSettings.logger.info("No valid response JSON found")

    #remove_tree(base_temp_dir_name)  # cleanup
    #print("process_tx_job() is returning:", build_log_json)
    #return build_log_json
#end of process_tx_job function


def job(queued_json_payload):
    """
    This function is called by the rq package to process a job in the queue(s).

    The job is removed from the queue before the job is started,
        but if the job throws an exception or times out (timeout specified in enqueue process)
            then the job gets added to the 'failed' queue.
    """
    GlobalSettings.logger.info("tX-Job-Handler received a job" + (" (in debug mode)" if debug_mode_flag else ""))
    start_time = time()
    stats_client.incr('jobs.attempted')

    #current_job = get_current_job()
    #print(f"Current job: {current_job}") # Mostly just displays the job number and payload
    #print("dir",dir(current_job))
    #print("id",current_job.id) # Displays job number
    #print("origin",current_job.origin) # Displays queue name
    #print("meta",current_job.meta) # Empty dict

    #print(f"Got a job from {current_job.origin} queue: {queued_json_payload}")
    #print(f"\nGot job {current_job.id} from {current_job.origin} queue")
    #queue_prefix = 'dev-' if current_job.origin.startswith('dev-') else ''
    #assert queue_prefix == prefix
    process_tx_job(prefix, queued_json_payload)

    elapsed_milliseconds = round((time() - start_time) * 1000)
    stats_client.timing('job.duration', elapsed_milliseconds)
    stats_client.incr('jobs.completed')
    GlobalSettings.logger.info(f"tX job handling completed in {elapsed_milliseconds:,} milliseconds!")
# end of job function

# end of webhook.py
