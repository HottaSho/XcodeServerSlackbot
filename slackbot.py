import os, zipfile, plistlib, json, requests, time, re

def change_directory():
	# environment variables and paths
	home = os.environ.get('HOME')
	bot_name = os.environ.get('XCS_BOT_NAME').split()[0]
	integration = os.environ.get('XCS_INTEGRATION_NUMBER')
	output_directory = '%s/%s/%s' % (home, os.environ.get('OUTPUT_PATH'), integration)
	path = '/Library/Developer/XcodeServer/IntegrationAssets/'

	os.chdir(path)
	assets_files = os.listdir('.')
	bot_folder = [i for i, s in enumerate(assets_files) if bot_name in s][0]
	os.chdir('%s/%s' % (assets_files[bot_folder], integration))

	# Xcode finishes post script before bundle is created so have to wait
	while not os.path.exists('xcodebuild_result.bundle.zip'):
		time.sleep(1)

	if not os.path.exists('%s/xcodebuild_result.bundle' % output_directory):
		zip_ref = zipfile.ZipFile('xcodebuild_result.bundle.zip', 'r')
		zip_ref.extractall('%s/' % output_directory)
		zip_ref.close()

	os.chdir('%s/xcodebuild_result.bundle' % output_directory)

def parse_plist():
	data = {}
	pl = plistlib.readPlist('Info.plist')

	# Add testcases
	total_testcases = pl['TestsCount']
	failed_testcases = pl['TestsFailedCount']
	passed_testcases = total_testcases - failed_testcases

	data_attachments = []

	failure_summaries = pl.get('TestFailureSummaries', '')
	for test in failure_summaries:
		attachment = {}
		testcase = test['TestCase']
		testcase = testcase[2:len(testcase)-3].split()
		message = test['Message']

		attachment['color'] = 'danger'
		attachment['title'] = re.sub(r"(\w)([A-Z])", r"\1 \2", testcase[1][4:])
		attachment['text'] = message.splitlines()[0]
		attachment['footer'] = testcase[0]

		data_attachments.append(attachment)

	# Add initial text
	devices = set()
	devices_str = ''
	for action in pl['Actions']:
		device = action['RunDestination']['Name']
		if not device in devices:
			devices.add(device)
			devices_str += ', %s' % device if len(devices_str) else device		

	data_text = (
			'Test Setup: %s.\nDevices: %s.\nTestcases: Passed: %s, Failed: %s' % 
			(
				str(os.environ.get('XCS_PRIMARY_REPO_BRANCH')),
				devices_str,
				str(passed_testcases),
				str(failed_testcases)
			)
		)

	# Create data dictionary
	data['icon_emoji'] = ':thunder_cloud_and_rain:' if failed_testcases else ':unicorn_face:'
	data['text'] = data_text
	data['attachments'] = data_attachments

	return data

if __name__ == "__main__":
	print('Starting bot...')
	slack_url = os.environ.get('SLACK_WEBHOOK_URL')
	change_directory()
	slack_data = parse_plist()
	print('Posting')

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
