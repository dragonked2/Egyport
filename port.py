import socket
import threading
import signal
from queue import Queue, Empty
from tqdm import tqdm
import time
import ipaddress
from colorama import Fore, init

# Initialize colorama
init()

# Number of threads for concurrent scanning
NUM_THREADS = 200

# Lock for thread synchronization
print_lock = threading.Lock()

# Flag for Ctrl+C interruption
interrupted = False

# Function to handle Ctrl+C interruption
def signal_handler(sig, frame):
    global interrupted
    interrupted = True

# Function to scan ports
def scan_ports(target_ip, port_queue, open_ports, services, pbar):
    while not port_queue.empty() and not interrupted:
        # Get the next port from the queue
        try:
            port = port_queue.get(timeout=0.1)
        except Empty:
            break

        # Create a socket object
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            # Set a timeout value for the socket operations
            sock.settimeout(1)

            # Attempt to connect to the port
            result = sock.connect_ex((target_ip, port))

            # Check if the port is open
            if result == 0:
                with print_lock:
                    open_ports.append(port)

                    # Get the service name and banner
                    service_name = socket.getservbyport(port)
                    banner = get_banner(sock)
                    service = f"{service_name} ({banner})" if banner else service_name
                    services[port] = service

                    progress_str = f"Port {port}: Open ({service})"
                    print(progress_str.ljust(pbar.ncols))

        except socket.error:
            pass

        finally:
            # Close the socket
            sock.close()

        # Mark the task as done in the queue
        port_queue.task_done()
        pbar.update()

# Function to get the banner from the socket
def get_banner(sock):
    try:
        # Set a timeout value for the receive operation
        sock.settimeout(1)

        # Receive the response
        response = sock.recv(1024).decode().strip()

        # Parse the response to extract the title or banner
        title = ""
        lines = response.split("\n")
        for line in lines:
            if line.startswith("Server:"):
                title = line.split(": ", 1)[1].strip()
                break
            elif line.startswith("SSH-"):
                title = "SSH"
                break
            elif line.startswith("HTTP/"):
                title = "HTTP"
                break
            elif line.startswith("220"):
                title = "FTP"
                break
            elif line.startswith("MySQL"):
                title = "MySQL"
                break

        return title

    except socket.error:
        return ""

# Function to print the logo with glowing effect
def print_logo():
    logo = """
    ███████╗██╗   ██╗██████╗ ███████╗██████╗  █████╗ ██████╗ ██╗     ███████╗
    ██╔════╝██║   ██║██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔══██╗██║     ██╔════╝
    ███████╗██║   ██║██████╔╝█████╗  ██████╔╝███████║██████╔╝██║     █████╗  
    ╚════██║██║   ██║██╔═══╝ ██╔══╝  ██╔══██╗██╔══██║██╔══██╗██║     ██╔══╝  
    ███████║╚██████╔╝██║     ███████╗██║  ██║██║  ██║██████╔╝███████╗███████╗
    ╚══════╝ ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝
    """

    glow_colors = [Fore.YELLOW]
    interval = 0.5  # Time interval between color changes (in seconds)

    for color in glow_colors:
        print(color + logo)
        time.sleep(interval)

# Get target IP or domain name from the user
target = input("Enter the target IP address or domain name: ")

# Check if the input is an IP address or domain name
try:
    ipaddress.ip_address(target)
    # Valid IP address provided
    target_ip = target
except ValueError:
    # Invalid IP address, try resolving it as a domain name
    try:
        target_ip = socket.gethostbyname(target)
    except socket.gaierror:
        print("Invalid domain name or unable to resolve the domain name to an IP address.")
        exit(1)

# Create a queue for ports
port_queue = Queue()

# Add common services ports to the queue
common_services = [21, 22, 23, 25, 53, 80, 110, 143, 443, 3306, 3389]
for port in common_services:
    port_queue.put(port)

# Add remaining ports to the queue
for port in range(1, 65336):
    if port not in common_services:
        port_queue.put(port)

# Create a list to store open ports and services
open_ports = []
services = {}

# Register the signal handler for Ctrl+C
signal.signal(signal.SIGINT, signal_handler)

# Create and start threads
threads = []
pbar = None

try:
    # Print the logo
    print_logo()

    # Scanning ports message
    print("\nScanning ports...\n")

    # Display progress bar
    pbar = tqdm(total=port_queue.qsize(), ncols=80, unit='port(s)', bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}', leave=False, ascii=True)

    for _ in range(NUM_THREADS):
        thread = threading.Thread(target=scan_ports, args=(target_ip, port_queue, open_ports, services, pbar))
        thread.daemon = True
        thread.start()
        threads.append(thread)

    # Wait for all tasks in the queue to be completed or interrupted
    while not port_queue.empty() and not interrupted:
        try:
            # Check if the queue is empty within a timeout interval
            start_time = time.time()
            while time.time() - start_time < 0.1:
                if port_queue.empty():
                    break
                time.sleep(0.01)

        except KeyboardInterrupt:
            # Handle Ctrl+C interruption
            interrupted = True
            break

except KeyboardInterrupt:
    # Handle Ctrl+C interruption
    interrupted = True

finally:
    # Close the progress bar
    if pbar is not None:
        pbar.close()

# Print open ports and services
print("\nOpen Ports:")
print("-----------")
for port in open_ports:
    service = services.get(port, "Unknown")
    print(f"Port {port}: Open ({service})")
