import argparse

from src.ops.experiments import run_experiment


parser = argparse.ArgumentParser()
parser.add_argument("proposal_id")
parser.add_argument("--dataset", required=True)

args = parser.parse_args()
print(run_experiment(args.proposal_id, args.dataset))
