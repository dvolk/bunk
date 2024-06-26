import collections
import json
import logging
import os
import pathlib
import pwd
import shlex
import sys
import threading
import time
import uuid
import random

import argh
import flask
import paramiko
import waitress

### ssh utilities ###


def run_ssh_cmd(host, cmd):
    """
    run a command over ssh; blocking
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    my_username = pwd.getpwuid(os.getuid())[0]
    attempt = 0
    while True:
        attempt += 1
        try:
            client.connect(
                host,
                port=22,
                username=my_username,
                banner_timeout=600,
                auth_timeout=600,
                timeout=600,
            )
            break
        except Exception as e:
            logging.warning(str(e))
            if attempt > 10:
                logging.error(f"Couldn't connect to {host} after {attempt} attempts.")
                raise
            else:
                sleepy_time = int(2 ** attempt * (random.random() + 0.5))
                logging.warning(
                    f"Couldn't connect to {host} -attempt {attempt}- sleeping for {sleepy_time}"
                )
                time.sleep(sleepy_time)

    stdin, stdout, stderr = client.exec_command(cmd)
    stdout_str, stderr_str = stdout.read(), stderr.read()
    retcode = stdout.channel.recv_exit_status()
    stdin.close()
    stdout.close()
    stderr.close()
    client.close()
    logging.debug(cmd)
    logging.debug(stdout_str, stderr_str)
    return retcode, stdout_str, stderr_str


def run_ssh_script(host, script, work_dir, script_filename_prefix=".command"):
    """
    run a script over ssh; blocking
    note that the work directory must be mounted on the catgrid machine and the cluster
    """

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    my_username = pwd.getpwuid(os.getuid())[0]
    client.connect(
        host,
        port=22,
        username=my_username,
        banner_timeout=600,
        auth_timeout=600,
        timeout=600,
    )
    local_script_path = pathlib.Path(f"/tmp/{script_filename_prefix}.script")
    with open(local_script_path, "w") as f:
        f.write(script)
    
    sftp = client.open_sftp()
    remote_script_path = f"{work_dir}/{script_filename_prefix}.script"
    sftp.put(local_script_path, remote_script_path)
    sftp.close()
    client.close()
    local_script_path.unlink()
        
    cmd = f"""cd {shlex.quote(str(work_dir))} && bash ./{shlex.quote(script_filename_prefix)}.script"""
    return run_ssh_cmd(host, cmd)


def get_stats_over_ssh(name):
    """
    get cores and memory over ssh; blocking
    """
    _, cores_str, _ = run_ssh_cmd(name, "cat /proc/cpuinfo | grep vendor_id | wc -l")
    cores = int(cores_str.decode("utf-8"))

    _, mem_str, _ = run_ssh_cmd(
        name, "cat /proc/meminfo | grep MemTotal | awk '{ print $2 }'"
    )
    mem = int(mem_str.decode("utf-8")) // (2 ** 10)

    return mem, cores


### scheduler ###

"""map from job guid to [returncode, stdout, stderr]"""
results = collections.defaultdict(list)

scheduling_lock = threading.Lock()


class JobQueue:
    def __init__(self):
        self.queue = list()
        self.node_affinity_map = dict()

    def add(self, job):
        self.queue.insert(0, job)

    def remove(self, jobid):
        with scheduling_lock:
            old_queue = self.queue
            self.queue = [x for x in self.queue if x.uuid != jobid]
            return old_queue != self.queue

    def run(self, nodes, scheduler_type="standard", strictorder=True):
        if scheduler_type == "standard":
            self.schedule_standard(nodes, strictorder)
        elif scheduler_type == "least_used_node":
            self.schedule_least_used_node(nodes, strictorder)
        elif scheduler_type == "node_tag_affinity":
            self.schedule_node_tag_affinity(nodes, strictorder)

    def schedule_standard(self, nodes, strictorder):
        """
        Go over queue and add jobs to nodes that have enough free cores and memory
        """
        with scheduling_lock:
            for job in self.queue[:]:
                for node in nodes.values():
                    if (
                        node.status == "ready"
                        and job.mem <= node.mem_free()
                        and job.cores <= node.cores_free()
                    ):
                        node.add_job(job)
                        self.queue.remove(job)
                        break
                else:
                    if strictorder:
                        # we want jobs to be allocated strictly in order,
                        # but we couldn't place a job, so stop trying
                        break

    def schedule_least_used_node(self, nodes, strictorder):
        """
        Go over queue and add jobs to nodes that have enough free cores and memory, but first sort nodes by most used cores
        """
        with scheduling_lock:
            for job in self.queue[:]:
                nodes = dict(
                    sorted(nodes.items(), key=lambda x: x[1].cores_free(), reverse=True)
                )
                for node in nodes.values():
                    if (
                        node.status == "ready"
                        and job.mem <= node.mem_free()
                        and job.cores <= node.cores_free()
                    ):
                        node.add_job(job)
                        self.queue.remove(job)
                        break
                else:
                    if strictorder:
                        # we want jobs to be allocated strictly in order,
                        # but we couldn't place a job, so stop trying
                        break

    def schedule_node_tag_affinity(self, nodes, strictorder):
        with scheduling_lock:
            self.queue = sorted(self.queue, key=lambda x: x.tag_name == None)

            for job in self.queue[:]:
                tag_node = self.node_affinity_map.get(job.tag_name)
                nodes = dict(
                    sorted(nodes.items(), key=lambda x: x[1].cores_free(), reverse=True)
                )

                for node in nodes.values():
                    ok_to_place_job = (
                        node.status == "ready"
                        and job.mem <= node.mem_free()
                        and job.cores <= node.cores_free()
                        and (not tag_node or tag_node == node.name)
                    )
                    if ok_to_place_job:
                        node.add_job(job)
                        if job.tag_name:
                            self.node_affinity_map[job.tag_name] = node.name
                            print(self.node_affinity_map)
                        self.queue.remove(job)
                        break
                else:
                    if not self.node_affinity_map.get(tag_node):
                        break


jq = JobQueue()


class Node:
    def __init__(self, name):
        self.status = "initializing"
        self.name = name
        self.jobs = dict()
        self.last_finished = time.time()
        try:
            self.mem, self.cores = get_stats_over_ssh(name)
            self.status = "ready"
        except Exception as e:
            logging.error(f"failed to add node {self.name} - removing node")
            logging.error(f"error: {e}")
            self.status = "failed"
            self.cores, self.mem = 0, 0
        logging.warning(self.display())

    def display(self):
        return {
            self.name: {
                "cores": self.cores,
                "mem": self.mem,
                "free_mem": self.mem_free(),
                "status": self.status,
                "last_finished": int(self.last_finished),
                "jobs": [job.display() for job in self.jobs.values()],
            }
        }

    def mem_used(self):
        return sum([job.mem for job in self.jobs.values()])

    def mem_free(self):
        return self.mem - self.mem_used()

    def cores_used(self):
        return sum([job.cores for job in self.jobs.values()])

    def cores_free(self):
        return self.cores - self.cores_used()

    def add_job(self, job):
        """
        add a job to node and run it immediately; non-blocking
        """
        self.jobs[job.uuid] = job

        def run_job():
            logging.warning(f"node {self.name} started job name {job.name}")
            try:
                job.started_epochtime = int(time.time())
                retcode, stdout, stderr = run_ssh_script(
                    self.name, job.script, job.work_dir, job.filename_uuid
                )
            except Exception as e:
                logging.error(
                    f"job {job.name} failed on node {self.name} - removing node and requeueing"
                )
                logging.error(f"error: {e}")
                jq.add(job)
                del self.jobs[job.uuid]
                self.status = "failed"
                self.last_finished = time.time()
                return

            results[job.uuid] = {
                "retcode": int(retcode),
                "stdout": stdout.decode("utf-8"),
                "stderr": stderr.decode("utf-8"),
                "node": self.name,
            }
            del self.jobs[job.uuid]
            self.last_finished = time.time()
            logging.warning(f"node {self.name} finished job name {job.name}")

        threading.Thread(target=run_job).start()


last_job_id = 0


class Job:
    def __init__(self, name, script, mem, cores, work_dir):
        self.name = name
        self.script = script
        self.mem = mem
        self.cores = cores
        self.work_dir = work_dir
        global last_job_id
        self.uuid = last_job_id + 1
        last_job_id = self.uuid
        self.filename_uuid = str(uuid.uuid4())
        self.started_epochtime = None
        try:
            self.process_name, self.tag_name = self.name.split("(")
            self.process_name = self.process_name[:-1]
            self.tag_name = self.tag_name[:-1]
        except:
            self.process_name, self.tag_name = None, None

    def display(self):
        return {
            self.uuid: {
                "name": self.name,
                "process": self.process_name,
                "tag": self.tag_name,
                "mem": self.mem,
                "cores": self.cores,
                "started": self.started_epochtime,
            }
        }


nodes = collections.defaultdict(str)

### web api endpoints ###

app = flask.Flask(__name__)


@app.route("/terminate/<job_name_to_kill>")
def terminate(job_name_to_kill):
    def terminate_(node_host, job):
        cmd = f'kill $(ps -s $(ps axwf | grep "bash ./{job.filename_uuid}.script" | grep -v "grep" | head -1 | awk \'{{ print $1 }}\') -o pid=)'
        run_ssh_cmd(node_host, cmd)

    if jq.remove(int(job_name_to_kill)):
        return "removed from queue"

    for node_host, node in nodes.items():
        for job_name, job in node.jobs.items():
            if str(job_name) == job_name_to_kill:
                threading.Thread(
                    target=terminate_,
                    args=(
                        node_host,
                        job,
                    ),
                ).start()
                return "terminating"

    return "job not found"


@app.route("/output/<job_name>")
def output(job_name):
    return json.dumps({"result": results[int(job_name)]})


@app.route("/submit", methods=["POST"])
def submit():
    data = flask.request.get_json(force=True)
    job = Job(
        data["name"],
        data["script"],
        int(data["mem"]),
        int(data["cores"]),
        data["work_dir"],
    )
    jq.add(job)
    return json.dumps(job.uuid)


@app.route("/status")
def status():
    ret = dict()
    with scheduling_lock:
        for node in nodes.values():
            ret.update(node.display())
    return json.dumps({"nodes": ret, "queue": [j.display() for j in jq.queue]})


@app.route("/add_node/<name>")
def add_node(name):
    if name in nodes:
        return f"node {name} already exists"
    else:

        def add_node_():
            node = Node(name)
            if node.status != "failed":
                nodes[name] = node

        threading.Thread(target=add_node_).start()
        return f"adding node {name}"


@app.route("/remove_node/<name>")
def remove_node(name):
    if name not in nodes:
        return f"node {name} doesn't exist"
    elif nodes[name].status == "draining":
        return f"node {name} already being drained"
    else:
        nodes[name].status = "draining"

        with scheduling_lock:
            if len(nodes[name].jobs) == 0:
                del nodes[name]
                return f"removed {name}"

        def wait_then_remove():
            while True:
                with scheduling_lock:
                    if len(nodes[name].jobs) == 0:
                        del nodes[name]
                        break
                time.sleep(5)

        threading.Thread(target=wait_then_remove).start()
        return f"draining {name}"


### main ###


def main(node_names=None, scheduler_type="standard", strictorder=True):
    if node_names:
        node_names = node_names.split(",")
        for name in node_names:
            logging.warning(add_node(name))

    def scheduler():
        while True:
            for node in nodes.values():
                if node.status == "failed":
                    logging.warning(remove_node(node))

            jq.run(nodes, scheduler_type, strictorder)
            time.sleep(1)

    threading.Thread(target=scheduler).start()

    waitress.serve(app, listen="0.0.0.0:6000")


if __name__ == "__main__":
    argh.dispatch_command(main)
