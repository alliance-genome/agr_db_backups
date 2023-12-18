FROM public.ecr.aws/amazonlinux/amazonlinux:2023

# Install pip and PostgreSql client libraries
RUN dnf install -y  python3-pip postgresql15

# Copy function code
COPY app/ /app/

# Install function's python library dependencies
WORKDIR /app/
RUN  pip install -r requirements.txt

RUN rm -rf /var/cache/dnf/*

ENTRYPOINT [ "python3", "app.py" ]
CMD [ "--help" ]
