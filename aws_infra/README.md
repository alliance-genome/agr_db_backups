
# AGR DB backups infra using CDK (Python)

This is the AWS infrastructure component of the agr-db-backups application.
This includes all AWS resources and infrastructure required to make the main
application callable and executable in AWS, and is defined and deployed using AWS CDK
and written as Python code in this subdirectory.

AWS CDK is an open-source framework that enables writing
the entire cloud application as code, including all event sources and other AWS resources
which are require to make the application executable in AWS in addition to the application code.
This allows for an easy and reproducible deployment, that can be fully documented and versioned as code.

For instructions on how to install the AWS CDK CLI,
see the [AWS docs](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html#getting_started_install).


This project is set up as a Python project, using a virtualenv
stored in the `.venv` directory in this directory.

To activate the virtualenv:
```bash
$ source .venv/bin/activate
```

Once the virtualenv is activated, you can install the required dependencies through:
```bash
$ pip install -r requirements.txt
```

After that, you can execute all required CDK commands as described in below chapters.

## Important files
Two standard CDK configuration files can be found at the root level of this directory:
 * [cdk.json](./cdk.json)
    Contains the main CDK execution configuration parameters
 * [cdk.context.json](./cdk.context.json)
    Contains the VPC context in which to deploy the CDK Stack.

Then the AWS Stack to be deployed using CDK is define in the following files and directories:
 * [cdk_app.py](./cdk_app.py)
    The root level CDK application, defining the entire AWS Stack to be deployed.
 * [cdk_classes/](./cdk_classes/)
    Python sub-classes defining the CDK stack (representing a single CloudFormation stack)
    and all individual CDK constructs, representing individual cloud components.

## Validating
When making changes to any of the CDK files, validate them before requesting a PR
or attempting a deployment, by running the following command:
```bash
> cdk diff
```
This will attempt to synthesize the (Cloudformation) stack and produce errors when (syntax) errors
would be present in any of the CDK code.  
When no (more) errors are present, `cdk diff` will compare the stack to the deployed stack,
and display the changes that would get deployed. Inspect these changes to ensure
the code changes made will have the expected effect on the deployed AWS resources.

This allows the developer to fix any errors before deployment, reducing the amount of
troubleshooting that would otherwise be required on failing or incorrect deployments.

## Deployment
After making all necessary changes to the CDK code and [validating](#validating)
the resulting stack changes are as expected, you can deploy
the new stack to AWS by running the following command:
```bash
# This command will interactively ask for confirmation before deploying security-sensitive changes.
# To disable this approval (e.g. for use in CI/CD pipelines), add "--require-approval never"
> cdk deploy
```
Any code pushed to the main branch of this repository (both main application and CDK code)
automatically gets built and deployed, through [github actions](./.github/workflows/main-build-and-deploy.yml).

## Other useful CDK commands
Here's a list of the most useful CDK commands. For a full list, call `cdk help`.
 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to AWS
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation
