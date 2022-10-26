# AGR DB Backups

This repo holds the code used to run automated (daily) postgres DB dumps through AWS Lambda,
and to restore them, enabling data rollback to different environments.

## Getting Started

These instructions will help you setup a local development environment to develop and test this code locally.

## Contents

-  [Developing](#developing)
-  [Testing and Deployment](#testing-and-deployment)
   *  [Validating](#validating)
   *  [Building](#building)
   *  [Testing](#testing)
   *  [Deployment](#deployment)
-  [Invocation](#invocation)
   *  [Scheduled invocation](#scheduled-invocation)
   *  [Manual invocation](#manual-invocation)


## Developing
This application is developed as a docker container intended to run on AWS Lambda.

To run the container and the backup code it contains locally, execute the following commands
```bash
#Build the container (essential when dependencies changed, optional when only app.py changes were made.)
> docker build -t agr_db_backups_lambda .
#Start the container (which will receive requests to execute the function)
# Below example command breakdown:
#  * "--net curation":
#      To enable creating a backup of your local dockerized database, ensure the backup container
#      (this code) is run in the same network as the database container (here "curation").
#  * "-v /.../app/app.py:/var/task/app.py":
#      To enable quick testing of local changes, without requiring rebuilding the container
#      for every change made, you can mount-in the app.py file. That way you only need to restart
#      the container (rerun the docker run command) after making any changes to the file to be able
#      to test them (locally).
# * "-v ~/.aws:/root/.aws -e AWS_PROFILE":
#      As the backup code will (optionally) try to retrieve configuration settings from AWS SSM,
#      and (always) upload the result directly to S3, the container needs to be aware of valid AWS credentials
#      to authorize access. This can either be done by defining, exporting and passing on the AWS access key,
#      secret key and default region directly through the applicable environment variables (see https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html),
#      or by passing your local AWS configuration files into the backup container, optionally accompanied by the
#      AWS_PROFILE variable to indicate the named profile to use, if your agr profile does not have the "default" name.
> docker run --net curation -p 9000:8080 -v /home/mlp/gitrepos/agr-db_backups/app/app.py:/var/task/app.py -v ~/.aws:/root/.aws -e AWS_PROFILE agr_db_backups_lambda
# Trigger the lambda function in the locally running container (use a different terminal session)
#  "identifier" and "target_env" are required data fields, all others will be retrieved from SSM when left undefined,
#  or use the defined value otherwise (note that SSM does not hold values for local dev env operations/testing).

#To backup your local postgres DB (will create a dumpfile of your local DB in S3):
> curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{"action": "backup", "identifier": "curation", "target_env": "mluypaert-dev", "db_name": "curation", "db_user": "postgres", "db_password": "...", "db_host": "postgres", "s3_bucket": "agr-db-backups"}'
#To restore the latest available alpha dump to your local postgres DB:
> curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{"action": "restore", "identifier": "curation", "src_env": "alpha", "target_env": "mluypaert-dev", "db_name": "curation", "db_user": "postgres", "db_password": "...", "db_host": "postgres"}'
```


## Testing and deployment
The application is built and deployed to AWS using AWS SAM, an open-source framework that enables
writing the entire serverless application as code, including all event sources and other AWS resources
which are require in addition to the function code. This allows for an easy and reproducible deployment
, that can be fully documented and versioned as code.

For instructions on how to install AWS SAM, see the [AWS docs](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html).

SAM configuration is generally stored in two files:
 * [template.yaml](template.yaml)
    This file contains the AWS SAM template describing all aspects of the serverless application.
 * [samconfig.toml](samconfig.toml)
    This file contains sets of CLI argument (and template parameter) values,
    which can be used as defaults when building/deploying etc using AWS SAM,
    or to easily apply sets of values to specific environments using named sets.

### Validating
When making changes to the [SAM template file](template.yaml), validate them before requesting a PR
or attempting a deployment, by running the following command:
```bash
> sam validate
```
This will report any errors found in the template file, allowing you to fix those errors before deployment,
hence reducing the amount of troubleshooting that would otherwise be required on failing deployments.

### Building
To build the complete serverless application (locally), run the following command:
```bash
> sam build
```

### Testing
After building, you can test the application locally using the sam cli:
```bash
# Below example command breakdown:
# * "-e -":
#     echo the input data as a json string, capture it through stdin and pass it on to the function
# * "--profile agr"
#     Use this argument to indicate the AWS CLI profile name to be use, if it is not named "default" (otherwise ommit this argument).
# * ""
#     To enable creating a backup of your local dockerized database, ensure the lambda container
#      (this code) is run in the same network as the database container (here "curation").
> echo '{"action": "backup", "identifier": "curation", "target_env": "mluypaert-dev", "db_name": "curation", "db_user": "postgres", "db_password": "...", "db_host": "postgres", "s3_bucket": "agr-db-backups"}' | sam local invoke "agrDbBackups" --event - --profile agr --docker-network curation
```

### Deployment
After building (and optional testing), you can deploy the built
serverless application to AWS by running the following command:
```bash
# Below example command breakdown:
# * "--resolve-image-repos --resolve-s3"
#     This creates AWS-managed ECR repositories and S3 buckets to store the serverless application's
#     configurations, code and docker images.
# * "--capabilities CAPABILITY_IAM"
#     As the template.yaml defines IAM permissions the serverless application needs to function correctly,
#     this argument serves to acknowledge that and allow AWS to automatically create the necessary IAM policies
#     and roles required for this serverless application.
> sam deploy --resolve-image-repos --resolve-s3 --capabilities CAPABILITY_IAM
```
Code pushed to the main branch of this repository automatically gets built and deployed, through [github actions](./.github/workflows/main-build-and-deploy.yml).


## Invocation
### Scheduled invocation
To enable automatic scheduled backups of several application DBs and environments,
we use Amazon EventBridge to trigger the deployed AWS lambda function of this repository.
These events are defined as code in the [template.yaml](template.yaml) file in the `Resources` > `agrDbBackups` > `Properties` > `Events` section,
and each define a cron schedule to run on, and the payload to send upon triggering.
Each of those events thus backs ups up one environment of one application.

To add the backup of a new DB or environment to the event list:
1. Ensure the necessary parameters for the DB to be backed up are stored in the [AWS Systems Manager Parameter Store](https://us-east-1.console.aws.amazon.com/systems-manager/parameters/). This repository code retrieves the required (unprovided) credentials from the parameter store.
2. Add a new record to the `Resources` > `agrDbBackups` > `Properties` > `Events` list in the [template.yaml](template.yaml) file.
   You can copy any existing record and edit the keyname, `Name`, `Description`, `Schedule` and `Input` data accordingly.
3. Commit the above made changes to the [template.yaml](template.yaml) file and create a PR to merge.
   After PR merge, the new event will get deployed automatically and the new backups will run on their schedule.

### Manual invocation
As the application code is deployed as an AWS lambda function, it can be manually invoked through the aws cli.
This can be useful to invoke a one-off backup of a specific database/environment before attempting to make manual changes to it,
or to restore a dump of one environment, to any other environment (and resetting the data in place in the process).

To print (readably-formatted) help on all available arguments for the payload:
```bash
aws lambda invoke --function-name agr_db_backups --cli-binary-format raw-in-base64-out  --payload '{"help": "true"}' lambda.output \
 && jq . lambda.output
```

To invoke an one-off backup of the curation alpha DB, and synchronously wait for its completion:
```bash
# Change the payload to match the desired application (identifier) and target environment if not curation-alpha.
aws --cli-read-timeout 960 lambda invoke --function-name agr_db_backups --cli-binary-format raw-in-base64-out \
 --payload '{"action": "backup", "target_env": "alpha", "identifier": "curation", "region": "us-east-1", "s3_bucket": "agr-db-backups"}' \
 lambda.output
```

To restore the latest production DB backup to the beta environment, and synchronously wait for its completion
```bash
# Change the payload to match the desired application (identifier), source environment and target environment if not curation prod => beta.
aws --cli-read-timeout 960 lambda invoke --function-name agr_db_backups --cli-binary-format raw-in-base64-out \
 --payload '{"action": "restore", "target_env": "beta", "src_env": "production", "identifier": "curation", "region": "us-east-1", "s3_bucket": "agr-db-backups"}' \
 lambda.output
```

Such manual invocations will produce output like the following on STDOUT on success
```bash
{
    "StatusCode": 200,
    "ExecutedVersion": "$LATEST"
}
```
, or report a non-200 `StatusCode` or `"FunctionError": "Unhandled"` in its reported status on failure.
The output of the function, which can contain more details on failure, can be found in the `lambda.output` file.

As another option, the ECS docker image can be invoked directly, and the application execution configured through CLI options.
```bash
docker build -f ECS.Dockerfile -t agr_db_backups_ecs .
docker run --rm -it -v ~/.aws:/root/.aws -e AWS_PROFILE=agr agr_db_backups_ecs --help
```
