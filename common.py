import sys
from os import  (
    getenv,
    path
)
from snyk import SnykClient
from app.utils.github_utils import (
    create_github_client,
    create_github_enterprise_client
)
import argparse
import configparser

MANIFEST_PATTERN_SCA = '^(?![.]).*(package[.]json|Gemfile[.]lock|pom[.]xml|build[.]gradle|.*[.]lockfile|build[.]sbt|.*req.*[.]txt|Gopkg[.]lock|go[.]mod|vendor[.]json|packages[.]config|.*[.]csproj|.*[.]fsproj|.*[.]vbproj|project[.]json|project[.]assets[.]json|composer[.]lock|Podfile|Podfile[.]lock)$'
MANIFEST_PATTERN_CONTAINER = '^.*(Dockerfile)$'
MANIFEST_PATTERN_IAC = '.*[.](yaml|yml|tf)$'
MANIFEST_PATTERN_CODE = '.*[.](js|cs|php|java|py)$'
MANIFEST_PATTERN_EXCLUSIONS = '^.*(fixtures|tests\/|__tests__|test\/|__test__|[.].*ci\/|.*ci[.].yml|node_modules\/|bower_components\/|variables[.]tf|outputs[.]tf).*$'

GITHUB_ENABLED = False
GITHUB_ENTERPRISE_ENABLED = False

SNYK_TOKEN = getenv("SNYK_TOKEN")
GITHUB_TOKEN = getenv("GITHUB_TOKEN")
GITHUB_ENTERPRISE_TOKEN = getenv("GITHUB_ENTERPRISE_TOKEN")
GITHUB_ENTERPRISE_HOST = getenv("GITHUB_ENTERPRISE_HOST")

LOG_PREFIX = "snyk-scm-refresh"
LOG_FILENAME = LOG_PREFIX + ".log"
POTENTIAL_DELETES_FILE = open("%s_potential-repo-deletes.csv" % LOG_PREFIX, "w")
POTENTIAL_DELETES_FILE.write("org,repo\n")
STALE_MANIFESTS_DELETED_FILE = open(
    "%s_stale-manifests-deleted.csv" % LOG_PREFIX, "w"
)
STALE_MANIFESTS_DELETED_FILE.write("org,project\n")
RENAMED_MANIFESTS_DELETED_FILE = open(
    "%s_renamed-manifests-deleted.csv" % LOG_PREFIX, "w"
)
RENAMED_MANIFESTS_DELETED_FILE.write("org,project\n")
RENAMED_MANIFESTS_PENDING_FILE = open(
    "%s_renamed-manifests-pending.csv" % LOG_PREFIX, "w"
)
RENAMED_MANIFESTS_PENDING_FILE.write("org,project\n")
COMPLETED_PROJECT_IMPORTS_FILE = open(
    "%s_completed-project-imports.csv" % LOG_PREFIX, "w"
)
COMPLETED_PROJECT_IMPORTS_FILE.write("org,project,success\n")
REPOS_SKIPPED_ON_ERROR_FILE = open(
    "%s_repos-skipped-on-error.csv" % LOG_PREFIX, "w"
)
REPOS_SKIPPED_ON_ERROR_FILE.write("org,repo,status\n")
UPDATED_PROJECT_BRANCHES_FILE = open(
    "%s_updated-project-branches.csv" % LOG_PREFIX, "w"
)
UPDATED_PROJECT_BRANCHES_FILE.write("org,project_name,project_id,new_branch\n")
UPDATE_PROJECT_BRANCHES_ERRORS_FILE = open(
    "%s_update-project-branches-errors.csv" % LOG_PREFIX, "w"
)
UPDATE_PROJECT_BRANCHES_ERRORS_FILE.write("org,project_name,project_id,new_branch\n")

PENDING_REMOVAL_MAX_CHECKS = 45
PENDING_REMOVAL_CHECK_INTERVAL = 20

snyk_client = SnykClient(SNYK_TOKEN)

if (GITHUB_TOKEN):
    GITHUB_ENABLED = True
    gh_client = create_github_client(GITHUB_TOKEN)

if (GITHUB_ENTERPRISE_HOST):
    GITHUB_ENTERPRISE_ENABLED = True
    gh_enterprise_client = create_github_enterprise_client(GITHUB_ENTERPRISE_TOKEN, GITHUB_ENTERPRISE_HOST)

def parse_command_line_args():
    """Parse command-line arguments"""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--org-id",
        type=str,
        help="The Snyk Organisation Id found in Organization > Settings. \
            If omitted, process all orgs the Snyk user has access to.",
        required=False,
    )
    parser.add_argument(
        "--repo-name",
        type=str,
        help="The full name of the repo to process (e.g. githubuser/githubrepo). \
            If omitted, process all repos in the Snyk org.",
        required=False,
    )
    parser.add_argument(
        "--sca",
        help="scan for SCA manifests (on by default)",
        required=False,
        default=True,
        choices=['on', 'off']
    )
    parser.add_argument(
        "--container",
        help="scan for container projects, e.g. Dockerfile (on by default)",
        required=False,
        default=True,
        choices=['on', 'off']
    )
    parser.add_argument(
        "--iac",
        help="scan for IAC manifests (experimental, off by default)",
        required=False,
        default=False,
        choices=['on', 'off']
    )
    parser.add_argument(
        "--code",
        help="create code analysis if not present (experimental, off by default)",
        required=False,
        default=False,
        choices=['on', 'off']
    )
    parser.add_argument(
        "--dry-run",
        help="Simulate processing of the script without making changes to Snyk",
        required=False,
        action="store_true",
    )
    parser.add_argument(
        "--debug",
        help="Write detailed debug data to snyk_scm_refresh.log for troubleshooting",
        required=False,
        action="store_true",
    )
    parser.add_argument(
        "--clean-archived",
        help="wheter to delete manifests of archived respos",
        required=False,
        default=False,
        choices=['on', 'off']
    )

    return parser.parse_args()

ARGS = parse_command_line_args()

def toggle_to_bool(toggle_value) -> bool:
    if toggle_value == "on":
        return True
    if toggle_value == "off":
        return False
    return toggle_value

PROJECT_TYPE_ENABLED_SCA = toggle_to_bool(ARGS.sca)
PROJECT_TYPE_ENABLED_CONTAINER = toggle_to_bool(ARGS.container)
PROJECT_TYPE_ENABLED_IAC = toggle_to_bool(ARGS.iac)
PROJECT_TYPE_ENABLED_CODE = toggle_to_bool(ARGS.code)
CLEAN_ARCHIVED = toggle_to_bool(ARGS.clean_archived)
