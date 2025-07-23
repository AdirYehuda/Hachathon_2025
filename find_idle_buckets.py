#!/usr/bin/env python3
import subprocess
import json
import datetime
from dateutil.parser import parse
import sys

def run_aws_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error executing command: {command}")
        print(result.stderr)
        return None
    return result.stdout

def get_all_buckets():
    command = "aws s3api list-buckets"
    output = run_aws_command(command)
    if not output:
        return []
    
    buckets_data = json.loads(output)
    return [(bucket["Name"], bucket["CreationDate"]) for bucket in buckets_data.get("Buckets", [])]

def check_bucket_activity(bucket_name):
    # Check if bucket has objects
    command = f"aws s3api list-objects-v2 --bucket {bucket_name} --max-keys 1"
    output = run_aws_command(command)
    if not output:
        return None
    
    data = json.loads(output)
    if "Contents" not in data or len(data["Contents"]) == 0:
        return {"bucket": bucket_name, "status": "Empty", "last_modified": None}
    
    # Get the most recent object
    command = f"aws s3api list-objects-v2 --bucket {bucket_name} --query 'sort_by(Contents, &LastModified)[-1].LastModified'"
    output = run_aws_command(command)
    if not output:
        return None
    
    last_modified = output.strip().strip('"')
    
    # Check bucket metrics for recent activity
    current_date = datetime.datetime.now(datetime.timezone.utc)
    last_modified_date = parse(last_modified)
    days_since_modified = (current_date - last_modified_date).days
    
    status = "Active"
    if days_since_modified > 365:
        status = "Idle (>1 year)"
    elif days_since_modified > 180:
        status = "Potentially idle (>6 months)"
    elif days_since_modified > 90:
        status = "Low activity (>3 months)"
    
    return {
        "bucket": bucket_name,
        "status": status,
        "last_modified": last_modified,
        "days_since_modified": days_since_modified
    }

def main():
    print("Fetching all S3 buckets...")
    buckets = get_all_buckets()
    
    print(f"Found {len(buckets)} buckets. Analyzing activity...")
    
    results = []
    count = 0
    total = len(buckets)
    
    for bucket_name, creation_date in buckets:
        count += 1
        print(f"Checking bucket {count}/{total}: {bucket_name}")
        
        try:
            result = check_bucket_activity(bucket_name)
            if result:
                results.append(result)
        except Exception as e:
            print(f"Error checking bucket {bucket_name}: {str(e)}")
    
    # Sort results by days since modified (descending)
    results.sort(key=lambda x: x.get("days_since_modified", 0) if x.get("days_since_modified") else 0, reverse=True)
    
    # Print results
    print("\n=== Potentially Idle S3 Buckets ===")
    print("{:<40} {:<25} {:<30} {:<15}".format("Bucket Name", "Status", "Last Modified", "Days Since Modified"))
    print("-" * 110)
    
    for result in results:
        if result["status"] in ["Idle (>1 year)", "Potentially idle (>6 months)", "Low activity (>3 months)", "Empty"]:
            days = result.get("days_since_modified", "N/A")
            print("{:<40} {:<25} {:<30} {:<15}".format(
                result["bucket"], 
                result["status"], 
                result.get("last_modified", "N/A"), 
                days if days != "N/A" else "N/A"
            ))

if __name__ == "__main__":
    main()
