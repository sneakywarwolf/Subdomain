import os  # Provides functions to interact with the operating system
import csv  # Facilitates reading and writing CSV files
import sys  # Access system-specific parameters and functions
import requests  # Simplifies HTTP requests (GET, POST, etc.)
from tqdm import tqdm  # Displays progress bars for loops or operations
import subprocess  # Allows execution of system commands
import time  # Provides time-related functions
from concurrent.futures import ThreadPoolExecutor  # Enables multithreading with a high-level interface
import re  # Supports regular expression operations
import argparse  # Parses command-line arguments and options
import socket  # Facilitates networking operations and socket programming
import random  # Generates random numbers and choices

ascii_art = """
                                                                                 
   SSSSSSSSSSSSSSS FFFFFFFFFFFFFFFFFFFFFF      AAA                  CCCCCCCCCCCCC
 SS:::::::::::::::SF::::::::::::::::::::F     A:::A              CCC::::::::::::C
S:::::SSSSSS::::::SF::::::::::::::::::::F    A:::::A           CC:::::::::::::::C
S:::::S     SSSSSSSFF::::::FFFFFFFFF::::F   A:::::::A         C:::::CCCCCCCC::::C
S:::::S              F:::::F       FFFFFF  A:::::::::A       C:::::C       CCCCCC
S:::::S              F:::::F              A:::::A:::::A     C:::::C              
 S::::SSSS           F::::::FFFFFFFFFF   A:::::A A:::::A    C:::::C              
  SS::::::SSSSS      F:::::::::::::::F  A:::::A   A:::::A   C:::::C              
    SSS::::::::SS    F:::::::::::::::F A:::::A     A:::::A  C:::::C              
       SSSSSS::::S   F::::::FFFFFFFFFFA:::::AAAAAAAAA:::::A C:::::C              
            S:::::S  F:::::F         A:::::::::::::::::::::AC:::::C              
            S:::::S  F:::::F        A:::::AAAAAAAAAAAAA:::::AC:::::C       CCCCCC
SSSSSSS     S:::::SFF:::::::FF     A:::::A             A:::::AC:::::CCCCCCCC::::C
S::::::SSSSSS:::::SF::::::::FF    A:::::A               A:::::ACC:::::::::::::::C
S:::::::::::::::SS F::::::::FF   A:::::A                 A:::::A CCC::::::::::::C
 SSSSSSSSSSSSSSS   FFFFFFFFFFF  AAAAAAA                   AAAAAAA   CCCCCCCCCCCCC
     
                                    Subdomain Finder and Accessibility Checker  
                                                                    v1.4 created by Sneakywarwolf
"""
print(ascii_art)

def print_status(message):
    """Print a status message with a timestamp."""
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

def run_sublist3r(domain):
    """Run Sublist3r to enumerate subdomains with a dynamic progress bar."""
    sublist3r_path = os.path.join('Sublist3r', 'sublist3r.py')
    if not os.path.exists(sublist3r_path):
        print("Error: Sublist3r script not found in the Sublist3r folder.")
        return []

    try:
        print_status("Starting Sublist3r...")
        process = subprocess.Popen(
            ['python', sublist3r_path, '-d', domain],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        subdomains = set()

        with tqdm(desc="Finding subdomains", unit="subdomain", leave=True) as pbar:
            for line in process.stdout:
                line = line.strip()
                if line and "://" not in line:  # Ignore noise
                    subdomain = line.split()[-1] if line.startswith("[+]") else line
                    if subdomain and subdomain not in subdomains:
                        subdomains.add(subdomain)
                        pbar.update(1)

        process.wait()

        if process.returncode != 0:
            print(f"Sublist3r error: {process.stderr.read().strip()}")
            return []

        print_status(f"Sublist3r found {len(subdomains)} unique subdomains.")
        return list(subdomains)
    except Exception as e:
        print(f"Error running Sublist3r: {e}")
        return []

def is_valid_subdomain(subdomain):
    """Validate subdomain using a regular expression."""
    subdomain_regex = r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.(?!-)[A-Za-z0-9.-]{1,255}$'
    return re.match(subdomain_regex, subdomain) is not None

def resolve_subdomain(subdomain, resolver_ip=None):
    """Resolve a subdomain to an IP address using a custom resolver if provided."""
    try:
        resolver = dns.resolver.Resolver()
        if resolver_ip:
            resolver.nameservers = [resolver_ip]
        answers = resolver.resolve(subdomain, 'A')
        return answers[0].to_text()  # Return the first resolved IP
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.Timeout) as e:
        return None

