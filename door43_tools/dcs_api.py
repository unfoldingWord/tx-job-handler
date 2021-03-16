import requests
import giteapy
import yaml
from giteapy.rest import ApiException
from urllib.parse import urlencode

DEFAULT_BRANCH = 'master'
PRODUCTION_DCS_DOMAIN = "https://qa.door43.org"
QA_DCS_DOMAIN = "https://qa.door43.org"
API_LATEST_VERSION = 1
CATALOG_NEXT_LATEST_VERSION = 4


class DcsApi(object):
    def __init__(self, dcs_domain=None, api_version=API_LATEST_VERSION,
                 catalog_version=CATALOG_NEXT_LATEST_VERSION, debug=False):
        self.dcs_domain = dcs_domain
        if dcs_domain:
            self.cs_domain = dcs_domain
        elif debug:
            self.dcs_domain = QA_DCS_DOMAIN
        else:
            self.dcs_domain = PRODUCTION_DCS_DOMAIN

        self.api_base_url = f"{dcs_domain}/api/v{api_version}"
        self.catalog_url = f"{dcs_domain}/api/catalog/v{catalog_version}"
        self.api_config = giteapy.Configuration()
        self.api_config.host = self.api_base_url
        self.gitea_api = giteapy.ApiClient(configuration=self.api_config)
        self.repo_api = giteapy.RepositoryApi(api_client=self.gitea_api)

    def get_manifest(self, owner, repo_name):
        try:
            # Currently just gets the manifest of the master branch
            # Todo: when DCS goes to Gitea 1.14 and giteapy adds ref= to the raw file contents param, add to the below
            response = self.repo_api.repo_get_raw_file(owner, repo_name, 'manifest.yaml')
            return yaml.safe_load(response.data)
        except ApiException as e:
            print("Exception when calling RepositoryApi->repo_get_raw_file: %s\n" % e)
            return None

    def get_repo(self, owner, repo_name):
        try:
            # Currently just gets the manifest of the master branch
            # Todo: when DCS goes to Gitea 1.14 and giteapy adds ref= to the raw file contents param, add to the below
            response = self.repo_api.repo_get(owner, repo_name)
            return response
        except ApiException as e:
            print("Exception when calling RepositoryApi->repo_get: %s\n" % e)
            return None

    def get_catalog_entry(self, owner, repo_name, ref=None):
        if not ref:
            ref = DEFAULT_BRANCH
        url = f"{self.catalog_url}/entry/{owner}/{repo_name}/{ref}"
        print(url)
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            return None

    def get_last_commit(self, owner, repo_name, ref=None):
        query = {
            'limit': 1
        }
        if ref:
            query['sha'] = ref
        url = f"{self.api_base_url}/repos/{owner}/{repo_name}/commits?{urlencode(query)}"
        print(url)
        response = requests.get(url)
        if response.status_code == 200:
            commits = response.json()
        else:
            commits = []
        if len(commits):
            return commits[0]
        else:
            return None

    def query_catalog(self, search=None, owners=None, repos=None, tags=None, langs=None, stage=None,
                      subjects=None, checking_levels=None, books=None, include_history=False,
                      include_metadata=True, show_ingredients=False, sort=None, order=None, page=1, limit=1000):
        query = {
            'q': search,
            'owner': owners,
            'repo': repos,
            'tag': tags,
            'lang': langs,
            'stage': stage,
            'subject': subjects,
            'checkingLevel': checking_levels,
            'book': books,
            'includeHistory': include_history,
            'includeMetadata': include_metadata,
            'showIngredients': show_ingredients,
            'sort': sort,
            'order': order,
            'page': page,
            'limit': limit,
        }
        query = {k: v for k, v in query.items() if v is not None}
        url = f"{self.catalog_url}/?{urlencode(query, doseq=True)}"
        print(url)
        response = requests.get(url)
        return response.json()
