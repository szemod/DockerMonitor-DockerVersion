import warnings
try:
    from cryptography.utils import CryptographyDeprecationWarning
except ImportError:
    CryptographyDeprecationWarning = DeprecationWarning

warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)

import os
import time
import paramiko
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from config import PORT

app = Flask(__name__)
app.secret_key = 'supersecretkey'

def is_configured():
    """
    Checks if any of the SSH details are provided in config.py.
    """
    try:
        with open('config.py', 'r') as f:
            config_content = f.read()
        config = {}
        exec(config_content, config)
        ssh_host = config.get('SSH_HOST', '')
        ssh_user = config.get('SSH_USER', '')
        ssh_password = config.get('SSH_PASSWORD', '')
        return bool(ssh_host and ssh_user and ssh_password)
    except Exception as e:
        print(f"Error reading configuration: {e}")
        return False

def get_ssh_credentials():
    """
    Reads the contents of the config.py file and returns the SSH settings.
    """
    try:
        with open('config.py', 'r') as f:
            config_content = f.read()
        config = {}
        exec(config_content, config)
        return config.get('SSH_PASSWORD'), config.get('SSH_HOST'), config.get('SSH_USER')
    except Exception as e:
        print(f"Error reading config: {e}")
        return None, None, None

def get_ssh_connection():
    SSH_PASSWORD, SSH_HOST, SSH_USER = get_ssh_credentials()
    if not all([SSH_PASSWORD, SSH_HOST, SSH_USER]):
        raise Exception("SSH credentials not configured properly.")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(SSH_HOST, username=SSH_USER, password=SSH_PASSWORD)
    except (paramiko.ssh_exception.NoValidConnectionsError,
            paramiko.ssh_exception.AuthenticationException) as e:
        print(f"SSH connection error: {e}")
        raise
    return ssh

def convert_to_mb(value_str):
    value_str = value_str.strip()
    if value_str == 'N/A':
        return 0.0
    unit = ''
    num_part = ''
    for c in value_str:
        if c.isdigit() or c == '.':
            num_part += c
        else:
            unit = c.upper()
            break
    if not num_part:
        return 0.0
    try:
        num = float(num_part)
    except ValueError:
        return 0.0
    first_char = unit[0] if unit else ''
    if first_char == 'K':
        return num / 1024
    elif first_char == 'M':
        return num
    elif first_char == 'G':
        return num * 1024
    elif first_char == 'T':
        return num * 1024 * 1024
    else:
        return num

def parse_container_status(status_str):
    status_str = status_str.strip()
    if "Paused" in status_str:
        return "paused"
    elif status_str.startswith("Up"):
        return "running"
    elif status_str.startswith("Exited"):
        return "stopped"
    else:
        return status_str

def parse_docker_stats(output):
    containers = []
    for line in output.strip().split('\n'):
        parts = line.split('|')
        if len(parts) != 7:
            continue
        cid, name, cpu, mem, net, io, pids = parts
        try:
            cpu_percent = float(cpu.replace('%', ''))
        except ValueError:
            cpu_percent = 0.0
        mem_parts = mem.split('/')
        if len(mem_parts) == 2:
            mem_used, mem_total = mem_parts
            mem_used = mem_used.strip()
            mem_total = mem_total.strip()
            used_mb = convert_to_mb(mem_used)
            total_mb = convert_to_mb(mem_total)
            mem_percent = (used_mb / total_mb * 100) if total_mb > 0 else 0
            mem_used_formatted = f"{used_mb:.1f} MB"
        else:
            used_mb = convert_to_mb(mem.strip())
            mem_percent = 0
            mem_used_formatted = f"{used_mb:.1f} MB"
        containers.append({
            'name': name,
            'cid': cid[:12],
            'cpu': cpu_percent,
            'cpu_display': f"{cpu_percent:.1f} %",
            'mem': mem_used_formatted,
            'mem_used_val': used_mb,
            'mem_percent': mem_percent,
            'net': net,
            'io': io,
            'status': 'unknown'
        })
    return containers

