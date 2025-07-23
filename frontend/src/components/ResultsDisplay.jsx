import React, { useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Divider,
  Chip,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Collapse,
  List,
  ListItem,
  ListItemText,
  ListItemIcon
} from '@mui/material';
import {
  Launch as LaunchIcon,
  Code as CodeIcon,
  ContentCopy as CopyIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  CheckCircle as CheckIcon,
  Timer as TimerIcon,
  Dashboard as DashboardIcon,
  Analytics as AnalyticsIcon
} from '@mui/icons-material';

const ResultsDisplay = ({ result, executionTime }) => {
  const [embedDialogOpen, setEmbedDialogOpen] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);
  const [expandedSections, setExpandedSections] = useState({
    queries: false,
    processing: false,
    dashboard: true
  });

  // Error protection - return early if result is invalid
  if (!result || !result.dashboard) {
    return (
      <Alert severity="error" sx={{ mb: 3 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
          Invalid Workflow Result
        </Typography>
        <Typography variant="body2">
          The workflow result is incomplete or invalid. Please try executing the workflow again.
        </Typography>
      </Alert>
    );
  }

  const handleCopyEmbed = async () => {
    try {
      const embedCode = result?.dashboard?.embed_code;
      if (!embedCode) {
        console.error('No embed code available');
        return;
      }
      await navigator.clipboard.writeText(embedCode);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch (err) {
      console.error('Failed to copy embed code:', err);
    }
  };

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <Box>
      {/* Execution Summary */}
      <Alert severity="success" sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <CheckIcon />
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
              Workflow Completed Successfully
            </Typography>
            <Typography variant="body2">
              Execution time: {executionTime}s | Workflow ID: {result.workflow_id}
            </Typography>
          </Box>
        </Box>
      </Alert>

      {/* Dashboard Section */}
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <DashboardIcon color="primary" />
              <Typography variant="h6">Generated Dashboard</Typography>
            </Box>
            <IconButton
              onClick={() => toggleSection('dashboard')}
              size="small"
            >
              {expandedSections.dashboard ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          </Box>

          <Collapse in={expandedSections.dashboard}>
            <Box>
              <Typography variant="body2" color="text.secondary" paragraph>
                Interactive dashboard deployed to S3 static hosting
              </Typography>

              <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
                <Chip
                  icon={<TimerIcon />}
                  label={`Generated: ${formatTimestamp(result.dashboard?.timestamp || new Date().toISOString())}`}
                  size="small"
                />
                <Chip
                  label={`Type: ${result.dashboard?.dashboard_type || 'Unknown'}`}
                  size="small"
                  color="primary"
                />
              </Box>

              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <Button
                  variant="contained"
                  startIcon={<LaunchIcon />}
                  href={result.dashboard?.dashboard_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  disabled={!result.dashboard?.dashboard_url}
                >
                  View Dashboard
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<CodeIcon />}
                  onClick={() => setEmbedDialogOpen(true)}
                >
                  Get Embed Code
                </Button>
              </Box>
            </Box>
          </Collapse>
        </CardContent>
      </Card>

      {/* Amazon Q Results Section */}
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <AnalyticsIcon color="primary" />
              <Typography variant="h6">
                Amazon Q Results ({result.amazon_q_results.length})
              </Typography>
            </Box>
            <IconButton
              onClick={() => toggleSection('queries')}
              size="small"
            >
              {expandedSections.queries ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          </Box>

          <Collapse in={expandedSections.queries}>
            <List>
              {result.amazon_q_results.map((queryResult, index) => (
                <ListItem key={index} divider={index < result.amazon_q_results.length - 1}>
                  <ListItemIcon>
                    <Chip label={index + 1} color="primary" size="small" />
                  </ListItemIcon>
                  <ListItemText
                    primary={queryResult.query}
                    secondary={
                      <Box sx={{ mt: 1 }}>
                        <Typography variant="body2" paragraph>
                          {queryResult.response.substring(0, 200)}...
                        </Typography>
                        <Chip
                          label={queryResult.query_type}
                          size="small"
                          variant="outlined"
                        />
                      </Box>
                    }
                  />
                </ListItem>
              ))}
            </List>
          </Collapse>
        </CardContent>
      </Card>

      {/* Bedrock Processing Section */}
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6">Bedrock Analysis</Typography>
            <IconButton
              onClick={() => toggleSection('processing')}
              size="small"
            >
              {expandedSections.processing ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          </Box>

          <Collapse in={expandedSections.processing}>
            <Box>
              <Typography variant="body2" color="text.secondary" paragraph>
                Comprehensive analysis and summary generated by Bedrock AI
              </Typography>
              
              <Box sx={{ 
                backgroundColor: 'grey.50', 
                p: 2, 
                borderRadius: 1,
                maxHeight: 200,
                overflow: 'auto'
              }}>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                  {typeof result.bedrock_processing.processed_data === 'string' 
                    ? result.bedrock_processing.processed_data 
                    : JSON.stringify(result.bedrock_processing.processed_data, null, 2)
                  }
                </Typography>
              </Box>
            </Box>
          </Collapse>
        </CardContent>
      </Card>

      {/* Embed Code Dialog */}
      <Dialog 
        open={embedDialogOpen} 
        onClose={() => setEmbedDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Embed Dashboard</DialogTitle>
        <DialogContent>
          <Typography variant="body2" paragraph>
            Copy this HTML code to embed the dashboard in your website:
          </Typography>
          
          <TextField
            fullWidth
            multiline
            rows={4}
            value={result.dashboard?.embed_code || 'No embed code available'}
            variant="outlined"
            InputProps={{
              readOnly: true,
              sx: { fontFamily: 'monospace', fontSize: '0.875rem' }
            }}
          />
          
          {copySuccess && (
            <Alert severity="success" sx={{ mt: 2 }}>
              Embed code copied to clipboard!
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEmbedDialogOpen(false)}>
            Close
          </Button>
          <Button 
            variant="contained" 
            startIcon={<CopyIcon />}
            onClick={handleCopyEmbed}
          >
            Copy Code
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ResultsDisplay; 