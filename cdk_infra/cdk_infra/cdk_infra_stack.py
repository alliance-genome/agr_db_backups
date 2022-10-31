from aws_cdk import (
    Stack
)

from constructs import Construct

from cdk_infra.ecs_stack import EcsCluster, EcsTaskDefinition

class CdkInfraStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        EcsCluster(self)
        EcsTaskDefinition(self)
