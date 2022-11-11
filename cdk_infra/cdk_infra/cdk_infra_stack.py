from aws_cdk import (
    Stack
)

from constructs import Construct

from cdk_infra.ecs_stack import EcsCluster, EcsTaskDefinition
from cdk_infra.lambda_stack import LambdaEcsTrigger

class CdkInfraStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ecs_cluster = EcsCluster(self)
        ecs_task_def = EcsTaskDefinition(self)
        LambdaEcsTrigger(self, ecs_cluster.get_cluster_arn(), ecs_task_def.get_task_def_arn(),
            ecs_task_def.get_container_name(), ecs_task_def.get_aws_log_url_template(),
            ecs_task_def.get_ecs_task_detail_url_template(ecs_cluster.get_cluster_name()))
