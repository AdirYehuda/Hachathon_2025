import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  CardActions,
  Button,
  CircularProgress,
  Alert,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField
} from '@mui/material';
import {
  Launch as LaunchIcon,
  Code as CodeIcon,
  Refresh as RefreshIcon,
  Dashboard as DashboardIcon
} from '@mui/icons-material';

import { apiService } from '../services/apiService';

const DashboardsPage = () => {
  const [dashboards, setDashboards] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [embedDialog, setEmbedDialog] = useState({ open: false, siteId: '', embedCode: '' });

  useEffect(() => {
    loadDashboards();
  }, []);

  const loadDashboards = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await apiService.listDashboards();
      setDashboards(response.data.dashboards || []);
    } catch (err) {
      setError('Failed to load dashboards: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleGetEmbedCode = async (siteId) => {
    try {
      const response = await apiService.getEmbedCode(siteId);
      setEmbedDialog({
        open: true,
        siteId: siteId,
        embedCode: response.data.embed_code
      });
    } catch (err) {
      setError('Failed to get embed code: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleCopyEmbedCode = async () => {
    try {
      await navigator.clipboard.writeText(embedDialog.embedCode);
      // You could add a success message here
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  };

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant="h4" gutterBottom>
              Deployed Dashboards
            </Typography>
            <Typography variant="body1" color="text.secondary">
              View and manage your generated cost optimization dashboards
            </Typography>
          </Box>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={loadDashboards}
            disabled={loading}
          >
            Refresh
          </Button>
        </Box>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : dashboards.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <DashboardIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            No Dashboards Found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Execute a workflow to generate your first dashboard
          </Typography>
        </Paper>
      ) : (
        <Grid container spacing={3}>
          {dashboards.map((dashboard, index) => (
            <Grid item xs={12} md={6} lg={4} key={dashboard.site_id || index}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    {dashboard.site_id || `Dashboard ${index + 1}`}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" paragraph>
                    Static dashboard hosted on S3
                  </Typography>
                  <Chip
                    label={dashboard.created || 'Unknown date'}
                    size="small"
                    variant="outlined"
                  />
                </CardContent>
                <CardActions>
                  <Button
                    size="small"
                    startIcon={<LaunchIcon />}
                    href={dashboard.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View
                  </Button>
                  <Button
                    size="small"
                    startIcon={<CodeIcon />}
                    onClick={() => handleGetEmbedCode(dashboard.site_id)}
                  >
                    Embed
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Embed Code Dialog */}
      <Dialog
        open={embedDialog.open}
        onClose={() => setEmbedDialog({ ...embedDialog, open: false })}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Embed Code for {embedDialog.siteId}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" paragraph>
            Copy this HTML code to embed the dashboard in your website:
          </Typography>
          <TextField
            fullWidth
            multiline
            rows={4}
            value={embedDialog.embedCode}
            variant="outlined"
            InputProps={{
              readOnly: true,
              sx: { fontFamily: 'monospace', fontSize: '0.875rem' }
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEmbedDialog({ ...embedDialog, open: false })}>
            Close
          </Button>
          <Button variant="contained" onClick={handleCopyEmbedCode}>
            Copy Code
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default DashboardsPage; 