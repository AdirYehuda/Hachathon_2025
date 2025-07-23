# Bedrock Timeout Issue - Resolution Guide

## Problem Summary

You were experiencing timeout errors when running workflows:

```
ERROR:src.services.bedrock_service:Unexpected error in invoke_agent: AWSHTTPSConnectionPool(host='bedrock-agent-runtime.eu-west-1.amazonaws.com', port=443): Read timed out.
```

This occurred because the Bedrock service was using default boto3 timeouts which are too short for complex agent processing.

## Root Cause

1. **No timeout configuration**: The `BedrockService` class wasn't configuring any custom timeouts for boto3
2. **Default timeouts too short**: Default boto3 timeouts (typically 60 seconds) are insufficient for Bedrock agent processing
3. **Large data sets**: Sending large amounts of data to Bedrock agents can take several minutes to process
4. **No retry mechanism**: Failed requests weren't being retried with proper exponential backoff

## Applied Fixes

### 1. Enhanced Timeout Configuration

**File: `backend/src/core/config.py`**
- Increased default `bedrock_timeout` from 300s (5 min) to 600s (10 min)
- Added `bedrock_max_retries` configuration (default: 3)
- Added `bedrock_connect_timeout` configuration (default: 60s)

### 2. Improved boto3 Client Configuration

**File: `backend/src/services/bedrock_service.py`**
- Added proper `Config` object with timeout settings
- Implemented adaptive retry strategy
- Configured connection pooling for better performance
- Added specific `ReadTimeoutError` handling with user-friendly messages

### 3. Data Chunking for Large Datasets

**File: `backend/src/services/bedrock_service.py`**
- Implemented `_chunk_data_objects()` method to split large data into manageable chunks
- Automatic chunking when data exceeds 50KB
- Separate processing of chunks followed by consolidation
- Better logging for chunk processing progress

### 4. Enhanced Error Handling

- Specific timeout error handling with 504 status code
- Detailed error messages for different failure scenarios
- Better logging for debugging timeout issues

### 5. Updated Environment Configuration

**File: `env.template`**
- Added new timeout configuration options
- Updated default values with explanations
- Cleaner organization of configuration sections

## Configuration Options

Add these to your `.env` file to customize timeout behavior:

```bash
# Bedrock timeout settings
BEDROCK_TIMEOUT=600              # Total request timeout (10 minutes)
BEDROCK_MAX_RETRIES=3            # Number of retry attempts
BEDROCK_CONNECT_TIMEOUT=60       # Connection establishment timeout
BEDROCK_REGION=us-east-1         # Ensure correct region
```

## Testing Your Configuration

Run the diagnostic script to test your Bedrock connectivity:

```bash
cd scripts
python test_bedrock_connection.py
```

This script will:
- Validate your configuration
- Test simple agent invocation
- Test complex data processing
- Test large dataset handling with chunking
- Provide specific recommendations

## Troubleshooting Steps

### If you still experience timeouts:

1. **Increase timeouts further**:
   ```bash
   BEDROCK_TIMEOUT=900          # 15 minutes
   BEDROCK_CONNECT_TIMEOUT=120  # 2 minutes
   BEDROCK_MAX_RETRIES=5        # More attempts
   ```

2. **Reduce data size**:
   - Limit the number of Amazon Q queries in your workflow
   - Use more specific queries instead of broad ones
   - Process data in smaller batches

3. **Check network connectivity**:
   - Ensure stable internet connection
   - Verify AWS region accessibility
   - Check firewall settings for HTTPS to AWS endpoints

4. **Optimize your Bedrock agent**:
   - Check agent configuration in AWS console
   - Verify agent resource allocation
   - Consider using a different agent alias

### Monitoring

The enhanced logging will now show:
- Chunk processing progress for large datasets
- Timeout durations before failure
- Retry attempts and their outcomes
- Specific error types for better debugging

## Summary of Changes

| Component | Change | Benefit |
|-----------|--------|---------|
| **Timeouts** | Increased from 5min to 10min | Allows complex processing |
| **Retries** | Added adaptive retry strategy | Handles transient failures |
| **Chunking** | Automatic data splitting | Prevents oversized requests |
| **Error Handling** | Specific timeout error types | Better debugging |
| **Diagnostics** | Test script for validation | Easy troubleshooting |

## Next Steps

1. Update your `.env` file with the new timeout settings
2. Run the diagnostic script to validate your setup
3. Test your workflow with the improved configuration
4. Monitor logs for any remaining issues

The chunking feature should automatically handle large datasets, and the increased timeouts should resolve the connection issues you were experiencing. 