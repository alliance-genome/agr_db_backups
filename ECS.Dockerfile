FROM public.ecr.aws/amazonlinux/amazonlinux:2

# Install python
RUN yum install -y python3 python3-pip

# Copy function code
COPY app/ /app/

# Install function's python library dependencies
WORKDIR /app/
RUN  pip3 install -r requirements.txt

# Install function's external binary dependencies
COPY pgdg.repo /etc/yum.repos.d/
RUN yum update -y \
    && yum install -y postgresql13

RUN rm -rf /var/cache/apk/*

ENTRYPOINT [ "python3", "app.py" ]
CMD [ "--help" ]