def check_subdomain(subdomain, resolver_ip=None):
    """Check the accessibility of a single subdomain."""
    if not is_valid_subdomain(subdomain):
        return {"Subdomain": subdomain, "Status Code": "Invalid", "Accessible": "No", "Resolved IP": "N/A"}

    resolved_ip = resolve_subdomain(subdomain, resolver_ip)
    if not resolved_ip:
        return {"Subdomain": subdomain, "Status Code": "Unresolved", "Accessible": "No", "Resolved IP": "N/A"}

    try:
        response = requests.get(f"http://{subdomain}", timeout=10)
        status_code = response.status_code
        accessible = "Yes" if status_code == 200 else "No"
    except requests.RequestException:
        status_code = "N/A"
        accessible = "No"

    return {"Subdomain": subdomain, "Status Code": status_code, "Accessible": accessible, "Resolved IP": resolved_ip}

def retry_with_resolvers(subdomain, resolvers):
    """Retry checking the accessibility of a subdomain with random resolvers."""
    for resolver in resolvers:
        result = check_subdomain(subdomain, resolver_ip=resolver)
        if result["Accessible"] == "Yes":
            return result
    return {"Subdomain": subdomain, "Status Code": "Unresolved", "Accessible": "No", "Resolved IP": "N/A"}

def write_filtered_to_csv(results, output_file):
    """Write only valid subdomains to a CSV file."""
    valid_results = [result for result in results if is_valid_subdomain(result["Subdomain"])]
    
    with open(output_file, mode='w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ["Subdomain", "Status Code", "Accessible", "Resolved IP"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(valid_results)
    
    print_status(f"Filtered results saved to {output_file}")

def check_subdomains_concurrently(subdomain_list, resolvers, output_file):
    """Check subdomains concurrently and save results to a CSV file."""
    print_status(f"Checking accessibility of {len(subdomain_list)} subdomains...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(tqdm(executor.map(lambda sub: retry_with_resolvers(sub, resolvers), subdomain_list), total=len(subdomain_list), desc="Checking subdomains"))
    
    write_filtered_to_csv(results, output_file)

def load_resolvers(file_path):
    """Load resolver IPs from a file."""
    if not os.path.exists(file_path):
        print_status(f"Resolver file '{file_path}' not found. Continuing without custom resolvers.")
        return []
    with open(file_path, 'r') as file:
        return [line.strip() for line in file.readlines() if line.strip()]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Subdomain enumeration and accessibility checker.")
    parser.add_argument("-D", "--domain", help="Domain to enumerate subdomains for.")
    parser.add_argument("-t", "--textfile", help="Path to the text file containing subdomains.")
    parser.add_argument("-o", "--output", help="Output CSV file to save results.", default=f"output_{int(time.time())}.csv")
    parser.add_argument("-r", "--resolvers", help="Path to the resolvers.txt file.", default="resolvers.txt")

    args = parser.parse_args()

    resolvers = load_resolvers(args.resolvers)

    if args.domain:
        output_file = args.output
        if not output_file.endswith(".csv"):
            output_file += ".csv"

        subdomains = run_sublist3r(args.domain)
        if subdomains:
            check_subdomains_concurrently(subdomains, resolvers, output_file)
        else:
            print_status("No subdomains found.")

    elif args.textfile:
        if os.path.exists(args.textfile):
            with open(args.textfile, 'r') as file:
                subdomains = [line.strip() for line in file.readlines()]
            if subdomains:
                check_subdomains_concurrently(subdomains, resolvers, args.output)
            else:
                print_status("Subdomain list is empty.")
        else:
            print(f"Error: File {args.textfile} not found.")
    else:
        parser.print_help()
        sys.exit(1)
