import logging
import os
import subprocess
from datetime import datetime
from smart_open import open

import boto3

def lambda_handler(event, context):

	logger = logging.getLogger(context.function_name)

	logger.info('Retrieving input args...')

	DB_ARG_PARAMS = {       #key-value pairs matching {`input_param_name`: `ssm_param_key`}
		'db_host' :     'host',
		'db_name' :     'name',
		'db_user' :     'user',
		'db_password' : 'password',
		's3_bucket' :   'bucket'
	};
	args_response = get_args_dict(event, DB_ARG_PARAMS)
	if 'help' in args_response:
		logger.info(args_response['help'])
		return args_response['help']
	if 'err_msg' in args_response:
		err_msg = 'Error while retrieving args: '+args_response['err_msg']
		logger.error(err_msg)
		raise Exception(err_msg)

	db_args = args_response['db_args']
	logger.info('target_env: '+db_args['target_env'])
	logger.info('identifier: '+db_args['identifier'])
	logger.debug('db_args: {}'.format(db_args))

	response = []
	if db_args['action'] == 'backup':
		logger.info('Creating backup to S3...')
		response = backup_postgres_to_s3(db_args)
	elif db_args['action'] == 'restore':
		logger.info('Restoring backup from S3...')
		response = restore_s3_to_postgres(db_args)

	if 'err_msg' in response:
		err_msg = 'Error while running {action}: {msg}'.format(
			action=db_args['action'], msg=response['err_msg'])
		logger.error(err_msg)
		raise Exception(err_msg)

	return {
		'message' : '{action} completed successfully.'.format(action=db_args['action'])
	}

def get_args_dict(event, arg_set):

	logger = logging.getLogger(__name__)

	help_json = {
		"description": "This function can backup any AGR database or restore an earlier made"+
		               " backup to the same or a different environment (e.g. for data roll-down)."+
		               " Send in a json payload with one or more of the below options as key-value pairs.",
		"options": {
			"action":       "Define an action to perform. Value must be either 'backup' or 'restore'.",
			"db_host":      "Host URL of target DB. Defaults to AWS SSM parameter store value.",
			"db_name":      "DB name of target DB. Defaults to AWS SSM parameter store value.",
			"db_password":  "DB password for target DB. Defaults to AWS SSM parameter store value.",
			"db_user":      "DB username for target DB. Defaults to AWS SSM parameter store value.",
			"help":         "Print this help text (provide any value).",
			"identifier":   "Application identifier to backup/restore for (for example 'curation').",
			"prod_restore": "Extra flag to prevent accidental restores to 'production' environments."+
			                " Define this argument as 'true' to confirm intend to do a production environment restore.",
			"region":       "AWS region to retrieve/write backups from/to. Defaults to 'us-east-1'.",
			"s3_bucket":    "AWS S3 bucket name to retrieve/write backups from/to. Defaults to AWS SSM parameter store value.",
			"src_env":      "The source environment to find a backup from to restore."+
			                " Defaults to 'production', only relevant for restore action.",
			"target_env":   "The target environment to backup/restore from/to. Defaults to 'dev'."
		}
	}
	if 'help' in event:
		return {'help': help_json}

	#Default values
	return_args = {
		'target_env': 'dev',
		'src_env': 'production',
		'region': 'us-east-1'
	}

	#Input argument validation
	if 'action' in event:
		if event['action'] not in ('backup', 'restore'):
			error_message = "Argument action can only have value 'backup' or 'restore'"
			return {'err_msg': error_message}

		return_args['action'] = event['action']
	else:
		error_message = "Missing input argument action"
		return {'err_msg': error_message}

	if 'identifier' in event:
		return_args['identifier'] = event['identifier']
	else:
		error_message = "Missing input argument identifier"
		return {'err_msg': error_message}

	if 'target_env' in event:
		return_args['target_env'] = event['target_env']
	if 'src_env' in event:
		return_args['src_env'] = event['src_env']

	# Prevent data roll-up from environments with lower data integrity
	# to environments with higher data integrity
	if return_args['action'] == 'restore' and env_rank(return_args['src_env']) > env_rank(return_args['target_env']):
		error_message = "Action 'restore' is not allowed to target env {target} from source env {source}."\
		                .format(target=return_args['target_env'],source=return_args['src_env'])
		return {'err_msg': error_message}

	# Prevent accidental production environment restore
	if return_args['action'] == 'restore' and return_args['target_env'] == 'production':
		if 'prod_restore' not in event or event['prod_restore'] != 'true':
			error_message = "Action 'restore' to target env production requested, but prod_restore is not defined as 'true'."
			return {'err_msg': error_message}

	if 'region' in event:
		return_args['region'] = event['region']

	# Retrieve database details from ssm if not defined directly
	logger.info('Setting up ssm client...')
	ssm_client = boto3.client('ssm', region_name=return_args['region'])
	logger.info('Defining ssm parameter name template...')
	ssm_parameter_name = '/{identifier}/{{env}}/db/backup/{{keyname}}'.format(identifier=return_args['identifier'])

	for arg_key, ssm_key in arg_set.items():
		logger.debug('\tDefining {}...'.format(arg_key))
		if arg_key in event and event[arg_key] != "":
			return_args[arg_key] = event[arg_key]
		else:
			logger.debug("\t\tRetrieving {} from SSM...".format(arg_key))

			env = ''
			#For restore action calls, fetch s3_bucket from src_env rather than target_env (to ensure correct src file retrieval)
			if event['action'] == 'restore' and arg_key == 's3_bucket':
				env = return_args['src_env']
			#In all other cases, target_env value from SSM
			else:
				env=return_args['target_env']

			param_name = ssm_parameter_name.format(env=env, keyname=ssm_key)
			logger.debug("\t\t... as param {param_name} for env {env}, identifier {identifier}".format(
					env=env, identifier=return_args['identifier'], param_name=param_name))
			try:
				param = ssm_client.get_parameter(Name=param_name, WithDecryption=True)
				return_args[arg_key] = param['Parameter']['Value']
			except ssm_client.exceptions.ParameterNotFound as err:
				error_message = "parameter {param_name} not found in SSM for env {env} identifier {identifier}.".format(
					env=return_args['env'], identifier=return_args['identifier'], param_name=param_name)
				return {'err_msg': error_message}

	return { 'db_args': return_args }

