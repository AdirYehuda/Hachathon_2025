import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Paper,
  Typography,
  Stepper,
  Step,
  StepLabel,
  Box,
  Button,
  CircularProgress,
  Alert,
  Divider,
  Grid,
  Card,
  CardContent,
  CardActions,
  Chip,
  TextField
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Launch as LaunchIcon
} from '@mui/icons-material';

import QueryForm from '../components/QueryForm';
import ResultsDisplay from '../components/ResultsDisplay';
import { apiService } from '../services/apiService';

const steps = [
  'Configure Queries',
  'Process with Amazon Q', 
  'Analyze with Bedrock',
  'Generate Dashboard'
];

const WorkflowPage = () => {
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [queries, setQueries] = useState([]);
  const [workflowResult, setWorkflowResult] = useState(null);
  const [executionTime, setExecutionTime] = useState(null);
  const [currentStepMessage, setCurrentStepMessage] = useState('');
  const [dashboardName, setDashboardName] = useState('costAnalysis');
  const [redirectCountdown, setRedirectCountdown] = useState(null);

  // Handle automatic redirection after workflow completion
  useEffect(() => {
    let timer;
    if (redirectCountdown > 0) {
      timer = setTimeout(() => {
        setRedirectCountdown(redirectCountdown - 1);
      }, 1000);
    } else if (redirectCountdown === 0) {
      navigate('/dashboards');
    }
    return () => clearTimeout(timer);
  }, [redirectCountdown, navigate]);

  const handleAddQuery = (query) => {
    setQueries([...queries, { ...query, id: Date.now() }]);
  };

  const handleRemoveQuery = (id) => {
    setQueries(queries.filter(q => q.id !== id));
  };

  const handleExecuteWorkflow = async () => {
    if (queries.length === 0) {
      setError('Please add at least one query before executing the workflow.');
      return;
    }

    if (!dashboardName.trim()) {
      setError('Please enter a dashboard name.');
      return;
    }

    setLoading(true);
    setError(null);
    setActiveStep(0);
    setCurrentStepMessage('Initializing workflow...');
    
    const startTime = Date.now();

    try {
      // Prepare queries for API - ensure they match CostOptimizationQuery schema
      const amazonQQueries = queries.map(query => ({
        query: query.query,
        time_range: query.timeRange || '30d',
        resource_types: query.resourceTypes || []
      }));

      // Execute workflow with progress tracking
      const response = await apiService.executeWorkflowWithProgress({
        amazon_q_queries: amazonQQueries,
        processing_type: 'analysis',
        dashboard_config: {
          type: 'cost_optimization',
          dashboard_name: dashboardName.trim()
        }
      }, (step, message) => {
        // Progress update callback
        setActiveStep(step);
        setCurrentStepMessage(message);
        console.log(`Step ${step}: ${message}`);
      });
      
      setWorkflowResult(response.data);

      setExecutionTime(((Date.now() - startTime) / 1000).toFixed(2));
      setActiveStep(4); // Completed
      setCurrentStepMessage('Workflow completed successfully! Redirecting to dashboards...');
      
      // Start 3-second countdown before redirecting to dashboards
      setRedirectCountdown(3);
      
    } catch (err) {
      console.error('Workflow execution failed:', err);
      console.error('Full error response:', err.response);
      
      // Better error message handling
      let errorMessage = 'Workflow execution failed. Please try again.';
      
      if (err.response?.data) {
        if (typeof err.response.data === 'string') {
          errorMessage = err.response.data;
        } else if (err.response.data.detail) {
          // Handle both string and object details
          if (typeof err.response.data.detail === 'string') {
            errorMessage = err.response.data.detail;
          } else {
            errorMessage = JSON.stringify(err.response.data.detail, null, 2);
          }
        } else if (err.response.data.message) {
          // Handle both string and object messages
          if (typeof err.response.data.message === 'string') {
            errorMessage = err.response.data.message;
          } else {
            errorMessage = JSON.stringify(err.response.data.message, null, 2);
          }
        } else {
          // Fallback to stringifying the entire data object
          errorMessage = JSON.stringify(err.response.data, null, 2);
        }
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(`Workflow Error: ${errorMessage}`);
      setActiveStep(0); // Reset to beginning
      setCurrentStepMessage('');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setActiveStep(0);
    setWorkflowResult(null);
    setError(null);
    setExecutionTime(null);
    setCurrentStepMessage('');
    setRedirectCountdown(null); // Reset countdown
  };

  const getStepIcon = (stepIndex) => {
    if (stepIndex < activeStep || (activeStep === 4 && stepIndex <= 3)) {
      return <CheckIcon color="success" />;
    }
    if (stepIndex === activeStep && loading) {
      return <CircularProgress size={24} />;
    }
    if (error && stepIndex >= activeStep) {
      return <ErrorIcon color="error" />;
    }
    return null;
  };

  return (
    <Box>
      {/* Header */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          AWS Cost Optimization Workflow
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          Query Amazon Q for cost optimization insights, process results through Bedrock AI, 
          and generate interactive dashboards automatically.
        </Typography>
        
        {/* Progress Stepper */}
        <Stepper activeStep={activeStep} sx={{ mt: 3 }}>
          {steps.map((label, index) => (
            <Step key={label}>
              <StepLabel icon={getStepIcon(index)}>
                {label}
              </StepLabel>
            </Step>
          ))}
        </Stepper>
      </Paper>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Success Alert with Countdown */}
      {redirectCountdown !== null && (
        <Alert severity="success" sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                Workflow Completed Successfully!
              </Typography>
              <Typography variant="body2">
                Redirecting to dashboards in {redirectCountdown} second{redirectCountdown !== 1 ? 's' : ''}...
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button 
                variant="contained" 
                size="small" 
                onClick={() => navigate('/dashboards')}
              >
                View Dashboards Now
              </Button>
              <Button 
                variant="outlined" 
                size="small" 
                onClick={() => setRedirectCountdown(null)}
              >
                Cancel
              </Button>
            </Box>
          </Box>
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Left Column - Query Configuration */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Cost Optimization Queries
            </Typography>
            
            <QueryForm onAddQuery={handleAddQuery} disabled={loading} />
            
            <Divider sx={{ my: 2 }} />
            
            {/* Dashboard Name Field */}
            <Box sx={{ mb: 3 }}>
              <Typography variant="subtitle1" gutterBottom>
                Dashboard Name
              </Typography>
              <TextField
                fullWidth
                label="Dashboard Name"
                value={dashboardName}
                onChange={(e) => setDashboardName(e.target.value)}
                disabled={loading}
                placeholder="Enter a name for your dashboard"
                helperText="This name will be used to identify your dashboard"
                variant="outlined"
                size="small"
              />
            </Box>
            
            {/* Query List */}
            <Typography variant="subtitle1" gutterBottom>
              Configured Queries ({queries.length})
            </Typography>
            
            {queries.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                No queries configured. Add a query above to get started.
              </Typography>
            ) : (
              <Box sx={{ mt: 2 }}>
                {queries.map((query, index) => (
                  <Card key={query.id} variant="outlined" sx={{ mb: 2 }}>
                    <CardContent sx={{ pb: 1 }}>
                      <Typography variant="body2" sx={{ mb: 1 }}>
                        <strong>Query {index + 1}:</strong> {query.query}
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                        <Chip size="small" label={`Time: ${query.timeRange || '30d'}`} />
                        {query.resourceTypes?.length > 0 && (
                          <Chip size="small" label={`Resources: ${query.resourceTypes.join(', ')}`} />
                        )}
                      </Box>
                    </CardContent>
                    <CardActions sx={{ pt: 0 }}>
                      <Button 
                        size="small" 
                        color="error"
                        onClick={() => handleRemoveQuery(query.id)}
                        disabled={loading}
                      >
                        Remove
                      </Button>
                    </CardActions>
                  </Card>
                ))}
              </Box>
            )}
            
            {/* Execution Controls */}
            <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
              <Button
                variant="contained"
                startIcon={loading ? <CircularProgress size={20} /> : <PlayIcon />}
                onClick={handleExecuteWorkflow}
                disabled={loading || queries.length === 0}
                size="large"
              >
                {loading ? 'Executing...' : 'Execute Workflow'}
              </Button>
              
              {workflowResult && (
                <Button
                  variant="outlined"
                  onClick={handleReset}
                  disabled={loading}
                >
                  Reset
                </Button>
              )}
            </Box>
          </Paper>
        </Grid>

        {/* Right Column - Results */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Workflow Results
            </Typography>
            
            {!workflowResult && !loading && (
              <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                Results will appear here after executing the workflow.
              </Typography>
            )}
            
            {loading && (
              <Box sx={{ textAlign: 'center', py: 4 }}>
                <CircularProgress size={40} />
                <Typography variant="body2" sx={{ mt: 2 }}>
                  {currentStepMessage || 'Processing...'}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  Step {activeStep} of 4: {steps[activeStep] || 'Initializing'}
                </Typography>
              </Box>
            )}
            
            {workflowResult && (
              <ResultsDisplay 
                result={workflowResult} 
                executionTime={executionTime}
              />
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default WorkflowPage; 