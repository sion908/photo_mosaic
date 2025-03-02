ARG python_image_v="python:3.11-buster"
# ARG python_image_v="lambci/lambda:build-python3.8"
# python3.10のイメージをダウンロード
FROM ${python_image_v}

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    curl \
    build-essential \
    git \
    cmake \
    sqlite3 \
    zip \
    python3-pip

RUN python -m pip install -U pip


RUN echo "/app/python_modules/python/lib/python3.11/site-packages/" > /usr/local/lib/python3.11/site-packages/.pth

# poetryのインストール先の指定
ENV POETRY_HOME=/opt/poetry
# poetryインストール
RUN curl -sSL https://install.python-poetry.org/ | python && \
    # シンボリックによるpathへのpoetryコマンドの追加
    cd /usr/local/bin && \
    ln -s /opt/poetry/bin/poetry && \
    # 仮想環境を作成しない設定(コンテナ前提のため，仮想環境を作らない)
    # poetry config virtualenvs.create false
    poetry config virtualenvs.in-project true && \
    poetry self add poetry-plugin-export && \
    poetry self update

WORKDIR /workspace

ADD . /workspace

# RUN poetry install

# CMD poetry run python app.py
