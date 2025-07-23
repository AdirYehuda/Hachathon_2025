#!/usr/bin/env python3
"""
Test script for Bedrock agent connectivity and timeout diagnostics.
Run this script to verify your Bedrock configuration and identify timeout issues.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime

# Add the backend source to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from src.core.config import settings
from src.services.bedrock_service import BedrockService


async def test_bedrock_connectivity():
    """Test Bedrock agent connectivity with various timeout scenarios."""
    
    print("🔍 Bedrock Agent Connectivity Test")
    print("=" * 50)
    
    # Display current configuration
    print(f"📋 Current Configuration:")
    print(f"   Region: {settings.bedrock_region}")
    print(f"   Agent ID: {settings.bedrock_agent_id}")
    print(f"   Agent Alias: {settings.bedrock_agent_alias_id}")
    print(f"   Timeout: {settings.bedrock_timeout}s")
    print(f"   Max Retries: {settings.bedrock_max_retries}")
    print(f"   Connect Timeout: {settings.bedrock_connect_timeout}s")
    print()
    
    # Validate configuration
    if not settings.bedrock_agent_id:
        print("❌ ERROR: BEDROCK_AGENT_ID is not configured")
        print("   Please set BEDROCK_AGENT_ID in your .env file")
        return False
    
    if not settings.bedrock_agent_alias_id:
        print("❌ ERROR: BEDROCK_AGENT_ALIAS_ID is not configured")
        print("   Please set BEDROCK_AGENT_ALIAS_ID in your .env file")
        return False
    
    # Initialize Bedrock service
    print("🚀 Initializing Bedrock service...")
    try:
        bedrock = BedrockService(
            region=settings.bedrock_region,
            timeout=settings.bedrock_timeout,
            max_retries=settings.bedrock_max_retries,
            connect_timeout=settings.bedrock_connect_timeout
        )
        print("✅ Bedrock service initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Bedrock service: {e}")
        return False
    
    # Test 1: Simple connectivity test
    print("\n🧪 Test 1: Simple Agent Invocation")
    try:
        start_time = time.time()
        
        session_id = f"test-{int(time.time())}"
        simple_query = "Hello, can you confirm you're working correctly? Please respond with a simple acknowledgment."
        
        print(f"   Invoking agent with simple query...")
        result = await bedrock.invoke_agent(
            agent_id=settings.bedrock_agent_id,
            agent_alias_id=settings.bedrock_agent_alias_id,
            session_id=session_id,
            input_text=simple_query
        )
        
        duration = time.time() - start_time
        print(f"✅ Simple invocation successful in {duration:.2f}s")
        print(f"   Response length: {len(result['response'])} characters")
        
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Simple invocation failed after {duration:.2f}s")
        print(f"   Error: {e}")
        return False
    
    # Test 2: Complex data processing test
    print("\n🧪 Test 2: Complex Data Processing")
    try:
        start_time = time.time()
        
        # Create sample data objects similar to what the workflow would send
        sample_data = [
            {
                "query": "EC2 underutilization analysis",
                "response": "Found 5 underutilized EC2 instances with average CPU usage below 10%",
                "query_type": "ec2_analysis",
                "timestamp": datetime.now().isoformat()
            },
            {
                "query": "S3 bucket analysis", 
                "response": "Identified 3 empty S3 buckets and 7 buckets with minimal access patterns",
                "query_type": "s3_analysis",
                "timestamp": datetime.now().isoformat()
            }
        ]
        
        print(f"   Processing {len(sample_data)} data objects...")
        result = await bedrock.process_data_objects(
            data_objects=sample_data,
            agent_id=settings.bedrock_agent_id,
            agent_alias_id=settings.bedrock_agent_alias_id
        )
        
        duration = time.time() - start_time
        print(f"✅ Complex processing successful in {duration:.2f}s")
        print(f"   Response length: {len(result['response'])} characters")
        
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Complex processing failed after {duration:.2f}s")
        print(f"   Error: {e}")
        print(f"   💡 This might indicate timeout issues with larger datasets")
        return False
    
    # Test 3: Large data processing test
    print("\n🧪 Test 3: Large Data Processing (Chunking Test)")
    try:
        start_time = time.time()
        
        # Create a larger dataset to test chunking
        large_data = []
        for i in range(20):  # Create 20 sample objects
            large_data.append({
                "query": f"Resource analysis {i+1}",
                "response": f"Analysis result {i+1}: " + "Sample data " * 50,  # Make responses longer
                "query_type": "comprehensive_analysis",
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "cost_savings": 1000 + i * 100,
                    "utilization": 15 + i * 2,
                    "resources_affected": 5 + i
                }
            })
        
        print(f"   Processing {len(large_data)} data objects (testing chunking)...")
        result = await bedrock.process_data_objects(
            data_objects=large_data,
            agent_id=settings.bedrock_agent_id,
            agent_alias_id=settings.bedrock_agent_alias_id
        )
        
        duration = time.time() - start_time
        print(f"✅ Large data processing successful in {duration:.2f}s")
        print(f"   Response length: {len(result['response'])} characters")
        
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Large data processing failed after {duration:.2f}s")
        print(f"   Error: {e}")
        print(f"   💡 Consider increasing BEDROCK_TIMEOUT or reducing data size")
        return False
    
    print("\n🎉 All tests passed! Bedrock connectivity is working correctly.")
    print("\n💡 Recommendations:")
    print("   - Current timeout settings appear to be adequate")
    print("   - If you experience timeouts in production, consider:")
    print("     * Increasing BEDROCK_TIMEOUT (currently {}s)".format(settings.bedrock_timeout))
    print("     * Reducing the amount of data sent in single requests")
    print("     * Using the chunking feature for large datasets")
    
    return True


def print_timeout_troubleshooting():
    """Print troubleshooting guide for timeout issues."""
    print("\n🔧 Timeout Troubleshooting Guide")
    print("=" * 50)
    print("If you're experiencing timeout issues, try these solutions:")
    print()
    print("1. 📈 INCREASE TIMEOUTS:")
    print("   Add these to your .env file:")
    print("   BEDROCK_TIMEOUT=900          # 15 minutes")
    print("   BEDROCK_CONNECT_TIMEOUT=120  # 2 minutes")
    print("   BEDROCK_MAX_RETRIES=5        # More retry attempts")
    print()
    print("2. 📊 REDUCE DATA SIZE:")
    print("   - Limit the number of Amazon Q queries in your workflow")
    print("   - Use more specific queries instead of broad ones")
    print("   - Process data in smaller batches")
    print()
    print("3. 🔄 CHECK NETWORK:")
    print("   - Ensure stable internet connection")
    print("   - Check if your AWS region is accessible")
    print("   - Verify firewall settings allow HTTPS to AWS endpoints")
    print()
    print("4. 🎯 OPTIMIZE AGENT:")
    print("   - Ensure your Bedrock agent is properly configured")
    print("   - Check agent resource allocation in AWS console")
    print("   - Consider using a different agent alias if available")
    print()


async def main():
    """Main test function."""
    try:
        success = await test_bedrock_connectivity()
        if not success:
            print_timeout_troubleshooting()
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error during testing: {e}")
        print_timeout_troubleshooting()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 