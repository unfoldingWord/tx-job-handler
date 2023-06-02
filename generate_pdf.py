#!/usr/bin/env python3
#
#  Copyright (c) 2021 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

import argparse
import sys
import os
import shutil
import boto3
import dcs_api_client
from webhook import process_tx_job
from door43_tools.subjects import SUBJECT_ALIASES
from door43_tools.bible_books import BOOK_NAMES
from glob import glob
from botocore.exceptions import ClientError


def file_exists_on_s3(bucket, key):
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
    except ClientError:
        return False
    return True


def generate_pdf(repo_name, owner='unfoldingWord', ref=None, dcs_domain='git.door43.org', input_format=None, project_ids=[], output_file=None, upload=True, subject=None):
    if not owner or owner == "unfoldingword":
        owner = "unfoldingWord"
    if owner == "door43-catalog":
        owner = "Door43-Catalog"

    if '_' in repo_name:
        lang, resource = repo_name.lower().split('_')
    else:
        lang = 'en'
        resource = repo_name.lower()

    if resource == 'bhp':
        lang = 'el-x-koine'

    if not subject:
        for s, aliases in SUBJECT_ALIASES.items():
            for alias in aliases:
                if resource == alias:
                    subject = s
                    break
            else:
                continue
            break

    if subject:
        subject = subject.replace(' ', '_')

    if not input_format:
        if subject:
            if subject.startswith('TSV'):
                input_format = "tsv"
            elif subject.replace(' ', '_') in ['Aligned_Bible', 'Bible', 'Greek_New_Testament', 'Hebrew_Old_Testament']:
                input_format = "usfm"
            else:
                input_format = "md"
        else:
            input_format = "md"
 
    if project_ids:
        (map(lambda x: x.lower(), project_ids))
    else:
        project_ids = []

    api_config = dcs_api_client.Configuration()
    api_config.host = f"{dcs_domain}/api/v1"
    api_config.api_key['access_token'] = os.getenv('DCS_TOKEN')
    repo_api = dcs_api_client.RepositoryApi(dcs_api_client.ApiClient(api_config))
    release = None
    releases = repo_api.repo_list_releases(owner, repo_name)
    if not ref:
        if len(releases):
            release = releases[0]
            ref = release.tag_name
        else:
            ref = 'master'
    elif ref != 'master':
        for r in releases:
            if r.tag_name == ref:
                release = r

    output_file = output_file
    if not output_file:
        output_file = os.path.join("/tmp", f"{repo_name}_{ref}")
    if not output_file.endswith(".zip"):
        output_file = os.path.join(output_file, f"{repo_name}_{ref}.zip")
    # if os.path.exists(output_file):
    #     if input(f"Are you sure you want to overwrite {output_file}? (y/n)") != "y":
    #         return

    orig_pdf_files = sorted(glob(os.path.join(os.path.dirname(output_file), 'Output', '*.pdf')))

    if len(orig_pdf_files) < 1 or (len(orig_pdf_files) > 2 and len(orig_pdf_files) != 67):
        data = {
            "output": output_file,
            "job_id": f"Door43--{owner}--{repo_name}",
            "identifier": f"{owner}--{repo_name}",
            "resource_type": subject,
            "input_format": input_format,
            "output_format": "pdf",
            "source": f"https://{dcs_domain}/{owner}/{repo_name}/archive/{ref}.zip",
            "repo_name": repo_name,
            "repo_owner": owner,
            "repo_ref": ref,
            "repo_ref_type": "tag",
            "repo_data_url": f"https://{dcs_domain}/{owner}/{repo_name}/archive/{ref}.zip",
            "dcs_domain": f"https://{dcs_domain}",
            "project_ids": project_ids,
        }
    
        print(data)
        process_tx_job("dev", data)

        orig_pdf_files = sorted(glob(os.path.join(os.path.dirname(output_file), 'Output', '*.pdf')))

    if len(orig_pdf_files) < 1:
        print("NO PDF FILES WERE GENERATED!!!")
        sys.exit(1)

    print("PDF files were generated.")

    if not upload:
        print("Not uploading to S3 CDN")
        return

    print("Uploading...")
    mount_dir = os.path.join('/mnt', 'PDF')
    public_dir = os.path.join('/mnt', 'pCloud Drive', 'Public Folder')
    if not os.path.exists(os.path.join(mount_dir, '.mounted')):
        print(f"WARNING! UNABLE TO FIND PCLOUD PDF DIR AT: {mount_dir}")
    if not os.path.exists(os.path.join(public_dir, '.mounted')):
        print(f"WARNING! UNABLE TO FIND PCLOUD PUBLIC HTML DIR AT: {public_dir}")
    mount_files_dir = os.path.join(mount_dir, owner, repo_name, ref)
    public_files_dir = os.path.join(public_dir, owner, repo_name, ref)
    s3_client = boto3.client('s3')
    bucket_name = "cdn.door43.org"
    for orig_file in orig_pdf_files:
        filename = os.path.basename(orig_file)
        if release:
            for asset in release.assets:
                if asset.name == filename:
                    repo_api.repo_delete_release_attachment(owner, repo_name, release.id, asset.id)
                    print(f"Deleted old attchment {filename} from release {release.name}")
            repo_api.repo_create_release_attachment(owner, repo_name, release.id, orig_file)
            print(f"Created release attachment for {filename} in release {release.name}")
        else:
            print(f"There is no release for ref {ref}, so not uploading attachments.")
        mount_file = os.path.join(mount_files_dir, filename)
        public_file = os.path.join(public_files_dir, filename)
        if os.path.exists(os.path.join(mount_dir, '.mounted')):
            os.makedirs(mount_files_dir, exist_ok=True)
            shutil.copy(orig_file, mount_file)
            print(f"Copied {orig_file} to {mount_file}")
        if os.path.exists(os.path.join(public_dir, '.mounted')):
            os.makedirs(public_files_dir, exist_ok=True)
            shutil.copy(orig_file, public_file)
            print(f"Copied {orig_file} to {public_file}")
        if ref[0] == "v" or ref[0].isdigit():
            s3_path = f"{lang}/{owner}/{repo_name}/{ref}/pdf/{filename}"
            print(f'Uploading {orig_file} to Amazon S3 bucket {bucket_name}/{s3_path}')
            try:
                response = s3_client.upload_file(orig_file, bucket_name, s3_path)
            except ClientError as e:
                print(e)
                return

            s3_path = f"{lang}/{resource}/{ref}/pdf/{filename}"
            print(f'Uploading {orig_file} to Amazon S3 bucket {bucket_name}/{s3_path}')
            try:
                response = s3_client.upload_file(orig_file, bucket_name, s3_path)
            except ClientError as e:
                print(e)
                return

        s3_path = f"u/{owner}/{repo_name}/{ref}/pdf/{filename}"
        print(f'Uploading {orig_file} to Amazon S3 bucket {bucket_name}/{s3_path}')
        try:
            response = s3_client.upload_file(orig_file, bucket_name, s3_path)
        except ClientError as e:
            print(e)
            return

    if os.path.exists(os.path.join(public_dir, '.mounted')):
        orig_html_files = sorted(glob(os.path.join(os.path.dirname(output_file), 'Output', '*.html')))
        for orig_file in orig_html_files:
            public_file = os.path.join(public_files_dir, os.path.basename(orig_file))
            if 'resized' not in orig_file:
                os.makedirs(public_files_dir, exist_ok=True)
                shutil.copy(orig_file, public_file)
                print(f"Copied {orig_file} to {public_file}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-o', '--output_file', dest='output_file', required=False,
                        help='Path to output file, including the zip file name')
    parser.add_argument('--owner', dest='owner', default="unfoldingWord", required=False,
                        help='Owner of the resource repo on GitHub. Default: unfoldingWord')
    parser.add_argument('--repo', dest='repo_name', required=True, help='Repo name')
    parser.add_argument('--ref', dest='ref', required=False, help='Branch or tag name. Default: latest release or master')
    parser.add_argument('--input', dest='input_format', required=False, help='Input type. Default: md')
    parser.add_argument('-s', '--subject', dest='subject', required=False, help='subject is guessed, but you can provide it')
    parser.add_argument('-p', '--project_id', metavar='PROJECT ID', dest='project_ids', required=False, action='append',
                        help='Project ID for resources with projects, as listed in the manfiest.yaml file, such as a Bible book ' +
                        '(-p gen). Can specify multiple projects. Default: None (different converters will handle no or multiple ' +
                        'projects differently, such as compiling all into one PDF, or generating a PDF for each project)')
    parser.add_argument('--no-upload', dest='upload', action='store_false', help="Do NOT upload files to the S3 CDN")
    parser.add_argument('--dcs-domain', dest='dcs_domain', default='git.door43.org', help='DCS domain name. Default: git.door43.org')

    args = parser.parse_args(sys.argv[1:])
    generate_pdf(**vars(args))
