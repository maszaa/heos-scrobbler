FROM python:3.8-alpine

RUN pip install --upgrade pip

WORKDIR /usr/src

COPY requirements.txt ./

RUN pip install -r requirements.txt

COPY . ./
