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
import requests
import json
import hashlib
from datetime import datetime, timedelta, date
from time import time

# Library (PyPi) imports
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



OUR_NAME = 'tX_job_handler'
our_adjusted_name = prefix + OUR_NAME # Used for statsd prefix

GlobalSettings(prefix=prefix)
if prefix not in ('', 'dev-'):
    GlobalSettings.logger.critical(f"Unexpected prefix: {prefix!r} -- expected '' or 'dev-'")

# Enable DEBUG logging for dev- instances (but less logging for production)
#GlobalSettings.logger.basicConfig(level=logging.DEBUG if prefix else logging.ERROR)


CONVERTER_CALLBACK = f'{GlobalSettings.api_url}/client/callback/converter'
LINTER_CALLBACK = f'{GlobalSettings.api_url}/client/callback/linter'


# Get the Graphite URL from the environment, otherwise use a local test instance
graphite_url = os.getenv('GRAPHITE_HOSTNAME', 'localhost')
stats_client = StatsClient(host=graphite_url, port=8125, prefix=our_adjusted_name)


def send_request_to_converter(srtc_job, converter):
    """
    :param TxJob srtc_job:
    :param TxModule converter:
    :return bool:
    """
    payload = {
        'identifier': srtc_job.identifier,
        'source_url': srtc_job.source,
        'resource_id': srtc_job.resource_type,
        'cdn_bucket': srtc_job.cdn_bucket,
        'cdn_file': srtc_job.cdn_file,
        'options': srtc_job.options,
        'convert_callback': CONVERTER_CALLBACK
    }
    # NOTE: The returned result is not currently used
    return send_payload_to_converter(payload, converter)
# end of send_request_to_converter function


def send_payload_to_converter(payload, converter):
    """
    :param dict payload:
    :param TxModule converter:
    :return bool:
    """
    # TODO: Make this use urllib2 to make a async POST to the API. Currently invokes Lambda directly XXXXXXXXXXXXXXXXX
    payload = {
        'data': payload,
        'vars': {
            'prefix': GlobalSettings.prefix
        }
    }
    converter_name = converter.name
    if not isinstance(converter_name, str): # bytes in Python3 -- not sure where it gets set
        converter_name = converter_name.decode()
    print("converter_name", repr(converter_name))
    GlobalSettings.logger.debug(f'Sending Payload to converter {converter_name}:')
    GlobalSettings.logger.debug(payload)
    converter_function = f'{GlobalSettings.prefix}tx_convert_{converter_name}'
    print(f"send_payload_to_converter: converter_function is {converter_function!r} payload={payload}")
    stats_client.incr('ConvertersInvoked')
    # TODO: Put an alternative function call in here RJH
    response = GlobalSettings.lambda_handler().invoke(function_name=converter_function, payload=payload, asyncFlag=True)
    GlobalSettings.logger.debug('finished.')
    return response
# end of send_payload_to_converter function


def send_request_to_linter(srtl_job, linter, commit_url, commit_data, extra_payload=None):
    """
    :param TxJob srtl_job:
    :param TxModule linter:
    :param string commit_url:
    :param dict extra_payload:
    :return bool:
    """
    payload = {
        'identifier': srtl_job.identifier,
        'resource_id': srtl_job.resource_type,
        'cdn_bucket': srtl_job.cdn_bucket,
        'cdn_file': srtl_job.cdn_file,
        'options': srtl_job.options,
        'lint_callback': LINTER_CALLBACK,
        'commit_data': commit_data
    }
    if extra_payload:
        payload.update(extra_payload)
    if srtl_job.input_format == 'usfm' or srtl_job.resource_type == 'obs':
        # Need to give the massaged source since it maybe was in chunks originally
        payload['source_url'] = srtl_job.source
    else:
        payload['source_url'] = commit_url.replace('commit', 'archive') + '.zip'
    # NOTE: The returned result is not currently used
    return send_payload_to_linter(payload, linter)
# end of send_request_to_linter function


def send_payload_to_linter(payload, linter):
    """
    :param dict payload:
    :param TxModule linter:
    :return bool:
    """
    # TODO: Make this use urllib2 to make a async POST to the API. Currently invokes Lambda directly
    payload = {
        'data': payload,
        'vars': {
            'prefix': GlobalSettings.prefix
        }
    }
    linter_name = linter.name
    if not isinstance(linter_name, str): # bytes in Python3 -- not sure where it gets set
        linter_name = linter_name.decode()
    print("linter_name", repr(linter_name))
    GlobalSettings.logger.debug(f'Sending payload to linter {linter_name}:')
    GlobalSettings.logger.debug(payload)
    linter_function = f'{GlobalSettings.prefix}tx_lint_{linter_name}'
    print(f"send_payload_to_linter: linter_function is {linter_function!r}, payload={payload}")
    stats_client.incr('LintersInvoked')
    # TODO: Put an alternative function call in here RJH
    response = GlobalSettings.lambda_handler().invoke(function_name=linter_function, payload=payload, asyncFlag=True)
    GlobalSettings.logger.debug('finished.')
    return response
# end of send_payload_to_linter function


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


def get_converter_module(gcm_job):
    """
    :param TxJob gcm_job:
    :return TxModule:
    """
    converters = TxModule.query().filter(TxModule.type == 'converter') \
        .filter(TxModule.input_format.contains(gcm_job.input_format)) \
        .filter(TxModule.output_format.contains(gcm_job.output_format))
    converter = converters.filter(TxModule.resource_types.contains(gcm_job.resource_type)).first()
    if not converter:
        converter = converters.filter(TxModule.resource_types.contains('other')).first()
    return converter
