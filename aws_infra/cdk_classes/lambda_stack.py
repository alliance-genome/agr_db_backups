import json
import os
import shutil

from aws_cdk import Duration, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda
from aws_cdk import aws_events
from aws_cdk import aws_events_targets


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

		# Copy helper file into lambda bundle
		dirname = os.path.dirname(os.path.realpath(__file__))
		shutil.copyfile(os.path.join(dirname, '..','..','app','interfaces','helper.py'),
		                os.path.join(dirname, '..', 'lambda_bundle', 'helper.py'))

		# Create lambda function
		aws_lambda_fn = aws_lambda.Function(scope, "agrDbBackupsLambdaTrigger",
			function_name='agr_db_backups',
			description='Lambda function to trigger a backup or restore of a postgres databases to or from S3, through ECS',
			runtime=aws_lambda.Runtime.PYTHON_3_7,
			handler="ecs_trigger.lambda_handler",
			code=aws_lambda.Code.from_asset(os.path.join(dirname, '..', 'lambda_bundle')),
			environment={
				'AGRDB_ECS_CLUSTER': ecs_cluster_arn,
				'AGRDB_ECS_TASK_DEF': ecs_task_def_arn,
				'AGRDB_CONTAINER_NAME': container_name,
				'AGRDB_LOG_URL_TEMPLATE': log_url_template,
				'AGRDB_ECS_TASK_DETAILS_URL_TEMPLATE': task_details_template
			},
			role=excecution_role,
			timeout=Duration.seconds(60))

		os.remove(os.path.join(dirname, '..', 'lambda_bundle', 'helper.py'))

		# Add targets to nightly backup event rule for every DB requiring nightly backup
		backup_list = json.load(open(os.path.join(dirname, '..', 'resources', 'backup_list.json'), 'r'))

		for backup_target in backup_list:
			# Create nightly backup event rule (scheduled backup trigger)
			# for each target, as each event only support max 5 targets
			rule_name = "agrdb-"+backup_target['name']
			backup_event_rule = aws_events.Rule(scope, rule_name,
				rule_name=rule_name,
				enabled=True,
				schedule=aws_events.Schedule.expression(backup_target['schedule'])
			)

			backup_event_rule.add_target(aws_events_targets.LambdaFunction(
				handler=aws_lambda_fn,
				event=aws_events.RuleTargetInput.from_object(backup_target['payload'])
			))
