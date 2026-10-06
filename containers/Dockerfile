# =============================================================================
# GRETH — AI Hacking Adversary
# File: containers/Dockerfile
# Image: greth-offensive
# =============================================================================

FROM kalilinux/kali-rolling:latest


# --- OCI metadata ------------------------------------------------------------
LABEL org.opencontainers.image.title="GRETH — AI Hacking Adversary" \
      org.opencontainers.image.description="Isolated environment for AI Hacking Adversary" \
      org.opencontainers.image.authors="BLAKRAVAT" \
      org.opencontainers.image.vendor="GRETH Offensive"

# --- Global runtime environment ----------------------------------------------
ENV DEBIAN_FRONTEND=noninteractive \
    TERM=xterm-256color \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# --- Browser-automation identity ---------------------------------------------
ENV DEFAULT_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36" \
    AGENT_BROWSER_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36" \
    AGENT_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium \
    CHROMIUM_FLAGS="--no-sandbox --disable-dev-shm-usage --disable-gpu"


# =============================================================================
# OS TOOLCHAIN
# =============================================================================

# --- Layer 1: filesystem / text / process utilities --------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        coreutils \
        findutils \
        grep \
        sed \
        gawk \
        file \
        procps \
        psmisc \
        lsof; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 2: archive / compression / data utilities -------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        tar \
        gzip \
        bzip2 \
        xz-utils \
        zip \
        unzip \
        jq \
        sqlite3 \
        xxd; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 3: network / DNS / socket utilities -------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        iputils-ping \
        dnsutils \
        iproute2 \
        net-tools \
        curl \
        wget \
        ncat \
        telnet \
        socat; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 4: remote access / directory / authentication utilities ----------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        openssh-client \
        smbclient \
        ldap-utils \
        krb5-user; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 5: crypto / binary analysis / debugging ---------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        openssl \
        binutils \
        strace \
        gdb; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 6: shell -----------------------------------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        zsh \
        tmux; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 7: Python runtime --------------------------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 8: Java runtime ----------------------------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        openjdk-21-jdk \
        maven; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 9: Go toolchain ----------------------------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        golang-go; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 10: Rust toolchain -------------------------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        rustc \
        cargo; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 11: Node.js / npm --------------------------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        nodejs \
        npm; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 12: browser --------------------------------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        chromium \
        ca-certificates; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 13: Git ------------------------------------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        git; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 14: network scanning ------------------------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        nmap; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 15: exploitation framework -----------------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        metasploit-framework; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 17: enumeration / wordlists ----------------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        gobuster \
        seclists; \
    rm -rf /var/lib/apt/lists/*


# --- Layer 18: Exploit Database -----------------------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        exploitdb; \
    rm -rf /var/lib/apt/lists/*


# =============================================================================
# HTTP CLIENT DEFAULT USER-AGENT
# =============================================================================

RUN set -eux; \
    printf 'user-agent = "%s"\n' "$DEFAULT_USER_AGENT" > /etc/curlrc; \
    printf 'user_agent = "%s"\n' "$DEFAULT_USER_AGENT" > /etc/wgetrc


# =============================================================================
# NODE-BASED TOOLING
# =============================================================================

RUN npm install -g agent-browser


# =============================================================================
# JAVA DESERIALIZATION TOOLKIT
# =============================================================================

RUN set -eux; \
    mkdir -p /opt/ysoserial; \
    curl -fsSL \
        "https://github.com/frohoff/ysoserial/releases/latest/download/ysoserial-all.jar" \
        -o /opt/ysoserial/ysoserial-all.jar; \
    printf '%s\n' \
        '#!/bin/sh' \
        'exec java -jar /opt/ysoserial/ysoserial-all.jar "$@"' \
        > /usr/bin/ysoserial; \
    chmod +x /usr/bin/ysoserial


# =============================================================================
# OUT-OF-BAND INTERACTION TOOLKIT
# =============================================================================

RUN go install \
        "github.com/projectdiscovery/interactsh/cmd/interactsh-client@latest" && \
    go install \
        "github.com/projectdiscovery/interactsh/cmd/interactsh-server@latest"


# =============================================================================
# WORKSPACE
# =============================================================================

RUN mkdir -p /workspace

WORKDIR /workspace

ENV GOPATH=/root/go
ENV PATH="/root/go/bin:/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin"

CMD ["/bin/zsh"]