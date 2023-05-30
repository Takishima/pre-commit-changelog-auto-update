#   Copyright 2023 <Damien Nguyen>
#
#   Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#   documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
#   rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
#   permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
#   Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
#   THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
#   TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#   SOFTWARE.

"""Script used to update CHANGELOG file based on pull request generated by pre-commit.ci."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import keepachangelog
import mdformat

_version_regex = r'v?([0-9]+(?:\.[0-9]+){0,2})'
_url_regex = r'[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}/\b([-a-zA-Z0-9()@:%_\+.~#?&\/=]*)'


def clean_version_str(version: str) -> str:
    """
    Clean version string.

    Args:
        version: Version as a string
    """
    if version.startswith(('v', 'V')):
        return version[1:]
    return version


def get_changelog(changelog_path: Path, show_unreleased: bool = False) -> dict[str, str]:
    """
    Read a CHANGELOG file.

    Args:
        changelog_path: Path to a changelog file
        show_unreleased: Whether to read data from unreleased section or not
    """
    changelog = keepachangelog.to_dict(str(changelog_path), show_unreleased=show_unreleased)

    if 'unreleased' not in changelog:
        versions = [v['metadata']['version'] for k, v in changelog.items() if v['metadata']['version'] != 'unreleased']
        last_version, _ = keepachangelog.to_sorted_semantic([clean_version_str(version) for version in versions])[-1]
        version_name = next(version for version in versions if last_version in version)

        changelog = {
            'unreleased': {
                'metadata': {
                    'release_data': None,
                    'url': f'https://github.com/Takishima/flake8-secure-coding-standard/compare/{version_name}...HEAD',
                    'version': 'unreleased',
                },
            },
            **changelog,
        }
    return changelog


def parse_changelog(changelog_dict: dict[str, str], target_section: str) -> tuple[list, dict[str, str]]:
    """
    Parse dictionary containing CHANGELOG data.

    Args:
        changelog_dict: Dictionary contaning the CHANGELOG data
        target_section: Content section to read data from
    """
    new_content = []
    hook_data = {}
    for item in changelog_dict['unreleased'].setdefault(target_section, []):
        hook_match = re.match(rf'(?:-\s+)Update `([a-zA-Z0-9_\-/]+)`(?: hook)? to {_version_regex}', item)
        if hook_match:
            hook_data[hook_match.group(1)] = hook_match.group(2)
        elif item:
            new_content.append(item)

    return new_content, hook_data


def parse_pull_request_body(pr_body):
    """
    Parse the pull request body generated by pre-commit.ci.

    Args:
        pr_body: Body of the pull request
    """
    pr_body_marker_start = '<!--pre-commit.ci start-->'
    pr_body_marker_end = '<!--pre-commit.ci end-->'

    skip = True
    new_hook_data = {}
    for line in pr_body.splitlines():
        if line.strip() == pr_body_marker_start:
            skip = False
            continue
        if skip:
            continue
        if line.strip() == pr_body_marker_end:
            break
        hook_line = re.match(r'-\s+\[(.*)\].*', line.strip())
        if hook_line:
            hook_match = re.match(rf'{_url_regex}\s*:\s*{_version_regex}\s+→\s+{_version_regex}', hook_line.group(1))
            if hook_match:
                new_hook_data[hook_match.group(1)] = hook_match.group(3)
    return new_hook_data


def udpate_changelog_from_pr_body(changelog_path: Path, pr_body: str, target_section: str) -> None:
    """
    Update a CHANGELOG file based on pre-commit.ci pull request body.

    Modifies the CHANGELOG file in-place.

    Args:
        changelog_path: Path to a changelog file
        pr_body: Body of the pull request
        target_section: Content section to read data from
    """
    changelog = get_changelog(changelog_path, show_unreleased=True)
    new_content, hook_data = parse_changelog(changelog, target_section)
    new_hook_data = parse_pull_request_body(pr_body)

    # Take care of cases where the CHANGELOG has a short name for the hook
    # e.g. "Update `black` hook to..." instead of "Update `psf/black` hook to..."
    for hook, version in hook_data.items():
        if not any(hook.lower() in new_hook.lower() for new_hook in new_hook_data):
            new_hook_data[hook] = version

    for hook_name in sorted(new_hook_data, key=str.lower):
        new_content.append(f'-   Update `{hook_name}` hook to v{new_hook_data[hook_name]}')

    changelog['unreleased'][target_section] = new_content

    with changelog_path.open(mode='wt', encoding='utf-8') as fd:
        fd.write(mdformat.text(keepachangelog.from_dict(changelog), options={'number': True}))


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(description='Update a CHANGELOG file based on pre-commit.ci pull request body')
    parser.add_argument(
        '-f', '--file', dest='path', help='Path to CHANGELOG file (defauls to CHANGELOG.md)', default='CHANGELOG.md'
    )
    parser.add_argument('--pr-body', help='Body of pull request generated by pre-commit.ci.', required=True)
    parser.add_argument(
        '--target-section',
        help='Sub-section to look for hook updates in CHANGELOG (e.g. `Added`)',
        default='repository',
    )

    args = parser.parse_args()

    udpate_changelog_from_pr_body(Path(args.path), args.pr_body, 'repository')


if __name__ == '__main__':
    main()