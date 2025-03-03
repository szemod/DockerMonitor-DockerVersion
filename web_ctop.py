# web_ctop.py
import warnings
try:
    from cryptography.utils import CryptographyDeprecationWarning
except ImportError:
    CryptographyDeprecationWarning = DeprecationWarning

# Ignore specific cryptography deprecation warnings
warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)

import os
import time
import paramiko
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from config import PORT

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Secret key for session management

def is_configured():
    try:
        with open('config.py', 'r') as f:
            config_content = f.read()
        config = {}
        exec(config_content, config)
        hosts = config.get('DOCKER_HOSTS', [])
        return bool(hosts)  # Check if Docker hosts are configured
    except Exception as e:
        print(f"Error reading configuration: {e}")
        return False

def get_ssh_credentials():
    try:
        with open('config.py', 'r') as f:
            config_content = f.read()
        config = {}
        exec(config_content, config)
        hosts = config.get('DOCKER_HOSTS', [])
        if not hosts:
            return None, None, None
        selected_host = session.get('selected_host')
        if selected_host:
            for host in hosts:
                if host.get('docker_host_name') == selected_host:
                    return host.get('ssh_password'), host.get('ssh_host'), host.get('ssh_user')
            host = hosts[0]
            return host.get('ssh_password'), host.get('ssh_host'), host.get('ssh_user')
        else:
            host = hosts[0]
            return host.get('ssh_password'), host.get('ssh_host'), host.get('ssh_user')
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
        ssh.connect(SSH_HOST, username=SSH_USER, password=SSH_PASSWORD)  # Establish SSH connection
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
        return num / 1024  # Convert kilobytes to megabytes
    elif first_char == 'M':
        return num  # Already in megabytes
    elif first_char == 'G':
        return num * 1024  # Convert gigabytes to megabytes
    elif first_char == 'T':
        return num * 1024 * 1024  # Convert terabytes to megabytes
    else:
        return num

def parse_container_status(status_str):
    status_str = status_str.strip()
    if "Paused" in status_str:
        return "paused"  # Container is paused
    elif status_str.startswith("Up"):
        return "running"  # Container is running
    elif status_str.startswith("Exited"):
        return "stopped"  # Container has stopped
    else:
        return status_str  # Default case for unknown status

def parse_docker_stats(output):
    containers = []
    for line in output.strip().split('\n'):
        parts = line.split('|')
        if len(parts) != 7:
            continue
        cid, name, cpu, mem, net, io, pids = parts
        try:
            cpu_percent = float(cpu.replace('%', ''))  # Parse CPU percentage
        except ValueError:
            cpu_percent = 0.0

        mem_parts = mem.split('/')
        if len(mem_parts) == 2:
            mem_used, mem_total = mem_parts
            mem_used = mem_used.strip()
            mem_total = mem_total.strip()
            used_mb = convert_to_mb(mem_used)  # Convert memory used to MB
            total_mb = convert_to_mb(mem_total)  # Convert total memory to MB
            mem_percent = (used_mb / total_mb * 100) if total_mb > 0 else 0  # Calculate memory percentage
            mem_used_formatted = f"{used_mb:.1f} MB"
        else:
            used_mb = convert_to_mb(mem.strip())  # Convert memory to MB if not in used/total format
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
        stdin, stdout, stderr = ssh.exec_command(command_stats)
        output_stats = stdout.read().decode()  # Fetch container stats
        ssh.close()
    except Exception as e:
        print(f"Error fetching stats: {str(e)}")
        output_stats = ""
    containers = parse_docker_stats(output_stats)  # Parse fetched stats
    command_status = """ docker ps -a --format "{{.ID}}|{{.Status}}" """
    try:
        ssh = get_ssh_connection()
        stdin, stdout, stderr = ssh.exec_command(command_status)
        output_status = stdout.read().decode()  # Fetch container statuses
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
            container_id = parts[0]
            stat = parts[1]
            statuses[container_id[:12]] = parse_container_status(stat)  # Parse status of each container
    max_used = 0
    for i in range(len(containers)):
        container = containers[i]
        cid = container['cid']
        container['status'] = statuses.get(cid, 'unknown')
        if container['mem_used_val'] > max_used:
            max_used = container['mem_used_val']  # Track maximum memory used
    for i in range(len(containers)):
        c = containers[i]
        if max_used > 0:
            c['mem_bar_percent'] = (c['mem_used_val'] / max_used) * 100  # Calculate memory bar percentage
        else:
            c['mem_bar_percent'] = 0
    return containers

