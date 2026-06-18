FROM node:20-alpine

USER node
WORKDIR /home/node/app

COPY --chown=node:node package.json package-lock.json* ./

RUN npm install

COPY --chown=node:node . .

EXPOSE 5173 

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]