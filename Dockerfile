FROM public.ecr.aws/lambda/python:3.8

# Copy function code
COPY app/* ${LAMBDA_TASK_ROOT}/

# Install function's python library dependencies
WORKDIR ${LAMBDA_TASK_ROOT}
RUN  pip3 install -r requirements.txt

# Install function's external binary dependencies
COPY pgdg.repo /etc/yum.repos.d/
RUN yum update -y \
    && yum install -y postgresql13

RUN rm -rf /var/cache/apk/*

CMD [ "app.lambda_handler" ]