def backup_postgres_to_s3(db_args):

	logger = logging.getLogger(__name__)

	backup_command = 'pg_dump -Fc -v -d {DB_NAME}'.format(DB_NAME=db_args['db_name'])

	now_datetime_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
	filename = '{identifier}/{env}/{date}.dump'.format(identifier=db_args['identifier'], env=db_args['target_env'], date=now_datetime_str)
	s3_target = 's3://{s3_bucket}/{filename}'.format(s3_bucket=db_args['s3_bucket'], filename=filename)
	s3_transport_params = {
		'client': boto3.client('s3', region_name=db_args['region']),
		'client_kwargs': {
			'S3.Client.create_multipart_upload': {'StorageClass': 'GLACIER_IR'}
		}
	}
	with open(s3_target, 'wb', transport_params=s3_transport_params) as wout:
		pg_env = os.environ.copy()
		pg_env["PGUSER"] = db_args['db_user']
		pg_env["PGHOST"] = db_args['db_host']
		pg_env["PGPASSWORD"] = db_args['db_password']

		process = subprocess.Popen(backup_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, env=pg_env)

		logger.info("Streaming backup to {}...".format(s3_target))
		for c in iter(lambda: process.stdout.read(1), b''):
			wout.write(c)

		exitcode = process.wait()
		if exitcode != 0:
			error_message = "pg_dump execution failed (exitcode {}).\n".format(exitcode)
			out, err = process.communicate()
			error_message += err.decode()

			return {'err_msg': error_message}

	return {}

