"""
Command-line interface for GitDigital Policy Engine
"""
import json
import yaml
import argparse
import sys
from pathlib import Path
from typing import Optional

from ..engine.core import PolicyEngine, EngineMode
from ..language.dsl import PolicyDSL, create_eligibility_policy
from ..models.policy import Policy
from ..utils.logger import setup_logging


def main():
    """Main CLI entry point"""
    
    parser = argparse.ArgumentParser(
        description="GitDigital Policy Engine - Rules-as-Code for eligibility and compliance"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate policy against data")
    eval_parser.add_argument("policy", help="Policy file or ID")
    eval_parser.add_argument("data", help="Applicant data file")
    eval_parser.add_argument("--format", choices=["json", "yaml"], default="json")
    eval_parser.add_argument("--output", "-o", help="Output file")
    eval_parser.add_argument("--mode", choices=["strict", "lenient", "debug"], default="strict")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate policy file")
    validate_parser.add_argument("policy", help="Policy file")
    validate_parser.add_argument("--format", choices=["json", "yaml"], default="json")
    
    # Create command
    create_parser = subparsers.add_parser("create", help="Create example policy")
    create_parser.add_argument("type", help="Policy type", choices=["eligibility", "compliance"])
    create_parser.add_argument("--output", "-o", help="Output file")
    create_parser.add_argument("--format", choices=["json", "yaml"], default="json")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List loaded policies")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export policy")
    export_parser.add_argument("policy_id", help="Policy ID")
    export_parser.add_argument("--format", choices=["json", "yaml"], default="json")
    export_parser.add_argument("--output", "-o", help="Output file")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    setup_logging()
    
    if args.command == "evaluate":
        evaluate_command(args)
    elif args.command == "validate":
        validate_command(args)
    elif args.command == "create":
        create_command(args)
    elif args.command == "list":
        list_command(args)
    elif args.command == "export":
        export_command(args)


def evaluate_command(args):
    """Handle evaluate command"""
    
    engine = PolicyEngine(mode=EngineMode(args.mode))
    
    # Load policy
    policy_path = Path(args.policy)
    if policy_path.exists():
        with open(policy_path, 'r') as f:
            if args.format == "json":
                policy_data = json.load(f)
            else:
                policy_data = yaml.safe_load(f)
                
        policy = engine.load_policy(policy_data, format=args.format)
    else:
        # Assume it's a policy ID already loaded
        policy = engine.get_policy(args.policy)
        if not policy:
            print(f"Error: Policy not found: {args.policy}")
            sys.exit(1)
            
    # Load data
    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Error: Data file not found: {args.data}")
        sys.exit(1)
        
    with open(data_path, 'r') as f:
        if args.format == "json":
            applicant_data = json.load(f)
        else:
            applicant_data = yaml.safe_load(f)
            
    # Evaluate
    try:
        decision = engine.evaluate_eligibility(policy.id, applicant_data)
        
        # Output result
        result = {
            "policy_id": decision.policy_id,
            "policy_version": decision.policy_version,
            "overall_eligible": decision.overall_eligible,
            "results": [r.model_dump() for r in decision.results],
            "timestamp": decision.timestamp.isoformat(),
            "metadata": decision.metadata
        }
        
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w') as f:
                if args.format == "json":
                    json.dump(result, f, indent=2, default=str)
                else:
                    yaml.dump(result, f, default_flow_style=False)
            print(f"Result written to {args.output}")
        else:
            print(json.dumps(result, indent=2, default=str))
            
    except Exception as e:
        print(f"Error during evaluation: {e}")
        sys.exit(1)


def validate_command(args):
    """Handle validate command"""
    
    from ..engine.validator import RuleValidator
    
    validator = RuleValidator()
    policy_path = Path(args.policy)
    
    if not policy_path.exists():
        print(f"Error: Policy file not found: {args.policy}")
        sys.exit(1)
        
    try:
        with open(policy_path, 'r') as f:
            if args.format == "json":
                policy_data = json.load(f)
            else:
                policy_data = yaml.safe_load(f)
                
        # Validate
        is_valid, errors = validator.validate_policy_structure(policy_data)
        
        if is_valid:
            print("✓ Policy is valid")
        else:
            print("✗ Policy has errors:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error validating policy: {e}")
        sys.exit(1)


def create_command(args):
    """Handle create command"""
    
    if args.type == "eligibility":
        policy = create_eligibility_policy()
    else:
        print(f"Policy type not implemented: {args.type}")
        sys.exit(1)
        
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            if args.format == "json":
                json.dump(policy.model_dump(), f, indent=2, default=str)
            else:
                yaml.dump(policy.model_dump(), f, default_flow_style=False)
        print(f"Policy created: {output_path}")
    else:
        if args.format == "json":
            print(policy.model_dump_json(indent=2))
        else:
            print(yaml.dump(policy.model_dump(), default_flow_style=False))


def list_command(args):
    """Handle list command"""
    
    engine = PolicyEngine()
    policies = engine.list_policies()
    
    if policies:
        print("Loaded policies:")
        for policy_id in policies:
            policy = engine.get_policy(policy_id)
            print(f"  - {policy_id}: {policy.name} (v{policy.version})")
    else:
        print("No policies loaded")


def export_command(args):
    """Handle export command"""
    
    engine = PolicyEngine()
    policy = engine.get_policy(args.policy_id)
    
    if not policy:
        print(f"Error: Policy not found: {args.policy_id}")
        sys.exit(1)
        
    export_data = engine.export_policy(args.policy_id, args.format)
    
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            f.write(export_data)
        print(f"Policy exported to {args.output}")
    else:
        print(export_data)


if __name__ == "__main__":
    main()
