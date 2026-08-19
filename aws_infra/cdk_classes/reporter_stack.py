import os
import shutil

from aws_cdk import Duration, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda
from aws_cdk import aws_events
from aws_cdk import aws_events_targets

SLACK_TOKEN_SECRET = 'agr/slack/bot-token'
SLACK_CHANNEL = 'a-team-code'
BACKUP_BUCKET = 'agr-db-backups'

# Backups are triggered at 21:00 UTC and the largest (curation) takes ~15 minutes,
# so report at 21:45 UTC to leave margin.
REPORT_SCHEDULE = 'cron(45 21 * * ? *)'


class LambdaBackupReporter:

	def __init__(self, scope: Stack) -> None:

		account = Stack.of(scope).account
		region = Stack.of(scope).region

		# Create lambda function role
		execution_role = iam.Role(scope, "agr-db-backups-reporter-role",
			assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
			managed_policies=[
				iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
			]
		)

		execution_role.add_to_policy(iam.PolicyStatement(
			actions=["s3:ListBucket"],
			resources=["arn:aws:s3:::" + BACKUP_BUCKET]
		))

		execution_role.add_to_policy(iam.PolicyStatement(
			actions=["ssm:GetParameter"],
			resources=["arn:aws:ssm:{}:{}:parameter/*/db/backup/bucket".format(region, account)]
		))

		execution_role.add_to_policy(iam.PolicyStatement(
			actions=["secretsmanager:GetSecretValue"],
			resources=["arn:aws:secretsmanager:{}:{}:secret:{}-*".format(region, account, SLACK_TOKEN_SECRET)]
		))

		# Copy the backup list into the lambda bundle so the reporter checks
		# exactly the set of backups that get scheduled.
		dirname = os.path.dirname(os.path.realpath(__file__))
		shutil.copyfile(os.path.join(dirname, '..', 'resources', 'backup_list.json'),
		                os.path.join(dirname, '..', 'reporter_bundle', 'backup_list.json'))

		# Create lambda function
		aws_lambda_fn = aws_lambda.Function(scope, "agrDbBackupsReporter",
			function_name='agr_db_backups_reporter',
			description='Lambda function to report the status of the nightly AGR database backups to Slack',
			runtime=aws_lambda.Runtime.PYTHON_3_13,
			handler="backup_reporter.lambda_handler",
			code=aws_lambda.Code.from_asset(os.path.join(dirname, '..', 'reporter_bundle')),
			environment={
				'AGRDB_SLACK_CHANNEL': SLACK_CHANNEL,
				'AGRDB_SLACK_TOKEN_SECRET': SLACK_TOKEN_SECRET
			},
			role=execution_role,
			timeout=Duration.seconds(120))

		os.remove(os.path.join(dirname, '..', 'reporter_bundle', 'backup_list.json'))

		# Create the daily reporting event rule
		rule_name = "agrdb-nightly-backup-report"
		report_event_rule = aws_events.Rule(scope, rule_name,
			rule_name=rule_name,
			enabled=True,
			schedule=aws_events.Schedule.expression(REPORT_SCHEDULE)
		)

		report_event_rule.add_target(aws_events_targets.LambdaFunction(handler=aws_lambda_fn))
