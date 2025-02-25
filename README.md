# DockerMonitor-DockerVersion
A Docker host monitoring tool that runs in its own Docker container and can monitor both local and remote Docker hosts.

Docker Monitor is a lightweight Python-based web application that provides real-time monitoring of Docker container resource usage through a web dashboard. Inspired by the command-line tool `ctop`, it displays essential metrics such as CPU, memory, network I/O, and container status (running, paused, stopped) while also allowing basic container management actions.

You can access the monitoring dashboard remotely via `http://localhost:PORT`, where `PORT` is the port number specified in the configuration (default is 5434).

Use the SSH credentials you provide during setup to log in, which should match the SSH host login details.

![Dashboard Screenshot](https://github.com/user-attachments/assets/f9ce68a9-8e4d-4a52-9852-d14fa856b7c0)
![Container Management](https://github.com/user-attachments/assets/b0ffdff0-0469-415c-ab5d-6ef3673adc95)

## The Goal of the Project

- **Real-Time Visibility:**  
  Provide a lightweight dashboard that shows the resource usage of all running or filtered Docker containers on a single screen. This makes it easy to identify containers with excessive or abnormal resource consumption, which could impact overall performance.
- **Basic Container Management:**  
  Allow for simple intervention actions, such as stopping, restarting, or pausing containers, directly from the dashboard.

## Features

- **Real-Time Monitoring:**  
  - Displays live data for Docker containers including CPU usage, memory usage (with progress bars), network traffic, and I/O statistics.

- **Container Status & Management:**  
  - Shows the status of each container (running, paused, stopped) and provides a context menu to perform actions (start, stop, restart, pause, resume).

- **Inspect Container Logs:**  
  - Offers a simple view of container logs that update periodically, making it easier to monitor log entries and errors.  
  ![Logs Screenshot](https://github.com/user-attachments/assets/87ae79f6-e6af-4cdc-a6a4-e15c0110fec0)

- **Filtering and Sorting:**  
  - Click on the "NAME" header to filter containers by name.
  - Click on "CPU" or "MEM" headers to sort containers by resource usage.  
  ![Filtering and Sorting](https://github.com/user-attachments/assets/997ac9e2-88e5-4246-8261-b21bef0d657a)  
  ![Sorting Screenshot](https://github.com/user-attachments/assets/8cb33330-f211-4b5f-8cde-8cb510132b5f)

- **Remote Docker Host Access & Statistics:**  
  - Connects via SSH (using Paramiko) to a Docker host to retrieve container statistics.
  - Utilizes CHART.JS for real-time and short-term historical data visualization.  
  ![Charts Screenshot](https://github.com/user-attachments/assets/dd745752-cd1c-46df-bb1d-1e46e884f109)

- **Multiple Instance Support:**  
  - Easily update the SSH settings to monitor different Docker hosts without conflicts.

- **Auto Logout & Dark/Light Mode:**  
  - Login page options allow for auto logout and switching between dark and light themes.

- **Production-Ready Deployment:**  
  - Runs with Gunicorn as the production WSGI server to ensure better performance and reliability.

- **Simple & Responsive UI:**  
  - A minimal, clean interface built with HTML/CSS for straightforward monitoring.

## Getting Started

### Prerequisites

- **Operating System:**  
  Docker Monitor can run on any system that supports Docker (Linux, Windows, macOS). For production, a Linux-based system is recommended.
- **Docker:**  
  Ensure Docker is installed and running on your system.
- **Docker Host:**  
  Access to a Docker host (local or remote) with valid SSH credentials for executing Docker commands.
- **SSH Credentials:**  
  You must have valid SSH credentials (host, username, and password) to connect to your Docker host.

### Installation

Docker Monitor is available on Docker Hub. Follow these steps to install and run it:

1. **Pull the Docker Image:**
   Open a terminal and run:
   
    $ docker pull szemod/dockermonitor

2. **Run the Docker Container:**
   Launch the container with:

    $ docker run --name dockermonitor -p 5434:5434 szemod/dockermonitor
   
3. **SSH Setup:**
   On the first launch, you will be directed to the SSH setup page.

4. **Configure SSH Settings:**
   - The setup page will prompt you for your SSH Host, SSH Username, and SSH Password.
   - Save the settings to configure the connection to your Docker host.
   - After a successful setup, you will be redirected to the login page.

## Login to the Dashboard

Use the SSH Username and SSH Password provided during setup to log in.  
Once authenticated, you can access real-time Docker container statistics via the web dashboard.

## Repository Structure

- **web_ctop.py**: Main Python script that retrieves Docker container statistics and serves the web dashboard.
- **templates/index.html**: HTML template for the web interface.
- **templates/login.html**: HTML template for the login page.
- **templates/setup.html**: HTML template for the SSH setup page.
- **Dockerfile**: Instructions for building the Docker image.
- **requirements.txt**: Lists all required Python packages.
- **config.py**: Configuration file where SSH credentials and port settings are stored.

## Customization

### SSH Configuration

The default SSH credentials are stored in `config.py` and can be updated via the setup page.

### Port Setting

The application listens on port 5434 by default; modify the `PORT` variable in `config.py` to change this.

## License

This project is licensed under the MIT License.

## Acknowledgements

- **Flask**: Web framework for building the dashboard.
- **Paramiko**: Provides SSH connectivity to the Docker host.
- **Gunicorn**: Production-ready WSGI server used for deployment.
- **CHART.JS**: Used for real-time charting of container statistics.
- **Docker**: Containerization platform that powers this solution.
- Inspired by the functionality of ctop for real-time Docker monitoring.

## Future Developments

- Encrypted password management for enhanced security.
- Enhanced logging and alerting features.
- Additional container management capabilities.

