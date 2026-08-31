FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Outils de base + dépendances d'affichage / DBus
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    wget \
    xauth \
    dbus-x11 \
    libcanberra-gtk3-module \
    libgtk-3-0 \
    locales \
    && apt-get clean

# Génération de la locale française (l'hôte est en fr_FR.UTF-8)
RUN sed -i 's/^# *fr_FR.UTF-8 UTF-8/fr_FR.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen fr_FR.UTF-8 C.UTF-8

# Téléchargement des paquets officiels PTXprint (GUI + moteur PDF) et usfmtc
ARG PTX_VERSION=3.0.17-1ubuntu1-202603271032~ubuntu24.04.1
ARG USFMTC_VERSION=0.4.1-1ubuntu3
RUN mkdir -p /tmp/debs && cd /tmp/debs \
    && wget -q "https://software.sil.org/downloads/r/ptxprint/python3-usfmtc_${USFMTC_VERSION}_all.deb" \
    && wget -q "https://software.sil.org/downloads/r/ptxprint/python3-ptxprint_${PTX_VERSION}_all.deb"

# Installation : apt résout automatiquement toutes les dépendances Ubuntu
# (python3-gi, gir1.2-gtk-3.0, gir1.2-popper, texlive-xetex, etc.)
RUN apt-get update && apt-get install -y \
    /tmp/debs/python3-usfmtc_${USFMTC_VERSION}_all.deb \
    /tmp/debs/python3-ptxprint_${PTX_VERSION}_all.deb \
    && apt-get clean \
    && rm -rf /tmp/debs

# Mise à jour d'usfmtc vers la dernière version PyPI (surcharge le paquet DEB)
RUN apt-get update && apt-get install -y python3-pip python3-dev \
    && pip install --break-system-packages --ignore-installed --no-cache-dir "usfmtc==0.4.7" \
    && apt-get clean

# Polices courantes conseillées pour la composition d'Écritures (optionnel)
RUN apt-get update && apt-get install -y \
    fonts-sil-charis \
    fonts-sil-doulos \
    fonts-sil-galatia \
    fonts-sil-gentiumplus \
    fonts-sil-scheherazade \
    && apt-get clean

# Renomme l'utilisateur `ubuntu` par défaut (UID 1000) pour garder un UID
# non-privilégié aligné sur l'hôte, tout en évitant un conflit d'UID.
RUN usermod -l ptxuser -d /home/ptxuser -m ubuntu \
    && groupmod -n ptxuser ubuntu \
    && mkdir -p /work && chown ptxuser:ptxuser /work

RUN mkdir -p /etc/fonts/conf.d && printf '%s\n' \
    '<?xml version="1.0"?>' \
    '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">' \
    '<fontconfig>' \
    '  <selectfont><rejectfont>' \
    '    <glob>/usr/share/fonts/X11/Type1/*</glob>' \
    '    <pattern><patelt name="fontformat"><string>Type 1</string></patelt></pattern>' \
    '  </rejectfont></selectfont>' \
    '</fontconfig>' > /etc/fonts/conf.d/99-no-type1.conf \
    && fc-cache -fv

USER ptxuser
ENV HOME=/home/ptxuser
ENV LANG=fr_FR.UTF-8
ENV LC_ALL=fr_FR.UTF-8
WORKDIR /work

CMD ["ptxprint"]