def restore_s3_to_postgres(db_args):
	"""
	This function will drop the specified target_env db,
	recreate an empty one, and populate it with
	the latest DB dump found from the src_env
	"""

	logger = logging.getLogger(__name__)

	# now_datetime_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
	filename_prefix = '{identifier}/{env}/'.format(identifier=db_args['identifier'], env=db_args['src_env'])
	# s3_target = 's3://{s3_bucket}/{filename}'.format(s3_bucket=db_args['s3_bucket'], filename=filename_prefix)

	latest_backup_s3_filepath = get_latest_s3_backup(db_args['s3_bucket'], filename_prefix)
	tmp_local_filepath = '/tmp/'+latest_backup_s3_filepath.replace('/','-')

	logger.info('Retrieving latest backup: '+latest_backup_s3_filepath)

	s3 = boto3.client('s3')
	s3.download_file(db_args['s3_bucket'], latest_backup_s3_filepath, tmp_local_filepath)

	# -h {DB_HOST} -U {DB_USER}
	dropdb_cmd  = 'dropdb {DB_NAME}'.format(DB_NAME=db_args['db_name'])
	createdb_cmd  = 'createdb {DB_NAME}'.format(DB_NAME=db_args['db_name'])
	restore_cmd = 'pg_restore -Fc -v -j 8 -d {DB_NAME} {FILENAME}'.format(
		DB_NAME=db_args['db_name'],
		FILENAME=tmp_local_filepath)

	pg_env = os.environ.copy()
	pg_env["PGUSER"] = db_args['db_user']
	pg_env["PGHOST"] = db_args['db_host']
	pg_env["PGPASSWORD"] = db_args['db_password']

	logger.info("Dropping DB {DB} at host {HOST}...".format(DB=db_args['db_name'], HOST=db_args['db_host']))
	process_dbdrop = subprocess.Popen(dropdb_cmd, shell=True, stderr=subprocess.PIPE, env=pg_env)
	exitcode_dbdrop = process_dbdrop.wait()
	if exitcode_dbdrop != 0:
		error_message = "dropdb execution failed (exitcode {}).\n".format(exitcode_dbdrop)
		out, err = process_dbdrop.communicate()
		error_message += err.decode()

		return {'err_msg': error_message}

	logger.info("Recreating DB {DB} at host {HOST}...".format(DB=db_args['db_name'], HOST=db_args['db_host']))
	process_dbcreate = subprocess.Popen(createdb_cmd, shell=True, stderr=subprocess.PIPE, env=pg_env)
	exitcode_dbcreate = process_dbcreate.wait()
	if exitcode_dbcreate != 0:
		error_message = "createdb execution failed (exitcode {}).\n".format(exitcode_dbcreate)
		out, err = process_dbcreate.communicate()
		error_message += err.decode()

		return {'err_msg': error_message}

	logger.info("Restoring dump {dumpfile} to DB {DB} at host {HOST}...".format(
		dumpfile=tmp_local_filepath,DB=db_args['db_name'], HOST=db_args['db_host']))
	process_dbrestore = subprocess.Popen(restore_cmd, shell=True, stderr=subprocess.PIPE, env=pg_env)
	exitcode_dbrestore = process_dbrestore.wait()

	# Currently every restore to a non-RDS location "fails" because
	# the role "rdsadmin" does not exist on local postgres installations.
	if exitcode_dbrestore != 0:
		error_message = "pg_restore execution failed (exitcode {}).\n".format(exitcode_dbrestore)
		out, err = process_dbrestore.communicate()
		error_message += err.decode()

		return {'err_msg': error_message}

	return {}

def get_latest_s3_backup(bucket_name, prefix):

	logger = logging.getLogger(__name__)

	s3 = boto3.client('s3')
	paginator = s3.get_paginator( "list_objects_v2" )

	logger.debug('Finding latest backup in bucket {bucket} with prefix {prefix}...'.format(bucket=bucket_name, prefix=prefix))
	page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
	latest_all = None
	for page in page_iterator:
		if "Contents" in page:
			latest_page = max(page['Contents'], key=lambda x: x['LastModified'])
			if latest_all is None or latest_page['LastModified'] > latest_all['LastModified']:
				latest_all = latest_page

	return latest_all['Key']

def env_rank(env_name):
	'''
	Function to return the rank of an environment.
	Higher ranked envs (lower integer value) should have
	better data consistency than lower ranked ones.
	'''
	ENV_RANK = {
		'production': 1,
		'prod':  1,
		'beta':  2,
		'alpha': 3,
		'dev': 4
	}

	if env_name in ENV_RANK:
		return ENV_RANK[env_name]
	# If the environment name is unkown, rank it below all known envs
	else:
		return max(ENV_RANK.values())+1
