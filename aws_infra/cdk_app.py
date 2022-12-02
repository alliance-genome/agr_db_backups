#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk_classes.cdk_infra_stack import CdkInfraStack


app = cdk.App()
CdkInfraStack(app, "DbBackupsCdkStack",
	env=cdk.Environment(account='100225593120', region='us-east-1'))

app.synth()
