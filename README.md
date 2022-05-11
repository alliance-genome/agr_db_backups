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
#       (this code) is run in the same network as the database container (here "curation").
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
#Trigger the lambda function in the locally running container (use a different terminal session)
# "identifier" and "env" are required data fields, all others will be retrieved from SSM
# when left undefined, or use the defined value otherwise (SSM does not hold value for local dev env testing though).
> curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{"identifier": "curation", "env": "mluypaert-dev", "db_name": "curation", "db_user": "postgres", "db_password": "...", "db_host": "postgres", "s3_bucket": "agr-db-backups"}'
```