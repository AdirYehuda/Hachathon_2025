#!/usr/bin/env python3
"""
Test script to verify Amazon Q service fixes
Tests the corrected model name and improved parsing
"""

import asyncio
import os
import sys
import json

# Add backend src to path for imports
backend_src_path = os.path.join(os.path.dirname(__file__), 'backend', 'src')
sys.path.insert(0, backend_src_path)

# Import with modified settings
import tempfile

# Create a mock settings object
class MockSettings:
    amazon_q_cli_path = "q"
    amazon_q_cli_timeout = 300
    amazon_q_cli_max_retries = 3
    amazon_q_cli_working_dir = None

# Mock the settings import temporarily
import sys
sys.modules['src.core.config'] = type('MockModule', (), {'settings': MockSettings()})()

from services.amazon_q_service import AmazonQService

async def test_fixed_service():
    """Test the fixed Amazon Q service"""
    
    print("🔧 Testing Fixed Amazon Q Service")
    print("=" * 50)
    
    # Initialize service
    service = AmazonQService(
        aws_profile="rnd",
        region="us-east-1"
    )
    
    print(f"📡 CLI Path: {service.cli_path}")
    print(f"👤 AWS Profile: {service.aws_profile}")
    print(f"🌍 Region: {service.region}")
    print()
    
    # Test S3 analysis (which we know works from manual test)
    print("🧪 Testing S3 Underutilization Analysis")
    print("-" * 40)
    
    try:
        result = await service.analyze_s3_underutilization()
        
        print("✅ S3 Analysis Completed Successfully!")
        print(f"📊 Response Length: {len(result['response'])} characters")
        print(f"🔍 Raw Output Length: {len(result['raw_output'])} characters")
        print()
        
        print("📄 Parsed Response Preview:")
        print("-" * 30)
        preview = result['response'][:800] + "..." if len(result['response']) > 800 else result['response']
        print(preview)
        print()
        
        # Check if response contains AWS data indicators
        aws_indicators = ['bucket', 's3', 'aws', 'storage', 'size', 'object']
        found_indicators = [indicator for indicator in aws_indicators if indicator.lower() in result['response'].lower()]
        
        print(f"🎯 AWS Data Indicators Found: {found_indicators}")
        
        if found_indicators:
            print("✅ Response contains AWS data - this should work with Bedrock!")
        else:
            print("⚠️  Response might not contain enough AWS data")
            
        return result
        
    except Exception as e:
        print(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_cost_optimization():
    """Test cost optimization query"""
    print("\n💰 Testing Cost Optimization Query")
    print("-" * 40)
    
    service = AmazonQService(aws_profile="rnd", region="us-east-1")
    
    try:
        result = await service.query_cost_optimization("S3 analysis - Identify AWS resources incurring cost but showing near-zero utilization")
        
        print("✅ Cost Optimization Completed Successfully!")
        print(f"📊 Response Length: {len(result['response'])} characters")
        print()
        
        print("📄 Parsed Response Preview:")
        print("-" * 30)
        preview = result['response'][:800] + "..." if len(result['response']) > 800 else result['response']
        print(preview)
        
        return result
        
    except Exception as e:
        print(f"❌ Cost Optimization Test Failed: {e}")
        return None

def simulate_workflow_data(s3_result, cost_result):
    """Simulate the data structure that would be sent to Bedrock"""
    print("\n🔬 Simulating Workflow Data Structure")
    print("-" * 45)
    
    # This mimics what the workflow endpoint creates
    amazon_q_results = []
    
    if s3_result:
        amazon_q_results.append({
            "query": "S3 underutilization analysis",
            "response": s3_result["response"],
            "conversation_id": s3_result.get("conversation_id"),
            "source_attributions": s3_result.get("source_attributions", []),
            "timestamp": "2025-07-23T00:43:33.521Z",
            "query_type": "s3_analysis",
        })
    
    if cost_result:
        amazon_q_results.append({
            "query": "S3 analysis - Identify AWS resources incurring cost but showing near-zero utilization",
            "response": cost_result["response"],
            "conversation_id": cost_result.get("conversation_id"),
            "source_attributions": cost_result.get("source_attributions", []),
            "timestamp": "2025-07-23T00:43:33.521Z",
            "query_type": "cost_optimization",
        })
    
    print(f"📊 Generated {len(amazon_q_results)} data objects for Bedrock")
    
    # Check data quality
    total_chars = sum(len(result["response"]) for result in amazon_q_results)
    print(f"📝 Total response characters: {total_chars}")
    
    # Look for data quality indicators
    all_responses = " ".join(result["response"] for result in amazon_q_results)
    indicators = {
        "contains_bucket_names": "bucket" in all_responses.lower(),
        "contains_aws_commands": "aws " in all_responses.lower(),
        "contains_cost_data": any(term in all_responses.lower() for term in ["$", "cost", "saving", "usage"]),
        "contains_numbers": any(char.isdigit() for char in all_responses),
        "contains_resource_ids": any(term in all_responses.lower() for term in ["vol-", "i-", "arn:", "s3://"]),
    }
    
    print(f"🔍 Data Quality Indicators: {indicators}")
    
    if any(indicators.values()):
        print("✅ This data should work well with Bedrock instead of falling back to raw mode!")
    else:
        print("⚠️  Data might still trigger fallback mode")
    
    return amazon_q_results

async def main():
    """Main test function"""
    print("🚀 Testing Fixed Amazon Q Integration")
    print("=" * 60)
    
    # Test S3 analysis
    s3_result = await test_fixed_service()
    
    # Test cost optimization
    cost_result = await test_cost_optimization()
    
    # Simulate workflow data
    if s3_result or cost_result:
        workflow_data = simulate_workflow_data(s3_result, cost_result)
        
        print(f"\n🎯 Summary")
        print("=" * 20)
        print(f"S3 Analysis: {'✅ Success' if s3_result else '❌ Failed'}")
        print(f"Cost Analysis: {'✅ Success' if cost_result else '❌ Failed'}")
        print(f"Data Objects: {len(workflow_data) if 'workflow_data' in locals() else 0}")
        
        if workflow_data:
            print("\n✅ Ready to test full workflow!")
            print("The fixes should resolve the 'raw_data_fallback' issue.")
        else:
            print("\n❌ Issues detected - need further debugging")
    else:
        print("\n❌ Both tests failed - check Amazon Q CLI configuration")

if __name__ == "__main__":
    asyncio.run(main()) 