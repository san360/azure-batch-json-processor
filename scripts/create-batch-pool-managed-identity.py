#!/usr/bin/env python3
"""
Azure Batch Pool Creation with Managed Identity
This script creates an Azure Batch pool with user-assigned managed identity support
for secure storage access without using storage keys.

Uses Azure CLI REST API for reliable pool creation with autoscaling.
"""

import os
import sys
import json
import time
import subprocess
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """Load configuration from config.json file."""
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "..", "config", "config.json")
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Configuration file not found: {config_path}")
        print("Please create config/config.json from config/config.sample.json")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in configuration file: {e}")
        sys.exit(1)

def create_batch_pool_with_managed_identity():
    """Create Azure Batch pool with user-assigned managed identity using Azure CLI."""
    
    print("🚀 Azure Batch Pool Creation with Managed Identity")
    print("=" * 55)
    
    # Load configuration
    config = load_config()
    azure_config = config['azure']
    
    subscription_id = azure_config['subscription_id']
    resource_group_name = azure_config['resource_group']
    batch_account_name = azure_config['batch']['account_name']
    pool_id = azure_config['batch']['pool_id']
    managed_identity_id = azure_config['batch']['managed_identity_id']
    
    # Container configuration
    acr_config = azure_config['acr']
    container_image = f"{acr_config['login_server']}/{acr_config['image_name']}:{acr_config['image_tag']}"
    
    print(f"📋 Configuration:")
    print(f"   Subscription: {subscription_id}")
    print(f"   Resource Group: {resource_group_name}")
    print(f"   Batch Account: {batch_account_name}")
    print(f"   Pool ID: {pool_id}")
    print(f"   Container Image: {container_image}")
    print(f"   Managed Identity: {managed_identity_id}")
    print()
    
    return create_pool_with_azure_cli(config)

