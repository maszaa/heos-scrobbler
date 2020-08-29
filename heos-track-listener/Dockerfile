FROM node:12-alpine

WORKDIR /usr/src

COPY package.json package-lock.json ./

RUN npm install --only=production

COPY . ./
