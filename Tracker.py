import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import subprocess

PUSHOVER_USER_KEY = os.environ.get("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.environ.get("PUSHOVER_API_TOKEN")

# Define milestones
milestones = list(range(314100, 314140, 2)) + list(range(314140, 314160, 1))

# Paths to local state files
LAST_KNOWN_FILE = "last_known.txt"
LAST_MILESTONE_FILE = "last_milestone.txt"

# Repo settings for state branch
git_user_email = "actions@github.com"
git_user_name = "GitHub Actions"
state_branch = "state"

def get_latest_pdga_number():
    url = "https://www.pdga.com/players?order=PDGANum&sort=desc"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Cache-Control": "no-cache"
    }
    response = requests.get(url, headers=headers, params={"t": datetime.utcnow().timestamp()})
    soup = BeautifulSoup(response.text, 'html.parser')

    rows = soup.select("table.views-table tbody tr")
    if not rows:
        print("No table rows found — site layout may have changed.")
        return None

    first_row = rows[0]
    columns = first_row.find_all('td')
    if len(columns) < 2:
        print("Unexpected table row structure.")
        return None

    pdga_number = columns[1].text.strip()
    try:
        return int(pdga_number)
    except ValueError:
        print(f"Invalid number in PDGA column: {pdga_number}")
        return None


def send_pushover(message):
    if not (PUSHOVER_USER_KEY and PUSHOVER_API_TOKEN):
        print("Missing Pushover credentials")
        return

    data = {
        "token": PUSHOVER_API_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "message": message
    }
    response = requests.post("https://api.pushover.net/1/messages.json", data=data)
    if response.status_code != 200:
        print(f"Pushover error: {response.text}")

def run_git_command(cmd):
    print(f"Running git command: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

def checkout_state_branch():
    run_git_command(f"git config user.email \"{git_user_email}\"")
    run_git_command(f"git config user.name \"{git_user_name}\"")
    run_git_command("git fetch origin")
    try:
        run_git_command(f"git checkout {state_branch}")
    except subprocess.CalledProcessError:
        run_git_command(f"git checkout --orphan {state_branch}")
        run_git_command("git rm -rf .")
        open(LAST_KNOWN_FILE, 'w').close()
        open(LAST_MILESTONE_FILE, 'w').close()
        run_git_command("git add .")
        run_git_command("git commit -m 'Initialize state branch'")
        run_git_command(f"git push origin {state_branch}")

def load_value(filepath, default=0):
    if not os.path.exists(filepath):
        return default
    with open(filepath, 'r') as f:
        try:
            return int(f.read().strip())
        except ValueError:
            return default

def save_value(filepath, value):
    with open(filepath, 'w') as f:
        f.write(str(value))

def commit_and_push_state():
    run_git_command("git add .")
    run_git_command("git commit -m 'Update PDGA tracker state' || echo 'No changes to commit'")
    run_git_command(f"git push origin {state_branch} --force")

def run_check():
    checkout_state_branch()

    latest = get_latest_pdga_number()
    if latest is None:
        print("Could not retrieve PDGA number")
        return

    print(f"Latest PDGA number: {latest}")
    last_known = load_value(LAST_KNOWN_FILE)
    last_milestone = load_value(LAST_MILESTONE_FILE)

    crossed = [m for m in milestones if last_known < m <= latest and m > last_milestone]
    if crossed:
        newest = max(crossed)
        if newest >= 314130:
            message = f"PDGA number crossed milestone: {newest}! Latest: {latest}. CHANGE TO 5 MINUTE CHECKS"
        else:
            message = f"PDGA number crossed milestone: {newest}! Latest: {latest}"
        send_pushover(message)
        save_value(LAST_MILESTONE_FILE, newest)

    save_value(LAST_KNOWN_FILE, latest)
    commit_and_push_state()

if __name__ == "__main__":
    run_check()
