import logging
import os
import subprocess
from datetime import datetime

import boto3

import importlib
from interfaces.helper import SSM_ARG_PARAMS
lambda_interface = importlib.import_module('interfaces.lambda')
cli_interface    = importlib.import_module('interfaces.cli')

def main(options):

	log_level = 'INFO'
	if 'loglevel' in options and options['loglevel'] != None:
		log_level = options['loglevel'].upper()

	logging.basicConfig(level=os.environ.get("LOGLEVEL", log_level))

	logging.info('Processing input args...')

	args_response = get_args_dict(options, SSM_ARG_PARAMS)
	if 'err_msg' in args_response:
		err_msg = 'Error while retrieving args: '+args_response['err_msg']
		logging.error(err_msg)
		raise Exception(err_msg)

	db_args = args_response['db_args']
	logging.info('target_env: '+db_args['target_env'])
	logging.info('identifier: '+db_args['identifier'])
	logging.debug('db_args: {}'.format(db_args))

	response = []
	if db_args['action'] == 'backup':
		logging.info('Creating backup to S3...')
		response = backup_postgres_to_s3(db_args)
	elif db_args['action'] == 'restore':
		logging.info('Restoring backup from S3...')
		response = restore_s3_to_postgres(db_args)

	if 'err_msg' in response:
		err_msg = 'Error while running {action}: {msg}'.format(
			action=db_args['action'], msg=response['err_msg'])
		logging.error(err_msg)
		raise Exception(err_msg)

	return '{action} completed successfully.'.format(action=db_args['action'])

def get_args_dict(options, arg_set):

	#Default values
	return_args = {
		'target_env': 'dev',
		'src_env': 'production',
		'region': 'us-east-1'
	}

	#Input argument validation
	if 'action' in options and options['action'] != None:
		if options['action'] not in ('backup', 'restore'):
			error_message = "Argument action can only have value 'backup' or 'restore'"
			return {'err_msg': error_message}

		return_args['action'] = options['action']
	else:
		error_message = "Missing input argument action"
		return {'err_msg': error_message}

	if 'identifier' in options and options['identifier'] != None:
		return_args['identifier'] = options['identifier']
	else:
		error_message = "Missing input argument identifier"
		return {'err_msg': error_message}

	if 'target_env' in options and options['target_env'] != None:
		return_args['target_env'] = options['target_env']
	if 'src_env' in options and options['src_env'] != None:
		return_args['src_env'] = options['src_env']

	if 'restore_timestamp' in options and options['restore_timestamp'] != None and return_args['action'] != 'restore':
		error_message = "Input argument restore_timestamp only relevant for restore action."
		return {'err_msg': error_message}

	if return_args['action'] == 'restore':
		# Prevent data roll-up from environments with lower data integrity
		# to environments with higher data integrity
		if env_rank(return_args['src_env']) > env_rank(return_args['target_env']):
			error_message = "Action 'restore' is not allowed to target env {target} from source env {source}."\
							.format(target=return_args['target_env'],source=return_args['src_env'])
			return {'err_msg': error_message}

		# Prevent accidental production environment restore
		if return_args['target_env'] == 'production':
			if 'prod_restore' not in options or options['prod_restore'] != 'true':
				error_message = "Action 'restore' to target env production requested, but prod_restore is not defined as 'true'."
				return {'err_msg': error_message}

		if 'restore_timestamp' in options and options['restore_timestamp'] != None:
			return_args['restore_timestamp'] = options['restore_timestamp']
		else:
			return_args['restore_timestamp'] = ''

		if 'ignore_privileges' in options and options['ignore_privileges'] == 'true':
			return_args['ignore_privileges'] = True

	if 'region' in options and options['region'] != None:
		return_args['region'] = options['region']

	# Retrieve database details from ssm if not defined directly
	logging.info('Setting up ssm client...')
	ssm_client = boto3.client('ssm', region_name=return_args['region'])
	logging.info('Defining ssm parameter name template...')
	ssm_parameter_name = '/{identifier}/{{env}}/db/backup/{{keyname}}'.format(identifier=return_args['identifier'])

	for arg_key, ssm_key in arg_set.items():
		logging.debug('\tDefining {}...'.format(arg_key))
		if arg_key in options and options[arg_key] != None and options[arg_key] != "":
			logging.debug("\t\tRetrieving {} from options...".format(arg_key))
			return_args[arg_key] = options[arg_key]
		else:
			logging.debug("\t\tRetrieving {} from SSM...".format(arg_key))

			env = ''
			#For restore action calls, fetch s3_bucket from src_env rather than target_env (to ensure correct src file retrieval)
			if options['action'] == 'restore' and arg_key == 's3_bucket':
				env = return_args['src_env']
			#In all other cases, target_env value from SSM
			else:
				env=return_args['target_env']

			param_name = ssm_parameter_name.format(env=env, keyname=ssm_key)
			logging.debug("\t\t... as param {param_name} for env {env}, identifier {identifier}".format(
					env=env, identifier=return_args['identifier'], param_name=param_name))
			try:
				param = ssm_client.get_parameter(Name=param_name, WithDecryption=True)
				return_args[arg_key] = param['Parameter']['Value']
			except ssm_client.exceptions.ParameterNotFound as err:
				error_message = "parameter {param_name} not found in SSM for env {env} identifier {identifier}.".format(
					env=env, identifier=return_args['identifier'], param_name=param_name)
				return {'err_msg': error_message}

	return { 'db_args': return_args }

