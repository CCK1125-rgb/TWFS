FROM node:20-bookworm-slim

ENV HOST=0.0.0.0
ENV PORT=10000
ENV PYTHON=/opt/venv/bin/python
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY package.json .npmrc ./
RUN npm install --omit=dev

COPY requirements.txt ./
RUN python3 -m venv /opt/venv \
  && /opt/venv/bin/python -m pip install --upgrade pip \
  && /opt/venv/bin/python -m pip install -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["node", "server.mjs"]
