# NOTE: This module name and function name are defined by the rq package and our own tx-enqueue-job package
# This code adapted by RJH Sept 2018 from webhook.py

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
from datetime import datetime, timedelta
from time import time

# Library (PyPi) imports
from rq import get_current_job
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



OUR_NAME = 'tX_callback_handler'
our_adjusted_name = prefix + OUR_NAME # Used for statsd prefix

GlobalSettings(prefix=prefix)
if prefix not in ('', 'dev-'):
    GlobalSettings.logger.critical(f"Unexpected prefix: {prefix!r} -- expected '' or 'dev-'")

# Enable DEBUG logging for dev- instances (but less logging for production)
# NOTE: Done in global_settings.py
#GlobalSettings.logger.basicConfig(level=logging.DEBUG if prefix else logging.INFO)


# Get the Graphite URL from the environment, otherwise use a local test instance
graphite_url = os.getenv('GRAPHITE_HOSTNAME', 'localhost')
stats_client = StatsClient(host=graphite_url, port=8125, prefix=our_adjusted_name)


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


def download_repo(base_temp_dir_name, commit_url, repo_dir):
    """
    Downloads and unzips a git repository from Github or git.door43.org
    :param str|unicode commit_url: The URL of the repository to download
    :param str|unicode repo_dir:   The directory where the downloaded file should be unzipped
    :return: None
    """
    repo_zip_url = commit_url.replace('commit', 'archive') + '.zip'
    repo_zip_file = os.path.join(base_temp_dir_name, repo_zip_url.rpartition(os.path.sep)[2])

    try:
        GlobalSettings.logger.debug(f'Downloading {repo_zip_url}...')

        # if the file already exists, remove it, we want a fresh copy
        if os.path.isfile(repo_zip_file):
            os.remove(repo_zip_file)

        download_file(repo_zip_url, repo_zip_file)
    finally:
        GlobalSettings.logger.debug('Downloading finished.')

    try:
        GlobalSettings.logger.debug(f'Unzipping {repo_zip_file}...')
        # NOTE: This is unsafe if the zipfile comes from an untrusted source
        unzip(repo_zip_file, repo_dir)
    finally:
        GlobalSettings.logger.debug('Unzipping finished.')

    # clean up the downloaded zip file
    if os.path.isfile(repo_zip_file):
        os.remove(repo_zip_file)
#end of download_repo function


def process_callback(pc_prefix, queued_json_payload):
    """
    TODO

    The given payload will be appended to the 'failed' queue
        if an exception is thrown in this module.
    """
    GlobalSettings.logger.debug(f"Processing {pc_prefix+' ' if pc_prefix else ''}callback: {queued_json_payload}")

    ## Setup a temp folder to use
    #source_url_base = f'https://s3-{GlobalSettings.aws_region_name}.amazonaws.com/{GlobalSettings.pre_convert_bucket_name}'
    ## Move everything down one directory level for simple delete
    #intermediate_dir_name = OUR_NAME
    #base_temp_dir_name = os.path.join(tempfile.gettempdir(), intermediate_dir_name)
    #try:
        #os.makedirs(base_temp_dir_name)
    #except:
        #pass
    ##print("source_url_base", repr(source_url_base), "base_temp_dir_name", repr(base_temp_dir_name))

    ## Get the commit_id, commit_url
    #commit_id = queued_json_payload['after']
    #commit = None
    #for commit in queued_json_payload['commits']:
        #if commit['id'] == commit_id:
            #break
    #commit_id = commit_id[:10]  # Only use the short form
    #commit_url = commit['url']
    ##print("commit_id", repr(commit_id), "commit_url", repr(commit_url))

    ## Gather other details from the commit that we will note for the job(s)
    #user_name = queued_json_payload['repository']['owner']['username']
    #repo_name = queued_json_payload['repository']['name']
    ##print("user_name", repr(user_name), "repo_name", repr(repo_name))
    #compare_url = queued_json_payload['compare_url']
    #commit_message = commit['message']
    ##print("compare_url", repr(compare_url), "commit_message", repr(commit_message))

    #if 'pusher' in queued_json_payload:
        #pusher = queued_json_payload['pusher']
    #else:
        #pusher = {'username': commit['author']['username']}
    #pusher_username = pusher['username']
    ##print("pusher", repr(pusher), "pusher_username", repr(pusher_username))

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

    ##print(f"Webhook.process_callback setting up TxJob with username={user.username}...")
    #print("Webhook.process_callback setting up TxJob...")
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

    ## Pass the work onto the tX system
    ## NOTE: The system isn't implemented yet -- this is just the beginnings of it
    #tx_post_url = f'http://git.door43.org/{prefix}tx/'
    #print(f"About to POST request to tX system @ {tx_post_url}")
    ## TODO: What headers do we really need?
    #headers = {"Content-type": "application/json",}
    ## TODO: What payload do we really need?
    #tx_payload = {
        #'identifier': pj_job.identifier,
        #'source_url': pj_job.source,
        #'resource_id': pj_job.resource_type,
        #'cdn_bucket': pj_job.cdn_bucket,
        #'cdn_file': pj_job.cdn_file,
        #'options': pj_job.options,
        #'callback': f'http://git.door43.org/{prefix}client/webhook/tx-callback/',
    #}
    #req = Request(tx_post_url, urlencode(tx_payload).encode(), headers)
    #try:
        #response = urlopen(req)
        #print("response", response)
        #response_json = response.read().decode()
        #print("response json", response_json)
    #except urllib_error.HTTPError as e:
        #GlobalSettings.logger.error(f"tX POST request got {e}")

    ## For now, we ignore the above
    ##   and just go ahead and process it the old way anyway so it keeps working
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

    #remove_tree(base_temp_dir_name)  # cleanup
    #print("process_callback() is returning:", build_log_json)
    #return build_log_json
    return {"ok":"ok"}
#end of process_callback function


def job(queued_json_payload):
    """
    This function is called by the rq package to process a job in the queue(s).

    The job is removed from the queue before the job is started,
        but if the job throws an exception or times out (timeout specified in enqueue process)
            then the job gets added to the 'failed' queue.
    """
    GlobalSettings.logger.info("TX-Job-Handler received a callback" + (" (in debug mode)" if debug_mode_flag else ""))
    start_time = time()
    stats_client.incr('CallbacksStarted')

    current_job = get_current_job()
    #print(f"Current job: {current_job}") # Mostly just displays the job number and payload
    #print("dir",dir(current_job))
    #print("id",current_job.id) # Displays job number
    #print("origin",current_job.origin) # Displays queue name
    #print("meta",current_job.meta) # Empty dict

    #print(f"Got a job from {current_job.origin} queue: {queued_json_payload}")
    #print(f"\nGot job {current_job.id} from {current_job.origin} queue")
    queue_prefix = 'dev-' if current_job.origin.startswith('dev-') else ''
    assert queue_prefix == prefix
    process_callback(queue_prefix, queued_json_payload)

    elapsed_milliseconds = round((time() - start_time) * 1000)
    stats_client.timing('CallbackTime', elapsed_milliseconds)
    stats_client.incr('CallbacksCompleted')
    GlobalSettings.logger.info(f"tX callback handling completed in {elapsed_milliseconds:,} milliseconds!")
# end of job function

# end of callback.py
