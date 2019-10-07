FROM python:3.7 as build_image

WORKDIR /wt_dashboard_with_master_db
COPY . /wt_dashboard_with_master_db/

RUN pip install --upgrade pip && \
    pip install pipenv && \
    pipenv install --system && \
    pip list

EXPOSE 8050

CMD cd wt_dashboard_with_master_db

ENTRYPOINT python dashboard.py