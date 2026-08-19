import datetime
import json
import logging
import os
import urllib.error
import urllib.request

import boto3

SLACK_API_URL = 'https://slack.com/api/chat.postMessage'
SIZE_DROP_THRESHOLD = 0.25


def lambda_handler(event, context):

	logging.getLogger().setLevel(os.environ.get('LOGLEVEL', 'INFO'))

	report_date = datetime.datetime.utcnow().date()
	if 'report_date' in event:
		report_date = datetime.date.fromisoformat(event['report_date'])

	backup_list = json.load(open(os.path.join(os.path.dirname(__file__), 'backup_list.json'), 'r'))
	targets = [b['payload'] for b in backup_list if b['payload'].get('action') == 'backup']

	results = [check_backup(t['identifier'], t['target_env'], report_date) for t in targets]
	results.sort(key=lambda r: (r['identifier'], r['target_env']))

	message = format_message(results, report_date)
	logging.info("Report:\n" + message['text'])

	if event.get('dry_run'):
		return {'dry_run': True, 'results': results, 'text': message['text']}

	post_to_slack(message)

	return {
		'report_date': report_date.isoformat(),
		'ok': sum(1 for r in results if r['status'] == 'ok'),
		'total': len(results),
		'results': results
	}


def check_backup(identifier, target_env, report_date):
	"""Look for a dump written on report_date under {identifier}/{target_env}/ in the
	   backup bucket, and compare its size against the previous available dump."""

	result = {'identifier': identifier, 'target_env': target_env,
	          'status': 'missing', 'size': None, 'last_seen': None, 'note': ''}

	try:
		bucket = get_ssm_value('/{}/{}/db/backup/bucket'.format(identifier, target_env))
	except Exception as e:
		result['status'] = 'error'
		result['note'] = 'could not resolve bucket: {}'.format(e)
		return result

	prefix = '{}/{}/'.format(identifier, target_env)
	objects = list_objects(bucket, prefix)

	if not objects:
		result['note'] = 'no backups found at all'
		return result

	objects.sort(key=lambda o: o['Key'])
	todays = [o for o in objects if basename(o['Key']).startswith(report_date.isoformat())]

	if not todays:
		latest = objects[-1]
		last_date = basename(latest['Key'])[:10]
		result['last_seen'] = last_date
		try:
			age = (report_date - datetime.date.fromisoformat(last_date)).days
			result['note'] = 'last backup {} ({}d ago)'.format(last_date, age)
		except ValueError:
			result['note'] = 'last backup {}'.format(last_date)
		return result

	current = todays[-1]
	result['status'] = 'ok'
	result['size'] = current['Size']

	previous = [o for o in objects if not basename(o['Key']).startswith(report_date.isoformat())]
	if previous and previous[-1]['Size'] > 0:
		drop = 1 - (current['Size'] / previous[-1]['Size'])
		if drop >= SIZE_DROP_THRESHOLD:
			result['status'] = 'shrunk'
			result['note'] = '{:.0%} smaller than {}'.format(drop, basename(previous[-1]['Key'])[:10])

	return result


def list_objects(bucket, prefix):
	s3 = boto3.client('s3')
	paginator = s3.get_paginator('list_objects_v2')
	objects = []
	for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
		objects.extend(page.get('Contents', []))
	return [o for o in objects if o['Key'].endswith('.dump')]


def get_ssm_value(name):
	return boto3.client('ssm').get_parameter(Name=name)['Parameter']['Value']


def basename(key):
	return key.split('/')[-1]


def human_size(size):
	if size is None:
		return '-'
	for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
		if size < 1024:
			return '{:.1f} {}'.format(size, unit)
		size /= 1024
	return '{:.1f} PB'.format(size)


ICONS = {'ok': ':white_check_mark:', 'shrunk': ':warning:', 'missing': ':x:', 'error': ':x:'}


def format_message(results, report_date):

	ok_count = sum(1 for r in results if r['status'] == 'ok')
	total = len(results)
	failed = [r for r in results if r['status'] not in ('ok',)]

	lines = []
	for r in results:
		name = '{}/{}'.format(r['identifier'], r['target_env'])
		lines.append('{:<22} {:>10}  {} {}'.format(
			name, human_size(r['size']), ICONS.get(r['status'], ':grey_question:'), r['note']).rstrip())

	text = '*AGR Nightly DB Backups* - {}\n\n{} of {} succeeded\n```\n{}\n```'.format(
		report_date.isoformat(), ok_count, total, '\n'.join(lines))

	return {'text': text, 'color': 'good' if not failed else 'danger'}


def post_to_slack(message):

	token = get_slack_token()
	payload = {
		'channel': os.environ['AGRDB_SLACK_CHANNEL'],
		'text': message['text'],
		'unfurl_links': False
	}

	request = urllib.request.Request(SLACK_API_URL,
		data=json.dumps(payload).encode('utf-8'),
		headers={
			'Content-Type': 'application/json; charset=utf-8',
			'Authorization': 'Bearer ' + token
		})

	with urllib.request.urlopen(request, timeout=15) as response:
		body = json.loads(response.read().decode('utf-8'))

	if not body.get('ok'):
		raise Exception('Slack chat.postMessage failed: {}'.format(body.get('error')))

	logging.info('Posted to Slack channel {}'.format(payload['channel']))


def get_slack_token():
	secret_id = os.environ['AGRDB_SLACK_TOKEN_SECRET']
	return boto3.client('secretsmanager').get_secret_value(SecretId=secret_id)['SecretString']
