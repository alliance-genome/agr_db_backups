from os import path

from aws_cdk import Duration, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda


class LambdaEcsTrigger:

    def __init__(self, scope: Stack, ecs_cluster_arn: str, ecs_task_def_arn: str,
                    container_name: str, log_url_template: str, task_details_template: str) -> None:

        # Create lambda function role
        excecution_role = iam.Role(scope, "agr-db-backups-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonECS_FullAccess")
            ]
        )

        # Create lambda function
        aws_lambda.Function(scope, "agrDbBackupsLambdaTrigger",
            function_name='agr_db_backups_ecs',
            runtime=aws_lambda.Runtime.PYTHON_3_7,
            handler="ecs_trigger.lambda_handler",
            code=aws_lambda.Code.from_asset(path.join(path.dirname(path.realpath(__file__)), "lambda_bundle")),
            environment={
                'AGRDB_ECS_CLUSTER': ecs_cluster_arn,
                'AGRDB_ECS_TASK_DEF': ecs_task_def_arn,
                'AGRDB_CONTAINER_NAME': container_name,
                'AGRDB_LOG_URL_TEMPLATE': log_url_template,
                'AGRDB_ECS_TASK_DETAILS_URL_TEMPLATE': task_details_template
            },
            role=excecution_role,
            timeout=Duration.seconds(60))
