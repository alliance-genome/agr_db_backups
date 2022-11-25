from aws_cdk import (
	Stack,
	aws_ecs as ecs,
	aws_ecr as ecr,
	aws_ec2 as ec2,
	aws_iam as iam,
	aws_s3 as s3
)

class EcsCluster:

	cluster = None

	def __init__(self, scope: Stack) -> None:

		# Create the ECS cluster
		vpc = ec2.Vpc.from_lookup(scope, "AgrVpc", vpc_id = "vpc-55522232")
		self.cluster = ecs.Cluster(scope, "AgrDbBackupsCluster", vpc=vpc)

	def get_cluster_arn(self) -> str:
		return self.cluster.cluster_arn

	def get_cluster_name(self) -> str:
		return self.cluster.cluster_name

class EcsTaskDefinition:

	task_def = None

	def __init__(self, scope: Stack) -> None:

		# Find the S3 bucket to read/write backups from/to
		s3_bucket = s3.Bucket.from_bucket_name(scope, "AgrDbBackupsBucket","agr-db-backups")

		# Create ECS task definition
		iam_ecr_read_policy = iam.ManagedPolicy.from_managed_policy_name(scope, "IamEcrReadPolicy", "ReadOnlyAccessECR")

		# Execution role defines the AWS permissions required by AWS ECS
		# to run the ECS task
		execution_role = iam.Role(scope, "agr-db-backups-execution-role",
			assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
			managed_policies=[
				iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchFullAccess"),
				iam_ecr_read_policy
			]
		)

		# Task role defines the AWS permissions required by the container at runtime
		# to run the application
		task_role_policy_doc = iam.PolicyDocument(
			statements= [
				iam.PolicyStatement(
					sid="SSMParametersReadAll",
					effect=iam.Effect.ALLOW,
					actions=[ 'ssm:List*', 'ssm:Describe*', 'ssm:Get*' ],
					resources=[ 'arn:aws:ssm:*:100225593120:parameter/*' ]
				),
				iam.PolicyStatement(
					sid="S3BucketWriteAll",
					effect=iam.Effect.ALLOW,
					actions=[ 's3:Put*' ],
					resources=[ s3_bucket.bucket_arn+'/*' ]
				),
				iam.PolicyStatement(
					sid="S3BucketReadAll",
					effect=iam.Effect.ALLOW,
					actions=[ 's3:ListBucket*', 's3:Get*' ],
					resources=[ s3_bucket.bucket_arn, s3_bucket.bucket_arn+'/*' ]
				)
			]
		)

		task_role = iam.Role(scope, "agr-db-backups-task-role",
			assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
			inline_policies= { 'agrDbBackupsTaskRolePolicy' : task_role_policy_doc }
		)

		# Task definition
		task_definition = ecs.FargateTaskDefinition(scope, "DbBackupsTaskDefinition",
			memory_limit_mib = 2048,
			cpu = 1024, # 1 vCPU
			ephemeral_storage_gib = 21,
			execution_role=execution_role,
			task_role=task_role
		)

		task_definition.add_container("DbBackupsFargateContainer",
			image=ecs.ContainerImage.from_ecr_repository(
				ecr.Repository.from_repository_name(scope, "EcrRepo", "agr_db_backups_ecs"), tag="latest"),
			logging=ecs.AwsLogDriver(stream_prefix=task_definition.family)
		)

		self.task_def = task_definition

	def get_task_def_arn(self) -> str:
		return self.task_def.task_definition_arn

	def get_container_name(self) -> str:
		return self.task_def.default_container.container_name

	def get_aws_log_url_template(self) -> str:
		url = None
		log_driver_config = self.task_def.default_container.log_driver_config

		if self.task_def.default_container.log_driver_config.log_driver == 'awslogs':
			log_config_options = self.task_def.default_container.log_driver_config.options
			url_template = 'https://{region}.console.aws.amazon.com/cloudwatch/home'
			url_template += '?region={region}#logsV2:log-groups/log-group/{log_group_name}'
			url_template += '/log-events/{stream_prefix}$252F{container_name}$252F{{}}'

			url = url_template.format(
				region=log_config_options['awslogs-region'],
				log_group_name=log_config_options['awslogs-group'],
				stream_prefix=log_config_options['awslogs-stream-prefix'],
				container_name=self.get_container_name()
			)

		return url

	def get_ecs_task_detail_url_template(self, cluster_name) -> str:
		url_template = 'https://{region}.console.aws.amazon.com/ecs/home?region={region}#'
		url_template += '/clusters/{cluster_name}'
		url_template += '/tasks/{{}}/details'

		url = url_template.format(
			region=self.task_def.env.region,
			cluster_name=cluster_name
		)

		return url
