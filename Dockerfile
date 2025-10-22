# AWS Lambda-optimized Docker image for Business Scraper
FROM public.ecr.aws/lambda/python:3.12

# Install system dependencies for Playwright Chromium
RUN dnf update -y && \
    dnf install -y \
    atk \
    cups-libs \
    gtk3 \
    libXcomposite \
    libXcursor \
    libXdamage \
    libXext \
    libXi \
    libXrandr \
    libXScrnSaver \
    libXtst \
    pango \
    at-spi2-atk \
    nss \
    libdrm \
    libxkbcommon \
    libxshmfence \
    alsa-lib \
    && dnf clean all

# Set environment variables for Lambda
ENV PLAYWRIGHT_BROWSERS_PATH=/var/task/.playwright
ENV PLAYWRIGHT_HEADLESS=true
ENV LAMBDA_ENVIRONMENT=true
ENV PYTHONPATH=/var/task:/var/lang/lib/python3.12/site-packages

# Copy requirements and install Python dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and browsers
RUN playwright install chromium

# Copy application code
COPY . ${LAMBDA_TASK_ROOT}/

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Make sure the lambda handler is executable
RUN chmod +x lambda_handler.py

# Set the Lambda handler
CMD ["app.handler"]