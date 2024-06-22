FROM debian:12

# Install curl and kubectl
RUN apt-get update && \
    apt-get install -y curl && \
    curl -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x ./kubectl && \
    mv ./kubectl /usr/local/bin/kubectl

# Install SSH server
RUN apt-get update && apt-get install -y openssh-server git emacs-nox build-essential python3-venv python3-requests && \
    mkdir /var/run/sshd

COPY . /root/bunk
COPY .ssh /root/.ssh

# Set root password
RUN echo 'root:password' | chpasswd

# SSH login fix. Otherwise, user is kicked off after login
RUN sed -i 's@session    required   pam_loginuid.so@session optional pam_loginuid.so@g' /etc/pam.d/sshd

RUN cd /root && \
    python3 -m venv env && \
    ./env/bin/pip install argh flask paramiko waitress kubernetes && \
    cp /root/bunk/scheduler/tools/slurm_emu/* /usr/local/bin

# Expose SSH port
EXPOSE 22

# Start the SSH service
CMD ["/usr/sbin/sshd", "-D"]