def create_pool_with_azure_cli(config: Dict[str, Any]) -> bool:
    """Create Azure Batch pool using Azure CLI REST API calls."""
    
    azure_config = config['azure']
    subscription_id = azure_config['subscription_id']
    resource_group_name = azure_config['resource_group']
    batch_account_name = azure_config['batch']['account_name']
    pool_id = azure_config['batch']['pool_id']
    managed_identity_id = azure_config['batch']['managed_identity_id']
    
    # Container configuration
    acr_config = azure_config['acr']
    container_image = f"{acr_config['login_server']}/{acr_config['image_name']}:{acr_config['image_tag']}"
    
    print("🔧 Creating pool using Azure CLI REST API...")
    
    # Define autoscale formula for optimal scaling
    autoscale_formula = (
        "// In this example, the pool size is adjusted based on the number of tasks in the queue.\n"
        "// Note that both comments and line breaks are acceptable in formula strings.\n"
        "\n"
        "// Get pending tasks for the past 15 minutes.\n"
        "$samples = $ActiveTasks.GetSamplePercent(TimeInterval_Minute * 15);\n"
        "// If we have fewer than 70 percent data points, we use the last sample point, otherwise we use the maximum of last sample point and the history average.\n"
        "$tasks = $samples < 70 ? max(0, $ActiveTasks.GetSample(1)) : \n"
        "max( $ActiveTasks.GetSample(1), avg($ActiveTasks.GetSample(TimeInterval_Minute * 15)));\n"
        "// If number of pending tasks is not 0, set targetVM to pending tasks, otherwise half of current dedicated.\n"
        "$targetVMs = $tasks > 0 ? $tasks : max(0, $TargetDedicatedNodes / 2);\n"
        "// The pool size is capped at 5, if target VM value is more than that, set it to5. This value should be adjusted according to your use case.\n"
        "cappedPoolSize = 5;\n"
        "$TargetDedicatedNodes = max(0, min($targetVMs, cappedPoolSize));\n"
        "// Set node deallocation mode - keep nodes active only until tasks finish\n"
        "$NodeDeallocationOption = taskcompletion;"
    )
    
    # Create pool JSON configuration
    pool_config = {
        "name": pool_id,
        "type": "Microsoft.Batch/batchAccounts/pools",
        "properties": {
            "displayName": "JSON Processor Pool with Managed Identity",
            "vmSize": "Standard_D2s_v3",
            "deploymentConfiguration": {
                "virtualMachineConfiguration": {
                    "imageReference": {
                        "publisher": "microsoft-dsvm",
                        "offer": "ubuntu-hpc", 
                        "sku": "2204",
                        "version": "latest"
                    },
                    "nodeAgentSkuId": "batch.node.ubuntu 22.04",
                    "containerConfiguration": {
                        "type": "dockerCompatible",
                        "containerImageNames": [container_image],
                        "containerRegistries": [
                            {
                                "registryServer": acr_config['login_server'],
                                "identityReference": {
                                    "resourceId": managed_identity_id
                                }
                            }
                        ]
                    }
                }
            },
            "scaleSettings": {
                "autoScale": {
                    "formula": autoscale_formula,
                    "evaluationInterval": "PT5M"
                }
            }
        },
        "identity": {
            "type": "UserAssigned",
            "userAssignedIdentities": {
                managed_identity_id: {}
            }
        }
    }
    
    # Save pool configuration to temporary file for debugging
    pool_config_file = "pool_config_debug.json"
    try:
        with open(pool_config_file, 'w') as f:
            json.dump(pool_config, f, indent=2)
        
        print(f"📄 Pool configuration saved to {pool_config_file} for review")
        print()
        
        # Check if pool exists and delete if necessary
        print(f"🔍 Checking if pool '{pool_id}' exists...")
        check_cmd = [
            "az", "rest",
            "--method", "GET",
            "--url", f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Batch/batchAccounts/{batch_account_name}/pools/{pool_id}?api-version=2024-07-01"
        ]
        result = subprocess.run(check_cmd, capture_output=True, text=True, shell=True, check=False)
        
        if result.returncode == 0:
            print(f"⚠️  Pool '{pool_id}' already exists. Deleting first...")
            delete_cmd = [
                "az", "rest",
                "--method", "DELETE",
                "--url", f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Batch/batchAccounts/{batch_account_name}/pools/{pool_id}?api-version=2024-07-01"
            ]
            subprocess.run(delete_cmd, capture_output=True, text=True, shell=True, check=True)
            print("⏳ Waiting for pool deletion...")
            time.sleep(30)  # Wait for deletion to complete
            print(f"✅ Pool '{pool_id}' deleted successfully")
        else:
            print(f"✅ Pool '{pool_id}' does not exist, proceeding with creation")
        
        # Create the pool using Azure REST API
        print(f"🏗️  Creating pool '{pool_id}' with managed identity...")
        print("   VM Size: Standard_A2_v2")
        print("   Scaling: Autoscale (0-5 nodes)")
        print("   Formula: ActiveTasks-based with 15min history")
        print("   Evaluation Interval: 5 minutes")
        print("   Identity Type: User-assigned managed identity")
        print("   Container Support: Enabled")
        print()
        
        create_cmd = [
            "az", "rest",
            "--method", "PUT",
            "--url", f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Batch/batchAccounts/{batch_account_name}/pools/{pool_id}?api-version=2024-07-01",
            "--body", f"@{pool_config_file}"
        ]
        
        result = subprocess.run(create_cmd, capture_output=True, text=True, shell=True, check=False)
        
        if result.returncode == 0:
            print("✅ Pool created successfully!")
            print()
            print("📊 Pool Details:")
            print(f"   Pool ID: {pool_id}")
            print(f"   VM Size: Standard_A2_v2")
            print(f"   Scaling: Autoscale enabled")
            print(f"   Max Nodes: 5")
            print(f"   Formula: ActiveTasks with 15min sampling")
            print("   Identity: User-assigned managed identity configured")
            print()
            print("🎉 Success! Pool is ready for job submission.")
            print()
            print("Next Steps:")
            print(f"  1. Submit batch job: python scripts/submit-batch-job.py --pool-id {pool_id}")
            print(f"  2. Monitor job: az batch job list --account-name {batch_account_name}")
            print("  3. Download results: python scripts/download-results.py --output ./results/")
            
            return True
        else:
            print(f"❌ Failed to create pool:")
            print(f"   Return code: {result.returncode}")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Keep the file for debugging
        print(f"📄 Pool configuration file kept at: {pool_config_file}")
        pass

if __name__ == "__main__":
    success = create_batch_pool_with_managed_identity()
    sys.exit(0 if success else 1)