# end if get_converter_module function


def get_linter_module(glm_job):
    """
    :param TxJob glm_job:
    :return TxModule:
    """
    linters = TxModule.query().filter(TxModule.type == 'linter') \
        .filter(TxModule.input_format.contains(glm_job.input_format))
    linter = linters.filter(TxModule.resource_types.contains(glm_job.resource_type)).first()
    if not linter:
        linter = linters.filter(TxModule.resource_types.contains('other')).first()
    return linter
# end of get_linter_module function


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
    print(f"download_source_file( {source_url}, {destination_folder} )")
    source_filepath = os.path.join(destination_folder, source_url.rpartition(os.path.sep)[2])
    print(f"source_filepath: {source_filepath}")

    try:
        GlobalSettings.logger.debug(f'Downloading {source_url}...')

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

    print(f"Destination folder now has: {os.listdir(destination_folder)}")
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


def process_job(pj_prefix, queued_json_payload):
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
    try:
        os.makedirs(base_temp_dir_name)
    except:
        GlobalSettings.logger.critical(f"Oh, folder {base_temp_dir_name} already existed!")
        GlobalSettings.logger.info(f"It contained {os.listdir(base_temp_dir_name)}")
        pass
    print("base_temp_dir_name", repr(base_temp_dir_name))

    # Download and unzip the specified source file
    download_source_file(queued_json_payload['source'], base_temp_dir_name)

    ## Download and unzip the repo files
    #repo_dir = get_repo_files(base_temp_dir_name, commit_url, repo_name)

    ## Get the resource container
    #rc = RC(repo_dir, repo_name)

    ## Save manifest to manifest table
    #manifest_data = {
        #'repo_name': repo_name,
        #'user_name': user_name,
        #'lang_code': rc.resource.language.identifier,
        #'resource_id': rc.resource.identifier,
        #'resource_type': rc.resource.type,
        #'title': rc.resource.title,
        #'manifest': json.dumps(rc.as_dict()),
        #'last_updated': datetime.utcnow()
    #}
    #print("client_webhook got manifest_data:", manifest_data) # RJH


    ## First see if manifest already exists in DB and update it if it is
    #print(f"client_webhook getting manifest for {repo_name!r} with user {user_name!r}") # RJH
    #tx_manifest = TxManifest.get(repo_name=repo_name, user_name=user_name)
    #if tx_manifest:
        #for key, value in manifest_data.items():
            #setattr(tx_manifest, key, value)
        #GlobalSettings.logger.debug(f'Updating manifest in manifest table: {manifest_data}')
        #tx_manifest.update()
    #else:
        #tx_manifest = TxManifest(**manifest_data)
        #GlobalSettings.logger.debug(f'Inserting manifest into manifest table: {tx_manifest}')
        #tx_manifest.insert()

    ## Preprocess the files
    #preprocess_dir = tempfile.mkdtemp(dir=base_temp_dir_name, prefix='preprocess_')
    #preprocessor_result, preprocessor = do_preprocess(rc, repo_dir, preprocess_dir)

    ## Zip up the massaged files
    #zip_filepath = tempfile.mktemp(dir=base_temp_dir_name, suffix='.zip')
    #GlobalSettings.logger.debug(f'Zipping files from {preprocess_dir} to {zip_filepath}...')
    #add_contents_to_zip(zip_filepath, preprocess_dir)
    #GlobalSettings.logger.debug('Zipping finished.')

    ## Upload zipped file to the S3 pre-convert bucket
    #file_key = upload_zip_file(commit_id, zip_filepath)

    ##print(f"Webhook.process_job setting up TxJob with username={user.username}...")
    #print("Webhook.process_job setting up TxJob...")
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


    #converter = get_converter_module(pj_job)
    #linter = get_linter_module(pj_job)

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

    #if linter:
        #pj_job.lint_module = linter.name
    #else:
        #GlobalSettings.logger.debug(f'No linter was found to lint {pj_job.resource_type}')

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
        GlobalSettings.logger.debug(f"tX-Job-Handler about to do callback to {queued_json_payload['callback']}")
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
            print("response.status_code", response.status_code)
            print("response.reason", response.reason)
            print("response.headers", response.headers)
            print("response.text", response.text)
            try:
                print("response.json", response.json())
            except json.decoder.JSONDecodeError:
                print("No valid response JSON found")

    #remove_tree(base_temp_dir_name)  # cleanup
    #print("process_job() is returning:", build_log_json)
    #return build_log_json
#end of process_job function


def job(queued_json_payload):
    """
    This function is called by the rq package to process a job in the queue(s).

    The job is removed from the queue before the job is started,
        but if the job throws an exception or times out (timeout specified in enqueue process)
            then the job gets added to the 'failed' queue.
    """
    GlobalSettings.logger.info("TX-Job-Handler received a job" + (" (in debug mode)" if debug_mode_flag else ""))
    start_time = time()
    stats_client.incr('JobsStarted')

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
    process_job(prefix, queued_json_payload)

    elapsed_milliseconds = round((time() - start_time) * 1000)
    stats_client.timing('JobTime', elapsed_milliseconds)
    stats_client.incr('JobsCompleted')
    GlobalSettings.logger.info(f"tX job handling completed in {elapsed_milliseconds:,} milliseconds!")
# end of job function

# end of webhook.py
