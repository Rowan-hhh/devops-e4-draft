FROM python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f
WORKDIR /work
COPY main.c helper.c *.h Makefile ./
RUN sed -i -e 's|https\{0,1\}://deb\.debian\.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' -e 's|https\{0,1\}://security\.debian\.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' -e 's|https\{0,1\}://deb\.debian\.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources && apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=3 update && apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=3 install -y --no-install-recommends gcc make libc6-dev && rm -rf /var/lib/apt/lists/*
RUN make app
CMD ["./app"]
