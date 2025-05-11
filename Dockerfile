# Use an Ubuntu-based image
FROM ubuntu:20.04

# Set environment variables to non-interactive (to avoid prompts during apt-get)
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies and clean up to reduce image size
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    gnupg \
    libnss3 \
    libxss1 \
    libappindicator1 \
    libindicator7 \
    fonts-liberation \
    xdg-utils \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libasound2 \
    libxshmfence-dev \
    libgbm-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the ChromeDriver version
ENV CHROME_DRIVER_VERSION=125.0.6422.141

# Install ChromeDriver
RUN wget -O chromedriver.zip https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_DRIVER_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip chromedriver.zip && \
    mv chromedriver-linux64/chromedriver /usr/bin/chromedriver && \
    chmod +x /usr/bin/chromedriver && \
    rm -rf chromedriver.zip chromedriver-linux64

# Install Google Chrome
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i google-chrome-stable_current_amd64.deb || apt-get --fix-broken install -y && \
    rm google-chrome-stable_current_amd64.deb

# Set up Chrome environment variables
ENV CHROME_BIN=/usr/bin/google-chrome-stable
ENV CHROME_DRIVER=/usr/bin/chromedriver

# Clean up unnecessary packages to reduce Docker image size
RUN apt-get autoremove -y && apt-get clean

# Set the default command (in case you want to run Chrome or ChromeDriver directly)
CMD ["google-chrome-stable", "--no-sandbox"]
