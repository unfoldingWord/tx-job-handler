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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-o', '--output_file', dest='output_file', required=False,
                        help='Path to output file, including the zip file name')
    parser.add_argument('--owner', dest='owner', default="unfoldingWord", required=False,
                        help='Owner of the resource repo on GitHub. Default: unfoldingWord')
    parser.add_argument('--repo', dest='repo_name',
                        required=True, help='Repo name')
    parser.add_argument('--ref', dest='ref', default='master',
                        help='Branch or tag name. Default: master')
    parser.add_argument('--input', dest='input', help='Input type. Default: md')
    parser.add_argument('-p', '--project_id', metavar='PROJECT ID', dest='project_ids', required=False, action='append',
                        help='Project ID for resources with projects, as listed in the manfiest.yaml file, such as a Bible book ' +
                        '(-p gen). Can specify multiple projects. Default: None (different converters will handle no or multiple ' +
                        'projects differently, such as compiling all into one PDF, or generating a PDF for each project)')
    parser.add_argument('--no-upload', dest='upload', action='store_false', help="Do NOT upload files to the S3 CDN")

    args = parser.parse_args(sys.argv[1:])

    upload = args.upload

    owner = args.owner
    if owner == "unfoldingword":
        owner = "unfoldingWord"
    if owner == "door43-catalog":
        owner = "Door43-Catalog"
    repo_name = args.repo_name

    lang, resource = repo_name.split('_')
    subject = None
    for s, aliases in SUBJECT_ALIASES.items():
        for alias in aliases:
            if resource == alias:
                subject = s.replace(' ', '_')
                break
        else:
            continue
        break

    input_format = args.input
    if not input_format:
        if subject.startswith('TSV'):
            input_format = "tsv"
        elif subject in ['Aligned_Bible', 'Bible']:
            input_format = "usfm"
        else:
            input_format = "md"

    project_ids = []
    if args.project_ids:
        project_ids = args.project_ids

    output_file = args.output_file
    if not output_file:
        output_file = os.path.join("/tmp", f"{repo_name}_{args.ref}")    
    if not output_file.endswith(".zip"):
        output_file = os.path.join(output_file, f"{repo_name}_{args.ref}.zip")
    if os.path.exists(output_file):
        if input(f"Are you sure you want to overwrite {output_file}? (y/n)") != "y":
            sys.exit()

    data = {
        "output": output_file,
        "job_id": f"Door43--{owner}--{repo_name}",
        "identifier": f"{owner}--{repo_name}",
        "resource_type": subject,
        "input_format": input_format,
        "output_format": "pdf",
        "source": f"https://git.door43.org/{owner}/{repo_name}/archive/{args.ref}.zip",
        "repo_name": repo_name,
        "repo_owner": owner,
        "repo_ref": args.ref,
        "repo_data_url": f"https://git.door43.org/{owner}/{repo_name}/archive/{args.ref}.zip",
        "dcs_domain": "https://git.door43.org",
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
        sys.exit()

    print("Uploading...")
    mount_dir = os.path.join('/mnt', 'PDF')
    public_dir = os.path.join('/mnt', 'pCloud Drive', 'Public Folder')
    if not os.path.exists(os.path.join(mount_dir, '.mounted')):
        print(f"WARNING! UNABLE TO FIND PCLOUD PDF DIR AT: {mount_dir}")
    if not os.path.exists(os.path.join(public_dir, '.mounted')):
        print(f"WARNING! UNABLE TO FIND PCLOUD PUBLIC HTML DIR AT: {public_dir}")
    mount_files_dir = os.path.join(mount_dir, owner, args.repo_name, args.ref)
    public_files_dir = os.path.join(public_dir, owner, args.repo_name, args.ref)
    s3_client = boto3.client('s3')
    bucket_name = "cdn.door43.org"
    for orig_file in orig_pdf_files:
        mount_file = os.path.join(mount_files_dir, os.path.basename(orig_file))
        public_file = os.path.join(public_files_dir, os.path.basename(orig_file))
        if os.path.exists(os.path.join(mount_dir, '.mounted')):
            os.makedirs(mount_files_dir, exist_ok=True)
            shutil.copy(orig_file, mount_file)
            print(f"Copied {orig_file} to {mount_file}")
        if os.path.exists(os.path.join(public_dir, '.mounted')):
            os.makedirs(public_files_dir, exist_ok=True)
            shutil.copy(orig_file, public_file)
            print(f"Copied {orig_file} to {public_file}")
        if args.ref[0] == "v" or args.ref[0].isdigit():
            s3_path = f"{lang}/{owner}/{repo_name}/{args.ref}/pdf/{os.path.basename(orig_file)}"
            print(f'Uploading {orig_file} to Amazon S3 bucket {bucket_name}/{s3_path}')
            try:
                response = s3_client.upload_file(orig_file, bucket_name, s3_path)
            except ClientError as e:
                print(e)
                sys.exit()

            s3_path = f"{lang}/{resource}/{args.ref}/pdf/{os.path.basename(orig_file)}"
            print(f'Uploading {orig_file} to Amazon S3 bucket {bucket_name}/{s3_path}')
            try:
                response = s3_client.upload_file(orig_file, bucket_name, s3_path)
            except ClientError as e:
                print(e)
                sys.exit()

        s3_path = f"u/{owner}/{repo_name}/{args.ref}/pdf/{os.path.basename(orig_file)}"
        print(f'Uploading {orig_file} to Amazon S3 bucket {bucket_name}/{s3_path}')
        try:
            response = s3_client.upload_file(orig_file, bucket_name, s3_path)
        except ClientError as e:
            print(e)
            sys.exit()

    if os.path.exists(os.path.join(public_dir, '.mounted')):
        orig_html_files = sorted(glob(os.path.join(os.path.dirname(output_file), 'Output', '*.html')))
        for orig_file in orig_html_files:
            public_file = os.path.join(public_files_dir, os.path.basename(orig_file))
            if 'resized' not in orig_file:
                os.makedirs(public_files_dir, exist_ok=True)
                shutil.copy(orig_file, public_file)
                print(f"Copied {orig_file} to {public_file}")