def fetch_docker_data():
    command_stats = """
    docker stats --all --no-stream --format "{{.Container}}|{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.NetIO}}|{{.BlockIO}}|{{.PIDs}}"
    """

    try:
        ssh = get_ssh_connection()

        # Ping the host before executing docker command
        stdin, stdout, stderr = ssh.exec_command("ping -c 1 " + ssh.get_transport().getpeername()[0])
        if stdout.read().decode().strip() == "":
            raise Exception("Ping to SSH host failed, check the connection.")

        stdin, stdout, stderr = ssh.exec_command(command_stats)
        output_stats = stdout.read().decode()
        ssh.close()

    except Exception as e:
        print(f"Error fetching stats: {str(e)}")
        output_stats = ""

    containers = parse_docker_stats(output_stats)

    command_status = """ docker ps -a --format "{{.ID}}|{{.Status}}" """
    try:
        ssh = get_ssh_connection()  # Creating a new SSH connection for status command
        stdin, stdout, stderr = ssh.exec_command(command_status)
        output_status = stdout.read().decode()
        ssh.close()
    except Exception as e:
        print(f"Error fetching status: {str(e)}")
        output_status = ""

    statuses = {}
    for line in output_status.strip().split('\n'):
        if not line:
            continue
        parts = line.split('|')
        if len(parts) == 2:
            container_id, stat = parts
            statuses[container_id[:12]] = parse_container_status(stat)

    for container in containers:
        container['status'] = statuses.get(container['cid'], 'unknown')

    max_used = max((c['mem_used_val'] for c in containers), default=0)
    for c in containers:
        if max_used > 0:
            c['mem_bar_percent'] = (c['mem_used_val'] / max_used) * 100
        else:
            c['mem_bar_percent'] = 0

    return containers

@app.before_request
def require_login():
    if request.endpoint not in ['setup', 'static'] and not is_configured():
        return redirect(url_for('setup'))
    if request.endpoint not in ['login', 'setup', 'static']:
        if not session.get('logged_in'):
            return redirect(url_for('login'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    message = None
    error = None
    if request.method == 'POST':
        ssh_host = request.form.get('ssh_host')
        ssh_user = request.form.get('ssh_user')
        ssh_password = request.form.get('ssh_password')
        if not ssh_host or not ssh_user or not ssh_password:
            error = "All fields must be filled out!"
        else:
            try:
                with open('config.py', 'w') as f:
                    f.write(f"SSH_HOST = '{ssh_host}'\n")
                    f.write(f"SSH_USER = '{ssh_user}'\n")
                    f.write(f"SSH_PASSWORD = '{ssh_password}'\n")
                    f.write("PORT = 5434\n")
                message = "SSH settings saved. Please log in."
                return redirect(url_for('login'))
            except Exception as e:
                error = "An error occurred while saving the configuration!"
    return render_template('setup.html', message=message, error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if not is_configured():
        return redirect(url_for('setup'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        stored_ssh_password, stored_ssh_host, stored_ssh_user = get_ssh_credentials()
        if username == stored_ssh_user and password == stored_ssh_password:
            session['logged_in'] = True
            session['dark_mode'] = True if request.form.get('dark_mode') == 'on' else False
            session['auto_logout'] = True if request.form.get('auto_logout') == 'on' else False
            return redirect(url_for('index'))
        else:
            error = "Invalid username or password!"
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    return render_template('index.html',
                           dark_mode=session.get('dark_mode', True),
                           auto_logout=session.get('auto_logout', True))

@app.route('/data')
def data():
    containers = fetch_docker_data()
    return jsonify(containers)

@app.route('/manage', methods=['POST'])
def manage():
    action = request.json.get('action')
    container_id = request.json.get('cid')
    if action.lower() == 'resume':
        action = 'unpause'
    command = f"docker {action} {container_id}"
    try:
        ssh = get_ssh_connection()
        ssh.exec_command(command)
        ssh.close()
    except Exception as e:
        print(f"Error managing container {action}: {str(e)}")
    return jsonify(success=True)

@app.route('/logs')
def logs():
    cid_trunc = request.args.get('cid')
    if not cid_trunc:
        return jsonify(success=False, error="No container id provided")
    try:
        ssh = get_ssh_connection()
        stdin, stdout, stderr = ssh.exec_command("docker ps -a -q --no-trunc")
        full_ids = stdout.read().decode().strip().splitlines()
        ssh.close()
        full_id = None
        for fid in full_ids:
            if fid.startswith(cid_trunc):
                full_id = fid
                break
        if full_id is None:
            full_id = cid_trunc  # fallback
        command = f"docker logs --tail 100 {full_id} 2>&1"
        ssh = get_ssh_connection()
        stdin, stdout, stderr = ssh.exec_command(command)
        logs_output = stdout.read().decode() + stderr.read().decode()
        ssh.close()
    except Exception as e:
        logs_output = f"Error fetching logs: {str(e)}"
    return jsonify(logs=logs_output)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
