import logging
import os
import boto3

def lambda_handler(event, context):

    logger = logging.getLogger(context.function_name)

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

    return { 'initiated_task_arn': task_arn, 'task_logs_url': task_logs_url, 'task_details_url': task_details_url }

def event_data_to_CMD(event_data):
    """This function parses lambda event data and
        returns it as CMD arguments for the ECS task to take as CMD overwrite (as input args).
        TODO: Figure out possibility to reuse the app.interfaces.helper module to return help directly?"""
    CMD = []
    for key, value in event_data.items():
        CMD.append(key)
        CMD.append(value)

    return CMD
