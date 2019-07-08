FROM node:10-alpine

WORKDIR /usr/src

COPY package.json package-lock.json ./

RUN npm install

COPY . ./
