from typing import Container
from aws_cdk import (
    # Duration,
    # Construct,
    Stack,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_ec2 as ec2,
    aws_iam as iam
)
from constructs import Construct

class CdkInfraStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)


        # Create the ECS cluster
        vpc = ec2.Vpc.from_lookup(self, "AgrVpc", vpc_id = "vpc-55522232")
        ecs.Cluster(self, "AgrDbBackupsCluster", vpc=vpc)

        # Create ECS task definition
        iam_ecr_read_policy = iam.ManagedPolicy.from_managed_policy_name(self, "IamEcrReadPolicy", "ReadOnlyAccessECR")
        
        # Execution role defines the AWS permissions required by AWS ECS
        # to run the ECS task
        execution_role = iam.Role(self, "agr-db-backups-execution-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchFullAccess"),
                iam_ecr_read_policy
            ]
        )

        # Task role defines the AWS permissions required by the container at runtime
        # to run the application
        #TODO: reduce task role permissions to match POLP (implement policy document used in current template.yaml)
        task_role = iam.Role(self, "agr-db-backups-task-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
                iam_ecr_read_policy
            ]
        )

        # Task definition
        task_definition = ecs.FargateTaskDefinition(self, "DbBackupsTaskDefinition",
            memory_limit_mib = 2048,
            cpu = 1024, # 1 vCPU
            ephemeral_storage_gib = 21,
            execution_role=execution_role,
            task_role=task_role
        )

        task_definition.add_container("DbBackupsFargateContainer",
            image=ecs.ContainerImage.from_ecr_repository(
                ecr.Repository.from_repository_name(self, "EcrRepo", "agr_db_backups_ecs"), tag="latest"),
            logging=ecs.AwsLogDriver(stream_prefix=task_definition.family)
        )
