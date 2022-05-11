import logging
import subprocess
from datetime import date
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
    if 'err_msg' in args_response:
        logger.error('Error while retrieving args: '+args_response['err_msg'])
        exit

    db_args = args_response['db_args']
    logger.info('env: '+db_args['env'])
    logger.info('identifier: '+db_args['identifier'])
    logger.debug('db_args: {}'.format(db_args))

    logger.info('Creating backup to S3...')
    backup_response = backup_postgres_to_s3(db_args)
    if 'err_msg' in backup_response:
        logger.error('Error while running backup: '+backup_response['err_msg'])
        exit #TODO: figure out if this is the correct way to indicate failure in lambda

    return {
        'message' : 'Backup completed successfully.'
    }

def get_args_dict(event, arg_set):

    logger = logging.getLogger(__name__)

    #Default values
    return_args = {
        'env': 'dev',
        'region': 'us-east-1'
    }

    if 'identifier' in event:
        return_args['identifier'] = event['identifier']
    else:
        error_message = "Missing input argument identifier"
        return {'err_msg': error_message}

    if 'env' in event:
        return_args['env'] = event['env']
    if 'region' in event:
        return_args['region'] = event['region']

    # Retrieve database details from ssm if not defined directly
    logger.info('Setting up ssm client...')
    ssm_client = boto3.client('ssm', region_name=return_args['region'])
    logger.info('Defining ssm parameter name template...')
    ssm_parameter_name = '/{env}/cron/backup/{identifier}/{{}}'.format(env=return_args['env'], identifier=return_args['identifier'])

    for arg_key, ssm_key in arg_set.items():
        logger.debug('\tDefining {}...'.format(arg_key))
        if arg_key in event:
            return_args[arg_key] = event[arg_key]
        else:
            logger.debug("\t\tRetrieving {} from SSM...".format(arg_key))
            param_name = ssm_parameter_name.format(ssm_key)
            try:
                param = ssm_client.get_parameter(Name=param_name, WithDecryption=True)
                return_args[arg_key] = param['Parameter']['Value']
            except ssm_client.exceptions.ParameterNotFound as err:
                error_message = "db_host not found in SSM for env {env} identifier {identifier} ({param_name}).".format(
                    env=return_args['env'], identifier=return_args['identifier'], param_name=param_name)
                return {'err_msg': error_message}

    return { 'db_args': return_args }

def backup_postgres_to_s3(db_args):

    logger = logging.getLogger(__name__)

    backup_command = 'PGPASSWORD={PGPASS} pg_dump -Fc -v -h {DB_HOST} -U {DB_USER} -d {DB_NAME}'.format(
        PGPASS=db_args['db_password'], DB_HOST=db_args['db_host'], DB_USER=db_args['db_user'], DB_NAME=db_args['db_name'])

    today_str = date.today().strftime("%Y-%m-%d")
    filename = '{env}-{identifier}-{date}.dump'.format(env=db_args['env'], identifier=db_args['identifier'], date=today_str)
    s3_target = 's3://{s3_bucket}/{filename}'.format(s3_bucket=db_args['s3_bucket'], filename=filename)
    with open(s3_target, 'wb', transport_params={'client': boto3.client('s3', region_name=db_args['region'])}) as wout:
        process = subprocess.Popen(backup_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

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