def backup_postgres_to_s3(db_args):

	now_datetime_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
	filename = '{identifier}/{env}/{date}.dump'.format(identifier=db_args['identifier'], env=db_args['target_env'], date=now_datetime_str)

	# Create local backup
	tmp_local_filepath = '/tmp/'+filename.replace('/','-')

	backup_command = 'pg_dump -Fc -v -d {DB_NAME} -f {FILE}'.format(DB_NAME=db_args['db_name'], FILE=tmp_local_filepath)

	pg_env = os.environ.copy()
	pg_env["PGUSER"] = db_args['db_user']
	pg_env["PGHOST"] = db_args['db_host']
	pg_env["PGPASSWORD"] = db_args['db_password']

	logging.info("Storing backup to {}...".format(tmp_local_filepath))

	process = subprocess.Popen(backup_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, env=pg_env)

	stderr_str = ""
	for line in iter(process.stderr.readline, b''):
		decoded_str = line.decode().strip()
		stderr_str += decoded_str+"\n"
		logging.info(decoded_str)

	exitcode = process.wait()
	if exitcode != 0:
		error_message = "pg_dump execution failed (exitcode {}).\n".format(exitcode)\
		                +stderr_str

		return {'err_msg': error_message}

	# Upload backup to S3
	s3_target = 's3://{s3_bucket}/{filename}'.format(s3_bucket=db_args['s3_bucket'], filename=filename)
	logging.info("Uploading backup to {}...".format(s3_target))

	s3_client = boto3.client('s3')

	s3_client.upload_file(tmp_local_filepath, db_args['s3_bucket'], filename,
		ExtraArgs={'StorageClass': 'GLACIER_IR'})

	return {}

