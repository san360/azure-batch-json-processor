#!/usr/bin/env python3
"""
Azure Batch Troubleshooting Script

Helps diagnose common issues with Azure Batch jobs.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def load_config(config_path: str = "../config/config.json") -> dict:
    """Load configuration from JSON file."""
    config_file = Path(__file__).parent / config_path
    
    if not config_file.exists():
        print(f"Error: Configuration file not found at {config_file}")
        return None
    
    with open(config_file, 'r') as f:
        return json.load(f)


def run_command(cmd: str, description: str) -> tuple:
    """Run a command and return result."""
    print(f"🔍 {description}")
    print(f"   Command: {cmd}")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


def check_job_status(job_id: str, config: dict):
    """Check job and task status."""
    print("\n" + "="*60)
    print("JOB STATUS ANALYSIS")
    print("="*60)
    
    batch_account = config["azure"]["batch"]["account_name"]
    batch_url = config["azure"]["batch"]["account_url"]
    
    # Check job status
    cmd = f'az batch job show --job-id {job_id} --account-name {batch_account} --account-endpoint {batch_url} --output json'
    code, stdout, stderr = run_command(cmd, "Checking job status")
    
    if code == 0:
        try:
            job_data = json.loads(stdout)
            print(f"✅ Job Status: {job_data.get('state', 'Unknown')}")
            print(f"   Pool ID: {job_data.get('poolInfo', {}).get('poolId', 'Unknown')}")
            print(f"   Creation Time: {job_data.get('creationTime', 'Unknown')}")
            
            if 'executionInfo' in job_data:
                exec_info = job_data['executionInfo']
                print(f"   Start Time: {exec_info.get('startTime', 'Not started')}")
                print(f"   End Time: {exec_info.get('endTime', 'Not finished')}")
            
        except json.JSONDecodeError:
            print(f"❌ Failed to parse job data")
            print(f"Raw output: {stdout[:500]}")
    else:
        print(f"❌ Job not found or error: {stderr}")
    
    # List tasks
    cmd = f'az batch task list --job-id {job_id} --account-name {batch_account} --account-endpoint {batch_url} --output json'
    code, stdout, stderr = run_command(cmd, "Listing tasks")
    
    if code == 0:
        try:
            tasks = json.loads(stdout)
            print(f"\n📋 Found {len(tasks)} task(s):")
            
            for task in tasks:
                task_id = task.get('id', 'Unknown')
                state = task.get('state', 'Unknown')
                print(f"   Task {task_id}: {state}")
                
                # Check for execution info
                if 'executionInfo' in task:
                    exec_info = task['executionInfo']
                    exit_code = exec_info.get('exitCode')
                    if exit_code is not None:
                        print(f"     Exit Code: {exit_code}")
                    
                    if 'failureInfo' in exec_info:
                        failure = exec_info['failureInfo']
                        print(f"     ❌ Failure Category: {failure.get('category', 'Unknown')}")
                        print(f"     ❌ Failure Code: {failure.get('code', 'Unknown')}")
                        print(f"     ❌ Failure Message: {failure.get('message', 'Unknown')}")
                
        except json.JSONDecodeError:
            print(f"❌ Failed to parse tasks data")
    else:
        print(f"❌ Failed to list tasks: {stderr}")


def check_task_files(job_id: str, task_id: str, config: dict):
    """Check task output files."""
    print("\n" + "="*60)
    print(f"TASK FILES ANALYSIS - {task_id}")
    print("="*60)
    
    batch_account = config["azure"]["batch"]["account_name"]
    batch_url = config["azure"]["batch"]["account_url"]
    
    # List task files
    cmd = f'az batch task file list --job-id {job_id} --task-id {task_id} --account-name {batch_account} --account-endpoint {batch_url} --output json'
    code, stdout, stderr = run_command(cmd, f"Listing files for task {task_id}")
    
    if code == 0:
        try:
            files = json.loads(stdout)
            print(f"📁 Found {len(files)} file(s):")
            
            for file_info in files:
                name = file_info.get('name', 'Unknown')
                size = file_info.get('properties', {}).get('contentLength', 0)
                print(f"   {name} ({size} bytes)")
                
                # Download key files for analysis
                if name in ['stdout.txt', 'stderr.txt']:
                    output_dir = Path("logs")
                    output_dir.mkdir(exist_ok=True)
                    
                    output_file = output_dir / f"{job_id}_{task_id}_{name}"
                    
                    download_cmd = f'az batch task file download --job-id {job_id} --task-id {task_id} --file-path {name} --destination {output_file} --account-name {batch_account} --account-endpoint {batch_url}'
                    
                    dl_code, dl_stdout, dl_stderr = run_command(download_cmd, f"Downloading {name}")
                    
                    if dl_code == 0:
                        print(f"     ✅ Downloaded to {output_file}")
                        
                        # Show content if small enough
                        if output_file.exists() and output_file.stat().st_size < 2000:
                            content = output_file.read_text(encoding='utf-8', errors='ignore')
                            if content.strip():
                                print(f"     Content:")
                                for line in content.split('\n')[:10]:  # Show first 10 lines
                                    print(f"       {line}")
                                if len(content.split('\n')) > 10:
                                    print(f"       ... (truncated)")
                    else:
                        print(f"     ❌ Failed to download: {dl_stderr}")
        
        except json.JSONDecodeError:
            print(f"❌ Failed to parse files data")
    else:
        print(f"❌ Failed to list files: {stderr}")


def check_pool_status(config: dict):
    """Check pool status."""
    print("\n" + "="*60)
    print("POOL STATUS ANALYSIS")
    print("="*60)
    
    batch_account = config["azure"]["batch"]["account_name"]
    batch_url = config["azure"]["batch"]["account_url"]
    pool_id = config["azure"]["batch"]["pool_id"]
    
    # Check pool status
    cmd = f'az batch pool show --pool-id {pool_id} --account-name {batch_account} --account-endpoint {batch_url} --output json'
    code, stdout, stderr = run_command(cmd, f"Checking pool {pool_id}")
    
    if code == 0:
        try:
            pool_data = json.loads(stdout)
            print(f"✅ Pool Status: {pool_data.get('state', 'Unknown')}")
            print(f"   VM Size: {pool_data.get('vmSize', 'Unknown')}")
            print(f"   Dedicated Nodes: {pool_data.get('currentDedicatedNodes', 0)}")
            print(f"   Low Priority Nodes: {pool_data.get('currentLowPriorityNodes', 0)}")
            
            # Check autoscale
            if 'autoScaleFormula' in pool_data:
                print(f"   Autoscale: Enabled")
            else:
                print(f"   Target Dedicated: {pool_data.get('targetDedicatedNodes', 0)}")
                print(f"   Target Low Priority: {pool_data.get('targetLowPriorityNodes', 0)}")
            
            # Check container configuration
            if 'deploymentConfiguration' in pool_data:
                vm_config = pool_data['deploymentConfiguration'].get('virtualMachineConfiguration', {})
                if 'containerConfiguration' in vm_config:
                    container_config = vm_config['containerConfiguration']
                    print(f"   Container Type: {container_config.get('type', 'Unknown')}")
                    
                    images = container_config.get('containerImageNames', [])
                    print(f"   Container Images: {len(images)}")
                    for img in images:
                        print(f"     - {img}")
            
        except json.JSONDecodeError:
            print(f"❌ Failed to parse pool data")
    else:
        print(f"❌ Pool not found or error: {stderr}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Troubleshoot Azure Batch jobs")
    
    parser.add_argument("--job-id", type=str, help="Job ID to analyze")
    parser.add_argument("--task-id", type=str, help="Specific task ID to analyze")
    parser.add_argument("--config", type=str, default="../config/config.json", help="Config file path")
    parser.add_argument("--check-pool", action="store_true", help="Check pool status")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    if not config:
        sys.exit(1)
    
    print("🔧 Azure Batch Troubleshooting Tool")
    print("="*60)
    print(f"Batch Account: {config['azure']['batch']['account_name']}")
    print(f"Pool ID: {config['azure']['batch']['pool_id']}")
    
    if args.check_pool:
        check_pool_status(config)
    
    if args.job_id:
        check_job_status(args.job_id, config)
        
        if args.task_id:
            check_task_files(args.job_id, args.task_id, config)
        else:
            # Try to analyze first task
            check_task_files(args.job_id, "task-0", config)
    
    if not args.job_id and not args.check_pool:
        print("\n💡 Usage examples:")
        print("  Check pool status:")
        print("    python scripts/troubleshoot.py --check-pool")
        print("  Analyze specific job:")
        print("    python scripts/troubleshoot.py --job-id json-processing-20251017-231345")
        print("  Analyze specific task:")
        print("    python scripts/troubleshoot.py --job-id json-processing-20251017-231345 --task-id task-0")


if __name__ == "__main__":
    main()