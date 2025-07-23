import axios from 'axios';

// Base API configuration
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 minutes for long-running operations
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    console.log(`API Response: ${response.status} ${response.config.url}`);
    return response;
  },
  (error) => {
    console.error('API Response Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export const apiService = {
  // Health check
  async checkHealth() {
    const response = await api.get('/health');
    return response.data;
  },

  // Amazon Q endpoints
  async queryCostOptimization(queryData) {
    const response = await api.post('/api/v1/amazon-q/cost-optimization', queryData);
    return response.data;
  },

  async queryUnderutilization(queryData) {
    const response = await api.post('/api/v1/amazon-q/underutilization', queryData);
    return response.data;
  },

  async chatWithAmazonQ(message, conversationId = null) {
    const response = await api.post('/api/v1/amazon-q/chat', {
      message,
      conversation_id: conversationId
    });
    return response.data;
  },

  // Bedrock endpoints
  async processDataObjects(processData) {
    const response = await api.post('/api/v1/bedrock/process', processData);
    return response.data;
  },

  async createDashboardSummary(processedData, agentId = null, agentAliasId = null) {
    // Debug: Log what we're about to send
    console.log('DEBUG - createDashboardSummary called with:', {
      processedData: typeof processedData === 'string' ? processedData.substring(0, 200) + '...' : processedData,
      processedDataType: typeof processedData,
      processedDataLength: typeof processedData === 'string' ? processedData.length : 'N/A',
      agentId,
      agentAliasId
    });

    const payload = {
      processed_data: processedData,
      agent_id: agentId,
      agent_alias_id: agentAliasId
    };

    console.log('DEBUG - Final payload being sent:', {
      processed_data: typeof payload.processed_data === 'string' ? payload.processed_data.substring(0, 100) + '...' : payload.processed_data,
      agent_id: payload.agent_id,
      agent_alias_id: payload.agent_alias_id
    });

    const response = await api.post('/api/v1/bedrock/create-dashboard-summary', payload);
    return response.data;
  },

  async bulkProcessData(bulkData) {
    const response = await api.post('/api/v1/bedrock/bulk-process', bulkData);
    return response.data;
  },

  // Dashboard endpoints
  async generateDashboard(dashboardData) {
    const response = await api.post('/api/v1/dashboard/generate', dashboardData);
    return response.data;
  },

  async executeCompleteWorkflow(workflowData) {
    const response = await api.post('/api/v1/dashboard/workflow/complete', workflowData);
    return response.data;
  },

  async listDashboards() {
    const response = await api.get('/api/v1/dashboard/list');
    return response.data;
  },

  async getEmbedCode(siteId, width = '100%', height = '600px') {
    const response = await api.get(`/api/v1/dashboard/${siteId}/embed-code`, {
      params: { width, height }
    });
    return response.data;
  },

  // Utility methods
  async uploadFile(file, endpoint) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post(endpoint, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Example workflow methods
  async runBasicWorkflow(queries) {
    try {
      // Step 1: Process Amazon Q queries
      const amazonQResults = [];
      for (const query of queries) {
        const result = await this.queryCostOptimization(query);
        amazonQResults.push(result.data);
      }

      // Step 2: Process through Bedrock
      const bedrockResult = await this.processDataObjects({
        data_objects: amazonQResults,
        processing_type: 'analysis'
      });

      // Step 3: Create dashboard summary
      const dashboardSummary = await this.createDashboardSummary(
        bedrockResult.data.processed_data
      );

      // Step 4: Generate dashboard
      const dashboard = await this.generateDashboard({
        summary_data: dashboardSummary.data.processed_data,
        dashboard_type: 'cost_optimization'
      });

      return {
        amazon_q_results: amazonQResults,
        bedrock_processing: bedrockResult.data,
        dashboard_summary: dashboardSummary.data,
        dashboard: dashboard.data
      };
    } catch (error) {
      console.error('Workflow execution failed:', error);
      throw error;
    }
  },

  // Step-by-step workflow execution with progress tracking
  async executeWorkflowWithProgress(workflowData, onProgressUpdate) {
    try {
      const workflowId = `workflow-${Date.now()}`;
      let results = {
        workflow_id: workflowId,
        amazon_q_results: [],
        bedrock_processing: null,
        dashboard: null
      };

      // Step 1: Execute Amazon Q queries
      if (onProgressUpdate) onProgressUpdate(1, 'Querying Amazon Q...');
      
      for (let i = 0; i < workflowData.amazon_q_queries.length; i++) {
        const query = workflowData.amazon_q_queries[i];
        if (onProgressUpdate) onProgressUpdate(1, `Processing query ${i + 1}/${workflowData.amazon_q_queries.length}...`);
        
        // Determine query type and call appropriate endpoint
        if (query.resource_types && query.resource_types.length > 0) {
          // Handle specific resource type queries
          for (const resourceType of query.resource_types) {
            let result;
            switch (resourceType.toUpperCase()) {
              case 'EC2':
                // For now, use cost optimization endpoint with resource-specific query
                result = await this.queryCostOptimization({
                  query: `EC2 underutilization analysis - ${query.query}`,
                  time_range: query.time_range
                });
                break;
              case 'EBS':
                result = await this.queryCostOptimization({
                  query: `EBS underutilization analysis - ${query.query}`,
                  time_range: query.time_range
                });
                break;
              case 'S3':
                result = await this.queryCostOptimization({
                  query: `S3 underutilization analysis - ${query.query}`,
                  time_range: query.time_range
                });
                break;
              case 'LAMBDA':
                result = await this.queryCostOptimization({
                  query: `Lambda underutilization analysis - ${query.query}`,
                  time_range: query.time_range
                });
                break;
              case 'RDS':
                result = await this.queryCostOptimization({
                  query: `RDS underutilization analysis - ${query.query}`,
                  time_range: query.time_range
                });
                break;
              default:
                result = await this.queryCostOptimization({
                  query: `${resourceType} cost optimization - ${query.query}`,
                  time_range: query.time_range
                });
            }
            
            results.amazon_q_results.push({
              query: `${resourceType} analysis - ${query.query}`,
              response: result.response,
              conversation_id: result.conversation_id,
              source_attributions: result.source_attributions || [],
              timestamp: new Date().toISOString(),
              query_type: `${resourceType.toLowerCase()}_analysis`,
              resource_type: resourceType.toUpperCase()
            });
          }
        } else {
          // General cost optimization query
          const result = await this.queryCostOptimization(query);
          results.amazon_q_results.push({
            query: query.query,
            response: result.response,
            conversation_id: result.conversation_id,
            source_attributions: result.source_attributions || [],
            timestamp: new Date().toISOString(),
            query_type: 'cost_optimization'
          });
        }
      }

      // Step 2: Process through Bedrock
      if (onProgressUpdate) onProgressUpdate(2, 'Processing with Bedrock AI...');
      
      const bedrockResult = await this.processDataObjects({
        data_objects: results.amazon_q_results,
        processing_type: workflowData.processing_type || 'analysis'
      });

      results.bedrock_processing = {
        processed_data: bedrockResult.data.processed_data,
        processing_type: workflowData.processing_type || 'analysis',
        session_id: bedrockResult.data.session_id,
        timestamp: new Date().toISOString(),
        metadata: { input_queries_count: results.amazon_q_results.length }
      };

      // Step 2.5: Create dashboard summary
      if (onProgressUpdate) onProgressUpdate(2, 'Creating dashboard summary...');
      
      const dashboardSummary = await this.createDashboardSummary(bedrockResult.data.processed_data);
      
      // Parse summary data
      let summaryData;
      try {
        summaryData = typeof dashboardSummary.data.processed_data === 'string' 
          ? JSON.parse(dashboardSummary.data.processed_data) 
          : dashboardSummary.data.processed_data;
      } catch (e) {
        summaryData = {
          executive_summary: dashboardSummary.data.processed_data,
          recommendations: [],
          key_metrics: {},
          cost_savings: {}
        };
      }

      // Step 3: Generate and deploy dashboard
      if (onProgressUpdate) onProgressUpdate(3, 'Generating dashboard...');
      
      const dashboardConfig = workflowData.dashboard_config || {};
      const dashboardResult = await this.generateDashboard({
        summary_data: summaryData,
        dashboard_type: dashboardConfig.type || 'cost_optimization',
        title: `Complete Analysis Dashboard - ${workflowId}`,
        embed_options: dashboardConfig.embed_options
      });

      results.dashboard = dashboardResult.data;
      results.total_execution_time = ((Date.now() - parseInt(workflowId.split('-')[1])) / 1000);
      results.timestamp = new Date().toISOString();
      results.status = 'completed';

      // Step 4: Complete
      if (onProgressUpdate) onProgressUpdate(4, 'Workflow completed successfully!');

      return { data: results };

    } catch (error) {
      console.error('Step-by-step workflow execution failed:', error);
      throw error;
    }
  }
};

export default apiService; 