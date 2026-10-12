import argparse
from getpass import getpass

from src.auth.service import login, logout, auth_scope
from src.ops.experiments import run_experiment


parser = argparse.ArgumentParser()
parser.add_argument("proposal_id")
parser.add_argument("--dataset", required=True)

parser.add_argument("--username", required=True)
args = parser.parse_args()
token = login(args.username, getpass("Mật khẩu admin: "))

try:
    with auth_scope(token):
        print(run_experiment(args.proposal_id, args.dataset))
finally:
    logout(token)
