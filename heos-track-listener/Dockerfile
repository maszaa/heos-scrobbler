FROM node:16-alpine

WORKDIR /usr/src

COPY package.json package-lock.json ./

RUN npm install --omit=dev

COPY . ./
