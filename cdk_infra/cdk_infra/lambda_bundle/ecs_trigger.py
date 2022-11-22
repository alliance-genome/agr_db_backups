import logging
import os
import boto3

from helper import APP_DESCRIPTION, APP_OPTIONS

def lambda_handler(event, context):

    log_level = 'INFO'
    if 'loglevel' in event and event['loglevel'] != None:
        log_level = event['loglevel'].upper()

    logging.getLogger().setLevel(os.environ.get("LOGLEVEL", log_level))

    logging.info("Event data received:\n"+str(event))

    help_json = {
        "description": APP_DESCRIPTION+
                       " Send in a json payload with one or more of the below options as key-value pairs."+
                       " Backup/restore will get executed through ECS (async) and URLs for tracking the ECS task"+
                       " status and viewing the logs will be returned (sync).",
        "options": APP_OPTIONS
    }

    if 'help' in event:
        logging.info("Help response:\n"+str(help_json))
        return help_json

    cmd_overwrite = event_data_to_CMD(event)

    ecs_client = boto3.client('ecs')
    ecs_response = ecs_client.run_task(
        count=1,
        cluster=os.environ.get('AGRDB_ECS_CLUSTER'),
        launchType='FARGATE',
        networkConfiguration={
            'awsvpcConfiguration': {
                'subnets': ['subnet-0d4703177afb1797d', 'subnet-04262fc338f638054'
                    , 'subnet-044457c061edf85f2', 'subnet-04019d42d5c9e6fb9', 'subnet-049778993fb504a7c'],
                'assignPublicIp': 'DISABLED'
            }
        },
        overrides = {
            'containerOverrides': [{
                'name': os.environ.get('AGRDB_CONTAINER_NAME'),
                'command': cmd_overwrite
            }]
        },
        taskDefinition = os.environ.get('AGRDB_ECS_TASK_DEF')
    )

    task_arn = ecs_response['tasks'][0]['taskArn']
    task_short_name = task_arn.split('/').pop()

    task_logs_url = os.environ.get('AGRDB_LOG_URL_TEMPLATE').format(task_short_name)
    task_details_url = os.environ.get('AGRDB_ECS_TASK_DETAILS_URL_TEMPLATE').format(task_short_name)

    response = { 'initiated_task_arn': task_arn, 'task_logs_url': task_logs_url, 'task_details_url': task_details_url }

    logging.info("Function response returned:\n"+str(response))

    return response

def event_data_to_CMD(event_data):
    """This function parses lambda event data and
        returns it as CMD arguments for the ECS task to take as CMD overwrite (as input args)."""

    CMD = []
    for key, value in event_data.items():
        CMD.append('--'+key)
        CMD.append(value)

    return CMD
