# AGR DB Backups

This repo holds the code used to run automated (daily) postgres DB dumps through AWS Lambda.

## Getting Started

These instructions will help you setup a local development environment to develop and test this code locally.

## Contents

-  [Developing](#developing)

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
#  "identifier" and "env" are required data fields, all others will be retrieved from SSM
#  when left undefined, or use the defined value otherwise (SSM does not hold value for local dev env testing though).
> curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{"identifier": "curation", "env": "mluypaert-dev", "db_name": "curation", "db_user": "postgres", "db_password": "...", "db_host": "postgres", "s3_bucket": "agr-db-backups"}'
```

## Testing and deployment
The application is built and deployed to AWS using AWS SAM, an open-source framework that enables
writing the entire serverless application as code, including all event sources and other AWS resources
which are require in addition to the function code. This allows for an easy and reproducible deployment
, that can be fully documented and versioned as code.

For instructions on how to install AWS SAM, see the [AWS docs](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html).

SAM configuration is store in two files:
 * [template.yaml](template.yaml)
    This file contains the AWS SAM template describing all aspects of the serverless application.
 * [samconfig.toml](samconfig.toml)
    This file contains named sets of CLI argument (and template parameter) values,
    which can be used to easily apply those values when building/deploying/... for specific environments.

### Validation
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
> echo '{"identifier": "curation", "env": "mluypaert-dev", "db_name": "curation", "db_user": "postgres", "db_password": "...", "db_host": "postgres", "s3_bucket": "agr-db-backups"}' | sam local invoke "agrDbBackups" --event - --profile agr --docker-network curation
```

### Deployment
After building (and optional testing), you can deploy the built
serverless application to AWS by running the following command:
```bash
# Below example command breakdown:
# * "--config-env curationAlpha":
#     This sets arguments as stored in the samconfig.toml file to deploy a specific environment.
#     Use "curationAlpha" to deploy the application to create regular backups from the curation alpha database,
#     "curationBeta" for the curation beta database or "curationProd" for the curation production database.
# * "--resolve-image-repos --resolve-s3"
#     This creates AWS-managed ECR repositories and S3 buckets to store the serverless application's
#     configurations, code and docker images.
# * "--capabilities CAPABILITY_IAM"
#     As the template.yaml defines IAM permissions the serverless application needs to function correctly,
#     this argument serves to acknowledge that and allow AWS to automatically create the necessary IAM policies
#     and roles required for this serverless application.
> sam deploy --config-env curationAlpha --resolve-image-repos --resolve-s3 --capabilities CAPABILITY_IAM
```