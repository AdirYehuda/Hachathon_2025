#!/usr/bin/env python3
"""
Test script for Amazon Q CLI integration
Tests the new --no-interactive flag and retry mechanism
"""

import asyncio
import os
import sys
import logging

# Add backend src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend', 'src'))

from services.amazon_q_service import AmazonQService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_amazon_q_cli():
    """Test Amazon Q CLI integration"""
    
    print("🔧 Testing Amazon Q CLI Integration")
    print("=" * 50)
    
    # Initialize service
    service = AmazonQService(
        aws_profile="rnd",  # Use your AWS profile
        region="us-east-1"
    )
    
    print(f"📡 CLI Path: {service.cli_path}")
    print(f"👤 AWS Profile: {service.aws_profile}")
    print(f"🌍 Region: {service.region}")
    print(f"⏰ Timeout: {service.timeout}s")
    print(f"🔄 Max Retries: {service.max_retries}")
    print()
    
    # Test cases
    test_cases = [
        {
            "name": "EBS Underutilization Analysis",
            "method": "analyze_ebs_underutilization",
            "description": "Test EBS volume analysis (similar to successful manual test)"
        },
        {
            "name": "EC2 Underutilization Analysis", 
            "method": "analyze_ec2_underutilization",
            "description": "Test EC2 instance analysis with 7-day timeframe"
        },
        {
            "name": "General Cost Optimization",
            "method": "query_cost_optimization", 
            "description": "Test general cost optimization query"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"🧪 Test {i}/{len(test_cases)}: {test_case['name']}")
        print(f"   {test_case['description']}")
        
        try:
            # Run the test
            if test_case['method'] == 'analyze_ebs_underutilization':
                result = await service.analyze_ebs_underutilization()
            elif test_case['method'] == 'analyze_ec2_underutilization':
                result = await service.analyze_ec2_underutilization("7d")
            elif test_case['method'] == 'query_cost_optimization':
                result = await service.query_cost_optimization("EC2 and EBS optimization")
            
            print("   ✅ SUCCESS")
            print(f"   📊 Response length: {len(result['response'])} characters")
            print(f"   🔍 Preview: {result['response'][:200]}..." if len(result['response']) > 200 else f"   📝 Full response: {result['response']}")
            print()
            
        except Exception as e:
            print(f"   ❌ FAILED: {str(e)}")
            print()
    
    print("🎯 Testing completed!")
    print("\n💡 Tips:")
    print("- If tests fail, ensure 'q' CLI is installed and working")
    print("- Check that AWS profile 'rnd' is configured")
    print("- Verify you have proper AWS permissions")
    print("- Try running 'q --help' manually to verify CLI availability")

async def test_cli_availability():
    """Test if Amazon Q CLI is available"""
    print("🔍 Checking Amazon Q CLI availability...")
    
    import subprocess
    try:
        result = subprocess.run(['q', '--help'], 
                              capture_output=True, 
                              text=True, 
                              timeout=10)
        if result.returncode == 0:
            print("✅ Amazon Q CLI is available")
            return True
        else:
            print("❌ Amazon Q CLI returned error code", result.returncode)
            return False
    except FileNotFoundError:
        print("❌ Amazon Q CLI not found - install with 'pip install amazon-q-developer-cli'")
        return False
    except subprocess.TimeoutError:
        print("❌ Amazon Q CLI check timed out")
        return False
    except Exception as e:
        print(f"❌ Error checking CLI: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Amazon Q CLI Integration Test")
    print("=" * 40)
    
    # First check CLI availability
    if asyncio.run(test_cli_availability()):
        print()
        asyncio.run(test_amazon_q_cli())
    else:
        print("\n⚠️  Cannot proceed with tests - Amazon Q CLI not available")
        sys.exit(1) 