@app.before_request
def require_login():
    # Ensure user is logged in unless accessing setup or delete_host
    if request.endpoint not in ['setup', 'static', 'delete_host'] and not is_configured():
        return redirect(url_for('setup'))
    if request.endpoint not in ['login', 'setup', 'static', 'delete_host']:
        if not session.get('logged_in'):
            return redirect(url_for('login'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    message = None
    error = None
    # Load current hosts from config.py
    current_hosts = []
    try:
        with open('config.py', 'r') as f:
            config_content = f.read()
        config = {}
        exec(config_content, config)
        current_hosts = config.get('DOCKER_HOSTS', [])
    except Exception as e:
        print(f"Error reading config: {e}")

    if request.method == 'POST':
        # Expect all fields to be filled: docker_host_name, ssh_host, ssh_user, ssh_password
        ssh_host = request.form.get('ssh_host')
        ssh_user = request.form.get('ssh_user')
        ssh_password = request.form.get('ssh_password')
        docker_host_name = request.form.get('docker_host_name')
        if not ssh_host or not ssh_user or not ssh_password or not docker_host_name:
            error = "All fields must be filled out!"  # Validation error for empty fields
        else:
            new_host = {
                'docker_host_name': docker_host_name,
                'ssh_host': ssh_host,
                'ssh_user': ssh_user,
                'ssh_password': ssh_password
            }
            current_hosts.append(new_host)
            # Update LAST_SELECTED_HOST value
            last_selected = docker_host_name
            try:
                with open('config.py', 'w') as f:
                    f.write("DOCKER_HOSTS = " + repr(current_hosts) + "\n")
                    f.write("LAST_SELECTED_HOST = " + repr(last_selected) + "\n")
                    f.write("PORT = 5434\n")
                message = "SSH settings saved. You can add more hosts or proceed to login."
                return redirect(url_for('setup'))
            except Exception as e:
                error = "An error occurred while saving the configuration!"  # Error during saving

    return render_template('setup.html', message=message, error=error, hosts=current_hosts)  # Render the setup page

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if not is_configured():
        return redirect(url_for('setup'))  # Redirect to setup if not configured
    # Load hosts from config
    current_hosts = []
    config = {}
    try:
        with open('config.py', 'r') as f:
            config_content = f.read()
        exec(config_content, config)
        current_hosts = config.get('DOCKER_HOSTS', [])
    except Exception as e:
        print(f"Error reading config: {e}")
    default_host = None
    if 'selected_host' in session:
        default_host = session['selected_host']
    elif config.get('LAST_SELECTED_HOST'):
        default_host = config.get('LAST_SELECTED_HOST')
    elif current_hosts:
        default_host = current_hosts[0].get('docker_host_name')
    if request.method == 'POST':
        selected_host = request.form.get('selected_host')
        session['selected_host'] = selected_host
        username = request.form.get('username')
        password = request.form.get('password')
        stored_ssh_password, stored_ssh_host, stored_ssh_user = get_ssh_credentials()
        if username == stored_ssh_user and password == stored_ssh_password:
            # Update LAST_SELECTED_HOST value in config file
            try:
                config['LAST_SELECTED_HOST'] = selected_host
                with open('config.py', 'w') as f:
                    f.write("DOCKER_HOSTS = " + repr(config.get('DOCKER_HOSTS', [])) + "\n")
                    f.write("LAST_SELECTED_HOST = " + repr(selected_host) + "\n")
                    f.write("PORT = 5434\n")
            except Exception as e:
                print("Error updating LAST_SELECTED_HOST:", e)
            session['logged_in'] = True
            session['dark_mode'] = True if request.form.get('dark_mode') == 'on' else False
            session['auto_logout'] = True if request.form.get('auto_logout') == 'on' else False
            session['mobile_view'] = True if request.form.get('mobile_view') == 'on' else False
            return redirect(url_for('index'))  # Redirect to index after successful login
        else:
            error = "Invalid username or password!"  # Invalid login credentials
    return render_template('login.html', error=error, hosts=current_hosts, default_host=default_host)  # Render the login page

@app.route('/logout')
def logout():
    session.pop('logged_in', None)  # Clear the logged-in session
    return redirect(url_for('login'))  # Redirect to login page

@app.route('/')
def index():
    if session.get('mobile_view', False):
        return render_template('mobile.html',
                               dark_mode=session.get('dark_mode', True),
                               auto_logout=session.get('auto_logout', True),
                               mobile_view=True)  # Render mobile view
    else:
        return render_template('index.html',
                               dark_mode=session.get('dark_mode', True),
                               auto_logout=session.get('auto_logout', True),
                               mobile_view=False)  # Render desktop view

@app.route('/data')
def data():
    containers = fetch_docker_data()  # Fetch and return docker data
    return jsonify(containers)

@app.route('/manage', methods=['POST'])
def manage():
    action = request.json.get('action')
    container_id = request.json.get('cid')
    if action.lower() == 'resume':
        action = 'unpause'  # Convert 'resume' action to 'unpause'
    command = f'docker {action} {container_id}'
    try:
        ssh = get_ssh_connection()
        ssh.exec_command(command)  # Execute docker command to manage container
        ssh.close()
    except Exception as e:
        print(f"Error managing container {action}: {str(e)}")
    return jsonify(success=True)  # Return success response

@app.route('/logs')
def logs():
    cid_trunc = request.args.get('cid')
    if not cid_trunc:
        return jsonify(success=False, error="No container id provided")  # Error for missing container ID
    try:
        ssh = get_ssh_connection()
        stdin, stdout, stderr = ssh.exec_command("docker ps -a -q --no-trunc")
        full_ids = stdout.read().decode().strip().splitlines()  # Get full container IDs
        ssh.close()
        full_id = None
        for id in full_ids:
            if id.startswith(cid_trunc):
                full_id = id
                break
        if full_id is None:
            full_id = cid_trunc
        command = f'docker logs --tail 100 {full_id} 2>&1'  # Command to fetch container logs
        ssh = get_ssh_connection()
        stdin, stdout, stderr = ssh.exec_command(command)
        logs_output = stdout.read().decode() + stderr.read().decode()  # Get logs output
        ssh.close()
    except Exception as e:
        logs_output = f'Error fetching logs: {str(e)}'  # Error during fetching logs
    return jsonify(logs=logs_output)  # Return logs response

@app.route('/delete_host', methods=['POST'])
def delete_host():
    data = request.get_json()
    host_name = data.get('docker_host_name')
    if not host_name:
        return jsonify(success=False, error="No host name provided"), 400  # Error for missing host name
    current_hosts = []
    try:
        with open('config.py', 'r') as f:
            config_content = f.read()
        config = {}
        exec(config_content, config)
        current_hosts = config.get('DOCKER_HOSTS', [])
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500  # Error reading config

    new_hosts = [host for host in current_hosts if host.get('docker_host_name') != host_name]
    last_selected = config.get('LAST_SELECTED_HOST')
    if last_selected == host_name:
        last_selected = new_hosts[0]['docker_host_name'] if new_hosts else None  # Update last selected host

    try:
        with open('config.py', 'w') as f:
            f.write("DOCKER_HOSTS = " + repr(new_hosts) + "\n")
            f.write("LAST_SELECTED_HOST = " + repr(last_selected) + "\n")
            f.write("PORT = 5434\n")
    except Exception as e:
        return jsonify(success=False, error="An error occurred while saving the configuration!"), 500  # Error during saving

    return jsonify(success=True)  # Return success response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)  # Run the Flask application
