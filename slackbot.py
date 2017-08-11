"""Python script that posts test results into slack."""

import os
import zipfile
import plistlib
import json
import time
import re
import shutil
import requests


def change_directory():
    """Change directory to where output plist is."""
    # environment variables and paths
    home = os.environ.get('HOME')
    bot_name = os.environ.get('XCS_BOT_NAME').split()[0]
    integration = os.environ.get('XCS_INTEGRATION_NUMBER')
    output_directory = '%s/Downloads/%s' % (home, integration)
    path = '/Library/Developer/XcodeServer/IntegrationAssets/'

    os.chdir(path)
    bot_folder = [s for s in os.listdir('.') if bot_name in s][0]
    os.chdir('%s/%s' % (bot_folder, integration))

    # Xcode finishes post script before bundle is created so have to wait
    while not os.path.exists('xcodebuild_result.bundle.zip'):
        time.sleep(1)

    if not os.path.exists('%s/xcodebuild_result.bundle' % output_directory):
        zip_ref = zipfile.ZipFile('xcodebuild_result.bundle.zip', 'r')
        zip_ref.extractall('%s/' % output_directory)
        zip_ref.close()

    os.chdir('%s/xcodebuild_result.bundle' % output_directory)


def remove_directory():
    """Remove temporary directory."""
    integration = os.environ.get('XCS_INTEGRATION_NUMBER')
    os.chdir('../..')
    shutil.rmtree(integration)


def format_failure_text(text):
    """Format failure text and return it."""
    if 'Failure attempting to launch' in text:
        return 'Failure attempting to launch'
    return text.splitlines()[0]


def parse_plist():
    """Parse plist to get testcase information."""
    change_directory()

    data = {}
    plist = plistlib.readPlist('Info.plist')

    # Add testcases
    failed_testcases = plist['TestsFailedCount']
    passed_testcases = plist['TestsCount'] - failed_testcases

    data_attachments = []

    failure_summaries = plist.get('TestFailureSummaries', '')
    for test in failure_summaries:
        attachment = {}
        testcase = test['TestCase']
        testcase = testcase[2:len(testcase) - 3].split()
        message = test['Message']

        attachment['color'] = 'danger'
        attachment['title'] = re.sub(r"(\w)([A-Z])", r"\1 \2", testcase[1][4:])
        attachment['text'] = format_failure_text(message)
        attachment['footer'] = testcase[0]

        data_attachments.append(attachment)

    # Add setup and device information
    devices = set()
    devices_str = ''
    for action in plist['Actions']:
        device = action['RunDestination']['Name']
        if device not in devices:
            devices.add(device)
            devices_str += ', %s' % device if devices_str else device

    data_text = (
        'Test Setup: %s | %s.\nTestcases: Passed: %s, Failed: %s' %
        (
            str(os.environ.get('XCS_PRIMARY_REPO_BRANCH')),
            devices_str,
            str(passed_testcases),
            str(failed_testcases)
        )
    )

    # Create dictionary for slackbot
    data['icon_emoji'] = (
        ':thunder_cloud_and_rain:' if failed_testcases else ':unicorn_face:'
    )
    data['text'] = data_text
    data['attachments'] = data_attachments

    remove_directory()

    return data

if __name__ == "__main__":
    slack_url = os.environ.get('SLACK_WEBHOOK_URL')
    slack_data = parse_plist()

    # Post to slack
    response = requests.post(
        slack_url, data=json.dumps(slack_data),
        headers={'Content-Type': 'application/json'}
    )
    if response.status_code != 200:
        raise ValueError(
            'Request to slack returned an error %s, the response is:\n%s'
            % (response.status_code, response.text)
        )
