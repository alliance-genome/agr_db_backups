
# AGR DB backups infra using CDK (Python)

This is the infrastructure component of the agr-db-backups application.
This infrastructure is defined and deployed using the AWS CDK through Python.

The `cdk.json` file tells the CDK Toolkit how to execute the app.

This project is set up as a standard Python project, using a virtualenv
stored in the `.venv` directory in this directory.

To activate the virtualenv:
```bash
$ source .venv/bin/activate
```

Once the virtualenv is activated, you can install the required dependencies through:
```bash
$ pip install -r requirements.txt
```

Then, to synthesize the CloudFormation template for this application:
```bash
$ cdk synth
```

## Useful CDK commands
 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to AWS
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation
