FROM debian:12

# Install curl and kubectl
RUN apt-get update && \
    apt-get install -y curl && \
    curl -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x ./kubectl && \
    mv ./kubectl /usr/local/bin/kubectl

# Install SSH server and other packages
RUN apt-get update && apt-get install -y openssh-server git emacs-nox lsof build-essential python3-venv python3-tabulate python3-requests nfs-server && \
    mkdir /var/run/sshd && \
    mkdir /work

# Configure nfs share
RUN echo "/work *(rw,sync,fsid=0,no_subtree_check)" > /etc/exports

COPY . /root/bunk

# Set root ssh key for the scheduler
RUN ssh-keygen -t rsa -b 4096 -f /root/.ssh/id_rsa -N "" -q && \
    cp /root/.ssh/id_rsa.pub /root/.ssh/authorized_keys

# SSH login fix. Otherwise, user is kicked off after login
RUN sed -i 's@session    required   pam_loginuid.so@session optional pam_loginuid.so@g' /etc/pam.d/sshd

RUN cd /root && \
    python3 -m venv env && \
    ./env/bin/pip install argh flask paramiko waitress kubernetes && \
    cp /root/bunk/scheduler/tools/slurm_emu/* /usr/local/bin && \
    cp /root/bunk/scheduler/tools/c* /usr/local/bin

# Expose SSH port
EXPOSE 22

# Start the SSH service
CMD ["/usr/sbin/sshd", "-D"]
