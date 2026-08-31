import aws_cdk as core
import aws_cdk.assertions as assertions

from cdk_classes.cdk_infra_stack import CdkInfraStack

TEST_ENV = core.Environment(account="100225593120", region="us-east-1")

# example tests. To run these tests, uncomment this file along with the example
# resource in cdk_classes/cdk_infra_stack.py
def test_sqs_queue_created():
	app = core.App()
	stack = CdkInfraStack(app, "cdk-infra", env=TEST_ENV)
	template = assertions.Template.from_stack(stack)

	# template.has_resource_properties("AWS::SQS::Queue", {
	# 	"VisibilityTimeout": 300
	# })


def test_backup_reporter_has_cost_tags():
	app = core.App()
	stack = CdkInfraStack(app, "cdk-infra", env=TEST_ENV)
	template = assertions.Template.from_stack(stack)

	template.has_resource_properties("AWS::Lambda::Function", {
		"FunctionName": "agr_db_backups_reporter",
		"Tags": assertions.Match.array_with([
			{"Key": "Project", "Value": "db-backups"},
			{"Key": "Team", "Value": "devops"},
		]),
	})
