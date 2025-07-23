import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  TextField,
  Button,
  Alert,
  Divider,
  Card,
  CardContent,
  CardActions,
  Chip,
  CircularProgress
} from '@mui/material';
import {
  Save as SaveIcon,
  Check as CheckIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';

import { apiService } from '../services/apiService';

const SettingsPage = () => {
  const [apiUrl, setApiUrl] = useState(localStorage.getItem('api_url') || 'http://localhost:8000');
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    checkHealth();
  }, []);

  const checkHealth = async () => {
    setLoading(true);
    try {
      const healthData = await apiService.checkHealth();
      setHealth(healthData);
    } catch (err) {
      setHealth({ status: 'error', error: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = () => {
    localStorage.setItem('api_url', apiUrl);
    setSuccess(true);
    setTimeout(() => setSuccess(false), 3000);
    // In a real app, you might want to update the API base URL dynamically
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'success';
      case 'degraded': return 'warning';
      case 'partial': return 'warning';
      default: return 'error';
    }
  };

  const getServiceStatus = (serviceStatus) => {
    switch (serviceStatus) {
      case 'available': return { color: 'success', icon: <CheckIcon /> };
      case 'not_configured': return { color: 'warning', icon: <ErrorIcon /> };
      default: return { color: 'error', icon: <ErrorIcon /> };
    }
  };

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          Settings
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Configure API connection and view system status
        </Typography>
      </Paper>

      {success && (
        <Alert severity="success" sx={{ mb: 3 }}>
          Settings saved successfully!
        </Alert>
      )}

      {/* API Configuration */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          API Configuration
        </Typography>
        
        <TextField
          fullWidth
          label="API Base URL"
          value={apiUrl}
          onChange={(e) => setApiUrl(e.target.value)}
          sx={{ mb: 2 }}
          helperText="Base URL for the Amazon Q Wrapper API"
        />
        
        <Button
          variant="contained"
          startIcon={<SaveIcon />}
          onClick={handleSave}
        >
          Save Settings
        </Button>
      </Paper>

      {/* Health Check */}
      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">
            System Health
          </Typography>
          <Button
            variant="outlined"
            startIcon={loading ? <CircularProgress size={20} /> : <RefreshIcon />}
            onClick={checkHealth}
            disabled={loading}
          >
            Check Health
          </Button>
        </Box>

        {health ? (
          <Box>
            <Box sx={{ mb: 3 }}>
              <Chip
                label={`Status: ${health.status}`}
                color={getStatusColor(health.status)}
                sx={{ mr: 2 }}
              />
              {health.version && (
                <Chip
                  label={`Version: ${health.version}`}
                  variant="outlined"
                />
              )}
            </Box>

            {health.services && (
              <Box>
                <Typography variant="subtitle1" gutterBottom>
                  Service Status
                </Typography>
                <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))' }}>
                  {Object.entries(health.services).map(([service, status]) => {
                    const serviceInfo = getServiceStatus(status);
                    return (
                      <Card key={service} variant="outlined">
                        <CardContent sx={{ pb: 1 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {serviceInfo.icon}
                            <Typography variant="subtitle2">
                              {service.toUpperCase()}
                            </Typography>
                          </Box>
                          <Chip
                            label={status}
                            color={serviceInfo.color}
                            size="small"
                            sx={{ mt: 1 }}
                          />
                        </CardContent>
                      </Card>
                    );
                  })}
                </Box>
              </Box>
            )}

            {health.timestamp && (
              <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
                Last checked: {new Date(health.timestamp).toLocaleString()}
              </Typography>
            )}
          </Box>
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
            Click "Check Health" to verify system status
          </Typography>
        )}

        {health?.status === 'error' && (
          <Alert severity="error" sx={{ mt: 2 }}>
            Unable to connect to API: {health.error}
          </Alert>
        )}
      </Paper>
    </Box>
  );
};

export default SettingsPage; 