def restore_s3_to_postgres(db_args):
	"""
	This function will
	1.  Refuse all new connections to target DB
	2.  Terminate all open connections to target DB
	3.  Put target DB in readonly mode
	4.  Re-enable new connections to target DB
	5.  Create a new, temporarily named, DB
	6.  Populate the new DB with the appropriate
	    DB dump file found from the src_env
	7.  Refuse all new connections to target DB
	8.  Terminate all open connections to target DB
	9.  Drop the specified target_env db
	10. Rename the temporarily named DB to the target_env DB name
	"""

	filename_prefix = '{identifier}/{env}/{timestamp}'.format(identifier=db_args['identifier'],
	                                                          env=db_args['src_env'],
	                                                          timestamp=db_args['restore_timestamp'])

	latest_backup_s3_filepath = get_latest_s3_backup(db_args['s3_bucket'], filename_prefix)

	if latest_backup_s3_filepath == None:
		error_message = "Failed to find backup (filename_prefix {}).\n".format(filename_prefix)

		return {'err_msg': error_message}

	tmp_local_filepath = '/tmp/'+latest_backup_s3_filepath.replace('/','-')

	temp_DB_name = db_args['db_name']+datetime.now().strftime("%Y%m%d_%H%M%S")

	logging.info('Retrieving latest backup: '+latest_backup_s3_filepath)

	s3 = boto3.client('s3')
	s3.download_file(db_args['s3_bucket'], latest_backup_s3_filepath, tmp_local_filepath)

	# -h {DB_HOST} -U {DB_USER}
	dropconn_cmd = 'psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = \'{DB_NAME}\' and pid <> pg_backend_pid()"'.format(DB_NAME=db_args['db_name'])
	readonlydb_cmd = 'psql -c \'ALTER DATABASE "{DB_NAME}" SET default_transaction_read_only=on;\''.format(DB_NAME=db_args['db_name'])
	dropdb_cmd  = 'dropdb {DB_NAME}'.format(DB_NAME=db_args['db_name'])
	createdb_cmd  = 'createdb {DB_NAME}'.format(DB_NAME=temp_DB_name)
	renamedb_cmd  = 'psql -c \'ALTER DATABASE "{TEMP_DB_NAME}" RENAME TO "{DB_NAME}";\''.format(TEMP_DB_NAME=temp_DB_name,DB_NAME=db_args['db_name'])
	queryconnlimit_cmd = 'psql -t -A -c "SELECT datconnlimit FROM pg_database WHERE datname = \'{DB_NAME}\';"'.format(DB_NAME=db_args['db_name'])
	setconnlimit_cmd = 'psql -c \'ALTER DATABASE "{DB_NAME}" CONNECTION LIMIT {{connlimit}};\''.format(DB_NAME=db_args['db_name'])
	refuseconn_cmd = setconnlimit_cmd.format(connlimit=0)
	restore_cmd = 'pg_restore -Fc -v -j 8'
	if 'ignore_privileges' in db_args:
		restore_cmd += ' -O -x'
	restore_cmd += ' -d {DB_NAME}'.format(DB_NAME=temp_DB_name)
	restore_cmd += ' {FILENAME}'.format(FILENAME=tmp_local_filepath)

	pg_env = os.environ.copy()
	pg_env["PGUSER"] = db_args['db_user']
	pg_env["PGHOST"] = db_args['db_host']
	pg_env["PGPASSWORD"] = db_args['db_password']

	# Query and store current DB connection limit (for restore after DB restore completed)
	logging.info("Retrieving connection limit for DB {DB} at host {HOST}...".format(DB=db_args['db_name'], HOST=db_args['db_host']))
	process_queryconnlimit = subprocess.Popen(queryconnlimit_cmd, shell=True, stdout=subprocess.PIPE, env=pg_env)

	connlimit = process_queryconnlimit.communicate()[0].decode().strip()
	logging.info("\tCurrent connection limit for DB: {connlimit}".format(connlimit=connlimit))

	# 1.  Refuse all new connections to target DB
	logging.info("Refusing all new connections to DB...")
	process_refuseconn = subprocess.Popen(refuseconn_cmd, shell=True, stderr=subprocess.PIPE, env=pg_env)

	stderr_str = ""
	for line in iter(process_refuseconn.stderr.readline, b''):
		decoded_str = line.decode().strip()
		stderr_str += decoded_str+"\n"
		logging.info(decoded_str)

	exitcode_refuseconn = process_refuseconn.wait()
	if exitcode_refuseconn != 0:
		error_message = "Updating DB to refuse new connections failed (exitcode {}).\n".format(exitcode_refuseconn)\
		                +stderr_str

		return {'err_msg': error_message}

	# 2.  Terminate all open connections to target DB
	logging.info("Dropping all existing connections to DB...")
	process_dropconn = subprocess.Popen(dropconn_cmd, shell=True, stderr=subprocess.PIPE, env=pg_env)

	stderr_str = ""
	for line in iter(process_dropconn.stderr.readline, b''):
		decoded_str = line.decode().strip()
		stderr_str += decoded_str+"\n"
		logging.info(decoded_str)

	exitcode_dropconn = process_dropconn.wait()
	if exitcode_dropconn != 0:
		error_message = "Dropping all existing connections to DB failed (exitcode {}).\n".format(exitcode_dropconn)\
		                +stderr_str

		return {'err_msg': error_message}

	# 3.  Put target DB in readonly mode
	logging.info("Update DB to become read-only...")
	process_readonlydb = subprocess.Popen(readonlydb_cmd, shell=True, stderr=subprocess.PIPE, env=pg_env)

	stderr_str = ""
	for line in iter(process_readonlydb.stderr.readline, b''):
		decoded_str = line.decode().strip()
		stderr_str += decoded_str+"\n"
		logging.info(decoded_str)

	exitcode_readonlydb = process_readonlydb.wait()
	if exitcode_readonlydb != 0:
		error_message = "Updating DB to be read-only failed (exitcode {}).\n".format(exitcode_readonlydb)\
		                +stderr_str

		return {'err_msg': error_message}

	# 4.  Re-enable new connections to target DB
	logging.info("Allowing new (read-only) connections to DB...")
	process_allowconn = subprocess.Popen(setconnlimit_cmd.format(connlimit=connlimit), shell=True, stderr=subprocess.PIPE, env=pg_env)

	stderr_str = ""
	for line in iter(process_allowconn.stderr.readline, b''):
		decoded_str = line.decode().strip()
		stderr_str += decoded_str+"\n"
		logging.info(decoded_str)

	exitcode_allowconn = process_allowconn.wait()
	if exitcode_allowconn != 0:
		error_message = "Re-enabling DB connections (read-only) failed (exitcode {}).\n".format(exitcode_allowconn)\
		                +stderr_str

		return {'err_msg': error_message}

	# 5.  Create a new, temporarily named, DB
	logging.info("Creating new (temp) DB {}...".format(temp_DB_name))
	process_dbcreate = subprocess.Popen(createdb_cmd, shell=True, stderr=subprocess.PIPE, env=pg_env)

	stderr_str = ""
	for line in iter(process_dbcreate.stderr.readline, b''):
		decoded_str = line.decode().strip()
		stderr_str += decoded_str+"\n"
		logging.info(decoded_str)

	exitcode_dbcreate = process_dbcreate.wait()
	if exitcode_dbcreate != 0:
		error_message = "createdb execution failed (exitcode {}).\n".format(exitcode_dbcreate)\
		                +stderr_str

		return {'err_msg': error_message}

	# 6.  Populate the new DB with the appropriate
	#     DB dump file found from the src_env
	logging.info("Restoring dump {dumpfile} to DB {DB}...".format(
		dumpfile=tmp_local_filepath, DB=temp_DB_name))
	process_dbrestore = subprocess.Popen(restore_cmd, shell=True, stderr=subprocess.PIPE, env=pg_env)

	stderr_str = ""
	for line in iter(process_dbrestore.stderr.readline, b''):
		decoded_str = line.decode().strip()
		stderr_str += decoded_str+"\n"
		logging.info(decoded_str)

	exitcode_dbrestore = process_dbrestore.wait()

	logging.debug("Dump restore process exited.")

	# 7.  Refuse all new connections to target DB
	logging.info("Refusing all new connections to DB...")
	process_refuseconn = subprocess.Popen(refuseconn_cmd, shell=True, stderr=subprocess.PIPE, env=pg_env)

	stderr_str = ""
	for line in iter(process_refuseconn.stderr.readline, b''):
		decoded_str = line.decode().strip()
		stderr_str += decoded_str+"\n"
		logging.info(decoded_str)

	exitcode_refuseconn = process_refuseconn.wait()
	if exitcode_refuseconn != 0:
		error_message = "Updating DB to refuse new connections failed (exitcode {}).\n".format(exitcode_refuseconn)\
		                +stderr_str

		return {'err_msg': error_message}

	# 8.  Terminate all open connections to target DB
	logging.info("Dropping all existing connections to DB...")
	process_dropconn = subprocess.Popen(dropconn_cmd, shell=True, stderr=subprocess.PIPE, env=pg_env)

	stderr_str = ""
	for line in iter(process_dropconn.stderr.readline, b''):
		decoded_str = line.decode().strip()
		stderr_str += decoded_str+"\n"
		logging.info(decoded_str)

	exitcode_dropconn = process_dropconn.wait()
	if exitcode_dropconn != 0:
		error_message = "Dropping all existing connections to DB failed (exitcode {}).\n".format(exitcode_dropconn)\
		                +stderr_str

		return {'err_msg': error_message}

	# 9.  Drop the specified target_env db
	logging.info("Dropping original DB...")
	process_dbdrop = subprocess.Popen(dropdb_cmd, shell=True, stderr=subprocess.PIPE, env=pg_env)

	stderr_str = ""
	for line in iter(process_dbdrop.stderr.readline, b''):
		decoded_str = line.decode().strip()
		stderr_str += decoded_str+"\n"
		logging.info(decoded_str)

	exitcode_dbdrop = process_dbdrop.wait()
	if exitcode_dbdrop != 0:
		error_message = "dropdb execution failed (exitcode {}).\n".format(exitcode_dbdrop)\
		                +stderr_str

		return {'err_msg': error_message}

	# 10. Rename the temporarily named DB to the target_env DB name
	logging.info("Renaming temp DB...")
	process_dbrename = subprocess.Popen(renamedb_cmd, shell=True, stderr=subprocess.PIPE, env=pg_env)

	stderr_str = ""
	for line in iter(process_dbrename.stderr.readline, b''):
		decoded_str = line.decode().strip()
		stderr_str += decoded_str+"\n"
		logging.info(decoded_str)

	exitcode_dbrename = process_dbrename.wait()
	if exitcode_dbrename != 0:
		error_message = "Rename-DB query execution failed (exitcode {}).\n".format(exitcode_dbrename)\
		                +stderr_str

		return {'err_msg': error_message}

	# Currently every restore to a non-RDS location "fails" because
	# the role "rdsadmin" does not exist on local postgres installations.
	if exitcode_dbrestore != 0:
		error_message = "pg_restore execution failed (exitcode {}).\n".format(exitcode_dbrestore)\
		                +stderr_str

		return {'err_msg': error_message}

	return {}

def get_latest_s3_backup(bucket_name, prefix):

	s3 = boto3.client('s3')
	paginator = s3.get_paginator( "list_objects_v2" )

	logging.debug('Finding latest backup in bucket {bucket} with prefix {prefix}...'.format(bucket=bucket_name, prefix=prefix))
	page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
	latest_all = None
	for page in page_iterator:
		if "Contents" in page:
			latest_page = max(page['Contents'], key=lambda x: x['LastModified'])
			if latest_all is None or latest_page['LastModified'] > latest_all['LastModified']:
				latest_all = latest_page

	if latest_all == None:
		logging.error('No backups found in bucket {bucket} with prefix {prefix}...'.format(bucket=bucket_name, prefix=prefix))
		return None
	else:
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

def lambda_handler(event, context):
	response = lambda_interface.lambda_handler(event, context)
	return response

if __name__ == '__main__':
    cli_interface.cli_handler()
